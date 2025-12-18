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

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/hooks`, `GET /hooks/{hook_id}`, `POST /repos/{owner}/{repo}/hooks`, `PATCH /hooks/{hook_id}`, `DELETE /hooks/{hook_id}`, `POST /hooks/{hook_id}/pings`, `GET /hooks/{hook_id}/deliveries`, `GET /hooks/{hook_id}/deliveries/{delivery_id}`, `POST /hooks/{hook_id}/deliveries/{delivery_id}/attempts`, `GET /orgs/{org}/hooks` | `GET /hooks`, `POST /hooks`, `PATCH /hooks`, `pings`, `deliveries` |

**Note:** Webhooks are entirely REST-based. No GraphQL schema coverage for webhook management.
