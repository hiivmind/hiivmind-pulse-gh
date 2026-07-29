---
name: gh-workflow-run-headless
description: >
  Run a v2 workflow non-interactively under its headless policy. ASKs are recorded, withheld
  mutations become proposed_actions, notable items become typed findings; writes
  workflow-run-result.yaml (kind: workflow-run). Zero prompts; explicit inputs only. Use when:
  a scheduler runs a workflow unattended, an orchestrator needs a workflow's findings as data.
  Trigger phrases: "headless workflow run", "run workflow headless", "scheduled workflow".
inputs:
  workspace_path: "required — absolute path to the workspace root (directory containing .hiivmind/github/)"
  workflow: "required — workflow name; resolved to {workspace_path}/.hiivmind/github/workflows/{workflow}.yaml"
  workflow_path: "optional — explicit YAML path, overriding name resolution (e.g. a repo-overlay workflow)"
  params: "optional — parameter values as a YAML/JSON map; params with default: null and no value here abort the run"
  repo: "optional — owner/name repo scope recorded in the result and passed to the executor context"
  result_path: "optional — default: {workspace_path}/.hiivmind/github/workflow-run-result.yaml"
  ignore_cooldown: "optional — skip the cooldown check (default: false)"
  mode: "optional — actor mode recorded in the result: interactive | scheduled (default: scheduled)"
outputs:
  result_file: "workflow-run-result.yaml conforming to lib/patterns/headless-contract.md (kind: workflow-run)"
author: hiivmind
---

# Headless Workflow Run

Execute one v2 workflow with no user present. This skill is a thin caller: it builds the
execution context and delegates to the executor
(`lib/patterns/workflow-execution.md` — read the **Headless Execution** section in full
before executing). The workflow definition is untouched — the same YAML serves
interactive runs.

## Path Convention

`{PLUGIN_ROOT}` = plugin root (where plugin.json lives).

## Contract

- **Zero prompts. Explicit inputs only (D4). Every exit writes a result file** —
  including cooldown skips (`outcome: skipped-cooldown`) and aborts (`outcome: aborted`).
- The operation blocklist is absolute regardless of the workflow's `on_mutation` policy.

## State

```
computed:
  CONFIG_DIR   = {workspace_path}/.hiivmind/github
  WF_PATH      = {workflow_path input, or CONFIG_DIR/workflows/{workflow}.yaml}
  RESULT_PATH  = {result_path input, or CONFIG_DIR/workflow-run-result.yaml}
  RUN_AT       = $(date -u +%Y-%m-%dT%H:%M:%SZ)
  LOGIN        = yq -r '.workspace.login' CONFIG_DIR/config.yaml
  GH_LOGIN     = $(gh api user --jq .login)   ("unknown" on failure, + errors[] entry)
  MACHINE      = $(hostname -s)
  MODE         = {mode input, default "scheduled"}
  RUN_ID       = {UTC date}-{GH_LOGIN}-{UTC HHMMSS}   e.g. 2026-07-10-octocat-093012
  OUTCOME      = success | failure | skipped-cooldown | aborted
  FINDINGS, PROPOSED_ACTIONS, ASKS_RECORDED, ERRORS = []   (accumulated by the executor)
```

## Phase 1: VALIDATE

**Outputs:** loaded workflow, policy.

1. `workspace_path` or `workflow` missing → ABORT `"missing required input: {name}"`.
2. `CONFIG_DIR/config.yaml` missing or lacking `^workspace:` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. `WF_PATH` missing → ABORT `"workflow not found: {WF_PATH}"`.
4. Load the YAML. No `workflow:` field (v1 or malformed) → ABORT
   `"v1 workflows have no headless projection"` / `"invalid workflow YAML"`.
5. `headless.enabled` not `true` → ABORT `"workflow not headless-enabled: {workflow}"`.
6. `enabled: false` on the workflow itself → ABORT `"workflow disabled: {workflow}"`.
7. Resolve params: merge the `params` input over the workflow's declared defaults.
   Any param left at `default: null` → append its name to ASKS_RECORDED, ABORT
   `"missing required param: {name}"` (outcome: aborted — the contract's designed
   behavior for unanswerable required params).
8. Verify gitignore coverage (`*-result.yaml`) in CONFIG_DIR, append if missing.

## Phase 2: COOLDOWN

Unless `ignore_cooldown: true`: perform the executor's cooldown check against
`CONFIG_DIR/poll-state.yaml`. If active → OUTCOME = `skipped-cooldown`, go straight to
Phase 4 (write result; this is a valid, complete run).

## Phase 3: EXECUTE

**Delegate to the executor:** run the workflow per
`{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` with context
`{mode: headless, approval: pre-approved, enforce_cooldown: false (already checked),
workspace_root: {workspace_path}, repo: {repo input}}`, applying the Headless Execution
projection with the workflow's `headless:` policy. Accumulate FINDINGS,
PROPOSED_ACTIONS, ASKS_RECORDED per the projection table.

- **Driver-backed workflows** (whose pseudocode is `INVOKE skill X-headless`, e.g. the
  F6–F9 marketplace-sync / plan-sync / generated-artifact workflows) produce their
  proposals in the sibling's own `{kind}-result.yaml`. Per the executor's "Folding a
  headless sibling's result" rule, run
  `uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/subresult_fold.py" <sibling result>`
  and extend FINDINGS / PROPOSED_ACTIONS / ASKS_RECORDED with its output — otherwise this
  run's result carries none of the sibling's proposals and the scheduled PR body shows
  nothing. A fold error (`exit 3`) is appended to ERRORS.

- Pseudocode completed (end or `STOP`) → OUTCOME = `success`.
- Unrecoverable error → OUTCOME = `failure`, append to ERRORS, proceed to Phase 4.
- `on_ask: abort` triggered → OUTCOME = `aborted`, proceed to Phase 4.

Update poll-state (`last_run_at`, `last_result`, `run_count`) as the executor specifies.

## Phase 4: WRITE + VALIDATE

1. Write RESULT_PATH:

```yaml
contract_version: 1
kind: workflow-run
workspace: {LOGIN}
run_at: "{RUN_AT}"               # quote: an unquoted ISO-8601 value parses as a YAML datetime; the contract requires a string
actor: { gh_login: {GH_LOGIN}, machine: {MACHINE}, mode: {MODE} }
workflow: {workflow name from YAML}
repos: {[repo input] if given, else repos the workflow touched, else []}
run_id: "{RUN_ID}"               # quote: keep it a string (the {date}-... prefix would otherwise risk datetime coercion)
outcome: {OUTCOME}
findings: {FINDINGS}              # [{kind, repo, severity, detail?, ref?, classification?, inferred?}]
                                 # ref, when present, is a MAPPING: { type: <str>, id: <any>, url: <str> } (see headless-contract.md) — never a bare string
proposed_actions: {PROPOSED_ACTIONS}
asks_recorded: {ASKS_RECORDED}
errors: {ERRORS}
```

2. Validate:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind workflow-run
```

   Exit ≠ 0 → skill bug; report validator stderr verbatim.

3. Print a one-line log summary:
   `workflow-run: {workflow} outcome={OUTCOME} findings={n} proposed={n} asks={n}`

## ABORT semantics

Every ABORT above sets OUTCOME = `aborted`, appends the reason to ERRORS, and falls
through to Phase 4 — the result file is always written and validated. If CONFIG_DIR is
unusable, write to the `result_path` input, else `workflow-run-result.yaml` in the
current directory, and say so.

## Related

- `lib/patterns/workflow-execution.md` — the executor + Headless Execution projection
- `lib/patterns/headless-contract.md` — the workflow-run schema
- `lib/references/operation-blocklist.md` — absolute in headless mode
