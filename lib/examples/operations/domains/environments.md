# Environments

**Full GraphQL support. REST API available. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | |
| Get | ✗ | ✓ | ✓ | ✓ | By name |
| Create | ✗ | ✓ | ✓ | ✓ | createEnvironment mutation |
| Update | ✗ | ✓ | ✓ | ✓ | updateEnvironment mutation |
| Delete | ✗ | ✓ | ✓ | ✓ | deleteEnvironment mutation |
| Get secrets | ✗ | ✓ | ✗ | ✓ | Via secrets endpoints |
| Set secret | ✗ | ✓ | ✗ | ✓ | Via secrets endpoints |
| Get variables | ✗ | ✓ | ✗ | ✓ | Via variables endpoints |
| Set variable | ✗ | ✓ | ✗ | ✓ | Via variables endpoints |
| Set protection rules | ✗ | ✓ | ✓ | ✓ | Reviewers, wait timer, branch policy |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or GraphQL |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/environments` | |
| Get | GET | `/repos/{owner}/{repo}/environments/{environment_name}` | |
| Create/Update | PUT | `/repos/{owner}/{repo}/environments/{environment_name}` | Upsert |
| Delete | DELETE | `/repos/{owner}/{repo}/environments/{environment_name}` | |
| List secrets | GET | `/repos/{owner}/{repo}/environments/{environment_name}/secrets` | |
| Get secret | GET | `/repos/{owner}/{repo}/environments/{environment_name}/secrets/{secret_name}` | |
| Set secret | PUT | `/repos/{owner}/{repo}/environments/{environment_name}/secrets/{secret_name}` | |
| Delete secret | DELETE | `/repos/{owner}/{repo}/environments/{environment_name}/secrets/{secret_name}` | |
| List variables | GET | `/repos/{owner}/{repo}/environments/{environment_name}/variables` | |
| Set variable | POST | `/repos/{owner}/{repo}/environments/{environment_name}/variables` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.environments` | |
| Get | Query | `node(id:)` | Use `Environment` type |
| Create | Mutation | `createEnvironment` | |
| Update | Mutation | `updateEnvironment` | |
| Delete | Mutation | `deleteEnvironment` | |

**Note:** Environments provide deployment targets with protection rules (required reviewers, wait timers, branch policies).
