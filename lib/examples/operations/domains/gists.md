# Gists

**Full CLI + REST support. GraphQL read-only. No authentication required to read public gists.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | User's gists |
| Get | ✓ | ✓ | ✓ | ✓ | By ID |
| Create | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update/Edit | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Clone | ✓ | ✗ | ✗ | ✗ | CLI only (git operation) |
| Rename file | ✓ | ✓ | ✗ | ✓ | Rename file within gist |
| Fork | ✗ | ✓ | ✗ | ✓ | No CLI support |
| Star | ✗ | ✓ | ✗ | ✓ | No CLI support |
| Unstar | ✗ | ✓ | ✗ | ✓ | No CLI support |
| List starred | ✗ | ✓ | ✓ | ✓ | Via user gists query |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh gist list` | Your gists |
| Get | `gh gist view {id}` | View gist contents |
| Create | `gh gist create {file}` | Use `--public` for public gists |
| Edit | `gh gist edit {id}` | Opens editor |
| Delete | `gh gist delete {id}` | |
| Clone | `gh gist clone {id}` | Clone to local directory |
| Rename | `gh gist rename {id} {old} {new}` | Rename file in gist |

## Corpus Lookup Guide

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /gists`, `GET /gists/{gist_id}`, `GET /users/{username}/gists`, `POST /gists`, `PATCH /gists/{gist_id}`, `DELETE /gists/{gist_id}`, `POST /gists/{gist_id}/forks`, `PUT /gists/{gist_id}/star`, `DELETE /gists/{gist_id}/star`, `GET /gists/starred` | `GET /gists`, `POST /gists`, `PATCH /gists/{gist_id}`, `PUT /star`, `DELETE /star` |
| GraphQL | `gist`, `gists` (queries via user/viewer) - No mutations available | `query { viewer { gists } }`, `query { user { gists } }` |

**Note:** GraphQL has no mutations for gist management. Use CLI (simplest) or REST API.
