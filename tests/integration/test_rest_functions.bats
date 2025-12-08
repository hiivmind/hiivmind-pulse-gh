#!/usr/bin/env bats
# Integration tests for REST API functions

setup() {
    load '../test_helper'

    # Prepend mock directory to PATH
    export PATH="$BATS_TEST_DIRNAME/mocks:$PATH"

    # Source the REST library functions
    source_lib "gh-rest-functions.sh"

    FIXTURES="$BATS_TEST_DIRNAME/fixtures"
}

# =============================================================================
# Milestone REST Functions
# =============================================================================

@test "list_milestones returns valid JSON array" {
    result=$(list_milestones "test-org" "test-repo")

    assert_valid_json "$result"

    # Should be an array
    type=$(echo "$result" | jq 'type')
    [ "$type" = '"array"' ]
}

@test "list_milestones contains expected milestone data" {
    result=$(list_milestones "test-org" "test-repo")

    # Should have 3 milestones
    count=$(echo "$result" | jq 'length')
    [ "$count" -eq 3 ]

    # First milestone should be v1.0.0
    title=$(echo "$result" | jq -r '.[0].title')
    [ "$title" = "v1.0.0" ]
}

@test "list_milestones includes all expected fields" {
    result=$(list_milestones "test-org" "test-repo")

    # Check first milestone has required fields
    echo "$result" | jq -e '.[0] | has("id") and has("number") and has("title") and has("state")' > /dev/null
}

@test "format_milestones formats output correctly" {
    result=$(list_milestones "test-org" "test-repo" | format_milestones)

    assert_valid_json "$result"

    # Should have progress calculated
    echo "$result" | jq -e '.[0] | has("progress")' > /dev/null
}

# =============================================================================
# Branch REST Functions
# =============================================================================

@test "list_branches returns valid JSON array" {
    result=$(list_branches "test-org" "test-repo")

    assert_valid_json "$result"

    # Should be an array
    type=$(echo "$result" | jq 'type')
    [ "$type" = '"array"' ]
}

@test "list_branches contains expected branch data" {
    result=$(list_branches "test-org" "test-repo")

    # Should have 3 branches
    count=$(echo "$result" | jq 'length')
    [ "$count" -eq 3 ]

    # Should include main branch
    echo "$result" | jq -e '.[] | select(.name == "main")' > /dev/null
}

@test "list_branches shows protection status" {
    result=$(list_branches "test-org" "test-repo")

    # main should be protected
    main_protected=$(echo "$result" | jq '.[] | select(.name == "main") | .protected')
    [ "$main_protected" = "true" ]

    # feature branch should not be protected
    feature_protected=$(echo "$result" | jq '.[] | select(.name == "feature/new-feature") | .protected')
    [ "$feature_protected" = "false" ]
}

# =============================================================================
# Auth Check Functions
# =============================================================================

@test "gh_auth_status returns user info" {
    result=$(gh auth status 2>&1)

    # Should contain logged in message
    [[ "$result" == *"Logged in"* ]]
}

# =============================================================================
# Pipeline Tests
# =============================================================================

@test "milestones can be piped to jq filters" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".milestone_filters.list_milestones_rest.filter")

    result=$(list_milestones "test-org" "test-repo" | jq "$filter")

    assert_valid_json "$result"

    # Formatted result should have progress field
    echo "$result" | jq -e '.[0] | has("progress")' > /dev/null
}

@test "open milestones can be filtered" {
    result=$(list_milestones "test-org" "test-repo" | jq '[.[] | select(.state == "open")]')

    assert_valid_json "$result"

    # Should have 2 open milestones (v1.0.0 and v1.1.0)
    count=$(echo "$result" | jq 'length')
    [ "$count" -eq 2 ]
}

@test "closed milestones can be filtered" {
    result=$(list_milestones "test-org" "test-repo" | jq '[.[] | select(.state == "closed")]')

    assert_valid_json "$result"

    # Should have 1 closed milestone (v0.9.0)
    count=$(echo "$result" | jq 'length')
    [ "$count" -eq 1 ]
}
