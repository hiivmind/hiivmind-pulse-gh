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

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/environments`, `GET /environments/{environment_name}`, `PUT /environments/{environment_name}`, `DELETE /environments/{environment_name}`, `GET /environments/{environment_name}/secrets`, `PUT /environments/{environment_name}/secrets/{secret_name}`, `GET /environments/{environment_name}/variables` | `GET /environments`, `PUT /environments`, `DELETE /environments`, `secrets`, `variables`, `protection_rules` |
| GraphQL | `environment` (query), `createEnvironment`, `updateEnvironment`, `deleteEnvironment` (mutations) | `query { repository { environments } }`, `mutation { createEnvironment }`, `mutation { updateEnvironment }` |

**Note:** Environments provide deployment targets with protection rules (required reviewers, wait timers, branch policies). Environment secrets/variables use REST endpoints under `/environments/{name}/secrets` and `/environments/{name}/variables`.
