#!/bin/bash
# Test helper functions for BATS tests
# This file maintains backward compatibility while importing enhanced helpers

# =============================================================================
# PROJECT PATHS
# =============================================================================

# Get the root directory of the project
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROJECT_ROOT

# Get the fixtures root directory
FIXTURES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/fixtures" && pwd)"
export FIXTURES_ROOT

# Get the test directory
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TEST_DIR

# Add node_modules/.bin to PATH for local tools (yq, bats)
export PATH="$PROJECT_ROOT/node_modules/.bin:$PATH"

# =============================================================================
# LOAD ENHANCED HELPERS
# =============================================================================

# Determine the correct path to helpers based on where this file is loaded from
HELPERS_DIR="${BASH_SOURCE[0]%/*}/bats-helpers"

# Load enhanced assertion helpers
if [[ -f "$HELPERS_DIR/assertions.bash" ]]; then
    source "$HELPERS_DIR/assertions.bash"
fi

# Load fixture loading helpers
if [[ -f "$HELPERS_DIR/fixtures.bash" ]]; then
    source "$HELPERS_DIR/fixtures.bash"
fi

# Load mock utilities
if [[ -f "$HELPERS_DIR/mocks.bash" ]]; then
    source "$HELPERS_DIR/mocks.bash"
fi

# Load bats-support and bats-assert if available
load_helpers() {
    if [ -d "$BATS_TEST_DIRNAME/../node_modules/bats-support" ]; then
        load '../node_modules/bats-support/load'
        load '../node_modules/bats-assert/load'
    fi
}

# =============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# These functions maintain compatibility with existing tests
# New tests should use the enhanced functions from bats-helpers/assertions.bash
# =============================================================================

# Assert JSON structure - check a jq path equals expected value
# DEPRECATED: Use assert_field_equals from assertions.bash for new tests
assert_json_path() {
    local json="$1"
    local path="$2"
    local expected="$3"

    actual=$(echo "$json" | jq -r "$path")
    if [ "$actual" != "$expected" ]; then
        echo "Expected $path to be '$expected', got '$actual'" >&2
        return 1
    fi
}

# Assert JSON array length
assert_json_length() {
    local json="$1"
    local path="$2"
    local expected="$3"

    actual=$(echo "$json" | jq "$path | length")
    if [ "$actual" != "$expected" ]; then
        echo "Expected $path length to be '$expected', got '$actual'" >&2
        return 1
    fi
}

# Assert command succeeds and outputs valid JSON
assert_valid_json() {
    local result="$1"

    echo "$result" | jq . > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Invalid JSON output: $result" >&2
        return 1
    fi
}

# Assert command succeeds
assert_success() {
    if [ "$status" -ne 0 ]; then
        echo "Command failed with status $status" >&2
        echo "Output: $output" >&2
        return 1
    fi
}

# Assert command fails
assert_failure() {
    if [ "$status" -eq 0 ]; then
        echo "Command succeeded but was expected to fail" >&2
        return 1
    fi
}

# Assert output contains string
assert_output_contains() {
    local expected="$1"

    if [[ "$output" != *"$expected"* ]]; then
        echo "Expected output to contain '$expected'" >&2
        echo "Actual output: $output" >&2
        return 1
    fi
}

# Assert JSON has key
assert_json_has_key() {
    local json="$1"
    local key="$2"

    if ! echo "$json" | jq -e "has(\"$key\")" > /dev/null 2>&1; then
        echo "Expected JSON to have key '$key'" >&2
        return 1
    fi
}

# Get fixture path (legacy)
# DEPRECATED: Use load_fixture from fixtures.bash for new tests
fixture() {
    local name="$1"
    echo "$BATS_TEST_DIRNAME/fixtures/$name"
}

# Load fixture content (legacy - loads from test-local fixtures directory)
# NOTE: This is overridden by fixtures.bash which loads from centralized location
# Existing tests still use this for backward compatibility
load_fixture_legacy() {
    local name="$1"
    cat "$(fixture "$name")"
}

# Alias for backward compatibility if fixtures.bash not loaded
if ! type -t load_fixture >/dev/null 2>&1; then
    load_fixture() {
        load_fixture_legacy "$@"
    }
fi

# Source library functions
source_lib() {
    local lib="$1"
    source "$PROJECT_ROOT/lib/github/$lib"
}

# Get filter from YAML
# NOTE: Enhanced version available in fixtures.bash as get_domain_filter
get_filter() {
    local yaml_file="$1"
    local filter_path="$2"

    yq -r "$filter_path" "$PROJECT_ROOT/lib/github/$yaml_file"
}

# =============================================================================
# ENHANCED HELPER FUNCTIONS
# =============================================================================

# Source a domain's function library (convenience wrapper)
# Usage: source_domain_lib "milestone"
source_domain_lib() {
    local domain="$1"
    source_lib "gh-${domain}-functions.sh"
}
