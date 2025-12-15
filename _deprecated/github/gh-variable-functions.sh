#!/usr/bin/env bash
# GitHub Variables Domain Functions
# Layer 2 primitives for managing unencrypted configuration variables

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

_get_variable_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [ -h "$source" ]; do
        local dir
        dir=$(cd -P "$(dirname "$source")" && pwd)
        source=$(readlink "$source")
        [[ $source != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

# =============================================================================
# FETCH PRIMITIVES
# =============================================================================
# Retrieve single variable with value

# Fetch repository variable
# Args: owner, repo, variable_name
# Output: Variable JSON {name, value, created_at, updated_at}
fetch_repo_variable() {
    local owner="$1"
    local repo="$2"
    local variable_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$variable_name" ]]; then
        echo "ERROR: fetch_repo_variable requires owner, repo, and variable_name" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/variables/$variable_name" \
        -H "Accept: application/vnd.github+json"
}

# Fetch organization variable
# Args: org, variable_name
# Output: Variable JSON {name, value, created_at, updated_at, visibility, ...}
fetch_org_variable() {
    local org="$1"
    local variable_name="$2"

    if [[ -z "$org" || -z "$variable_name" ]]; then
        echo "ERROR: fetch_org_variable requires org and variable_name" >&2
        return 2
    fi

    gh api "orgs/$org/actions/variables/$variable_name" \
        -H "Accept: application/vnd.github+json"
}

# Fetch environment variable
# Args: owner, repo, environment, variable_name
# Output: Variable JSON {name, value, created_at, updated_at}
fetch_env_variable() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local variable_name="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$variable_name" ]]; then
        echo "ERROR: fetch_env_variable requires owner, repo, environment, and variable_name" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/environments/$environment/variables/$variable_name" \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# DISCOVER PRIMITIVES
# =============================================================================
# List variables at various scopes

# Discover repository variables
# Args: owner, repo
# Output: JSON array of variables
discover_repo_variables() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_variables requires owner and repo" >&2
        return 2
    fi

    gh variable list -R "$owner/$repo" --json name,value,createdAt,updatedAt
}

# Discover environment variables
# Args: owner, repo, environment
# Output: JSON array of variables
discover_env_variables() {
    local owner="$1"
    local repo="$2"
    local environment="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" ]]; then
        echo "ERROR: discover_env_variables requires owner, repo, and environment" >&2
        return 2
    fi

    gh variable list -R "$owner/$repo" --env "$environment" --json name,value,createdAt,updatedAt
}

# Discover organization variables
# Args: org
# Output: JSON array of variables
discover_org_variables() {
    local org="$1"

    if [[ -z "$org" ]]; then
        echo "ERROR: discover_org_variables requires org" >&2
        return 2
    fi

    gh variable list --org "$org" --json name,value,createdAt,updatedAt,visibility,numSelectedRepos,selectedReposURL
}

# Discover which repositories can access an organization variable
# Args: org, variable_name
# Output: JSON array of repositories
discover_org_variable_repos() {
    local org="$1"
    local variable_name="$2"

    if [[ -z "$org" || -z "$variable_name" ]]; then
        echo "ERROR: discover_org_variable_repos requires org and variable_name" >&2
        return 2
    fi

    gh api "orgs/$org/actions/variables/$variable_name/repositories" --jq '.repositories'
}

# Discover organization variables available to a repository
# Args: owner, repo
# Output: JSON array of organization variables
discover_org_variables_available() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_org_variables_available requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/organization-variables" --jq '.variables'
}

# Discover repository variables via REST (for pagination)
# Args: owner, repo, [per_page], [page]
# Output: JSON array of variables
discover_repo_variables_rest() {
    local owner="$1"
    local repo="$2"
    local per_page="${3:-30}"
    local page="${4:-1}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_variables_rest requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/variables?per_page=$per_page&page=$page" --jq '.variables'
}

# =============================================================================
# LOOKUP PRIMITIVES
# =============================================================================
# Resolve variable properties

# Get variable value by name
# Args: owner, repo, variable_name, [scope], [env_or_org]
# Output: Variable value as plain text
get_variable_value() {
    local owner="$1"
    local repo="$2"
    local variable_name="$3"
    local scope="${4:-repo}"  # repo|env|org
    local env_or_org="${5:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$variable_name" ]]; then
        echo "ERROR: get_variable_value requires owner, repo, and variable_name" >&2
        return 2
    fi

    case "$scope" in
        repo)
            gh variable get "$variable_name" -R "$owner/$repo"
            ;;
        env)
            if [[ -z "$env_or_org" ]]; then
                echo "ERROR: get_variable_value with scope=env requires environment name" >&2
                return 2
            fi
            gh variable get "$variable_name" -R "$owner/$repo" --env "$env_or_org"
            ;;
        org)
            if [[ -z "$env_or_org" ]]; then
                echo "ERROR: get_variable_value with scope=org requires org name" >&2
                return 2
            fi
            gh variable get "$variable_name" --org "$env_or_org"
            ;;
        *)
            echo "ERROR: Invalid scope '$scope'. Must be: repo, env, or org" >&2
            return 2
            ;;
    esac
}

# Get organization variable visibility
# Args: org, variable_name
# Output: "all" | "private" | "selected"
get_variable_visibility() {
    local org="$1"
    local variable_name="$2"

    if [[ -z "$org" || -z "$variable_name" ]]; then
        echo "ERROR: get_variable_visibility requires org and variable_name" >&2
        return 2
    fi

    gh api "orgs/$org/actions/variables/$variable_name" --jq '.visibility'
}

# =============================================================================
# FILTER PRIMITIVES
# =============================================================================
# Transform/filter JSON data (stdin → stdout)

# Filter organization variables by visibility
# Args: visibility (all|private|selected)
# Input: JSON array of org variables
# Output: Filtered JSON array
filter_variables_by_visibility() {
    local visibility="$1"

    if [[ -z "$visibility" ]]; then
        echo "ERROR: filter_variables_by_visibility requires visibility argument" >&2
        return 2
    fi

    jq --arg vis "$visibility" 'map(select(.visibility == $vis))'
}

# Filter variables by name pattern
# Args: pattern (regex)
# Input: JSON array of variables
# Output: Filtered JSON array
filter_variables_by_name() {
    local pattern="$1"

    if [[ -z "$pattern" ]]; then
        echo "ERROR: filter_variables_by_name requires pattern argument" >&2
        return 2
    fi

    jq --arg pattern "$pattern" 'map(select(.name | test($pattern)))'
}

# Filter variables by value pattern
# Args: pattern (regex)
# Input: JSON array of variables
# Output: Filtered JSON array
filter_variables_by_value() {
    local pattern="$1"

    if [[ -z "$pattern" ]]; then
        echo "ERROR: filter_variables_by_value requires pattern argument" >&2
        return 2
    fi

    jq --arg pattern "$pattern" 'map(select(.value | test($pattern)))'
}

# =============================================================================
# FORMAT PRIMITIVES
# =============================================================================
# Transform JSON to human-readable output (stdin → stdout)

# Format variables as table
# Input: JSON array of variables
# Output: Formatted table
format_variables() {
    jq -r '
        ["NAME", "VALUE", "UPDATED", "VISIBILITY"] as $headers |
        [$headers],
        (.[] | [
            .name,
            .value,
            (.updatedAt // .updated_at),
            (.visibility // "-")
        ]) |
        @tsv
    '
}

# Format single variable detail
# Input: Single variable JSON
# Output: Formatted details
format_variable_detail() {
    jq -r '
        "Variable Name: \(.name)",
        "Value: \(.value)",
        "Created: \(.created_at // .createdAt // "N/A")",
        "Updated: \(.updated_at // .updatedAt)",
        "Visibility: \(.visibility // "N/A")",
        "Selected Repos: \(.num_selected_repos // .numSelectedRepos // "N/A")",
        "Selected Repos URL: \(.selected_repositories_url // .selectedReposURL // "N/A")"
    '
}

# Format repository access list
# Input: JSON array of repositories
# Output: Formatted table
format_variable_repos() {
    jq -r '
        ["REPO_ID", "NAME", "FULL_NAME"] as $headers |
        [$headers],
        (.[] | [.id, .name, .full_name]) |
        @tsv
    '
}

# =============================================================================
# DETECT PRIMITIVES
# =============================================================================
# Determine variable properties

# Detect if variable exists at repository scope
# Args: owner, repo, variable_name
# Output: "true" | "false"
detect_repo_variable_exists() {
    local owner="$1"
    local repo="$2"
    local variable_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$variable_name" ]]; then
        echo "ERROR: detect_repo_variable_exists requires owner, repo, and variable_name" >&2
        return 2
    fi

    if gh api "repos/$owner/$repo/actions/variables/$variable_name" 2>/dev/null >/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# Detect if environment variable exists
# Args: owner, repo, environment, variable_name
# Output: "true" | "false"
detect_env_variable_exists() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local variable_name="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$variable_name" ]]; then
        echo "ERROR: detect_env_variable_exists requires owner, repo, environment, and variable_name" >&2
        return 2
    fi

    if gh api "repos/$owner/$repo/environments/$environment/variables/$variable_name" 2>/dev/null >/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# Detect if organization variable exists
# Args: org, variable_name
# Output: "true" | "false"
detect_org_variable_exists() {
    local org="$1"
    local variable_name="$2"

    if [[ -z "$org" || -z "$variable_name" ]]; then
        echo "ERROR: detect_org_variable_exists requires org and variable_name" >&2
        return 2
    fi

    if gh api "orgs/$org/actions/variables/$variable_name" 2>/dev/null >/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# =============================================================================
# MUTATE PRIMITIVES
# =============================================================================
# Create, update, or delete variables

# Set repository variable
# Args: owner, repo, variable_name, value
# Output: Empty (201 Created or 204 No Content)
set_repo_variable() {
    local owner="$1"
    local repo="$2"
    local variable_name="$3"
    local value="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$variable_name" ]]; then
        echo "ERROR: set_repo_variable requires owner, repo, variable_name, and value" >&2
        return 2
    fi

    # Allow empty string as value
    echo "$value" | gh variable set "$variable_name" -R "$owner/$repo"
}

# Set environment variable
# Args: owner, repo, environment, variable_name, value
# Output: Empty (201 Created or 204 No Content)
set_env_variable() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local variable_name="$4"
    local value="$5"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$variable_name" ]]; then
        echo "ERROR: set_env_variable requires owner, repo, environment, variable_name, and value" >&2
        return 2
    fi

    echo "$value" | gh variable set "$variable_name" -R "$owner/$repo" --env "$environment"
}

# Set organization variable
# Args: org, variable_name, value, [visibility], [repo_ids]
# Output: Empty (201 Created or 204 No Content)
set_org_variable() {
    local org="$1"
    local variable_name="$2"
    local value="$3"
    local visibility="${4:-all}"
    local repo_ids="${5:-}"

    if [[ -z "$org" || -z "$variable_name" ]]; then
        echo "ERROR: set_org_variable requires org, variable_name, and value" >&2
        return 2
    fi

    local args=()
    args+=(--org "$org")
    args+=(--visibility "$visibility")

    if [[ "$visibility" == "selected" && -n "$repo_ids" ]]; then
        args+=(--repos "$repo_ids")
    fi

    echo "$value" | gh variable set "$variable_name" "${args[@]}"
}

# Delete repository variable
# Args: owner, repo, variable_name
# Output: Empty (204 No Content)
delete_repo_variable() {
    local owner="$1"
    local repo="$2"
    local variable_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$variable_name" ]]; then
        echo "ERROR: delete_repo_variable requires owner, repo, and variable_name" >&2
        return 2
    fi

    gh variable delete "$variable_name" -R "$owner/$repo"
}

# Delete environment variable
# Args: owner, repo, environment, variable_name
# Output: Empty (204 No Content)
delete_env_variable() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local variable_name="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$variable_name" ]]; then
        echo "ERROR: delete_env_variable requires owner, repo, environment, and variable_name" >&2
        return 2
    fi

    gh variable delete "$variable_name" -R "$owner/$repo" --env "$environment"
}

# Delete organization variable
# Args: org, variable_name
# Output: Empty (204 No Content)
delete_org_variable() {
    local org="$1"
    local variable_name="$2"

    if [[ -z "$org" || -z "$variable_name" ]]; then
        echo "ERROR: delete_org_variable requires org and variable_name" >&2
        return 2
    fi

    gh variable delete "$variable_name" --org "$org"
}

# Update repository variable via REST
# Args: owner, repo, variable_name, value
# Output: Empty (204 No Content)
update_repo_variable() {
    local owner="$1"
    local repo="$2"
    local variable_name="$3"
    local value="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$variable_name" ]]; then
        echo "ERROR: update_repo_variable requires owner, repo, variable_name, and value" >&2
        return 2
    fi

    gh api -X PATCH "repos/$owner/$repo/actions/variables/$variable_name" \
        -f name="$variable_name" \
        -f value="$value"
}

# Update organization variable via REST
# Args: org, variable_name, value, [visibility], [repo_ids_json]
# Output: Empty (204 No Content)
update_org_variable() {
    local org="$1"
    local variable_name="$2"
    local value="$3"
    local visibility="${4:-all}"
    local repo_ids_json="${5:-}"

    if [[ -z "$org" || -z "$variable_name" ]]; then
        echo "ERROR: update_org_variable requires org, variable_name, and value" >&2
        return 2
    fi

    local args=(-X PATCH)
    args+=(-f name="$variable_name")
    args+=(-f value="$value")
    args+=(-f visibility="$visibility")

    if [[ "$visibility" == "selected" && -n "$repo_ids_json" ]]; then
        args+=(-f selected_repository_ids="$repo_ids_json")
    fi

    gh api "orgs/$org/actions/variables/$variable_name" "${args[@]}"
}

# Update environment variable via REST
# Args: owner, repo, environment, variable_name, value
# Output: Empty (204 No Content)
update_env_variable() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local variable_name="$4"
    local value="$5"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$variable_name" ]]; then
        echo "ERROR: update_env_variable requires owner, repo, environment, variable_name, and value" >&2
        return 2
    fi

    gh api -X PATCH "repos/$owner/$repo/environments/$environment/variables/$variable_name" \
        -f name="$variable_name" \
        -f value="$value"
}

# Set organization variable repository access
# Args: org, variable_name, repo_ids_json (array of repo IDs)
# Output: Empty (204 No Content)
set_org_variable_repos() {
    local org="$1"
    local variable_name="$2"
    local repo_ids_json="$3"

    if [[ -z "$org" || -z "$variable_name" || -z "$repo_ids_json" ]]; then
        echo "ERROR: set_org_variable_repos requires org, variable_name, and repo_ids_json" >&2
        return 2
    fi

    gh api -X PUT "orgs/$org/actions/variables/$variable_name/repositories" \
        -f selected_repository_ids="$repo_ids_json"
}

# Add repository to organization variable access
# Args: org, variable_name, repo_id
# Output: Empty (204 No Content)
add_repo_to_org_variable() {
    local org="$1"
    local variable_name="$2"
    local repo_id="$3"

    if [[ -z "$org" || -z "$variable_name" || -z "$repo_id" ]]; then
        echo "ERROR: add_repo_to_org_variable requires org, variable_name, and repo_id" >&2
        return 2
    fi

    gh api -X PUT "orgs/$org/actions/variables/$variable_name/repositories/$repo_id"
}

# Remove repository from organization variable access
# Args: org, variable_name, repo_id
# Output: Empty (204 No Content)
remove_repo_from_org_variable() {
    local org="$1"
    local variable_name="$2"
    local repo_id="$3"

    if [[ -z "$org" || -z "$variable_name" || -z "$repo_id" ]]; then
        echo "ERROR: remove_repo_from_org_variable requires org, variable_name, and repo_id" >&2
        return 2
    fi

    gh api -X DELETE "orgs/$org/actions/variables/$variable_name/repositories/$repo_id"
}
