# Deployments

**REST + GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | |
| Get | ✗ | ✓ | ✓ | ✓ | |
| Create | ✗ | ✓ | ✓ | ✗ | createDeployment mutation |
| Delete | ✗ | ✓ | ✗ | ✗ | REST only, inactive only |
| Create status | ✗ | ✓ | ✓ | ✗ | createDeploymentStatus mutation |
| List statuses | ✗ | ✓ | ✓ | ✓ | |
| Get status | ✗ | ✓ | ✓ | ✓ | |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or GraphQL |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/deployments` | |
| Get | GET | `/repos/{owner}/{repo}/deployments/{deployment_id}` | |
| Create | POST | `/repos/{owner}/{repo}/deployments` | |
| Delete | DELETE | `/repos/{owner}/{repo}/deployments/{deployment_id}` | Inactive only |
| List statuses | GET | `/repos/{owner}/{repo}/deployments/{deployment_id}/statuses` | |
| Get status | GET | `/repos/{owner}/{repo}/deployments/{deployment_id}/statuses/{status_id}` | |
| Create status | POST | `/repos/{owner}/{repo}/deployments/{deployment_id}/statuses` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.deployments` | |
| Get | Query | `node(id:)` | Use `Deployment` type |
| List statuses | Query | `deployment.statuses` | |
| Create | Mutation | `createDeployment` | |
| Create status | Mutation | `createDeploymentStatus` | |

**Note:** Deployments track code being deployed to environments. Use with environments for full deployment workflow.
