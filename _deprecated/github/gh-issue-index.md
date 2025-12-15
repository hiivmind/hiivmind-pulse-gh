# Issue Domain Index

> **Domain:** Issue
> **Priority:** P1 (Work Tracking)
> **Depends on:** Identity (for user IDs), Repository (for repo context), Milestone (for milestone IDs)
> **Files:**
> - `gh-issue-functions.sh` - Shell function primitives
> - `gh-issue-graphql-queries.yaml` - GraphQL query templates
> - `gh-issue-jq-filters.yaml` - jq filter templates

## Overview

The Issue domain handles GitHub issues - queries, filtering, and mutations (labels, assignees, milestones, state changes).

**API Selection:**
- **GraphQL:** Complex queries, mutations, getting node IDs
- **REST:** Simple issue listing, basic creation

## Quick Start

```bash
# Source the functions
source lib/github/gh-issue-functions.sh

# List open issues
discover_repo_issues "hiivmind" "hiivmind-pulse-gh" "OPEN" | format_issues_list

# Get a specific issue
fetch_issue "hiivmind" "hiivmind-pulse-gh" 12 | format_issue

# Get issue ID
ISSUE_ID=$(get_issue_id "hiivmind" "hiivmind-pulse-gh" 12)

# Close an issue
close_issue "$ISSUE_ID"
```

---

## Function Reference

### LOOKUP Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_issue_id` | `owner`, `repo`, `number` | Node ID | Issue's GraphQL node ID |
| `get_label_id` | `owner`, `repo`, `label_name` | Node ID | Label's GraphQL node ID |
| `get_user_id` | `login` | Node ID | User's GraphQL node ID |

### FETCH Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `fetch_issue` | `owner`, `repo`, `number` | JSON | Full issue data (GraphQL) |
| `discover_repo_issues` | `owner`, `repo`, `[states]`, `[first]` | JSON | List issues in repo |

### REST API Functions

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `list_issues_rest` | `owner`, `repo`, `[state]`, `[per_page]` | JSON | List issues via REST |
| `get_issue_rest` | `owner`, `repo`, `number` | JSON | Single issue via REST |
| `create_issue` | `owner`, `repo`, `title`, ... | JSON | Create new issue |

### FILTER Primitives

| Function | Args | Input | Output | Description |
|----------|------|-------|--------|-------------|
| `filter_issues_by_state` | `state` | JSON stdin | JSON | Filter by OPEN/CLOSED |
| `filter_issues_by_label` | `label` | JSON stdin | JSON | Filter by label name |
| `filter_issues_by_assignee` | `login` | JSON stdin | JSON | Filter by assignee |
| `filter_issues_by_milestone` | `title` | JSON stdin | JSON | Filter by milestone |

### MUTATE Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `set_issue_milestone` | `issue_id`, `milestone_id` | JSON | Set milestone on issue |
| `clear_issue_milestone` | `issue_id` | JSON | Clear milestone |
| `add_issue_labels` | `issue_id`, `label_ids` | JSON | Add labels (comma-sep IDs) |
| `remove_issue_labels` | `issue_id`, `label_ids` | JSON | Remove labels |
| `set_issue_assignees` | `issue_id`, `assignee_ids` | JSON | Set assignees |
| `close_issue` | `issue_id`, `[state_reason]` | JSON | Close issue |
| `reopen_issue` | `issue_id` | JSON | Reopen issue |

### FORMAT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `format_issue` | JSON stdin | JSON | Format GraphQL single issue |
| `format_issues_list` | JSON stdin | JSON | Format GraphQL issue list |
| `format_issues_rest` | JSON stdin | JSON | Format REST issue list |

### EXTRACT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `extract_issue_numbers` | JSON stdin | Array | Issue numbers |
| `extract_issue_ids` | JSON stdin | Array | Issue node IDs |

### DETECT Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `check_issue_exists` | `owner`, `repo`, `number` | Exit code | 0 if exists |
| `detect_issue_state` | `owner`, `repo`, `number` | State | "open" or "closed" |

---

## GraphQL Queries

| Query | Parameters | Purpose |
|-------|------------|---------|
| `issue_by_number` | `owner`, `repo`, `number` | Full issue data |
| `issue_id_only` | `owner`, `repo`, `number` | Just node ID |
| `repository_issues` | `owner`, `repo`, `states`, `first` | List issues |
| `issue_with_comments` | `owner`, `repo`, `number`, `commentFirst` | Issue + comments |
| `issue_timeline` | `owner`, `repo`, `number`, `first` | Issue + timeline events |

---

## GraphQL Mutations

| Mutation | Parameters | Purpose |
|----------|------------|---------|
| `set_issue_milestone` | `issueId`, `milestoneId` | Set/clear milestone |
| `update_issue` | `issueId`, `assigneeIds` | Update assignees |
| `close_issue` | `issueId`, `stateReason` | Close issue |
| `reopen_issue` | `issueId` | Reopen issue |
| `add_labels_to_labelable` | `labelableId`, `labelIds` | Add labels |
| `remove_labels_from_labelable` | `labelableId`, `labelIds` | Remove labels |

---

## jq Filters

### Format Filters (GraphQL)

| Filter | Input | Output |
|--------|-------|--------|
| `format_issue` | issue query | Formatted single |
| `format_issues_list` | issues query | Formatted list |
| `format_issue_with_comments` | issue + comments | Full details |
| `format_issues_summary` | issues query | Compact summary |

### Format Filters (REST)

| Filter | Input | Output |
|--------|-------|--------|
| `format_issues_rest` | REST issues array | Formatted list |
| `format_issue_rest` | REST issue object | Formatted single |

### Extract Filters

| Filter | Output |
|--------|--------|
| `extract_issue_id` | Single node ID |
| `extract_issue_numbers` | Array of numbers |
| `extract_issue_ids` | Array of IDs |
| `extract_open_issues` | Open issues only |
| `extract_closed_issues` | Closed issues only |
| `extract_issues_by_label` | Issues with label |
| `extract_issues_by_assignee` | Issues by assignee |
| `extract_issues_by_milestone` | Issues in milestone |

---

## Composition Examples

### List and Filter Issues

```bash
source lib/github/gh-issue-functions.sh

# List open issues
discover_repo_issues "hiivmind" "hiivmind-pulse-gh" "OPEN" | format_issues_list

# Filter by label
discover_repo_issues "hiivmind" "hiivmind-pulse-gh" | filter_issues_by_label "bug"

# Filter by assignee
discover_repo_issues "hiivmind" "hiivmind-pulse-gh" | filter_issues_by_assignee "discreteds"
```

### Close an Issue

```bash
source lib/github/gh-issue-functions.sh

# Get issue ID
ISSUE_ID=$(get_issue_id "hiivmind" "hiivmind-pulse-gh" 123)

# Close as completed
close_issue "$ISSUE_ID" "COMPLETED"

# Or as not planned
close_issue "$ISSUE_ID" "NOT_PLANNED"
```

### Set Milestone on Issue

```bash
source lib/github/gh-issue-functions.sh
source lib/github/gh-milestone-functions.sh

# Get IDs
ISSUE_ID=$(get_issue_id "hiivmind" "hiivmind-pulse-gh" 123)
MILESTONE_ID=$(get_milestone_id "hiivmind" "hiivmind-pulse-gh" "v1.0")

# Set milestone
set_issue_milestone "$ISSUE_ID" "$MILESTONE_ID"
```

### Add Labels to Issue

```bash
source lib/github/gh-issue-functions.sh

# Get IDs
ISSUE_ID=$(get_issue_id "hiivmind" "hiivmind-pulse-gh" 123)
LABEL_ID=$(get_label_id "hiivmind" "hiivmind-pulse-gh" "bug")

# Add label
add_issue_labels "$ISSUE_ID" "$LABEL_ID"
```

### Create Issue with REST

```bash
source lib/github/gh-issue-functions.sh

# Simple issue
create_issue "hiivmind" "hiivmind-pulse-gh" "New feature" "Description here"

# With labels and assignees (comma-separated)
create_issue "hiivmind" "hiivmind-pulse-gh" \
    "Bug report" \
    "Something is broken" \
    "bug,priority" \
    "discreteds"
```

---

## Dependencies

- **External tools:** `gh` (GitHub CLI), `jq` (1.6+), `yq` (4.0+)
- **Other domains:**
  - Identity: `get_user_id` for assignee IDs
  - Milestone: `get_milestone_id` for milestone assignment

## Dependents

- **Project:** May use issue IDs for project item operations

---

## Error Handling

All functions follow these patterns:

1. **Missing arguments:** Return exit code 2 with error message to stderr
2. **API errors:** Propagate gh CLI exit codes
3. **Not found:** Return empty/null output or exit code 1 for check functions

Example error handling:

```bash
ISSUE_ID=$(get_issue_id "owner" "repo" 99999 2>/dev/null)
if [[ -z "$ISSUE_ID" || "$ISSUE_ID" == "null" ]]; then
    echo "Issue not found"
fi
```

---

## Notes

### Issue States

| GraphQL | REST | Description |
|---------|------|-------------|
| `OPEN` | `open` | Issue is open |
| `CLOSED` | `closed` | Issue is closed |

### Close State Reasons

| Value | Description |
|-------|-------------|
| `COMPLETED` | Issue was resolved |
| `NOT_PLANNED` | Issue won't be worked on |
| `DUPLICATE` | Issue is a duplicate |

### REST vs GraphQL

| Operation | API | Reason |
|-----------|-----|--------|
| List issues | Either | REST is simpler, GraphQL more flexible |
| Get single issue | Either | REST for basic, GraphQL for full data |
| Create issue | REST | Simpler parameter handling |
| Update issue | GraphQL | Better field control |
| Close/Reopen | GraphQL | Proper state reason support |
| Add/Remove labels | GraphQL | Uses node IDs for precision |

### REST Includes Pull Requests

The REST `/repos/:owner/:repo/issues` endpoint returns both issues AND pull requests. The `format_issues_rest` filter excludes PRs by checking for absence of the `.pull_request` field.
