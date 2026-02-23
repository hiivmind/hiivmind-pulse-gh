# Actions (Workflows, Runs, Jobs)

**REST API + gh CLI. No GraphQL support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List workflows | ✓ | ✓ | ✗ | ✓ | Full support |
| Get workflow | ✓ | ✓ | ✗ | ✓ | Full support |
| Disable workflow | ✓ | ✓ | ✗ | ✓ | |
| Enable workflow | ✓ | ✓ | ✗ | ✓ | |
| List runs | ✓ | ✓ | ✗ | ✓ | Full support |
| Get run | ✓ | ✓ | ✗ | ✓ | Full support |
| Trigger workflow | ✓ | ✓ | ✗ | ✓ | Full support |
| Cancel run | ✓ | ✓ | ✗ | ✓ | Full support |
| Delete run | ✓ | ✓ | ✗ | ✗ | |
| Re-run job | ✓ | ✓ | ✗ | ✓ | Full support |
| Re-run failed | ✓ | ✓ | ✗ | ✓ | Full support |
| Watch run | ✓ | ✗ | ✗ | ✓ | CLI only — live status |
| Download artifacts | ✓ | ✓ | ✗ | ✓ | |
| List caches | ✓ | ✓ | ✗ | ✗ | Action cache management |
| Delete cache | ✓ | ✓ | ✗ | ✗ | Action cache management |

## CLI Command Reference

| Operation | Command |
|-----------|---------|
| List workflows | `gh workflow list` |
| Get workflow | `gh workflow view {workflow-id}` |
| List runs | `gh run list` |
| Get run | `gh run view {run-id}` |
| Trigger workflow | `gh workflow run {workflow-name}` |
| Cancel run | `gh run cancel {run-id}` |
| Re-run job | `gh run rerun {run-id}` |
| Re-run failed | `gh run rerun {run-id} --failed` |
| Delete run | `gh run delete {run-id}` |
| Watch run | `gh run watch {run-id}` |
| Download artifacts | `gh run download {run-id}` |
| Disable workflow | `gh workflow disable {workflow-id}` |
| Enable workflow | `gh workflow enable {workflow-id}` |
| List caches | `gh cache list` |
| Delete cache | `gh cache delete {key}` |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List workflows | GET | `/repos/{owner}/{repo}/actions/workflows` | |
| Get workflow | GET | `/repos/{owner}/{repo}/actions/workflows/{workflow_id}` | |
| List runs | GET | `/repos/{owner}/{repo}/actions/runs` | |
| Get run | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}` | |
| Trigger workflow | POST | `/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` | Requires `workflow_dispatch` |
| Cancel run | POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/cancel` | |
| Re-run jobs | POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/rerun` | |
| Re-run failed | POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs` | |
| List jobs | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` | |
| Get job | GET | `/repos/{owner}/{repo}/actions/jobs/{job_id}` | |
| Delete run | DELETE | `/repos/{owner}/{repo}/actions/runs/{run_id}` | |
| Download logs | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/logs` | Returns ZIP |
| Download artifacts | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts` | |
| Disable workflow | PUT | `/repos/{owner}/{repo}/actions/workflows/{workflow_id}/disable` | |
| Enable workflow | PUT | `/repos/{owner}/{repo}/actions/workflows/{workflow_id}/enable` | |
| List caches | GET | `/repos/{owner}/{repo}/actions/caches` | |
| Delete cache | DELETE | `/repos/{owner}/{repo}/actions/caches/{cache_id}` | By ID |
| Delete cache (key) | DELETE | `/repos/{owner}/{repo}/actions/caches?key={key}` | By key |

**Note:** No GraphQL support for Actions. Use gh CLI (simpler) or REST API.
