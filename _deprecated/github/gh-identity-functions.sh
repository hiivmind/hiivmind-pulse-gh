#!/bin/bash
# GitHub Identity Domain Functions
# Source this file to use: source gh-identity-functions.sh
#
# This domain handles:
# - Users (viewer, specific users by login)
# - Organizations
# - Authentication scopes
# - Owner type detection
#
# Dependencies:
#   - gh (GitHub CLI, authenticated)
#   - jq (1.6+)
#   - yq (4.0+)
#
# Follows hiivmind-pulse-gh architecture principles:
#   - Explicit scope prefixes (viewer_, user_, org_)
#   - Pipe-first composition pattern
#   - Single responsibility per function

set -euo pipefail

# Ensure yq is in PATH (snap installs to /snap/bin on Ubuntu)
export PATH="/snap/bin:$PATH"

# Get the directory where this script is located
IDENTITY_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# YAML template locations
IDENTITY_GRAPHQL_QUERIES="$IDENTITY_SCRIPT_DIR/gh-identity-graphql-queries.yaml"
IDENTITY_JQ_FILTERS="$IDENTITY_SCRIPT_DIR/gh-identity-jq-filters.yaml"

#==============================================================================
# LOOKUP PRIMITIVES
#==============================================================================
# Pattern: get_{entity}_id
# Purpose: Resolve identifiers (login -> node ID)
# Output: Single value (ID string) to stdout

# Get the authenticated user's GraphQL node ID
# Output: Node ID string (e.g., "U_kgDOA...")
get_viewer_id() {
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='{ viewer { id } }' \
        --jq '.data.viewer.id'
}

# Get a specific user's GraphQL node ID by login
# Args: login
# Output: Node ID string
get_user_id() {
    local login="$1"

    if [[ -z "$login" ]]; then
        echo "ERROR: get_user_id requires login argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($login: String!) { user(login: $login) { id } }' \
        -f login="$login" \
        --jq '.data.user.id'
}

# Get an organization's GraphQL node ID by login
# Args: org_login
# Output: Node ID string
get_org_id() {
    local org_login="$1"

    if [[ -z "$org_login" ]]; then
        echo "ERROR: get_org_id requires org_login argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($orgLogin: String!) { organization(login: $orgLogin) { id } }' \
        -f orgLogin="$org_login" \
        --jq '.data.organization.id'
}

#==============================================================================
# FETCH PRIMITIVES
#==============================================================================
# Pattern: fetch_{entity}, discover_{scope}_{entities}
# Purpose: Retrieve data from GitHub API
# Output: JSON to stdout

# Fetch the authenticated user's information
# Output: JSON with viewer data
fetch_viewer() {
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.viewer.query' "$IDENTITY_GRAPHQL_QUERIES")"
}

# Fetch the authenticated user with their organizations
# Output: JSON with viewer and organizations
fetch_viewer_with_orgs() {
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.viewer_with_orgs.query' "$IDENTITY_GRAPHQL_QUERIES")"
}

# Fetch a specific user by login
# Args: login
# Output: JSON with user data
fetch_user() {
    local login="$1"

    if [[ -z "$login" ]]; then
        echo "ERROR: fetch_user requires login argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.specific_user.query' "$IDENTITY_GRAPHQL_QUERIES")" \
        -f login="$login"
}

# Fetch an organization by login
# Args: org_login
# Output: JSON with organization data
fetch_organization() {
    local org_login="$1"

    if [[ -z "$org_login" ]]; then
        echo "ERROR: fetch_organization requires org_login argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.specific_organization.query' "$IDENTITY_GRAPHQL_QUERIES")" \
        -f login="$org_login"
}

# Discover organizations the authenticated user belongs to
# Output: JSON with list of organizations
discover_viewer_organizations() {
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.viewer_organizations.query' "$IDENTITY_GRAPHQL_QUERIES")"
}

#==============================================================================
# DETECT PRIMITIVES
#==============================================================================
# Pattern: detect_{what}
# Purpose: Determine type/state of an entity
# Output: Type string to stdout

# Detect if a login is a user or organization
# Args: login
# Output: "organization" or "user"
detect_owner_type() {
    local login="$1"

    if [[ -z "$login" ]]; then
        echo "ERROR: detect_owner_type requires login argument" >&2
        return 2
    fi

    # Try to access as organization first (more specific)
    if gh api "orgs/$login" --jq '.login' &> /dev/null; then
        echo "organization"
    else
        echo "user"
    fi
}

#==============================================================================
# AUTH SCOPE CHECKING
#==============================================================================
# These functions verify GitHub CLI authentication and scopes

# Required scopes for hiivmind-pulse-gh functionality
REQUIRED_SCOPES=("repo" "read:org")
RECOMMENDED_SCOPES=("read:project" "project")

# Check if GitHub CLI is installed
# Returns: 0 if installed, 1 if not
check_gh_cli() {
    if command -v gh &> /dev/null; then
        return 0
    else
        echo "ERROR: GitHub CLI (gh) not installed" >&2
        echo "  Install:" >&2
        echo "    Ubuntu/Debian: sudo apt install gh" >&2
        echo "    macOS:         brew install gh" >&2
        echo "    Other:         https://cli.github.com/" >&2
        return 1
    fi
}

# Check if user is authenticated to GitHub CLI
# Returns: 0 if authenticated, 1 if not
check_gh_auth() {
    if gh auth status &> /dev/null; then
        return 0
    else
        echo "ERROR: Not authenticated to GitHub CLI" >&2
        echo "  Run: gh auth login" >&2
        return 1
    fi
}

# Get the authenticated account name
# Output: Username string
get_auth_account() {
    gh auth status 2>&1 | grep -oP 'account \K\S+' | head -1
}

# Get current token scopes as a string
# Output: Comma-separated scope list
get_current_scopes() {
    gh auth status 2>&1 | grep "Token scopes:" | sed "s/.*Token scopes: //" | tr -d "'" || echo ""
}

# Check if a specific scope is present
# Args: scope_name
# Returns: 0 if present, 1 if not
has_scope() {
    local scope="$1"
    local current_scopes
    current_scopes=$(get_current_scopes)
    [[ "$current_scopes" =~ $scope ]]
}

# Get list of missing required scopes
# Output: Space-separated list of missing scopes
get_missing_required_scopes() {
    local current_scopes missing=()
    current_scopes=$(get_current_scopes)

    for scope in "${REQUIRED_SCOPES[@]}"; do
        if [[ ! "$current_scopes" =~ $scope ]]; then
            missing+=("$scope")
        fi
    done

    echo "${missing[*]}"
}

# Get list of missing recommended scopes (for Projects v2)
# Output: Space-separated list of missing scopes
get_missing_recommended_scopes() {
    local current_scopes missing=()
    current_scopes=$(get_current_scopes)

    for scope in "${RECOMMENDED_SCOPES[@]}"; do
        if [[ ! "$current_scopes" =~ $scope ]]; then
            missing+=("$scope")
        fi
    done

    echo "${missing[*]}"
}

# Check if all required scopes are present
# Returns: 0 if all present, 1 if any missing
check_required_scopes() {
    local missing
    missing=$(get_missing_required_scopes)

    if [[ -z "$missing" ]]; then
        return 0
    else
        echo "ERROR: Missing required scopes: $missing" >&2
        echo "  Fix: gh auth refresh --scopes 'repo,read:org,read:project,project'" >&2
        return 1
    fi
}

# Check if Projects v2 access works
# Returns: 0 if working, 1 if not
check_projects_access() {
    if gh api graphql -f query='{ viewer { projectsV2(first: 1) { totalCount } } }' &> /dev/null; then
        return 0
    else
        echo "ERROR: Projects v2 access failed" >&2
        echo "  This usually means missing 'read:project' scope" >&2
        echo "  Fix: gh auth refresh --scopes 'repo,read:org,read:project,project'" >&2
        return 1
    fi
}

# Get the command to fix missing scopes
# Output: The gh auth refresh command
get_scope_fix_command() {
    echo "gh auth refresh --scopes 'repo,read:org,read:project,project'"
}

#==============================================================================
# CLI TOOL VERSION CHECKS
#==============================================================================

# Get GitHub CLI version
get_gh_version() {
    gh --version | head -1
}

# Check if jq is installed
# Returns: 0 if installed, 1 if not
check_jq() {
    if command -v jq &> /dev/null; then
        return 0
    else
        echo "ERROR: jq not installed" >&2
        echo "  Install:" >&2
        echo "    Ubuntu/Debian: sudo apt install jq" >&2
        echo "    macOS:         brew install jq" >&2
        return 1
    fi
}

# Get jq version
get_jq_version() {
    jq --version
}

# Check if yq is installed
# Returns: 0 if installed, 1 if not
check_yq() {
    if command -v yq &> /dev/null; then
        return 0
    else
        echo "ERROR: yq not installed" >&2
        echo "  Install:" >&2
        echo "    Ubuntu (snap): sudo snap install yq" >&2
        echo "    macOS:         brew install yq" >&2
        echo "    Other:         https://github.com/mikefarah/yq#install" >&2
        return 1
    fi
}

# Get yq version
get_yq_version() {
    yq --version
}

#==============================================================================
# COMBINED PREREQUISITE CHECK
#==============================================================================

# Check all prerequisites for identity operations
# Returns: 0 if all pass, 1 if any fail
# Outputs: Status for each check
check_identity_prerequisites() {
    local errors=0

    echo "=== Checking Prerequisites ==="
    echo ""

    # Check gh CLI
    echo -n "GitHub CLI (gh): "
    if check_gh_cli 2>/dev/null; then
        echo "$(get_gh_version)"
    else
        echo "NOT FOUND"
        errors=$((errors + 1))
    fi

    # Check jq
    echo -n "jq: "
    if check_jq 2>/dev/null; then
        echo "$(get_jq_version)"
    else
        echo "NOT FOUND"
        errors=$((errors + 1))
    fi

    # Check yq
    echo -n "yq: "
    if check_yq 2>/dev/null; then
        echo "$(get_yq_version)"
    else
        echo "NOT FOUND"
        errors=$((errors + 1))
    fi

    # Check gh auth
    echo -n "GitHub auth: "
    if check_gh_auth 2>/dev/null; then
        echo "Logged in as $(get_auth_account)"
    else
        echo "NOT AUTHENTICATED"
        errors=$((errors + 1))
    fi

    # Check scopes
    echo -n "Token scopes: "
    local scopes
    scopes=$(get_current_scopes)
    echo "$scopes"

    local missing_required missing_recommended
    missing_required=$(get_missing_required_scopes)
    missing_recommended=$(get_missing_recommended_scopes)

    if [[ -n "$missing_required" ]]; then
        echo "  MISSING REQUIRED: $missing_required"
        errors=$((errors + 1))
    fi

    if [[ -n "$missing_recommended" ]]; then
        echo "  MISSING RECOMMENDED: $missing_recommended (needed for Projects v2)"
    fi

    # Check Projects v2 access
    echo -n "Projects v2 access: "
    if check_projects_access 2>/dev/null; then
        echo "OK"
    else
        echo "FAILED"
        errors=$((errors + 1))
    fi

    echo ""

    if [[ $errors -eq 0 ]]; then
        echo "All checks passed!"
        return 0
    else
        echo "$errors issue(s) found."
        echo ""
        echo "Quick fixes:"
        echo "  gh not installed:    sudo apt install gh"
        echo "  jq not installed:    sudo apt install jq"
        echo "  yq not installed:    sudo snap install yq"
        echo "  Not authenticated:   gh auth login"
        echo "  Missing scopes:      $(get_scope_fix_command)"
        return 1
    fi
}

#==============================================================================
# FORMAT PRIMITIVES
#==============================================================================
# Pattern: format_{entity}
# Purpose: Transform JSON to human-readable output
# Input: JSON from stdin
# Output: Formatted text to stdout

# Format viewer information
# Input: JSON from fetch_viewer
# Output: Formatted text
format_viewer() {
    jq -f <(yq '.format_filters.format_viewer.filter' "$IDENTITY_JQ_FILTERS")
}

# Format organizations list
# Input: JSON from discover_viewer_organizations
# Output: Formatted text
format_organizations() {
    jq -f <(yq '.format_filters.format_organizations.filter' "$IDENTITY_JQ_FILTERS")
}

# Format user information
# Input: JSON from fetch_user
# Output: Formatted text
format_user() {
    jq -f <(yq '.format_filters.format_user.filter' "$IDENTITY_JQ_FILTERS")
}

# Format organization information
# Input: JSON from fetch_organization
# Output: Formatted text
format_organization() {
    jq -f <(yq '.format_filters.format_organization.filter' "$IDENTITY_JQ_FILTERS")
}

#==============================================================================
# COMPOSITION EXAMPLES
#==============================================================================
# These show how to compose primitives

# Example: Get viewer info and format it
# fetch_viewer | format_viewer

# Example: Get org ID for use in mutations
# ORG_ID=$(get_org_id "hiivmind")

# Example: Check owner type before deciding which function to use
# OWNER_TYPE=$(detect_owner_type "hiivmind")
# if [[ "$OWNER_TYPE" == "organization" ]]; then
#     fetch_organization "hiivmind"
# else
#     fetch_user "hiivmind"
# fi
