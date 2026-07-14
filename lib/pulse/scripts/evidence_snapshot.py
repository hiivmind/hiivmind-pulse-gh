#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Normalize Nave JSON reports into a Pulse fleet evidence snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


INVALID_OUTCOMES = {
    "drift",
    "parse_failed",
    "render_failed",
    "reparse_failed",
    "missing",
}


def _repo_name(entry: dict[str, Any]) -> str | None:
    owner = entry.get("owner")
    repo = entry.get("repo")
    if isinstance(owner, str) and isinstance(repo, str):
        return f"{owner}/{repo}"
    return None


def _add_path(files: defaultdict[str, set[str]], repo: str | None, path: Any) -> None:
    if repo is not None and isinstance(path, str):
        files[repo].add(path)


def _collect_search(report: dict, files: defaultdict[str, set[str]]) -> None:
    for entry in report.get("repos", []):
        if not isinstance(entry, dict):
            continue
        repo = _repo_name(entry)
        if repo is not None:
            files[repo]
        for hit_key in ("hits", "match_hits"):
            for hit in entry.get(hit_key, []):
                if not isinstance(hit, dict):
                    continue
                for file_hit in hit.get("files", []):
                    if isinstance(file_hit, dict):
                        _add_path(files, repo, file_hit.get("path"))


def _collect_build(report: dict, files: defaultdict[str, set[str]]) -> None:
    for group in report.get("groups", []):
        if not isinstance(group, dict):
            continue
        for instance in group.get("instances", []):
            if not isinstance(instance, dict):
                continue
            repo = _repo_name(instance)
            if repo is not None:
                files[repo]
            _add_path(files, repo, instance.get("path"))


def _collect_check(
    report: dict,
    files: defaultdict[str, set[str]],
    outcomes: defaultdict[str, list[dict]],
) -> None:
    for result in report.get("results", []):
        if not isinstance(result, dict):
            continue
        repo = _repo_name(result)
        if repo is None:
            continue
        files[repo]
        _add_path(files, repo, result.get("path"))
        outcomes[repo].append(result)


def _adapter_error(report: Any) -> str | None:
    if isinstance(report, dict) and report.get("adapter_state") == "error":
        error = report.get("error")
        return error if isinstance(error, str) else "Nave adapter error"
    if not isinstance(report, dict):
        return "Nave adapter report root is not an object"
    return None


def _signals(paths: set[str]) -> list[str]:
    signals: set[str] = set()
    for raw_path in paths:
        normalized = raw_path.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        path = PurePosixPath(normalized)
        lower = normalized.lower()
        name = path.name.lower()
        if lower == "pyproject.toml":
            signals.add("has_pyproject")
        if lower == "package.json":
            signals.add("has_package_json")
        if name.startswith("readme") or lower == "docs" or lower.startswith("docs/"):
            signals.add("has_documentation")
        if path.suffix.lower() == ".tf":
            signals.add("has_terraform")
        if lower.startswith(".github/workflows/"):
            signals.add("has_workflows")
        if lower == "claude.md":
            signals.add("has_claude_context")
        if lower == ".claude-plugin/plugin.json":
            signals.add("has_claude_plugin_manifest")
        if name == "skill.md":
            signals.add("has_skill")
    return sorted(signals)


def _validation(results: list[dict], check_available: bool) -> dict:
    if not check_available or not results:
        return {"state": "unknown", "errors": []}
    invalid = [r for r in results if r.get("outcome") in INVALID_OUTCOMES]
    if invalid:
        errors = []
        for result in invalid:
            path = result.get("path", "unknown path")
            outcome = result.get("outcome", "invalid")
            detail = result.get("detail")
            message = f"{path}: {outcome}"
            if isinstance(detail, str) and detail:
                message += f": {detail}"
            errors.append(message)
        return {"state": "invalid", "errors": sorted(errors)}
    if any(r.get("outcome") == "ok" for r in results):
        return {"state": "valid", "errors": []}
    if all(r.get("outcome") == "unknown_format" for r in results):
        return {"state": "unsupported", "errors": []}
    return {"state": "unknown", "errors": []}


def normalize(
    search: dict,
    build: dict,
    check: dict,
    provider: dict,
    generated_at: str,
) -> dict:
    """Produce deterministic, profile-neutral evidence from Nave reports."""
    files: defaultdict[str, set[str]] = defaultdict(set)
    outcomes: defaultdict[str, list[dict]] = defaultdict(list)
    errors = [error for error in provider.get("errors", []) if isinstance(error, str)]
    reports = (("search", search), ("build", build), ("check", check))
    report_errors = {name: _adapter_error(report) for name, report in reports}
    errors.extend(error for error in report_errors.values() if error is not None)

    if report_errors["search"] is None:
        _collect_search(search, files)
    if report_errors["build"] is None:
        _collect_build(build, files)
    if report_errors["check"] is None:
        _collect_check(check, files, outcomes)

    provider_state = provider.get("state", "unsupported")
    capability_state = provider_state
    if any(report_errors.values()) and provider_state == "available":
        capability_state = "degraded"

    repos = []
    for repo in sorted(files):
        repos.append(
            {
                "repo": repo,
                "remote_sha": None,
                "files": sorted(files[repo]),
                "structural_signals": _signals(files[repo]),
                "validation": _validation(
                    outcomes[repo], report_errors["check"] is None
                ),
            }
        )

    return {
        "contract_version": 1,
        "provider": {
            "name": "nave",
            "version": provider.get("version"),
            "protocol": provider.get("protocol"),
        },
        "generated_at": generated_at,
        "capability_status": {
            "state": capability_state,
            "capabilities": sorted(
                capability
                for capability in provider.get("capabilities", [])
                if isinstance(capability, str)
            ),
        },
        "repos": repos,
        "errors": sorted(set(errors)),
    }


def _load_json(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--check", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    try:
        snapshot = normalize(
            _load_json(args.search),
            _load_json(args.build),
            _load_json(args.check),
            _load_json(args.provider),
            args.generated_at or _now(),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: could not load Nave report: {exc}", file=sys.stderr)
        return 2
    print(yaml.safe_dump(snapshot, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
