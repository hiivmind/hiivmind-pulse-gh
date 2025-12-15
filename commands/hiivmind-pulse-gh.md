---
description: Unified entry point for GitHub operations - describe what you need in natural language
argument-hint: Describe your goal (e.g., "create issue for login bug", "set milestone v2.0 on #42", "add PR to project")
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep", "TodoWrite", "AskUserQuestion", "Skill", "Task"]
---

# GitHub Operations Gateway

Unified entry point for all GitHub operations via hiivmind-pulse-gh.

**User request:** $ARGUMENTS

---

## Step 1: Check for Arguments

**If `$ARGUMENTS` is empty** → Go to **Mode: Interactive Menu**

**If `$ARGUMENTS` is provided** → Continue to Step 2: Context Detection

---

## Step 2: Context Detection

### 2a: Check Initialization

```bash
CONFIG=".hiivmind/github/config.yaml"
USER_CONFIG=".hiivmind/github/user.yaml"

if [[ -f "$CONFIG" ]]; then
  echo "INITIALIZED=true"
  OWNER=$(yq '.workspace.login' "$CONFIG")
  WORKSPACE_TYPE=$(yq '.workspace.type' "$CONFIG")
  echo "OWNER=$OWNER"
  echo "WORKSPACE_TYPE=$WORKSPACE_TYPE"
else
  echo "INITIALIZED=false"
fi
```

**If not initialized:**
1. Inform user: "This workspace hasn't been initialized for GitHub operations."
2. Ask: "Would you like to initialize now? This will discover projects and cache field IDs."
3. If yes → Load `hiivmind-pulse-gh-init` skill
4. After init completes → Return here and continue

### 2b: Check Freshness

**Phase 1+:** Per-section freshness checking based on operation domain.

```bash
CONFIG=".hiivmind/github/config.yaml"
FRESHNESS=".hiivmind/github/freshness.yaml"

# Determine required section based on intent (Step 3)
# For now, check if freshness.yaml exists
if [[ -f "$FRESHNESS" ]]; then
  echo "FRESHNESS_TRACKING=enabled"

  # Map operation domain to required section
  # This will be filled in during Step 3 (Intent Detection)
  # For now, just check if any sections are stale
  STALE_SECTIONS=$(yq '.sections | to_entries | .[] | select(.value.stale == true) | .key' "$FRESHNESS" 2>/dev/null)

  if [[ -n "$STALE_SECTIONS" ]]; then
    echo "STALE_SECTIONS=$STALE_SECTIONS"
  else
    echo "ALL_SECTIONS_FRESH=true"
  fi
else
  echo "FRESHNESS_TRACKING=disabled"

  # Fallback to legacy freshness check
  USER_CONFIG=".hiivmind/github/user.yaml"
  THRESHOLD_DAYS=$(yq '.preferences.freshness_threshold_days // 7' "$USER_CONFIG" 2>/dev/null || echo 7)
  LAST_SYNC=$(yq '.cache.last_synced_at' "$CONFIG")

  # Calculate age in days
  # Note: Using positive-first logic to avoid != escaping bug in Claude Code Bash tool
  if [[ "$LAST_SYNC" = "null" ]] || [[ -z "$LAST_SYNC" ]]; then
    echo "STALE=unknown"
  else
    LAST_SYNC_EPOCH=$(date -d "$LAST_SYNC" +%s 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    AGE_DAYS=$(( (NOW_EPOCH - LAST_SYNC_EPOCH) / 86400 ))

    if [[ $AGE_DAYS -gt $THRESHOLD_DAYS ]]; then
      echo "STALE=true"
      echo "AGE_DAYS=$AGE_DAYS"
    else
      echo "STALE=false"
    fi
  fi
fi
```

**If using per-section freshness (Phase 1+):**
- After Step 3 (Intent Detection), map domain to required section
- Check if that specific section is stale
- If stale, offer targeted refresh: "Would you like to refresh [section]?"

**If using legacy freshness:**
1. Inform user: "Your workspace config is $AGE_DAYS days old (threshold: $THRESHOLD_DAYS days)."
2. Ask: "Would you like to refresh before proceeding?"
3. If yes → Load `hiivmind-pulse-gh-refresh` skill
4. After refresh → Continue to Step 3

**Domain to Section Mapping (Phase 7):**

| Domain | Required Section(s) | Rationale |
|--------|---------------------|-----------|
| issues | workspace, projects | Basic issue ops need project IDs if adding to project |
| pull_requests | workspace, repositories, repo_settings, teams | PR ops need repo settings (merge methods, protection) and teams (reviewers) |
| milestones | workspace, repositories | Milestone ops need repo catalog |
| labels | workspace, repositories, repo_settings | Label ops need repo catalog and existing labels |
| projects | workspace, projects, views, automations | Project ops need field IDs, view configs, automation awareness |
| branch_protection | workspace, repositories, repo_settings | Protection ops need repo settings for current rules |
| rulesets | workspace, repositories, repo_settings | Ruleset ops need repo settings for current rules |
| actions | workspace, repositories | Workflow ops need repo catalog |
| secrets | workspace, repositories | Secret ops need repo catalog |
| variables | workspace, repositories | Variable ops need repo catalog |
| releases | workspace, repositories, relationships | Release ops may involve cross-repo coordination |
| reviewers | workspace, teams | Reviewer suggestions need team membership |
| cross_repo | workspace, relationships | Cross-repo ops need dependency mapping |

### Per-Section Staleness Checking (Phase 7)

After Step 3 (Intent Detection), check staleness of required sections:

```bash
# Function to check section staleness
check_section_staleness() {
  local section=$1
  local freshness_file=".hiivmind/github/freshness.yaml"

  if [[ ! -f "$freshness_file" ]]; then
    echo "fresh"  # No tracking = assume fresh
    return 0
  fi

  local last_checked=$(yq ".sections.$section.last_checked" "$freshness_file")
  local threshold_hours=$(yq ".sections.$section.threshold_hours" "$freshness_file")

  if [[ "$last_checked" = "null" ]] || [[ -z "$last_checked" ]]; then
    echo "never_checked"
    return 2  # Never checked = stale
  fi

  local last_epoch=$(date -d "$last_checked" +%s 2>/dev/null || echo 0)
  local now_epoch=$(date +%s)
  local age_hours=$(( (now_epoch - last_epoch) / 3600 ))

  # Soft staleness: between threshold and 2x threshold
  if [[ $age_hours -gt $threshold_hours ]] && [[ $age_hours -lt $((threshold_hours * 2)) ]]; then
    echo "soft_stale"
    return 1
  fi

  # Hard staleness: >= 2x threshold
  if [[ $age_hours -ge $((threshold_hours * 2)) ]]; then
    echo "hard_stale"
    return 2
  fi

  echo "fresh"
  return 0
}

# Example: Check required sections for a domain
DOMAIN="pull_requests"
REQUIRED_SECTIONS="workspace repositories repo_settings teams"

SOFT_STALE=()
HARD_STALE=()

for section in $REQUIRED_SECTIONS; do
  STALENESS=$(check_section_staleness "$section")
  case "$STALENESS" in
    "soft_stale")
      SOFT_STALE+=("$section")
      ;;
    "hard_stale"|"never_checked")
      HARD_STALE+=("$section")
      ;;
  esac
done

# Handle staleness
if [[ ${#HARD_STALE[@]} -gt 0 ]]; then
  # BLOCK mutations if hard stale
  if [[ "$OPERATION" == "create" ]] || [[ "$OPERATION" == "update" ]] || [[ "$OPERATION" == "delete" ]]; then
    echo "ERROR: Cannot perform mutation - required sections are critically stale:"
    printf '  - %s\n' "${HARD_STALE[@]}"
    echo ""
    echo "Please refresh these sections before proceeding:"
    echo "  /hiivmind-pulse-gh-refresh [section-name]"
    exit 1
  else
    # Warn but allow reads
    echo "WARNING: Some required sections are critically stale:"
    printf '  - %s\n' "${HARD_STALE[@]}"
    echo ""
    echo "Results may be inaccurate. Consider refreshing."
  fi
elif [[ ${#SOFT_STALE[@]} -gt 0 ]]; then
  # Warn about soft staleness
  echo "NOTE: Some sections are getting stale:"
  printf '  - %s\n' "${SOFT_STALE[@]}"
  echo ""
  echo "Consider refreshing soon for best results."
fi
```

**Staleness Policy:**

| Staleness Level | Age | Read Ops | Mutation Ops |
|-----------------|-----|----------|--------------|
| Fresh | < threshold | ✅ Allow | ✅ Allow |
| Soft Stale | threshold to 2x | ✅ Allow + warn | ✅ Allow + warn |
| Hard Stale | >= 2x threshold | ✅ Allow + warn | ❌ Block + require refresh |
| Never Checked | null | ✅ Allow + warn | ❌ Block + require refresh |

### 2c: Update Freshness Check Timestamp

After checking freshness (whether refresh was performed or not):

```bash
CONFIG=".hiivmind/github/config.yaml"

# Update last_freshness_check in config (legacy)
yq -i '.cache.last_freshness_check = "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"' "$CONFIG"

# If using per-section tracking, staleness flags are updated automatically during checks
```

---

## Step 3: Intent Detection

Analyze the user's request to determine:

1. **Domain** - Which GitHub entity
2. **Operation** - What action to perform
3. **Target** - Specific entity (if any)

### Domain Detection

| Keywords | Domain |
|----------|--------|
| issue, bug, feature, task, ticket | `issues` |
| pr, pull request, pull-request, merge, review | `pull_requests` |
| milestone, release planning, due date, version | `milestones` |
| label, tag, categorize | `labels` |
| project, board, kanban, status, field, column | `projects` |
| protect, protection, branch rule, require review | `branch_protection` |
| ruleset, rules, enforcement | `rulesets` |
| workflow, action, run, trigger, dispatch, ci, cd | `actions` |
| secret, credential, encrypted | `secrets` |
| variable, env, environment variable, config | `variables` |
| release, publish, asset, changelog | `releases` |

### Operation Detection

| Keywords | Operation |
|----------|-----------|
| create, add, new, open, make | `create` |
| update, edit, change, modify, set, assign | `update` |
| list, show, get, view, check, query, find | `read` |
| delete, remove, close, archive | `delete` |
| link, connect, attach, add to | `link` |
| trigger, run, start, dispatch | `trigger` |
| merge, squash, rebase | `merge` |

### Target Extraction

Look for:
- Issue/PR numbers: `#42`, `issue 42`, `PR #15`
- Milestone names: `"v2.0"`, `milestone v2.0`
- Project numbers: `project 2`, `project #1`
- Branch names: `main`, `develop`, `feature/...`
- Workflow names: `ci.yml`, `deploy.yml`
- Repository names: `owner/repo`

### Compound Intent Detection

Some requests imply multiple operations:

| Request Pattern | Operations |
|-----------------|------------|
| "create issue and add to project" | create (issues) → link (projects) |
| "close issue and set milestone" | update (issues) → update (milestones) |
| "merge PR and create release" | merge (pull_requests) → create (releases) |

For compound intents, use TodoWrite to track the sequence.

### Ambiguity Resolution

If intent is unclear, use AskUserQuestion:

```
I understand you want to work with [domain], but I need clarification:

1. **[Option A]** - [description]
2. **[Option B]** - [description]
3. **Something else** - Please describe
```

---

## Step 4: Check Mutation Confirmation

For create/update/delete operations:

```bash
CONFIRM=$(yq '.preferences.confirm_mutations // true' "$USER_CONFIG" 2>/dev/null || echo true)
```

**If `confirm_mutations: true` and operation is a mutation:**
1. Summarize the intended action
2. Ask: "Proceed with this operation?"
3. If no → Abort gracefully

---

## Step 5: Route to Operations Skill

After detecting intent, route to the operations skill:

```markdown
Loading hiivmind-pulse-gh-operations skill...

**Context:**
- Domain: {detected domain}
- Operation: {detected operation}
- Target: {extracted target}
- Workspace: {OWNER} ({WORKSPACE_TYPE})
- Config: {CONFIG path}
```

Pass the detected intent to the skill for execution.

---

## Mode: Interactive Menu (No Arguments)

When invoked without arguments, present options:

```
What would you like to do with GitHub?

**Issue & PR Management**
1. Create an issue
2. Update or close an issue
3. Create a pull request
4. Merge a pull request

**Project Management**
5. Add item to project board
6. Update project field/status
7. View project items

**Repository Configuration**
8. Manage milestones
9. Set up branch protection
10. Configure rulesets

**CI/CD & Releases**
11. Trigger a workflow
12. View workflow runs
13. Create a release

**Maintenance**
14. Refresh workspace config
15. View current configuration
```

After selection, gather details and route to operations skill.

---

## Domain-Specific Clarifications

### Issues

If domain is `issues`, may need to clarify:
- Which repository? (if multiple in config)
- Labels to apply?
- Assignees?
- Add to project?

### Projects

If domain is `projects`, may need to clarify:
- Which project? (if multiple in config)
- Which field to update?
- Which status/value?

### Milestones

If domain is `milestones`, may need to clarify:
- Create new or update existing?
- Due date?
- Which issues to assign?

### Branch Protection

If domain is `branch_protection`, clarify:
- Legacy branch protection or modern rulesets?
- Which branch pattern?
- What rules to enforce?

---

## Error Handling

| Error | Cause | Action |
|-------|-------|--------|
| Config not found | Not initialized | Offer to run init |
| Config stale | Threshold exceeded | Offer to refresh |
| Permission denied | Insufficient GitHub access | Check `gh auth status` |
| Ambiguous intent | Multiple interpretations | Use AskUserQuestion |
| Unknown domain | Request not recognized | Show interactive menu |

---

## Example Sessions

### Simple Issue Creation

**User:** `/hiivmind-pulse-gh create issue for login timeout bug`

**Flow:**
1. Context: Initialized ✓, Fresh ✓
2. Intent: domain=issues, operation=create, target="login timeout bug"
3. Confirm: "Create issue titled 'login timeout bug'?"
4. Route to operations skill

### Milestone Assignment

**User:** `/hiivmind-pulse-gh set milestone v2.0 on issue #42`

**Flow:**
1. Context: Initialized ✓, Fresh ✓
2. Intent: domain=milestones, operation=update (assign), target=issue #42, milestone="v2.0"
3. Confirm: "Assign milestone 'v2.0' to issue #42?"
4. Route to operations skill

### Compound Operation

**User:** `/hiivmind-pulse-gh create issue for auth bug and add to project`

**Flow:**
1. Context: Initialized ✓, Fresh ✓
2. Intent: Compound - create issue, then link to project
3. TodoWrite: Track both operations
4. Route to operations skill with sequence

### Not Initialized

**User:** `/hiivmind-pulse-gh create issue for bug`

**Flow:**
1. Context: NOT initialized
2. Ask: "Initialize workspace first?"
3. If yes → Load init skill
4. After init → Resume with original request

### Stale Config

**User:** `/hiivmind-pulse-gh add PR to project`

**Flow:**
1. Context: Initialized ✓, Stale (15 days old)
2. Ask: "Config is 15 days old. Refresh first?"
3. If yes → Load refresh skill
4. After refresh → Continue with intent detection

---

## Notes

- **Natural language first**: Describe your goal, the command routes automatically
- **Context-aware**: Checks initialization and freshness before operations
- **Confirmation by default**: Mutations require confirmation (configurable)
- **Skill-based execution**: Routes to `hiivmind-pulse-gh-operations` for all GitHub operations
- **Compound support**: Multi-step operations tracked via TodoWrite
