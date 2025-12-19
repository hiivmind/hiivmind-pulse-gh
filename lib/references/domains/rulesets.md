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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/rulesets` | |
| Get | GET | `/repos/{owner}/{repo}/rulesets/{ruleset_id}` | |
| Create | POST | `/repos/{owner}/{repo}/rulesets` | |
| Update | PUT | `/repos/{owner}/{repo}/rulesets/{ruleset_id}` | |
| Delete | DELETE | `/repos/{owner}/{repo}/rulesets/{ruleset_id}` | |
| Test rule | POST | `/repos/{owner}/{repo}/rulesets/test` | Check if ref matches |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.rulesets` | Read-only |
| Get | Query | `node(id:)` | Use `RepositoryRuleset` type |

**Key concepts:** `target`, `enforcement` level, `conditions`, `ref_name` pattern, `rules` array
