# Action Domain Functions Index

> **Domain:** GitHub Actions (Workflows, Runs, Jobs)
> **File:** `lib/github/gh-action-functions.sh`
> **Layer:** 2 (Primitives only - no Layer 3 needed)
> **Last updated:** 2025-12-11

## Quick Reference

### FETCH Primitives (6)

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_workflow` | Get single workflow | `fetch_workflow "owner" "repo" "ci.yml"` |
| `fetch_workflow_usage` | Get billable minutes (deprecated) | `fetch_workflow_usage "owner" "repo" 123` |
| `fetch_run` | Get workflow run | `fetch_run "owner" "repo" 456` |
| `fetch_run_logs` | Download run logs (302 redirect) | `fetch_run_logs "owner" "repo" 456` |
| `fetch_job` | Get job details | `fetch_job "owner" "repo" 789` |
| `fetch_job_logs` | Download job logs | `fetch_job_logs "owner" "repo" 789` |

### DISCOVER Primitives (5)

| Function | Purpose | Example |
|----------|---------|---------|
| `discover_repo_workflows` | List all workflows | `discover_repo_workflows "owner" "repo"` |
| `discover_repo_runs` | List all runs | `discover_repo_runs "owner" "repo" ["status"] ["branch"]` |
| `discover_workflow_runs` | List runs for workflow | `discover_workflow_runs "owner" "repo" "workflow_id"` |
| `discover_run_jobs` | List jobs in run | `discover_run_jobs "owner" "repo" "run_id"` |
| `discover_pending_deployments` | Get pending deployment requests | `discover_pending_deployments "owner" "repo" "run_id"` |

### LOOKUP Primitives (1)

| Function | Purpose | Example |
|----------|---------|---------|
| `get_workflow_id` | Resolve filename → ID | `get_workflow_id "owner" "repo" "ci.yml"` |

### FILTER Primitives (6)

| Function | Purpose | Example |
|----------|---------|---------|
| `filter_runs_by_status` | Filter by status | `echo "$RUNS" \| filter_runs_by_status "completed"` |
| `filter_runs_by_branch` | Filter by branch | `echo "$RUNS" \| filter_runs_by_branch "main"` |
| `filter_runs_by_event` | Filter by event | `echo "$RUNS" \| filter_runs_by_event "push"` |
| `filter_runs_by_actor` | Filter by user | `echo "$RUNS" \| filter_runs_by_actor "octocat"` |
| `filter_runs_by_conclusion` | Filter by result | `echo "$RUNS" \| filter_runs_by_conclusion "failure"` |
| `filter_workflows_by_state` | Filter by state | `echo "$WORKFLOWS" \| filter_workflows_by_state "active"` |

### FORMAT Primitives (4)

| Function | Purpose | Example |
|----------|---------|---------|
| `format_workflows` | Tabular workflow list | `discover_repo_workflows "owner" "repo" \| format_workflows` |
| `format_workflow` | Single workflow details | `fetch_workflow "owner" "repo" "ci.yml" \| format_workflow` |
| `format_runs` | Tabular run list | `discover_repo_runs "owner" "repo" \| format_runs` |
| `format_run` | Single run details | `fetch_run "owner" "repo" 123 \| format_run` |
| `format_jobs` | Tabular job list | `discover_run_jobs "owner" "repo" 456 \| format_jobs` |

### DETECT Primitives (3)

| Function | Returns | Example |
|----------|---------|---------|
| `detect_workflow_state` | "active" \| "disabled_manually" | `detect_workflow_state "owner" "repo" "ci.yml"` |
| `detect_run_status` | "completed" \| "in_progress" \| "queued" | `detect_run_status "owner" "repo" 123` |
| `detect_run_conclusion` | "success" \| "failure" \| "cancelled" | `detect_run_conclusion "owner" "repo" 123` |

### MUTATE Primitives (9)

| Function | Purpose | Example |
|----------|---------|---------|
| `trigger_workflow` | Create workflow dispatch | `trigger_workflow "owner" "repo" "ci.yml" "main" '{}'` |
| `enable_workflow` | Enable workflow | `enable_workflow "owner" "repo" "ci.yml"` |
| `disable_workflow` | Disable workflow | `disable_workflow "owner" "repo" "ci.yml"` |
| `cancel_run` | Cancel in-progress run | `cancel_run "owner" "repo" 123` |
| `force_cancel_run` | Force cancel run | `force_cancel_run "owner" "repo" 123` |
| `rerun_workflow` | Re-run entire workflow | `rerun_workflow "owner" "repo" 123 [false]` |
| `rerun_failed_jobs` | Re-run only failed jobs | `rerun_failed_jobs "owner" "repo" 123 [false]` |
| `delete_run_logs` | Delete workflow logs | `delete_run_logs "owner" "repo" 123` |
| `review_pending_deployment` | Approve/reject deployment | `review_pending_deployment "owner" "repo" 123 "[1]" "approved"` |

---

## Function Details

### FETCH Primitives

#### `fetch_workflow`
Get single workflow by ID or filename.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `workflow_id` - Numeric workflow ID or filename (e.g., "ci.yml", ".github/workflows/ci.yml")

**Output:** Workflow JSON

**Example:**
```bash
fetch_workflow "octocat" "hello-world" "ci.yml"
fetch_workflow "octocat" "hello-world" 161335
```

**Composition:**
```bash
fetch_workflow "octocat" "hello-world" "ci.yml" | format_workflow
```

---

#### `fetch_workflow_usage`
Get workflow usage/timing (billable minutes by runner).

**Note:** This endpoint is deprecated by GitHub.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `workflow_id` - Workflow ID

**Output:** Usage JSON with `billable_ms` by runner type

**Example:**
```bash
fetch_workflow_usage "octocat" "hello-world" 161335
```

---

#### `fetch_run`
Get workflow run details.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Workflow run ID

**Output:** Run JSON

**Example:**
```bash
fetch_run "octocat" "hello-world" 30433642
```

**Composition:**
```bash
fetch_run "octocat" "hello-world" 30433642 | format_run
```

---

#### `fetch_run_logs`
Download workflow run logs (returns 302 redirect to archive).

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Workflow run ID

**Output:** Log archive download URL or archive data

**Example:**
```bash
fetch_run_logs "octocat" "hello-world" 30433642 > logs.zip
```

---

#### `fetch_job`
Get job details.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `job_id` - Job ID

**Output:** Job JSON

**Example:**
```bash
fetch_job "octocat" "hello-world" 399444496
```

---

#### `fetch_job_logs`
Download job logs.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `job_id` - Job ID

**Output:** Log text

**Example:**
```bash
fetch_job_logs "octocat" "hello-world" 399444496 > job.log
```

---

### DISCOVER Primitives

#### `discover_repo_workflows`
List all workflows in repository.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name

**Output:** JSON array of workflows

**Example:**
```bash
discover_repo_workflows "octocat" "hello-world"
```

**Composition:**
```bash
discover_repo_workflows "octocat" "hello-world" | filter_workflows_by_state "active" | format_workflows
```

---

#### `discover_repo_runs`
List workflow runs in repository with optional filtering.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `status` (optional) - Filter by status (completed, in_progress, queued)
- `branch` (optional) - Filter by branch
- `event` (optional) - Filter by event (push, pull_request, etc.)
- `actor` (optional) - Filter by user

**Output:** JSON array of runs

**Example:**
```bash
# All runs
discover_repo_runs "octocat" "hello-world"

# Completed runs only
discover_repo_runs "octocat" "hello-world" "completed"

# Runs on main branch
discover_repo_runs "octocat" "hello-world" "" "main"

# Failed push runs
discover_repo_runs "octocat" "hello-world" "completed" "" "push" | filter_runs_by_conclusion "failure"
```

**Composition:**
```bash
discover_repo_runs "octocat" "hello-world" | filter_runs_by_status "completed" | filter_runs_by_conclusion "failure" | format_runs
```

---

#### `discover_workflow_runs`
List runs for specific workflow.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `workflow_id` - Workflow ID or filename
- `status` (optional) - Filter by status
- `branch` (optional) - Filter by branch

**Output:** JSON array of runs

**Example:**
```bash
discover_workflow_runs "octocat" "hello-world" "ci.yml"
discover_workflow_runs "octocat" "hello-world" 161335 "completed" "main"
```

---

#### `discover_run_jobs`
List jobs in a workflow run.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID
- `filter` (optional) - "latest" or "all" (default: all)

**Output:** JSON array of jobs

**Example:**
```bash
discover_run_jobs "octocat" "hello-world" 30433642
discover_run_jobs "octocat" "hello-world" 30433642 "latest"
```

**Composition:**
```bash
discover_run_jobs "octocat" "hello-world" 30433642 | format_jobs
```

---

#### `discover_pending_deployments`
Get pending deployment requests for a run.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID

**Output:** JSON array of pending deployment requests

**Example:**
```bash
discover_pending_deployments "octocat" "hello-world" 30433642
```

---

### LOOKUP Primitives

#### `get_workflow_id`
Resolve workflow filename to numeric ID.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `filename` - Workflow filename (e.g., "ci.yml")

**Output:** Workflow ID (numeric)

**Example:**
```bash
WORKFLOW_ID=$(get_workflow_id "octocat" "hello-world" "ci.yml")
echo "Workflow ID: $WORKFLOW_ID"
```

**Note:** Most functions accept both IDs and filenames, so lookup is often optional.

---

### FILTER Primitives

#### `filter_runs_by_status`
Keep only runs matching status.

**Args:**
- `status` - One of: completed, in_progress, queued, requested, waiting, pending

**Input:** JSON array from stdin
**Output:** Filtered JSON array

**Example:**
```bash
discover_repo_runs "octocat" "hello-world" | filter_runs_by_status "completed"
```

---

#### `filter_runs_by_branch`
Keep only runs from specific branch.

**Args:**
- `branch` - Branch name

**Input:** JSON array from stdin
**Output:** Filtered JSON array

**Example:**
```bash
discover_repo_runs "octocat" "hello-world" | filter_runs_by_branch "main"
```

---

#### `filter_runs_by_event`
Keep only runs triggered by specific event.

**Args:**
- `event` - Event type: push, pull_request, workflow_dispatch, schedule, etc.

**Input:** JSON array from stdin
**Output:** Filtered JSON array

**Example:**
```bash
discover_repo_runs "octocat" "hello-world" | filter_runs_by_event "pull_request"
```

---

#### `filter_runs_by_actor`
Keep only runs triggered by specific user.

**Args:**
- `actor` - GitHub username

**Input:** JSON array from stdin
**Output:** Filtered JSON array

**Example:**
```bash
discover_repo_runs "octocat" "hello-world" | filter_runs_by_actor "octocat"
```

---

#### `filter_runs_by_conclusion`
Keep only runs with specific conclusion (completed runs only).

**Args:**
- `conclusion` - One of: success, failure, cancelled, skipped, timed_out, action_required

**Input:** JSON array from stdin
**Output:** Filtered JSON array

**Example:**
```bash
discover_repo_runs "octocat" "hello-world" | filter_runs_by_conclusion "failure"
```

---

#### `filter_workflows_by_state`
Keep only workflows in specific state.

**Args:**
- `state` - One of: active, disabled_manually, disabled_inactivity

**Input:** JSON array from stdin
**Output:** Filtered JSON array

**Example:**
```bash
discover_repo_workflows "octocat" "hello-world" | filter_workflows_by_state "active"
```

---

### FORMAT Primitives

#### `format_workflows`
Format workflows as tabular list.

**Input:** JSON array from stdin
**Output:** TSV table with headers

**Example:**
```bash
discover_repo_workflows "octocat" "hello-world" | format_workflows
```

**Output:**
```
ID      NAME    PATH                            STATE
161335  CI      .github/workflows/ci.yml        active
161336  Deploy  .github/workflows/deploy.yml    active
```

---

#### `format_workflow`
Format single workflow with details.

**Input:** Single workflow JSON from stdin
**Output:** Formatted text

**Example:**
```bash
fetch_workflow "octocat" "hello-world" "ci.yml" | format_workflow
```

**Output:**
```
Workflow ID: 161335
Name: CI
Path: .github/workflows/ci.yml
State: active
Created: 2019-12-06T14:20:20.000Z
Updated: 2019-12-06T14:20:20.000Z
URL: https://github.com/octocat/hello-world/blob/main/.github/workflows/ci.yml
```

---

#### `format_runs`
Format runs as tabular list.

**Input:** JSON array from stdin
**Output:** TSV table with headers

**Example:**
```bash
discover_repo_runs "octocat" "hello-world" | format_runs
```

**Output:**
```
RUN_ID      NAME    BRANCH  EVENT   STATUS      CONCLUSION
30433642    CI      main    push    completed   success
30433641    CI      dev     push    completed   failure
```

---

#### `format_run`
Format single run with details.

**Input:** Single run JSON from stdin
**Output:** Formatted text

**Example:**
```bash
fetch_run "octocat" "hello-world" 30433642 | format_run
```

---

#### `format_jobs`
Format jobs as tabular list.

**Input:** JSON array from stdin
**Output:** TSV table with headers

**Example:**
```bash
discover_run_jobs "octocat" "hello-world" 30433642 | format_jobs
```

**Output:**
```
JOB_ID      NAME    STATUS      CONCLUSION  STARTED                 COMPLETED
399444496   build   completed   success     2020-01-20T17:42:40Z    2020-01-20T17:44:39Z
399444497   test    completed   success     2020-01-20T17:44:40Z    2020-01-20T17:46:15Z
```

---

### DETECT Primitives

#### `detect_workflow_state`
Determine if workflow is enabled or disabled.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `workflow_id` - Workflow ID or filename

**Output:** "active" | "disabled_manually" | "disabled_inactivity"

**Example:**
```bash
STATE=$(detect_workflow_state "octocat" "hello-world" "ci.yml")
if [[ "$STATE" == "active" ]]; then
    echo "Workflow is enabled"
fi
```

---

#### `detect_run_status`
Get current status of a run.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID

**Output:** "completed" | "in_progress" | "queued" | "requested" | "waiting" | "pending"

**Example:**
```bash
STATUS=$(detect_run_status "octocat" "hello-world" 30433642)
echo "Run status: $STATUS"
```

---

#### `detect_run_conclusion`
Get conclusion of a completed run.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID

**Output:** "success" | "failure" | "cancelled" | "skipped" | "timed_out" | "action_required" | "null"

**Example:**
```bash
CONCLUSION=$(detect_run_conclusion "octocat" "hello-world" 30433642)
if [[ "$CONCLUSION" == "failure" ]]; then
    echo "Run failed, re-running failed jobs..."
    rerun_failed_jobs "octocat" "hello-world" 30433642
fi
```

---

### MUTATE Primitives

#### `trigger_workflow`
Trigger workflow via workflow_dispatch event.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `workflow_id` - Workflow ID or filename
- `ref` - Git ref (branch or tag)
- `inputs_json` (optional) - JSON object with workflow inputs (default: {})

**Output:** Empty (204 No Content)

**Example:**
```bash
# Simple trigger
trigger_workflow "octocat" "hello-world" "ci.yml" "main"

# With inputs
trigger_workflow "octocat" "hello-world" "deploy.yml" "main" '{"environment": "production"}'
```

**Note:** Workflow must have `workflow_dispatch` trigger configured.

---

#### `enable_workflow`
Enable a disabled workflow.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `workflow_id` - Workflow ID or filename

**Output:** Empty (204 No Content)

**Example:**
```bash
enable_workflow "octocat" "hello-world" "ci.yml"
```

---

#### `disable_workflow`
Disable a workflow.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `workflow_id` - Workflow ID or filename

**Output:** Empty (204 No Content)

**Example:**
```bash
disable_workflow "octocat" "hello-world" "ci.yml"
```

---

#### `cancel_run`
Cancel an in-progress workflow run.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID

**Output:** Empty (202 Accepted)

**Example:**
```bash
cancel_run "octocat" "hello-world" 30433642
```

---

#### `force_cancel_run`
Force cancel a workflow run (even if cancellation is stuck).

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID

**Output:** Empty (202 Accepted)

**Example:**
```bash
force_cancel_run "octocat" "hello-world" 30433642
```

---

#### `rerun_workflow`
Re-run an entire workflow.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID
- `enable_debug` (optional) - "true" to enable debug logging (default: false)

**Output:** Result JSON (201 Created)

**Example:**
```bash
rerun_workflow "octocat" "hello-world" 30433642
rerun_workflow "octocat" "hello-world" 30433642 "true"  # With debug logging
```

---

#### `rerun_failed_jobs`
Re-run only failed jobs from a workflow run.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID
- `enable_debug` (optional) - "true" to enable debug logging (default: false)

**Output:** Result JSON (201 Created)

**Example:**
```bash
rerun_failed_jobs "octocat" "hello-world" 30433642
```

---

#### `delete_run_logs`
Delete workflow run logs.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID

**Output:** Empty (204 No Content)

**Example:**
```bash
delete_run_logs "octocat" "hello-world" 30433642
```

---

#### `review_pending_deployment`
Approve or reject pending deployment.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `run_id` - Run ID
- `environment_ids_json` - JSON array of environment IDs (e.g., "[1, 2]")
- `state` - "approved" or "rejected"
- `comment` (optional) - Comment for the review

**Output:** Deployment JSON array

**Example:**
```bash
review_pending_deployment "octocat" "hello-world" 30433642 "[1]" "approved" "LGTM"
review_pending_deployment "octocat" "hello-world" 30433642 "[1]" "rejected" "Needs more testing"
```

---

## Composition Examples

### List Failed Runs on Main Branch
```bash
discover_repo_runs "octocat" "hello-world" "completed" "main" | \
    filter_runs_by_conclusion "failure" | \
    format_runs
```

### Monitor In-Progress Runs
```bash
discover_repo_runs "octocat" "hello-world" "in_progress" | format_runs
```

### Re-run All Failed Runs
```bash
discover_repo_runs "octocat" "hello-world" "completed" | \
    filter_runs_by_conclusion "failure" | \
    jq -r '.[].databaseId' | \
    while read run_id; do
        echo "Re-running failed jobs for run $run_id"
        rerun_failed_jobs "octocat" "hello-world" "$run_id"
    done
```

### List Active Workflows
```bash
discover_repo_workflows "octocat" "hello-world" | \
    filter_workflows_by_state "active" | \
    format_workflows
```

### Get Job Details for Latest Run
```bash
# Get latest run ID
RUN_ID=$(discover_repo_runs "octocat" "hello-world" | jq -r '.[0].databaseId')

# Get jobs for that run
discover_run_jobs "octocat" "hello-world" "$RUN_ID" | format_jobs
```

### Trigger Workflow and Wait for Completion
```bash
# Trigger workflow
trigger_workflow "octocat" "hello-world" "deploy.yml" "main" '{"env": "prod"}'

# Wait a moment for run to start
sleep 5

# Get latest run
RUN_ID=$(discover_workflow_runs "octocat" "hello-world" "deploy.yml" | jq -r '.[0].id')

# Poll status
while true; do
    STATUS=$(detect_run_status "octocat" "hello-world" "$RUN_ID")
    echo "Status: $STATUS"
    [[ "$STATUS" == "completed" ]] && break
    sleep 10
done

# Check conclusion
CONCLUSION=$(detect_run_conclusion "octocat" "hello-world" "$RUN_ID")
echo "Conclusion: $CONCLUSION"
```

---

## jq Filters Reference

See `lib/github/gh-action-jq-filters.yaml` for full filter definitions.

### Format Filters
- `format_workflows_list` - Tabular workflow list
- `format_workflow_detail` - Single workflow details
- `format_runs_list` - Tabular run list
- `format_run_detail` - Single run details
- `format_jobs_list` - Tabular job list
- `format_job_detail` - Single job details
- `format_run_summary` - Run with job summary

### Extract Filters
- `extract_workflow_ids` - Get workflow IDs
- `extract_run_ids` - Get run IDs
- `extract_job_names` - Get job names
- `extract_failed_jobs` - Get failed jobs
- `extract_pending_environments` - Get environments awaiting approval

### Summary Filters
- `count_by_status` - Count runs by status
- `count_by_conclusion` - Count runs by conclusion
- `workflow_success_rate` - Calculate success percentage
- `job_duration_summary` - Min/max/avg duration
- `recent_activity` - Recent run summary

---

## Common Workflows

### Check Workflow Health
```bash
#!/bin/bash
OWNER="octocat"
REPO="hello-world"

echo "=== Workflow Status ==="
discover_repo_workflows "$OWNER" "$REPO" | format_workflows

echo -e "\n=== Recent Runs ==="
discover_repo_runs "$OWNER" "$REPO" | \
    jq 'limit(10; .[])' | \
    format_runs

echo -e "\n=== Failed Runs (Last 24h) ==="
discover_repo_runs "$OWNER" "$REPO" "completed" | \
    filter_runs_by_conclusion "failure" | \
    jq 'map(select(.created_at > (now - 86400 | todate)))' | \
    format_runs
```

### Cancel All Queued Runs
```bash
discover_repo_runs "octocat" "hello-world" "queued" | \
    jq -r '.[].databaseId' | \
    while read run_id; do
        echo "Cancelling run $run_id"
        cancel_run "octocat" "hello-world" "$run_id"
    done
```

### Enable All Disabled Workflows
```bash
discover_repo_workflows "octocat" "hello-world" | \
    filter_workflows_by_state "disabled_manually" | \
    jq -r '.[].id' | \
    while read workflow_id; do
        echo "Enabling workflow $workflow_id"
        enable_workflow "octocat" "hello-world" "$workflow_id"
    done
```

---

## Error Handling

| Error Code | Meaning | Common Causes |
|------------|---------|---------------|
| 404 | Not found | Workflow/run/job doesn't exist |
| 403 | Forbidden | Insufficient permissions |
| 422 | Unprocessable | Invalid input (bad ref, missing workflow_dispatch trigger) |
| 409 | Conflict | Run already completed/cancelled |

### Required Scopes
```bash
gh auth refresh -s repo -s workflow
```

---

## Related Domains

- **Repository domain** - Workflows belong to repositories
- **Secret domain** - Workflows use repository/organization secrets
- **Variable domain** - Workflows use repository/organization variables

---

## API Coverage

| Operation | gh CLI | REST API | GraphQL |
|-----------|--------|----------|---------|
| List workflows | ✅ `gh workflow list` | ✅ | Limited |
| Get workflow | ✅ `gh workflow view` | ✅ | Limited |
| List runs | ✅ `gh run list` | ✅ | Read-only |
| Get run | ✅ `gh run view` | ✅ | Read-only |
| Trigger | ✅ `gh workflow run` | ✅ | ❌ |
| Cancel | ✅ `gh run cancel` | ✅ | ❌ |
| Re-run | ✅ `gh run rerun` | ✅ | ❌ |
| Enable/Disable | ✅ `gh workflow enable/disable` | ✅ | ❌ |

**Recommendation:** Use gh CLI for most operations, REST for specific mutations not in CLI.
