"""Tests for poll.py — heartbeat engine with recorded API fixtures."""
import json
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = "lib/pulse/scripts/poll.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures/poll").resolve()
REPO_ROOT = Path(".").resolve()


def make_workspace(tmp_path, with_workflow=True):
    cfg = tmp_path / ".hiivmind" / "github"
    (cfg / "workflows").mkdir(parents=True)
    (cfg / "config.yaml").write_text("workspace:\n  login: testorg\n  type: organization\n")
    if with_workflow:
        (cfg / "workflows" / "pr-watch.yaml").write_text(
            "name: pr-watch\n"
            "enabled: true\n"
            "auto: false\n"
            "cooldown_minutes: 0\n"
            "trigger:\n  type: session_poll\n  source: pull_requests\n"
        )
    return tmp_path, cfg


def run_poll(workspace, repo="testorg/widget"):
    cmd = [sys.executable, SCRIPT, "--workspace", str(workspace),
           "--plugin-root", str(REPO_ROOT)]
    if repo:
        cmd += ["--repo", repo]
    return subprocess.run(cmd, capture_output=True, text=True,
                          env={"PULSE_GH_FIXTURES": str(FIXTURES), "PATH": "/usr/bin:/bin"})


def test_first_run_bootstraps_poll_state(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    r = run_poll(ws)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out == {"first_run": True, "stale_sections": []}
    assert (cfg / "poll-state.yaml").exists()


def test_second_run_triggers_on_pr_change(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    run_poll(ws)  # bootstrap
    r = run_poll(ws)
    out = json.loads(r.stdout)
    # bash-compatible keys, exactly
    assert set(out) >= {"stale_sections", "triggered_workflows", "auto_workflows"}
    # fixture has 1 open PR vs template count 0 -> pr-watch triggers
    assert out["triggered_workflows"] == ["pr-watch"]
    assert out["auto_workflows"] == []
    state = yaml.safe_load((cfg / "poll-state.yaml").read_text())
    assert state["state"]["pull_requests"]["open_count"] == 1
    assert state["last_polled_at"] is not None


def test_third_run_no_change_no_trigger(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    run_poll(ws)
    run_poll(ws)
    r = run_poll(ws)
    out = json.loads(r.stdout)
    assert out["triggered_workflows"] == []


def test_repo_scoped_source_skipped_without_repo(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    run_poll(ws)
    r = run_poll(ws, repo=None)
    out = json.loads(r.stdout)
    assert out["triggered_workflows"] == []


def test_no_workflows_dir_silent_exit(tmp_path):
    ws, cfg = make_workspace(tmp_path, with_workflow=False)
    (cfg / "workflows").rmdir()
    r = run_poll(ws)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_shared_source_triggers_both_workflows(tmp_path):
    """Intended change vs bash: memoized source result feeds every watcher."""
    ws, cfg = make_workspace(tmp_path)
    (cfg / "workflows" / "pr-watch2.yaml").write_text(
        "name: pr-watch2\nenabled: true\nauto: true\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: pull_requests\n"
    )
    run_poll(ws)
    r = run_poll(ws)
    out = json.loads(r.stdout)
    assert sorted(out["triggered_workflows"]) == ["pr-watch", "pr-watch2"]
    assert out["auto_workflows"] == ["pr-watch2"]


def test_gate_blocked_runs_in_summary(tmp_path, monkeypatch):
    ws, _ = make_workspace(tmp_path)       # existing helper from the P2 tests
    runs = ws / ".hiivmind" / "github" / "runs"
    runs.mkdir()
    (runs / "release-train-2026-07-11-octocat-100000.yaml").write_text(
        "ledger_version: 1\nworkflow: release-train\n"
        "run_id: 2026-07-11-octocat-100000\nstatus: blocked-on-gate\nsteps: []\n")
    (runs / "old-done.yaml").write_text(
        "ledger_version: 1\nrun_id: x\nstatus: done\nsteps: []\n")
    run_poll(ws)                            # bootstrap poll-state.yaml (first_run)
    out = json.loads(run_poll(ws).stdout)  # existing helper
    assert out["gate_blocked_runs"] == ["2026-07-11-octocat-100000"]
