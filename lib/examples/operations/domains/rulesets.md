# Repository Rulesets (Modern)

**Hybrid: Read via both, mutations via REST only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | Both support reading |
| Get | ✗ | ✓ | ✓ | ✓ | Both support reading |
| Create | ✗ | ✓ | ✗ | ✓ | REST only |
| Update | ✗ | ✓ | ✗ | ✓ | REST only |
| Delete | ✗ | ✓ | ✗ | ✓ | REST only |
| Test rule | ✗ | ✓ | ✗ | ✓ | REST only |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or Web UI |

## Corpus Lookup Guide

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/rulesets`, `GET /rulesets/{ruleset_id}`, `POST /rulesets`, `PUT /rulesets/{ruleset_id}`, `DELETE /rulesets/{ruleset_id}`, `POST /rulesets/test` | `GET /repos`, `POST /rulesets`, `enforcement`, `conditions`, `rules` |
| GraphQL | `repository { rulesets }` (read-only query) | `query { repository { rulesets { edges { node } } } }` |

**Key concepts:** `target`, `enforcement` level, `conditions`, `ref_name` pattern, `rules` array
