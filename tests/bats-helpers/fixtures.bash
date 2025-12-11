#!/usr/bin/env bash
# Fixture loading utilities for BATS tests
# Provides domain-aware fixture loading from centralized location

# Get the fixtures root directory
get_fixtures_root() {
    echo "${BATS_TEST_DIRNAME%/*}/fixtures"
}

# Get the project root directory
get_project_root() {
    echo "${BATS_TEST_DIRNAME%/*/*}"
}

# =============================================================================
# FIXTURE LOADING
# =============================================================================

# Load a fixture from the centralized fixtures directory
# Usage: load_fixture DOMAIN FIXTURE_NAME [TYPE]
# TYPE defaults to "graphql" if not specified
# Returns: The fixture content
load_fixture() {
    local domain="$1"
    local fixture_name="$2"
    local type="${3:-graphql}"  # Default to graphql if not specified

    local fixtures_root=$(get_fixtures_root)
    local fixture_path="${fixtures_root}/${type}/${domain}/${fixture_name}.json"

    if [[ ! -f "$fixture_path" ]]; then
        # Try without .json extension (in case it's already included)
        fixture_path="${fixtures_root}/${type}/${domain}/${fixture_name}"
    fi

    if [[ ! -f "$fixture_path" ]]; then
        echo "ERROR: Fixture not found: ${type}/${domain}/${fixture_name}" >&2
        echo "Searched path: $fixture_path" >&2
        return 1
    fi

    cat "$fixture_path"
}

# Load a GraphQL fixture
# Usage: load_graphql_fixture DOMAIN FIXTURE_NAME
load_graphql_fixture() {
    local domain="$1"
    local fixture_name="$2"
    load_fixture "$domain" "$fixture_name" "graphql"
}

# Load a REST API fixture
# Usage: load_rest_fixture DOMAIN FIXTURE_NAME
load_rest_fixture() {
    local domain="$1"
    local fixture_name="$2"
    load_fixture "$domain" "$fixture_name" "rest"
}

# Load a synthetic fixture (hand-crafted for edge cases)
# Usage: load_synthetic_fixture CATEGORY FIXTURE_NAME
# Example: load_synthetic_fixture "empty" "array"
load_synthetic_fixture() {
    local category="$1"
    local fixture_name="$2"

    local fixtures_root=$(get_fixtures_root)
    local fixture_path="${fixtures_root}/_synthetic/${category}/${fixture_name}.json"

    if [[ ! -f "$fixture_path" ]]; then
        echo "ERROR: Synthetic fixture not found: _synthetic/${category}/${fixture_name}" >&2
        return 1
    fi

    cat "$fixture_path"
}

# =============================================================================
# JQ FILTER LOADING
# =============================================================================

# Load a jq filter from domain's jq-filters.yaml
# Usage: get_domain_filter DOMAIN FILTER_PATH
# Example: get_domain_filter "milestone" ".filters.format_milestones_list"
get_domain_filter() {
    local domain="$1"
    local filter_path="$2"

    local project_root=$(get_project_root)
    local filters_file="${project_root}/lib/github/gh-${domain}-jq-filters.yaml"

    if [[ ! -f "$filters_file" ]]; then
        echo "ERROR: Filters file not found: $filters_file" >&2
        return 1
    fi

    # Extract filter using yq
    local filter=$(yq "${filter_path}.filter" "$filters_file")

    if [[ -z "$filter" ]] || [[ "$filter" == "null" ]]; then
        echo "ERROR: Filter not found at path: $filter_path" >&2
        return 1
    fi

    echo "$filter"
}

# Get filter from any jq-filters.yaml file by filename
# Usage: get_filter FILENAME FILTER_PATH
# Example: get_filter "gh-milestone-jq-filters.yaml" ".filters.format_milestones_list"
get_filter() {
    local filename="$1"
    local filter_path="$2"

    local project_root=$(get_project_root)
    local filters_file="${project_root}/lib/github/${filename}"

    if [[ ! -f "$filters_file" ]]; then
        echo "ERROR: Filters file not found: $filters_file" >&2
        return 1
    fi

    local filter=$(yq "${filter_path}.filter" "$filters_file")

    if [[ -z "$filter" ]] || [[ "$filter" == "null" ]]; then
        echo "ERROR: Filter not found at path: $filter_path" >&2
        return 1
    fi

    echo "$filter"
}

# =============================================================================
# GRAPHQL QUERY LOADING
# =============================================================================

# Load a GraphQL query from domain's graphql-queries.yaml
# Usage: get_domain_query DOMAIN QUERY_NAME
# Example: get_domain_query "milestone" "fetch_repo_milestones"
get_domain_query() {
    local domain="$1"
    local query_name="$2"

    local project_root=$(get_project_root)
    local queries_file="${project_root}/lib/github/gh-${domain}-graphql-queries.yaml"

    if [[ ! -f "$queries_file" ]]; then
        echo "ERROR: Queries file not found: $queries_file" >&2
        return 1
    fi

    local query=$(yq ".queries.${query_name}.query" "$queries_file")

    if [[ -z "$query" ]] || [[ "$query" == "null" ]]; then
        echo "ERROR: Query not found: $query_name" >&2
        return 1
    fi

    echo "$query"
}

# =============================================================================
# REST ENDPOINT LOADING
# =============================================================================

# Get REST endpoint template from gh-rest-endpoints.yaml
# Usage: get_rest_endpoint DOMAIN ENDPOINT_NAME
# Example: get_rest_endpoint "milestone" "list_milestones"
get_rest_endpoint() {
    local domain="$1"
    local endpoint_name="$2"

    local project_root=$(get_project_root)
    local endpoints_file="${project_root}/lib/github/gh-rest-endpoints.yaml"

    if [[ ! -f "$endpoints_file" ]]; then
        echo "ERROR: Endpoints file not found: $endpoints_file" >&2
        return 1
    fi

    local endpoint=$(yq ".endpoints.${domain}.${endpoint_name}" "$endpoints_file")

    if [[ -z "$endpoint" ]] || [[ "$endpoint" == "null" ]]; then
        echo "ERROR: Endpoint not found: ${domain}.${endpoint_name}" >&2
        return 1
    fi

    echo "$endpoint"
}

# =============================================================================
# FUNCTION LIBRARY SOURCING
# =============================================================================

# Source a domain's function library
# Usage: source_domain_lib DOMAIN
# Example: source_domain_lib "milestone"
source_domain_lib() {
    local domain="$1"

    local project_root=$(get_project_root)
    local lib_file="${project_root}/lib/github/gh-${domain}-functions.sh"

    if [[ ! -f "$lib_file" ]]; then
        echo "ERROR: Function library not found: $lib_file" >&2
        return 1
    fi

    source "$lib_file"
}

# =============================================================================
# FIXTURE VALIDATION
# =============================================================================

# Check if a fixture exists
# Usage: fixture_exists DOMAIN FIXTURE_NAME [TYPE]
fixture_exists() {
    local domain="$1"
    local fixture_name="$2"
    local type="${3:-graphql}"

    local fixtures_root=$(get_fixtures_root)
    local fixture_path="${fixtures_root}/${type}/${domain}/${fixture_name}.json"

    [[ -f "$fixture_path" ]] || [[ -f "${fixtures_root}/${type}/${domain}/${fixture_name}" ]]
}

# List available fixtures for a domain
# Usage: list_fixtures DOMAIN [TYPE]
list_fixtures() {
    local domain="$1"
    local type="${2:-graphql}"

    local fixtures_root=$(get_fixtures_root)
    local fixtures_dir="${fixtures_root}/${type}/${domain}"

    if [[ ! -d "$fixtures_dir" ]]; then
        echo "No fixtures directory for ${type}/${domain}" >&2
        return 1
    fi

    find "$fixtures_dir" -type f -name "*.json" -exec basename {} .json \; | sort
}

# =============================================================================
# FIXTURE TEMPLATING (for parameterized fixtures)
# =============================================================================

# Load fixture with variable substitution
# Usage: load_fixture_with_vars DOMAIN FIXTURE_NAME VAR1=value1 VAR2=value2 ...
# Variables in fixture use ${VAR_NAME} syntax
load_fixture_with_vars() {
    local domain="$1"
    local fixture_name="$2"
    shift 2
    local vars=("$@")

    local fixture_content=$(load_fixture "$domain" "$fixture_name")

    # Apply variable substitutions
    for var_assignment in "${vars[@]}"; do
        local var_name="${var_assignment%%=*}"
        local var_value="${var_assignment#*=}"

        # Use sed to replace ${VAR_NAME} with value
        fixture_content=$(echo "$fixture_content" | sed "s/\${${var_name}}/${var_value}/g")
    done

    echo "$fixture_content"
}

# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# For tests that still use old fixture locations
# Usage: load_legacy_fixture RELATIVE_PATH
load_legacy_fixture() {
    local relative_path="$1"
    local test_dir="$BATS_TEST_DIRNAME"

    local legacy_path="${test_dir}/${relative_path}"

    if [[ ! -f "$legacy_path" ]]; then
        echo "ERROR: Legacy fixture not found: $legacy_path" >&2
        return 1
    fi

    cat "$legacy_path"
}
