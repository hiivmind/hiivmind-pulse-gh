# Milestone Domain Index

> **Domain:** Milestone
> **Priority:** P1 (Work Tracking)
> **Depends on:** None (isolated domain)
> **Files:**
> - `gh-milestone-functions.sh` - Shell function primitives
> - `gh-milestone-graphql-queries.yaml` - GraphQL query templates
> - `gh-milestone-jq-filters.yaml` - jq filter templates

## Overview

The Milestone domain handles GitHub repository milestones. Milestones are used to track progress toward specific goals by grouping related issues and pull requests.

**Important:** Milestone CRUD operations (create, update, delete) require the **REST API**. GraphQL is used for queries and setting milestones on issues/PRs (via Issue/PR domains).

## Quick Start

```bash
# Source the functions
source lib/github/gh-milestone-functions.sh

# List milestones (GraphQL)
fetch_repo_milestones "hiivmind" "hiivmind-pulse-gh" | format_milestones

# List milestones (REST)
list_milestones_rest "hiivmind" "hiivmind-pulse-gh" | format_milestones_rest

# Get milestone ID by title
MILESTONE_ID=$(get_milestone_id "hiivmind" "hiivmind-pulse-gh" "v1.0")

# Create a milestone
create_milestone "hiivmind" "hiivmind-pulse-gh" "v1.0" "First release" "2024-12-31T00:00:00Z"

# Close a milestone
close_milestone "hiivmind" "hiivmind-pulse-gh" 1
```

---

## Function Reference

### LOOKUP Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_milestone_id` | `owner`, `repo`, `title` | Node ID | Milestone's GraphQL node ID by title |
| `get_milestone_number` | `owner`, `repo`, `title` | Number | Milestone number by title |

### FETCH Primitives (GraphQL)

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `fetch_repo_milestones` | `owner`, `repo`, `[states]` | JSON | List milestones (OPEN/CLOSED/both) |
| `fetch_milestone` | `owner`, `repo`, `number` | JSON | Single milestone by number |

### REST API Functions (CRUD)

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `list_milestones_rest` | `owner`, `repo`, `[state]`, `[sort]`, `[direction]` | JSON | List milestones via REST |
| `get_milestone_rest` | `owner`, `repo`, `number` | JSON | Single milestone via REST |
| `create_milestone` | `owner`, `repo`, `title`, `[desc]`, `[due]`, `[state]` | JSON | Create new milestone |
| `update_milestone` | `owner`, `repo`, `number`, `[title]`, `[desc]`, `[due]`, `[state]` | JSON | Update milestone |
| `close_milestone` | `owner`, `repo`, `number` | JSON | Close a milestone |
| `reopen_milestone` | `owner`, `repo`, `number` | JSON | Reopen a milestone |
| `delete_milestone` | `owner`, `repo`, `number` | - | Delete a milestone |

### FILTER Primitives

| Function | Args | Input | Output | Description |
|----------|------|-------|--------|-------------|
| `filter_milestones_by_state` | `state` | JSON stdin | JSON | Filter GraphQL response by state |
| `filter_milestones_rest_by_state` | `state` | JSON stdin | JSON | Filter REST response by state |

### FORMAT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `format_milestones` | JSON stdin | JSON | Format GraphQL milestone list |
| `format_milestone` | JSON stdin | JSON | Format GraphQL single milestone |
| `format_milestones_rest` | JSON stdin | JSON | Format REST milestone list |
| `format_milestone_rest` | JSON stdin | JSON | Format REST single milestone |

### EXTRACT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `extract_milestone_titles` | JSON stdin | Array | Extract milestone titles |
| `extract_milestone_ids` | JSON stdin | Array | Extract milestone node IDs |

### DETECT Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `check_milestone_exists` | `owner`, `repo`, `title` | Exit code | 0 if exists, 1 if not |
| `detect_milestone_state` | `owner`, `repo`, `number` | State | "open" or "closed" |

### Convenience Functions

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_milestone_progress` | `owner`, `repo`, `number` | Integer | Progress percentage (0-100) |
| `create_or_update_milestone` | `owner`, `repo`, `title`, ... | JSON | Upsert milestone by title |

---

## GraphQL Queries

| Query | Parameters | Purpose |
|-------|------------|---------|
| `repository_milestones` | `owner`, `repo`, `states` | List milestones |
| `milestone_by_number` | `owner`, `repo`, `number` | Single milestone |
| `milestone_with_issues` | `owner`, `repo`, `number`, `issueFirst` | Milestone with issues/PRs |
| `milestone_id_only` | `owner`, `repo`, `number` | Just node ID |

---

## jq Filters

### Format Filters (GraphQL)

| Filter | Input | Output |
|--------|-------|--------|
| `format_milestones` | milestones query | Formatted list |
| `format_milestone` | milestone query | Formatted single |
| `format_milestone_with_issues` | milestone with issues query | Full details |
| `format_milestones_summary` | milestones query | Simple summary |

### Format Filters (REST)

| Filter | Input | Output |
|--------|-------|--------|
| `format_milestones_rest` | REST milestones array | Formatted list |
| `format_milestone_rest` | REST milestone object | Formatted single |
| `format_milestone_progress` | REST milestone | Progress stats |

### Extract Filters

| Filter | Output |
|--------|--------|
| `extract_milestone_id` | Single node ID |
| `extract_milestone_titles` | Array of titles |
| `extract_milestone_numbers` | Array of numbers |
| `extract_open_milestones` | Open milestones only |
| `extract_closed_milestones` | Closed milestones only |
| `extract_overdue_milestones` | Past due date |

---

## Composition Examples

### List Open Milestones with Progress

```bash
source lib/github/gh-milestone-functions.sh

fetch_repo_milestones "hiivmind" "hiivmind-pulse-gh" "OPEN" | format_milestones
```

### Create Milestone with Due Date

```bash
source lib/github/gh-milestone-functions.sh

# Create milestone due at end of year
create_milestone "hiivmind" "hiivmind-pulse-gh" \
    "v1.0" \
    "First stable release" \
    "2024-12-31T00:00:00Z"
```

### Get Milestone ID for Setting on Issues

```bash
source lib/github/gh-milestone-functions.sh

# Get milestone ID
MILESTONE_ID=$(get_milestone_id "hiivmind" "hiivmind-pulse-gh" "v1.0")

# Use with Issue domain functions (when available)
# set_issue_milestone "$ISSUE_ID" "$MILESTONE_ID"
```

### Check and Close Completed Milestone

```bash
source lib/github/gh-milestone-functions.sh

OWNER="hiivmind"
REPO="hiivmind-pulse-gh"
NUMBER=1

# Check progress
PROGRESS=$(get_milestone_progress "$OWNER" "$REPO" "$NUMBER")
echo "Progress: $PROGRESS%"

# Close if complete
if [[ "$PROGRESS" -eq 100 ]]; then
    close_milestone "$OWNER" "$REPO" "$NUMBER"
    echo "Milestone closed"
fi
```

### Upsert Milestone (Create or Update)

```bash
source lib/github/gh-milestone-functions.sh

# Will create if doesn't exist, update if it does
create_or_update_milestone "hiivmind" "hiivmind-pulse-gh" \
    "Sprint 1" \
    "First sprint goals" \
    "2024-02-01T00:00:00Z"
```

---

## Dependencies

- **External tools:** `gh` (GitHub CLI), `jq` (1.6+), `yq` (4.0+)
- **Other domains:** None (milestones are isolated)

## Dependents

Other domains that use Milestone:
- **Issue:** Uses `get_milestone_id` for setting milestone on issues
- **Pull Request:** Uses `get_milestone_id` for setting milestone on PRs

---

## Error Handling

All functions follow these patterns:

1. **Missing arguments:** Return exit code 2 with error message to stderr
2. **API errors:** Propagate gh CLI exit codes
3. **Not found:** Return empty/null output or exit code 1 for check functions

Example error handling:

```bash
MILESTONE_ID=$(get_milestone_id "owner" "repo" "nonexistent" 2>/dev/null)
if [[ -z "$MILESTONE_ID" || "$MILESTONE_ID" == "null" ]]; then
    echo "Milestone not found"
fi
```

---

## Notes

### GraphQL vs REST

| Operation | API | Reason |
|-----------|-----|--------|
| List/Query | GraphQL | Better field selection, pagination |
| Create | REST | Not available in GraphQL |
| Update | REST | Not available in GraphQL |
| Delete | REST | Not available in GraphQL |
| Set on Issue/PR | GraphQL | Via updateIssue/updatePullRequest mutations |

### State Values

| GraphQL | REST | Description |
|---------|------|-------------|
| `OPEN` | `open` | Milestone is active |
| `CLOSED` | `closed` | Milestone is complete |

### Due Date Format

Due dates use ISO 8601 format: `2024-12-31T00:00:00Z`

### Progress Calculation

- GraphQL: `progressPercentage` field (0-100)
- REST: Calculate as `(closed_issues / total_issues) * 100`
