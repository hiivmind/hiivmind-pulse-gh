---
name: gh-refresh
description: >
  Sync cached workspace config with current GitHub state. This skill should be used when: config is
  stale, "ID not found" errors occur, project fields changed, new projects created, options renamed,
  or after making changes in GitHub UI. Trigger phrases: "refresh config", "sync workspace", "update
  cache", "ID not found", "field not found", "stale config", "refresh projects", "config out of date",
  "resync GitHub", "fix stale config", "revalidate github IDs", "config refresh", "github settings
  changed", "reload github config", "update github cache", "sync github state". Supports selective
  refresh of sections: workspace, projects, views, repo_settings, automations, relationships, teams.
trigger: "refresh config|sync workspace|update cache|ID not found|stale config|refresh projects|config out of date|resync GitHub"
tools: [shell, filesystem]
author: hiivmind
---

# GitHub Workspace Refresh

Synchronize cached configuration with current GitHub state. Run when config becomes stale or IDs change.

## Path Convention

`{PLUGIN_ROOT}` = Plugin root directory (where plugin.json lives)

When this skill references files like `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`,
read from the plugin root, not relative to this skill folder.

## Scope

| Does | Does NOT |
|------|----------|
| Check staleness per section | Execute GitHub mutations |
| Refresh selected sections | Initialize new workspaces |
| Update freshness timestamps | Modify GitHub resources |
| Update cached IDs and fields | Create new projects/fields |

## Phase Overview

```
1. CONTEXT → 1.5 TOOLS → 2. STALENESS → 3. SELECT → 4. REFRESH → 5. UPDATE → 6. REPORT
   (load)      (check)      (check)       (user)      (query)      (write)      (done)
      │           │             │            │            │            │            │
   STOP if     STOP if      Show all      STOP for    Query API      -         STOP: offer
   not init    missing      sections      selection   per section             next steps
```

---

## Phase 1: CONTEXT

**Goal:** Load existing configuration and verify workspace is initialized.

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

### What to Do

1. Check for `.hiivmind/github/config.yaml`
2. Load workspace info (login, type, repositories)
3. Check for `freshness.yaml`

### STOP Point

**If not initialized:**

```
Workspace not initialized.

Config file not found: .hiivmind/github/config.yaml

Run: /gh init
```

---

## Phase 1.5: CHECK TOOLS

**See:** `{PLUGIN_ROOT}/lib/patterns/tool-detection.md`

Verify required tools are available before refreshing:

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

---

## Phase 2: STALENESS

**Goal:** Check which sections need refreshing based on timestamps and thresholds.

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

### What to Do

1. Read `freshness.yaml`
2. For each section, compare `last_checked` against `threshold_hours`
3. Mark sections as stale/fresh

### Staleness Calculation

```
age_hours = (now - last_checked) / 3600
stale = age_hours > threshold_hours OR last_checked is null
```

### Present Status

```
=== Freshness Status ===

Section          Last Checked         Age      Threshold   Status
─────────────────────────────────────────────────────────────────
workspace        2024-01-15 09:00     2h       24h         FRESH
projects         2024-01-14 12:00     23h      24h         FRESH
views            2024-01-10 08:00     120h     48h         STALE
repo_settings    never                -        72h         STALE
automations      2024-01-12 15:00     70h      168h        FRESH
relationships    never                -        168h        STALE
teams            2024-01-08 10:00     168h     168h        STALE
```

---

## Phase 3: SELECT

**Goal:** Let user choose which sections to refresh.

### STOP Point

**Present options to user:**

```
Stale sections that need refreshing:
  1. views (120h old, threshold: 48h)
  2. repo_settings (never checked)
  3. relationships (never checked)
  4. teams (168h old, threshold: 168h)

Fresh sections (optional refresh):
  5. workspace (2h old)
  6. projects (23h old)
  7. automations (70h old)

Which sections to refresh? [1,2,3,4 / stale / all / none]
```

**Never auto-refresh** without user confirmation.

---

## Phase 4: REFRESH

**Goal:** Refresh each selected section by querying GitHub APIs.

**See:** `{PLUGIN_ROOT}/lib/patterns/error-handling.md`

### PREREQUISITE: Read Routing Guide

**IMPORTANT:** Before refreshing ANY section, read the FULL `{PLUGIN_ROOT}/lib/references/api-routing.md` file.

- The file is ~245 lines - read it completely, do NOT grep or search
- This gives you routing decisions for ALL domains upfront
- You need this context to make correct GraphQL vs REST decisions

```
Read: {PLUGIN_ROOT}/lib/references/api-routing.md (full file)
```

### Refresh Approach

For each selected section:

1. **Check Routing Guide** (already read above)
   - Determine: GraphQL vs REST
   - Note keywords if you need corpus lookup

2. **Execute Query**
   - If syntax is clear: Execute directly
   - If uncertain: Use corpus lookup (`{PLUGIN_ROOT}/lib/patterns/corpus-lookup.md`)
   - GraphQL: temp file pattern (`{PLUGIN_ROOT}/lib/patterns/graphql-execution.md`)
   - REST: `gh api /endpoint`

3. **Update Config Files**
   - Write results to appropriate config file
   - Use patterns from `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

### Corpus Lookup (When Needed)

If uncertain about query syntax:
- **Invoke:** `hiivmind-corpus-github-docs-navigate`
- **Query:** With keywords from routing guide
- **Get:** Exact query syntax from schema/docs

### Refreshable Sections

| Section | Config File | Keywords | Data Updated |
|---------|-------------|------------------|--------------|
| workspace | `config.yaml` | `organization`, `user` | Org/user info, login, type |
| projects | `config.yaml` | `projectsV2`, `fields`, `SingleSelectField` | Project IDs, field IDs, option IDs |
| views | `views/project-N.yaml` | `projectV2.views`, `layout`, `filter` | View configurations |
| repo_settings | `repos/REPO.yaml` | `branchProtectionRules`, REST `/branches` | Protection rules, rulesets, labels |
| automations | `automations/project-N.yaml` | `projectV2.workflows` | Workflow templates (manual update) |
| relationships | `relationships.yaml` | `projectsV2.repositories` | Project-repo links |
| teams | `teams.yaml` | `organization.teams`, `members` | Team membership, permissions |

### Notes on Specific Sections

**views:** View CRUD is UI-only (no createProjectV2View mutation). Refresh fetches current state.

**automations:** GitHub Projects v2 automations are configured in UI and not fully exposed via API. Creates template file for manual documentation.

**teams:** Only available for organizations, not user accounts.

---

## Phase 5: UPDATE

**Goal:** Update freshness timestamps after refresh.

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

### What to Do

For each refreshed section:

1. Set `last_checked` to current timestamp
2. Set `stale` to `false`
3. Record coverage (projects_covered, repos_covered)
4. Update `cache.last_updated_at`

### Timestamp Format

ISO 8601 UTC: `2024-01-15T14:30:00Z`

### Decision Capture (headless replay)

Record the sections just refreshed so `gh-refresh-headless` can replay this decision
without prompting (spec: decision capture — headless variants replay, never guess):

1. Read `automation.refresh_sections` from config.yaml (treat missing as `[]`)
2. Set it to the **union** of the existing list and the sections refreshed this run
3. Set `automation.refresh_recorded_at` to the current UTC timestamp

The list only grows through interactive use; the team prunes it by editing config.yaml.

---

## Phase 6: REPORT

**Goal:** Summarize refresh results and offer next steps.

### What to Do

1. Display summary of refreshed sections
2. Note any errors or warnings
3. Offer next actions

### STOP Point

**After successful refresh:**

```
Refresh complete!

Sections refreshed:
  ✓ views (project 2, 3)
  ✓ repo_settings (hiivmind-pulse-gh)
  ✓ relationships
  ✓ teams

Warnings:
  ⚠ automations: Template created - update manually

Config files updated:
  .hiivmind/github/views/project-2.yaml
  .hiivmind/github/views/project-3.yaml
  .hiivmind/github/repos/hiivmind-pulse-gh.yaml
  .hiivmind/github/relationships.yaml
  .hiivmind/github/teams.yaml
  .hiivmind/github/freshness.yaml

What would you like to do next?
  1. Run an operation (use /hiivmind-pulse-gh)
  2. Refresh more sections
  3. Done for now
```

---

## When to Refresh

| Trigger | Symptom | Section |
|---------|---------|---------|
| Field ID changed | "Field not found" errors | projects |
| Option renamed | "Option not found" errors | projects |
| New project added | Project not in config | projects |
| Fields added/removed | Missing field in config | projects |
| View layout changed | View settings outdated | views |
| Protection rules changed | Rule not found | repo_settings |
| Team membership changed | Wrong permissions | teams |

---

## Quick Reference

### Check Freshness Status

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` - "Read freshness.yaml" section

### Force Refresh Specific Section

```
/gh refresh [section]
```

Sections: `workspace`, `projects`, `views`, `repo_settings`, `automations`, `relationships`, `teams`

### Force Refresh All

```
/gh refresh all
```

### Related Skills

- **init** - First-time workspace setup
- **operations** - Execute GitHub operations using cached config

---

## Examples Library

All implementation details are in the examples library:

**Introspection Examples (HEAVY):**

| Example | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` | Read/write YAML config files |
| `{PLUGIN_ROOT}/lib/patterns/graphql-execution.md` | Execute queries via temp file |
| `{PLUGIN_ROOT}/lib/patterns/error-handling.md` | Handle API errors |
| `{PLUGIN_ROOT}/lib/patterns/id-resolution.md` | Resolve names to IDs |

**Operations Examples (LIGHT):**

| Example | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/references/api-routing.md` | API routing decisions (canonical source) |
| `{PLUGIN_ROOT}/lib/patterns/corpus-lookup.md` | Look up API syntax when uncertain |

**External Resources:**

| Resource | Purpose |
|----------|---------|
| `hiivmind-corpus-github-docs-navigate` | GitHub corpus skill for syntax lookup |
