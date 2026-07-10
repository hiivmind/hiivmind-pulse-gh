---
name: gh-init
description: >
  Initialize GitHub workspace to enable context enrichment for all GitHub operations. This skill
  should be used when: setting up a new workspace, first-time configuration, config.yaml is missing,
  or "workspace not initialized" errors occur. Trigger phrases: "initialize workspace", "setup GitHub",
  "first time setup", "init pulse-gh", "configure workspace", "cache project IDs", "workspace not
  initialized", "start github plugin", "get github working", "new workspace setup", "bootstrap github",
  "prepare github workspace", "github init", "enable project linking", "setup issue enrichment".
  Verifies gh CLI, jq, yq tools and authentication. Discovers projects and caches field IDs so
  issues/PRs can be automatically linked to projects. Run once per repository.
trigger: "initialize workspace|setup GitHub|first time setup|init pulse-gh|configure workspace|cache project IDs|workspace not initialized|github init|bootstrap github"
tools: [shell, filesystem]
author: hiivmind
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
| Create workflows directory and install templates | Run workflows |
| Set up heartbeat logging directory | Configure advanced workflow options |

## Phase Overview

```
1. CONTEXT    → 2. PREREQS   → 3. INPUT    → 4. DISCOVER → 5. CACHE    → 5.5 HEARTBEAT → 5.7 HEALTHCHECK → 6. VERIFY
   (detect)       (tools)        (confirm)     (projects)    (write)       (workflows)      (optional)       (done)
      │              │               │              │            │              │                │               │
   STOP if       STOP if         STOP for       STOP for       -          STOP for        STOP for         STOP: offer
   ambiguous     missing         user OK        selection              template select   user choice     refresh/ops
```

---

## Phase 1: CONTEXT

**Goal:** Detect the GitHub workspace (organization or user) from context.

**See:** `{PLUGIN_ROOT}/lib/patterns/workspace-detection.md`

### Resolve Existing Workspace

**See:** `{PLUGIN_ROOT}/lib/patterns/workspace-detection.md` § Workspace Root Resolution

```bash
WORKSPACE_ROOT=""
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
    if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] \
       && grep -q '^workspace:' "$DIR/.hiivmind/github/config.yaml"; then
        WORKSPACE_ROOT="$DIR"
        break
    fi
    DIR="$(dirname "$DIR")"
done
```

**CRITICAL — NEVER delete a `.hiivmind/` directory.** It is a shared namespace
used by multiple plugins (github, corpus, etc.). Only `.hiivmind/github/` is
managed by this plugin.

**If a workspace root is found:** the workspace is already initialized.

```
Found workspace config at {WORKSPACE_ROOT}/.hiivmind/github/config.yaml
(workspace: {login}, {type})

Options:
1. Refresh it (run gh-refresh)
2. Add a repo-level overlay for this repo (repo-scoped workflows/overrides only)
3. Re-initialize the workspace config (overwrites catalogs; workspace repo history preserved)

Which would you like? [1/2/3]
```

An overlay (option 2) is a `.hiivmind/github/` inside the current repo
**without** a `workspace:` section — it never carries workspace identity.

**If no workspace root is found — choose placement:**

```bash
GIT_TOP=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$GIT_TOP" ]]; then
    CANDIDATE_ROOT=$(dirname "$GIT_TOP")
else
    CANDIDATE_ROOT="$PWD"
fi
# Count sibling repo clones under the candidate root
SIBLING_CLONES=$(find "$CANDIDATE_ROOT" -mindepth 2 -maxdepth 2 -name .git 2>/dev/null | wc -l | tr -d ' ')
```

| Situation | Default placement |
|-----------|-------------------|
| `SIBLING_CLONES` ≥ 2 (multi-repo parent) | **Workspace root = `$CANDIDATE_ROOT`** (recommended default) |
| Single repo, no siblings | Workspace root = the repo itself (config committed to the host repo; no separate workspace repo) |
| Repo-local config with a `workspace:` section exists at `$GIT_TOP` AND siblings exist | Offer **promotion** (below) |

```
No workspace found. This looks like a multi-repo parent:
  {CANDIDATE_ROOT} contains {N} repo clones.

Where should the workspace live?
1. {CANDIDATE_ROOT}/.hiivmind/github/  — shared workspace repo, serves all clones (recommended)
2. {GIT_TOP}/.hiivmind/github/          — this repo only

Which would you like? [1/2]
```

**Promotion flow** (existing repo-local workspace config, multi-repo parent):

```
Found a workspace config inside {repo}, but {CANDIDATE_ROOT} holds {N} sibling
clones. Promote it to the workspace root? This will:
  1. Move .hiivmind/github/ content to {CANDIDATE_ROOT}/.hiivmind/github/
  2. Initialize it as the workspace repo (Phase 5.9)
  3. Remove the tracked copy from {repo} (git rm) — or keep a slimmed overlay
     if this repo has repo-scoped workflows/overrides

Proceed? [Y/n]
```

Implementation (after user confirms; run from `$GIT_TOP`):

```bash
mkdir -p "$CANDIDATE_ROOT/.hiivmind"
cp -R .hiivmind/github "$CANDIDATE_ROOT/.hiivmind/github"
git rm -r -q .hiivmind/github
rmdir .hiivmind 2>/dev/null || true
# Clean host-repo .gitignore entries that referenced .hiivmind/github/*
```

Then continue to Phase 5.9 to git-init the promoted directory, and remind the
user to commit the removal in the host repo. Per-machine transients that were
copied (`poll-state.yaml`, `log/`, `user.yaml`) are excluded by the workspace
repo's `.gitignore` automatically.

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
5. Copy `{PLUGIN_ROOT}/templates/workspace-gitignore.template` to `{WORKSPACE_ROOT}/.hiivmind/github/.gitignore` (workspace placement); for repo-local placement, add `.hiivmind/github/user.yaml`, `.hiivmind/github/poll-state.yaml`, and `.hiivmind/github/log/` to the host repo's `.gitignore` instead
6. Configure `.claude/settings.json` with marketplace dependency (repo-scoped — apply to each repo where the team should get the marketplace prompt, not to the workspace repo)

### Configure Marketplace Dependency

Create or update `.claude/settings.json` to declare the hiivmind-pulse-gh marketplace as a recommended dependency:

```json
{
  "extraKnownMarketplaces": {
    "hiivmind-pulse-gh": {
      "source": {
        "source": "github",
        "repo": "hiivmind/gh"
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
| `{WORKSPACE_ROOT}/.hiivmind/github/config.yaml` | Workspace config (shared) | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/user.yaml` | User identity (personal) | Gitignored |
| `{WORKSPACE_ROOT}/.hiivmind/github/freshness.yaml` | Staleness tracking | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/.gitignore` | Per-machine transient split | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/workflows/*.yaml` | Heartbeat workflow configs | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/log/` | Heartbeat run logs | Gitignored |
| `.claude/settings.json` (per repo, optional) | Plugin dependencies | Committed to each repo |

---

## Phase 5.5: HEARTBEAT

**Goal:** Set up the heartbeat workflow system so event-driven automation is active from first session.

### What to Do

1. Create `.hiivmind/github/workflows/` directory
2. Create `.hiivmind/github/log/` directory
3. Add `.hiivmind/github/log/` to `.gitignore`
4. Present bundled workflow templates to user for selection

### STOP Point

**Present workflow templates:**

```
The heartbeat runs on every session start and can detect changes.
Install workflow templates? These control what the heartbeat monitors.

  1. auto-refresh — Refresh config when sections go stale (recommended)
  2. pr-lifecycle — Summarize open PRs on session start
  3. issue-triage — Flag untriaged issues
  4. ci-monitor — Check CI/CD run status
  5. stale-check — Flag stale PRs/issues
  6. release-monitor — Notify on new releases
  7. dependabot-alerts — Flag open security vulnerabilities
  8. deploy-monitor — Track deployment status changes
  9. project-sync — Detect project board changes

Which templates to install? [1 / 1,2,3 / all / none]
```

### After Selection

1. Copy selected templates from `{PLUGIN_ROOT}/templates/workflows/` to `.hiivmind/github/workflows/`
2. Note: `poll-state.yaml` is self-bootstrapped by heartbeat on first run — no action needed

---

## Phase 5.7: HEALTHCHECK (Optional)

**Goal:** Offer a governance healthcheck for newly initialized workspaces. Non-blocking.

### What to Do

After heartbeat setup, offer to run the healthcheck:

```
Would you like to run a governance healthcheck?

This assesses repository maturity across:
  - Security (branch protection, security policy, dependabot, secrets scanning)
  - Governance (project linkage, triage labels, CODEOWNERS)
  - Automation (CI/CD, releases)
  - Documentation (README, LICENSE)

Run healthcheck now? [Y/n]
```

### If Yes

Invoke skill: `hiivmind-pulse-gh:gh-healthcheck`

After healthcheck completes, return to Phase 6 (VERIFY).

### If No

Skip — the user can run `/gh healthcheck` at any time.

---

## Phase 5.9: WORKSPACE REPO

**Goal:** Version the workspace so the team can share it (D1). Skip this phase
entirely when placement was repo-local (the host repo versions the config).

### What to Do

```bash
cd "$WORKSPACE_ROOT/.hiivmind/github"
if [[ ! -d .git ]]; then
    git init
    cp "{PLUGIN_ROOT}/templates/workspace-gitignore.template" .gitignore
    git add -A
    git commit -m "chore: initialize hiivmind workspace repo for {login}"
fi
```

The `.gitignore` keeps per-machine transients (`user.yaml`, `poll-state.yaml`,
snapshots, result files, `log/`) out of the shared repo. Everything else —
config, freshness, workflows, views, teams, relationships, healthcheck, runs —
is committed.

### STOP Point

```
Workspace repo initialized at {WORKSPACE_ROOT}/.hiivmind/github/

Create a private GitHub remote so your team can share it?
  gh repo create {login}/{login}-workspace --private --source=. --push

[Y/n — you can also do this later]
```

If yes, run the command and confirm the push succeeded. If the repo name is
taken or the user prefers another name, ask for one. Teammates join with:

    git clone git@github.com:{login}/{login}-workspace.git {workspace_root}/.hiivmind/github

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

Heartbeat:
  Workflows installed: 3 (auto-refresh, pr-lifecycle, ci-monitor)
  Log directory: .hiivmind/github/log/

The hiivmind marketplace is now configured as a dependency.
Team members will be prompted to install it when they trust this repo.

Tip: To reduce approval prompts during heartbeat and operations,
add this to your .claude/settings.local.json allowlist:

  "Edit(.hiivmind/github/**)"

This allows config, freshness, and workflow file edits without
manual approval each time.

What would you like to do next?
  1. Run an operation (use /hiivmind-pulse-gh)
  2. Fetch extended config (views, teams, automations)
  3. Configure workflows (use /gh workflows)
  4. Done for now
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
/gh reinitialize workspace [owner]
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
