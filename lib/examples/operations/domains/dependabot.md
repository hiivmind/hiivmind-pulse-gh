# Dependabot

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List alerts | ✗ | ✓ | ✗ | ✓ | |
| Get alert | ✗ | ✓ | ✗ | ✓ | |
| Update alert | ✗ | ✓ | ✗ | ✓ | Dismiss/reopen |
| List org alerts | ✗ | ✓ | ✗ | ✓ | Enterprise scope |
| Enable/disable | ✗ | ✓ | ✗ | ✓ | Via repo settings |
| List secrets | ✗ | ✓ | ✗ | ✓ | Dependabot secrets |
| Set secret | ✗ | ✓ | ✗ | ✓ | Encrypted |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/dependabot/alerts`, `GET /dependabot/alerts/{alert_number}`, `PATCH /dependabot/alerts/{alert_number}`, `GET /orgs/{org}/dependabot/alerts`, `GET /repos/{owner}/{repo}/dependabot/secrets`, `PUT /dependabot/secrets/{secret_name}` | `GET /dependabot/alerts`, `PATCH /dependabot/alerts`, `state`, `dismissed_reason`, `dependabot/secrets` |

**Note:** Dependabot alerts are REST-only. No GraphQL schema coverage for security alerts.
