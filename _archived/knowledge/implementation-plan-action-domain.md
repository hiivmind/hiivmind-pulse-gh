# Implementation Plan: Action Domain

> **Document ID:** IMPL-004
> **Created:** 2025-12-11
> **Status:** Planning
> **GitHub Issue:** #17

## Overview

Implement the Action domain for GitHub Actions workflows, runs, and jobs. This domain provides access to CI/CD workflow management, execution history, and job details.

## Design Decision

**Action domain will be Layer 2 primitives only** - No Layer 3 (Smart Application) functions needed.

**Rationale:**
- Simple CRUD operations (no 40+ field configurations like Protection domain)
- No schema variations between org/personal repos
- No context detection requirements
- Native `gh workflow` and `gh run` CLI commands handle most operations elegantly

## API Strategy

| Operation Category | Primary API | Reason |
|-------------------|-------------|---------|
| List workflows | gh CLI (`gh workflow list --json`) | Native pagination, formatting |
| List runs | gh CLI (`gh run list --json`) | Rich filtering (status, branch, event) |
| View details | gh CLI → REST fallback | CLI for common cases, REST for specific fields |
| Mutations | REST API | Enable/disable, trigger, cancel, rerun |
| GraphQL | **Not used** | Read-only, limited fields, no mutations |

### GraphQL Limitations

**Why we're skipping GraphQL for Actions:**
- `Workflow` type: Only basic fields (id, name, state, createdAt, updatedAt)
- `WorkflowRun` type: Read-only, no mutations available
- No mutation support for: trigger, cancel, rerun, enable, disable
- REST API is complete and well-supported

## Primitive Specification

### FETCH Primitives (6)

| Function | API | Purpose |
|----------|-----|---------|
| `fetch_workflow` | REST | Get single workflow by ID/filename |
| `fetch_workflow_usage` | REST | Get billable minutes (deprecated endpoint) |
| `fetch_run` | REST | Get workflow run details |
| `fetch_run_logs` | REST | Download run logs (302 redirect) |
| `fetch_job` | REST | Get job details |
| `fetch_job_logs` | REST | Download job logs |

**Signature pattern:**
```bash
fetch_workflow "owner" "repo" "workflow_id"   # ID or filename (main.yaml)
fetch_run "owner" "repo" "run_id"
fetch_job "owner" "repo" "job_id"
```

### DISCOVER Primitives (5)

| Function | API | Purpose |
|----------|-----|---------|
| `discover_repo_workflows` | gh CLI | List all workflows in repo |
| `discover_repo_runs` | gh CLI | List all runs in repo (with filters) |
| `discover_workflow_runs` | gh CLI/REST | List runs for specific workflow |
| `discover_run_jobs` | REST | List jobs in a run |
| `discover_pending_deployments` | REST | Get pending deployment requests |

**Signature pattern:**
```bash
discover_repo_workflows "owner" "repo"
discover_repo_runs "owner" "repo"              # All runs
discover_workflow_runs "owner" "repo" "workflow_id"
discover_run_jobs "owner" "repo" "run_id"
```

### LOOKUP Primitives (2)

| Function | API | Purpose |
|----------|-----|---------|
| `get_workflow_id` | gh CLI/REST | Resolve filename → workflow ID |
| `get_run_id` | N/A | Runs use numeric IDs (no lookup needed) |

**Note:** Workflows accept both numeric IDs and filenames, so lookup is optional.

### FILTER Primitives (5)

| Function | Purpose |
|----------|---------|
| `filter_runs_by_status` | Keep runs matching status (completed, in_progress, queued, etc.) |
| `filter_runs_by_branch` | Keep runs from specific branch |
| `filter_runs_by_event` | Keep runs triggered by event (push, pull_request, etc.) |
| `filter_runs_by_actor` | Keep runs triggered by specific user |
| `filter_workflows_by_state` | Keep workflows in state (active, disabled, etc.) |

**Input/Output:** JSON from stdin → filtered JSON to stdout

### FORMAT Primitives (4)

| Function | Purpose |
|----------|---------|
| `format_workflows` | Tabular workflow list (name, state, ID) |
| `format_workflow` | Single workflow details |
| `format_runs` | Tabular run list (number, status, branch, event) |
| `format_run` | Single run details with jobs summary |
| `format_jobs` | Tabular job list (name, status, started, completed) |

### DETECT Primitives (3)

| Function | Returns | Purpose |
|----------|---------|---------|
| `detect_workflow_state` | "active" \| "disabled_manually" | Check if workflow is enabled |
| `detect_run_status` | "completed" \| "in_progress" \| "queued" | Check run status |
| `detect_run_conclusion` | "success" \| "failure" \| "cancelled" | Check run result (if completed) |

### MUTATE Primitives (8)

| Function | API | Purpose |
|----------|-----|---------|
| `trigger_workflow` | REST POST | Create workflow dispatch event |
| `enable_workflow` | REST PUT | Enable disabled workflow |
| `disable_workflow` | REST PUT | Disable workflow |
| `cancel_run` | REST POST | Cancel in-progress run |
| `force_cancel_run` | REST POST | Force cancel run |
| `rerun_workflow` | REST POST | Re-run entire workflow |
| `rerun_failed_jobs` | REST POST | Re-run only failed jobs |
| `delete_run_logs` | REST DELETE | Delete workflow run logs |
| `review_pending_deployment` | REST POST | Approve/reject pending deployment |

**Signature pattern:**
```bash
trigger_workflow "owner" "repo" "workflow_id" "ref" ["inputs_json"]
enable_workflow "owner" "repo" "workflow_id"
cancel_run "owner" "repo" "run_id"
rerun_workflow "owner" "repo" "run_id" ["enable_debug"]
```

## Total: 33 Primitives

- FETCH: 6
- DISCOVER: 5
- LOOKUP: 2
- FILTER: 5
- FORMAT: 4
- DETECT: 3
- MUTATE: 8

## REST API Endpoints Reference

### Workflows
- `GET /repos/{owner}/{repo}/actions/workflows` - List workflows
- `GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}` - Get workflow
- `PUT /repos/{owner}/{repo}/actions/workflows/{workflow_id}/enable` - Enable
- `PUT /repos/{owner}/{repo}/actions/workflows/{workflow_id}/disable` - Disable
- `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` - Trigger
- `GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}/timing` - Usage (deprecated)

### Workflow Runs
- `GET /repos/{owner}/{repo}/actions/runs` - List all runs
- `GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs` - List runs for workflow
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}` - Get run
- `POST /repos/{owner}/{repo}/actions/runs/{run_id}/cancel` - Cancel
- `POST /repos/{owner}/{repo}/actions/runs/{run_id}/force-cancel` - Force cancel
- `POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun` - Re-run
- `POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs` - Re-run failed
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/logs` - Download logs
- `DELETE /repos/{owner}/{repo}/actions/runs/{run_id}/logs` - Delete logs
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` - Pending deployments
- `POST /repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` - Review deployment

### Workflow Jobs
- `GET /repos/{owner}{repo}/actions/runs/{run_id}/jobs` - List jobs
- `GET /repos/{owner}/{repo}/actions/jobs/{job_id}` - Get job
- `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs` - Download job logs

## gh CLI Commands

```bash
# Workflows
gh workflow list --repo owner/repo --json id,name,path,state
gh workflow view WORKFLOW --repo owner/repo
gh workflow enable WORKFLOW --repo owner/repo
gh workflow disable WORKFLOW --repo owner/repo
gh workflow run WORKFLOW --repo owner/repo --ref branch

# Runs
gh run list --repo owner/repo --json databaseId,status,conclusion,headBranch,event
gh run view RUN_ID --repo owner/repo
gh run cancel RUN_ID --repo owner/repo
gh run rerun RUN_ID --repo owner/repo
gh run download RUN_ID --repo owner/repo  # Downloads artifacts, not logs
gh run watch RUN_ID --repo owner/repo
```

## Data Structures

### Workflow Object
```json
{
  "id": 161335,
  "node_id": "MDg6V29ya2Zsb3cxNjEzMzU=",
  "name": "CI",
  "path": ".github/workflows/ci.yml",
  "state": "active",
  "created_at": "2019-12-06T14:20:20.000Z",
  "updated_at": "2019-12-06T14:20:20.000Z",
  "url": "https://api.github.com/repos/octocat/hello-world/actions/workflows/161335",
  "html_url": "https://github.com/octocat/hello-world/blob/main/.github/workflows/ci.yml",
  "badge_url": "https://github.com/octocat/hello-world/workflows/CI/badge.svg"
}
```

### Workflow Run Object
```json
{
  "id": 30433642,
  "name": "CI",
  "node_id": "MDExOldvcmtmbG93UnVuMzA0MzM2NDI=",
  "head_branch": "main",
  "head_sha": "acb5820ced9479c074f688cc328bf03f341a511d",
  "run_number": 106,
  "event": "push",
  "status": "completed",
  "conclusion": "success",
  "workflow_id": 161335,
  "created_at": "2020-01-22T19:33:08Z",
  "updated_at": "2020-01-22T19:33:08Z",
  "actor": { "login": "octocat", ... },
  "run_attempt": 1,
  "pull_requests": []
}
```

### Workflow Job Object
```json
{
  "id": 399444496,
  "run_id": 29679449,
  "run_url": "https://api.github.com/repos/octocat/hello-world/actions/runs/29679449",
  "node_id": "MDg6Q2hlY2tSdW4zOTk0NDQ0OTY=",
  "head_sha": "f83a356604ae3c5d03e1b46ef4d1ca77d64a90b0",
  "url": "https://api.github.com/repos/octocat/hello-world/actions/jobs/399444496",
  "html_url": "https://github.com/octocat/hello-world/runs/399444496",
  "status": "completed",
  "conclusion": "success",
  "started_at": "2020-01-20T17:42:40Z",
  "completed_at": "2020-01-20T17:44:39Z",
  "name": "build",
  "steps": [ ... ]
}
```

## Files to Create

1. **`lib/github/gh-action-functions.sh`** (~600 lines)
   - 33 primitive functions
   - Follow ARCH-001 Layer 2 patterns
   - Use gh CLI where appropriate, REST for mutations

2. **`lib/github/gh-action-graphql-queries.yaml`** (minimal or skip)
   - Decision: **SKIP** - GraphQL provides no value for Actions
   - All operations handled by gh CLI or REST

3. **`lib/github/gh-action-jq-filters.yaml`** (~200 lines)
   - Format filters: `format_workflows_list`, `format_workflow_detail`, `format_runs_list`, `format_run_detail`, `format_jobs_list`
   - Extract filters: `extract_workflow_ids`, `extract_run_ids`, `extract_job_names`
   - Filter operations: `filter_by_status`, `filter_by_branch`, `filter_by_event`

4. **`lib/github/gh-action-index.md`** (~400 lines)
   - Quick reference table
   - Function details with examples
   - jq filters reference
   - Composition examples
   - Common workflows

## Why No Layer 3 Functions?

Action domain **does not need** Smart Application functions because:

1. **No context detection required** - Workflows work identically for org/personal repos
2. **No schema variations** - Same API structure regardless of repository type
3. **No complex templates** - Operations are simple (trigger, cancel, enable)
4. **gh CLI is already smart** - `gh workflow run` handles ref validation, input prompts
5. **No multi-step compositions** - Each operation is self-contained

**Comparison with Protection domain (which HAS Layer 3):**
- Protection: 40+ fields, org vs personal schemas, `restrictions` object complexity
- Action: 1-3 parameters max, uniform API, no variations

## Implementation Tasks

- [x] Research GitHub Actions REST API
- [x] Research GraphQL schema (determined: not useful)
- [x] Design primitive specification
- [ ] Create `gh-action-functions.sh` with 33 primitives
- [ ] Create `gh-action-jq-filters.yaml`
- [ ] Create `gh-action-index.md`
- [ ] Update `CLAUDE.md` with Action domain section
- [ ] Test key workflows

## Acceptance Criteria

1. All 33 primitives implemented and tested
2. Functions follow ARCH-001 Layer 2 patterns:
   - Explicit parameters (owner, repo, workflow_id, run_id)
   - Stdin→stdout for data flow (filters, formatters)
   - No context detection (leave that to Layer 4 Skills)
3. Error handling: stderr for errors, proper exit codes
4. Composition works: `discover_repo_runs | filter_runs_by_status "failed" | format_runs`
5. Documentation complete in gh-action-index.md
6. Integration with existing domains (repos, issues for run context)

## Related Documents

- **ARCH-001:** `knowledge/architecture-principles.md` - Layer 2 primitive patterns
- **ARCH-002:** `knowledge/domain-segmentation.md` - Domain boundaries
- **Issue #17:** P2 Action Domain Implementation
