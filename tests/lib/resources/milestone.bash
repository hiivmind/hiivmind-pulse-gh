#!/usr/bin/env bash
# tests/lib/resources/milestone.bash
# Milestone resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# CREATE
# =============================================================================

# Create a milestone without tracking (for use in subshells)
# Usage: create_milestone_raw "owner" "repo" "title" [description] [due_on]
# Output: milestone number
create_milestone_raw() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local description="${4:-}"
    local due_on="${5:-}"

    local args=(-f "title=${title}" -f "state=open")
    [[ -n "$description" ]] && args+=(-f "description=${description}")
    [[ -n "$due_on" ]] && args+=(-f "due_on=${due_on}")

    local result
    result=$(gh api "repos/${owner}/${repo}/milestones" "${args[@]}")

    local number
    number=$(echo "$result" | jq -r '.number')

    if [[ "$number" == "null" || -z "$number" ]]; then
        echo "Error: Failed to create milestone" >&2
        return 1
    fi

    echo "$number"
}

# Create a milestone and track it for cleanup
# Usage: create_milestone "owner" "repo" "title" [description] [due_on]
# Output: milestone number
create_milestone() {
    local owner="$1"
    local repo="$2"
    local number
    number=$(create_milestone_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "milestone" "${owner}/${repo}/${number}"
        echo "$number"
    else
        return 1
    fi
}

# Create a milestone with auto-generated name
# Usage: create_test_milestone "owner" "repo"
# Output: milestone number
create_test_milestone() {
    local owner="$1"
    local repo="$2"
    local title
    title=$(generate_resource_name "milestone")

    create_milestone "$owner" "$repo" "$title" "Auto-generated test milestone"
}

# =============================================================================
# READ
# =============================================================================

# Get milestone by number
# Usage: get_milestone "owner" "repo" "number"
get_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/milestones/${number}"
}

# List all milestone numbers
# Usage: list_milestones "owner" "repo" [state]
# Output: milestone numbers, one per line
list_milestones() {
    local owner="$1"
    local repo="$2"
    local state="${3:-all}"

    gh api "repos/${owner}/${repo}/milestones?state=${state}&per_page=100" \
        --jq '.[].number'
}

# Check if milestone exists
# Usage: milestone_exists "owner" "repo" "number"
milestone_exists() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/milestones/${number}" &>/dev/null
}

# =============================================================================
# UPDATE
# =============================================================================

# Update milestone
# Usage: update_milestone "owner" "repo" "number" [title] [description] [state] [due_on]
update_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local title="${4:-}"
    local description="${5:-}"
    local state="${6:-}"
    local due_on="${7:-}"

    local args=(-X PATCH)
    [[ -n "$title" ]] && args+=(-f "title=${title}")
    [[ -n "$description" ]] && args+=(-f "description=${description}")
    [[ -n "$state" ]] && args+=(-f "state=${state}")
    [[ -n "$due_on" ]] && args+=(-f "due_on=${due_on}")

    gh api "repos/${owner}/${repo}/milestones/${number}" "${args[@]}"
}

# Close milestone
# Usage: close_milestone "owner" "repo" "number"
close_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/milestones/${number}" \
        -X PATCH -f state=closed
}

# =============================================================================
# DELETE
# =============================================================================

# Delete milestone by identifier
# Usage: delete_milestone "owner/repo/number"
delete_milestone() {
    local identifier="$1"

    parse_owner_repo_number "$identifier"

    gh api -X DELETE "repos/${PARSED_OWNER}/${PARSED_REPO}/milestones/${PARSED_NUMBER}" \
        2>/dev/null || true
}

# Delete milestone by parts
# Usage: delete_milestone_by_parts "owner" "repo" "number"
delete_milestone_by_parts() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api -X DELETE "repos/${owner}/${repo}/milestones/${number}" \
        2>/dev/null || true
}
