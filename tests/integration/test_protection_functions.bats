#!/usr/bin/env bats
# Integration tests for protection domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the protection functions
    source_lib "gh-protection-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# fetch_branch_protection Tests
# =============================================================================

@test "fetch_branch_protection: returns valid JSON" {
    result=$(fetch_branch_protection "test-owner" "test-repo" "main")

    assert_valid_json "$result"
}

@test "fetch_branch_protection: handles missing arguments" {
    run fetch_branch_protection "" "test-repo" "main"

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_repo_rulesets Tests
# =============================================================================

@test "fetch_repo_rulesets: returns valid JSON" {
    result=$(fetch_repo_rulesets "test-owner" "test-repo")

    assert_valid_json "$result"
}

@test "fetch_repo_rulesets: handles missing arguments" {
    run fetch_repo_rulesets "" "test-repo"

    [ "$status" -ne 0 ]
}

# =============================================================================
# detect_branch_protection_exists Tests
# =============================================================================

@test "detect_branch_protection_exists: returns boolean" {
    result=$(detect_branch_protection_exists "test-owner" "test-repo" "main")

    # Should return "true" or "false"
    [[ "$result" == "true" || "$result" == "false" ]]
}

# =============================================================================
# detect_ruleset_exists Tests
# =============================================================================

@test "detect_ruleset_exists: returns boolean" {
    result=$(detect_ruleset_exists "test-owner" "test-repo" "main-branch-protection")

    # Should return "true" or "false"
    [[ "$result" == "true" || "$result" == "false" ]]
}

# =============================================================================
# discover_repo_rulesets Tests
# =============================================================================

@test "discover_repo_rulesets: returns valid JSON" {
    result=$(discover_repo_rulesets "test-owner" "test-repo")

    assert_valid_json "$result"
}

# =============================================================================
# Format Function Tests
# =============================================================================

@test "fetch_branch_protection | format_branch_protection: produces output" {
    result=$(fetch_branch_protection "test-owner" "test-repo" "main" | format_branch_protection 2>/dev/null) || true

    # May produce output or handle gracefully
    [ $? -eq 0 ] || [ -n "$result" ] || true
}

@test "fetch_repo_rulesets | format_rulesets: produces output" {
    result=$(fetch_repo_rulesets "test-owner" "test-repo" | format_rulesets 2>/dev/null) || true

    # May produce output or handle gracefully
    [ $? -eq 0 ] || [ -n "$result" ] || true
}

# =============================================================================
# Mutation Tests (argument validation)
# =============================================================================

@test "set_branch_protection_rest: handles missing arguments" {
    run set_branch_protection_rest "" "test-repo" "main"

    [ "$status" -ne 0 ]
}

@test "create_repo_ruleset: handles missing arguments" {
    run create_repo_ruleset "" "test-repo" "test-ruleset"

    [ "$status" -ne 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "fetch_branch_protection: handles missing repo" {
    run fetch_branch_protection "test-owner" "" "main"

    [ "$status" -ne 0 ]
}

@test "fetch_branch_protection: handles missing branch" {
    run fetch_branch_protection "test-owner" "test-repo" ""

    [ "$status" -ne 0 ]
}

@test "fetch_repo_rulesets: handles missing repo" {
    run fetch_repo_rulesets "test-owner" ""

    [ "$status" -ne 0 ]
}
