#!/usr/bin/env python3
"""Collect pushed plan-document and GitHub issue evidence for F8 sync.

All git operations pass through ``runner`` and all GitHub reads pass through
``gh_api``.  A local checkout is only inspected for dirty/ahead *metadata*;
its document content is never an input to reconciliation.
"""
from __future__ import annotations

import contextlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from lib.pulse.scripts.impact_snapshot import (
    _slug,
    _valid_branch,
    _valid_sha,
    default_runner,
)
from lib.pulse.scripts.plan_sync import BoundDocument, parse_document


Runner = Callable[..., object]
GhApi = Callable[[str], Any]

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class SnapshotFinding:
    kind: str
    repo: str
    severity: str
    detail: str | None = None
    path: str | None = None
    new_path: str | None = None


@dataclass(frozen=True)
class DocumentSnapshot:
    binding: dict[str, Any]
    repo: str
    branch: str
    path: str
    head: str | None
    blob: str | None
    state: str  # in_sync | changed | excluded | error
    document: BoundDocument | None = None
    base_body: str | None = None
    github: dict[str, Any] | None = None
    milestones: tuple[str, ...] = ()


@dataclass(frozen=True)
class SyncSnapshot:
    documents: tuple[DocumentSnapshot, ...]
    findings: tuple[SnapshotFinding, ...]


def _failed(result: object) -> bool:
    return getattr(result, "returncode", 1) != 0


def _stdout(result: object) -> str:
    return (getattr(result, "stdout", "") or "").strip()


def _valid_repo(value: Any) -> bool:
    return isinstance(value, str) and bool(_REPO_RE.fullmatch(value))


def _valid_path(value: Any) -> bool:
    """Accept ordinary repository-relative paths only.

    The revision passed to ``git rev-parse`` is formed as ``FETCH_HEAD:path``;
    it cannot use ``--`` without changing git's meaning, so reject values that
    could change revision parsing instead.
    """
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("-")
        and not value.startswith("/")
        and "\x00" not in value
        and ":" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def _repo_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _sync(binding: dict[str, Any]) -> dict[str, Any]:
    nested = binding.get("sync")
    return nested if isinstance(nested, dict) else binding


def _binding_values(binding: dict[str, Any]) -> tuple[str | None, str | None, str | None, dict[str, Any]]:
    return binding.get("repo"), binding.get("branch"), binding.get("path"), _sync(binding)


def _is_local_checkout(run: Runner, workdir: str | Path | None) -> bool:
    if workdir is None:
        return False
    result = run(["git", "rev-parse", "--is-inside-work-tree"], Path(workdir))
    return not _failed(result) and _stdout(result).lower() == "true"


@contextlib.contextmanager
def _bare_workdir(workdir: str | Path | None, local_checkout: bool) -> Iterator[Path]:
    """Use a supplied non-repository directory, or an isolated temp bare repo.

    A local checkout is never repurposed as the fetch destination.
    """
    if workdir is not None and not local_checkout:
        yield Path(workdir)
        return
    with tempfile.TemporaryDirectory(prefix="pulse-plan-sync-") as temp:
        yield Path(temp)


def _resolve_head(run: Runner, repo_dir: Path) -> str | None:
    result = run(["git", "rev-parse", "FETCH_HEAD"], repo_dir)
    head = _stdout(result)
    return head if not _failed(result) and _valid_sha(head) else None


def _resolve_blob(run: Runner, repo_dir: Path, path: str) -> str | None:
    result = run(["git", "rev-parse", f"FETCH_HEAD:{path}"], repo_dir)
    blob = _stdout(result)
    return blob if not _failed(result) and _valid_sha(blob) else None


def _read_blob(run: Runner, repo_dir: Path, blob: str) -> str | None:
    if not _valid_sha(blob):
        return None
    result = run(["git", "cat-file", "blob", blob], repo_dir)
    # Blob bytes are merge inputs: unlike ref output, a trailing newline is
    # significant and must not be normalized away.
    return (getattr(result, "stdout", "") or "") if not _failed(result) else None


def _rename_target(run: Runner, repo_dir: Path, path: str) -> str | None:
    result = run(
        ["git", "log", "--follow", "--format=%H", "--name-only", "--", path], repo_dir
    )
    if _failed(result):
        return None
    for line in _stdout(result).splitlines():
        candidate = line.strip()
        if candidate != path and not _valid_sha(candidate) and _valid_path(candidate):
            return candidate
    return None


def _local_dirty(run: Runner, workdir: Path, path: str) -> bool:
    result = run(["git", "status", "--porcelain", "--", path], workdir)
    return not _failed(result) and bool(_stdout(result))


def _local_ahead(run: Runner, workdir: Path, head: str) -> bool:
    if not _valid_sha(head):
        return False
    result = run(["git", "rev-list", "--count", f"{head}..HEAD"], workdir)
    try:
        return not _failed(result) and int(_stdout(result) or "0") > 0
    except ValueError:
        return False


def _github_snapshot(sync: dict[str, Any], gh_api: GhApi | None) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Read and normalize the V1 issue state exclusively through ``gh_api``."""
    if gh_api is None:
        return None, ()
    issue_ref = sync.get("issue") or {}
    issue_repo = issue_ref.get("repo") if isinstance(issue_ref, dict) else None
    number = issue_ref.get("number") if isinstance(issue_ref, dict) else None
    if not _valid_repo(issue_repo) or isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        return None, ()
    issue = gh_api(f"/repos/{issue_repo}/issues/{number}") or {}
    catalog = gh_api(f"/repos/{issue_repo}/milestones?state=all&per_page=100") or []
    if not isinstance(issue, dict):
        return None, ()
    assignees = sorted({a.get("login") for a in issue.get("assignees") or [] if isinstance(a, dict) and a.get("login")})
    milestone = issue.get("milestone") or {}
    github = {
        "title": issue.get("title"),
        "body": issue.get("body"),
        "state": issue.get("state"),
        "assignees": assignees,
        "milestone": milestone.get("title") if isinstance(milestone, dict) else None,
    }
    milestones = tuple(sorted({m.get("title") for m in catalog if isinstance(m, dict) and m.get("title")})) if isinstance(catalog, list) else ()
    return github, milestones


def _error(binding: dict[str, Any], repo: str, branch: str, path: str, head: str | None,
           detail: str) -> tuple[DocumentSnapshot, SnapshotFinding]:
    return (
        DocumentSnapshot(binding, repo, branch, path, head, None, "error"),
        SnapshotFinding("snapshot_error", repo, "high", detail=detail, path=path),
    )


def collect(bindings, workdir=None, runner=default_runner, gh_api=None) -> SyncSnapshot:
    """Collect only pushed document blobs and injected GitHub API evidence.

    ``bindings`` are mappings with ``repo``, ``branch``, ``path``, and either
    a nested ``sync`` mapping or the sync fields at top level.  Failed blob
    resolution remains explicit error evidence; it is never treated as a
    no-op.  Local dirty/ahead documents are excluded before reconciliation.
    """
    raw_bindings = [item for item in (bindings or []) if isinstance(item, dict)]
    run: Runner = runner
    local_checkout = _is_local_checkout(run, workdir)
    local_dir = Path(workdir) if local_checkout and workdir is not None else None
    documents: list[DocumentSnapshot] = []
    findings: list[SnapshotFinding] = []

    pending: list[dict[str, Any]] = []
    for binding in raw_bindings:
        repo, branch, path, _ = _binding_values(binding)
        if not (_valid_repo(repo) and _valid_branch(branch) and _valid_path(path)):
            doc, finding = _error(binding, str(repo or ""), str(branch or ""), str(path or ""), None,
                                  "invalid document repository, branch, or path")
            documents.append(doc)
            findings.append(finding)
        elif local_dir is not None and _local_dirty(run, local_dir, path):
            documents.append(DocumentSnapshot(binding, repo, branch, path, None, None, "excluded"))
            findings.append(SnapshotFinding("dirty_doc", repo, "medium", path=path,
                                            detail="local document changes must be pushed before sync"))
        else:
            pending.append(binding)

    with _bare_workdir(workdir, local_checkout) as base_dir:
        for binding in pending:
            repo, branch, path, sync = _binding_values(binding)
            assert isinstance(repo, str) and isinstance(branch, str) and isinstance(path, str)
            repo_dir = base_dir / _slug(repo, branch)
            if _failed(run(["git", "init", "--bare", "-q", "--", str(repo_dir)], None)):
                doc, finding = _error(binding, repo, branch, path, None, "could not initialize bare repository")
                documents.append(doc)
                findings.append(finding)
                continue
            if _failed(run(["git", "fetch", "--filter=blob:none", "-q", "--", _repo_url(repo), branch], repo_dir)):
                doc, finding = _error(binding, repo, branch, path, None, "could not fetch pushed branch")
                documents.append(doc)
                findings.append(finding)
                continue
            head = _resolve_head(run, repo_dir)
            if head is None:
                doc, finding = _error(binding, repo, branch, path, None, "could not resolve fetched head")
                documents.append(doc)
                findings.append(finding)
                continue
            if local_dir is not None and _local_ahead(run, local_dir, head):
                documents.append(DocumentSnapshot(binding, repo, branch, path, head, None, "excluded"))
                findings.append(SnapshotFinding("local_ahead", repo, "medium", path=path,
                                                detail="local commits must be pushed before sync"))
                continue
            blob = _resolve_blob(run, repo_dir, path)
            if blob is None:
                new_path = _rename_target(run, repo_dir, path)
                documents.append(DocumentSnapshot(binding, repo, branch, path, head, None, "excluded"))
                findings.append(SnapshotFinding(
                    "rename_detected" if new_path else "snapshot_error", repo,
                    "medium" if new_path else "high", path=path, new_path=new_path,
                    detail=(f"document was renamed to {new_path}; update its binding" if new_path
                            else "document path is absent from pushed head"),
                ))
                continue
            base = sync.get("base") if isinstance(sync, dict) else None
            base_blob = base.get("blob") if isinstance(base, dict) else None
            if blob == base_blob:
                documents.append(DocumentSnapshot(binding, repo, branch, path, head, blob, "in_sync"))
                continue
            document_text = _read_blob(run, repo_dir, blob)
            base_text = _read_blob(run, repo_dir, base_blob) if isinstance(base_blob, str) else None
            if document_text is None or base_text is None:
                doc, finding = _error(binding, repo, branch, path, head, "document or body-base blob is unavailable")
                documents.append(doc)
                findings.append(finding)
                continue
            # The base body base is the body of the reconciled base document, not
            # its raw blob — compute() compares it against the current doc's body
            # (frontmatter-stripped), so the base must be stripped identically.
            base_body = parse_document(base_text).body
            github, milestones = _github_snapshot(sync, gh_api)
            documents.append(DocumentSnapshot(
                binding, repo, branch, path, head, blob, "changed", parse_document(document_text),
                base_body, github, milestones,
            ))

    return SyncSnapshot(tuple(documents), tuple(findings))
