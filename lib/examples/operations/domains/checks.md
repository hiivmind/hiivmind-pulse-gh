# Checks

**REST + GraphQL support. No CLI support. Used by GitHub Apps for CI status reporting.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Create check run | ✗ | ✓ | ✓ | ✗ | GitHub App only |
| Update check run | ✗ | ✓ | ✓ | ✗ | GitHub App only |
| Get check run | ✗ | ✓ | ✓ | ✓ | |
| List check runs | ✗ | ✓ | ✓ | ✓ | For ref or check suite |
| Rerequest check run | ✗ | ✓ | ✓ | ✓ | rerequestCheckSuite mutation |
| Create check suite | ✗ | ✓ | ✗ | ✗ | REST only |
| Get check suite | ✗ | ✓ | ✓ | ✓ | |
| List check suites | ✗ | ✓ | ✓ | ✓ | For ref |
| Set preferences | ✗ | ✓ | ✗ | ✓ | Auto-trigger settings |
| List annotations | ✗ | ✓ | ✓ | ✓ | Per check run |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| View PR checks | `gh pr checks {number}` | View check status only |
| All mutations | (Not available) | Use REST API or GraphQL |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| Create check run | POST | `/repos/{owner}/{repo}/check-runs` | GitHub App only |
| Update check run | PATCH | `/repos/{owner}/{repo}/check-runs/{check_run_id}` | |
| Get check run | GET | `/repos/{owner}/{repo}/check-runs/{check_run_id}` | |
| List check runs (ref) | GET | `/repos/{owner}/{repo}/commits/{ref}/check-runs` | |
| List check runs (suite) | GET | `/repos/{owner}/{repo}/check-suites/{check_suite_id}/check-runs` | |
| List annotations | GET | `/repos/{owner}/{repo}/check-runs/{check_run_id}/annotations` | |
| Create check suite | POST | `/repos/{owner}/{repo}/check-suites` | |
| Get check suite | GET | `/repos/{owner}/{repo}/check-suites/{check_suite_id}` | |
| List check suites | GET | `/repos/{owner}/{repo}/commits/{ref}/check-suites` | |
| Set preferences | PATCH | `/repos/{owner}/{repo}/check-suites/preferences` | |
| Rerequest suite | POST | `/repos/{owner}/{repo}/check-suites/{check_suite_id}/rerequest` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| Get check run | Query | `node(id:)` | Use `CheckRun` type |
| List check runs | Query | `checkSuite.checkRuns` | |
| Get check suite | Query | `node(id:)` | Use `CheckSuite` type |
| List check suites | Query | `commit.checkSuites` | |
| Create check run | Mutation | `createCheckRun` | GitHub App only |
| Update check run | Mutation | `updateCheckRun` | |
| Rerequest suite | Mutation | `rerequestCheckSuite` | |

**Note:** Check run creation/updates require a GitHub App installation. PATs cannot create checks.
