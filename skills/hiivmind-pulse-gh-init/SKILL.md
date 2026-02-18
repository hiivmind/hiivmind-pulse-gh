---
name: hiivmind-pulse-gh-init
version: 4.0.0
description: >
  Initialize GitHub workspace to enable context enrichment for all GitHub operations. This skill
  should be used when: setting up a new workspace, first-time configuration, config.yaml is missing,
  or "workspace not initialized" errors occur. Trigger phrases: "initialize workspace", "setup GitHub",
  "first time setup", "init pulse-gh", "configure workspace", "cache project IDs", "workspace not
  initialized", "start github plugin", "get github working", "new workspace setup", "bootstrap github",
  "prepare github workspace", "github init", "enable project linking", "setup issue enrichment".
  Verifies gh CLI, jq, yq tools and authentication. Discovers projects and caches field IDs so
  issues/PRs can be automatically linked to projects. Run once per repository.
---

# GitHub Workspace Initialization

One-time setup that enables context enrichment for all GitHub operations. Without this initialization,
issues and PRs created are orphans with no project linking.

## Path Convention

`{PLUGIN_ROOT}` = Plugin root directory (where plugin.json lives)

When this skill references files like `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`,
read from the plugin root, not relative to this skill folder.

## Scope

| Does | Does NOT |
|------|----------|
| Verify CLI tools (gh, jq, yq) | Execute GitHub operations |
| Validate authentication and scopes | Refresh stale configs |
| Detect workspace from git or user input | Fetch views/automations/teams |
| Discover and cache project IDs | Build extended configs |
| Create config.yaml + user.yaml | Modify GitHub resources |

## Phase Overview

```
1. CONTEXT    → 2. PREREQS   → 3. INPUT    → 4. DISCOVER → 5. CACHE    → 6. VERIFY
   (detect)       (tools)        (confirm)     (projects)    (write)       (done)
      │              │               │              │            │            │
   STOP if       STOP if         STOP for       STOP for       -         STOP: offer
   ambiguous     missing         user OK        selection              refresh/ops
```

---

## Phase 1: CONTEXT

**Goal:** Detect the GitHub workspace (organization or user) from context.

**See:** `{PLUGIN_ROOT}/lib/patterns/workspace-detection.md`

### Check for Existing Config

**IMPORTANT:** Before initializing, check if config already exists in current or parent directory:

```bash
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    echo "Config found in current directory"
    EXISTING_CONFIG=".hiivmind/github/config.yaml"
elif [[ -f "../.hiivmind/github/config.yaml" ]]; then
    echo "Config found in parent directory"
    EXISTING_CONFIG="../.hiivmind/github/config.yaml"
fi
```

**If config exists in parent:**
```
Found existing workspace config in parent directory: ../.hiivmind/github/config.yaml

This is common for workspace setups where multiple repos share one config.

Options:
1. Use parent config (recommended for workspace setup)
2. Create local config for this repo only
3. Re-initialize parent config

Which would you like? [1/2/3]
```

### What to Do

1. **Check for existing config** (current and parent directories)
2. Check if we're in a git repository
3. If yes: extract owner from git remote URL
4. If no: prompt user to specify the workspace
5. Determine if workspace is organization or user type

### STOP Point

**If context is ambiguous** (not in git repo, no remote, multiple remotes):

```
I couldn't detect a GitHub workspace from git context.

Please specify the GitHub organization or username to initialize:
```

**Never auto-decide** on workspace target. Always confirm with user.

---

## Phase 2: PREREQS

**Goal:** Verify required tools and authentication.

**See:** `{PLUGIN_ROOT}/lib/patterns/tool-detection.md`
**See:** `{PLUGIN_ROOT}/lib/patterns/authentication.md`

### What to Do

1. Check for gh CLI, jq, yq availability
2. Verify gh is authenticated
3. Check for required scopes: `repo`, `read:org`, `project`, `read:project`

### STOP Point

**If tools missing:**

```
Missing required tools: [list]

Install instructions:
- gh: https://cli.github.com/
- jq: apt install jq / brew install jq
- yq: https://github.com/mikefarah/yq#install
```

**If not authenticated:**

```
gh CLI is not authenticated.

Run: gh auth login
```

**If scopes missing:**

```
Missing required scopes: [list]

Run: gh auth refresh --scopes 'repo,read:org,project,read:project'
```

---

## Phase 3: INPUT

**Goal:** Confirm workspace with user before proceeding.

### What to Do

Present detected workspace and ask for confirmation:

```
Detected workspace:
  Owner: hiivmind
  Type: organization
  Source: git remote (origin)

Is this the workspace you want to initialize? [Y/n]
```

### STOP Point

Wait for user confirmation before proceeding. If user says no, ask them to specify the correct workspace.

---

## Phase 4: DISCOVER

**Goal:** Discover projects and their field configurations.

### Discovery Approach

1. **Read Routing Guide**
   - Read `{PLUGIN_ROOT}/lib/references/api-routing.md`
   - Projects v2 → List projects → GraphQL
   - Keywords: `projectsV2`, `organization`, `user`

2. **Execute Query**
   - If syntax is clear: Execute directly
   - If uncertain: Use corpus lookup (`{PLUGIN_ROOT}/lib/patterns/corpus-lookup.md`)
   - Use temp file pattern from `{PLUGIN_ROOT}/lib/patterns/graphql-execution.md`

### Corpus Lookup (When Needed)

If uncertain about projectsV2 query syntax:
- **Invoke:** `hiivmind-corpus-github-docs-navigate`
- **Query:** "projectsV2 organization list projects GraphQL"
- **Get:** Query syntax for listing projects

### What to Do

1. Query for all projects in the workspace (org or user)
2. For each project, fetch field configurations
3. Present list to user for selection

### STOP Point

**After discovering projects:**

```
Found 3 projects:

  1. Feature Planner (open) - 5 fields
  2. Bug Tracker (open) - 4 fields
  3. Archive (closed) - 3 fields

Which projects should I cache? [1,2 / all / none]
```

**After selection:**

```
Set default project for operations?
  1. Feature Planner
  2. Bug Tracker
  [number / none]
```

---

## Phase 5: CACHE

**Goal:** Write configuration files.

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

### What to Do

1. Create `.hiivmind/github/` directory
2. Write `config.yaml` with:
   - Workspace info (type, login, id)
   - Project catalog with field IDs
   - Default project setting
   - Cache timestamps
3. Write `user.yaml` with authenticated user info
4. Write `freshness.yaml` with section timestamps
5. Update `.gitignore` to exclude `user.yaml`
6. Configure `.claude/settings.json` with marketplace dependency

### Configure Marketplace Dependency

Create or update `.claude/settings.json` to declare the hiivmind-pulse-gh marketplace as a recommended dependency:

```json
{
  "extraKnownMarketplaces": {
    "hiivmind-pulse-gh": {
      "source": {
        "source": "github",
        "repo": "hiivmind/hiivmind-pulse-gh"
      }
    }
  },
  "enabledPlugins": {
    "hiivmind-pulse-gh@hiivmind-pulse-gh": true
  }
}
```

**Why this matters:**
- Makes hiivmind plugins discoverable to your team
- Works in both local and web sessions
- Enables access to corpus plugins (GitHub API docs, etc.)
- Team members get prompted to install on trust

**If `.claude/settings.json` exists:**
- Read current settings
- Merge in `extraKnownMarketplaces` entry (preserve existing entries)
- Merge in `enabledPlugins` entry (preserve existing plugins)
- Write back

**If file doesn't exist:**
- Create `.claude/` directory
- Write new settings file with marketplace config

### Create Freshness Tracking

Copy the freshness template and stamp initial timestamps:

```bash
cp "{PLUGIN_ROOT}/templates/freshness.yaml.template" ".hiivmind/github/freshness.yaml"
```

Then update with current timestamp:
- Replace `{{initialized_at}}` in the header comment with the current ISO 8601 timestamp
- Set `cache.created_at` to current timestamp
- Set `cache.last_updated_at` to current timestamp
- Set `sections.workspace.last_checked` to current timestamp (just discovered)
- Set `sections.workspace.stale` to `false`
- Set `sections.projects.last_checked` to current timestamp (just discovered)
- Set `sections.projects.stale` to `false`
- Set `sections.repositories.last_checked` to current timestamp (just discovered)
- Set `sections.repositories.stale` to `false`

All other sections remain `stale: true` with `last_checked: null` until explicitly refreshed.

### Output Files

| File | Purpose | Git Status |
|------|---------|------------|
| `.hiivmind/github/config.yaml` | Workspace config (shared) | Committed |
| `.hiivmind/github/user.yaml` | User identity (personal) | Gitignored |
| `.hiivmind/github/freshness.yaml` | Staleness tracking | Committed |
| `.claude/settings.json` | Plugin dependencies | Committed |

---

## Phase 6: VERIFY

**Goal:** Confirm initialization and offer next steps.

### What to Do

1. Verify config files were created
2. Display summary of cached data
3. Offer next steps

### STOP Point

**After successful init:**

```
Initialization complete!

Workspace: hiivmind (organization)
Projects cached: 2
Default project: Feature Planner (#2)

Config files:
  .hiivmind/github/config.yaml (shared)
  .hiivmind/github/user.yaml (personal)
  .hiivmind/github/freshness.yaml
  .claude/settings.json (marketplace dependencies)

The hiivmind marketplace is now configured as a dependency.
Team members will be prompted to install it when they trust this repo.

What would you like to do next?
  1. Run an operation (use /hiivmind-pulse-gh)
  2. Fetch extended config (views, teams, automations)
  3. Done for now
```

---

## Quick Reference

### Check If Already Initialized

```bash
ls -la .hiivmind/github/
```

If `config.yaml` exists and is recent, workspace is already initialized.

### Re-initialize

To re-initialize (updates existing config):

```
/hiivmind-pulse-gh reinitialize workspace [owner]
```

### Related Skills

- **refresh** - Update stale sections of config
- **operations** - Execute GitHub operations using cached config

### Examples Library

All implementation details are in the examples library:

**Introspection Examples (HEAVY):**

| Example | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/patterns/tool-detection.md` | Check for gh, jq, yq |
| `{PLUGIN_ROOT}/lib/patterns/authentication.md` | Verify auth and scopes |
| `{PLUGIN_ROOT}/lib/patterns/workspace-detection.md` | Detect org/user from context |
| `{PLUGIN_ROOT}/lib/patterns/graphql-execution.md` | Execute queries via temp file |
| `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` | Read/write YAML config |

**Operations Examples (LIGHT):**

| Example | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/references/api-routing.md` | API routing decisions (canonical source) |
| `{PLUGIN_ROOT}/lib/patterns/corpus-lookup.md` | Look up API syntax when uncertain |

**External Resources:**

| Resource | Purpose |
|----------|---------|
| `hiivmind-corpus-github-docs-navigate` | GitHub corpus skill for syntax lookup |
