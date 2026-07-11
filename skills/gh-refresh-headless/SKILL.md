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
