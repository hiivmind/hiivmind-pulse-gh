#!/usr/bin/env bats
# Integration tests for identity domain functions
# Uses mock gh CLI to test function behavior

load '../test_helper'

setup() {
    # Source bats helpers
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"
    source "${BATS_TEST_DIRNAME}/../bats-helpers/mocks.bash"

    # Setup mock gh CLI
    setup_mock_gh

    # Source the identity functions
    source_lib "gh-identity-functions.sh"
}

teardown() {
    teardown_mock_gh
}

# =============================================================================
# get_viewer_id Tests
# =============================================================================

@test "get_viewer_id: returns viewer ID from GraphQL response" {
    result=$(get_viewer_id)

    # Should return a non-empty ID
    [ -n "$result" ]

    # Should look like a GitHub node ID
    [[ "$result" =~ ^[A-Za-z0-9_]+$ ]]
}

# =============================================================================
# fetch_viewer Tests
# =============================================================================

@test "fetch_viewer: returns valid JSON" {
    result=$(fetch_viewer)

    assert_valid_json "$result"
}

@test "fetch_viewer: contains viewer data" {
    result=$(fetch_viewer)

    # Should have viewer object
    echo "$result" | jq -e '.data.viewer' > /dev/null
}

@test "fetch_viewer: includes login" {
    result=$(fetch_viewer)

    login=$(echo "$result" | jq -r '.data.viewer.login')
    [ -n "$login" ]
}

@test "fetch_viewer: includes id" {
    result=$(fetch_viewer)

    id=$(echo "$result" | jq -r '.data.viewer.id')
    [ -n "$id" ]
}

# =============================================================================
# fetch_user Tests
# =============================================================================

@test "fetch_user: returns valid JSON for valid user" {
    result=$(fetch_user "test-user")

    assert_valid_json "$result"
}

@test "fetch_user: contains user data" {
    result=$(fetch_user "test-user")

    echo "$result" | jq -e '.data.user' > /dev/null
}

@test "fetch_user: returns error without login argument" {
    run fetch_user ""

    [ "$status" -ne 0 ]
}

# =============================================================================
# fetch_organization Tests
# =============================================================================

@test "fetch_organization: returns valid JSON for valid org" {
    result=$(fetch_organization "test-org")

    assert_valid_json "$result"
}

@test "fetch_organization: contains organization data" {
    result=$(fetch_organization "test-org")

    echo "$result" | jq -e '.data.organization' > /dev/null
}

@test "fetch_organization: returns error without org argument" {
    run fetch_organization ""

    [ "$status" -ne 0 ]
}

# =============================================================================
# discover_viewer_organizations Tests
# =============================================================================

@test "discover_viewer_organizations: returns valid JSON" {
    result=$(discover_viewer_organizations)

    assert_valid_json "$result"
}

@test "discover_viewer_organizations: contains organizations array" {
    result=$(discover_viewer_organizations)

    echo "$result" | jq -e '.data.viewer.organizations' > /dev/null
}

# =============================================================================
# Format Function Pipeline Tests
# =============================================================================

@test "fetch_viewer | format_viewer: produces formatted output" {
    result=$(fetch_viewer | format_viewer)

    # Should produce some output
    [ -n "$result" ]
}

@test "discover_viewer_organizations | format_organizations: produces formatted output" {
    result=$(discover_viewer_organizations | format_organizations)

    # Should produce some output
    [ -n "$result" ]
}

# =============================================================================
# Auth Check Functions Tests
# =============================================================================

@test "check_gh_cli: returns success when gh is installed" {
    run check_gh_cli

    [ "$status" -eq 0 ]
}

@test "check_jq: returns success when jq is installed" {
    run check_jq

    [ "$status" -eq 0 ]
}

@test "check_yq: returns success when yq is installed" {
    run check_yq

    [ "$status" -eq 0 ]
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "get_user_id: handles missing argument" {
    run get_user_id

    [ "$status" -ne 0 ]
    [[ "$output" == *"ERROR"* ]] || [[ "$output" == *"requires"* ]]
}

@test "get_org_id: handles missing argument" {
    run get_org_id

    [ "$status" -ne 0 ]
    [[ "$output" == *"ERROR"* ]] || [[ "$output" == *"requires"* ]]
}
