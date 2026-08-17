> **ARCHIVED 2026-08-17.** Implementation complete — kept for historical
> reference only. See
> `docs/superpowers/archive/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
> §8.9 for original phase tracking.
>
> ---

# P4 — Workflow Executor Split + Headless Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One normative workflow executor (`workflow-execution.md`) with an execution-context parameter, a per-workflow `headless:` policy block so the same v2 YAML runs interactively and unattended, and `gh-workflow-run-headless` writing `workflow-run-result.yaml`.

**Architecture:** Execution is currently described three times (workflow-execution.md, gh-heartbeat §4/§5, gh-workflows "Run"). This plan makes workflow-execution.md the single executor — callers build an execution context (`mode`, `approval`, `enforce_cooldown`) and delegate — and adds a headless projection: `ASK` → `asks_recorded`, mutations → `proposed_actions` (per policy), `SHOW` → `findings`, with the operation blocklist absolute. Headless runs emit the P1 `workflow-run` result kind.

**Tech Stack:** Markdown patterns/skills, workflow YAML (v2 pseudocode format), P1 contract + validator.

**Spec:** `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` — Part 6.1, §P4 (P4.1–P4.4). Depends on P1 only (independent of P2/P3), but the verification steps use `validate_result.py`, so **P1 must be executed first**.

## Global Constraints

- **Reusable-first:** no `hiivmind` hardcoding except steps marked **(dogfood verification)**.
- **Backward compatible:** existing workflow YAMLs without a `headless:` block keep working interactively, unchanged. Default when the block is absent: `enabled: false` (headless run refuses), `on_ask: record`, `on_mutation: propose`, `mutation_allowlist: []`.
- **Mutation safety:** `on_mutation: propose` is the default; `allow-listed` requires a non-empty `mutation_allowlist`; `lib/references/operation-blocklist.md` applies unconditionally in headless mode — even under `on_mutation: allow`.
- **workflow-run result contract (P1):** required fields `workflow` (str), `repos` (list of str), `run_id` (`{date}-{gh_login}-{n}`), `outcome` (`success | failure | skipped-cooldown | aborted`), `findings[]` (`{kind, repo, severity, detail?, ref?, classification?, inferred?}`), `proposed_actions[]`, `asks_recorded[]`, plus the common fields (`contract_version: 1`, `kind: workflow-run`, `workspace`, `run_at`, `actor{gh_login, machine, mode}`, `errors[]`). Validate with `uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py <file> --kind workflow-run`.
- **run_id (interim):** `{UTC date}-{gh_login}-{n}` with `n` = UTC `HHMMSS` at run start (e.g. `2026-07-10-octocat-093012`). Actor-embedded so two machines can't collide (I3/I4); the P6 run ledger takes over sequence assignment.
- **D4:** the headless skill takes explicit `workspace_path` / `workflow` inputs; no discovery.
- Commit after every task. Version bump once, in the close-out task: nominal `4.8.0` (or next unused minor).

## File Structure

| File | Responsibility |
|---|---|
| `lib/patterns/workflow-execution.md` (modify) | THE executor: execution context, single flow, headless projection section |
| `skills/gh-heartbeat/SKILL.md` (modify) | §4/§5 become delegation stubs (presenter keeps presenting; executor executes) |
| `skills/gh-workflows/SKILL.md` (modify) | "Run Workflow" becomes a delegation stub |
| `lib/references/operation-blocklist.md` (modify) | Declared unconditional in headless mode |
| `skills/gh-workflow-run-headless/SKILL.md` (new) | P4.3 — headless workflow run → workflow-run-result.yaml |
| `templates/workflow.yaml.template` (modify) | Documented `headless:` block |
| `templates/workflows/repo-healthcheck.yaml`, `templates/workflows/stale-check.yaml` (modify) | P4.4 reference `headless:` annotations |
| `CLAUDE.md`, spec, `.claude-plugin/plugin.json` (modify) | Close-out |

---

### Task 1: Single executor — execution context in `workflow-execution.md` + delegation stubs (P4.1)

**Files:**
- Modify: `lib/patterns/workflow-execution.md`
- Modify: `skills/gh-heartbeat/SKILL.md` (§4, §5)
- Modify: `skills/gh-workflows/SKILL.md` ("Run Workflow (On Demand)" section)

**Interfaces:**
- Produces: the execution-context table (`mode`, `approval`, `enforce_cooldown`, `workspace_root`, `repo`) that Task 2's headless section keys off and Task 3's skill supplies. Caller-context rows for gh-heartbeat / gh-workflows / gh-workflow-run-headless.

- [ ] **Step 1: Add the Single Executor section to workflow-execution.md**

In `lib/patterns/workflow-execution.md`, immediately after the `## Prerequisites` section (before `## Format Detection`), insert:

```markdown
---

## Single Executor

This document is the ONE normative execution description. gh-heartbeat, gh-workflows
"Run", and gh-workflow-run-headless are **callers**: they select workflows, obtain
approval, build an execution context, and delegate here. Skills MUST NOT re-describe
execution steps.

Callers supply an execution context:

| Field | Values | Meaning |
|-------|--------|---------|
| `mode` | `interactive` \| `headless` | interactive: ASK/SHOW reach a user. headless: policy projection (see Headless Execution below) |
| `approval` | `pre-approved` \| `ask` | pre-approved skips the `auto: false` permission gate (step 3 of the flow) |
| `enforce_cooldown` | `true` \| `false` | on-demand interactive runs pass `false` |
| `workspace_root` | path | resolved by the caller (interactive walk-up, or explicit headless input — D4) |
| `repo` | `owner/name` or empty | repo scope, when the caller has one |

Caller contexts:

| Caller | mode | approval | enforce_cooldown |
|--------|------|----------|------------------|
| gh-heartbeat (auto + user-selected workflows) | interactive | pre-approved | true |
| gh-workflows "Run" (on demand) | interactive | pre-approved | false |
| gh-workflow-run-headless | headless | pre-approved | true (unless its `ignore_cooldown` input) |

Poll-state paths in this document are relative to `{workspace_root}/.hiivmind/github/`.
```

Also, in the existing `## Cooldown Check` section, change the hardcoded path
`.hiivmind/github/poll-state.yaml` to `"${WORKSPACE_ROOT}/.hiivmind/github/poll-state.yaml"`, and change the section's opening line from "Before executing any workflow:" to "Before executing any workflow (skip when the context has `enforce_cooldown: false`):".

- [ ] **Step 2: Reduce gh-heartbeat §4 to a delegation stub**

In `skills/gh-heartbeat/SKILL.md`, replace the entire `### 4. Execute Auto Workflows` section (from the heading through the example block ending `Result: success`, up to but not including `### 5.`) with:

```markdown
### 4. Execute Auto Workflows

Auto workflows are pre-approved by definition — execute without confirmation, and do NOT
re-confirm operations invoked downstream.

**Delegate to the executor:** for each workflow in `auto_workflows`, execute it per
`{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` with context
`{mode: interactive, approval: pre-approved, enforce_cooldown: true, workspace_root: <resolved root>}`.
The executor owns format detection (v1/v2), parameter resolution, FSM interpretation,
and poll-state result recording — this skill only reports the outcome:

```
Running auto workflow: auto-refresh
  Result: success
```
```

- [ ] **Step 3: Reduce gh-heartbeat §5's execution tail to a delegation stub**

In `skills/gh-heartbeat/SKILL.md` §5, keep the selection prompt and the pre-approval
rules block (presentation is this skill's job), but replace the trailing numbered list:

```markdown
For each selected workflow, execute using the workflow execution pattern:

1. Load workflow YAML
2. Detect format:
   - **v2 (`workflow:` field):** Follow pseudocode handoff — resolve params, follow FSM
   - **v1 (`actions:` field):** Sequential dispatch
3. Update poll-state.yaml with result
```

with:

```markdown
**Delegate to the executor:** for each selected workflow, execute it per
`{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` with context
`{mode: interactive, approval: pre-approved, enforce_cooldown: true, workspace_root: <resolved root>}`.
```

- [ ] **Step 4: Reduce gh-workflows "Run" to a delegation stub**

In `skills/gh-workflows/SKILL.md`, replace the `### Run Workflow (On Demand)` section body — everything from `**See:** ...workflow-execution.md` through the v1 example block ending `Workflow complete. Result: success` (up to but not including `### Create Workflow`) — with:

```markdown
On-demand runs are pre-approved by the user's request and skip cooldowns.

**Delegate to the executor:** execute the named workflow per
`{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` with context
`{mode: interactive, approval: pre-approved, enforce_cooldown: false, workspace_root: <resolved root>}`.
The executor owns format detection, parameter resolution (extract from the run request →
defaults → ASK for required), FSM interpretation, and poll-state recording. Report the
executor's summary when it finishes.
```

- [ ] **Step 5: Verify no duplicated execution descriptions remain**

```bash
grep -c "Detect format" skills/gh-heartbeat/SKILL.md skills/gh-workflows/SKILL.md
```

Expected: `0` in each file (grep exits non-zero for zero matches — that's the pass condition).

- [ ] **Step 6: Commit**

```bash
git add lib/patterns/workflow-execution.md skills/gh-heartbeat/SKILL.md skills/gh-workflows/SKILL.md
git commit -m "refactor(workflows): single executor in workflow-execution.md; heartbeat/workflows delegate

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `headless:` policy block + headless projection (P4.2)

**Files:**
- Modify: `lib/patterns/workflow-execution.md` (new section)
- Modify: `templates/workflow.yaml.template`
- Modify: `lib/references/operation-blocklist.md`

**Interfaces:**
- Consumes: execution context from Task 1; `workflow-run` schema from P1.
- Produces: the `headless:` schema (`enabled`, `on_ask: record|default|abort`, `on_mutation: propose|allow-listed|allow`, `mutation_allowlist`) and the projection rules Task 3's skill executes and Task 4's templates annotate.

- [ ] **Step 1: Add the Headless Execution section to workflow-execution.md**

Insert after the `## Pre-Approved Execution` section (before `## Cooldown Check`):

```markdown
---

## Headless Execution (v2 Projection)

One workflow definition serves both modes. A per-workflow policy block declares how
interactive constructs project onto an unattended run — headless runs **replay policy**
instead of guessing:

```yaml
headless:
  enabled: true           # default false — a headless run of a non-enabled workflow
                          # aborts (outcome: aborted, error "workflow not headless-enabled")
  on_ask: record          # record | default | abort  (default: record)
  on_mutation: propose    # propose | allow-listed | allow  (default: propose)
  mutation_allowlist: []  # operation verbs permitted under allow-listed, e.g. [comment, label]
```

### Interpretation overrides in headless mode

All other rows of the v2 interpretation table apply unchanged. A **mutation** is any
state-changing GitHub operation (create, update, close, comment, label, merge, assign,
delete, …); read-only operations always execute.

| Construct | Headless behavior |
|-----------|-------------------|
| `ASK "q" (options)` | per `on_ask` — **record**: append `"{phase}: {q}"` to `asks_recorded`, then take the explicitly non-mutating option (skip/none/cancel) if one is offered, else end that branch and continue; **default**: take the workflow-declared default option, falling back to record behavior when none exists; **abort**: outcome `aborted`, write result, stop |
| Mutation | per `on_mutation` — **propose**: append a one-line description (verb + target) to `proposed_actions`, do not execute; **allow-listed**: execute if the operation's verb is in `mutation_allowlist`, else propose; **allow**: execute |
| `SHOW` / `PRESENT` phases | no user to show to; notable items become `findings` entries — `kind` from the workflow's domain (e.g. `stale-item`, `ci-failure`), `severity` via `INFER` with `inferred: true` |
| `INFER` | executes normally; any finding it classifies carries `inferred: true` and its label in `classification` |
| `INVOKE skill X` | if a headless sibling exists (`X-headless`), invoke it with explicit inputs (`workspace_path` from context); otherwise append `"invoke {X}"` to `proposed_actions` |
| `STOP "reason"` | normal completion (outcome `success`); the reason lands in the result summary, not `errors` |
| `params` with `default: null` | if the caller did not supply the param: append to `asks_recorded`, outcome `aborted` |

### Unconditional rules (regardless of `on_mutation`)

- `lib/references/operation-blocklist.md` applies **absolutely** in headless mode — a
  blocked operation is never executed, not even under `on_mutation: allow`; it is
  appended to `proposed_actions` prefixed `"blocked: "`.
- Cooldowns are enforced (context `enforce_cooldown: true`); an active cooldown yields
  outcome `skipped-cooldown` with a valid result file — never a silent skip.
- v1 (`actions:`) workflows are not headless-runnable: outcome `aborted`, error
  `"v1 workflows have no headless projection"`.

### Result file

Headless runs write `workflow-run-result.yaml` per `lib/patterns/headless-contract.md`
(kind `workflow-run`) to `{workspace_root}/.hiivmind/github/workflow-run-result.yaml`
(or the caller's `result_path`), and still record `last_run_at` / `last_result` /
`run_count` in poll-state as usual. `run_id` = `{UTC date}-{gh_login}-{n}` with `n` =
UTC `HHMMSS` at run start — actor-embedded so concurrent machines cannot collide
(interim scheme until the P6 run ledger assigns sequence numbers).
```

- [ ] **Step 2: Document the block in the workflow template**

In `templates/workflow.yaml.template`, insert after the `auto: false` line:

```yaml
# Headless policy (optional) — how this workflow projects onto unattended runs.
# See lib/patterns/workflow-execution.md "Headless Execution". Absent => headless disabled.
# headless:
#   enabled: true
#   on_ask: record          # record | default | abort
#   on_mutation: propose    # propose | allow-listed | allow
#   mutation_allowlist: []  # verbs permitted when allow-listed, e.g. [comment, label]
```

- [ ] **Step 3: Declare the blocklist unconditional in headless mode**

In `lib/references/operation-blocklist.md`, in the `## Handling Blocked Requests` section, after the line `**Do not proceed** with blocked operations under any circumstances.`, append:

```markdown
### Headless mode

In headless workflow runs this blocklist is **unconditional**: it overrides any
`headless.on_mutation` policy, including `allow`. The executor records the blocked
operation in the result file's `proposed_actions` with a `"blocked: "` prefix and
continues. See `lib/patterns/workflow-execution.md` — Headless Execution.
```

- [ ] **Step 4: Verify and commit**

```bash
grep -c "on_mutation" lib/patterns/workflow-execution.md templates/workflow.yaml.template lib/references/operation-blocklist.md
```

Expected: ≥ 1 in each file.

```bash
git add lib/patterns/workflow-execution.md templates/workflow.yaml.template lib/references/operation-blocklist.md
git commit -m "feat(workflows): headless policy block + projection rules; blocklist unconditional headless

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `gh-workflow-run-headless` (P4.3)

**Files:**
- Create: `skills/gh-workflow-run-headless/SKILL.md`

**Interfaces:**
- Consumes: executor + headless projection (Tasks 1–2), `validate_result.py --kind workflow-run` (P1).
- Produces: `workflow-run-result.yaml` with `findings` / `proposed_actions` / `asks_recorded`; the P5 scheduler and heartbeat summaries consume the file.

- [ ] **Step 1: Write the skill**

`skills/gh-workflow-run-headless/SKILL.md` with exactly this content:

````markdown
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
run_at: {RUN_AT}
actor: { gh_login: {GH_LOGIN}, machine: {MACHINE}, mode: {MODE} }
workflow: {workflow name from YAML}
repos: {[repo input] if given, else repos the workflow touched, else []}
run_id: {RUN_ID}
outcome: {OUTCOME}
findings: {FINDINGS}              # [{kind, repo, severity, detail?, ref?, classification?, inferred?}]
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
````

- [ ] **Step 2: Broken-input verification**

Execute the skill with `workspace_path=$(mktemp -d)`, `workflow=nope`, and an explicit `result_path` in the scratchpad; then:

```bash
PLUGIN=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
uv run "$PLUGIN/lib/pulse/scripts/validate_result.py" <result_path> --kind workflow-run && echo VALID
yq -r '.outcome' <result_path>
```

Expected: `VALID`; `aborted`.

- [ ] **Step 3: Commit**

```bash
git add skills/gh-workflow-run-headless/
git commit -m "feat(skills): gh-workflow-run-headless — policy-projected workflow runs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Reference `headless:` annotations on two shipped templates (P4.4)

**Files:**
- Modify: `templates/workflows/repo-healthcheck.yaml`
- Modify: `templates/workflows/stale-check.yaml`

**Interfaces:**
- Consumes: the policy schema from Task 2.
- Produces: the two reference implementations the spec names; stale-check is the exit-criterion workflow.

- [ ] **Step 1: Annotate repo-healthcheck.yaml**

In `templates/workflows/repo-healthcheck.yaml`, insert after the line `auto: false  # Must be explicitly requested — never runs automatically`:

```yaml
# Reference headless annotation: the audit is read-only; INVOKE maps to the
# gh-healthcheck-headless sibling when present (see workflow-execution.md).
headless:
  enabled: true
  on_ask: record
  on_mutation: propose   # fixes are proposed, never applied unattended
```

- [ ] **Step 2: Annotate stale-check.yaml**

In `templates/workflows/stale-check.yaml`, insert after the line `auto: false`:

```yaml
# Reference headless annotation: stale items become findings; ping/label may run
# unattended, close is only ever proposed.
headless:
  enabled: true
  on_ask: record
  on_mutation: allow-listed
  mutation_allowlist: [comment, label]
```

- [ ] **Step 3: Verify both templates still parse and the FSM is untouched**

```bash
yq -r '.headless.enabled' templates/workflows/repo-healthcheck.yaml templates/workflows/stale-check.yaml
git diff templates/workflows/ | grep '^[-+]' | grep -v '^[-+][-+]' | grep -cv '^\+'
```

Expected: `true` twice; second command prints `0` (additions only — no existing line changed, proving the interactive definition is unchanged).

- [ ] **Step 4: Commit**

```bash
git add templates/workflows/repo-healthcheck.yaml templates/workflows/stale-check.yaml
git commit -m "feat(templates): headless policy annotations on repo-healthcheck and stale-check

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Exit-criteria verification + close-out

**Files:**
- Modify: live workspace `stale-check.yaml` **(dogfood verification)**
- Modify: `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
- Modify: `CLAUDE.md`, `.claude-plugin/plugin.json`

- [ ] **Step 1: Headless stale-check run on the live workspace (dogfood verification)**

```bash
PLUGIN=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
WS=/Users/nathanielramm/git/hiivmind
```

1. If `$WS/.hiivmind/github/workflows/stale-check.yaml` lacks a `headless:` block, add the Task 4 Step 2 block to it (workspace copies are user-owned; this is the dogfood opt-in) and commit that change **in the workspace repo**.
2. Execute `gh-workflow-run-headless` per its SKILL.md with `workspace_path=$WS`, `workflow=stale-check`, `ignore_cooldown=true`, `repo=hiivmind/hiivmind-pulse-gh`.
3. Verify:

```bash
uv run "$PLUGIN/lib/pulse/scripts/validate_result.py" "$WS/.hiivmind/github/workflow-run-result.yaml" --kind workflow-run && echo VALID
yq -r '.outcome, .run_id' "$WS/.hiivmind/github/workflow-run-result.yaml"
```

Expected: `VALID`; outcome `success` (or `skipped-cooldown` only if step 2 skipped the flag); `run_id` matches `{date}-{gh_login}-{HHMMSS}`. If anything stale exists, `findings[]` entries have `kind: stale-item` and severities; any close actions appear in `proposed_actions`, not executed.

- [ ] **Step 2: Interactive-parity check (exit criterion: same YAML, both modes)**

Confirm the definition needed no changes beyond the additive `headless:` block:

```bash
yq -r '.workflow' templates/workflows/stale-check.yaml | head -3
```

Expected: the `GATHER:` pseudocode unchanged from before this plan (`git log -p -1 templates/workflows/stale-check.yaml` shows only the `headless:` insertion). Interactive runs read the same file through the same executor with `mode: interactive` — ASKs still prompt.

- [ ] **Step 3: Spec close-out**

1. Tick P4.1–P4.4 checkboxes to `- [x]`.
2. §8.9 table: P4 row → `✅ done` with the actual execution date.
3. P7.4 note: no change needed (workflow_lint.py stays a P7 deliverable).

- [ ] **Step 4: CLAUDE.md**

In the `## Skills` table, append:

```markdown
| `gh-workflow-run-headless` | Run a v2 workflow unattended under its headless policy → workflow-run-result.yaml |
```

In the Library Structure "Patterns" table, update the `workflow-execution` row (add it if absent):

```markdown
| `lib/patterns/workflow-execution.md` | THE workflow executor (single normative description; interactive + headless) |
```

- [ ] **Step 5: Version bump, verify, commit**

`.claude-plugin/plugin.json`: bump to `4.8.0` (or next unused minor).

```bash
uv run pytest -q                                       # suite green (no Python changed; sanity)
grep -c "gh-workflow-run-headless" CLAUDE.md           # >= 1
git add CLAUDE.md docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md .claude-plugin/plugin.json
git commit -m "docs: mark P4 complete (executor split + headless policy); bump version

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Deliverable → Task map (spec coverage)

| Spec deliverable | Task |
|------------------|------|
| P4.1 single executor pattern; heartbeat §4/§5 + workflows "Run" as delegation stubs | Task 1 |
| P4.2 `headless:` policy block (on_ask, on_mutation, mutation_allowlist) documented in workflow-execution.md; blocklist unconditional headless | Task 2 |
| P4.3 gh-workflow-run-headless → workflow-run-result.yaml with findings/proposed_actions/asks_recorded | Task 3 |
| P4.4 two shipped templates annotated (repo-healthcheck, stale-check) | Task 4 |
| Exit criteria: same YAML both modes, no definition changes; live headless stale-check yields a valid result | Task 5 Steps 1–2 |
| Spec progress tracking rule | Task 5 Steps 3–5 |
