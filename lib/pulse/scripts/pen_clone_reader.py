#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Reader over a pen's local repo clones driven by a defined clone-root source.

Implements the three injectable reader seams consumed by `pen_orchestrator.execute`:
- `read_repo_head(repo)` -> SHA string via `git rev-parse HEAD`
- `read_repo_file(repo, path)` -> file content bytes
- `read_repo_changed_paths(repo)` -> repo-relative changed paths tuple (modified, added, deleted, untracked)

The clone-root contract resolves clone root from:
1. `clone_root` argument if provided to `make_pen_clone_reader`
2. `PULSE_PEN_ROOT` environment variable
Per-repo layout is expected at `{clone_root}/{owner}/{name}` for repo `owner/name`.
Fails closed loudly with `PenCloneReaderError` if clone_root is unset, missing, or if any selected repo's checkout is absent/not a git worktree.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


class PenCloneReaderError(ValueError):
    """Raised when clone root or repo clone validation fails."""


@dataclass(frozen=True)
class PenCloneReaders:
    """Container holding the three reader seams for pen_orchestrator.execute."""

    read_repo_head: Callable[[str], str]
    read_repo_file: Callable[[str, str], bytes]
    read_repo_changed_paths: Callable[[str], tuple[str, ...]]


def make_pen_clone_reader(
    clone_root: str | Path | None = None,
    selection: Sequence[str] = (),
) -> PenCloneReaders:
    """Validate clone root and selected repos up front, returning the 3 reader callables.

    Raises PenCloneReaderError if:
    - clone_root is unset and PULSE_PEN_ROOT environment variable is not set
    - resolved clone root directory does not exist
    - any repo in selection is invalid, missing, or not a git worktree
    """
    if clone_root is not None:
        root_path = Path(clone_root)
    elif "PULSE_PEN_ROOT" in os.environ:
        root_path = Path(os.environ["PULSE_PEN_ROOT"])
    else:
        raise PenCloneReaderError(
            "clone_root was not provided and PULSE_PEN_ROOT environment variable is not set"
        )

    if not root_path.exists() or not root_path.is_dir():
        raise PenCloneReaderError(
            f"clone_root directory does not exist or is not a directory: {root_path}"
        )

    clone_paths: dict[str, Path] = {}
    for repo in selection:
        parts = repo.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise PenCloneReaderError(f"Invalid repo format {repo!r}; expected 'owner/name'")
        owner, name = parts
        repo_dir = root_path / owner / name
        if not repo_dir.exists() or not repo_dir.is_dir():
            raise PenCloneReaderError(
                f"Repo clone for {repo!r} not found at {repo_dir}"
            )
        git_dir = repo_dir / ".git"
        if not git_dir.exists():
            raise PenCloneReaderError(
                f"Repo clone for {repo!r} at {repo_dir} is not a git worktree (missing .git)"
            )
        clone_paths[repo] = repo_dir

    def read_repo_head(repo: str) -> str:
        if repo not in clone_paths:
            raise KeyError(f"Unknown or unvalidated repo {repo!r}")
        repo_dir = clone_paths[repo]
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
        if repo not in clone_paths:
            raise KeyError(f"Unknown or unvalidated repo {repo!r}")
        repo_dir = clone_paths[repo]
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
        if repo not in clone_paths:
            raise KeyError(f"Unknown or unvalidated repo {repo!r}")
        repo_dir = clone_paths[repo]
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

            if status_code.startswith(("R", "C")):
                if idx < len(parts):
                    idx += 1

        return tuple(sorted(changed_paths))

    return PenCloneReaders(
        read_repo_head=read_repo_head,
        read_repo_file=read_repo_file,
        read_repo_changed_paths=read_repo_changed_paths,
    )
