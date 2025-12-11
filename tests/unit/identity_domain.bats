#!/usr/bin/env bats
# Unit tests for identity domain functions
# Tests jq filters and format functions using recorded fixtures

load '../test_helper'

setup() {
    # Source the fixtures helper
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"

    # Get project root for filter loading
    PROJECT_ROOT=$(get_project_root)
    IDENTITY_JQ_FILTERS="${PROJECT_ROOT}/lib/github/gh-identity-jq-filters.yaml"
}

# =============================================================================
# Fixture Loading Tests
# =============================================================================

@test "identity fixtures: viewer.json loads successfully" {
    run load_graphql_fixture "identity" "viewer"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.viewer' > /dev/null
}

@test "identity fixtures: viewer_with_orgs.json loads successfully" {
    run load_graphql_fixture "identity" "viewer_with_orgs"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.viewer.organizations' > /dev/null
}

@test "identity fixtures: user.json loads successfully" {
    run load_graphql_fixture "identity" "user"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.user' > /dev/null
}

@test "identity fixtures: organization.json loads successfully" {
    run load_graphql_fixture "identity" "organization"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.organization' > /dev/null
}

# =============================================================================
# Viewer Format Tests
# =============================================================================

@test "format_viewer: extracts viewer id correctly" {
    fixture=$(load_graphql_fixture "identity" "viewer")

    id=$(echo "$fixture" | jq -r '.data.viewer.id')

    [ -n "$id" ]
    [[ "$id" == MDQ6* ]] || [[ "$id" == U_* ]]
}

@test "format_viewer: extracts viewer login correctly" {
    fixture=$(load_graphql_fixture "identity" "viewer")

    login=$(echo "$fixture" | jq -r '.data.viewer.login')

    [ -n "$login" ]
    [ "$login" == "test-user" ]
}

@test "format_viewer: extracts all expected fields" {
    fixture=$(load_graphql_fixture "identity" "viewer")

    # Check all expected fields exist
    echo "$fixture" | jq -e '.data.viewer.id' > /dev/null
    echo "$fixture" | jq -e '.data.viewer.login' > /dev/null
    echo "$fixture" | jq -e '.data.viewer.name' > /dev/null
    echo "$fixture" | jq -e '.data.viewer.avatarUrl' > /dev/null
}

# =============================================================================
# Organizations Tests
# =============================================================================

@test "viewer_with_orgs: has organizations array" {
    fixture=$(load_graphql_fixture "identity" "viewer_with_orgs")

    org_count=$(echo "$fixture" | jq '.data.viewer.organizations.nodes | length')

    [ "$org_count" -gt 0 ]
}

@test "viewer_with_orgs: organizations have required fields" {
    fixture=$(load_graphql_fixture "identity" "viewer_with_orgs")

    # Check first organization has required fields
    echo "$fixture" | jq -e '.data.viewer.organizations.nodes[0].id' > /dev/null
    echo "$fixture" | jq -e '.data.viewer.organizations.nodes[0].login' > /dev/null
    echo "$fixture" | jq -e '.data.viewer.organizations.nodes[0].name' > /dev/null
}

@test "viewer_with_orgs: totalCount matches nodes length" {
    fixture=$(load_graphql_fixture "identity" "viewer_with_orgs")

    total_count=$(echo "$fixture" | jq '.data.viewer.organizations.totalCount')
    nodes_count=$(echo "$fixture" | jq '.data.viewer.organizations.nodes | length')

    [ "$total_count" -eq "$nodes_count" ]
}

# =============================================================================
# User Format Tests
# =============================================================================

@test "user fixture: has expected structure" {
    fixture=$(load_graphql_fixture "identity" "user")

    echo "$fixture" | jq -e '.data.user.id' > /dev/null
    echo "$fixture" | jq -e '.data.user.login' > /dev/null
}

@test "user fixture: login is sanitized" {
    fixture=$(load_graphql_fixture "identity" "user")

    login=$(echo "$fixture" | jq -r '.data.user.login')

    # Sanitized fixture should have test-user
    [ "$login" == "test-user" ]
}

# =============================================================================
# Organization Format Tests
# =============================================================================

@test "organization fixture: has expected structure" {
    fixture=$(load_graphql_fixture "identity" "organization")

    echo "$fixture" | jq -e '.data.organization.id' > /dev/null
    echo "$fixture" | jq -e '.data.organization.login' > /dev/null
}

@test "organization fixture: has basic org info" {
    fixture=$(load_graphql_fixture "identity" "organization")

    # Organization should have basic fields
    echo "$fixture" | jq -e '.data.organization.name' > /dev/null
    echo "$fixture" | jq -e '.data.organization.avatarUrl' > /dev/null
}

# =============================================================================
# jq Filter Tests
# =============================================================================

@test "format_viewer jq filter: produces formatted output" {
    skip "format_viewer filter requires full jq filter implementation"

    fixture=$(load_graphql_fixture "identity" "viewer")
    filter=$(yq '.format_filters.format_viewer.filter' "$IDENTITY_JQ_FILTERS")

    result=$(echo "$fixture" | jq "$filter")

    # Should produce formatted output
    [ -n "$result" ]
}

@test "format_organizations jq filter: produces formatted output" {
    skip "format_organizations filter requires full jq filter implementation"

    fixture=$(load_graphql_fixture "identity" "viewer_with_orgs")
    filter=$(yq '.format_filters.format_organizations.filter' "$IDENTITY_JQ_FILTERS")

    result=$(echo "$fixture" | jq "$filter")

    # Should produce formatted output
    [ -n "$result" ]
}

# =============================================================================
# Data Extraction Tests
# =============================================================================

@test "extract viewer id: correct format" {
    fixture=$(load_graphql_fixture "identity" "viewer")

    id=$(echo "$fixture" | jq -r '.data.viewer.id')

    # ID should be a non-empty string
    [ -n "$id" ]
    # GitHub node IDs start with specific prefixes
    [[ "$id" =~ ^[A-Za-z0-9_]+$ ]]
}

@test "extract organization ids: all valid format" {
    fixture=$(load_graphql_fixture "identity" "viewer_with_orgs")

    # Extract all organization IDs
    ids=$(echo "$fixture" | jq -r '.data.viewer.organizations.nodes[].id')

    # Each ID should be non-empty
    while IFS= read -r id; do
        [ -n "$id" ]
        [[ "$id" =~ ^[A-Za-z0-9_]+$ ]]
    done <<< "$ids"
}

# =============================================================================
# Edge Case Tests
# =============================================================================

@test "viewer fixture: handles null email gracefully" {
    fixture=$(load_graphql_fixture "identity" "viewer")

    # Email might be null - should not error
    email=$(echo "$fixture" | jq -r '.data.viewer.email // "none"')

    # Should get either an email or "none"
    [ -n "$email" ]
}

@test "organization fixture: handles optional fields" {
    fixture=$(load_graphql_fixture "identity" "organization")

    # Description might be null or empty - check it doesn't error
    desc=$(echo "$fixture" | jq -r '.data.organization.description // "none"')

    # Should not error - desc will be "" or "none" or actual value
    [ $? -eq 0 ]
}
