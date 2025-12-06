---
name: github-projects-explorer
description: Explore and analyze GitHub Projects v2 using pipeline-based bash functions. Use when working with GitHub project boards, filtering project items, analyzing team workloads, or querying project data via GraphQL.
---

# GitHub Projects Explorer Skill

You are an expert at using the GitHub Projects Explorer system - a pipeline-based toolkit for querying, filtering, and analyzing GitHub Projects v2 data via the GraphQL API.

## Prerequisites

Before using these functions, ensure:
- **GitHub CLI** (`gh`) is installed and authenticated
- **jq** (1.6+) is installed for JSON processing
- **yq** (4.0+) is installed for YAML processing
- Functions are sourced: `source lib/github/gh-project-functions.sh`

## Core Architecture

The system follows a 4-layer pipeline architecture:
1. **GraphQL Query Layer** - YAML templates for API queries
2. **Bash Function Pipeline** - Pipeable functions for data fetching/filtering
3. **jq Filter Templates** - YAML-driven JSON transformations
4. **Output Layer** - Structured JSON for LLM interpretation

**Key Principle**: All functions read from stdin and write to stdout. Compose with Unix pipes.

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
| `apply_universal_filter "REPO" "USER" "STATUS" "PRIORITY"` | Multi-criteria filter (use "" to skip) | `apply_universal_filter "api" "john" "Backlog" ""` |
| `apply_assignee_filter "USER"` | Filter by assignee | `apply_assignee_filter "john"` |
| `apply_repo_filter "REPO"` | Filter by repository | `apply_repo_filter "frontend"` |
| `apply_status_filter "STATUS"` | Filter by status | `apply_status_filter "In Progress"` |

### Discovery

| Function | Purpose | Example |
|----------|---------|---------|
| `list_assignees` | List all assignees in project | `fetch_org_project 2 "org" \| list_assignees` |
| `list_repositories` | List all repositories | `fetch_org_project 2 "org" \| list_repositories` |
| `list_statuses` | List all status values | `fetch_org_project 2 "org" \| list_statuses` |
| `list_priorities` | List all priority values | `fetch_org_project 2 "org" \| list_priorities` |
| `list_fields` | List project field structure | `fetch_org_project_fields 2 "org" \| list_fields` |

### Project Discovery

| Function | Purpose | Example |
|----------|---------|---------|
| `discover_user_projects` | Find user's projects | `discover_user_projects \| format_user_projects` |
| `discover_org_projects "ORG"` | Find org projects | `discover_org_projects "acme" \| format_org_projects "acme"` |
| `discover_repo_projects "OWNER" "REPO"` | Find repo projects | `discover_repo_projects "acme" "api"` |
| `discover_all_projects` | Find all accessible projects | `discover_all_projects \| format_all_projects` |

### Output Utilities

| Function | Purpose | Example |
|----------|---------|---------|
| `get_count` | Extract filtered item count | `... \| apply_assignee_filter "john" \| get_count` |
| `get_items` | Extract items array | `... \| apply_status_filter "Done" \| get_items` |

## Common Workflows

### 1. Project Dashboard

```bash
source lib/github/gh-project-functions.sh

# Get full project overview
fetch_org_project 2 "my-org" | apply_universal_filter "" "" "" ""
```

**Output Structure**:
```json
{
  "project": "Project Name",
  "description": "...",
  "totalItems": 118,
  "filters": {"repository": "", "assignee": "", "status": "", "priority": ""},
  "filteredItems": [...],
  "filteredCount": 118
}
```

### 2. Team Workload Analysis

```bash
source lib/github/gh-project-functions.sh

# List team members
fetch_org_project 2 "my-org" | list_assignees

# Count items per assignee
fetch_org_project 2 "my-org" | apply_assignee_filter "john" | get_count

# Find assignee's backlog
fetch_org_project 2 "my-org" | apply_universal_filter "" "john" "Backlog" ""
```

### 3. Repository Focus

```bash
source lib/github/gh-project-functions.sh

# List all repositories in project
fetch_org_project 2 "my-org" | list_repositories

# Analyze specific repository
fetch_org_project 2 "my-org" | apply_repo_filter "frontend-app"

# Find who's working on a repo
fetch_org_project 2 "my-org" | apply_repo_filter "frontend-app" | list_assignees
```

### 4. Status Flow Analysis

```bash
source lib/github/gh-project-functions.sh

# See all statuses
fetch_org_project 2 "my-org" | list_statuses

# Count items by status
for status in "Backlog" "In Progress" "Done"; do
  count=$(fetch_org_project 2 "my-org" | apply_status_filter "$status" | get_count)
  echo "$status: $count"
done

# Find blocked high-priority items
fetch_org_project 2 "my-org" | apply_universal_filter "" "" "Blocked" "P0"
```

### 5. Project Discovery

```bash
source lib/github/gh-project-functions.sh

# Find all projects you have access to
discover_all_projects | format_all_projects

# Find organization's projects
discover_org_projects "acme-corp" | format_org_projects "acme-corp"

# Find projects linked to a repository
discover_repo_projects "acme-corp" "api-service" | format_repo_projects "acme-corp" "api-service"
```

### 6. Field Structure Inspection

```bash
source lib/github/gh-project-functions.sh

# Inspect project fields (custom fields, iterations, etc.)
fetch_org_project_fields 2 "my-org" | list_fields
```

## Pipeline Patterns

### Chaining Filters

```bash
# Multiple filters via chaining
fetch_org_project 2 "org" | apply_repo_filter "api" | apply_assignee_filter "john"

# Or use universal filter for efficiency
fetch_org_project 2 "org" | apply_universal_filter "api" "john" "" ""
```

### Discovery on Filtered Data

```bash
# Find which repos a user works on
fetch_org_project 2 "org" | apply_assignee_filter "john" | list_repositories

# Find who works on backlog items
fetch_org_project 2 "org" | apply_status_filter "Backlog" | list_assignees
```

### Count Analysis

```bash
# Get counts for multiple criteria
source lib/github/gh-project-functions.sh
project_data=$(fetch_org_project 2 "my-org")

echo "Total: $(echo "$project_data" | apply_universal_filter "" "" "" "" | get_count)"
echo "Backlog: $(echo "$project_data" | apply_status_filter "Backlog" | get_count)"
echo "P0 items: $(echo "$project_data" | apply_universal_filter "" "" "" "P0" | get_count)"
```

## Output Formats

All functions return structured JSON optimized for LLM interpretation:

### Filtered Result
```json
{
  "project": "My Project",
  "description": "Project description",
  "status": false,
  "created": "2024-03-19T04:57:16Z",
  "updated": "2025-07-31T22:43:05Z",
  "totalItems": 118,
  "filters": {
    "repository": "api",
    "assignee": "john",
    "status": "",
    "priority": ""
  },
  "filteredItems": [
    {
      "title": "Fix login bug",
      "type": "ISSUE",
      "status": "In Progress",
      "priority": "P1",
      "assignees": ["john"],
      "repository": "api",
      "labels": ["bug", "auth"]
    }
  ],
  "filteredCount": 15
}
```

### Discovery Result
```json
{
  "project": "My Project",
  "assignees": ["john", "jane", "bob"]
}
```

### Project List
```json
{
  "context": "organization",
  "organization": "acme-corp",
  "projects": [
    {
      "number": 2,
      "title": "Q4 Roadmap",
      "items": 118,
      "url": "https://github.com/orgs/acme-corp/projects/2"
    }
  ]
}
```

## Important Notes

### Pipeline Safety
- All functions use process substitution to avoid shell escaping issues
- No temporary files - streaming data processing
- Memory efficient for large projects

### Filter Empty String Logic
The universal filter uses empty strings to skip criteria:
```bash
# Filter by repo only
apply_universal_filter "api" "" "" ""

# Filter by assignee and status
apply_universal_filter "" "john" "Backlog" ""

# All filters
apply_universal_filter "api" "john" "Backlog" "P1"
```

### Error Handling
- Functions fail silently on API errors - check `gh` authentication
- Invalid filter values return empty results (filteredCount: 0)
- Use `list_*` functions first to discover valid filter values

### Performance
- Single GraphQL API call per fetch operation
- Filtering happens client-side via jq (efficient for <1000 items)
- Use universal filter instead of chaining for multiple criteria

## Troubleshooting

### "command not found: gh"
Install GitHub CLI: `brew install gh` or see https://cli.github.com/

### "command not found: yq"
Install yq: `brew install yq` or `pip install yq`

### Empty results
1. Check filter values with `list_*` functions
2. Verify project number and org name
3. Ensure `gh auth status` shows authenticated

### Permission errors
Ensure your GitHub token has `read:project` scope:
```bash
gh auth refresh -s read:project
```
