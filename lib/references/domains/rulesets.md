# Repository Rulesets (Modern)

**Hybrid: Read via both, mutations via REST only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All support reading |
| Get | ✓ | ✓ | ✓ | ✓ | All support reading |
| Check | ✓ | ✗ | ✗ | ✗ | CLI only — check rules for branch |
| Create | ✗ | ✓ | ✗ | ✓ | REST only |
| Update | ✗ | ✓ | ✗ | ✓ | REST only |
| Delete | ✗ | ✓ | ✗ | ✓ | REST only |
| Test rule | ✗ | ✓ | ✗ | ✓ | REST only |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh ruleset list` | List rulesets for repo |
| Get | `gh ruleset view {id}` | View ruleset details |
| Check | `gh ruleset check` | Check rules for a branch |

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
