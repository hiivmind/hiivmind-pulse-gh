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
run_at: "{RUN_AT}"    # quote: an unquoted ISO-8601 value parses as a YAML datetime; the contract requires a string
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
