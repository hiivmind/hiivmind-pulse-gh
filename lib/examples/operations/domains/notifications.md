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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/notifications` | All notifications |
| Mark all read | PUT | `/notifications` | |
| Get thread | GET | `/notifications/threads/{thread_id}` | |
| Mark thread read | PATCH | `/notifications/threads/{thread_id}` | |
| Get subscription | GET | `/notifications/threads/{thread_id}/subscription` | |
| Set subscription | PUT | `/notifications/threads/{thread_id}/subscription` | Subscribe/ignore |
| Delete subscription | DELETE | `/notifications/threads/{thread_id}/subscription` | |
| List repo notifications | GET | `/repos/{owner}/{repo}/notifications` | |
| Mark repo read | PUT | `/repos/{owner}/{repo}/notifications` | |

**Note:** Notifications are REST-only. The `gh status` command shows a summary but doesn't support mutations.
