# Pull Requests

**All 4 methods fully supported for core operations.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All methods work |
| Get | ✓ | ✓ | ✓ | ✓ | |
| Create | ✓ | ✓ | ✓ | ✓ | |
| Update | ✓ | ✓ | ✓ | ✓ | |
| Merge | ✓ | ✓ | ✓ | ✓ | |
| Close | ✓ | ✓ | ✓ | ✓ | |
| Request review | ✓ | ✓ | ✓ | ✓ | |
| Add comment | ✓ | ✓ | ✓ | ✓ | |
| Dismiss review | ✗ | ✓ | ✓ | ✓ | CLI not available |
| Lock | ✗ | ✓ | ✗ | ✓ | REST-only |
| Unlock | ✗ | ✓ | ✗ | ✓ | REST-only |

## CLI Command Reference

| Operation | Command |
|-----------|---------|
| List | `gh pr list` |
| Get | `gh pr view {number}` |
| Create | `gh pr create --title {title}` |
| Update | `gh pr edit {number}` |
| Merge | `gh pr merge {number}` |
| Close | `gh pr close {number}` |
| Request review | `gh pr review --request-review {reviewer}` |
| Add comment | `gh pr comment {number} --body {body}` |
| Dismiss review | (Web UI only) |
| Lock | (Web UI only) |
| Unlock | (Web UI only) |

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/pulls`, `GET /pulls/{number}`, `POST /pulls`, `PATCH /pulls/{number}`, `PUT /pulls/{number}/merge`, `POST /pulls/{number}/comments`, `DELETE /pulls/{number}/requested_reviewers` | `GET /repos`, `POST /pulls`, `PATCH /pulls/{number}`, `PUT /pulls/{number}/merge`, `pulls/{number}/comments`, `pulls/{number}/requested_reviewers` |
| GraphQL | `pullRequest`, `pullRequests` (queries), `createPullRequest`, `updatePullRequest`, `mergePullRequest`, `closePullRequest`, `requestReviews`, `addComment`, `dismissPullRequestReview` (mutations) | `query { pullRequest }`, `query { repository { pullRequests } }`, `mutation { createPullRequest }`, `mutation { mergePullRequest }` |
