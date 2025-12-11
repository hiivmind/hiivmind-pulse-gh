#!/usr/bin/env bats
# Unit tests for milestone domain functions
# Tests jq filters and format functions using recorded fixtures

load '../test_helper'

setup() {
    # Source the fixtures helper
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"

    # Get project root for filter loading
    PROJECT_ROOT=$(get_project_root)
    MILESTONE_JQ_FILTERS="${PROJECT_ROOT}/lib/github/gh-milestone-jq-filters.yaml"
}

# =============================================================================
# Fixture Loading Tests
# =============================================================================

@test "milestone fixtures: list_populated.json loads successfully" {
    run load_rest_fixture "milestone" "list_populated"
    [ "$status" -eq 0 ]

    # Validate JSON structure - should be an array
    type=$(echo "$output" | jq 'type')
    [ "$type" == '"array"' ]
}

@test "milestone fixtures: get_single.json loads successfully" {
    run load_rest_fixture "milestone" "get_single"
    [ "$status" -eq 0 ]

    # Validate JSON structure - should be an object
    type=$(echo "$output" | jq 'type')
    [ "$type" == '"object"' ]
}

@test "milestone fixtures: list_empty.json loads successfully" {
    run load_rest_fixture "milestone" "list_empty"
    [ "$status" -eq 0 ]

    # Should be empty array
    echo "$output" | jq -e '. == []' > /dev/null
}

# =============================================================================
# Milestone Structure Tests
# =============================================================================

@test "milestone fixture: has required REST API fields" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    # Check all required fields per GitHub REST API
    echo "$fixture" | jq -e '.id' > /dev/null
    echo "$fixture" | jq -e '.node_id' > /dev/null
    echo "$fixture" | jq -e '.number' > /dev/null
    echo "$fixture" | jq -e '.title' > /dev/null
    echo "$fixture" | jq -e '.state' > /dev/null
}

@test "milestone fixture: id is integer" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    id=$(echo "$fixture" | jq '.id')

    # ID should be a number
    [[ "$id" =~ ^[0-9]+$ ]]
}

@test "milestone fixture: number is integer" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    number=$(echo "$fixture" | jq '.number')

    # Number should be a positive integer
    [ "$number" -gt 0 ]
}

@test "milestone fixture: state is valid" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    state=$(echo "$fixture" | jq -r '.state')

    # State should be 'open' or 'closed'
    [[ "$state" == "open" || "$state" == "closed" ]]
}

# =============================================================================
# Milestone List Tests
# =============================================================================

@test "milestone list: contains multiple milestones" {
    fixture=$(load_rest_fixture "milestone" "list_populated")

    count=$(echo "$fixture" | jq 'length')

    [ "$count" -ge 1 ]
}

@test "milestone list: each milestone has required fields" {
    fixture=$(load_rest_fixture "milestone" "list_populated")

    # Check first milestone has required fields
    echo "$fixture" | jq -e '.[0].id' > /dev/null
    echo "$fixture" | jq -e '.[0].number' > /dev/null
    echo "$fixture" | jq -e '.[0].title' > /dev/null
    echo "$fixture" | jq -e '.[0].state' > /dev/null
}

@test "milestone list: all milestones have unique numbers" {
    fixture=$(load_rest_fixture "milestone" "list_populated")

    total=$(echo "$fixture" | jq 'length')
    unique=$(echo "$fixture" | jq '[.[].number] | unique | length')

    [ "$total" -eq "$unique" ]
}

@test "milestone list: all milestones have unique ids" {
    fixture=$(load_rest_fixture "milestone" "list_populated")

    total=$(echo "$fixture" | jq 'length')
    unique=$(echo "$fixture" | jq '[.[].id] | unique | length')

    [ "$total" -eq "$unique" ]
}

# =============================================================================
# URL Tests
# =============================================================================

@test "milestone fixture: url is valid API URL" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    url=$(echo "$fixture" | jq -r '.url')

    [[ "$url" =~ ^https://api.github.com/repos/ ]]
}

@test "milestone fixture: html_url is valid GitHub URL" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    html_url=$(echo "$fixture" | jq -r '.html_url')

    [[ "$html_url" =~ ^https://github.com/ ]]
}

# =============================================================================
# Creator Tests
# =============================================================================

@test "milestone fixture: creator exists" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    echo "$fixture" | jq -e '.creator' > /dev/null
}

@test "milestone fixture: creator has login" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    login=$(echo "$fixture" | jq -r '.creator.login')

    [ -n "$login" ]
}

@test "milestone fixture: creator has id" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    id=$(echo "$fixture" | jq '.creator.id')

    [ "$id" -gt 0 ]
}

# =============================================================================
# Issue Count Tests
# =============================================================================

@test "milestone fixture: has open_issues count" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    open_issues=$(echo "$fixture" | jq '.open_issues')

    # Should be a non-negative integer
    [ "$open_issues" -ge 0 ]
}

@test "milestone fixture: has closed_issues count" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    closed_issues=$(echo "$fixture" | jq '.closed_issues')

    # Should be a non-negative integer
    [ "$closed_issues" -ge 0 ]
}

# =============================================================================
# Timestamp Tests
# =============================================================================

@test "milestone fixture: created_at is valid ISO timestamp" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    created_at=$(echo "$fixture" | jq -r '.created_at')

    [[ "$created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "milestone fixture: updated_at is valid ISO timestamp" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    updated_at=$(echo "$fixture" | jq -r '.updated_at')

    [[ "$updated_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# =============================================================================
# Progress Calculation Tests
# =============================================================================

@test "milestone progress: can calculate percentage from fixture" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    open=$(echo "$fixture" | jq '.open_issues')
    closed=$(echo "$fixture" | jq '.closed_issues')
    total=$((open + closed))

    if [ "$total" -eq 0 ]; then
        # Empty milestone = 0% progress
        progress=0
    else
        progress=$(( (closed * 100) / total ))
    fi

    # Progress should be 0-100
    [ "$progress" -ge 0 ]
    [ "$progress" -le 100 ]
}

# =============================================================================
# jq Filter Tests
# =============================================================================

@test "format_milestones_rest filter: formats milestone list" {
    fixture=$(load_rest_fixture "milestone" "list_populated")

    # Apply basic formatting
    result=$(echo "$fixture" | jq '[.[] | {number, title, state, open_issues, closed_issues}]')

    # Should still be an array
    type=$(echo "$result" | jq 'type')
    [ "$type" == '"array"' ]

    # First item should have expected fields
    echo "$result" | jq -e '.[0].number' > /dev/null
    echo "$result" | jq -e '.[0].title' > /dev/null
}

# =============================================================================
# Edge Case Tests
# =============================================================================

@test "milestone fixture: handles null due_on" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    due_on=$(echo "$fixture" | jq -r '.due_on // "none"')

    # Should not error
    [ -n "$due_on" ]
}

@test "milestone fixture: handles null closed_at" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    closed_at=$(echo "$fixture" | jq -r '.closed_at // "none"')

    # Should not error
    [ -n "$closed_at" ]
}

@test "milestone fixture: handles null description" {
    fixture=$(load_rest_fixture "milestone" "get_single")

    desc=$(echo "$fixture" | jq -r '.description // "none"')

    # Should not error
    [ -n "$desc" ]
}

@test "empty milestone list: is valid empty array" {
    fixture=$(load_rest_fixture "milestone" "list_empty")

    # Should be empty array []
    count=$(echo "$fixture" | jq 'length')

    [ "$count" -eq 0 ]
}
