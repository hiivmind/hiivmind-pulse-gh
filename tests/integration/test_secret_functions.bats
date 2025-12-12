#!/usr/bin/env bats
# Integration tests for secret domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the secret functions
    source_lib "gh-secret-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# discover_repo_secrets Tests
# =============================================================================

@test "discover_repo_secrets: returns valid JSON" {
    result=$(discover_repo_secrets "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "discover_repo_secrets: handles missing arguments" {
    run discover_repo_secrets "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_repo_public_key Tests
# =============================================================================

@test "fetch_repo_public_key: returns valid JSON" {
    result=$(fetch_repo_public_key "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "fetch_repo_public_key: handles missing arguments" {
    run fetch_repo_public_key "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_secret_exists Tests
# =============================================================================

@test "detect_secret_exists: returns boolean" {
    result=$(detect_secret_exists "test-owner" "test-repo" "TEST_SECRET")

    # Should return "true" or "false"
    [[ "$result" == "true" || "$result" == "false" ]]
}

# =============================================================================
# Mutation Tests (argument validation)
# =============================================================================

@test "set_repo_secret: handles missing arguments" {
    run set_repo_secret "" "test-repo" "SECRET" "value"

    [ "$status" -ne 0 ]
}

@test "delete_repo_secret: handles missing arguments" {
    run delete_repo_secret "" "test-repo" "SECRET"

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "discover_repo_secrets: handles missing repo" {
    run discover_repo_secrets "test-owner" ""

    [ "$status" -ne 0 ]
}

@test "fetch_repo_public_key: handles missing repo" {
    run fetch_repo_public_key "test-owner" ""

    [ "$status" -ne 0 ]
}
