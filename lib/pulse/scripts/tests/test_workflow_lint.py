"""Tests for workflow_lint.py."""
import subprocess
import sys
from pathlib import Path

SCRIPT = "lib/pulse/scripts/workflow_lint.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures")


def run(*paths):
    return subprocess.run([sys.executable, SCRIPT, *[str(p) for p in paths]],
                          capture_output=True, text=True)


def test_valid_v2_clean():
    r = run(FIXTURES / "wf-valid-v2.yaml")
    assert r.returncode == 0, r.stderr


def test_valid_v3_clean():
    r = run(FIXTURES / "wf-valid-v3.yaml")
    assert r.returncode == 0, r.stderr


def test_bad_goto_and_unused_state():
    r = run(FIXTURES / "wf-bad-goto.yaml")
    assert r.returncode == 1
    assert "GOTO REVIEW" in r.stderr
    assert "ghost" in r.stderr


def test_bad_headless():
    r = run(FIXTURES / "wf-bad-headless.yaml")
    assert r.returncode == 1
    assert "on_ask" in r.stderr
    assert "mutation_allowlist" in r.stderr


def test_cyclic_v3():
    r = run(FIXTURES / "wf-cyclic-v3.yaml")
    assert r.returncode == 1
    assert "cycle" in r.stderr.lower()


def test_multiple_files_aggregate():
    r = run(FIXTURES / "wf-valid-v2.yaml", FIXTURES / "wf-bad-goto.yaml")
    assert r.returncode == 1


def test_missing_file_exit_2(tmp_path):
    r = run(tmp_path / "nope.yaml")
    assert r.returncode == 2
