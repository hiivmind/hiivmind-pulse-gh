"""Tests for resolve_run.py — deterministic run-ledger operations."""
import json
import subprocess
import sys

import yaml

SCRIPT = "lib/pulse/scripts/resolve_run.py"

STEPS = json.dumps([
    {"id": "tag-lib", "repo": "testorg/lib"},
    {"id": "verify-lib", "repo": "testorg/lib", "depends_on": ["tag-lib"],
     "gate": "release published AND checks green"},
    {"id": "bump-consumers", "repo": ["testorg/app-a", "testorg/app-b"],
     "depends_on": ["verify-lib"]},
])


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


def create(tmp_path, steps=STEPS, run_id="2026-07-11-octocat-100000"):
    r = run("create", "--runs-dir", str(tmp_path), "--workflow", "release-train",
            "--run-id", run_id, "--actor-login", "octocat",
            "--actor-machine", "mba-m4", "--steps", steps,
            "--repos", "testorg/lib,testorg/app-a,testorg/app-b",
            "--params", '{"version": "1.2.0"}')
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_create_writes_ledger(tmp_path):
    path = create(tmp_path)
    doc = yaml.safe_load(open(path))
    assert doc["ledger_version"] == 1
    assert doc["status"] == "running"
    assert doc["params"] == {"version": "1.2.0"}
    assert [s["id"] for s in doc["steps"]] == ["tag-lib", "verify-lib", "bump-consumers"]
    assert all(s["status"] == "pending" for s in doc["steps"])


def test_create_refuses_overwrite(tmp_path):
    create(tmp_path)
    r = run("create", "--runs-dir", str(tmp_path), "--workflow", "release-train",
            "--run-id", "2026-07-11-octocat-100000", "--actor-login", "octocat",
            "--actor-machine", "mba-m4", "--steps", STEPS)
    assert r.returncode == 1
    assert "exists" in r.stderr


def test_create_rejects_cycle(tmp_path):
    cyclic = json.dumps([
        {"id": "a", "repo": "r", "depends_on": ["b"]},
        {"id": "b", "repo": "r", "depends_on": ["a"]},
    ])
    r = run("create", "--runs-dir", str(tmp_path), "--workflow", "w",
            "--run-id", "x", "--actor-login", "o", "--actor-machine", "m",
            "--steps", cyclic)
    assert r.returncode == 1
    assert "cycle" in r.stderr.lower()


def test_next_initial(tmp_path):
    path = create(tmp_path)
    out = json.loads(run("next", "--file", path).stdout)
    assert out["runnable"] == ["tag-lib"]
    assert out["blocked"] == []
    assert out["done"] is False


def test_gate_flow(tmp_path):
    path = create(tmp_path)
    assert run("update", "--file", path, "--step", "tag-lib", "--status", "done",
               "--actor-login", "octocat", "--actor-machine", "mba-m4").returncode == 0
    out = json.loads(run("next", "--file", path).stdout)
    assert out["runnable"] == []
    assert out["blocked"] == [{"id": "verify-lib",
                               "gate": "release published AND checks green"}]
    doc = yaml.safe_load(open(path))
    assert doc["status"] == "blocked-on-gate"

    assert run("gate-result", "--file", path, "--step", "verify-lib",
               "--satisfied", "true").returncode == 0
    out = json.loads(run("next", "--file", path).stdout)
    # gate-only step (no workflow block content is the executor's concern;
    # ledger-wise a satisfied gate with no further work marks the step done)
    assert out["runnable"] == ["bump-consumers"]


def test_completion(tmp_path):
    path = create(tmp_path)
    for sid in ["tag-lib", "verify-lib", "bump-consumers"]:
        if sid == "verify-lib":
            run("gate-result", "--file", path, "--step", sid, "--satisfied", "true")
        else:
            run("update", "--file", path, "--step", sid, "--status", "done")
    out = json.loads(run("next", "--file", path).stdout)
    assert out["done"] is True
    assert yaml.safe_load(open(path))["status"] == "done"


def test_lease_conflict_and_steal(tmp_path):
    path = create(tmp_path)
    assert run("lease", "--file", path, "--step", "tag-lib",
               "--by", "octocat@mba-m4").returncode == 0
    r = run("lease", "--file", path, "--step", "tag-lib", "--by", "hubot@nuc-lab")
    assert r.returncode == 3                       # actively held
    r = run("lease", "--file", path, "--step", "tag-lib", "--by", "hubot@nuc-lab",
            "--ttl-minutes", "0")                  # everything is expired at ttl 0
    assert r.returncode == 0                       # stolen
    doc = yaml.safe_load(open(path))
    step = [s for s in doc["steps"] if s["id"] == "tag-lib"][0]
    assert step["lease"]["leased_by"] == "hubot@nuc-lab"


def test_gate_plus_workflow_step_runs_not_skipped(tmp_path):
    # A step carrying BOTH a gate and a workflow block must still run its block
    # after the gate clears: gate-result may not force it terminal, or its
    # mutations are silently dropped. (Whole-branch review finding, P6.)
    steps = json.dumps([
        {"id": "build", "repo": "r"},
        {"id": "gated-work", "repo": "r", "depends_on": ["build"],
         "gate": "artifact published", "workflow": "EXECUTE:\n  do the thing"},
    ])
    path = create(tmp_path, steps=steps)
    assert run("update", "--file", path, "--step", "build",
               "--status", "done").returncode == 0
    # gate cleared, but the step has work to do → runnable, not done
    assert run("gate-result", "--file", path, "--step", "gated-work",
               "--satisfied", "true").returncode == 0
    out = json.loads(run("next", "--file", path).stdout)
    assert out["runnable"] == ["gated-work"]
    assert out["done"] is False
    step = [s for s in yaml.safe_load(open(path))["steps"]
            if s["id"] == "gated-work"][0]
    assert step["status"] != "done"
    # the executor then runs the block and marks it done → run completes
    run("update", "--file", path, "--step", "gated-work", "--status", "done")
    assert json.loads(run("next", "--file", path).stdout)["done"] is True


def test_gate_only_step_completes_on_satisfy(tmp_path):
    # Guard the other side: a gate-ONLY step (no workflow block) still completes
    # when its gate clears, so downstream steps unblock (existing behavior).
    path = create(tmp_path)  # STEPS' verify-lib is gate-only
    run("update", "--file", path, "--step", "tag-lib", "--status", "done")
    run("gate-result", "--file", path, "--step", "verify-lib", "--satisfied", "true")
    out = json.loads(run("next", "--file", path).stdout)
    assert out["runnable"] == ["bump-consumers"]
    step = [s for s in yaml.safe_load(open(path))["steps"]
            if s["id"] == "verify-lib"][0]
    assert step["status"] == "done"


# --------------------------------------------------------------------------
# check-gate: binding_edges_current (F5 Task 4 release gate)
# --------------------------------------------------------------------------

GATE_STEPS = json.dumps([
    {"id": "audit", "repo": "testorg/app"},
    {"id": "release-gate", "repo": "testorg/app", "depends_on": ["audit"],
     "gate": "binding edges current"},
])


def create_gate_run(tmp_path, run_id="2026-07-19-octocat-100000"):
    return create(tmp_path, steps=GATE_STEPS, run_id=run_id)


def impact_result(edges, edges_stale=None, kind="impact"):
    stale_count = (
        edges_stale if edges_stale is not None
        else sum(1 for e in edges if e.get("state") == "stale")
    )
    return {
        "contract_version": 1,
        "kind": kind,
        "workspace": "testorg",
        "run_at": "2026-07-19T00:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "mba-m4", "mode": "scheduled"},
        "edges_checked": len(edges),
        "edges_stale": stale_count,
        "markers_updated": 0,
        "edges": edges,
        "findings": [],
        "proposed_actions": [],
        "asks_recorded": [],
        "errors": [],
    }


def _edge(state, dependent="testorg/app", upstream="testorg/lib"):
    return {
        "dependent": dependent,
        "upstream": upstream,
        "watch_branch": "main",
        "state": state,
        "tested_sha": "aaa" if state != "unknown" else None,
        "remote_head": "bbb",
        "changed_paths": ["lib/x.py"] if state == "stale" else [],
    }


def write_yaml(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def check_gate(path, result_path, step="release-gate", gate_type="binding_edges_current"):
    return run("check-gate", "--file", path, "--step", step,
               "--result", str(result_path), "--gate-type", gate_type)


def test_check_gate_current_satisfies(tmp_path):
    path = create_gate_run(tmp_path)
    result_path = tmp_path / "impact-result.yaml"
    write_yaml(result_path, impact_result([_edge("current")]))

    r = check_gate(path, result_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["satisfied"] is True

    doc = yaml.safe_load(open(path))
    step = [s for s in doc["steps"] if s["id"] == "release-gate"][0]
    assert step["gate_satisfied"] is True
    assert step["status"] == "done"


def test_check_gate_stale_edge_blocks_closed(tmp_path):
    path = create_gate_run(tmp_path)
    result_path = tmp_path / "impact-result.yaml"
    write_yaml(result_path, impact_result([_edge("current"), _edge("stale")]))

    r = check_gate(path, result_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["satisfied"] is False

    doc = yaml.safe_load(open(path))
    step = [s for s in doc["steps"] if s["id"] == "release-gate"][0]
    assert step["gate_satisfied"] is False
    assert step["status"] == "blocked-on-gate"


def test_check_gate_unknown_edge_blocks_closed(tmp_path):
    path = create_gate_run(tmp_path)
    result_path = tmp_path / "impact-result.yaml"
    write_yaml(result_path, impact_result([_edge("current"), _edge("unknown")]))

    r = check_gate(path, result_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["satisfied"] is False

    step = [s for s in yaml.safe_load(open(path))["steps"]
            if s["id"] == "release-gate"][0]
    assert step["gate_satisfied"] is False


def test_check_gate_missing_result_blocks_closed(tmp_path):
    path = create_gate_run(tmp_path)
    missing_path = tmp_path / "no-such-impact-result.yaml"

    r = check_gate(path, missing_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["satisfied"] is False
    assert "not found" in out["detail"]

    step = [s for s in yaml.safe_load(open(path))["steps"]
            if s["id"] == "release-gate"][0]
    assert step["gate_satisfied"] is False


def test_check_gate_malformed_result_blocks_closed(tmp_path):
    path = create_gate_run(tmp_path)
    result_path = tmp_path / "impact-result.yaml"
    result_path.write_text("not: [valid, yaml structure for this schema\n")

    r = check_gate(path, result_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["satisfied"] is False

    step = [s for s in yaml.safe_load(open(path))["steps"]
            if s["id"] == "release-gate"][0]
    assert step["gate_satisfied"] is False


def test_check_gate_schema_invalid_result_blocks_closed(tmp_path):
    # Valid YAML, but fails impact schema validation (wrong kind).
    path = create_gate_run(tmp_path)
    result_path = tmp_path / "impact-result.yaml"
    write_yaml(result_path, impact_result([_edge("current")], kind="healthcheck"))

    r = check_gate(path, result_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["satisfied"] is False


def test_check_gate_unknown_gate_type_errors(tmp_path):
    path = create_gate_run(tmp_path)
    result_path = tmp_path / "impact-result.yaml"
    write_yaml(result_path, impact_result([_edge("current")]))

    r = check_gate(path, result_path, gate_type="nonsense_gate")
    assert r.returncode == 1
    assert "unknown gate type" in r.stderr.lower()
