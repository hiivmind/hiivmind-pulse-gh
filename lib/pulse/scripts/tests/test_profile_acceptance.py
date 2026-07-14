"""Acceptance coverage for heterogeneous repository profile dispatch."""

from pathlib import Path

import yaml

from lib.pulse.scripts.profile_dispatch import dispatch, load_profiles


FIXTURES = Path("lib/pulse/scripts/tests/fixtures/profiles")


def test_heterogeneous_fleet_dispatches_by_authoritative_intent():
    config = load_profiles(FIXTURES / "profiles.yaml")
    evidence = yaml.safe_load((FIXTURES / "evidence.yaml").read_text())

    expected_scorecards = {
        "acme/python-lib": "python-library-v1",
        "acme/python-service": "python-service-v1",
        "acme/node-web": "node-web-v1",
        "acme/docs": "docs-v1",
        "acme/terraform": "terraform-v1",
        "acme/plugin": "claude-plugin-v1",
        "acme/unknown": "generic-v1",
    }

    plans = {repo: dispatch(repo, evidence, config) for repo in expected_scorecards}

    assert {repo: plan.scorecard for repo, plan in plans.items()} == expected_scorecards

    for repo, plan in plans.items():
        if repo == "acme/plugin":
            assert plan.checks["claude-plugin-structure"].state is None
        else:
            assert plan.checks["claude-plugin-structure"].state == "not_applicable"

    terraform = plans["acme/terraform"]
    assert terraform.checks["dependency-updates"].state == "unsupported"
    assert "not implemented" in terraform.checks["dependency-updates"].reason

    unknown = plans["acme/unknown"]
    assert unknown.profiles == ("unclassified",)
    assert set(unknown.checks) == {
        "documentation",
        "ci",
        "claude-plugin-structure",
    }
    assert unknown.checks["documentation"].state is None
    assert unknown.checks["ci"].state == "not_applicable"
