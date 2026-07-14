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


def inheritance_config(tmp_path, child_checks):
    data = {
        "repository_profiles": {
            "acme/lib": {
                "profiles": ["python", "library"],
                "scorecard": "child",
            }
        },
        "scorecards": {
            "base": {
                "checks": [
                    {"id": "docs", "adapter": "generic.docs", "weight": 1},
                    {"id": "ci", "adapter": "github.actions", "weight": 2},
                ]
            },
            "child": {"extends": "base", "checks": child_checks},
        },
        "adapters": {
            "generic.docs": {"state": "available"},
            "github.actions": {"state": "available"},
            "other.actions": {"state": "available"},
            "terraform.dependencies": {
                "state": "unsupported",
                "reason": "not implemented",
            },
        },
    }
    return profile_dispatch.load_profiles(write_yaml(tmp_path, data))


def test_child_must_explicitly_replace_parent_check(tmp_path):
    config = inheritance_config(
        tmp_path,
        [{"id": "ci", "adapter": "other.actions", "weight": 3}],
    )

    with pytest.raises(
        profile_dispatch.ConfigError,
        match="duplicate check ci requires replace: true",
    ):
        profile_dispatch.resolve_scorecard(config, "child")


def test_child_can_replace_parent_check_once(tmp_path):
    config = inheritance_config(
        tmp_path,
        [
            {
                "id": "ci",
                "adapter": "other.actions",
                "weight": 3,
                "replace": True,
            },
            {"id": "release", "adapter": "generic.docs", "weight": 1},
        ],
    )

    checks = profile_dispatch.resolve_scorecard(config, "child")

    assert [check.id for check in checks] == ["docs", "ci", "release"]
    assert checks[1].adapter == "other.actions"
    assert sum(check.id == "ci" for check in checks) == 1


def test_replace_requires_an_inherited_check(tmp_path):
    config = inheritance_config(
        tmp_path,
        [
            {
                "id": "release",
                "adapter": "generic.docs",
                "weight": 1,
                "replace": True,
            }
        ],
    )

    with pytest.raises(
        profile_dispatch.ConfigError,
        match="check release sets replace but is not inherited",
    ):
        profile_dispatch.resolve_scorecard(config, "child")


def dispatch_config(tmp_path):
    checks = [
        {
            "id": "python",
            "adapter": "generic.docs",
            "weight": 1,
            "applicability": "profile:python",
        },
        {
            "id": "claude-context",
            "adapter": "generic.docs",
            "weight": 1,
            "applicability": "profile:claude-plugin",
        },
        {
            "id": "ci-capability",
            "adapter": "github.actions",
            "weight": 2,
            "applicability": "capability:ci",
        },
        {
            "id": "manifest",
            "adapter": "generic.docs",
            "weight": 1,
            "applicability": "evidence_path:pyproject.toml",
        },
        {
            "id": "terraform-dependencies",
            "adapter": "terraform.dependencies",
            "weight": 2,
            "applicability": "always",
        },
    ]
    return inheritance_config(tmp_path, checks)


def repo_evidence(capabilities=("python", "ci"), files=("pyproject.toml",)):
    return {
        "repos": [
            {
                "repo": "acme/lib",
                "capabilities": list(capabilities),
                "files": list(files),
                "structural_signals": [],
            }
        ]
    }


def test_dispatch_evaluates_all_supported_applicability_predicates(tmp_path):
    config = dispatch_config(tmp_path)

    plan = profile_dispatch.dispatch("acme/lib", repo_evidence(), config)

    assert plan.scorecard == "child"
    assert plan.profiles == ("python", "library")
    assert plan.checks["docs"].state is None
    assert plan.checks["python"].state is None
    assert plan.checks["ci-capability"].state is None
    assert plan.checks["manifest"].state is None
    assert plan.checks["claude-context"].state == "not_applicable"
    assert plan.checks["terraform-dependencies"].state == "unsupported"


def test_applicability_excludes_absent_capability(tmp_path):
    config = dispatch_config(tmp_path)

    plan = profile_dispatch.dispatch(
        "acme/lib", repo_evidence(capabilities=["python"]), config
    )

    assert plan.checks["ci-capability"].state == "not_applicable"


def test_unsupported_predicate_is_configuration_error(tmp_path):
    config = inheritance_config(
        tmp_path,
        [
            {
                "id": "bad",
                "adapter": "generic.docs",
                "weight": 1,
                "applicability": "language:python",
            }
        ],
    )

    with pytest.raises(profile_dispatch.ConfigError, match="unsupported applicability"):
        profile_dispatch.dispatch("acme/lib", repo_evidence(), config)
