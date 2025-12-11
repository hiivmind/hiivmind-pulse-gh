#!/usr/bin/env bash
# tests/lib/resources/protection.bash
# Branch protection and ruleset resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# RULESETS - CREATE
# =============================================================================

# Create a repository ruleset and track it for cleanup
# Usage: create_ruleset "owner" "repo" "name" "target" "enforcement" [bypass_actors_json] [conditions_json] [rules_json]
# Output: ruleset id
create_ruleset() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local target="${4:-branch}"           # branch or tag
    local enforcement="${5:-active}"      # active, disabled, evaluate
    local bypass_actors="${6:-[]}"
    local conditions="${7:-}"
    local rules="${8:-[]}"

    # Default conditions if not provided
    if [[ -z "$conditions" ]]; then
        conditions='{"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}'
    fi

    local payload
    payload=$(jq -n \
        --arg name "$name" \
        --arg target "$target" \
        --arg enforcement "$enforcement" \
        --argjson bypass_actors "$bypass_actors" \
        --argjson conditions "$conditions" \
        --argjson rules "$rules" \
        '{
            name: $name,
            target: $target,
            enforcement: $enforcement,
            bypass_actors: $bypass_actors,
            conditions: $conditions,
            rules: $rules
        }')

    local result
    result=$(gh api "repos/${owner}/${repo}/rulesets" \
        -X POST \
        --input - <<< "$payload")

    local ruleset_id
    ruleset_id=$(echo "$result" | jq -r '.id')

    if [[ "$ruleset_id" == "null" || -z "$ruleset_id" ]]; then
        echo "Error: Failed to create ruleset: $result" >&2
        return 1
    fi

    track_resource "ruleset" "${owner}/${repo}/${ruleset_id}"
    echo "$ruleset_id"
}

# Create a simple branch protection ruleset
# Usage: create_branch_ruleset "owner" "repo" "name" [branch_pattern]
# Output: ruleset id
create_branch_ruleset() {
    local owner="$1"
    local repo="$2"
    local name="$3"
    local branch_pattern="${4:-~DEFAULT_BRANCH}"

    local conditions
    conditions=$(jq -n --arg pattern "$branch_pattern" \
        '{ref_name: {include: [$pattern], exclude: []}}')

    local rules='[{"type": "pull_request", "parameters": {"required_approving_review_count": 1}}]'

    create_ruleset "$owner" "$repo" "$name" "branch" "active" "[]" "$conditions" "$rules"
}

# Create a test ruleset with auto-generated name
# Usage: create_test_ruleset "owner" "repo"
# Output: ruleset id
create_test_ruleset() {
    local owner="$1"
    local repo="$2"
    local name
    name=$(generate_resource_name "ruleset")

    create_branch_ruleset "$owner" "$repo" "$name"
}

# =============================================================================
# RULESETS - READ
# =============================================================================

# Get ruleset by id
# Usage: get_ruleset "owner" "repo" "ruleset_id"
get_ruleset() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    gh api "repos/${owner}/${repo}/rulesets/${ruleset_id}"
}

# Get ruleset by name
# Usage: get_ruleset_by_name "owner" "repo" "name"
get_ruleset_by_name() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    gh api "repos/${owner}/${repo}/rulesets" \
        --jq ".[] | select(.name == \"${name}\")"
}

# List all ruleset ids
# Usage: list_rulesets "owner" "repo"
# Output: ruleset ids, one per line
list_rulesets() {
    local owner="$1"
    local repo="$2"

    gh api "repos/${owner}/${repo}/rulesets?per_page=100" \
        --jq '.[].id'
}

# Check if ruleset exists
# Usage: ruleset_exists "owner" "repo" "ruleset_id"
ruleset_exists() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    gh api "repos/${owner}/${repo}/rulesets/${ruleset_id}" &>/dev/null
}

# =============================================================================
# RULESETS - UPDATE
# =============================================================================

# Update ruleset enforcement
# Usage: update_ruleset_enforcement "owner" "repo" "ruleset_id" "enforcement"
update_ruleset_enforcement() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"
    local enforcement="$4"

    gh api "repos/${owner}/${repo}/rulesets/${ruleset_id}" \
        -X PUT \
        -f "enforcement=${enforcement}"
}

# Disable ruleset
# Usage: disable_ruleset "owner" "repo" "ruleset_id"
disable_ruleset() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    update_ruleset_enforcement "$owner" "$repo" "$ruleset_id" "disabled"
}

# =============================================================================
# RULESETS - DELETE
# =============================================================================

# Delete ruleset by identifier
# Usage: delete_ruleset "owner/repo/ruleset_id"
delete_ruleset() {
    local identifier="$1"

    parse_owner_repo_number "$identifier"

    gh api -X DELETE "repos/${PARSED_OWNER}/${PARSED_REPO}/rulesets/${PARSED_NUMBER}" \
        2>/dev/null || true
}

# Delete ruleset by parts
# Usage: delete_ruleset_by_parts "owner" "repo" "ruleset_id"
delete_ruleset_by_parts() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    gh api -X DELETE "repos/${owner}/${repo}/rulesets/${ruleset_id}" \
        2>/dev/null || true
}

# =============================================================================
# BRANCH PROTECTION (Legacy API)
# =============================================================================

# Set branch protection (legacy API)
# Usage: set_branch_protection "owner" "repo" "branch" [require_reviews] [required_approvals]
set_branch_protection() {
    local owner="$1"
    local repo="$2"
    local branch="$3"
    local require_reviews="${4:-true}"
    local required_approvals="${5:-1}"

    local payload
    if [[ "$require_reviews" == "true" ]]; then
        payload=$(jq -n \
            --argjson approvals "$required_approvals" \
            '{
                required_status_checks: null,
                enforce_admins: false,
                required_pull_request_reviews: {
                    required_approving_review_count: $approvals
                },
                restrictions: null
            }')
    else
        payload=$(jq -n '{
            required_status_checks: null,
            enforce_admins: false,
            required_pull_request_reviews: null,
            restrictions: null
        }')
    fi

    gh api "repos/${owner}/${repo}/branches/${branch}/protection" \
        -X PUT \
        --input - <<< "$payload"

    track_resource "branch_protection" "${owner}/${repo}/${branch}"
}

# Get branch protection
# Usage: get_branch_protection "owner" "repo" "branch"
get_branch_protection() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    gh api "repos/${owner}/${repo}/branches/${branch}/protection"
}

# Delete branch protection
# Usage: delete_branch_protection "owner/repo/branch"
delete_branch_protection() {
    local identifier="$1"

    local owner="${identifier%%/*}"
    local rest="${identifier#*/}"
    local repo="${rest%%/*}"
    local branch="${rest#*/}"

    gh api -X DELETE "repos/${owner}/${repo}/branches/${branch}/protection" \
        2>/dev/null || true
}
