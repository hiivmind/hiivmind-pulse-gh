# Pattern: Workflow Execution

## Purpose

Execute workflow actions after triggers fire, with cooldown enforcement and result recording.

## When to Use

- Heartbeat skill needs to run triggered workflows
- Workflows skill runs an on-demand workflow
- Post-operation hook triggers a workflow

## Prerequisites

- **poll-state.md** — Cooldown checks and result recording
- **config-parsing.md** — Read workflow YAML files

---

## Action Types

### `operation`

Route a natural language operation through the operations skill:

```yaml
actions:
  - name: "Summarize PR changes"
    type: operation
    operation: "list open PRs with their diff stats"
```

**Execution:** Invoke `gh-operations` with the `operation` string as arguments.

### `skill_invoke`

Invoke a specific skill directly:

```yaml
actions:
  - name: "Refresh stale config"
    type: skill_invoke
    skill: "hiivmind-pulse-gh:gh-refresh"
```

**Execution:** Invoke the named skill via the Skill tool.

---

## Execution Flow

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

---

## Pre-Approved Execution

When a caller has already obtained user approval to run a workflow (e.g., the heartbeat skill
presented workflows and the user selected which to run), downstream execution MUST NOT re-confirm.

**How to recognize pre-approved context:**
- The heartbeat skill explicitly states workflows are pre-approved after user selection
- On-demand workflow runs (via workflows skill "run" command) are pre-approved by the user's request

**When pre-approved:**
1. Skip the `auto: false` permission check in step 3 of the execution flow — the user already approved
2. Execute actions directly without confirmation prompts
3. If stale config is detected during execution, auto-refresh and continue — do not stop to ask
4. Read-only operations (list, show, summarize, get) never need confirmation regardless of context

**The `auto` flag meaning is unchanged:**
- `auto: true` — Heartbeat runs this workflow without presenting it for selection (Phase 4)
- `auto: false` — Heartbeat presents this workflow for user selection (Phase 5)
- After selection, both are pre-approved for execution

---

## Cooldown Check

Before executing any workflow:

```bash
WORKFLOW_NAME="$1"
WORKFLOW_FILE="$2"

COOLDOWN=$(yq -r '.cooldown_minutes // 5' "$WORKFLOW_FILE")
LAST_RUN=$(yq -r ".workflows.\"${WORKFLOW_NAME}\".last_run_at // \"null\"" .hiivmind/github/poll-state.yaml)

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

---

## Result Recording

After execution, update poll-state.yaml:

| Field | Value |
|-------|-------|
| `last_run_at` | Current UTC timestamp |
| `last_result` | `success`, `failure`, or `skipped` |
| `run_count` | Increment by 1 |

---

## Multi-Action Workflows

When a workflow has multiple actions:

1. Execute actions **sequentially** (order matters)
2. If an action fails, **stop** and record `failure`
3. Report which action failed and why

---

## Related Patterns

- **poll-state.md** — State tracking and cooldown data
- **config-parsing.md** — Read workflow YAML files
- **error-handling.md** — Handle execution errors
