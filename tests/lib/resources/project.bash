#!/usr/bin/env bash
# tests/lib/resources/project.bash
# Project item resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# HELPERS
# =============================================================================

# Get project node ID from project number
# Usage: get_project_node_id "org" "project_number"
get_project_node_id() {
    local org="$1"
    local project_number="$2"

    gh api graphql -f query='
        query($org: String!, $number: Int!) {
            organization(login: $org) {
                projectV2(number: $number) {
                    id
                }
            }
        }
    ' -F org="$org" -F number="$project_number" --jq '.data.organization.projectV2.id'
}

# Get issue/PR node ID
# Usage: get_content_node_id "owner" "repo" "number" "type"
# type: "issue" or "pr"
get_content_node_id() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local type="${4:-issue}"

    if [[ "$type" == "pr" ]]; then
        gh api graphql -f query='
            query($owner: String!, $repo: String!, $number: Int!) {
                repository(owner: $owner, name: $repo) {
                    pullRequest(number: $number) {
                        id
                    }
                }
            }
        ' -f owner="$owner" -f repo="$repo" -F number="$number" --jq '.data.repository.pullRequest.id'
    else
        gh api graphql -f query='
            query($owner: String!, $repo: String!, $number: Int!) {
                repository(owner: $owner, name: $repo) {
                    issue(number: $number) {
                        id
                    }
                }
            }
        ' -f owner="$owner" -f repo="$repo" -F number="$number" --jq '.data.repository.issue.id'
    fi
}

# =============================================================================
# CREATE
# =============================================================================

# Add an item to a project without tracking (for use in subshells)
# Usage: add_project_item_raw "org" "project_number" "owner" "repo" "content_number" [type]
# Output: project item ID
add_project_item_raw() {
    local org="$1"
    local project_number="$2"
    local owner="$3"
    local repo="$4"
    local content_number="$5"
    local type="${6:-issue}"

    # Get project node ID
    local project_id
    project_id=$(get_project_node_id "$org" "$project_number")

    if [[ -z "$project_id" || "$project_id" == "null" ]]; then
        echo "Error: Could not find project $org/$project_number" >&2
        return 1
    fi

    # Get content node ID
    local content_id
    content_id=$(get_content_node_id "$owner" "$repo" "$content_number" "$type")

    if [[ -z "$content_id" || "$content_id" == "null" ]]; then
        echo "Error: Could not find $type $owner/$repo#$content_number" >&2
        return 1
    fi

    # Add item to project
    local result
    result=$(gh api graphql -f query='
        mutation($projectId: ID!, $contentId: ID!) {
            addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
                item {
                    id
                }
            }
        }
    ' -f projectId="$project_id" -f contentId="$content_id")

    local item_id
    item_id=$(echo "$result" | jq -r '.data.addProjectV2ItemById.item.id')

    if [[ -z "$item_id" || "$item_id" == "null" ]]; then
        echo "Error: Failed to add item to project: $result" >&2
        return 1
    fi

    echo "$item_id"
}

# Add an item to a project and track it for cleanup
# Usage: add_project_item "org" "project_number" "owner" "repo" "content_number" [type]
# Output: project item ID
add_project_item() {
    local org="$1"
    local project_number="$2"
    local item_id
    item_id=$(add_project_item_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "project_item" "${org}/${project_number}/${item_id}"
        echo "$item_id"
    else
        return 1
    fi
}

# Create a draft item in a project without tracking
# Usage: create_draft_item_raw "org" "project_number" "title" [body]
# Output: project item ID
create_draft_item_raw() {
    local org="$1"
    local project_number="$2"
    local title="$3"
    local body="${4:-}"

    # Get project node ID
    local project_id
    project_id=$(get_project_node_id "$org" "$project_number")

    if [[ -z "$project_id" || "$project_id" == "null" ]]; then
        echo "Error: Could not find project $org/$project_number" >&2
        return 1
    fi

    # Create draft item
    local result
    if [[ -n "$body" ]]; then
        result=$(gh api graphql -f query='
            mutation($projectId: ID!, $title: String!, $body: String) {
                addProjectV2DraftIssue(input: {projectId: $projectId, title: $title, body: $body}) {
                    projectItem {
                        id
                    }
                }
            }
        ' -f projectId="$project_id" -f title="$title" -f body="$body")
    else
        result=$(gh api graphql -f query='
            mutation($projectId: ID!, $title: String!) {
                addProjectV2DraftIssue(input: {projectId: $projectId, title: $title}) {
                    projectItem {
                        id
                    }
                }
            }
        ' -f projectId="$project_id" -f title="$title")
    fi

    local item_id
    item_id=$(echo "$result" | jq -r '.data.addProjectV2DraftIssue.projectItem.id')

    if [[ -z "$item_id" || "$item_id" == "null" ]]; then
        echo "Error: Failed to create draft item: $result" >&2
        return 1
    fi

    echo "$item_id"
}

# Create a draft item in a project and track it for cleanup
# Usage: create_draft_item "org" "project_number" "title" [body]
# Output: project item ID
create_draft_item() {
    local org="$1"
    local project_number="$2"
    local item_id
    item_id=$(create_draft_item_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "project_item" "${org}/${project_number}/${item_id}"
        echo "$item_id"
    else
        return 1
    fi
}

# Create a test draft item with auto-generated title
# Usage: create_test_project_item "org" "project_number"
# Output: project item ID
create_test_project_item() {
    local org="$1"
    local project_number="$2"
    local title
    title="Test Item $(date +%s)"

    create_draft_item "$org" "$project_number" "$title" "Auto-generated test item"
}

# =============================================================================
# READ
# =============================================================================

# Get project item by ID
# Usage: get_project_item "org" "project_number" "item_id"
get_project_item() {
    local org="$1"
    local project_number="$2"
    local item_id="$3"

    local project_id
    project_id=$(get_project_node_id "$org" "$project_number")

    gh api graphql -f query='
        query($id: ID!) {
            node(id: $id) {
                ... on ProjectV2Item {
                    id
                    type
                    createdAt
                    content {
                        ... on Issue {
                            title
                            number
                        }
                        ... on PullRequest {
                            title
                            number
                        }
                        ... on DraftIssue {
                            title
                            body
                        }
                    }
                }
            }
        }
    ' -f id="$item_id"
}

# List project items
# Usage: list_project_items "org" "project_number" [first]
# Output: item IDs, one per line
list_project_items() {
    local org="$1"
    local project_number="$2"
    local first="${3:-100}"

    gh api graphql -f query='
        query($org: String!, $number: Int!, $first: Int!) {
            organization(login: $org) {
                projectV2(number: $number) {
                    items(first: $first) {
                        nodes {
                            id
                        }
                    }
                }
            }
        }
    ' -f org="$org" -F number="$project_number" -F first="$first" \
        --jq '.data.organization.projectV2.items.nodes[].id'
}

# Check if project item exists
# Usage: project_item_exists "item_id"
project_item_exists() {
    local item_id="$1"

    local result
    result=$(gh api graphql -f query='
        query($id: ID!) {
            node(id: $id) {
                ... on ProjectV2Item {
                    id
                }
            }
        }
    ' -f id="$item_id" --jq '.data.node.id' 2>/dev/null)

    [[ -n "$result" && "$result" != "null" ]]
}

# =============================================================================
# DELETE
# =============================================================================

# Delete project item by identifier
# Usage: delete_project_item "org/project_number/item_id"
delete_project_item() {
    local identifier="$1"

    # Parse org/project_number/item_id
    local org="${identifier%%/*}"
    local rest="${identifier#*/}"
    local project_number="${rest%%/*}"
    local item_id="${rest#*/}"

    # Get project node ID
    local project_id
    project_id=$(get_project_node_id "$org" "$project_number" 2>/dev/null) || return 0

    if [[ -z "$project_id" || "$project_id" == "null" ]]; then
        return 0
    fi

    # Delete the item
    gh api graphql -f query='
        mutation($projectId: ID!, $itemId: ID!) {
            deleteProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
                deletedItemId
            }
        }
    ' -f projectId="$project_id" -f itemId="$item_id" 2>/dev/null || true
}

# Delete project item by parts
# Usage: delete_project_item_by_parts "org" "project_number" "item_id"
delete_project_item_by_parts() {
    local org="$1"
    local project_number="$2"
    local item_id="$3"

    delete_project_item "${org}/${project_number}/${item_id}"
}
