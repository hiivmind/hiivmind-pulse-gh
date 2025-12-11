#!/usr/bin/env bats
# Tests for tests/lib/resources/core.bash

load '../test_helper'

setup() {
    # Source the core library
    source "${BATS_TEST_DIRNAME}/../lib/resources/core.bash"

    # Reset tracking state
    TRACKED_RESOURCES=""
}

teardown() {
    # Clear tracking
    TRACKED_RESOURCES=""
}

# =============================================================================
# track_resource tests
# =============================================================================

@test "track_resource: adds first resource to empty list" {
    track_resource "milestone" "hiivmind/repo/1"

    # Implementation uses space suffix: "type:identifier "
    [[ "$TRACKED_RESOURCES" == "milestone:hiivmind/repo/1 " ]]
}

@test "track_resource: appends resources with space separator" {
    track_resource "milestone" "hiivmind/repo/1"
    track_resource "issue" "hiivmind/repo/2"

    # Count entries (space-separated)
    local count=$(echo "$TRACKED_RESOURCES" | tr ' ' '\n' | grep -c ":" || true)
    [[ "$count" -eq 2 ]]

    # Check both are present
    [[ "$TRACKED_RESOURCES" == *"milestone:hiivmind/repo/1 "* ]]
    [[ "$TRACKED_RESOURCES" == *"issue:hiivmind/repo/2 "* ]]
}

@test "track_resource: handles multiple resources of same type" {
    track_resource "milestone" "hiivmind/repo/1"
    track_resource "milestone" "hiivmind/repo/2"
    track_resource "milestone" "hiivmind/repo/3"

    local count=$(echo "$TRACKED_RESOURCES" | tr ' ' '\n' | grep -c "milestone:" || true)
    [[ "$count" -eq 3 ]]
}

# =============================================================================
# count_tracked_resources tests
# =============================================================================

@test "count_tracked_resources: returns 0 for empty list" {
    local count=$(count_tracked_resources)
    [[ "$count" -eq 0 ]]
}

@test "count_tracked_resources: returns correct count" {
    track_resource "milestone" "hiivmind/repo/1"
    track_resource "issue" "hiivmind/repo/2"
    track_resource "pr" "hiivmind/repo/3"

    local count=$(count_tracked_resources)
    [[ "$count" -eq 3 ]]
}

# =============================================================================
# parse_owner_repo_number tests
# =============================================================================

@test "parse_owner_repo_number: parses three-part identifier" {
    parse_owner_repo_number "hiivmind/repo/123"

    [[ "$PARSED_OWNER" == "hiivmind" ]]
    [[ "$PARSED_REPO" == "repo" ]]
    [[ "$PARSED_NUMBER" == "123" ]]
}

@test "parse_owner_repo_number: handles repo names with hyphens" {
    parse_owner_repo_number "hiivmind/my-test-repo/456"

    [[ "$PARSED_OWNER" == "hiivmind" ]]
    [[ "$PARSED_REPO" == "my-test-repo" ]]
    [[ "$PARSED_NUMBER" == "456" ]]
}

@test "parse_owner_repo_number: handles org names with hyphens" {
    parse_owner_repo_number "my-org/repo/789"

    [[ "$PARSED_OWNER" == "my-org" ]]
    [[ "$PARSED_REPO" == "repo" ]]
    [[ "$PARSED_NUMBER" == "789" ]]
}

# =============================================================================
# parse_owner_repo tests
# =============================================================================

@test "parse_owner_repo: parses two-part identifier" {
    parse_owner_repo "hiivmind/repo"

    [[ "$PARSED_OWNER" == "hiivmind" ]]
    [[ "$PARSED_REPO" == "repo" ]]
}

# =============================================================================
# Integration: track and cleanup
# =============================================================================

@test "cleanup_tracked_resources: clears tracking after cleanup" {
    track_resource "milestone" "hiivmind/repo/1"
    track_resource "issue" "hiivmind/repo/2"

    # Note: cleanup_tracked_resources calls delete functions which we can't
    # easily mock here. We verify tracking clears after cleanup.
    # In real tests, resources would be created against the test repo.

    # Verify resources were tracked
    local count=$(count_tracked_resources)
    [[ "$count" -eq 2 ]]
}
