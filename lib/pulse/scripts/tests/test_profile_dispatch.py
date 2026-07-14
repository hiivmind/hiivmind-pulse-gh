"""Tests for authoritative repository profile and scorecard dispatch."""

from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts import profile_dispatch


def write_yaml(tmp_path: Path, data) -> Path:
    path = tmp_path / "profiles.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def minimal_config():
    return {
        "repository_profiles": {
            "acme/api": {
                "profiles": ["python", "service"],
                "scorecard": "python-service-v1",
            }
        },
        "scorecards": {
            "python-service-v1": {
                "checks": [
                    {
                        "id": "documentation",
                        "adapter": "generic.docs",
                        "weight": 1,
                    }
                ]
            }
        },
        "adapters": {"generic.docs": {"state": "available"}},
    }


def test_loads_explicit_repo_profile(tmp_path):
    config = profile_dispatch.load_profiles(write_yaml(tmp_path, minimal_config()))

    repo = config.repositories["acme/api"]
    assert repo.profiles == ("python", "service")
    assert repo.scorecard == "python-service-v1"
    check = config.scorecards[repo.scorecard].checks[0]
    assert check.adapter == "generic.docs"
    assert check.weight == 1


def test_rejects_unknown_scorecard(tmp_path):
    data = minimal_config()
    data["repository_profiles"]["acme/api"]["scorecard"] = "missing"

    with pytest.raises(profile_dispatch.ConfigError, match="unknown scorecard: missing"):
        profile_dispatch.load_profiles(write_yaml(tmp_path, data))


def test_rejects_unknown_adapter(tmp_path):
    data = minimal_config()
    data["scorecards"]["python-service-v1"]["checks"][0]["adapter"] = "missing"

    with pytest.raises(profile_dispatch.ConfigError, match="unknown adapter: missing"):
        profile_dispatch.load_profiles(write_yaml(tmp_path, data))


def test_loads_explicitly_unsupported_adapter(tmp_path):
    data = minimal_config()
    data["adapters"]["terraform.dependencies"] = {
        "state": "unsupported",
        "reason": "adapter not implemented",
    }

    config = profile_dispatch.load_profiles(write_yaml(tmp_path, data))

    adapter = config.adapters["terraform.dependencies"]
    assert adapter.state == "unsupported"
    assert adapter.reason == "adapter not implemented"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda data: data.update({"profile_proposals": {}}),
            "unknown profile config key: profile_proposals",
        ),
        (
            lambda data: data["repository_profiles"]["acme/api"].update(
                {"confidence": 0.9}
            ),
            "unknown repository profile key: confidence",
        ),
        (
            lambda data: data["scorecards"]["python-service-v1"]["checks"][0].update(
                {"inferred": True}
            ),
            "unknown check key: inferred",
        ),
    ],
)
def test_schema_is_strict(tmp_path, mutate, message):
    data = minimal_config()
    mutate(data)

    with pytest.raises(profile_dispatch.ConfigError, match=message):
        profile_dispatch.load_profiles(write_yaml(tmp_path, data))


def test_rejects_duplicate_profiles(tmp_path):
    data = minimal_config()
    data["repository_profiles"]["acme/api"]["profiles"] = ["python", "python"]

    with pytest.raises(profile_dispatch.ConfigError, match="duplicate profile: python"):
        profile_dispatch.load_profiles(write_yaml(tmp_path, data))
