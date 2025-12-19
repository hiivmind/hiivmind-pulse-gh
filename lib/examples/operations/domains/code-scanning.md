# Code Scanning

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List alerts | ✗ | ✓ | ✗ | ✓ | |
| Get alert | ✗ | ✓ | ✗ | ✓ | |
| Update alert | ✗ | ✓ | ✗ | ✓ | Dismiss/reopen |
| List instances | ✗ | ✓ | ✗ | ✓ | Alert instances |
| List analyses | ✗ | ✓ | ✗ | ✓ | |
| Get analysis | ✗ | ✓ | ✗ | ✓ | |
| Delete analysis | ✗ | ✓ | ✗ | ✗ | REST only |
| Upload SARIF | ✗ | ✓ | ✗ | ✗ | For custom tools |
| Get SARIF | ✗ | ✓ | ✗ | ✗ | Upload status |
| List org alerts | ✗ | ✓ | ✗ | ✓ | Enterprise scope |
| Get default setup | ✗ | ✓ | ✗ | ✓ | CodeQL config |
| Update default setup | ✗ | ✓ | ✗ | ✓ | Enable/configure |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List alerts | GET | `/repos/{owner}/{repo}/code-scanning/alerts` | |
| Get alert | GET | `/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}` | |
| Update alert | PATCH | `/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}` | Dismiss/reopen |
| List instances | GET | `/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/instances` | |
| List analyses | GET | `/repos/{owner}/{repo}/code-scanning/analyses` | |
| Get analysis | GET | `/repos/{owner}/{repo}/code-scanning/analyses/{analysis_id}` | |
| Delete analysis | DELETE | `/repos/{owner}/{repo}/code-scanning/analyses/{analysis_id}` | |
| Upload SARIF | POST | `/repos/{owner}/{repo}/code-scanning/sarifs` | For custom tools |
| Get SARIF status | GET | `/repos/{owner}/{repo}/code-scanning/sarifs/{sarif_id}` | |
| List org alerts | GET | `/orgs/{org}/code-scanning/alerts` | Enterprise scope |
| Get default setup | GET | `/repos/{owner}/{repo}/code-scanning/default-setup` | CodeQL config |
| Update default setup | PATCH | `/repos/{owner}/{repo}/code-scanning/default-setup` | Enable/configure |

**Note:** Code scanning alerts are REST-only. SARIF upload enables integration with third-party security tools.
