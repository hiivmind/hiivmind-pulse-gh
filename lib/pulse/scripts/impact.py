#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Pure path-scoped integration-currency audit (F5).

No network, no git commands here — this module consumes a pre-collected
`snapshot` data structure (built by a separate collector, see F5 Task 3) and
the `repo_dependencies` section of a relationships config, and classifies
each configured object edge (`lib/references/config-schema.md` § depends_on
edges) as `current`, `stale`, or `unknown`. See
`lib/patterns/headless-contract.md` § impact-result.yaml for the result
shape `ImpactReport.edges` maps onto.

Binding rules (see F5 phase doc for the full rationale):
  - Currency is `git diff tested_sha..remote_head -- watch_paths`, computed
    here from pre-collected changed-file evidence, never git directly.
  - `integration_tested_sha` is committed shared state; local working-tree
    content is never a binding side.
  - A missing or unreachable baseline blocks closed: `state: unknown`,
    never `current`.
  - Legacy string `depends_on[]` entries (bare repo name, no watch
    metadata) produce an `unconfigured_edge` finding (severity low)
    instead of an edges[] verdict — the audit cannot determine their
    currency.
  - Severity inference (breaking vs. additive) is out of scope for this
    module: findings default to a deterministic severity and
    `inferred: False`. An LLM-judgment pass may annotate `severity` and set
    `inferred: True` later, but must never change `state`.

Snapshot shape (produced by the F5 Task 3 collector, consumed verbatim
here):

    {
      "<repo>": {
        "<branch>": {
          "head": "<sha>" | None,             # resolved branch head
          "changed_files_by_base": {
            "<base_sha>": ["<path>", ...],     # files changed base..head
          },
          "base_missing": ["<base_sha>", ...], # bases that could not be
                                                # resolved/diffed (e.g. the
                                                # commit doesn't exist on
                                                # the remote)
        }
      }
    }

A base is treated as unreachable/missing — and the edge as `unknown` — if
it is absent from `changed_files_by_base` entirely, or listed in
`base_missing`, or the repo/branch itself is absent from the snapshot.

Watch-path glob semantics (`watch_paths[]`, matched against snapshot
changed-file paths, POSIX-style forward-slash paths):
  - `?` matches exactly one character, never `/`.
  - `*` matches zero or more characters within a single path segment
    (never crosses a `/`).
  - `**/` matches zero or more whole path segments, so `lib/**/*.py`
    matches both `lib/a/b/c.py` and (zero segments) `lib/top.py`. A
    trailing `/**` likewise matches zero or more trailing segments. A
    bare `**` watch_path matches every path — i.e. "watch the whole
    tree".
  - All other characters match literally.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# --------------------------------------------------------------------------
# Watch-path glob matching
# --------------------------------------------------------------------------

_GLOB_CACHE: dict[str, re.Pattern] = {}


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a watch_paths glob (see module docstring) to a compiled
    regex. `**/` matches zero or more whole path segments (so it also
    matches zero segments — `a/**/b` matches both `a/b` and `a/x/y/b`);
    a trailing `/**` similarly matches zero or more trailing segments; a
    bare `**` (standalone, or a run not anchored by `/` on either side)
    matches any run of characters including `/`. `*` matches within a
    single path segment (never crosses `/`); `?` matches one
    non-separator character; everything else is literal."""
    if pattern in _GLOB_CACHE:
        return _GLOB_CACHE[pattern]
    parts: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i:i + 3] == "**/":
            parts.append("(?:.*/)?")
            i += 3
            continue
        if pattern[i:i + 3] == "/**" and i + 3 == n:
            parts.append("(?:/.*)?")
            i += 3
            continue
        if pattern[i:i + 2] == "**":
            parts.append(".*")
            i += 2
            continue
        c = pattern[i]
        if c == "*":
            parts.append("[^/]*")
            i += 1
        elif c == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(c))
            i += 1
    compiled = re.compile("^" + "".join(parts) + "$")
    _GLOB_CACHE[pattern] = compiled
    return compiled


def _matches_any(path: str, watch_paths: list[str]) -> bool:
    return any(_glob_to_regex(pattern).match(path) for pattern in watch_paths)


def _matched_paths(changed_files: list[str], watch_paths: list[str]) -> list[str]:
    """Deterministic file evidence: sorted, deduplicated matches."""
    hits = {path for path in changed_files if _matches_any(path, watch_paths)}
    return sorted(hits)


# --------------------------------------------------------------------------
# audit()
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class EdgeResult:
    dependent: str
    upstream: str
    watch_branch: str
    state: str  # current | stale | unknown
    tested_sha: str | None
    remote_head: str | None
    changed_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Finding:
    kind: str
    repo: str
    severity: str  # low | medium | high
    detail: str | None = None
    ref: dict | None = None
    inferred: bool = False


@dataclass(frozen=True)
class ImpactReport:
    edges: list[EdgeResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def edges_checked(self) -> int:
        return len(self.edges)

    @property
    def edges_stale(self) -> int:
        return sum(1 for e in self.edges if e.state == "stale")


def _branch_snapshot(snapshot: dict, repo: str, branch: str) -> dict | None:
    repo_snap = snapshot.get(repo)
    if not repo_snap:
        return None
    return repo_snap.get(branch)


def _audit_edge(dependent: str, edge_config: dict, snapshot: dict) -> EdgeResult:
    upstream = edge_config["repo"]
    watch_branch = edge_config["watch_branch"]
    watch_paths = edge_config.get("watch_paths") or []
    tested_sha = edge_config.get("integration_tested_sha")

    branch_snap = _branch_snapshot(snapshot, upstream, watch_branch)
    if branch_snap is None:
        return EdgeResult(dependent, upstream, watch_branch, "unknown",
                           tested_sha, None, [])

    remote_head = branch_snap.get("head")
    changed_files_by_base = branch_snap.get("changed_files_by_base") or {}
    base_missing = set(branch_snap.get("base_missing") or [])

    if (
        remote_head is None
        or tested_sha is None
        or tested_sha in base_missing
        or tested_sha not in changed_files_by_base
    ):
        return EdgeResult(dependent, upstream, watch_branch, "unknown",
                           tested_sha, remote_head, [])

    changed_paths = _matched_paths(changed_files_by_base[tested_sha], watch_paths)
    state = "stale" if changed_paths else "current"
    return EdgeResult(dependent, upstream, watch_branch, state,
                       tested_sha, remote_head, changed_paths)


def audit(relationships: dict, snapshot: dict) -> ImpactReport:
    """Classify every configured `depends_on[]` object edge as
    current/stale/unknown from pre-collected snapshot evidence. Pure: no
    network, no git commands. Legacy string edges produce an
    `unconfigured_edge` finding instead of an edges[] verdict."""
    edges: list[EdgeResult] = []
    findings: list[Finding] = []

    repo_dependencies = (relationships or {}).get("repo_dependencies") or {}
    for dependent, entry in repo_dependencies.items():
        for depends_on in (entry or {}).get("depends_on") or []:
            if isinstance(depends_on, str):
                findings.append(Finding(
                    kind="unconfigured_edge",
                    repo=dependent,
                    severity="low",
                    detail=(
                        f"legacy string depends_on edge to '{depends_on}' "
                        "carries no watch metadata; impact audit cannot "
                        "determine currency"
                    ),
                    inferred=False,
                ))
                continue
            edges.append(_audit_edge(dependent, depends_on, snapshot))

    return ImpactReport(edges=edges, findings=findings)


# --------------------------------------------------------------------------
# mark()
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class MarkerResult:
    status: str  # updated | noop | conflict | not_found
    dependent: str
    upstream: str
    previous_sha: str | None
    new_sha: str | None
    detail: str | None = None


def _find_edge(config: dict, dependent: str, upstream: str) -> dict | None:
    entry = ((config.get("repo_dependencies") or {}).get(dependent)) or {}
    for depends_on in entry.get("depends_on") or []:
        if isinstance(depends_on, dict) and depends_on.get("repo") == upstream:
            return depends_on
    return None


def _atomic_write_yaml(path: Path, data: dict) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except OSError:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except OSError:
                pass
        raise


def mark(path: Path | str, dependent: str, upstream: str, expected_sha: str,
          new_sha: str, tested_at: str) -> MarkerResult:
    """Patch `integration_tested_sha` (and `tested_at`) on the
    `repo_dependencies.<dependent>.depends_on[]` edge whose `repo` ==
    `upstream`, atomically (write temp + rename) and expected-base guarded:

      - current marker == expected_sha  -> apply, status "updated".
      - current marker == new_sha already (the update was already applied,
        e.g. a repeated call with the same arguments) -> no write,
        status "noop". This is what makes repeat calls with the same
        arguments idempotent.
      - anything else (current marker differs from both expected_sha and
        new_sha) -> conflict, no write.
      - dependent/upstream edge not found, or matched entry is a legacy
        string edge -> not_found, no write.

    Comment/structure preservation: this rewrites the file via
    yaml.safe_load/yaml.safe_dump, the same approach `fleet_membership.py`
    uses for its config patches — PyYAML does not round-trip comments, and
    no comment-preserving YAML library (e.g. ruamel.yaml) is a dependency
    elsewhere in this codebase, so a full structural rewrite (not an
    in-place comment-preserving edit) is the consistent choice here.
    """
    path = Path(path)
    config = yaml.safe_load(path.read_text()) or {}

    edge = _find_edge(config, dependent, upstream)
    if edge is None:
        return MarkerResult("not_found", dependent, upstream, None, None,
                             detail=f"no object depends_on edge {dependent} -> {upstream}")

    current_sha = edge.get("integration_tested_sha")

    if current_sha == new_sha:
        return MarkerResult("noop", dependent, upstream, current_sha, new_sha,
                             detail="marker already at new_sha; no write")

    if current_sha != expected_sha:
        return MarkerResult("conflict", dependent, upstream, current_sha, new_sha,
                             detail=f"expected base {expected_sha!r} but found {current_sha!r}")

    edge["integration_tested_sha"] = new_sha
    edge["tested_at"] = tested_at
    _atomic_write_yaml(path, config)
    return MarkerResult("updated", dependent, upstream, current_sha, new_sha)


# --------------------------------------------------------------------------
# propose_marks() / apply_proposals() — close the validation loop
# --------------------------------------------------------------------------
#
# Dispatch alone is never evidence of currency (see Task 4 report and
# `lib/patterns/workflow-execution.md` § Marker Advancement from Workflow-Run
# Evidence). Only a SUCCESSFUL run of the edge's *configured*
# `integration_workflow`, evaluated against the edge's *upstream repo*,
# proposes marker advancement. Everything else — failure, in-progress/aborted,
# cooldown-skipped, an unrelated workflow, an edge with no
# `integration_workflow` configured, or a legacy string edge — proposes
# nothing.
#
# `run_evidence` items are grounded in the workflow-run-result.yaml contract
# (`lib/patterns/headless-contract.md` § workflow-run-result.yaml): `workflow`
# and `outcome` reuse that contract's field names and `outcome` enum
# (success | failure | skipped-cooldown | aborted) verbatim. `repos` on that
# contract is a list (a run can span repos); a proposal is evaluated per
# upstream repo, so evidence here is per-repo: `repo` (one entry of that
# list) and `head_sha` (the commit on `repo` that the run validated — not a
# field the workflow-run contract carries today, since it has no per-repo SHA
# concept; a caller adapting a workflow-run-result.yaml into evidence supplies
# it from the run's known head). `tested_at` carries through to the proposal
# and, ultimately, to `mark()`'s `tested_at` argument.
#
#   run_evidence item shape:
#     {
#       "workflow": <str>,     # workflow identifier, e.g. "ci.yml"
#       "repo": <str>,         # owner/name of the repo the run validated
#       "outcome": <str>,      # success | failure | skipped-cooldown | aborted
#       "head_sha": <str>,     # commit on `repo` validated by this run
#       "tested_at": <str>,    # ISO 8601 timestamp
#     }

@dataclass(frozen=True)
class MarkProposal:
    dependent: str
    upstream: str
    expected_sha: str | None
    new_sha: str
    tested_at: str


def propose_marks(relationships: dict, run_evidence: list[dict]) -> list[MarkProposal]:
    """Join configured object edges to workflow-run evidence and propose
    exact expected-base `mark` calls. Pure: no I/O, no mutation — a proposal
    only becomes a write via `apply_proposals`/`mark`.

    An edge proposes advancement only when ALL hold:
      - the edge is an object edge (legacy string edges carry no
        `integration_workflow` and are never proposed)
      - the edge configures `integration_workflow`
      - a `run_evidence` item's `workflow` matches that configured value
      - that same item's `repo` matches the edge's upstream `repo`
      - that same item's `outcome` == "success" (failure, aborted, and
        skipped-cooldown are all non-evidence — dispatch/attempt alone never
        advances a marker)

    `expected_sha` is the edge's *current* `integration_tested_sha` at
    proposal time (the exact base `mark()` must still see for the write to
    apply) and `new_sha` is the evidence's validated `head_sha`.
    """
    proposals: list[MarkProposal] = []
    repo_dependencies = (relationships or {}).get("repo_dependencies") or {}

    for dependent, entry in repo_dependencies.items():
        for depends_on in (entry or {}).get("depends_on") or []:
            if not isinstance(depends_on, dict):
                continue  # legacy string edge: no watch/workflow metadata
            configured_workflow = depends_on.get("integration_workflow")
            if not configured_workflow:
                continue
            upstream = depends_on.get("repo")
            for evidence in run_evidence:
                if evidence.get("outcome") != "success":
                    continue
                if evidence.get("workflow") != configured_workflow:
                    continue
                if evidence.get("repo") != upstream:
                    continue
                proposals.append(MarkProposal(
                    dependent=dependent,
                    upstream=upstream,
                    expected_sha=depends_on.get("integration_tested_sha"),
                    new_sha=evidence["head_sha"],
                    tested_at=evidence["tested_at"],
                ))

    return proposals


def apply_proposals(path: Path | str, proposals: list[MarkProposal]) -> list[MarkerResult]:
    """Apply each proposal via `mark()`, in order. Each call is independently
    expected-base guarded and idempotent — a conflict or not_found on one
    proposal does not block the rest. Returns one `MarkerResult` per
    proposal, in the same order."""
    return [
        mark(path, proposal.dependent, proposal.upstream,
             proposal.expected_sha, proposal.new_sha, proposal.tested_at)
        for proposal in proposals
    ]


# --------------------------------------------------------------------------
# CLI (thin — orchestration lives in the calling skill/script)
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit_p = sub.add_parser("audit", help="Audit relationships against a snapshot")
    audit_p.add_argument("--relationships", required=True, type=Path)
    audit_p.add_argument("--snapshot", required=True, type=Path)

    mark_p = sub.add_parser("mark", help="Patch an integration_tested_sha marker")
    mark_p.add_argument("--relationships", required=True, type=Path)
    mark_p.add_argument("--dependent", required=True)
    mark_p.add_argument("--upstream", required=True)
    mark_p.add_argument("--expected-sha", required=True)
    mark_p.add_argument("--new-sha", required=True)
    mark_p.add_argument("--tested-at", required=True)

    args = parser.parse_args()

    if args.command == "audit":
        relationships = yaml.safe_load(args.relationships.read_text()) or {}
        snapshot = json.loads(args.snapshot.read_text())
        report = audit(relationships, snapshot)
        print(json.dumps({
            "edges_checked": report.edges_checked,
            "edges_stale": report.edges_stale,
            "edges": [vars(e) for e in report.edges],
            "findings": [vars(f) for f in report.findings],
        }, indent=2))
    elif args.command == "mark":
        result = mark(args.relationships, args.dependent, args.upstream,
                       args.expected_sha, args.new_sha, args.tested_at)
        print(json.dumps(vars(result), indent=2))
        if result.status in ("conflict", "not_found"):
            sys.exit(1)


if __name__ == "__main__":
    main()
