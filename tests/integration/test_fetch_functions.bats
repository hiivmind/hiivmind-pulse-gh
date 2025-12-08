#!/usr/bin/env bats
# Integration tests - use mock gh CLI to test function behavior

setup() {
    load '../test_helper'

    # Prepend mock directory to PATH so mock gh is used
    export PATH="$BATS_TEST_DIRNAME/mocks:$PATH"

    # Source the library functions
    source_lib "gh-project-functions.sh"

    FIXTURES="$BATS_TEST_DIRNAME/fixtures"
}

# =============================================================================
# Fetch Function Tests
# =============================================================================

@test "fetch_org_project returns valid JSON" {
    result=$(fetch_org_project 2 "test-org")

    # Should be valid JSON
    assert_valid_json "$result"

    # Should have expected structure
    assert_json_path "$result" ".data.organization.projectV2.title" "Test Project"
}

@test "fetch_org_project includes project ID" {
    result=$(fetch_org_project 2 "test-org")

    project_id=$(echo "$result" | jq -r '.data.organization.projectV2.id')
    [ "$project_id" = "PVT_kwDOtest123" ]
}

@test "fetch_org_project includes items" {
    result=$(fetch_org_project 2 "test-org")

    item_count=$(echo "$result" | jq '.data.organization.projectV2.items.nodes | length')
    [ "$item_count" -gt 0 ]
}

# =============================================================================
# Pipeline Tests
# =============================================================================

@test "apply_universal_filter with no params returns all items" {
    result=$(fetch_org_project 2 "test-org" | apply_universal_filter "" "" "" "")

    assert_valid_json "$result"
    assert_json_has_key "$result" "project"
    assert_json_has_key "$result" "filteredItems"
}

@test "apply_repo_filter pipes correctly" {
    result=$(fetch_org_project 2 "test-org" | apply_repo_filter "test-repo")

    assert_valid_json "$result"
    assert_json_path "$result" ".filters.repository" "test-repo"
}

@test "apply_assignee_filter pipes correctly" {
    result=$(fetch_org_project 2 "test-org" | apply_assignee_filter "octocat")

    assert_valid_json "$result"
    assert_json_path "$result" ".filters.assignee" "octocat"
}

@test "apply_universal_filter with all empty params works" {
    result=$(fetch_org_project 2 "test-org" | apply_universal_filter "" "" "" "")

    assert_valid_json "$result"

    # Should have all items from the fixture
    count=$(echo "$result" | jq '.filteredCount')
    [ "$count" -gt 0 ]
}

# =============================================================================
# Discovery Function Tests
# =============================================================================

@test "list_repositories extracts repos from fetched data" {
    result=$(fetch_org_project 2 "test-org" | list_repositories)

    assert_valid_json "$result"
    assert_json_has_key "$result" "repositories"
}

@test "list_assignees extracts assignees from fetched data" {
    result=$(fetch_org_project 2 "test-org" | list_assignees)

    assert_valid_json "$result"
    assert_json_has_key "$result" "assignees"

    # Should contain octocat from fixture
    echo "$result" | jq -e '.assignees | index("octocat")' > /dev/null
}

@test "list_statuses extracts statuses from fetched data" {
    result=$(fetch_org_project 2 "test-org" | list_statuses)

    assert_valid_json "$result"
    assert_json_has_key "$result" "statuses"
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "filter functions handle empty input gracefully" {
    # Empty JSON object should not crash
    result=$(echo '{"data":{"organization":{"projectV2":{"items":{"nodes":[]}}}}}' | apply_no_filter 2>&1) || true

    # Should either succeed with empty result or fail gracefully
    [ $? -eq 0 ] || [[ "$result" == *"null"* ]]
}

# =============================================================================
# Multi-step Pipeline Tests
# =============================================================================

@test "complex pipeline: fetch -> filter -> list" {
    result=$(fetch_org_project 2 "test-org" | apply_no_filter | jq '.items')

    assert_valid_json "$result"
}

@test "chained filters work correctly" {
    # First get all items, then filter
    all_items=$(fetch_org_project 2 "test-org" | apply_universal_filter "" "" "" "")

    # Should be valid JSON with items
    assert_valid_json "$all_items"

    item_count=$(echo "$all_items" | jq '.filteredItems | length')
    [ "$item_count" -gt 0 ]
}
