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
| Revert | ✓ | ✓ | ✓ | ✓ | Creates revert PR |
| Ready | ✓ | ✓ | ✓ | ✓ | Mark draft as ready |
| Update branch | ✓ | ✓ | ✗ | ✓ | Sync with base branch |
| Request review | ✓ | ✓ | ✓ | ✓ | |
| Add comment | ✓ | ✓ | ✓ | ✓ | |
| Dismiss review | ✗ | ✓ | ✓ | ✓ | CLI not available |
| Lock | ✓ | ✓ | ✓ | ✓ | |
| Unlock | ✓ | ✓ | ✓ | ✓ | |
| Checkout | ✓ | ✗ | ✗ | ✗ | CLI only (git operation) |
| Checks | ✓ | ✗ | ✗ | ✓ | View CI status |
| Diff | ✓ | ✗ | ✗ | ✓ | View changes |

## CLI Command Reference

| Operation | Command |
|-----------|---------|
| List | `gh pr list` |
| Get | `gh pr view {number}` |
| Create | `gh pr create --title {title}` |
| Update | `gh pr edit {number}` |
| Merge | `gh pr merge {number}` |
| Close | `gh pr close {number}` |
| Revert | `gh pr revert {number}` |
| Ready | `gh pr ready {number}` |
| Update branch | `gh pr update-branch {number}` |
| Request review | `gh pr review --request-review {reviewer}` |
| Add comment | `gh pr comment {number} --body {body}` |
| Dismiss review | (Web UI only) |
| Lock | `gh pr lock {number}` |
| Unlock | `gh pr unlock {number}` |
| Checkout | `gh pr checkout {number}` |
| Checks | `gh pr checks {number}` |
| Diff | `gh pr diff {number}` |

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
| Revert | POST | `/repos/{owner}/{repo}/pulls/{number}/revert` | Creates revert PR |
| Mark ready | PATCH | `/repos/{owner}/{repo}/pulls/{number}` | Set `draft: false` |
| Update branch | PUT | `/repos/{owner}/{repo}/pulls/{number}/update-branch` | Sync with base |
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
| Revert | Mutation | `revertPullRequest` | Creates revert PR |
| Mark ready | Mutation | `markPullRequestReadyForReview` | |
| Request review | Mutation | `requestReviews` | |
| Add comment | Mutation | `addComment` | |
| Dismiss review | Mutation | `dismissPullRequestReview` | |
| Lock | Mutation | `lockLockable` | |
| Unlock | Mutation | `unlockLockable` | |
