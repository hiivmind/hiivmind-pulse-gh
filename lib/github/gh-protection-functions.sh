#!/bin/bash
# GitHub Protection Domain Functions
# Shell functions for branch protection rules and repository rulesets
# Source this file to use: source gh-protection-functions.sh
#
# This domain provides a unified interface for:
# - Legacy Branch Protection Rules (per-branch, REST-primary)
# - Modern Repository Rulesets (pattern-based, GraphQL-primary)
# - Organization Rulesets (org-wide rules)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Get the directory where this script is located
_get_protection_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [[ -h "$source" ]]; do
        local dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ "$source" != /* ]] && source="$dir/$source"
    done
    echo "$(cd -P "$(dirname "$source")" && pwd)"
}

# Load jq filters from YAML
_get_protection_filter() {
    local filter_path="$1"
    local script_dir
    script_dir=$(_get_protection_script_dir)
    yq -r "$filter_path" "$script_dir/gh-protection-jq-filters.yaml"
}

# Load GraphQL query from YAML
_get_protection_query() {
    local query_path="$1"
    local script_dir
    script_dir=$(_get_protection_script_dir)
    yq -r "$query_path" "$script_dir/gh-protection-graphql-queries.yaml"
}

# =============================================================================
# FETCH PRIMITIVES - Branch Protection (REST)
# =============================================================================

# Fetch branch protection rules for a specific branch
# Args: owner, repo, branch
# Output: JSON protection configuration
fetch_branch_protection() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: fetch_branch_protection requires owner, repo, and branch" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/branches/$branch/protection" \
        -H "Accept: application/vnd.github+json" 2>/dev/null
}

# Fetch branch protection via GraphQL (richer data model)
# Args: owner, repo, pattern
# Output: JSON with branch protection rule details
fetch_branch_protection_graphql() {
    local owner="$1"
    local repo="$2"
    local pattern="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$pattern" ]]; then
        echo "ERROR: fetch_branch_protection_graphql requires owner, repo, and pattern" >&2
        return 2
    fi

    local query
    query=$(_get_protection_query '.queries.branch_protection_by_pattern')

    gh api graphql \
        -H "X-Github-Next-Global-ID: 1" \
        -f query="$query" \
        -f owner="$owner" \
        -f repo="$repo" \
        -f pattern="$pattern"
}

# =============================================================================
# FETCH PRIMITIVES - Repository Rulesets (REST)
# =============================================================================

# Fetch all rulesets for a repository
# Args: owner, repo, [include_parents=true]
# Output: JSON array of rulesets
fetch_repo_rulesets() {
    local owner="$1"
    local repo="$2"
    local include_parents="${3:-true}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: fetch_repo_rulesets requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/rulesets?includes_parents=$include_parents" \
        -H "Accept: application/vnd.github+json"
}

# Fetch all rulesets for a repository via GraphQL
# Args: owner, repo, [targets]
# Output: JSON with rulesets
fetch_repo_rulesets_graphql() {
    local owner="$1"
    local repo="$2"
    local targets="${3:-}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: fetch_repo_rulesets_graphql requires owner and repo" >&2
        return 2
    fi

    local query
    query=$(_get_protection_query '.queries.repo_rulesets')

    if [[ -n "$targets" ]]; then
        gh api graphql \
            -H "X-Github-Next-Global-ID: 1" \
            -f query="$query" \
            -f owner="$owner" \
            -f repo="$repo" \
            -f targets="$targets"
    else
        gh api graphql \
            -H "X-Github-Next-Global-ID: 1" \
            -f query="$query" \
            -f owner="$owner" \
            -f repo="$repo"
    fi
}

# Fetch a specific ruleset by ID
# Args: owner, repo, ruleset_id
# Output: JSON ruleset details
fetch_ruleset() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$ruleset_id" ]]; then
        echo "ERROR: fetch_ruleset requires owner, repo, and ruleset_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/rulesets/$ruleset_id" \
        -H "Accept: application/vnd.github+json"
}

# Fetch a ruleset by name
# Args: owner, repo, name
# Output: JSON ruleset details (first match)
fetch_ruleset_by_name() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$name" ]]; then
        echo "ERROR: fetch_ruleset_by_name requires owner, repo, and name" >&2
        return 2
    fi

    fetch_repo_rulesets "$owner" "$repo" | \
        jq -r --arg name "$name" '.[] | select(.name == $name)'
}

# =============================================================================
# FETCH PRIMITIVES - Organization Rulesets
# =============================================================================

# Fetch all rulesets for an organization
# Args: org
# Output: JSON array of rulesets
fetch_org_rulesets() {
    local org="$1"

    if [[ -z "$org" ]]; then
        echo "ERROR: fetch_org_rulesets requires org" >&2
        return 2
    fi

    gh api "orgs/$org/rulesets" \
        -H "Accept: application/vnd.github+json"
}

# Fetch organization rulesets via GraphQL
# Args: org
# Output: JSON with rulesets
fetch_org_rulesets_graphql() {
    local org="$1"

    if [[ -z "$org" ]]; then
        echo "ERROR: fetch_org_rulesets_graphql requires org" >&2
        return 2
    fi

    local query
    query=$(_get_protection_query '.queries.org_rulesets')

    gh api graphql \
        -H "X-Github-Next-Global-ID: 1" \
        -f query="$query" \
        -f org="$org"
}

# =============================================================================
# DISCOVER PRIMITIVES
# =============================================================================

# Discover all branch protection rules for a repository
# Args: owner, repo
# Output: JSON array of branch protection rules
discover_repo_branch_protections() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_branch_protections requires owner and repo" >&2
        return 2
    fi

    local query
    query=$(_get_protection_query '.queries.repo_branch_protection_rules')

    gh api graphql \
        -H "X-Github-Next-Global-ID: 1" \
        -f query="$query" \
        -f owner="$owner" \
        -f repo="$repo"
}

# Discover all rulesets for a repository (alias for fetch_repo_rulesets)
# Args: owner, repo
# Output: JSON array of rulesets
discover_repo_rulesets() {
    local owner="$1"
    local repo="$2"

    fetch_repo_rulesets "$owner" "$repo" "true"
}

# Discover all rulesets for an organization (alias for fetch_org_rulesets)
# Args: org
# Output: JSON array of rulesets
discover_org_rulesets() {
    local org="$1"

    fetch_org_rulesets "$org"
}

# Discover all rules that apply to a specific branch
# Args: owner, repo, branch
# Output: JSON array of rules
discover_rules_for_branch() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: discover_rules_for_branch requires owner, repo, and branch" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/rules/branches/$branch" \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# LOOKUP PRIMITIVES
# =============================================================================

# Get branch protection rule node ID by pattern
# Args: owner, repo, pattern
# Output: Node ID string
get_branch_protection_rule_id() {
    local owner="$1"
    local repo="$2"
    local pattern="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$pattern" ]]; then
        echo "ERROR: get_branch_protection_rule_id requires owner, repo, and pattern" >&2
        return 2
    fi

    discover_repo_branch_protections "$owner" "$repo" | \
        jq -r --arg pattern "$pattern" \
        '.data.repository.branchProtectionRules.nodes[] | select(.pattern == $pattern) | .id'
}

# Get ruleset ID by name
# Args: owner, repo, name
# Output: Ruleset ID (numeric)
get_ruleset_id() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$name" ]]; then
        echo "ERROR: get_ruleset_id requires owner, repo, and name" >&2
        return 2
    fi

    fetch_repo_rulesets "$owner" "$repo" | \
        jq -r --arg name "$name" '.[] | select(.name == $name) | .id' | head -1
}

# Get organization ruleset ID by name
# Args: org, name
# Output: Ruleset ID (numeric)
get_org_ruleset_id() {
    local org="$1"
    local name="$2"

    if [[ -z "$org" || -z "$name" ]]; then
        echo "ERROR: get_org_ruleset_id requires org and name" >&2
        return 2
    fi

    fetch_org_rulesets "$org" | \
        jq -r --arg name "$name" '.[] | select(.name == $name) | .id' | head -1
}

# =============================================================================
# DETECT PRIMITIVES
# =============================================================================

# Check if branch protection exists (returns 0 if exists, 1 if not)
# Args: owner, repo, branch
# Output: exit code
detect_branch_protection_exists() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: detect_branch_protection_exists requires owner, repo, and branch" >&2
        return 2
    fi

    if gh api "repos/$owner/$repo/branches/$branch/protection" --silent 2>/dev/null; then
        return 0  # Protection exists
    else
        return 1  # No protection
    fi
}

# Check if ruleset exists by name (returns 0 if exists, 1 if not)
# Args: owner, repo, name
# Output: exit code
detect_ruleset_exists() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$name" ]]; then
        echo "ERROR: detect_ruleset_exists requires owner, repo, and name" >&2
        return 2
    fi

    local ruleset_id
    ruleset_id=$(get_ruleset_id "$owner" "$repo" "$name")

    if [[ -n "$ruleset_id" ]]; then
        return 0  # Ruleset exists
    else
        return 1  # No ruleset
    fi
}

# Detect where protection comes from for a branch
# Args: owner, repo, branch
# Output: "branch_rule", "repo_ruleset", "org_ruleset", or "none"
detect_protection_source() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: detect_protection_source requires owner, repo, and branch" >&2
        return 2
    fi

    # Check branch protection first
    if detect_branch_protection_exists "$owner" "$repo" "$branch"; then
        echo "branch_rule"
        return 0
    fi

    # Check rulesets
    local rules
    rules=$(discover_rules_for_branch "$owner" "$repo" "$branch" 2>/dev/null)

    if [[ -n "$rules" && "$rules" != "[]" ]]; then
        local source_type
        source_type=$(echo "$rules" | jq -r '.[0].source_type // empty')

        case "$source_type" in
            "Organization")
                echo "org_ruleset"
                ;;
            "Repository")
                echo "repo_ruleset"
                ;;
            *)
                echo "repo_ruleset"
                ;;
        esac
        return 0
    fi

    echo "none"
}

# =============================================================================
# FILTER PRIMITIVES (stdin → stdout)
# =============================================================================

# Filter rulesets by target (BRANCH, TAG, PUSH, REPOSITORY)
# Input: JSON array of rulesets from stdin
# Args: target
# Output: Filtered JSON array
filter_rulesets_by_target() {
    local target="$1"

    if [[ -z "$target" ]]; then
        echo "ERROR: filter_rulesets_by_target requires target" >&2
        return 2
    fi

    jq --arg target "$target" '[.[] | select(.target == $target)]'
}

# Filter rulesets by enforcement level (active, evaluate, disabled)
# Input: JSON array of rulesets from stdin
# Args: enforcement
# Output: Filtered JSON array
filter_rulesets_by_enforcement() {
    local enforcement="$1"

    if [[ -z "$enforcement" ]]; then
        echo "ERROR: filter_rulesets_by_enforcement requires enforcement" >&2
        return 2
    fi

    jq --arg enforcement "$enforcement" '[.[] | select(.enforcement == $enforcement)]'
}

# Filter rules by type
# Input: JSON array of rules from stdin
# Args: type (e.g., "pull_request", "required_status_checks")
# Output: Filtered JSON array
filter_rules_by_type() {
    local rule_type="$1"

    if [[ -z "$rule_type" ]]; then
        echo "ERROR: filter_rules_by_type requires type" >&2
        return 2
    fi

    jq --arg type "$rule_type" '[.[] | select(.type == $type)]'
}

# =============================================================================
# FORMAT PRIMITIVES (stdin → stdout)
# =============================================================================

# Format branch protection for display
# Input: JSON protection config from stdin
# Output: Formatted JSON
format_branch_protection() {
    local filter
    filter=$(_get_protection_filter '.filters.format_branch_protection')
    jq "$filter"
}

# Format rulesets list for display
# Input: JSON array of rulesets from stdin
# Output: Formatted JSON array
format_rulesets() {
    local filter
    filter=$(_get_protection_filter '.filters.format_rulesets_list')
    jq "$filter"
}

# Format single ruleset with detail
# Input: JSON ruleset from stdin
# Output: Formatted JSON
format_ruleset_detail() {
    local filter
    filter=$(_get_protection_filter '.filters.format_ruleset_detail')
    jq "$filter"
}

# Format rules applying to a branch
# Input: JSON array of rules from stdin
# Output: Formatted JSON
format_rules_for_branch() {
    local filter
    filter=$(_get_protection_filter '.filters.format_rules_for_branch')
    jq "$filter"
}

# =============================================================================
# MUTATE PRIMITIVES - Branch Protection (REST)
# =============================================================================

# Set branch protection rules via REST (creates or replaces)
# Args: owner, repo, branch
# Input: JSON config from stdin
# Output: Result JSON
set_branch_protection_rest() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: set_branch_protection_rest requires owner, repo, and branch" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/branches/$branch/protection" \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Delete branch protection via REST
# Args: owner, repo, branch
# Output: empty on success
delete_branch_protection_rest() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$branch" ]]; then
        echo "ERROR: delete_branch_protection_rest requires owner, repo, and branch" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/branches/$branch/protection" \
        --method DELETE \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# MUTATE PRIMITIVES - Branch Protection (GraphQL)
# =============================================================================

# Create branch protection rule via GraphQL
# Args: repo_id, pattern, [additional options as JSON stdin]
# Output: Result JSON
create_branch_protection() {
    local repo_id="$1"
    local pattern="$2"

    if [[ -z "$repo_id" || -z "$pattern" ]]; then
        echo "ERROR: create_branch_protection requires repo_id and pattern" >&2
        return 2
    fi

    # Read additional options from stdin if available
    local options
    if [[ ! -t 0 ]]; then
        options=$(cat)
    else
        options="{}"
    fi

    local mutation
    mutation=$(_get_protection_query '.mutations.create_branch_protection_rule')

    # Merge options with required fields
    local input
    input=$(echo "$options" | jq --arg repo_id "$repo_id" --arg pattern "$pattern" \
        '. + {repositoryId: $repo_id, pattern: $pattern}')

    gh api graphql \
        -H "X-Github-Next-Global-ID: 1" \
        -f query="$mutation" \
        --raw-field input="$input"
}

# Update branch protection rule via GraphQL
# Args: rule_id
# Input: JSON config from stdin
# Output: Result JSON
update_branch_protection() {
    local rule_id="$1"

    if [[ -z "$rule_id" ]]; then
        echo "ERROR: update_branch_protection requires rule_id" >&2
        return 2
    fi

    local options
    options=$(cat)

    local mutation
    mutation=$(_get_protection_query '.mutations.update_branch_protection_rule')

    local input
    input=$(echo "$options" | jq --arg rule_id "$rule_id" \
        '. + {branchProtectionRuleId: $rule_id}')

    gh api graphql \
        -H "X-Github-Next-Global-ID: 1" \
        -f query="$mutation" \
        --raw-field input="$input"
}

# Delete branch protection rule via GraphQL
# Args: rule_id
# Output: Result JSON
delete_branch_protection() {
    local rule_id="$1"

    if [[ -z "$rule_id" ]]; then
        echo "ERROR: delete_branch_protection requires rule_id" >&2
        return 2
    fi

    local mutation
    mutation=$(_get_protection_query '.mutations.delete_branch_protection_rule')

    gh api graphql \
        -H "X-Github-Next-Global-ID: 1" \
        -f query="$mutation" \
        -f ruleId="$rule_id"
}

# =============================================================================
# MUTATE PRIMITIVES - Repository Rulesets (REST)
# =============================================================================

# Create a repository ruleset
# Args: owner, repo
# Input: JSON config from stdin
# Output: Result JSON
create_repo_ruleset() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: create_repo_ruleset requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/rulesets" \
        --method POST \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Update a repository ruleset
# Args: owner, repo, ruleset_id
# Input: JSON config from stdin
# Output: Result JSON
update_repo_ruleset() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$ruleset_id" ]]; then
        echo "ERROR: update_repo_ruleset requires owner, repo, and ruleset_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/rulesets/$ruleset_id" \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Delete a repository ruleset
# Args: owner, repo, ruleset_id
# Output: empty on success
delete_repo_ruleset() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$ruleset_id" ]]; then
        echo "ERROR: delete_repo_ruleset requires owner, repo, and ruleset_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/rulesets/$ruleset_id" \
        --method DELETE \
        -H "Accept: application/vnd.github+json"
}

# Create or update a repository ruleset by name (upsert)
# Args: owner, repo, name
# Input: JSON config from stdin
# Output: Result JSON
upsert_repo_ruleset() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$name" ]]; then
        echo "ERROR: upsert_repo_ruleset requires owner, repo, and name" >&2
        return 2
    fi

    # Read stdin into variable so we can use it twice if needed
    local config
    config=$(cat)

    local ruleset_id
    ruleset_id=$(get_ruleset_id "$owner" "$repo" "$name")

    if [[ -n "$ruleset_id" ]]; then
        # Update existing ruleset
        echo "$config" | update_repo_ruleset "$owner" "$repo" "$ruleset_id"
    else
        # Create new ruleset
        echo "$config" | create_repo_ruleset "$owner" "$repo"
    fi
}

# =============================================================================
# MUTATE PRIMITIVES - Organization Rulesets
# =============================================================================

# Create an organization ruleset
# Args: org
# Input: JSON config from stdin
# Output: Result JSON
create_org_ruleset() {
    local org="$1"

    if [[ -z "$org" ]]; then
        echo "ERROR: create_org_ruleset requires org" >&2
        return 2
    fi

    gh api "orgs/$org/rulesets" \
        --method POST \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Update an organization ruleset
# Args: org, ruleset_id
# Input: JSON config from stdin
# Output: Result JSON
update_org_ruleset() {
    local org="$1"
    local ruleset_id="$2"

    if [[ -z "$org" || -z "$ruleset_id" ]]; then
        echo "ERROR: update_org_ruleset requires org and ruleset_id" >&2
        return 2
    fi

    gh api "orgs/$org/rulesets/$ruleset_id" \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Delete an organization ruleset
# Args: org, ruleset_id
# Output: empty on success
delete_org_ruleset() {
    local org="$1"
    local ruleset_id="$2"

    if [[ -z "$org" || -z "$ruleset_id" ]]; then
        echo "ERROR: delete_org_ruleset requires org and ruleset_id" >&2
        return 2
    fi

    gh api "orgs/$org/rulesets/$ruleset_id" \
        --method DELETE \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# UTILITY FUNCTIONS - Templates
# =============================================================================

# Get a branch protection template by name
# Args: template_name
# Output: JSON configuration
get_protection_template() {
    local template_name="$1"
    local script_dir
    script_dir=$(_get_protection_script_dir)

    if [[ -z "$template_name" ]]; then
        echo "ERROR: get_protection_template requires template_name" >&2
        return 2
    fi

    yq -o=json ".branch_protection.$template_name" "$script_dir/gh-branch-protection-templates.yaml"
}

# Get a ruleset template by name
# Args: template_name
# Output: JSON configuration
get_ruleset_template() {
    local template_name="$1"
    local script_dir
    script_dir=$(_get_protection_script_dir)

    if [[ -z "$template_name" ]]; then
        echo "ERROR: get_ruleset_template requires template_name" >&2
        return 2
    fi

    yq -o=json ".rulesets.$template_name" "$script_dir/gh-branch-protection-templates.yaml"
}

# List available protection templates
# Output: List of template names
list_protection_templates() {
    local script_dir
    script_dir=$(_get_protection_script_dir)

    yq '.branch_protection | keys' "$script_dir/gh-branch-protection-templates.yaml"
}

# List available ruleset templates
# Output: List of template names
list_ruleset_templates() {
    local script_dir
    script_dir=$(_get_protection_script_dir)

    yq '.rulesets | keys' "$script_dir/gh-branch-protection-templates.yaml"
}

# =============================================================================
# UTILITY FUNCTIONS - Smart Apply
# =============================================================================

# Detect repository type (organization vs personal)
# Args: owner, repo
# Output: "organization" or "personal"
_detect_repo_type() {
    local owner="$1"
    local repo="$2"

    local owner_type
    owner_type=$(gh api "repos/$owner/$repo" --jq '.owner.type')

    if [[ "$owner_type" == "Organization" ]]; then
        echo "organization"
    else
        echo "personal"
    fi
}

# Apply main branch protection (auto-detects org vs personal)
# Args: owner, repo
# Output: Result JSON
apply_main_branch_protection() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: apply_main_branch_protection requires owner and repo" >&2
        return 2
    fi

    local repo_type
    repo_type=$(_detect_repo_type "$owner" "$repo")

    local template_name
    if [[ "$repo_type" == "organization" ]]; then
        template_name="main_org"
    else
        template_name="main_personal"
    fi

    get_protection_template "$template_name" | set_branch_protection_rest "$owner" "$repo" "main"
}

# Apply develop branch protection (auto-detects org vs personal)
# Args: owner, repo
# Output: Result JSON
apply_develop_branch_protection() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: apply_develop_branch_protection requires owner and repo" >&2
        return 2
    fi

    local repo_type
    repo_type=$(_detect_repo_type "$owner" "$repo")

    local template_name
    if [[ "$repo_type" == "organization" ]]; then
        template_name="develop_org"
    else
        template_name="develop_personal"
    fi

    get_protection_template "$template_name" | set_branch_protection_rest "$owner" "$repo" "develop"
}

# Apply branch naming convention ruleset
# Args: owner, repo
# Output: Result JSON
apply_branch_naming_ruleset() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: apply_branch_naming_ruleset requires owner and repo" >&2
        return 2
    fi

    get_ruleset_template "branch_naming" | upsert_repo_ruleset "$owner" "$repo" "Branch Naming Convention"
}

# Apply release branch protection ruleset
# Args: owner, repo
# Output: Result JSON
apply_release_branch_ruleset() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: apply_release_branch_ruleset requires owner and repo" >&2
        return 2
    fi

    get_ruleset_template "release_branches" | upsert_repo_ruleset "$owner" "$repo" "Release Branch Protection"
}

# Apply tag protection ruleset
# Args: owner, repo
# Output: Result JSON
apply_tag_protection_ruleset() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: apply_tag_protection_ruleset requires owner and repo" >&2
        return 2
    fi

    get_ruleset_template "tag_protection" | upsert_repo_ruleset "$owner" "$repo" "Tag Protection"
}

# =============================================================================
# COMPOSITION HELPERS
# =============================================================================

# Get protection summary for a repository
# Args: owner, repo
# Output: Summary JSON
get_protection_summary() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: get_protection_summary requires owner and repo" >&2
        return 2
    fi

    local branch_rules
    branch_rules=$(discover_repo_branch_protections "$owner" "$repo" 2>/dev/null | \
        jq '.data.repository.branchProtectionRules.totalCount // 0')

    local rulesets
    rulesets=$(fetch_repo_rulesets "$owner" "$repo" 2>/dev/null | jq 'length // 0')

    jq -n \
        --arg owner "$owner" \
        --arg repo "$repo" \
        --argjson branch_rules "$branch_rules" \
        --argjson rulesets "$rulesets" \
        '{
            repository: "\($owner)/\($repo)",
            branch_protection_rules: $branch_rules,
            rulesets: $rulesets,
            total_protections: ($branch_rules + $rulesets)
        }'
}
