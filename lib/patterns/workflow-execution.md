# Pattern: Workflow Execution

## Purpose

Execute workflows after triggers fire, with format detection, parameter resolution, cooldown enforcement, and result recording.

## When to Use

- Heartbeat skill needs to run triggered workflows
- Workflows skill runs an on-demand workflow
- Post-operation hook triggers a workflow

## Prerequisites

- **poll-state.md** — Cooldown checks and result recording
- **config-parsing.md** — Read workflow YAML files

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
| gh-workflow-run-headless | headless | pre-approved | true — but the skill pre-checks the cooldown itself (Phase 2) so it can emit `skipped-cooldown`, then delegates with `enforce_cooldown: false`; skipped entirely under its `ignore_cooldown` input |

Poll-state paths in this document are relative to `{workspace_root}/.hiivmind/github/`.

---

## Format Detection

Workflows exist in two formats. Detect which format before executing:

```
IF workflow YAML has 'workflow:' field → use pseudocode handoff (v2)
ELIF workflow YAML has 'actions:' field → use sequential dispatch (v1, legacy)
ELSE → error: workflow has neither actions nor workflow field
```

---

## V2 Execution: Pseudocode Handoff

### Execution Flow

```
1. LOAD workflow YAML
2. CHECK cooldown (poll-state.md)
   └── If cooldown active → skip, report "cooldown"
3. CHECK approval context
   ├── pre-approved (heartbeat selection, on-demand run) → execute immediately
   ├── auto: true  → execute immediately
   └── auto: false → present to user, ask permission
4. RESOLVE params (if params: field exists)
   ├── Extract from natural language request context
   ├── Apply defaults for missing params
   └── ASK user for remaining required params (default: null)
5. FOLLOW pseudocode
   ├── Read workflow: field — this is the instruction script
   ├── Read state: field — these are the workflow's variables
   └── Follow the pseudocode phases using the interpretation guidelines below
6. UPDATE poll-state.yaml with result
7. REPORT summary (from pseudocode's SUMMARIZE phase output, if present)
```

### Parameter Resolution

For workflows with a `params:` field, resolve all parameters before the pseudocode starts executing. The pseudocode references them as `params.name` and assumes they are populated.

**Resolution order:**

1. **Extract from context** — if the workflow was invoked via natural language (e.g., `/gh commit summary last 3 days on main`), extract matching parameter values from the request
2. **Apply defaults** — for params with a `default:` value set, use the default if not extracted from context
3. **ASK for required** — for params with `default: null` (required), prompt the user before starting the workflow

**Example params block:**

```yaml
params:
  scope:
    description: "Time range or commit range to summarize"
    type: string
    default: "since last session"
    examples: ["last 3 days", "since v4.1.0"]
  author:
    description: "Filter to a specific git author"
    type: string
    default: null  # required — ASK if not provided
```

### Pseudocode Interpretation Guidelines

When following a workflow's pseudocode, apply these interpretation rules:

| Pseudocode | Runtime Action |
|------------|---------------|
| **Phase labels** (e.g., `GATHER:`, `PRESENT:`) | Execute top to bottom unless `GOTO` redirects |
| **Natural language operations** (e.g., `failures = list recent failed workflow runs`) | Invoke gh-operations skill or use `gh` CLI directly |
| **`ASK "question" (options)`** | Use AskUserQuestion to present choices to the user |
| **`SHOW`** | Display information to the user (tables, summaries, details) |
| **`INFER`** | Use LLM judgment to classify or categorize |
| **`GOTO PHASE`** | Jump back to the named phase (loop) |
| **`STOP "reason"`** | Halt workflow execution, report the reason, record result |
| **`INVOKE skill plugin:name`** | Invoke the named skill via the Skill tool |
| **`state:` variables** | Track in working memory throughout execution |
| **`IF / ELIF / ELSE`** | Branch based on gathered data or user responses |
| **`FOR EACH item IN list`** | Iterate over collected items |
| **`STORE / REMOVE / SET / RECORD`** | Manage state variables |

### State Management

The `state:` field in the workflow YAML declares the workflow's variables. Initialize them at execution start:

```yaml
state:
  failures: []        # initialized as empty list
  selected: null      # initialized as null
  actions_taken: []   # initialized as empty list
```

The pseudocode reads and writes these variables throughout execution. They exist only for the duration of the workflow run — no persistence across sessions.

---

## V1 Execution: Sequential Dispatch (Legacy)

For backward compatibility with workflows that still use `actions:` instead of `workflow:`.

### Action Types

#### `operation`

Route a natural language operation through the operations skill:

```yaml
actions:
  - name: "Summarize PR changes"
    type: operation
    operation: "list open PRs with their diff stats"
```

**Execution:** Invoke `gh-operations` with the `operation` string as arguments.

#### `skill_invoke`

Invoke a specific skill directly:

```yaml
actions:
  - name: "Refresh stale config"
    type: skill_invoke
    skill: "hiivmind-pulse-gh:gh-refresh"
```

**Execution:** Invoke the named skill via the Skill tool.

### Execution Flow

```
1. LOAD workflow YAML
2. CHECK cooldown (poll-state.md)
   └── If cooldown active → skip, report "cooldown"
3. CHECK approval context
   ├── pre-approved (heartbeat selection, on-demand run) → execute immediately
   ├── auto: true  → execute immediately
   └── auto: false → present to user, ask permission
4. EXECUTE actions sequentially
   ├── For each action:
   │   ├── operation → invoke skill: gh-operations, args=action.operation
   │   └── skill_invoke → invoke skill: action.skill
   └── Record per-action result
5. UPDATE poll-state.yaml with execution result
6. REPORT summary
```

### Multi-Action Workflows

When a workflow has multiple actions:

1. Execute actions **sequentially** (order matters)
2. If an action fails, **stop** and record `failure`
3. Report which action failed and why

---

## Pre-Approved Execution

Applies to both v1 and v2 workflows.

When a caller has already obtained user approval to run a workflow (e.g., the heartbeat skill
presented workflows and the user selected which to run), downstream execution MUST NOT re-confirm.

**How to recognize pre-approved context:**
- The heartbeat skill explicitly states workflows are pre-approved after user selection
- On-demand workflow runs (via workflows skill "run" command) are pre-approved by the user's request

**When pre-approved:**
1. Skip the `auto: false` permission check in step 3 of the execution flow — the user already approved
2. Execute directly without confirmation prompts
3. If stale config is detected during execution, auto-refresh and continue — do not stop to ask
4. Read-only operations (list, show, summarize, get) never need confirmation regardless of context
5. For v2 workflows: `ASK` statements in the pseudocode are part of the workflow's designed interaction flow, not permission checks — always execute them

**The `auto` flag meaning is unchanged:**
- `auto: true` — Heartbeat runs this workflow without presenting it for selection
- `auto: false` — Heartbeat presents this workflow for user selection
- After selection, both are pre-approved for execution

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
| `INVOKE skill X` | if a headless sibling exists (`X-headless`), invoke it with explicit inputs (its `workspace_path` = the context's `workspace_root`); otherwise append `"invoke {X}"` to `proposed_actions` |
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

---

## Cooldown Check

Before executing any workflow (skip when the context has `enforce_cooldown: false`):

```bash
WORKFLOW_NAME="$1"
WORKFLOW_FILE="$2"

COOLDOWN=$(yq -r '.cooldown_minutes // 5' "$WORKFLOW_FILE")
LAST_RUN=$(yq -r ".workflows.\"${WORKFLOW_NAME}\".last_run_at // \"null\"" "${WORKSPACE_ROOT}/.hiivmind/github/poll-state.yaml")

if [[ "$LAST_RUN" != "null" ]]; then
    NOW=$(date -u +%s)
    LAST_EPOCH=$(date -d "$LAST_RUN" +%s 2>/dev/null || echo 0)
    ELAPSED=$(( (NOW - LAST_EPOCH) / 60 ))
    if (( ELAPSED < COOLDOWN )); then
        echo "Skipped: cooldown active (${ELAPSED}/${COOLDOWN} min)"
        return 1
    fi
fi
```

**Note:** On-demand workflow runs (via the workflows skill "run" command) skip cooldown checks entirely.

---

## Result Recording

After execution, update poll-state.yaml:

| Field | Value |
|-------|-------|
| `last_run_at` | Current UTC timestamp |
| `last_result` | `success`, `failure`, or `skipped` |
| `run_count` | Increment by 1 |

For v2 workflows, `success` means the pseudocode completed (reached end or `STOP`). `failure` means an unrecoverable error occurred during execution.

---

## Related Patterns

- **poll-state.md** — State tracking and cooldown data
- **config-parsing.md** — Read workflow YAML files
- **error-handling.md** — Handle execution errors
