# GitHub Projects Explorer System

A powerful command-line system for exploring, filtering, and analyzing GitHub Projects v2 data. Designed specifically for Claude Code integration, this tool provides a virtual CLI experience for managing and understanding your GitHub Projects.

## Overview

The GitHub Projects Explorer System transforms GitHub Projects v2 data into actionable insights through a modular, pipeline-based architecture. Whether you're tracking issues across repositories, monitoring team workload, or analyzing project progress, this system provides the tools you need in a Claude Code-friendly format.

### Key Features

- **🔍 Project Discovery**: Find projects across user, organization, and repository contexts
- **📊 Advanced Filtering**: Filter by repository, assignee, status, priority, or any combination
- **👥 Team Analytics**: Analyze assignee workload and repository distribution
- **🚀 Pipeline Architecture**: Composable bash functions for custom workflows
- **💾 Memory Efficient**: Streaming data processing with no temporary files
- **🤖 LLM-Optimized**: JSON output designed for Claude Code interpretation

## Quick Start

### Prerequisites

- **GitHub CLI (`gh`)**: Authenticated with your GitHub account
- **jq**: JSON processor (1.6+)
- **yq**: YAML processor (4.0+)
- **Bash**: With process substitution support

### Basic Usage

1. **Source the functions** (once per session):
```bash
source .hiivmind/gh-project-functions.sh
```

2. **Explore your projects**:
```bash
# Discover all your projects
discover_user_projects | format_user_projects

# Discover organization projects
discover_org_projects "your-org" | format_org_projects "your-org"
```

3. **Analyze a specific project**:
```bash
# Get all items from project #2
fetch_org_project 2 "your-org" | apply_universal_filter "" "" "" ""

# Filter by assignee
fetch_org_project 2 "your-org" | apply_assignee_filter "username"

# See who's working on what
fetch_org_project 2 "your-org" | list_assignees
```

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Projects API                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │ GraphQL Queries
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              gh-project-functions.sh                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Data Fetching   │  │ Filter Pipeline │  │ Discovery Tools │ │
│  │ Functions       │  │ Functions       │  │ Functions       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Bash Pipeline Processing
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    JSON Output                                  │
│          (Structured for LLM Interpretation)                    │
└─────────────────────────────────────────────────────────────────┘
```

### File Structure

```
hiivmind-github-projects/
├── README.md                           # This file
├── .claude/commands/                   # Claude Code command documentation
│   ├── hv-gh-project-explorer.md      # Main explorer command
│   └── hv-gh-project-discover.md      # Discovery command
├── .hiivmind/                         # Core implementation
│   ├── gh-project-functions.sh        # Bash pipeline functions
│   ├── gh-project-graphql-queries.yaml # GraphQL query templates
│   └── gh-project-jq-filters.yaml     # jq filter templates
└── hv-gh-project-system-architecture.md # Detailed architecture docs
```

## Function Reference

### Data Fetching Functions

| Function | Description | Example |
|----------|-------------|---------|
| `fetch_org_project PROJECT_NUM "ORG"` | Fetch organization project data | `fetch_org_project 2 "acme-corp"` |
| `fetch_user_project PROJECT_NUM` | Fetch user project data | `fetch_user_project 7` |

### Filter Functions

| Function | Description | Example |
|----------|-------------|---------|
| `apply_universal_filter "REPO" "USER" "STATUS" "PRIORITY"` | Apply multiple filters | `apply_universal_filter "" "alice" "Backlog" "P1"` |
| `apply_assignee_filter "USER"` | Filter by assignee | `apply_assignee_filter "bob"` |
| `apply_repo_filter "REPO"` | Filter by repository | `apply_repo_filter "main-app"` |
| `apply_status_filter "STATUS"` | Filter by status | `apply_status_filter "In Progress"` |

### Discovery Functions

| Function | Description | Example |
|----------|-------------|---------|
| `list_assignees` | List all project assignees | `fetch_org_project 2 "org" \| list_assignees` |
| `list_repositories` | List all repositories | `fetch_org_project 2 "org" \| list_repositories` |
| `list_statuses` | List all status values | `fetch_org_project 2 "org" \| list_statuses` |
| `list_priorities` | List all priority values | `fetch_org_project 2 "org" \| list_priorities` |

### Utility Functions

| Function | Description | Example |
|----------|-------------|---------|
| `get_count` | Extract filtered item count | `... \| apply_filter \| get_count` |
| `get_items` | Extract items array | `... \| apply_filter \| get_items` |

## Common Workflows

### 1. Project Discovery Workflow

```bash
# Find all accessible projects
source .hiivmind/gh-project-functions.sh
discover_all_projects | format_all_projects

# Extract project numbers for further analysis
discover_org_projects "acme-corp" | format_org_projects "acme-corp" | jq '.projects[].number'
```

### 2. Team Workload Analysis

```bash
# See who's assigned to what
source .hiivmind/gh-project-functions.sh
fetch_org_project 2 "acme-corp" | list_assignees

# Count items per assignee
for user in alice bob charlie; do
  count=$(fetch_org_project 2 "acme-corp" | apply_assignee_filter "$user" | get_count)
  echo "$user: $count items"
done
```

### 3. Status Flow Analysis

```bash
# Check project status distribution
source .hiivmind/gh-project-functions.sh
fetch_org_project 2 "acme-corp" | list_statuses

# Count items by status
for status in "Backlog" "In Progress" "Done"; do
  count=$(fetch_org_project 2 "acme-corp" | apply_status_filter "$status" | get_count)
  echo "$status: $count items"
done
```

### 4. Repository-Focused Analysis

```bash
# Find which repositories are in the project
source .hiivmind/gh-project-functions.sh
fetch_org_project 2 "acme-corp" | list_repositories

# Analyze a specific repository
fetch_org_project 2 "acme-corp" | apply_repo_filter "main-app" | list_assignees
```

## Deployment in Claude Code

### Option 1: Clone and Use Directly

1. Clone this repository to your local machine:
```bash
git clone https://github.com/yourusername/hiivmind-github-projects.git
cd hiivmind-github-projects
```

2. Source the functions in your Claude Code session:
```bash
source .hiivmind/gh-project-functions.sh
```

3. Start exploring your projects!

### Option 2: Add to Existing Project

1. Copy the `.hiivmind` directory to your project:
```bash
cp -r /path/to/hiivmind-github-projects/.hiivmind your-project/
```

2. (Optional) Copy the Claude command documentation:
```bash
cp -r /path/to/hiivmind-github-projects/.claude your-project/
```

3. Source and use the functions as needed.

### Option 3: Global Installation

1. Add to your shell profile (e.g., `~/.bashrc` or `~/.zshrc`):
```bash
export HIIVMIND_GH_PROJECTS="/path/to/hiivmind-github-projects"
alias gh-project-init="source $HIIVMIND_GH_PROJECTS/.hiivmind/gh-project-functions.sh"
```

2. Use `gh-project-init` in any Claude Code session to enable the functions.

## Claude Code Commands

When using Claude Code, you can leverage the built-in command documentation:

- `/hv-gh-project-explorer` - Main project exploration interface
- `/hv-gh-project-discover` - Project discovery across contexts

These commands provide a user-friendly interface that internally uses the bash functions.

## Advanced Usage

### Custom Filter Pipelines

Create complex filter chains by combining functions:

```bash
# High-priority items assigned to alice in the backend repo
fetch_org_project 2 "acme-corp" \
  | apply_repo_filter "backend" \
  | apply_assignee_filter "alice" \
  | apply_status_filter "In Progress" \
  | jq '.filteredItems[] | select(.fieldValues.nodes[] | select(.field.name == "Priority" and .name == "P1"))'
```

### Batch Processing

Process multiple projects programmatically:

```bash
# Analyze all organization projects
source .hiivmind/gh-project-functions.sh
PROJECT_NUMBERS=$(discover_org_projects "acme-corp" | format_org_projects "acme-corp" | jq -r '.projects[].number')

for num in $PROJECT_NUMBERS; do
  echo "=== Project #$num ==="
  fetch_org_project $num "acme-corp" | jq '{
    project: .project,
    total: .totalItems,
    backlog: ([.items[] | select(.fieldValues.nodes[] | select(.field.name == "Status" and .name == "Backlog"))] | length)
  }'
done
```

### Export to CSV

Convert project data to CSV format:

```bash
fetch_org_project 2 "acme-corp" | jq -r '
  ["Title", "Repository", "Assignee", "Status", "Priority"],
  (.items[] | [
    .content.title,
    .content.repository.name,
    (.content.assignees.nodes[0].login // "Unassigned"),
    (.fieldValues.nodes[] | select(.field.name == "Status") | .name) // "No Status",
    (.fieldValues.nodes[] | select(.field.name == "Priority") | .name) // "No Priority"
  ]) | @csv'
```

## Performance Considerations

- **Single API Call**: Each fetch operation makes one GraphQL query
- **Streaming Processing**: Data flows through pipes without temporary files
- **Memory Efficient**: Handles large projects through streaming architecture
- **Cache Friendly**: GitHub CLI caches authentication tokens

## Troubleshooting

### Common Issues

1. **"gh: command not found"**
   - Install GitHub CLI: https://cli.github.com/
   - Authenticate: `gh auth login`

2. **"jq: command not found"**
   - Install jq: `brew install jq` (macOS) or `apt-get install jq` (Ubuntu)

3. **"yq: command not found"**
   - Install yq: `brew install yq` (macOS) or download from https://github.com/mikefarah/yq

4. **Empty results**
   - Check project number and organization name
   - Verify you have access to the project
   - Try the discovery functions first

### Debug Mode

Enable verbose output for troubleshooting:

```bash
# See the raw GraphQL response
fetch_org_project 2 "acme-corp" | jq '.'

# Check available field values
fetch_org_project 2 "acme-corp" | jq '.items[0].fieldValues'
```

## Contributing

Contributions are welcome! The system is designed to be extensible:

1. **New Filters**: Add to `.hiivmind/gh-project-jq-filters.yaml`
2. **New Functions**: Add to `.hiivmind/gh-project-functions.sh`
3. **New Queries**: Add to `.hiivmind/gh-project-graphql-queries.yaml`

## License

This project is open source and available under the MIT License.

## Acknowledgments

Built specifically for Claude Code users who need powerful GitHub Projects analytics without leaving their development environment. Special thanks to the GitHub GraphQL API team for comprehensive Projects v2 support.