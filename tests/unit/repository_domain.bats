#!/usr/bin/env bats
# Unit tests for repository domain functions
# Tests jq filters and format functions using recorded fixtures

load '../test_helper'

setup() {
    # Source the fixtures helper
    source "${BATS_TEST_DIRNAME}/../bats-helpers/fixtures.bash"

    # Get project root for filter loading
    PROJECT_ROOT=$(get_project_root)
    REPO_JQ_FILTERS="${PROJECT_ROOT}/lib/github/gh-repo-jq-filters.yaml"
}

# =============================================================================
# Fixture Loading Tests
# =============================================================================

@test "repository fixtures: repo.json loads successfully" {
    run load_graphql_fixture "repository" "repo"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data.repository' > /dev/null
}

@test "repository fixtures: org_repos.json loads successfully" {
    run load_graphql_fixture "repository" "org_repos"
    [ "$status" -eq 0 ]

    # Validate JSON structure
    echo "$output" | jq -e '.data' > /dev/null
}

# =============================================================================
# Repository Structure Tests
# =============================================================================

@test "repo fixture: has required fields" {
    fixture=$(load_graphql_fixture "repository" "repo")

    # Check all required fields
    echo "$fixture" | jq -e '.data.repository.id' > /dev/null
    echo "$fixture" | jq -e '.data.repository.name' > /dev/null
    echo "$fixture" | jq -e '.data.repository.nameWithOwner' > /dev/null
    echo "$fixture" | jq -e '.data.repository.url' > /dev/null
}

@test "repo fixture: id has correct format" {
    fixture=$(load_graphql_fixture "repository" "repo")

    id=$(echo "$fixture" | jq -r '.data.repository.id')

    # Repository IDs start with R_
    [[ "$id" =~ ^R_ ]]
}

@test "repo fixture: nameWithOwner has correct format" {
    fixture=$(load_graphql_fixture "repository" "repo")

    name_with_owner=$(echo "$fixture" | jq -r '.data.repository.nameWithOwner')

    # Should be in owner/repo format
    [[ "$name_with_owner" =~ ^[^/]+/[^/]+$ ]]
}

@test "repo fixture: url is valid GitHub URL" {
    fixture=$(load_graphql_fixture "repository" "repo")

    url=$(echo "$fixture" | jq -r '.data.repository.url')

    [[ "$url" =~ ^https://github.com/ ]]
}

@test "repo fixture: sshUrl is valid Git SSH URL" {
    fixture=$(load_graphql_fixture "repository" "repo")

    ssh_url=$(echo "$fixture" | jq -r '.data.repository.sshUrl')

    [[ "$ssh_url" =~ ^git@github.com: ]]
}

# =============================================================================
# Repository Boolean Fields Tests
# =============================================================================

@test "repo fixture: isPrivate is boolean" {
    fixture=$(load_graphql_fixture "repository" "repo")

    is_private=$(echo "$fixture" | jq '.data.repository.isPrivate')

    [[ "$is_private" == "true" || "$is_private" == "false" ]]
}

@test "repo fixture: isFork is boolean" {
    fixture=$(load_graphql_fixture "repository" "repo")

    is_fork=$(echo "$fixture" | jq '.data.repository.isFork')

    [[ "$is_fork" == "true" || "$is_fork" == "false" ]]
}

@test "repo fixture: isArchived is boolean" {
    fixture=$(load_graphql_fixture "repository" "repo")

    is_archived=$(echo "$fixture" | jq '.data.repository.isArchived')

    [[ "$is_archived" == "true" || "$is_archived" == "false" ]]
}

# =============================================================================
# Default Branch Tests
# =============================================================================

@test "repo fixture: defaultBranchRef exists" {
    fixture=$(load_graphql_fixture "repository" "repo")

    # defaultBranchRef should exist
    echo "$fixture" | jq -e '.data.repository.defaultBranchRef' > /dev/null
}

@test "repo fixture: default branch has name" {
    fixture=$(load_graphql_fixture "repository" "repo")

    branch_name=$(echo "$fixture" | jq -r '.data.repository.defaultBranchRef.name')

    # Should be a non-empty branch name
    [ -n "$branch_name" ]
    [[ "$branch_name" =~ ^[a-zA-Z0-9_-]+$ ]]
}

# =============================================================================
# Owner Tests
# =============================================================================

@test "repo fixture: owner has login" {
    fixture=$(load_graphql_fixture "repository" "repo")

    owner_login=$(echo "$fixture" | jq -r '.data.repository.owner.login')

    # Should be non-empty
    [ -n "$owner_login" ]
}

# =============================================================================
# Organization Repos Tests
# =============================================================================

@test "org_repos fixture: has repositories array" {
    fixture=$(load_graphql_fixture "repository" "org_repos")

    # Should have an organization with repositories or direct repos
    repos=$(echo "$fixture" | jq '.data.organization.repositories.nodes // .data.repositoryOwner.repositories.nodes // []')

    # Should be an array
    type=$(echo "$repos" | jq 'type')
    [ "$type" == '"array"' ]
}

# =============================================================================
# Timestamp Tests
# =============================================================================

@test "repo fixture: createdAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "repository" "repo")

    created_at=$(echo "$fixture" | jq -r '.data.repository.createdAt')

    # Should match ISO 8601 format
    [[ "$created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "repo fixture: updatedAt is valid ISO timestamp" {
    fixture=$(load_graphql_fixture "repository" "repo")

    updated_at=$(echo "$fixture" | jq -r '.data.repository.updatedAt')

    # Should match ISO 8601 format
    [[ "$updated_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# =============================================================================
# Data Extraction Tests
# =============================================================================

@test "extract repo id: correct prefix" {
    fixture=$(load_graphql_fixture "repository" "repo")

    id=$(echo "$fixture" | jq -r '.data.repository.id')

    # Repository node IDs start with R_
    [[ "$id" == R_* ]]
}

@test "extract repo name: valid format" {
    fixture=$(load_graphql_fixture "repository" "repo")

    name=$(echo "$fixture" | jq -r '.data.repository.name')

    # Name should not contain special characters except hyphen and underscore
    [[ "$name" =~ ^[a-zA-Z0-9._-]+$ ]]
}

# =============================================================================
# Edge Case Tests
# =============================================================================

@test "repo fixture: handles null description" {
    fixture=$(load_graphql_fixture "repository" "repo")

    # Description might be null - should not error
    desc=$(echo "$fixture" | jq -r '.data.repository.description // "none"')

    # Should get either a description or "none"
    [ -n "$desc" ]
}

@test "repo fixture: handles missing optional fields" {
    fixture=$(load_graphql_fixture "repository" "repo")

    # homepageUrl might not exist
    homepage=$(echo "$fixture" | jq -r '.data.repository.homepageUrl // "none"')

    # Should not error
    [ -n "$homepage" ]
}
