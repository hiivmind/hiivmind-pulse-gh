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

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/code-scanning/alerts`, `GET /code-scanning/alerts/{alert_number}`, `PATCH /code-scanning/alerts/{alert_number}`, `GET /code-scanning/alerts/{alert_number}/instances`, `GET /repos/{owner}/{repo}/code-scanning/analyses`, `DELETE /code-scanning/analyses/{analysis_id}`, `POST /repos/{owner}/{repo}/code-scanning/sarifs`, `GET /code-scanning/sarifs/{sarif_id}`, `GET /repos/{owner}/{repo}/code-scanning/default-setup`, `PATCH /repos/{owner}/{repo}/code-scanning/default-setup` | `GET /code-scanning/alerts`, `PATCH /code-scanning/alerts`, `sarifs`, `default-setup`, `state`, `dismissed_reason` |

**Note:** Code scanning alerts are REST-only. SARIF upload enables integration with third-party security tools.
