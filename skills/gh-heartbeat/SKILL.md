---
name: gh-heartbeat
version: 4.0.0
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

For each workflow in `auto_workflows`:

**See:** `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md`

1. Load workflow YAML from `.hiivmind/github/workflows/`
2. Execute actions sequentially
3. Update poll-state.yaml with result

```
Running auto workflow: auto-refresh
  Action: Refresh stale sections → invoking refresh skill...
  Result: success
```

### 5. Present Non-Auto Workflows

For workflows in `triggered_workflows` but NOT in `auto_workflows`:

```
The following workflows were triggered but need your approval:
```

Ask the user which workflows to run:

```
Which workflows would you like to run?

  1. pr-lifecycle — Summarize PR diffs, suggest reviewers (PR state changed)
  2. Skip all — Don't run any workflows this session
```

For each selected workflow, execute using the workflow execution pattern.

### 6. Update State

After all executions:

1. Update poll-state.yaml with results for each executed workflow
2. Report final summary:

```
## Heartbeat Complete

| Workflow | Result |
|----------|--------|
| auto-refresh | success |
| pr-lifecycle | success |

Next heartbeat will run on next session start.
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
