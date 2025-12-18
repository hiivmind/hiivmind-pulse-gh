# Variables

**REST API + gh CLI only. No GraphQL support. No encryption needed (unlike Secrets).**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (repo) | ✓ | ✓ | ✗ | ✓ | Repository variables |
| Get (repo) | ✓ | ✓ | ✗ | ✓ | By name |
| Create (repo) | ✓ | ✓ | ✗ | ✓ | Via POST |
| Update (repo) | ✓ | ✓ | ✗ | ✓ | Via PATCH |
| Delete (repo) | ✓ | ✓ | ✗ | ✓ | |
| List (org) | ✗ | ✓ | ✗ | ✓ | Organization level |
| Create (org) | ✗ | ✓ | ✗ | ✓ | With visibility control |
| Update (org) | ✗ | ✓ | ✗ | ✓ | With visibility control |
| Delete (org) | ✗ | ✓ | ✗ | ✓ | |
| List (env) | ✗ | ✓ | ✗ | ✓ | Environment scope |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh variable list` | Repository only |
| Get | `gh variable get {name}` | Repository only |
| Set | `gh variable set {name} {value}` | Repository only; creates or updates |
| Delete | `gh variable delete {name}` | Repository only |
| Org operations | (Not available) | Use REST API |
| Env operations | (Not available) | Use REST API |

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | Repository: `GET /repos/{owner}/{repo}/actions/variables`, `POST /variables`, `PATCH /variables/{name}`, `DELETE /variables/{name}` | Organization: `GET /orgs/{org}/actions/variables`, `POST /variables` | Environment: `GET /repos/{owner}/{repo}/environments/{env_name}/variables` | `GET /actions/variables`, `POST /variables`, `PATCH /variables/{name}`, `visibility`, `selected_repository_ids` |

## Key Differences from Secrets

- **No encryption needed** - Variables are plain text
- **Org-level visibility control** - Can be marked `all`, `private`, or `selected` repositories
- **No GraphQL support** - Variables are REST-only
