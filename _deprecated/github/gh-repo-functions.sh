#!/bin/bash
# GitHub Repository Domain Functions
# Source this file to use: source gh-repo-functions.sh
#
# This domain handles:
# - Repository metadata and discovery
# - Branches (listing, detection)
# - Repository type detection (fork/source/template)
# - Visibility detection (public/private/internal)
#
# Dependencies:
#   - gh (GitHub CLI, authenticated)
#   - jq (1.6+)
#   - yq (4.0+)
#   - gh-identity-functions.sh (for detect_owner_type)
#
# Follows hiivmind-pulse-gh architecture principles:
#   - Explicit scope prefixes (repo_, user_, org_, viewer_)
#   - Pipe-first composition pattern
#   - Single responsibility per function

set -euo pipefail

# Ensure yq is in PATH (snap installs to /snap/bin on Ubuntu)
export PATH="/snap/bin:$PATH"

# Get the directory where this script is located
REPO_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# YAML template locations
REPO_GRAPHQL_QUERIES="$REPO_SCRIPT_DIR/gh-repo-graphql-queries.yaml"
REPO_JQ_FILTERS="$REPO_SCRIPT_DIR/gh-repo-jq-filters.yaml"

# Source identity functions for detect_owner_type
# shellcheck source=gh-identity-functions.sh
if [[ -f "$REPO_SCRIPT_DIR/gh-identity-functions.sh" ]]; then
    source "$REPO_SCRIPT_DIR/gh-identity-functions.sh"
fi

#==============================================================================
# LOOKUP PRIMITIVES
#==============================================================================
# Pattern: get_{entity}_id
# Purpose: Resolve identifiers (owner/name -> node ID)
# Output: Single value (ID string) to stdout

# Get a repository's GraphQL node ID
# Args: owner, repo_name
# Output: Node ID string (e.g., "R_kgDO...")
get_repo_id() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: get_repo_id requires owner and repo arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name) { id }
        }' \
        -f owner="$owner" \
        -f name="$repo" \
        --jq '.data.repository.id'
}

#==============================================================================
# FETCH PRIMITIVES
#==============================================================================
# Pattern: fetch_{entity}, discover_{scope}_{entities}
# Purpose: Retrieve data from GitHub API
# Output: JSON to stdout

# Fetch a repository's metadata
# Args: owner, repo_name
# Output: JSON with repository data
fetch_repo() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: fetch_repo requires owner and repo arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.repository.query' "$REPO_GRAPHQL_QUERIES")" \
        -f owner="$owner" \
        -f name="$repo"
}

# Discover repositories for a specific user
# Args: login, [first (default 100)]
# Output: JSON with repository list
discover_user_repos() {
    local login="$1"
    local first="${2:-100}"

    if [[ -z "$login" ]]; then
        echo "ERROR: discover_user_repos requires login argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.user_repositories.query' "$REPO_GRAPHQL_QUERIES")" \
        -f login="$login" \
        -F first="$first"
}

# Discover repositories for an organization
# Args: org_login, [first (default 100)]
# Output: JSON with repository list
discover_org_repos() {
    local org_login="$1"
    local first="${2:-100}"

    if [[ -z "$org_login" ]]; then
        echo "ERROR: discover_org_repos requires org_login argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.organization_repositories.query' "$REPO_GRAPHQL_QUERIES")" \
        -f login="$org_login" \
        -F first="$first"
}

# Discover repositories for the authenticated user (viewer)
# Args: [first (default 100)]
# Output: JSON with repository list
discover_viewer_repos() {
    local first="${1:-100}"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.viewer_repositories.query' "$REPO_GRAPHQL_QUERIES")" \
        -F first="$first"
}

# List branches for a repository
# Args: owner, repo, [first (default 100)]
# Output: JSON with branch list
list_repo_branches() {
    local owner="$1"
    local repo="$2"
    local first="${3:-100}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: list_repo_branches requires owner and repo arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.repository_branches.query' "$REPO_GRAPHQL_QUERIES")" \
        -f owner="$owner" \
        -f name="$repo" \
        -F first="$first"
}

# List branches using REST API (supports protected filter)
# Args: owner, repo, [protected: true/false]
# Output: JSON array of branches
list_branches_rest() {
    local owner="$1"
    local repo="$2"
    local protected="${3:-}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: list_branches_rest requires owner and repo arguments" >&2
        return 2
    fi

    local args=()
    [[ -n "$protected" ]] && args+=(-f protected="$protected")

    gh api --paginate "repos/$owner/$repo/branches" "${args[@]}"
}

#==============================================================================
# DETECT PRIMITIVES
#==============================================================================
# Pattern: detect_{what}
# Purpose: Determine type/state of an entity
# Output: Type string to stdout

# Detect the default branch of a repository
# Args: owner, repo
# Output: Branch name (e.g., "main")
detect_default_branch() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: detect_default_branch requires owner and repo arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo" --jq '.default_branch'
}

# Detect repository visibility
# Args: owner, repo
# Output: "public", "private", or "internal"
detect_repo_visibility() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: detect_repo_visibility requires owner and repo arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo" --jq '.visibility'
}

# Detect repository type (fork, source, template)
# Args: owner, repo
# Output: "fork", "template", or "source"
detect_repo_type() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: detect_repo_type requires owner and repo arguments" >&2
        return 2
    fi

    local repo_json
    repo_json=$(gh api "repos/$owner/$repo" --jq '{fork: .fork, is_template: .is_template}')

    local is_fork is_template
    is_fork=$(echo "$repo_json" | jq -r '.fork')
    is_template=$(echo "$repo_json" | jq -r '.is_template')

    if [[ "$is_fork" == "true" ]]; then
        echo "fork"
    elif [[ "$is_template" == "true" ]]; then
        echo "template"
    else
        echo "source"
    fi
}

# Detect repository owner type (organization or user)
# Args: owner, repo
# Output: "organization" or "user"
detect_repo_owner_type() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: detect_repo_owner_type requires owner and repo arguments" >&2
        return 2
    fi

    local owner_type
    owner_type=$(gh api "repos/$owner/$repo" --jq '.owner.type')

    if [[ "$owner_type" == "Organization" ]]; then
        echo "organization"
    else
        echo "user"
    fi
}

# Check if a branch exists
# Args: owner, repo, branch
# Returns: 0 if exists, 1 if not
check_branch_exists() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: check_branch_exists requires owner, repo, and branch arguments" >&2
        return 2
    fi

    if gh api "repos/$owner/$repo/branches/$branch" --silent 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Check if repository is archived
# Args: owner, repo
# Returns: 0 if archived, 1 if not
check_repo_archived() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: check_repo_archived requires owner and repo arguments" >&2
        return 2
    fi

    local is_archived
    is_archived=$(gh api "repos/$owner/$repo" --jq '.archived')

    if [[ "$is_archived" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

#==============================================================================
# FORMAT PRIMITIVES
#==============================================================================
# Pattern: format_{entity}
# Purpose: Transform JSON to structured output
# Input: JSON from stdin
# Output: Formatted JSON to stdout

# Format repository information
# Input: JSON from fetch_repo
# Output: Formatted JSON
format_repo() {
    jq -f <(yq '.format_filters.format_repo.filter' "$REPO_JQ_FILTERS")
}

# Format repository list
# Input: JSON from discover_*_repos
# Output: Formatted JSON
format_repos_list() {
    jq -f <(yq '.format_filters.format_repos_list.filter' "$REPO_JQ_FILTERS")
}

# Format branch list
# Input: JSON from list_repo_branches
# Output: Formatted JSON
format_branches() {
    jq -f <(yq '.format_filters.format_branches.filter' "$REPO_JQ_FILTERS")
}

# Format branch list from REST API
# Input: JSON array from list_branches_rest
# Output: Formatted JSON
format_branches_rest() {
    jq '[.[] | {
        name: .name,
        protected: .protected,
        sha: .commit.sha
    }]'
}

#==============================================================================
# EXTRACT PRIMITIVES
#==============================================================================
# Pattern: extract_{what}
# Purpose: Pull specific fields from responses
# Input: JSON from stdin
# Output: Extracted data to stdout

# Extract repository names from list
# Input: JSON from discover_*_repos
# Output: Array of names
extract_repo_names() {
    jq -f <(yq '.extract_filters.extract_repo_names.filter' "$REPO_JQ_FILTERS")
}

# Extract branch names from list
# Input: JSON from list_repo_branches
# Output: Array of names
extract_branch_names() {
    jq -f <(yq '.extract_filters.extract_branch_names.filter' "$REPO_JQ_FILTERS")
}

#==============================================================================
# CONVENIENCE FUNCTIONS
#==============================================================================
# Higher-level functions that compose primitives

# Get repository info using REST API (simpler, returns flat JSON)
# Args: owner, repo
# Output: Repository JSON from REST API
get_repo_rest() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: get_repo_rest requires owner and repo arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo"
}

# Get a specific branch
# Args: owner, repo, branch
# Output: Branch JSON from REST API
get_branch() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: get_branch requires owner, repo, and branch arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/branches/$branch"
}

#==============================================================================
# COMPOSITION EXAMPLES
#==============================================================================
# These show how to compose primitives

# Example: Get repo info and format it
# fetch_repo "owner" "repo" | format_repo

# Example: List user's repos and get names
# discover_user_repos "octocat" | extract_repo_names

# Example: Check visibility before performing action
# VISIBILITY=$(detect_repo_visibility "owner" "repo")
# if [[ "$VISIBILITY" == "public" ]]; then
#     echo "This is a public repository"
# fi

# Example: Get default branch for git operations
# DEFAULT_BRANCH=$(detect_default_branch "owner" "repo")
# git checkout "$DEFAULT_BRANCH"
