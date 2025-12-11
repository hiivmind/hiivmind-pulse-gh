#!/usr/bin/env bash
# tests/lib/resources/label.bash
# Label resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# CREATE
# =============================================================================

# Create a label without tracking (for use in subshells)
# Usage: create_label_raw "owner" "repo" "name" [color] [description]
# Output: label name
create_label_raw() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local color="${4:-0366d6}"  # Default blue
    local description="${5:-}"

    # Remove # from color if present
    color="${color#\#}"

    local args=(-f "name=${name}" -f "color=${color}")
    [[ -n "$description" ]] && args+=(-f "description=${description}")

    local result
    result=$(gh api "repos/${owner}/${repo}/labels" "${args[@]}" 2>&1)

    # Check if label already exists
    if [[ "$result" == *"already_exists"* ]]; then
        echo "$name"
        return 0
    fi

    local returned_name
    returned_name=$(echo "$result" | jq -r '.name' 2>/dev/null)

    if [[ "$returned_name" == "null" || -z "$returned_name" ]]; then
        echo "Error: Failed to create label: $result" >&2
        return 1
    fi

    echo "$name"
}

# Create a label and track it for cleanup
# Usage: create_label "owner" "repo" "name" [color] [description]
# Output: label name
create_label() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local result_name
    result_name=$(create_label_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "label" "${owner}/${repo}/${result_name}"
        echo "$result_name"
    else
        return 1
    fi
}

# Create a label with auto-generated name
# Usage: create_test_label "owner" "repo"
# Output: label name
create_test_label() {
    local owner="$1"
    local repo="$2"
    local name
    name=$(generate_resource_name "label")

    create_label "$owner" "$repo" "$name" "ff0000" "Auto-generated test label"
}

# =============================================================================
# READ
# =============================================================================

# Get label by name
# Usage: get_label "owner" "repo" "name"
get_label() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    # URL encode the label name
    local encoded_name
    encoded_name=$(printf '%s' "$name" | jq -sRr @uri)

    gh api "repos/${owner}/${repo}/labels/${encoded_name}"
}

# List all label names
# Usage: list_labels "owner" "repo"
# Output: label names, one per line
list_labels() {
    local owner="$1"
    local repo="$2"

    gh api "repos/${owner}/${repo}/labels?per_page=100" \
        --jq '.[].name'
}

# Check if label exists
# Usage: label_exists "owner" "repo" "name"
label_exists() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    local encoded_name
    encoded_name=$(printf '%s' "$name" | jq -sRr @uri)

    gh api "repos/${owner}/${repo}/labels/${encoded_name}" &>/dev/null
}

# =============================================================================
# UPDATE
# =============================================================================

# Update label
# Usage: update_label "owner" "repo" "name" [new_name] [color] [description]
update_label() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local new_name="${4:-}"
    local color="${5:-}"
    local description="${6:-}"

    local encoded_name
    encoded_name=$(printf '%s' "$name" | jq -sRr @uri)

    local args=(-X PATCH)
    [[ -n "$new_name" ]] && args+=(-f "new_name=${new_name}")
    [[ -n "$color" ]] && args+=(-f "color=${color#\#}")
    [[ -n "$description" ]] && args+=(-f "description=${description}")

    gh api "repos/${owner}/${repo}/labels/${encoded_name}" "${args[@]}"
}

# =============================================================================
# DELETE
# =============================================================================

# Delete label by identifier
# Usage: delete_label "owner/repo/name"
delete_label() {
    local identifier="$1"

    # Parse owner/repo/name (name might contain slashes, so be careful)
    local owner="${identifier%%/*}"
    local rest="${identifier#*/}"
    local repo="${rest%%/*}"
    local name="${rest#*/}"

    local encoded_name
    encoded_name=$(printf '%s' "$name" | jq -sRr @uri)

    gh api -X DELETE "repos/${owner}/${repo}/labels/${encoded_name}" \
        2>/dev/null || true
}

# Delete label by parts
# Usage: delete_label_by_parts "owner" "repo" "name"
delete_label_by_parts() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    local encoded_name
    encoded_name=$(printf '%s' "$name" | jq -sRr @uri)

    gh api -X DELETE "repos/${owner}/${repo}/labels/${encoded_name}" \
        2>/dev/null || true
}
