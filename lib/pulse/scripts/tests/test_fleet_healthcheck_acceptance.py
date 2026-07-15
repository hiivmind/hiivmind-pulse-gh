"""Acceptance gate for profile-safe fleet healthcheck orchestration."""

from __future__ import annotations

from pathlib import Path

import yaml

from lib.pulse.scripts.check_adapters import AdapterRegistry
from lib.pulse.scripts.healthcheck_dispatch import evaluate_fleet


def _write_profiles(path: Path) -> Path:
    profiles = {
        "repository_profiles": {
            "neutral/scored": {
                "profiles": ["unclassified"],
                "scorecard": "generic-v1",
            },
            "neutral/evidence-gap": {
                "profiles": ["unclassified"],
                "scorecard": "generic-v1",
            },
            "neutral/terraform": {
                "profiles": ["terraform", "infrastructure"],
                "scorecard": "terraform-v1",
            },
        },
        "scorecards": {
            "generic-v1": {
                "checks": [
                    {
                        "id": "documentation",
                        "adapter": "generic.docs",
                        "weight": 1,
                    },
                    {
                        "id": "ci",
                        "adapter": "github.actions",
                        "weight": 1,
                    },
                ]
            },
            "terraform-v1": {
                "extends": "generic-v1",
                "checks": [
                    {
                        "id": "claude-plugin-structure",
                        "adapter": "claude.plugin-structure",
                        "applicability": "profile:claude-plugin",
                        "weight": 7,
                    },
                    {
                        "id": "python-project",
                        "adapter": "python.dependencies",
                        "applicability": "profile:python",
                        "weight": 11,
                    },
                    {
                        "id": "terraform-validation",
                        "adapter": "terraform.validate",
                        "weight": 5,
                    },
                ],
            },
        },
        "adapters": {
            "generic.docs": {"state": "available"},
            "github.actions": {"state": "available"},
            "claude.plugin-structure": {"state": "available"},
            "python.dependencies": {"state": "available"},
            "terraform.validate": {
                "state": "unsupported",
                "reason": "Terraform adapter is not implemented",
            },
        },
    }
    path.write_text(yaml.safe_dump(profiles))
    return path


def test_complete_fleet_path_is_profile_safe_for_neutral_repositories(
    tmp_path, monkeypatch
):
    """Load, resolve, dispatch, evaluate, score, and aggregate one neutral fleet."""
    evaluated_adapters = []
    real_evaluate = AdapterRegistry.evaluate

    def record_real_adapter_evaluation(self, adapter_id, context):
        evaluated_adapters.append((context.repo, adapter_id))
        return real_evaluate(self, adapter_id, context)

    monkeypatch.setattr(AdapterRegistry, "evaluate", record_real_adapter_evaluation)
    evidence = {
        "repos": [
            {
                "repo": "neutral/scored",
                "capabilities": [],
                "files": [
                    "README.md",
                    "docs/index.md",
                    ".github/workflows/ci.yml",
                ],
                "structural_signals": [],
            },
            {
                "repo": "neutral/terraform",
                "capabilities": ["terraform"],
                "files": [
                    "README.md",
                    "docs/index.md",
                    ".github/workflows/ci.yml",
                    "main.tf",
                ],
                "structural_signals": ["terraform-module"],
            },
            {
                "repo": "neutral/truly-unprofiled",
                "capabilities": ["python", "claude-plugin"],
                "files": ["pyproject.toml", "CLAUDE.md"],
                "structural_signals": ["claude-plugin-manifest"],
            },
        ]
    }

    result = evaluate_fleet(
        evidence=evidence,
        profiles_path=_write_profiles(tmp_path / "profiles.yaml"),
        workspace=tmp_path / "must-not-be-inspected",
    )

    by_repo = {repo["repo"]: repo for repo in result["repos"]}
    assert set(by_repo) == {
        "neutral/scored",
        "neutral/evidence-gap",
        "neutral/terraform",
    }
    assert "neutral/truly-unprofiled" not in by_repo
    assert result["coverage"]["unprofiled_repos"] == [
        "neutral/truly-unprofiled"
    ]

    # An authored unclassified repository executes the resolved universal registry only.
    scored = by_repo["neutral/scored"]
    assert set(scored["checks"]) == {"documentation", "ci"}
    assert {check["status"] for check in scored["checks"].values()} == {"pass"}
    assert {
        adapter for repo, adapter in evaluated_adapters if repo == "neutral/scored"
    } == {"generic.docs", "github.actions"}
    assert scored["score"] == scored["total"] == 2

    terraform = by_repo["neutral/terraform"]
    assert "CLAUDE.md" not in evidence["repos"][1]["files"]
    assert "pyproject.toml" not in evidence["repos"][1]["files"]
    assert terraform["checks"]["claude-plugin-structure"]["status"] == (
        "not_applicable"
    )
    assert terraform["checks"]["python-project"]["status"] == "not_applicable"
    for check_id in ("claude-plugin-structure", "python-project"):
        assert terraform["checks"][check_id]["status"] not in {
            "fail",
            "warn",
            "unknown",
        }
    assert not any(
        adapter == "python.dependencies" for _, adapter in evaluated_adapters
    )
    assert not any(
        adapter == "claude.plugin-structure" for _, adapter in evaluated_adapters
    )
    # The high weights prove inapplicable profile checks do not enter scoring.
    assert terraform["score"] == terraform["total"] == 2

    unsupported = terraform["checks"]["terraform-validation"]
    assert unsupported["status"] == "unsupported"
    assert unsupported["status"] != "fail"
    assert terraform["coverage_supported"] == 20
    assert terraform["coverage_total"] == 25
    assert result["coverage"]["unsupported_by_adapter"] == {
        "terraform.validate": 1
    }

    # Missing evidence is a distinct zero-denominator aggregate case.
    evidence_gap = by_repo["neutral/evidence-gap"]
    assert evidence_gap["score"] == evidence_gap["total"] == 0
    assert result["aggregate"]["by_scorecard"]["generic-v1"] == {
        "repos": 2,
        "repos_scored": 1,
        "average_percent": 100.0,
    }
