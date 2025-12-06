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

# Function to list reviewers (reads from stdin)
list_reviewers() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.list_reviewers.filter' "$script_dir/gh-project-jq-filters.yaml")
}

# Function to list linked PRs (reads from stdin)
list_linked_prs() {
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"
    jq -f <(yq '.discovery_filters.list_linked_prs.filter' "$script_dir/gh-project-jq-filters.yaml")
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

# =============================================================================
# README FUNCTIONS
# =============================================================================

# Fetch project README content by project ID
fetch_project_readme() {
    local project_id="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.utilities.project_readme.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id"
}

# Update project README content
update_project_readme() {
    local project_id="$1"
    local readme_content="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_project_readme.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f readme="$readme_content"
}

# =============================================================================
# MILESTONE FUNCTIONS
# =============================================================================
# Note: Milestones are repository-level entities assigned to issues/PRs.
# They appear in Projects as read-only field values. To set milestones,
# use the issue/PR mutation functions below.

# Fetch all milestones for a repository
fetch_repo_milestones() {
    local owner="$1"
    local repo="$2"
    local states="${3:-OPEN}"  # OPEN, CLOSED, or "OPEN,CLOSED" for both
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.milestones.repository_milestones.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f owner="$owner" \
        -f repo="$repo" \
        -f states="[$states]"
}

# Fetch a specific milestone by number
fetch_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.milestones.milestone_by_number.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f owner="$owner" \
        -f repo="$repo" \
        -F number="$number"
}

# Get milestone ID by title (helper function)
get_milestone_id() {
    local owner="$1"
    local repo="$2"
    local title="$3"

    fetch_repo_milestones "$owner" "$repo" "OPEN,CLOSED" | \
        jq -r --arg title "$title" '.data.repository.milestones.nodes[] | select(.title == $title) | .id'
}

# Set milestone on an issue (GraphQL mutation)
set_issue_milestone() {
    local issue_id="$1"
    local milestone_id="$2"  # Can be null/empty to clear
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.set_issue_milestone.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f issueId="$issue_id")
    if [[ -n "$milestone_id" ]]; then
        args+=(-f milestoneId="$milestone_id")
    else
        args+=(-f milestoneId=null)
    fi

    gh api graphql "${args[@]}"
}

# Set milestone on a pull request (GraphQL mutation)
set_pr_milestone() {
    local pr_id="$1"
    local milestone_id="$2"  # Can be null/empty to clear
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.set_pr_milestone.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f prId="$pr_id")
    if [[ -n "$milestone_id" ]]; then
        args+=(-f milestoneId="$milestone_id")
    else
        args+=(-f milestoneId=null)
    fi

    gh api graphql "${args[@]}"
}

# Clear milestone from an issue (convenience wrapper)
clear_issue_milestone() {
    local issue_id="$1"
    set_issue_milestone "$issue_id" ""
}

# Clear milestone from a pull request (convenience wrapper)
clear_pr_milestone() {
    local pr_id="$1"
    set_pr_milestone "$pr_id" ""
}

# Note: For creating/updating/closing milestones, use REST API functions
# in gh-rest-functions.sh (create_milestone, update_milestone, close_milestone)

# =============================================================================
# STATUS UPDATE FUNCTIONS
# =============================================================================
# Status values: ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, INACTIVE

# Fetch all status updates for a project
fetch_project_status_updates() {
    local project_id="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.status_updates.project_status_updates.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id"
}

# Get the latest status update for a project
get_latest_status_update() {
    local project_id="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.status_updates.latest_status_update.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id"
}

# Create a new status update for a project
create_status_update() {
    local project_id="$1"
    local status="$2"  # ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, INACTIVE
    local body="${3:-}"
    local start_date="${4:-}"  # YYYY-MM-DD
    local target_date="${5:-}"  # YYYY-MM-DD
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.create_status_update.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f projectId="$project_id")
    args+=(-f status="$status")
    [[ -n "$body" ]] && args+=(-f body="$body")
    [[ -n "$start_date" ]] && args+=(-f startDate="$start_date")
    [[ -n "$target_date" ]] && args+=(-f targetDate="$target_date")

    gh api graphql "${args[@]}"
}

# Update an existing status update
update_status_update() {
    local status_update_id="$1"
    local status="${2:-}"  # Optional: ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, INACTIVE
    local body="${3:-}"
    local start_date="${4:-}"
    local target_date="${5:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.update_status_update.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f statusUpdateId="$status_update_id")
    [[ -n "$status" ]] && args+=(-f status="$status")
    [[ -n "$body" ]] && args+=(-f body="$body")
    [[ -n "$start_date" ]] && args+=(-f startDate="$start_date")
    [[ -n "$target_date" ]] && args+=(-f targetDate="$target_date")

    gh api graphql "${args[@]}"
}

# =============================================================================
# REPOSITORY LINKING FUNCTIONS
# =============================================================================

# Fetch linked repositories for a project
fetch_linked_repositories() {
    local project_id="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.repository_linking.project_linked_repositories.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id"
}

# Link a repository to a project
link_repo_to_project() {
    local project_id="$1"
    local repository_id="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.link_repository.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f repositoryId="$repository_id"
}

# Unlink a repository from a project
unlink_repo_from_project() {
    local project_id="$1"
    local repository_id="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.unlink_repository.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f repositoryId="$repository_id"
}

# Helper: Get repository ID by owner/name
get_repository_id() {
    local owner="$1"
    local name="$2"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { id } }' \
        -f owner="$owner" \
        -f name="$name" | jq -r '.data.repository.id'
}

# =============================================================================
# VIEW FUNCTIONS
# =============================================================================
# Layout types: TABLE, BOARD, ROADMAP

# Fetch all views for a project
fetch_project_views() {
    local project_id="$1"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.views.project_views.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id"
}

# Fetch a specific view by number
fetch_project_view() {
    local project_id="$1"
    local view_number="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.views.project_view_by_number.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -F viewNumber="$view_number"
}

# Create a new project view
create_project_view() {
    local project_id="$1"
    local name="$2"
    local layout="${3:-TABLE}"  # TABLE, BOARD, or ROADMAP
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.create_view.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f name="$name" \
        -f layout="$layout"
}

# Update view settings
update_project_view() {
    local view_id="$1"
    local name="${2:-}"
    local layout="${3:-}"  # TABLE, BOARD, or ROADMAP
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.update_view.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f viewId="$view_id")
    [[ -n "$name" ]] && args+=(-f name="$name")
    [[ -n "$layout" ]] && args+=(-f layout="$layout")

    gh api graphql "${args[@]}"
}

# =============================================================================
# PAGINATION FUNCTIONS
# =============================================================================

# Function to fetch user project with pagination (single page)
fetch_user_project_page() {
    local project_number="$1"
    local cursor="${2:-}"
    local page_size="${3:-100}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    if [[ -n "$cursor" ]]; then
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.pagination.user_project_items_paginated.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -F projectNumber="$project_number" \
            -F first="$page_size" \
            -f after="$cursor"
    else
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.pagination.user_project_items_paginated.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -F projectNumber="$project_number" \
            -F first="$page_size"
    fi
}

# Function to fetch organization project with pagination (single page)
fetch_org_project_page() {
    local project_number="$1"
    local org_login="$2"
    local cursor="${3:-}"
    local page_size="${4:-100}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    if [[ -n "$cursor" ]]; then
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.pagination.organization_project_items_paginated.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -f orgLogin="$org_login" \
            -F projectNumber="$project_number" \
            -F first="$page_size" \
            -f after="$cursor"
    else
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.pagination.organization_project_items_paginated.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -f orgLogin="$org_login" \
            -F projectNumber="$project_number" \
            -F first="$page_size"
    fi
}

# Function to fetch ALL user project items with automatic pagination
fetch_user_project_all() {
    local project_number="$1"
    local page_size="${2:-100}"
    local all_items="[]"
    local cursor=""
    local has_next_page=true
    local project_info=""
    local total_count=0

    while [[ "$has_next_page" == "true" ]]; do
        local response
        response=$(fetch_user_project_page "$project_number" "$cursor" "$page_size")

        # Extract project info on first page
        if [[ -z "$project_info" ]]; then
            project_info=$(echo "$response" | jq '{
                id: .data.viewer.projectV2.id,
                title: .data.viewer.projectV2.title
            }')
            total_count=$(echo "$response" | jq '.data.viewer.projectV2.items.totalCount')
        fi

        # Extract items and append
        local page_items
        page_items=$(echo "$response" | jq '.data.viewer.projectV2.items.nodes')
        all_items=$(echo "$all_items" "$page_items" | jq -s 'add')

        # Check for next page
        has_next_page=$(echo "$response" | jq -r '.data.viewer.projectV2.items.pageInfo.hasNextPage')
        cursor=$(echo "$response" | jq -r '.data.viewer.projectV2.items.pageInfo.endCursor')
    done

    # Return combined result in same format as non-paginated queries
    echo "{\"data\":{\"viewer\":{\"projectV2\":$(echo "$project_info" | jq ". + {items: {totalCount: $total_count, nodes: $all_items}}")}}}"
}

# Function to fetch ALL organization project items with automatic pagination
fetch_org_project_all() {
    local project_number="$1"
    local org_login="$2"
    local page_size="${3:-100}"
    local all_items="[]"
    local cursor=""
    local has_next_page=true
    local project_info=""
    local total_count=0

    while [[ "$has_next_page" == "true" ]]; do
        local response
        response=$(fetch_org_project_page "$project_number" "$org_login" "$cursor" "$page_size")

        # Extract project info on first page
        if [[ -z "$project_info" ]]; then
            project_info=$(echo "$response" | jq '{
                id: .data.organization.projectV2.id,
                title: .data.organization.projectV2.title
            }')
            total_count=$(echo "$response" | jq '.data.organization.projectV2.items.totalCount')
        fi

        # Extract items and append
        local page_items
        page_items=$(echo "$response" | jq '.data.organization.projectV2.items.nodes')
        all_items=$(echo "$all_items" "$page_items" | jq -s 'add')

        # Check for next page
        has_next_page=$(echo "$response" | jq -r '.data.organization.projectV2.items.pageInfo.hasNextPage')
        cursor=$(echo "$response" | jq -r '.data.organization.projectV2.items.pageInfo.endCursor')
    done

    # Return combined result in same format as non-paginated queries
    echo "{\"data\":{\"organization\":{\"projectV2\":$(echo "$project_info" | jq ". + {items: {totalCount: $total_count, nodes: $all_items}}")}}}"
}

# =============================================================================
# SORTED QUERY FUNCTIONS
# =============================================================================

# Fetch user project items with server-side sorting
# orderField: POSITION, CREATED_AT, UPDATED_AT
# orderDirection: ASC, DESC
fetch_user_project_sorted() {
    local project_number="$1"
    local order_field="${2:-POSITION}"
    local order_direction="${3:-ASC}"
    local page_size="${4:-100}"
    local cursor="${5:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.pagination.user_project_items_sorted.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-F projectNumber="$project_number")
    args+=(-F first="$page_size")
    args+=(-f orderField="$order_field")
    args+=(-f orderDirection="$order_direction")
    [[ -n "$cursor" ]] && args+=(-f after="$cursor")

    gh api graphql "${args[@]}"
}

# Fetch organization project items with server-side sorting
# orderField: POSITION, CREATED_AT, UPDATED_AT
# orderDirection: ASC, DESC
fetch_org_project_sorted() {
    local project_number="$1"
    local org_login="$2"
    local order_field="${3:-POSITION}"
    local order_direction="${4:-ASC}"
    local page_size="${5:-100}"
    local cursor="${6:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.pagination.organization_project_items_sorted.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f orgLogin="$org_login")
    args+=(-F projectNumber="$project_number")
    args+=(-F first="$page_size")
    args+=(-f orderField="$order_field")
    args+=(-f orderDirection="$order_direction")
    [[ -n "$cursor" ]] && args+=(-f after="$cursor")

    gh api graphql "${args[@]}"
}

# =============================================================================
# MUTATION FUNCTIONS - Field Updates
# =============================================================================

# Update a single-select field (e.g., Status, Priority)
update_item_single_select() {
    local project_id="$1"
    local item_id="$2"
    local field_id="$3"
    local option_id="$4"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_item_field_single_select.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id" \
        -f fieldId="$field_id" \
        -f optionId="$option_id"
}

# Update a text field
update_item_text() {
    local project_id="$1"
    local item_id="$2"
    local field_id="$3"
    local text="$4"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_item_field_text.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id" \
        -f fieldId="$field_id" \
        -f text="$text"
}

# Update a number field
update_item_number() {
    local project_id="$1"
    local item_id="$2"
    local field_id="$3"
    local number="$4"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_item_field_number.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id" \
        -f fieldId="$field_id" \
        -F number="$number"
}

# Update a date field (date in ISO 8601 format: YYYY-MM-DD)
update_item_date() {
    local project_id="$1"
    local item_id="$2"
    local field_id="$3"
    local date="$4"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_item_field_date.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id" \
        -f fieldId="$field_id" \
        -f date="$date"
}

# Update an iteration field
update_item_iteration() {
    local project_id="$1"
    local item_id="$2"
    local field_id="$3"
    local iteration_id="$4"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_item_field_iteration.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id" \
        -f fieldId="$field_id" \
        -f iterationId="$iteration_id"
}

# Clear a field value
clear_item_field() {
    local project_id="$1"
    local item_id="$2"
    local field_id="$3"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.clear_item_field.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id" \
        -f fieldId="$field_id"
}

# =============================================================================
# MUTATION FUNCTIONS - Item Management
# =============================================================================

# Add an existing issue or PR to a project
add_item_to_project() {
    local project_id="$1"
    local content_id="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.add_item_by_id.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f contentId="$content_id"
}

# Create a draft issue in a project
add_draft_issue() {
    local project_id="$1"
    local title="$2"
    local body="${3:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    if [[ -n "$body" ]]; then
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.mutations.add_draft_issue.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -f projectId="$project_id" \
            -f title="$title" \
            -f body="$body"
    else
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.mutations.add_draft_issue.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -f projectId="$project_id" \
            -f title="$title"
    fi
}

# Convert a draft issue to a real issue
convert_draft_to_issue() {
    local project_id="$1"
    local item_id="$2"
    local repository_id="$3"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.convert_draft_to_issue.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id" \
        -f repositoryId="$repository_id"
}

# Archive an item
archive_project_item() {
    local project_id="$1"
    local item_id="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.archive_item.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id"
}

# Unarchive an item
unarchive_project_item() {
    local project_id="$1"
    local item_id="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.unarchive_item.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f itemId="$item_id"
}

# =============================================================================
# MUTATION FUNCTIONS - Project Management
# =============================================================================

# Create a new project
create_project() {
    local owner_id="$1"
    local title="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.create_project.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f ownerId="$owner_id" \
        -f title="$title"
}

# Update project settings
update_project() {
    local project_id="$1"
    local title="${2:-}"
    local description="${3:-}"
    local closed="${4:-}"
    local public="${5:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.update_project.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f projectId="$project_id")

    [[ -n "$title" ]] && args+=(-f title="$title")
    [[ -n "$description" ]] && args+=(-f shortDescription="$description")
    [[ -n "$closed" ]] && args+=(-F closed="$closed")
    [[ -n "$public" ]] && args+=(-F public="$public")

    gh api graphql "${args[@]}"
}

# Copy an existing project
copy_project() {
    local project_id="$1"
    local owner_id="$2"
    local title="$3"
    local include_drafts="${4:-false}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.copy_project.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f projectId="$project_id" \
        -f ownerId="$owner_id" \
        -f title="$title" \
        -F includeDraftIssues="$include_drafts"
}

# =============================================================================
# MUTATION FUNCTIONS - Field Management
# =============================================================================

# Create a new custom field
create_project_field() {
    local project_id="$1"
    local data_type="$2"  # TEXT, NUMBER, DATE, SINGLE_SELECT, ITERATION
    local name="$3"
    local options="${4:-}"  # JSON array for SINGLE_SELECT, e.g., '[{"name":"Option1","color":"GREEN"}]'
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    if [[ -n "$options" ]]; then
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.mutations.create_field.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -f projectId="$project_id" \
            -f dataType="$data_type" \
            -f name="$name" \
            -f singleSelectOptions="$options"
    else
        gh api graphql -H X-Github-Next-Global-ID:1 \
            -f query="$(yq '.mutations.create_field.query' "$script_dir/gh-project-graphql-queries.yaml")" \
            -f projectId="$project_id" \
            -f dataType="$data_type" \
            -f name="$name"
    fi
}

# Update field settings (rename)
update_project_field() {
    local field_id="$1"
    local name="$2"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_field.query' "$script_dir/gh-project-graphql-queries.yaml")" \
        -f fieldId="$field_id" \
        -f name="$name"
}

# Add a new option to a single-select field
add_field_option() {
    local field_id="$1"
    local name="$2"
    local color="$3"  # GRAY, BLUE, GREEN, YELLOW, ORANGE, RED, PINK, PURPLE
    local description="${4:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.create_single_select_option.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f fieldId="$field_id")
    args+=(-f name="$name")
    args+=(-f color="$color")
    [[ -n "$description" ]] && args+=(-f description="$description")

    gh api graphql "${args[@]}"
}

# Update a single-select option
update_field_option() {
    local option_id="$1"
    local name="${2:-}"
    local color="${3:-}"  # GRAY, BLUE, GREEN, YELLOW, ORANGE, RED, PINK, PURPLE
    local description="${4:-}"
    local script_dir="$(dirname "${BASH_SOURCE[0]}")"

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.update_single_select_option.query' "$script_dir/gh-project-graphql-queries.yaml")")
    args+=(-f optionId="$option_id")
    [[ -n "$name" ]] && args+=(-f name="$name")
    [[ -n "$color" ]] && args+=(-f color="$color")
    [[ -n "$description" ]] && args+=(-f description="$description")

    gh api graphql "${args[@]}"
}

# =============================================================================
# HELPER FUNCTIONS - ID Lookups
# =============================================================================

# Get project ID from project number (organization)
get_org_project_id() {
    local project_number="$1"
    local org_login="$2"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($orgLogin: String!, $projectNumber: Int!) {
            organization(login: $orgLogin) {
                projectV2(number: $projectNumber) {
                    id
                }
            }
        }' \
        -f orgLogin="$org_login" \
        -F projectNumber="$project_number" | jq -r '.data.organization.projectV2.id'
}

# Get project ID from project number (user)
get_user_project_id() {
    local project_number="$1"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($projectNumber: Int!) {
            viewer {
                projectV2(number: $projectNumber) {
                    id
                }
            }
        }' \
        -F projectNumber="$project_number" | jq -r '.data.viewer.projectV2.id'
}

# Get user/org ID for project creation
get_user_id() {
    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query { viewer { id } }' | jq -r '.data.viewer.id'
}

get_org_id() {
    local org_login="$1"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($orgLogin: String!) {
            organization(login: $orgLogin) {
                id
            }
        }' \
        -f orgLogin="$org_login" | jq -r '.data.organization.id'
}

# Get repository ID for draft-to-issue conversion
get_repo_id() {
    local owner="$1"
    local repo="$2"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name) {
                id
            }
        }' \
        -f owner="$owner" \
        -f name="$repo" | jq -r '.data.repository.id'
}

# Get issue/PR ID by number
get_issue_id() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($owner: String!, $name: String!, $number: Int!) {
            repository(owner: $owner, name: $name) {
                issue(number: $number) {
                    id
                }
            }
        }' \
        -f owner="$owner" \
        -f name="$repo" \
        -F number="$number" | jq -r '.data.repository.issue.id'
}

get_pr_id() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($owner: String!, $name: String!, $number: Int!) {
            repository(owner: $owner, name: $name) {
                pullRequest(number: $number) {
                    id
                }
            }
        }' \
        -f owner="$owner" \
        -f name="$repo" \
        -F number="$number" | jq -r '.data.repository.pullRequest.id'
}

# Get field ID by name from a project
get_field_id() {
    local project_id="$1"
    local field_name="$2"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    fields(first: 50) {
                        nodes {
                            ... on ProjectV2Field {
                                id
                                name
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                            }
                            ... on ProjectV2IterationField {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }' \
        -f projectId="$project_id" | jq -r --arg name "$field_name" '.data.node.fields.nodes[] | select(.name == $name) | .id'
}

# Get single-select option ID by name
get_option_id() {
    local project_id="$1"
    local field_name="$2"
    local option_name="$3"

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    fields(first: 50) {
                        nodes {
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                options {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }' \
        -f projectId="$project_id" | jq -r --arg field "$field_name" --arg option "$option_name" \
            '.data.node.fields.nodes[] | select(.name == $field) | .options[] | select(.name == $option) | .id'
}

# =============================================================================
# EXAMPLES
# =============================================================================

# Pipeline usage examples (commented out):
# fetch_org_project 2 "my-org" | apply_universal_filter "" "username" "" ""
# fetch_org_project 2 "my-org" | apply_assignee_filter "username" | get_count
# fetch_org_project 2 "my-org" | list_repositories
# fetch_org_project 2 "my-org" | apply_repo_filter "my-repo" | apply_assignee_filter "username"
# fetch_org_project_fields 2 "my-org" | list_fields

# Pagination usage examples (commented out):
# fetch_org_project_all 2 "my-org" | apply_universal_filter "" "" "" ""  # Fetch all items with auto-pagination
# fetch_org_project_page 2 "my-org" "" 50  # Fetch first 50 items
# fetch_org_project_page 2 "my-org" "cursor_string" 50  # Fetch next 50 items after cursor

# Mutation usage examples (commented out):
# PROJECT_ID=$(get_org_project_id 2 "my-org")
# FIELD_ID=$(get_field_id "$PROJECT_ID" "Status")
# OPTION_ID=$(get_option_id "$PROJECT_ID" "Status" "In Progress")
# update_item_single_select "$PROJECT_ID" "$ITEM_ID" "$FIELD_ID" "$OPTION_ID"
#
# ISSUE_ID=$(get_issue_id "my-org" "my-repo" 123)
# add_item_to_project "$PROJECT_ID" "$ISSUE_ID"
#
# add_draft_issue "$PROJECT_ID" "New task title" "Task description"
# archive_project_item "$PROJECT_ID" "$ITEM_ID"

# Discovery usage examples (commented out):
# discover_user_projects | format_user_projects
# discover_org_projects "my-org" | format_org_projects "my-org"
# discover_repo_projects "my-org" "my-repo" | format_repo_projects "my-org" "my-repo"
# discover_all_projects | format_all_projects
