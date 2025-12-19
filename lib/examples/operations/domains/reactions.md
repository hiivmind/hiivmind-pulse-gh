# Reactions

**Full GraphQL support. REST API available. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (issue) | ✗ | ✓ | ✓ | ✓ | |
| List (comment) | ✗ | ✓ | ✓ | ✓ | |
| List (PR) | ✗ | ✓ | ✓ | ✓ | |
| Add | ✗ | ✓ | ✓ | ✓ | addReaction mutation |
| Remove | ✗ | ✓ | ✓ | ✓ | removeReaction mutation |
| Delete (by ID) | ✗ | ✓ | ✗ | ✗ | REST only |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or GraphQL |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (issue) | GET | `/repos/{owner}/{repo}/issues/{issue_number}/reactions` | |
| Add (issue) | POST | `/repos/{owner}/{repo}/issues/{issue_number}/reactions` | |
| List (issue comment) | GET | `/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions` | |
| Add (issue comment) | POST | `/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions` | |
| List (PR comment) | GET | `/repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions` | |
| Add (PR comment) | POST | `/repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions` | |
| Delete | DELETE | `/repos/{owner}/{repo}/issues/{issue_number}/reactions/{reaction_id}` | By ID |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `issue.reactions`, `pullRequest.reactions` | On Reactable types |
| Add | Mutation | `addReaction` | `subjectId` + `content` |
| Remove | Mutation | `removeReaction` | `subjectId` + `content` |

## Reaction Types

- REST: `+1`, `-1`, `laugh`, `confused`, `heart`, `hooray`, `rocket`, `eyes`
- GraphQL enum: `THUMBS_UP`, `THUMBS_DOWN`, `LAUGH`, `CONFUSED`, `HEART`, `HOORAY`, `ROCKET`, `EYES`
