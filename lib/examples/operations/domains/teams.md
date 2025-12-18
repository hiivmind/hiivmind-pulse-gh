# Teams

**Primarily REST API. GraphQL has read + discussion mutations only. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (org) | ✗ | ✓ | ✓ | ✓ | Organization teams |
| Get | ✗ | ✓ | ✓ | ✓ | By slug |
| Create | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| List members | ✗ | ✓ | ✓ | ✓ | Team membership |
| Add member | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Remove member | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Get membership | ✗ | ✓ | ✓ | ✓ | User's role in team |
| List repos | ✗ | ✓ | ✓ | ✓ | Team's repos |
| Add repo | ✗ | ✓ | ✓ | ✓ | updateTeamsRepository mutation |
| Remove repo | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Team discussions | ✗ | ✓ | ✓ | ✓ | Full CRUD via GraphQL |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /orgs/{org}/teams`, `GET /orgs/{org}/teams/{team_slug}`, `POST /orgs/{org}/teams`, `PATCH /teams/{team_id}`, `DELETE /teams/{team_id}`, `GET /teams/{team_id}/members`, `PUT /teams/{team_id}/memberships/{username}`, `DELETE /teams/{team_id}/memberships/{username}`, `GET /teams/{team_id}/repos`, `PUT /teams/{team_id}/repos/{owner}/{repo}`, `DELETE /teams/{team_id}/repos/{owner}/{repo}` | `GET /orgs/{org}/teams`, `POST /teams`, `PUT /memberships`, `PUT /repos` |
| GraphQL | `team`, `teams` (queries), `createTeamDiscussion`, `updateTeamDiscussion`, `deleteTeamDiscussion`, `updateTeamsRepository` (mutations) | `query { organization { teams } }`, `mutation { updateTeamsRepository }` |

**Note:** Team CRUD and membership mutations are REST-only. GraphQL supports team discussions and repository assignments.
