#!/usr/bin/env bats
# Integration tests for milestone domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the milestone functions
    source_lib "gh-milestone-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# list_milestones_rest Tests
# =============================================================================

@test "list_milestones_rest: returns valid JSON array" {
    result=$(list_milestones_rest "test-owner" "test-repo")

    assert_valid_json "$result"

    # Should be an array
    type=$(echo "$result" | jq 'type')
    [ "$type" == '"array"' ]
}

@test "list_milestones_rest: with state filter returns JSON" {
    result=$(list_milestones_rest "test-owner" "test-repo" "open")

    assert_valid_json "$result"
}

@test "list_milestones_rest: handles missing owner" {
    run list_milestones_rest "" "test-repo"

    [ "$status" -ne 0 ]
}

@test "list_milestones_rest: handles missing repo" {
    run list_milestones_rest "test-owner" ""

    [ "$status" -ne 0 ]
}

# =============================================================================
# get_milestone_rest Tests
# =============================================================================

@test "get_milestone_rest: returns valid JSON object" {
    result=$(get_milestone_rest "test-owner" "test-repo" 1)

    assert_valid_json "$result"

    # Should be an object
    type=$(echo "$result" | jq 'type')
    [ "$type" == '"object"' ]
}

@test "get_milestone_rest: includes milestone number" {
    result=$(get_milestone_rest "test-owner" "test-repo" 1)

    number=$(echo "$result" | jq '.number')
    [ "$number" -gt 0 ]
}

@test "get_milestone_rest: includes title" {
    result=$(get_milestone_rest "test-owner" "test-repo" 1)

    title=$(echo "$result" | jq -r '.title')
    [ -n "$title" ]
}

# =============================================================================
# detect_milestone_state Tests
# =============================================================================

@test "detect_milestone_state: returns state string" {
    result=$(detect_milestone_state "test-owner" "test-repo" 1)

    # Should return "open" or "closed"
    [[ "$result" == "open" || "$result" == "closed" ]]
}

# =============================================================================
# get_milestone_progress Tests
# =============================================================================

@test "get_milestone_progress: returns progress percentage" {
    result=$(get_milestone_progress "test-owner" "test-repo" 1)

    # Should return a number 0-100
    [ "$result" -ge 0 ]
    [ "$result" -le 100 ]
}

# =============================================================================
# Format Function Pipeline Tests
# =============================================================================

@test "list_milestones_rest | format_milestones_rest: produces formatted output" {
    result=$(list_milestones_rest "test-owner" "test-repo" | format_milestones_rest)

    assert_valid_json "$result"
}

@test "get_milestone_rest | format_milestone_rest: produces formatted output" {
    result=$(get_milestone_rest "test-owner" "test-repo" 1 | format_milestone_rest)

    assert_valid_json "$result"
}

# =============================================================================
# Mutation Tests (with mock)
# =============================================================================

@test "create_milestone: handles required arguments" {
    run create_milestone "" "test-repo" "Test Milestone"

    [ "$status" -ne 0 ]
}

@test "update_milestone: handles required arguments" {
    run update_milestone "" "test-repo" 1 "Updated Title"

    [ "$status" -ne 0 ]
}

@test "close_milestone: handles required arguments" {
    run close_milestone "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "get_milestone_rest: handles missing arguments" {
    run get_milestone_rest

    [ "$status" -ne 0 ]
}

@test "get_milestone_progress: handles missing arguments" {
    run get_milestone_progress "test-owner" "test-repo"

    [ "$status" -ne 0 ]
}
