# Notifications

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✗ | ✓ | All notifications |
| Mark as read | ✗ | ✓ | ✗ | ✓ | Single notification |
| Mark all read | ✗ | ✓ | ✗ | ✓ | All or per-repo |
| Get thread | ✗ | ✓ | ✗ | ✓ | |
| Mark thread read | ✗ | ✓ | ✗ | ✓ | |
| Get subscription | ✗ | ✓ | ✗ | ✓ | Thread subscription |
| Set subscription | ✗ | ✓ | ✗ | ✓ | Subscribe/ignore |
| Delete subscription | ✗ | ✓ | ✗ | ✓ | Unsubscribe |
| List repo notifications | ✗ | ✓ | ✗ | ✓ | Scoped to repo |
| Mark repo read | ✗ | ✓ | ✗ | ✓ | All in repo |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| View status | `gh status` | Shows notifications summary |
| All mutations | (Not available) | Use REST API |

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /notifications`, `PUT /notifications`, `GET /notifications/threads/{thread_id}`, `PATCH /notifications/threads/{thread_id}`, `GET /notifications/threads/{thread_id}/subscription`, `PUT /notifications/threads/{thread_id}/subscription`, `DELETE /notifications/threads/{thread_id}/subscription`, `GET /repos/{owner}/{repo}/notifications`, `PUT /repos/{owner}/{repo}/notifications` | `GET /notifications`, `PUT /notifications`, `threads`, `subscription`, `all`, `participating` |

**Note:** Notifications are REST-only. The `gh status` command shows a summary but doesn't support mutations.
