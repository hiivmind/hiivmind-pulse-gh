#!/usr/bin/env bats
# Integration tests for release domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the release functions
    source_lib "gh-release-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# discover_repo_releases Tests
# =============================================================================

@test "discover_repo_releases: returns valid JSON" {
    result=$(discover_repo_releases "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "discover_repo_releases: handles missing arguments" {
    run discover_repo_releases "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_release Tests
# =============================================================================

@test "fetch_release: returns valid JSON" {
    result=$(fetch_release "test-owner" "test-repo" 1)

    assert_valid_json "$result"
}

@test "fetch_release: handles missing arguments" {
    run fetch_release "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_latest_release Tests
# =============================================================================

@test "fetch_latest_release: returns valid JSON" {
    result=$(fetch_latest_release "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "fetch_latest_release: handles missing arguments" {
    run fetch_latest_release "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_release_by_tag Tests
# =============================================================================

@test "fetch_release_by_tag: returns valid JSON" {
    result=$(fetch_release_by_tag "test-owner" "test-repo" "v1.0.0")

    assert_valid_json "$result"
}

@test "fetch_release_by_tag: handles missing arguments" {
    run fetch_release_by_tag "" "test-repo" "v1.0.0"

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_release_exists Tests
# =============================================================================

@test "detect_release_exists: returns boolean" {
    result=$(detect_release_exists "test-owner" "test-repo" "v1.0.0")

    # Should return "true" or "false"
    [[ "$result" == "true" || "$result" == "false" ]]
}

# =============================================================================
# detect_is_prerelease Tests
# =============================================================================

@test "detect_is_prerelease: returns boolean" {
    result=$(detect_is_prerelease "test-owner" "test-repo" 1)

    # Should return "true" or "false"
    [[ "$result" == "true" || "$result" == "false" ]]
}

# =============================================================================
# Mutation Tests (argument validation)
# =============================================================================

@test "create_release: handles missing arguments" {
    run create_release "" "test-repo" "v1.0.0"

    [ "$status" -ne 0 ]
}

@test "delete_release: handles missing arguments" {
    run delete_release "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "fetch_release: handles missing repo" {
    run fetch_release "test-owner" "" 1

    [ "$status" -ne 0 ]
}

@test "fetch_release: handles missing release_id" {
    run fetch_release "test-owner" "test-repo"

    [ "$status" -ne 0 ]
}

@test "fetch_latest_release: handles missing repo" {
    run fetch_latest_release "test-owner" ""

    [ "$status" -ne 0 ]
}
