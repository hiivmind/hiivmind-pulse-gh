#!/usr/bin/env bash
# tests/lib/resources/pr.bash
# Pull Request resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# HELPER: BRANCH CREATION
# =============================================================================

# Create a branch for PR testing
# Usage: create_test_branch "owner" "repo" "branch_name" [base_branch]
# Output: branch name
create_test_branch() {
    local owner="$1"
    local repo="$2"
    local branch_name="$3"
    local base_branch="${4:-}"

    # Get default branch if not specified
    if [[ -z "$base_branch" ]]; then
        base_branch=$(gh api "repos/${owner}/${repo}" --jq '.default_branch')
    fi

    # Get the SHA of the base branch
    local base_sha
    base_sha=$(gh api "repos/${owner}/${repo}/git/ref/heads/${base_branch}" --jq '.object.sha')

    # Create the new branch
    gh api "repos/${owner}/${repo}/git/refs" \
        -f "ref=refs/heads/${branch_name}" \
        -f "sha=${base_sha}" >/dev/null

    track_resource "branch" "${owner}/${repo}/${branch_name}"
    echo "$branch_name"
}

# Delete a branch
# Usage: delete_branch "owner/repo/branch_name"
delete_branch() {
    local identifier="$1"

    local owner="${identifier%%/*}"
    local rest="${identifier#*/}"
    local repo="${rest%%/*}"
    local branch="${rest#*/}"

    gh api -X DELETE "repos/${owner}/${repo}/git/refs/heads/${branch}" \
        2>/dev/null || true
}

# Create a commit on a branch (for PR content)
# Usage: create_test_commit "owner" "repo" "branch" "message" [file_path] [content]
create_test_commit() {
    local owner="$1"
    local repo="$2"
    local branch="$3"
    local message="$4"
    local file_path="${5:-.test-file-$(date +%s).txt}"
    local content="${6:-Test content created at $(date)}"

    # Get the current commit SHA
    local current_sha
    current_sha=$(gh api "repos/${owner}/${repo}/git/ref/heads/${branch}" --jq '.object.sha')

    # Get the tree SHA
    local tree_sha
    tree_sha=$(gh api "repos/${owner}/${repo}/git/commits/${current_sha}" --jq '.tree.sha')

    # Create a blob with the content
    local blob_sha
    blob_sha=$(gh api "repos/${owner}/${repo}/git/blobs" \
        -f "content=${content}" \
        -f "encoding=utf-8" \
        --jq '.sha')

    # Create a new tree
    local new_tree_sha
    new_tree_sha=$(gh api "repos/${owner}/${repo}/git/trees" \
        -f "base_tree=${tree_sha}" \
        -f "tree[][path]=${file_path}" \
        -f "tree[][mode]=100644" \
        -f "tree[][type]=blob" \
        -f "tree[][sha]=${blob_sha}" \
        --jq '.sha')

    # Create a new commit
    local new_commit_sha
    new_commit_sha=$(gh api "repos/${owner}/${repo}/git/commits" \
        -f "message=${message}" \
        -f "tree=${new_tree_sha}" \
        -f "parents[]=${current_sha}" \
        --jq '.sha')

    # Update the branch reference
    gh api "repos/${owner}/${repo}/git/refs/heads/${branch}" \
        -X PATCH \
        -f "sha=${new_commit_sha}" >/dev/null

    echo "$new_commit_sha"
}

# =============================================================================
# CREATE
# =============================================================================

# Create a pull request and track it for cleanup
# Usage: create_pr "owner" "repo" "title" "head" "base" [body] [draft]
# Output: PR number
create_pr() {
    local owner="$1"
    local repo="$2"
    local title="$3"
    local head="$4"
    local base="$5"
    local body="${6:-}"
    local draft="${7:-false}"

    local args=(
        -f "title=${title}"
        -f "head=${head}"
        -f "base=${base}"
        -F "draft=${draft}"
    )
    [[ -n "$body" ]] && args+=(-f "body=${body}")

    local result
    result=$(gh api "repos/${owner}/${repo}/pulls" "${args[@]}")

    local number
    number=$(echo "$result" | jq -r '.number')

    if [[ "$number" == "null" || -z "$number" ]]; then
        echo "Error: Failed to create PR" >&2
        return 1
    fi

    track_resource "pr" "${owner}/${repo}/${number}"
    echo "$number"
}

# Create a complete test PR without tracking (creates branch, commit, and PR)
# Usage: create_test_pr_raw "owner" "repo" [title]
# Output: PR number
create_test_pr_raw() {
    local owner="$1"
    local repo="$2"
    local title="${3:-}"

    local timestamp
    timestamp=$(date +%s)

    local branch_name="test-branch-${timestamp}"
    [[ -z "$title" ]] && title="Test PR ${timestamp}"

    # Get default branch
    local base_branch
    base_branch=$(gh api "repos/${owner}/${repo}" --jq '.default_branch')

    # Create branch (track it for cleanup)
    create_test_branch "$owner" "$repo" "$branch_name" "$base_branch" >/dev/null

    # Create a commit
    create_test_commit "$owner" "$repo" "$branch_name" "Test commit for PR" >/dev/null

    # Create PR without tracking
    local args=(
        -f "title=${title}"
        -f "head=${branch_name}"
        -f "base=${base_branch}"
        -F "draft=false"
        -f "body=Auto-generated test PR"
    )

    local result
    result=$(gh api "repos/${owner}/${repo}/pulls" "${args[@]}")

    local number
    number=$(echo "$result" | jq -r '.number')

    if [[ "$number" == "null" || -z "$number" ]]; then
        echo "Error: Failed to create PR" >&2
        return 1
    fi

    echo "$number"
}

# Create a complete test PR (creates branch, commit, and PR)
# Usage: create_test_pr "owner" "repo" [title]
# Output: PR number
create_test_pr() {
    local owner="$1"
    local repo="$2"
    local number
    number=$(create_test_pr_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "pr" "${owner}/${repo}/${number}"
        echo "$number"
    else
        return 1
    fi
}

# =============================================================================
# READ
# =============================================================================

# Get PR by number
# Usage: get_pr "owner" "repo" "number"
get_pr() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/pulls/${number}"
}

# List all PR numbers
# Usage: list_prs "owner" "repo" [state]
# Output: PR numbers, one per line
list_prs() {
    local owner="$1"
    local repo="$2"
    local state="${3:-all}"

    gh api "repos/${owner}/${repo}/pulls?state=${state}&per_page=100" \
        --jq '.[].number'
}

# Check if PR exists
# Usage: pr_exists "owner" "repo" "number"
pr_exists() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/pulls/${number}" &>/dev/null
}

# =============================================================================
# UPDATE
# =============================================================================

# Update PR
# Usage: update_pr "owner" "repo" "number" [title] [body] [state] [base]
update_pr() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local title="${4:-}"
    local body="${5:-}"
    local state="${6:-}"
    local base="${7:-}"

    local args=(-X PATCH)
    [[ -n "$title" ]] && args+=(-f "title=${title}")
    [[ -n "$body" ]] && args+=(-f "body=${body}")
    [[ -n "$state" ]] && args+=(-f "state=${state}")
    [[ -n "$base" ]] && args+=(-f "base=${base}")

    gh api "repos/${owner}/${repo}/pulls/${number}" "${args[@]}"
}

# Close PR
# Usage: close_pr "owner" "repo" "number"
close_pr() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    gh api "repos/${owner}/${repo}/pulls/${number}" \
        -X PATCH -f state=closed
}

# Mark PR ready for review (remove draft status)
# Usage: mark_pr_ready "owner" "repo" "number"
mark_pr_ready() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    # Get node ID
    local node_id
    node_id=$(gh api "repos/${owner}/${repo}/pulls/${number}" --jq '.node_id')

    # Use GraphQL to mark ready
    gh api graphql -f query='
        mutation($id: ID!) {
            markPullRequestReadyForReview(input: {pullRequestId: $id}) {
                pullRequest { number }
            }
        }
    ' -f id="$node_id"
}

# Request review on PR
# Usage: request_pr_review "owner" "repo" "number" "reviewer"
request_pr_review() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local reviewer="$4"

    gh api "repos/${owner}/${repo}/pulls/${number}/requested_reviewers" \
        -f "reviewers[]=${reviewer}"
}

# Add labels to PR
# Usage: add_pr_labels "owner" "repo" "number" "label1,label2"
add_pr_labels() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local labels="$4"

    # PRs use the issues endpoint for labels
    local labels_json
    labels_json=$(echo "$labels" | jq -R 'split(",") | map(select(length > 0))')

    gh api "repos/${owner}/${repo}/issues/${number}/labels" \
        --input - <<< "{\"labels\": ${labels_json}}"
}

# Set PR milestone
# Usage: set_pr_milestone "owner" "repo" "number" "milestone_number"
set_pr_milestone() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local milestone="$4"

    # PRs use the issues endpoint for milestones
    gh api "repos/${owner}/${repo}/issues/${number}" \
        -X PATCH -F "milestone=${milestone}"
}

# =============================================================================
# DELETE
# =============================================================================

# Delete (close) PR by identifier and clean up branch
# Usage: delete_pr "owner/repo/number"
delete_pr() {
    local identifier="$1"

    parse_owner_repo_number "$identifier"

    # Get the head branch before closing
    local head_ref
    head_ref=$(gh api "repos/${PARSED_OWNER}/${PARSED_REPO}/pulls/${PARSED_NUMBER}" \
        --jq '.head.ref' 2>/dev/null) || true

    # Close the PR
    gh api "repos/${PARSED_OWNER}/${PARSED_REPO}/pulls/${PARSED_NUMBER}" \
        -X PATCH -f state=closed 2>/dev/null || true

    # Delete the head branch if it was a test branch
    if [[ -n "$head_ref" && "$head_ref" == test-* ]]; then
        gh api -X DELETE "repos/${PARSED_OWNER}/${PARSED_REPO}/git/refs/heads/${head_ref}" \
            2>/dev/null || true
    fi
}

# Delete PR by parts
# Usage: delete_pr_by_parts "owner" "repo" "number"
delete_pr_by_parts() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    delete_pr "${owner}/${repo}/${number}"
}
