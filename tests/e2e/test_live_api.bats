#!/usr/bin/env bats
# E2E tests - run against real GitHub API
# These tests require:
#   - GITHUB_TOKEN: Personal access token with appropriate scopes
#   - TEST_ORG: Organization name to test against
#   - TEST_PROJECT_NUMBER: Project number in the org to test
#   - TEST_REPO: Repository name for milestone/branch tests
#
# Run locally: TEST_ORG=myorg TEST_PROJECT_NUMBER=1 TEST_REPO=myrepo bats tests/e2e/
# In CI: Only runs on main branch pushes with secrets configured

setup() {
    load '../test_helper'

    # Skip if required environment variables are not set
    if [ -z "$GITHUB_TOKEN" ] && [ -z "$GH_TOKEN" ]; then
        skip "E2E tests require GITHUB_TOKEN or GH_TOKEN"
    fi

    if [ -z "$TEST_ORG" ]; then
        skip "E2E tests require TEST_ORG environment variable"
    fi

    # Source the library functions (use real gh, not mock)
    source_lib "gh-project-functions.sh"
    source_lib "gh-rest-functions.sh"
}

# =============================================================================
# Authentication Tests
# =============================================================================

@test "gh is authenticated" {
    run gh auth status

    # Should succeed
    [ "$status" -eq 0 ]

    # Should show logged in
    [[ "$output" == *"Logged in"* ]]
}

# =============================================================================
# Project Fetch Tests
# =============================================================================

@test "fetch real project from test org" {
    if [ -z "$TEST_PROJECT_NUMBER" ]; then
        skip "Requires TEST_PROJECT_NUMBER"
    fi

    result=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG")

    # Should succeed and return valid JSON
    [ $? -eq 0 ]
    assert_valid_json "$result"

    # Should have project ID
    project_id=$(echo "$result" | jq -r '.data.organization.projectV2.id')
    [ -n "$project_id" ]
    [ "$project_id" != "null" ]
}

@test "fetch project and apply no_filter" {
    if [ -z "$TEST_PROJECT_NUMBER" ]; then
        skip "Requires TEST_PROJECT_NUMBER"
    fi

    result=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG" | apply_no_filter)

    assert_valid_json "$result"
    assert_json_has_key "$result" "project"
    assert_json_has_key "$result" "items"
}

@test "list_repositories returns repos from real project" {
    if [ -z "$TEST_PROJECT_NUMBER" ]; then
        skip "Requires TEST_PROJECT_NUMBER"
    fi

    result=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG" | list_repositories)

    assert_valid_json "$result"
    assert_json_has_key "$result" "repositories"
}

@test "list_assignees returns users from real project" {
    if [ -z "$TEST_PROJECT_NUMBER" ]; then
        skip "Requires TEST_PROJECT_NUMBER"
    fi

    result=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG" | list_assignees)

    assert_valid_json "$result"
    assert_json_has_key "$result" "assignees"
}

@test "list_statuses returns status values from real project" {
    if [ -z "$TEST_PROJECT_NUMBER" ]; then
        skip "Requires TEST_PROJECT_NUMBER"
    fi

    result=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG" | list_statuses)

    assert_valid_json "$result"
    assert_json_has_key "$result" "statuses"
}

# =============================================================================
# Milestone Tests
# =============================================================================

@test "list real milestones from test repo" {
    if [ -z "$TEST_REPO" ]; then
        skip "Requires TEST_REPO"
    fi

    result=$(list_milestones "$TEST_ORG" "$TEST_REPO")

    # Should succeed
    [ $? -eq 0 ]
    assert_valid_json "$result"

    # Should be an array
    type=$(echo "$result" | jq 'type')
    [ "$type" = '"array"' ]
}

@test "milestones have expected structure" {
    if [ -z "$TEST_REPO" ]; then
        skip "Requires TEST_REPO"
    fi

    result=$(list_milestones "$TEST_ORG" "$TEST_REPO")

    # If there are milestones, check structure
    count=$(echo "$result" | jq 'length')
    if [ "$count" -gt 0 ]; then
        echo "$result" | jq -e '.[0] | has("number") and has("title") and has("state")' > /dev/null
    fi
}

# =============================================================================
# Branch Tests
# =============================================================================

@test "list real branches from test repo" {
    if [ -z "$TEST_REPO" ]; then
        skip "Requires TEST_REPO"
    fi

    result=$(list_branches "$TEST_ORG" "$TEST_REPO")

    [ $? -eq 0 ]
    assert_valid_json "$result"

    # Should have at least main/master branch
    count=$(echo "$result" | jq 'length')
    [ "$count" -gt 0 ]
}

# =============================================================================
# User Project Tests
# =============================================================================

@test "fetch user projects" {
    result=$(fetch_user_projects)

    [ $? -eq 0 ]
    assert_valid_json "$result"

    # Should have viewer data
    echo "$result" | jq -e '.data.viewer' > /dev/null
}

# =============================================================================
# Discovery Tests
# =============================================================================

@test "discover all accessible projects" {
    result=$(discover_all_projects 2>/dev/null) || result=""

    # This may or may not have projects, but should be valid JSON if it returns
    if [ -n "$result" ]; then
        assert_valid_json "$result"
    fi
}

# =============================================================================
# Write Operation Tests (use with caution)
# =============================================================================

# These tests modify data - uncomment only if you have a dedicated test project

# @test "create and archive draft issue" {
#     if [ -z "$TEST_PROJECT_NUMBER" ]; then
#         skip "Requires TEST_PROJECT_NUMBER"
#     fi
#
#     # Get project ID
#     project_id=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG" | \
#         jq -r '.data.organization.projectV2.id')
#
#     [ -n "$project_id" ]
#     [ "$project_id" != "null" ]
#
#     # Create draft issue
#     result=$(create_draft_issue "$project_id" "BATS E2E Test Item" "Automated test - safe to delete")
#
#     assert_valid_json "$result"
#
#     item_id=$(echo "$result" | jq -r '.data.addProjectV2DraftIssue.projectItem.id')
#     [ -n "$item_id" ]
#     [ "$item_id" != "null" ]
#
#     # Clean up - archive the item
#     archive_result=$(archive_item "$project_id" "$item_id")
#     [ $? -eq 0 ]
# }
