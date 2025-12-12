#!/usr/bin/env bats
# Integration tests for pull request domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the PR functions
    source_lib "gh-pr-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# get_pr_id Tests
# =============================================================================

@test "get_pr_id: returns PR ID from GraphQL response" {
    result=$(get_pr_id "test-owner" "test-repo" 1)

    # Should return a non-empty ID
    [ -n "$result" ]
}

@test "get_pr_id: handles missing arguments" {
    run get_pr_id "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_pr Tests
# =============================================================================

@test "fetch_pr: returns valid JSON" {
    result=$(fetch_pr "test-owner" "test-repo" 1)

    assert_valid_json "$result"
}

@test "fetch_pr: handles missing arguments" {
    run fetch_pr "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# discover_repo_prs Tests
# =============================================================================

@test "discover_repo_prs: returns valid JSON" {
    result=$(discover_repo_prs "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "discover_repo_prs: with state filter returns JSON" {
    result=$(discover_repo_prs "test-owner" "test-repo" "OPEN")

    assert_valid_json "$result"
}

@test "discover_repo_prs: contains pullRequests array" {
    result=$(discover_repo_prs "test-owner" "test-repo")

    echo "$result" | jq -e '.data.repository.pullRequests.nodes' > /dev/null
}

@test "discover_repo_prs: handles missing arguments" {
    run discover_repo_prs "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_pr_state Tests
# =============================================================================

@test "detect_pr_state: returns state string" {
    result=$(detect_pr_state "test-owner" "test-repo" 1)

    # Should return "OPEN", "CLOSED", or "MERGED"
    [[ "$result" == "OPEN" || "$result" == "CLOSED" || "$result" == "MERGED" ]]
}

# =============================================================================
# check_pr_is_draft Tests
# =============================================================================

@test "check_pr_is_draft: returns draft status" {
    result=$(check_pr_is_draft "test-owner" "test-repo" 1)

    # Should return "true" or "false"
    [[ "$result" == "true" || "$result" == "false" ]]
}

# =============================================================================
# Filter Function Tests
# =============================================================================

@test "filter_prs_by_state: filters open PRs" {
    prs=$(discover_repo_prs "test-owner" "test-repo")
    result=$(echo "$prs" | filter_prs_by_state "OPEN")

    assert_valid_json "$result"
}

@test "filter_draft_prs: filters draft PRs" {
    prs=$(discover_repo_prs "test-owner" "test-repo")
    result=$(echo "$prs" | filter_draft_prs)

    assert_valid_json "$result"
}

@test "filter_ready_prs: filters ready PRs" {
    prs=$(discover_repo_prs "test-owner" "test-repo")
    result=$(echo "$prs" | filter_ready_prs)

    assert_valid_json "$result"
}

# =============================================================================
# Format Function Pipeline Tests
# =============================================================================

@test "discover_repo_prs | format_prs_list: produces formatted output" {
    result=$(discover_repo_prs "test-owner" "test-repo" | format_prs_list)

    # Should produce some output
    [ -n "$result" ]
}

# =============================================================================
# Mutation Tests (argument validation)
# =============================================================================

@test "set_pr_milestone: handles missing arguments" {
    run set_pr_milestone "" "test-repo" 1 1

    [ "$status" -ne 0 ]
}

@test "request_pr_review: handles missing arguments" {
    run request_pr_review "" "test-repo" 1 "reviewer"

    [ "$status" -ne 0 ]
}

@test "mark_pr_ready: handles missing arguments" {
    run mark_pr_ready "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "fetch_pr: handles missing repo argument" {
    run fetch_pr "test-owner" "" 1

    [ "$status" -ne 0 ]
}

@test "fetch_pr: handles missing number argument" {
    run fetch_pr "test-owner" "test-repo"

    [ "$status" -ne 0 ]
}
