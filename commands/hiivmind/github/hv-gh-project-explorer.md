---
command: hv-gh-project-explorer
allowed-tools: Bash(source lib/:*)
description: Comprehensive GitHub Projects v2 analysis tool with filtering, discovery, field inspection, and multiple output formats using YAML template imports.
---

# GitHub Project Explorer Command
Comprehensive GitHub Projects v2 analysis tool with filtering, discovery, field inspection, and multiple output formats using YAML template imports.

**Default Behavior**: Lists all project items with summary format output. Use `--help` for additional options and related commands.

## Usage

```claude-code
/hv-gh-project-explorer <project_number> [owner] [context] [options...]
/hv-gh-project-explorer --help
```

### Command Parameters

- `project_number`: Project number (required)
- `owner`: Organization/user name (defaults to current user)
- `context`: `user` (default) or `org`

### Filtering Options

- `--assignee=USERNAME`: Filter by assignee username
- `--status=STATUS`: Filter by status (e.g., Backlog, Shipped, Ready)
- `--priority=PRIORITY`: Filter by priority (e.g., P0, P1, P2, P3)
- `--repo=REPOSITORY`: Filter by repository name

### Discovery Options
- `--list-assignees`: List all assignees in project
- `--list-repos`: List all repositories in project
- `--list-statuses`: List all status values in project
- `--list-priorities`: List all priority values in project
- `--list-fields`: Inspect project field structure and types

### Output Options

- `--format=summary`: LLM interpretation/summary of the data (default)
- `--format=json`: Structured JSON output for detailed analysis
- `--format=table`: Formatted table output
- `--limit=N`: Limit number of items listed (default: 50, max: 100)
- `--count-only`: Show only filtered item count
- `--help`: Show usage examples, available flags, and related commands

### Further Usage Examples

```claude-code
# Show help with all options and related commands
/hv-gh-project-explorer --help

# Basic project dashboard - shows all items with summary format (default behavior)
/hv-gh-project-explorer 2 my-org-name org

# Show project team assignees
/hv-gh-project-explorer 2 my-org-name org --list-assignees

# Inspect project structure
/hv-gh-project-explorer 2 my-org-name org --list-fields

# Filter by assignee with JSON output
/hv-gh-project-explorer 2 my-org-name org --assignee=my_username --format=json

# Multiple filters with count
/hv-gh-project-explorer 2 my-org-name org --assignee=my_username --status=Backlog --count-only

# Table view with limit
/hv-gh-project-explorer 2 my-org-name org --format=table --limit=20

# Focussed summary analysis
/hv-gh-project-explorer 2 my-org-name org --repo=hiivmind-mcp --assignee=my_username --format=summary

# Repository-specific analysis as a table
/hv-gh-project-explorer 2 myorg org --repo=myrepo --format=table

# Count high-priority backlog
/hv-gh-project-explorer 2 myorg org --status=Backlog --priority=P1 --count-only

```

## Help Information (--help flag)

When using `--help`, display this information instead of running any analysis:

### Quick Reference

**Basic Usage:**
```
/hv-gh-project-explorer <project_number> [owner] [context]
```

**Default Behavior:** Lists all project items with summary format. No additional flags needed for basic project overview.

### Command Parameters

- `project_number`: Project number (required)
- `owner`: Organization/user name (defaults to current user)
- `context`: `user` (default) or `org`

### All Available Flags

**Filtering Options:**
- `--assignee=USERNAME` - Filter by specific assignee
- `--status=STATUS` - Filter by status (Backlog, Ready, Shipped, etc.)
- `--priority=PRIORITY` - Filter by priority (P0, P1, P2, P3)
- `--repo=REPOSITORY` - Filter by repository name

**Discovery Options:**
- `--list-assignees` - List all team members
- `--list-repos` - List all repositories
- `--list-statuses` - List all status values
- `--list-priorities` - List all priority levels
- `--list-fields` - Inspect project field structure

**Output Options:**
- `--format=summary` - LLM summary and insights (default)
- `--format=json` - Raw structured data
- `--format=table` - Human-readable table
- `--count-only` - Show only filtered item count
- `--limit=N` - Limit number of items (max 100)
- `--help`: Show usage examples, available flags, and related commands

### Common Usage Patterns

```claude-code

```

### Related Commands

- `hv-gh-project-discover` - Find available projects across organizations

### Tips

- **Start Simple**: Use basic command first to understand project structure
- **Combine Filters**: Most flags can be used together for precise analysis
- **Use Discovery**: Try `--list-*` flags to understand available values before filtering
- **Format for Purpose**: Use `--format=summary` for insights, `--format=json` for processing, `--format=table` for viewing
- **Paramater Inference**: Parameters such as owner and project_number may be inferred from recent chat history, or set in CLAUDE.md

---

## LLM Implementation Reference

### Parameter Resolution
Ensure that command Parameters are provided or inferable from:
- User's natural language instructions
- Recent chat history
- Set in CLAUDE.md


### Core Pattern: Bash Functions with YAML Templates


**✅ PRODUCTION APPROACH**: Use bash functions that leverage YAML templates for clean, pipeable commands:

1. **Step 1**: Source the helper functions: `source lib/github/gh-project-functions.sh`
2. **Step 2**: Use pipeable functions for data fetching and processing
3. **Functions handle**: YAML template extraction, command substitution issues, and data flow

### Command Templates

#### Basic Dashboard Analysis

```bash
# Source helper functions (once per session)
source lib/github/gh-project-functions.sh

# Basic organization project analysis
fetch_org_project PROJECT_NUM "ORG_NAME" | apply_universal_filter "" "" "" ""

# User project analysis
fetch_user_project PROJECT_NUM | apply_universal_filter "" "" "" ""
```

#### Filtering Patterns

```bash
# Single filter
fetch_org_project PROJECT_NUM "ORG_NAME" | apply_assignee_filter "USERNAME"

# Multiple filters chained
fetch_org_project PROJECT_NUM "ORG_NAME" | apply_repo_filter "REPO" | apply_assignee_filter "USERNAME"

# Universal filter (most efficient for multiple criteria)
fetch_org_project PROJECT_NUM "ORG_NAME" | apply_universal_filter "REPO" "ASSIGNEE" "STATUS" "PRIORITY"
```

#### Discovery Patterns

```bash
# Show project team
fetch_org_project PROJECT_NUM "ORG_NAME" | list_assignees

# Show repositories
fetch_org_project PROJECT_NUM "ORG_NAME" | list_repositories

# Show status breakdown
fetch_org_project PROJECT_NUM "ORG_NAME" | list_statuses

# Show priority distribution
fetch_org_project PROJECT_NUM "ORG_NAME" | list_priorities
```

#### Output Formatting

```bash
# Count only
fetch_org_project PROJECT_NUM "ORG_NAME" | apply_assignee_filter "USERNAME" | get_count

# Extract items for processing
fetch_org_project PROJECT_NUM "ORG_NAME" | apply_status_filter "STATUS" | get_items

# Discovery on filtered data
fetch_org_project PROJECT_NUM "ORG_NAME" | apply_assignee_filter "USERNAME" | list_repositories
```

---

## Working Examples

### Example 1: Basic Explorer Analysis

```bash
# Source functions and fetch project data
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | apply_universal_filter "" "" "" ""
```

**Expected JSON Output:**
```json
{
  "project": "My Project",
  "description": null,
  "status": false,
  "created": "2024-03-19T04:57:16Z",
  "updated": "2025-07-31T22:43:05Z",
  "totalItems": 118,
  "filters": {
    "repository": "",
    "assignee": "",
    "status": "",
    "priority": ""
  },
  "filteredItems": [...],
  "filteredCount": 118
}
```

### Example 2: Team Discovery

```bash
# List project assignees
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | list_assignees
```

**Expected JSON Output:**
```json
{
  "project": "My Project",
  "assignees": [
    "my_username"
  ]
}
```

### Example 3: Repository Analysis

```bash
# List all repositories
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | list_repositories
```

**Expected JSON Output:**
```json
{
  "project": "My Project",
  "repositories": [
    "hiivmind",
    "hiivmind-mcp",
  ]
}
```

### Example 4: Filtered Analysis

```bash
# Filter by assignee
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | apply_assignee_filter "my_username"
```

**Expected JSON Output:**
```json
{
  "project": "My Project",
  "totalItems": 118,
  "filters": {
    "assignee": "my_username"
  },
  "filteredItems": [...],
  "filteredCount": 30
}
```

### Example 5: Status Breakdown

```bash
# Show all status values
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | list_statuses
```

**Expected JSON Output:**
```json
{
  "project": "My Project",
  "statuses": [
    "Backlog",
    "Housekeeping",
    "Ready",
    "Shipped",
    "Will not implement"
  ]
}
```

### Example 6: Complex Filtering

```bash
# Multiple criteria with universal filter
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | apply_universal_filter "hiivmind-mcp" "my_username" "Backlog" "P1"
```

### Example 7: Count Analysis

```bash
# Get filtered count only
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | apply_assignee_filter "my_username" | get_count
```

**Expected Output:**
```
30
```

### Example 8: Advanced Pipeline

```bash
# Discovery on filtered data
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | apply_assignee_filter "my_username" | list_repositories
```

---

## Flag Implementation Mapping

### Filter Flags → Function Calls

| Flag | Function Pattern | Example |
|------|------------------|---------|
| `--assignee=my_username` | `apply_assignee_filter "my_username"` | Filter by user |
| `--status=Backlog` | `apply_status_filter "Backlog"` | Filter by status |
| `--repo=hiivmind-mcp` | `apply_repo_filter "hiivmind-mcp"` | Filter by repository |
| `--priority=P1` | Universal filter with priority | Filter by priority |

### Discovery Flags → Function Calls

| Flag | Function Pattern | Purpose |
|------|------------------|---------|
| `--list-assignees` | `list_assignees` | List project team |
| `--list-repos` | `list_repositories` | List repositories |
| `--list-statuses` | `list_statuses` | List status options |
| `--list-priorities` | `list_priorities` | List priority levels |
| `--list-fields` | Field inspection function | List project schema |

### Output Flags → Processing

| Flag | Implementation | Result |
|------|----------------|--------|
| `--format=summary` | LLM interprets JSON → insights (default) | High level analysis and key findings |
| `--format=json` | Return bash function JSON directly | Structured data for processing |
| `--format=table` | LLM interprets JSON → table format | Clean, aligned table presentation |
| `--count-only` | Extract count via `get_count` | Numeric count only |
| `--limit=20` | Limit bash function processing | First N items |
| `--help` | Show help information | Usage examples and related commands |

**Key Principle**: Bash functions produce JSON → LLM handles all formatting. No jq table injection or complex shell formatting.

---

## Advanced Usage Patterns

### Multi-Step Analysis

```bash
# 1. Discover team members
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | list_assignees

# 2. Analyze each team member's work
fetch_org_project 2 "my-org-name" | apply_assignee_filter "my_username" | list_statuses

# 3. Find high-priority backlog for user
fetch_org_project 2 "my-org-name" | apply_universal_filter "" "my_username" "Backlog" "P0"
```

### Repository Focus Analysis

```bash
# 1. Find all repositories
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | list_repositories

# 2. Analyze specific repository
fetch_org_project 2 "my-org-name" | apply_repo_filter "hiivmind-mcp"

# 3. Find repository team
fetch_org_project 2 "my-org-name" | apply_repo_filter "hiivmind-mcp" | list_assignees
```

### Status Flow Analysis

```bash
# 1. Show status distribution
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org-name" | list_statuses

# 2. Count items in each status
for status in "Backlog" "Ready" "Shipped"; do
  count=$(fetch_org_project 2 "my-org-name" | apply_status_filter "$status" | get_count)
  echo "$status: $count items"
done
```

---

## Parameter Substitution Reference

### Template Variables

| Template | Replace With | Example |
|----------|--------------|---------|
| `PROJECT_NUM` | Project number | `2` |
| `ORG_NAME` | Organization login | `"my-org-name"` |
| `USERNAME` | Assignee username | `"my_username"` |
| `REPO` | Repository name | `"hiivmind-mcp"` |
| `STATUS` | Status value | `"Backlog"` |
| `PRIORITY` | Priority value | `"P1"` |

### YAML Template Paths

| Component | YAML Path |
|-----------|-----------|
| **GraphQL Queries** | `.hiivmind/github-projects-graphql-queries.yaml` |
| User project query | `.item_queries.user_project_items_full.query` |
| Org project query | `.item_queries.organization_project_items_full.query` |
| Field inspection query | `.project_structure.organization_project_fields.query` |
| **jq Filters** | `.hiivmind/github-projects-jq-filters.yaml` |
| Universal filter | `.combined_filters.universal_filter.filter` |
| Repository filter | `.basic_filters.repository_filter.filter` |
| Assignee filter | `.basic_filters.assignee_filter.filter` |
| Status filter | `.basic_filters.status_filter.filter` |
| List repositories | `.discovery_filters.list_repositories.filter` |
| List assignees | `.discovery_filters.list_assignees.filter` |
| List statuses | `.discovery_filters.list_statuses.filter` |
| List priorities | `.discovery_filters.list_priorities.filter` |

---

## Benefits of Consolidated Approach

### ✅ Advantages

1. **Single Command Interface**: One command for all project analysis needs
2. **Consistent Flag System**: Intuitive `--list-*`, `--format=*` patterns
3. **Pipeline Integration**: All features work with existing bash function architecture
4. **Flexible Output**: JSON, table, detailed, and count-only formats
5. **Discovery Built-in**: Team, repository, status, and field discovery integrated
6. **Memory Efficient**: Streaming pipeline processing, no temporary files
7. **Composable**: All flags can be combined for complex analysis
8. **Maintainable**: Single codebase instead of 5 separate commands

### 🔄 Implementation Pattern

```bash
# Standard usage pattern for LLM implementation:
# 1. Source functions once per session
source lib/github/gh-project-functions.sh

# 2. Execute appropriate bash pipeline to get JSON data
fetch_org_project PROJECT_NUM "ORG_NAME" | [filter_functions]

# 3. LLM interprets JSON and formats according to --format flag:
#    - format=summary: Provide insights and analysis
#    - format=json: Return raw JSON data
#    - format=table: Create formatted table presentation
#    - format=count: Extract and show count only
```

**Critical**: Never use jq for table formatting or inject table commands. Always get clean JSON from bash functions, then let LLM handle formatting.

## LLM Implementation Guidelines

### Format Handling Protocol

**Step 1: Execute Bash Pipeline**
```bash
# Get JSON data using appropriate bash functions
source lib/github/gh-project-functions.sh
result=$(fetch_org_project 2 "my-org-name" | apply_assignee_filter "my_username")
```

**Step 2: Format According to Flag**
- `--format=summary` → Analyze JSON and provide insights, trends, key findings
- `--format=json` → Return the JSON data directly with no interpretation
- `--format=table` → Parse JSON and create well-formatted table with headers and alignment
- `--count-only` → Extract count number only using `get_count`

**Step 3: Present Results**
- **Summary**: "The project has 30 items assigned to my_username, with 15 in Backlog status and 8 high-priority (P1/P2) items..."
- **JSON**: Return raw JSON structure
- **Table**: Create properly aligned table with columns and headers
- **Count**: "30"

### ❌ Wrong Approach
```bash
# DON'T DO THIS - no jq table formatting
fetch_org_project 2 "org" | jq -r '...' | some_table_format
```

### ✅ Correct Approach
```bash
# DO THIS - clean JSON → LLM formatting
result=$(fetch_org_project 2 "org" | apply_filters)
# Then LLM processes $result according to --format flag
```

### 📊 Output Formats

- **Summary** (default): LLM interpretation and insights from project data
- **JSON**: Structured data for detailed analysis and processing
- **Table**: LLM-formatted table presentation for human viewing
- **Count**: Numeric results for statistical analysis and reporting

**Implementation Approach**: All formats use the same bash function pipeline to get JSON data, then LLM processes the results according to the requested format. No complex jq table formatting needed - LLM handles presentation.

---

## Production Notes

- **Consolidates 4 previous commands** into single interface
- **Backwards compatible** through function layer (existing scripts still work)
- **All examples tested** with real project data (my-org-name project #2)
- **Pipeline architecture validated** with process substitution and proper error handling
- **Universal filter handles** all parameter combinations with empty string logic
- **Discovery commands integrated** with consistent `--list-*` flag pattern
- **Output formatting unified** with `--format=*` flag system
- **Field inspection capability** added through `--list-fields` flag
- **Memory efficient** streaming eliminates intermediate file storage
- **Clean flag system** replaces complex parameter variations

## Available Bash Functions Reference

### Core Functions
- `fetch_org_project PROJECT_NUM "ORG_NAME"` - Fetch organization project data
- `fetch_user_project PROJECT_NUM` - Fetch user project data

### Filter Functions
- `apply_universal_filter "REPO" "ASSIGNEE" "STATUS" "PRIORITY"` - Apply multiple filters
- `apply_assignee_filter "USERNAME"` - Filter by assignee
- `apply_repo_filter "REPO_NAME"` - Filter by repository
- `apply_status_filter "STATUS"` - Filter by status

### Discovery Functions
- `list_assignees` - List all assignees (`--list-assignees`)
- `list_repositories` - List all repositories (`--list-repos`)
- `list_statuses` - List all status values (`--list-statuses`)
- `list_priorities` - List all priority values (`--list-priorities`)
- `list_fields` - List all priority values (`--list-fields`)

### Output Functions
- `get_count` - Extract count only (`--count-only`)
- `get_items` - Extract items array for processing

### Flag Mapping
- **Discovery**: `--list-*` → `list_*` functions.
- **Filtering**: `--assignee`, `--repo`, `--status`, `--priority` → `apply_*_filter` functions
- **Output**: `--format`, `--count-only`, `--limit` → processing modifiers
