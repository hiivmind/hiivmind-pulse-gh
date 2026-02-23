# Issues

**All 4 methods fully supported for core operations.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All methods work |
| Get | ✓ | ✓ | ✓ | ✓ | |
| Create | ✓ | ✓ | ✓ | ✓ | |
| Update | ✓ | ✓ | ✓ | ✓ | |
| Close | ✓ | ✓ | ✓ | ✓ | |
| Reopen | ✓ | ✓ | ✓ | ✓ | |
| Delete | ✓ | ✓ | ✓ | ✓ | |
| Add comment | ✓ | ✓ | ✓ | ✓ | |
| Add labels | ✓ | ✓ | ✓ | ✓ | Separate endpoint in REST |
| Set milestone | ✓ | ✓ | ✓ | ✓ | Via PATCH in REST |
| Lock | ✓ | ✓ | ✓ | ✓ | |
| Unlock | ✓ | ✓ | ✓ | ✓ | |
| Pin | ✓ | ✗ | ✓ | ✓ | CLI + GraphQL |
| Unpin | ✓ | ✗ | ✓ | ✓ | CLI + GraphQL |
| Transfer | ✓ | ✗ | ✓ | ✓ | CLI + GraphQL |
| Develop | ✓ | ✗ | ✗ | ✓ | Create linked branch |

## CLI Command Reference

| Operation | Command |
|-----------|---------|
| List | `gh issue list` |
| Get | `gh issue view {number}` |
| Create | `gh issue create --title {title}` |
| Update | `gh issue edit {number}` |
| Close | `gh issue close {number}` |
| Reopen | `gh issue reopen {number}` |
| Delete | `gh issue delete {number}` |
| Add comment | `gh issue comment {number} --body {body}` |
| Add labels | `gh issue edit {number} --add-label {label}` |
| Set milestone | `gh issue edit {number} --milestone {milestone}` |
| Lock | `gh issue lock {number}` |
| Unlock | `gh issue unlock {number}` |
| Pin | `gh issue pin {number}` |
| Unpin | `gh issue unpin {number}` |
| Transfer | `gh issue transfer {number} {destination-repo}` |
| Develop | `gh issue develop {number}` |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/issues` | |
| Get | GET | `/repos/{owner}/{repo}/issues/{number}` | |
| Create | POST | `/repos/{owner}/{repo}/issues` | |
| Update | PATCH | `/repos/{owner}/{repo}/issues/{number}` | |
| Close | PATCH | `/repos/{owner}/{repo}/issues/{number}` | Set `state: closed` |
| Reopen | PATCH | `/repos/{owner}/{repo}/issues/{number}` | Set `state: open` |
| Delete | DELETE | `/repos/{owner}/{repo}/issues/{number}` | |
| Add comment | POST | `/repos/{owner}/{repo}/issues/{number}/comments` | |
| Add labels | POST | `/repos/{owner}/{repo}/issues/{number}/labels` | |
| Set milestone | PATCH | `/repos/{owner}/{repo}/issues/{number}` | Set `milestone` field |
| Lock | PUT | `/repos/{owner}/{repo}/issues/{number}/lock` | |
| Unlock | DELETE | `/repos/{owner}/{repo}/issues/{number}/lock` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.issues` | |
| Get | Query | `node(id:)` | Use `Issue` type |
| Create | Mutation | `createIssue` | |
| Update | Mutation | `updateIssue` | |
| Close | Mutation | `closeIssue` | |
| Reopen | Mutation | `reopenIssue` | |
| Delete | Mutation | `deleteIssue` | |
| Add comment | Mutation | `addComment` | |
| Add labels | Mutation | `addLabelsToLabelable` | |
| Remove labels | Mutation | `removeLabelsFromLabelable` | |
| Set milestone | Mutation | `updateIssue` | Set `milestoneId` field |
| Lock | Mutation | `lockLockable` | |
| Unlock | Mutation | `unlockLockable` | |
| Pin | Mutation | `pinIssue` | |
| Unpin | Mutation | `unpinIssue` | |
| Transfer | Mutation | `transferIssue` | |
