"""Tests for evaluate_checks.py — mechanical healthcheck evaluation."""
import json
import subprocess
import sys
from pathlib import Path

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
    assert out["checks"]["secrets_scanning"]["status"] == "dismissed"
    assert out["total"] == 9   # dismissed + unknown excluded


def test_check_shape_matches_contract():
    r = run_checks(FIXTURES / "bare")
    out = json.loads(r.stdout)
    for c in out["checks"].values():
        assert set(c) >= {"status", "detail", "data"}
