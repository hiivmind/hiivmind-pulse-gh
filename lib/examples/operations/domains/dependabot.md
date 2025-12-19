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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List alerts | GET | `/repos/{owner}/{repo}/dependabot/alerts` | |
| Get alert | GET | `/repos/{owner}/{repo}/dependabot/alerts/{alert_number}` | |
| Update alert | PATCH | `/repos/{owner}/{repo}/dependabot/alerts/{alert_number}` | Dismiss/reopen |
| List org alerts | GET | `/orgs/{org}/dependabot/alerts` | Enterprise scope |
| List secrets | GET | `/repos/{owner}/{repo}/dependabot/secrets` | |
| Get secret | GET | `/repos/{owner}/{repo}/dependabot/secrets/{secret_name}` | |
| Set secret | PUT | `/repos/{owner}/{repo}/dependabot/secrets/{secret_name}` | Encrypted |
| Delete secret | DELETE | `/repos/{owner}/{repo}/dependabot/secrets/{secret_name}` | |
| Get public key | GET | `/repos/{owner}/{repo}/dependabot/secrets/public-key` | For encryption |

**Note:** Dependabot alerts are REST-only. No GraphQL schema coverage for security alerts.
