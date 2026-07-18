#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Strictly validate a normalized temporary dependency-evidence document.

See lib/patterns/dependency-evidence-contract.md for the schema. The document
this validates is TRANSIENT and may carry raw file `content` — validation
errors must never interpolate any artifact `content` value.

Usage: validate_dependency_evidence.py FILE

Exit codes:
  0 - valid
  1 - parsed but invalid
  2 - missing or unparseable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from math import isfinite
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_VERSIONS = {1}
REQUIRED_PROTOCOL = 2
ARTIFACT_STATES = {
    "found",
    "absent",
    "unresolved",
    "too_large",
    "binary",
    "unsupported",
    "error",
}
TOP_LEVEL_KEYS = {
    "contract_version",
    "provider",
    "generated_at",
    "request_sha256",
    "repos",
    "errors",
}
PROVIDER_KEYS = {"name", "version", "protocol"}
REPO_KEYS = {"repo", "ref_name", "tree_sha", "tree_complete", "artifacts"}
ARTIFACT_KEYS = {
    "selector_id",
    "path",
    "blob_sha",
    "size_bytes",
    "state",
    "encoding",
    "content",
    "detail",
}
REPO_NAME_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _type_name(types: type | tuple[type, ...]) -> str:
    if isinstance(types, tuple):
        return " or ".join(t.__name__ for t in types)
    return types.__name__


def require(
    data: dict[str, Any],
    key: str,
    types: type | tuple[type, ...],
    errors: list[str],
    ctx: str = "",
) -> Any:
    label = f"{ctx}{key}"
    if key not in data:
        errors.append(f"missing required key: {label}")
        return None
    value = data[key]
    if not isinstance(value, types) or (
        isinstance(value, bool)
        and (types is int or (isinstance(types, tuple) and int in types))
    ):
        errors.append(
            f"wrong type for {label}: expected {_type_name(types)}, "
            f"got {type(value).__name__}"
        )
        return None
    return value


def require_nullable(
    data: dict[str, Any],
    key: str,
    types: type | tuple[type, ...],
    errors: list[str],
    ctx: str = "",
) -> Any:
    if key not in data:
        errors.append(f"missing required key: {ctx}{key}")
        return None
    if data[key] is None:
        return None
    return require(data, key, types, errors, ctx)


def require_enum(
    data: dict[str, Any],
    key: str,
    allowed: set[str],
    errors: list[str],
    ctx: str = "",
) -> str | None:
    value = require(data, key, str, errors, ctx)
    if value is not None and value not in allowed:
        errors.append(f"{ctx}{key} invalid: {value}")
    return value


def _require_exact_keys(
    data: dict[str, Any], allowed: set[str], errors: list[str], ctx: str
) -> None:
    extra = sorted(set(data.keys()) - allowed)
    for key in extra:
        errors.append(f"{ctx}unexpected key: {key}")
    missing = sorted(allowed - set(data.keys()))
    for key in missing:
        errors.append(f"missing required key: {ctx}{key}")


def _require_nonnegative_finite_int_or_null(
    data: dict[str, Any], key: str, errors: list[str], ctx: str, *, required: bool = False
) -> None:
    """Validate size_bytes: int-or-null in general; `required=True` forbids null.

    Nave's `size_bytes` field is `Option<u64>` in Rust and serializes as JSON
    `null` for artifacts with no matched content (absent/unresolved). A
    `found` artifact always has a decoded size, so callers pass
    `required=True` for that state.
    """
    label = f"{ctx}{key}"
    if key not in data:
        errors.append(f"missing required key: {label}")
        return
    value = data[key]
    if value is None:
        if required:
            errors.append(f"{label} must be a finite non-negative integer when state is found")
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"wrong type for {label}: expected int or null")
        return
    if not isfinite(value) or value < 0 or (isinstance(value, float) and not value.is_integer()):
        errors.append(f"{label} must be a finite non-negative integer or null")
        return


def _validate_artifact(
    artifact: Any, errors: list[str], ctx: str
) -> tuple[str | None, str | None]:
    """Validate one artifact; returns (selector_id, path) for identity checks."""
    if not isinstance(artifact, dict):
        errors.append(f"{ctx[:-1]} is not a mapping")
        return None, None

    _require_exact_keys(artifact, ARTIFACT_KEYS, errors, ctx)

    selector_id = require(artifact, "selector_id", str, errors, ctx)
    path = require_nullable(artifact, "path", str, errors, ctx)
    # blob_sha may be a 40-char (sha1) or 64-char (sha256) hex string, or null.
    if "blob_sha" not in artifact:
        errors.append(f"missing required key: {ctx}blob_sha")
    else:
        blob_sha = artifact["blob_sha"]
        if blob_sha is not None and (
            not isinstance(blob_sha, str)
            or not (HEX40_RE.match(blob_sha) or HEX64_RE.match(blob_sha))
        ):
            errors.append(f"{ctx}blob_sha must be a 40- or 64-char hex string or null")
    state = require_enum(artifact, "state", ARTIFACT_STATES, errors, ctx)
    _require_nonnegative_finite_int_or_null(
        artifact, "size_bytes", errors, ctx, required=(state == "found")
    )
    require_nullable(artifact, "encoding", str, errors, ctx)
    content_present = "content" in artifact
    if not content_present:
        errors.append(f"missing required key: {ctx}content")
    else:
        content = artifact["content"]
        if state == "found":
            if content is None or not isinstance(content, str):
                errors.append(f"{ctx}content is required when state is found")
            if artifact.get("encoding") != "utf-8":
                errors.append(f"{ctx}encoding must be utf-8 when state is found")
        else:
            if content is not None:
                errors.append(f"{ctx}content must be absent/null when state is {state}")
    require_nullable(artifact, "detail", str, errors, ctx)

    return selector_id, path


def _validate_repo(repo_entry: Any, errors: list[str], ctx: str) -> str | None:
    if not isinstance(repo_entry, dict):
        errors.append(f"{ctx[:-1]} is not a mapping")
        return None

    _require_exact_keys(repo_entry, REPO_KEYS, errors, ctx)

    repo = require(repo_entry, "repo", str, errors, ctx)
    if repo is not None and not REPO_NAME_RE.match(repo):
        errors.append(f"{ctx}repo must match owner/name: {repo}")
    require(repo_entry, "ref_name", str, errors, ctx)
    if "tree_sha" not in repo_entry:
        errors.append(f"missing required key: {ctx}tree_sha")
    else:
        tree_sha = repo_entry["tree_sha"]
        if tree_sha is not None and (
            not isinstance(tree_sha, str)
            or not (HEX40_RE.match(tree_sha) or HEX64_RE.match(tree_sha))
        ):
            errors.append(f"{ctx}tree_sha must be a 40- or 64-char hex string or null")
    require(repo_entry, "tree_complete", bool, errors, ctx)

    artifacts = require(repo_entry, "artifacts", list, errors, ctx)
    seen_paths: set[str] = set()
    for index, artifact in enumerate(artifacts or []):
        actx = f"{ctx}artifacts[{index}]."
        selector_id, path = _validate_artifact(artifact, errors, actx)
        # selector_id is intentionally NOT required to be unique per repo: a
        # single glob selector fans out into one artifact per matched path,
        # all sharing that selector_id (see Nave's
        # `glob_fan_out_yields_sorted_found_sharing_selector_id` contract
        # test). Non-null `path` uniqueness below is what actually catches
        # duplicate/conflicting entries.
        if path is not None:
            if path in seen_paths:
                errors.append(f"{ctx}duplicate path: {path}")
            seen_paths.add(path)

    return repo


def validate(data: Any) -> list[str]:
    """Return all contract violations in a parsed dependency-evidence document."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["dependency evidence is not a mapping"]

    _require_exact_keys(data, TOP_LEVEL_KEYS, errors, "")

    version = require(data, "contract_version", int, errors)
    if version is not None and version not in SUPPORTED_VERSIONS:
        errors.append(f"unsupported contract_version: {version}")

    provider = require(data, "provider", dict, errors)
    if provider is not None:
        _require_exact_keys(provider, PROVIDER_KEYS, errors, "provider.")
        require(provider, "name", str, errors, "provider.")
        require_nullable(provider, "version", str, errors, "provider.")
        protocol = require(provider, "protocol", int, errors, "provider.")
        if protocol is not None and protocol != REQUIRED_PROTOCOL:
            errors.append(
                f"provider.protocol must be {REQUIRED_PROTOCOL}, got {protocol}"
            )

    generated_at = require(data, "generated_at", str, errors)
    if generated_at is not None and not generated_at:
        errors.append("generated_at must not be empty")

    request_hash = require(data, "request_sha256", str, errors)
    if request_hash is not None and not HEX64_RE.match(request_hash):
        errors.append("request_sha256 must be a 64-char lowercase hex string")

    repos = require(data, "repos", list, errors)
    seen_repos: set[str] = set()
    for index, repo_entry in enumerate(repos or []):
        repo = _validate_repo(repo_entry, errors, f"repos[{index}].")
        if repo is not None:
            if repo in seen_repos:
                errors.append(f"duplicate repo: {repo}")
            seen_repos.add(repo)

    error_list = require(data, "errors", list, errors)
    if error_list is not None:
        for index, value in enumerate(error_list):
            if not isinstance(value, str):
                errors.append(f"errors[{index}] is not a string")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Dependency evidence JSON/YAML file")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text()
    try:
        if path.suffix == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"error: unparseable file: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
