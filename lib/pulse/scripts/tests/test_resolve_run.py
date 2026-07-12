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
