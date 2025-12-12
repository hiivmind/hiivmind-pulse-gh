#!/usr/bin/env bats
# Integration tests for repository domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the repository functions
    source_lib "gh-repo-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# get_repo_id Tests
# =============================================================================

@test "get_repo_id: returns repo ID from GraphQL response" {
    result=$(get_repo_id "test-owner" "test-repo")

    # Should return a non-empty ID
    [ -n "$result" ]

    # Repository IDs start with R_
    [[ "$result" == R_* ]]
}

@test "get_repo_id: handles missing owner argument" {
    run get_repo_id "" "test-repo"

    [ "$status" -ne 0 ]
}

@test "get_repo_id: handles missing repo argument" {
    run get_repo_id "test-owner" ""

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_repo Tests
# =============================================================================

@test "fetch_repo: returns valid JSON" {
    result=$(fetch_repo "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "fetch_repo: contains repository data" {
    result=$(fetch_repo "test-owner" "test-repo")

    echo "$result" | jq -e '.data.repository' > /dev/null
}

@test "fetch_repo: includes name" {
    result=$(fetch_repo "test-owner" "test-repo")

    name=$(echo "$result" | jq -r '.data.repository.name')
    [ -n "$name" ]
}

@test "fetch_repo: includes id" {
    result=$(fetch_repo "test-owner" "test-repo")

    id=$(echo "$result" | jq -r '.data.repository.id')
    [ -n "$id" ]
}

@test "fetch_repo: includes defaultBranchRef" {
    result=$(fetch_repo "test-owner" "test-repo")

    echo "$result" | jq -e '.data.repository.defaultBranchRef' > /dev/null
}

# =============================================================================
# discover_org_repos Tests
# =============================================================================

@test "discover_org_repos: returns valid JSON" {
    result=$(discover_org_repos "test-org")

    assert_valid_json "$result"
}

@test "discover_org_repos: handles missing org argument" {
    run discover_org_repos ""

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_default_branch Tests
# =============================================================================

@test "detect_default_branch: returns branch name" {
    result=$(detect_default_branch "test-owner" "test-repo")

    # Should return a branch name like "main" or "master"
    [ -n "$result" ]
    [[ "$result" =~ ^[a-zA-Z0-9_-]+$ ]]
}

# =============================================================================
# detect_repo_visibility Tests
# =============================================================================

@test "detect_repo_visibility: returns visibility status" {
    result=$(detect_repo_visibility "test-owner" "test-repo")

    # Should return "public" or "private"
    [[ "$result" == "public" || "$result" == "private" ]]
}

# =============================================================================
# Format Function Pipeline Tests
# =============================================================================

@test "fetch_repo | format_repo: produces formatted output" {
    result=$(fetch_repo "test-owner" "test-repo" | format_repo)

    # Should produce some output
    [ -n "$result" ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "fetch_repo: handles missing arguments" {
    run fetch_repo

    [ "$status" -ne 0 ]
}

@test "discover_org_repos: handles missing arguments" {
    run discover_org_repos

    [ "$status" -ne 0 ]
}
