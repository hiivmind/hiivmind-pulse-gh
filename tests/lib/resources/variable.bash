#!/usr/bin/env bash
# tests/lib/resources/variable.bash
# Repository variable resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# CREATE
# =============================================================================

# Create a repository variable without tracking (for use in subshells)
# Usage: create_variable_raw "owner" "repo" "name" "value"
# Output: variable name
create_variable_raw() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local value="$4"

    local result
    result=$(gh api "repos/${owner}/${repo}/actions/variables" \
        -f "name=${name}" -f "value=${value}" 2>&1)

    # Check for success or already exists
    if [[ "$result" == *"already exists"* ]]; then
        # Update existing variable
        gh api "repos/${owner}/${repo}/actions/variables/${name}" \
            -X PATCH -f "value=${value}" >/dev/null
    elif [[ "$result" == *"error"* || "$result" == *"Error"* ]]; then
        echo "Error: Failed to create variable: $result" >&2
        return 1
    fi

    echo "$name"
}

# Create a repository variable and track it for cleanup
# Usage: create_variable "owner" "repo" "name" "value"
# Output: variable name
create_variable() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local result_name
    result_name=$(create_variable_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "variable" "${owner}/${repo}/${result_name}"
        echo "$result_name"
    else
        return 1
    fi
}

# Create a variable with auto-generated name
# Usage: create_test_variable "owner" "repo"
# Output: variable name
create_test_variable() {
    local owner="$1"
    local repo="$2"
    local name
    # Variables must be uppercase with underscores
    name="TEST_VAR_$(date +%s)"

    create_variable "$owner" "$repo" "$name" "test-value-$(date +%s)"
}

# =============================================================================
# READ
# =============================================================================

# Get variable by name
# Usage: get_variable "owner" "repo" "name"
get_variable() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    gh api "repos/${owner}/${repo}/actions/variables/${name}"
}

# List all variable names
# Usage: list_variables "owner" "repo"
# Output: variable names, one per line
list_variables() {
    local owner="$1"
    local repo="$2"

    gh api "repos/${owner}/${repo}/actions/variables?per_page=100" \
        --jq '.variables[].name'
}

# Check if variable exists
# Usage: variable_exists "owner" "repo" "name"
variable_exists() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    gh api "repos/${owner}/${repo}/actions/variables/${name}" &>/dev/null
}

# Get variable value
# Usage: get_variable_value "owner" "repo" "name"
get_variable_value() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    gh api "repos/${owner}/${repo}/actions/variables/${name}" \
        --jq '.value'
}

# =============================================================================
# UPDATE
# =============================================================================

# Update variable
# Usage: update_variable "owner" "repo" "name" "value"
update_variable() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local value="$4"

    gh api "repos/${owner}/${repo}/actions/variables/${name}" \
        -X PATCH -f "value=${value}"
}

# =============================================================================
# DELETE
# =============================================================================

# Delete variable by identifier
# Usage: delete_variable "owner/repo/name"
delete_variable() {
    local identifier="$1"

    local owner="${identifier%%/*}"
    local rest="${identifier#*/}"
    local repo="${rest%%/*}"
    local name="${rest#*/}"

    gh api -X DELETE "repos/${owner}/${repo}/actions/variables/${name}" \
        2>/dev/null || true
}

# Delete variable by parts
# Usage: delete_variable_by_parts "owner" "repo" "name"
delete_variable_by_parts() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    gh api -X DELETE "repos/${owner}/${repo}/actions/variables/${name}" \
        2>/dev/null || true
}

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

# Create an environment variable
# Usage: create_env_variable "owner" "repo" "env_name" "var_name" "value"
create_env_variable() {
    local owner="$1"
    local repo="$2"
    local env_name="$3"
    local var_name="$4"
    local value="$5"

    local repo_id
    repo_id=$(gh api "repos/${owner}/${repo}" --jq '.id')

    gh api "repositories/${repo_id}/environments/${env_name}/variables" \
        -f "name=${var_name}" -f "value=${value}"

    track_resource "env_variable" "${owner}/${repo}/${env_name}/${var_name}"
    echo "$var_name"
}

# Delete environment variable
# Usage: delete_env_variable "owner/repo/env_name/var_name"
delete_env_variable() {
    local identifier="$1"

    local owner="${identifier%%/*}"
    local rest="${identifier#*/}"
    local repo="${rest%%/*}"
    rest="${rest#*/}"
    local env_name="${rest%%/*}"
    local var_name="${rest#*/}"

    local repo_id
    repo_id=$(gh api "repos/${owner}/${repo}" --jq '.id' 2>/dev/null) || return 0

    gh api -X DELETE "repositories/${repo_id}/environments/${env_name}/variables/${var_name}" \
        2>/dev/null || true
}
