# Repository Domain Index

> **Domain:** Repository
> **Priority:** P0 (Foundation)
> **Depends on:** Identity
> **Files:**
> - `gh-repo-functions.sh` - Shell function primitives
> - `gh-repo-graphql-queries.yaml` - GraphQL query templates
> - `gh-repo-jq-filters.yaml` - jq filter templates

## Overview

The Repository domain handles GitHub repository metadata, branches, and detection utilities. This is a **foundation domain** - other domains (Issue, PR, Milestone) depend on it for repository context.

## Quick Start

```bash
# Source the functions
source lib/github/gh-repo-functions.sh

# Get repository ID
REPO_ID=$(get_repo_id "hiivmind" "hiivmind-pulse-gh")

# Fetch and format repository info
fetch_repo "hiivmind" "hiivmind-pulse-gh" | format_repo

# Detect repository characteristics
VISIBILITY=$(detect_repo_visibility "hiivmind" "hiivmind-pulse-gh")
DEFAULT_BRANCH=$(detect_default_branch "hiivmind" "hiivmind-pulse-gh")
REPO_TYPE=$(detect_repo_type "hiivmind" "hiivmind-pulse-gh")

# List organization repositories
discover_org_repos "hiivmind" | format_repos_list
```

---

## Function Reference

### LOOKUP Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_repo_id` | `owner`, `repo` | Node ID | Repository's GraphQL node ID |

### FETCH Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `fetch_repo` | `owner`, `repo` | JSON | Full repository metadata |
| `discover_user_repos` | `login`, `[first]` | JSON | List user's repositories |
| `discover_org_repos` | `org_login`, `[first]` | JSON | List org's repositories |
| `discover_viewer_repos` | `[first]` | JSON | List authenticated user's repos |
| `list_repo_branches` | `owner`, `repo`, `[first]` | JSON | List repository branches (GraphQL) |
| `list_branches_rest` | `owner`, `repo`, `[protected]` | JSON | List branches (REST, filterable) |

### DETECT Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `detect_default_branch` | `owner`, `repo` | Branch name | Get default branch (e.g., "main") |
| `detect_repo_visibility` | `owner`, `repo` | Visibility | "public", "private", or "internal" |
| `detect_repo_type` | `owner`, `repo` | Type | "fork", "template", or "source" |
| `detect_repo_owner_type` | `owner`, `repo` | Owner type | "organization" or "user" |
| `check_branch_exists` | `owner`, `repo`, `branch` | Exit code | 0 if exists, 1 if not |
| `check_repo_archived` | `owner`, `repo` | Exit code | 0 if archived, 1 if not |

### FORMAT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `format_repo` | JSON stdin | JSON | Clean repository object |
| `format_repos_list` | JSON stdin | JSON | Clean repository list |
| `format_branches` | JSON stdin | JSON | Clean branch list |
| `format_branches_rest` | JSON stdin | JSON | Format REST branch response |

### EXTRACT Primitives

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `extract_repo_names` | JSON stdin | Array | Extract repository names |
| `extract_branch_names` | JSON stdin | Array | Extract branch names |

### Convenience Functions

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_repo_rest` | `owner`, `repo` | JSON | Get repo via REST API (simpler) |
| `get_branch` | `owner`, `repo`, `branch` | JSON | Get specific branch details |

---

## GraphQL Queries

| Query | Parameters | Purpose |
|-------|------------|---------|
| `repository` | `owner`, `name` | Full repository metadata |
| `repository_minimal` | `owner`, `name` | Basic repo info |
| `repository_id_only` | `owner`, `name` | Just node ID |
| `user_repositories` | `login`, `first` | User's repos |
| `organization_repositories` | `login`, `first` | Org's repos |
| `viewer_repositories` | `first` | Authenticated user's repos |
| `repository_branches` | `owner`, `name`, `first` | Branch list |
| `repository_branch` | `owner`, `name`, `branch` | Single branch |
| `repository_collaborators` | `owner`, `name`, `first` | Collaborator list |

---

## jq Filters

### Format Filters

| Filter | Input | Output |
|--------|-------|--------|
| `format_repo` | repository query | Clean repo JSON |
| `format_repo_summary` | repository query | Minimal repo info |
| `format_repos_list` | repos list query | Formatted list |
| `format_repos_compact` | repos list query | Compact list |
| `format_branches` | branches query | Branch list |
| `format_collaborators` | collaborators query | Collaborator list |
| `format_repository_for_config` | REST API repo | Config-ready JSON (name, id, full_name, default_branch, visibility) |

### Extract Filters

| Filter | Output |
|--------|--------|
| `extract_repo_id` | Node ID string |
| `extract_repo_names` | Array of names |
| `extract_repo_full_names` | Array of owner/repo |
| `extract_branch_names` | Array of branch names |
| `extract_default_branch` | Default branch name |
| `extract_primary_language` | Language name |

### Filter Filters

| Filter | Purpose |
|--------|---------|
| `filter_public_repos` | Only public repos |
| `filter_private_repos` | Only private repos |
| `filter_non_archived` | Exclude archived |
| `filter_by_language` | By primary language |
| `filter_forks` | Only forks |
| `filter_source_repos` | Only non-forks |

---

## Composition Examples

### Get Repository ID for Mutations

```bash
source lib/github/gh-repo-functions.sh

REPO_ID=$(get_repo_id "hiivmind" "hiivmind-pulse-gh")
echo "Repository ID: $REPO_ID"
```

### Check Repository Before Operations

```bash
source lib/github/gh-repo-functions.sh

OWNER="hiivmind"
REPO="hiivmind-pulse-gh"

# Check if archived first
if check_repo_archived "$OWNER" "$REPO"; then
    echo "Repository is archived, cannot modify"
    exit 1
fi

# Get default branch for git operations
DEFAULT_BRANCH=$(detect_default_branch "$OWNER" "$REPO")
echo "Default branch: $DEFAULT_BRANCH"
```

### List All Organization Repositories

```bash
source lib/github/gh-repo-functions.sh

# Get formatted list
discover_org_repos "hiivmind" | format_repos_list

# Get just names
discover_org_repos "hiivmind" | extract_repo_names
```

### Filter Repositories by Criteria

```bash
source lib/github/gh-repo-functions.sh

# Get non-archived public repos
discover_org_repos "github" | jq '[(.data.organization.repositories.nodes[] | select(.isArchived == false and .visibility == "PUBLIC"))]'
```

### Check Branch Before Operations

```bash
source lib/github/gh-repo-functions.sh

if check_branch_exists "hiivmind" "hiivmind-pulse-gh" "develop"; then
    echo "develop branch exists"
else
    echo "develop branch does not exist"
fi
```

---

## Dependencies

- **External tools:** `gh` (GitHub CLI), `jq` (1.6+), `yq` (4.0+)
- **Other domains:** Identity (for `detect_owner_type` if needed)

## Dependents

Other domains that depend on Repository:
- **Issue:** Uses `get_repo_id` for repository context
- **Pull Request:** Uses `get_repo_id` for repository context
- **Milestone:** Uses repository owner/name for API calls
- **Project:** Uses repository linking functions

---

## Error Handling

All functions follow these patterns:

1. **Missing arguments:** Return exit code 2 with error message to stderr
2. **API errors:** Propagate gh CLI exit codes
3. **Not found:** Return empty/null output or exit code 1 for check functions

Example error handling:

```bash
REPO_ID=$(get_repo_id "owner" "nonexistent-repo" 2>/dev/null)
if [[ -z "$REPO_ID" || "$REPO_ID" == "null" ]]; then
    echo "Repository not found"
fi
```

---

## Notes

### Visibility Values

Repository visibility in GitHub:
- `public` / `PUBLIC` - Visible to everyone
- `private` / `PRIVATE` - Visible only to authorized users
- `internal` / `INTERNAL` - Visible to org members (Enterprise only)

Note: REST API returns lowercase, GraphQL returns uppercase.

### Fork vs Source

- **Fork:** Repository created by forking another
- **Source:** Original repository (not a fork)
- **Template:** Repository marked as a template

Use `detect_repo_type` to determine which category a repository falls into.
