"""Tests for validate_result.py — pulse headless result contract validation."""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = "lib/pulse/scripts/validate_result.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures")
KINDS = ["status", "healthcheck", "refresh", "workflow-run", "fleet-membership"]


def run_validator(path, kind):
    return subprocess.run(
        [sys.executable, SCRIPT, str(path), "--kind", kind],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_valid_fixture_passes(kind):
    r = run_validator(FIXTURES / f"{kind}-valid.yaml", kind)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("kind", KINDS)
def test_invalid_fixture_fails_with_errors(kind):
    r = run_validator(FIXTURES / f"{kind}-invalid.yaml", kind)
    assert r.returncode == 1
    assert r.stderr.strip(), "expected one error per line on stderr"


def test_kind_mismatch(tmp_path):
    r = run_validator(FIXTURES / "status-valid.yaml", "refresh")
    assert r.returncode == 1
    assert "kind mismatch" in r.stderr


def test_missing_actor_reported():
    r = run_validator(FIXTURES / "status-invalid.yaml", "status")
    assert "actor" in r.stderr


def test_missing_file_exit_2(tmp_path):
    r = run_validator(tmp_path / "nope.yaml", "status")
    assert r.returncode == 2


def test_unparseable_yaml_exit_2(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("kind: [unclosed")
    r = run_validator(bad, "status")
    assert r.returncode == 2


@pytest.mark.parametrize(
    "status",
    ["pass", "warn", "fail", "unknown", "not_applicable", "unsupported", "error"],
)
def test_healthcheck_accepts_exact_profile_states(tmp_path, status):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["repos"][0]["checks"]["branch_protection"]["status"] = status
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 0, result.stderr


def test_healthcheck_rejects_legacy_dismissed_state(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["repos"][0]["checks"]["branch_protection"]["status"] = "dismissed"
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "status invalid: dismissed" in result.stderr


def test_healthcheck_requires_scorecard_coverage_and_check_identity(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    repo = doc["repos"][0]
    repo.pop("scorecard", None)
    repo.pop("coverage_supported", None)
    repo.pop("coverage_total", None)
    for check in repo["checks"].values():
        check.pop("check_id", None)
        check.pop("adapter", None)
        check.pop("weight", None)
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "scorecard" in result.stderr
    assert "coverage_supported" in result.stderr
    assert "check_id" in result.stderr
    assert "adapter" in result.stderr
    assert "weight" in result.stderr


def test_healthcheck_requires_fleet_coverage(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc.pop("coverage")
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "missing required key: coverage" in result.stderr


@pytest.mark.parametrize(
    ("container", "key"),
    [
        ("top", "score"),
        ("top", "total"),
        ("top", "grade"),
        ("top", "aggregate_score"),
        ("top", "aggregate_total"),
        ("top", "aggregate_grade"),
        ("aggregate", "score"),
        ("aggregate", "total"),
        ("aggregate", "grade"),
        ("aggregate", "aggregate_score"),
        ("aggregate", "aggregate_total"),
        ("aggregate", "aggregate_grade"),
    ],
)
def test_healthcheck_rejects_mixed_fleet_grade_keys(tmp_path, container, key):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    target = doc if container == "top" else doc["aggregate"]
    target[key] = 100
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert f"forbidden mixed fleet grade key: {container}.{key}" in result.stderr


def test_healthcheck_allows_unrelated_common_contract_fields(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["metadata"] = {"scheduler": "nightly"}
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 0, result.stderr


def test_healthcheck_governance_template_uses_only_new_last_run_fields():
    template = yaml.safe_load(Path("templates/healthcheck.yaml.template").read_text())

    assert template["last_run"] == {
        "run_at": None,
        "by_scorecard": {},
        "coverage": {
            "checks_total": 0,
            "checks_supported": 0,
            "unsupported_by_adapter": {},
            "unprofiled_repos": [],
        },
    }


def test_healthcheck_requires_scorecard_aggregate_fields(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    entry = doc["aggregate"]["by_scorecard"]["github-governance-v1"]
    entry.pop("repos")
    entry.pop("repos_scored")
    entry.pop("average_percent")
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "aggregate.by_scorecard.github-governance-v1.repos" in result.stderr
    assert "aggregate.by_scorecard.github-governance-v1.repos_scored" in result.stderr
    assert "aggregate.by_scorecard.github-governance-v1.average_percent" in result.stderr


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("coverage", "checks_total"), True),
        (("coverage", "checks_supported"), -1),
        (("coverage", "unsupported_by_adapter", "generic.docs"), 1.5),
        (
            (
                "aggregate",
                "by_scorecard",
                "github-governance-v1",
                "average_percent",
            ),
            "100",
        ),
    ],
)
def test_healthcheck_rejects_invalid_fleet_summary_types(tmp_path, path, value):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result_path = tmp_path / "healthcheck.yaml"
    result_path.write_text(yaml.safe_dump(doc))

    result = run_validator(result_path, "healthcheck")

    assert result.returncode == 1


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("repos", 0, "coverage_total"), True),
        (("repos", 0, "checks", "branch_protection", "weight"), -1),
    ],
)
def test_healthcheck_rejects_invalid_numeric_metadata(tmp_path, path, value):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result_path = tmp_path / "healthcheck.yaml"
    result_path.write_text(yaml.safe_dump(doc))

    result = run_validator(result_path, "healthcheck")

    assert result.returncode == 1
    assert "non-negative number" in result.stderr


def test_membership_explanation_requires_inferred_marker(tmp_path):
    doc = yaml.safe_load((FIXTURES / "fleet-membership-valid.yaml").read_text())
    doc["profile_proposals"][0]["explanation"] = "Inferred explanation"
    path = tmp_path / "fleet-membership.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "fleet-membership")

    assert result.returncode == 1
    assert "inferred: true" in result.stderr
