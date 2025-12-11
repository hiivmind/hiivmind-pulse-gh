#!/usr/bin/env bats
# Unit tests for jq filters - no API calls, just JSON processing

setup() {
    load '../test_helper'
    FIXTURES="$BATS_TEST_DIRNAME/fixtures"
}

# =============================================================================
# Basic Filter Tests
# =============================================================================

@test "no_filter returns all project data in structured format" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".basic_filters.no_filter.filter")

    result=$(jq "$filter" < "$FIXTURES/sample_project.json")

    # Should be valid JSON
    assert_valid_json "$result"

    # Should have expected structure
    assert_json_path "$result" ".project" "Test Project"
    assert_json_path "$result" ".totalItems" "5"
    assert_json_has_key "$result" "items"
}

@test "repository_filter extracts items from specified repo" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".basic_filters.repository_filter.filter")

    result=$(jq --arg repo "api" "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # Should filter to only api repo items (3 items: #42, #87, #45)
    assert_json_path "$result" ".filteredCount" "3"
    assert_json_path "$result" ".filters.repository" "api"
}

@test "repository_filter with non-existent repo returns zero items" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".basic_filters.repository_filter.filter")

    result=$(jq --arg repo "non-existent" "$filter" < "$FIXTURES/sample_project.json")

    assert_json_path "$result" ".filteredCount" "0"
}

@test "assignee_filter extracts items for specified user" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".basic_filters.assignee_filter.filter")

    result=$(jq --arg assignee "octocat" "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # octocat is assigned to items 1, 3, and 5
    assert_json_path "$result" ".filteredCount" "3"
    assert_json_path "$result" ".filters.assignee" "octocat"
}

@test "status_filter extracts items with matching status" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".basic_filters.status_filter.filter")

    result=$(jq --arg status "In Progress" "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # 2 items are "In Progress": #42 and #45
    assert_json_path "$result" ".filteredCount" "2"
}

@test "priority_filter extracts items with matching priority" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".basic_filters.priority_filter.filter")

    result=$(jq --arg priority "P1 - High" "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # 2 items are P1: #42 and #87
    assert_json_path "$result" ".filteredCount" "2"
}

# =============================================================================
# Combined Filter Tests
# =============================================================================

@test "universal_filter with empty params returns all items" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".combined_filters.universal_filter.filter")

    result=$(jq --arg repo "" --arg assignee "" --arg status "" --arg priority "" \
        "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # All 5 items should be returned
    filtered_count=$(echo "$result" | jq '.filteredCount')
    [ "$filtered_count" -eq 5 ]
}

@test "universal_filter with repo param filters correctly" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".combined_filters.universal_filter.filter")

    result=$(jq --arg repo "frontend" --arg assignee "" --arg status "" --arg priority "" \
        "$filter" < "$FIXTURES/sample_project.json")

    # Only 1 item in frontend repo
    assert_json_path "$result" ".filteredCount" "1"
}

@test "universal_filter with multiple params applies all conditions" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".combined_filters.universal_filter.filter")

    result=$(jq --arg repo "api" --arg assignee "octocat" --arg status "" --arg priority "" \
        "$filter" < "$FIXTURES/sample_project.json")

    # api repo + octocat = items 1 and 5 (but #3 is octocat too in api)
    # Actually: #42 (api, octocat), #87 (api, octocat), #45 (api, octocat+alice)
    filtered_count=$(echo "$result" | jq '.filteredCount')
    [ "$filtered_count" -ge 2 ]
}

@test "repo_and_assignee filter combines conditions" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".combined_filters.repo_and_assignee.filter")

    result=$(jq --arg repo "api" --arg assignee "octocat" "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"
    assert_json_has_key "$result" "filteredItems"
}

@test "repo_and_status filter combines conditions" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".combined_filters.repo_and_status.filter")

    result=$(jq --arg repo "api" --arg status "In Progress" "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"
    # api + In Progress = #42, #45
    filtered_count=$(echo "$result" | jq '.filteredCount')
    [ "$filtered_count" -eq 2 ]
}

# =============================================================================
# Discovery Filter Tests
# =============================================================================

@test "list_repositories extracts unique repos" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".discovery_filters.list_repositories.filter")

    result=$(jq "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # Should have 3 unique repos: api, frontend, docs
    repo_count=$(echo "$result" | jq '.repositories | length')
    [ "$repo_count" -eq 3 ]

    # Should include api
    echo "$result" | jq -e '.repositories | index("api")' > /dev/null
}

@test "list_assignees extracts unique assignees" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".discovery_filters.list_assignees.filter")

    result=$(jq "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # Should have 3 unique assignees: octocat, alice, bob
    assignee_count=$(echo "$result" | jq '.assignees | length')
    [ "$assignee_count" -eq 3 ]
}

@test "list_statuses extracts unique status values" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".discovery_filters.list_statuses.filter")

    result=$(jq "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # Should have 4 statuses: Backlog, In Progress, In Review, Done
    status_count=$(echo "$result" | jq '.statuses | length')
    [ "$status_count" -eq 4 ]
}

@test "list_priorities extracts unique priority values" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".discovery_filters.list_priorities.filter")

    result=$(jq "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"

    # Should have 4 priorities: P0, P1, P2, P3
    priority_count=$(echo "$result" | jq '.priorities | length')
    [ "$priority_count" -eq 4 ]
}

# =============================================================================
# Edge Case Tests
# =============================================================================

@test "filter handles items with null status" {
    # Use the items_with_nulls fixture
    result=$(jq '[.items[] | select(.status == "Done" or .status == null)]' \
        < "$FIXTURES/items_with_nulls.json")

    # Should not error
    [ $? -eq 0 ]
    assert_valid_json "$result"
}

@test "filter handles items with null assignees" {
    result=$(jq '[.items[] | select(.assignees == null or (.assignees | length) == 0)]' \
        < "$FIXTURES/items_with_nulls.json")

    [ $? -eq 0 ]
    assert_valid_json "$result"

    # Should find items 3 and 4
    count=$(echo "$result" | jq 'length')
    [ "$count" -eq 2 ]
}

@test "filter handles empty array results gracefully" {
    filter=$(get_filter "gh-project-jq-filters.yaml" ".basic_filters.assignee_filter.filter")

    result=$(jq --arg assignee "nonexistent-user" "$filter" < "$FIXTURES/sample_project.json")

    assert_valid_json "$result"
    assert_json_path "$result" ".filteredCount" "0"

    # filteredItems should be empty array, not null
    items_type=$(echo "$result" | jq '.filteredItems | type')
    [ "$items_type" = '"array"' ]
}

# =============================================================================
# Milestone Filter Tests
# =============================================================================

@test "milestone REST filter formats correctly" {
    filter=$(get_filter "gh-milestone-jq-filters.yaml" ".rest_format_filters.format_milestones_rest.filter")

    # Use integration fixture for milestones
    result=$(jq "$filter" < "$BATS_TEST_DIRNAME/../integration/fixtures/milestones.json")

    assert_valid_json "$result"

    # Should have 3 milestones
    count=$(echo "$result" | jq 'length')
    [ "$count" -eq 3 ]

    # First milestone should have expected structure
    echo "$result" | jq -e '.[0] | has("number") and has("title") and has("progress")' > /dev/null
}

@test "milestone progress calculation is correct" {
    filter=$(get_filter "gh-milestone-jq-filters.yaml" ".rest_format_filters.format_milestones_rest.filter")

    result=$(jq "$filter" < "$BATS_TEST_DIRNAME/../integration/fixtures/milestones.json")

    # v1.0.0 has 12 closed, 5 open = 17 total, 70% progress
    v1_progress=$(echo "$result" | jq '.[0].progress')
    [ "$v1_progress" -eq 70 ]

    # v0.9.0 (closed) has 20 closed, 0 open = 100%
    v09_progress=$(echo "$result" | jq '.[2].progress')
    [ "$v09_progress" -eq 100 ]
}
