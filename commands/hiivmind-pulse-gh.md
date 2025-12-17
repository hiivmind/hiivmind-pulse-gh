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

## Step 2: Intent Detection

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
| repo, repository, fork, clone | `repositories` |
| collaborator, contributor, invite | `collaborators` |
| team, membership | `teams` |
| check, check run, status check | `checks` |
| deploy, deployment | `deployments` |
| scan, alert, security, vulnerability | `security` |
| dependabot, dependency | `dependabot` |
| search, find, query | `search` |
| gist | `gists` |
| adr, architecture decision, document decision, decision record, design decision | `adr` |
| awareness, configure claude, setup claude, enable features, what can, capabilities, tour | `awareness` |

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

### Blocked Operations

Before proceeding, check if the request matches a blocked operation:

| Domain | Operation | Blocked |
|--------|-----------|---------|
| repositories | delete, transfer, archive | ✅ BLOCKED |
| organizations | delete, remove all members | ✅ BLOCKED |
| branches | delete default | ✅ BLOCKED |

**If blocked:**
1. Explain: "This operation is blocked for safety: [reason]"
2. Offer alternative if available (e.g., "Use archive instead of delete")
3. Suggest: "For this operation, please use the GitHub web UI"
4. **Do not proceed** to Step 3

**Reference:** `reference/operation-blocklist.md`

### Unlisted Domains

If the domain is not in the table above:
1. Set domain to the detected resource name (e.g., `codespaces`, `pages`)
2. Continue to operations skill
3. Operations skill will use corpus lookup for syntax

### Ambiguity Resolution

If intent is still unclear after domain/operation detection, use AskUserQuestion to clarify.

---

## Step 3: Context Detection (Conditional)

**Skip this step if domain is:** `adr`, `awareness`, `search`, `gists`

These domains either handle their own context checks internally or don't require workspace initialization.

**For all other domains, continue below:**

### 3a: Check Initialization

**See:** `lib/github/patterns/config-parsing.md`

Check for `.hiivmind/github/config.yaml`:

**If not found:**
1. Inform user: "This workspace hasn't been initialized for GitHub operations."
2. Ask: "Would you like to initialize now?"
3. If yes → Invoke skill: `hiivmind-pulse-gh:hiivmind-pulse-gh-init`
4. After init completes → Return and continue

### 3b: Check Freshness

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

### Awareness Domain

**If domain is `awareness`:**

**Invoke:** `hiivmind-pulse-gh:hiivmind-pulse-gh-awareness`

The awareness skill auto-detects capabilities from project context and guides through CLAUDE.md configuration.

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

When invoked without arguments, use AskUserQuestion for hierarchical navigation.

### Menu Step 1: Category Selection

Use AskUserQuestion:

```
question: "What type of GitHub operation?"
header: "Category"
options:
  - label: "Issues & PRs"
    description: "Create, update, close issues and pull requests"
  - label: "Projects & Milestones"
    description: "Project boards, fields, status, milestones"
  - label: "CI/CD & Releases"
    description: "Workflows, actions, releases, deployments"
  - label: "More options..."
    description: "Repository config, security, search, documentation"
```

### Menu Step 2: Action Selection

Based on category selected, present specific actions:

**If "Issues & PRs":**
```
question: "What would you like to do?"
header: "Action"
options:
  - label: "Create an issue"
    description: "Open a new issue with title and body"
  - label: "Update or close an issue"
    description: "Modify, comment on, or close an existing issue"
  - label: "Create a pull request"
    description: "Open a new PR from a branch"
  - label: "Merge a pull request"
    description: "Merge, squash, or rebase a PR"
```

**If "Projects & Milestones":**
```
question: "What would you like to do?"
header: "Action"
options:
  - label: "Add item to project"
    description: "Add issue or PR to a project board"
  - label: "Update project field"
    description: "Change status, priority, or custom fields"
  - label: "Manage milestones"
    description: "Create, update, or assign milestones"
  - label: "View project items"
    description: "List items in a project board"
```

**If "CI/CD & Releases":**
```
question: "What would you like to do?"
header: "Action"
options:
  - label: "Trigger a workflow"
    description: "Dispatch a GitHub Actions workflow"
  - label: "View workflow runs"
    description: "Check status of recent runs"
  - label: "Create a release"
    description: "Publish a new release with assets"
  - label: "View checks & deployments"
    description: "Check run status, deployment history"
```

**If "More options...":**
```
question: "Select a category:"
header: "Category"
options:
  - label: "Repository config"
    description: "Branch protection, rulesets, collaborators"
  - label: "Security & compliance"
    description: "Alerts, Dependabot, vulnerability scanning"
  - label: "Search & discovery"
    description: "Search issues/PRs/code, manage gists"
  - label: "Documentation & maintenance"
    description: "ADRs, refresh config, CLAUDE.md awareness"
```

### Menu Step 2b: Expanded Categories

**If "Repository config":**
```
options:
  - label: "Branch protection"
  - label: "Configure rulesets"
  - label: "Manage collaborators"
  - label: "Repository settings"
```

**If "Security & compliance":**
```
options:
  - label: "View security alerts"
  - label: "Manage Dependabot"
  - label: "Code scanning settings"
  - label: "Secret scanning"
```

**If "Search & discovery":**
```
options:
  - label: "Search issues & PRs"
  - label: "Search code"
  - label: "Create a gist"
  - label: "Manage gists"
```

**If "Documentation & maintenance":**
```
options:
  - label: "Create ADR"
    description: "Architecture Decision Record"
  - label: "List existing ADRs"
  - label: "Refresh workspace config"
  - label: "Configure CLAUDE.md awareness"
```

### Menu Step 3: Execute

After action selection:
1. Map selection to domain + operation
2. Continue to **Step 3: Context Detection**
3. Route to appropriate skill

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
1. Arguments provided
2. Intent: domain=issues, operation=create, target="login timeout bug"
3. Context: Initialized ✓, Fresh ✓
4. Confirm: "Create issue titled 'login timeout bug'?"
5. Route to operations skill

### Not Initialized

**User:** `/hiivmind-pulse-gh create issue for bug`

**Flow:**
1. Arguments provided
2. Intent: domain=issues, operation=create
3. Context: NOT initialized → Ask "Initialize workspace first?"
4. If yes → Invoke `hiivmind-pulse-gh:hiivmind-pulse-gh-init`
5. After init → Resume with original request

### Stale Config

**User:** `/hiivmind-pulse-gh add PR to project`

**Flow:**
1. Arguments provided
2. Intent: domain=projects, operation=link
3. Context: Initialized ✓, Hard Stale → Block mutation, offer refresh
4. If yes → Invoke `hiivmind-pulse-gh:hiivmind-pulse-gh-refresh`
5. After refresh → Continue

### ADR Creation

**User:** `/hiivmind-pulse-gh document decision about using GraphQL`

**Flow:**
1. Arguments provided
2. Intent: domain=adr, operation=document, topic="using GraphQL"
3. Context: SKIPPED (ADR doesn't require workspace config)
4. Route to ADR skill
5. Skill guides through ADR creation with STOP points

### Capability Awareness

**User:** `/hiivmind-pulse-gh configure Claude for GitHub`

**Flow:**
1. Arguments provided
2. Intent: domain=awareness
3. Context: SKIPPED (awareness doesn't require workspace config)
4. Route to awareness skill
5. Skill scans project and edits CLAUDE.md

### Unlisted Domain (Fallback)

**User:** `/hiivmind-pulse-gh list codespaces`

**Flow:**
1. Arguments provided
2. Intent: domain=codespaces (not in table), operation=read
3. Context: Initialized ✓
4. Route to operations skill with corpus fallback
5. Operations skill looks up codespaces API in corpus
