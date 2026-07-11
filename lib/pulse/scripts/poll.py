#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Session-poll engine for hiivmind-pulse-gh (extracted from hooks/heartbeat.sh).

Implements the lakehouse layering for the projects source:
RAW (one batched GraphQL query) -> BRONZE (project-snapshot.json, all items,
all fields) -> SILVER (poll-state views: my_assignments, status_distribution,
my_summary) -> GOLD (structured changeset in the summary JSON and
.project-changes.json). See docs/polymorphic-giggling-bentley.md.

Usage:
  poll.py --workspace <workspace_root> --plugin-root <dir>
          [--repo owner/name] [--overlay-workflows <dir>]

Never discovers the workspace (D4): --workspace is explicit. Prints the
heartbeat summary JSON to stdout; exit 0 for all operational outcomes (hook
semantics), 2 for usage errors.

Testing: set PULSE_GH_FIXTURES=<dir> to serve recorded API responses.
A request for <path> reads <dir>/<slug>.json where slug replaces every
non-[A-Za-z0-9._-] char with '_'. GraphQL requests use the slug 'graphql'.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_SCOPED_SOURCES = {"pull_requests", "issues", "actions", "releases",
                       "dependabot", "deployments"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gh_api(path: str, graphql_query: str | None = None):
    """Single network seam. Returns parsed JSON or None on any failure."""
    fixtures = os.environ.get("PULSE_GH_FIXTURES")
    if fixtures:
        slug = "graphql" if graphql_query else re.sub(r"[^A-Za-z0-9._-]", "_", path)
        f = Path(fixtures) / f"{slug}.json"
        if not f.exists():
            return None
        return json.loads(f.read_text())
    if graphql_query:
        cmd = ["gh", "api", "graphql", "-f", f"query={graphql_query}"]
    else:
        cmd = ["gh", "api", path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}


def save_yaml(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def parse_iso(ts: str):
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- sources

def check_pull_requests(repo: str, state: dict) -> bool:
    resp = gh_api(f"/repos/{repo}/pulls?state=open&per_page=1&sort=updated") or []
    curr = len(resp)
    slot = state.setdefault("pull_requests", {})
    if curr != slot.get("open_count", 0):
        slot["open_count"] = curr
        return True
    return False


def check_issues(repo: str, state: dict) -> bool:
    resp = gh_api(f"/repos/{repo}/issues?state=open&per_page=1&sort=updated") or []
    curr = len(resp)
    slot = state.setdefault("issues", {})
    if curr != slot.get("open_count", 0):
        slot["open_count"] = curr
        return True
    return False


def check_actions(repo: str, state: dict) -> bool:
    resp = gh_api(f"/repos/{repo}/actions/runs?per_page=1") or {"workflow_runs": []}
    runs = resp.get("workflow_runs") or []
    curr_id = str(runs[0]["id"]) if runs else ""
    slot = state.setdefault("actions", {})
    prev_id = str(slot.get("latest_run_id") or "")
    if curr_id and curr_id != prev_id:
        slot["latest_run_id"] = curr_id
        slot["latest_run_conclusion"] = str(runs[0].get("conclusion") or "null")
        return True
    return False


def check_releases(repo: str, state: dict) -> bool:
    resp = gh_api(f"/repos/{repo}/releases?per_page=1") or []
    curr_id = str(resp[0]["id"]) if resp else ""
    slot = state.setdefault("releases", {})
    prev_id = str(slot.get("latest_id") or "")
    if curr_id and curr_id != prev_id:
        slot["latest_id"] = curr_id
        slot["latest_tag"] = str(resp[0].get("tag_name") or "null")
        return True
    return False


def check_dependabot(repo: str, state: dict) -> bool:
    resp = gh_api(f"/repos/{repo}/dependabot/alerts?state=open&per_page=1&sort=updated")
    if not isinstance(resp, list):     # 403/404/error -> skip silently
        return False
    curr = len(resp)
    slot = state.setdefault("dependabot", {})
    if curr != slot.get("open_count", 0):
        slot["open_count"] = curr
        return True
    return False


def check_deployments(repo: str, state: dict) -> bool:
    resp = gh_api(f"/repos/{repo}/deployments?per_page=1") or []
    curr_id = str(resp[0]["id"]) if resp else ""
    slot = state.setdefault("deployments", {})
    prev_id = str(slot.get("latest_id") or "")
    if curr_id and curr_id != prev_id:
        slot["latest_id"] = curr_id
        slot["latest_environment"] = str(resp[0].get("environment") or "null")
        return True
    return False


REPO_CHECKS = {
    "pull_requests": check_pull_requests,
    "issues": check_issues,
    "actions": check_actions,
    "releases": check_releases,
    "dependabot": check_dependabot,
    "deployments": check_deployments,
}

# The projects source (lakehouse) is added in check_projects() below.


def evaluate_source(source: str, repo: str, config: dict, config_dir: Path,
                    state: dict, cache: dict, gold: dict) -> bool:
    """Memoized per-source evaluation (spec 5.2: dedup is per run)."""
    if source in cache:
        return cache[source]
    changed = False
    if source in REPO_CHECKS:
        if repo:
            changed = REPO_CHECKS[source](repo, state)
    elif source == "projects":
        changed = check_projects(config, config_dir, state, gold)
    cache[source] = changed
    return changed


# ---------------------------------------------------------------- projects

FIELD_KEYS = ("Status", "Priority", "Size", "Iteration")


def _build_query(catalog: list[dict]) -> tuple[str, list[dict]]:
    """One batched query, expanded fragment (zero additional API calls)."""
    parts = []
    aliases = []
    for idx, proj in enumerate(catalog):
        pid = proj.get("id")
        if not pid:
            continue
        alias = f"p{idx}"
        aliases.append({"alias": alias, "number": proj.get("number"),
                        "title": proj.get("title", "")})
        parts.append(
            f'{alias}: node(id: "{pid}") {{ ... on ProjectV2 {{ items(first: 100) {{ nodes {{ '
            f'id content {{ __typename ... on Issue {{ number title }} '
            f'... on PullRequest {{ number title }} ... on DraftIssue {{ title }} }} '
            f'fieldValues(first: 20) {{ nodes {{ '
            f'... on ProjectV2ItemFieldSingleSelectValue {{ name optionId field {{ ... on ProjectV2FieldCommon {{ name }} }} }} '
            f'... on ProjectV2ItemFieldIterationValue {{ title startDate duration field {{ ... on ProjectV2FieldCommon {{ name }} }} }} '
            f'... on ProjectV2ItemFieldUserValue {{ users(first: 10) {{ nodes {{ login }} }} field {{ ... on ProjectV2FieldCommon {{ name }} }} }} '
            f'}} }} }} }} }} }}'
        )
    return "query { " + " ".join(parts) + " }", aliases


def _bronze_item(node: dict) -> dict:
    content = node.get("content") or {}
    fields: dict = {}
    for fv in ((node.get("fieldValues") or {}).get("nodes") or []):
        fname = ((fv or {}).get("field") or {}).get("name")
        if not fname:
            continue
        if "users" in fv:
            fields[fname] = [u["login"] for u in (fv["users"].get("nodes") or [])]
        elif "name" in fv:                      # single-select
            fields[fname] = fv["name"]
        elif "title" in fv:                     # iteration
            fields[fname] = fv["title"]
    typename = content.get("__typename")
    return {
        "id": node.get("id"),
        "content_type": typename,
        "number": content.get("number"),
        "title": content.get("title", "Draft"),
        "fields": fields,
    }


def _item_type(content_type) -> str:
    return {"Issue": "issue", "PullRequest": "pull_request"}.get(content_type, "draft")


def _silver_views(snapshot: dict, gh_user: str):
    my_assignments, distribution = [], []
    total, by_status, by_priority = 0, {}, {}
    for pnum, proj in snapshot["projects"].items():
        mine = []
        counts: dict = {}
        for item in proj["items"]:
            status = item["fields"].get("Status")
            if status:
                counts[status] = counts.get(status, 0) + 1
            assigned = any(isinstance(v, list) and gh_user in v
                           for v in item["fields"].values())
            if assigned:
                mine.append({
                    "id": item["id"],
                    "number": item["number"],
                    "title": item["title"],
                    "type": _item_type(item["content_type"]),
                    "status": status,
                    "priority": item["fields"].get("Priority"),
                    "size": item["fields"].get("Size"),
                    "iteration": item["fields"].get("Iteration"),
                })
                total += 1
                if status:
                    by_status[status] = by_status.get(status, 0) + 1
                prio = item["fields"].get("Priority")
                if prio:
                    by_priority[prio] = by_priority.get(prio, 0) + 1
        if mine:
            my_assignments.append({"project": proj["title"],
                                   "project_number": int(pnum), "items": mine})
        distribution.append({"project": proj["title"], "project_number": int(pnum),
                             "counts": counts, "total": len(proj["items"])})
    summary = {"total_assigned": total, "by_status": by_status,
               "by_priority": by_priority}
    return my_assignments, distribution, summary


def _flatten(assignments: list) -> dict:
    flat = {}
    for proj in assignments or []:
        for item in proj.get("items", []):
            key = item.get("id") or f"#{item.get('number')}"
            flat[key] = item
    return flat


def _gold_changeset(prev: list, curr: list) -> dict:
    p, c = _flatten(prev), _flatten(curr)
    label = lambda it: f"#{it.get('number')}" if it.get("number") else str(it.get("title"))
    changes = {"status_changes": [], "new_assignments": [],
               "removed_assignments": [], "priority_changes": []}
    for key, item in c.items():
        if key not in p:
            changes["new_assignments"].append({"item": label(item),
                                               "title": item.get("title")})
            continue
        old = p[key]
        if old.get("status") != item.get("status"):
            changes["status_changes"].append({"item": label(item),
                                              "from": old.get("status"),
                                              "to": item.get("status")})
        if old.get("priority") != item.get("priority"):
            changes["priority_changes"].append({"item": label(item),
                                                "from": old.get("priority"),
                                                "to": item.get("priority")})
    for key, item in p.items():
        if key not in c:
            changes["removed_assignments"].append({"item": label(item),
                                                   "title": item.get("title")})
    return changes


def check_projects(config: dict, config_dir: Path, state: dict, gold: dict) -> bool:
    catalog = ((config.get("projects") or {}).get("catalog")) or []
    if not catalog:
        return False
    user = (gh_api("/user") or {}).get("login")
    if not user:
        return False
    query, aliases = _build_query(catalog)
    result = gh_api("graphql", graphql_query=query)
    if not result:
        return False

    # BRONZE: full snapshot, no filtering
    snapshot = {"captured_at": now_iso(), "projects": {}}
    for a in aliases:
        node = ((result.get("data") or {}).get(a["alias"])) or {}
        items = [(n) for n in ((node.get("items") or {}).get("nodes") or []) if n]
        snapshot["projects"][str(a["number"])] = {
            "title": a["title"],
            "items": [_bronze_item(n) for n in items],
        }
    snapshot_json = json.dumps(snapshot["projects"], sort_keys=True)
    snapshot_hash = hashlib.sha256(snapshot_json.encode()).hexdigest()
    (config_dir / "project-snapshot.json").write_text(
        json.dumps(snapshot, indent=2))

    slot = state.setdefault("projects", {})
    if slot.get("snapshot_hash") == snapshot_hash:
        return False                      # fast path: bronze unchanged

    # SILVER: derived views
    my_assignments, distribution, summary = _silver_views(snapshot, user)
    item_count = sum(len(p["items"]) for p in snapshot["projects"].values())
    prev_assignments = slot.get("my_assignments") or []
    prev_distribution = slot.get("status_distribution") or []
    prev_count = slot.get("item_count", 0)

    changed = (
        json.dumps(my_assignments, sort_keys=True) != json.dumps(prev_assignments, sort_keys=True)
        or json.dumps(distribution, sort_keys=True) != json.dumps(prev_distribution, sort_keys=True)
        or item_count != prev_count
    )

    # GOLD: structured changeset
    if changed:
        changes = _gold_changeset(prev_assignments, my_assignments)
        (config_dir / ".project-changes.json").write_text(json.dumps(changes, indent=2))
        gold["project_changes"] = changes

    slot.update({"snapshot_hash": snapshot_hash, "item_count": item_count,
                 "my_assignments": my_assignments,
                 "status_distribution": distribution, "my_summary": summary})
    return changed


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--plugin-root", required=True)
    ap.add_argument("--repo", default="")
    ap.add_argument("--overlay-workflows", default="")
    args = ap.parse_args()

    config_dir = Path(args.workspace) / ".hiivmind" / "github"
    config_path = config_dir / "config.yaml"
    if not config_path.is_file():
        return 0
    config = load_yaml(config_path)

    workflows_dir = config_dir / "workflows"
    overlay_dir = Path(args.overlay_workflows) if args.overlay_workflows else None
    wf_files = sorted(workflows_dir.glob("*.yaml")) if workflows_dir.is_dir() else []
    if overlay_dir and overlay_dir.is_dir():
        wf_files += sorted(overlay_dir.glob("*.yaml"))
    if not wf_files and not workflows_dir.is_dir() and overlay_dir is None:
        return 0
    if not workflows_dir.is_dir() and not (overlay_dir and overlay_dir.is_dir()):
        return 0

    rate = gh_api("/rate_limit") or {}
    remaining = (rate.get("rate") or {}).get("remaining", 100)
    if remaining < 50:
        print(json.dumps({"skipped": True, "reason": "rate_limit_low",
                          "remaining": remaining}))
        return 0

    freshness = load_yaml(config_dir / "freshness.yaml")
    stale_sections = [k for k, v in (freshness.get("sections") or {}).items()
                      if isinstance(v, dict) and v.get("stale") is True]

    poll_state_path = config_dir / "poll-state.yaml"
    if not poll_state_path.is_file():
        template = Path(args.plugin_root) / "templates" / "poll-state.yaml.template"
        try:
            shutil.copy(template, poll_state_path)
        except OSError:
            return 0
        print(json.dumps({"first_run": True, "stale_sections": stale_sections}))
        return 0

    poll_state = load_yaml(poll_state_path)
    state = poll_state.setdefault("state", {})
    now = datetime.now(timezone.utc)

    triggered: list[str] = []
    auto_workflows: list[str] = []
    source_cache: dict[str, bool] = {}
    gold: dict = {}

    for wf_file in wf_files:
        wf = load_yaml(wf_file)
        if not wf or wf.get("enabled", True) is not True:
            continue
        name = str(wf.get("name") or wf_file.stem)
        trigger = wf.get("trigger") or {}
        cooldown = int(wf.get("cooldown_minutes", 5))

        last_run = ((poll_state.get("workflows") or {}).get(name) or {}).get("last_run_at")
        last_dt = parse_iso(last_run) if isinstance(last_run, str) else None
        if last_dt and (now - last_dt).total_seconds() / 60 < cooldown:
            continue

        should = False
        ttype = trigger.get("type")
        if ttype == "session_poll":
            source = str(trigger.get("source") or "")
            if source in REPO_SCOPED_SOURCES and not args.repo:
                continue          # D3: repo-scoped sources need repo context
            should = evaluate_source(source, args.repo, config, config_dir,
                                     state, source_cache, gold)
        elif ttype == "freshness":
            should = bool(stale_sections)

        if should:
            triggered.append(name)
            if wf.get("auto", False) is True:
                auto_workflows.append(name)

    poll_state["last_polled_at"] = now_iso()
    save_yaml(poll_state_path, poll_state)

    summary = {"stale_sections": stale_sections,
               "triggered_workflows": triggered,
               "auto_workflows": auto_workflows}
    if gold.get("project_changes"):
        summary["project_changes"] = gold["project_changes"]

    log_dir = config_dir / "log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "heartbeat.log"
    with log_file.open("a") as fh:
        fh.write(f"[{now_iso()}] {json.dumps(summary)}\n")
    lines = log_file.read_text().splitlines(keepends=True)
    if len(lines) > 500:
        log_file.write_text("".join(lines[-250:]))

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
