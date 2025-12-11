#!/usr/bin/env bash
# Mock utilities for BATS tests
# Provides setup and configuration for mocked `gh` CLI

# Store original PATH
ORIGINAL_PATH="$PATH"

# Store mock configuration directory
MOCK_CONFIG_DIR=""

# =============================================================================
# MOCK SETUP/TEARDOWN
# =============================================================================

# Setup mock gh CLI by prepending mock directory to PATH
# Usage: setup_mock_gh
setup_mock_gh() {
    local test_dir="${BATS_TEST_DIRNAME}"

    # Find the mocks directory (could be at tests/mocks or tests/integration/mocks)
    if [[ -d "${test_dir%/*}/mocks" ]]; then
        MOCK_DIR="${test_dir%/*}/mocks"
    elif [[ -d "${test_dir}/mocks" ]]; then
        MOCK_DIR="${test_dir}/mocks"
    else
        echo "ERROR: Could not find mocks directory" >&2
        return 1
    fi

    # Make mock gh executable
    if [[ -f "$MOCK_DIR/gh" ]]; then
        chmod +x "$MOCK_DIR/gh"
    fi

    # Prepend mock directory to PATH
    export PATH="$MOCK_DIR:$ORIGINAL_PATH"

    # Create temp directory for mock config if needed
    MOCK_CONFIG_DIR=$(mktemp -d)
    export MOCK_CONFIG_DIR

    # Source registry if available (for enhanced mock system)
    if [[ -f "$MOCK_DIR/registry.bash" ]]; then
        source "$MOCK_DIR/registry.bash"
        init_mock_registry "$MOCK_CONFIG_DIR"
    fi
}

# Restore original PATH and cleanup mock configuration
# Usage: teardown_mock_gh
teardown_mock_gh() {
    export PATH="$ORIGINAL_PATH"

    # Cleanup mock config directory
    if [[ -n "$MOCK_CONFIG_DIR" ]] && [[ -d "$MOCK_CONFIG_DIR" ]]; then
        rm -rf "$MOCK_CONFIG_DIR"
    fi
}

# =============================================================================
# MOCK RESPONSE CONFIGURATION
# =============================================================================

# Configure mock to return specific fixture for an endpoint
# Usage: mock_response ENDPOINT_PATTERN FIXTURE_PATH
# Example: mock_response "repos/.*/milestones" "milestone/list_all.json"
mock_response() {
    local endpoint_pattern="$1"
    local fixture_path="$2"

    if [[ -z "$MOCK_CONFIG_DIR" ]]; then
        echo "ERROR: mock_response called before setup_mock_gh" >&2
        return 1
    fi

    # Store mapping in config file
    echo "${endpoint_pattern}|${fixture_path}" >> "$MOCK_CONFIG_DIR/responses.map"
}

# Configure mock to return error for an endpoint
# Usage: mock_error ENDPOINT_PATTERN HTTP_CODE [ERROR_MESSAGE]
# Example: mock_error "repos/.*/milestones/999" 404 "Not Found"
mock_error() {
    local endpoint_pattern="$1"
    local http_code="$2"
    local error_message="${3:-Error}"

    if [[ -z "$MOCK_CONFIG_DIR" ]]; then
        echo "ERROR: mock_error called before setup_mock_gh" >&2
        return 1
    fi

    # Store error config
    echo "${endpoint_pattern}|${http_code}|${error_message}" >> "$MOCK_CONFIG_DIR/errors.map"
}

# Configure mock GraphQL response
# Usage: mock_graphql_response QUERY_NAME FIXTURE_PATH
# Example: mock_graphql_response "fetch_repo_milestones" "milestone/graphql_list.json"
mock_graphql_response() {
    local query_name="$1"
    local fixture_path="$2"

    if [[ -z "$MOCK_CONFIG_DIR" ]]; then
        echo "ERROR: mock_graphql_response called before setup_mock_gh" >&2
        return 1
    fi

    echo "${query_name}|${fixture_path}" >> "$MOCK_CONFIG_DIR/graphql_responses.map"
}

# =============================================================================
# MOCK VERIFICATION
# =============================================================================

# Check if mock gh is in PATH
# Usage: assert_mock_gh_active
assert_mock_gh_active() {
    local gh_path=$(which gh)

    if [[ ! "$gh_path" =~ /mocks/gh$ ]]; then
        echo "ERROR: Mock gh is not active in PATH" >&2
        echo "Current gh path: $gh_path" >&2
        return 1
    fi
}

# Get number of times mock was called with specific pattern
# Usage: get_mock_call_count PATTERN
get_mock_call_count() {
    local pattern="$1"

    if [[ -z "$MOCK_CONFIG_DIR" ]] || [[ ! -f "$MOCK_CONFIG_DIR/calls.log" ]]; then
        echo "0"
        return
    fi

    grep -c "$pattern" "$MOCK_CONFIG_DIR/calls.log" || echo "0"
}

# Assert that mock was called with specific pattern
# Usage: assert_mock_called PATTERN [MIN_COUNT]
assert_mock_called() {
    local pattern="$1"
    local min_count="${2:-1}"

    local actual_count=$(get_mock_call_count "$pattern")

    if [[ "$actual_count" -lt "$min_count" ]]; then
        echo "Mock was not called enough times with pattern: $pattern" >&2
        echo "Expected at least: $min_count" >&2
        echo "Actual: $actual_count" >&2
        if [[ -f "$MOCK_CONFIG_DIR/calls.log" ]]; then
            echo "All calls:" >&2
            cat "$MOCK_CONFIG_DIR/calls.log" >&2
        fi
        return 1
    fi
}

# =============================================================================
# MOCK MODE CONFIGURATION
# =============================================================================

# Enable strict mode (fail on unmapped requests)
# Usage: mock_enable_strict_mode
mock_enable_strict_mode() {
    if [[ -z "$MOCK_CONFIG_DIR" ]]; then
        echo "ERROR: mock_enable_strict_mode called before setup_mock_gh" >&2
        return 1
    fi

    touch "$MOCK_CONFIG_DIR/strict_mode"
}

# Enable passthrough mode (forward unmapped requests to real gh)
# Usage: mock_enable_passthrough
mock_enable_passthrough() {
    if [[ -z "$MOCK_CONFIG_DIR" ]]; then
        echo "ERROR: mock_enable_passthrough called before setup_mock_gh" >&2
        return 1
    fi

    touch "$MOCK_CONFIG_DIR/passthrough_mode"
}

# Enable recording mode (save responses for future use)
# Usage: mock_enable_recording OUTPUT_DIR
mock_enable_recording() {
    local output_dir="$1"

    if [[ -z "$MOCK_CONFIG_DIR" ]]; then
        echo "ERROR: mock_enable_recording called before setup_mock_gh" >&2
        return 1
    fi

    mkdir -p "$output_dir"
    echo "$output_dir" > "$MOCK_CONFIG_DIR/recording_dir"
}

# =============================================================================
# MOCK RESPONSE HELPERS
# =============================================================================

# Create a simple JSON response
# Usage: mock_json_response KEY1 VALUE1 KEY2 VALUE2 ...
mock_json_response() {
    local json="{"

    while [[ $# -gt 0 ]]; do
        local key="$1"
        local value="$2"
        shift 2

        # Check if value looks like a number or boolean
        if [[ "$value" =~ ^[0-9]+$ ]] || [[ "$value" == "true" ]] || [[ "$value" == "false" ]]; then
            json+="\"$key\":$value"
        else
            json+="\"$key\":\"$value\""
        fi

        if [[ $# -gt 0 ]]; then
            json+=","
        fi
    done

    json+="}"
    echo "$json"
}

# Create an array response
# Usage: mock_array_response ITEM1 ITEM2 ...
mock_array_response() {
    local array="["

    while [[ $# -gt 0 ]]; do
        array+="\"$1\""
        shift

        if [[ $# -gt 0 ]]; then
            array+=","
        fi
    done

    array+="]"
    echo "$array"
}

# Create a GraphQL success response
# Usage: mock_graphql_success DATA_JSON
mock_graphql_success() {
    local data="$1"
    echo "{\"data\":$data}"
}

# Create a GraphQL error response
# Usage: mock_graphql_error MESSAGE
mock_graphql_error() {
    local message="$1"
    echo "{\"errors\":[{\"message\":\"$message\"}]}"
}

# =============================================================================
# MOCK STATE MANAGEMENT
# =============================================================================

# Reset all mock configuration
# Usage: reset_mock_state
reset_mock_state() {
    if [[ -z "$MOCK_CONFIG_DIR" ]]; then
        return
    fi

    # Clear response mappings
    rm -f "$MOCK_CONFIG_DIR/responses.map"
    rm -f "$MOCK_CONFIG_DIR/errors.map"
    rm -f "$MOCK_CONFIG_DIR/graphql_responses.map"

    # Clear call log
    rm -f "$MOCK_CONFIG_DIR/calls.log"

    # Clear mode flags
    rm -f "$MOCK_CONFIG_DIR/strict_mode"
    rm -f "$MOCK_CONFIG_DIR/passthrough_mode"
    rm -f "$MOCK_CONFIG_DIR/recording_dir"
}

# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# Setup mock using old integration test location
# Usage: setup_integration_mock
setup_integration_mock() {
    # This function maintains compatibility with existing integration tests
    # that expect mock gh at tests/integration/mocks/gh
    setup_mock_gh
}

# Teardown mock for integration tests
# Usage: teardown_integration_mock
teardown_integration_mock() {
    teardown_mock_gh
}

# =============================================================================
# REGISTRY-BASED MOCK FUNCTIONS (Enhanced Mock System)
# =============================================================================

# Register a mock GraphQL response using the registry
# Usage: register_mock_graphql QUERY_NAME_OR_PATTERN FIXTURE_PATH
register_mock_graphql() {
    local pattern="$1"
    local fixture="$2"

    # Use registry if available
    if type -t mock_graphql >/dev/null 2>&1; then
        mock_graphql "$pattern" "$fixture"
    else
        # Fallback to old system
        mock_graphql_response "$pattern" "$fixture"
    fi
}

# Register a mock REST response using the registry
# Usage: register_mock_rest ENDPOINT FIXTURE_PATH [METHOD]
register_mock_rest() {
    local endpoint="$1"
    local fixture="$2"
    local method="${3:-GET}"

    # Use registry if available
    if type -t mock_rest >/dev/null 2>&1; then
        mock_rest "$endpoint" "$fixture" "$method"
    else
        # Fallback to old system
        mock_response "$endpoint" "$fixture"
    fi
}

# Register an inline JSON mock response
# Usage: register_mock_json PATTERN TYPE JSON_STRING
register_mock_json() {
    local pattern="$1"
    local type="$2"
    local json="$3"

    # Use registry if available
    if type -t mock_json >/dev/null 2>&1; then
        mock_json "$pattern" "$type" "$json"
    else
        echo "ERROR: Registry not loaded, cannot register JSON mock" >&2
        return 1
    fi
}

# Clear the mock registry
# Usage: clear_mocks
clear_mocks() {
    # Use registry if available
    if type -t clear_mock_registry >/dev/null 2>&1; then
        clear_mock_registry
    else
        reset_mock_state
    fi
}

# Assert mock was called (registry-aware)
# Usage: assert_registry_mock_called PATTERN [MIN_COUNT]
assert_registry_mock_called() {
    local pattern="$1"
    local min_count="${2:-1}"

    # Use registry if available
    if type -t was_mock_called >/dev/null 2>&1; then
        if ! was_mock_called "$pattern"; then
            echo "Mock was not called with pattern: $pattern" >&2
            return 1
        fi

        local actual=$(get_mock_call_count "$pattern")
        if [[ "$actual" -lt "$min_count" ]]; then
            echo "Mock called $actual times, expected at least $min_count" >&2
            return 1
        fi
    else
        # Fallback to old system
        assert_mock_called "$pattern" "$min_count"
    fi
}

# Load a mock configuration file (YAML)
# Usage: load_mock_config_file PATH
load_mock_config_file() {
    local config_file="$1"

    if type -t load_mock_config >/dev/null 2>&1; then
        load_mock_config "$config_file"
    else
        echo "ERROR: Registry not loaded, cannot load config file" >&2
        return 1
    fi
}

# Debug: Print mock registry state
# Usage: print_mock_registry
print_mock_registry() {
    if type -t debug_registry >/dev/null 2>&1; then
        debug_registry
    else
        echo "Registry not available (old mock system)"
    fi
}
