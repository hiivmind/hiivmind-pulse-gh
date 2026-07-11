"""Tests for validate_result.py — pulse headless result contract validation."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = "lib/pulse/scripts/validate_result.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures")
KINDS = ["status", "healthcheck", "refresh", "workflow-run"]


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
