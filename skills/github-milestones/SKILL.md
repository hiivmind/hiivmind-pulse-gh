---
name: hiivmind-github-milestones
description: Manage GitHub milestones using GraphQL and REST APIs. Use when querying repository milestones, setting milestones on issues/PRs, or creating/updating/closing milestones.
---

# GitHub Milestones Skill

You are an expert at using hiivmind-github-skills' Milestones module - for managing repository-level milestones via GraphQL queries and REST API mutations.

## Important Concepts

**Milestones are repository-level entities**, not ProjectV2 entities:
- They belong to repositories, not projects
- They can be assigned to Issues and Pull Requests
- In Projects, `ProjectV2ItemFieldMilestoneValue` is **read-only** - it reflects the milestone on the underlying issue/PR
- To set milestones, use `updateIssue` or `updatePullRequest` mutations

## Prerequisites

```bash
# Source both function files
source lib/github/gh-project-functions.sh  # GraphQL functions
source lib/github/gh-rest-functions.sh     # REST functions
```

## Workspace Configuration

If a `.hiivmind/github/config.yaml` file exists in the repository root, use it to simplify commands:

```bash
CONFIG_PATH=".hiivmind/github/config.yaml"

if [[ -f "$CONFIG_PATH" ]]; then
    # Load workspace context
    ORG=$(yq '.workspace.login' "$CONFIG_PATH")

    # Get cached repository info
    get_repo_id() {
        local repo_name="$1"
        yq ".repositories[] | select(.name == \"$repo_name\") | .id" "$CONFIG_PATH"
    }

    # Get cached milestone ID
    get_cached_milestone_id() {
        local repo_name="$1"
        local milestone_title="$2"
        yq ".milestones.${repo_name}[] | select(.title == \"$milestone_title\") | .id" "$CONFIG_PATH"
    }
fi
```

### With Config (Simplified)

```bash
# List milestones using org from config
list_milestones "$ORG" "api" | format_milestones

# Get cached milestone ID
MILESTONE_ID=$(get_cached_milestone_id "api" "v1.0")
set_issue_milestone "$ISSUE_ID" "$MILESTONE_ID"
```

### Without Config (Explicit)

```bash
# Must specify owner explicitly
list_milestones "acme-corp" "api" | format_milestones

# Must look up milestone ID
MILESTONE_ID=$(get_milestone_id "acme-corp" "api" "v1.0")
set_issue_milestone "$ISSUE_ID" "$MILESTONE_ID"
```

### Setup Workspace

To create a workspace configuration:
1. Run `hiivmind-github-workspace-init` to create and populate `.hiivmind/github/config.yaml`
2. Commit `config.yaml` to share with team

## Function Reference

### GraphQL Functions (Queries)

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_repo_milestones "OWNER" "REPO"` | List milestones | `fetch_repo_milestones "acme" "api"` |
| `fetch_milestone "OWNER" "REPO" NUM` | Get specific milestone | `fetch_milestone "acme" "api" 3` |
| `get_milestone_id "OWNER" "REPO" "TITLE"` | Get ID by title | `get_milestone_id "acme" "api" "v1.0"` |

### GraphQL Functions (Setting on Issues/PRs)

| Function | Purpose | Example |
|----------|---------|---------|
| `set_issue_milestone "ISSUE_ID" "MILESTONE_ID"` | Set on issue | `set_issue_milestone "I_xxx" "MI_xxx"` |
| `set_pr_milestone "PR_ID" "MILESTONE_ID"` | Set on PR | `set_pr_milestone "PR_xxx" "MI_xxx"` |
| `clear_issue_milestone "ISSUE_ID"` | Remove from issue | `clear_issue_milestone "I_xxx"` |
| `clear_pr_milestone "PR_ID"` | Remove from PR | `clear_pr_milestone "PR_xxx"` |

### REST Functions (Create/Update/Close)

These functions require `source lib/github/gh-rest-functions.sh`:

| Function | Purpose | Example |
|----------|---------|---------|
| `list_milestones "OWNER" "REPO"` | List (REST) | `list_milestones "acme" "api"` |
| `get_milestone "OWNER" "REPO" NUM` | Get (REST) | `get_milestone "acme" "api" 3` |
| `create_milestone "OWNER" "REPO" "TITLE"` | Create new | `create_milestone "acme" "api" "v2.0"` |
| `update_milestone "OWNER" "REPO" NUM` | Update | `update_milestone "acme" "api" 3 "New Title"` |
| `close_milestone "OWNER" "REPO" NUM` | Close | `close_milestone "acme" "api" 3` |
| `reopen_milestone "OWNER" "REPO" NUM` | Reopen | `reopen_milestone "acme" "api" 3` |

### REST Helper Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `get_milestone_number_by_title "OWNER" "REPO" "TITLE"` | Find by title | `get_milestone_number_by_title "acme" "api" "v1.0"` |
| `get_milestone_progress "OWNER" "REPO" NUM` | Progress stats | `get_milestone_progress "acme" "api" 3` |
| `format_milestones` | Format output | `list_milestones "acme" "api" \| format_milestones` |

## Common Workflows

### List Repository Milestones

```bash
source lib/github/gh-rest-functions.sh

# List open milestones
list_milestones "acme" "api" "open"

# List all milestones with formatting
list_milestones "acme" "api" "all" | format_milestones

# Check milestone progress
get_milestone_progress "acme" "api" 3
```

### Create a New Milestone

```bash
source lib/github/gh-rest-functions.sh

# Basic milestone
create_milestone "acme" "api" "v2.0"

# With description and due date
create_milestone "acme" "api" "v2.0" "Q1 Release" "2025-03-31T00:00:00Z"
```

### Set Milestone on an Issue

```bash
source lib/github/gh-project-functions.sh

# Get the milestone ID
milestone_id=$(get_milestone_id "acme" "api" "v2.0")

# Set on an issue (need issue node ID)
set_issue_milestone "I_kwDOAxxx" "$milestone_id"
```

### Bulk Update Milestones from Project

```bash
source lib/github/gh-project-functions.sh

# Get project items, find issues, set milestones
project_data=$(fetch_org_project 2 "acme")

# Extract issue IDs and set milestone
echo "$project_data" | jq -r '.data.organization.projectV2.items.nodes[].content.id' | while read issue_id; do
    [[ -n "$issue_id" ]] && set_issue_milestone "$issue_id" "MI_xxx"
done
```

### Close Completed Milestone

```bash
source lib/github/gh-rest-functions.sh

# Check progress first
get_milestone_progress "acme" "api" 3

# Close if complete
close_milestone "acme" "api" 3
```

## API Differences

### GraphQL vs REST for Milestones

| Operation | GraphQL | REST |
|-----------|---------|------|
| List milestones | `fetch_repo_milestones` | `list_milestones` |
| Get milestone | `fetch_milestone` | `get_milestone` |
| Create milestone | N/A | `create_milestone` |
| Update milestone | N/A | `update_milestone` |
| Close milestone | N/A | `close_milestone` |
| Set on issue | `set_issue_milestone` | N/A |
| Set on PR | `set_pr_milestone` | N/A |

**Why both?** GitHub's GraphQL API doesn't have mutations for creating/updating milestones - only REST API supports that. But setting milestones on issues/PRs is done via GraphQL mutations.

## Output Formats

### GraphQL Milestone Query
```json
{
  "data": {
    "repository": {
      "milestones": {
        "nodes": [
          {
            "id": "MI_xxx",
            "number": 3,
            "title": "v2.0",
            "state": "OPEN",
            "dueOn": "2025-03-31T00:00:00Z",
            "progressPercentage": 45
          }
        ]
      }
    }
  }
}
```

### REST Milestone (formatted)
```json
{
  "number": 3,
  "title": "v2.0",
  "state": "open",
  "dueOn": "2025-03-31T00:00:00Z",
  "openIssues": 5,
  "closedIssues": 4,
  "progress": "44%"
}
```

## Related Skills

- **github-projects** - Project management (status updates, views, fields)
- **github-branch-protection** - Branch protection rules and rulesets
