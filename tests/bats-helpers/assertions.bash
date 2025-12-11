#!/usr/bin/env bash
# Enhanced assertions for BATS tests
# Provides JSON-specific and API-focused assertion helpers

# =============================================================================
# JSON ASSERTIONS
# =============================================================================

# Assert that two JSON structures are deeply equal
# Usage: assert_json_equals EXPECTED ACTUAL
assert_json_equals() {
    local expected="$1"
    local actual="$2"

    local expected_sorted=$(echo "$expected" | jq -S '.')
    local actual_sorted=$(echo "$actual" | jq -S '.')

    if [[ "$expected_sorted" != "$actual_sorted" ]]; then
        echo "JSON structures are not equal"
        echo "Expected:"
        echo "$expected_sorted" | head -20
        echo "Actual:"
        echo "$actual_sorted" | head -20
        return 1
    fi
}

# Assert that JSON contains specific fields/values (partial match)
# Usage: assert_json_contains JSON FRAGMENT
assert_json_contains() {
    local json="$1"
    local fragment="$2"

    # Check if all keys in fragment exist in json with matching values
    local result=$(jq -n --argjson json "$json" --argjson frag "$fragment" '
        $json | contains($frag)
    ')

    if [[ "$result" != "true" ]]; then
        echo "JSON does not contain expected fragment"
        echo "JSON:"
        echo "$json" | jq '.' | head -20
        echo "Expected to contain:"
        echo "$fragment" | jq '.'
        return 1
    fi
}

# Assert that JSON has all specified keys
# Usage: assert_json_has_keys JSON KEY1 KEY2 ...
assert_json_has_keys() {
    local json="$1"
    shift
    local keys=("$@")

    for key in "${keys[@]}"; do
        local has_key=$(echo "$json" | jq -e "has(\"$key\")" 2>/dev/null)
        if [[ "$has_key" != "true" ]]; then
            echo "JSON missing required key: $key"
            echo "Available keys: $(echo "$json" | jq -r 'keys | join(", ")')"
            return 1
        fi
    done
}

# Assert array length
# Usage: assert_json_array_length JSON_ARRAY EXPECTED_LENGTH
assert_json_array_length() {
    local json="$1"
    local expected="$2"

    local actual=$(echo "$json" | jq 'length')

    if [[ "$actual" != "$expected" ]]; then
        echo "Array length mismatch"
        echo "Expected: $expected"
        echo "Actual: $actual"
        return 1
    fi
}

# Assert array is not empty
# Usage: assert_json_array_not_empty JSON_ARRAY
assert_json_array_not_empty() {
    local json="$1"

    local length=$(echo "$json" | jq 'length')

    if [[ "$length" == "0" ]]; then
        echo "Array is empty (expected non-empty)"
        return 1
    fi
}

# Assert JSON value type
# Usage: assert_json_type JSON_VALUE EXPECTED_TYPE
# EXPECTED_TYPE can be: string, number, boolean, array, object, null
assert_json_type() {
    local json="$1"
    local expected_type="$2"

    local actual_type=$(echo "$json" | jq -r 'type')

    if [[ "$actual_type" != "$expected_type" ]]; then
        echo "JSON type mismatch"
        echo "Expected: $expected_type"
        echo "Actual: $actual_type"
        echo "Value: $(echo "$json" | jq '.')"
        return 1
    fi
}

# =============================================================================
# API RESPONSE ASSERTIONS
# =============================================================================

# Assert that API response indicates success
# Usage: assert_api_success RESPONSE
assert_api_success() {
    local response="$1"

    # Check if response has error field
    local has_errors=$(echo "$response" | jq -e 'has("errors")' 2>/dev/null)
    if [[ "$has_errors" == "true" ]]; then
        echo "API response contains errors:"
        echo "$response" | jq '.errors'
        return 1
    fi

    # Check for GraphQL data field
    local has_data=$(echo "$response" | jq -e 'has("data")' 2>/dev/null)
    if [[ "$has_data" == "true" ]]; then
        local data_is_null=$(echo "$response" | jq -e '.data == null' 2>/dev/null)
        if [[ "$data_is_null" == "true" ]]; then
            echo "API response data field is null"
            return 1
        fi
    fi
}

# Assert that JSON is valid
# Usage: assert_valid_json STRING
assert_valid_json() {
    local json="$1"

    if ! echo "$json" | jq '.' >/dev/null 2>&1; then
        echo "Invalid JSON:"
        echo "$json" | head -20
        return 1
    fi
}

# Assert that output matches expected pattern
# Usage: assert_output_matches PATTERN
assert_output_matches() {
    local pattern="$1"

    if ! echo "$output" | grep -qE "$pattern"; then
        echo "Output does not match pattern: $pattern"
        echo "Actual output:"
        echo "$output" | head -20
        return 1
    fi
}

# Assert that output does not match pattern
# Usage: assert_output_not_matches PATTERN
assert_output_not_matches() {
    local pattern="$1"

    if echo "$output" | grep -qE "$pattern"; then
        echo "Output unexpectedly matches pattern: $pattern"
        echo "Actual output:"
        echo "$output" | head -20
        return 1
    fi
}

# =============================================================================
# FIELD VALIDATION ASSERTIONS
# =============================================================================

# Assert that field exists and is not null
# Usage: assert_field_not_null JSON PATH
assert_field_not_null() {
    local json="$1"
    local path="$2"

    local value=$(echo "$json" | jq -r "$path" 2>/dev/null)

    if [[ "$value" == "null" ]] || [[ -z "$value" ]]; then
        echo "Field is null or missing: $path"
        echo "JSON:"
        echo "$json" | jq '.' | head -20
        return 1
    fi
}

# Assert that field equals expected value
# Usage: assert_field_equals JSON PATH EXPECTED_VALUE
assert_field_equals() {
    local json="$1"
    local path="$2"
    local expected="$3"

    local actual=$(echo "$json" | jq -r "$path" 2>/dev/null)

    if [[ "$actual" != "$expected" ]]; then
        echo "Field value mismatch at path: $path"
        echo "Expected: $expected"
        echo "Actual: $actual"
        return 1
    fi
}

# Assert that field matches regex pattern
# Usage: assert_field_matches JSON PATH PATTERN
assert_field_matches() {
    local json="$1"
    local path="$2"
    local pattern="$3"

    local value=$(echo "$json" | jq -r "$path" 2>/dev/null)

    if ! echo "$value" | grep -qE "$pattern"; then
        echo "Field value does not match pattern: $path"
        echo "Pattern: $pattern"
        echo "Actual: $value"
        return 1
    fi
}

# =============================================================================
# TABULAR OUTPUT ASSERTIONS
# =============================================================================

# Assert that TSV output has expected number of rows (excluding header)
# Usage: assert_tsv_row_count TSV_OUTPUT EXPECTED_COUNT
assert_tsv_row_count() {
    local output="$1"
    local expected="$2"

    # Count rows excluding header
    local actual=$(echo "$output" | tail -n +2 | wc -l)

    if [[ "$actual" != "$expected" ]]; then
        echo "TSV row count mismatch"
        echo "Expected: $expected"
        echo "Actual: $actual"
        return 1
    fi
}

# Assert that TSV has specific header columns
# Usage: assert_tsv_headers TSV_OUTPUT COLUMN1 COLUMN2 ...
assert_tsv_headers() {
    local output="$1"
    shift
    local expected_headers=("$@")

    local header_line=$(echo "$output" | head -1)

    for header in "${expected_headers[@]}"; do
        if ! echo "$header_line" | grep -q "$header"; then
            echo "Missing expected header: $header"
            echo "Actual headers: $header_line"
            return 1
        fi
    done
}

# =============================================================================
# GITHUB-SPECIFIC ASSERTIONS
# =============================================================================

# Assert that value is a valid GitHub node ID
# Usage: assert_valid_github_node_id VALUE
assert_valid_github_node_id() {
    local value="$1"

    # GitHub node IDs are base64-encoded strings starting with specific prefixes
    if ! echo "$value" | grep -qE '^[A-Za-z0-9_-]+$'; then
        echo "Invalid GitHub node ID format: $value"
        return 1
    fi
}

# Assert that value is a valid ISO 8601 timestamp
# Usage: assert_valid_iso8601_timestamp VALUE
assert_valid_iso8601_timestamp() {
    local value="$1"

    # Basic ISO 8601 format check
    if ! echo "$value" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'; then
        echo "Invalid ISO 8601 timestamp: $value"
        return 1
    fi
}

# Assert that value is a valid GitHub repository full name (owner/repo)
# Usage: assert_valid_repo_full_name VALUE
assert_valid_repo_full_name() {
    local value="$1"

    if ! echo "$value" | grep -qE '^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$'; then
        echo "Invalid repository full name format: $value"
        echo "Expected format: owner/repo"
        return 1
    fi
}
