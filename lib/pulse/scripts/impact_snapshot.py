#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Remote-evidence collector for the F5 impact audit (F5 Task 3).

Builds the `snapshot` data structure `impact.py::audit()` consumes verbatim
— see that module's docstring for the exact shape. This module is the only
place that touches git/network for the impact audit; `impact.py` itself
stays pure.

Binding rules (mirrors the F5 phase doc; see impact.py for the audit side):
  - Currency evidence comes from remote refs only. Local working-tree
    content is never a binding side — this collector never reads a local
    checkout's working tree, only bare/partial clones of the *remote*
    branch and base commits.
  - git is the collector's default and its fallback: branch heads are
    resolved via `git ls-remote`, and changed-path evidence via a
    filtered (`--filter=blob:none`) temporary bare fetch plus
    `git diff --name-only <tested_sha> <head>`. An optional pre-supplied
    `known_heads` evidence map (e.g. from a cheaper cached source, such as
    the F0 Nave evidence layer or poll.py's `branch_heads` trigger state)
    may short-circuit the `git ls-remote` head-resolution round trip, but
    never substitutes for the git diff itself — changed-path evidence is
    always computed by this module, never trusted from an external source.
    Likewise the diff endpoint itself is never taken from `known_heads`
    directly: after fetching the branch, this module resolves the actual
    fetched tip (`git rev-parse FETCH_HEAD`) and diffs against *that* — a
    stale cached head must never under-report staleness.
  - A tested SHA that cannot be fetched/resolved on the remote is recorded
    in `base_missing` for that repo/branch, never guessed or omitted
    silently.

All git invocations go through an injectable `runner(argv, cwd) ->
CompletedProcess-like` seam (`.returncode`, `.stdout`, `.stderr`), so tests
can run hermetically against a fake runner — no real git process, no
network. The default runner shells out to the real `git` binary.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import yaml

Runner = Callable[..., "subprocess.CompletedProcess[str] | object"]


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def default_runner(argv: list[str], cwd: str | Path | None = None):
    """Real git invocation. Never called from tests — those inject a fake
    runner instead."""
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _failed(result) -> bool:
    return getattr(result, "returncode", 1) != 0


def _lines(result) -> list[str]:
    stdout = getattr(result, "stdout", "") or ""
    return [line for line in stdout.splitlines() if line.strip()]


# --------------------------------------------------------------------------
# relationships -> watched edges
# --------------------------------------------------------------------------

def _edges(relationships: dict):
    """Yield (upstream_repo, watch_branch, integration_tested_sha) for every
    object depends_on edge (F5 Task 1 shape). Legacy string edges carry no
    watch metadata and are skipped — they never resolve to a currency
    verdict (see impact.py's `unconfigured_edge` finding)."""
    repo_dependencies = (relationships or {}).get("repo_dependencies") or {}
    for entry in repo_dependencies.values():
        for depends_on in (entry or {}).get("depends_on") or []:
            if not isinstance(depends_on, dict):
                continue
            repo = depends_on.get("repo")
            branch = depends_on.get("watch_branch")
            if repo and branch:
                yield repo, branch, depends_on.get("integration_tested_sha")


def _watched_bases(relationships: dict) -> dict[tuple[str, str], set[str]]:
    """Every watched (repo, branch) mapped to the union of tested_sha values
    any dependent has recorded against it. A branch with no tested_sha yet
    (edge never marked) still gets a snapshot entry with an empty base set,
    so its `head` is available once the edge is first marked."""
    grouped: dict[tuple[str, str], set[str]] = {}
    for repo, branch, tested_sha in _edges(relationships):
        key = (repo, branch)
        grouped.setdefault(key, set())
        if tested_sha:
            grouped[key].add(tested_sha)
    return grouped


# --------------------------------------------------------------------------
# git evidence
# --------------------------------------------------------------------------

def _repo_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _slug(*parts: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", "_".join(parts))


# Config-sourced values (`watch_branch`, `integration_tested_sha`) are never
# trusted as git argv positionals as-is — a value starting with `-` could be
# parsed as an option by `git ls-remote`/`git fetch`/`git diff`. Strict regex
# validation is the primary guard (see module docstring); `git diff` in
# particular takes two bare revision positionals with no clean place for a
# `--` separator, so regex validation is its *only* guard. Values that fail
# validation are never passed to git — they're recorded as missing/failed
# the same way an unresolvable remote ref would be.
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_BRANCH_RE = re.compile(r"^[^\s-][^\s]*$")


def _valid_sha(value: str | None) -> bool:
    return bool(value) and bool(_SHA_RE.match(value))


def _valid_branch(value: str | None) -> bool:
    return bool(value) and bool(_BRANCH_RE.match(value))


def _resolve_head(run: Runner, repo: str, branch: str) -> str | None:
    result = run(["git", "ls-remote", "--", _repo_url(repo), f"refs/heads/{branch}"], None)
    if _failed(result):
        return None
    lines = _lines(result)
    if not lines:
        return None
    fields = lines[0].split()
    return fields[0] if fields else None


def _resolve_fetched_head(run: Runner, repo_dir: Path) -> str | None:
    """Resolve the actual tip just fetched into `repo_dir`. This — never a
    caller-supplied `known_head` — is the diff endpoint and the reported
    `head`: `known_heads` may only skip the `git ls-remote` round trip, it
    never substitutes for the true current remote head, which can have
    moved since the caller's cache was populated."""
    result = run(["git", "rev-parse", "FETCH_HEAD"], repo_dir)
    if _failed(result):
        return None
    lines = _lines(result)
    return lines[0].strip() if lines else None


def _collect_branch(run: Runner, base_dir: Path, repo: str, branch: str,
                     tested_shas: set[str], known_head: str | None) -> dict:
    url = _repo_url(repo)
    repo_dir = base_dir / _slug(repo, branch)

    init = run(["git", "init", "--bare", "-q", str(repo_dir)], None)
    if _failed(init):
        return {"head": None, "changed_files_by_base": {},
                 "base_missing": sorted(tested_shas)}

    if not _valid_branch(branch):
        return {"head": None, "changed_files_by_base": {},
                 "base_missing": sorted(tested_shas)}

    if known_head is not None:
        head_hint = known_head
    else:
        head_hint = _resolve_head(run, repo, branch)
        if head_hint is None:
            return {"head": None, "changed_files_by_base": {},
                     "base_missing": sorted(tested_shas)}

    fetch_head = run(["git", "fetch", "--filter=blob:none", "-q", "--", url, branch], repo_dir)
    if _failed(fetch_head):
        return {"head": head_hint, "changed_files_by_base": {},
                 "base_missing": sorted(tested_shas)}

    # The real diff endpoint: resolved fresh from the fetch just performed,
    # never trusted from `known_head`/`ls-remote` alone — those may be stale
    # relative to the tip this fetch actually retrieved.
    head = _resolve_fetched_head(run, repo_dir)
    if head is None:
        return {"head": head_hint, "changed_files_by_base": {},
                 "base_missing": sorted(tested_shas)}

    changed_files_by_base: dict[str, list[str]] = {}
    base_missing: list[str] = []

    for tested_sha in sorted(tested_shas):
        if not _valid_sha(tested_sha):
            base_missing.append(tested_sha)
            continue
        fetch_base = run(["git", "fetch", "--filter=blob:none", "-q", "--", url, tested_sha],
                          repo_dir)
        if _failed(fetch_base):
            base_missing.append(tested_sha)
            continue
        diff = run(["git", "diff", "--name-only", tested_sha, head], repo_dir)
        if _failed(diff):
            base_missing.append(tested_sha)
            continue
        changed_files_by_base[tested_sha] = sorted(set(_lines(diff)))

    return {
        "head": head,
        "changed_files_by_base": changed_files_by_base,
        "base_missing": sorted(base_missing),
    }


@contextlib.contextmanager
def _workdir_ctx(workdir: str | Path | None):
    if workdir is not None:
        path = Path(workdir)
        path.mkdir(parents=True, exist_ok=True)
        yield path
    else:
        with tempfile.TemporaryDirectory(prefix="pulse-impact-") as tmp:
            yield Path(tmp)


# --------------------------------------------------------------------------
# collect()
# --------------------------------------------------------------------------

def collect(relationships: dict, workdir: str | Path | None = None,
            runner: Runner | None = None,
            known_heads: dict[str, dict[str, str]] | None = None) -> dict:
    """Collect the audit snapshot for every watched object depends_on edge
    in `relationships`. Shape matches `impact.py`'s module docstring
    exactly: `{repo: {branch: {head, changed_files_by_base, base_missing}}}`.

    `workdir` — directory for the temporary bare clones; a fresh temp dir
    is created and cleaned up when omitted.

    `runner` — injectable `runner(argv, cwd) -> CompletedProcess-like` git
    seam; defaults to `default_runner` (real git). Tests always inject a
    fake.

    `known_heads` — optional pre-resolved `{repo: {branch: head_sha}}`
    evidence (e.g. poll.py's `branch_heads` trigger state, or a cached F0
    evidence layer). When a (repo, branch) pair is present here, `git
    ls-remote` is skipped — this saves a round trip only. The actual diff
    endpoint and reported `head` are always resolved fresh from the branch
    fetch this module performs (`git rev-parse FETCH_HEAD`), never taken
    from `known_heads` directly: a cached head can be stale relative to the
    remote's true current tip, and diffing against a stale head would
    under-report staleness. `known_heads` never supplies path evidence.
    """
    run = runner or default_runner
    known_heads = known_heads or {}
    watched = _watched_bases(relationships)
    if not watched:
        return {}

    snapshot: dict = {}
    with _workdir_ctx(workdir) as base_dir:
        for repo, branch in sorted(watched):
            tested_shas = watched[(repo, branch)]
            known_head = (known_heads.get(repo) or {}).get(branch)
            branch_snap = _collect_branch(run, base_dir, repo, branch, tested_shas,
                                          known_head)
            snapshot.setdefault(repo, {})[branch] = branch_snap
    return snapshot


# --------------------------------------------------------------------------
# CLI (thin — orchestration lives in the calling skill/script)
# --------------------------------------------------------------------------

def _load_known_heads(path: Path) -> dict:
    """Load a `--known-heads` evidence file. Accepts either YAML or JSON —
    `yaml.safe_load` parses both (JSON is a YAML subset) — so a caller can
    hand this a YAML section extracted from poll-state.yaml (e.g.
    `.state.branch_heads`) or a hand-authored JSON file without caring which
    serialization it used."""
    return yaml.safe_load(path.read_text()) or {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relationships", required=True, type=Path)
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--known-heads", type=Path, default=None,
                        help="Optional YAML or JSON {repo: {branch: head_sha}} evidence "
                             "file (e.g. poll-state.yaml's .state.branch_heads section)")
    args = parser.parse_args()

    relationships = yaml.safe_load(args.relationships.read_text()) or {}
    known_heads = None
    if args.known_heads is not None:
        known_heads = _load_known_heads(args.known_heads)

    snapshot = collect(relationships, workdir=args.workdir, known_heads=known_heads)
    print(json.dumps(snapshot, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
