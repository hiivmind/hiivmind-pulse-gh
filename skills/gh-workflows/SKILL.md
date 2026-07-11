---
name: gh-workflows
description: >
  Manage event-driven workflows for GitHub automation. List, enable, disable, run, create, and check
  status of workflows that trigger on session start, after operations, or on demand. Use this when:
  managing automation rules, configuring what happens on session start, enabling/disabling workflows,
  running workflows manually, creating custom workflows, checking workflow status. Trigger phrases:
  "list workflows", "enable workflow", "disable workflow", "run workflow", "create workflow",
  "workflow status", "show automations", "manage automations", "configure automation",
  "what workflows are active", "turn on workflow", "turn off workflow", "automation settings",
  "heartbeat config", "event triggers", "workflow list", "my workflows".
trigger: "list workflows|enable workflow|disable workflow|run workflow|create workflow|workflow status|manage automations"
tools: [shell, filesystem]
author: hiivmind
---

# Workflow Management

Manage event-driven workflows that automate GitHub operations based on triggers.

## Path Convention

`{PLUGIN_ROOT}` = Plugin root directory (where plugin.json lives)

When this skill references files like `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md`,
read from the plugin root, not relative to this skill folder.

## Scope

| Does | Does NOT |
|------|----------|
| List, enable, disable workflows | Execute GitHub API operations directly |
| Run workflows on demand | Modify workspace config.yaml |
| Create workflows from templates | Handle SessionStart hook logic |
| Show workflow status and history | Poll GitHub for state changes |

## Expected Context

When invoked by the gateway command, expect:

- **Operation**: list, enable, disable, run, create, status
- **Target**: Workflow name (optional, for specific workflow operations)
- **Config**: `.hiivmind/github/config.yaml` must exist
- **Workflows dir**: `.hiivmind/github/workflows/`

---

## Execution Flow

### 1. Verify Workspace

Check for `.hiivmind/github/config.yaml` in current directory OR parent directories:

```bash
# Resolve workspace root (see lib/patterns/workspace-detection.md)
CONFIG_DIR=""
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
    if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] \
       && grep -q '^workspace:' "$DIR/.hiivmind/github/config.yaml"; then
        CONFIG_DIR="$DIR/.hiivmind/github"
        break
    fi
    DIR="$(dirname "$DIR")"
done
```

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

**If not found:**

```
Workspace not initialized.

Run: /gh init
```

**STOP** — Cannot manage workflows without initialized workspace.

### 2. Ensure Workflows Directory

```bash
WORKFLOWS_DIR="${CONFIG_DIR}/workflows"
mkdir -p "$WORKFLOWS_DIR"
```

### 3. Detect Operation

Parse `$ARGUMENTS` to determine the requested operation:

| Keywords | Operation |
|----------|-----------|
| `list`, `show`, `active` | **list** |
| `enable`, `turn on`, `activate` | **enable** |
| `disable`, `turn off`, `deactivate` | **disable** |
| `run`, `execute`, `trigger` | **run** |
| `create`, `new`, `add` | **create** |
| `status`, `history`, `info` | **status** |

**If ambiguous:** Ask the user to choose from the available options.

---

## Operations

### List Workflows

Show all workflows with their status:

```bash
for WF_FILE in "$WORKFLOWS_DIR"/*.yaml; do
    [[ -f "$WF_FILE" ]] || continue
    NAME=$(yq -r '.name' "$WF_FILE")
    ENABLED=$(yq -r '.enabled // true' "$WF_FILE")
    AUTO=$(yq -r '.auto // false' "$WF_FILE")
    TRIGGER=$(yq -r '.trigger.type' "$WF_FILE")
    DESC=$(yq -r '.description' "$WF_FILE")
done
```

**Output format:**

```
## Active Workflows

| Workflow | Trigger | Auto | Status |
|----------|---------|------|--------|
| pr-lifecycle | session_poll | no | enabled |
| ci-monitor | session_poll | no | enabled |
| auto-refresh | freshness | no | enabled |

## Available Templates

Templates not yet installed:
- issue-triage — Detect new issues, suggest labels
- stale-check — Flag stale PRs/issues
```

**If no workflows exist:**

```
No workflows configured yet.

Would you like to install a built-in workflow template?
```

Present available templates from `{PLUGIN_ROOT}/templates/workflows/` and ask the user to choose.

### Enable/Disable Workflow

```bash
yq -i '.enabled = true' "$WORKFLOWS_DIR/${WF_NAME}.yaml"   # enable
yq -i '.enabled = false' "$WORKFLOWS_DIR/${WF_NAME}.yaml"  # disable
```

**If workflow not found:** List available workflows and ask which one.

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

### Create Workflow

1. Present available templates from `{PLUGIN_ROOT}/templates/workflows/`:

```
Available workflow templates:

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

2. Copy selected template to `$WORKFLOWS_DIR/`
3. Ask if user wants to customize (name, auto flag, cooldown)

**For custom workflows:**

1. Copy `{PLUGIN_ROOT}/templates/workflow.yaml.template` to `$WORKFLOWS_DIR/`
2. Walk through fields by prompting the user for each value
3. **See:** `{PLUGIN_ROOT}/lib/references/workflow-triggers.md` for trigger options

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

---

## Error Handling

| Error | Cause | Action |
|-------|-------|--------|
| Workspace not initialized | No config.yaml | Offer to run init |
| Workflow not found | Name doesn't match any file | List available workflows |
| Invalid YAML | Malformed workflow file | Show parse error, suggest fix |
| Template not found | Missing templates directory | Check plugin installation |

---

## Related Skills

| Skill | Use For |
|-------|---------|
| **heartbeat** | Handles triggered workflows on session start |
| **operations** | Executes workflow actions |
| **refresh** | Auto-refresh workflow target |
| **init** | Prerequisite workspace setup |

---

## Resources

### Patterns

| Pattern | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` | Action types, cooldown, result recording |
| `{PLUGIN_ROOT}/lib/patterns/poll-state.md` | State tracking and change detection |
| `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` | Read/write YAML config files |

### References

| Reference | Purpose |
|-----------|---------|
| `{PLUGIN_ROOT}/lib/references/workflow-triggers.md` | Trigger type lookup table |
