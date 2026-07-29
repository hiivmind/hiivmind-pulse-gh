"""Overlay-only content collector for Claude plugin healthchecks.

The neutral F0 evidence snapshot is content-free (paths only). Overlay
scorecards need a bounded, ref-pinned ``file_contents`` channel. This
module is that channel: it resolves the overlay repo's default-branch
head SHA once via an injected ``gh_api`` seam, then reads only the
overlay-relevant paths at that immutable SHA.

Neutral fleet runs never call this module. Content is attached only to
opted-in repo entries by ``healthcheck_dispatch``.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from typing import Any


GhApi = Callable[[str], Any]

# Bounded content channel — overlay-scoped only.
PER_FILE_BYTE_LIMIT = 256 * 1024  # 256 KiB
TOTAL_BYTE_BUDGET = 1 * 1024 * 1024  # 1 MiB

PLUGIN_MANIFEST_PATH = ".claude-plugin/plugin.json"
CLAUDE_CONTEXT_PATH = "CLAUDE.md"
SKILL_PATH_PREFIX = "skills/"
SKILL_FILENAME = "SKILL.md"

UNAVAILABLE_MISSING = "missing"
UNAVAILABLE_TOO_LARGE = "too_large"
UNAVAILABLE_FETCH_ERROR = "fetch_error"

_UNAVAILABLE_STATES = frozenset(
    {UNAVAILABLE_MISSING, UNAVAILABLE_TOO_LARGE, UNAVAILABLE_FETCH_ERROR}
)

_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _unavailable(state: str) -> dict[str, str]:
    if state not in _UNAVAILABLE_STATES:
        raise ValueError(f"unknown unavailable state: {state}")
    return {"unavailable": state}


def _is_skill_path(path: str) -> bool:
    if not path.startswith(SKILL_PATH_PREFIX):
        return False
    if not path.endswith("/" + SKILL_FILENAME):
        return False
    remainder = path[len(SKILL_PATH_PREFIX) : -len("/" + SKILL_FILENAME)]
    return bool(remainder) and "/" not in remainder


def overlay_paths(files: Sequence[str]) -> list[str]:
    """Return the deterministic set of overlay paths to fetch.

    Always includes the plugin manifest and ``CLAUDE.md``. Skill paths are
    taken from the F0 ``files`` list matching ``skills/*/SKILL.md``.
    """
    paths: set[str] = {PLUGIN_MANIFEST_PATH, CLAUDE_CONTEXT_PATH}
    for path in files:
        if isinstance(path, str) and _is_skill_path(path):
            paths.add(path)
    # Fixed paths first, then skills in lexical order — deterministic.
    skills = sorted(p for p in paths if _is_skill_path(p))
    fixed = [PLUGIN_MANIFEST_PATH, CLAUDE_CONTEXT_PATH]
    return fixed + skills


def _resolve_default_branch(
    repo: str, gh_api: GhApi, default_branch: str | None
) -> str | None:
    if isinstance(default_branch, str) and default_branch.strip():
        return default_branch.strip()
    try:
        meta = gh_api(f"repos/{repo}")
    except Exception:
        return None
    if not isinstance(meta, Mapping):
        return None
    branch = meta.get("default_branch")
    if isinstance(branch, str) and branch.strip():
        return branch.strip()
    return None


def _resolve_head_sha(repo: str, branch: str, gh_api: GhApi) -> str | None:
    try:
        payload = gh_api(f"repos/{repo}/commits/{branch}")
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
    sha = payload.get("sha")
    if isinstance(sha, str) and _SHA_RE.fullmatch(sha):
        return sha
    return None


def _decode_contents_payload(payload: Any) -> tuple[str | None, str | None]:
    """Return ``(text, error_state)`` from a GitHub contents API payload.

    ``error_state`` is one of the unavailable states when content cannot be
    decoded; ``text`` is the decoded string on success.
    """
    if payload is None:
        return None, UNAVAILABLE_MISSING
    if not isinstance(payload, Mapping):
        return None, UNAVAILABLE_FETCH_ERROR
    if payload.get("type") not in (None, "file"):
        # Directory listing or unexpected type — not a file we can grade.
        return None, UNAVAILABLE_MISSING
    encoding = payload.get("encoding")
    content = payload.get("content")
    if encoding == "base64" and isinstance(content, str):
        try:
            raw = base64.b64decode(content, validate=False)
        except Exception:
            return None, UNAVAILABLE_FETCH_ERROR
        try:
            return raw.decode("utf-8"), None
        except UnicodeDecodeError:
            return None, UNAVAILABLE_FETCH_ERROR
    if isinstance(content, str) and encoding in (None, "utf-8", "text"):
        return content, None
    # Malformed: claimed to be a file but missing usable content.
    return None, UNAVAILABLE_FETCH_ERROR


def _payload_size_bytes(payload: Any, text: str | None) -> int | None:
    if isinstance(payload, Mapping):
        size = payload.get("size")
        if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
            return size
    if text is not None:
        return len(text.encode("utf-8"))
    return None


def collect(
    repo: str,
    *,
    files: Sequence[str],
    gh_api: GhApi,
    default_branch: str | None = None,
    per_file_byte_limit: int = PER_FILE_BYTE_LIMIT,
    total_byte_budget: int = TOTAL_BYTE_BUDGET,
) -> dict[str, Any]:
    """Collect overlay file contents at a pinned remote SHA.

    Returns a mapping suitable for ``evidence["file_contents"]``:

    * path → ``str`` when content is available
    * path → ``{"unavailable": "missing"|"too_large"|"fetch_error"}`` otherwise

    Paths are never silently omitted. A SHA resolution failure marks **all**
    paths ``fetch_error`` and never issues an unpinned content read.
    """
    if not isinstance(repo, str) or not repo.strip():
        raise ValueError("repo must be a non-empty string")
    if per_file_byte_limit < 0 or total_byte_budget < 0:
        raise ValueError("byte limits must be non-negative")

    paths = overlay_paths(files)
    branch = _resolve_default_branch(repo, gh_api, default_branch)
    sha = _resolve_head_sha(repo, branch, gh_api) if branch else None
    if sha is None:
        return {path: _unavailable(UNAVAILABLE_FETCH_ERROR) for path in paths}

    result: dict[str, Any] = {}
    used_bytes = 0
    for path in paths:
        remaining = total_byte_budget - used_bytes
        if remaining <= 0:
            result[path] = _unavailable(UNAVAILABLE_TOO_LARGE)
            continue
        try:
            payload = gh_api(f"repos/{repo}/contents/{path}?ref={sha}")
        except Exception:
            result[path] = _unavailable(UNAVAILABLE_FETCH_ERROR)
            continue

        # Pre-check declared size before decoding when present.
        if isinstance(payload, Mapping):
            declared = payload.get("size")
            if (
                isinstance(declared, int)
                and not isinstance(declared, bool)
                and declared > per_file_byte_limit
            ):
                result[path] = _unavailable(UNAVAILABLE_TOO_LARGE)
                continue
            if (
                isinstance(declared, int)
                and not isinstance(declared, bool)
                and declared > remaining
            ):
                result[path] = _unavailable(UNAVAILABLE_TOO_LARGE)
                continue

        text, error = _decode_contents_payload(payload)
        if error is not None:
            result[path] = _unavailable(error)
            continue

        size = _payload_size_bytes(payload, text)
        if size is None:
            result[path] = _unavailable(UNAVAILABLE_FETCH_ERROR)
            continue
        if size > per_file_byte_limit or size > remaining:
            result[path] = _unavailable(UNAVAILABLE_TOO_LARGE)
            continue

        assert text is not None
        result[path] = text
        used_bytes += size

    return result


def default_branch_from_evidence(evidence: Mapping[str, Any]) -> str | None:
    """Extract ``github.repo.default_branch`` when Phase-2 enrichment ran."""
    github = evidence.get("github")
    if not isinstance(github, Mapping):
        return None
    repo = github.get("repo")
    if not isinstance(repo, Mapping):
        return None
    branch = repo.get("default_branch")
    if isinstance(branch, str) and branch.strip():
        return branch.strip()
    return None


def default_gh_api(path: str) -> Any:
    """Default ``gh api`` seam — returns parsed JSON or ``None`` on failure."""
    cmd = ["gh", "api", path]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
