"""Tests for freshness_status.py — deterministic staleness from freshness.yaml."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = "lib/pulse/scripts/freshness_status.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


def test_mixed_staleness():
    r = run("--freshness", str(FIXTURES / "freshness-mixed.yaml"),
            "--now", "2026-07-10T12:00:00Z")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    by_id = {s["id"]: s for s in out["sections"]}
    assert by_id["workspace"]["stale"] is False
    assert by_id["projects"]["stale"] is True       # stored stale: false is ignored
    assert by_id["views"]["stale"] is True
    assert by_id["views"]["last_checked"] is None
    assert by_id["teams"]["stale"] is False         # falls back to defaults threshold
    assert by_id["repo_settings"]["stale"] is False  # unquoted yaml timestamp handled
    assert by_id["repo_settings"]["last_checked"] == "2026-07-09T12:00:00Z"  # normalized to str
    assert out["refresh_needed"] is True


def test_all_fresh():
    r = run("--freshness", str(FIXTURES / "freshness-fresh.yaml"),
            "--now", "2026-07-10T12:00:00Z")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["refresh_needed"] is False
    assert all(s["stale"] is False for s in out["sections"])


def test_missing_file_exit_2(tmp_path):
    r = run("--freshness", str(tmp_path / "nope.yaml"))
    assert r.returncode == 2


def test_unparseable_exit_2(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("sections: [unclosed")
    r = run("--freshness", str(bad))
    assert r.returncode == 2
