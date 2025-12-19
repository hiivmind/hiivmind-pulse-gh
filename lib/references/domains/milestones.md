# Milestones

**Hybrid: Read via GraphQL, CRUD via REST. Set on issue via GraphQL.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | No CLI direct support |
| Get | ✗ | ✓ | ✓ | ✓ | No CLI direct support |
| Create | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Close | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Set on issue | ✗ | ✓ | ✓ | ✓ | Via updateIssue mutation |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | (Not available) | Use REST or GraphQL |
| Get | (Not available) | Use REST or GraphQL |
| Create | (Not available) | Use REST API |
| Update | (Not available) | Use REST API |
| Close | (Not available) | Use REST API |
| Delete | (Not available) | Use REST API |
| Set on issue | `gh issue edit {number} --milestone {milestone}` | Via issue edit |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/milestones` | |
| Get | GET | `/repos/{owner}/{repo}/milestones/{number}` | |
| Create | POST | `/repos/{owner}/{repo}/milestones` | |
| Update | PATCH | `/repos/{owner}/{repo}/milestones/{number}` | |
| Close | PATCH | `/repos/{owner}/{repo}/milestones/{number}` | Set `state: closed` |
| Delete | DELETE | `/repos/{owner}/{repo}/milestones/{number}` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.milestones` | |
| Get | Query | `node(id:)` | Use `Milestone` type |
| Set on issue | Mutation | `updateIssue` | Set `milestoneId` field |
