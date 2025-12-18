# Secret Scanning

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List alerts | ✗ | ✓ | ✗ | ✓ | |
| Get alert | ✗ | ✓ | ✗ | ✓ | |
| Update alert | ✗ | ✓ | ✗ | ✓ | Resolve/reopen |
| List locations | ✗ | ✓ | ✗ | ✓ | Where secret found |
| List org alerts | ✗ | ✓ | ✗ | ✓ | Enterprise scope |
| Enable push protection | ✗ | ✓ | ✗ | ✓ | Via repo settings |
| Bypass push protection | ✗ | ✓ | ✗ | ✗ | Requires reason |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/secret-scanning/alerts`, `GET /secret-scanning/alerts/{alert_number}`, `PATCH /secret-scanning/alerts/{alert_number}`, `GET /secret-scanning/alerts/{alert_number}/locations`, `GET /orgs/{org}/secret-scanning/alerts` | `GET /secret-scanning/alerts`, `PATCH /secret-scanning/alerts`, `locations`, `state`, `resolution` |

**Note:** Secret scanning alerts are REST-only. No GraphQL schema coverage for security alerts.
