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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List alerts | GET | `/repos/{owner}/{repo}/secret-scanning/alerts` | |
| Get alert | GET | `/repos/{owner}/{repo}/secret-scanning/alerts/{alert_number}` | |
| Update alert | PATCH | `/repos/{owner}/{repo}/secret-scanning/alerts/{alert_number}` | Resolve/reopen |
| List locations | GET | `/repos/{owner}/{repo}/secret-scanning/alerts/{alert_number}/locations` | Where secret found |
| List org alerts | GET | `/orgs/{org}/secret-scanning/alerts` | Enterprise scope |
| Bypass push protection | POST | `/repos/{owner}/{repo}/secret-scanning/push-protection-bypasses` | Requires reason |

**Note:** Secret scanning alerts are REST-only. No GraphQL schema coverage for security alerts.
