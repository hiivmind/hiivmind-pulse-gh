# Search

**Full CLI + REST + GraphQL support. Read-only operations (search is inherently read-only).**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Search repos | ✓ | ✓ | ✓ | ✓ | Full search syntax support |
| Search issues | ✓ | ✓ | ✓ | ✓ | Full search syntax support |
| Search PRs | ✓ | ✓ | ✓ | ✓ | Full search syntax support |
| Search code | ✓ | ✓ | ✓ | ✓ | Rate limited |
| Search commits | ✓ | ✓ | ✗ | ✓ | No GraphQL support |
| Search users | ✗ | ✓ | ✓ | ✓ | No CLI support |
| Search topics | ✗ | ✓ | ✗ | ✓ | REST only |
| Search labels | ✗ | ✓ | ✗ | ✓ | REST only |
| Search discussions | ✗ | ✗ | ✓ | ✓ | GraphQL only |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| Search repos | `gh search repos {query}` | Rich filtering flags |
| Search issues | `gh search issues {query}` | Use `--` for queries with `-` |
| Search PRs | `gh search prs {query}` | Same syntax as issues |
| Search code | `gh search code {query}` | Rate limited |
| Search commits | `gh search commits {query}` | |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| Search repos | GET | `/search/repositories` | |
| Search issues | GET | `/search/issues` | Also includes PRs |
| Search code | GET | `/search/code` | Rate limited |
| Search commits | GET | `/search/commits` | |
| Search users | GET | `/search/users` | |
| Search topics | GET | `/search/topics` | |
| Search labels | GET | `/search/labels` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| Search repos | Query | `search(type: REPOSITORY)` | |
| Search issues | Query | `search(type: ISSUE)` | Also includes PRs |
| Search issues (advanced) | Query | `search(type: ISSUE_ADVANCED)` | Extended filters |
| Search discussions | Query | `search(type: DISCUSSION)` | |
| Search users | Query | `search(type: USER)` | |

**Note:** Search is read-only. Code search is heavily rate limited.
