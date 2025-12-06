# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## System Overview

This is the **GitHub Projects Explorer** - a Claude Code plugin providing pipeline-based functions for querying, filtering, and analyzing GitHub Projects v2 data via GraphQL.

## Quick Start

```bash
# Source functions (once per session)
source lib/github/gh-project-functions.sh

# Fetch and analyze a project
fetch_org_project 2 "org-name" | apply_universal_filter "" "" "" ""
```

## Key Commands

### Data Fetching
- `fetch_org_project PROJECT_NUM "ORG"` - Fetch organization project
- `fetch_user_project PROJECT_NUM` - Fetch user project

### Filtering
- `apply_universal_filter "REPO" "ASSIGNEE" "STATUS" "PRIORITY"` - Multi-filter (use "" to skip)
- `apply_assignee_filter "USER"` - Filter by assignee
- `apply_repo_filter "REPO"` - Filter by repository
- `apply_status_filter "STATUS"` - Filter by status

### Discovery
- `list_assignees` - List all assignees
- `list_repositories` - List all repositories
- `list_statuses` - List all status values
- `list_priorities` - List all priority values

### Project Discovery
- `discover_org_projects "ORG" | format_org_projects "ORG"` - Find org projects
- `discover_user_projects | format_user_projects` - Find user projects

### Output
- `get_count` - Extract filtered count
- `get_items` - Extract items array

## File Structure

```
github-projects-explorer/
├── .claude-plugin/          # Plugin manifests
├── skills/                  # Claude skills
├── commands/                # Slash commands
├── lib/github/              # Core implementation
│   ├── gh-project-functions.sh
│   ├── gh-project-graphql-queries.yaml
│   └── gh-project-jq-filters.yaml
└── docs/
```

## Pipeline Pattern

All functions read stdin, write stdout. Compose with pipes:

```bash
fetch_org_project 2 "org" | apply_assignee_filter "user" | list_repositories
```

## Dependencies

- GitHub CLI (`gh`) - authenticated
- jq (1.6+)
- yq (4.0+)
