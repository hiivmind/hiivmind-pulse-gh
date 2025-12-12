#!/usr/bin/env bats
# Smoke tests for GitHub authentication
# Verifies that the token is valid and has required scopes

load '../../test_helper'

# =============================================================================
# Authentication Tests
# =============================================================================

@test "smoke: gh CLI is authenticated" {
    run gh auth status

    assert_success
}

@test "smoke: can identify current user" {
    run gh api /user --jq '.login'

    assert_success
    # Should return a non-empty login
    [ -n "$output" ]
}

@test "smoke: viewer query returns authenticated user" {
    run gh api graphql -f query='{ viewer { login } }' --jq '.data.viewer.login'

    assert_success
    [ -n "$output" ]
}

# =============================================================================
# Token Scope Tests
# =============================================================================

@test "smoke: token has repo scope (can access repos)" {
    # Try to access a repo endpoint - if this fails, repo scope is missing
    run gh api /user/repos --jq 'length'

    assert_success
    # Should return a number (even if 0)
    [[ "$output" =~ ^[0-9]+$ ]]
}

@test "smoke: token has read:org scope (can list orgs)" {
    run gh api /user/orgs --jq 'length'

    assert_success
    [[ "$output" =~ ^[0-9]+$ ]]
}

@test "smoke: token has project scope (can access projects)" {
    # GraphQL project access requires project scope
    run gh api graphql -f query='{ viewer { login projectsV2(first: 1) { totalCount } } }' \
        --jq '.data.viewer.projectsV2.totalCount'

    assert_success
    [[ "$output" =~ ^[0-9]+$ ]]
}

# =============================================================================
# Permission Tests
# =============================================================================

@test "smoke: can access test repository" {
    # Uses E2E_TEST_REPO if set, otherwise uses this repo
    local repo="${E2E_TEST_REPO:-hiivmind/hiivmind-pulse-gh}"

    run gh api "repos/${repo}" --jq '.full_name'

    assert_success
    [ -n "$output" ]
}

@test "smoke: can read repository issues" {
    local repo="${E2E_TEST_REPO:-hiivmind/hiivmind-pulse-gh}"

    run gh api "repos/${repo}/issues" --jq 'length'

    assert_success
    [[ "$output" =~ ^[0-9]+$ ]]
}

@test "smoke: can read repository milestones" {
    local repo="${E2E_TEST_REPO:-hiivmind/hiivmind-pulse-gh}"

    run gh api "repos/${repo}/milestones" --jq 'length'

    assert_success
    [[ "$output" =~ ^[0-9]+$ ]]
}

# =============================================================================
# OAuth Scopes Verification
# =============================================================================

@test "smoke: token scopes include required permissions" {
    # Get the X-OAuth-Scopes header from a request
    scopes=$(gh api /user -i 2>&1 | grep -i "x-oauth-scopes:" | cut -d: -f2- | tr -d ' ')

    # Check for essential scopes (at minimum should have repo)
    # Note: Fine-grained PATs don't return scopes the same way
    if [ -n "$scopes" ]; then
        [[ "$scopes" == *"repo"* ]] || [[ "$scopes" == *"public_repo"* ]]
    else
        # Fine-grained PAT or token without scope header - skip this check
        skip "Token doesn't expose OAuth scopes (likely fine-grained PAT)"
    fi
}
