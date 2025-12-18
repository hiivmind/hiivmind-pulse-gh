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

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/actions/workflows`, `GET /actions/workflows/{workflow_id}`, `GET /actions/runs`, `POST /actions/workflows/{workflow_id}/dispatches`, `POST /actions/runs/{run_id}/cancel`, `POST /actions/runs/{run_id}/rerun` | `GET /actions/workflows`, `GET /actions/runs`, `POST /dispatches`, `workflow_dispatch`, `run_id` |

**Note:** No GraphQL support for Actions. Use gh CLI (simpler) or REST API.
