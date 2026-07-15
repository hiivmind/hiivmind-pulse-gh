"""Tests for evaluate_checks.py — mechanical healthcheck evaluation."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.pulse.scripts.evaluate_checks import score_checks

SCRIPT = "lib/pulse/scripts/evaluate_checks.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures/checks")


def run_checks(data_dir, extra=()):
    return subprocess.run(
        [sys.executable, SCRIPT, "--repo", "testorg/widget",
         "--data-dir", str(data_dir), *extra],
        capture_output=True, text=True)


def test_good_repo_grades_a():
    r = run_checks(FIXTURES / "good",
                   ["--relationships", str(FIXTURES / "good" / "relationships.yaml")])
    out = json.loads(r.stdout)
    statuses = {k: v["status"] for k, v in out["checks"].items()}
    assert statuses["branch_protection"] == "pass"
    assert statuses["project_linkage"] == "pass"
    assert statuses["issue_triage"] == "pass"
    assert statuses["ci_cd"] == "pass"
    assert statuses["releases"] == "pass"
    assert statuses["documentation"] == "pass"
    assert statuses["codeowners"] == "pass"
    assert statuses["security_policy"] == "pass"
    assert statuses["license"] == "pass"
    assert statuses["dependency_management"] == "pass"
    assert statuses["secrets_scanning"] == "pass"
    assert out["grade"] == "A"
    assert out["total"] == 11


def test_bare_repo_fails():
    r = run_checks(FIXTURES / "bare")
    out = json.loads(r.stdout)
    statuses = {k: v["status"] for k, v in out["checks"].items()}
    assert statuses["branch_protection"] == "fail"
    assert statuses["ci_cd"] == "fail"
    assert statuses["documentation"] == "fail"
    assert statuses["license"] == "fail"
    assert statuses["secrets_scanning"] == "fail"
    # no relationships data -> linkage unknown, excluded from total
    assert statuses["project_linkage"] == "unknown"
    assert out["grade"] == "F"
    assert out["total"] == 10


def test_dismissals_honored(tmp_path):
    dismissals = tmp_path / "healthcheck.yaml"
    dismissals.write_text(
        "dismissals:\n  testorg/widget:\n    secrets_scanning:\n"
        "      reason: Do later\n")
    r = run_checks(FIXTURES / "bare", ["--dismissals", str(dismissals)])
    out = json.loads(r.stdout)
    assert out["checks"]["secrets_scanning"]["status"] == "not_applicable"
    assert out["checks"]["secrets_scanning"]["data"]["dismissed"] is True
    assert out["total"] == 9   # dismissed + unknown excluded


def test_check_shape_matches_contract():
    r = run_checks(FIXTURES / "bare")
    out = json.loads(r.stdout)
    assert set(out) >= {
        "scorecard",
        "coverage_supported",
        "coverage_total",
    }
    for check_id, check in out["checks"].items():
        assert set(check) >= {
            "check_id",
            "adapter",
            "weight",
            "status",
            "detail",
            "data",
        }
        assert check["check_id"] == check_id


def block(status, weight):
    return {
        "check_id": status,
        "adapter": "test.adapter",
        "weight": weight,
        "status": status,
        "detail": "",
        "data": {},
    }


def test_non_applicable_and_unsupported_do_not_enter_denominator():
    checks = {
        "ci": block("pass", weight=2),
        "claude": block("not_applicable", weight=1),
        "cargo": block("unsupported", weight=2),
    }

    result = score_checks(checks)

    assert result.score == 2
    assert result.total == 2
    assert result.coverage_supported == 3
    assert result.coverage_total == 5


def test_unknown_and_error_are_unscored_but_coverage_supported():
    checks = {
        "known": block("warn", weight=2),
        "unknown": block("unknown", weight=3),
        "error": block("error", weight=4),
    }

    result = score_checks(checks)

    assert result.score == 1
    assert result.total == 2
    assert result.coverage_supported == 9
    assert result.coverage_total == 9


@pytest.mark.parametrize("status", ["pass", "unsupported", "not_applicable"])
@pytest.mark.parametrize("weight", [float("nan"), float("inf"), float("-inf"), -1])
def test_score_checks_rejects_nonfinite_or_negative_weight_in_every_state(
    status, weight
):
    with pytest.raises(ValueError, match="invalid check weight"):
        score_checks({"unsafe": block(status, weight)})
