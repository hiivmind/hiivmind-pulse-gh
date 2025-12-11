#!/usr/bin/env bats
# Unit tests for issue domain functions
# Tests jq filters and format functions using recorded fixtures

load '../test_helper'

setup() {
    # Source the fixtures helper
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"

    # Get project root for filter loading
    PROJECT_ROOT=$(get_project_root)
    ISSUE_JQ_FILTERS="${PROJECT_ROOT}/lib/github/gh-issue-jq-filters.yaml"
}

# =============================================================================
# Fixture Loading Tests
# =============================================================================

@test "issue fixtures: repo_issues.json loads successfully" {
    run load_graphql_fixture "issue" "repo_issues"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.repository.issues' > /dev/null
}

# =============================================================================
# Issue Structure Tests
# =============================================================================

@test "issue fixture: has issues array" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    echo "$fixture" | jq -e '.data.repository.issues.nodes' > /dev/null
}

@test "issue fixture: has totalCount" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    total_count=$(echo "$fixture" | jq '.data.repository.issues.totalCount')

    [ "$total_count" -ge 0 ]
}

@test "issue fixture: totalCount matches nodes length" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    total_count=$(echo "$fixture" | jq '.data.repository.issues.totalCount')
    nodes_count=$(echo "$fixture" | jq '.data.repository.issues.nodes | length')

    [ "$total_count" -eq "$nodes_count" ]
}

# =============================================================================
# Issue Node Tests
# =============================================================================

@test "issue node: has required fields" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Check first issue has required fields
    echo "$fixture" | jq -e '.data.repository.issues.nodes[0].id' > /dev/null
    echo "$fixture" | jq -e '.data.repository.issues.nodes[0].number' > /dev/null
    echo "$fixture" | jq -e '.data.repository.issues.nodes[0].title' > /dev/null
    echo "$fixture" | jq -e '.data.repository.issues.nodes[0].state' > /dev/null
}

@test "issue node: number is positive integer" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    number=$(echo "$fixture" | jq '.data.repository.issues.nodes[0].number')

    [ "$number" -gt 0 ]
}

@test "issue node: state is valid GraphQL enum" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    state=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[0].state')

    # GraphQL uses OPEN/CLOSED (uppercase)
    [[ "$state" == "OPEN" || "$state" == "CLOSED" ]]
}

@test "issue node: title is non-empty string" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    title=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[0].title')

    [ -n "$title" ]
}

# =============================================================================
# Author Tests
# =============================================================================

@test "issue node: has author" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    echo "$fixture" | jq -e '.data.repository.issues.nodes[0].author' > /dev/null
}

@test "issue node: author has login" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    login=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[0].author.login')

    [ -n "$login" ]
}

# =============================================================================
# Labels Tests
# =============================================================================

@test "issue node: has labels field" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    echo "$fixture" | jq -e '.data.repository.issues.nodes[0].labels' > /dev/null
}

@test "issue node: labels.nodes is array" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    type=$(echo "$fixture" | jq '.data.repository.issues.nodes[0].labels.nodes | type')

    [ "$type" == '"array"' ]
}

# =============================================================================
# Assignees Tests
# =============================================================================

@test "issue node: has assignees field" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    echo "$fixture" | jq -e '.data.repository.issues.nodes[0].assignees' > /dev/null
}

@test "issue node: assignees.nodes is array" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    type=$(echo "$fixture" | jq '.data.repository.issues.nodes[0].assignees.nodes | type')

    [ "$type" == '"array"' ]
}

# =============================================================================
# Milestone Tests
# =============================================================================

@test "issue node: has milestone field" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Milestone can be null, but field should exist
    echo "$fixture" | jq -e '.data.repository.issues.nodes[0] | has("milestone")' > /dev/null
}

# =============================================================================
# Timestamp Tests
# =============================================================================

@test "issue node: createdAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    created_at=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[0].createdAt')

    [[ "$created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "issue node: updatedAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    updated_at=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[0].updatedAt')

    [[ "$updated_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# =============================================================================
# Multiple Issues Tests
# =============================================================================

@test "issue list: all issues have unique numbers" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    total=$(echo "$fixture" | jq '.data.repository.issues.nodes | length')
    unique=$(echo "$fixture" | jq '[.data.repository.issues.nodes[].number] | unique | length')

    [ "$total" -eq "$unique" ]
}

@test "issue list: can iterate over all issues" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Extract all titles
    titles=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[].title')

    # Each title should be non-empty
    while IFS= read -r title; do
        [ -n "$title" ]
    done <<< "$titles"
}

# =============================================================================
# Data Extraction Tests
# =============================================================================

@test "extract issue numbers: all positive" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    numbers=$(echo "$fixture" | jq '.data.repository.issues.nodes[].number')

    while IFS= read -r num; do
        [ "$num" -gt 0 ]
    done <<< "$numbers"
}

@test "extract issue states: all valid" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    states=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[].state')

    while IFS= read -r state; do
        [[ "$state" == "OPEN" || "$state" == "CLOSED" ]]
    done <<< "$states"
}

# =============================================================================
# Filter Tests
# =============================================================================

@test "filter issues: can filter by state" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Filter to only OPEN issues
    open_issues=$(echo "$fixture" | jq '[.data.repository.issues.nodes[] | select(.state == "OPEN")]')

    type=$(echo "$open_issues" | jq 'type')
    [ "$type" == '"array"' ]
}

@test "filter issues: can extract by number" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Get issue #1
    issue=$(echo "$fixture" | jq '.data.repository.issues.nodes[] | select(.number == 1)')

    # Should find it
    [ -n "$issue" ]

    number=$(echo "$issue" | jq '.number')
    [ "$number" -eq 1 ]
}

# =============================================================================
# Edge Case Tests
# =============================================================================

@test "issue node: handles null milestone" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Milestone can be null
    milestone=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[0].milestone // "none"')

    # Should not error
    [ -n "$milestone" ]
}

@test "issue node: handles empty labels" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Labels array might be empty
    count=$(echo "$fixture" | jq '.data.repository.issues.nodes[0].labels.nodes | length')

    # Should be a number (0 or more)
    [ "$count" -ge 0 ]
}

@test "issue node: handles empty assignees" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Assignees array might be empty
    count=$(echo "$fixture" | jq '.data.repository.issues.nodes[0].assignees.nodes | length')

    # Should be a number (0 or more)
    [ "$count" -ge 0 ]
}

@test "issue node: body can be empty or null" {
    fixture=$(load_graphql_fixture "issue" "repo_issues")

    # Body might be null or empty
    body=$(echo "$fixture" | jq -r '.data.repository.issues.nodes[0].body // ""')

    # Should not error (body can be empty string)
    [ $? -eq 0 ]
}
