---
name: hiivmind-pulse-gh-discover
version: 0.1.0
description: >
  Explore available GitHub operations before executing them. This skill should be used when:
  users want to know what operations are available, need help choosing an operation, or want
  to browse capabilities. Trigger phrases: "what can I do", "list operations", "show capabilities",
  "explore domains", "what GitHub operations", "help with GitHub", "discover features", "browse
  operations", "what domains are supported", "show me operations", "how do I use this", "feature
  list", "operation guide", "what's possible", "capabilities tour", "explore GitHub features",
  "what commands are available", "help me find an operation". Presents quick reference table
  and interactive domain exploration with handoff to operations skill.
---

# GitHub Operations Discovery

Explore what GitHub operations are available and find the right one for your task.

## Path Convention

`{PLUGIN_ROOT}` = Plugin root directory (where plugin.json lives)

When this skill references files like `{PLUGIN_ROOT}/lib/references/api-routing.md`,
read from the plugin root, not relative to this skill folder.

## Scope

| Does | Does NOT |
|------|----------|
| Present quick reference of all domains | Execute GitHub operations |
| Drill down into domain-specific operations | Modify config or workspace |
| Show CLI commands, REST endpoints, GraphQL | Require workspace initialization |
| Hand off to operations skill for execution | Make any API calls |

## Phase Overview

```
1. OVERVIEW  -> 2. NAVIGATE  -> 3. DETAIL  -> 4. HANDOFF
   (quick ref)    (domain)       (ops)        (execute)
      |             |             |             |
   Always        STOP for      STOP for      STOP for
   display       selection     drill-down    confirmation
```

---

## Phase 1: OVERVIEW

**Goal:** Present the quick reference table showing all available domains.

### What to Do

1. Read `{PLUGIN_ROOT}/lib/references/api-routing.md` (full file)
2. Extract and display the Quick Reference table
3. Present the legend (symbols)
4. Offer navigation options

### Output Format

```
=== GitHub Operations Quick Reference ===

Legend: ✓ = Supported | ✗ = Not available | ⊗ = Blocked for safety

| Domain             | gh CLI | REST | GraphQL | Notes                           |
|--------------------|--------|------|---------|----------------------------------|
| Issues             | ✓      | ✓    | ✓       | Full CRUD via all methods        |
| Pull Requests      | ✓      | ✓    | ✓       | Full CRUD via all methods        |
| Milestones         | ✗      | ✓    | Read    | CRUD via REST, assign via GQL    |
| Labels             | ✓      | ✓    | Add/rm  | CLI has full CRUD                |
| Projects v2        | ✓      | Read | ✓       | Views UI-only                    |
... [all 25 domains from api-routing.md]

Choose a domain to explore, or describe what you want to do:
  1. Issues
  2. Pull Requests
  3. Milestones
  ... [numbered list of all domains]

  Or type what you need (e.g., "I want to trigger a workflow")
```

### STOP Point

Wait for user selection:
- **Number selected** → Go to Phase 2 (NAVIGATE)
- **Natural language** → Parse intent, go to Phase 4 (HANDOFF) if clear, or Phase 2 if domain identified

---

## Phase 2: NAVIGATE

**Goal:** Map user selection to the appropriate domain file.

### Domain File Mapping

**See:** `skills/hiivmind-pulse-gh-discover/examples/examples.md`

| User Input | Domain File |
|------------|-------------|
| 1, "issues", "bug", "ticket" | `{PLUGIN_ROOT}/lib/references/domains/issues.md` |
| 2, "pr", "pull request", "merge" | `{PLUGIN_ROOT}/lib/references/domains/pull-requests.md` |
| 3, "milestone", "version" | `{PLUGIN_ROOT}/lib/references/domains/milestones.md` |
| 4, "label", "tag" | `{PLUGIN_ROOT}/lib/references/domains/labels.md` |
| 5, "project", "board", "kanban" | `{PLUGIN_ROOT}/lib/references/domains/projects-v2.md` |
| 6, "protect", "branch protection" | `{PLUGIN_ROOT}/lib/references/domains/branch-protection.md` |
| 7, "ruleset", "rules" | `{PLUGIN_ROOT}/lib/references/domains/rulesets.md` |
| 8, "action", "workflow", "ci" | `{PLUGIN_ROOT}/lib/references/domains/actions.md` |
| 9, "secret", "credential" | `{PLUGIN_ROOT}/lib/references/domains/secrets.md` |
| 10, "variable", "env" | `{PLUGIN_ROOT}/lib/references/domains/variables.md` |
| 11, "release", "publish" | `{PLUGIN_ROOT}/lib/references/domains/releases.md` |
| 12, "repo", "repository" | `{PLUGIN_ROOT}/lib/references/domains/repository.md` |
| 13, "gist" | `{PLUGIN_ROOT}/lib/references/domains/gists.md` |
| 14, "search", "find", "query" | `{PLUGIN_ROOT}/lib/references/domains/search.md` |
| 15, "collaborator", "contributor" | `{PLUGIN_ROOT}/lib/references/domains/collaborators.md` |
| 16, "team", "membership" | `{PLUGIN_ROOT}/lib/references/domains/teams.md` |
| 17, "webhook", "hook" | `{PLUGIN_ROOT}/lib/references/domains/webhooks.md` |
| 18, "check", "status check" | `{PLUGIN_ROOT}/lib/references/domains/checks.md` |
| 19, "deploy", "deployment" | `{PLUGIN_ROOT}/lib/references/domains/deployments.md` |
| 20, "environment" | `{PLUGIN_ROOT}/lib/references/domains/environments.md` |
| 21, "dependabot", "dependency" | `{PLUGIN_ROOT}/lib/references/domains/dependabot.md` |
| 22, "code scan", "security scan" | `{PLUGIN_ROOT}/lib/references/domains/code-scanning.md` |
| 23, "secret scan" | `{PLUGIN_ROOT}/lib/references/domains/secret-scanning.md` |
| 24, "notification" | `{PLUGIN_ROOT}/lib/references/domains/notifications.md` |
| 25, "reaction", "emoji" | `{PLUGIN_ROOT}/lib/references/domains/reactions.md` |

### What to Do

1. Parse user input (number or keywords)
2. Match to domain using table above
3. Load the corresponding domain file from `{PLUGIN_ROOT}/lib/references/domains/`

### STOP Point (Ambiguous)

If input doesn't clearly match a domain:

```
I'm not sure which domain you mean. Did you mean:
  1. Actions (workflows, runs, jobs)
  2. Secrets (encrypted variables)
  3. Variables (plain environment vars)

[Select number or clarify]
```

---

## Phase 3: DETAIL

**Goal:** Present detailed operation matrix for the selected domain.

### What to Do

1. Read the domain file (e.g., `{PLUGIN_ROOT}/lib/references/domains/issues.md`)
2. Present:
   - Support matrix table (Operations × 4 methods)
   - CLI command reference (most useful for users)
   - Key limitations or notes
3. Offer next actions

### Output Format

```
=== Issues Domain ===

All 4 methods (CLI, REST, GraphQL, Web UI) fully supported for core operations.

| Operation      | gh CLI | REST | GraphQL | Notes                    |
|----------------|--------|------|---------|--------------------------|
| List           | ✓      | ✓    | ✓       | All methods work         |
| Get            | ✓      | ✓    | ✓       |                          |
| Create         | ✓      | ✓    | ✓       |                          |
| Update         | ✓      | ✓    | ✓       |                          |
| Close          | ✓      | ✓    | ✓       |                          |
| Add comment    | ✓      | ✓    | ✓       |                          |
| Add labels     | ✓      | ✓    | ✓       | Separate endpoint in REST|
| Set milestone  | ✓      | ✓    | ✓       | Via PATCH in REST        |
| Lock           | ✗      | ✓    | ✗       | REST-only                |

## CLI Commands (Recommended)

| Operation   | Command                                   |
|-------------|-------------------------------------------|
| Create      | `gh issue create --title {title}`         |
| Close       | `gh issue close {number}`                 |
| Add comment | `gh issue comment {number} --body {body}` |
| Add labels  | `gh issue edit {number} --add-label {l}`  |

What would you like to do?
  1. Execute an issue operation now
  2. Explore another domain
  3. See REST/GraphQL details
  4. Done
```

### STOP Point

Wait for user choice:
- **Execute** → Go to Phase 4 (HANDOFF)
- **Explore another** → Go back to Phase 1 or 2
- **More details** → Show REST endpoints and GraphQL mutations
- **Done** → End skill

---

## Phase 4: HANDOFF

**Goal:** Transfer to operations skill with context.

### What to Do

1. Confirm the operation the user wants
2. Summarize domain and operation
3. Invoke operations skill

### STOP Point (Before Handoff)

```
You want to: Create an issue

I'll hand off to the operations skill now.

Invoke: hiivmind-pulse-gh:hiivmind-pulse-gh-operations

Context:
  - Domain: issues
  - Operation: create
  - Target: (you'll specify the details)

Proceed? [Yes / Go back / Cancel]
```

### Execute Handoff

If user confirms:

**Invoke:** `hiivmind-pulse-gh:hiivmind-pulse-gh-operations`

The operations skill will:
1. Check workspace initialization
2. Resolve IDs from cache
3. Route to correct API
4. Execute the operation

---

## Fast Path: Direct Task Description

If user describes a task directly in Phase 1 (instead of selecting a domain):

**Example:** "I want to trigger the CI workflow"

### What to Do

1. Parse intent:
   - Domain: `actions`
   - Operation: `trigger`
   - Target: `CI workflow`

2. If clear → Skip to Phase 4 (HANDOFF)

3. If ambiguous → Ask for clarification or show relevant domain

```
I understand you want to trigger a workflow.

Shall I hand off to the operations skill to execute this?
  1. Yes, trigger a workflow
  2. First, show me all Actions domain operations
  3. Cancel
```

---

## Quick Reference

### Related Skills

| Skill | Use For |
|-------|---------|
| **discover** (this) | Explore what's available |
| **operations** | Execute an operation |
| **awareness** | Add plugin info to CLAUDE.md |
| **init** | First-time workspace setup |
| **refresh** | Sync stale config |

### Invoking This Skill

Via gateway:
```
/hiivmind-pulse-gh what can I do
/hiivmind-pulse-gh explore operations
/hiivmind-pulse-gh help with GitHub
```

Direct:
```
Skill: hiivmind-pulse-gh:hiivmind-pulse-gh-discover
```

---

## Reference Files

| File | Purpose |
|------|---------|
| `{PLUGIN_ROOT}/lib/references/api-routing.md` | Quick reference table (Phase 1) |
| `{PLUGIN_ROOT}/lib/references/domains/*.md` | Domain operation matrices (Phase 3) |
| `skills/hiivmind-pulse-gh-discover/examples/examples.md` | Domain mapping table |
