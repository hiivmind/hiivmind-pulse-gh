#!/bin/bash
# GitHub REST API Functions
# Shell functions for REST API operations not available via GraphQL
# Source this file to use: source gh-rest-functions.sh

# =============================================================================
# MILESTONE FUNCTIONS
# =============================================================================
# Note: Creating/updating/closing milestones requires REST API.
# For reading milestones and setting them on issues/PRs, use GraphQL functions
# in gh-project-functions.sh (fetch_repo_milestones, set_issue_milestone, etc.)

# List milestones for a repository
list_milestones() {
    local owner="$1"
    local repo="$2"
    local state="${3:-open}"  # open, closed, or all
    local sort="${4:-due_on}"  # due_on or completeness
    local direction="${5:-asc}"  # asc or desc

    gh api "repos/$owner/$repo/milestones" \
        -f state="$state" \
        -f sort="$sort" \
        -f direction="$direction"
}

# Get a specific milestone by number
get_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    gh api "repos/$owner/$repo/milestones/$milestone_number"
}

# Create a new milestone
create_milestone() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local description="${4:-}"
    local due_on="${5:-}"  # ISO 8601 format: 2024-12-31T00:00:00Z
    local state="${6:-open}"

    local args=(-X POST)
    args+=(-f title="$title")
    args+=(-f state="$state")
    [[ -n "$description" ]] && args+=(-f description="$description")
    [[ -n "$due_on" ]] && args+=(-f due_on="$due_on")

    gh api "repos/$owner/$repo/milestones" "${args[@]}"
}

# Update an existing milestone
update_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"
    local title="${4:-}"
    local description="${5:-}"
    local due_on="${6:-}"
    local state="${7:-}"  # open or closed

    local args=(-X PATCH)
    [[ -n "$title" ]] && args+=(-f title="$title")
    [[ -n "$description" ]] && args+=(-f description="$description")
    [[ -n "$due_on" ]] && args+=(-f due_on="$due_on")
    [[ -n "$state" ]] && args+=(-f state="$state")

    gh api "repos/$owner/$repo/milestones/$milestone_number" "${args[@]}"
}

# Close a milestone
close_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    gh api "repos/$owner/$repo/milestones/$milestone_number" -X PATCH -f state="closed"
}

# Reopen a milestone
reopen_milestone() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    gh api "repos/$owner/$repo/milestones/$milestone_number" -X PATCH -f state="open"
}

# =============================================================================
# MILESTONE HELPER FUNCTIONS
# =============================================================================

# Get milestone number by title (returns first match)
get_milestone_number_by_title() {
    local owner="$1"
    local repo="$2"
    local title="$3"

    list_milestones "$owner" "$repo" "all" | \
        jq -r --arg title "$title" '.[] | select(.title == $title) | .number' | head -1
}

# Format milestones for display
format_milestones() {
    jq '[.[] | {
        number: .number,
        title: .title,
        state: .state,
        description: (.description // ""),
        due_on: (.due_on // "No due date"),
        open_issues: .open_issues,
        closed_issues: .closed_issues,
        progress: (if (.open_issues + .closed_issues) > 0
                   then ((.closed_issues / (.open_issues + .closed_issues)) * 100 | floor | tostring) + "%"
                   else "0%" end),
        url: .html_url
    }]'
}

# Get milestone progress summary
get_milestone_progress() {
    local owner="$1"
    local repo="$2"
    local milestone_number="$3"

    get_milestone "$owner" "$repo" "$milestone_number" | \
        jq '{
            title: .title,
            state: .state,
            open_issues: .open_issues,
            closed_issues: .closed_issues,
            total: (.open_issues + .closed_issues),
            progress_percent: (if (.open_issues + .closed_issues) > 0
                              then ((.closed_issues / (.open_issues + .closed_issues)) * 100 | floor)
                              else 0 end),
            due_on: (.due_on // "No due date")
        }'
}

# =============================================================================
# BRANCH PROTECTION FUNCTIONS
# =============================================================================
# Note: Branch protection applies to specific branches (main, develop, etc.)
# For pattern-based protection (feature/*, release/*), use Rulesets below.

# Get branch protection rules for a specific branch
get_branch_protection() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    gh api "repos/$owner/$repo/branches/$branch/protection" \
        -H "Accept: application/vnd.github+json"
}

# Check if branch protection exists (returns 0 if exists, 1 if not)
check_branch_protection_exists() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if gh api "repos/$owner/$repo/branches/$branch/protection" --silent 2>/dev/null; then
        return 0  # Protection exists
    else
        return 1  # No protection
    fi
}

# Set branch protection rules (reads JSON config from stdin)
# Usage: echo '{"enforce_admins": true, ...}' | set_branch_protection "owner" "repo" "branch"
# Or: set_branch_protection "owner" "repo" "branch" < config.json
set_branch_protection() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    gh api "repos/$owner/$repo/branches/$branch/protection" \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Format branch protection for display
format_branch_protection() {
    jq '{
        enforce_admins: .enforce_admins.enabled,
        required_status_checks: (if .required_status_checks then {
            strict: .required_status_checks.strict,
            contexts: .required_status_checks.contexts
        } else null end),
        required_pull_request_reviews: (if .required_pull_request_reviews then {
            required_approving_review_count: .required_pull_request_reviews.required_approving_review_count,
            dismiss_stale_reviews: .required_pull_request_reviews.dismiss_stale_reviews,
            require_code_owner_reviews: .required_pull_request_reviews.require_code_owner_reviews,
            require_last_push_approval: .required_pull_request_reviews.require_last_push_approval
        } else null end),
        restrictions: (if .restrictions then {
            users: [.restrictions.users[].login],
            teams: [.restrictions.teams[].slug],
            apps: [.restrictions.apps[].slug]
        } else null end),
        required_linear_history: .required_linear_history.enabled,
        allow_force_pushes: .allow_force_pushes.enabled,
        allow_deletions: .allow_deletions.enabled,
        required_conversation_resolution: .required_conversation_resolution.enabled,
        required_signatures: .required_signatures.enabled,
        lock_branch: .lock_branch.enabled,
        allow_fork_syncing: .allow_fork_syncing.enabled
    }'
}

# =============================================================================
# RULESET FUNCTIONS
# =============================================================================
# Note: Rulesets are the modern replacement for branch protection rules.
# They support pattern matching (feature/*, release/*) and more rule types.

# List all rulesets for a repository
list_rulesets() {
    local owner="$1"
    local repo="$2"
    local includes_parents="${3:-true}"

    gh api "repos/$owner/$repo/rulesets" \
        -f includes_parents="$includes_parents"
}

# Get a specific ruleset by ID
get_ruleset() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    gh api "repos/$owner/$repo/rulesets/$ruleset_id"
}

# Get a ruleset by name (returns first match)
get_ruleset_by_name() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    list_rulesets "$owner" "$repo" | \
        jq -r --arg name "$name" '.[] | select(.name == $name)'
}

# Check if ruleset exists by name (returns ruleset ID if exists, empty if not)
check_ruleset_exists() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    list_rulesets "$owner" "$repo" | \
        jq -r --arg name "$name" '.[] | select(.name == $name) | .id' | head -1
}

# Create a new ruleset (reads JSON config from stdin)
# Usage: echo '{"name": "...", ...}' | create_ruleset "owner" "repo"
create_ruleset() {
    local owner="$1"
    local repo="$2"

    gh api "repos/$owner/$repo/rulesets" \
        --method POST \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Update an existing ruleset (reads JSON config from stdin)
# Usage: echo '{"name": "...", ...}' | update_ruleset "owner" "repo" "ruleset_id"
update_ruleset() {
    local owner="$1"
    local repo="$2"
    local ruleset_id="$3"

    gh api "repos/$owner/$repo/rulesets/$ruleset_id" \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        --input -
}

# Create or update a ruleset by name (upsert)
# Usage: echo '{"name": "...", ...}' | create_or_update_ruleset "owner" "repo" "ruleset_name"
create_or_update_ruleset() {
    local owner="$1"
    local repo="$2"
    local name="$3"

    # Read stdin into variable so we can use it twice if needed
    local config
    config=$(cat)

    local ruleset_id
    ruleset_id=$(check_ruleset_exists "$owner" "$repo" "$name")

    if [[ -n "$ruleset_id" ]]; then
        # Update existing ruleset
        echo "$config" | update_ruleset "$owner" "$repo" "$ruleset_id"
    else
        # Create new ruleset
        echo "$config" | create_ruleset "$owner" "$repo"
    fi
}

# Format rulesets for display
format_rulesets() {
    jq '[.[] | {
        id: .id,
        name: .name,
        target: .target,
        enforcement: .enforcement,
        source_type: .source_type,
        source: .source,
        conditions: .conditions,
        rules_count: (.rules | length)
    }]'
}

# =============================================================================
# HELPER FUNCTIONS - Repository Info
# =============================================================================

# Detect if repository is personal or organizational
detect_repo_type() {
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

# Get repository information
get_repository() {
    local owner="$1"
    local repo="$2"

    gh api "repos/$owner/$repo"
}

# =============================================================================
# HELPER FUNCTIONS - Branches
# =============================================================================

# List branches for a repository
list_branches() {
    local owner="$1"
    local repo="$2"
    local protected="${3:-}"  # Optional: true/false to filter

    local args=()
    [[ -n "$protected" ]] && args+=(-f protected="$protected")

    gh api --paginate "repos/$owner/$repo/branches" "${args[@]}"
}

# Check if a branch exists (returns 0 if exists, 1 if not)
check_branch_exists() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    if gh api "repos/$owner/$repo/branches/$branch" --silent 2>/dev/null; then
        return 0  # Branch exists
    else
        return 1  # Branch doesn't exist
    fi
}

# Get a specific branch
get_branch() {
    local owner="$1"
    local repo="$2"
    local branch="$3"

    gh api "repos/$owner/$repo/branches/$branch"
}

# Format branches for display
format_branches() {
    jq '[.[] | {
        name: .name,
        protected: .protected,
        commit_sha: .commit.sha,
        commit_url: .commit.url
    }]'
}

# =============================================================================
# TEMPLATE FUNCTIONS - Branch Protection
# =============================================================================
# Get protection templates from gh-branch-protection-templates.yaml

# Get the directory where this script is located
_get_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [[ -h "$source" ]]; do
        local dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ "$source" != /* ]] && source="$dir/$source"
    done
    echo "$(cd -P "$(dirname "$source")" && pwd)"
}

# Get a branch protection template by name
get_protection_template() {
    local template_name="$1"
    local script_dir
    script_dir=$(_get_script_dir)

    yq -o=json ".branch_protection.$template_name" "$script_dir/gh-branch-protection-templates.yaml"
}

# Get a ruleset template by name
get_ruleset_template() {
    local template_name="$1"
    local script_dir
    script_dir=$(_get_script_dir)

    yq -o=json ".rulesets.$template_name" "$script_dir/gh-branch-protection-templates.yaml"
}

# List available protection templates
list_protection_templates() {
    local script_dir
    script_dir=$(_get_script_dir)

    yq '.branch_protection | keys' "$script_dir/gh-branch-protection-templates.yaml"
}

# List available ruleset templates
list_ruleset_templates() {
    local script_dir
    script_dir=$(_get_script_dir)

    yq '.rulesets | keys' "$script_dir/gh-branch-protection-templates.yaml"
}

# =============================================================================
# SMART APPLICATION FUNCTIONS
# =============================================================================
# Convenience functions that auto-detect repo type and apply appropriate templates

# Apply main branch protection (auto-detects org vs personal)
apply_main_branch_protection() {
    local owner="$1"
    local repo="$2"

    local repo_type
    repo_type=$(detect_repo_type "$owner" "$repo")

    local template_name
    if [[ "$repo_type" == "organization" ]]; then
        template_name="main_org"
    else
        template_name="main_personal"
    fi

    get_protection_template "$template_name" | set_branch_protection "$owner" "$repo" "main"
}

# Apply develop branch protection (auto-detects org vs personal)
apply_develop_branch_protection() {
    local owner="$1"
    local repo="$2"

    local repo_type
    repo_type=$(detect_repo_type "$owner" "$repo")

    local template_name
    if [[ "$repo_type" == "organization" ]]; then
        template_name="develop_org"
    else
        template_name="develop_personal"
    fi

    get_protection_template "$template_name" | set_branch_protection "$owner" "$repo" "develop"
}

# Apply branch naming convention ruleset
apply_branch_naming_ruleset() {
    local owner="$1"
    local repo="$2"

    get_ruleset_template "branch_naming" | create_or_update_ruleset "$owner" "$repo" "Branch Naming Convention"
}

# Apply release branch protection ruleset
apply_release_branch_ruleset() {
    local owner="$1"
    local repo="$2"

    get_ruleset_template "release_branches" | create_or_update_ruleset "$owner" "$repo" "Release Branch Protection"
}

# =============================================================================
# Future REST-only functions can be added here
# =============================================================================
