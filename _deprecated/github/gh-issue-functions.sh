#!/bin/bash
# GitHub Issue Domain Functions
# Source this file to use: source gh-issue-functions.sh
#
# This domain handles:
# - Issue queries (GraphQL and REST)
# - Issue mutations (labels, assignees, milestones, state)
#
# Dependencies:
#   - gh (GitHub CLI, authenticated)
#   - jq (1.6+)
#   - yq (4.0+)
#   - gh-milestone-functions.sh (for get_milestone_id)
#
# Follows hiivmind-pulse-gh architecture principles:
#   - Explicit scope prefixes (repo_)
#   - Pipe-first composition pattern
#   - Single responsibility per function

set -euo pipefail

# Ensure yq is in PATH (snap installs to /snap/bin on Ubuntu)
export PATH="/snap/bin:$PATH"

# Get the directory where this script is located
ISSUE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# YAML template locations
ISSUE_GRAPHQL_QUERIES="$ISSUE_SCRIPT_DIR/gh-issue-graphql-queries.yaml"
ISSUE_JQ_FILTERS="$ISSUE_SCRIPT_DIR/gh-issue-jq-filters.yaml"

#==============================================================================
# LOOKUP PRIMITIVES
#==============================================================================
# Pattern: get_{entity}_id
# Purpose: Resolve identifiers (number -> node ID)
# Output: Single value (ID string) to stdout

# Get an issue's GraphQL node ID by number
# Args: owner, repo, issue_number
# Output: Node ID string (e.g., "I_kw...")
get_issue_id() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: get_issue_id requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='
        query($owner: String!, $repo: String!, $number: Int!) {
            repository(owner: $owner, name: $repo) {
                issue(number: $number) {
                    id
                }
            }
        }' \
        -f owner="$owner" \
        -f repo="$repo" \
        -F number="$number" \
        --jq '.data.repository.issue.id'
}

#==============================================================================
# FETCH PRIMITIVES (GraphQL)
#==============================================================================
# Pattern: fetch_{entity}, discover_{scope}_{entities}
# Purpose: Retrieve data from GitHub API
# Output: JSON to stdout

# Fetch a single issue by number
# Args: owner, repo, issue_number
# Output: JSON with issue data
fetch_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: fetch_issue requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.issue_by_number.query' "$ISSUE_GRAPHQL_QUERIES")" \
        -f owner="$owner" \
        -f repo="$repo" \
        -F number="$number"
}

# Discover issues in a repository
# Args: owner, repo, [states: "OPEN", "CLOSED", or "OPEN,CLOSED"], [first: default 50]
# Output: JSON with issue list
discover_repo_issues() {
    local owner="$1"
    local repo="$2"
    local states="${3:-OPEN}"
    local first="${4:-50}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_issues requires owner and repo arguments" >&2
        return 2
    fi

    # Build states array for GraphQL
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
        query(\$owner: String!, \$repo: String!, \$first: Int!) {
            repository(owner: \$owner, name: \$repo) {
                issues(first: \$first, states: $states_graphql, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    totalCount
                    nodes {
                        id
                        number
                        title
                        state
                        url
                        createdAt
                        updatedAt
                        closedAt
                        author { login }
                        assignees(first: 10) {
                            nodes { login }
                        }
                        labels(first: 10) {
                            nodes { name color }
                        }
                        milestone {
                            number
                            title
                        }
                    }
                }
            }
        }" \
        -f owner="$owner" \
        -f repo="$repo" \
        -F first="$first"
}

#==============================================================================
# REST API FUNCTIONS
#==============================================================================
# Some operations are simpler with REST

# List issues using REST API
# Args: owner, repo, [state: open/closed/all], [per_page: default 30]
# Output: JSON array of issues
list_issues_rest() {
    local owner="$1"
    local repo="$2"
    local state="${3:-open}"
    local per_page="${4:-30}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: list_issues_rest requires owner and repo arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/issues?state=$state&per_page=$per_page"
}

# Get a single issue via REST
# Args: owner, repo, issue_number
# Output: JSON issue object
get_issue_rest() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: get_issue_rest requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/issues/$number"
}

#==============================================================================
# FILTER PRIMITIVES
#==============================================================================
# Pattern: filter_{criteria}
# Purpose: Filter data based on criteria
# Input: JSON from stdin
# Output: Filtered JSON to stdout

# Filter issues by state (for GraphQL response)
# Args: state ("OPEN" or "CLOSED")
# Input: JSON from discover_repo_issues
# Output: Filtered JSON
filter_issues_by_state() {
    local state="$1"
    jq --arg state "$state" '.data.repository.issues.nodes | map(select(.state == $state))'
}

# Filter issues by label
# Args: label_name
# Input: JSON from discover_repo_issues
# Output: Filtered JSON
filter_issues_by_label() {
    local label="$1"
    jq --arg label "$label" '.data.repository.issues.nodes | map(select(.labels.nodes | any(.name == $label)))'
}

# Filter issues by assignee
# Args: assignee_login
# Input: JSON from discover_repo_issues
# Output: Filtered JSON
filter_issues_by_assignee() {
    local assignee="$1"
    jq --arg assignee "$assignee" '.data.repository.issues.nodes | map(select(.assignees.nodes | any(.login == $assignee)))'
}

# Filter issues by milestone
# Args: milestone_title
# Input: JSON from discover_repo_issues
# Output: Filtered JSON
filter_issues_by_milestone() {
    local milestone="$1"
    jq --arg milestone "$milestone" '.data.repository.issues.nodes | map(select(.milestone != null and .milestone.title == $milestone))'
}

#==============================================================================
# MUTATE PRIMITIVES
#==============================================================================
# Pattern: set_{what}, add_{what}, remove_{what}, close_{entity}, reopen_{entity}
# Purpose: Modify data via mutations
# Output: JSON response to stdout

# Set milestone on an issue
# Args: issue_id, milestone_id (empty to clear)
# Output: JSON response
set_issue_milestone() {
    local issue_id="$1"
    local milestone_id="${2:-}"

    if [[ -z "$issue_id" ]]; then
        echo "ERROR: set_issue_milestone requires issue_id argument" >&2
        return 2
    fi

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.set_issue_milestone.query' "$ISSUE_GRAPHQL_QUERIES")")
    args+=(-f issueId="$issue_id")
    if [[ -n "$milestone_id" ]]; then
        args+=(-f milestoneId="$milestone_id")
    else
        args+=(-f milestoneId=null)
    fi

    gh api graphql "${args[@]}"
}

# Clear milestone from an issue
# Args: issue_id
# Output: JSON response
clear_issue_milestone() {
    local issue_id="$1"
    set_issue_milestone "$issue_id" ""
}

# Add labels to an issue
# Args: issue_id, label_ids (comma-separated node IDs)
# Output: JSON response
add_issue_labels() {
    local issue_id="$1"
    local label_ids="$2"

    if [[ -z "$issue_id" || -z "$label_ids" ]]; then
        echo "ERROR: add_issue_labels requires issue_id and label_ids arguments" >&2
        return 2
    fi

    # Convert comma-separated to JSON array
    local labels_array
    labels_array=$(echo "$label_ids" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.add_labels_to_labelable.query' "$ISSUE_GRAPHQL_QUERIES")" \
        -f labelableId="$issue_id" \
        --argjson labelIds "$labels_array"
}

# Remove labels from an issue
# Args: issue_id, label_ids (comma-separated node IDs)
# Output: JSON response
remove_issue_labels() {
    local issue_id="$1"
    local label_ids="$2"

    if [[ -z "$issue_id" || -z "$label_ids" ]]; then
        echo "ERROR: remove_issue_labels requires issue_id and label_ids arguments" >&2
        return 2
    fi

    # Convert comma-separated to JSON array
    local labels_array
    labels_array=$(echo "$label_ids" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.remove_labels_from_labelable.query' "$ISSUE_GRAPHQL_QUERIES")" \
        -f labelableId="$issue_id" \
        --argjson labelIds "$labels_array"
}

# Set assignees on an issue (replaces existing)
# Args: issue_id, assignee_ids (comma-separated node IDs)
# Output: JSON response
set_issue_assignees() {
    local issue_id="$1"
    local assignee_ids="$2"

    if [[ -z "$issue_id" ]]; then
        echo "ERROR: set_issue_assignees requires issue_id argument" >&2
        return 2
    fi

    # Convert comma-separated to JSON array (empty string = empty array)
    local assignees_array
    if [[ -n "$assignee_ids" ]]; then
        assignees_array=$(echo "$assignee_ids" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')
    else
        assignees_array="[]"
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.update_issue.query' "$ISSUE_GRAPHQL_QUERIES")" \
        -f issueId="$issue_id" \
        --argjson assigneeIds "$assignees_array"
}

# Close an issue
# Args: issue_id, [state_reason: COMPLETED/NOT_PLANNED/DUPLICATE]
# Output: JSON response
close_issue() {
    local issue_id="$1"
    local state_reason="${2:-COMPLETED}"

    if [[ -z "$issue_id" ]]; then
        echo "ERROR: close_issue requires issue_id argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.close_issue.query' "$ISSUE_GRAPHQL_QUERIES")" \
        -f issueId="$issue_id" \
        -f stateReason="$state_reason"
}

# Reopen an issue
# Args: issue_id
# Output: JSON response
reopen_issue() {
    local issue_id="$1"

    if [[ -z "$issue_id" ]]; then
        echo "ERROR: reopen_issue requires issue_id argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.reopen_issue.query' "$ISSUE_GRAPHQL_QUERIES")" \
        -f issueId="$issue_id"
}

# Create an issue (REST API - simpler for basic creation)
# Args: owner, repo, title, [body], [labels: comma-separated], [assignees: comma-separated], [milestone: number]
# Output: JSON of created issue
create_issue() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local body="${4:-}"
    local labels="${5:-}"
    local assignees="${6:-}"
    local milestone="${7:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$title" ]]; then
        echo "ERROR: create_issue requires owner, repo, and title arguments" >&2
        return 2
    fi

    local args=(-X POST)
    args+=(-f title="$title")
    [[ -n "$body" ]] && args+=(-f body="$body")
    [[ -n "$milestone" ]] && args+=(-F milestone="$milestone")

    # Labels and assignees need to be JSON arrays
    if [[ -n "$labels" ]]; then
        local labels_json
        labels_json=$(echo "$labels" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')
        args+=(--argjson labels "$labels_json")
    fi

    if [[ -n "$assignees" ]]; then
        local assignees_json
        assignees_json=$(echo "$assignees" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')
        args+=(--argjson assignees "$assignees_json")
    fi

    gh api "repos/$owner/$repo/issues" "${args[@]}"
}

#==============================================================================
# FORMAT PRIMITIVES
#==============================================================================
# Pattern: format_{entity}
# Purpose: Transform JSON to structured output
# Input: JSON from stdin
# Output: Formatted JSON to stdout

# Format single issue (GraphQL response)
# Input: JSON from fetch_issue
# Output: Formatted JSON
format_issue() {
    jq -f <(yq '.format_filters.format_issue.filter' "$ISSUE_JQ_FILTERS")
}

# Format issue list (GraphQL response)
# Input: JSON from discover_repo_issues
# Output: Formatted JSON
format_issues_list() {
    jq -f <(yq '.format_filters.format_issues_list.filter' "$ISSUE_JQ_FILTERS")
}

# Format issue list (REST response)
# Input: JSON array from list_issues_rest
# Output: Formatted JSON
format_issues_rest() {
    jq '[.[] | select(.pull_request == null) | {
        number: .number,
        title: .title,
        state: .state,
        url: .html_url,
        author: .user.login,
        assignees: [.assignees[].login],
        labels: [.labels[].name],
        milestone: (.milestone.title // null),
        createdAt: .created_at,
        updatedAt: .updated_at
    }]'
}

#==============================================================================
# EXTRACT PRIMITIVES
#==============================================================================
# Pattern: extract_{what}
# Purpose: Pull specific fields from responses
# Input: JSON from stdin
# Output: Extracted data to stdout

# Extract issue numbers from list
# Input: JSON from discover_repo_issues
# Output: Array of numbers
extract_issue_numbers() {
    jq '[.data.repository.issues.nodes[].number]'
}

# Extract issue IDs from list
# Input: JSON from discover_repo_issues
# Output: Array of IDs
extract_issue_ids() {
    jq '[.data.repository.issues.nodes[].id]'
}

#==============================================================================
# DETECT PRIMITIVES
#==============================================================================
# Pattern: detect_{what}, check_{condition}
# Purpose: Determine type/state
# Output: String or exit code

# Check if an issue exists
# Args: owner, repo, issue_number
# Returns: 0 if exists, 1 if not
check_issue_exists() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: check_issue_exists requires owner, repo, and number arguments" >&2
        return 2
    fi

    local issue_id
    issue_id=$(get_issue_id "$owner" "$repo" "$number" 2>/dev/null)

    if [[ -n "$issue_id" && "$issue_id" != "null" ]]; then
        return 0
    else
        return 1
    fi
}

# Get issue state
# Args: owner, repo, issue_number
# Output: "open" or "closed"
detect_issue_state() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: detect_issue_state requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/issues/$number" --jq '.state'
}

#==============================================================================
# CONVENIENCE FUNCTIONS
#==============================================================================
# Higher-level functions that compose primitives

# Get label ID by name
# Args: owner, repo, label_name
# Output: Label node ID
get_label_id() {
    local owner="$1"
    local repo="$2"
    local label_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$label_name" ]]; then
        echo "ERROR: get_label_id requires owner, repo, and label_name arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='
        query($owner: String!, $repo: String!, $name: String!) {
            repository(owner: $owner, name: $repo) {
                label(name: $name) {
                    id
                }
            }
        }' \
        -f owner="$owner" \
        -f repo="$repo" \
        -f name="$label_name" \
        --jq '.data.repository.label.id'
}

# Get user ID by login
# Args: login
# Output: User node ID
get_user_id() {
    local login="$1"

    if [[ -z "$login" ]]; then
        echo "ERROR: get_user_id requires login argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='
        query($login: String!) {
            user(login: $login) {
                id
            }
        }' \
        -f login="$login" \
        --jq '.data.user.id'
}

#==============================================================================
# COMPOSITION EXAMPLES
#==============================================================================
# These show how to compose primitives

# Example: List open issues in a repo
# discover_repo_issues "owner" "repo" "OPEN" | format_issues_list

# Example: Get issue ID and close it
# ISSUE_ID=$(get_issue_id "owner" "repo" 123)
# close_issue "$ISSUE_ID"

# Example: Filter issues by label
# discover_repo_issues "owner" "repo" | filter_issues_by_label "bug"
