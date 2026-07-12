#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Deterministic run-ledger operations. See lib/patterns/run-ledger.md.

Subcommands: create, next, update, gate-result, lease.
Exit codes: 0 ok, 1 validation/state error, 2 file missing/unparseable,
3 lease actively held by someone else.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

LEDGER_VERSION = 1
STEP_STATUSES = {"pending", "running", "blocked-on-gate", "done", "failed", "skipped"}
TERMINAL = {"done", "failed", "skipped"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def load(path):
    p = Path(path)
    if not p.exists():
        die(f"file not found: {p}", 2)
    try:
        return yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        die(f"unparseable YAML: {e}", 2)


def save(path, doc):
    doc["updated_at"] = now_iso()
    Path(path).write_text(yaml.safe_dump(doc, sort_keys=False))


def find_step(doc, sid):
    for s in doc.get("steps", []):
        if s.get("id") == sid:
            return s
    die(f"no such step: {sid}")


def check_dag(steps):
    ids = [s.get("id") for s in steps]
    if len(ids) != len(set(ids)):
        die("duplicate step ids")
    idset = set(ids)
    for s in steps:
        for d in s.get("depends_on", []):
            if d not in idset:
                die(f"step {s['id']}: unknown dependency {d}")
    # Kahn's algorithm
    indeg = {s["id"]: len(s.get("depends_on", [])) for s in steps}
    queue = [i for i, d in indeg.items() if d == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for s in steps:
            if n in s.get("depends_on", []):
                indeg[s["id"]] -= 1
                if indeg[s["id"]] == 0:
                    queue.append(s["id"])
    if seen != len(steps):
        die("dependency cycle detected")


def deps_met(doc, step):
    by_id = {s["id"]: s for s in doc["steps"]}
    return all(by_id[d]["status"] in {"done", "skipped"}
               for d in step.get("depends_on", []))


def classify(doc):
    """Return (runnable_ids, blocked_list) from current step states."""
    runnable, blocked = [], []
    for s in doc["steps"]:
        if s["status"] in TERMINAL or s["status"] == "running":
            continue
        if not deps_met(doc, s):
            continue
        if s.get("gate") and s.get("gate_satisfied") is not True:
            blocked.append({"id": s["id"], "gate": s["gate"]})
        else:
            runnable.append(s["id"])
    return runnable, blocked


def recompute_status(doc):
    steps = doc["steps"]
    runnable, blocked = classify(doc)
    if any(s["status"] == "running" for s in steps):
        doc["status"] = "running"
    elif any(s["status"] == "failed" for s in steps):
        doc["status"] = "failed"
    elif all(s["status"] in {"done", "skipped"} for s in steps):
        doc["status"] = "done"
    elif runnable:
        doc["status"] = "running"
    elif blocked:
        doc["status"] = "blocked-on-gate"
    else:
        doc["status"] = "running"


def cmd_create(args):
    steps_in = json.loads(args.steps) if args.steps else [{"id": "run", "repo": ""}]
    check_dag(steps_in)
    steps = [{
        "id": s["id"],
        "repo": s.get("repo", ""),
        "depends_on": s.get("depends_on", []),
        "gate": s.get("gate"),
        "gate_satisfied": None,
        "gate_checked_at": None,
        "status": "pending",
        "actor": None,
        "started_at": None,
        "finished_at": None,
        "lease": None,
        "notes": [],
    } for s in steps_in]
    runs_dir = Path(args.runs_dir)
    if args.local:
        runs_dir = runs_dir / "local"
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{args.workflow}-{args.run_id}.yaml"
    if path.exists():
        die(f"ledger already exists: {path}")
    doc = {
        "ledger_version": LEDGER_VERSION,
        "workflow": args.workflow,
        "run_id": args.run_id,
        "status": "running",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "actor": {"gh_login": args.actor_login, "machine": args.actor_machine,
                  "mode": args.mode},
        "repos": [r for r in (args.repos or "").split(",") if r],
        "params": json.loads(args.params) if args.params else {},
        "state_snapshot": {},
        "steps": steps,
    }
    recompute_status(doc)
    save(path, doc)
    print(path)


def cmd_next(args):
    doc = load(args.file)
    runnable, blocked = classify(doc)
    print(json.dumps({
        "status": doc.get("status"),
        "runnable": runnable,
        "blocked": blocked,
        "done": doc.get("status") == "done",
    }))


def cmd_update(args):
    if args.status not in STEP_STATUSES:
        die(f"invalid status: {args.status}")
    doc = load(args.file)
    step = find_step(doc, args.step)
    step["status"] = args.status
    if args.status == "running" and not step.get("started_at"):
        step["started_at"] = now_iso()
    if args.status in TERMINAL:
        step["finished_at"] = now_iso()
        step["lease"] = None
    if args.actor_login:
        step["actor"] = {"gh_login": args.actor_login,
                         "machine": args.actor_machine or ""}
    if args.note:
        step["notes"].append(f"{now_iso()} {args.note}")
    recompute_status(doc)
    save(args.file, doc)


def cmd_gate_result(args):
    doc = load(args.file)
    step = find_step(doc, args.step)
    if not step.get("gate"):
        die(f"step {args.step} has no gate")
    satisfied = args.satisfied == "true"
    step["gate_satisfied"] = satisfied
    step["gate_checked_at"] = now_iso()
    if args.note:
        step["notes"].append(f"{now_iso()} gate: {args.note}")
    if satisfied:
        step["status"] = "done" if step["status"] in {"pending", "blocked-on-gate"} \
            else step["status"]
        step.setdefault("finished_at", None)
        if step["status"] == "done":
            step["finished_at"] = now_iso()
    else:
        step["status"] = "blocked-on-gate"
    recompute_status(doc)
    save(args.file, doc)


def cmd_lease(args):
    doc = load(args.file)
    step = find_step(doc, args.step)
    lease = step.get("lease")
    ttl = timedelta(minutes=args.ttl_minutes)
    if lease and lease.get("leased_by") != args.by:
        age = datetime.now(timezone.utc) - parse_ts(lease["leased_at"])
        if age < ttl:
            print(f"error: lease held by {lease['leased_by']} "
                  f"({int(age.total_seconds() // 60)} min old)", file=sys.stderr)
            sys.exit(3)
    step["lease"] = {"leased_by": args.by, "leased_at": now_iso()}
    save(args.file, doc)
    print(json.dumps(step["lease"]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--runs-dir", required=True)
    c.add_argument("--workflow", required=True)
    c.add_argument("--run-id", required=True)
    c.add_argument("--actor-login", required=True)
    c.add_argument("--actor-machine", required=True)
    c.add_argument("--mode", default="interactive",
                   choices=["interactive", "scheduled"])
    c.add_argument("--params", default="")
    c.add_argument("--repos", default="")
    c.add_argument("--steps", default="")
    c.add_argument("--local", action="store_true")
    c.set_defaults(fn=cmd_create)

    n = sub.add_parser("next")
    n.add_argument("--file", required=True)
    n.set_defaults(fn=cmd_next)

    u = sub.add_parser("update")
    u.add_argument("--file", required=True)
    u.add_argument("--step", required=True)
    u.add_argument("--status", required=True)
    u.add_argument("--actor-login", default="")
    u.add_argument("--actor-machine", default="")
    u.add_argument("--note", default="")
    u.set_defaults(fn=cmd_update)

    g = sub.add_parser("gate-result")
    g.add_argument("--file", required=True)
    g.add_argument("--step", required=True)
    g.add_argument("--satisfied", required=True, choices=["true", "false"])
    g.add_argument("--note", default="")
    g.set_defaults(fn=cmd_gate_result)

    l = sub.add_parser("lease")
    l.add_argument("--file", required=True)
    l.add_argument("--step", required=True)
    l.add_argument("--by", required=True)
    l.add_argument("--ttl-minutes", type=int, default=120)
    l.set_defaults(fn=cmd_lease)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
