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

**If `$ARGUMENTS` is provided** → Continue to Step 2

---

## Step 2: Context Detection

### 2a: Check Initialization

**See:** `lib/github/patterns/config-parsing.md`

Check for `.hiivmind/github/config.yaml`:

**If not found:**
1. Inform user: "This workspace hasn't been initialized for GitHub operations."
2. Ask: "Would you like to initialize now?"
3. If yes → Invoke skill: `hiivmind-pulse-gh:hiivmind-pulse-gh-init`
4. After init completes → Return and continue

### 2b: Check Freshness

**See:** `lib/github/patterns/config-parsing.md` (freshness section)

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
3. If yes → Invoke skill: `hiivmind-pulse-gh:hiivmind-pulse-gh-refresh`
4. After refresh → Continue

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
| pr, pull request, merge, review | `pull_requests` |
| milestone, version, due date | `milestones` |
| label, tag, categorize | `labels` |
| project, board, kanban, status, field | `projects` |
| protect, protection, branch rule | `branch_protection` |
| ruleset, rules, enforcement | `rulesets` |
| workflow, action, run, trigger, ci | `actions` |
| secret, credential, encrypted | `secrets` |
| variable, env, config | `variables` |
| release, publish, asset, changelog | `releases` |
| adr, architecture decision, document decision, decision record, design decision | `adr` |

### Operation Detection

| Keywords | Operation |
|----------|-----------|
| create, add, new, open, make | `create` |
| update, edit, change, modify, set | `update` |
| list, show, get, view, check | `read` |
| delete, remove, close, archive | `delete` |
| link, connect, attach, add to | `link` |
| trigger, run, start, dispatch | `trigger` |
| merge, squash, rebase | `merge` |
| document, record, capture, why | `document` |

### Target Extraction

Look for:
- Issue/PR numbers: `#42`, `issue 42`, `PR #15`
- Milestone names: `"v2.0"`, `milestone v2.0`
- Project numbers: `project 2`, `project #1`
- Branch names: `main`, `develop`
- Workflow names: `ci.yml`, `deploy.yml`

### Ambiguity Resolution

If intent is unclear, use AskUserQuestion to clarify.

---

## Step 4: Confirm Mutations

For create/update/delete operations:

1. Summarize the intended action
2. Ask: "Proceed with this operation?"
3. If no → Abort gracefully

---

## Step 5: Route to Appropriate Skill

After detecting intent, route based on domain:

### ADR Domain

**If domain is `adr`:**

**Invoke:** `hiivmind-pulse-gh:hiivmind-pulse-gh-adr`

**Pass context:**
- Operation: {create, list, update, sync}
- Topic: {extracted from request}
- Milestone: {if mentioned}

The ADR skill handles architecture decision records with file + GitHub issue integration.

### All Other Domains

**Invoke:** `hiivmind-pulse-gh:hiivmind-pulse-gh-operations`

**Pass context:**
- Domain: {detected domain}
- Operation: {detected operation}
- Target: {extracted target}
- Workspace: owner/type from config

The operations skill consults the routing guide and corpus (when needed) to perform the operation.

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

**Documentation**
14. Create Architecture Decision Record (ADR)
15. List existing ADRs

**Maintenance**
16. Refresh workspace config
17. View current configuration
```

After selection, gather details and route to operations skill.

---

## Error Handling

**See:** `lib/github/patterns/error-handling.md`

| Error | Cause | Action |
|-------|-------|--------|
| Config not found | Not initialized | Offer to run init |
| Config stale | Threshold exceeded | Offer to refresh |
| Permission denied | Insufficient access | Check `gh auth status` |
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

### Not Initialized

**User:** `/hiivmind-pulse-gh create issue for bug`

**Flow:**
1. Context: NOT initialized
2. Ask: "Initialize workspace first?"
3. If yes → Invoke `hiivmind-pulse-gh:hiivmind-pulse-gh-init`
4. After init → Resume with original request

### Stale Config

**User:** `/hiivmind-pulse-gh add PR to project`

**Flow:**
1. Context: Initialized ✓, Hard Stale
2. Block mutation, offer refresh
3. If yes → Invoke `hiivmind-pulse-gh:hiivmind-pulse-gh-refresh`
4. After refresh → Continue with intent detection

### ADR Creation

**User:** `/hiivmind-pulse-gh document decision about using GraphQL`

**Flow:**
1. Context: Initialized ✓, Fresh ✓
2. Intent: domain=adr, operation=document, topic="using GraphQL"
3. Route to ADR skill
4. Skill guides through ADR creation with STOP points
5. Creates file `doc/adr/NNNN-using-graphql.md`
6. Creates GitHub issue with `adr` label
7. Links to milestone if specified
