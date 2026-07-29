"""Tests for pen_clone_reader module — clone root contract and git seams."""

import os
import subprocess
from pathlib import Path
import pytest

from lib.pulse.scripts.pen_clone_reader import (
    PenCloneReaderError,
    PenCloneReaders,
    make_pen_clone_reader,
)


def _init_git_repo(path: Path) -> str:
    """Initialize a real git repository with an initial commit and return HEAD SHA."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)
    (path / "init.txt").write_text("initial content\n")
    subprocess.run(["git", "add", "init.txt"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=path, check=True, capture_output=True)
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True)
    return res.stdout.strip()


def test_make_pen_clone_reader_unset_root(monkeypatch):
    monkeypatch.delenv("PULSE_PEN_ROOT", raising=False)
    with pytest.raises(PenCloneReaderError, match="PULSE_PEN_ROOT"):
        make_pen_clone_reader(clone_root=None, selection=("owner/repo",))


def test_make_pen_clone_reader_missing_root_dir(tmp_path):
    missing_dir = tmp_path / "nonexistent"
    with pytest.raises(PenCloneReaderError, match="does not exist"):
        make_pen_clone_reader(clone_root=missing_dir, selection=("owner/repo",))


def test_make_pen_clone_reader_absent_repo_checkout(tmp_path):
    with pytest.raises(PenCloneReaderError, match="not found"):
        make_pen_clone_reader(clone_root=tmp_path, selection=("owner/repo",))


def test_make_pen_clone_reader_not_a_git_repo(tmp_path):
    repo_dir = tmp_path / "owner" / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "somefile.txt").write_text("not git")
    with pytest.raises(PenCloneReaderError, match="not a git worktree"):
        make_pen_clone_reader(clone_root=tmp_path, selection=("owner/repo",))


def test_make_pen_clone_reader_invalid_repo_format(tmp_path):
    with pytest.raises(PenCloneReaderError, match="Invalid repo format"):
        make_pen_clone_reader(clone_root=tmp_path, selection=("invalid-format",))


def test_pen_clone_reader_seams(tmp_path):
    repo_dir = tmp_path / "acme" / "widget"
    head_sha = _init_git_repo(repo_dir)

    # Add a second committed file
    (repo_dir / "unchanged.txt").write_text("unchanged\n")
    subprocess.run(["git", "add", "unchanged.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add unchanged"], cwd=repo_dir, check=True, capture_output=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True).stdout.strip()

    readers = make_pen_clone_reader(clone_root=tmp_path, selection=("acme/widget",))
    assert isinstance(readers, PenCloneReaders)

    # 1. read_repo_head
    assert readers.read_repo_head("acme/widget") == head_sha
    with pytest.raises(KeyError):
        readers.read_repo_head("unknown/repo")

    # 2. read_repo_file
    assert readers.read_repo_file("acme/widget", "init.txt") == b"initial content\n"
    with pytest.raises(FileNotFoundError):
        readers.read_repo_file("acme/widget", "nonexistent.txt")
    with pytest.raises(FileNotFoundError):
        readers.read_repo_file("acme/widget", "../outside.txt")
    with pytest.raises(KeyError):
        readers.read_repo_file("unknown/repo", "init.txt")

    # 3. read_repo_changed_paths
    # Clean tree initially
    assert readers.read_repo_changed_paths("acme/widget") == ()

    # Modify tracked init.txt and create untracked new_file.txt
    (repo_dir / "init.txt").write_text("modified content\n")
    (repo_dir / "untracked.txt").write_text("untracked content\n")

    changed = readers.read_repo_changed_paths("acme/widget")
    assert changed == ("init.txt", "untracked.txt")
    assert "unchanged.txt" not in changed

    with pytest.raises(KeyError):
        readers.read_repo_changed_paths("unknown/repo")


def test_make_pen_clone_reader_env_var_fallback(tmp_path, monkeypatch):
    repo_dir = tmp_path / "org" / "project"
    _init_git_repo(repo_dir)

    monkeypatch.setenv("PULSE_PEN_ROOT", str(tmp_path))
    readers = make_pen_clone_reader(selection=("org/project",))
    assert readers.read_repo_head("org/project") is not None
