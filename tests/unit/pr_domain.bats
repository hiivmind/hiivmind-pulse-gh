#!/usr/bin/env bats
# Unit tests for pull request domain functions
# Tests jq filters and format functions using recorded fixtures

load '../test_helper'

setup() {
    # Source the fixtures helper
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"

    # Get project root for filter loading
    PROJECT_ROOT=$(get_project_root)
    PR_JQ_FILTERS="${PROJECT_ROOT}/lib/github/gh-pr-jq-filters.yaml"
}

# =============================================================================
# Fixture Loading Tests
# =============================================================================

@test "pr fixtures: repo_prs.json loads successfully" {
    run load_graphql_fixture "pr" "repo_prs"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.repository.pullRequests' > /dev/null
}

# =============================================================================
# PR Structure Tests
# =============================================================================

@test "pr fixture: has pullRequests array" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes' > /dev/null
}

@test "pr fixture: has totalCount" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    total_count=$(echo "$fixture" | jq '.data.repository.pullRequests.totalCount')

    [ "$total_count" -ge 0 ]
}

@test "pr fixture: totalCount matches nodes length" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    total_count=$(echo "$fixture" | jq '.data.repository.pullRequests.totalCount')
    nodes_count=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes | length')

    [ "$total_count" -eq "$nodes_count" ]
}

# =============================================================================
# PR Node Tests
# =============================================================================

@test "pr node: has required fields" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    # Check first PR has required fields
    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0].id' > /dev/null
    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0].number' > /dev/null
    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0].title' > /dev/null
    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0].state' > /dev/null
}

@test "pr node: number is positive integer" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    number=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes[0].number')

    [ "$number" -gt 0 ]
}

@test "pr node: state is valid GraphQL enum" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    state=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].state')

    # GraphQL PR states: OPEN, CLOSED, MERGED
    [[ "$state" == "OPEN" || "$state" == "CLOSED" || "$state" == "MERGED" ]]
}

@test "pr node: title is non-empty string" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    title=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].title')

    [ -n "$title" ]
}

# =============================================================================
# Branch Reference Tests
# =============================================================================

@test "pr node: has headRefName" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    head_ref=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].headRefName')

    [ -n "$head_ref" ]
}

@test "pr node: has baseRefName" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    base_ref=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].baseRefName')

    [ -n "$base_ref" ]
}

@test "pr node: headRefName is valid branch name" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    head_ref=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].headRefName')

    # Branch names can contain alphanumeric, hyphens, underscores, slashes
    [[ "$head_ref" =~ ^[a-zA-Z0-9/_-]+$ ]]
}

# =============================================================================
# Draft Status Tests
# =============================================================================

@test "pr node: has isDraft field" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0] | has("isDraft")' > /dev/null
}

@test "pr node: isDraft is boolean" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    is_draft=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes[0].isDraft')

    [[ "$is_draft" == "true" || "$is_draft" == "false" ]]
}

# =============================================================================
# Mergeable Status Tests
# =============================================================================

@test "pr node: has mergeable field" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0] | has("mergeable")' > /dev/null
}

@test "pr node: mergeable is valid enum" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    mergeable=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].mergeable')

    # Mergeable states: MERGEABLE, CONFLICTING, UNKNOWN
    [[ "$mergeable" == "MERGEABLE" || "$mergeable" == "CONFLICTING" || "$mergeable" == "UNKNOWN" ]]
}

# =============================================================================
# Author Tests
# =============================================================================

@test "pr node: has author" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0].author' > /dev/null
}

@test "pr node: author has login" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    login=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].author.login')

    [ -n "$login" ]
}

# =============================================================================
# Labels Tests
# =============================================================================

@test "pr node: has labels field" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    echo "$fixture" | jq -e '.data.repository.pullRequests.nodes[0].labels' > /dev/null
}

@test "pr node: labels.nodes is array" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    type=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes[0].labels.nodes | type')

    [ "$type" == '"array"' ]
}

# =============================================================================
# Timestamp Tests
# =============================================================================

@test "pr node: createdAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    created_at=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].createdAt')

    [[ "$created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "pr node: updatedAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    updated_at=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].updatedAt')

    [[ "$updated_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# =============================================================================
# Data Extraction Tests
# =============================================================================

@test "extract pr numbers: all positive" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    numbers=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes[].number')

    while IFS= read -r num; do
        [ "$num" -gt 0 ]
    done <<< "$numbers"
}

@test "extract pr states: all valid" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    states=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[].state')

    while IFS= read -r state; do
        [[ "$state" == "OPEN" || "$state" == "CLOSED" || "$state" == "MERGED" ]]
    done <<< "$states"
}

# =============================================================================
# Filter Tests
# =============================================================================

@test "filter prs: can filter by state" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    # Filter to only OPEN PRs
    open_prs=$(echo "$fixture" | jq '[.data.repository.pullRequests.nodes[] | select(.state == "OPEN")]')

    type=$(echo "$open_prs" | jq 'type')
    [ "$type" == '"array"' ]
}

@test "filter prs: can filter by draft status" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    # Filter to non-draft PRs
    ready_prs=$(echo "$fixture" | jq '[.data.repository.pullRequests.nodes[] | select(.isDraft == false)]')

    type=$(echo "$ready_prs" | jq 'type')
    [ "$type" == '"array"' ]
}

@test "filter prs: can extract by number" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    # Get first PR number
    first_num=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes[0].number')

    # Find it by number
    pr=$(echo "$fixture" | jq ".data.repository.pullRequests.nodes[] | select(.number == $first_num)")

    # Should find it
    [ -n "$pr" ]
}

# =============================================================================
# Edge Case Tests
# =============================================================================

@test "pr node: handles empty labels" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    # Labels array might be empty
    count=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes[0].labels.nodes | length')

    # Should be a number (0 or more)
    [ "$count" -ge 0 ]
}

@test "pr node: body can be empty or null" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    # Body might be null or empty
    body=$(echo "$fixture" | jq -r '.data.repository.pullRequests.nodes[0].body // ""')

    # Should not error
    [ $? -eq 0 ]
}

@test "pr: can distinguish between OPEN and MERGED" {
    fixture=$(load_graphql_fixture "pr" "repo_prs")

    # Count by state
    open_count=$(echo "$fixture" | jq '[.data.repository.pullRequests.nodes[] | select(.state == "OPEN")] | length')
    merged_count=$(echo "$fixture" | jq '[.data.repository.pullRequests.nodes[] | select(.state == "MERGED")] | length')
    closed_count=$(echo "$fixture" | jq '[.data.repository.pullRequests.nodes[] | select(.state == "CLOSED")] | length')
    total=$(echo "$fixture" | jq '.data.repository.pullRequests.nodes | length')

    # Sum should equal total
    sum=$((open_count + merged_count + closed_count))
    [ "$sum" -eq "$total" ]
}
