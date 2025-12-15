# Identity Domain Index

> **Domain:** Identity
> **Priority:** P0 (Foundation)
> **Files:**
> - `gh-identity-functions.sh` - Shell function primitives
> - `gh-identity-graphql-queries.yaml` - GraphQL query templates
> - `gh-identity-jq-filters.yaml` - jq filter templates

## Overview

The Identity domain handles GitHub users, organizations, and authentication. This is a **foundation domain** - other domains depend on it for resolving identities and detecting owner types.

## Quick Start

```bash
# Source the functions
source lib/github/gh-identity-functions.sh

# Get current user's info
fetch_viewer | format_viewer

# Get a specific user's ID
USER_ID=$(get_user_id "octocat")

# Get an organization's ID
ORG_ID=$(get_org_id "github")

# Detect if login is user or org
OWNER_TYPE=$(detect_owner_type "hiivmind")
```

---

## Function Reference

### LOOKUP Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_viewer_id` | - | Node ID | Current authenticated user's ID |
| `get_user_id` | `login` | Node ID | Specific user's ID by login |
| `get_org_id` | `org_login` | Node ID | Organization's ID by login |

### FETCH Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `fetch_viewer` | - | JSON | Current user's full info |
| `fetch_viewer_with_orgs` | - | JSON | Current user with organizations |
| `fetch_user` | `login` | JSON | Specific user's full info |
| `fetch_organization` | `org_login` | JSON | Organization's full info |
| `discover_viewer_organizations` | - | JSON | List of user's organizations |

### DETECT Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `detect_owner_type` | `login` | "organization" or "user" | Determine login type |

### FORMAT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `format_viewer` | JSON stdin | JSON | Clean viewer object |
| `format_user` | JSON stdin | JSON | Clean user object |
| `format_organization` | JSON stdin | JSON | Clean org object |
| `format_organizations` | JSON stdin | JSON | Clean org list |

### Auth Checking Functions

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `check_gh_cli` | - | exit code | Verify gh installed |
| `check_gh_auth` | - | exit code | Verify authenticated |
| `check_jq` | - | exit code | Verify jq installed |
| `check_yq` | - | exit code | Verify yq installed |
| `get_auth_account` | - | username | Current auth account |
| `get_current_scopes` | - | scope list | Token scopes |
| `has_scope` | `scope` | exit code | Check specific scope |
| `check_required_scopes` | - | exit code | Verify required scopes |
| `check_projects_access` | - | exit code | Verify Projects v2 access |
| `check_identity_prerequisites` | - | report | Full prerequisite check |

---

## GraphQL Queries

| Query | Parameters | Purpose |
|-------|------------|---------|
| `viewer` | - | Current user info |
| `viewer_with_orgs` | - | Current user + orgs |
| `viewer_organizations` | - | Just user's orgs |
| `specific_user` | `login` | User by login |
| `specific_organization` | `login` | Org by login |
| `organization_members` | `login`, `first` | Org member list |
| `organization_teams` | `login`, `first` | Org team list |
| `owner_type_check` | `login` | Detect user vs org |

---

## jq Filters

### Format Filters

| Filter | Input | Output |
|--------|-------|--------|
| `format_viewer` | viewer query | Clean user JSON |
| `format_user` | user query | Clean user JSON |
| `format_organization` | org query | Clean org JSON |
| `format_organizations` | orgs query | Clean org list |
| `format_org_members` | members query | Member list |
| `format_org_teams` | teams query | Team list |

### Extract Filters

| Filter | Output |
|--------|--------|
| `extract_viewer_id` | Node ID string |
| `extract_user_id` | Node ID string |
| `extract_org_id` | Node ID string |
| `extract_org_logins` | Array of logins |
| `extract_member_logins` | Array of logins |
| `extract_team_slugs` | Array of slugs |

---

## Composition Examples

### Get User ID for Mutations

```bash
source lib/github/gh-identity-functions.sh

# Simple lookup
USER_ID=$(get_user_id "octocat")
echo "User ID: $USER_ID"
```

### Check Owner Type Before Querying

```bash
source lib/github/gh-identity-functions.sh

LOGIN="hiivmind"
OWNER_TYPE=$(detect_owner_type "$LOGIN")

if [[ "$OWNER_TYPE" == "organization" ]]; then
    echo "This is an organization"
    fetch_organization "$LOGIN" | format_organization
else
    echo "This is a user"
    fetch_user "$LOGIN" | format_user
fi
```

### List User's Organizations

```bash
source lib/github/gh-identity-functions.sh

discover_viewer_organizations | format_organizations | jq -r '.organizations[].login'
```

### Verify Prerequisites Before Running

```bash
source lib/github/gh-identity-functions.sh

if check_identity_prerequisites; then
    echo "All good, proceeding..."
else
    echo "Fix issues above first"
    exit 1
fi
```

---

## Dependencies

- **External tools:** `gh` (GitHub CLI), `jq` (1.6+), `yq` (4.0+)
- **Other domains:** None (this is a foundation domain)

## Dependents

Other domains that depend on Identity:
- **Repository:** Uses `detect_owner_type` for scoped queries
- **Issue:** Uses `get_user_id` for assignee mutations
- **Pull Request:** Uses `get_user_id` for reviewer mutations
- **Project:** Uses `get_org_id`, `get_user_id` for project lookups

---

## Error Handling

All functions follow these patterns:

1. **Missing arguments:** Return exit code 2 with error message to stderr
2. **API errors:** Propagate gh CLI exit codes
3. **Not found:** Return empty/null output (check with `-z` or `jq 'if .data.X'`)

Example error handling:

```bash
USER_ID=$(get_user_id "nonexistent-user-12345" 2>/dev/null)
if [[ -z "$USER_ID" || "$USER_ID" == "null" ]]; then
    echo "User not found"
fi
```
