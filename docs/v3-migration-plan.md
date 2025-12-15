# Architecture v3 Migration Plan

> **Goal:** Implement lean context engineering - one skill to initialize, reference docs for routing, corpus for specifics.

## Current State Assessment

### What's Done ✅

| Component | Status | Location |
|-----------|--------|----------|
| Specialized corpus | Complete | `.claude-plugin/skills/hiivmind-corpus-github/` |
| API routing guide | Complete | `reference/api-routing.md` |
| CLAUDE.md corpus section | Complete | Updated to reference embedded corpus |
| Workflow examples (partial) | 2 of 5 | `reference/workflows/` |

### What Remains

| Component | Status | Work Required |
|-----------|--------|---------------|
| Consolidated init skill | Not started | Merge user-init + workspace-init |
| Config schema reference | Not started | Document config.yaml usage |
| Workflow examples | Partial | Add 3 more examples |
| CLAUDE.md overhaul | Not started | Remove function-centric guidance |
| Function library demotion | Not started | Add README, remove as runtime deps |
| Old skills archival | Not started | Archive 5 domain skills |
| Plugin manifest update | Not started | Reflect new skill structure |

---

## Migration Phases

### Phase 1: Complete Reference Structure

**Objective:** Finish the reference documentation layer.

#### 1.1 Create `reference/config-schema.md`

Document how to read and use `.hiivmind/github/config.yaml`:

```markdown
# Config Schema Reference

## Loading Context

Before any GitHub operation, load workspace context:

\`\`\`bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
TYPE=$(yq '.workspace.type' "$CONFIG")
\`\`\`

## Schema

### workspace
- `.workspace.login` - GitHub username or org name
- `.workspace.type` - "user" or "organization"
- `.workspace.id` - GraphQL node ID

### projects
- `.projects.default` - Default project number
- `.projects.catalog[].number` - Project number
- `.projects.catalog[].id` - Project GraphQL ID
- `.projects.catalog[].fields.{Name}.id` - Field ID
- `.projects.catalog[].fields.{Name}.options.{Value}` - Option ID

### repositories
- `.repositories[].name` - Repo name
- `.repositories[].id` - Repo GraphQL ID
- `.repositories[].default_branch` - Default branch name

## Common Lookups

| Need | yq Command |
|------|------------|
| Owner | `yq '.workspace.login' "$CONFIG"` |
| Project ID | `yq '.projects.catalog[] | select(.number == N) | .id' "$CONFIG"` |
| Status field ID | `yq '.projects.catalog[0].fields.Status.id' "$CONFIG"` |
| Status option ID | `yq '.projects.catalog[0].fields.Status.options["In Progress"]' "$CONFIG"` |
```

#### 1.2 Complete Workflow Examples

Add 3 more workflow examples to `reference/workflows/`:

| File | Content |
|------|---------|
| `setup-branch-protection.md` | REST API flow for branch rules + rulesets |
| `project-status-update.md` | GraphQL flow for Projects v2 status updates |
| `bulk-operations.md` | Patterns for batch operations with loops |

**Template for each workflow:**
```markdown
# Workflow: {Title}

## Goal
{What this achieves}

## Prerequisites
- Config loaded from `.hiivmind/github/config.yaml`
- {Other requirements}

## Steps

### 1. {First step}
\`\`\`bash
# Load context
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
\`\`\`

### 2. {Second step}
\`\`\`bash
# API call using gh
gh api ...
\`\`\`

## Error Handling
{Common errors and solutions}

## Corpus References
- Routing: `reference/api-routing.md` → {section}
- Docs: `.claude-plugin/skills/hiivmind-corpus-github/data/sections/{section}.md`
```

---

### Phase 2: Consolidate Init Skills

**Objective:** Merge `user-init` + `workspace-init` into single `hiivmind-pulse-gh-init`.

#### 2.1 Create Consolidated Init Skill

**New location:** `skills/hiivmind-pulse-gh-init/SKILL.md`

**Combines:**
- All prerequisite checks (gh, jq, yq)
- Authentication validation
- Scope checking
- Workspace detection from git remote
- Project discovery
- Config generation
- User identity persistence

**Key design decisions:**
- Single entry point: `Run hiivmind-pulse-gh-init when starting work on a new repo`
- Interactive: Uses AskUserQuestion for project/repo selection
- Idempotent: Skips steps if already complete, offers refresh option

**SKILL.md structure:**
```markdown
---
name: hiivmind-pulse-gh-init
description: >
  Initialize GitHub workspace: verify CLI tools, authenticate, discover projects,
  and cache IDs to config.yaml. Run once per repository. This is the ONLY
  prerequisite for GitHub operations - after init, use gh CLI directly with
  routing guide and corpus for specifics.
---

# GitHub Workspace Initialization

## What This Does

1. Verifies gh CLI, jq, yq installed
2. Validates GitHub authentication and scopes
3. Detects workspace from git remote
4. Discovers projects and fields
5. Creates `.hiivmind/github/config.yaml`
6. Creates `.hiivmind/github/user.yaml`

## After Initialization

Once initialized, you DON'T need specialized skills. Instead:

1. **Load context:** `OWNER=$(yq '.workspace.login' .hiivmind/github/config.yaml)`
2. **Check routing:** Read `reference/api-routing.md` for which API
3. **Get syntax:** Use `github-navigate` skill for exact commands
4. **Execute:** Use `gh api` or `gh` commands directly

## Refreshing

If your config becomes stale (new projects, changed fields):
\`\`\`bash
# Re-run init to refresh
# Or use hiivmind-pulse-gh-refresh for targeted updates
\`\`\`
```

#### 2.2 Update Refresh Skill

Simplify `hiivmind-pulse-gh-workspace-refresh` → `hiivmind-pulse-gh-refresh`:
- Focus purely on syncing config with current GitHub state
- Remove references to other skills
- Lightweight, targeted updates

---

### Phase 3: Overhaul CLAUDE.md

**Objective:** Rewrite CLAUDE.md for v3 architecture flow.

#### 3.1 Sections to Remove/Relocate

| Section | Action |
|---------|--------|
| "Skills" (7 skill hierarchy) | Replace with 2-skill model |
| "Quick Start" (source functions) | Remove |
| "Key Function Groups" | Move to `lib/github/README.md` |
| "When to Use Function Libraries" | Remove |
| "Pipeline Pattern" | Move to `lib/github/README.md` |

#### 3.2 New CLAUDE.md Structure

```markdown
# CLAUDE.md

## System Overview
{Keep - describes what the plugin does}

## Getting Started

### First Time Setup
Run `hiivmind-pulse-gh-init` to initialize your workspace.

### After Initialization
1. Load context from `.hiivmind/github/config.yaml`
2. Check `reference/api-routing.md` for which API to use
3. Search corpus using keywords for exact syntax
4. Execute with `gh api` or `gh` commands

## Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `hiivmind-pulse-gh-init` | Initialize workspace | First time setup |
| `hiivmind-pulse-gh-refresh` | Sync config | When config is stale |

## Reference Documentation

| Document | Purpose |
|----------|---------|
| `reference/api-routing.md` | Which API for which operation |
| `reference/config-schema.md` | How to read config.yaml |
| `reference/workflows/` | Multi-shot examples |

## GitHub Documentation Corpus (Embedded)
{Keep existing section}

## Function Libraries (Reference Only)
The `lib/github/` directory contains bash function implementations
for reference. These are NOT required for operations - use `gh` directly
with routing guide and corpus. See `lib/github/README.md` for details.
```

---

### Phase 4: Demote Function Libraries

**Objective:** Keep functions for reference but make clear they're not runtime dependencies.

#### 4.1 Create `lib/github/README.md`

```markdown
# GitHub Function Libraries (Reference Only)

These bash functions are **reference implementations** showing how to
interact with GitHub APIs. They are NOT required for Claude Code operations.

## Recommended Approach (v3)

Instead of sourcing these functions, use:

1. **Routing guide:** `reference/api-routing.md` - which API for what
2. **Corpus:** `github-navigate` skill - exact syntax and endpoints
3. **Direct execution:** `gh api` or `gh` commands

## Why These Exist

- Historical: Originally the primary interface
- Reference: Show correct patterns for complex operations
- Debugging: Useful for understanding API behavior

## If You Need Them

For complex multi-step operations, you CAN still source:
\`\`\`bash
source lib/github/gh-project-functions.sh
\`\`\`

But prefer composing `gh` commands directly using the corpus.

## Function Index

{Table of files and their purpose - for reference only}
```

#### 4.2 Update Index Files

Each `lib/github/*-index.md` file should add a deprecation note:
```markdown
> **Note:** These functions are reference implementations. For v3 architecture,
> use `reference/api-routing.md` + corpus instead of sourcing functions.
```

---

### Phase 5: Archive Old Skills

**Objective:** Remove domain-specific skills that are replaced by routing + corpus.

#### 5.1 Skills to Archive

| Skill | Reason for Removal |
|-------|-------------------|
| `hiivmind-pulse-gh-projects` | LLM composes GraphQL with routing + corpus |
| `hiivmind-pulse-gh-milestones` | LLM uses REST API with routing + corpus |
| `hiivmind-pulse-gh-branch-protection` | LLM uses REST/GraphQL with routing + corpus |
| `hiivmind-pulse-gh-investigate` | LLM queries directly with cached IDs |
| `hiivmind-pulse-gh-user-init` | Merged into `hiivmind-pulse-gh-init` |
| `hiivmind-pulse-gh-workspace-init` | Merged into `hiivmind-pulse-gh-init` |

#### 5.2 Archive Strategy

Option A: Move to `archive/skills/` directory
Option B: Delete entirely (git history preserves)
Option C: Keep but add deprecation notices

**Recommended:** Option A - preserves for reference without cluttering active plugin.

```bash
mkdir -p archive/skills
mv skills/hiivmind-pulse-gh-projects archive/skills/
mv skills/hiivmind-pulse-gh-milestones archive/skills/
mv skills/hiivmind-pulse-gh-branch-protection archive/skills/
mv skills/hiivmind-pulse-gh-investigate archive/skills/
mv skills/hiivmind-pulse-gh-user-init archive/skills/
mv skills/hiivmind-pulse-gh-workspace-init archive/skills/
```

---

### Phase 6: Update Plugin Manifest

**Objective:** Update `.claude-plugin/plugin.json` to reflect new architecture.

#### 6.1 Updated plugin.json

```json
{
  "name": "hiivmind-pulse-gh",
  "description": "GitHub workspace initialization and API documentation corpus. Run init once, then use gh CLI directly with routing guide and corpus for GraphQL/REST operations.",
  "version": "4.0.0",
  "author": {
    "name": "Nathaniel Ramm <nathaniel@hiivmind.ai>"
  },
  "keywords": [
    "github",
    "graphql",
    "rest-api",
    "projects-v2",
    "milestones",
    "issues",
    "pull-requests",
    "actions",
    "workflows",
    "branch-protection",
    "rulesets",
    "gh-cli",
    "workspace-init"
  ],
  "repository": "https://github.com/hiivmind/hiivmind-pulse-gh"
}
```

#### 6.2 Update marketplace.json (if applicable)

Ensure marketplace listing reflects the new 2-skill model.

---

### Phase 7: Validation

**Objective:** Verify the new architecture works end-to-end.

#### 7.1 Test Scenarios

| Scenario | Steps | Expected |
|----------|-------|----------|
| Fresh init | Run init on new repo | Config created, user.yaml created |
| API routing | Need milestone create | Routing says REST, corpus has endpoint |
| GraphQL lookup | Need Projects v2 mutation | Corpus grep finds mutation definition |
| Direct gh usage | Create issue with config | Works without sourcing functions |
| Refresh | Add new project in GitHub | Refresh updates config |

#### 7.2 Documentation Walkthrough

Test that a new user can:
1. Read CLAUDE.md and understand the flow
2. Run init successfully
3. Find the right API via routing guide
4. Get syntax from corpus
5. Execute operation with `gh`

---

## Implementation Order

```
Phase 1: Reference Structure     ─┬─ 1.1 config-schema.md
                                  └─ 1.2 workflow examples (3)
                                        │
Phase 2: Consolidate Init        ─┬─ 2.1 Create init skill
                                  └─ 2.2 Update refresh skill
                                        │
Phase 3: CLAUDE.md Overhaul      ─── 3.1-3.2 Rewrite for v3
                                        │
Phase 4: Demote Libraries        ─┬─ 4.1 Create README.md
                                  └─ 4.2 Update index files
                                        │
Phase 5: Archive Old Skills      ─── Move to archive/
                                        │
Phase 6: Update Manifest         ─── plugin.json updates
                                        │
Phase 7: Validation              ─── End-to-end testing
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing users | Version bump to 4.0.0, document in CHANGELOG |
| Lost functionality | Archive (don't delete) old skills |
| Incomplete corpus | Corpus already has keyword-tagged index |
| Complex operations fail | Keep function libraries as reference |

---

## Success Criteria

- [ ] Single `init` skill handles all setup
- [ ] CLAUDE.md describes v3 flow without function references
- [ ] User can complete GitHub operations without sourcing bash functions
- [ ] Routing guide + corpus provides all needed syntax
- [ ] Old skills archived, not cluttering active plugin
- [ ] Plugin manifest reflects new architecture
