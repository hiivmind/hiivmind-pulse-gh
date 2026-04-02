# V2 Workflow Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the workflow execution runtime (3 markdown skill/pattern documents) to interpret v2 `workflow:` pseudocode instead of `actions[]`.

**Architecture:** The workflow-execution pattern is the shared foundation — update it first, then update the two skills that reference it (heartbeat and workflows). Each file is a complete rewrite of specific sections, preserving unchanged sections.

**Tech Stack:** Markdown skill documents only. No code, no tests.

---

### Task 1: Update workflow-execution pattern

**Files:**
- Modify: `lib/patterns/workflow-execution.md`

This is the shared pattern referenced by both skills. Replace the entire file with the v2 version that supports both pseudocode handoff and backward-compatible action dispatch.

- [ ] **Step 1: Read the current file**

Read: `lib/patterns/workflow-execution.md`

Confirm it currently has sections: Purpose, When to Use, Prerequisites, Action Types (`operation`, `skill_invoke`), Execution Flow (6 steps with actions[]), Pre-Approved Execution, Cooldown Check, Result Recording, Multi-Action Workflows, Related Patterns.

- [ ] **Step 2: Rewrite the file**

Replace the full content of `lib/patterns/workflow-execution.md` with:

````markdown
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
````

- [ ] **Step 3: Verify the file renders correctly**

Run: `head -5 lib/patterns/workflow-execution.md && echo "---" && wc -l lib/patterns/workflow-execution.md`
Expected: First 5 lines show the title and purpose. Line count should be approximately 180-200 lines.

- [ ] **Step 4: Commit**

```bash
git add lib/patterns/workflow-execution.md
git commit -m "feat(patterns): update workflow-execution for v2 pseudocode handoff

Replace actions[] dispatch with pseudocode handoff as primary
execution method. Retains v1 sequential dispatch for backward
compatibility. Adds parameter resolution and interpretation
guidelines."
```

---

### Task 2: Update heartbeat skill

**Files:**
- Modify: `skills/gh-heartbeat/SKILL.md`

The heartbeat skill needs Phases 4 and 6 updated to use the new workflow-execution pattern. Phase 5 (present non-auto workflows) is unchanged. Phase 7 gets a minor update.

- [ ] **Step 1: Read the current file**

Read: `skills/gh-heartbeat/SKILL.md`

Note the structure: frontmatter, intro, scope table, expected context, then Phases 0-7, error handling, related skills, resources.

- [ ] **Step 2: Update the frontmatter version**

In `skills/gh-heartbeat/SKILL.md`, change the version in the frontmatter:

```yaml
version: 4.1.0
```

- [ ] **Step 3: Replace Phase 4 section**

Find the section starting with `### 4. Execute Auto Workflows` and replace it entirely (up to but not including `### 5.`) with:

````markdown
### 4. Execute Auto Workflows

**Execution context:** Auto workflows are pre-approved by definition. Execute without confirmation.
When invoking downstream skills (operations, refresh), all execution is pre-approved — do NOT
re-confirm with the user.

**See:** `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md`

For each workflow in `auto_workflows`:

1. Load workflow YAML from `.hiivmind/github/workflows/`
2. Detect format:
   - **If `workflow:` field exists (v2):** Follow the pseudocode handoff pattern:
     - Read `state:` field and initialize variables
     - If `params:` exists, resolve parameters (extract from context → apply defaults → ASK for required)
     - Follow the `workflow:` pseudocode as executable instructions
     - Use gh-operations for data operations, AskUserQuestion for `ASK` statements
     - Track state variables through FSM phases
   - **If `actions:` field exists (v1):** Fall back to sequential dispatch:
     - Execute actions in order
     - `operation` → invoke gh-operations with the operation string
     - `skill_invoke` → invoke the named skill
3. Update poll-state.yaml with result

```
Running auto workflow: auto-refresh
  Following workflow pseudocode...
  EXECUTE: Invoking skill hiivmind-pulse-gh:gh-refresh
  Result: success
```
````

- [ ] **Step 4: Replace Phase 6 heading and content**

The current Phase 6 is combined into Phase 5 in the existing skill. Find the section after the user selection prompt in Phase 5 that describes executing selected workflows. It starts with `**After user selects:**`.

Replace the execution instructions (from `**After user selects:**` through to `For each selected workflow, execute using the workflow execution pattern with pre-approved context.`) with:

````markdown
**After user selects:** All selected workflows are **pre-approved**. Execute them immediately
without any further confirmation. This means:

- Do NOT re-confirm individual workflow execution
- Do NOT re-confirm operations invoked by workflow actions
- If stale config is detected during execution, auto-refresh and continue
- Read-only operations never need mutation confirmation
- For v2 workflows: `ASK` statements in the pseudocode are part of the workflow's designed
  interaction flow — always execute them

**See:** `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` (Pre-Approved Execution section)

For each selected workflow, execute using the workflow execution pattern:

1. Load workflow YAML
2. Detect format:
   - **v2 (`workflow:` field):** Follow pseudocode handoff — resolve params, follow FSM
   - **v1 (`actions:` field):** Sequential dispatch
3. Update poll-state.yaml with result
````

- [ ] **Step 5: Update Phase 6 (Collect Results)**

Find `### 6. Collect Results` and update the results structure to reflect v2 output:

Replace the `EXECUTED_RESULTS` block:

```
EXECUTED_RESULTS = {
  workflow_name: {
    result: "success" | "failure" | "skipped",
    findings: <output from workflow actions>
  }
}
```

with:

```
EXECUTED_RESULTS = {
  workflow_name: {
    result: "success" | "failure" | "skipped",
    findings: <output from workflow execution (v2: SUMMARIZE phase output, v1: per-action output)>
  }
}
```

- [ ] **Step 6: Verify the file structure**

Run: `grep "^### " skills/gh-heartbeat/SKILL.md`
Expected: Phase headers 0-7 should all be present, unchanged in naming.

- [ ] **Step 7: Commit**

```bash
git add skills/gh-heartbeat/SKILL.md
git commit -m "feat(heartbeat): update execution phases for v2 pseudocode workflows

Phases 4 and 5/6 now detect workflow format and use pseudocode
handoff for v2 workflows. Backward compatible with v1 actions[]."
```

---

### Task 3: Update workflows skill

**Files:**
- Modify: `skills/gh-workflows/SKILL.md`

The workflows skill needs its "Run Workflow" and "Status" operations updated.

- [ ] **Step 1: Read the current file**

Read: `skills/gh-workflows/SKILL.md`

Note the structure: frontmatter, intro, scope, expected context, execution flow (verify workspace, ensure dir, detect operation), then operations (List, Enable/Disable, Run, Create, Status), error handling, related skills, resources.

- [ ] **Step 2: Update the frontmatter version**

In `skills/gh-workflows/SKILL.md`, change the version in the frontmatter:

```yaml
version: 4.1.0
```

- [ ] **Step 3: Replace "Run Workflow" operation**

Find the `### Run Workflow (On Demand)` section and replace it entirely (up to but not including `### Create Workflow`) with:

````markdown
### Run Workflow (On Demand)

**See:** `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md`

1. Load the workflow YAML
2. Skip cooldown check (on-demand ignores cooldown)
3. Detect format and execute:

**V2 workflows (has `workflow:` field):**

1. If workflow has `params:`, resolve parameters:
   - Extract values from the user's run request (e.g., "run commit-summary last 3 days on main")
   - Apply defaults for params not mentioned
   - ASK for required params (where `default: null`) that weren't provided
2. Initialize `state:` variables
3. Follow the `workflow:` pseudocode as executable instructions
4. Update poll-state.yaml with result

```
Running workflow: ci-monitor

Following workflow pseudocode...

GATHER: Listing recent failed workflow runs...
  Found 2 failures.
  Classifying each failure...

PRESENT:
  | Workflow | Branch | Classification | You Touched | Time |
  |----------|--------|----------------|-------------|------|
  | CI       | main   | test           | yes         | 2h ago |
  | Deploy   | main   | infra          | no          | 5h ago |

  Which failure to investigate?
```

**V1 workflows (has `actions:` field, legacy):**

1. Execute actions sequentially
2. Update poll-state.yaml with result

```
Running workflow: pr-lifecycle

Action 1/2: Summarize open PRs
[operations skill output]

Action 2/2: Highlight review needs
[operations skill output]

Workflow complete. Result: success
```
````

- [ ] **Step 4: Replace "Status" operation**

Find the `### Status` section and replace it entirely (up to but not including `---` or the next top-level section) with:

````markdown
### Status

Show detailed info for a specific workflow:

**V2 workflows:**

```bash
NAME=$(yq -r '.name' "$WF_FILE")
ENABLED=$(yq -r '.enabled // true' "$WF_FILE")
AUTO=$(yq -r '.auto // false' "$WF_FILE")
TRIGGER_TYPE=$(yq -r '.trigger.type' "$WF_FILE")
TRIGGER_SOURCE=$(yq -r '.trigger.source // ""' "$WF_FILE")
TRIGGER_CONDITION=$(yq -r '.trigger.condition // ""' "$WF_FILE")
COOLDOWN=$(yq -r '.cooldown_minutes // 5' "$WF_FILE")
```

Extract phase names from the `workflow:` field:

```bash
PHASES=$(yq -r '.workflow' "$WF_FILE" | grep -oE '^  [A-Z]+(\([^)]*\))?' | sed 's/^ *//' | tr '\n' ' → ' | sed 's/ → $//')
```

Extract params summary if present:

```bash
if yq -e '.params' "$WF_FILE" >/dev/null 2>&1; then
    PARAMS=$(yq -r '.params | to_entries[] | .key + " (" + (if .value.default == null then "required" else "default: \"" + (.value.default // "null") + "\"" end) + ")"' "$WF_FILE" | paste -sd ', ')
else
    PARAMS="none"
fi
```

**Output format:**

```
## Workflow: ci-monitor

Description: Detect failed CI runs, classify failures, and offer targeted remediation
Enabled: yes
Auto: no
Trigger: session_poll (actions, new_failure)
Cooldown: 10 minutes
Params: none

### Phases

GATHER → PRESENT → INVESTIGATE → SUMMARIZE

### Execution History

Last run: 2026-04-01T10:30:00Z
Last result: success
Total runs: 5
```

For parameterized workflows:

```
Params: scope (default: "since last session"), branch (default: "current"), author (required)
```

**V1 workflows (legacy):**

```
### Actions

1. Summarize open PRs (operation)
2. Highlight review needs (operation)
```

Read execution history from `.hiivmind/github/poll-state.yaml`.
````

- [ ] **Step 5: Update "Create Workflow" template count**

In the `### Create Workflow` section, find the numbered list of available templates:

```
1. pr-lifecycle — Summarize PR diffs, suggest reviewers
2. issue-triage — Detect new issues, auto-label
3. ci-monitor — Detect failed CI runs, analyze logs
4. stale-check — Flag stale PRs/issues
5. auto-refresh — Refresh stale config sections
```

Replace it with the full list of 13 templates:

```
1. auto-refresh — Refresh stale config on session start
2. ci-monitor — Classify CI failures, offer targeted remediation
3. commit-summary — Summarize commit activity by time/branch/author
4. community-activity — Repo-wide activity across issues, PRs, discussions
5. dependabot-alerts — Prioritize security vulnerabilities, offer remediation
6. deploy-monitor — Track deployments, surface failures
7. issue-triage — Detect untriaged issues, suggest labels and milestones
8. pr-lifecycle — Triage PRs by urgency, offer review actions
9. project-sync — Detect project board changes, offer status management
10. release-monitor — Detect new releases, offer follow-up actions
11. repo-healthcheck — On-demand repository governance audit
12. stale-check — Find stale PRs/issues, offer actions
13. user-activity — Summarize a user's activity across all domains
```

- [ ] **Step 6: Verify the file structure**

Run: `grep "^### " skills/gh-workflows/SKILL.md`
Expected: Should show List Workflows, Enable/Disable Workflow, Run Workflow, Create Workflow, Status as operation sections.

- [ ] **Step 7: Commit**

```bash
git add skills/gh-workflows/SKILL.md
git commit -m "feat(workflows-skill): update run and status for v2 pseudocode workflows

Run operation now detects format and uses pseudocode handoff for v2.
Status shows phases and params instead of actions list.
Template list updated to 13 workflows."
```

---

### Task 4: Final verification

- [ ] **Step 1: Verify all three files reference the workflow-execution pattern consistently**

Run: `grep -n "workflow-execution" lib/patterns/workflow-execution.md skills/gh-heartbeat/SKILL.md skills/gh-workflows/SKILL.md`
Expected: Both skills reference `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md`.

- [ ] **Step 2: Verify "workflow:" appears in the execution pattern**

Run: `grep -c "workflow:" lib/patterns/workflow-execution.md`
Expected: Multiple occurrences (the field is referenced throughout).

- [ ] **Step 3: Verify backward compatibility is documented**

Run: `grep -n "actions:" lib/patterns/workflow-execution.md`
Expected: The v1 legacy section still documents `actions:` dispatch.

- [ ] **Step 4: Verify version bumps**

Run: `grep "version:" skills/gh-heartbeat/SKILL.md skills/gh-workflows/SKILL.md`
Expected: Both show `version: 4.1.0`.
