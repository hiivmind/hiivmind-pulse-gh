#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Validate a Pulse-owned normalized fleet evidence document.

Usage: validate_evidence.py FILE

Exit codes:
  0 - valid
  1 - parsed but invalid
  2 - missing or unparseable
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_VERSIONS = {1}
CAPABILITY_STATES = {"available", "degraded", "unavailable", "unsupported"}
VALIDATION_STATES = {"valid", "invalid", "unknown", "unsupported", "error"}


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
    """Require a key with a value of the requested type."""
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
    """Require a key whose value may also be null."""
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


def require_string_list(
    data: dict[str, Any], key: str, errors: list[str], ctx: str = ""
) -> list[str] | None:
    values = require(data, key, list, errors, ctx)
    if values is None:
        return None
    for index, value in enumerate(values):
        if not isinstance(value, str):
            errors.append(f"{ctx}{key}[{index}] is not a string")
    return values


def validate(data: Any) -> list[str]:
    """Return all contract violations in a parsed evidence document."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["evidence is not a mapping"]

    version = require(data, "contract_version", int, errors)
    if version is not None and version not in SUPPORTED_VERSIONS:
        errors.append(f"unsupported contract_version: {version}")

    provider = require(data, "provider", dict, errors)
    if provider is not None:
        require(provider, "name", str, errors, "provider.")
        require_nullable(provider, "version", str, errors, "provider.")
        require_nullable(provider, "protocol", int, errors, "provider.")

    require(data, "generated_at", str, errors)

    capability_status = require(data, "capability_status", dict, errors)
    if capability_status is not None:
        require_enum(
            capability_status,
            "state",
            CAPABILITY_STATES,
            errors,
            "capability_status.",
        )
        capabilities = require_string_list(
            capability_status, "capabilities", errors, "capability_status."
        )
        if capabilities is not None and len(capabilities) != len(set(capabilities)):
            errors.append("capability_status.capabilities contains duplicates")

    repos = require(data, "repos", list, errors)
    seen_repos: set[str] = set()
    for index, repo_entry in enumerate(repos or []):
        ctx = f"repos[{index}]."
        if not isinstance(repo_entry, dict):
            errors.append(f"repos[{index}] is not a mapping")
            continue
        repo = require(repo_entry, "repo", str, errors, ctx)
        if repo is not None:
            if repo in seen_repos:
                errors.append(f"duplicate repo: {repo}")
            seen_repos.add(repo)
        require_nullable(repo_entry, "remote_sha", str, errors, ctx)
        require_string_list(repo_entry, "files", errors, ctx)
        if "files_complete" in repo_entry and not isinstance(
            repo_entry["files_complete"], bool
        ):
            errors.append(
                f"wrong type for {ctx}files_complete: expected bool, "
                f"got {type(repo_entry['files_complete']).__name__}"
            )
        if "capabilities" in repo_entry:
            capabilities = require_string_list(
                repo_entry, "capabilities", errors, ctx
            )
            if capabilities is not None:
                if capabilities != sorted(capabilities):
                    errors.append(f"{ctx}capabilities must be sorted")
                if len(capabilities) != len(set(capabilities)):
                    errors.append(f"{ctx}capabilities contains duplicates")
        require_string_list(repo_entry, "structural_signals", errors, ctx)
        validation = require(repo_entry, "validation", dict, errors, ctx)
        if validation is not None:
            require_enum(
                validation,
                "state",
                VALIDATION_STATES,
                errors,
                f"{ctx}validation.",
            )
            require_string_list(
                validation, "errors", errors, f"{ctx}validation."
            )

    require_string_list(data, "errors", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Fleet evidence YAML file")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"error: unparseable YAML: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
