#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Build, hash, normalize, and securely persist temporary dependency evidence.

This module produces the Nave `MaterializeRequest`, hashes it deterministically,
normalizes a Nave `MaterializeResult` into the Pulse dependency-evidence
contract (see lib/patterns/dependency-evidence-contract.md), and writes the
resulting document to a run-specific, permission-locked temporary directory.

The normalized document is TRANSIENT: it carries raw file `content` and must
never be committed, logged, or folded into a committed snapshot. Callers are
responsible for deleting the run directory once F4 has emitted its
content-free snapshot.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


def build_request(repos: list[str], selectors: list[dict]) -> dict:
    """Build a Nave MaterializeRequest applying the same selectors to each repo.

    Shape: {"contract_version": 1, "repos": [{"repo": <name>, "selectors": [...]}]}.
    The same `selectors` list is applied to every repo in `repos` — F4 calls
    this with a flat repo-name list and a single selector catalog; there is no
    per-repo selector variance in the current caller.
    """
    return {
        "contract_version": 1,
        "repos": [{"repo": repo, "selectors": selectors} for repo in repos],
    }


def request_sha256(request: dict) -> str:
    """Deterministic hex digest of a request: sorted keys, no incidental whitespace."""
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _artifact_sort_key(artifact: dict[str, Any]) -> tuple[bool, str, str]:
    path = artifact.get("path")
    selector_id = artifact.get("selector_id") or ""
    if path is None:
        return (True, "", selector_id)
    return (False, str(PurePosixPath(path)), selector_id)


def _normalize_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "selector_id": artifact.get("selector_id"),
        "path": artifact.get("path"),
        "blob_sha": artifact.get("blob_sha"),
        "size_bytes": artifact.get("size_bytes"),
        "state": artifact.get("state"),
        "encoding": artifact.get("encoding"),
        "content": artifact.get("content"),
        "detail": artifact.get("detail"),
    }


def _normalize_repo(repo_entry: dict[str, Any]) -> dict[str, Any]:
    artifacts = sorted(
        (_normalize_artifact(a) for a in repo_entry.get("artifacts", [])),
        key=_artifact_sort_key,
    )
    return {
        "repo": repo_entry.get("repo"),
        "ref_name": repo_entry.get("ref_name"),
        "tree_sha": repo_entry.get("tree_sha"),
        "tree_complete": repo_entry.get("tree_complete"),
        "artifacts": artifacts,
    }


def normalize(
    raw: dict[str, Any],
    provider: dict[str, Any],
    generated_at: str,
    request_sha256_value: str,
) -> dict[str, Any]:
    """Normalize a Nave MaterializeResult into the Pulse dependency-evidence contract.

    INTERFACE NOTE: the task brief sketches `normalize(raw, provider,
    generated_at)`, but the normalized contract requires a top-level
    `request_sha256` that ties the evidence back to the exact request that
    produced it. That value is threaded in here as a fourth parameter
    (`request_sha256_value`) rather than recomputed from `raw`, since `raw` is
    Nave's response and does not carry the originating request.
    """
    repos = sorted(
        (_normalize_repo(r) for r in raw.get("repos", [])),
        key=lambda r: r["repo"] or "",
    )
    errors = [e for e in raw.get("errors", []) if isinstance(e, str)]
    return {
        "contract_version": 1,
        "provider": {
            "name": provider.get("name"),
            "version": provider.get("version"),
            "protocol": provider.get("protocol"),
        },
        "generated_at": generated_at,
        "request_sha256": request_sha256_value,
        "repos": repos,
        "errors": errors,
    }


def secure_run_dir() -> Path:
    """Create a run-specific temporary directory locked to mode 0700."""
    run_dir = Path(tempfile.mkdtemp(prefix="pulse-dependency-evidence-"))
    os.chmod(run_dir, 0o700)
    return run_dir


def write_evidence(directory: Path, name: str, data: dict[str, Any]) -> Path:
    """Write `data` as JSON to `directory/name` with mode 0600, refusing overwrite.

    Never logs or echoes `data` — callers must not print this file's content.
    """
    path = Path(directory) / name
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, sort_keys=True)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path
