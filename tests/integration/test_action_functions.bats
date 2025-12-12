#!/usr/bin/env bats
# Integration tests for action domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the action functions
    source_lib "gh-action-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# discover_repo_workflows Tests
# =============================================================================

@test "discover_repo_workflows: returns valid JSON" {
    result=$(discover_repo_workflows "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "discover_repo_workflows: handles missing arguments" {
    run discover_repo_workflows "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# discover_repo_runs Tests
# =============================================================================

@test "discover_repo_runs: returns valid JSON" {
    result=$(discover_repo_runs "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "discover_repo_runs: handles missing arguments" {
    run discover_repo_runs "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_workflow Tests
# =============================================================================

@test "fetch_workflow: returns valid JSON" {
    result=$(fetch_workflow "test-owner" "test-repo" 1)

    assert_valid_json "$result"
}

@test "fetch_workflow: handles missing arguments" {
    run fetch_workflow "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_run Tests
# =============================================================================

@test "fetch_run: returns valid JSON" {
    result=$(fetch_run "test-owner" "test-repo" 1)

    assert_valid_json "$result"
}

@test "fetch_run: handles missing arguments" {
    run fetch_run "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_workflow_state Tests
# =============================================================================

@test "detect_workflow_state: returns state string" {
    result=$(detect_workflow_state "test-owner" "test-repo" 1)

    # Should return "active" or "disabled"
    [[ "$result" == "active" || "$result" == "disabled" || "$result" == "disabled_manually" ]]
}

# =============================================================================
# detect_run_status Tests
# =============================================================================

@test "detect_run_status: returns status string" {
    result=$(detect_run_status "test-owner" "test-repo" 1)

    # Should return a valid status
    [[ "$result" == "queued" || "$result" == "in_progress" || "$result" == "completed" || "$result" == "waiting" ]]
}

# =============================================================================
# Mutation Tests (argument validation)
# =============================================================================

@test "trigger_workflow: handles missing arguments" {
    run trigger_workflow "" "test-repo" 1

    [ "$status" -ne 0 ]
}

@test "cancel_run: handles missing arguments" {
    run cancel_run "" "test-repo" 1

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "fetch_workflow: handles missing repo" {
    run fetch_workflow "test-owner" "" 1

    [ "$status" -ne 0 ]
}

@test "fetch_run: handles missing run_id" {
    run fetch_run "test-owner" "test-repo"

    [ "$status" -ne 0 ]
}
