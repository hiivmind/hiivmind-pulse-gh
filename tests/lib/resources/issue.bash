#!/usr/bin/env bash
# tests/lib/resources/issue.bash
# Issue resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# CREATE
# =============================================================================

# Create an issue without tracking (for use in subshells)
# Usage: create_issue_raw "owner" "repo" "title" [body] [labels] [milestone]
# Output: issue number
create_issue_raw() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local body="${4:-}"
    local labels="${5:-}"
    local milestone="${6:-}"

    local args=(-f "title=${title}")
    [[ -n "$body" ]] && args+=(-f "body=${body}")
    [[ -n "$labels" ]] && args+=(-f "labels=${labels}")
    [[ -n "$milestone" ]] && args+=(-f "milestone=${milestone}")

    local result
    result=$(gh api "repos/${owner}/${repo}/issues" "${args[@]}")

    local number
    number=$(echo "$result" | jq -r '.number')

    if [[ "$number" == "null" || -z "$number" ]]; then
        echo "Error: Failed to create issue" >&2
        return 1
    fi

    echo "$number"
}

# Create an issue and track it for cleanup
# Usage: create_issue "owner" "repo" "title" [body] [labels] [milestone]
# Output: issue number
create_issue() {
    local owner="$1"
    local repo="$2"
    local number
    number=$(create_issue_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "issue" "${owner}/${repo}/${number}"
        echo "$number"
    else
        return 1
    fi
}

# Create an issue with auto-generated title
# Usage: create_test_issue "owner" "repo"
# Output: issue number
create_test_issue() {
    local owner="$1"
    local repo="$2"
    local title
    title=$(generate_resource_name "issue")

    create_issue "$owner" "$repo" "$title" "Auto-generated test issue"
}

# =============================================================================
# READ
# =============================================================================

# Get issue by number
# Usage: get_issue "owner" "repo" "number"
get_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/issues/${number}"
}

# List all issue numbers
# Usage: list_issues "owner" "repo" [state]
# Output: issue numbers, one per line
list_issues() {
    local owner="$1"
    local repo="$2"
    local state="${3:-all}"

    gh api "repos/${owner}/${repo}/issues?state=${state}&per_page=100" \
        --jq '.[] | select(.pull_request == null) | .number'
}

# Check if issue exists
# Usage: issue_exists "owner" "repo" "number"
issue_exists() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/issues/${number}" &>/dev/null
}

# =============================================================================
# UPDATE
# =============================================================================

# Update issue
# Usage: update_issue "owner" "repo" "number" [title] [body] [state]
update_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local title="${4:-}"
    local body="${5:-}"
    local state="${6:-}"

    local args=(-X PATCH)
    [[ -n "$title" ]] && args+=(-f "title=${title}")
    [[ -n "$body" ]] && args+=(-f "body=${body}")
    [[ -n "$state" ]] && args+=(-f "state=${state}")

    gh api "repos/${owner}/${repo}/issues/${number}" "${args[@]}"
}

# Close issue
# Usage: close_issue "owner" "repo" "number"
close_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/issues/${number}" \
        -X PATCH -f state=closed
}

# Reopen issue
# Usage: reopen_issue "owner" "repo" "number"
reopen_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/issues/${number}" \
        -X PATCH -f state=open
}

# Add labels to issue
# Usage: add_issue_labels "owner" "repo" "number" "label1,label2"
add_issue_labels() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local labels="$4"

    # Convert comma-separated to JSON array
    local labels_json
    labels_json=$(echo "$labels" | jq -R 'split(",") | map(select(length > 0))')

    gh api "repos/${owner}/${repo}/issues/${number}/labels" \
        --input - <<< "{\"labels\": ${labels_json}}"
}

# Set issue milestone
# Usage: set_issue_milestone "owner" "repo" "number" "milestone_number"
set_issue_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local milestone="$4"

    gh api "repos/${owner}/${repo}/issues/${number}" \
        -X PATCH -F "milestone=${milestone}"
}

# =============================================================================
# DELETE
# =============================================================================

# Delete (close) issue by identifier
# Note: GitHub doesn't allow deleting issues, so we close them instead
# Usage: delete_issue "owner/repo/number"
delete_issue() {
    local identifier="$1"

    parse_owner_repo_number "$identifier"

    # Can't delete issues, close them instead
    gh api "repos/${PARSED_OWNER}/${PARSED_REPO}/issues/${PARSED_NUMBER}" \
        -X PATCH -f state=closed 2>/dev/null || true
}

# Delete issue by parts
# Usage: delete_issue_by_parts "owner" "repo" "number"
delete_issue_by_parts() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/issues/${number}" \
        -X PATCH -f state=closed 2>/dev/null || true
}
