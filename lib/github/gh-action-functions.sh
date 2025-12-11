#!/usr/bin/env bash
# GitHub Actions Domain Functions
# Layer 2 primitives for workflows, runs, and jobs

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

_get_action_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [ -h "$source" ]; do
        local dir
        dir=$(cd -P "$(dirname "$source")" && pwd)
        source=$(readlink "$source")
        [[ $source != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

# Internal: Load jq filter from YAML
_get_action_filter() {
    local filter_name="$1"
    local script_dir
    script_dir=$(_get_action_script_dir)

    yq -o=json ".filters.$filter_name" "$script_dir/gh-action-jq-filters.yaml"
}

# =============================================================================
# FETCH PRIMITIVES
# =============================================================================
# Retrieve single entities from GitHub API

# Fetch single workflow by ID or filename
# Args: owner, repo, workflow_id (numeric ID or filename like "ci.yml")
# Output: Workflow JSON
fetch_workflow() {
    local owner="$1"
    local repo="$2"
    local workflow_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$workflow_id" ]]; then
        echo "ERROR: fetch_workflow requires owner, repo, and workflow_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/workflows/$workflow_id" \
        -H "Accept: application/vnd.github+json"
}

# Fetch workflow usage/timing (billable minutes)
# Args: owner, repo, workflow_id
# Output: Usage JSON with billable_ms by runner
# Note: This endpoint is deprecated
fetch_workflow_usage() {
    local owner="$1"
    local repo="$2"
    local workflow_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$workflow_id" ]]; then
        echo "ERROR: fetch_workflow_usage requires owner, repo, and workflow_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/workflows/$workflow_id/timing" \
        -H "Accept: application/vnd.github+json"
}

# Fetch single workflow run
# Args: owner, repo, run_id
# Output: Workflow run JSON
fetch_run() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: fetch_run requires owner, repo, and run_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/runs/$run_id" \
        -H "Accept: application/vnd.github+json"
}

# Fetch workflow run logs (returns 302 redirect to download URL)
# Args: owner, repo, run_id
# Output: Redirect URL or log archive
fetch_run_logs() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: fetch_run_logs requires owner, repo, and run_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/runs/$run_id/logs" \
        -H "Accept: application/vnd.github+json"
}

# Fetch single job
# Args: owner, repo, job_id
# Output: Job JSON
fetch_job() {
    local owner="$1"
    local repo="$2"
    local job_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$job_id" ]]; then
        echo "ERROR: fetch_job requires owner, repo, and job_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/jobs/$job_id" \
        -H "Accept: application/vnd.github+json"
}

# Fetch job logs
# Args: owner, repo, job_id
# Output: Log text
fetch_job_logs() {
    local owner="$1"
    local repo="$2"
    local job_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$job_id" ]]; then
        echo "ERROR: fetch_job_logs requires owner, repo, and job_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/jobs/$job_id/logs" \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# DISCOVER PRIMITIVES
# =============================================================================
# List/discover multiple entities

# Discover all workflows in repository
# Args: owner, repo
# Output: JSON array of workflows
discover_repo_workflows() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_workflows requires owner and repo" >&2
        return 2
    fi

    gh workflow list -R "$owner/$repo" --json id,name,path,state,createdAt,updatedAt
}

# Discover workflow runs in repository
# Args: owner, repo, [status], [branch], [event], [actor]
# Output: JSON array of runs
discover_repo_runs() {
    local owner="$1"
    local repo="$2"
    local status="${3:-}"
    local branch="${4:-}"
    local event="${5:-}"
    local actor="${6:-}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_runs requires owner and repo" >&2
        return 2
    fi

    local args=("-R" "$owner/$repo")
    args+=(--json databaseId,name,headBranch,event,status,conclusion,workflowId,createdAt,updatedAt)

    [[ -n "$status" ]] && args+=(--status "$status")
    [[ -n "$branch" ]] && args+=(--branch "$branch")
    [[ -n "$event" ]] && args+=(--event "$event")
    [[ -n "$actor" ]] && args+=(--user "$actor")

    gh run list "${args[@]}"
}

# Discover runs for specific workflow
# Args: owner, repo, workflow_id, [status], [branch]
# Output: JSON array of runs
discover_workflow_runs() {
    local owner="$1"
    local repo="$2"
    local workflow_id="$3"
    local status="${4:-}"
    local branch="${5:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$workflow_id" ]]; then
        echo "ERROR: discover_workflow_runs requires owner, repo, and workflow_id" >&2
        return 2
    fi

    local endpoint="repos/$owner/$repo/actions/workflows/$workflow_id/runs"
    local args=()

    [[ -n "$status" ]] && args+=(-f status="$status")
    [[ -n "$branch" ]] && args+=(-f branch="$branch")

    gh api "$endpoint" "${args[@]}" --jq '.workflow_runs'
}

# Discover jobs for a workflow run
# Args: owner, repo, run_id, [filter: latest|all]
# Output: JSON array of jobs
discover_run_jobs() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"
    local filter="${4:-all}"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: discover_run_jobs requires owner, repo, and run_id" >&2
        return 2
    fi

    local args=()
    [[ "$filter" == "latest" ]] && args+=(-f filter=latest)

    gh api "repos/$owner/$repo/actions/runs/$run_id/jobs" "${args[@]}" --jq '.jobs'
}

# Discover pending deployments for a run
# Args: owner, repo, run_id
# Output: JSON array of pending deployment requests
discover_pending_deployments() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: discover_pending_deployments requires owner, repo, and run_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/actions/runs/$run_id/pending_deployments" --jq '.'
}

# =============================================================================
# LOOKUP PRIMITIVES
# =============================================================================
# Resolve identifiers

# Get workflow ID by filename
# Args: owner, repo, filename (e.g., "ci.yml")
# Output: Workflow ID (numeric)
get_workflow_id() {
    local owner="$1"
    local repo="$2"
    local filename="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$filename" ]]; then
        echo "ERROR: get_workflow_id requires owner, repo, and filename" >&2
        return 2
    fi

    discover_repo_workflows "$owner" "$repo" | \
        jq -r ".[] | select(.path | endswith(\"$filename\")) | .id"
}

# Note: Runs use numeric IDs directly, no lookup needed
# Note: Jobs use numeric IDs directly, no lookup needed

# =============================================================================
# FILTER PRIMITIVES
# =============================================================================
# Transform/filter JSON data (stdin → stdout)

# Filter runs by status
# Args: status (completed, in_progress, queued, requested, waiting, pending)
# Input: JSON array of runs
# Output: Filtered JSON array
filter_runs_by_status() {
    local status="$1"

    if [[ -z "$status" ]]; then
        echo "ERROR: filter_runs_by_status requires status argument" >&2
        return 2
    fi

    jq --arg status "$status" 'map(select(.status == $status))'
}

# Filter runs by branch
# Args: branch
# Input: JSON array of runs
# Output: Filtered JSON array
filter_runs_by_branch() {
    local branch="$1"

    if [[ -z "$branch" ]]; then
        echo "ERROR: filter_runs_by_branch requires branch argument" >&2
        return 2
    fi

    jq --arg branch "$branch" 'map(select(.headBranch == $branch or .head_branch == $branch))'
}

# Filter runs by event
# Args: event (push, pull_request, workflow_dispatch, schedule, etc.)
# Input: JSON array of runs
# Output: Filtered JSON array
filter_runs_by_event() {
    local event="$1"

    if [[ -z "$event" ]]; then
        echo "ERROR: filter_runs_by_event requires event argument" >&2
        return 2
    fi

    jq --arg event "$event" 'map(select(.event == $event))'
}

# Filter runs by actor (user who triggered)
# Args: actor (username)
# Input: JSON array of runs
# Output: Filtered JSON array
filter_runs_by_actor() {
    local actor="$1"

    if [[ -z "$actor" ]]; then
        echo "ERROR: filter_runs_by_actor requires actor argument" >&2
        return 2
    fi

    jq --arg actor "$actor" 'map(select(.actor.login == $actor or .triggering_actor.login == $actor))'
}

# Filter workflows by state
# Args: state (active, disabled_manually, disabled_inactivity)
# Input: JSON array of workflows
# Output: Filtered JSON array
filter_workflows_by_state() {
    local state="$1"

    if [[ -z "$state" ]]; then
        echo "ERROR: filter_workflows_by_state requires state argument" >&2
        return 2
    fi

    jq --arg state "$state" 'map(select(.state == $state))'
}

# Filter runs by conclusion (only for completed runs)
# Args: conclusion (success, failure, cancelled, skipped, timed_out, action_required)
# Input: JSON array of runs
# Output: Filtered JSON array
filter_runs_by_conclusion() {
    local conclusion="$1"

    if [[ -z "$conclusion" ]]; then
        echo "ERROR: filter_runs_by_conclusion requires conclusion argument" >&2
        return 2
    fi

    jq --arg conclusion "$conclusion" 'map(select(.conclusion == $conclusion))'
}

# =============================================================================
# FORMAT PRIMITIVES
# =============================================================================
# Transform JSON to human-readable output (stdin → stdout)

# Format workflows as table
# Input: JSON array of workflows
# Output: Formatted table
format_workflows() {
    jq -r '
        ["ID", "NAME", "PATH", "STATE"] as $headers |
        [$headers],
        (.[] | [.id, .name, .path, .state]) |
        @tsv
    '
}

# Format single workflow details
# Input: Single workflow JSON
# Output: Formatted details
format_workflow() {
    jq -r '
        "Workflow ID: \(.id)",
        "Name: \(.name)",
        "Path: \(.path)",
        "State: \(.state)",
        "Created: \(.created_at // .createdAt)",
        "Updated: \(.updated_at // .updatedAt)",
        "URL: \(.html_url // .url)"
    '
}

# Format runs as table
# Input: JSON array of runs
# Output: Formatted table
format_runs() {
    jq -r '
        ["RUN_ID", "NAME", "BRANCH", "EVENT", "STATUS", "CONCLUSION"] as $headers |
        [$headers],
        (.[] | [
            (.databaseId // .id),
            .name,
            (.headBranch // .head_branch),
            .event,
            .status,
            (.conclusion // "-")
        ]) |
        @tsv
    '
}

# Format single run details
# Input: Single run JSON
# Output: Formatted details
format_run() {
    jq -r '
        "Run ID: \(.id)",
        "Name: \(.name)",
        "Branch: \(.head_branch)",
        "Event: \(.event)",
        "Status: \(.status)",
        "Conclusion: \(.conclusion // "N/A")",
        "Workflow ID: \(.workflow_id)",
        "Run Number: \(.run_number)",
        "Created: \(.created_at)",
        "Updated: \(.updated_at)",
        "URL: \(.html_url)"
    '
}

# Format jobs as table
# Input: JSON array of jobs
# Output: Formatted table
format_jobs() {
    jq -r '
        ["JOB_ID", "NAME", "STATUS", "CONCLUSION", "STARTED", "COMPLETED"] as $headers |
        [$headers],
        (.[] | [
            .id,
            .name,
            .status,
            (.conclusion // "-"),
            (.started_at // "-"),
            (.completed_at // "-")
        ]) |
        @tsv
    '
}

# =============================================================================
# DETECT PRIMITIVES
# =============================================================================
# Determine type/state (returns string to stdout)

# Detect workflow state
# Args: owner, repo, workflow_id
# Output: "active" | "disabled_manually" | "disabled_inactivity"
detect_workflow_state() {
    local owner="$1"
    local repo="$2"
    local workflow_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$workflow_id" ]]; then
        echo "ERROR: detect_workflow_state requires owner, repo, and workflow_id" >&2
        return 2
    fi

    fetch_workflow "$owner" "$repo" "$workflow_id" | jq -r '.state'
}

# Detect run status
# Args: owner, repo, run_id
# Output: "completed" | "in_progress" | "queued" | "requested" | "waiting" | "pending"
detect_run_status() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: detect_run_status requires owner, repo, and run_id" >&2
        return 2
    fi

    fetch_run "$owner" "$repo" "$run_id" | jq -r '.status'
}

# Detect run conclusion (only valid if status is "completed")
# Args: owner, repo, run_id
# Output: "success" | "failure" | "cancelled" | "skipped" | "timed_out" | "action_required" | "null"
detect_run_conclusion() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: detect_run_conclusion requires owner, repo, and run_id" >&2
        return 2
    fi

    fetch_run "$owner" "$repo" "$run_id" | jq -r '.conclusion // "null"'
}

# =============================================================================
# MUTATE PRIMITIVES
# =============================================================================
# Create, update, or delete entities

# Trigger workflow via workflow_dispatch event
# Args: owner, repo, workflow_id, ref, [inputs_json]
# Output: Empty (204 No Content)
trigger_workflow() {
    local owner="$1"
    local repo="$2"
    local workflow_id="$3"
    local ref="$4"
    local inputs_json="${5:-{}}"

    if [[ -z "$owner" || -z "$repo" || -z "$workflow_id" || -z "$ref" ]]; then
        echo "ERROR: trigger_workflow requires owner, repo, workflow_id, and ref" >&2
        return 2
    fi

    local args=(-X POST)
    args+=(-f ref="$ref")

    if [[ "$inputs_json" != "{}" ]]; then
        args+=(-f inputs="$inputs_json")
    fi

    gh api "repos/$owner/$repo/actions/workflows/$workflow_id/dispatches" "${args[@]}"
}

# Enable a workflow
# Args: owner, repo, workflow_id
# Output: Empty (204 No Content)
enable_workflow() {
    local owner="$1"
    local repo="$2"
    local workflow_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$workflow_id" ]]; then
        echo "ERROR: enable_workflow requires owner, repo, and workflow_id" >&2
        return 2
    fi

    gh api -X PUT "repos/$owner/$repo/actions/workflows/$workflow_id/enable"
}

# Disable a workflow
# Args: owner, repo, workflow_id
# Output: Empty (204 No Content)
disable_workflow() {
    local owner="$1"
    local repo="$2"
    local workflow_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$workflow_id" ]]; then
        echo "ERROR: disable_workflow requires owner, repo, and workflow_id" >&2
        return 2
    fi

    gh api -X PUT "repos/$owner/$repo/actions/workflows/$workflow_id/disable"
}

# Cancel a workflow run
# Args: owner, repo, run_id
# Output: Empty (202 Accepted)
cancel_run() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: cancel_run requires owner, repo, and run_id" >&2
        return 2
    fi

    gh api -X POST "repos/$owner/$repo/actions/runs/$run_id/cancel"
}

# Force cancel a workflow run
# Args: owner, repo, run_id
# Output: Empty (202 Accepted)
force_cancel_run() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: force_cancel_run requires owner, repo, and run_id" >&2
        return 2
    fi

    gh api -X POST "repos/$owner/$repo/actions/runs/$run_id/force-cancel"
}

# Re-run a workflow
# Args: owner, repo, run_id, [enable_debug: true|false]
# Output: Result JSON (201 Created)
rerun_workflow() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"
    local enable_debug="${4:-false}"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: rerun_workflow requires owner, repo, and run_id" >&2
        return 2
    fi

    local args=(-X POST)
    if [[ "$enable_debug" == "true" ]]; then
        args+=(-f enable_debug_logging=true)
    fi

    gh api "repos/$owner/$repo/actions/runs/$run_id/rerun" "${args[@]}"
}

# Re-run only failed jobs from a workflow run
# Args: owner, repo, run_id, [enable_debug: true|false]
# Output: Result JSON (201 Created)
rerun_failed_jobs() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"
    local enable_debug="${4:-false}"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: rerun_failed_jobs requires owner, repo, and run_id" >&2
        return 2
    fi

    local args=(-X POST)
    if [[ "$enable_debug" == "true" ]]; then
        args+=(-f enable_debug_logging=true)
    fi

    gh api "repos/$owner/$repo/actions/runs/$run_id/rerun-failed-jobs" "${args[@]}"
}

# Delete workflow run logs
# Args: owner, repo, run_id
# Output: Empty (204 No Content)
delete_run_logs() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" ]]; then
        echo "ERROR: delete_run_logs requires owner, repo, and run_id" >&2
        return 2
    fi

    gh api -X DELETE "repos/$owner/$repo/actions/runs/$run_id/logs"
}

# Review pending deployment (approve or reject)
# Args: owner, repo, run_id, environment_ids_json, state (approved|rejected), [comment]
# Output: Deployment JSON array
review_pending_deployment() {
    local owner="$1"
    local repo="$2"
    local run_id="$3"
    local environment_ids_json="$4"
    local state="$5"
    local comment="${6:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$run_id" || -z "$environment_ids_json" || -z "$state" ]]; then
        echo "ERROR: review_pending_deployment requires owner, repo, run_id, environment_ids_json, and state" >&2
        return 2
    fi

    if [[ "$state" != "approved" && "$state" != "rejected" ]]; then
        echo "ERROR: state must be 'approved' or 'rejected'" >&2
        return 2
    fi

    local args=(-X POST)
    args+=(-f environment_ids="$environment_ids_json")
    args+=(-f state="$state")
    [[ -n "$comment" ]] && args+=(-f comment="$comment")

    gh api "repos/$owner/$repo/actions/runs/$run_id/pending_deployments" "${args[@]}"
}
