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

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/deployments`, `GET /deployments/{deployment_id}`, `POST /repos/{owner}/{repo}/deployments`, `DELETE /deployments/{deployment_id}`, `POST /deployments/{deployment_id}/statuses`, `GET /deployments/{deployment_id}/statuses` | `GET /deployments`, `POST /deployments`, `POST /statuses`, `environment`, `ref`, `task` |
| GraphQL | `deployment`, `deployments` (queries), `createDeployment`, `createDeploymentStatus` (mutations) | `query { repository { deployments } }`, `mutation { createDeployment }`, `mutation { createDeploymentStatus }` |

**Note:** Deployments track code being deployed to environments. Use with environments for full deployment workflow.
