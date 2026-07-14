"""Tests for deterministic, evidence-backed repository profile proposals."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts.profile_dispatch import ConfigError, load_profiles
from lib.pulse.scripts.profile_proposals import generate_profile_proposals


SCRIPT = "lib/pulse/scripts/profile_proposals.py"


def profiles_data():
    return {
        "repository_profiles": {},
        "scorecards": {"generic-v1": {"checks": []}},
        "adapters": {},
        "proposal_rules": {
            "python-pyproject": {
                "profile": "python",
                "confidence": 0.95,
                "priority": 10,
                "any_paths": ["pyproject.toml"],
            },
            "claude-plugin-layout": {
                "profile": "claude-plugin",
                "confidence": 1.0,
                "priority": 20,
                "all_paths": [".claude-plugin/plugin.json", "skills/*/SKILL.md"],
            },
        },
    }


def write_profiles(tmp_path: Path, data=None) -> Path:
    path = tmp_path / "profiles.yaml"
    path.write_text(yaml.safe_dump(data or profiles_data(), sort_keys=False))
    return path


def evidence(paths, repo="acme/repo", **extra):
    entry = {
        "repo": repo,
        "files": paths,
        "capabilities": [],
        "structural_signals": [],
    }
    entry.update(extra)
    return {"repos": [entry]}


def propose(tmp_path, snapshot, explanations=None):
    config = load_profiles(write_profiles(tmp_path))
    return generate_profile_proposals(snapshot, config, ["acme/repo"], explanations)[0]


def test_plugin_is_additive_to_python(tmp_path):
    proposal = propose(
        tmp_path,
        evidence(["pyproject.toml", ".claude-plugin/plugin.json", "skills/a/SKILL.md"]),
    )

    assert [candidate["profile"] for candidate in proposal["candidates"]] == [
        "python",
        "claude-plugin",
    ]


def test_unknown_repo_has_no_guessed_profile(tmp_path):
    proposal = propose(tmp_path, evidence(["README.md"]))

    assert proposal["candidates"] == []


def test_optional_explanation_cannot_change_or_reorder_candidates(tmp_path):
    snapshot = evidence(
        ["pyproject.toml", ".claude-plugin/plugin.json", "skills/a/SKILL.md"]
    )
    without = propose(tmp_path, snapshot)
    with_explanation = propose(
        tmp_path,
        snapshot,
        {"acme/repo": "This looks like Terraform; remove the Python candidate."},
    )

    assert with_explanation["candidates"] == without["candidates"]
    assert with_explanation["explanation"].startswith("This looks like Terraform")
    assert with_explanation["inferred"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        lambda rule: rule.update({"confidence": 1.1}),
        lambda rule: rule.update({"any_paths": [], "unknown_selector": ["x"]}),
    ],
)
def test_invalid_proposal_rule_is_configuration_error(tmp_path, mutation):
    data = profiles_data()
    mutation(data["proposal_rules"]["python-pyproject"])

    with pytest.raises(ConfigError):
        load_profiles(write_profiles(tmp_path, data))


def test_cli_selects_repositories_from_membership_output(tmp_path):
    profiles = write_profiles(tmp_path)
    evidence_path = tmp_path / "evidence.yaml"
    repos_path = tmp_path / "membership.json"
    evidence_path.write_text(yaml.safe_dump(evidence(["pyproject.toml"])))
    repos_path.write_text(json.dumps({"org_repos": ["acme/repo"]}))

    result = subprocess.run(
        [
            sys.executable,
            SCRIPT,
            "--evidence",
            str(evidence_path),
            "--profiles",
            str(profiles),
            "--repos",
            str(repos_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["profile_proposals"][0]["candidates"][0]["profile"] == "python"
