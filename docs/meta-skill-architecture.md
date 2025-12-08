# Meta-Skill Architecture

This document describes the workspace configuration system that enables persistent GitHub context across Claude Code sessions.

## Overview

The hiivmind-github-skills toolkit uses a **meta-skill pattern** to discover, cache, and persist GitHub organization/project metadata. This eliminates the need for users to repeatedly specify organization names, project numbers, and field IDs.

### Design Principles

1. **Config lives with the code** - Stored in `.hiivmind/` in the repository root
2. **Shared + Personal** - Team config is committed; user config is gitignored
3. **Generic skills, contextual config** - Single set of marketplace skills reads local config
4. **Graceful degradation** - Skills work without config (explicit params required)
5. **Multi-repo support** - Symlinks enable shared config across repositories

## Directory Structure

### In User's Repository

```
my-project/
├── .hiivmind/
│   └── github/
│       ├── config.yaml       # Shared team config (committed)
│       └── user.yaml         # Personal config (gitignored)
├── .gitignore                 # Includes .hiivmind/github/user.yaml
├── src/
└── ...
```

### Multi-Repo Setup (Symlinks)

```
~/work/
├── github-workspace/              # Centralized config location
│   └── github/
│       ├── config.yaml
│       └── user.yaml
│
├── api-repo/
│   └── .hiivmind -> ../github-workspace/
├── frontend-repo/
│   └── .hiivmind -> ../github-workspace/
└── docs-repo/
    └── .hiivmind -> ../github-workspace/
```

## Config Schema

### Shared Config (`config.yaml`)

Committed to git. Contains organization/project structure that applies to all team members.

```yaml
# Workspace identification
workspace:
  type: organization           # "organization" or "user"
  login: acme-corp             # GitHub org/user login
  id: O_kgDOxxxxxxx            # GraphQL node ID (cached)

# Project configuration
projects:
  default: 2                   # Default project number for commands
  catalog:
    - number: 2
      id: PVT_kwDOxxxxxxx
      title: Product Roadmap
      url: https://github.com/orgs/acme-corp/projects/2
      fields:
        # Single-select fields with option ID mappings
        Status:
          id: PVTSSF_xxxxxxx
          type: single_select
          options:
            Backlog: PVTSSFO_xxxxxxx1
            Ready: PVTSSFO_xxxxxxx2
            In Progress: PVTSSFO_xxxxxxx3
            In Review: PVTSSFO_xxxxxxx4
            Done: PVTSSFO_xxxxxxx5
        Priority:
          id: PVTSSF_yyyyyyy
          type: single_select
          options:
            P0 - Critical: PVTSSFO_yyyyyyy1
            P1 - High: PVTSSFO_yyyyyyy2
            P2 - Medium: PVTSSFO_yyyyyyy3
            P3 - Low: PVTSSFO_yyyyyyy4
        # Other field types
        Sprint:
          id: PVTIF_zzzzzzz
          type: iteration
        Due Date:
          id: PVTF_aaaaaaa
          type: date
        Estimate:
          id: PVTF_bbbbbbb
          type: number

# Repository catalog
repositories:
  - name: api
    id: R_kgDOxxxxxxx
    full_name: acme-corp/api
    default_branch: main
    visibility: private
  - name: frontend
    id: R_kgDOyyyyyyy
    full_name: acme-corp/frontend
    default_branch: main
    visibility: private
  - name: docs
    id: R_kgDOzzzzzzz
    full_name: acme-corp/docs
    default_branch: main
    visibility: public

# Milestone catalog (per-repo)
milestones:
  api:
    - number: 1
      id: MI_xxxxxxx
      title: v1.0.0
      state: open
    - number: 2
      id: MI_yyyyyyy
      title: v1.1.0
      state: open
  frontend:
    - number: 1
      id: MI_zzzzzzz
      title: MVP
      state: open

# Cache metadata
cache:
  initialized_at: 2025-12-08T10:00:00Z
  last_synced_at: 2025-12-08T10:00:00Z
  toolkit_version: 2.1.0
```

### User Config (`user.yaml`)

Gitignored. Contains user-specific identity and cached permissions.

```yaml
# User identification
user:
  login: nathanielramm
  id: U_kgDOxxxxxxx
  name: Nathaniel Ramm
  email: nathaniel@example.com

# Cached permissions (avoids repeated API calls)
permissions:
  # Organization-level role
  org_role: member             # owner, admin, member, billing_manager

  # Project-level roles
  project_roles:
    2: admin                   # admin, write, read, none
    5: write

  # Repository-level roles
  repo_roles:
    api: maintain              # admin, maintain, write, triage, read
    frontend: write
    docs: read

# User preferences
preferences:
  default_project: 2           # Override team default
  default_repo: api            # For ambiguous commands

# Cache metadata
cache:
  permissions_checked_at: 2025-12-08T10:00:00Z
  permissions_ttl_hours: 24    # Re-check after this period
```

## Meta-Skills

Three meta-skills manage the workspace configuration lifecycle.

### github-workspace-init

**Purpose:** Create initial `.hiivmind/github/` structure and config files.

**Workflow:**
1. Check if `.hiivmind/github/config.yaml` already exists
2. Prompt user for workspace type (organization or user)
3. Prompt for organization/user login
4. Create directory structure
5. Generate initial `config.yaml` with workspace identification
6. Generate empty `user.yaml`
7. Suggest `.gitignore` addition

**Output:**
```
.hiivmind/
└── github/
    ├── config.yaml    # Basic workspace info
    └── user.yaml      # Empty template
```

### github-workspace-analyze

**Purpose:** Discover and cache GitHub structure (projects, fields, repos, milestones).

**Workflow:**
1. Read workspace info from `config.yaml`
2. Discover all projects in the organization/user account
3. For each project, fetch:
   - Field definitions with IDs
   - Single-select option IDs
   - Iteration configurations
4. Discover linked/accessible repositories
5. For each repository, fetch milestones
6. Fetch current user's identity and permissions
7. Update `config.yaml` with discovered structure
8. Update `user.yaml` with user info and permissions
9. Set `last_synced_at` timestamp

**Interactive elements:**
- Ask which projects to include in catalog
- Ask which repositories to include
- Confirm before overwriting existing config

### github-workspace-refresh

**Purpose:** Sync configuration with current GitHub state.

**Workflow:**
1. Read existing `config.yaml` and `user.yaml`
2. For each cataloged project:
   - Check if still accessible
   - Detect new/removed/renamed fields
   - Detect new/removed/changed options
3. For each cataloged repository:
   - Check if still accessible
   - Update milestone list
4. Refresh user permissions
5. Report changes to user
6. Update configs with new state
7. Update `last_synced_at` timestamp

**Change detection:**
- New fields/options: Add to config
- Removed fields/options: Warn and remove from config
- Renamed fields/options: Warn and update
- Permission changes: Update user.yaml

## Generic Skill Behavior

Existing skills (`hiivmind-github-projects`, `hiivmind-github-milestones`, `hiivmind-github-branch-protection`) are updated to detect and use local config.

### Config Detection

At the start of any operation, skills check for config:

```bash
CONFIG_PATH=".hiivmind/github/config.yaml"
USER_CONFIG_PATH=".hiivmind/github/user.yaml"

if [[ -f "$CONFIG_PATH" ]]; then
    # Load cached context
    ORG=$(yq '.workspace.login' "$CONFIG_PATH")
    PROJECT_ID=$(yq '.projects.catalog[0].id' "$CONFIG_PATH")
    # ... etc
else
    # Require explicit parameters
    echo "No workspace config found. Specify org/project explicitly."
fi
```

### Behavior Matrix

| Config Present | Behavior |
|----------------|----------|
| Yes | Use cached IDs, simplified commands |
| No | Require explicit parameters (current behavior) |

### Simplified Commands (With Config)

```bash
# Without config (current)
fetch_org_project 2 "acme-corp" | apply_status_filter "In Progress"

# With config (new)
fetch_project | apply_status_filter "In Progress"
# ORG and PROJECT_NUMBER read from config

# Set status by name (config maps to option ID)
set_item_status "PVTI_xxx" "In Progress"
# Looks up option ID from config.yaml
```

### Permission Awareness

Skills can check cached permissions before attempting operations:

```bash
# Check if user can modify project
USER_ROLE=$(yq ".permissions.project_roles.2" "$USER_CONFIG_PATH")
if [[ "$USER_ROLE" == "read" ]]; then
    echo "Warning: You have read-only access to this project"
fi
```

## Implementation Phases

### Phase 1: Foundation
- [ ] Create `templates/` directory with config templates
- [ ] Implement `github-workspace-init` skill
- [ ] Add `.hiivmind` detection to existing skills (graceful fallback)

### Phase 2: Discovery
- [ ] Implement `github-workspace-analyze` skill
- [ ] Add project field discovery functions to `gh-project-functions.sh`
- [ ] Add permission checking functions to `gh-rest-functions.sh`

### Phase 3: Maintenance
- [ ] Implement `github-workspace-refresh` skill
- [ ] Add change detection logic
- [ ] Add staleness warnings (config older than N days)

### Phase 4: Enhancement
- [ ] Add shorthand commands that use config
- [ ] Add permission pre-flight checks
- [ ] Add config validation on load

## Gitignore Template

When initializing a workspace, suggest adding to `.gitignore`:

```gitignore
# hiivmind-github-skills - user-specific config
.hiivmind/github/user.yaml
```

## Error Handling

### Config Not Found
```
No workspace configuration found.
Run `github-workspace-init` to set up, or specify parameters explicitly.
```

### Stale Config Warning
```
Workspace config last synced 14 days ago.
Consider running `github-workspace-refresh` to update cached IDs.
```

### Permission Denied
```
Cached permissions indicate read-only access to project #2.
This operation requires write access. Refresh permissions with:
  github-workspace-refresh
```

### ID Not Found
```
Field "Status" not found in cached config.
The project structure may have changed. Run:
  github-workspace-refresh
```

## Related Documentation

- [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) - Overall toolkit architecture
- [api-implementation-plan.md](./api-implementation-plan.md) - API function reference
