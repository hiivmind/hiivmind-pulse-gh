---
name: hiivmind-github-projects
description: >
  GitHub Projects v2 management via GraphQL. Use for: checking if a repo is attached/linked/connected to a project,
  finding which projects a repository belongs to or is part of, discovering what project board a repo is on,
  checking project membership or association, seeing if a repo is tracked in a project or kanban board.
  Also handles: filtering project items by assignee/status/priority, managing status updates (on track/at risk),
  creating and managing project views (table/board/roadmap), field management, adding/removing issues and PRs,
  linking/unlinking repositories, project README content, and discovering all projects in an org or for a user.
---

# GitHub Projects Skill

You are an expert at using hiivmind-github-skills' Projects module - a pipeline-based toolkit for querying, filtering, and managing GitHub Projects v2 data via the GraphQL API.

## Prerequisites

Before using these functions, ensure:
- **GitHub CLI** (`gh`) is installed and authenticated
- **jq** (1.6+) is installed for JSON processing
- **yq** (4.0+) is installed for YAML processing
- Functions are sourced: `source lib/github/gh-project-functions.sh`

## Workspace Configuration

If a `.hiivmind/github/config.yaml` file exists in the repository root, use it to simplify commands:

```bash
CONFIG_PATH=".hiivmind/github/config.yaml"

if [[ -f "$CONFIG_PATH" ]]; then
    # Load workspace context
    ORG=$(yq '.workspace.login' "$CONFIG_PATH")
    WORKSPACE_TYPE=$(yq '.workspace.type' "$CONFIG_PATH")
    DEFAULT_PROJECT=$(yq '.projects.default' "$CONFIG_PATH")

    # Get cached project ID
    PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $DEFAULT_PROJECT) | .id" "$CONFIG_PATH")

    # Get cached field IDs
    STATUS_FIELD_ID=$(yq ".projects.catalog[] | select(.number == $DEFAULT_PROJECT) | .fields.Status.id" "$CONFIG_PATH")

    # Get cached option IDs
    get_status_option_id() {
        local status_name="$1"
        yq ".projects.catalog[] | select(.number == $DEFAULT_PROJECT) | .fields.Status.options.\"${status_name}\"" "$CONFIG_PATH"
    }
fi
```

### With Config (Simplified)

```bash
# Fetch default project (org/number from config)
fetch_org_project "$DEFAULT_PROJECT" "$ORG" | apply_universal_filter "" "" "" ""

# Update item status using cached option ID
OPTION_ID=$(get_status_option_id "In Progress")
update_item_single_select "$PROJECT_ID" "$ITEM_ID" "$STATUS_FIELD_ID" "$OPTION_ID"
```

### Without Config (Explicit)

```bash
# Must specify org and project number
fetch_org_project 2 "acme-corp" | apply_universal_filter "" "" "" ""

# Must look up IDs manually
PROJECT_ID=$(get_org_project_id 2 "acme-corp")
FIELD_ID=$(get_field_id "$PROJECT_ID" "Status")
OPTION_ID=$(get_option_id "$PROJECT_ID" "Status" "In Progress")
update_item_single_select "$PROJECT_ID" "$ITEM_ID" "$FIELD_ID" "$OPTION_ID"
```

### Setup Workspace

To create a workspace configuration:
1. Run `hiivmind-github-workspace-init` to create and populate `.hiivmind/github/config.yaml`
2. Commit `config.yaml` to share with team

## Quick Start

```bash
# Source functions (once per session)
source lib/github/gh-project-functions.sh

# Fetch and display all items from an org project
fetch_org_project 2 "my-org" | apply_universal_filter "" "" "" ""

# Fetch user project
fetch_user_project 1 | apply_universal_filter "" "" "" ""
```

## Function Reference

### Data Fetching

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_org_project NUM "ORG"` | Fetch organization project | `fetch_org_project 2 "acme-corp"` |
| `fetch_user_project NUM` | Fetch user's project | `fetch_user_project 1` |
| `fetch_org_project_fields NUM "ORG"` | Get project field structure | `fetch_org_project_fields 2 "acme-corp"` |
| `fetch_user_project_fields NUM` | Get user project fields | `fetch_user_project_fields 1` |

### Filtering

| Function | Purpose | Example |
|----------|---------|---------|
| `apply_universal_filter "REPO" "USER" "STATUS" "PRIORITY"` | Multi-criteria filter | `apply_universal_filter "api" "john" "Backlog" ""` |
| `apply_assignee_filter "USER"` | Filter by assignee | `apply_assignee_filter "john"` |
| `apply_repo_filter "REPO"` | Filter by repository | `apply_repo_filter "frontend"` |
| `apply_status_filter "STATUS"` | Filter by status | `apply_status_filter "In Progress"` |

### Discovery

| Function | Purpose | Example |
|----------|---------|---------|
| `list_assignees` | List all assignees | `fetch_org_project 2 "org" \| list_assignees` |
| `list_repositories` | List all repositories | `fetch_org_project 2 "org" \| list_repositories` |
| `list_statuses` | List all status values | `fetch_org_project 2 "org" \| list_statuses` |
| `list_priorities` | List all priority values | `fetch_org_project 2 "org" \| list_priorities` |
| `list_reviewers` | List reviewers | `fetch_org_project 2 "org" \| list_reviewers` |
| `list_linked_prs` | List linked PRs | `fetch_org_project 2 "org" \| list_linked_prs` |

### Project Discovery

| Function | Purpose | Example |
|----------|---------|---------|
| `discover_user_projects` | Find user's projects | `discover_user_projects \| format_user_projects` |
| `discover_org_projects "ORG"` | Find org projects | `discover_org_projects "acme" \| format_org_projects "acme"` |
| `discover_repo_projects "OWNER" "REPO"` | Find repo projects | `discover_repo_projects "acme" "api"` |
| `discover_all_projects` | Find all accessible projects | `discover_all_projects \| format_all_projects` |

### README Management

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_project_readme "PROJECT_ID"` | Get project README | `fetch_project_readme "PVT_xxx"` |
| `update_project_readme "PROJECT_ID" "CONTENT"` | Update README | `update_project_readme "PVT_xxx" "# My Project"` |

### Status Updates

Status values: `ON_TRACK`, `AT_RISK`, `OFF_TRACK`, `COMPLETE`, `INACTIVE`

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_project_status_updates "ID"` | Get all status updates | `fetch_project_status_updates "PVT_xxx"` |
| `get_latest_status_update "ID"` | Get latest update | `get_latest_status_update "PVT_xxx"` |
| `create_status_update "ID" "STATUS" "BODY"` | Create update | `create_status_update "PVT_xxx" "ON_TRACK" "Sprint going well"` |
| `update_status_update "UPDATE_ID" "STATUS"` | Modify update | `update_status_update "PVTSU_xxx" "AT_RISK"` |

### Project Views

Layout types: `TABLE`, `BOARD`, `ROADMAP`

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_project_views "ID"` | Get all views | `fetch_project_views "PVT_xxx"` |
| `fetch_project_view "ID" NUM` | Get specific view | `fetch_project_view "PVT_xxx" 1` |
| `create_project_view "ID" "NAME" "LAYOUT"` | Create view | `create_project_view "PVT_xxx" "Sprint Board" "BOARD"` |
| `update_project_view "VIEW_ID" "NAME"` | Update view | `update_project_view "PV_xxx" "New Name"` |

### Repository Linking

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_linked_repositories "ID"` | Get linked repos | `fetch_linked_repositories "PVT_xxx"` |
| `link_repo_to_project "PROJ_ID" "REPO_ID"` | Link repository | `link_repo_to_project "PVT_xxx" "R_xxx"` |
| `unlink_repo_from_project "PROJ_ID" "REPO_ID"` | Unlink repository | `unlink_repo_from_project "PVT_xxx" "R_xxx"` |
| `get_repository_id "OWNER" "NAME"` | Get repo ID | `get_repository_id "acme" "api"` |

### Field Management

| Function | Purpose | Example |
|----------|---------|---------|
| `create_project_field "ID" "TYPE" "NAME"` | Create field | `create_project_field "PVT_xxx" "TEXT" "Notes"` |
| `update_project_field "FIELD_ID" "NAME"` | Rename field | `update_project_field "PVTF_xxx" "New Name"` |
| `add_field_option "FIELD_ID" "NAME" "COLOR"` | Add option | `add_field_option "PVTSSF_xxx" "Done" "GREEN"` |
| `update_field_option "OPT_ID" "NAME" "COLOR"` | Update option | `update_field_option "PVTSSFO_xxx" "Complete" "BLUE"` |

Colors: `GRAY`, `BLUE`, `GREEN`, `YELLOW`, `ORANGE`, `RED`, `PINK`, `PURPLE`

### Server-Side Sorting

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_user_project_sorted NUM "FIELD" "DIR"` | Sorted fetch | `fetch_user_project_sorted 1 "CREATED_AT" "DESC"` |
| `fetch_org_project_sorted NUM "ORG" "FIELD" "DIR"` | Sorted org fetch | `fetch_org_project_sorted 2 "acme" "UPDATED_AT" "ASC"` |

Order fields: `POSITION`, `CREATED_AT`, `UPDATED_AT`
Directions: `ASC`, `DESC`

### Pagination

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_user_project_page NUM "CURSOR" SIZE` | Paginated fetch | `fetch_user_project_page 1 "" 100` |
| `fetch_org_project_page NUM "ORG" "CURSOR" SIZE` | Paginated org fetch | `fetch_org_project_page 2 "acme" "" 50` |

### Item Management

| Function | Purpose | Example |
|----------|---------|---------|
| `add_issue_to_project "PROJ_ID" "ISSUE_ID"` | Add issue | `add_issue_to_project "PVT_xxx" "I_xxx"` |
| `add_pr_to_project "PROJ_ID" "PR_ID"` | Add PR | `add_pr_to_project "PVT_xxx" "PR_xxx"` |
| `create_draft_issue "PROJ_ID" "TITLE" "BODY"` | Create draft | `create_draft_issue "PVT_xxx" "New task" "Details"` |
| `update_item_field "PROJ_ID" "ITEM_ID" "FIELD_ID" "VALUE"` | Set field | `update_item_field "PVT_xxx" "PVTI_xxx" "PVTF_xxx" "P0"` |

### Output Utilities

| Function | Purpose | Example |
|----------|---------|---------|
| `get_count` | Extract filtered count | `... \| apply_assignee_filter "john" \| get_count` |
| `get_items` | Extract items array | `... \| apply_status_filter "Done" \| get_items` |

## Common Workflows

### Project Dashboard
```bash
fetch_org_project 2 "my-org" | apply_universal_filter "" "" "" ""
```

### Team Workload
```bash
fetch_org_project 2 "my-org" | list_assignees
fetch_org_project 2 "my-org" | apply_assignee_filter "john" | get_count
```

### Status Update Workflow
```bash
# Check current status
get_latest_status_update "PVT_xxx"

# Post weekly update
create_status_update "PVT_xxx" "ON_TRACK" "Sprint 5 on schedule. 80% complete."
```

### View Management
```bash
# List existing views
fetch_project_views "PVT_xxx"

# Create a sprint board
create_project_view "PVT_xxx" "Sprint Board" "BOARD"
```

## Related Skills

- **github-milestones** - Milestone management (repository-level)
- **github-branch-protection** - Branch protection rules and rulesets
