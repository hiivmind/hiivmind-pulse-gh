# Pull Request Domain Index

> **Domain:** Pull Request
> **Priority:** P1 (Work Tracking)
> **Depends on:** Identity (for user IDs), Repository (for repo context), Milestone (for milestone IDs)
> **Files:**
> - `gh-pr-functions.sh` - Shell function primitives
> - `gh-pr-graphql-queries.yaml` - GraphQL query templates
> - `gh-pr-jq-filters.yaml` - jq filter templates

## Overview

The Pull Request domain handles GitHub pull requests - queries, filtering, and mutations (labels, assignees, milestones, reviewers, draft status).

**API Selection:**
- **GraphQL:** Complex queries, mutations, draft operations
- **REST:** Simple listing, requesting reviewers by login, merge operations

## Quick Start

```bash
# Source the functions
source lib/github/gh-pr-functions.sh

# List open PRs
discover_repo_prs "hiivmind" "hiivmind-pulse-gh" "OPEN" | format_prs_list

# Get a specific PR
fetch_pr "hiivmind" "hiivmind-pulse-gh" 1 | format_pr

# Get PR ID
PR_ID=$(get_pr_id "hiivmind" "hiivmind-pulse-gh" 1)

# Request review
request_pr_review "hiivmind" "hiivmind-pulse-gh" 1 "reviewer1,reviewer2"
```

---

## Function Reference

### LOOKUP Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_pr_id` | `owner`, `repo`, `number` | Node ID | PR's GraphQL node ID |

### FETCH Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `fetch_pr` | `owner`, `repo`, `number` | JSON | Full PR data (GraphQL) |
| `discover_repo_prs` | `owner`, `repo`, `[states]`, `[first]` | JSON | List PRs in repo |

### REST API Functions

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `list_prs_rest` | `owner`, `repo`, `[state]`, `[per_page]` | JSON | List PRs via REST |
| `get_pr_rest` | `owner`, `repo`, `number` | JSON | Single PR via REST |

### FILTER Primitives

| Function | Args | Input | Output | Description |
|----------|------|-------|--------|-------------|
| `filter_prs_by_state` | `state` | JSON stdin | JSON | Filter by OPEN/CLOSED/MERGED |
| `filter_prs_by_label` | `label` | JSON stdin | JSON | Filter by label name |
| `filter_prs_by_assignee` | `login` | JSON stdin | JSON | Filter by assignee |
| `filter_prs_by_reviewer` | `login` | JSON stdin | JSON | Filter by requested reviewer |
| `filter_prs_by_author` | `login` | JSON stdin | JSON | Filter by author |
| `filter_draft_prs` | - | JSON stdin | JSON | Filter draft PRs only |
| `filter_ready_prs` | - | JSON stdin | JSON | Filter ready PRs only |

### MUTATE Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `set_pr_milestone` | `pr_id`, `milestone_id` | JSON | Set milestone on PR |
| `clear_pr_milestone` | `pr_id` | JSON | Clear milestone |
| `add_pr_labels` | `pr_id`, `label_ids` | JSON | Add labels (comma-sep IDs) |
| `remove_pr_labels` | `pr_id`, `label_ids` | JSON | Remove labels |
| `set_pr_assignees` | `pr_id`, `assignee_ids` | JSON | Set assignees |
| `request_pr_review` | `owner`, `repo`, `number`, `reviewers` | JSON | Request reviewers (REST) |
| `mark_pr_ready` | `pr_id` | JSON | Mark draft as ready |
| `convert_pr_to_draft` | `pr_id` | JSON | Convert to draft |
| `close_pr` | `pr_id` | JSON | Close PR |
| `reopen_pr` | `pr_id` | JSON | Reopen PR |

### FORMAT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `format_pr` | JSON stdin | JSON | Format GraphQL single PR |
| `format_prs_list` | JSON stdin | JSON | Format GraphQL PR list |
| `format_prs_rest` | JSON stdin | JSON | Format REST PR list |

### EXTRACT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `extract_pr_numbers` | JSON stdin | Array | PR numbers |
| `extract_pr_ids` | JSON stdin | Array | PR node IDs |

### DETECT Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `check_pr_exists` | `owner`, `repo`, `number` | Exit code | 0 if exists |
| `detect_pr_state` | `owner`, `repo`, `number` | State | "open", "closed", "merged" |
| `check_pr_mergeable` | `owner`, `repo`, `number` | Exit code | 0 if mergeable |
| `check_pr_is_draft` | `owner`, `repo`, `number` | Exit code | 0 if draft |

---

## GraphQL Queries

| Query | Parameters | Purpose |
|-------|------------|---------|
| `pr_by_number` | `owner`, `repo`, `number` | Full PR data |
| `pr_id_only` | `owner`, `repo`, `number` | Just node ID |
| `repository_prs` | `owner`, `repo`, `states`, `first` | List PRs |
| `pr_with_reviews` | `owner`, `repo`, `number` | PR + detailed reviews |
| `pr_files_changed` | `owner`, `repo`, `number`, `first` | Files changed |

---

## GraphQL Mutations

| Mutation | Parameters | Purpose |
|----------|------------|---------|
| `set_pr_milestone` | `prId`, `milestoneId` | Set/clear milestone |
| `update_pull_request` | `prId`, `assigneeIds` | Update assignees |
| `close_pull_request` | `prId` | Close PR |
| `reopen_pull_request` | `prId` | Reopen PR |
| `mark_ready_for_review` | `prId` | Mark draft as ready |
| `convert_to_draft` | `prId` | Convert to draft |
| `add_labels_to_labelable` | `labelableId`, `labelIds` | Add labels |
| `remove_labels_from_labelable` | `labelableId`, `labelIds` | Remove labels |
| `request_reviews` | `prId`, `userIds`, `teamIds` | Request reviewers |

---

## jq Filters

### Format Filters (GraphQL)

| Filter | Input | Output |
|--------|-------|--------|
| `format_pr` | PR query | Formatted single |
| `format_prs_list` | PRs query | Formatted list |
| `format_pr_with_reviews` | PR + reviews | Full details |
| `format_pr_files` | PR files query | Files changed |
| `format_prs_summary` | PRs query | Compact summary |

### Format Filters (REST)

| Filter | Input | Output |
|--------|-------|--------|
| `format_prs_rest` | REST PRs array | Formatted list |
| `format_pr_rest` | REST PR object | Formatted single |

### Extract Filters

| Filter | Output |
|--------|--------|
| `extract_pr_id` | Single node ID |
| `extract_pr_numbers` | Array of numbers |
| `extract_pr_ids` | Array of IDs |
| `extract_open_prs` | Open PRs only |
| `extract_merged_prs` | Merged PRs only |
| `extract_draft_prs` | Draft PRs only |
| `extract_ready_prs` | Ready PRs only |
| `extract_prs_by_author` | PRs by author |
| `extract_prs_needing_review` | PRs needing review |

---

## Composition Examples

### List and Filter PRs

```bash
source lib/github/gh-pr-functions.sh

# List open PRs
discover_repo_prs "hiivmind" "hiivmind-pulse-gh" "OPEN" | format_prs_list

# Filter by author
discover_repo_prs "hiivmind" "hiivmind-pulse-gh" | filter_prs_by_author "discreteds"

# Get only draft PRs
discover_repo_prs "hiivmind" "hiivmind-pulse-gh" | filter_draft_prs
```

### Request Code Review

```bash
source lib/github/gh-pr-functions.sh

# Request review using REST (simpler with logins)
request_pr_review "hiivmind" "hiivmind-pulse-gh" 1 "reviewer1,reviewer2"
```

### Set Milestone on PR

```bash
source lib/github/gh-pr-functions.sh
source lib/github/gh-milestone-functions.sh

# Get IDs
PR_ID=$(get_pr_id "hiivmind" "hiivmind-pulse-gh" 1)
MILESTONE_ID=$(get_milestone_id "hiivmind" "hiivmind-pulse-gh" "v1.0")

# Set milestone
set_pr_milestone "$PR_ID" "$MILESTONE_ID"
```

### Mark Draft PR as Ready

```bash
source lib/github/gh-pr-functions.sh

# Get PR ID
PR_ID=$(get_pr_id "hiivmind" "hiivmind-pulse-gh" 1)

# Mark as ready for review
mark_pr_ready "$PR_ID"
```

### Check PR State

```bash
source lib/github/gh-pr-functions.sh

# Check if merged
STATE=$(detect_pr_state "hiivmind" "hiivmind-pulse-gh" 1)
echo "PR state: $STATE"  # "open", "closed", or "merged"

# Check if mergeable
if check_pr_mergeable "hiivmind" "hiivmind-pulse-gh" 1; then
    echo "PR is mergeable"
fi
```

---

## Dependencies

- **External tools:** `gh` (GitHub CLI), `jq` (1.6+), `yq` (4.0+)
- **Other domains:**
  - Identity: `get_user_id` for assignee/reviewer IDs
  - Milestone: `get_milestone_id` for milestone assignment

## Dependents

- **Project:** May use PR IDs for project item operations

---

## Error Handling

All functions follow these patterns:

1. **Missing arguments:** Return exit code 2 with error message to stderr
2. **API errors:** Propagate gh CLI exit codes
3. **Not found:** Return empty/null output or exit code 1 for check functions

Example error handling:

```bash
PR_ID=$(get_pr_id "owner" "repo" 99999 2>/dev/null)
if [[ -z "$PR_ID" || "$PR_ID" == "null" ]]; then
    echo "PR not found"
fi
```

---

## Notes

### PR States

| GraphQL | REST | Description |
|---------|------|-------------|
| `OPEN` | `open` | PR is open |
| `CLOSED` | `closed` | PR closed without merge |
| `MERGED` | Check `.merged` | PR was merged |

### Review States

| State | Description |
|-------|-------------|
| `PENDING` | Review not yet submitted |
| `COMMENTED` | Review with comments only |
| `APPROVED` | Changes approved |
| `CHANGES_REQUESTED` | Changes requested |
| `DISMISSED` | Review was dismissed |

### Draft PRs

- GraphQL: `.isDraft` field
- REST: `.draft` field
- Use `mark_pr_ready` to convert draft to ready
- Use `convert_pr_to_draft` to convert ready to draft

### REST vs GraphQL

| Operation | API | Reason |
|-----------|-----|--------|
| List PRs | Either | REST is simpler |
| Get single PR | Either | REST for basic, GraphQL for full |
| Request reviewers | REST | Simpler with logins instead of IDs |
| Draft operations | GraphQL | Not available in REST |
| Update PR | GraphQL | Better field control |
| Merge PR | REST | gh pr merge or REST API |
