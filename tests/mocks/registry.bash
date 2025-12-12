#!/usr/bin/env bash
# Mock Registry System
# Dynamic request routing and response management for gh CLI mock

# =============================================================================
# REGISTRY STATE
# =============================================================================

# Registry file location (set by mock setup)
MOCK_REGISTRY_FILE="${MOCK_CONFIG_DIR:-/tmp}/mock_registry.txt"
MOCK_CALLS_LOG="${MOCK_CONFIG_DIR:-/tmp}/mock_calls.log"
MOCK_DEFAULTS_DIR="${BASH_SOURCE[0]%/*}/defaults"

# =============================================================================
# REGISTRY MANAGEMENT
# =============================================================================

# Initialize mock registry
init_mock_registry() {
    local config_dir="${1:-/tmp}"
    export MOCK_CONFIG_DIR="$config_dir"
    export MOCK_REGISTRY_FILE="${config_dir}/mock_registry.txt"
    export MOCK_CALLS_LOG="${config_dir}/mock_calls.log"

    # Create registry file
    > "$MOCK_REGISTRY_FILE"
    > "$MOCK_CALLS_LOG"

    # Load default configurations if they exist
    load_default_mocks
}

# Load default mock configurations from defaults/ directory
load_default_mocks() {
    if [[ ! -d "$MOCK_DEFAULTS_DIR" ]]; then
        return 0
    fi

    # Load each domain's default config
    for config_file in "$MOCK_DEFAULTS_DIR"/*.yaml; do
        [[ -f "$config_file" ]] || continue
        load_mock_config "$config_file"
    done
}

# Load mock configuration from YAML file
load_mock_config() {
    local config_file="$1"

    if [[ ! -f "$config_file" ]]; then
        echo "WARNING: Mock config not found: $config_file" >&2
        return 1
    fi

    # Extract mock definitions from YAML and register them
    # Format: pattern<|>type<|>fixture_path (using <|> as separator to avoid conflicts)
    yq '.mocks[] | .pattern + "<|>" + .type + "<|>" + .fixture' "$config_file" 2>/dev/null | \
        while IFS='' read -r line; do
            # Parse using <|> separator (chosen to avoid conflicts with common patterns)
            local pattern="${line%%<|>*}"
            local rest="${line#*<|>}"
            local type="${rest%%<|>*}"
            local fixture="${rest#*<|>}"
            register_mock "$pattern" "$type" "$fixture"
        done
}

# Register a mock response
# Usage: register_mock PATTERN TYPE FIXTURE_OR_RESPONSE
register_mock() {
    local pattern="$1"
    local type="$2"
    local response="$3"

    # Append to registry: pattern<|>type<|>response (using <|> to avoid conflicts)
    echo "${pattern}<|>${type}<|>${response}" >> "$MOCK_REGISTRY_FILE"
}

# Clear mock registry
clear_mock_registry() {
    > "$MOCK_REGISTRY_FILE"
    > "$MOCK_CALLS_LOG"
}

# =============================================================================
# REQUEST MATCHING
# =============================================================================

# Find matching mock response for a request
# Usage: find_mock_response TYPE REQUEST
find_mock_response() {
    local request_type="$1"
    local request="$2"

    # Log the request
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)|${request_type}|${request}" >> "$MOCK_CALLS_LOG"

    # Search registry for matching pattern (using <|> separator)
    while IFS='' read -r line; do
        # Parse using <|> separator
        local pattern="${line%%<|>*}"
        local rest="${line#*<|>}"
        local type="${rest%%<|>*}"
        local response="${rest#*<|>}"

        # Check if type matches
        if [[ "$type" != "$request_type" ]]; then
            continue
        fi

        # Check if pattern matches request
        if [[ "$request" =~ $pattern ]]; then
            # Check if response is a fixture path
            if [[ "$response" == *".json" ]]; then
                # Load fixture
                load_mock_fixture "$response"
            else
                # Return inline response
                echo "$response"
            fi
            return 0
        fi
    done < "$MOCK_REGISTRY_FILE"

    # No match found
    return 1
}

# Load a mock fixture file
load_mock_fixture() {
    local fixture_path="$1"

    # Try relative to tests/fixtures
    local fixtures_base="${BASH_SOURCE[0]%/*}/../fixtures"

    if [[ -f "${fixtures_base}/${fixture_path}" ]]; then
        cat "${fixtures_base}/${fixture_path}"
    elif [[ -f "$fixture_path" ]]; then
        cat "$fixture_path"
    else
        echo "ERROR: Mock fixture not found: $fixture_path" >&2
        echo '{"error": "Mock fixture not found"}'
        return 1
    fi
}

# =============================================================================
# GRAPHQL REQUEST HANDLING
# =============================================================================

# Handle GraphQL API request
handle_graphql_request() {
    local query="$1"

    # Extract query name/operation (simplified)
    local query_name=$(echo "$query" | grep -oP 'query\s+\K\w+' || echo "anonymous")

    # Try to find mock response
    if response=$(find_mock_response "graphql" "$query_name"); then
        echo "$response"
        return 0
    fi

    # Try pattern matching on query content
    if response=$(find_mock_response "graphql" "$query"); then
        echo "$response"
        return 0
    fi

    # No mock found
    echo '{"errors":[{"message":"No mock registered for GraphQL query: '"$query_name"'"}]}' >&2
    return 1
}

# =============================================================================
# REST REQUEST HANDLING
# =============================================================================

# Handle REST API request
handle_rest_request() {
    local method="$1"
    local endpoint="$2"
    shift 2
    local args=("$@")

    # Normalize endpoint (remove leading slash if present)
    endpoint="${endpoint#/}"

    # Try exact match first
    if response=$(find_mock_response "rest" "${method}:${endpoint}"); then
        echo "$response"
        return 0
    fi

    # Try endpoint-only match (any method)
    if response=$(find_mock_response "rest" "$endpoint"); then
        echo "$response"
        return 0
    fi

    # Try pattern matching
    if response=$(find_mock_response "rest" ".*${endpoint}.*"); then
        echo "$response"
        return 0
    fi

    # No mock found
    echo '{"message":"No mock registered for: '"${method} ${endpoint}"'"}' >&2
    return 1
}

# =============================================================================
# CLI COMMAND HANDLING
# =============================================================================

# Handle gh CLI commands (secret, variable, project, etc.)
handle_cli_command() {
    local command="$1"
    shift
    local subcommand="${1:-}"
    shift || true
    local args=("$@")

    # Build command signature
    local signature="${command} ${subcommand}"

    # Try to find mock response
    if response=$(find_mock_response "cli" "$signature"); then
        echo "$response"
        return 0
    fi

    # Try just the command
    if response=$(find_mock_response "cli" "$command"); then
        echo "$response"
        return 0
    fi

    # No mock found - return empty/default response
    case "$command" in
        secret)
            echo '[]'
            ;;
        variable)
            echo '[]'
            ;;
        project)
            echo '{"items":[]}'
            ;;
        *)
            echo ''
            ;;
    esac
}

# =============================================================================
# MOCK VERIFICATION
# =============================================================================

# Check if mock was called with specific pattern
was_mock_called() {
    local pattern="$1"

    grep -q "$pattern" "$MOCK_CALLS_LOG" 2>/dev/null
}

# Get number of times mock was called with pattern
get_mock_call_count() {
    local pattern="$1"

    grep -c "$pattern" "$MOCK_CALLS_LOG" 2>/dev/null || echo "0"
}

# Get all mock calls
get_mock_calls() {
    cat "$MOCK_CALLS_LOG" 2>/dev/null || true
}

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Register a GraphQL mock response
# Usage: mock_graphql QUERY_NAME FIXTURE_PATH
mock_graphql() {
    local query_name="$1"
    local fixture="$2"
    register_mock "$query_name" "graphql" "$fixture"
}

# Register a REST mock response
# Usage: mock_rest ENDPOINT FIXTURE_PATH [METHOD]
mock_rest() {
    local endpoint="$1"
    local fixture="$2"
    local method="${3:-GET}"

    # Register with method prefix
    register_mock "${method}:${endpoint}" "rest" "$fixture"
}

# Register an inline JSON response
# Usage: mock_json PATTERN TYPE JSON_STRING
mock_json() {
    local pattern="$1"
    local type="$2"
    local json="$3"

    register_mock "$pattern" "$type" "$json"
}

# =============================================================================
# ERROR SIMULATION
# =============================================================================

# Register an error response
# Usage: mock_error PATTERN TYPE HTTP_CODE [MESSAGE]
mock_error() {
    local pattern="$1"
    local type="$2"
    local code="$3"
    local message="${4:-Error}"

    local error_json="{\"message\":\"${message}\",\"status\":${code}}"
    register_mock "$pattern" "$type" "$error_json"
}

# Register a GraphQL error
# Usage: mock_graphql_error QUERY_NAME MESSAGE
mock_graphql_error() {
    local query_name="$1"
    local message="$2"

    local error_json="{\"errors\":[{\"message\":\"${message}\"}]}"
    register_mock "$query_name" "graphql" "$error_json"
}

# =============================================================================
# DEBUGGING
# =============================================================================

# Print current registry state
debug_registry() {
    echo "=== Mock Registry ==="
    cat "$MOCK_REGISTRY_FILE" 2>/dev/null || echo "(empty)"
    echo ""
    echo "=== Call Log ==="
    cat "$MOCK_CALLS_LOG" 2>/dev/null || echo "(no calls)"
}

# Print registry statistics
registry_stats() {
    local total_mocks=$(wc -l < "$MOCK_REGISTRY_FILE" 2>/dev/null || echo "0")
    local total_calls=$(wc -l < "$MOCK_CALLS_LOG" 2>/dev/null || echo "0")

    echo "Registered mocks: $total_mocks"
    echo "Total calls: $total_calls"

    # Count by type
    if [[ -f "$MOCK_REGISTRY_FILE" ]]; then
        echo ""
        echo "By type:"
        cut -d'|' -f2 "$MOCK_REGISTRY_FILE" | sort | uniq -c | sed 's/^/  /'
    fi
}
