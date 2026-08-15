#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Deterministic run-ledger operations. See lib/patterns/run-ledger.md.

Subcommands: create, next, update, gate-result, lease, renew-lease.
Exit codes: 0 ok, 1 validation/state error, 2 file missing/unparseable,
3 lease actively held by someone else.
"""
import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.pulse.scripts import apply_lock as _apply_lock  # noqa: E402
from lib.pulse.scripts import validate_result as _validate_result  # noqa: E402

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


def _step_repos(s: dict) -> list[str]:
    raw = s.get("repos")
    if raw is None:
        raw = s.get("repo") or ""
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, str) and r]
    return [r for r in str(raw).split(",") if r]


def cmd_create(args):
    steps_in = json.loads(args.steps) if args.steps else [{"id": "run", "repo": ""}]
    check_dag(steps_in)
    steps = [{
        "id": s["id"],
        "repo": s.get("repo", ""),
        "repos": _step_repos(s),
        "depends_on": s.get("depends_on", []),
        "gate": s.get("gate"),
        "has_workflow": bool(s.get("workflow")),
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


def _apply_gate_result(step, satisfied, note=""):
    """Shared gate-clearing logic for both the externally-adjudicated
    `gate-result` command (a human/LLM evaluates prose and reports a
    boolean) and `check-gate` (a registered evaluator computes the boolean
    deterministically from a result file). Mutates `step` in place."""
    step["gate_satisfied"] = satisfied
    step["gate_checked_at"] = now_iso()
    if note:
        step["notes"].append(f"{now_iso()} gate: {note}")
    if satisfied:
        # A gate-only step (pure checkpoint) completes when its gate clears.
        # A gate+workflow step must still run its workflow block: only clear the
        # gate and leave the step non-terminal so classify()/next surfaces it as
        # runnable — the executor then leases, runs the block, and marks it done.
        if step.get("has_workflow"):
            if step["status"] == "blocked-on-gate":
                step["status"] = "pending"
        elif step["status"] in {"pending", "blocked-on-gate"}:
            step["status"] = "done"
            step["finished_at"] = now_iso()
    else:
        step["status"] = "blocked-on-gate"


def cmd_gate_result(args):
    doc = load(args.file)
    step = find_step(doc, args.step)
    if not step.get("gate"):
        die(f"step {args.step} has no gate")
    satisfied = args.satisfied == "true"
    _apply_gate_result(step, satisfied, args.note)
    recompute_status(doc)
    save(args.file, doc)


# --------------------------------------------------------------------------
# check-gate: deterministic gate evaluators over headless result files
# --------------------------------------------------------------------------
#
# `gate-result` records an externally-adjudicated verdict (a human or LLM
# evaluates the step's natural-language `gate` condition and reports true/
# false). `check-gate` is the deterministic counterpart: a registered
# evaluator computes the verdict itself from a validated headless result
# file (see lib/patterns/headless-contract.md), fails closed on any
# missing/malformed/non-conforming evidence, and records it the same way.
# New evaluators register in GATE_EVALUATORS by name — this is the generic
# extension point for future result-driven gates, not a one-off.

def _load_result_kind(path, kind):
    """Load and schema-validate a headless result file. Never raises —
    missing files, unparseable YAML, non-mapping documents, and schema
    violations are all reported as errors so gates built on this helper
    fail closed on bad evidence instead of crashing the ledger operation.
    Returns (data, errors); data is None whenever errors is non-empty."""
    p = Path(path)
    if not p.exists():
        return None, [f"result file not found: {p}"]
    try:
        raw = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        return None, [f"unparseable YAML: {e}"]
    if not isinstance(raw, dict):
        return None, ["result is not a mapping"]
    errors = _validate_result.validate(raw, kind)
    if errors:
        return None, errors
    return raw, []


def evaluate_binding_edges_gate(result_path):
    """`binding_edges_current` — fail-closed release gate over an
    impact-result.yaml (F5). Satisfied only when the result file is
    present, validates cleanly as kind `impact`, and every audited edge is
    current: `edges_stale == 0` and no edge in state `unknown`. A missing
    file, unparseable/malformed YAML, a schema-invalid result, any stale
    edge, or any unknown-state edge all fail closed (satisfied=False) —
    an unauditable or incomplete result is never treated as passing."""
    data, errors = _load_result_kind(result_path, "impact")
    if data is None:
        return False, "; ".join(errors) or "invalid impact result"
    edges = data.get("edges") or []
    stale = [e for e in edges if isinstance(e, dict) and e.get("state") == "stale"]
    unknown = [e for e in edges if isinstance(e, dict) and e.get("state") == "unknown"]
    if stale or unknown:
        parts = []
        if stale:
            parts.append(f"{len(stale)} stale edge(s)")
        if unknown:
            parts.append(f"{len(unknown)} unknown-state edge(s)")
        return False, "; ".join(parts)
    return True, f"{len(edges)} edge(s) current"


def evaluate_merge_detected_gate(result_path, repo=None):
    """`merge_detected` — fail-closed gate over an apply-status result (F11).

    With `repo` it checks that one repo's entry is applied + merged with
    matching observed base/head; without `repo` it checks the whole result
    (a fleet requires every repo applied; a v1 scalar doc is checked as before).
    """
    data, errors = _load_result_kind(result_path, "apply-status")
    if data is None:
        return False, "; ".join(errors) or "invalid apply-status result"
    if repo is not None:
        entry = (data.get("repos") or {}).get(repo)
        if entry is None:
            return False, f"repo {repo} missing from apply-status"
        merged_sha = entry.get("merged_sha")
        if not merged_sha or not isinstance(merged_sha, str):
            return False, f"{repo} merged_sha missing or empty"
        if entry.get("observed_base") != entry.get("intended_base"):
            return False, (
                f"{repo} observed_base mismatch: {entry.get('observed_base')!r} != "
                f"intended_base {entry.get('intended_base')!r}"
            )
        if entry.get("observed_head_sha") != entry.get("expected_head_sha"):
            return False, (
                f"{repo} observed_head_sha mismatch: {entry.get('observed_head_sha')!r} != "
                f"expected_head_sha {entry.get('expected_head_sha')!r}"
            )
        return True, f"merge detected: {merged_sha}"
    if "repos" in data:
        repos = data.get("repos") or {}
        if data.get("state") != "applied":
            return False, f"apply-status state is {data.get('state')!r}, expected 'applied'"
        for r, entry in repos.items():
            merged_sha = entry.get("merged_sha")
            if not merged_sha or not isinstance(merged_sha, str):
                return False, f"{r} merged_sha missing or empty"
            if entry.get("observed_base") != entry.get("intended_base"):
                return False, f"{r} observed_base mismatch"
            if entry.get("observed_head_sha") != entry.get("expected_head_sha"):
                return False, f"{r} observed_head_sha mismatch"
        return True, f"merge detected: {', '.join(str(e.get('merged_sha')) for e in repos.values())}"
    if data.get("state") != "applied":
        return False, f"apply-status state is {data.get('state')!r}, expected 'applied'"
    merged_sha = data.get("merged_sha")
    if not merged_sha or not isinstance(merged_sha, str):
        return False, "merged_sha missing or empty"
    if data.get("observed_base") != data.get("intended_base"):
        return False, (
            f"observed_base mismatch: {data.get('observed_base')!r} != "
            f"intended_base {data.get('intended_base')!r}"
        )
    if data.get("observed_head_sha") != data.get("expected_head_sha"):
        return False, (
            f"observed_head_sha mismatch: {data.get('observed_head_sha')!r} != "
            f"expected_head_sha {data.get('expected_head_sha')!r}"
        )
    return True, f"merge detected: {merged_sha}"


GATE_EVALUATORS = {
    "binding_edges_current": evaluate_binding_edges_gate,
    "merge_detected": evaluate_merge_detected_gate,
}


def cmd_check_gate(args):
    doc = load(args.file)
    step = find_step(doc, args.step)
    if not step.get("gate"):
        die(f"step {args.step} has no gate")
    evaluator = GATE_EVALUATORS.get(args.gate_type)
    if evaluator is None:
        die(f"unknown gate type: {args.gate_type} "
            f"(known: {', '.join(sorted(GATE_EVALUATORS))})")
    satisfied, detail = evaluator(args.result)
    _apply_gate_result(step, satisfied, detail)
    recompute_status(doc)
    save(args.file, doc)
    print(json.dumps({"satisfied": satisfied, "detail": detail}))


class LeaseError(Exception):
    pass


def acquire_lease(file_path, step_id, by, ttl_minutes=120):
    # Namespaced ".lease.lock", NOT ".lock": a future driver-owned fence
    # spanning the whole mutation sequence (plan Global Constraints - "held
    # across the whole mutation sequence ... never independently
    # reacquired") may reasonably claim "{ledger_path}.lock" for itself;
    # this lock only serializes THIS function's own read-modify-write and
    # must never collide with that outer lock's path, or a driver holding
    # its lock while calling into acquire_lease/renew_lease would
    # self-deadlock (flock is per open-file-description, not reentrant
    # across separate os.open() calls even from the same process).
    with _apply_lock.ApplyLock(f"{file_path}.lease.lock"):
        doc = load(file_path)
        step = find_step(doc, step_id)
        lease = step.get("lease")
        ttl = timedelta(minutes=ttl_minutes)
        if lease and lease.get("leased_by") != by:
            age = datetime.now(timezone.utc) - parse_ts(lease["leased_at"])
            if age < ttl:
                raise LeaseError(
                    f"lease held by {lease['leased_by']} "
                    f"({int(age.total_seconds() // 60)} min old)"
                )
        step["lease"] = {
            "leased_by": by,
            "leased_at": now_iso(),
            "token": uuid.uuid4().hex,
        }
        save(file_path, doc)
        return step["lease"]


def renew_lease(file_path, step_id, by, token) -> dict:
    with _apply_lock.ApplyLock(f"{file_path}.lease.lock"):
        doc = load(file_path)
        step = find_step(doc, step_id)
        lease = step.get("lease")
        if not lease:
            raise LeaseError("no active lease")
        if lease.get("token") != token:
            raise LeaseError("lease token mismatch")
        if lease.get("leased_by") != by:
            raise LeaseError(f"lease held by {lease.get('leased_by')}")
        lease["leased_at"] = now_iso()
        save(file_path, doc)
        return lease


def snapshot_audit(
    ledger_path,
    step_id,
    *,
    recorded_proposal_id,
    proposal_digest,
    authorization_digest,
    policy_version="v1",
):
    doc = load(ledger_path)
    find_step(doc, step_id)
    doc.setdefault("state_snapshot", {})[step_id] = {
        "recorded_proposal_id": recorded_proposal_id,
        "proposal_digest": proposal_digest,
        "authorization_digest": authorization_digest,
        "policy_version": policy_version,
        "run_at": now_iso(),
        "actor": doc["actor"].copy(),
    }
    save(ledger_path, doc)


def cmd_lease(args):
    try:
        lease = acquire_lease(args.file, args.step, args.by, args.ttl_minutes)
        print(json.dumps(lease))
    except LeaseError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(3)


def cmd_renew_lease(args):
    try:
        lease = renew_lease(args.file, args.step, args.by, args.token)
        print(json.dumps(lease))
    except LeaseError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(3)


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

    cg = sub.add_parser("check-gate")
    cg.add_argument("--file", required=True)
    cg.add_argument("--step", required=True)
    cg.add_argument("--result", required=True,
                    help="path to the headless result file the evaluator reads")
    cg.add_argument("--gate-type", required=True)
    cg.set_defaults(fn=cmd_check_gate)

    l = sub.add_parser("lease")
    l.add_argument("--file", required=True)
    l.add_argument("--step", required=True)
    l.add_argument("--by", required=True)
    l.add_argument("--ttl-minutes", type=int, default=120)
    l.set_defaults(fn=cmd_lease)

    rl = sub.add_parser("renew-lease")
    rl.add_argument("--file", required=True)
    rl.add_argument("--step", required=True)
    rl.add_argument("--by", required=True)
    rl.add_argument("--token", required=True)
    rl.set_defaults(fn=cmd_renew_lease)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
