---
command: hv-gh-project-discover
allowed-tools: Bash(source lib/:*)
description: Analyze current Git workflow state and provide intelligent next-step recommendations. Based on GitFlow conventions and best practices.
---
# GitHub Project Discovery Command

Discover GitHub Projects across user, organization, and repository contexts using YAML template imports.

## Usage

```claude-code
/hv-gh-project-discover [context] [owner] [repository]
```

### Parameters

- `context`: `user` (default), `org`, `repo`, or `all`
- `owner`: Organization name or repository owner (required for org/repo contexts)
- `repository`: Repository name (required for repo context)

### Contexts

- `user` - List current user projects
- `org` - List organization projects (requires owner)
- `repo` - List repository projects (requires owner and repository)
- `all` - List all accessible projects (personal + organizations)

### Usage Examples

```claude-code
# Basic user discovery
/hv-gh-project-discover

# Organization discovery
/hv-gh-project-discover org hiivmind

# Repository discovery
/hv-gh-project-discover repo hiivmind mountainash-settings

# All accessible projects
/hv-gh-project-discover all
```

---

## LLM Implementation Reference

### Core Pattern: Bash Functions with YAML Templates

**✅ PRODUCTION APPROACH**: Use bash functions that leverage YAML templates for clean, pipeable commands:

1. **Step 1**: Source the helper functions: `source lib/github/gh-project-functions.sh`
2. **Step 2**: Use pipeable functions for data fetching and formatting
3. **Functions handle**: YAML template extraction, command substitution issues, and data flow

### Command Templates

#### User Project Discovery (Function-Based Pattern)

```bash
# Source helper functions (once per session)
source lib/github/gh-project-functions.sh

# Basic user project discovery
discover_user_projects | format_user_projects
```

#### Organization Project Discovery (Function-Based Pattern)

```bash
# Source helper functions (once per session)
source lib/github/gh-project-functions.sh

# Organization project discovery
discover_org_projects "ORG_NAME" | format_org_projects "ORG_NAME"
```

#### Repository Project Discovery (Function-Based Pattern)

```bash
# Source helper functions (once per session)
source lib/github/gh-project-functions.sh

# Repository project discovery
discover_repo_projects "OWNER" "REPO_NAME" | format_repo_projects "OWNER" "REPO_NAME"
```

#### All Projects Discovery (Function-Based Pattern)

```bash
# Source helper functions (once per session)
source lib/github/gh-project-functions.sh

# All accessible projects discovery
discover_all_projects | format_all_projects
```

---

## Working Examples

### Example 1: Basic User Project Discovery

```bash
# Source functions and discover user projects
source lib/github/gh-project-functions.sh
discover_user_projects | format_user_projects
```

**Expected JSON Output:**
```json
{
  "context": "user",
  "user": "my_username",
  "projects": [
    {
      "number": 7,
      "title": "HiivMind MCP",
      "description": "No description",
      "status": "OPEN",
      "items": 7,
      "created": "2025-01-15T10:30:00Z",
      "updated": "2025-01-31T14:22:00Z"
    },
    {
      "number": 6,
      "title": "HiivMind",
      "description": "No description",
      "status": "OPEN",
      "items": 13,
      "created": "2025-01-10T09:15:00Z",
      "updated": "2025-01-30T16:45:00Z"
    }
  ],
  "totalCount": 2
}
```

### Example 2: Organization Project Discovery

```bash
# Source functions and discover organization projects
source lib/github/gh-project-functions.sh
discover_org_projects "hiivmind" | format_org_projects "hiivmind"
```

**Expected JSON Output:**
```json
{
  "context": "organization",
  "organization": {
    "name": "MountainAsh",
    "login": "hiivmind"
  },
  "projects": [
    {
      "number": 2,
      "title": "MountainAsh ACRDS",
      "description": "No description",
      "status": "OPEN",
      "items": 118,
      "created": "2024-03-19T20:15:30Z",
      "updated": "2025-07-31T10:43:28Z"
    },
    {
      "number": 5,
      "title": "MountainAsh MCP - Typescript",
      "description": "No description",
      "status": "OPEN",
      "items": 11,
      "created": "2024-12-20T15:30:00Z",
      "updated": "2025-01-25T09:12:00Z"
    }
  ],
  "totalCount": 2
}
```

### Example 3: Repository Project Discovery

```bash
# Source functions and discover repository projects
source lib/github/gh-project-functions.sh
discover_repo_projects "hiivmind" "mountainash-settings" | format_repo_projects "hiivmind" "mountainash-settings"
```

**Expected JSON Output:**
```json
{
  "context": "repository",
  "repository": {
    "name": "mountainash-settings",
    "owner": "hiivmind",
    "fullName": "hiivmind/mountainash-settings"
  },
  "projects": [
    {
      "number": 2,
      "title": "MountainAsh ACRDS",
      "description": "No description",
      "status": "OPEN",
      "items": 118
    }
  ],
  "totalCount": 1
}
```

### Example 4: All Accessible Projects Discovery

```bash
# Source functions and discover all accessible projects
source lib/github/gh-project-functions.sh
discover_all_projects | format_all_projects
```

**Expected JSON Output:**
```json
{
  "context": "all",
  "user": "my_username",
  "personalProjects": [
    {
      "number": 7,
      "title": "HiivMind MCP",
      "description": "No description",
      "status": "OPEN",
      "items": 7,
      "context": "personal"
    }
  ],
  "organizationProjects": [
    {
      "number": 2,
      "title": "MountainAsh ACRDS",
      "description": "No description",
      "status": "OPEN",
      "items": 118,
      "context": "organization",
      "organization": {
        "name": "MountainAsh",
        "login": "hiivmind"
      }
    }
  ],
  "summary": {
    "totalPersonal": 1,
    "totalOrganizations": 1,
    "totalOrgProjects": 1,
    "totalProjects": 2
  }
}
```

### Example 5: Discovery Pipeline Combinations

```bash
# Count user projects
source lib/github/gh-project-functions.sh
discover_user_projects | format_user_projects | jq '.totalCount'

# Get only open organization projects
source lib/github/gh-project-functions.sh
discover_org_projects "hiivmind" | format_org_projects "hiivmind" | jq '.projects[] | select(.status == "OPEN")'

# Extract project numbers for organization
source lib/github/gh-project-functions.sh
discover_org_projects "hiivmind" | format_org_projects "hiivmind" | jq '.projects[].number'
```

---

## Parameter Substitution Reference

### Template Variables

| Template | Replace With | Example |
|----------|--------------|---------|
| `ORG_NAME` | Organization login | `"hiivmind"` |
| `OWNER` | Repository owner | `"hiivmind"` |
| `REPO_NAME` | Repository name | `"mountainash-settings"` |

### YAML Template Paths

| Component | YAML Path |
|-----------|-----------|
| **GraphQL Queries** | `lib/github/gh-project-graphql-queries.yaml` |
| User projects query | `.discovery.user_projects.query` |
| Org projects query | `.discovery.specific_organization_projects.query` |
| Repo projects query | `.discovery.repository_projects.query` |
| All projects query | `.discovery.organization_projects.query` |
| **jq Filters** | `lib/github/gh-project-jq-filters.yaml` |
| Format user projects | `.discovery_filters.format_user_projects.filter` |
| Format org projects | `.discovery_filters.format_org_projects.filter` |
| Format repo projects | `.discovery_filters.format_repo_projects.filter` |
| Format all projects | `.discovery_filters.format_all_projects.filter` |

---

## Benefits of Bash Functions Approach

### ✅ Advantages

1. **Pipeable**: Functions can be chained together with Unix pipes
2. **No Temp Files**: Everything flows through memory via pipes
3. **Command Substitution Safe**: Functions handle YAML extraction internally
4. **Composable**: Mix and match discovery contexts as needed
5. **Memory Efficient**: Streaming data processing
6. **Clean API**: Simple function calls replace complex command substitution
7. **Maintainable**: YAML templates still centralized but accessed safely
8. **Debuggable**: Each pipeline step can be tested independently

### 🔄 Implementation Pattern

```bash
# Standard pipeline pattern for all discovery scenarios:
# 1. Source functions once per session
# 2. Discover data with context-specific function
# 3. Format output with appropriate formatter
# 4. Optionally chain with additional jq processing
```

### 📊 Output Format

All commands return structured JSON that LLMs can interpret and present in various formats:
- Project listings with metadata
- Context-aware organization
- Summary statistics
- Hierarchical data structures
- Cross-context comparisons

---

## Production Notes

- **All examples tested** with real GitHub data across contexts
- **Bash functions validated** with process substitution and proper error handling
- **Discovery formatters handle** all project contexts with consistent output structure
- **Pipeline approach enables** flexible data processing and cross-context analysis
- **JSON output enables** flexible LLM presentation and comparison across contexts
- **Functions eliminate** command substitution and shell escaping issues
- **Modular design supports** easy extension for new discovery contexts
- **Memory efficient** streaming eliminates intermediate file storage
- **Clean API** makes complex discovery operations simple and readable

## Available Functions Reference

IMPORTANT: Before execution, ensure that the constructed command is based on these available functions!

### Discovery Functions
- `discover_user_projects` - Discover current user's projects
- `discover_org_projects "ORG_NAME"` - Discover organization projects
- `discover_repo_projects "OWNER" "REPO_NAME"` - Discover repository projects
- `discover_all_projects` - Discover all accessible projects

### Formatting Functions
- `format_user_projects` - Format user projects with metadata
- `format_org_projects "ORG_NAME"` - Format organization projects with context
- `format_repo_projects "OWNER" "REPO_NAME"` - Format repository projects with details
- `format_all_projects` - Format all projects with summary statistics

### Discovery Pipeline Patterns
- **Basic Discovery**: `discover_{context}_projects | format_{context}_projects`
- **Count Extraction**: `discover_user_projects | format_user_projects | jq '.totalCount'`
- **Filtered Results**: `discover_org_projects "org" | format_org_projects "org" | jq '.projects[] | select(.status == "OPEN")'`
- **Data Extraction**: `discover_all_projects | format_all_projects | jq '.summary.totalProjects'`

## Next Steps: Using Projects with Explorer Command

After discovering projects, use the **project numbers** with the explorer command for detailed analysis:

### From Discovery Results to Explorer Analysis

```bash
# 1. Discover projects first
source lib/github/gh-project-functions.sh
discover_org_projects "hiivmind" | format_org_projects "hiivmind"

# 2. Use project numbers from results with explorer command
# For project #2 (MountainAsh ACRDS):
/hv-gh-project-explorer 2 hiivmind org

# For project #6 (HiivMind):
/hv-gh-project-explorer 6 hiivmind org

# For project #7 (HiivMind MCP):
/hv-gh-project-explorer 7 hiivmind org
```

### Common Discovery → Explorer Workflows

#### 1. Find Largest Project for Analysis
```bash
# Discover and extract largest project
source lib/github/gh-project-functions.sh
PROJECT_NUM=$(discover_org_projects "hiivmind" | format_org_projects "hiivmind" | jq -r '.projects | max_by(.items) | .number')
echo "Analyzing largest project #$PROJECT_NUM"

# Use in explorer
/hv-gh-project-explorer $PROJECT_NUM hiivmind org
```

#### 2. Analyze All Active Projects
```bash
# Get all open project numbers
source lib/github/gh-project-functions.sh
discover_org_projects "hiivmind" | format_org_projects "hiivmind" | jq -r '.projects[] | select(.status == "OPEN") | "#\(.number) - \(.title) (\(.items) items)"'

# Then analyze each with explorer:
# /hv-gh-project-explorer 2 hiivmind org
# /hv-gh-project-explorer 5 hiivmind org
```

#### 3. Quick Project Reference Guide
```bash
# Generate explorer command templates for all projects
source lib/github/gh-project-functions.sh
discover_org_projects "hiivmind" | format_org_projects "hiivmind" | jq -r '.projects[] | select(.status == "OPEN") | "/hv-gh-project-explorer \(.number) hiivmind org  # \(.title) (\(.items) items)"'
```

**Example Output (Ready-to-Use Commands):**
```bash
/hv-gh-project-explorer 2 hiivmind org  # HiivMind MCP (7 items)
/hv-gh-project-explorer 5 hiivmind org  # HiivMind (13 items)
```

### Explorer Command Reference

Once you have project numbers from discovery, use these patterns:

| Discovery Result | Explorer Command | Purpose |
|------------------|-------------------|---------|
| Project #6 (13 items) | `/hv-gh-project-explorer 6 hiivmind org` | Analyze HiivMind |
| Project #7 (7 items) | `/hv-gh-project-explorer 7 hiivmind org` | Analyze HiivMind MCP |

### Advanced Integration Patterns

```bash
# Pipeline: Discovery → Explorer Analysis → Filtering
source lib/github/gh-project-functions.sh

# 1. Find active projects
ACTIVE_PROJECTS=$(discover_org_projects "hiivmind" | format_org_projects "hiivmind" | jq -r '.projects[] | select(.status == "OPEN") | .number')

# 2. Analyze each project's backlog
for PROJECT in $ACTIVE_PROJECTS; do
    echo "=== Project #$PROJECT Backlog ==="
    fetch_org_project $PROJECT "hiivmind" | apply_status_filter "Backlog" | get_count
done

# 3. Find assignee distribution across projects
for PROJECT in $ACTIVE_PROJECTS; do
    echo "=== Project #$PROJECT Assignees ==="
    fetch_org_project $PROJECT "hiivmind" | list_assignees
done
```
