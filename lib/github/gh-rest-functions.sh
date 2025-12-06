#!/bin/bash
# GitHub REST API Functions
# Shell functions for REST API operations not available via GraphQL
# Source this file to use: source gh-rest-functions.sh

# =============================================================================
# MILESTONE FUNCTIONS
# =============================================================================
# Note: Creating/updating/closing milestones requires REST API.
# For reading milestones and setting them on issues/PRs, use GraphQL functions
# in gh-project-functions.sh (fetch_repo_milestones, set_issue_milestone, etc.)

# List milestones for a repository
list_milestones() {
    local owner="$1"
    local repo="$2"
    local state="${3:-open}"  # open, closed, or all
    local sort="${4:-due_on}"  # due_on or completeness
    local direction="${5:-asc}"  # asc or desc

    gh api "repos/$owner/$repo/milestones" \
        -f state="$state" \
        -f sort="$sort" \
        -f direction="$direction"
}

# Get a specific milestone by number
get_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    gh api "repos/$owner/$repo/milestones/$milestone_number"
}

# Create a new milestone
create_milestone() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local description="${4:-}"
    local due_on="${5:-}"  # ISO 8601 format: 2024-12-31T00:00:00Z
    local state="${6:-open}"

    local args=(-X POST)
    args+=(-f title="$title")
    args+=(-f state="$state")
    [[ -n "$description" ]] && args+=(-f description="$description")
    [[ -n "$due_on" ]] && args+=(-f due_on="$due_on")

    gh api "repos/$owner/$repo/milestones" "${args[@]}"
}

# Update an existing milestone
update_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"
    local title="${4:-}"
    local description="${5:-}"
    local due_on="${6:-}"
    local state="${7:-}"  # open or closed

    local args=(-X PATCH)
    [[ -n "$title" ]] && args+=(-f title="$title")
    [[ -n "$description" ]] && args+=(-f description="$description")
    [[ -n "$due_on" ]] && args+=(-f due_on="$due_on")
    [[ -n "$state" ]] && args+=(-f state="$state")

    gh api "repos/$owner/$repo/milestones/$milestone_number" "${args[@]}"
}

# Close a milestone
close_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    gh api "repos/$owner/$repo/milestones/$milestone_number" -X PATCH -f state="closed"
}

# Reopen a milestone
reopen_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    gh api "repos/$owner/$repo/milestones/$milestone_number" -X PATCH -f state="open"
}

# =============================================================================
# MILESTONE HELPER FUNCTIONS
# =============================================================================

# Get milestone number by title (returns first match)
get_milestone_number_by_title() {
    local owner="$1"
    local repo="$2"
    local title="$3"

    list_milestones "$owner" "$repo" "all" | \
        jq -r --arg title "$title" '.[] | select(.title == $title) | .number' | head -1
}

# Format milestones for display
format_milestones() {
    jq '[.[] | {
        number: .number,
        title: .title,
        state: .state,
        description: (.description // ""),
        due_on: (.due_on // "No due date"),
        open_issues: .open_issues,
        closed_issues: .closed_issues,
        progress: (if (.open_issues + .closed_issues) > 0
                   then ((.closed_issues / (.open_issues + .closed_issues)) * 100 | floor | tostring) + "%"
                   else "0%" end),
        url: .html_url
    }]'
}

# Get milestone progress summary
get_milestone_progress() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    get_milestone "$owner" "$repo" "$milestone_number" | \
        jq '{
            title: .title,
            state: .state,
            open_issues: .open_issues,
            closed_issues: .closed_issues,
            total: (.open_issues + .closed_issues),
            progress_percent: (if (.open_issues + .closed_issues) > 0
                              then ((.closed_issues / (.open_issues + .closed_issues)) * 100 | floor)
                              else 0 end),
            due_on: (.due_on // "No due date")
        }'
}

# =============================================================================
# Future REST-only functions can be added here
# =============================================================================
