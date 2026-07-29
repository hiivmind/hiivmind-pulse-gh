#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Lint workflow YAML files: v1/v2/v3 schema, FSM references, headless policy,
step-DAG acyclicity. See lib/patterns/workflow-execution.md.

Usage: workflow_lint.py <file.yaml> [more files...]

Exit codes: 0 clean, 1 findings (one 'file: message' per line on stderr),
2 a file was missing or unparseable.
"""
import re
import sys
from pathlib import Path

import yaml

TRIGGER_TYPES = {"session_poll", "post_operation", "freshness", "on_demand",
                 "periodic"}
ON_ASK = {"record", "default", "abort"}
ON_MUTATION = {"propose", "allow-listed", "allow"}
PHASE_RE = re.compile(r"^([A-Z][A-Z_]*)(\([^)]*\))?:\s*$")
GOTO_RE = re.compile(r"\bGOTO\s+([A-Z][A-Z_]*)")
PARAM_RE = re.compile(r"\bparams\.([A-Za-z_][A-Za-z0-9_]*)")


def lint_headless(h, errs):
    if not isinstance(h, dict):
        errs.append("headless: must be a mapping")
        return
    if "enabled" in h and not isinstance(h["enabled"], bool):
        errs.append("headless.enabled must be a bool")
    if h.get("on_ask") is not None and h["on_ask"] not in ON_ASK:
        errs.append(f"headless.on_ask invalid: {h['on_ask']}")
    om = h.get("on_mutation")
    if om is not None and om not in ON_MUTATION:
        errs.append(f"headless.on_mutation invalid: {om}")
    allow = h.get("mutation_allowlist")
    if om == "allow-listed" and not (isinstance(allow, list) and allow):
        errs.append("headless.on_mutation allow-listed requires a non-empty mutation_allowlist")
    if allow is not None and not isinstance(allow, list):
        errs.append("headless.mutation_allowlist must be a list")


def lint_pseudocode(text, state, params, errs, ctx=""):
    lines = text.splitlines()
    phases = {m.group(1) for line in lines if (m := PHASE_RE.match(line))}
    for m in GOTO_RE.finditer(text):
        if m.group(1) not in phases:
            errs.append(f"{ctx}GOTO {m.group(1)} has no matching phase label")
    for var in (state or {}):
        if not re.search(rf"\b{re.escape(str(var))}\b", text):
            errs.append(f"{ctx}state variable never referenced: {var}")
    declared = set(params or {})
    for m in PARAM_RE.finditer(text):
        if m.group(1) not in declared:
            errs.append(f"{ctx}params.{m.group(1)} referenced but not declared")


def lint_steps(steps, errs):
    if not isinstance(steps, list) or not steps:
        errs.append("steps: must be a non-empty list")
        return
    ids = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            errs.append(f"steps[{i}] is not a mapping")
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not sid:
            errs.append(f"steps[{i}]: missing id")
            continue
        ids.append(sid)
        if not s.get("repo"):
            errs.append(f"step {sid}: missing repo")
        if not s.get("workflow") and not s.get("gate"):
            errs.append(f"step {sid}: needs workflow, gate, or both")
        if "gate" in s and s["gate"] is not None and \
                (not isinstance(s["gate"], str) or not s["gate"].strip()):
            errs.append(f"step {sid}: gate must be a non-empty string")
    if len(ids) != len(set(ids)):
        errs.append("duplicate step ids")
    idset = set(ids)
    for s in steps:
        if not isinstance(s, dict):
            continue
        for d in s.get("depends_on", []) or []:
            if d not in idset:
                errs.append(f"step {s.get('id')}: unknown dependency {d}")
    # Kahn's for acyclicity
    indeg = {s["id"]: len(s.get("depends_on", []) or [])
             for s in steps if isinstance(s, dict) and s.get("id")}
    queue = [i for i, d in indeg.items() if d == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for s in steps:
            if isinstance(s, dict) and n in (s.get("depends_on", []) or []):
                indeg[s["id"]] -= 1
                if indeg[s["id"]] == 0:
                    queue.append(s["id"])
    if seen != len(indeg):
        errs.append("step dependency cycle detected")


def lint_file(path: Path) -> list[str]:
    doc = yaml.safe_load(path.read_text())
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not a mapping"]
    if not isinstance(doc.get("name"), str) or not doc.get("name"):
        errs.append("missing name")

    bodies = [k for k in ("steps", "workflow", "actions") if k in doc]
    if len(bodies) != 1:
        errs.append(f"exactly one of steps/workflow/actions required, found: {bodies}")

    trig = doc.get("trigger")
    if isinstance(trig, dict) and trig.get("type") not in TRIGGER_TYPES:
        errs.append(f"trigger.type invalid: {trig.get('type')}")
    if "headless" in doc:
        lint_headless(doc["headless"], errs)

    params = doc.get("params") or {}
    if "workflow" in doc and isinstance(doc["workflow"], str):
        lint_pseudocode(doc["workflow"], doc.get("state") or {}, params, errs)
    if "steps" in doc:
        lint_steps(doc["steps"], errs)
        if "repos" in doc and not (isinstance(doc["repos"], list)
                                   and all(isinstance(r, str) for r in doc["repos"])):
            errs.append("repos: must be a list of strings")
        for s in doc["steps"] if isinstance(doc["steps"], list) else []:
            if isinstance(s, dict) and isinstance(s.get("workflow"), str):
                lint_pseudocode(s["workflow"], {}, params, errs,
                                ctx=f"step {s.get('id')}: ")
    return errs


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: workflow_lint.py <file.yaml> [...]", file=sys.stderr)
        return 2
    any_errs = False
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"{arg}: file not found", file=sys.stderr)
            return 2
        try:
            errs = lint_file(path)
        except yaml.YAMLError as e:
            print(f"{arg}: unparseable YAML: {e}", file=sys.stderr)
            return 2
        for e in errs:
            print(f"{arg}: {e}", file=sys.stderr)
            any_errs = True
    return 1 if any_errs else 0


if __name__ == "__main__":
    sys.exit(main())
