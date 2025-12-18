---
name: hiivmind-pulse-gh-init
description: >
  Initialize GitHub workspace for hiivmind-pulse-gh operations. This skill should be used when:
  setting up a new workspace, first-time configuration, config.yaml is missing, or "workspace not
  initialized" errors occur. Trigger phrases: "initialize workspace", "setup GitHub", "first time
  setup", "init pulse-gh", "configure workspace", "cache project IDs", "workspace not initialized".
  Verifies gh CLI, jq, yq tools and authentication. Discovers projects and caches field IDs for
  fast operations. Run once per repository.
---

# GitHub Workspace Initialization

One-time setup for a GitHub workspace. Creates configuration files that enable all other operations.

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

**See:** `lib/github/patterns/workspace-detection.md`

### What to Do

1. Check if we're in a git repository
2. If yes: extract owner from git remote URL
3. If no: prompt user to specify the workspace
4. Determine if workspace is organization or user type

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

**See:** `lib/github/patterns/tool-detection.md`
**See:** `lib/github/patterns/authentication.md`

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
   - Read `reference/api-routing.md`
   - Projects v2 → List projects → GraphQL
   - Keywords: `projectsV2`, `organization`, `user`

2. **Execute Query**
   - If syntax is clear: Execute directly
   - If uncertain: Use corpus lookup (`lib/github/patterns/corpus-lookup.md`)
   - Use temp file pattern from `lib/github/patterns/graphql-execution.md`

### Corpus Lookup (When Needed)

If uncertain about projectsV2 query syntax:
- **Invoke:** `hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs`
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

**See:** `lib/github/patterns/config-parsing.md`

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

### Output Files

| File | Purpose | Git Status |
|------|---------|------------|
| `.hiivmind/github/config.yaml` | Workspace config (shared) | Committed |
| `.hiivmind/github/user.yaml` | User identity (personal) | Gitignored |
| `.hiivmind/github/freshness.yaml` | Staleness tracking | Committed |

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

### Pattern Library

All implementation details are in the pattern library:

| Pattern | Purpose |
|---------|---------|
| `lib/github/patterns/tool-detection.md` | Check for gh, jq, yq |
| `lib/github/patterns/authentication.md` | Verify auth and scopes |
| `lib/github/patterns/workspace-detection.md` | Detect org/user from context |
| `lib/github/patterns/graphql-execution.md` | Execute queries via temp file |
| `lib/github/patterns/config-parsing.md` | Read/write YAML config |
| `lib/github/patterns/corpus-lookup.md` | Look up API syntax when uncertain |

### References

| Reference | Purpose |
|-----------|---------|
| `reference/api-routing.md` | API routing decisions (useful standalone) |
| `hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs` | GitHub corpus skill for syntax lookup |
