#!/bin/bash
# GitHub Entity Investigation Functions
# Source this file to use: source gh-investigate-functions.sh
#
# These functions provide deep-dive investigation of GitHub entities
# (issues, PRs, project items) with full relationship traversal.
#
# Dependencies:
#   - gh (GitHub CLI, authenticated)
#   - jq (1.6+)
#   - yq (4.0+)
#
# Usage:
#   source lib/github/gh-investigate-functions.sh
#
#   # Analyze an issue
#   analyze_issue "owner" "repo" 42
#
#   # Analyze a pull request
#   analyze_pr "owner" "repo" 87
#
#   # Get quick summary
#   get_issue_summary "owner" "repo" 42

set -euo pipefail

# Get the directory where this script is located
INVESTIGATE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

#==============================================================================
# WORKSPACE CONTEXT HELPERS
#==============================================================================

# Get owner from workspace config or fail
get_workspace_owner() {
    local config_path=".hiivmind/github/config.yaml"
    if [[ -f "$config_path" ]]; then
        yq '.workspace.login' "$config_path"
    else
        echo ""
    fi
}

# Get repo from current directory name
get_current_repo() {
    basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || echo ""
}

#==============================================================================
# ISSUE ANALYSIS
#==============================================================================

# Fetch issue with full context (standard depth)
# Args: owner, repo, number
# Outputs JSON with issue data
fetch_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api graphql -f query="
    query {
        repository(owner: \"$owner\", name: \"$repo\") {
            issue(number: $number) {
                id
                number
                title
                body
                state
                stateReason
                createdAt
                updatedAt
                closedAt
                url
                author { login }
                assignees(first: 10) { nodes { login } }
                labels(first: 20) { nodes { name color } }
                milestone {
                    title
                    dueOn
                    state
                }
                projectItems(first: 5) {
                    nodes {
                        project { title number }
                        fieldValues(first: 10) {
                            nodes {
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    name
                                    field { ... on ProjectV2SingleSelectField { name } }
                                }
                                ... on ProjectV2ItemFieldIterationValue {
                                    title
                                    field { ... on ProjectV2IterationField { name } }
                                }
                                ... on ProjectV2ItemFieldTextValue {
                                    text
                                    field { ... on ProjectV2Field { name } }
                                }
                            }
                        }
                    }
                }
                comments(first: 50) {
                    totalCount
                    nodes {
                        author { login }
                        createdAt
                        body
                    }
                }
            }
        }
    }"
}

# Get a quick summary of an issue (shallow depth)
# Args: owner, repo, number
# Outputs formatted text
get_issue_summary() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    local data
    data=$(gh api graphql -f query="
    query {
        repository(owner: \"$owner\", name: \"$repo\") {
            issue(number: $number) {
                number
                title
                state
                author { login }
                assignees(first: 5) { nodes { login } }
                labels(first: 5) { nodes { name } }
                updatedAt
                milestone { title }
            }
        }
    }" --jq '.data.repository.issue')

    local state title author assignees labels updated milestone
    state=$(echo "$data" | jq -r '.state')
    title=$(echo "$data" | jq -r '.title')
    author=$(echo "$data" | jq -r '.author.login')
    assignees=$(echo "$data" | jq -r '[.assignees.nodes[].login] | join(", ")')
    labels=$(echo "$data" | jq -r '[.labels.nodes[].name] | join(", ")')
    updated=$(echo "$data" | jq -r '.updatedAt')
    milestone=$(echo "$data" | jq -r '.milestone.title // "none"')

    echo "Issue #$number: $title"
    echo "State: $state | Author: @$author | Assignees: ${assignees:-none}"
    echo "Labels: ${labels:-none} | Milestone: $milestone"
    echo "Updated: $updated"
}

# Analyze an issue with full context
# Args: owner, repo, number, [depth: shallow|standard|deep]
# Outputs structured analysis
analyze_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local depth="${4:-standard}"

    if [[ "$depth" == "shallow" ]]; then
        get_issue_summary "$owner" "$repo" "$number"
        return
    fi

    local data
    data=$(fetch_issue "$owner" "$repo" "$number")

    # Extract and format
    local issue
    issue=$(echo "$data" | jq '.data.repository.issue')

    echo "=== Issue #$number Analysis ==="
    echo ""

    # Basic info
    echo "Title: $(echo "$issue" | jq -r '.title')"
    echo "URL: $(echo "$issue" | jq -r '.url')"
    echo "State: $(echo "$issue" | jq -r '.state') ($(echo "$issue" | jq -r '.stateReason // "N/A"'))"
    echo "Created: $(echo "$issue" | jq -r '.createdAt')"
    echo "Updated: $(echo "$issue" | jq -r '.updatedAt')"
    echo ""

    # Attribution
    echo "--- Attribution ---"
    echo "Author: @$(echo "$issue" | jq -r '.author.login')"
    local assignees
    assignees=$(echo "$issue" | jq -r '[.assignees.nodes[].login] | join(", ")')
    echo "Assignees: ${assignees:-none}"
    echo ""

    # Labels
    echo "--- Labels ---"
    echo "$issue" | jq -r '.labels.nodes[] | "  - \(.name)"'
    echo ""

    # Milestone
    local milestone
    milestone=$(echo "$issue" | jq -r '.milestone.title // "none"')
    if [[ "$milestone" != "none" ]]; then
        echo "--- Milestone ---"
        echo "Title: $milestone"
        echo "Due: $(echo "$issue" | jq -r '.milestone.dueOn // "no due date"')"
        echo "State: $(echo "$issue" | jq -r '.milestone.state')"
        echo ""
    fi

    # Project status
    echo "--- Project Board ---"
    echo "$issue" | jq -r '
        .projectItems.nodes[] |
        "Project: \(.project.title) (#\(.project.number))",
        (.fieldValues.nodes[] |
            select(.field.name != null) |
            "  \(.field.name): \(.name // .title // .text // "N/A")"
        )
    ' 2>/dev/null || echo "  Not on any project"
    echo ""

    # Comments
    local comment_count
    comment_count=$(echo "$issue" | jq '.comments.totalCount')
    echo "--- Comments ($comment_count) ---"
    if [[ "$comment_count" -gt 0 ]]; then
        echo "$issue" | jq -r '
            .comments.nodes[-3:] |
            reverse |
            .[] |
            "[\(.createdAt | split("T")[0])] @\(.author.login): \(.body | split("\n")[0] | if length > 80 then .[0:77] + "..." else . end)"
        ' 2>/dev/null || echo "  No comments"
    fi
    echo ""

    # Deep analysis - linked PRs
    if [[ "$depth" == "deep" ]]; then
        echo "--- Linked Pull Requests ---"
        find_closing_prs "$owner" "$repo" "$number"
        echo ""
    fi

    echo "=== End Analysis ==="
}

#==============================================================================
# PULL REQUEST ANALYSIS
#==============================================================================

# Fetch PR with full context
# Args: owner, repo, number
# Outputs JSON with PR data
fetch_pr() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api graphql -f query="
    query {
        repository(owner: \"$owner\", name: \"$repo\") {
            pullRequest(number: $number) {
                id
                number
                title
                body
                state
                isDraft
                mergeable
                createdAt
                updatedAt
                mergedAt
                closedAt
                url
                author { login }
                assignees(first: 10) { nodes { login } }
                labels(first: 20) { nodes { name color } }
                headRefName
                baseRefName
                additions
                deletions
                changedFiles
                commits(first: 50) {
                    totalCount
                    nodes {
                        commit {
                            oid
                            messageHeadline
                            author { name date }
                        }
                    }
                }
                reviews(first: 20) {
                    nodes {
                        author { login }
                        state
                        submittedAt
                    }
                }
                reviewRequests(first: 10) {
                    nodes {
                        requestedReviewer {
                            ... on User { login }
                            ... on Team { name }
                        }
                    }
                }
                closingIssuesReferences(first: 10) {
                    nodes {
                        number
                        title
                        state
                    }
                }
                statusCheckRollup {
                    state
                }
            }
        }
    }"
}

# Get a quick summary of a PR
# Args: owner, repo, number
# Outputs formatted text
get_pr_summary() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    local data
    data=$(gh api graphql -f query="
    query {
        repository(owner: \"$owner\", name: \"$repo\") {
            pullRequest(number: $number) {
                number
                title
                state
                isDraft
                author { login }
                headRefName
                additions
                deletions
                updatedAt
                statusCheckRollup { state }
            }
        }
    }" --jq '.data.repository.pullRequest')

    local state title author branch adds dels updated checks draft
    state=$(echo "$data" | jq -r '.state')
    title=$(echo "$data" | jq -r '.title')
    author=$(echo "$data" | jq -r '.author.login')
    branch=$(echo "$data" | jq -r '.headRefName')
    adds=$(echo "$data" | jq -r '.additions')
    dels=$(echo "$data" | jq -r '.deletions')
    updated=$(echo "$data" | jq -r '.updatedAt')
    checks=$(echo "$data" | jq -r '.statusCheckRollup.state // "N/A"')
    draft=$(echo "$data" | jq -r '.isDraft')

    echo "PR #$number: $title"
    echo "State: $state | Draft: $draft | Author: @$author"
    echo "Branch: $branch | +$adds/-$dels | Checks: $checks"
    echo "Updated: $updated"
}

# Analyze a PR with full context
# Args: owner, repo, number, [depth: shallow|standard|deep]
# Outputs structured analysis
analyze_pr() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local depth="${4:-standard}"

    if [[ "$depth" == "shallow" ]]; then
        get_pr_summary "$owner" "$repo" "$number"
        return
    fi

    local data
    data=$(fetch_pr "$owner" "$repo" "$number")

    local pr
    pr=$(echo "$data" | jq '.data.repository.pullRequest')

    echo "=== PR #$number Analysis ==="
    echo ""

    # Basic info
    echo "Title: $(echo "$pr" | jq -r '.title')"
    echo "URL: $(echo "$pr" | jq -r '.url')"
    echo "State: $(echo "$pr" | jq -r '.state') $(echo "$pr" | jq -r 'if .isDraft then "(draft)" else "" end')"
    echo "Mergeable: $(echo "$pr" | jq -r '.mergeable // "UNKNOWN"')"
    echo "Created: $(echo "$pr" | jq -r '.createdAt')"
    echo "Updated: $(echo "$pr" | jq -r '.updatedAt')"
    echo ""

    # Branch info
    echo "--- Branch ---"
    echo "$(echo "$pr" | jq -r '.headRefName') -> $(echo "$pr" | jq -r '.baseRefName')"
    echo "+$(echo "$pr" | jq -r '.additions')/-$(echo "$pr" | jq -r '.deletions') across $(echo "$pr" | jq -r '.changedFiles') files"
    echo ""

    # Attribution
    echo "--- Attribution ---"
    echo "Author: @$(echo "$pr" | jq -r '.author.login')"
    local assignees
    assignees=$(echo "$pr" | jq -r '[.assignees.nodes[].login] | join(", ")')
    echo "Assignees: ${assignees:-none}"
    echo ""

    # Reviews
    echo "--- Reviews ---"
    local pending_reviewers
    pending_reviewers=$(echo "$pr" | jq -r '[.reviewRequests.nodes[].requestedReviewer | .login // .name] | join(", ")')
    echo "Requested: ${pending_reviewers:-none}"
    echo "$pr" | jq -r '
        .reviews.nodes |
        group_by(.author.login) |
        map(last) |
        .[] |
        "  @\(.author.login): \(.state)"
    ' 2>/dev/null || echo "  No reviews yet"
    echo ""

    # Commits
    local commit_count
    commit_count=$(echo "$pr" | jq '.commits.totalCount')
    echo "--- Commits ($commit_count) ---"
    echo "$pr" | jq -r '
        .commits.nodes[-5:] |
        .[] |
        "  \(.commit.oid[0:7]) \(.commit.messageHeadline)"
    ' 2>/dev/null
    echo ""

    # Status checks
    echo "--- CI Status ---"
    echo "Overall: $(echo "$pr" | jq -r '.statusCheckRollup.state // "N/A"')"
    echo ""

    # Closing issues
    echo "--- Closes Issues ---"
    echo "$pr" | jq -r '
        .closingIssuesReferences.nodes[] |
        "  #\(.number): \(.title) (\(.state))"
    ' 2>/dev/null || echo "  None linked"
    echo ""

    echo "=== End Analysis ==="
}

#==============================================================================
# RELATIONSHIP DISCOVERY
#==============================================================================

# Find PRs that would close an issue
# Args: owner, repo, issue_number
find_closing_prs() {
    local owner="$1"
    local repo="$2"
    local issue_number="$3"

    # Search for PRs mentioning "closes #N" or "fixes #N"
    local search_query="repo:$owner/$repo is:pr closes:$issue_number"
    gh pr list -R "$owner/$repo" --search "closes #$issue_number" --json number,title,state,author \
        --jq '.[] | "  PR #\(.number): \(.title) [\(.state)] by @\(.author.login)"' 2>/dev/null \
        || echo "  No PRs found"
}

# Find all participants in an issue
# Args: owner, repo, number
# Outputs list of usernames
find_issue_participants() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    local data
    data=$(fetch_issue "$owner" "$repo" "$number")

    local issue
    issue=$(echo "$data" | jq '.data.repository.issue')

    # Collect unique participants
    {
        echo "$issue" | jq -r '.author.login'
        echo "$issue" | jq -r '.assignees.nodes[].login'
        echo "$issue" | jq -r '.comments.nodes[].author.login'
    } | sort -u | grep -v '^$'
}

# Find all participants in a PR
# Args: owner, repo, number
# Outputs list of usernames
find_pr_participants() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    local data
    data=$(fetch_pr "$owner" "$repo" "$number")

    local pr
    pr=$(echo "$data" | jq '.data.repository.pullRequest')

    # Collect unique participants
    {
        echo "$pr" | jq -r '.author.login'
        echo "$pr" | jq -r '.assignees.nodes[].login'
        echo "$pr" | jq -r '.reviews.nodes[].author.login'
        echo "$pr" | jq -r '.commits.nodes[].commit.author.name' 2>/dev/null
    } | sort -u | grep -v '^$' | grep -v '^null$'
}

#==============================================================================
# TIMELINE / ACTIVITY
#==============================================================================

# Get recent activity on an issue
# Args: owner, repo, number, [limit]
get_issue_activity() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local limit="${4:-10}"

    local data
    data=$(fetch_issue "$owner" "$repo" "$number")

    local issue
    issue=$(echo "$data" | jq '.data.repository.issue')

    echo "Recent activity on #$number:"
    echo ""

    # Show creation
    echo "[$(echo "$issue" | jq -r '.createdAt | split("T")[0]')] Created by @$(echo "$issue" | jq -r '.author.login')"

    # Show recent comments
    echo "$issue" | jq -r "
        .comments.nodes[-$limit:] |
        .[] |
        \"[\(.createdAt | split(\"T\")[0])] @\(.author.login) commented\"
    " 2>/dev/null

    # Show closed/reopened if applicable
    local closed_at
    closed_at=$(echo "$issue" | jq -r '.closedAt')
    if [[ "$closed_at" != "null" ]]; then
        echo "[$(echo "$closed_at" | cut -d'T' -f1)] Issue closed"
    fi
}

#==============================================================================
# BATCH OPERATIONS
#==============================================================================

# Analyze multiple issues at once (shallow)
# Args: owner, repo, issue_numbers (space-separated)
batch_issue_summary() {
    local owner="$1"
    local repo="$2"
    shift 2
    local numbers="$@"

    for num in $numbers; do
        get_issue_summary "$owner" "$repo" "$num"
        echo "---"
    done
}

# Analyze multiple PRs at once (shallow)
# Args: owner, repo, pr_numbers (space-separated)
batch_pr_summary() {
    local owner="$1"
    local repo="$2"
    shift 2
    local numbers="$@"

    for num in $numbers; do
        get_pr_summary "$owner" "$repo" "$num"
        echo "---"
    done
}

#==============================================================================
# HELP
#==============================================================================

print_investigate_help() {
    cat << 'EOF'
GitHub Investigation Functions
==============================

Issue Analysis:
  get_issue_summary OWNER REPO NUM    Quick issue overview
  analyze_issue OWNER REPO NUM [DEPTH] Full analysis (shallow|standard|deep)
  fetch_issue OWNER REPO NUM          Raw JSON data

PR Analysis:
  get_pr_summary OWNER REPO NUM       Quick PR overview
  analyze_pr OWNER REPO NUM [DEPTH]   Full analysis (shallow|standard|deep)
  fetch_pr OWNER REPO NUM             Raw JSON data

Relationships:
  find_closing_prs OWNER REPO NUM     Find PRs closing an issue
  find_issue_participants O R N       List users involved in issue
  find_pr_participants O R N          List users involved in PR

Activity:
  get_issue_activity OWNER REPO NUM   Show recent activity timeline

Batch:
  batch_issue_summary O R NUMS...     Summarize multiple issues
  batch_pr_summary O R NUMS...        Summarize multiple PRs

Examples:
  source lib/github/gh-investigate-functions.sh
  get_issue_summary "hiivmind" "pulse" 42
  analyze_pr "hiivmind" "pulse" 15 deep
EOF
}
