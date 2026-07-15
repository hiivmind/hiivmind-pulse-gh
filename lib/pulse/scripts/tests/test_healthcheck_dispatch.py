"""Tests for heterogeneous, profile-dispatched healthcheck evaluation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from lib.pulse.scripts.healthcheck_dispatch import evaluate_fleet


FIXTURES = Path(__file__).parent / "fixtures" / "profiles"
SCRIPT = Path(__file__).parents[1] / "healthcheck_dispatch.py"


def test_dispatches_only_authoritative_resolved_checks_across_a_mixed_fleet():
    evidence = yaml.safe_load((FIXTURES / "evidence.yaml").read_text())
    evidence["repos"] = [
        entry for entry in evidence["repos"] if entry["repo"] != "acme/python-lib"
    ]
    evidence["repos"].extend(
        [
            {
                "repo": "acme/unprofiled",
                "capabilities": ["rust"],
                "files": ["Cargo.toml"],
                "structural_signals": [],
            }
        ]
    )

    result = evaluate_fleet(
        evidence=evidence,
        profiles_path=FIXTURES / "profiles.yaml",
        workspace=Path("/workspace/must-remain-context-only"),
    )

    assert list(result) == ["repos", "aggregate", "coverage"]
    assert [repo["repo"] for repo in result["repos"]] == [
        "acme/docs",
        "acme/node-web",
        "acme/plugin",
        "acme/python-lib",
        "acme/python-service",
        "acme/terraform",
        "acme/unknown",
    ]
    assert {
        repo["repo"]: list(repo["checks"])
        for repo in result["repos"]
    } == {
        "acme/docs": ["ci", "claude-plugin-structure", "docs-links", "documentation"],
        "acme/node-web": [
            "ci",
            "claude-plugin-structure",
            "dependency-updates",
            "documentation",
            "web-build",
        ],
        "acme/plugin": [
            "ci",
            "claude-plugin-structure",
            "documentation",
            "plugin-skills",
        ],
        "acme/python-lib": [
            "ci",
            "claude-plugin-structure",
            "dependency-updates",
            "documentation",
            "package-release",
        ],
        "acme/python-service": [
            "ci",
            "claude-plugin-structure",
            "dependency-updates",
            "documentation",
            "service-runtime",
        ],
        "acme/terraform": [
            "ci",
            "claude-plugin-structure",
            "dependency-updates",
            "documentation",
            "terraform-validation",
        ],
        "acme/unknown": ["ci", "claude-plugin-structure", "documentation"],
    }

    by_repo = {repo["repo"]: repo for repo in result["repos"]}
    assert by_repo["acme/docs"]["checks"]["ci"]["status"] == "not_applicable"
    assert by_repo["acme/docs"]["checks"]["ci"]["detail"] == (
        "predicate not satisfied: capability:ci"
    )
    terraform_dependencies = by_repo["acme/terraform"]["checks"][
        "dependency-updates"
    ]
    assert terraform_dependencies["status"] == "unsupported"
    assert terraform_dependencies["detail"] == (
        "Terraform dependency adapter not implemented"
    )
    assert by_repo["acme/node-web"]["checks"]["web-build"]["status"] == (
        "unsupported"
    )
    assert by_repo["acme/python-lib"]["checks"]["documentation"]["status"] == (
        "unknown"
    )
    assert by_repo["acme/python-lib"]["checks"]["package-release"]["status"] == (
        "not_applicable"
    )

    assert result["aggregate"] == {
        "by_scorecard": {
            "claude-plugin-v1": {"repos": 1, "average_percent": 25.0},
            "docs-v1": {"repos": 1, "average_percent": 50.0},
            "generic-v1": {"repos": 1, "average_percent": 50.0},
            "node-web-v1": {"repos": 1, "average_percent": 25.0},
            "python-library-v1": {"repos": 1, "average_percent": 0.0},
            "python-service-v1": {"repos": 1, "average_percent": 25.0},
            "terraform-v1": {"repos": 1, "average_percent": 25.0},
        }
    }
    assert result["coverage"] == {
        "checks_total": 31,
        "checks_supported": 21,
        "unsupported_by_adapter": {
            "claude.plugin-structure": 1,
            "claude.skills": 1,
            "docs.links": 1,
            "node.dependencies": 1,
            "node.web-build": 1,
            "python.dependencies": 2,
            "python.service-runtime": 1,
            "terraform.dependencies": 1,
            "terraform.validate": 1,
        },
        "unprofiled_repos": ["acme/unprofiled"],
    }


def test_cli_accepts_yaml_and_json_evidence_without_reading_workspace(tmp_path):
    source = yaml.safe_load((FIXTURES / "evidence.yaml").read_text())
    paths = [tmp_path / "evidence.yaml", tmp_path / "evidence.json"]
    paths[0].write_text(yaml.safe_dump(source))
    paths[1].write_text(json.dumps(source))

    outputs = []
    for path in paths:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--evidence",
                str(path),
                "--profiles",
                str(FIXTURES / "profiles.yaml"),
                "--workspace",
                str(tmp_path / "does-not-exist"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(json.loads(completed.stdout))

    assert outputs[0] == outputs[1]
    assert list(outputs[0]) == ["repos", "aggregate", "coverage"]
