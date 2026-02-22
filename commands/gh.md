---
description: Unified entry point for GitHub operations - describe what you need in natural language
argument-hint: Describe your goal (e.g., "create issue for login bug", "set milestone v2.0 on #42", "add PR to project")
trigger: "gh|github|create issue|close issue|merge PR|set milestone|add label|trigger workflow"
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep", "AskUserQuestion", "Skill", "Task"]
---

# GitHub Operations Gateway

Unified entry point for all GitHub operations via hiivmind-pulse-gh.

**User request:** $ARGUMENTS

**Intent mapping:** `commands/intent-mapping.yaml`

---

## Step 1: Check for Arguments

**If `$ARGUMENTS` is empty** → Go to **Mode: Interactive Menu**

> **Workflow/Heartbeat routing:** If arguments match workflow management (list/enable/disable/run/create workflows)
> or heartbeat (what changed, session summary), route to the workflows or heartbeat skill respectively.
> See intent-mapping.yaml for keyword definitions.

**If `$ARGUMENTS` is provided** → Continue to Step 2

---

## Step 2: Intent Detection (3VL)

Load `commands/intent-mapping.yaml` and evaluate `$ARGUMENTS` using three-valued logic.

### 2a: Load Intent Mapping

Read the intent mapping file from the plugin directory:

```
Read: {PLUGIN_ROOT}/commands/intent-mapping.yaml
```

This file defines `intent_flags`, `intent_rules`, and `actions`.

### 2b: Evaluate Flags

For each flag in `intent_flags`, scan `$ARGUMENTS` for keyword matches:

| Match Result | Flag Value | Meaning |
|-------------|------------|---------|
| Keyword found in input | **T** (True) | Positive match |
| Negative keyword found | **F** (False) | Explicit exclusion |
| Neither found | **U** (Unknown) | No signal |

```pseudocode
FOR flag IN intent_flags:
  IF any(keyword IN arguments.lower() FOR keyword IN flag.keywords):
    computed.intent_flags[flag.name] = T
  ELIF flag.negative_keywords AND any(nkw IN arguments.lower() FOR nkw IN flag.negative_keywords):
    computed.intent_flags[flag.name] = F
  ELSE:
    computed.intent_flags[flag.name] = U
```

### 2c: Match Rules

Evaluate rules in order (first match wins). A rule matches when ALL its conditions are satisfied:

```pseudocode
FOR rule IN intent_rules:
  match = true
  FOR flag_name, required_value IN rule.conditions:
    actual = computed.intent_flags[flag_name]
    IF required_value == T AND actual != T: match = false
    IF required_value == F AND actual != F: match = false
    # U conditions: actual must be U (no signal either way)
  IF match:
    computed.matched_rule = rule
    computed.matched_action = rule.action
    BREAK
```

**If no rule matches:** The fallback rule (empty conditions) always matches last.

### 2d: Extract Target

Regardless of intent matching, extract target entities from `$ARGUMENTS`:

- Issue/PR numbers: `#42`, `issue 42`, `PR #15`
- Milestone names: `"v2.0"`, `milestone v2.0`
- Project numbers: `project 2`, `project #1`
- Branch names: `main`, `develop`
- Workflow names: `ci.yml`, `deploy.yml`

Store in `computed.target` for passing to skills.

### 2e: Ambiguity Resolution

If the matched action is `show_main_menu` but arguments were provided (intent was unclear):

1. Prompt the user to choose between the top candidates
2. Present the top 2-3 candidate rules based on partial flag matches
3. User selection determines the action

---

## Step 2.5: Check Tool Availability

**See:** `lib/patterns/tool-detection.md`

Before proceeding, verify required tools are available:

1. **Check `gh` CLI** — `command -v gh >/dev/null 2>&1`
2. **Check `jq`** — `command -v jq >/dev/null 2>&1`
3. **Check `yq`** — `command -v yq >/dev/null 2>&1`

**STOP if `gh` is missing:**

```
GitHub CLI (gh) is required but wasn't found.

Install gh:
- macOS: brew install gh
- Linux (Debian/Ubuntu): sudo apt install gh
- Windows: winget install GitHub.cli

After installation, authenticate with: gh auth login

Cannot proceed without gh CLI.
```

**WARN if `jq` or `yq` is missing** (do not block):

```
⚠ Missing recommended tool: [jq/yq]

Install for best results:
- jq: brew install jq / apt install jq
- yq: https://github.com/mikefarah/yq#install

Proceeding with fallback methods...
```

---

## Step 3: Context Detection (Conditional)

**Skip this step if matched action is:** `delegate_discover`, `show_full_help`, `show_skill_help_*`, `block_operation`, `show_main_menu`

These actions either handle their own context checks internally or don't require workspace initialization.

**For all other actions, continue below:**

### 3a: Check Initialization

**See:** `lib/patterns/config-parsing.md`

Check for `.hiivmind/github/config.yaml` in **current directory and parent directories**:

```bash
# Check current and parent directory (covers workspace setups)
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH=".hiivmind/github/config.yaml"
    initialized="yes"
elif [[ -f "../.hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH="../.hiivmind/github/config.yaml"
    initialized="yes"
else
    initialized="no"
fi
```

**Why check parent:** Common in workspace setups where:
- Parent directory contains multiple repos with shared config
- User runs init from workspace root, operates from child repos
- Monorepo with config at root

**If not found (in current or parent):**
1. Inform user: "This workspace hasn't been initialized for GitHub operations."
2. Ask: "Would you like to initialize now?"
3. If yes → Invoke skill: `hiivmind-pulse-gh:gh-init`
4. After init completes → Return and continue

### 3b: Check Freshness

**See:** `lib/patterns/config-parsing.md` (freshness section)

Check `.hiivmind/github/freshness.yaml`:

**Staleness Policy:**

| Level | Age | Read Ops | Mutations |
|-------|-----|----------|-----------|
| Fresh | < threshold | ✅ Allow | ✅ Allow |
| Soft Stale | 1-2x threshold | ✅ Warn | ✅ Warn |
| Hard Stale | >= 2x threshold | ✅ Warn | ❌ Block |

**If hard stale and mutation requested:**
1. Block: "Config is critically stale. Cannot perform mutation."
2. Offer: "Would you like to refresh first?"
3. If yes → Invoke skill: `hiivmind-pulse-gh:gh-refresh`
4. After refresh → Continue

---

## Step 4: Confirm Mutations

For create/update/delete operations (when `has_create`, `has_update`, or `has_delete` is T):

1. Summarize the intended action
2. Ask: "Proceed with this operation?"
3. If no → Abort gracefully

---

## Step 5: Execute Matched Action

Look up `computed.matched_action` in the `actions` section of the intent mapping and execute:

### Skill Dispatch Protocol

**CRITICAL:** This gateway is a ROUTER, not an executor. When a skill is matched:

1. **DO NOT answer the user's request yourself** - Your job is routing, not answering
2. **DO NOT pre-validate or gather information** - Let the skill handle its own context
3. **IMMEDIATELY invoke the skill** using the Skill tool
4. **Let the skill take over** - It will load its own SKILL.md and execute

### Action Types

| Action Type | Behavior |
|-------------|----------|
| `invoke_skill` | Invoke the named skill via Skill tool, passing `$ARGUMENTS` |
| `display` | Display the content block to the user |
| `user_prompt` | Present options to the user for selection, then route |
| `block_operation` | Display safety block message, do not proceed |

### Invoke Skill Actions

For actions where `type: invoke_skill`:

```
Invoke skill: action.skill
  args: "$ARGUMENTS"
```

**Pass context** to operations skill:
- The full `$ARGUMENTS` text (skill parses its own domain/operation/target)
- Workspace config path if detected in Step 3

### Display Actions

For actions where `type: display`, output the `content` block directly to the user.

### User Prompt Actions

For actions where `type: user_prompt`, present the prompt's options to the user for selection. Map the user's selection back through intent detection (treat selection as new `$ARGUMENTS`).

---

## Mode: Interactive Menu (No Arguments)

When invoked without arguments, display a reference table for discoverability, then present context-aware quick actions.

### Step A: Display Reference Table

Output this table to show users what's available:

```
## GitHub Operations Reference

| Domain | Typical Operations |
|--------|-------------------|
| **Issues** | create, update, close, comment, label, assign |
| **Pull Requests** | create, merge, review, comment, request reviewers |
| **Projects** | add item, update status/fields, archive, view board |
| **Milestones** | create, assign to issue/PR, update, delete |
| **Actions** | trigger workflow, view runs, cancel, rerun |
| **Releases** | create, upload assets, publish, delete |
| **Labels** | create, add/remove from issue, update color |
| **Branch Protection** | set rules, require reviews, status checks |
| **Secrets & Variables** | set, update, delete, list |
| **Setup** | initialize workspace, refresh config |

Select a quick action below, or choose "Other" to describe what you need.
```

### Step B: Detect Context

Gather context to suggest relevant actions:

```bash
# 1. Check workspace initialization (current and parent directory)
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    initialized="yes"
    CONFIG_PATH=".hiivmind/github/config.yaml"
elif [[ -f "../.hiivmind/github/config.yaml" ]]; then
    initialized="yes"
    CONFIG_PATH="../.hiivmind/github/config.yaml"
else
    initialized="no"
fi

# 2. Check git state
current_branch=$(git branch --show-current 2>/dev/null)
is_main=$(test "$current_branch" = "main" -o "$current_branch" = "master" && echo "yes" || echo "no")
has_changes=$(test -n "$(git status --porcelain 2>/dev/null)" && echo "yes" || echo "no")

# 3. Check for open PRs on current branch
# (optional - only if gh is available and authenticated)
```

### Step C: Context-Aware Quick Actions

Based on detected context, select 3 relevant options:

**If NOT initialized:**
```yaml
question: "What would you like to do?"
header: "Action"
options:
  - label: "Initialize workspace"
    description: "Set up GitHub integration for this repo"
  - label: "Create an issue"
    description: "Will initialize first, then create issue"
# "Other" auto-added - user can type any request
```

**If on feature branch with changes:**
```yaml
question: "What would you like to do?"
header: "Action"
options:
  - label: "Create a PR"
    description: "Open pull request for current branch"
  - label: "Create an issue"
    description: "Open a new issue"
  - label: "View open PRs"
    description: "List pull requests in this repo"
# "Other" auto-added
```

**If on main/master branch (clean state):**
```yaml
question: "What would you like to do?"
header: "Action"
options:
  - label: "Create an issue"
    description: "Open a new issue"
  - label: "View project board"
    description: "See project items and status"
  - label: "Run healthcheck"
    description: "Assess repository governance maturity"
# "Other" auto-added
```

**If config is stale:**
```yaml
question: "What would you like to do?"
header: "Action"
options:
  - label: "Refresh config"
    description: "Sync workspace config with GitHub"
  - label: "Create an issue"
    description: "Open a new issue"
  - label: "View status"
    description: "Check repo and config status"
# "Other" auto-added
```

### Step D: Handle Selection

| Selection | Action |
|-----------|--------|
| Quick action selected | Treat label as `$ARGUMENTS`, run through **Step 2: Intent Detection** |
| "Other" selected | User provides text → treat as `$ARGUMENTS`, run through **Step 2: Intent Detection** |

---

## Error Handling

**See:** `lib/patterns/error-handling.md`

| Error | Cause | Action |
|-------|-------|--------|
| Intent mapping not found | File missing | Fall back to interactive menu |
| Config not found | Not initialized | Offer to run init |
| Config stale | Threshold exceeded | Offer to refresh |
| Permission denied | Insufficient access | Check `gh auth status` |
| Ambiguous intent | Multiple flag matches | Ask the user to disambiguate |
| Blocked operation | Safety rule matched | Display block message |

---

## Example Sessions

### Simple Issue Creation

**User:** `/gh create issue for login timeout bug`

**Flow:**
1. Arguments provided
2. Intent flags: `has_create: T`, `has_issues: T` → Rule `issues_operation` matches → Action `delegate_operations`
3. Context: Initialized ✓, Fresh ✓
4. Confirm: "Create issue titled 'login timeout bug'?"
5. Invoke skill: `hiivmind-pulse-gh:gh-operations`

### Not Initialized

**User:** `/gh create issue for bug`

**Flow:**
1. Arguments provided
2. Intent flags: `has_create: T`, `has_issues: T` → Rule `issues_operation` → Action `delegate_operations`
3. Context: NOT initialized → Ask "Initialize workspace first?"
4. If yes → Invoke `hiivmind-pulse-gh:gh-init`
5. After init → Resume with original request

### Stale Config

**User:** `/gh add PR to project`

**Flow:**
1. Arguments provided
2. Intent flags: `has_link: T`, `has_pull_requests: T`, `has_projects: T` → Rule `pull_requests_operation` → Action `delegate_operations`
3. Context: Initialized ✓, Hard Stale → Block mutation, offer refresh
4. If yes → Invoke `hiivmind-pulse-gh:gh-refresh`
5. After refresh → Continue

### Blocked Operation

**User:** `/gh delete repository`

**Flow:**
1. Arguments provided
2. Intent flags: `has_blocked: T` → Rule `blocked_operation` (highest priority)
3. Display safety block message
4. **Do not proceed**

### Help Request

**User:** `/gh --help`

**Flow:**
1. Arguments provided
2. Intent flags: `has_help_flag: T` → Rule `explicit_help_flag` (highest priority)
3. Display full help content from intent mapping actions

### Unlisted Domain (Fallback)

**User:** `/gh list codespaces`

**Flow:**
1. Arguments provided
2. Intent flags: `has_read: T` (no domain flag matches "codespaces")
3. Rule: `create_something` action-only fallback → Action `delegate_operations`
4. Operations skill handles unknown domain via corpus lookup
