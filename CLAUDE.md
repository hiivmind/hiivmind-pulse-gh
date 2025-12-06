# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## System Overview

This is the **GitHub CLI Toolkit** - a Claude Code plugin providing comprehensive GitHub API operations via GraphQL and REST APIs. It includes support for:

- **GitHub Projects v2** - Full project management, status updates, views, fields
- **Milestones** - Repository-level milestone management
- **Branch Protection** - Per-branch rules and repository rulesets
- **REST API** - Operations not available via GraphQL

## Skills

The toolkit provides four domain-specific skills:

| Skill | Purpose |
|-------|---------|
| `github-projects` | Projects v2 - items, filtering, status updates, views, fields |
| `github-milestones` | Milestone queries and management |
| `github-branch-protection` | Branch protection rules and repository rulesets |
| `github-rest-api` | REST API operations (creating milestones, etc.) |

## Quick Start

```bash
# Source functions (once per session)
source lib/github/gh-project-functions.sh  # GraphQL operations
source lib/github/gh-rest-functions.sh     # REST operations

# Fetch and analyze a project
fetch_org_project 2 "org-name" | apply_universal_filter "" "" "" ""

# List milestones
list_milestones "owner" "repo" | format_milestones
```

## File Structure

```
github-cli-toolkit/
├── .claude-plugin/              # Plugin manifests
├── skills/
│   ├── github-projects/         # Projects v2 skill
│   ├── github-milestones/       # Milestones skill
│   ├── github-branch-protection/# Branch protection skill
│   └── github-rest-api/         # REST API skill
├── lib/github/
│   ├── gh-project-functions.sh      # GraphQL shell functions
│   ├── gh-project-graphql-queries.yaml  # GraphQL templates
│   ├── gh-project-jq-filters.yaml   # jq filter templates
│   ├── gh-rest-functions.sh         # REST shell functions
│   ├── gh-rest-endpoints.yaml       # REST endpoint templates
│   └── gh-branch-protection-templates.yaml  # Protection presets
└── docs/
```

## Key Function Groups

### Projects v2 (GraphQL)
- `fetch_org_project`, `fetch_user_project` - Fetch project data
- `apply_*_filter` - Filter project items
- `list_*` - Discovery functions
- `fetch_project_status_updates`, `create_status_update` - Status updates
- `fetch_project_views`, `create_project_view` - View management
- `fetch_linked_repositories`, `link_repo_to_project` - Repository linking

### Milestones (Mixed)
- `fetch_repo_milestones` - Query via GraphQL
- `set_issue_milestone`, `set_pr_milestone` - Set via GraphQL
- `create_milestone`, `update_milestone`, `close_milestone` - Manage via REST

### Branch Protection (REST)
- `get_branch_protection`, `set_branch_protection` - Per-branch rules
- `list_rulesets`, `create_ruleset`, `update_ruleset` - Repository rulesets
- `apply_main_branch_protection`, `apply_develop_branch_protection` - Smart templates
- `apply_branch_naming_ruleset` - Naming convention enforcement

### REST API
- `list_milestones`, `get_milestone` - REST queries
- `create_milestone`, `update_milestone` - REST mutations
- `detect_repo_type`, `list_branches` - Helper functions
- Direct `gh api` usage for other operations

## Pipeline Pattern

All functions read stdin, write stdout. Compose with pipes:

```bash
fetch_org_project 2 "org" | apply_assignee_filter "user" | list_repositories
```

## Dependencies

- GitHub CLI (`gh`) - authenticated with appropriate scopes
- jq (1.6+)
- yq (4.0+)
