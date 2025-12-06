# GitHub Project Dashboard System Architecture

## Overview

The GitHub Project Dashboard System is a modular, pipeline-based architecture for querying, filtering, and presenting GitHub Projects v2 data. It consists of four main components that work together to provide flexible project analytics and reporting capabilities optimized for Claude Code command usage.

## System Architecture

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
│            github-projects-jq-filters.yaml                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Basic Filters   │  │ Combined        │  │ Discovery       │ │
│  │ - Repository    │  │ Filters         │  │ Filters         │ │
│  │ - Assignee      │  │ - Universal     │  │ - List Repos    │ │
│  │ - Status        │  │ - Multi-field   │  │ - List Users    │ │
│  │ - Priority      │  │ Combinations    │  │ - List Values   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────┘
                      │ JSON Output
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│        hv-gh-project-dashboard Command Interface               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Command Parser  │  │ Parameter       │  │ Output          │ │
│  │ - Args & Flags  │  │ Validation      │  │ Formatter       │ │
│  │ - Context Types │  │ - Filter Values │  │ - Dashboard     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. GraphQL Query Layer (`lib/github/github-projects-graphql-queries.yaml`)

**Purpose**: Centralized GraphQL query templates for GitHub Projects v2 API
**Location**: `lib/github/github-projects-graphql-queries.yaml`

```yaml
item_queries:
  user_project_items_full:
    query: |
      query($projectNumber: Int!) {
        viewer {
          projectV2(number: $projectNumber) {
            # Full project structure with items and fields
          }
        }
      }
  organization_project_items_full:
    query: |
      query($orgLogin: String!, $projectNumber: Int!) {
        organization(login: $orgLogin) {
          projectV2(number: $projectNumber) {
            # Full project structure with items and fields
          }
        }
      }
```

**Key Features**:
- Comprehensive field selection for complete project data
- Support for both user and organization contexts
- Optimized for single API call efficiency
- Includes nested relationships (assignees, repositories, field values)

### 2. Bash Function Pipeline (`lib/github/gh-project-functions.sh`)

**Purpose**: Executable functions providing pipeable data processing
**Location**: `gh-project-functions.sh`

#### Data Fetching Functions
```bash
# Fetch organization project data
fetch_org_project PROJECT_NUM "ORG_NAME"

# Fetch user project data
fetch_user_project PROJECT_NUM
```

#### Filter Pipeline Functions
```bash
# Universal filter with conditional logic
apply_universal_filter "REPO" "ASSIGNEE" "STATUS" "PRIORITY"

# Individual field filters
apply_assignee_filter "USERNAME"
apply_repo_filter "REPO_NAME"
apply_status_filter "STATUS"
```

#### Discovery Functions
```bash
# Extract available filter values
list_repositories
list_assignees
list_statuses
list_priorities
```

#### Utility Functions
```bash
# Extract specific data
get_count        # Get filtered item count
get_items        # Extract items array
```

**Key Features**:
- **Pipeable Design**: All functions read from stdin and write to stdout
- **Process Substitution**: Uses `<(yq ...)` to avoid command substitution issues
- **Memory Efficient**: No temporary files, streaming data processing
- **Composable**: Chain functions with Unix pipes for complex operations
- **Error Safe**: Proper handling of YAML extraction and shell escaping

### 3. jq Filter Templates (`lib/github/github-projects-jq-filters.yaml`)

**Purpose**: Centralized jq filter definitions for JSON data transformation
**Location**: `lib/github/github-projects-jq-filters.yaml`

#### Basic Filters
```yaml
basic_filters:
  repository_filter:
    description: "Filter project items by repository name"
    parameters:
      - name: "repo"
        description: "Repository name to filter by"
    filter: |
      {
        project: (.data.organization.projectV2 // .data.viewer.projectV2).title,
        filteredItems: [(.data.organization.projectV2 // .data.viewer.projectV2).items.nodes[] | select(.content.repository.name == $repo)],
        filteredCount: [(.data.organization.projectV2 // .data.viewer.projectV2).items.nodes[] | select(.content.repository.name == $repo)] | length
      }
```

#### Combined Filters
```yaml
combined_filters:
  universal_filter:
    description: "Apply all possible filters with conditional logic"
    parameters:
      - name: "repo"
        description: "Repository name (empty string to ignore)"
      - name: "assignee"
        description: "Username (empty string to ignore)"
      - name: "status"
        description: "Status value (empty string to ignore)"
      - name: "priority"
        description: "Priority value (empty string to ignore)"
    filter: |
      {
        project: (.data.organization.projectV2 // .data.viewer.projectV2).title,
        filteredItems: [
          (.data.organization.projectV2 // .data.viewer.projectV2).items.nodes[] |
          select(
            (if $repo != "" then .content.repository.name == $repo else true end) and
            (if $assignee != "" then .content.assignees.nodes[]?.login == $assignee else true end) and
            (if $status != "" then .fieldValues.nodes[]?.name == $status else true end) and
            (if $priority != "" then .fieldValues.nodes[]?.name == $priority else true end)
          )
        ]
      } | . + {filteredCount: (.filteredItems | length)}
```

#### Discovery Filters
```yaml
discovery_filters:
  list_repositories:
    description: "Extract unique repository names from project items"
    filter: |
      {
        project: (.data.organization.projectV2 // .data.viewer.projectV2).title,
        repositories: [(.data.organization.projectV2 // .data.viewer.projectV2).items.nodes[] | .content.repository.name] | unique | sort
      }
```

**Key Features**:
- **Conditional Logic**: Empty string parameters skip filters
- **Consistent Output**: All filters return structured JSON with metadata
- **Flexible Combinations**: Mix and match any filter criteria
- **Discovery Support**: Extract available filter values from data
- **Shell Safe**: Both multiline and compact single-line versions

### 4. Command Interface (`.claude/hv-gh-project-dashboard.md`)

**Purpose**: User-facing command documentation and implementation patterns
**Location**: `.claude/hv-gh-project-dashboard.md`

#### Command Syntax
```
/hv-gh-project-dashboard <project_number> [owner] [context] [filters...]
```

#### Implementation Patterns
```bash
# Basic usage pattern
source lib/github/gh-project-functions.sh
fetch_org_project 2 "my-org" | apply_assignee_filter "username"

# Chained filtering
fetch_org_project 2 "my-org" \
  | apply_repo_filter "my-repo" \
  | apply_assignee_filter "username"

# Discovery workflow
fetch_org_project 2 "my-org" | list_repositories
```

**Key Features**:
- **Complete Examples**: Working command patterns with real data
- **Parameter Reference**: Template variable substitution guide
- **Pipeline Patterns**: Standard workflows for common use cases
- **JSON Output Examples**: Expected response structures
- **Claude Code Integration**: Optimized for LLM command processing

## Data Flow Architecture

### 1. Query Execution Flow
```
User Command → Parse Parameters → Extract GraphQL Query → GitHub API → Raw JSON
```

### 2. Filter Pipeline Flow
```
Raw JSON → Fetch Function → Filter Functions (Chained) → Formatted JSON → LLM Processing
```

### 3. Discovery Flow
```
Raw JSON → Fetch Function → Discovery Function → Available Values → User Selection
```

## Key Design Principles

### 1. **Separation of Concerns**
- **Queries**: GraphQL templates isolated in YAML
- **Processing**: Bash functions handle data flow
- **Filtering**: jq templates provide transformation logic
- **Interface**: Command documentation provides usage patterns

### 2. **Pipeline Architecture**
- All functions are pipeable (stdin → processing → stdout)
- No temporary files or shared state
- Composable operations through Unix pipes
- Memory-efficient streaming processing

### 3. **Template-Driven Configuration**
- YAML templates provide centralized configuration
- Process substitution avoids command substitution issues
- Shell-safe parameter handling
- Maintainable filter definitions

### 4. **LLM-Optimized Output**
- Structured JSON output for consistent parsing
- Metadata includes filter context and counts
- Self-describing data structures
- Flexible presentation formats

## Usage Patterns for Claude Code Commands

### Standard Pipeline Pattern
```bash
# 1. Source functions (once per session)
source lib/github/gh-project-functions.sh

# 2. Fetch data with appropriate function
fetch_org_project PROJECT_NUM "ORG_NAME"

# 3. Apply filters through pipeline
| apply_assignee_filter "USERNAME"
| apply_repo_filter "REPO_NAME"

# 4. Extract results or counts
| get_count
```

### Discovery Pattern
```bash
# Discover available values before filtering
fetch_org_project 2 "my-org" | list_assignees
fetch_org_project 2 "my-org" | list_repositories

# Apply discovery to filtered data
fetch_org_project 2 "my-org" \
  | apply_assignee_filter "username" \
  | list_repositories
```

### Universal Filter Pattern
```bash
# Apply multiple filters in single operation
fetch_org_project 2 "my-org" \
  | apply_universal_filter "repo-name" "username" "status" "priority"

# Use empty strings to skip specific filters
fetch_org_project 2 "my-org" \
  | apply_universal_filter "" "username" "Shipped" ""
```

## File Dependencies

```
hv-gh-project-dashboard.md
├── gh-project-functions.sh
│   ├── github-projects-graphql-queries.yaml
│   └── github-projects-jq-filters.yaml
└── gh-project-functions_with_files.sh (legacy)
```

## Performance Characteristics

- **Memory Efficient**: Streaming pipeline processing, no temporary files
- **Network Efficient**: Single GraphQL API call fetches complete dataset
- **CPU Efficient**: jq native JSON processing with optimized filters
- **Scalable**: Handles large project datasets through streaming architecture

## Extensibility Points

1. **New Filters**: Add filter definitions to `lib/github/github-projects-jq-filters.yaml`
2. **New Functions**: Add pipeline functions to `lib/github/gh-project-functions.sh`
3. **New Queries**: Add GraphQL templates to query YAML file
4. **New Commands**: Extend command interface with additional patterns

This architecture provides a robust, maintainable, and efficient system for GitHub project analytics that integrates seamlessly with Claude Code command workflows.
