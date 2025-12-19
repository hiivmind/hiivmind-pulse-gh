# Branch Protection (Legacy)

**REST API only. GraphQL read-only. For new repos, use Rulesets instead.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Get | ✗ | ✓ | ✓ | ✓ | GraphQL read-only |
| Set | ✗ | ✓ | ✗ | ✓ | REST only |
| Delete | ✗ | ✓ | ✗ | ✓ | REST only |
| Update status checks | ✗ | ✓ | ✗ | ✓ | REST only |
| Update PR reviews | ✗ | ✓ | ✗ | ✓ | REST only |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or Web UI |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| Get | GET | `/repos/{owner}/{repo}/branches/{branch}/protection` | |
| Set | PUT | `/repos/{owner}/{repo}/branches/{branch}/protection` | Full replacement |
| Delete | DELETE | `/repos/{owner}/{repo}/branches/{branch}/protection` | |
| Get status checks | GET | `/repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks` | |
| Update status checks | PATCH | `/repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks` | |
| Get PR reviews | GET | `/repos/{owner}/{repo}/branches/{branch}/protection/required_pull_request_reviews` | |
| Update PR reviews | PATCH | `/repos/{owner}/{repo}/branches/{branch}/protection/required_pull_request_reviews` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.branchProtectionRules` | Read-only |
| Get | Query | `node(id:)` | Use `BranchProtectionRule` type |

**Note:** GraphQL is read-only for branch protection. Use REST for mutations or prefer Rulesets for new repos.
