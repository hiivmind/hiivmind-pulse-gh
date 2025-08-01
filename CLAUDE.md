# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Overview

This is the **GitHub Projects Explorer System** - a modular, pipeline-based architecture for querying, filtering, and presenting GitHub Projects v2 data.
The system provides flexible project analytics and reporting capabilities optimized for Claude Code command usage.
It is intended to act like a virtual CLI tool for managing GitHub Projects.

### Core Architecture

The system follows a 4-layer pipeline architecture:

1. **GraphQL Query Layer** (`.hiivmind/github-projects-graphql-queries.yaml`)
2. **Bash Function Pipeline** (`.hiivmind/gh-project-functions.sh`)
3. **jq Filter Templates** (`.hiivmind/github-projects-jq-filters.yaml`)
4. **Command Interface** (`.claude/commands/*.md`)

## Key Commands

### Primary Command
- **Source functions first**: `source .hiivmind/gh-project-functions.sh`
- **Basic dashboard**: `fetch_org_project PROJECT_NUM "ORG_NAME" | apply_universal_filter "REPO" "ASSIGNEE" "STATUS" "PRIORITY"`
- **User project**: `fetch_user_project PROJECT_NUM | apply_assignee_filter "USERNAME"`

### Discovery Commands
- **Organization discovery**: `discover_org_projects "ORG_NAME" | format_org_projects "ORG_NAME"`
- **User discovery**: `discover_user_projects | format_user_projects`
- **Repository discovery**: `discover_repo_projects "OWNER" "REPO_NAME" | format_repo_projects "OWNER" "REPO_NAME"`
- **All projects**: `discover_all_projects | format_all_projects`

### Analysis Commands
- **List repositories**: `fetch_org_project PROJECT_NUM "ORG_NAME" | list_repositories`
- **List assignees**: `fetch_org_project PROJECT_NUM "ORG_NAME" | list_assignees`
- **List statuses**: `fetch_org_project PROJECT_NUM "ORG_NAME" | list_statuses`
- **List priorities**: `fetch_org_project PROJECT_NUM "ORG_NAME" | list_priorities`

### Available Filter Functions
- `apply_universal_filter "REPO" "ASSIGNEE" "STATUS" "PRIORITY"` - Apply all filters (use "" to skip)
- `apply_assignee_filter "USERNAME"` - Filter by assignee
- `apply_repo_filter "REPO_NAME"` - Filter by repository
- `apply_status_filter "STATUS"` - Filter by status
- `get_count` - Extract filtered count
- `get_items` - Extract items array

## File Structure

```
hiivmind-github-projects/
├── .claude/commands/           # Command documentation
│   ├── hv-gh-project-explorer.md
│   ├── hv-gh-project-discover.md
├── .hiivmind/                  # Core implementation
│   ├── gh-project-functions.sh          # Pipeable bash functions
│   ├── github-projects-graphql-queries.yaml  # GraphQL templates
│   └── github-projects-jq-filters.yaml       # jq filter templates
└── hv-gh-project-system-architecture.md      # System documentation
```

## Development Patterns

### Pipeline Architecture
All functions follow Unix pipe principles:
- Read from stdin, write to stdout
- No temporary files - streaming data processing
- Composable with pipe operators
- Memory efficient

### Command Substitution Safety
**ALWAYS** use the bash functions instead of direct command substitution:
- ✅ `fetch_org_project 2 "mountainash-io" | apply_assignee_filter "user"`
- ❌ `gh api graphql -f query="$(yq '.item_queries...' ...)"` (shell escaping issues)

### Template-Driven Configuration
- GraphQL queries centralized in YAML templates
- jq filters defined with parameters and descriptions
- Process substitution handles YAML extraction safely: `jq -f <(yq '.path' file.yaml)`

## Working Examples

### Organization Project Analysis
```bash
# Source functions once per session
source .hiivmind/gh-project-functions.sh

# Basic dashboard with all items
fetch_org_project 2 "mountainash-io" | apply_universal_filter "" "" "" ""

# Filter by assignee and repository
fetch_org_project 2 "mountainash-io" | apply_repo_filter "mountainash-settings" | apply_assignee_filter "discreteds"

# Get count only
fetch_org_project 2 "mountainash-io" | apply_assignee_filter "discreteds" | get_count
```

### Discovery Workflow
```bash
# Discover available repositories
fetch_org_project 2 "mountainash-io" | list_repositories

# Find assignees in specific repository
fetch_org_project 2 "mountainash-io" | apply_repo_filter "mountainash-settings" | list_assignees

# Get status breakdown
fetch_org_project 2 "mountainash-io" | list_statuses
```

## Dependencies

- **GitHub CLI**: `gh` command with authentication
- **jq**: JSON processing
- **yq**: YAML processing
- **Bash**: Process substitution support

## Output Format

All commands return structured JSON for LLM interpretation:
```json
{
  "project": "Project Name",
  "description": "Project description",
  "totalItems": 118,
  "filters": {...},
  "filteredItems": [...],
  "filteredCount": 30
}
```

## Performance Notes

- **Single API Call**: GraphQL queries fetch complete datasets efficiently
- **Streaming Processing**: No intermediate files, memory-efficient pipelines
- **Template Caching**: YAML templates loaded once per function call
- **Conditional Filtering**: Empty string parameters skip filters dynamically

## Command Interface

The `.claude/commands/` directory contains detailed documentation for each command:
- `hv-gh-project-explorer.md` - Project explorer functionality
- `hv-gh-project-discover.md` - Discovery operations

These files provide comprehensive examples, parameter references, and LLM implementation patterns for each command type.
