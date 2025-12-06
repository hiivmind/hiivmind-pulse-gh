#!/bin/bash
# GitHub Projects Helper Functions
# Source this file to use: source gh-project-functions.sh

# Function to fetch user project data
fetch_user_project() {
    local project_number="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    # Use process substitution to avoid temp files
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.item_queries.user_project_items_full.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -F projectNumber="$project_number"
}

# Function to fetch organization project data
fetch_org_project() {
    local project_number="$1"
    local org_login="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    # Use process substitution to avoid temp files
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.item_queries.organization_project_items_full.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f orgLogin="$org_login" \
        -F projectNumber="$project_number"
}

# Function to apply universal filter (reads from stdin if no input provided)
apply_universal_filter() {
    local repo="${1:-}"
    local assignee="${2:-}"
    local status="${3:-}"
    local priority="${4:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    # Extract filter to process substitution to avoid command substitution issues
    jq \
        --arg repo "$repo" \
        --arg assignee "$assignee" \
        --arg status "$status" \
        --arg priority "$priority" \
        -f <(yq '.combined_filters.universal_filter.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to apply basic assignee filter (reads from stdin)
apply_assignee_filter() {
    local assignee="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    jq \
        --arg assignee "$assignee" \
        -f <(yq '.basic_filters.assignee_filter.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to apply repository filter (reads from stdin)
apply_repo_filter() {
    local repo="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    jq \
        --arg repo "$repo" \
        -f <(yq '.basic_filters.repository_filter.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to apply status filter (reads from stdin)
apply_status_filter() {
    local status="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    jq \
        --arg status "$status" \
        -f <(yq '.basic_filters.status_filter.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to list repositories (reads from stdin)
list_repositories() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.list_repositories.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to list assignees (reads from stdin)
list_assignees() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.list_assignees.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to list statuses (reads from stdin)
list_statuses() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.list_statuses.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to list priorities (reads from stdin)
list_priorities() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.list_priorities.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to fetch organization project fields
fetch_org_project_fields() {
    local project_number="$1"
    local org_login="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.project_structure.organization_project_fields.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f orgLogin="$org_login" \
        -F projectNumber="$project_number"
}

# Function to fetch user project fields
fetch_user_project_fields() {
    local project_number="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.project_structure.project_fields.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -F projectNumber="$project_number"
}

# Function to list fields (reads from stdin)
list_fields() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.list_fields.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Utility function to get filtered count
get_count() {
    jq '.filteredCount // (.items | length) // length'
}

# Utility function to extract just the items
get_items() {
    jq '.filteredItems // .items // .'
}

# Discovery Functions

# Function to discover user projects
discover_user_projects() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.discovery.user_projects.query' "$script_dir/gh-project-graphql-queries.yaml")"
}

# Function to discover organization projects
discover_org_projects() {
    local org_login="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.discovery.specific_organization_projects.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f orgLogin="$org_login"
}

# Function to discover repository projects
discover_repo_projects() {
    local owner="$1"
    local repo="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.discovery.repository_projects.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f owner="$owner" \
        -f name="$repo"
}

# Function to discover all accessible projects
discover_all_projects() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.discovery.organization_projects.query' "$script_dir/gh-project-graphql-queries.yaml")"
}

# Discovery formatting functions
format_user_projects() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.format_user_projects.filter' "$script_dir/gh-project-jq-filters.yaml")
}

format_org_projects() {
    local org_name="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq \
        --arg org_name "$org_name" \
        -f <(yq '.discovery_filters.format_org_projects.filter' "$script_dir/gh-project-jq-filters.yaml")
}

format_repo_projects() {
    local owner="$1"
    local repo="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq \
        --arg owner "$owner" \
        --arg repo "$repo" \
        -f <(yq '.discovery_filters.format_repo_projects.filter' "$script_dir/gh-project-jq-filters.yaml")
}

format_all_projects() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.format_all_projects.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Pipeline usage examples (commented out):
# fetch_org_project 2 "my-org" | apply_universal_filter "" "username" "" ""
# fetch_org_project 2 "my-org" | apply_assignee_filter "username" | get_count
# fetch_org_project 2 "my-org" | list_repositories
# fetch_org_project 2 "my-org" | apply_repo_filter "my-repo" | apply_assignee_filter "username"
# fetch_org_project_fields 2 "my-org" | list_fields

# Discovery usage examples (commented out):
# discover_user_projects | format_user_projects
# discover_org_projects "my-org" | format_org_projects "my-org"
# discover_repo_projects "my-org" "my-repo" | format_repo_projects "my-org" "my-repo"
# discover_all_projects | format_all_projects
