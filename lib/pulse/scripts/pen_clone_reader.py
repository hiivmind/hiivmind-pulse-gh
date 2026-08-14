#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Reader over a pen's local repo clones, driven by an exact repo -> path map.

Implements the three injectable reader seams consumed by `pen_orchestrator.execute`:
- `read_repo_head(repo)` -> SHA string via `git rev-parse HEAD`
- `read_repo_file(repo, path)` -> file content bytes
- `read_repo_changed_paths(repo)` -> repo-relative changed paths tuple (modified, added, deleted, untracked)

The caller supplies the exact `repo -> clone path` map (e.g. from `pen_status`/
`pen_list --json`'s `clone_path` per repo entry) — this module derives nothing.
Fails closed loudly with `PenCloneReaderError` if the map does not exactly cover
`selection`, if two repos resolve to the same canonical filesystem path, if any
selected repo's checkout is absent/not a git worktree, or (when the optional
identity checks are supplied) if a repo's `origin` remote, current branch, or
HEAD does not match the expected value.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


class PenCloneReaderError(ValueError):
    """Raised when clone-path-map coverage or repo clone identity validation fails."""


@dataclass(frozen=True)
class PenCloneReaders:
    """Container holding the three reader seams for pen_orchestrator.execute."""

    read_repo_head: Callable[[str], str]
    read_repo_file: Callable[[str, str], bytes]
    read_repo_changed_paths: Callable[[str], tuple[str, ...]]


_SSH_GITHUB_REMOTE = re.compile(
    r"git@github\.com:(?P<owner>[^/:?#\s]+)/(?P<name>[^/:?#\s]+?)(?:\.git)?"
)
_HTTPS_GITHUB_REMOTE = re.compile(
    r"https://github\.com/(?P<owner>[^/:?#\s]+)/(?P<name>[^/:?#\s]+?)(?:\.git)?/?"
)


def _normalize_remote_url(url: str) -> str:
    """Normalize a documented GitHub SSH or HTTPS remote to ``owner/name``."""
    trimmed = url.strip()
    match = _SSH_GITHUB_REMOTE.fullmatch(trimmed)
    if match is None:
        match = _HTTPS_GITHUB_REMOTE.fullmatch(trimmed)
    if match is None:
        raise PenCloneReaderError(
            f"Unsupported remote URL {url!r}; expected git@github.com:owner/name.git "
            "or https://github.com/owner/name.git"
        )
    return f"{match.group('owner')}/{match.group('name')}"


def make_pen_clone_reader(
    clone_paths: dict[str, str],
    selection: Sequence[str],
    *,
    expected_remotes: dict[str, str] | None = None,
    expected_branch: str | None = None,
    expected_heads: dict[str, str] | None = None,
) -> PenCloneReaders:
    """Validate the clone-path map and selected repos up front, returning the 3 reader callables.

    Raises PenCloneReaderError if:
    - `clone_paths` does not exactly cover `selection` (missing or extra entries)
    - two repo keys resolve to the same canonical filesystem path
    - any repo in selection is invalid, missing, or not a git worktree
    - `expected_remotes` is given but does not cover every selected repo, or any
      repo's `origin` remote does not normalize to the expected `owner/name`
      (or the remote cannot be read)
    - `expected_branch` is given and any repo's current branch differs
    - `expected_heads` is given but does not cover every selected repo, or any
      repo's HEAD differs from the expected SHA
    """
    provided = set(clone_paths)
    required = set(selection)
    missing = required - provided
    if missing:
        raise PenCloneReaderError(
            f"clone_paths not found for repos in selection: {sorted(missing)}"
        )
    extra = provided - required
    if extra:
        raise PenCloneReaderError(
            f"clone_paths contains repos not found in selection: {sorted(extra)}"
        )

    resolved_paths: dict[str, Path] = {}
    canonical_owners: dict[Path, str] = {}
    for repo in selection:
        repo_dir = Path(clone_paths[repo])
        canonical = repo_dir.resolve()
        if canonical in canonical_owners:
            raise PenCloneReaderError(
                f"Duplicate canonical clone path {canonical} for repos "
                f"{canonical_owners[canonical]!r} and {repo!r}"
            )
        canonical_owners[canonical] = repo

        if not repo_dir.exists() or not repo_dir.is_dir():
            raise PenCloneReaderError(
                f"Repo clone for {repo!r} not found at {repo_dir}"
            )
        git_dir = repo_dir / ".git"
        if not git_dir.exists():
            raise PenCloneReaderError(
                f"Repo clone for {repo!r} at {repo_dir} is not a git worktree (missing .git)"
            )
        resolved_paths[repo] = repo_dir

    def read_repo_head(repo: str) -> str:
        if repo not in resolved_paths:
            raise KeyError(f"Unknown or unvalidated repo {repo!r}")
        repo_dir = resolved_paths[repo]
        res = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise FileNotFoundError(
                f"Could not read HEAD for repo {repo!r}: {res.stderr.strip()}"
            )
        return res.stdout.strip()

    def read_repo_file(repo: str, path: str) -> bytes:
        if repo not in resolved_paths:
            raise KeyError(f"Unknown or unvalidated repo {repo!r}")
        repo_dir = resolved_paths[repo]
        target_path = (repo_dir / path).resolve()
        resolved_repo_dir = repo_dir.resolve()
        try:
            target_path.relative_to(resolved_repo_dir)
        except ValueError:
            raise FileNotFoundError(
                f"Path {path!r} traverses outside repo directory for {repo!r}"
            )
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"File {path!r} not found in repo {repo!r}")
        return target_path.read_bytes()

    def read_repo_changed_paths(repo: str) -> tuple[str, ...]:
        if repo not in resolved_paths:
            raise KeyError(f"Unknown or unvalidated repo {repo!r}")
        repo_dir = resolved_paths[repo]
        res = subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "-z",
            ],
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"Could not read status for repo {repo!r}: {res.stderr.decode('utf-8', errors='replace').strip()}"
            )

        changed_paths: set[str] = set()
        parts = res.stdout.split(b"\x00")
        idx = 0
        while idx < len(parts):
            part = parts[idx]
            idx += 1
            if not part:
                continue
            if len(part) < 3:
                continue
            status_code = part[:2].decode("utf-8", errors="replace")
            rel_path = part[3:].decode("utf-8", errors="replace")
            changed_paths.add(rel_path)

            if "R" in status_code or "C" in status_code:
                if idx < len(parts):
                    orig_path = parts[idx].decode("utf-8", errors="replace")
                    idx += 1
                    if orig_path:
                        changed_paths.add(orig_path)

        return tuple(sorted(changed_paths))

    if expected_remotes is not None:
        missing = set(selection) - set(expected_remotes)
        if missing:
            raise PenCloneReaderError(
                f"expected_remotes missing repos in selection: {sorted(missing)}"
            )
        for repo in selection:
            repo_dir = resolved_paths[repo]
            expected = expected_remotes[repo]
            res = subprocess.run(
                ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                raise PenCloneReaderError(
                    f"Could not read origin remote for repo {repo!r}: {res.stderr.strip()}"
                )
            remote_url = res.stdout.strip()
            try:
                actual = _normalize_remote_url(remote_url)
            except PenCloneReaderError as exc:
                raise PenCloneReaderError(
                    f"Repo {repo!r} has unsupported origin remote {remote_url!r}: {exc}"
                ) from exc
            if actual != expected:
                raise PenCloneReaderError(
                    f"Repo {repo!r} origin remote mismatch: expected {expected!r}, got {actual!r}"
                )

    if expected_branch is not None:
        for repo in selection:
            repo_dir = resolved_paths[repo]
            res = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                raise PenCloneReaderError(
                    f"Could not read current branch for repo {repo!r}: {res.stderr.strip()}"
                )
            actual_branch = res.stdout.strip()
            if actual_branch != expected_branch:
                raise PenCloneReaderError(
                    f"Repo {repo!r} branch mismatch: expected {expected_branch!r}, got {actual_branch!r}"
                )

    if expected_heads is not None:
        missing = set(selection) - set(expected_heads)
        if missing:
            raise PenCloneReaderError(
                f"expected_heads missing repos in selection: {sorted(missing)}"
            )
        for repo in selection:
            expected_sha = expected_heads[repo]
            actual_sha = read_repo_head(repo)
            if actual_sha != expected_sha:
                raise PenCloneReaderError(
                    f"Repo {repo!r} HEAD mismatch: expected {expected_sha!r}, got {actual_sha!r}"
                )

    return PenCloneReaders(
        read_repo_head=read_repo_head,
        read_repo_file=read_repo_file,
        read_repo_changed_paths=read_repo_changed_paths,
    )
