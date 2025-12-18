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

## Corpus Lookup Guide

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /search/repositories`, `GET /search/issues`, `GET /search/code`, `GET /search/commits`, `GET /search/users`, `GET /search/topics`, `GET /search/labels` | `GET /search/repositories`, `q=`, `sort=`, `order=`, `per_page` |
| GraphQL | `search(query: String!, type: SearchType!, first: Int)` - Types: REPOSITORY, ISSUE, ISSUE_ADVANCED, DISCUSSION, USER | `query { search(query: "...", type: REPOSITORY) { ... } }` |

**Note:** Search is read-only. GraphQL search returns a union type that includes Repository, Issue, PullRequest, Discussion, User. Code search is heavily rate limited.
