#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Generated-artifact binding audit engine (F7 Task 2).

This module classifies each generated-artifact binding as current,
template-drift, local-customization, conflict, or error from a pre-collected
`snapshot` data structure. It also provides guarded marker advancement for
the manifest (`templates/generated.yaml`) and the collector that builds the
snapshot.

Snapshot shape (produced by `collect()`, consumed verbatim by `audit()`):

    {
      "<repo>": {
        "<branch>": {
          "head": "<sha>" | None,
          "trees": {"<path>": "<tree_sha>" | "ABSENT", ...},
          "blobs": {"<path>": "<blob_sha>" | "ABSENT", ...},
        }
      }
    }

`audit()` is pure: no network, no git commands. `collect()` and `advance()`
are the only I/O paths.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from lib.pulse.scripts.impact import Finding, _atomic_write_yaml
from lib.pulse.scripts.impact_snapshot import (
    default_runner,
    _repo_url,
    _slug,
    _valid_branch,
    _resolve_fetched_head,
    _workdir_ctx,
)

# Sentinel for a path that does not exist at the fetched head.
ABSENT = "ABSENT"

Runner = Callable[..., "subprocess.CompletedProcess[str] | object"]


# --------------------------------------------------------------------------
# Dataclasses
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GeneratedFile:
    path: str
    blob: str


@dataclass(frozen=True)
class ManifestEntry:
    id: str
    source: str
    branch: str
    template_path: str
    template_tree: str
    generator: str
    files: list[GeneratedFile]
    generated_at: str


@dataclass(frozen=True)
class FileResult:
    path: str
    stored_blob: str
    snapshot_blob: str | None
    state: str  # current | changed | missing


@dataclass(frozen=True)
class BindingProposal:
    binding_id: str
    expected_tree: str
    new_tree: str
    files: list[GeneratedFile]
    generated_at: str


@dataclass(frozen=True)
class BindingResult:
    id: str
    state: str  # current | template-drift | local-customization | conflict | error
    source: str
    branch: str
    template_path: str
    stored_tree: str
    snapshot_tree: str | None
    files: list[FileResult]
    proposal: BindingProposal | None = None


@dataclass(frozen=True)
class GeneratedReport:
    bindings: list[BindingResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def bindings_checked(self) -> int:
        return len(self.bindings)

    @property
    def bindings_drift(self) -> int:
        return sum(1 for b in self.bindings if b.state == "template-drift")


@dataclass(frozen=True)
class MarkerResult:
    status: str  # updated | noop | conflict | not_found
    binding_id: str
    previous_tree: str | None
    new_tree: str | None
    detail: str | None = None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _failed(result) -> bool:
    return getattr(result, "returncode", 1) != 0


def _lines(result) -> list[str]:
    stdout = getattr(result, "stdout", "") or ""
    return [line for line in stdout.splitlines() if line.strip()]


# --------------------------------------------------------------------------
# backfill()
# --------------------------------------------------------------------------

def backfill(binding_input: dict, snapshot: dict) -> ManifestEntry:
    """Resolve current tree/blob SHAs for a new binding from `snapshot`."""
    source = binding_input["source"]
    branch = binding_input["branch"]
    repo_snap = snapshot.get(source)
    if repo_snap is None:
        raise ValueError(
            f"binding {binding_input.get('id')!r}: source repo {source!r} "
            f"branch {branch!r} not found in snapshot"
        )
    branch_snap = repo_snap.get(branch)
    if branch_snap is None:
        raise ValueError(
            f"binding {binding_input.get('id')!r}: source repo {source!r} "
            f"branch {branch!r} not found in snapshot"
        )

    template_path = binding_input["template_path"]
    trees = branch_snap.get("trees") or {}
    template_tree = trees.get(template_path)
    if template_tree is None or template_tree == ABSENT:
        raise ValueError(
            f"binding {binding_input.get('id')!r}: template path {template_path!r} "
            "not resolved in snapshot"
        )

    files: list[GeneratedFile] = []
    blobs = branch_snap.get("blobs") or {}
    for f in binding_input.get("files") or []:
        path = f["path"]
        blob = blobs.get(path)
        if blob is None or blob == ABSENT:
            raise ValueError(
                f"binding {binding_input.get('id')!r}: output path {path!r} "
                "not resolved in snapshot"
            )
        files.append(GeneratedFile(path, blob))

    return ManifestEntry(
        id=binding_input["id"],
        source=source,
        branch=branch,
        template_path=template_path,
        template_tree=template_tree,
        generator=binding_input.get("generator", ""),
        files=files,
        generated_at=binding_input.get("generated_at", ""),
    )


# --------------------------------------------------------------------------
# audit()
# --------------------------------------------------------------------------

def _audit_binding(binding: dict, snapshot: dict) -> tuple[BindingResult, Finding | None]:
    binding_id = binding["id"]
    source = binding["source"]
    branch = binding["branch"]
    template_path = binding["template_path"]
    stored_tree = binding.get("template_tree")
    files_config = binding.get("files") or []
    generated_at = binding.get("generated_at", "")

    repo_snap = snapshot.get(source)
    branch_snap = repo_snap.get(branch) if repo_snap else None

    if branch_snap is None or branch_snap.get("head") is None:
        file_results = [
            FileResult(f["path"], f.get("blob"), None, "unknown")
            for f in files_config
        ]
        finding = Finding(
            kind="snapshot_gap",
            repo=source,
            severity="high",
            detail=(
                f"binding {binding_id!r}: repo {source!r} branch {branch!r} "
                "absent from snapshot"
            ),
            inferred=False,
        )
        return BindingResult(
            id=binding_id,
            state="error",
            source=source,
            branch=branch,
            template_path=template_path,
            stored_tree=stored_tree,
            snapshot_tree=None,
            files=file_results,
            proposal=None,
        ), finding

    trees = branch_snap.get("trees") or {}
    blobs = branch_snap.get("blobs") or {}
    snapshot_tree = trees.get(template_path)
    tree_changed = snapshot_tree != stored_tree

    file_results: list[FileResult] = []
    any_blob_changed = False
    any_missing = False

    for f in files_config:
        path = f["path"]
        stored_blob = f.get("blob")
        snapshot_blob = blobs.get(path)
        if snapshot_blob is None or snapshot_blob == ABSENT:
            file_state = "missing"
            any_missing = True
        elif snapshot_blob != stored_blob:
            file_state = "changed"
            any_blob_changed = True
        else:
            file_state = "current"
        file_results.append(
            FileResult(path, stored_blob, snapshot_blob, file_state)
        )

    if any_missing:
        state = "error"
        finding = Finding(
            kind="missing_output",
            repo=source,
            severity="high",
            detail=(
                f"binding {binding_id!r}: output path(s) missing at head: "
                f"{', '.join(fr.path for fr in file_results if fr.state == 'missing')}"
            ),
            ref={"paths": [fr.path for fr in file_results if fr.state == "missing"]},
            inferred=False,
        )
        proposal = None
    elif tree_changed and not any_blob_changed:
        state = "template-drift"
        finding = None
        proposal_files = [
            GeneratedFile(fr.path, fr.snapshot_blob)
            for fr in file_results
        ]
        proposal = BindingProposal(
            binding_id=binding_id,
            expected_tree=stored_tree,
            new_tree=snapshot_tree,
            files=proposal_files,
            generated_at=generated_at,
        )
    elif not tree_changed and any_blob_changed:
        state = "local-customization"
        finding = Finding(
            kind="local_customization",
            repo=source,
            severity="medium",
            detail=f"binding {binding_id!r}: generated file(s) changed locally",
            ref={"paths": [fr.path for fr in file_results if fr.state == "changed"]},
            inferred=False,
        )
        proposal = None
    elif tree_changed and any_blob_changed:
        state = "conflict"
        finding = Finding(
            kind="conflict",
            repo=source,
            severity="high",
            detail=f"binding {binding_id!r}: template drift and local customization",
            inferred=False,
        )
        proposal = None
    else:
        state = "current"
        finding = None
        proposal = None

    return BindingResult(
        id=binding_id,
        state=state,
        source=source,
        branch=branch,
        template_path=template_path,
        stored_tree=stored_tree,
        snapshot_tree=snapshot_tree,
        files=file_results,
        proposal=proposal,
    ), finding


def audit(manifest: dict, snapshot: dict) -> GeneratedReport:
    """Classify every binding in `manifest` against `snapshot`. Pure."""
    bindings: list[BindingResult] = []
    findings: list[Finding] = []

    for binding in (manifest or {}).get("bindings") or []:
        if not isinstance(binding, dict):
            continue
        result, finding = _audit_binding(binding, snapshot or {})
        bindings.append(result)
        if finding is not None:
            findings.append(finding)

    return GeneratedReport(bindings=bindings, findings=findings)


# --------------------------------------------------------------------------
# advance()
# --------------------------------------------------------------------------

def _find_binding(config: dict, binding_id: str) -> dict | None:
    for binding in (config.get("bindings") or []):
        if isinstance(binding, dict) and binding.get("id") == binding_id:
            return binding
    return None


def advance(path: Path | str, binding_id: str, expected_tree: str,
            new_tree: str, files: list[dict], generated_at: str) -> MarkerResult:
    """CAS marker patch on `templates/generated.yaml`.

    Guard rules (mirror impact.mark()):
      - current binding.template_tree == expected_tree -> apply, "updated".
      - current binding.template_tree == new_tree -> "noop" (idempotent).
      - current binding.template_tree != expected_tree and != new_tree ->
        "conflict", no write.
      - binding not found -> "not_found".
    """
    path = Path(path)
    config = yaml.safe_load(path.read_text()) or {}

    binding = _find_binding(config, binding_id)
    if binding is None:
        return MarkerResult(
            "not_found", binding_id, None, None,
            detail=f"binding {binding_id!r} not found in manifest",
        )

    current_tree = binding.get("template_tree")

    if current_tree == new_tree:
        return MarkerResult(
            "noop", binding_id, current_tree, new_tree,
            detail="marker already at new_tree; no write",
        )

    if current_tree != expected_tree:
        return MarkerResult(
            "conflict", binding_id, current_tree, new_tree,
            detail=f"expected tree {expected_tree!r} but found {current_tree!r}",
        )

    binding["template_tree"] = new_tree
    binding["files"] = files
    binding["generated_at"] = generated_at
    _atomic_write_yaml(path, config)
    return MarkerResult("updated", binding_id, current_tree, new_tree)


# --------------------------------------------------------------------------
# collect()
# --------------------------------------------------------------------------

def _watched_bindings(manifest: dict) -> dict[tuple[str, str], list[dict]]:
    """Group bindings by (source, branch) for a single fetch per pair."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    for binding in (manifest or {}).get("bindings") or []:
        if not isinstance(binding, dict):
            continue
        source = binding.get("source")
        branch = binding.get("branch")
        if source and branch:
            grouped.setdefault((source, branch), []).append(binding)
    return grouped


def _resolve_path(run, repo_dir: Path, path: str) -> str:
    """Resolve a path via `git rev-parse FETCH_HEAD:<path>`.

    A path that does not exist at the fetched head resolves to `ABSENT`,
    never raises.
    """
    result = run(["git", "rev-parse", f"FETCH_HEAD:{path}"], repo_dir)
    if _failed(result):
        return ABSENT
    lines = _lines(result)
    return lines[0].strip() if lines else ABSENT


def _collect_branch(run, base_dir: Path, source: str, branch: str,
                    bindings: list[dict]) -> dict:
    """Collect snapshot for one source repo/branch."""
    url = _repo_url(source)
    repo_dir = base_dir / _slug(source, branch)

    init = run(["git", "init", "--bare", "-q", str(repo_dir)], None)
    if _failed(init):
        return {"head": None, "trees": {}, "blobs": {}}

    if not _valid_branch(branch):
        return {"head": None, "trees": {}, "blobs": {}}

    fetch = run(["git", "fetch", "--filter=blob:none", "-q", "--", url, branch],
                repo_dir)
    if _failed(fetch):
        return {"head": None, "trees": {}, "blobs": {}}

    head = _resolve_fetched_head(run, repo_dir)
    if head is None:
        return {"head": None, "trees": {}, "blobs": {}}

    template_paths: set[str] = set()
    file_paths: set[str] = set()
    for binding in bindings:
        template_path = binding.get("template_path")
        if template_path:
            template_paths.add(template_path)
        for f in binding.get("files") or []:
            file_path = f.get("path")
            if file_path:
                file_paths.add(file_path)

    trees: dict[str, str] = {}
    blobs: dict[str, str] = {}
    for path in sorted(template_paths):
        trees[path] = _resolve_path(run, repo_dir, path)
    for path in sorted(file_paths):
        blobs[path] = _resolve_path(run, repo_dir, path)

    return {"head": head, "trees": trees, "blobs": blobs}


def collect(manifest: dict, workdir: str | Path | None = None,
            runner: Runner | None = None) -> dict:
    """Collect the snapshot for every binding in `manifest`.

    Reuses `impact_snapshot.default_runner` and its argv-guard style. One
    fetch is performed per (source, branch) pair; every path is resolved via
    `git rev-parse FETCH_HEAD:<path>`. Paths that do not exist at the head
    resolve to `ABSENT` and drive `missing_output` findings in `audit()`.
    """
    run = runner or default_runner
    grouped = _watched_bindings(manifest)
    if not grouped:
        return {}

    snapshot: dict = {}
    with _workdir_ctx(workdir) as base_dir:
        for source, branch in sorted(grouped):
            bindings = grouped[(source, branch)]
            branch_snap = _collect_branch(run, base_dir, source, branch, bindings)
            snapshot.setdefault(source, {})[branch] = branch_snap
    return snapshot


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit_p = sub.add_parser("audit", help="Audit generated-artifact bindings")
    audit_p.add_argument("--manifest", required=True, type=Path)
    audit_p.add_argument("--snapshot", required=True, type=Path)

    mark_p = sub.add_parser("advance", help="Advance a binding marker")
    mark_p.add_argument("--manifest", required=True, type=Path)
    mark_p.add_argument("--binding-id", required=True)
    mark_p.add_argument("--expected-tree", required=True)
    mark_p.add_argument("--new-tree", required=True)
    mark_p.add_argument("--generated-at", required=True)
    mark_p.add_argument("--files", required=True, type=json.loads)

    args = parser.parse_args()

    if args.command == "audit":
        manifest = yaml.safe_load(args.manifest.read_text()) or {}
        snapshot = json.loads(args.snapshot.read_text())
        report = audit(manifest, snapshot)
        print(json.dumps({
            "bindings_checked": report.bindings_checked,
            "bindings_drift": report.bindings_drift,
            "bindings": [vars(b) for b in report.bindings],
            "findings": [vars(f) for f in report.findings],
        }, indent=2))
    elif args.command == "advance":
        result = advance(args.manifest, args.binding_id, args.expected_tree,
                         args.new_tree, args.files, args.generated_at)
        print(json.dumps(vars(result), indent=2))


if __name__ == "__main__":
    main()
