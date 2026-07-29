"""Tests for the overlay-only content collector (F10 Task 4)."""

from __future__ import annotations

import base64
from typing import Any

import pytest

from lib.pulse.scripts import overlay_content


SHA = "abc123def4567890abc123def4567890abc123de"
REPO = "acme/plugin"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _file_payload(text: str, *, size: int | None = None) -> dict[str, Any]:
    raw = text.encode("utf-8")
    return {
        "type": "file",
        "encoding": "base64",
        "size": size if size is not None else len(raw),
        "content": _b64(text),
    }


def _gh_api_for(
    *,
    branch: str = "main",
    sha: str = SHA,
    contents: dict[str, str | dict[str, Any] | None] | None = None,
    fail_sha: bool = False,
    fail_repo: bool = False,
) -> Any:
    """Build a recording gh_api seam for content-collection tests."""
    contents = contents or {}
    calls: list[str] = []

    def gh_api(path: str) -> Any:
        calls.append(path)
        if path == f"repos/{REPO}":
            if fail_repo:
                return None
            return {"default_branch": branch}
        if path == f"repos/{REPO}/commits/{branch}":
            if fail_sha:
                return None
            return {"sha": sha}
        prefix = f"repos/{REPO}/contents/"
        if path.startswith(prefix):
            # path shape: repos/{repo}/contents/{file_path}?ref={sha}
            rest = path[len(prefix) :]
            file_path, _, query = rest.partition("?")
            assert query == f"ref={sha}", f"content reads must be SHA-pinned: {path}"
            if file_path not in contents:
                return None
            value = contents[file_path]
            if value is None:
                return None
            if isinstance(value, dict):
                return value
            return _file_payload(value)
        return None

    gh_api.calls = calls  # type: ignore[attr-defined]
    return gh_api


def test_collect_pins_reads_to_resolved_sha_and_returns_strings():
    gh = _gh_api_for(
        contents={
            ".claude-plugin/plugin.json": '{"name":"p","version":"1"}',
            "CLAUDE.md": "# context\n",
            "skills/audit/SKILL.md": "---\nname: audit\ndescription: d\n---\n",
        }
    )
    files = [
        ".claude-plugin/plugin.json",
        "CLAUDE.md",
        "skills/audit/SKILL.md",
        "README.md",
    ]

    result = overlay_content.collect(
        REPO, files=files, gh_api=gh, default_branch="main"
    )

    assert result[".claude-plugin/plugin.json"] == '{"name":"p","version":"1"}'
    assert result["CLAUDE.md"] == "# context\n"
    assert result["skills/audit/SKILL.md"].startswith("---")
    assert "README.md" not in result  # not an overlay path
    assert any(c.endswith(f"/commits/main") for c in gh.calls)
    assert all(
        "?ref=" not in c or f"ref={SHA}" in c
        for c in gh.calls
        if "/contents/" in c
    )


def test_collect_resolves_default_branch_via_gh_api_when_not_provided():
    gh = _gh_api_for(
        branch="develop",
        contents={".claude-plugin/plugin.json": "{}", "CLAUDE.md": "x"},
    )

    overlay_content.collect(
        REPO,
        files=[".claude-plugin/plugin.json", "CLAUDE.md"],
        gh_api=gh,
        default_branch=None,
    )

    assert f"repos/{REPO}" in gh.calls
    assert f"repos/{REPO}/commits/develop" in gh.calls


def test_sha_resolution_failure_marks_all_paths_fetch_error():
    gh = _gh_api_for(fail_sha=True)
    files = [
        ".claude-plugin/plugin.json",
        "CLAUDE.md",
        "skills/a/SKILL.md",
    ]

    result = overlay_content.collect(
        REPO, files=files, gh_api=gh, default_branch="main"
    )

    assert result == {
        ".claude-plugin/plugin.json": {"unavailable": "fetch_error"},
        "CLAUDE.md": {"unavailable": "fetch_error"},
        "skills/a/SKILL.md": {"unavailable": "fetch_error"},
    }
    # Never unpinned content reads
    assert not any("/contents/" in c for c in gh.calls)


def test_missing_path_is_explicit_unavailable_not_omitted():
    gh = _gh_api_for(
        contents={
            "CLAUDE.md": "# ok\n",
            # plugin.json intentionally absent from contents map → None
        }
    )

    result = overlay_content.collect(
        REPO,
        files=[".claude-plugin/plugin.json", "CLAUDE.md"],
        gh_api=gh,
        default_branch="main",
    )

    assert result["CLAUDE.md"] == "# ok\n"
    assert result[".claude-plugin/plugin.json"] == {"unavailable": "missing"}


def test_too_large_path_is_explicit_and_does_not_crash():
    big = "x" * 100
    gh = _gh_api_for(
        contents={
            "CLAUDE.md": _file_payload(big, size=100),
            ".claude-plugin/plugin.json": "{}",
        }
    )

    result = overlay_content.collect(
        REPO,
        files=[".claude-plugin/plugin.json", "CLAUDE.md"],
        gh_api=gh,
        default_branch="main",
        per_file_byte_limit=50,
        total_byte_budget=10_000,
    )

    assert result[".claude-plugin/plugin.json"] == "{}"
    assert result["CLAUDE.md"] == {"unavailable": "too_large"}


def test_total_budget_marks_later_paths_too_large():
    gh = _gh_api_for(
        contents={
            ".claude-plugin/plugin.json": "a" * 40,
            "CLAUDE.md": "b" * 40,
            "skills/a/SKILL.md": "c" * 40,
        }
    )

    result = overlay_content.collect(
        REPO,
        files=[
            ".claude-plugin/plugin.json",
            "CLAUDE.md",
            "skills/a/SKILL.md",
        ],
        gh_api=gh,
        default_branch="main",
        per_file_byte_limit=100,
        total_byte_budget=50,  # first file fits; later ones exceed remaining budget
    )

    assert result[".claude-plugin/plugin.json"] == "a" * 40
    assert result["CLAUDE.md"] == {"unavailable": "too_large"}
    assert result["skills/a/SKILL.md"] == {"unavailable": "too_large"}


def test_fetch_error_on_malformed_payload_is_explicit():
    gh = _gh_api_for(
        contents={
            ".claude-plugin/plugin.json": "{}",
            # Malformed: not a file-shaped contents payload
            "CLAUDE.md": {"type": "file", "encoding": "base64"},  # no content key
        }
    )

    result = overlay_content.collect(
        REPO,
        files=[".claude-plugin/plugin.json", "CLAUDE.md"],
        gh_api=gh,
        default_branch="main",
    )

    assert result[".claude-plugin/plugin.json"] == "{}"
    assert result["CLAUDE.md"] == {"unavailable": "fetch_error"}


def test_api_none_for_path_is_missing():
    gh = _gh_api_for(
        contents={
            ".claude-plugin/plugin.json": "{}",
            "CLAUDE.md": None,  # seam returns None → 404-style missing
        }
    )

    result = overlay_content.collect(
        REPO,
        files=[".claude-plugin/plugin.json", "CLAUDE.md"],
        gh_api=gh,
        default_branch="main",
    )

    assert result["CLAUDE.md"] == {"unavailable": "missing"}


def test_skill_paths_discovered_from_files_list_only():
    gh = _gh_api_for(
        contents={
            ".claude-plugin/plugin.json": "{}",
            "CLAUDE.md": "c",
            "skills/one/SKILL.md": "s1",
            "skills/two/SKILL.md": "s2",
            "skills/nested/deep/SKILL.md": "nope",
        }
    )

    result = overlay_content.collect(
        REPO,
        files=[
            ".claude-plugin/plugin.json",
            "CLAUDE.md",
            "skills/one/SKILL.md",
            "skills/two/SKILL.md",
            "skills/nested/deep/SKILL.md",  # not skills/*/SKILL.md shape
        ],
        gh_api=gh,
        default_branch="main",
    )

    assert "skills/one/SKILL.md" in result
    assert "skills/two/SKILL.md" in result
    assert "skills/nested/deep/SKILL.md" not in result
