#!/usr/bin/env bash
# tests/lib/resources/core.bash
# Core resource tracking and cleanup utilities
# Used by both fixture recording (Phase 2B) and E2E testing (Phase 6)

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default test organization and repository (can be overridden)
: "${TEST_ORG:=hiivmind}"
: "${TEST_REPO:=hiivmind-pulse-gh}"

# Resource prefix for easy identification
: "${RESOURCE_PREFIX:=test-}"

# =============================================================================
# RESOURCE TRACKING
# =============================================================================

# Global tracking - space-separated list of "type:identifier" pairs
# Example: "milestone:owner/repo/1 issue:owner/repo/42 label:owner/repo/test-label"
declare -g TRACKED_RESOURCES=""

# Track a resource for later cleanup
# Usage: track_resource "milestone" "owner/repo/number"
track_resource() {
    local type="$1"
    local identifier="$2"
    TRACKED_RESOURCES+="${type}:${identifier} "

    if [[ "${RESOURCE_DEBUG:-}" == "true" ]]; then
        echo "[TRACK] ${type}:${identifier}" >&2
    fi
}

# Check if a resource is tracked
# Usage: is_tracked "milestone" "owner/repo/1"
is_tracked() {
    local type="$1"
    local identifier="$2"
    [[ "$TRACKED_RESOURCES" == *"${type}:${identifier} "* ]]
}

# Get count of tracked resources
# Usage: count_tracked_resources
count_tracked_resources() {
    if [[ -z "$TRACKED_RESOURCES" ]]; then
        echo "0"
    else
        echo "$TRACKED_RESOURCES" | wc -w | tr -d ' '
    fi
}

# List all tracked resources
# Usage: list_tracked_resources
list_tracked_resources() {
    if [[ -n "$TRACKED_RESOURCES" ]]; then
        echo "$TRACKED_RESOURCES" | tr ' ' '\n' | grep -v '^$'
    fi
}

# =============================================================================
# CLEANUP
# =============================================================================

# Cleanup all tracked resources
# Calls delete_<type> function for each tracked resource
# Usage: cleanup_tracked_resources
cleanup_tracked_resources() {
    local failed=0

    if [[ -z "$TRACKED_RESOURCES" ]]; then
        return 0
    fi

    echo "[CLEANUP] Cleaning up $(count_tracked_resources) tracked resources..." >&2

    # Process in reverse order (LIFO) - delete dependent resources first
    local resources
    resources=$(echo "$TRACKED_RESOURCES" | tr ' ' '\n' | grep -v '^$' | tac)

    while IFS= read -r resource; do
        [[ -z "$resource" ]] && continue

        local type="${resource%%:*}"
        local identifier="${resource#*:}"

        if [[ "${RESOURCE_DEBUG:-}" == "true" ]]; then
            echo "[CLEANUP] Deleting ${type}: ${identifier}" >&2
        fi

        # Call the appropriate delete function
        if type "delete_${type}" &>/dev/null; then
            if ! "delete_${type}" "$identifier" 2>/dev/null; then
                echo "[CLEANUP] Warning: Failed to delete ${type}: ${identifier}" >&2
                ((failed++)) || true
            fi
        else
            echo "[CLEANUP] Warning: No delete function for type: ${type}" >&2
            ((failed++)) || true
        fi
    done <<< "$resources"

    # Clear tracking
    TRACKED_RESOURCES=""

    if [[ $failed -gt 0 ]]; then
        echo "[CLEANUP] Completed with $failed failures" >&2
    else
        echo "[CLEANUP] All resources cleaned up successfully" >&2
    fi

    return 0  # Don't fail the script on cleanup errors
}

# Setup trap for automatic cleanup on exit or error
# Usage: setup_cleanup_trap
setup_cleanup_trap() {
    trap 'cleanup_tracked_resources' EXIT
}

# Disable the cleanup trap (useful when you want manual control)
# Usage: disable_cleanup_trap
disable_cleanup_trap() {
    trap - EXIT
}

# =============================================================================
# UTILITIES
# =============================================================================

# Generate a unique resource name with timestamp
# Usage: generate_resource_name "milestone"
# Output: test-milestone-1702345678
generate_resource_name() {
    local base="${1:-resource}"
    echo "${RESOURCE_PREFIX}${base}-$(date +%s)"
}

# Parse owner/repo from identifier
# Usage: parse_owner_repo "owner/repo/extra"
# Sets: PARSED_OWNER, PARSED_REPO
parse_owner_repo() {
    local identifier="$1"
    PARSED_OWNER="${identifier%%/*}"
    local rest="${identifier#*/}"
    PARSED_REPO="${rest%%/*}"
}

# Parse owner/repo/number from identifier
# Usage: parse_owner_repo_number "owner/repo/123"
# Sets: PARSED_OWNER, PARSED_REPO, PARSED_NUMBER
parse_owner_repo_number() {
    local identifier="$1"
    PARSED_OWNER="${identifier%%/*}"
    local rest="${identifier#*/}"
    PARSED_REPO="${rest%%/*}"
    PARSED_NUMBER="${rest#*/}"
}

# Check if gh CLI is available and authenticated
# Usage: require_gh_cli
require_gh_cli() {
    if ! command -v gh &>/dev/null; then
        echo "Error: gh CLI is not installed" >&2
        return 1
    fi

    if ! gh auth status &>/dev/null; then
        echo "Error: gh CLI is not authenticated" >&2
        return 1
    fi
}

# Execute gh API call with error handling
# Usage: gh_api_call "repos/owner/repo/milestones" [-X POST] [-f field=value]
gh_api_call() {
    local result
    local exit_code

    result=$(gh api "$@" 2>&1) && exit_code=0 || exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        echo "Error: gh api call failed: $result" >&2
        return $exit_code
    fi

    echo "$result"
}

# =============================================================================
# ENSURE EMPTY HELPERS
# =============================================================================

# Ensure no resources of a type exist (for recording empty fixtures)
# Usage: ensure_empty "milestone" "owner" "repo"
ensure_empty() {
    local type="$1"
    local owner="$2"
    local repo="$3"

    local list_func="list_${type}s"
    local delete_func="delete_${type}"

    if ! type "$list_func" &>/dev/null; then
        echo "Warning: No list function for type: ${type}" >&2
        return 0
    fi

    echo "[ENSURE_EMPTY] Removing all ${type}s from ${owner}/${repo}..." >&2

    local items
    items=$("$list_func" "$owner" "$repo" 2>/dev/null) || return 0

    while IFS= read -r item; do
        [[ -z "$item" ]] && continue
        "$delete_func" "${owner}/${repo}/${item}" 2>/dev/null || true
    done <<< "$items"
}
