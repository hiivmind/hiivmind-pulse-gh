"""Tests for normalization of Nave reports into Pulse fleet evidence."""

import json
import subprocess
import sys

import yaml

from lib.pulse.scripts import evidence_snapshot, validate_evidence


GENERATED_AT = "2026-07-13T10:00:00Z"


def provider():
    return {
        "available": True,
        "state": "available",
        "version": "0.0.8",
        "protocol": 1,
        "capabilities": [
            "scan",
            "pull",
            "search_json",
            "build_json",
            "check_json",
            "pen",
        ],
        "errors": [],
    }


def mixed_reports():
    search = {
        "repos": [
            {
                "owner": "acme",
                "repo": "python-api",
                "hits": [
                    {
                        "term": "project",
                        "files": [
                            {"path": "pyproject.toml", "matched_needle": "project"}
                        ],
                    }
                ],
            },
            {
                "owner": "acme",
                "repo": "node-web",
                "hits": [],
                "match_hits": [
                    {
                        "predicate": "scripts.test",
                        "files": [
                            {"path": "package.json", "addresses": ["scripts.test"]}
                        ],
                    }
                ],
            },
        ],
        "repos_considered": 5,
        "repos_without_checkout": 0,
    }
    build = {
        "groups": [
            {
                "pattern": "README.md",
                "instances": [
                    {"owner": "acme", "repo": "docs", "path": "README.md"}
                ],
            },
            {
                "pattern": "*.tf",
                "instances": [
                    {"owner": "acme", "repo": "infra", "path": "main.tf"}
                ],
            },
        ],
        "skipped": [],
    }
    check = {
        "results": [
            {
                "owner": "acme",
                "repo": "broken-config",
                "path": "config.yaml",
                "format": "yaml",
                "outcome": "parse_failed",
                "detail": "mapping values are not allowed",
            },
            {
                "owner": "acme",
                "repo": "docs",
                "path": "README.md",
                "format": None,
                "outcome": "unknown_format",
            },
            {
                "owner": "acme",
                "repo": "infra",
                "path": "main.tf",
                "format": None,
                "outcome": "unknown_format",
            },
            {
                "owner": "acme",
                "repo": "node-web",
                "path": "package.json",
                "format": None,
                "outcome": "unknown_format",
            },
            {
                "owner": "acme",
                "repo": "python-api",
                "path": "pyproject.toml",
                "format": "toml",
                "outcome": "ok",
            },
        ],
        "totals": {
            "ok": 1,
            "drift": 0,
            "parse_failed": 1,
            "render_failed": 0,
            "reparse_failed": 0,
            "unknown_format": 3,
            "missing": 0,
        },
    }
    return search, build, check


def test_normalizes_mixed_repositories_without_profile_inference():
    search, build, check = mixed_reports()

    snapshot = evidence_snapshot.normalize(
        search, build, check, provider(), GENERATED_AT
    )

    assert [repo["repo"] for repo in snapshot["repos"]] == [
        "acme/broken-config",
        "acme/docs",
        "acme/infra",
        "acme/node-web",
        "acme/python-api",
    ]
    by_repo = {repo["repo"]: repo for repo in snapshot["repos"]}
    assert by_repo["acme/python-api"]["structural_signals"] == ["has_pyproject"]
    assert by_repo["acme/node-web"]["structural_signals"] == ["has_package_json"]
    assert by_repo["acme/docs"]["structural_signals"] == ["has_documentation"]
    assert by_repo["acme/infra"]["structural_signals"] == ["has_terraform"]
    assert by_repo["acme/broken-config"]["validation"]["state"] == "invalid"
    assert all("profiles" not in repo for repo in snapshot["repos"])
    assert validate_evidence.validate(snapshot) == []


def test_files_and_signals_are_deterministic_and_deduplicated():
    search, build, check = mixed_reports()
    search["repos"][0]["hits"][0]["files"].append(
        {"path": "pyproject.toml", "matched_needle": "project"}
    )

    snapshot = evidence_snapshot.normalize(
        search, build, check, provider(), GENERATED_AT
    )
    python = next(r for r in snapshot["repos"] if r["repo"] == "acme/python-api")

    assert python["files"] == ["pyproject.toml"]
    assert python["structural_signals"] == ["has_pyproject"]


def test_preserves_dot_prefixed_paths_when_deriving_signals():
    paths = {
        ".github/workflows/ci.yml",
        ".claude-plugin/plugin.json",
        "./CLAUDE.md",
        "skills/release/SKILL.md",
    }

    assert evidence_snapshot._signals(paths) == [
        "has_claude_context",
        "has_claude_plugin_manifest",
        "has_skill",
        "has_workflows",
    ]


def test_analysis_error_degrades_capability_without_failing_repositories():
    search, build, _ = mixed_reports()
    check = {
        "adapter_state": "error",
        "command": "check",
        "returncode": 2,
        "error": "invalid JSON from nave check",
        "stderr": "",
    }

    snapshot = evidence_snapshot.normalize(
        search, build, check, provider(), GENERATED_AT
    )

    assert snapshot["capability_status"]["state"] == "degraded"
    assert "invalid JSON from nave check" in snapshot["errors"]
    assert {r["validation"]["state"] for r in snapshot["repos"]} == {"unknown"}


def test_cli_writes_validator_compatible_yaml(tmp_path):
    search, build, check = mixed_reports()
    inputs = {}
    for name, value in {
        "search": search,
        "build": build,
        "check": check,
        "provider": provider(),
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value))
        inputs[name] = path

    result = subprocess.run(
        [
            sys.executable,
            "lib/pulse/scripts/evidence_snapshot.py",
            "--search",
            str(inputs["search"]),
            "--build",
            str(inputs["build"]),
            "--check",
            str(inputs["check"]),
            "--provider",
            str(inputs["provider"]),
            "--generated-at",
            GENERATED_AT,
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert validate_evidence.validate(yaml.safe_load(result.stdout)) == []
