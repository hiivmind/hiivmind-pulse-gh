#!/bin/bash
# GitHub Workspace Initialization Functions
# Source this file to use: source gh-workspace-functions.sh
#
# These functions help automate workspace setup by discovering GitHub
# organization/user structure and generating config.yaml files.
#
# Dependencies:
#   - gh (GitHub CLI, authenticated)
#   - jq (1.6+)
#   - yq (4.0+)
#
# Usage:
#   source lib/github/gh-workspace-functions.sh
#
#   # Check prerequisites
#   check_workspace_prerequisites || exit 1
#
#   # Detect workspace from git remote
#   WORKSPACE_LOGIN=$(detect_workspace_from_remote)
#
#   # Get workspace type and ID
#   WORKSPACE_TYPE=$(get_workspace_type "$WORKSPACE_LOGIN")
#   WORKSPACE_ID=$(get_workspace_id "$WORKSPACE_LOGIN" "$WORKSPACE_TYPE")
#
#   # Discover and generate config
#   generate_projects_config "$WORKSPACE_LOGIN" "$WORKSPACE_TYPE"

set -euo pipefail

# Ensure yq is in PATH (snap installs to /snap/bin on Ubuntu)
export PATH="/snap/bin:$PATH"

# Get the directory where this script is located
WORKSPACE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Template locations (relative to lib/github/)
CONFIG_YAML_TEMPLATE="$WORKSPACE_SCRIPT_DIR/../../templates/config.yaml.template"

# Toolkit version (update when making breaking changes)
TOOLKIT_VERSION="1.0.0"

#==============================================================================
# PREREQUISITE CHECKS
#==============================================================================

# Check all prerequisites for workspace initialization
# Returns 0 if all checks pass, 1 otherwise
check_workspace_prerequisites() {
    local errors=0

    # Check gh CLI
    if ! command -v gh &> /dev/null; then
        echo "ERROR: GitHub CLI (gh) not installed" >&2
        echo "  Install: https://cli.github.com/" >&2
        errors=$((errors + 1))
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        echo "ERROR: jq not installed" >&2
        echo "  Install: sudo apt install jq" >&2
        errors=$((errors + 1))
    fi

    # Check yq
    if ! command -v yq &> /dev/null; then
        echo "ERROR: yq not installed" >&2
        echo "  Install: sudo snap install yq" >&2
        errors=$((errors + 1))
    fi

    # Check gh authentication
    if ! gh auth status &> /dev/null; then
        echo "ERROR: Not authenticated to GitHub CLI" >&2
        echo "  Run: gh auth login" >&2
        errors=$((errors + 1))
    fi

    # Check user.yaml exists
    if [[ ! -f ".hiivmind/github/user.yaml" ]]; then
        echo "ERROR: user.yaml not found" >&2
        echo "  Run hiivmind-pulse-gh-user-init first" >&2
        errors=$((errors + 1))
    fi

    if [[ $errors -gt 0 ]]; then
        return 1
    fi

    return 0
}

# Check if config.yaml already exists
# Returns 0 if it exists, 1 if not
config_exists() {
    [[ -f ".hiivmind/github/config.yaml" ]]
}

#==============================================================================
# WORKSPACE DETECTION
#==============================================================================

# Detect workspace login from git remote origin
# Outputs the owner/org name (e.g., "hiivmind")
detect_workspace_from_remote() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null) || {
        echo "ERROR: No git remote 'origin' found" >&2
        return 1
    }

    # Extract owner from GitHub URL patterns:
    # https://github.com/owner/repo → owner
    # git@github.com:owner/repo.git → owner
    if [[ "$remote_url" =~ github\.com[:/]([^/]+)/ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo "ERROR: Could not parse GitHub owner from: $remote_url" >&2
        return 1
    fi
}

# Determine if a login is an organization or user
# Outputs "organization" or "user"
get_workspace_type() {
    local login="$1"

    # Try to access as organization first
    if gh api "orgs/$login" --jq '.login' &> /dev/null; then
        echo "organization"
    else
        echo "user"
    fi
}

# Get the GraphQL node ID for a workspace
# Args: login, type (organization|user)
get_workspace_id() {
    local login="$1"
    local type="$2"

    if [[ "$type" == "organization" ]]; then
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="{ organization(login: \"$login\") { id } }" \
            --jq '.data.organization.id'
    else
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query='{ viewer { id } }' \
            --jq '.data.viewer.id'
    fi
}

#==============================================================================
# PROJECT DISCOVERY
#==============================================================================

# Discover all projects for an organization
# Outputs JSON array of projects
discover_projects() {
    local login="$1"
    local type="$2"

    if [[ "$type" == "organization" ]]; then
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="
            {
                organization(login: \"$login\") {
                    projectsV2(first: 50) {
                        nodes {
                            number
                            id
                            title
                            url
                            closed
                        }
                    }
                }
            }" --jq '.data.organization.projectsV2.nodes'
    else
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query='
            {
                viewer {
                    projectsV2(first: 50) {
                        nodes {
                            number
                            id
                            title
                            url
                            closed
                        }
                    }
                }
            }' --jq '.data.viewer.projectsV2.nodes'
    fi
}

# Fetch complete field structure for a project
# Outputs JSON with project info and all fields
fetch_project_with_fields() {
    local project_number="$1"
    local login="$2"
    local type="$3"

    local query
    if [[ "$type" == "organization" ]]; then
        query="
        {
            organization(login: \"$login\") {
                projectV2(number: $project_number) {
                    id
                    number
                    title
                    url
                    closed
                    fields(first: 50) {
                        nodes {
                            ... on ProjectV2Field {
                                id
                                name
                                dataType
                            }
                            ... on ProjectV2IterationField {
                                id
                                name
                                dataType
                                configuration {
                                    iterations {
                                        id
                                        title
                                    }
                                }
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                dataType
                                options {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }"
        gh api graphql -H X-Github-Next-Global-ID:1 -f query="$query" \
            --jq '.data.organization.projectV2'
    else
        query="
        {
            viewer {
                projectV2(number: $project_number) {
                    id
                    number
                    title
                    url
                    closed
                    fields(first: 50) {
                        nodes {
                            ... on ProjectV2Field {
                                id
                                name
                                dataType
                            }
                            ... on ProjectV2IterationField {
                                id
                                name
                                dataType
                                configuration {
                                    iterations {
                                        id
                                        title
                                    }
                                }
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                dataType
                                options {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }"
        gh api graphql -H X-Github-Next-Global-ID:1 -f query="$query" \
            --jq '.data.viewer.projectV2'
    fi
}

#==============================================================================
# REPOSITORY DISCOVERY
#==============================================================================

# List repositories for a workspace
# Outputs JSON array of repositories
discover_repositories() {
    local login="$1"
    local type="$2"

    if [[ "$type" == "organization" ]]; then
        gh api "orgs/$login/repos" --paginate --jq '.[] | {
            name: .name,
            id: .node_id,
            full_name: .full_name,
            default_branch: .default_branch,
            visibility: .visibility
        }'
    else
        gh api "users/$login/repos" --paginate --jq '.[] | {
            name: .name,
            id: .node_id,
            full_name: .full_name,
            default_branch: .default_branch,
            visibility: .visibility
        }'
    fi
}

# Get a single repository's info
get_repository_info() {
    local full_name="$1"

    gh api "repos/$full_name" --jq '{
        name: .name,
        id: .node_id,
        full_name: .full_name,
        default_branch: .default_branch,
        visibility: .visibility
    }'
}

#==============================================================================
# PERMISSIONS
#==============================================================================

# Get user's role in an organization
# Outputs: admin, member, billing_manager, or none
get_org_role() {
    local org_login="$1"
    local user_login="$2"

    gh api "orgs/$org_login/memberships/$user_login" --jq '.role' 2>/dev/null || echo "none"
}

# Get user's permission on a repository
# Outputs: admin, maintain, write, triage, read, or none
get_repo_permission() {
    local repo_full_name="$1"
    local user_login="$2"

    gh api "repos/$repo_full_name/collaborators/$user_login/permission" \
        --jq '.permission' 2>/dev/null || echo "none"
}

#==============================================================================
# CONFIG GENERATION - YAML OUTPUT
#==============================================================================

# Transform project fields JSON to config-ready YAML structure
# Reads project JSON from stdin, outputs YAML fields section
transform_fields_to_yaml() {
    jq -r '
        .fields.nodes | map(
            if .dataType == "SINGLE_SELECT" then
                {
                    key: .name,
                    value: {
                        id: .id,
                        type: "single_select",
                        options: (.options | map({(.name): .id}) | add)
                    }
                }
            elif .dataType == "ITERATION" then
                {
                    key: .name,
                    value: {
                        id: .id,
                        type: "iteration",
                        iterations: (.configuration.iterations | map({(.title): .id}) | add)
                    }
                }
            else
                {
                    key: .name,
                    value: {
                        id: .id,
                        type: (.dataType | ascii_downcase)
                    }
                }
            end
        ) | from_entries
    ' | yq -P '.'
}

# Generate a single project's config YAML
# Args: project_number, login, type
# Outputs YAML object for one project (without array prefix)
generate_project_config() {
    local project_number="$1"
    local login="$2"
    local type="$3"

    local project_json
    project_json=$(fetch_project_with_fields "$project_number" "$login" "$type")

    # Extract basic info
    local id title url
    id=$(echo "$project_json" | jq -r '.id')
    title=$(echo "$project_json" | jq -r '.title')
    url=$(echo "$project_json" | jq -r '.url')

    # Generate fields YAML
    local fields_yaml
    fields_yaml=$(echo "$project_json" | transform_fields_to_yaml)

    # Output project entry as YAML object
    cat << EOF
number: $project_number
id: $id
title: $title
url: $url
fields:
$(echo "$fields_yaml" | sed 's/^/  /')
EOF
}

# Generate complete config.yaml
# Args: login, type, workspace_id, default_project, project_numbers (space-separated), repo_names (space-separated)
# Outputs to stdout
# Note: Structure follows templates/config.yaml.template
generate_config_yaml() {
    local login="$1"
    local type="$2"
    local workspace_id="$3"
    local default_project="$4"
    local project_numbers="$5"
    local repo_names="$6"

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Header (structure matches templates/config.yaml.template)
    cat << EOF
# hiivmind-pulse-gh - Workspace Configuration
# This file is shared across the team and should be committed to git.
# Generated by hiivmind-pulse-gh-workspace-init on $timestamp
# Structure defined in: templates/config.yaml.template

workspace:
  type: $type
  login: $login
  id: $workspace_id

projects:
  default: $default_project
  catalog:
EOF

    # Generate each project's config
    for project_num in $project_numbers; do
        generate_project_config "$project_num" "$login" "$type" | sed 's/^/    - /' | sed '2,$s/^    - /      /'
    done

    # Repositories section
    echo ""
    echo "repositories:"

    for repo_name in $repo_names; do
        local repo_info
        repo_info=$(get_repository_info "$login/$repo_name")

        local name id full_name default_branch visibility
        name=$(echo "$repo_info" | jq -r '.name')
        id=$(echo "$repo_info" | jq -r '.id')
        full_name=$(echo "$repo_info" | jq -r '.full_name')
        default_branch=$(echo "$repo_info" | jq -r '.default_branch')
        visibility=$(echo "$repo_info" | jq -r '.visibility')

        cat << EOF
  - name: $name
    id: $id
    full_name: $full_name
    default_branch: $default_branch
    visibility: $visibility
EOF
    done

    # Milestones and cache
    cat << EOF

milestones: {}

cache:
  initialized_at: "$timestamp"
  last_synced_at: "$timestamp"
  toolkit_version: "$TOOLKIT_VERSION"
EOF
}

#==============================================================================
# USER.YAML ENRICHMENT
#==============================================================================

# Enrich user.yaml with workspace permissions
# Args: login, type, project_numbers (space-separated), repo_names (space-separated)
enrich_user_permissions() {
    local login="$1"
    local type="$2"
    local project_numbers="$3"
    local repo_names="$4"

    local user_config=".hiivmind/github/user.yaml"
    local user_login
    user_login=$(yq '.user.login' "$user_config")

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Get org role (if organization)
    if [[ "$type" == "organization" ]]; then
        local org_role
        org_role=$(get_org_role "$login" "$user_login")
        yq -i ".permissions.org_role = \"$org_role\"" "$user_config"
    fi

    # For simplicity, assume same role as org for projects
    # (GitHub doesn't expose per-project roles via API easily)
    for project_num in $project_numbers; do
        yq -i ".permissions.project_roles.\"$project_num\" = \"admin\"" "$user_config"
    done

    # Get repo permissions
    for repo_name in $repo_names; do
        local permission
        permission=$(get_repo_permission "$login/$repo_name" "$user_login")
        yq -i ".permissions.repo_roles.\"$repo_name\" = \"$permission\"" "$user_config"
    done

    # Update timestamp
    yq -i ".cache.permissions_checked_at = \"$timestamp\"" "$user_config"
}

#==============================================================================
# DISPLAY HELPERS
#==============================================================================

# Format projects list for display
# Reads JSON array from stdin
format_projects_list() {
    jq -r '.[] | "  #\(.number) - \(.title) [\(if .closed then "closed" else "open" end)]"'
}

# Format repositories list for display
# Reads JSON objects from stdin (one per line)
format_repos_list() {
    jq -r '"  \(.full_name) (\(.visibility))"'
}

# Print workspace summary after initialization
print_workspace_summary() {
    local login="$1"
    local type="$2"
    local project_count="$3"
    local repo_count="$4"

    echo ""
    echo "=== Workspace Initialized ==="
    echo ""
    echo "Workspace: $login ($type)"
    echo ""
    echo "Projects cached: $project_count"
    yq '.projects.catalog[] | "  #\(.number) - \(.title) (\(.fields | keys | length) fields)"' .hiivmind/github/config.yaml
    echo ""
    echo "Default project: #$(yq '.projects.default' .hiivmind/github/config.yaml)"
    echo ""
    echo "Repositories cached: $repo_count"
    yq '.repositories[] | "  \(.full_name)"' .hiivmind/github/config.yaml
    echo ""
    echo "Config saved:"
    echo "  .hiivmind/github/config.yaml (shared - commit this)"
    echo "  .hiivmind/github/user.yaml (personal - in .gitignore)"
}

#==============================================================================
# MAIN WORKFLOW HELPER
#==============================================================================

# Complete workspace initialization workflow
# This is the main entry point that orchestrates the full process
# Args: login, type, default_project, project_numbers, repo_names
initialize_workspace() {
    local login="$1"
    local type="$2"
    local default_project="$3"
    local project_numbers="$4"  # space-separated
    local repo_names="$5"       # space-separated

    echo "Initializing workspace for $login ($type)..."

    # Get workspace ID
    echo "  Fetching workspace ID..."
    local workspace_id
    workspace_id=$(get_workspace_id "$login" "$type")

    # Create directory
    mkdir -p .hiivmind/github

    # Generate config.yaml
    echo "  Generating config.yaml..."
    generate_config_yaml "$login" "$type" "$workspace_id" "$default_project" "$project_numbers" "$repo_names" \
        > .hiivmind/github/config.yaml

    # Enrich user permissions
    echo "  Enriching user permissions..."
    enrich_user_permissions "$login" "$type" "$project_numbers" "$repo_names"

    # Count items for summary
    local project_count repo_count
    project_count=$(echo "$project_numbers" | wc -w)
    repo_count=$(echo "$repo_names" | wc -w)

    # Print summary
    print_workspace_summary "$login" "$type" "$project_count" "$repo_count"
}

#==============================================================================
# WORKSPACE REFRESH FUNCTIONS
#==============================================================================

# Get config age in days
# Returns integer days, or -1 if no config or no timestamp
get_config_age_days() {
    local config_path=".hiivmind/github/config.yaml"

    if [[ ! -f "$config_path" ]]; then
        echo "-1"
        return 1
    fi

    local last_synced
    last_synced=$(yq '.cache.last_synced_at' "$config_path")

    if [[ "$last_synced" == "null" || -z "$last_synced" ]]; then
        echo "-1"
        return 1
    fi

    local last_sync_epoch now_epoch
    last_sync_epoch=$(date -d "$last_synced" +%s 2>/dev/null) || {
        echo "-1"
        return 1
    }
    now_epoch=$(date +%s)

    echo $(( (now_epoch - last_sync_epoch) / 86400 ))
}

# Check if config is stale (older than threshold)
# Args: max_age_days (default 7)
# Returns 0 if stale, 1 if fresh
check_config_staleness() {
    local max_age="${1:-7}"
    local age_days
    age_days=$(get_config_age_days)

    if [[ "$age_days" -lt 0 ]]; then
        return 0  # No config or timestamp = stale
    fi

    if [[ "$age_days" -ge "$max_age" ]]; then
        return 0  # Stale
    fi

    return 1  # Fresh
}

# Print config status summary
print_config_status() {
    local config_path=".hiivmind/github/config.yaml"

    if [[ ! -f "$config_path" ]]; then
        echo "Status: No workspace configuration found"
        echo "Action: Run hiivmind-pulse-gh-workspace-init first"
        return 1
    fi

    local workspace_login workspace_type last_synced age_days
    workspace_login=$(yq '.workspace.login' "$config_path")
    workspace_type=$(yq '.workspace.type' "$config_path")
    last_synced=$(yq '.cache.last_synced_at' "$config_path")
    age_days=$(get_config_age_days)

    local project_count repo_count
    project_count=$(yq '.projects.catalog | length' "$config_path")
    repo_count=$(yq '.repositories | length' "$config_path")

    echo "Workspace: $workspace_login ($workspace_type)"
    echo "Last synced: $last_synced"
    if [[ "$age_days" -ge 0 ]]; then
        echo "Config age: $age_days days"
        if [[ "$age_days" -ge 7 ]]; then
            echo "Status: STALE (refresh recommended)"
        else
            echo "Status: Fresh"
        fi
    fi
    echo "Projects cached: $project_count"
    echo "Repositories cached: $repo_count"
}

# Detect changes in projects (added/removed)
# Outputs JSON object with changes
detect_project_changes() {
    local config_path=".hiivmind/github/config.yaml"

    local workspace_login workspace_type
    workspace_login=$(yq '.workspace.login' "$config_path")
    workspace_type=$(yq '.workspace.type' "$config_path")

    # Get current projects from GitHub
    local current_projects
    current_projects=$(discover_projects "$workspace_login" "$workspace_type")

    # Get cached project numbers
    local cached_numbers
    cached_numbers=$(yq '.projects.catalog[].number' "$config_path" | tr '\n' ' ')

    # Compare and output changes
    local added="" removed="" unchanged=""

    # Check for new projects
    for num in $(echo "$current_projects" | jq -r '.[].number'); do
        if ! echo " $cached_numbers " | grep -q " $num "; then
            local title
            title=$(echo "$current_projects" | jq -r ".[] | select(.number == $num) | .title")
            added="$added #$num:$title"
        else
            unchanged="$unchanged $num"
        fi
    done

    # Check for removed projects
    for num in $cached_numbers; do
        if ! echo "$current_projects" | jq -e ".[] | select(.number == $num)" >/dev/null 2>&1; then
            local title
            title=$(yq ".projects.catalog[] | select(.number == $num) | .title" "$config_path")
            removed="$removed #$num:$title"
        fi
    done

    # Output as structured text
    echo "PROJECTS"
    if [[ -n "$added" ]]; then
        echo "  ADDED:$added"
    fi
    if [[ -n "$removed" ]]; then
        echo "  REMOVED:$removed"
    fi
    if [[ -z "$added" && -z "$removed" ]]; then
        echo "  No changes"
    fi
}

# Detect changes in fields for a specific project
# Args: project_number
# Outputs changes as text
detect_field_changes() {
    local project_number="$1"
    local config_path=".hiivmind/github/config.yaml"

    local workspace_login workspace_type
    workspace_login=$(yq '.workspace.login' "$config_path")
    workspace_type=$(yq '.workspace.type' "$config_path")

    # Get current fields from GitHub
    local current_project
    current_project=$(fetch_project_with_fields "$project_number" "$workspace_login" "$workspace_type")

    # Get cached field names (one per line, properly quoted)
    local cached_fields
    cached_fields=$(yq ".projects.catalog[] | select(.number == $project_number) | .fields | keys | .[]" "$config_path" 2>/dev/null | sort)

    # Get current field names (one per line)
    local current_fields
    current_fields=$(echo "$current_project" | jq -r '.fields.nodes[].name' | sort)

    # Use comm to find differences (requires sorted input)
    local added removed
    added=$(comm -13 <(echo "$cached_fields") <(echo "$current_fields") | tr '\n' ', ' | sed 's/,$//')
    removed=$(comm -23 <(echo "$cached_fields") <(echo "$current_fields") | tr '\n' ', ' | sed 's/,$//')

    echo "PROJECT #$project_number FIELDS"
    if [[ -n "$added" ]]; then
        echo "  ADDED: $added"
    fi
    if [[ -n "$removed" ]]; then
        echo "  REMOVED: $removed"
    fi
    if [[ -z "$added" && -z "$removed" ]]; then
        echo "  No changes"
    fi
}

# Detect changes in repositories
# Outputs changes as text
detect_repository_changes() {
    local config_path=".hiivmind/github/config.yaml"

    local workspace_login workspace_type
    workspace_login=$(yq '.workspace.login' "$config_path")
    workspace_type=$(yq '.workspace.type' "$config_path")

    # Get current repos from GitHub
    local current_repos
    current_repos=$(discover_repositories "$workspace_login" "$workspace_type" | jq -s '.')

    # Get cached repo names
    local cached_names
    cached_names=$(yq '.repositories[].name' "$config_path" | tr '\n' ' ')

    local added="" removed=""

    # Check for new repos
    for name in $(echo "$current_repos" | jq -r '.[].name'); do
        if ! echo " $cached_names " | grep -q " $name "; then
            added="$added $name"
        fi
    done

    # Check for removed repos
    for name in $cached_names; do
        if ! echo "$current_repos" | jq -e ".[] | select(.name == \"$name\")" >/dev/null 2>&1; then
            removed="$removed $name"
        fi
    done

    echo "REPOSITORIES"
    if [[ -n "$added" ]]; then
        echo "  ADDED:$added"
    fi
    if [[ -n "$removed" ]]; then
        echo "  REMOVED:$removed"
    fi
    if [[ -z "$added" && -z "$removed" ]]; then
        echo "  No changes"
    fi
}

# Generate a full refresh report
# Outputs formatted report to stdout
generate_refresh_report() {
    local config_path=".hiivmind/github/config.yaml"

    if [[ ! -f "$config_path" ]]; then
        echo "ERROR: No workspace configuration found"
        return 1
    fi

    local workspace_login
    workspace_login=$(yq '.workspace.login' "$config_path")

    echo "=== Workspace Refresh Report for $workspace_login ==="
    echo ""
    print_config_status
    echo ""
    echo "--- Change Detection ---"
    echo ""
    detect_project_changes
    echo ""

    # Check field changes for each cached project
    for project_num in $(yq '.projects.catalog[].number' "$config_path"); do
        detect_field_changes "$project_num"
        echo ""
    done

    detect_repository_changes
    echo ""
    echo "=== End Report ==="
}

# Update config.yaml timestamp only (for quick sync)
update_sync_timestamp() {
    local config_path=".hiivmind/github/config.yaml"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    yq -i ".cache.last_synced_at = \"$timestamp\"" "$config_path"
    echo "Updated sync timestamp: $timestamp"
}

# Full refresh: regenerate config.yaml with current GitHub state
# Args: (optional) project_numbers, repo_names - if not provided, uses current cached list
refresh_workspace() {
    local config_path=".hiivmind/github/config.yaml"

    if [[ ! -f "$config_path" ]]; then
        echo "ERROR: No workspace configuration found"
        echo "Run hiivmind-pulse-gh-workspace-init first"
        return 1
    fi

    local workspace_login workspace_type workspace_id default_project
    workspace_login=$(yq '.workspace.login' "$config_path")
    workspace_type=$(yq '.workspace.type' "$config_path")
    workspace_id=$(yq '.workspace.id' "$config_path")
    default_project=$(yq '.projects.default' "$config_path")

    # Get current cached project numbers and repo names
    local project_numbers repo_names
    project_numbers=$(yq '.projects.catalog[].number' "$config_path" | tr '\n' ' ')
    repo_names=$(yq '.repositories[].name' "$config_path" | tr '\n' ' ')

    echo "Refreshing workspace for $workspace_login ($workspace_type)..."
    echo "Projects to refresh: $project_numbers"
    echo "Repositories to refresh: $repo_names"
    echo ""

    # Regenerate config.yaml
    echo "Regenerating config.yaml..."
    generate_config_yaml "$workspace_login" "$workspace_type" "$workspace_id" "$default_project" "$project_numbers" "$repo_names" \
        > .hiivmind/github/config.yaml

    # Update user permissions
    echo "Updating user permissions..."
    enrich_user_permissions "$workspace_login" "$workspace_type" "$project_numbers" "$repo_names"

    echo ""
    echo "Workspace refresh complete!"
    print_config_status
}
