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
            "claude-plugin-v1": {
                "repos": 1,
                "repos_scored": 1,
                "average_percent": 25.0,
            },
            "docs-v1": {
                "repos": 1,
                "repos_scored": 1,
                "average_percent": 50.0,
            },
            "generic-v1": {
                "repos": 1,
                "repos_scored": 1,
                "average_percent": 50.0,
            },
            "node-web-v1": {
                "repos": 1,
                "repos_scored": 1,
                "average_percent": 25.0,
            },
            "python-library-v1": {
                "repos": 1,
                "repos_scored": 0,
                "average_percent": None,
            },
            "python-service-v1": {
                "repos": 1,
                "repos_scored": 1,
                "average_percent": 25.0,
            },
            "terraform-v1": {
                "repos": 1,
                "repos_scored": 1,
                "average_percent": 25.0,
            },
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


def test_scorecard_average_excludes_unscored_repositories(tmp_path):
    profiles = {
        "repository_profiles": {
            "acme/scored": {"profiles": [], "scorecard": "docs-v1"},
            "acme/unscored": {"profiles": [], "scorecard": "docs-v1"},
        },
        "scorecards": {
            "docs-v1": {
                "checks": [
                    {"id": "documentation", "adapter": "generic.docs", "weight": 1}
                ]
            }
        },
        "adapters": {"generic.docs": {"state": "available"}},
    }
    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text(yaml.safe_dump(profiles))

    result = evaluate_fleet(
        evidence={
            "repos": [
                {
                    "repo": "acme/scored",
                    "files": ["README.md", "docs/index.md"],
                }
            ]
        },
        profiles_path=profiles_path,
        workspace=tmp_path,
    )

    assert result["aggregate"]["by_scorecard"]["docs-v1"] == {
        "repos": 2,
        "repos_scored": 1,
        "average_percent": 100.0,
    }


def test_entirely_unscored_scorecard_has_null_average(tmp_path):
    profiles = {
        "repository_profiles": {
            "acme/unscored": {"profiles": [], "scorecard": "docs-v1"}
        },
        "scorecards": {
            "docs-v1": {
                "checks": [
                    {"id": "documentation", "adapter": "generic.docs", "weight": 1}
                ]
            }
        },
        "adapters": {"generic.docs": {"state": "available"}},
    }
    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text(yaml.safe_dump(profiles))

    result = evaluate_fleet(
        evidence={"repos": []},
        profiles_path=profiles_path,
        workspace=tmp_path,
    )

    assert result["aggregate"]["by_scorecard"]["docs-v1"] == {
        "repos": 1,
        "repos_scored": 0,
        "average_percent": None,
    }


def test_dismissals_match_full_and_short_repo_names_before_scoring(tmp_path):
    evidence = yaml.safe_load((FIXTURES / "evidence.yaml").read_text())
    dismissals = tmp_path / "healthcheck.yaml"
    dismissals.write_text(
        yaml.safe_dump(
            {
                "dismissals": {
                    "acme/docs": {
                        "documentation": {
                            "reason": "Docs are hosted elsewhere",
                            "dismissed_by": "octocat",
                        },
                        "not-in-scorecard": {"reason": "Must not be invented"},
                    },
                    "docs": {
                        "docs-links": {
                            "reason": "External checker owns this",
                            "review_after": "2027-01-01",
                        }
                    },
                }
            }
        )
    )

    result = evaluate_fleet(
        evidence=evidence,
        profiles_path=FIXTURES / "profiles.yaml",
        workspace=tmp_path,
        dismissals_path=dismissals,
    )

    docs = next(repo for repo in result["repos"] if repo["repo"] == "acme/docs")
    assert "not-in-scorecard" not in docs["checks"]
    for check_id in ("documentation", "docs-links"):
        assert docs["checks"][check_id]["status"] == "not_applicable"
        assert docs["checks"][check_id]["data"]["dismissed"] is True
        assert docs["checks"][check_id]["data"]["dismissal"]["reason"]
        assert docs["checks"][check_id]["data"]["evidence"]["refs"]
    assert docs["score"] == 0
    assert docs["total"] == 0


def test_cli_accepts_optional_dismissals_path(tmp_path):
    dismissals = tmp_path / "healthcheck.yaml"
    dismissals.write_text(
        "dismissals:\n  acme/docs:\n    documentation:\n"
        "      reason: Docs are hosted elsewhere\n"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--evidence",
            str(FIXTURES / "evidence.yaml"),
            "--profiles",
            str(FIXTURES / "profiles.yaml"),
            "--workspace",
            str(tmp_path),
            "--dismissals",
            str(dismissals),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    docs = next(repo for repo in result["repos"] if repo["repo"] == "acme/docs")
    assert docs["checks"]["documentation"]["status"] == "not_applicable"
