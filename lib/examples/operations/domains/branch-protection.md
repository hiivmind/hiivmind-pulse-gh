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

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/branches/{branch}/protection`, `PUT /branches/{branch}/protection`, `DELETE /branches/{branch}/protection` | `GET /repos`, `PUT /branches/{branch}/protection`, `required_status_checks`, `required_pull_request_reviews` |
| GraphQL | `branchProtectionRule` (read-only query) | `query { repository { branchProtectionRules } }` |

**Note:** `BranchProtectionRule` GraphQL type is read-only. Use REST for mutations or prefer Rulesets for new repos.
