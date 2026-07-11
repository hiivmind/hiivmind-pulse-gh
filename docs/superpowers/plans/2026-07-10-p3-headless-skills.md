# P3 — Headless Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three headless skill variants — `gh-status-headless`, `gh-healthcheck-headless`, `gh-refresh-headless` — each writing a contract-valid result file with zero prompts, so the P5 scheduler has composable building blocks.

**Architecture:** Each skill is a corpus-style headless SKILL.md: `inputs:` frontmatter (explicit paths, no discovery — D4), a State block, numbered phases with declared outputs, and ABORT-still-emits-result semantics. The LLM orchestrates; deterministic Python computes: staleness math goes into a new `freshness_status.py`, healthcheck evaluation reuses P2's `evaluate_checks.py`, and every result file is gated by P1's `validate_result.py` before the run reports success.

**Tech Stack:** Markdown skills, Python ≥3.10 (PEP 723 + pyyaml, `uv run`), gh CLI, yq/jq.

**Spec:** `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` — Part 4, §P3 (P3.1–P3.3).

## Global Constraints

- **Reusable-first:** no `hiivmind` hardcoding anywhere except steps explicitly marked **(dogfood verification)**. Skills use `{workspace_path}` / `{login}` placeholders.
- **P1/P2 must be executed first.** This plan consumes: `lib/patterns/headless-contract.md` schemas; `uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py <file> --kind <k>` (exit 0/1/2); `uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/evaluate_checks.py --repo owner/name --data-dir DIR [--relationships <yaml>] [--dismissals <healthcheck.yaml>]` (prints `{repo, score, total, grade, checks}` JSON); the root `pyproject.toml` (testpaths `lib/pulse/scripts/tests`). If any of these is missing, STOP — execute the P1/P2 plans first.
- **D4 — headless never discovers:** every skill takes an explicit `workspace_path` input. No walk-up, no `git rev-parse`.
- **Zero prompts:** no AskUserQuestion, no STOP-and-wait. Judgment calls are recorded in the result file.
- **ABORT emits a result:** every abort path writes a contract-valid result file with `errors[]` populated before stopping. A missing result file must be indistinguishable from a crashed run — so never exit without writing one.
- **Actor block** (required on all kinds): `gh_login` = `gh api user --jq .login` (fallback string `"unknown"` + an `errors[]` entry), `machine` = `hostname -s`, `mode` = the skill's `mode` input (`interactive | scheduled`, default `scheduled`).
- **Result files:** default path `{workspace_path}/.hiivmind/github/{kind}-result.yaml`; before writing, verify the workspace `.gitignore` contains a `*-result.yaml` line (append if missing — corpus rule).
- Commit after every task. Version bump once, in the close-out task: nominal `4.7.0` (if P4 landed first and took 4.7.0, use the next unused minor).

## File Structure

| File | Responsibility |
|---|---|
| `lib/pulse/scripts/freshness_status.py` (new) | Deterministic staleness computation from freshness.yaml |
| `lib/pulse/scripts/tests/test_freshness_status.py` + 2 fixtures (new) | Tests for the above |
| `skills/gh-status-headless/SKILL.md` (new) | P3.1 — status pre-check → status-result.yaml |
| `skills/gh-healthcheck-headless/SKILL.md` (new) | P3.2 — fleet governance audit → healthcheck-result.yaml + committed healthcheck.yaml update |
| `skills/gh-refresh-headless/SKILL.md` (new) | P3.3 — decision-replay config sync → refresh-result.yaml |
| `skills/gh-refresh/SKILL.md` (modify) | Decision capture: record refreshed sections into config `automation.refresh_sections` |
| `templates/config.yaml.template` (modify) | Add `automation:` block |
| `CLAUDE.md`, spec, `.claude-plugin/plugin.json` (modify) | Close-out |

---

### Task 1: `freshness_status.py` — deterministic staleness

**Files:**
- Create: `lib/pulse/scripts/freshness_status.py`
- Create: `lib/pulse/scripts/tests/fixtures/freshness-mixed.yaml`, `lib/pulse/scripts/tests/fixtures/freshness-fresh.yaml`
- Test: `lib/pulse/scripts/tests/test_freshness_status.py`

**Interfaces:**
- Consumes: freshness.yaml shape (`defaults.threshold_hours`, `sections.<id>.{threshold_hours, last_checked}` — see `templates/freshness.yaml.template`).
- Produces: `uv run {PLUGIN_ROOT}/lib/pulse/scripts/freshness_status.py --freshness <file> [--now <ISO>]` → prints one JSON object `{"sections": [{"id": str, "stale": bool, "last_checked": str|null}], "refresh_needed": bool}` — exactly the `sections` + `refresh_needed` payload of the P1 `status` kind. Exit 0 ok, 2 file missing/unparseable. Tasks 2 and 5 call this.

- [ ] **Step 1: Write the fixtures**

`lib/pulse/scripts/tests/fixtures/freshness-mixed.yaml`:

```yaml
defaults:
  threshold_hours: 168
sections:
  workspace:
    threshold_hours: 720
    last_checked: "2026-07-01T12:00:00Z"   # 216h old, threshold 720h -> fresh
    stale: false
  projects:
    threshold_hours: 168
    last_checked: "2026-07-01T12:00:00Z"   # 216h old, threshold 168h -> stale (recomputed; stored flag ignored)
    stale: false
  views:
    threshold_hours: 24
    last_checked: null                      # never checked -> stale
    stale: true
  teams:
    last_checked: "2026-07-09T12:00:00Z"   # 24h old, defaults 168h -> fresh
  repo_settings:
    last_checked: 2026-07-09T12:00:00Z     # UNQUOTED — pyyaml parses this to a datetime object
```

`lib/pulse/scripts/tests/fixtures/freshness-fresh.yaml`:

```yaml
defaults:
  threshold_hours: 168
sections:
  workspace:
    last_checked: "2026-07-10T11:00:00Z"
  projects:
    threshold_hours: 24
    last_checked: "2026-07-10T00:00:00Z"   # 12h < 24h -> fresh
```

- [ ] **Step 2: Write the failing tests**

`lib/pulse/scripts/tests/test_freshness_status.py`:

```python
"""Tests for freshness_status.py — deterministic staleness from freshness.yaml."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = "lib/pulse/scripts/freshness_status.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


def test_mixed_staleness():
    r = run("--freshness", str(FIXTURES / "freshness-mixed.yaml"),
            "--now", "2026-07-10T12:00:00Z")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    by_id = {s["id"]: s for s in out["sections"]}
    assert by_id["workspace"]["stale"] is False
    assert by_id["projects"]["stale"] is True       # stored stale: false is ignored
    assert by_id["views"]["stale"] is True
    assert by_id["views"]["last_checked"] is None
    assert by_id["teams"]["stale"] is False         # falls back to defaults threshold
    assert by_id["repo_settings"]["stale"] is False  # unquoted yaml timestamp handled
    assert by_id["repo_settings"]["last_checked"] == "2026-07-09T12:00:00Z"  # normalized to str
    assert out["refresh_needed"] is True


def test_all_fresh():
    r = run("--freshness", str(FIXTURES / "freshness-fresh.yaml"),
            "--now", "2026-07-10T12:00:00Z")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["refresh_needed"] is False
    assert all(s["stale"] is False for s in out["sections"])


def test_missing_file_exit_2(tmp_path):
    r = run("--freshness", str(tmp_path / "nope.yaml"))
    assert r.returncode == 2


def test_unparseable_exit_2(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("sections: [unclosed")
    r = run("--freshness", str(bad))
    assert r.returncode == 2
```

- [ ] **Step 3: Run tests to verify they fail for the right reason**

Run: `uv run pytest lib/pulse/scripts/tests/test_freshness_status.py -v`
Expected: FAIL/ERROR — `freshness_status.py` does not exist (interpreter exits 2 with "No such file"; the two exit-2 tests may pass by accident, the JSON tests must fail).

- [ ] **Step 4: Write the script**

`lib/pulse/scripts/freshness_status.py`:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Compute per-section staleness from a freshness.yaml file.

Timestamps are the authority: any stored `stale:` flag is ignored and staleness
is recomputed as (now - last_checked) > threshold_hours, with null last_checked
always stale. Output is the `sections` + `refresh_needed` payload of the
`status` result kind (lib/patterns/headless-contract.md).

Usage: freshness_status.py --freshness <freshness.yaml> [--now <ISO 8601 UTC>]

Exit codes: 0 ok (JSON on stdout), 2 file missing or unparseable.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_THRESHOLD_HOURS = 168


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freshness", required=True)
    ap.add_argument("--now", default="")
    args = ap.parse_args()

    path = Path(args.freshness)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    import yaml
    try:
        doc = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        print(f"error: unparseable YAML: {e}", file=sys.stderr)
        return 2

    now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
    default_threshold = (doc.get("defaults") or {}).get(
        "threshold_hours", DEFAULT_THRESHOLD_HOURS)

    sections = []
    for sid, s in (doc.get("sections") or {}).items():
        if not isinstance(s, dict):
            continue
        last = s.get("last_checked")
        threshold = s.get("threshold_hours", default_threshold)
        # pyyaml parses unquoted ISO timestamps to datetime; normalize to str + UTC
        if isinstance(last, datetime):
            checked = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
            last = checked.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if last is None:
            stale = True
        else:
            try:
                age_hours = (now - parse_ts(str(last))).total_seconds() / 3600
                stale = age_hours > threshold
            except ValueError:
                stale = True
        sections.append({"id": sid, "stale": stale, "last_checked": last})

    print(json.dumps({"sections": sections,
                      "refresh_needed": any(s["stale"] for s in sections)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_freshness_status.py -v`
Expected: 4 tests PASS. Then `uv run pytest -q` — the whole suite (P1 + P2 tests) still green.

- [ ] **Step 6: Commit**

```bash
git add lib/pulse/scripts/freshness_status.py lib/pulse/scripts/tests/
git commit -m "feat(pulse): freshness_status.py — deterministic staleness for headless status

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `gh-status-headless` (P3.1)

**Files:**
- Create: `skills/gh-status-headless/SKILL.md`

**Interfaces:**
- Consumes: `freshness_status.py` (Task 1), `validate_result.py --kind status` (P1), `status` schema in `lib/patterns/headless-contract.md`.
- Produces: `status-result.yaml` at `{workspace_path}/.hiivmind/github/status-result.yaml` (or `result_path` input). The P5 scheduler gates on its `refresh_needed`.

- [ ] **Step 1: Write the skill**

`skills/gh-status-headless/SKILL.md` with exactly this content:

````markdown
---
name: gh-status-headless
description: >
  Headless workspace status pre-check for schedulers and orchestrators. Computes per-section
  config freshness and API rate limit, writes status-result.yaml (kind: status) per the headless
  result contract. Zero prompts; explicit inputs only — never discovers a workspace. Use when:
  a scheduled run must decide whether a refresh is warranted, an orchestrator gates on
  refresh_needed. Trigger phrases: "headless status", "status headless", "scheduled status check".
inputs:
  workspace_path: "required — absolute path to the workspace root (directory containing .hiivmind/github/)"
  result_path: "optional — where to write the result (default: {workspace_path}/.hiivmind/github/status-result.yaml)"
  mode: "optional — actor mode recorded in the result: interactive | scheduled (default: scheduled)"
outputs:
  result_file: "status-result.yaml conforming to lib/patterns/headless-contract.md (kind: status)"
author: hiivmind
---

# Headless Status Pre-Check

Cheap, read-only pre-check: is the workspace config fresh, and is API budget available?
Orchestrators read the result **file**, not this skill's prose output.

## Path Convention

`{PLUGIN_ROOT}` = plugin root (where plugin.json lives). Scripts run as
`uv run {PLUGIN_ROOT}/lib/pulse/scripts/<script>.py`.

## Contract

- **Zero prompts.** Never ask the user anything.
- **Explicit inputs only** (D4). If `workspace_path` was not provided, ABORT — do not walk up.
- **Every exit writes a result file** — including every ABORT below.

## State

```
computed:
  CONFIG_DIR   = {workspace_path}/.hiivmind/github
  RESULT_PATH  = {result_path input, or CONFIG_DIR/status-result.yaml}
  RUN_AT       = $(date -u +%Y-%m-%dT%H:%M:%SZ)  (captured once, at start)
  LOGIN        = yq -r '.workspace.login' CONFIG_DIR/config.yaml   ("unknown" until Phase 1)
  GH_LOGIN     = $(gh api user --jq .login)       ("unknown" on failure, + errors[] entry)
  MACHINE      = $(hostname -s)
  MODE         = {mode input, default "scheduled"}
  ERRORS       = []   (accumulate strings; goes into errors[])
```

## Phase 1: VALIDATE

**Outputs:** validated CONFIG_DIR, LOGIN.

1. If `workspace_path` input missing → ABORT `"missing required input: workspace_path"`.
2. If `CONFIG_DIR/config.yaml` missing, or `grep -q '^workspace:' CONFIG_DIR/config.yaml`
   fails → ABORT `"not a workspace root: {workspace_path}"`.
3. If `gh` CLI unavailable (`command -v gh`) → ABORT `"gh CLI not found"`.
4. Set LOGIN from config. Verify gitignore coverage: if `CONFIG_DIR/.gitignore` exists and
   lacks a `*-result.yaml` line, append it.

## Phase 2: GATHER

**Outputs:** SECTIONS, REFRESH_NEEDED, RATE_LIMIT.

1. Freshness (deterministic):

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/freshness_status.py" \
  --freshness "${CONFIG_DIR}/freshness.yaml"
```

   - Exit 0 → SECTIONS and REFRESH_NEEDED from the JSON.
   - Exit 2 (missing/unparseable freshness.yaml) → SECTIONS = [], REFRESH_NEEDED = true
     (unknown freshness must trigger a refresh, never silently skip one), append
     `"freshness.yaml missing or unparseable"` to ERRORS.

2. Rate limit:

```bash
gh api rate_limit --jq '.resources.core.remaining'
```

   - Success → RATE_LIMIT = the integer.
   - Failure → RATE_LIMIT = null, append `"rate_limit query failed"` to ERRORS (not an abort).

## Phase 3: WRITE + VALIDATE

**Outputs:** RESULT_PATH written and validated.

1. Write RESULT_PATH:

```yaml
contract_version: 1
kind: status
workspace: {LOGIN}
run_at: {RUN_AT}
actor:
  gh_login: {GH_LOGIN}
  machine: {MACHINE}
  mode: {MODE}
sections: {SECTIONS}          # [{id, stale, last_checked}, ...]
rate_limit_remaining: {RATE_LIMIT}
refresh_needed: {REFRESH_NEEDED}
errors: {ERRORS}
```

2. Validate:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind status
```

   Exit ≠ 0 means this skill has a bug — report the validator's stderr verbatim.

3. Print a one-line summary for logs (informational only — the file is the contract):
   `status: refresh_needed={REFRESH_NEEDED} sections_stale={count} rate_limit={RATE_LIMIT}`

## ABORT semantics

On any ABORT: write RESULT_PATH with `sections: []`, `rate_limit_remaining: null`,
`refresh_needed: false`, `errors: [<abort reason>, ...]`, all common fields populated
(LOGIN may be `"unknown"` if config was unreadable), then validate and stop. If even
CONFIG_DIR is unusable, write to the `result_path` input; if neither is available,
write `status-result.yaml` in the current directory and say so.

## Related

- `lib/patterns/headless-contract.md` — the schema this writes
- `lib/patterns/workspace-detection.md` — D4: why this skill never discovers
- `skills/gh-refresh-headless/` — what an orchestrator runs when refresh_needed
````

- [ ] **Step 2: Live verification (dogfood verification)**

```bash
PLUGIN=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
WS=/Users/nathanielramm/git/hiivmind
```

Execute the skill's phases manually against `workspace_path=$WS` (follow SKILL.md exactly), then:

```bash
uv run "$PLUGIN/lib/pulse/scripts/validate_result.py" "$WS/.hiivmind/github/status-result.yaml" --kind status && echo VALID
yq -r '.refresh_needed' "$WS/.hiivmind/github/status-result.yaml"
```

Expected: `VALID`; `refresh_needed` is `true` or `false` (not an error).

- [ ] **Step 3: Broken-input verification (exit criterion: broken input still yields a valid result)**

```bash
BROKEN=$(mktemp -d)
```

Execute the skill with `workspace_path=$BROKEN` and `result_path=$BROKEN/status-result.yaml`. Then:

```bash
uv run "$PLUGIN/lib/pulse/scripts/validate_result.py" "$BROKEN/status-result.yaml" --kind status && echo VALID
yq -r '.errors[0]' "$BROKEN/status-result.yaml"
```

Expected: `VALID`; first error mentions `not a workspace root`.

- [ ] **Step 4: Commit**

```bash
git add skills/gh-status-headless/
git commit -m "feat(skills): gh-status-headless — contract-valid status pre-check

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `gh-healthcheck-headless` (P3.2)

**Files:**
- Create: `skills/gh-healthcheck-headless/SKILL.md`

**Interfaces:**
- Consumes: `evaluate_checks.py` (P2; `--repo owner/name --data-dir DIR [--relationships] [--dismissals]` → `{repo, score, total, grade, checks}` JSON), `validate_result.py --kind healthcheck`, config `repositories[]` catalog (`full_name`, `name` keys), committed `healthcheck.yaml` (repos keyed by short name; `dismissals:` map).
- Produces: `healthcheck-result.yaml` (repos keyed by `owner/name` full names per contract); updated committed `healthcheck.yaml` (`last_run` + `repos.{short-name}` blocks, dismissals preserved).

- [ ] **Step 1: Write the skill**

`skills/gh-healthcheck-headless/SKILL.md` with exactly this content:

````markdown
---
name: gh-healthcheck-headless
description: >
  Headless multi-repo governance audit. Fetches per-repo API data, evaluates the 11-check catalog
  deterministically via evaluate_checks.py honoring team dismissals, writes healthcheck-result.yaml
  (kind: healthcheck) and updates the committed healthcheck.yaml governance record. Zero prompts;
  explicit inputs only. Use when: a scheduled fleet audit runs, an orchestrator needs repo grades.
  Trigger phrases: "headless healthcheck", "fleet healthcheck", "scheduled governance audit".
inputs:
  workspace_path: "required — absolute path to the workspace root (directory containing .hiivmind/github/)"
  repos: "optional — comma-separated repo filter (full owner/name or short names); default: every entry in the config repositories[] catalog"
  result_path: "optional — where to write the result (default: {workspace_path}/.hiivmind/github/healthcheck-result.yaml)"
  update_governance: "optional — also update the committed healthcheck.yaml (default: true)"
  mode: "optional — actor mode recorded in the result: interactive | scheduled (default: scheduled)"
outputs:
  result_file: "healthcheck-result.yaml conforming to lib/patterns/headless-contract.md (kind: healthcheck)"
  governance: "updated {workspace_path}/.hiivmind/github/healthcheck.yaml (unless update_governance: false)"
author: hiivmind
---

# Headless Fleet Healthcheck

The 11-check governance catalog (`lib/references/healthcheck-checks.md`) evaluated per repo,
deterministically, with dismissals honored. Read-only against GitHub — fixes are never applied.

## Path Convention

`{PLUGIN_ROOT}` = plugin root (where plugin.json lives).

## Contract

- **Zero prompts. Explicit inputs only (D4). Every exit writes a result file.**
- A repo that fails to evaluate does not abort the run: record an `errors[]` entry and
  continue with the remaining repos (partial fleets are valid results).

## State

```
computed:
  CONFIG_DIR   = {workspace_path}/.hiivmind/github
  RESULT_PATH  = {result_path input, or CONFIG_DIR/healthcheck-result.yaml}
  RUN_AT       = $(date -u +%Y-%m-%dT%H:%M:%SZ)
  LOGIN        = yq -r '.workspace.login' CONFIG_DIR/config.yaml
  GH_LOGIN     = $(gh api user --jq .login)   ("unknown" on failure, + errors[] entry)
  MACHINE      = $(hostname -s)
  MODE         = {mode input, default "scheduled"}
  REPOS        = resolved full_name list (Phase 1)
  REPO_RESULTS = []   (per-repo JSON blocks from evaluate_checks.py)
  ERRORS       = []
```

## Phase 1: VALIDATE + SCOPE

**Outputs:** REPOS.

1. `workspace_path` missing → ABORT `"missing required input: workspace_path"`.
2. `CONFIG_DIR/config.yaml` missing or lacking a top-level `workspace:` key →
   ABORT `"not a workspace root: {workspace_path}"`.
3. `gh` unavailable → ABORT `"gh CLI not found"`.
4. Catalog:

```bash
yq -r '.repositories[].full_name' "${CONFIG_DIR}/config.yaml"
```

   Empty catalog and no `repos` input → ABORT `"repositories catalog is empty"`.
5. If `repos` input given: match each entry against catalog `full_name` or `name`;
   entries with no catalog match are still evaluated if they look like `owner/name`
   (API-only repos are legitimate — see spec Part 9), otherwise append
   `"unknown repo: {entry}"` to ERRORS and drop it. REPOS = the resolved full names.
6. Verify gitignore coverage: append `*-result.yaml` to `CONFIG_DIR/.gitignore` if missing.

## Phase 2: EVALUATE (per repo)

**Outputs:** REPO_RESULTS.

For each `FULL` (owner/name) in REPOS:

1. Fetch API data into a fresh temp dir (404s are expected for some endpoints —
   a missing file is how evaluate_checks.py learns the resource is absent):

```bash
DATA_DIR=$(mktemp -d)
fetch() { gh api "$1" > "$DATA_DIR/$2" 2>/dev/null || rm -f "$DATA_DIR/$2"; }

fetch "repos/${FULL}" repo.json
DEFAULT_BRANCH=$(jq -r '.default_branch // "main"' "$DATA_DIR/repo.json" 2>/dev/null || echo main)
fetch "repos/${FULL}/branches/${DEFAULT_BRANCH}/protection" protection.json
fetch "repos/${FULL}/rulesets" rulesets.json
fetch "repos/${FULL}/labels?per_page=100" labels.json
fetch "repos/${FULL}/actions/workflows" workflows.json
fetch "repos/${FULL}/releases?per_page=30" releases.json
fetch "repos/${FULL}/tags?per_page=30" tags.json
fetch "repos/${FULL}/contents/" root-contents.json
fetch "repos/${FULL}/contents/.github" github-contents.json
```

   If `repo.json` is missing after the fetch (repo inaccessible), append
   `"{FULL}: repo metadata unavailable"` to ERRORS and continue to the next repo.

2. Evaluate deterministically:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/evaluate_checks.py" \
  --repo "$FULL" --data-dir "$DATA_DIR" \
  --relationships "${CONFIG_DIR}/relationships.yaml" \
  --dismissals "${CONFIG_DIR}/healthcheck.yaml"
```

   Append the printed JSON object to REPO_RESULTS. Non-zero exit → append
   `"{FULL}: evaluate_checks failed"` to ERRORS, continue.

3. Space repos out (fleet politeness): no parallel fetching; sequential per repo.

## Phase 3: AGGREGATE + WRITE RESULT

**Outputs:** RESULT_PATH written and validated.

1. Aggregate: `score` = sum of repo scores, `total` = sum of repo totals, `grade` from
   score/total fraction — A ≥ 0.90, B ≥ 0.72, C ≥ 0.54, D ≥ 0.36, F below (same table
   evaluate_checks.py uses; total 0 → F).
2. Write RESULT_PATH:

```yaml
contract_version: 1
kind: healthcheck
workspace: {LOGIN}
run_at: {RUN_AT}
actor: { gh_login: {GH_LOGIN}, machine: {MACHINE}, mode: {MODE} }
repos: {REPO_RESULTS}          # each: {repo, score, total, grade, checks}
aggregate: { score: {sum}, total: {sum}, grade: {computed} }
errors: {ERRORS}
```

3. Validate:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind healthcheck
```

   Exit ≠ 0 → skill bug; report validator stderr verbatim.

## Phase 4: UPDATE GOVERNANCE RECORD

**Outputs:** updated `CONFIG_DIR/healthcheck.yaml` (skip entirely if `update_governance: false`).

1. Create from `{PLUGIN_ROOT}/templates/healthcheck.yaml.template` if missing.
2. Set `last_run`: `timestamp: RUN_AT`, `scope:` comma-joined short names (or `fleet`
   when the whole catalog ran), `aggregate_score / aggregate_total / aggregate_grade`.
3. For each repo result, write `repos.{short-name}` (short name = part after `/`):
   `score`, `total`, `grade`, and each check with `status`, `detail`, `data`, plus
   `last_evaluated: RUN_AT` (the governance record keeps timestamps; the result file
   does not need them).
4. **Preserve `dismissals:` untouched** — merge, never overwrite. Repos not evaluated
   this run keep their existing blocks.
5. Do NOT commit or push — the orchestrator (P5) owns the commit/PR step.

## ABORT semantics

On ABORT: write RESULT_PATH with `repos: []`, `aggregate: {score: 0, total: 0, grade: F}`,
`errors: [<reason>, ...]`, all common fields populated; validate; stop. Fallback write
locations as in gh-status-headless.

## Related

- `lib/patterns/headless-contract.md` — schema
- `lib/references/healthcheck-checks.md` — the catalog evaluate_checks.py implements
- `skills/gh-healthcheck/` — the interactive sibling (fix/dismiss flows live there)
````

- [ ] **Step 2: Live verification (dogfood verification)**

```bash
PLUGIN=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
WS=/Users/nathanielramm/git/hiivmind
```

Execute the skill's phases against `workspace_path=$WS` (full catalog). Then:

```bash
uv run "$PLUGIN/lib/pulse/scripts/validate_result.py" "$WS/.hiivmind/github/healthcheck-result.yaml" --kind healthcheck && echo VALID
yq -r '.aggregate.grade' "$WS/.hiivmind/github/healthcheck-result.yaml"
yq -r '.repos."hiivmind-pulse-gh".checks.dependency_management.status' "$WS/.hiivmind/github/healthcheck.yaml"
```

Expected: `VALID`; a grade letter; last command prints `dismissed` (dismissal honored and preserved). Also confirm `git -C "$WS/.hiivmind/github" status --porcelain` shows `healthcheck.yaml` modified but NOT `healthcheck-result.yaml` (gitignored).

- [ ] **Step 3: Broken-input verification**

Execute with `workspace_path=$(mktemp -d)` and an explicit `result_path`; validate the result file passes `--kind healthcheck` and `errors[]` is non-empty, `repos: []`.

- [ ] **Step 4: Commit**

```bash
git add skills/gh-healthcheck-headless/
git commit -m "feat(skills): gh-healthcheck-headless — deterministic fleet governance audit

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Decision capture in interactive gh-refresh

**Files:**
- Modify: `skills/gh-refresh/SKILL.md` (Phase 5)
- Modify: `templates/config.yaml.template`

**Interfaces:**
- Produces: `automation.refresh_sections` (list of section ids) in config.yaml — the recorded decision `gh-refresh-headless` (Task 5) replays. Monotonic union: interactive refreshes only ever add sections; users prune by editing config.

- [ ] **Step 1: Add the `automation:` block to the config template**

In `templates/config.yaml.template`, insert before the `# Cache metadata` comment:

```yaml
# Headless automation decisions (recorded by interactive skills, replayed by headless siblings)
# refresh_sections: sections gh-refresh-headless may sync without prompting.
# Recorded as the union of sections refreshed interactively; edit to prune.
automation:
  refresh_sections: []
```

- [ ] **Step 2: Add decision capture to gh-refresh Phase 5**

In `skills/gh-refresh/SKILL.md`, at the end of the `## Phase 5: UPDATE` section (after the "Timestamp Format" subsection), append:

```markdown
### Decision Capture (headless replay)

Record the sections just refreshed so `gh-refresh-headless` can replay this decision
without prompting (spec: decision capture — headless variants replay, never guess):

1. Read `automation.refresh_sections` from config.yaml (treat missing as `[]`)
2. Set it to the **union** of the existing list and the sections refreshed this run
3. Set `automation.refresh_recorded_at` to the current UTC timestamp

The list only grows through interactive use; the team prunes it by editing config.yaml.
```

- [ ] **Step 3: Verify and commit**

```bash
grep -c "refresh_sections" skills/gh-refresh/SKILL.md templates/config.yaml.template
```

Expected: `1` or more in each file.

```bash
git add skills/gh-refresh/SKILL.md templates/config.yaml.template
git commit -m "feat(refresh): capture refreshed-sections decision for headless replay

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `gh-refresh-headless` (P3.3)

**Files:**
- Create: `skills/gh-refresh-headless/SKILL.md`

**Interfaces:**
- Consumes: `automation.refresh_sections` (Task 4), `freshness_status.py` (Task 1), the interactive gh-refresh Phase 4 refresh procedures (`lib/references/api-routing.md`, `lib/patterns/graphql-execution.md`), `validate_result.py --kind refresh`.
- Produces: `refresh-result.yaml` (`sections[{id, status: refreshed|skipped|failed}]`, `config_updated: bool`); refreshed config files + freshness.yaml timestamps.

- [ ] **Step 1: Write the skill**

`skills/gh-refresh-headless/SKILL.md` with exactly this content:

````markdown
---
name: gh-refresh-headless
description: >
  Headless config sync. Refreshes workspace config sections against GitHub without prompting,
  replaying the section selection recorded by interactive gh-refresh (automation.refresh_sections)
  or an explicit sections input. Writes refresh-result.yaml (kind: refresh). Zero prompts;
  explicit inputs only. Use when: a scheduled run found refresh_needed, an orchestrator syncs
  catalogs before a fleet audit. Trigger phrases: "headless refresh", "scheduled config sync".
inputs:
  workspace_path: "required — absolute path to the workspace root (directory containing .hiivmind/github/)"
  sections: "optional — comma-separated section ids to refresh, overriding the recorded decision"
  result_path: "optional — where to write the result (default: {workspace_path}/.hiivmind/github/refresh-result.yaml)"
  mode: "optional — actor mode recorded in the result: interactive | scheduled (default: scheduled)"
outputs:
  result_file: "refresh-result.yaml conforming to lib/patterns/headless-contract.md (kind: refresh)"
  config: "refreshed section files + freshness.yaml timestamps under {workspace_path}/.hiivmind/github/"
author: hiivmind
---

# Headless Config Refresh

Sync cached workspace config with GitHub, unattended. The interactive sibling asks which
sections to refresh; this skill **replays a recorded decision** instead:

Target sections, in priority order:
1. `sections` input (explicit override)
2. `automation.refresh_sections` from config.yaml (recorded by interactive gh-refresh)
3. Every currently-stale section (fallback when nothing was ever recorded)

## Path Convention

`{PLUGIN_ROOT}` = plugin root (where plugin.json lives).

## Contract

- **Zero prompts. Explicit inputs only (D4). Every exit writes a result file.**
- A section that fails does not abort the run: mark it `failed`, record the error, continue.
- Sections whose refresh requires user interaction by nature (`automations` — UI-only data,
  manual template) are marked `skipped`, never attempted.

## State

```
computed:
  CONFIG_DIR   = {workspace_path}/.hiivmind/github
  RESULT_PATH  = {result_path input, or CONFIG_DIR/refresh-result.yaml}
  RUN_AT       = $(date -u +%Y-%m-%dT%H:%M:%SZ)
  LOGIN        = yq -r '.workspace.login' CONFIG_DIR/config.yaml
  GH_LOGIN     = $(gh api user --jq .login)   ("unknown" on failure, + errors[] entry)
  MACHINE      = $(hostname -s)
  MODE         = {mode input, default "scheduled"}
  ALL_SECTIONS = section ids present in CONFIG_DIR/freshness.yaml
  TARGETS      = resolved per the priority order above (minus "automations")
  SECTION_RESULTS = []   ({id, status} per section in ALL_SECTIONS)
  ERRORS       = []
```

## Phase 1: VALIDATE + RESOLVE TARGETS

**Outputs:** TARGETS.

1. `workspace_path` missing → ABORT `"missing required input: workspace_path"`.
2. `CONFIG_DIR/config.yaml` missing or lacking `^workspace:` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. `gh` unavailable → ABORT `"gh CLI not found"`.
4. **Pull before reconcile** (multi-machine rule, workspace-detection.md): if CONFIG_DIR
   is a git repo with a remote, `git -C CONFIG_DIR pull --ff-only` first; a pull failure
   is an ERRORS entry, not an abort (proceed on local state).
5. Resolve TARGETS by the priority order in the intro. For the stale fallback, run
   `uv run {PLUGIN_ROOT}/lib/pulse/scripts/freshness_status.py --freshness CONFIG_DIR/freshness.yaml`
   and take sections with `stale: true`. Remove `automations` from TARGETS always.
   Unknown section ids in the `sections` input → ERRORS entry, dropped.
6. Verify gitignore coverage (`*-result.yaml`), append if missing.
7. Record baseline for config_updated:

```bash
BASELINE=$(git -C "$CONFIG_DIR" status --porcelain 2>/dev/null | sort | shasum | cut -d' ' -f1)
```

## Phase 2: REFRESH

**Outputs:** SECTION_RESULTS.

Read `{PLUGIN_ROOT}/lib/references/api-routing.md` in full once, then for each section in
ALL_SECTIONS:

- Not in TARGETS → record `{id, status: skipped}`.
- In TARGETS → execute the same per-section refresh procedure as interactive gh-refresh
  Phase 4 (query GitHub, write the section's config file — see the "Refreshable Sections"
  table in `skills/gh-refresh/SKILL.md`; GraphQL via `lib/patterns/graphql-execution.md`).
  - Success → `{id, status: refreshed}`; update the section in freshness.yaml
    (`last_checked: RUN_AT`, `stale: false`).
  - Any error → `{id, status: failed}`, append `"{id}: {error}"` to ERRORS, leave
    freshness untouched, continue.

Headless deviations from the interactive procedure: never use corpus lookup interactively;
if syntax is uncertain, mark the section `failed` with error `"{id}: syntax uncertain,
needs interactive run"` rather than guessing mutations. (All refresh queries are read-only,
so the risk is wasted calls, not damage — but a wrong query recorded as success would
corrupt the cache.)

## Phase 3: WRITE + VALIDATE

**Outputs:** RESULT_PATH written and validated.

1. Compute config_updated:

```bash
NOW=$(git -C "$CONFIG_DIR" status --porcelain 2>/dev/null | sort | shasum | cut -d' ' -f1)
# config_updated = [ "$NOW" != "$BASELINE" ]
```

   If CONFIG_DIR is not a git repo, fall back to: config_updated = any section refreshed.
2. Update `cache.last_synced_at: RUN_AT` in config.yaml if any section refreshed.
3. Write RESULT_PATH:

```yaml
contract_version: 1
kind: refresh
workspace: {LOGIN}
run_at: {RUN_AT}
actor: { gh_login: {GH_LOGIN}, machine: {MACHINE}, mode: {MODE} }
sections: {SECTION_RESULTS}    # every section in ALL_SECTIONS: {id, status}
config_updated: {bool}
errors: {ERRORS}
```

4. Validate:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind refresh
```

5. Do NOT commit or push the workspace repo — the orchestrator owns that.

## ABORT semantics

On ABORT: write RESULT_PATH with `sections: []`, `config_updated: false`,
`errors: [<reason>, ...]`, all common fields populated; validate; stop. Fallback write
locations as in gh-status-headless.

## Related

- `lib/patterns/headless-contract.md` — schema
- `skills/gh-refresh/` — interactive sibling; Phase 4 procedures are shared, Phase 5
  records the decision this skill replays
````

- [ ] **Step 2: Live verification (dogfood verification)**

```bash
PLUGIN=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
WS=/Users/nathanielramm/git/hiivmind
```

Execute the skill against `workspace_path=$WS` with `sections=workspace` (cheapest section — one API call). Then:

```bash
uv run "$PLUGIN/lib/pulse/scripts/validate_result.py" "$WS/.hiivmind/github/refresh-result.yaml" --kind refresh && echo VALID
yq -r '.sections[] | select(.id == "workspace") | .status' "$WS/.hiivmind/github/refresh-result.yaml"
yq -r '.config_updated' "$WS/.hiivmind/github/refresh-result.yaml"
```

Expected: `VALID`; `refreshed`; `config_updated` true or false (both legitimate — false when GitHub state matches cache and only freshness.yaml timestamps moved… note freshness.yaml IS tracked, so expect `true`).

- [ ] **Step 3: Broken-input verification**

Execute with `workspace_path=$(mktemp -d)` and explicit `result_path`; validate the result passes `--kind refresh` with non-empty `errors[]`, `sections: []`, `config_updated: false`.

- [ ] **Step 4: Commit**

```bash
git add skills/gh-refresh-headless/
git commit -m "feat(skills): gh-refresh-headless — decision-replay config sync

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Close-out — spec, CLAUDE.md, version

**Files:**
- Modify: `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
- Modify: `CLAUDE.md`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Spec close-out**

1. Tick P3.1, P3.2, P3.3 checkboxes to `- [x]`.
2. §8.9 table: P3 row → `✅ done` with date (today's actual date at execution).

- [ ] **Step 2: CLAUDE.md**

In the `## Skills` table (7 rows after P1's Task 4), append:

```markdown
| `gh-status-headless` | Headless status pre-check → status-result.yaml (zero prompts) |
| `gh-healthcheck-headless` | Headless fleet governance audit → healthcheck-result.yaml |
| `gh-refresh-headless` | Headless config sync (replays recorded decisions) → refresh-result.yaml |
```

In the File Structure block's `lib/pulse/scripts/` listing, add `freshness_status.py` with comment `# Staleness computation for headless status`. Under `skills/`, add the three new skill dirs.

- [ ] **Step 3: Version bump**

`.claude-plugin/plugin.json`: bump to `4.7.0` (or next unused minor if P4 landed first).

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest -q                                  # full suite green
grep -c "gh-status-headless" CLAUDE.md            # >= 1
git add CLAUDE.md docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md .claude-plugin/plugin.json
git commit -m "docs: mark P3 complete (headless skills); bump version

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Deliverable → Task map (spec coverage)

| Spec deliverable | Task |
|------------------|------|
| P3.1 gh-status-headless → status-result.yaml (refresh_needed) | Tasks 1 (staleness helper) + 2 |
| P3.2 gh-healthcheck-headless → healthcheck-result.yaml; iterates repositories[]/filter; honors dismissals; updates committed healthcheck.yaml | Task 3 |
| P3.3 gh-refresh-headless → refresh-result.yaml; replays recorded decisions (decision-capture fields added to config) | Tasks 4 (capture) + 5 (replay) |
| Part 4 conventions: inputs frontmatter, State block, ABORT-emits-result, result gitignored, zero prompts | every skill in Tasks 2/3/5 |
| Exit criteria: live runs pass validate_result.py; broken input still yields valid result with errors[] | Steps 2–3 of Tasks 2/3/5 |
| Spec progress tracking rule (tick boxes + §8.9 same commit) | Task 6 |
