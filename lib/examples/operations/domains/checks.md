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

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `POST /repos/{owner}/{repo}/check-runs`, `PATCH /check-runs/{check_run_id}`, `GET /check-runs/{check_run_id}`, `GET /repos/{owner}/{repo}/commits/{ref}/check-runs`, `POST /check-suites`, `GET /check-suites/{check_suite_id}`, `GET /commits/{ref}/check-suites`, `PATCH /repos/{owner}/{repo}/check-suites/preferences`, `GET /check-runs/{check_run_id}/annotations` | `POST /check-runs`, `PATCH /check-runs`, `check-suites`, `annotations` |
| GraphQL | `checkRun`, `checkSuite` (queries), `createCheckRun`, `updateCheckRun`, `rerequestCheckSuite` (mutations) | `query { repository { checkSuites } }`, `mutation { createCheckRun }`, `mutation { updateCheckRun }` |

**Note:** Check run creation/updates require a GitHub App installation. PATs cannot create checks. CLI can only view check status via `gh pr checks`.
