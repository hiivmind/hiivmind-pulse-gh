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

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/milestones`, `GET /milestones/{number}`, `POST /milestones`, `PATCH /milestones/{number}`, `DELETE /milestones/{number}` | `GET /repos`, `POST /milestones`, `PATCH /milestones/{number}`, `DELETE /milestones/{number}` |
| GraphQL | `milestones` (query), `updateIssue` with `milestoneId` (mutation) | `query { repository { milestones } }`, `mutation { updateIssue(input: {milestoneId: }) }` |
