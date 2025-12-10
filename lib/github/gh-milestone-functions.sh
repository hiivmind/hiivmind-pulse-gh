#!/bin/bash
# GitHub Milestone Domain Functions
# Source this file to use: source gh-milestone-functions.sh
#
# This domain handles:
# - Milestone queries (GraphQL)
# - Milestone CRUD operations (REST API)
# - Milestone assignment to issues/PRs (GraphQL mutations)
#
# Dependencies:
#   - gh (GitHub CLI, authenticated)
#   - jq (1.6+)
#   - yq (4.0+)
#
# Note: Creating/updating/deleting milestones requires REST API.
# GraphQL is used for queries and setting milestones on issues/PRs.
#
# Follows hiivmind-pulse-gh architecture principles:
#   - Explicit scope prefixes (repo_)
#   - Pipe-first composition pattern
#   - Single responsibility per function

set -euo pipefail

# Ensure yq is in PATH (snap installs to /snap/bin on Ubuntu)
export PATH="/snap/bin:$PATH"

# Get the directory where this script is located
MILESTONE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# YAML template locations
MILESTONE_GRAPHQL_QUERIES="$MILESTONE_SCRIPT_DIR/gh-milestone-graphql-queries.yaml"
MILESTONE_JQ_FILTERS="$MILESTONE_SCRIPT_DIR/gh-milestone-jq-filters.yaml"

#==============================================================================
# LOOKUP PRIMITIVES
#==============================================================================
# Pattern: get_{entity}_id
# Purpose: Resolve identifiers (title -> node ID)
# Output: Single value (ID string) to stdout

# Get a milestone's GraphQL node ID by title
# Args: owner, repo, title
# Output: Node ID string (e.g., "MI_kw...")
get_milestone_id() {
    local owner="$1"
    local repo="$2"
    local title="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$title" ]]; then
        echo "ERROR: get_milestone_id requires owner, repo, and title arguments" >&2
        return 2
    fi

    fetch_repo_milestones "$owner" "$repo" "OPEN,CLOSED" | \
        jq -r --arg title "$title" '.data.repository.milestones.nodes[] | select(.title == $title) | .id'
}

# Get a milestone's number by title
# Args: owner, repo, title
# Output: Milestone number (integer)
get_milestone_number() {
    local owner="$1"
    local repo="$2"
    local title="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$title" ]]; then
        echo "ERROR: get_milestone_number requires owner, repo, and title arguments" >&2
        return 2
    fi

    # Use REST API for simpler lookup - query params in URL
    gh api "repos/$owner/$repo/milestones?state=all" | \
        jq -r --arg title "$title" '.[] | select(.title == $title) | .number'
}

#==============================================================================
# FETCH PRIMITIVES (GraphQL)
#==============================================================================
# Pattern: fetch_{entity}, discover_{scope}_{entities}
# Purpose: Retrieve data from GitHub API
# Output: JSON to stdout

# Fetch all milestones for a repository
# Args: owner, repo, [states: "OPEN", "CLOSED", or "OPEN,CLOSED"]
# Output: JSON with milestone list
fetch_repo_milestones() {
    local owner="$1"
    local repo="$2"
    local states="${3:-OPEN}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: fetch_repo_milestones requires owner and repo arguments" >&2
        return 2
    fi

    # Build the query with states directly substituted (GraphQL variables for enums are tricky)
    local states_graphql
    if [[ "$states" == "OPEN,CLOSED" || "$states" == "CLOSED,OPEN" ]]; then
        states_graphql="[OPEN, CLOSED]"
    elif [[ "$states" == "CLOSED" ]]; then
        states_graphql="[CLOSED]"
    else
        states_graphql="[OPEN]"
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="
        query(\$owner: String!, \$repo: String!) {
            repository(owner: \$owner, name: \$repo) {
                owner { login }
                name
                milestones(first: 100, states: $states_graphql, orderBy: {field: DUE_DATE, direction: ASC}) {
                    totalCount
                    nodes {
                        id
                        number
                        title
                        description
                        dueOn
                        state
                        closed
                        closedAt
                        createdAt
                        updatedAt
                        url
                        progressPercentage
                        issues(first: 1) { totalCount }
                        pullRequests(first: 1) { totalCount }
                    }
                }
            }
        }" \
        -f owner="$owner" \
        -f repo="$repo"
}

# Fetch a specific milestone by number
# Args: owner, repo, milestone_number
# Output: JSON with milestone data
fetch_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: fetch_milestone requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.milestone_by_number.query' "$MILESTONE_GRAPHQL_QUERIES")" \
        -f owner="$owner" \
        -f repo="$repo" \
        -F number="$number"
}

#==============================================================================
# REST API FUNCTIONS (CRUD)
#==============================================================================
# Milestone creation/update/delete requires REST API

# List milestones using REST API
# Args: owner, repo, [state: open/closed/all], [sort: due_on/completeness], [direction: asc/desc]
# Output: JSON array of milestones
list_milestones_rest() {
    local owner="$1"
    local repo="$2"
    local state="${3:-open}"
    local sort="${4:-due_on}"
    local direction="${5:-asc}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: list_milestones_rest requires owner and repo arguments" >&2
        return 2
    fi

    # Build query string - gh api accepts query params in the URL
    gh api "repos/$owner/$repo/milestones?state=${state}&sort=${sort}&direction=${direction}&per_page=100"
}

# Get a specific milestone by number (REST)
# Args: owner, repo, milestone_number
# Output: JSON milestone object
get_milestone_rest() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: get_milestone_rest requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/milestones/$number"
}

# Create a new milestone
# Args: owner, repo, title, [description], [due_on: ISO 8601], [state: open/closed]
# Output: JSON of created milestone
create_milestone() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local description="${4:-}"
    local due_on="${5:-}"
    local state="${6:-open}"

    if [[ -z "$owner" || -z "$repo" || -z "$title" ]]; then
        echo "ERROR: create_milestone requires owner, repo, and title arguments" >&2
        return 2
    fi

    local args=(-X POST)
    args+=(-f title="$title")
    args+=(-f state="$state")
    [[ -n "$description" ]] && args+=(-f description="$description")
    [[ -n "$due_on" ]] && args+=(-f due_on="$due_on")

    gh api "repos/$owner/$repo/milestones" "${args[@]}"
}

# Update an existing milestone
# Args: owner, repo, milestone_number, [title], [description], [due_on], [state]
# Output: JSON of updated milestone
update_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local title="${4:-}"
    local description="${5:-}"
    local due_on="${6:-}"
    local state="${7:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: update_milestone requires owner, repo, and number arguments" >&2
        return 2
    fi

    local args=(-X PATCH)
    [[ -n "$title" ]] && args+=(-f title="$title")
    [[ -n "$description" ]] && args+=(-f description="$description")
    [[ -n "$due_on" ]] && args+=(-f due_on="$due_on")
    [[ -n "$state" ]] && args+=(-f state="$state")

    gh api "repos/$owner/$repo/milestones/$number" "${args[@]}"
}

# Close a milestone
# Args: owner, repo, milestone_number
# Output: JSON of closed milestone
close_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: close_milestone requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/milestones/$number" -X PATCH -f state="closed"
}

# Reopen a milestone
# Args: owner, repo, milestone_number
# Output: JSON of reopened milestone
reopen_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: reopen_milestone requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/milestones/$number" -X PATCH -f state="open"
}

# Delete a milestone
# Args: owner, repo, milestone_number
# Returns: 0 on success
delete_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: delete_milestone requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/milestones/$number" -X DELETE
}

#==============================================================================
# FILTER PRIMITIVES
#==============================================================================
# Pattern: filter_{criteria}
# Purpose: Filter data based on criteria
# Input: JSON from stdin
# Output: Filtered JSON to stdout

# Filter milestones by state (for GraphQL response)
# Args: state ("OPEN" or "CLOSED")
# Input: JSON from fetch_repo_milestones
# Output: Filtered JSON
filter_milestones_by_state() {
    local state="$1"
    jq --arg state "$state" '.data.repository.milestones.nodes | map(select(.state == $state))'
}

# Filter milestones by state (for REST response)
# Note: REST API has state filter built-in, but this is for post-filtering
filter_milestones_rest_by_state() {
    local state="$1"
    jq --arg state "$state" 'map(select(.state == $state))'
}

#==============================================================================
# FORMAT PRIMITIVES
#==============================================================================
# Pattern: format_{entity}
# Purpose: Transform JSON to structured output
# Input: JSON from stdin
# Output: Formatted JSON to stdout

# Format milestone list (GraphQL response)
# Input: JSON from fetch_repo_milestones
# Output: Formatted JSON
format_milestones() {
    jq -f <(yq '.format_filters.format_milestones.filter' "$MILESTONE_JQ_FILTERS")
}

# Format single milestone (GraphQL response)
# Input: JSON from fetch_milestone
# Output: Formatted JSON
format_milestone() {
    jq -f <(yq '.format_filters.format_milestone.filter' "$MILESTONE_JQ_FILTERS")
}

# Format milestone list (REST response)
# Input: JSON array from list_milestones_rest
# Output: Formatted JSON
format_milestones_rest() {
    jq '[.[] | {
        number: .number,
        title: .title,
        description: (.description // ""),
        state: .state,
        dueOn: (.due_on // "No due date"),
        openIssues: .open_issues,
        closedIssues: .closed_issues,
        progress: (if (.open_issues + .closed_issues) > 0
                   then ((.closed_issues / (.open_issues + .closed_issues)) * 100 | floor)
                   else 0 end),
        url: .html_url,
        createdAt: .created_at,
        updatedAt: .updated_at
    }]'
}

# Format single milestone (REST response)
# Input: JSON from get_milestone_rest
# Output: Formatted JSON
format_milestone_rest() {
    jq '{
        number: .number,
        title: .title,
        description: (.description // ""),
        state: .state,
        dueOn: (.due_on // "No due date"),
        openIssues: .open_issues,
        closedIssues: .closed_issues,
        total: (.open_issues + .closed_issues),
        progress: (if (.open_issues + .closed_issues) > 0
                   then ((.closed_issues / (.open_issues + .closed_issues)) * 100 | floor)
                   else 0 end),
        url: .html_url,
        createdAt: .created_at,
        updatedAt: .updated_at,
        closedAt: .closed_at
    }'
}

#==============================================================================
# EXTRACT PRIMITIVES
#==============================================================================
# Pattern: extract_{what}
# Purpose: Pull specific fields from responses
# Input: JSON from stdin
# Output: Extracted data to stdout

# Extract milestone titles from list
# Input: JSON from fetch_repo_milestones
# Output: Array of titles
extract_milestone_titles() {
    jq '[.data.repository.milestones.nodes[].title]'
}

# Extract milestone IDs from list
# Input: JSON from fetch_repo_milestones
# Output: Array of IDs
extract_milestone_ids() {
    jq '[.data.repository.milestones.nodes[].id]'
}

#==============================================================================
# DETECT PRIMITIVES
#==============================================================================
# Pattern: detect_{what}, check_{condition}
# Purpose: Determine type/state
# Output: String or exit code

# Check if a milestone exists by title
# Args: owner, repo, title
# Returns: 0 if exists, 1 if not
check_milestone_exists() {
    local owner="$1"
    local repo="$2"
    local title="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$title" ]]; then
        echo "ERROR: check_milestone_exists requires owner, repo, and title arguments" >&2
        return 2
    fi

    local milestone_id
    milestone_id=$(get_milestone_id "$owner" "$repo" "$title")

    if [[ -n "$milestone_id" && "$milestone_id" != "null" ]]; then
        return 0
    else
        return 1
    fi
}

# Get milestone state by number
# Args: owner, repo, milestone_number
# Output: "open" or "closed"
detect_milestone_state() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: detect_milestone_state requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/milestones/$number" --jq '.state'
}

#==============================================================================
# CONVENIENCE FUNCTIONS
#==============================================================================
# Higher-level functions that compose primitives

# Get milestone progress as percentage
# Args: owner, repo, milestone_number
# Output: Progress percentage (integer 0-100)
get_milestone_progress() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: get_milestone_progress requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/milestones/$number" --jq '
        if (.open_issues + .closed_issues) > 0 then
            ((.closed_issues / (.open_issues + .closed_issues)) * 100 | floor)
        else
            0
        end
    '
}

# Create or update milestone by title (upsert)
# Args: owner, repo, title, [description], [due_on], [state]
# Output: JSON of created/updated milestone
create_or_update_milestone() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local description="${4:-}"
    local due_on="${5:-}"
    local state="${6:-open}"

    if [[ -z "$owner" || -z "$repo" || -z "$title" ]]; then
        echo "ERROR: create_or_update_milestone requires owner, repo, and title arguments" >&2
        return 2
    fi

    local existing_number
    existing_number=$(get_milestone_number "$owner" "$repo" "$title")

    if [[ -n "$existing_number" && "$existing_number" != "null" ]]; then
        # Update existing
        update_milestone "$owner" "$repo" "$existing_number" "$title" "$description" "$due_on" "$state"
    else
        # Create new
        create_milestone "$owner" "$repo" "$title" "$description" "$due_on" "$state"
    fi
}

#==============================================================================
# COMPOSITION EXAMPLES
#==============================================================================
# These show how to compose primitives

# Example: List open milestones with progress
# fetch_repo_milestones "owner" "repo" "OPEN" | format_milestones

# Example: Get milestone ID for setting on issue
# MILESTONE_ID=$(get_milestone_id "owner" "repo" "v1.0")

# Example: Create milestone with due date
# create_milestone "owner" "repo" "v1.0" "First release" "2024-12-31T00:00:00Z"

# Example: Close completed milestone
# close_milestone "owner" "repo" 1
