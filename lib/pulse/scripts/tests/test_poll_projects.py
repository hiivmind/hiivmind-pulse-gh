"""Tests for the projects lakehouse layering in poll.py."""
import json
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = "lib/pulse/scripts/poll.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures/poll").resolve()
REPO_ROOT = Path(".").resolve()

CONFIG = """\
workspace:
  login: testorg
  type: organization
projects:
  default: 2
  catalog:
    - number: 2
      id: PVT_kwTEST
      title: Feature Planner
"""


def make_workspace(tmp_path):
    cfg = tmp_path / ".hiivmind" / "github"
    (cfg / "workflows").mkdir(parents=True)
    (cfg / "config.yaml").write_text(CONFIG)
    (cfg / "workflows" / "project-sync.yaml").write_text(
        "name: project-sync\nenabled: true\nauto: false\ncooldown_minutes: 0\n"
        "trigger:\n  type: session_poll\n  source: projects\n"
    )
    return tmp_path, cfg


def run_poll(workspace):
    return subprocess.run(
        [sys.executable, SCRIPT, "--workspace", str(workspace),
         "--plugin-root", str(REPO_ROOT), "--repo", "testorg/widget"],
        capture_output=True, text=True,
        env={"PULSE_GH_FIXTURES": str(FIXTURES), "PATH": "/usr/bin:/bin"})


def test_bronze_snapshot_written(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    run_poll(ws)          # bootstrap
    r = run_poll(ws)
    snap = json.loads((cfg / "project-snapshot.json").read_text())
    items = snap["projects"]["2"]["items"]
    assert len(items) == 2
    assert items[0]["fields"]["Status"] == "In progress"
    assert items[0]["fields"]["Assignees"] == ["octocat"]


def test_silver_views_derived(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    run_poll(ws)
    run_poll(ws)
    state = yaml.safe_load((cfg / "poll-state.yaml").read_text())["state"]["projects"]
    assert state["item_count"] == 2
    my = state["my_assignments"]
    assert my[0]["project_number"] == 2
    assert my[0]["items"][0]["number"] == 29
    assert my[0]["items"][0]["status"] == "In progress"
    assert my[0]["items"][0]["priority"] == "P1"
    dist = state["status_distribution"][0]["counts"]
    assert dist == {"In progress": 1, "Backlog": 1}
    assert state["my_summary"]["total_assigned"] == 1
    assert state["snapshot_hash"]


def test_trigger_and_gold_changeset_on_first_sight(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    run_poll(ws)
    r = run_poll(ws)
    out = json.loads(r.stdout)
    assert out["triggered_workflows"] == ["project-sync"]
    changes = out["project_changes"]
    assert [c["item"] for c in changes["new_assignments"]] == ["#29"]
    assert json.loads((cfg / ".project-changes.json").read_text()) == changes


def test_fast_path_no_retrigger(tmp_path):
    ws, cfg = make_workspace(tmp_path)
    run_poll(ws)
    run_poll(ws)
    r = run_poll(ws)   # same snapshot hash -> silver skipped, no trigger
    out = json.loads(r.stdout)
    assert out["triggered_workflows"] == []
    assert "project_changes" not in out
