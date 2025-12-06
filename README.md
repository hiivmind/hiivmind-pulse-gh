# GitHub Projects Explorer

A Claude Code plugin for exploring, filtering, and analyzing GitHub Projects v2 data. Provides a pipeline-based toolkit with bash functions, GraphQL queries, and jq filters optimized for LLM interpretation.

## Features

- **Project Discovery**: Find projects across user, organization, and repository contexts
- **Advanced Filtering**: Filter by repository, assignee, status, priority, or any combination
- **Team Analytics**: Analyze assignee workload and repository distribution
- **Pipeline Architecture**: Composable bash functions for custom workflows
- **Memory Efficient**: Streaming data processing with no temporary files
- **LLM-Optimized**: JSON output designed for Claude Code interpretation

## Installation

### As Claude Code Plugin

```bash
# Add the marketplace
/plugin marketplace add discreteds/hiivmind-github-projects

# Install the plugin
/plugin install github-projects-explorer@github-projects-explorer
```

### Prerequisites

- **GitHub CLI (`gh`)**: Authenticated with your GitHub account
- **jq**: JSON processor (1.6+)
- **yq**: YAML processor (4.0+)
- **Bash**: With process substitution support

## Quick Start

```bash
# Source the functions (once per session)
source lib/github/gh-project-functions.sh

# Discover your projects
discover_user_projects | format_user_projects

# Analyze an organization project
fetch_org_project 2 "your-org" | apply_universal_filter "" "" "" ""

# Filter by assignee
fetch_org_project 2 "your-org" | apply_assignee_filter "username"

# List team members
fetch_org_project 2 "your-org" | list_assignees
```

## Plugin Structure

```
github-projects-explorer/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest
│   └── marketplace.json         # Marketplace manifest
├── skills/
│   └── github-projects-explorer/
│       └── SKILL.md             # Claude skill documentation
├── commands/
│   └── hiivmind/github/
│       ├── hv-gh-project-explorer.md
│       └── hv-gh-project-discover.md
├── lib/github/
│   ├── gh-project-functions.sh  # Core bash functions
│   ├── gh-project-graphql-queries.yaml
│   └── gh-project-jq-filters.yaml
├── docs/
└── README.md
```

## Function Reference

### Data Fetching

| Function | Description |
|----------|-------------|
| `fetch_org_project NUM "ORG"` | Fetch organization project data |
| `fetch_user_project NUM` | Fetch user project data |
| `fetch_org_project_fields NUM "ORG"` | Get project field structure |

### Filtering

| Function | Description |
|----------|-------------|
| `apply_universal_filter "REPO" "USER" "STATUS" "PRIORITY"` | Multi-criteria filter (use "" to skip) |
| `apply_assignee_filter "USER"` | Filter by assignee |
| `apply_repo_filter "REPO"` | Filter by repository |
| `apply_status_filter "STATUS"` | Filter by status |

### Discovery

| Function | Description |
|----------|-------------|
| `list_assignees` | List all project assignees |
| `list_repositories` | List all repositories |
| `list_statuses` | List all status values |
| `list_priorities` | List all priority values |
| `list_fields` | List project field structure |

### Project Discovery

| Function | Description |
|----------|-------------|
| `discover_user_projects` | Find user's projects |
| `discover_org_projects "ORG"` | Find organization projects |
| `discover_repo_projects "OWNER" "REPO"` | Find repository projects |
| `discover_all_projects` | Find all accessible projects |

### Utilities

| Function | Description |
|----------|-------------|
| `get_count` | Extract filtered item count |
| `get_items` | Extract items array |

## Common Workflows

### Team Workload Analysis

```bash
source lib/github/gh-project-functions.sh

# List team members
fetch_org_project 2 "acme-corp" | list_assignees

# Count items per assignee
for user in alice bob charlie; do
  count=$(fetch_org_project 2 "acme-corp" | apply_assignee_filter "$user" | get_count)
  echo "$user: $count items"
done
```

### Status Distribution

```bash
source lib/github/gh-project-functions.sh

# See all statuses
fetch_org_project 2 "acme-corp" | list_statuses

# Count by status
for status in "Backlog" "In Progress" "Done"; do
  count=$(fetch_org_project 2 "acme-corp" | apply_status_filter "$status" | get_count)
  echo "$status: $count"
done
```

### Repository Focus

```bash
source lib/github/gh-project-functions.sh

# List repositories in project
fetch_org_project 2 "acme-corp" | list_repositories

# Analyze specific repo
fetch_org_project 2 "acme-corp" | apply_repo_filter "frontend" | list_assignees
```

## Output Format

All functions return structured JSON:

```json
{
  "project": "My Project",
  "totalItems": 118,
  "filters": {
    "repository": "",
    "assignee": "john",
    "status": "",
    "priority": ""
  },
  "filteredItems": [...],
  "filteredCount": 30
}
```

## Claude Code Commands

The plugin includes slash commands:

- `/hv-gh-project-explorer` - Comprehensive project analysis with filtering
- `/hv-gh-project-discover` - Find projects across contexts

## Troubleshooting

### "gh: command not found"
Install GitHub CLI: https://cli.github.com/

### "yq: command not found"
Install yq v4+: `brew install yq` or https://github.com/mikefarah/yq

### Empty results
1. Check project number and org name
2. Verify access with `gh project list --owner ORG`
3. Use `list_*` functions to discover valid filter values

### Permission errors
Ensure token has `read:project` scope:
```bash
gh auth refresh -s read:project
```

## License

MIT

## Contributing

Contributions welcome! The system is designed to be extensible:

1. **New Filters**: Add to `lib/github/gh-project-jq-filters.yaml`
2. **New Functions**: Add to `lib/github/gh-project-functions.sh`
3. **New Queries**: Add to `lib/github/gh-project-graphql-queries.yaml`
