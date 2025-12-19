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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (user) | GET | `/users/{username}/gists` | |
| List (viewer) | GET | `/gists` | Authenticated user |
| Get | GET | `/gists/{gist_id}` | |
| Create | POST | `/gists` | |
| Update | PATCH | `/gists/{gist_id}` | |
| Delete | DELETE | `/gists/{gist_id}` | |
| Fork | POST | `/gists/{gist_id}/forks` | |
| Star | PUT | `/gists/{gist_id}/star` | |
| Unstar | DELETE | `/gists/{gist_id}/star` | |
| List starred | GET | `/gists/starred` | |
| List commits | GET | `/gists/{gist_id}/commits` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `viewer.gists` or `user.gists` | |
| Get | Query | `node(id:)` | Use `Gist` type |

**Note:** GraphQL has no mutations for gist management. Use CLI (simplest) or REST API.
