#!/usr/bin/env bats
# Smoke tests for GitHub API connectivity
# Verifies that the GitHub API is reachable and responding

load '../../test_helper'

# =============================================================================
# API Reachability Tests
# =============================================================================

@test "smoke: GitHub API is reachable" {
    run gh api /rate_limit --jq '.resources.core.limit'

    assert_success
    # Should return a number (rate limit)
    [[ "$output" =~ ^[0-9]+$ ]]
}

@test "smoke: GitHub GraphQL API is reachable" {
    run gh api graphql -f query='{ __typename }'

    assert_success
    # Should return Query type
    echo "$output" | jq -e '.data.__typename == "Query"'
}

@test "smoke: can reach api.github.com" {
    run curl -s -o /dev/null -w "%{http_code}" https://api.github.com

    assert_success
    [ "$output" = "200" ]
}

# =============================================================================
# Rate Limit Tests
# =============================================================================

@test "smoke: rate limit is not exhausted" {
    run gh api /rate_limit --jq '.resources.core.remaining'

    assert_success
    remaining="$output"

    # Should have at least 100 requests remaining
    [ "$remaining" -ge 100 ]
}

@test "smoke: GraphQL rate limit is not exhausted" {
    run gh api /rate_limit --jq '.resources.graphql.remaining'

    assert_success
    remaining="$output"

    # Should have at least 100 requests remaining
    [ "$remaining" -ge 100 ]
}

# =============================================================================
# Response Format Tests
# =============================================================================

@test "smoke: REST API returns valid JSON" {
    result=$(gh api /rate_limit)

    assert_valid_json "$result"
}

@test "smoke: GraphQL API returns valid JSON" {
    result=$(gh api graphql -f query='{ viewer { login } }')

    assert_valid_json "$result"
}
