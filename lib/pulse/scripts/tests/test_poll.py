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


def run_poll(workspace, repo="testorg/widget", fixtures=FIXTURES):
    cmd = [sys.executable, SCRIPT, "--workspace", str(workspace),
           "--plugin-root", str(REPO_ROOT)]
    if repo:
        cmd += ["--repo", repo]
    return subprocess.run(cmd, capture_output=True, text=True,
                          env={"PULSE_GH_FIXTURES": str(fixtures), "PATH": "/usr/bin:/bin"})


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


def test_org_repos_first_sight_baselines_then_signature_change_triggers(tmp_path):
    ws, cfg = make_workspace(tmp_path, with_workflow=False)
    (cfg / "workflows" / "fleet-watch.yaml").write_text(
        "name: fleet-watch\nenabled: true\nauto: false\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: org_repos\n"
    )
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "_rate_limit.json").write_text('{"rate":{"remaining":5000}}')
    org_fixture = fixtures / (
        "_orgs_testorg_repos_per_page_100_type_all_sort_full_name_direction_asc.json"
    )
    org_fixture.write_text(json.dumps([
        {"node_id": "R_ONE", "full_name": "testorg/one", "archived": False}
    ]))

    run_poll(ws, fixtures=fixtures)  # poll-state bootstrap
    first_observation = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert first_observation["triggered_workflows"] == []
    state = yaml.safe_load((cfg / "poll-state.yaml").read_text())
    assert set(state["state"]["org_repos"]) == {"signature"}

    org_fixture.write_text(json.dumps([
        {"node_id": "R_ONE", "full_name": "testorg/one", "archived": False},
        {"node_id": "R_TWO", "full_name": "testorg/two", "archived": False},
    ]))
    changed = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert changed["triggered_workflows"] == ["fleet-watch"]


def test_org_repos_unchanged_signature_does_not_trigger(tmp_path):
    ws, cfg = make_workspace(tmp_path, with_workflow=False)
    (cfg / "workflows" / "fleet-watch.yaml").write_text(
        "name: fleet-watch\nenabled: true\nauto: false\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: org_repos\n"
    )
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "_rate_limit.json").write_text('{"rate":{"remaining":5000}}')
    (fixtures / "_orgs_testorg_repos_per_page_100_type_all_sort_full_name_direction_asc.json").write_text(
        '[{"node_id":"R_ONE","full_name":"testorg/one"}]'
    )

    run_poll(ws, fixtures=fixtures)
    run_poll(ws, fixtures=fixtures)
    unchanged = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert unchanged["triggered_workflows"] == []


def make_impact_relationships(cfg, dependent="testorg/downstream",
                              upstream="testorg/upstream", branch="main"):
    (cfg / "relationships.yaml").write_text(
        "repo_dependencies:\n"
        f"  {dependent}:\n"
        "    depends_on:\n"
        f"      - repo: {upstream}\n"
        "        watch_paths:\n"
        "          - \"**\"\n"
        f"        watch_branch: {branch}\n"
        "        integration_tested_sha: abc123\n"
        "        tested_at: \"2026-07-01T10:00:00Z\"\n"
        "    depended_by: []\n"
        "    relationship_type: main\n"
        f"  {upstream}:\n"
        "    depends_on: []\n"
        f"    depended_by:\n      - {dependent}\n"
        "    relationship_type: main\n"
    )


def _ref_fixture_slug(repo, branch):
    import re
    path = f"/repos/{repo}/git/ref/heads/{branch}"
    return re.sub(r"[^A-Za-z0-9._-]", "_", path)


def test_branch_heads_first_sight_baselines_then_move_triggers(tmp_path):
    ws, cfg = make_workspace(tmp_path, with_workflow=False)
    (cfg / "workflows" / "impact-watch.yaml").write_text(
        "name: impact-watch\nenabled: true\nauto: false\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: branch_heads\n"
    )
    make_impact_relationships(cfg)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "_rate_limit.json").write_text('{"rate":{"remaining":5000}}')
    ref_fixture = fixtures / f"{_ref_fixture_slug('testorg/upstream', 'main')}.json"
    ref_fixture.write_text(json.dumps({"object": {"sha": "sha-one"}}))

    run_poll(ws, fixtures=fixtures)  # poll-state bootstrap
    first_observation = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert first_observation["triggered_workflows"] == []
    state = yaml.safe_load((cfg / "poll-state.yaml").read_text())
    assert state["state"]["branch_heads"]["testorg/upstream"]["main"] == "sha-one"

    ref_fixture.write_text(json.dumps({"object": {"sha": "sha-two"}}))
    changed = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert changed["triggered_workflows"] == ["impact-watch"]
    state = yaml.safe_load((cfg / "poll-state.yaml").read_text())
    assert state["state"]["branch_heads"]["testorg/upstream"]["main"] == "sha-two"


def test_branch_heads_unchanged_head_does_not_trigger(tmp_path):
    ws, cfg = make_workspace(tmp_path, with_workflow=False)
    (cfg / "workflows" / "impact-watch.yaml").write_text(
        "name: impact-watch\nenabled: true\nauto: false\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: branch_heads\n"
    )
    make_impact_relationships(cfg)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "_rate_limit.json").write_text('{"rate":{"remaining":5000}}')
    ref_fixture = fixtures / f"{_ref_fixture_slug('testorg/upstream', 'main')}.json"
    ref_fixture.write_text(json.dumps({"object": {"sha": "sha-one"}}))

    run_poll(ws, fixtures=fixtures)
    run_poll(ws, fixtures=fixtures)
    unchanged = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert unchanged["triggered_workflows"] == []


def test_branch_heads_no_relationships_file_does_not_trigger_or_crash(tmp_path):
    ws, cfg = make_workspace(tmp_path, with_workflow=False)
    (cfg / "workflows" / "impact-watch.yaml").write_text(
        "name: impact-watch\nenabled: true\nauto: false\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: branch_heads\n"
    )
    # no relationships.yaml written at all
    run_poll(ws)
    r = run_poll(ws)
    out = json.loads(r.stdout)
    assert r.returncode == 0, r.stderr
    assert out["triggered_workflows"] == []


def test_docs_first_sight_baselines_then_pushed_head_move_triggers(tmp_path):
    ws, cfg = make_workspace(tmp_path, with_workflow=False)
    (cfg / "workflows" / "plan-watch.yaml").write_text(
        "name: plan-watch\nenabled: true\nauto: false\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: docs\n"
    )
    (cfg / "plan-sync.yaml").write_text(
        "docs:\n  - repo: testorg/docs\n    branch: main\n    path: plans/release.md\n"
    )
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "_rate_limit.json").write_text('{"rate":{"remaining":5000}}')
    ref_fixture = fixtures / f"{_ref_fixture_slug('testorg/docs', 'main')}.json"
    ref_fixture.write_text(json.dumps({"object": {"sha": "sha-one"}}))

    run_poll(ws, fixtures=fixtures)
    first_observation = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert first_observation["triggered_workflows"] == []
    state = yaml.safe_load((cfg / "poll-state.yaml").read_text())
    assert state["state"]["docs"]["testorg/docs"]["main"] == "sha-one"

    ref_fixture.write_text(json.dumps({"object": {"sha": "sha-two"}}))
    changed = json.loads(run_poll(ws, fixtures=fixtures).stdout)

    assert changed["triggered_workflows"] == ["plan-watch"]
    state = yaml.safe_load((cfg / "poll-state.yaml").read_text())
    assert state["state"]["docs"]["testorg/docs"]["main"] == "sha-two"
