# Webhooks

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (repo) | ✗ | ✓ | ✗ | ✓ | Repository webhooks |
| Get | ✗ | ✓ | ✗ | ✓ | By ID |
| Create | ✗ | ✓ | ✗ | ✓ | |
| Update | ✗ | ✓ | ✗ | ✓ | |
| Delete | ✗ | ✓ | ✗ | ✓ | |
| Test (ping) | ✗ | ✓ | ✗ | ✓ | Trigger ping event |
| List deliveries | ✗ | ✓ | ✗ | ✓ | Delivery history |
| Get delivery | ✗ | ✓ | ✗ | ✓ | Specific delivery |
| Redeliver | ✗ | ✓ | ✗ | ✓ | Retry delivery |
| List (org) | ✗ | ✓ | ✗ | ✓ | Organization webhooks |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (repo) | GET | `/repos/{owner}/{repo}/hooks` | |
| Get | GET | `/repos/{owner}/{repo}/hooks/{hook_id}` | |
| Create | POST | `/repos/{owner}/{repo}/hooks` | |
| Update | PATCH | `/repos/{owner}/{repo}/hooks/{hook_id}` | |
| Delete | DELETE | `/repos/{owner}/{repo}/hooks/{hook_id}` | |
| Test (ping) | POST | `/repos/{owner}/{repo}/hooks/{hook_id}/pings` | |
| List deliveries | GET | `/repos/{owner}/{repo}/hooks/{hook_id}/deliveries` | |
| Get delivery | GET | `/repos/{owner}/{repo}/hooks/{hook_id}/deliveries/{delivery_id}` | |
| Redeliver | POST | `/repos/{owner}/{repo}/hooks/{hook_id}/deliveries/{delivery_id}/attempts` | |
| List (org) | GET | `/orgs/{org}/hooks` | |
| Create (org) | POST | `/orgs/{org}/hooks` | |

**Note:** Webhooks are entirely REST-based. No GraphQL schema coverage for webhook management.
