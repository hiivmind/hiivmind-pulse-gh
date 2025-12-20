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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (org) | GET | `/orgs/{org}/teams` | |
| Get | GET | `/orgs/{org}/teams/{team_slug}` | |
| Create | POST | `/orgs/{org}/teams` | |
| Update | PATCH | `/orgs/{org}/teams/{team_slug}` | |
| Delete | DELETE | `/orgs/{org}/teams/{team_slug}` | |
| List members | GET | `/orgs/{org}/teams/{team_slug}/members` | |
| Get membership | GET | `/orgs/{org}/teams/{team_slug}/memberships/{username}` | |
| Add member | PUT | `/orgs/{org}/teams/{team_slug}/memberships/{username}` | |
| Remove member | DELETE | `/orgs/{org}/teams/{team_slug}/memberships/{username}` | |
| List repos | GET | `/orgs/{org}/teams/{team_slug}/repos` | |
| Add repo | PUT | `/orgs/{org}/teams/{team_slug}/repos/{owner}/{repo}` | |
| Remove repo | DELETE | `/orgs/{org}/teams/{team_slug}/repos/{owner}/{repo}` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `organization.teams` | |
| Get | Query | `organization.team(slug:)` | |
| List members | Query | `team.members` | |
| List repos | Query | `team.repositories` | |
| Add repo | Mutation | `updateTeamsRepository` | |
| Create discussion | Mutation | `createTeamDiscussion` | |
| Update discussion | Mutation | `updateTeamDiscussion` | |
| Delete discussion | Mutation | `deleteTeamDiscussion` | |

## Prerequisites

**Token scope:** Most team operations require `admin:org` scope. Read-only operations work with `read:org`.

**Note:** Team CRUD and membership mutations are REST-only. GraphQL supports discussions and repository assignments.
