---
name: github-rest-api
description: GitHub REST API operations using the gh CLI. Use for operations not available via GraphQL, such as creating milestones, managing branch protection, or other repository settings.
---

# GitHub REST API Skill

You are an expert at using the GitHub CLI Toolkit's REST API module - for operations that require REST API rather than GraphQL.

## When to Use REST vs GraphQL

| Use REST API for | Use GraphQL for |
|------------------|-----------------|
| Creating milestones | Querying Projects v2 |
| Managing branch protection | Setting milestone on issues |
| Repository settings | Project mutations |
| Webhooks | Complex nested queries |
| Release assets | Batch operations |

## Prerequisites

```bash
source lib/github/gh-rest-functions.sh
```

## Function Reference

### Milestone Operations

| Function | Purpose | Example |
|----------|---------|---------|
| `list_milestones "OWNER" "REPO"` | List milestones | `list_milestones "acme" "api" "open"` |
| `get_milestone "OWNER" "REPO" NUM` | Get milestone | `get_milestone "acme" "api" 3` |
| `create_milestone "OWNER" "REPO" "TITLE"` | Create milestone | `create_milestone "acme" "api" "v2.0"` |
| `update_milestone "OWNER" "REPO" NUM` | Update milestone | `update_milestone "acme" "api" 3 "New Title"` |
| `close_milestone "OWNER" "REPO" NUM` | Close milestone | `close_milestone "acme" "api" 3` |
| `reopen_milestone "OWNER" "REPO" NUM` | Reopen milestone | `reopen_milestone "acme" "api" 3` |

### Helper Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `get_milestone_number_by_title` | Find by title | `get_milestone_number_by_title "acme" "api" "v1.0"` |
| `get_milestone_progress` | Progress stats | `get_milestone_progress "acme" "api" 3` |
| `format_milestones` | Format list | `list_milestones "acme" "api" \| format_milestones` |

## Direct gh api Usage

For operations not yet wrapped in functions, use `gh api` directly:

### Repository Operations

```bash
# Get repository info
gh api repos/OWNER/REPO

# Update repository settings
gh api repos/OWNER/REPO -X PATCH -f description="New description"

# Get repository topics
gh api repos/OWNER/REPO/topics
```

### Branch Protection

```bash
# Get branch protection rules
gh api repos/OWNER/REPO/branches/main/protection

# Update branch protection
gh api repos/OWNER/REPO/branches/main/protection -X PUT \
  -f required_status_checks='{"strict":true,"contexts":["ci"]}' \
  -f enforce_admins=true
```

### Labels

```bash
# List labels
gh api repos/OWNER/REPO/labels

# Create label
gh api repos/OWNER/REPO/labels -X POST \
  -f name="priority:high" \
  -f color="ff0000" \
  -f description="High priority issues"

# Update label
gh api repos/OWNER/REPO/labels/bug -X PATCH \
  -f new_name="type:bug" \
  -f color="d73a4a"
```

### Webhooks

```bash
# List webhooks
gh api repos/OWNER/REPO/hooks

# Create webhook
gh api repos/OWNER/REPO/hooks -X POST \
  -f name="web" \
  -f config='{"url":"https://example.com/webhook","content_type":"json"}' \
  -f events='["push","pull_request"]'
```

### Releases

```bash
# List releases
gh api repos/OWNER/REPO/releases

# Create release
gh api repos/OWNER/REPO/releases -X POST \
  -f tag_name="v1.0.0" \
  -f name="Version 1.0.0" \
  -f body="Release notes here"
```

## Endpoint Reference

Endpoint definitions are in `lib/github/gh-rest-endpoints.yaml`:

```yaml
milestones:
  list:
    method: GET
    endpoint: "repos/{owner}/{repo}/milestones"
  create:
    method: POST
    endpoint: "repos/{owner}/{repo}/milestones"
    body:
      - title (required)
      - description
      - due_on (ISO 8601)
  update:
    method: PATCH
    endpoint: "repos/{owner}/{repo}/milestones/{number}"
```

## Adding New REST Operations

To add new REST operations:

1. **Add endpoint template** to `gh-rest-endpoints.yaml`:
```yaml
branches:
  get_protection:
    method: GET
    endpoint: "repos/{owner}/{repo}/branches/{branch}/protection"
```

2. **Add shell function** to `gh-rest-functions.sh`:
```bash
get_branch_protection() {
    local owner="$1"
    local repo="$2"
    local branch="$3"
    gh api "repos/$owner/$repo/branches/$branch/protection"
}
```

## Error Handling

REST API returns standard HTTP status codes:

| Code | Meaning | Common Cause |
|------|---------|--------------|
| 401 | Unauthorized | Token expired or missing |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 422 | Validation Failed | Invalid parameters |

Check authentication:
```bash
gh auth status
gh auth refresh -s admin:repo_hook  # Add specific scopes
```

## Related Skills

- **github-projects** - Projects v2 GraphQL operations
- **github-milestones** - Focused milestone management
