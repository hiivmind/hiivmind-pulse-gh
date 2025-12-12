#!/usr/bin/env bats
# Integration tests for variable domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the variable functions
    source_lib "gh-variable-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# discover_repo_variables Tests
# =============================================================================

@test "discover_repo_variables: returns valid JSON" {
    result=$(discover_repo_variables "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "discover_repo_variables: handles missing arguments" {
    run discover_repo_variables "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_repo_variable Tests
# =============================================================================

@test "fetch_repo_variable: returns valid JSON" {
    result=$(fetch_repo_variable "test-owner" "test-repo" "TEST_VAR")

    assert_valid_json "$result"
}

@test "fetch_repo_variable: handles missing arguments" {
    run fetch_repo_variable "" "test-repo" "TEST_VAR"

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_repo_variable_exists Tests
# =============================================================================

@test "detect_repo_variable_exists: returns boolean" {
    result=$(detect_repo_variable_exists "test-owner" "test-repo" "TEST_VAR")

    # Should return "true" or "false"
    [[ "$result" == "true" || "$result" == "false" ]]
}

# =============================================================================
# get_variable_value Tests
# =============================================================================

@test "get_variable_value: returns value string" {
    result=$(get_variable_value "test-owner" "test-repo" "TEST_VAR")

    # Should return a string (could be empty)
    [ $? -eq 0 ]
}

# =============================================================================
# Mutation Tests (argument validation)
# =============================================================================

@test "set_repo_variable: handles missing arguments" {
    run set_repo_variable "" "test-repo" "VAR" "value"

    [ "$status" -ne 0 ]
}

@test "delete_repo_variable: handles missing arguments" {
    run delete_repo_variable "" "test-repo" "VAR"

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "discover_repo_variables: handles missing repo" {
    run discover_repo_variables "test-owner" ""

    [ "$status" -ne 0 ]
}

@test "fetch_repo_variable: handles missing variable name" {
    run fetch_repo_variable "test-owner" "test-repo" ""

    [ "$status" -ne 0 ]
}
