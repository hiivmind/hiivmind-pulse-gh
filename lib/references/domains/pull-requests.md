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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/pulls` | |
| Get | GET | `/repos/{owner}/{repo}/pulls/{number}` | |
| Create | POST | `/repos/{owner}/{repo}/pulls` | |
| Update | PATCH | `/repos/{owner}/{repo}/pulls/{number}` | |
| Merge | PUT | `/repos/{owner}/{repo}/pulls/{number}/merge` | |
| Close | PATCH | `/repos/{owner}/{repo}/pulls/{number}` | Set `state: closed` |
| Request review | POST | `/repos/{owner}/{repo}/pulls/{number}/requested_reviewers` | |
| Remove reviewer | DELETE | `/repos/{owner}/{repo}/pulls/{number}/requested_reviewers` | |
| Add comment | POST | `/repos/{owner}/{repo}/pulls/{number}/comments` | |
| Dismiss review | PUT | `/repos/{owner}/{repo}/pulls/{number}/reviews/{review_id}/dismissals` | |
| Lock | PUT | `/repos/{owner}/{repo}/issues/{number}/lock` | Uses issues endpoint |
| Unlock | DELETE | `/repos/{owner}/{repo}/issues/{number}/lock` | Uses issues endpoint |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.pullRequests` | |
| Get | Query | `node(id:)` | Use `PullRequest` type |
| Create | Mutation | `createPullRequest` | |
| Update | Mutation | `updatePullRequest` | |
| Merge | Mutation | `mergePullRequest` | |
| Close | Mutation | `closePullRequest` | |
| Request review | Mutation | `requestReviews` | |
| Add comment | Mutation | `addComment` | |
| Dismiss review | Mutation | `dismissPullRequestReview` | |
