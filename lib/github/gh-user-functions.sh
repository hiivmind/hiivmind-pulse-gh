#!/bin/bash
# GitHub User Initialization Functions
# Source this file to use: source gh-user-functions.sh
#
# These functions handle first-time user setup including:
# - Checking CLI tools (gh, jq, yq)
# - Validating GitHub authentication and scopes
# - Fetching and persisting user identity
#
# Dependencies:
#   - gh (GitHub CLI)
#   - jq (1.6+)
#   - yq (4.0+)
#
# Usage:
#   source lib/github/gh-user-functions.sh
#
#   # Run full initialization
#   initialize_user
#
#   # Or run individual checks
#   check_all_prerequisites && fetch_user_identity && create_user_yaml

set -euo pipefail

# Ensure yq is in PATH (snap installs to /snap/bin on Ubuntu)
export PATH="/snap/bin:$PATH"

# Get the directory where this script is located
USER_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Template locations (relative to lib/github/)
USER_YAML_TEMPLATE="$USER_SCRIPT_DIR/../../templates/user.yaml.template"
GITIGNORE_TEMPLATE="$USER_SCRIPT_DIR/../../templates/gitignore.template"

#==============================================================================
# REQUIRED SCOPES
#==============================================================================

# Scopes required for hiivmind-pulse-gh functionality
REQUIRED_SCOPES=("repo" "read:org")
RECOMMENDED_SCOPES=("read:project" "project")  # For Projects v2 access

#==============================================================================
# CLI TOOL CHECKS
#==============================================================================

# Check if GitHub CLI is installed
# Returns 0 if installed, 1 if not
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

# Get GitHub CLI version
get_gh_version() {
    gh --version | head -1
}

# Check if jq is installed
# Returns 0 if installed, 1 if not
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
# Returns 0 if installed, 1 if not
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
# AUTHENTICATION CHECKS
#==============================================================================

# Check if user is authenticated to GitHub CLI
# Returns 0 if authenticated, 1 if not
check_gh_auth() {
    if gh auth status &> /dev/null; then
        return 0
    else
        echo "ERROR: Not authenticated to GitHub CLI" >&2
        echo "  Run: gh auth login" >&2
        echo "" >&2
        echo "  When prompted, select:" >&2
        echo "    - GitHub.com (or your enterprise host)" >&2
        echo "    - HTTPS (recommended)" >&2
        echo "    - Login with a web browser" >&2
        return 1
    fi
}

# Get the authenticated account name
get_auth_account() {
    gh auth status 2>&1 | grep -oP 'account \K\S+' | head -1
}

# Get current token scopes as a string
get_current_scopes() {
    # Scopes appear as: Token scopes: 'scope1', 'scope2', 'scope3'
    # Extract everything after "Token scopes: " and remove quotes
    gh auth status 2>&1 | grep "Token scopes:" | sed "s/.*Token scopes: //" | tr -d "'" || echo ""
}

# Check if a specific scope is present
# Args: scope_name
has_scope() {
    local scope="$1"
    local current_scopes
    current_scopes=$(get_current_scopes)
    [[ "$current_scopes" =~ $scope ]]
}

# Get list of missing required scopes
# Outputs space-separated list of missing scopes
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
# Returns 0 if all present, 1 if any missing
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
# Returns 0 if working, 1 if not
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
get_scope_fix_command() {
    echo "gh auth refresh --scopes 'repo,read:org,read:project,project'"
}

#==============================================================================
# COMBINED PREREQUISITE CHECK
#==============================================================================

# Check all prerequisites for user initialization
# Returns 0 if all pass, 1 if any fail
# Outputs status for each check
check_all_prerequisites() {
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
# USER IDENTITY
#==============================================================================

# Fetch user identity from GitHub API
# Outputs JSON with login, id, name, email
fetch_user_identity() {
    local user_json user_login user_name user_email user_id

    # Get basic user info from REST API
    user_json=$(gh api user)
    user_login=$(echo "$user_json" | jq -r '.login')
    user_name=$(echo "$user_json" | jq -r '.name // empty')
    user_email=$(echo "$user_json" | jq -r '.email // empty')

    # Get GraphQL node ID (new global ID format)
    user_id=$(gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='{ viewer { id } }' --jq '.data.viewer.id')

    # Output as JSON
    jq -n \
        --arg login "$user_login" \
        --arg id "$user_id" \
        --arg name "$user_name" \
        --arg email "$user_email" \
        '{login: $login, id: $id, name: $name, email: $email}'
}

# Display user identity
# Reads JSON from stdin
display_user_identity() {
    local json
    json=$(cat)

    echo "User identity:"
    echo "  Login: $(echo "$json" | jq -r '.login')"
    echo "  ID:    $(echo "$json" | jq -r '.id')"

    local name email
    name=$(echo "$json" | jq -r '.name')
    email=$(echo "$json" | jq -r '.email')

    [[ -n "$name" ]] && echo "  Name:  $name"
    [[ -n "$email" ]] && echo "  Email: $email"
}

#==============================================================================
# USER.YAML MANAGEMENT
#==============================================================================

# Check if user.yaml exists
user_yaml_exists() {
    [[ -f ".hiivmind/github/user.yaml" ]]
}

# Create new user.yaml file from template
# Args: login, id, name, email
create_user_yaml() {
    local login="$1"
    local id="$2"
    local name="${3:-}"
    local email="${4:-}"

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    mkdir -p .hiivmind/github

    # Check template exists
    if [[ ! -f "$USER_YAML_TEMPLATE" ]]; then
        echo "ERROR: Template not found: $USER_YAML_TEMPLATE" >&2
        echo "  Expected at: templates/user.yaml.template" >&2
        return 1
    fi

    # Copy template and substitute placeholders
    cp "$USER_YAML_TEMPLATE" .hiivmind/github/user.yaml

    # Substitute template variables using yq
    yq -i ".user.login = \"$login\"" .hiivmind/github/user.yaml
    yq -i ".user.id = \"$id\"" .hiivmind/github/user.yaml
    yq -i ".user.name = \"$name\"" .hiivmind/github/user.yaml
    yq -i ".user.email = \"$email\"" .hiivmind/github/user.yaml
    yq -i ".cache.user_checked_at = \"$timestamp\"" .hiivmind/github/user.yaml

    # Update the header comment with actual timestamp
    sed -i "s/{{user_checked_at}}/$timestamp/g" .hiivmind/github/user.yaml
    sed -i "s/{{permissions_checked_at}}/null/g" .hiivmind/github/user.yaml

    echo "Created: .hiivmind/github/user.yaml (from template)"
}

# Update existing user.yaml with new identity
# Args: login, id, name, email
update_user_yaml() {
    local login="$1"
    local id="$2"
    local name="${3:-}"
    local email="${4:-}"

    local user_config=".hiivmind/github/user.yaml"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    yq -i ".user.login = \"$login\"" "$user_config"
    yq -i ".user.id = \"$id\"" "$user_config"
    yq -i ".user.name = \"$name\"" "$user_config"
    yq -i ".user.email = \"$email\"" "$user_config"
    yq -i ".cache.user_checked_at = \"$timestamp\"" "$user_config"

    echo "Updated: $user_config"
}

# Save user identity to user.yaml (create or update)
# Reads JSON with login, id, name, email from stdin
save_user_yaml() {
    local json login id name email
    json=$(cat)

    login=$(echo "$json" | jq -r '.login')
    id=$(echo "$json" | jq -r '.id')
    name=$(echo "$json" | jq -r '.name')
    email=$(echo "$json" | jq -r '.email')

    if user_yaml_exists; then
        update_user_yaml "$login" "$id" "$name" "$email"
    else
        create_user_yaml "$login" "$id" "$name" "$email"
    fi
}

#==============================================================================
# GITIGNORE CHECK
#==============================================================================

# Check if user.yaml is in .gitignore
# Returns 0 if present, 1 if not
check_gitignore_has_user_yaml() {
    if [[ -f ".gitignore" ]]; then
        grep -q ".hiivmind/github/user.yaml" .gitignore
    else
        return 1
    fi
}

# Remind user to add user.yaml to .gitignore if needed
remind_gitignore() {
    if ! check_gitignore_has_user_yaml; then
        echo ""
        echo "REMINDER: Add to .gitignore: .hiivmind/github/user.yaml"
        if [[ ! -f ".gitignore" ]]; then
            echo "  Run: echo '.hiivmind/github/user.yaml' >> .gitignore"
        else
            echo "  Run: echo '.hiivmind/github/user.yaml' >> .gitignore"
        fi
    fi
}

#==============================================================================
# MAIN WORKFLOW
#==============================================================================

# Complete user initialization workflow
# This is the main entry point
initialize_user() {
    echo "=== hiivmind-pulse-gh User Setup ==="
    echo ""

    # Check prerequisites
    if ! check_all_prerequisites; then
        echo ""
        echo "Please fix the issues above before continuing."
        return 1
    fi

    echo ""
    echo "Fetching user identity..."

    # Fetch and save user identity
    local user_json
    user_json=$(fetch_user_identity)

    echo "$user_json" | display_user_identity

    echo ""
    echo "Saving to user.yaml..."
    echo "$user_json" | save_user_yaml

    # Gitignore reminder
    remind_gitignore

    echo ""
    echo "User setup complete!"
    echo ""
    echo "Next step: Run hiivmind-pulse-gh-workspace-init to set up your workspace."
}

# Print summary of what initialize_user will do
print_user_init_help() {
    cat << 'EOF'
hiivmind-pulse-gh User Initialization

This script performs first-time setup:
  1. Checks CLI tools (gh, jq, yq)
  2. Validates GitHub authentication
  3. Checks token scopes for Projects v2 access
  4. Fetches your GitHub identity
  5. Creates .hiivmind/github/user.yaml

Usage:
  source lib/github/gh-user-functions.sh
  initialize_user

Individual functions:
  check_all_prerequisites  - Run all checks, show status
  fetch_user_identity      - Get user info from GitHub API
  save_user_yaml           - Create/update user.yaml (reads JSON from stdin)
  check_gitignore_has_user_yaml - Check if user.yaml is gitignored

Scope fix:
  gh auth refresh --scopes 'repo,read:org,read:project,project'
EOF
}
