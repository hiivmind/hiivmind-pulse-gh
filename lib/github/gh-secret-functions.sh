#!/usr/bin/env bash
# GitHub Secrets Domain Functions
# Layer 2 primitives for managing encrypted secrets

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

_get_secret_script_dir() {
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
# Retrieve public keys for secret encryption

# Fetch repository public key for secret encryption
# Args: owner, repo, app (actions|dependabot|codespaces)
# Output: Public key JSON {key_id, key}
fetch_repo_public_key() {
    local owner="$1"
    local repo="$2"
    local app="${3:-actions}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: fetch_repo_public_key requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/$app/secrets/public-key" -H "Accept: application/vnd.github+json"
}

# Fetch organization public key for secret encryption
# Args: org, app (actions|dependabot)
# Output: Public key JSON {key_id, key}
fetch_org_public_key() {
    local org="$1"
    local app="${2:-actions}"

    if [[ -z "$org" ]]; then
        echo "ERROR: fetch_org_public_key requires org" >&2
        return 2
    fi

    gh api "orgs/$org/$app/secrets/public-key" -H "Accept: application/vnd.github+json"
}

# Fetch environment public key for secret encryption
# Args: owner, repo, environment
# Output: Public key JSON {key_id, key}
fetch_env_public_key() {
    local owner="$1"
    local repo="$2"
    local environment="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" ]]; then
        echo "ERROR: fetch_env_public_key requires owner, repo, and environment" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/environments/$environment/secrets/public-key" \
        -H "Accept: application/vnd.github+json"
}

# Fetch user public key for Codespaces secret encryption
# Args: none
# Output: Public key JSON {key_id, key}
fetch_user_public_key() {
    gh api "user/codespaces/secrets/public-key" -H "Accept: application/vnd.github+json"
}

# =============================================================================
# DISCOVER PRIMITIVES
# =============================================================================
# List secrets at various scopes

# Discover repository secrets
# Args: owner, repo, app (actions|dependabot|codespaces)
# Output: JSON array of secrets
discover_repo_secrets() {
    local owner="$1"
    local repo="$2"
    local app="${3:-actions}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_secrets requires owner and repo" >&2
        return 2
    fi

    gh secret list -R "$owner/$repo" --app "$app" --json name,updatedAt
}

# Discover environment secrets
# Args: owner, repo, environment
# Output: JSON array of secrets
discover_env_secrets() {
    local owner="$1"
    local repo="$2"
    local environment="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" ]]; then
        echo "ERROR: discover_env_secrets requires owner, repo, and environment" >&2
        return 2
    fi

    gh secret list -R "$owner/$repo" --env "$environment" --json name,updatedAt
}

# Discover organization secrets
# Args: org, app (actions|dependabot|codespaces)
# Output: JSON array of secrets
discover_org_secrets() {
    local org="$1"
    local app="${2:-actions}"

    if [[ -z "$org" ]]; then
        echo "ERROR: discover_org_secrets requires org" >&2
        return 2
    fi

    gh secret list --org "$org" --app "$app" --json name,updatedAt,visibility,selectedReposURL
}

# Discover user secrets (Codespaces)
# Args: none
# Output: JSON array of secrets
discover_user_secrets() {
    gh secret list --user --json name,updatedAt,selectedReposURL
}

# Discover which repositories can access an organization secret
# Args: org, secret_name, app (actions|dependabot)
# Output: JSON array of repositories
discover_org_secret_repos() {
    local org="$1"
    local secret_name="$2"
    local app="${3:-actions}"

    if [[ -z "$org" || -z "$secret_name" ]]; then
        echo "ERROR: discover_org_secret_repos requires org and secret_name" >&2
        return 2
    fi

    gh api "orgs/$org/$app/secrets/$secret_name/repositories" --jq '.repositories'
}

# Discover organization secrets available to a repository
# Args: owner, repo
# Output: JSON array of organization secrets
discover_org_secrets_available() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_org_secrets_available requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/organization-secrets" --jq '.secrets'
}

# =============================================================================
# LOOKUP PRIMITIVES
# =============================================================================
# Resolve secret properties

# Get organization secret visibility
# Args: org, secret_name, app (actions|dependabot)
# Output: "all" | "private" | "selected"
get_secret_visibility() {
    local org="$1"
    local secret_name="$2"
    local app="${3:-actions}"

    if [[ -z "$org" || -z "$secret_name" ]]; then
        echo "ERROR: get_secret_visibility requires org and secret_name" >&2
        return 2
    fi

    gh api "orgs/$org/$app/secrets/$secret_name" --jq '.visibility'
}

# =============================================================================
# FILTER PRIMITIVES
# =============================================================================
# Transform/filter JSON data (stdin → stdout)

# Filter secrets by app type (from gh secret list output)
# Args: app (actions|dependabot|codespaces)
# Input: JSON array of secrets
# Output: Filtered JSON array
# Note: This assumes secrets have been tagged with app metadata
filter_secrets_by_app() {
    local app="$1"

    if [[ -z "$app" ]]; then
        echo "ERROR: filter_secrets_by_app requires app argument" >&2
        return 2
    fi

    jq --arg app "$app" 'map(select(.app == $app or .application == $app))'
}

# Filter organization secrets by visibility
# Args: visibility (all|private|selected)
# Input: JSON array of org secrets
# Output: Filtered JSON array
filter_secrets_by_visibility() {
    local visibility="$1"

    if [[ -z "$visibility" ]]; then
        echo "ERROR: filter_secrets_by_visibility requires visibility argument" >&2
        return 2
    fi

    jq --arg vis "$visibility" 'map(select(.visibility == $vis))'
}

# Filter secrets by name pattern
# Args: pattern (regex)
# Input: JSON array of secrets
# Output: Filtered JSON array
filter_secrets_by_name() {
    local pattern="$1"

    if [[ -z "$pattern" ]]; then
        echo "ERROR: filter_secrets_by_name requires pattern argument" >&2
        return 2
    fi

    jq --arg pattern "$pattern" 'map(select(.name | test($pattern)))'
}

# =============================================================================
# FORMAT PRIMITIVES
# =============================================================================
# Transform JSON to human-readable output (stdin → stdout)

# Format secrets as table
# Input: JSON array of secrets
# Output: Formatted table
format_secrets() {
    jq -r '
        ["NAME", "UPDATED", "VISIBILITY", "REPOS"] as $headers |
        [$headers],
        (.[] | [
            .name,
            .updatedAt,
            (.visibility // "-"),
            (.numSelectedRepos // "-")
        ]) |
        @tsv
    '
}

# Format single secret detail
# Input: Single secret JSON
# Output: Formatted details
format_secret_detail() {
    jq -r '
        "Secret Name: \(.name)",
        "Created: \(.created_at // "N/A")",
        "Updated: \(.updated_at // .updatedAt)",
        "Visibility: \(.visibility // "N/A")",
        "Selected Repos: \(.num_selected_repos // .numSelectedRepos // "N/A")",
        "Selected Repos URL: \(.selected_repositories_url // .selectedReposURL // "N/A")"
    '
}

# Format public key
# Input: Public key JSON
# Output: Formatted key info
format_public_key() {
    jq -r '
        "Key ID: \(.key_id)",
        "Public Key: \(.key)"
    '
}

# =============================================================================
# DETECT PRIMITIVES
# =============================================================================
# Determine secret properties

# Detect if secret exists at repository scope
# Args: owner, repo, secret_name, app (actions|dependabot)
# Output: "true" | "false"
detect_secret_exists() {
    local owner="$1"
    local repo="$2"
    local secret_name="$3"
    local app="${4:-actions}"

    if [[ -z "$owner" || -z "$repo" || -z "$secret_name" ]]; then
        echo "ERROR: detect_secret_exists requires owner, repo, and secret_name" >&2
        return 2
    fi

    if gh api "repos/$owner/$repo/$app/secrets/$secret_name" 2>/dev/null >/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# Detect if environment secret exists
# Args: owner, repo, environment, secret_name
# Output: "true" | "false"
detect_env_secret_exists() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local secret_name="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$secret_name" ]]; then
        echo "ERROR: detect_env_secret_exists requires owner, repo, environment, and secret_name" >&2
        return 2
    fi

    if gh api "repos/$owner/$repo/environments/$environment/secrets/$secret_name" 2>/dev/null >/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# Detect if organization secret exists
# Args: org, secret_name, app (actions|dependabot)
# Output: "true" | "false"
detect_org_secret_exists() {
    local org="$1"
    local secret_name="$2"
    local app="${3:-actions}"

    if [[ -z "$org" || -z "$secret_name" ]]; then
        echo "ERROR: detect_org_secret_exists requires org and secret_name" >&2
        return 2
    fi

    if gh api "orgs/$org/$app/secrets/$secret_name" 2>/dev/null >/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# =============================================================================
# MUTATE PRIMITIVES
# =============================================================================
# Create, update, or delete secrets

# Set repository secret
# Args: owner, repo, secret_name, value, app (actions|dependabot|codespaces)
# Output: Empty (201 Created or 204 No Content)
set_repo_secret() {
    local owner="$1"
    local repo="$2"
    local secret_name="$3"
    local value="$4"
    local app="${5:-actions}"

    if [[ -z "$owner" || -z "$repo" || -z "$secret_name" || -z "$value" ]]; then
        echo "ERROR: set_repo_secret requires owner, repo, secret_name, and value" >&2
        return 2
    fi

    echo "$value" | gh secret set "$secret_name" -R "$owner/$repo" --app "$app"
}

# Set environment secret
# Args: owner, repo, environment, secret_name, value
# Output: Empty (201 Created or 204 No Content)
set_env_secret() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local secret_name="$4"
    local value="$5"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$secret_name" || -z "$value" ]]; then
        echo "ERROR: set_env_secret requires owner, repo, environment, secret_name, and value" >&2
        return 2
    fi

    echo "$value" | gh secret set "$secret_name" -R "$owner/$repo" --env "$environment"
}

# Set organization secret
# Args: org, secret_name, value, app (actions|dependabot|codespaces), visibility (all|private|selected), [repo_ids]
# Output: Empty (201 Created or 204 No Content)
set_org_secret() {
    local org="$1"
    local secret_name="$2"
    local value="$3"
    local app="${4:-actions}"
    local visibility="${5:-all}"
    local repo_ids="${6:-}"

    if [[ -z "$org" || -z "$secret_name" || -z "$value" ]]; then
        echo "ERROR: set_org_secret requires org, secret_name, and value" >&2
        return 2
    fi

    local args=()
    args+=(--org "$org")
    args+=(--app "$app")
    args+=(--visibility "$visibility")

    if [[ "$visibility" == "selected" && -n "$repo_ids" ]]; then
        args+=(--repos "$repo_ids")
    fi

    echo "$value" | gh secret set "$secret_name" "${args[@]}"
}

# Set user secret (Codespaces)
# Args: secret_name, value
# Output: Empty (201 Created or 204 No Content)
set_user_secret() {
    local secret_name="$1"
    local value="$2"

    if [[ -z "$secret_name" || -z "$value" ]]; then
        echo "ERROR: set_user_secret requires secret_name and value" >&2
        return 2
    fi

    echo "$value" | gh secret set "$secret_name" --user
}

# Delete repository secret
# Args: owner, repo, secret_name, app (actions|dependabot|codespaces)
# Output: Empty (204 No Content)
delete_repo_secret() {
    local owner="$1"
    local repo="$2"
    local secret_name="$3"
    local app="${4:-actions}"

    if [[ -z "$owner" || -z "$repo" || -z "$secret_name" ]]; then
        echo "ERROR: delete_repo_secret requires owner, repo, and secret_name" >&2
        return 2
    fi

    gh secret delete "$secret_name" -R "$owner/$repo" --app "$app"
}

# Delete environment secret
# Args: owner, repo, environment, secret_name
# Output: Empty (204 No Content)
delete_env_secret() {
    local owner="$1"
    local repo="$2"
    local environment="$3"
    local secret_name="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$environment" || -z "$secret_name" ]]; then
        echo "ERROR: delete_env_secret requires owner, repo, environment, and secret_name" >&2
        return 2
    fi

    gh secret delete "$secret_name" -R "$owner/$repo" --env "$environment"
}

# Delete organization secret
# Args: org, secret_name, app (actions|dependabot|codespaces)
# Output: Empty (204 No Content)
delete_org_secret() {
    local org="$1"
    local secret_name="$2"
    local app="${3:-actions}"

    if [[ -z "$org" || -z "$secret_name" ]]; then
        echo "ERROR: delete_org_secret requires org and secret_name" >&2
        return 2
    fi

    gh secret delete "$secret_name" --org "$org" --app "$app"
}

# Delete user secret (Codespaces)
# Args: secret_name
# Output: Empty (204 No Content)
delete_user_secret() {
    local secret_name="$1"

    if [[ -z "$secret_name" ]]; then
        echo "ERROR: delete_user_secret requires secret_name" >&2
        return 2
    fi

    gh secret delete "$secret_name" --user
}

# Set organization secret repository access
# Args: org, secret_name, app (actions|dependabot), repo_ids_json (array of repo IDs)
# Output: Empty (204 No Content)
set_org_secret_repos() {
    local org="$1"
    local secret_name="$2"
    local app="${3:-actions}"
    local repo_ids_json="$4"

    if [[ -z "$org" || -z "$secret_name" || -z "$repo_ids_json" ]]; then
        echo "ERROR: set_org_secret_repos requires org, secret_name, and repo_ids_json" >&2
        return 2
    fi

    gh api -X PUT "orgs/$org/$app/secrets/$secret_name/repositories" \
        -f selected_repository_ids="$repo_ids_json"
}

# Add repository to organization secret access
# Args: org, secret_name, app (actions|dependabot), repo_id
# Output: Empty (204 No Content)
add_repo_to_org_secret() {
    local org="$1"
    local secret_name="$2"
    local app="${3:-actions}"
    local repo_id="$4"

    if [[ -z "$org" || -z "$secret_name" || -z "$repo_id" ]]; then
        echo "ERROR: add_repo_to_org_secret requires org, secret_name, and repo_id" >&2
        return 2
    fi

    gh api -X PUT "orgs/$org/$app/secrets/$secret_name/repositories/$repo_id"
}

# Remove repository from organization secret access
# Args: org, secret_name, app (actions|dependabot), repo_id
# Output: Empty (204 No Content)
remove_repo_from_org_secret() {
    local org="$1"
    local secret_name="$2"
    local app="${3:-actions}"
    local repo_id="$4"

    if [[ -z "$org" || -z "$secret_name" || -z "$repo_id" ]]; then
        echo "ERROR: remove_repo_from_org_secret requires org, secret_name, and repo_id" >&2
        return 2
    fi

    gh api -X DELETE "orgs/$org/$app/secrets/$secret_name/repositories/$repo_id"
}
