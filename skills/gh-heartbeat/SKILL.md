---
name: gh-heartbeat
description: >
  Handle session wake-up when the heartbeat hook detects pending work. Processes triggered workflows,
  runs auto workflows immediately, and presents non-auto workflows for user approval. Use this when:
  session starts with pending workflows, heartbeat detected changes, stale config needs attention,
  GitHub state changed since last session. Trigger phrases: "heartbeat", "wake up", "session start",
  "what changed", "pending workflows", "check for changes", "session summary", "what happened",
  "github changes since last session", "morning briefing", "status update",
  "run heartbeat", "check heartbeat", "poll github".
trigger: "heartbeat|wake up|session start|what changed|pending workflows|check for changes|session summary|morning briefing"
tools: [shell, filesystem]
author: hiivmind
---

# Heartbeat Wake-Up

Process triggered workflows detected by the SessionStart hook. Run auto workflows immediately,
present non-auto workflows for user approval.

## Path Convention

`{PLUGIN_ROOT}` = Plugin root directory (where plugin.json lives)

When this skill references files like `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md`,
read from the plugin root, not relative to this skill folder.

## Scope

| Does | Does NOT |
|------|----------|
| Run heartbeat poll when invoked manually | Manage workflow definitions |
| Process heartbeat hook JSON output | Poll GitHub directly (delegates to hook) |
| Run auto workflows immediately | Modify workflow YAML files |
| Present non-auto workflows for approval | Initialize workspaces |
| Update poll-state after execution | |

## Expected Context

This skill receives JSON output from the SessionStart heartbeat hook:

```json
{
  "stale_sections": ["projects", "milestones"],
  "triggered_workflows": ["pr-lifecycle", "auto-refresh"],
  "auto_workflows": ["auto-refresh"]
}
```

---

## Execution Flow

### Phase 0: Run Heartbeat

Ensure heartbeat JSON is available regardless of how this skill was invoked.

**See:** `{PLUGIN_ROOT}/lib/patterns/tool-detection.md`

**0a. Check tool availability** before running the heartbeat script:

1. Check for `gh` CLI, `jq`, `yq` availability
2. **STOP if `gh` is missing** — Cannot proceed without it:

```
GitHub CLI (gh) is required but wasn't found.

Install gh:
- macOS: brew install gh
- Linux (Debian/Ubuntu): sudo apt install gh
- Windows: winget install GitHub.cli

After installation, authenticate with: gh auth login

Cannot proceed without gh CLI.
```

3. **WARN if `jq` or `yq` is missing** (do not block):

```
⚠ Missing recommended tool: [jq/yq]

Install for best results:
- jq: brew install jq / apt install jq
- yq: https://github.com/mikefarah/yq#install

Proceeding with fallback methods...
```

**0b. Run heartbeat:**

1. **Check** if heartbeat JSON was passed as context (from SessionStart hook)
2. **If no hook output is present** (manual invocation): run the heartbeat script directly:

```bash
HEARTBEAT_OUTPUT=$(bash "${CLAUDE_PLUGIN_ROOT}/hooks/heartbeat.sh" 2>/dev/null)
```

3. **If hook output is already available:** use it directly as `HEARTBEAT_OUTPUT`

### 1. Parse Heartbeat Output

Parse the heartbeat JSON from Phase 0.

**If `first_run: true`:** This is the first session with workflows. Report initialization only.

**If `skipped: true`:** Rate limit is low. Report and skip.

```
GitHub heartbeat: Skipped (API rate limit low, ${remaining} remaining)
```

**STOP** — Do not proceed if skipped.

### 2. Assess Triggered Workflows

From the JSON output:

```bash
TRIGGERED=$(echo "$HEARTBEAT_OUTPUT" | jq -r '.triggered_workflows[]')
AUTO=$(echo "$HEARTBEAT_OUTPUT" | jq -r '.auto_workflows[]')
STALE=$(echo "$HEARTBEAT_OUTPUT" | jq -r '.stale_sections[]')
```

**If nothing triggered and no stale sections:**

```
GitHub heartbeat: All clear. No changes detected since last session.
```

**STOP** — Nothing to do.

### 3. Present Summary

Display what was detected:

```
## GitHub Session Summary

### Changes Detected

| Workflow | Trigger | Auto |
|----------|---------|------|
| pr-lifecycle | PR state changed | ask |
| auto-refresh | Config stale | auto |

### Stale Config Sections

- projects (last checked 3 days ago)
- milestones (last checked 2 days ago)
```

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

### 5. Execute Non-Auto Workflows

For workflows in `triggered_workflows` but NOT in `auto_workflows`:

Present a single selection prompt:

```
Which workflows would you like to run?

  1. pr-lifecycle — Summarize PR diffs, suggest reviewers (PR state changed)
  2. project-sync — Detect project board changes (board updated)
  3. All — Run all triggered workflows
  4. Skip — Don't run any workflows

Select one or more (e.g., "1, 2" or "all"):
```

**After user selects:** All selected workflows are **pre-approved**. Execute them immediately
without any further confirmation. This means:

- Do NOT re-confirm individual workflow execution
- Do NOT re-confirm operations invoked by workflow actions
- If stale config is detected during execution, auto-refresh and continue
- Read-only operations never need mutation confirmation
- For v2 workflows: `ASK` statements in the pseudocode are part of the workflow's designed
  interaction flow — always execute them

**See:** `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` (Pre-Approved Execution section)

**Delegate to the executor:** for each selected workflow, execute it per
`{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` with context
`{mode: interactive, approval: pre-approved, enforce_cooldown: true, workspace_root: <resolved root>}`.

### 6. Collect Results

After all executions, update poll-state.yaml with results for each executed workflow.

Build a results summary for Phase 7:

```
EXECUTED_RESULTS = {
  workflow_name: {
    result: "success" | "failure" | "skipped",
    findings: <output from workflow execution (v2: SUMMARIZE phase output, v1: per-action output)>
  }
}

SKIPPED_WORKFLOWS = workflows in triggered but not selected by user
```

Display execution summary:

```
## Heartbeat Results

| Workflow | Result |
|----------|--------|
| auto-refresh | success |
| project-sync | success |
```

### 7. What's Next

Present actionable next steps derived from workflow results. This phase ensures the heartbeat
never ends at a dead end.

**Structure (always in this order):**

**7a. Actions from findings**

Analyze the output of each executed workflow and suggest concrete next actions.
Map workflow types to suggestion patterns:

| Workflow | What to Look For | Suggestion |
|----------|-----------------|------------|
| project-sync | Items in actionable states (Approved, In Review) | "Issue #N is [Status] — [action]?" |
| project-sync | Items assigned to user | "You have N items assigned across projects" |
| pr-lifecycle | PRs needing review | "PR #N needs your review" |
| pr-lifecycle | PRs with requested changes | "PR #N has requested changes to address" |
| ci-monitor | Failed CI runs | "CI run failed on [branch] — investigate?" |
| ci-monitor | Successful runs | "[branch] CI is green" (informational) |
| issue-triage | Untriaged issues | "N new issues need labels" |
| stale-check | Stale PRs/issues | "PR #N has had no activity for N days" |
| auto-refresh | Sections refreshed | "Refreshed: [sections]" (informational) |
| deploy-monitor | Recent deployments | "Deployment to [env] [succeeded/failed]" |
| release-monitor | New releases | "Release [tag] published — review notes?" |
| dependabot-alerts | New or critical alerts | "N new dependabot alerts — review?" |

**Example:**
```
## What's Next

Based on what we found:
  - #9 Plan: Dev Ops Clarity is Approved — start implementing?
  - Board has 4 items in Implementing
  - PR #15 needs your review
```

**7b. Remaining workflows** (only if some triggered workflows were not selected)

```
Workflows not run this session:
  - pr-lifecycle, ci-monitor

Run remaining?
```

**7c. Fallback**

Always end with an escape to broader options:

```
Pick an action, or /gh for more options.
```

**If no workflows produced actionable findings** (e.g., only auto-refresh ran):

```
## What's Next

All clear — no items need attention right now.

/gh for GitHub operations.
```

---

## Error Handling

| Error | Cause | Action |
|-------|-------|--------|
| No heartbeat output | Hook didn't run or failed | Run heartbeat manually |
| Workflow file missing | Referenced workflow deleted | Skip and warn |
| Action execution failed | API error or skill error | Record failure, continue with next |
| Rate limit exceeded | Too many API calls | Stop execution, report remaining |

**See:** `{PLUGIN_ROOT}/lib/patterns/error-handling.md`

---

## Related Skills

| Skill | Use For |
|-------|---------|
| **workflows** | Managing workflow definitions |
| **operations** | Executing workflow actions |
| **refresh** | Target of auto-refresh workflow |

---

## Resources

### Patterns

| Pattern | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` | Action types, cooldown, result recording |
| `{PLUGIN_ROOT}/lib/patterns/poll-state.md` | State tracking and change detection |
| `{PLUGIN_ROOT}/lib/patterns/error-handling.md` | Handle execution errors |

### References

| Reference | Purpose |
|-----------|---------|
| `{PLUGIN_ROOT}/lib/references/workflow-triggers.md` | Trigger type lookup table |
