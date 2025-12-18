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

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/issues/{issue_number}/reactions`, `POST /issues/{issue_number}/reactions`, `DELETE /reactions/{reaction_id}`, `GET /issues/comments/{comment_id}/reactions`, `POST /issues/comments/{comment_id}/reactions`, `GET /pulls/comments/{comment_id}/reactions` | `GET /reactions`, `POST /reactions`, `DELETE /reactions`, `content` (+1, -1, laugh, confused, heart, hooray, rocket, eyes) |
| GraphQL | `reactions` (query on Reactable types), `addReaction`, `removeReaction` (mutations) | `query { issue { reactions } }`, `mutation { addReaction(input: {subjectId: ..., content: THUMBS_UP}) }` |

## Reaction Types

- REST: `+1`, `-1`, `laugh`, `confused`, `heart`, `hooray`, `rocket`, `eyes`
- GraphQL enum: `THUMBS_UP`, `THUMBS_DOWN`, `LAUGH`, `CONFUSED`, `HEART`, `HOORAY`, `ROCKET`, `EYES`
