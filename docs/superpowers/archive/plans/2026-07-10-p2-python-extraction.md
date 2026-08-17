> **ARCHIVED 2026-08-17.** Implementation complete — kept for historical
> reference only. See
> `docs/superpowers/archive/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
> §8.9 for original phase tracking.
>
> ---

# P2 — Deterministic Python Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the heartbeat's polling logic into `lib/pulse/scripts/poll.py` (implementing the lakehouse layering RAW→BRONZE→SILVER→GOLD for the projects source), reduce `hooks/heartbeat.sh` to a thin wrapper, and implement `evaluate_checks.py` for the mechanical healthcheck catalog — all testable against recorded API fixtures.

**Architecture:** Two PEP 723 self-contained scripts run via `uv run` (corpus conventions, scaffolding from P1). `poll.py` owns everything after workspace resolution: rate-limit gate, poll-state bootstrap, per-source change detection, cooldowns, and summary JSON — the bash hook only resolves the workspace root and repo context (interactive-side discovery) and delegates. Network access goes through one seam (`gh_api()`), overridable with recorded fixtures via `PULSE_GH_FIXTURES` for tests. `evaluate_checks.py` is **pure** — the caller fetches API responses to disk; the script only compares data, keeping LLM judgment (and network) out of the deterministic layer.

**Tech Stack:** Python ≥3.10 (pyyaml only), uv, pytest, bash wrapper.

**Spec:** `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` — Part 7, §P2 (P2.1–P2.4). Lakehouse detail: `docs/polymorphic-giggling-bentley.md`. Check catalog: `lib/references/healthcheck-checks.md`.

## Global Constraints

- **Reusable-first:** no `hiivmind` hardcoding anywhere; tests use `testorg`.
- **Assumes P1 landed:** `pyproject.toml`, `lib/pulse/scripts/tests/`, pytest conventions exist. If P1 hasn't landed, do P1 Task 2 Step 1 (pyproject) first.
- **Output contract unchanged (exit criterion):** heartbeat JSON keys identical to the bash implementation — `{"first_run", "stale_sections"}`, `{"skipped", "reason", "remaining"}`, `{"error", "tool"}`, `{"stale_sections", "triggered_workflows", "auto_workflows"}`. The only additive key is `project_changes` (optional, lakehouse GOLD). gh-heartbeat needs **no skill edits**.
- **One intended behavior change (spec 5.2):** per-source results are memoized per run, so two workflows watching the same source both trigger (the bash version updated state on first evaluation, silently starving the second workflow). Document it; don't replicate the bug.
- **D4:** `poll.py` takes explicit `--workspace`; it never discovers. Discovery stays in the bash wrapper (interactive side).
- **Zero additional API calls** for the lakehouse: same single batched GraphQL query, more data extracted.
- **Per-machine transients:** `project-snapshot.json` is already gitignored; `.project-changes.json` must be added to `templates/workspace-gitignore.template`.
- Commit after every task. Version bump to `4.6.0` (or next minor from current) happens once, in Task 5.

---

### Task 1: `poll.py` — core engine, repo-scoped sources, freshness, workflows loop (P2.1 part 1)

**Files:**
- Create: `lib/pulse/scripts/poll.py`
- Test: `lib/pulse/scripts/tests/test_poll.py`
- Create: `lib/pulse/scripts/tests/fixtures/poll/` (recorded API responses)

**Interfaces:**
- Produces: `uv run {PLUGIN_ROOT}/lib/pulse/scripts/poll.py --workspace <root> [--repo owner/name] [--overlay-workflows <dir>] --plugin-root <dir>` → summary JSON on stdout, exit 0 (hook semantics; exit 2 only for usage errors).
- Produces: `gh_api(path, graphql_query=None)` seam; `PULSE_GH_FIXTURES=<dir>` maps a request to `<dir>/<slug>.json` where `slug = re.sub(r"[^A-Za-z0-9._-]", "_", path)` (GraphQL requests use slug `graphql`).
- Task 2 extends this file with the projects source; Task 3's wrapper calls it.

- [ ] **Step 1: Write the fixtures**

`lib/pulse/scripts/tests/fixtures/poll/_rate_limit.json`:

```json
{"rate": {"remaining": 4800}}
```

`lib/pulse/scripts/tests/fixtures/poll/_repos_testorg_widget_pulls_state_open_per_page_1_sort_updated.json`:

```json
[{"number": 7, "title": "Add widgets", "updated_at": "2026-07-10T08:00:00Z"}]
```

(That slug is `/repos/testorg/widget/pulls?state=open&per_page=1&sort=updated` with every non-`[A-Za-z0-9._-]` char replaced by `_`.)

- [ ] **Step 2: Write the failing tests**

`lib/pulse/scripts/tests/test_poll.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest lib/pulse/scripts/tests/test_poll.py -v
```

Expected: FAIL — `poll.py` doesn't exist.

- [ ] **Step 4: Write `lib/pulse/scripts/poll.py`**

```python
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
# (implemented in Task 2 — Task 1 lands this stub so the file is complete)

def check_projects(config: dict, config_dir: Path, state: dict, gold: dict) -> bool:
    return False


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
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest lib/pulse/scripts/tests/test_poll.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/pulse/scripts/poll.py lib/pulse/scripts/tests/test_poll.py lib/pulse/scripts/tests/fixtures/poll/
git commit -m "feat(pulse): poll.py engine — repo-scoped sources, freshness, cooldowns, memoized dedup

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `poll.py` — projects lakehouse (RAW→BRONZE→SILVER→GOLD) (P2.1 part 2)

**Files:**
- Modify: `lib/pulse/scripts/poll.py` (replace the `check_projects` stub)
- Modify: `templates/poll-state.yaml.template` (silver view keys)
- Modify: `templates/workspace-gitignore.template` (add `.project-changes.json`)
- Modify: `lib/patterns/poll-state.md` (document the layers)
- Test: `lib/pulse/scripts/tests/test_poll_projects.py` + fixture `lib/pulse/scripts/tests/fixtures/poll/graphql.json`, `_user.json`

**Interfaces:**
- Consumes: `gh_api`, `state`, `gold` dict from Task 1.
- Produces: BRONZE `{config_dir}/project-snapshot.json`; SILVER `state.projects.{snapshot_hash, item_count, my_assignments, status_distribution, my_summary}`; GOLD `{config_dir}/.project-changes.json` + `project_changes` key in summary JSON with keys `status_changes`, `new_assignments`, `removed_assignments`, `priority_changes`.

- [ ] **Step 1: Write the fixtures**

`lib/pulse/scripts/tests/fixtures/poll/_user.json`:

```json
{"login": "octocat"}
```

`lib/pulse/scripts/tests/fixtures/poll/graphql.json` (one project, two items; octocat assigned to #29):

```json
{"data": {"p0": {"items": {"nodes": [
  {"id": "PVTI_1",
   "content": {"__typename": "Issue", "number": 29, "title": "Fix schema"},
   "fieldValues": {"nodes": [
     {"name": "In progress", "optionId": "47fc9ee4", "field": {"name": "Status"}},
     {"name": "P1", "optionId": "aa11", "field": {"name": "Priority"}},
     {"users": {"nodes": [{"login": "octocat"}]}, "field": {"name": "Assignees"}}
   ]}},
  {"id": "PVTI_2",
   "content": {"__typename": "PullRequest", "number": 30, "title": "Add docs"},
   "fieldValues": {"nodes": [
     {"name": "Backlog", "optionId": "f75ad846", "field": {"name": "Status"}},
     {"users": {"nodes": [{"login": "someone-else"}]}, "field": {"name": "Assignees"}}
   ]}}
]}}}}
```

- [ ] **Step 2: Write the failing tests**

`lib/pulse/scripts/tests/test_poll_projects.py`:

```python
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
```

Run: `uv run pytest lib/pulse/scripts/tests/test_poll_projects.py -v` — expected FAIL (stub returns False).

- [ ] **Step 3: Replace the `check_projects` stub in `poll.py`**

```python
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
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest lib/pulse/scripts/tests/ -v
```

Expected: all tests PASS (Task 1's included — no regressions).

- [ ] **Step 5: Update templates and pattern doc**

In `templates/poll-state.yaml.template`, replace the `projects:` block:

```yaml
  projects:
    item_count: 0
    my_assignments: []
```

with:

```yaml
  projects:
    snapshot_hash: null
    item_count: 0
    my_assignments: []
    status_distribution: []
    my_summary: {}
```

In `templates/workspace-gitignore.template`, append after `.assignments-tmp.json`:

```
.project-changes.json
```

Append to `lib/patterns/poll-state.md` (end of file):

````markdown
## Lakehouse Layers (projects source)

The projects source is layered (see `docs/polymorphic-giggling-bentley.md`);
all layers derive from **one** batched GraphQL query per poll:

| Layer | Artifact | Contents |
|-------|----------|----------|
| RAW | GraphQL response (in-memory) | All catalog projects, items, field values |
| BRONZE | `project-snapshot.json` | Full items + all fields, unfiltered; SHA-256 hash stored as `state.projects.snapshot_hash` — unchanged hash short-circuits derivation |
| SILVER | `poll-state.yaml` → `state.projects.*` | `my_assignments` (enriched with status/priority/size/iteration), `status_distribution`, `my_summary` |
| GOLD | `.project-changes.json` + `project_changes` in heartbeat JSON | `status_changes`, `new_assignments`, `removed_assignments`, `priority_changes` |

Triggers fire on silver-view change (assignments, distribution, or item
count), not on every bronze change. `project-snapshot.json` and
`.project-changes.json` are per-machine transients (gitignored).
````

- [ ] **Step 6: Commit**

```bash
git add lib/pulse/scripts/poll.py lib/pulse/scripts/tests/test_poll_projects.py \
  lib/pulse/scripts/tests/fixtures/poll/ templates/poll-state.yaml.template \
  templates/workspace-gitignore.template lib/patterns/poll-state.md
git commit -m "feat(pulse): projects lakehouse in poll.py — bronze snapshot, silver views, gold changeset

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `heartbeat.sh` thin wrapper (P2.2)

**Files:**
- Modify: `hooks/heartbeat.sh` (full replacement)

**Interfaces:**
- Consumes: `poll.py` CLI from Task 1.
- Produces: identical hook behavior; the hook now requires `gh` + `uv` (jq/yq no longer used by the hook — still required by skills).

- [ ] **Step 1: Replace `hooks/heartbeat.sh` entirely with:**

```bash
#!/usr/bin/env bash
# hiivmind-pulse-gh - SessionStart heartbeat hook (thin wrapper)
# Resolves interactive context (workspace root, repo, overlay) and delegates
# all polling to lib/pulse/scripts/poll.py. See: lib/patterns/poll-state.md

set -euo pipefail

# Resolve workspace root: walk up to the first .hiivmind/github/config.yaml
# carrying a `workspace:` section (repo overlays lack it and are skipped).
# See: lib/patterns/workspace-detection.md § Workspace Root Resolution
WORKSPACE_ROOT=""
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
    if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] \
       && grep -q '^workspace:' "$DIR/.hiivmind/github/config.yaml"; then
        WORKSPACE_ROOT="$DIR"
        break
    fi
    DIR="$(dirname "$DIR")"
done

# Exit early if not initialized
if [[ -z "$WORKSPACE_ROOT" ]]; then
    exit 0
fi

# Check required tools (exit 0 with error JSON so hook doesn't crash the session)
for tool in gh uv; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "{\"error\": \"missing_tool\", \"tool\": \"$tool\"}"
        exit 0
    fi
done

# Repo overlay workflows (D2)
OVERLAY_WORKFLOWS=""
REPO_TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$REPO_TOPLEVEL" && "$REPO_TOPLEVEL" != "$WORKSPACE_ROOT" \
      && -d "$REPO_TOPLEVEL/.hiivmind/github/workflows" ]]; then
    OVERLAY_WORKFLOWS="$REPO_TOPLEVEL/.hiivmind/github/workflows"
fi

# Detect owner/repo from git remote (D3: repo-filtered slice)
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
OWNER_REPO=""
if [[ -n "$REMOTE_URL" ]]; then
    OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's#.*[:/]([^/]+/[^/.]+)(\.git)?$#\1#')
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

exec uv run "$PLUGIN_ROOT/lib/pulse/scripts/poll.py" \
    --workspace "$WORKSPACE_ROOT" \
    --plugin-root "$PLUGIN_ROOT" \
    ${OWNER_REPO:+--repo "$OWNER_REPO"} \
    ${OVERLAY_WORKFLOWS:+--overlay-workflows "$OVERLAY_WORKFLOWS"}
```

- [ ] **Step 2: Verify against the P0 fixture scenario (byte-compat exit criterion)**

```bash
PLUGIN=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
bash -n "$PLUGIN/hooks/heartbeat.sh" && echo "syntax OK"
FIX=$(mktemp -d)
mkdir -p "$FIX/ws/.hiivmind/github/workflows" "$FIX/ws/repo-a/src/deep"
printf 'workspace:\n  login: testorg\n' > "$FIX/ws/.hiivmind/github/config.yaml"
cd "$FIX/ws/repo-a/src/deep"
CLAUDE_PLUGIN_ROOT=$PLUGIN bash "$PLUGIN/hooks/heartbeat.sh"
# Expected: {"first_run": true, "stale_sections": []}
CLAUDE_PLUGIN_ROOT=$PLUGIN bash "$PLUGIN/hooks/heartbeat.sh"
# Expected: {"stale_sections": [], "triggered_workflows": [], "auto_workflows": []}
cd "$PLUGIN" && rm -rf "$FIX"
cd "$(mktemp -d)" && bash "$PLUGIN/hooks/heartbeat.sh"; echo "exit=$?"
# Expected: no output, exit=0
cd "$PLUGIN"
```

Same JSON keys as the bash implementation on the same inputs — the P2 exit criterion. Also run once for real from a repo under the live workspace and eyeball the summary JSON.

- [ ] **Step 3: Commit**

```bash
git add hooks/heartbeat.sh
git commit -m "feat(heartbeat): reduce hook to thin wrapper over poll.py

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `evaluate_checks.py` (P2.3 + P2.4)

**Files:**
- Create: `lib/pulse/scripts/evaluate_checks.py`
- Test: `lib/pulse/scripts/tests/test_evaluate_checks.py` + `lib/pulse/scripts/tests/fixtures/checks/` fixtures

**Interfaces:**
- Produces: `uv run {PLUGIN_ROOT}/lib/pulse/scripts/evaluate_checks.py --repo owner/name --data-dir <dir> [--relationships <yaml>] [--dismissals <healthcheck.yaml>]` → prints one JSON object `{repo, score, total, grade, checks: {...}}` matching the P1 `healthcheck` kind's per-repo shape. **Pure**: no network; the caller (gh-healthcheck skill in P3.2, or a scheduler) fetches API responses into `--data-dir` first.
- Data-dir files (all optional; a missing file makes dependent checks `unknown`): `repo.json` (`GET /repos/{o}/{r}`), `protection.json` (branch protection; omit to mean 404), `rulesets.json`, `labels.json`, `workflows.json` (`actions/workflows`), `releases.json`, `tags.json`, `root-contents.json` (`GET .../contents/`), `github-contents.json` (`GET .../contents/.github`).
- Out of scope (stated in the module docstring): LLM-judgment checks — none exist in the current catalog; any future ones are evaluated by the calling skill and flagged `inferred: true` there.

- [ ] **Step 1: Write the fixtures**

`lib/pulse/scripts/tests/fixtures/checks/good/repo.json`:

```json
{"default_branch": "main",
 "license": {"spdx_id": "MIT"},
 "security_and_analysis": {
   "secret_scanning": {"status": "enabled"},
   "secret_scanning_push_protection": {"status": "enabled"}}}
```

`.../checks/good/protection.json`: `{"enforce_admins": {"enabled": true}, "required_pull_request_reviews": {"required_approving_review_count": 1}}`
`.../checks/good/labels.json`: `[{"name": "bug"}, {"name": "P1"}, {"name": "enhancement"}]`
`.../checks/good/workflows.json`: `{"total_count": 2}`
`.../checks/good/releases.json`: `[{"id": 1, "tag_name": "v1.0.0"}]`
`.../checks/good/tags.json`: `[{"name": "v1.0.0"}]`
`.../checks/good/root-contents.json`: `[{"name": "README.md"}, {"name": "LICENSE"}, {"name": "SECURITY.md"}, {"name": "docs", "type": "dir"}]`
`.../checks/good/github-contents.json`: `[{"name": "CODEOWNERS"}, {"name": "dependabot.yml"}, {"name": "workflows", "type": "dir"}]`
`.../checks/good/relationships.yaml`:

```yaml
project_repo_links:
  - project_number: 2
    repos: [testorg/widget]
```

`.../checks/bare/repo.json`: `{"default_branch": "main", "license": null, "security_and_analysis": {"secret_scanning": {"status": "disabled"}}}`
`.../checks/bare/labels.json`: `[]`
`.../checks/bare/workflows.json`: `{"total_count": 0}`
`.../checks/bare/releases.json`: `[]`
`.../checks/bare/tags.json`: `[]`
`.../checks/bare/root-contents.json`: `[{"name": "main.py"}]`
`.../checks/bare/github-contents.json`: `[]`
(no protection.json, no rulesets.json, no relationships.yaml — bare repo)

- [ ] **Step 2: Write the failing tests**

`lib/pulse/scripts/tests/test_evaluate_checks.py`:

```python
"""Tests for evaluate_checks.py — mechanical healthcheck evaluation."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = "lib/pulse/scripts/evaluate_checks.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures/checks")


def run_checks(data_dir, extra=()):
    return subprocess.run(
        [sys.executable, SCRIPT, "--repo", "testorg/widget",
         "--data-dir", str(data_dir), *extra],
        capture_output=True, text=True)


def test_good_repo_grades_a():
    r = run_checks(FIXTURES / "good",
                   ["--relationships", str(FIXTURES / "good" / "relationships.yaml")])
    out = json.loads(r.stdout)
    statuses = {k: v["status"] for k, v in out["checks"].items()}
    assert statuses["branch_protection"] == "pass"
    assert statuses["project_linkage"] == "pass"
    assert statuses["issue_triage"] == "pass"
    assert statuses["ci_cd"] == "pass"
    assert statuses["releases"] == "pass"
    assert statuses["documentation"] == "pass"
    assert statuses["codeowners"] == "pass"
    assert statuses["security_policy"] == "pass"
    assert statuses["license"] == "pass"
    assert statuses["dependency_management"] == "pass"
    assert statuses["secrets_scanning"] == "pass"
    assert out["grade"] == "A"
    assert out["total"] == 11


def test_bare_repo_fails():
    r = run_checks(FIXTURES / "bare")
    out = json.loads(r.stdout)
    statuses = {k: v["status"] for k, v in out["checks"].items()}
    assert statuses["branch_protection"] == "fail"
    assert statuses["ci_cd"] == "fail"
    assert statuses["documentation"] == "fail"
    assert statuses["license"] == "fail"
    assert statuses["secrets_scanning"] == "fail"
    # no relationships data -> linkage unknown, excluded from total
    assert statuses["project_linkage"] == "unknown"
    assert out["grade"] == "F"
    assert out["total"] == 10


def test_dismissals_honored(tmp_path):
    dismissals = tmp_path / "healthcheck.yaml"
    dismissals.write_text(
        "dismissals:\n  testorg/widget:\n    secrets_scanning:\n"
        "      reason: Do later\n")
    r = run_checks(FIXTURES / "bare", ["--dismissals", str(dismissals)])
    out = json.loads(r.stdout)
    assert out["checks"]["secrets_scanning"]["status"] == "dismissed"
    assert out["total"] == 9   # dismissed + unknown excluded


def test_check_shape_matches_contract():
    r = run_checks(FIXTURES / "bare")
    out = json.loads(r.stdout)
    for c in out["checks"].values():
        assert set(c) >= {"status", "detail", "data"}
```

Run: `uv run pytest lib/pulse/scripts/tests/test_evaluate_checks.py -v` — expected FAIL (script missing).

- [ ] **Step 3: Write `lib/pulse/scripts/evaluate_checks.py`**

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Evaluate the mechanical healthcheck catalog from recorded API data.

Pure data comparison — no network. The caller (gh-healthcheck / a scheduler)
fetches the API responses listed below into --data-dir; this script evaluates
lib/references/healthcheck-checks.md's catalog and prints the per-repo block
of the `healthcheck` result kind (lib/patterns/headless-contract.md) as JSON.

LLM-judgment checks are out of scope here: none exist in the current catalog;
any added later are evaluated by the calling skill and flagged inferred: true.

Data-dir files (missing file => dependent check 'unknown', except where the
catalog defines absence as fail — e.g. protection.json absent means the API
returned 404 when repo.json is present):
  repo.json protection.json rulesets.json labels.json workflows.json
  releases.json tags.json root-contents.json github-contents.json

Usage:
  evaluate_checks.py --repo owner/name --data-dir DIR
                     [--relationships relationships.yaml]
                     [--dismissals healthcheck.yaml]

Scoring (catalog): pass=1, warn=0.5; unknown/dismissed excluded from total.
Grade by score/total fraction: A >= 0.90, B >= 0.72, C >= 0.54, D >= 0.36, F below.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import yaml

BUG_LABELS = {"bug", "defect", "error", "incident"}
PRIORITY_HINTS = {"priority", "p0", "p1", "p2", "p3", "p4", "critical", "urgent"}
DEP_FILES = {"dependabot.yml", "dependabot.yaml", "renovate.json", ".renovaterc",
             ".renovaterc.json"}


def load(data_dir: Path, name: str):
    f = data_dir / name
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return None


def names(listing) -> set[str]:
    return {e.get("name", "") for e in (listing or [])}


def check_branch_protection(d):
    if d["repo"] is None:
        return "unknown", "repo metadata unavailable"
    prot, rules = d["protection"], d["rulesets"]
    active_rulesets = any(r.get("enforcement") == "active" for r in (rules or []))
    if prot is None and not active_rulesets:
        return "fail", "No protection rules and no active rulesets on default branch"
    if prot is not None:
        admins = (prot.get("enforce_admins") or {}).get("enabled", False)
        reviews = (prot.get("required_pull_request_reviews") or {})
        count = reviews.get("required_approving_review_count", 0)
        if not admins or count < 1:
            return "warn", f"Protection exists but enforce_admins: {str(admins).lower()}, required reviews: {count}"
        return "pass", f"Protected ({count} required review(s), enforce_admins)"
    return "pass", "Active ruleset on default branch"


def check_project_linkage(d, repo):
    rel = d["relationships"]
    if rel is None:
        return "unknown", "no relationships data provided"
    links = rel.get("project_repo_links") or []
    linked = [l for l in links if repo in (l.get("repos") or [])]
    if linked:
        return "pass", f"Linked to {len(linked)} project(s)"
    return "fail", "Repo not linked to any project"


def check_issue_triage(d):
    if d["labels"] is None:
        return "unknown", "labels unavailable"
    labels = {l.get("name", "").lower() for l in d["labels"]}
    has_bug = bool(labels & BUG_LABELS)
    has_prio = any(any(h in lbl for h in PRIORITY_HINTS) for lbl in labels)
    if has_bug and has_prio:
        return "pass", "Bug-type and priority labels present"
    if has_bug or has_prio:
        return "warn", "Has bug-type or priority labels, not both"
    return "fail", "Missing both bug-type and priority labels"


def check_ci_cd(d):
    if d["workflows"] is None:
        return "unknown", "workflows unavailable"
    n = d["workflows"].get("total_count", 0)
    return ("pass", f"{n} workflow(s) configured") if n > 0 else ("fail", "No workflow files found")


def check_releases(d):
    if d["releases"] is None and d["tags"] is None:
        return "unknown", "releases/tags unavailable"
    if d["releases"]:
        return "pass", f"{len(d['releases'])} release(s)"
    if d["tags"]:
        return "warn", "Tags exist but no formal releases"
    return "fail", "No releases or tags"


def check_documentation(d):
    root = d["root"]
    if root is None:
        return "unknown", "contents unavailable"
    root_names = names(root)
    has_readme = "README.md" in root_names
    has_extra = "CONTRIBUTING.md" in root_names or "docs" in root_names
    if has_readme and has_extra:
        return "pass", "README ✓, docs/ or CONTRIBUTING ✓"
    if has_readme:
        return "warn", "README exists but no CONTRIBUTING.md and no docs/"
    return "fail", "No README.md"


def check_codeowners(d):
    if d["root"] is None and d["github"] is None:
        return "unknown", "contents unavailable"
    for where, listing in (("CODEOWNERS", d["root"]), (".github/CODEOWNERS", d["github"])):
        if "CODEOWNERS" in names(listing):
            return "pass", f"Found at {where}"
    return "fail", "No CODEOWNERS file found"


def check_security_policy(d):
    if d["root"] is None and d["github"] is None:
        return "unknown", "contents unavailable"
    if "SECURITY.md" in names(d["root"]) or "SECURITY.md" in names(d["github"]):
        return "pass", "SECURITY.md present"
    return "fail", "No SECURITY.md found"


def check_license(d):
    if d["repo"] is None:
        return "unknown", "repo metadata unavailable"
    lic = d["repo"].get("license")
    if lic:
        return "pass", str(lic.get("spdx_id") or lic.get("name") or "present")
    if any(n.startswith("LICENSE") for n in names(d["root"])):
        return "pass", "LICENSE file present"
    return "fail", "No LICENSE file found"


def check_dependency_management(d):
    if d["root"] is None and d["github"] is None:
        return "unknown", "contents unavailable"
    found = (names(d["root"]) | names(d["github"])) & DEP_FILES
    if found:
        return "pass", f"Configured: {sorted(found)[0]}"
    return "fail", "No dependency management tool configured"


def check_secrets_scanning(d):
    if d["repo"] is None:
        return "unknown", "repo metadata unavailable"
    saa = d["repo"].get("security_and_analysis") or {}
    scanning = (saa.get("secret_scanning") or {}).get("status")
    push = (saa.get("secret_scanning_push_protection") or {}).get("status")
    if scanning == "enabled" and push == "enabled":
        return "pass", "Secret scanning + push protection enabled"
    if scanning == "enabled":
        return "warn", "Secret scanning enabled but push protection disabled"
    if scanning is None:
        return "unknown", "secret scanning status not visible (needs admin)"
    return "fail", "Secret scanning not enabled"


def grade_for(score: float, total: int) -> str:
    if total == 0:
        return "F"
    frac = score / total
    for g, floor_ in (("A", 0.90), ("B", 0.72), ("C", 0.54), ("D", 0.36)):
        if frac >= floor_:
            return g
    return "F"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--relationships", default="")
    ap.add_argument("--dismissals", default="")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    d = {
        "repo": load(data_dir, "repo.json"),
        "protection": load(data_dir, "protection.json"),
        "rulesets": load(data_dir, "rulesets.json"),
        "labels": load(data_dir, "labels.json"),
        "workflows": load(data_dir, "workflows.json"),
        "releases": load(data_dir, "releases.json"),
        "tags": load(data_dir, "tags.json"),
        "root": load(data_dir, "root-contents.json"),
        "github": load(data_dir, "github-contents.json"),
        "relationships": (yaml.safe_load(Path(args.relationships).read_text())
                          if args.relationships and Path(args.relationships).exists()
                          else None),
    }

    dismissed: dict = {}
    if args.dismissals and Path(args.dismissals).exists():
        hc = yaml.safe_load(Path(args.dismissals).read_text()) or {}
        for scope in ((hc.get("dismissals") or {}).get(args.repo, {}),
                      (hc.get("dismissals") or {}).get(args.repo.split("/")[-1], {})):
            dismissed.update(scope or {})

    evaluators = {
        "branch_protection": lambda: check_branch_protection(d),
        "project_linkage": lambda: check_project_linkage(d, args.repo),
        "issue_triage": lambda: check_issue_triage(d),
        "ci_cd": lambda: check_ci_cd(d),
        "releases": lambda: check_releases(d),
        "documentation": lambda: check_documentation(d),
        "codeowners": lambda: check_codeowners(d),
        "security_policy": lambda: check_security_policy(d),
        "license": lambda: check_license(d),
        "dependency_management": lambda: check_dependency_management(d),
        "secrets_scanning": lambda: check_secrets_scanning(d),
    }

    checks: dict = {}
    score, total = 0.0, 0
    for cid, fn in evaluators.items():
        if cid in dismissed:
            reason = (dismissed[cid] or {}).get("reason", "")
            checks[cid] = {"status": "dismissed",
                           "detail": f"Dismissed: {reason}", "data": {}}
            continue
        status, detail = fn()
        checks[cid] = {"status": status, "detail": detail, "data": {}}
        if status == "unknown":
            continue
        total += 1
        score += {"pass": 1.0, "warn": 0.5, "fail": 0.0}[status]

    score = math.floor(score * 2) / 2   # keep the 0.5 granularity, no float dust
    print(json.dumps({"repo": args.repo, "score": score, "total": total,
                      "grade": grade_for(score, total), "checks": checks},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest lib/pulse/scripts/tests/test_evaluate_checks.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/pulse/scripts/evaluate_checks.py lib/pulse/scripts/tests/test_evaluate_checks.py \
  lib/pulse/scripts/tests/fixtures/checks/
git commit -m "feat(pulse): evaluate_checks.py — mechanical healthcheck catalog, pure data comparison

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Spec close-out + version bump

**Files:**
- Modify: `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
- Modify: `.claude-plugin/plugin.json`
- Modify: `CLAUDE.md` (add the two scripts to the File Structure block from P1's Task 4)

- [ ] **Step 1: Full-suite verification**

```bash
uv run pytest -q                        # everything green
bash -n hooks/heartbeat.sh              # wrapper syntax OK
```

Also re-run the live sanity check from Task 3 Step 2 (heartbeat from a repo under the live workspace produces a summary JSON with the standard keys).

- [ ] **Step 2: Spec updates**

1. Tick P2.1–P2.4 checkboxes to `- [x]`.
2. §8.9 table: P2 row → `✅ done` with today's date.

- [ ] **Step 3: Version + CLAUDE.md**

1. `.claude-plugin/plugin.json`: bump minor (from `4.5.0` → `4.6.0`, or next minor from current).
2. In CLAUDE.md's File Structure `lib/pulse/scripts/` block, add `poll.py` and `evaluate_checks.py` lines under `validate_result.py`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md \
  .claude-plugin/plugin.json CLAUDE.md
git commit -m "docs(spec): mark P2 complete; bump version to 4.6.0

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Deliverable → Task map (spec coverage)

| Spec deliverable | Task |
|------------------|------|
| P2.1 poll.py — GraphQL + diff extraction, lakehouse RAW→BRONZE→SILVER→GOLD, rate-limit pre-check | Task 1 (engine) + Task 2 (lakehouse) |
| P2.2 heartbeat.sh thin wrapper, output contract unchanged | Task 3 |
| P2.3 evaluate_checks.py — mechanical checks, healthcheck-kind shape, LLM checks out of scope | Task 4 |
| P2.4 tests against recorded API fixtures | Tasks 1, 2, 4 (fixtures under `tests/fixtures/{poll,checks}/`) |
| Exit criteria: byte-compatible heartbeat JSON; check catalog reproduced on fixture repo | Task 3 Step 2 + Task 4 tests |
| Lakehouse plan §5 (template, poll-state.md, gitignore) | Task 2 Step 5 |
