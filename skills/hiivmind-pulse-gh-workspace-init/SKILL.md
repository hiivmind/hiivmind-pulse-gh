---
name: hiivmind-pulse-gh-workspace-init
description: >
  Initialize and configure a GitHub workspace. Creates .hiivmind/github/config.yaml,
  discovers projects/fields/repositories, and enriches user.yaml with permissions.
  REQUIRES hiivmind-pulse-gh-user-init to be run first (creates user.yaml).
  Run once per repository, then use hiivmind-pulse-gh-workspace-refresh to keep in sync.
---

# GitHub Workspace Initializer

Complete workspace setup: create config structure, discover GitHub projects, and cache IDs for simplified operations.

## Skill Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  hiivmind-pulse-gh-user-init          ← Must run FIRST (creates user.yaml) │
│       │                                                                     │
│       ▼                                                                     │
│  hiivmind-pulse-gh-workspace-init     ← YOU ARE HERE                       │
│       │                                                                     │
│       ▼                                                                     │
│  All other skills                     ← Require both init skills           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

The simplest way to initialize a workspace using the provided functions:

```bash
# 1. Source the workspace functions
source lib/github/gh-workspace-functions.sh

# 2. Check prerequisites (will error if something is missing)
check_workspace_prerequisites || exit 1

# 3. Check if already initialized
if config_exists; then
    echo "Workspace already initialized. Use workspace-refresh to update."
    exit 0
fi

# 4. Detect workspace from git remote
WORKSPACE_LOGIN=$(detect_workspace_from_remote)
WORKSPACE_TYPE=$(get_workspace_type "$WORKSPACE_LOGIN")

echo "Detected workspace: $WORKSPACE_LOGIN ($WORKSPACE_TYPE)"

# 5. Discover projects
echo "Discovering projects..."
PROJECTS=$(discover_projects "$WORKSPACE_LOGIN" "$WORKSPACE_TYPE")
echo "$PROJECTS" | format_projects_list

# 6. Ask user for selections (projects, default, repos)
# ... use AskUserQuestion tool here ...

# 7. Initialize with selections
initialize_workspace "$WORKSPACE_LOGIN" "$WORKSPACE_TYPE" "$DEFAULT_PROJECT" "$PROJECT_NUMBERS" "$REPO_NAMES"
```

---

## Prerequisites

**REQUIRED:** Run `hiivmind-pulse-gh-user-init` first.

| Requirement | Check |
|-------------|-------|
| user.yaml exists | `check_workspace_prerequisites` verifies this |
| gh CLI authenticated | `check_workspace_prerequisites` verifies this |
| jq installed | `check_workspace_prerequisites` verifies this |
| yq installed | `check_workspace_prerequisites` verifies this |

---

## Process Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. SOURCE       →  2. CHECK        →  3. DETECT      →  4. DISCOVER       │
│     (functions)      (prerequisites)    (workspace)       (projects/repos) │
│                                                                             │
│  5. SELECT       →  6. GENERATE     →  7. ENRICH      →  8. SUMMARY        │
│     (ask user)       (config.yaml)      (permissions)     (display)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Implementation

### Step 1: Source Functions

```bash
# Source workspace functions (includes project functions)
source lib/github/gh-workspace-functions.sh
```

This provides all the functions needed for workspace initialization.

### Step 2: Check Prerequisites

```bash
if ! check_workspace_prerequisites; then
    echo "Fix the issues above before continuing."
    exit 1
fi
```

This checks:
- `gh` CLI is installed and authenticated
- `jq` and `yq` are installed
- `.hiivmind/github/user.yaml` exists (from user-init)

### Step 3: Check Existing Config

```bash
if config_exists; then
    echo "Workspace already initialized at .hiivmind/github/config.yaml"
    echo "To reinitialize, remove the file first."
    echo "To update, use hiivmind-pulse-gh-workspace-refresh."
    exit 0
fi
```

### Step 4: Detect Workspace

```bash
# Auto-detect from git remote
WORKSPACE_LOGIN=$(detect_workspace_from_remote)

# Determine if org or user
WORKSPACE_TYPE=$(get_workspace_type "$WORKSPACE_LOGIN")

echo "Workspace: $WORKSPACE_LOGIN ($WORKSPACE_TYPE)"
```

**Alternative: Ask user directly if detection fails:**
```bash
# If auto-detect fails, ask user
if [[ -z "$WORKSPACE_LOGIN" ]]; then
    # Use AskUserQuestion tool to get workspace login
fi
```

### Step 5: Discover Projects

```bash
# Discover all projects
PROJECTS=$(discover_projects "$WORKSPACE_LOGIN" "$WORKSPACE_TYPE")

# Display for user
echo "Found projects:"
echo "$PROJECTS" | format_projects_list
```

**Output:**
```
Found projects:
  #1 - Bug Tracker [open]
  #2 - Feature Planner [open]
  #3 - Archive [closed]
```

### Step 6: Select Projects and Repos

Ask the user which projects and repositories to include:

**Questions to ask:**
1. Which projects to include? (default: all open)
2. Which project should be the default?
3. Which repositories to include? (options: all, current repo only, select)

**Default behavior:**
- Include all **open** projects
- Set the **lowest-numbered open project** as default
- Include **current repository only** (detected from git remote)

### Step 7: Initialize Workspace

Use the main workflow function:

```bash
# Example with user selections:
# - Projects: 1 and 2
# - Default: 2
# - Repos: just hiivmind-pulse-gh

initialize_workspace \
    "$WORKSPACE_LOGIN" \
    "$WORKSPACE_TYPE" \
    "2" \
    "1 2" \
    "hiivmind-pulse-gh"
```

This function:
1. Fetches workspace ID
2. Creates `.hiivmind/github/` directory
3. Generates `config.yaml` with all project fields
4. Enriches `user.yaml` with permissions
5. Prints summary

---

## Available Functions Reference

### Prerequisite Checks

| Function | Description |
|----------|-------------|
| `check_workspace_prerequisites` | Check all requirements, return 0 if OK |
| `config_exists` | Return 0 if config.yaml exists |

### Workspace Detection

| Function | Description |
|----------|-------------|
| `detect_workspace_from_remote` | Extract owner from git remote origin |
| `get_workspace_type LOGIN` | Return "organization" or "user" |
| `get_workspace_id LOGIN TYPE` | Get GraphQL node ID |

### Discovery

| Function | Description |
|----------|-------------|
| `discover_projects LOGIN TYPE` | List all projects (JSON array) |
| `fetch_project_with_fields NUM LOGIN TYPE` | Get project with all fields |
| `discover_repositories LOGIN TYPE` | List all repositories |
| `get_repository_info FULL_NAME` | Get single repo info |

### Permissions

| Function | Description |
|----------|-------------|
| `get_org_role ORG USER` | Get user's org role |
| `get_repo_permission REPO USER` | Get user's repo permission |

### Config Generation

| Function | Description |
|----------|-------------|
| `generate_config_yaml LOGIN TYPE ID DEFAULT PROJECTS REPOS` | Output complete config.yaml |
| `generate_project_config NUM LOGIN TYPE` | Output single project YAML |
| `transform_fields_to_yaml` | Transform fields JSON to YAML (stdin) |
| `enrich_user_permissions LOGIN TYPE PROJECTS REPOS` | Update user.yaml permissions |

### Display

| Function | Description |
|----------|-------------|
| `format_projects_list` | Format projects for display (stdin) |
| `format_repos_list` | Format repos for display (stdin) |
| `print_workspace_summary LOGIN TYPE PROJ_COUNT REPO_COUNT` | Show final summary |

### Main Workflow

| Function | Description |
|----------|-------------|
| `initialize_workspace LOGIN TYPE DEFAULT PROJECTS REPOS` | Complete initialization |

---

## Output Files

### config.yaml (Shared)

Generated at `.hiivmind/github/config.yaml`:

```yaml
workspace:
  type: organization
  login: hiivmind
  id: O_kgDOxxxxxxx

projects:
  default: 2
  catalog:
    - number: 1
      id: PVT_kwDOxxxxxxx
      title: Bug Tracker
      url: https://github.com/orgs/hiivmind/projects/1
      fields:
        Status:
          id: PVTSSF_xxxxxxx
          type: single_select
          options:
            Backlog: abc123
            In Progress: def456
            Done: ghi789
        # ... more fields ...

repositories:
  - name: hiivmind-pulse-gh
    id: R_kgDOxxxxxxx
    full_name: hiivmind/hiivmind-pulse-gh
    default_branch: main
    visibility: private

cache:
  initialized_at: "2025-12-09T10:00:00Z"
  last_synced_at: "2025-12-09T10:00:00Z"
```

**Commit this file** to share with your team.

### user.yaml (Enriched)

Updated at `.hiivmind/github/user.yaml`:

```yaml
user:
  login: discreteds
  id: U_kgDOxxxxxxx
  name: Nathaniel Ramm

permissions:           # ← Added by workspace-init
  org_role: admin
  project_roles:
    "1": admin
    "2": admin
  repo_roles:
    hiivmind-pulse-gh: admin

cache:
  user_checked_at: "2025-12-09T09:00:00Z"
  permissions_checked_at: "2025-12-09T10:00:00Z"  # ← Updated
```

**Keep this in .gitignore** - contains personal identity.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "user.yaml not found" | user-init not run | Run `hiivmind-pulse-gh-user-init` first |
| "Cannot access organization" | No membership | Check `gh auth status` and org membership |
| "No projects found" | No projects or no access | Create a project or check permissions |
| "config.yaml exists" | Already initialized | Remove file or use workspace-refresh |

---

## Multi-Repository Setup

Share config across repositories with symlinks:

```bash
# Create centralized config
mkdir -p ~/workspaces/hiivmind/.hiivmind/github
cd ~/workspaces/hiivmind
source lib/github/gh-workspace-functions.sh
initialize_workspace "hiivmind" "organization" "2" "1 2" "repo1 repo2"

# Link from each repo
cd ~/projects/repo1
ln -s ~/workspaces/hiivmind/.hiivmind .hiivmind

cd ~/projects/repo2
ln -s ~/workspaces/hiivmind/.hiivmind .hiivmind
```

---

## Templates

The `generate_config_yaml` function uses the template at `templates/config.yaml.template`.

The template defines the expected structure:
```yaml
workspace:
  type: {{workspace_type}}
  login: {{workspace_login}}
  id: null

projects:
  default: null
  catalog: []

repositories: []

milestones: {}

cache:
  initialized_at: {{initialized_at}}
  last_synced_at: null
  toolkit_version: {{toolkit_version}}
```

Placeholders (`{{...}}`) are substituted during generation. Arrays are populated dynamically.

If you need to modify the config.yaml structure, update the template first.

---

## Reference

- **Functions library:** `lib/github/gh-workspace-functions.sh`
- **Template:** `templates/config.yaml.template`
- **jq filters:** `lib/github/gh-project-jq-filters.yaml` (workspace_filters section)
- **Refresh workspace:** `skills/hiivmind-pulse-gh-workspace-refresh/SKILL.md`
