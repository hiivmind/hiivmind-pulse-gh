#!/usr/bin/env bats
# Integration tests for issue domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the issue functions
    source_lib "gh-issue-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# get_issue_id Tests
# =============================================================================

@test "get_issue_id: returns issue ID from GraphQL response" {
    result=$(get_issue_id "test-owner" "test-repo" 1)

    # Should return a non-empty ID
    [ -n "$result" ]
}

@test "get_issue_id: handles missing arguments" {
    run get_issue_id "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_issue Tests
# =============================================================================

@test "fetch_issue: returns valid JSON" {
    result=$(fetch_issue "test-owner" "test-repo" 1)

    assert_valid_json "$result"
}

@test "fetch_issue: handles missing arguments" {
    run fetch_issue "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# discover_repo_issues Tests
# =============================================================================

@test "discover_repo_issues: returns valid JSON" {
    result=$(discover_repo_issues "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "discover_repo_issues: with state filter returns JSON" {
    result=$(discover_repo_issues "test-owner" "test-repo" "OPEN")

    assert_valid_json "$result"
}

@test "discover_repo_issues: contains issues array" {
    result=$(discover_repo_issues "test-owner" "test-repo")

    echo "$result" | jq -e '.data.repository.issues.nodes' > /dev/null
}

@test "discover_repo_issues: handles missing arguments" {
    run discover_repo_issues "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_issue_state Tests
# =============================================================================

@test "detect_issue_state: returns state string" {
    result=$(detect_issue_state "test-owner" "test-repo" 1)

    # Should return "OPEN" or "CLOSED"
    [[ "$result" == "OPEN" || "$result" == "CLOSED" ]]
}

# =============================================================================
# Filter Function Tests
# =============================================================================

@test "filter_issues_by_state: filters open issues" {
    issues=$(discover_repo_issues "test-owner" "test-repo")
    result=$(echo "$issues" | filter_issues_by_state "OPEN")

    assert_valid_json "$result"
}

@test "filter_issues_by_state: filters closed issues" {
    issues=$(discover_repo_issues "test-owner" "test-repo")
    result=$(echo "$issues" | filter_issues_by_state "CLOSED")

    assert_valid_json "$result"
}

# =============================================================================
# Format Function Pipeline Tests
# =============================================================================

@test "discover_repo_issues | format_issues_list: produces formatted output" {
    result=$(discover_repo_issues "test-owner" "test-repo" | format_issues_list)

    # Should produce some output
    [ -n "$result" ]
}

# =============================================================================
# Mutation Tests (argument validation)
# =============================================================================

@test "set_issue_milestone: handles missing arguments" {
    run set_issue_milestone "" "test-repo" 1 1

    [ "$status" -ne 0 ]
}

@test "add_issue_labels: handles missing arguments" {
    run add_issue_labels "" "test-repo" 1 "bug"

    [ "$status" -ne 0 ]
}

@test "close_issue: handles missing arguments" {
    run close_issue "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "fetch_issue: handles missing repo argument" {
    run fetch_issue "test-owner" "" 1

    [ "$status" -ne 0 ]
}

@test "fetch_issue: handles missing number argument" {
    run fetch_issue "test-owner" "test-repo"

    [ "$status" -ne 0 ]
}
