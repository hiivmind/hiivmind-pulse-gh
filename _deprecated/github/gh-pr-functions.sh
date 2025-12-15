#!/bin/bash
# GitHub Pull Request Domain Functions
# Source this file to use: source gh-pr-functions.sh
#
# This domain handles:
# - Pull request queries (GraphQL and REST)
# - Pull request mutations (labels, assignees, milestones, reviewers)
#
# Dependencies:
#   - gh (GitHub CLI, authenticated)
#   - jq (1.6+)
#   - yq (4.0+)
#
# Follows hiivmind-pulse-gh architecture principles:
#   - Explicit scope prefixes (repo_)
#   - Pipe-first composition pattern
#   - Single responsibility per function

set -euo pipefail

# Ensure yq is in PATH (snap installs to /snap/bin on Ubuntu)
export PATH="/snap/bin:$PATH"

# Get the directory where this script is located
PR_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# YAML template locations
PR_GRAPHQL_QUERIES="$PR_SCRIPT_DIR/gh-pr-graphql-queries.yaml"
PR_JQ_FILTERS="$PR_SCRIPT_DIR/gh-pr-jq-filters.yaml"

#==============================================================================
# LOOKUP PRIMITIVES
#==============================================================================
# Pattern: get_{entity}_id
# Purpose: Resolve identifiers (number -> node ID)
# Output: Single value (ID string) to stdout

# Get a pull request's GraphQL node ID by number
# Args: owner, repo, pr_number
# Output: Node ID string (e.g., "PR_kw...")
get_pr_id() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: get_pr_id requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query='
        query($owner: String!, $repo: String!, $number: Int!) {
            repository(owner: $owner, name: $repo) {
                pullRequest(number: $number) {
                    id
                }
            }
        }' \
        -f owner="$owner" \
        -f repo="$repo" \
        -F number="$number" \
        --jq '.data.repository.pullRequest.id'
}

#==============================================================================
# FETCH PRIMITIVES (GraphQL)
#==============================================================================
# Pattern: fetch_{entity}, discover_{scope}_{entities}
# Purpose: Retrieve data from GitHub API
# Output: JSON to stdout

# Fetch a single pull request by number
# Args: owner, repo, pr_number
# Output: JSON with PR data
fetch_pr() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: fetch_pr requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.queries.pr_by_number.query' "$PR_GRAPHQL_QUERIES")" \
        -f owner="$owner" \
        -f repo="$repo" \
        -F number="$number"
}

# Discover pull requests in a repository
# Args: owner, repo, [states: "OPEN", "CLOSED", "MERGED", or combinations], [first: default 50]
# Output: JSON with PR list
discover_repo_prs() {
    local owner="$1"
    local repo="$2"
    local states="${3:-OPEN}"
    local first="${4:-50}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_prs requires owner and repo arguments" >&2
        return 2
    fi

    # Build states array for GraphQL
    local states_graphql
    if [[ "$states" == *","* ]]; then
        # Multiple states - build array
        states_graphql=$(echo "$states" | sed 's/,/, /g' | sed 's/^/[/' | sed 's/$/]/')
    else
        states_graphql="[$states]"
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="
        query(\$owner: String!, \$repo: String!, \$first: Int!) {
            repository(owner: \$owner, name: \$repo) {
                pullRequests(first: \$first, states: $states_graphql, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    totalCount
                    nodes {
                        id
                        number
                        title
                        state
                        isDraft
                        url
                        createdAt
                        updatedAt
                        mergedAt
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
                        reviewRequests(first: 10) {
                            nodes {
                                requestedReviewer {
                                    ... on User { login }
                                    ... on Team { name }
                                }
                            }
                        }
                        reviews(first: 10) {
                            nodes {
                                author { login }
                                state
                            }
                        }
                        headRefName
                        baseRefName
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

# List pull requests using REST API
# Args: owner, repo, [state: open/closed/all], [per_page: default 30]
# Output: JSON array of PRs
list_prs_rest() {
    local owner="$1"
    local repo="$2"
    local state="${3:-open}"
    local per_page="${4:-30}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: list_prs_rest requires owner and repo arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/pulls?state=$state&per_page=$per_page"
}

# Get a single PR via REST
# Args: owner, repo, pr_number
# Output: JSON PR object
get_pr_rest() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: get_pr_rest requires owner, repo, and number arguments" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/pulls/$number"
}

#==============================================================================
# FILTER PRIMITIVES
#==============================================================================
# Pattern: filter_{criteria}
# Purpose: Filter data based on criteria
# Input: JSON from stdin
# Output: Filtered JSON to stdout

# Filter PRs by state (for GraphQL response)
# Args: state ("OPEN", "CLOSED", or "MERGED")
# Input: JSON from discover_repo_prs
# Output: Filtered JSON
filter_prs_by_state() {
    local state="$1"
    jq --arg state "$state" '.data.repository.pullRequests.nodes | map(select(.state == $state))'
}

# Filter PRs by label
# Args: label_name
# Input: JSON from discover_repo_prs
# Output: Filtered JSON
filter_prs_by_label() {
    local label="$1"
    jq --arg label "$label" '.data.repository.pullRequests.nodes | map(select(.labels.nodes | any(.name == $label)))'
}

# Filter PRs by assignee
# Args: assignee_login
# Input: JSON from discover_repo_prs
# Output: Filtered JSON
filter_prs_by_assignee() {
    local assignee="$1"
    jq --arg assignee "$assignee" '.data.repository.pullRequests.nodes | map(select(.assignees.nodes | any(.login == $assignee)))'
}

# Filter PRs by requested reviewer
# Args: reviewer_login
# Input: JSON from discover_repo_prs
# Output: Filtered JSON
filter_prs_by_reviewer() {
    local reviewer="$1"
    jq --arg reviewer "$reviewer" '.data.repository.pullRequests.nodes | map(select(.reviewRequests.nodes | any(.requestedReviewer.login == $reviewer)))'
}

# Filter PRs by author
# Args: author_login
# Input: JSON from discover_repo_prs
# Output: Filtered JSON
filter_prs_by_author() {
    local author="$1"
    jq --arg author "$author" '.data.repository.pullRequests.nodes | map(select(.author.login == $author))'
}

# Filter draft PRs
# Input: JSON from discover_repo_prs
# Output: Filtered JSON (drafts only)
filter_draft_prs() {
    jq '.data.repository.pullRequests.nodes | map(select(.isDraft == true))'
}

# Filter ready PRs (non-draft)
# Input: JSON from discover_repo_prs
# Output: Filtered JSON (ready only)
filter_ready_prs() {
    jq '.data.repository.pullRequests.nodes | map(select(.isDraft == false))'
}

#==============================================================================
# MUTATE PRIMITIVES
#==============================================================================
# Pattern: set_{what}, add_{what}, remove_{what}, request_{what}
# Purpose: Modify data via mutations
# Output: JSON response to stdout

# Set milestone on a pull request
# Args: pr_id, milestone_id (empty to clear)
# Output: JSON response
set_pr_milestone() {
    local pr_id="$1"
    local milestone_id="${2:-}"

    if [[ -z "$pr_id" ]]; then
        echo "ERROR: set_pr_milestone requires pr_id argument" >&2
        return 2
    fi

    local args=(-H X-Github-Next-Global-ID:1)
    args+=(-f query="$(yq '.mutations.set_pr_milestone.query' "$PR_GRAPHQL_QUERIES")")
    args+=(-f prId="$pr_id")
    if [[ -n "$milestone_id" ]]; then
        args+=(-f milestoneId="$milestone_id")
    else
        args+=(-f milestoneId=null)
    fi

    gh api graphql "${args[@]}"
}

# Clear milestone from a pull request
# Args: pr_id
# Output: JSON response
clear_pr_milestone() {
    local pr_id="$1"
    set_pr_milestone "$pr_id" ""
}

# Add labels to a pull request
# Args: pr_id, label_ids (comma-separated node IDs)
# Output: JSON response
add_pr_labels() {
    local pr_id="$1"
    local label_ids="$2"

    if [[ -z "$pr_id" || -z "$label_ids" ]]; then
        echo "ERROR: add_pr_labels requires pr_id and label_ids arguments" >&2
        return 2
    fi

    # Convert comma-separated to JSON array
    local labels_array
    labels_array=$(echo "$label_ids" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.add_labels_to_labelable.query' "$PR_GRAPHQL_QUERIES")" \
        -f labelableId="$pr_id" \
        --argjson labelIds "$labels_array"
}

# Remove labels from a pull request
# Args: pr_id, label_ids (comma-separated node IDs)
# Output: JSON response
remove_pr_labels() {
    local pr_id="$1"
    local label_ids="$2"

    if [[ -z "$pr_id" || -z "$label_ids" ]]; then
        echo "ERROR: remove_pr_labels requires pr_id and label_ids arguments" >&2
        return 2
    fi

    # Convert comma-separated to JSON array
    local labels_array
    labels_array=$(echo "$label_ids" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.remove_labels_from_labelable.query' "$PR_GRAPHQL_QUERIES")" \
        -f labelableId="$pr_id" \
        --argjson labelIds "$labels_array"
}

# Set assignees on a pull request (replaces existing)
# Args: pr_id, assignee_ids (comma-separated node IDs)
# Output: JSON response
set_pr_assignees() {
    local pr_id="$1"
    local assignee_ids="$2"

    if [[ -z "$pr_id" ]]; then
        echo "ERROR: set_pr_assignees requires pr_id argument" >&2
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
        -f query="$(yq '.mutations.update_pull_request.query' "$PR_GRAPHQL_QUERIES")" \
        -f prId="$pr_id" \
        --argjson assigneeIds "$assignees_array"
}

# Request reviewers for a pull request (REST - simpler for user logins)
# Args: owner, repo, pr_number, reviewers (comma-separated logins)
# Output: JSON response
request_pr_review() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local reviewers="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$number" || -z "$reviewers" ]]; then
        echo "ERROR: request_pr_review requires owner, repo, number, and reviewers arguments" >&2
        return 2
    fi

    # Convert comma-separated to JSON array
    local reviewers_json
    reviewers_json=$(echo "$reviewers" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')

    gh api "repos/$owner/$repo/pulls/$number/requested_reviewers" \
        -X POST \
        --argjson reviewers "$reviewers_json"
}

# Mark PR as ready for review (convert from draft)
# Args: pr_id
# Output: JSON response
mark_pr_ready() {
    local pr_id="$1"

    if [[ -z "$pr_id" ]]; then
        echo "ERROR: mark_pr_ready requires pr_id argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.mark_ready_for_review.query' "$PR_GRAPHQL_QUERIES")" \
        -f prId="$pr_id"
}

# Convert PR to draft
# Args: pr_id
# Output: JSON response
convert_pr_to_draft() {
    local pr_id="$1"

    if [[ -z "$pr_id" ]]; then
        echo "ERROR: convert_pr_to_draft requires pr_id argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.convert_to_draft.query' "$PR_GRAPHQL_QUERIES")" \
        -f prId="$pr_id"
}

# Close a pull request
# Args: pr_id
# Output: JSON response
close_pr() {
    local pr_id="$1"

    if [[ -z "$pr_id" ]]; then
        echo "ERROR: close_pr requires pr_id argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.close_pull_request.query' "$PR_GRAPHQL_QUERIES")" \
        -f prId="$pr_id"
}

# Reopen a pull request
# Args: pr_id
# Output: JSON response
reopen_pr() {
    local pr_id="$1"

    if [[ -z "$pr_id" ]]; then
        echo "ERROR: reopen_pr requires pr_id argument" >&2
        return 2
    fi

    gh api graphql -H X-Github-Next-Global-ID:1 \
        -f query="$(yq '.mutations.reopen_pull_request.query' "$PR_GRAPHQL_QUERIES")" \
        -f prId="$pr_id"
}

#==============================================================================
# FORMAT PRIMITIVES
#==============================================================================
# Pattern: format_{entity}
# Purpose: Transform JSON to structured output
# Input: JSON from stdin
# Output: Formatted JSON to stdout

# Format single PR (GraphQL response)
# Input: JSON from fetch_pr
# Output: Formatted JSON
format_pr() {
    jq -f <(yq '.format_filters.format_pr.filter' "$PR_JQ_FILTERS")
}

# Format PR list (GraphQL response)
# Input: JSON from discover_repo_prs
# Output: Formatted JSON
format_prs_list() {
    jq -f <(yq '.format_filters.format_prs_list.filter' "$PR_JQ_FILTERS")
}

# Format PR list (REST response)
# Input: JSON array from list_prs_rest
# Output: Formatted JSON
format_prs_rest() {
    jq '[.[] | {
        number: .number,
        title: .title,
        state: .state,
        draft: .draft,
        url: .html_url,
        author: .user.login,
        assignees: [.assignees[].login],
        labels: [.labels[].name],
        headBranch: .head.ref,
        baseBranch: .base.ref,
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

# Extract PR numbers from list
# Input: JSON from discover_repo_prs
# Output: Array of numbers
extract_pr_numbers() {
    jq '[.data.repository.pullRequests.nodes[].number]'
}

# Extract PR IDs from list
# Input: JSON from discover_repo_prs
# Output: Array of IDs
extract_pr_ids() {
    jq '[.data.repository.pullRequests.nodes[].id]'
}

#==============================================================================
# DETECT PRIMITIVES
#==============================================================================
# Pattern: detect_{what}, check_{condition}
# Purpose: Determine type/state
# Output: String or exit code

# Check if a PR exists
# Args: owner, repo, pr_number
# Returns: 0 if exists, 1 if not
check_pr_exists() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: check_pr_exists requires owner, repo, and number arguments" >&2
        return 2
    fi

    local pr_id
    pr_id=$(get_pr_id "$owner" "$repo" "$number" 2>/dev/null)

    if [[ -n "$pr_id" && "$pr_id" != "null" ]]; then
        return 0
    else
        return 1
    fi
}

# Get PR state
# Args: owner, repo, pr_number
# Output: "open", "closed", or "merged"
detect_pr_state() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: detect_pr_state requires owner, repo, and number arguments" >&2
        return 2
    fi

    local result
    result=$(gh api "repos/$owner/$repo/pulls/$number" --jq 'if .merged then "merged" elif .state == "closed" then "closed" else "open" end')
    echo "$result"
}

# Check if PR is mergeable
# Args: owner, repo, pr_number
# Returns: 0 if mergeable, 1 if not
check_pr_mergeable() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: check_pr_mergeable requires owner, repo, and number arguments" >&2
        return 2
    fi

    local mergeable
    mergeable=$(gh api "repos/$owner/$repo/pulls/$number" --jq '.mergeable')

    if [[ "$mergeable" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Check if PR is a draft
# Args: owner, repo, pr_number
# Returns: 0 if draft, 1 if not
check_pr_is_draft() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$number" ]]; then
        echo "ERROR: check_pr_is_draft requires owner, repo, and number arguments" >&2
        return 2
    fi

    local draft
    draft=$(gh api "repos/$owner/$repo/pulls/$number" --jq '.draft')

    if [[ "$draft" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

#==============================================================================
# COMPOSITION EXAMPLES
#==============================================================================
# These show how to compose primitives

# Example: List open PRs in a repo
# discover_repo_prs "owner" "repo" "OPEN" | format_prs_list

# Example: Get PR ID and set milestone
# PR_ID=$(get_pr_id "owner" "repo" 123)
# set_pr_milestone "$PR_ID" "$MILESTONE_ID"

# Example: Filter PRs by author
# discover_repo_prs "owner" "repo" | filter_prs_by_author "username"
