#!/usr/bin/env bats
# Unit tests for project domain functions
# Tests jq filters and format functions using recorded fixtures

load '../test_helper'

setup() {
    # Source the fixtures helper
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"

    # Get project root for filter loading
    PROJECT_ROOT=$(get_project_root)
    PROJECT_JQ_FILTERS="${PROJECT_ROOT}/lib/github/gh-project-jq-filters.yaml"

    # Local unit test fixtures
    LOCAL_FIXTURES="${BATS_TEST_DIRNAME}/fixtures"
}

# =============================================================================
# Fixture Loading Tests
# =============================================================================

@test "project fixtures: org_project.json loads successfully" {
    run load_graphql_fixture "project" "org_project"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.organization.projectV2' > /dev/null
}

@test "project fixtures: sample_project.json (local) loads successfully" {
    [ -f "$LOCAL_FIXTURES/sample_project.json" ]

    fixture=$(cat "$LOCAL_FIXTURES/sample_project.json")
    # Local fixture has .data.organization.projectV2 structure
    echo "$fixture" | jq -e '.data.organization.projectV2' > /dev/null
}

# =============================================================================
# Project Structure Tests
# =============================================================================

@test "project fixture: has required fields" {
    fixture=$(load_graphql_fixture "project" "org_project")

    # Check required fields
    echo "$fixture" | jq -e '.data.organization.projectV2.id' > /dev/null
    echo "$fixture" | jq -e '.data.organization.projectV2.title' > /dev/null
    echo "$fixture" | jq -e '.data.organization.projectV2.items' > /dev/null
    echo "$fixture" | jq -e '.data.organization.projectV2.fields' > /dev/null
}

@test "project fixture: id has correct prefix" {
    fixture=$(load_graphql_fixture "project" "org_project")

    id=$(echo "$fixture" | jq -r '.data.organization.projectV2.id')

    # Project V2 IDs start with PVT_
    [[ "$id" == PVT_* ]]
}

@test "project fixture: title is non-empty" {
    fixture=$(load_graphql_fixture "project" "org_project")

    title=$(echo "$fixture" | jq -r '.data.organization.projectV2.title')

    [ -n "$title" ]
}

# =============================================================================
# Project Boolean Tests
# =============================================================================

@test "project fixture: public is boolean" {
    fixture=$(load_graphql_fixture "project" "org_project")

    is_public=$(echo "$fixture" | jq '.data.organization.projectV2.public')

    [[ "$is_public" == "true" || "$is_public" == "false" ]]
}

@test "project fixture: closed is boolean" {
    fixture=$(load_graphql_fixture "project" "org_project")

    is_closed=$(echo "$fixture" | jq '.data.organization.projectV2.closed')

    [[ "$is_closed" == "true" || "$is_closed" == "false" ]]
}

# =============================================================================
# Items Tests
# =============================================================================

@test "project fixture: items has totalCount" {
    fixture=$(load_graphql_fixture "project" "org_project")

    total_count=$(echo "$fixture" | jq '.data.organization.projectV2.items.totalCount')

    [ "$total_count" -ge 0 ]
}

@test "project fixture: items.nodes is array" {
    fixture=$(load_graphql_fixture "project" "org_project")

    type=$(echo "$fixture" | jq '.data.organization.projectV2.items.nodes | type')

    [ "$type" == '"array"' ]
}

# =============================================================================
# Fields Tests
# =============================================================================

@test "project fixture: fields.nodes is array" {
    fixture=$(load_graphql_fixture "project" "org_project")

    type=$(echo "$fixture" | jq '.data.organization.projectV2.fields.nodes | type')

    [ "$type" == '"array"' ]
}

@test "project fixture: has Status field" {
    fixture=$(load_graphql_fixture "project" "org_project")

    status_field=$(echo "$fixture" | jq '.data.organization.projectV2.fields.nodes[] | select(.name == "Status")')

    [ -n "$status_field" ]
}

@test "project fixture: Status field has options" {
    fixture=$(load_graphql_fixture "project" "org_project")

    options=$(echo "$fixture" | jq '.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .options')

    type=$(echo "$options" | jq 'type')
    [ "$type" == '"array"' ]
}

@test "project fixture: fields have dataType" {
    fixture=$(load_graphql_fixture "project" "org_project")

    # Check first field has dataType
    data_type=$(echo "$fixture" | jq -r '.data.organization.projectV2.fields.nodes[0].dataType')

    [ -n "$data_type" ]
}

@test "project fixture: field dataTypes are valid" {
    fixture=$(load_graphql_fixture "project" "org_project")

    # Get all unique dataTypes
    data_types=$(echo "$fixture" | jq -r '[.data.organization.projectV2.fields.nodes[].dataType] | unique | .[]')

    # Each should be a known type
    while IFS= read -r dtype; do
        [[ "$dtype" =~ ^(TITLE|ASSIGNEES|SINGLE_SELECT|LABELS|LINKED_PULL_REQUESTS|MILESTONE|REPOSITORY|REVIEWERS|PARENT_ISSUE|SUB_ISSUES_PROGRESS|TEXT|NUMBER|DATE|ITERATION)$ ]]
    done <<< "$data_types"
}

# =============================================================================
# Timestamp Tests
# =============================================================================

@test "project fixture: createdAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "project" "org_project")

    created_at=$(echo "$fixture" | jq -r '.data.organization.projectV2.createdAt')

    [[ "$created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "project fixture: updatedAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "project" "org_project")

    updated_at=$(echo "$fixture" | jq -r '.data.organization.projectV2.updatedAt')

    [[ "$updated_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# =============================================================================
# Local Fixture Tests (sample_project.json)
# =============================================================================

@test "sample_project: has items array" {
    fixture=$(cat "$LOCAL_FIXTURES/sample_project.json")

    # Local fixture has items under .data.organization.projectV2.items.nodes
    type=$(echo "$fixture" | jq '.data.organization.projectV2.items.nodes | type')
    [ "$type" == '"array"' ]
}

@test "sample_project: items have content" {
    fixture=$(cat "$LOCAL_FIXTURES/sample_project.json")

    # Check first item has content
    echo "$fixture" | jq -e '.data.organization.projectV2.items.nodes[0].content' > /dev/null
}

@test "sample_project: items have fieldValues" {
    fixture=$(cat "$LOCAL_FIXTURES/sample_project.json")

    # Check first item has fieldValues
    echo "$fixture" | jq -e '.data.organization.projectV2.items.nodes[0].fieldValues' > /dev/null
}

# =============================================================================
# Items with Nulls Tests
# =============================================================================

@test "items_with_nulls: loads successfully" {
    [ -f "$LOCAL_FIXTURES/items_with_nulls.json" ]

    fixture=$(cat "$LOCAL_FIXTURES/items_with_nulls.json")
    echo "$fixture" | jq -e '.items' > /dev/null
}

@test "items_with_nulls: can handle null status" {
    fixture=$(cat "$LOCAL_FIXTURES/items_with_nulls.json")

    # Find items with null status
    null_status_items=$(echo "$fixture" | jq '[.items[] | select(.status == null)]')

    type=$(echo "$null_status_items" | jq 'type')
    [ "$type" == '"array"' ]
}

@test "items_with_nulls: can handle null assignees" {
    fixture=$(cat "$LOCAL_FIXTURES/items_with_nulls.json")

    # Find items with null/empty assignees
    no_assignees=$(echo "$fixture" | jq '[.items[] | select(.assignees == null or (.assignees | length) == 0)]')

    type=$(echo "$no_assignees" | jq 'type')
    [ "$type" == '"array"' ]
}

# =============================================================================
# Field Extraction Tests
# =============================================================================

@test "extract Status field options: all have id and name" {
    fixture=$(load_graphql_fixture "project" "org_project")

    # Get options as a JSON array, then check each
    options_count=$(echo "$fixture" | jq '.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .options | length')

    [ "$options_count" -gt 0 ]

    # Check that all options have both id and name
    all_have_id=$(echo "$fixture" | jq '[.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .options[] | has("id")] | all')
    all_have_name=$(echo "$fixture" | jq '[.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .options[] | has("name")] | all')

    [ "$all_have_id" == "true" ]
    [ "$all_have_name" == "true" ]
}

@test "extract field ids: all have correct prefix" {
    fixture=$(load_graphql_fixture "project" "org_project")

    ids=$(echo "$fixture" | jq -r '.data.organization.projectV2.fields.nodes[].id')

    while IFS= read -r id; do
        # Field IDs start with PVTF_ or PVTSSF_
        [[ "$id" == PVTF_* || "$id" == PVTSSF_* ]]
    done <<< "$ids"
}

# =============================================================================
# Edge Case Tests
# =============================================================================

@test "project fixture: handles null shortDescription" {
    fixture=$(load_graphql_fixture "project" "org_project")

    desc=$(echo "$fixture" | jq -r '.data.organization.projectV2.shortDescription // "none"')

    # Should not error
    [ -n "$desc" ]
}

@test "project fixture: handles empty items" {
    fixture=$(load_graphql_fixture "project" "org_project")

    count=$(echo "$fixture" | jq '.data.organization.projectV2.items.nodes | length')

    # Empty items should return 0, not error
    [ "$count" -ge 0 ]
}
