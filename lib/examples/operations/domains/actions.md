# Actions (Workflows, Runs, Jobs)

**REST API + gh CLI. No GraphQL support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List workflows | ✓ | ✓ | ✗ | ✓ | Full support |
| Get workflow | ✓ | ✓ | ✗ | ✓ | Full support |
| List runs | ✓ | ✓ | ✗ | ✓ | Full support |
| Get run | ✓ | ✓ | ✗ | ✓ | Full support |
| Trigger workflow | ✓ | ✓ | ✗ | ✓ | Full support |
| Cancel run | ✓ | ✓ | ✗ | ✓ | Full support |
| Re-run job | ✓ | ✓ | ✗ | ✓ | Full support |
| Re-run failed | ✓ | ✓ | ✗ | ✓ | Full support |

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
| Download logs | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/logs` | Returns ZIP |

**Note:** No GraphQL support for Actions. Use gh CLI (simpler) or REST API.
