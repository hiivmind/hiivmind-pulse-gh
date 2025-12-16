---
name: hiivmind-corpus-github-navigate
description: >-
  Find GitHub API documentation for hiivmind-pulse-gh operations. Use when you need GraphQL schema types, REST endpoint syntax, or gh CLI commands. Trigger keywords: "find in docs", "check the docs", "GraphQL schema", "REST endpoint", "gh command", "API syntax", issue, pullRequest, milestone, projectV2, rulesets, workflows, secrets, releases.
---

# GitHub API Documentation Navigator (Pulse Edition)

This corpus provides GitHub API documentation specialized for hiivmind-pulse-gh.

## How to Use

1. **Read routing guide first:** `reference/api-routing.md` - tells you which API (GraphQL vs REST)
2. **Search this index:** Use keywords from routing guide
3. **Read source docs:** Get exact syntax from `.source/docs/content/`

## Entry Points

| Need | Start Here |
|------|------------|
| Which API to use | `reference/api-routing.md` |
| Find a topic | `data/index.md` → keyword search |
| GraphQL type/mutation | `data/uploads/graphql-schema/schema.docs.graphql` (grep) |
| REST endpoint | `data/sections/rest.md` |
| gh CLI command | `data/sections/github-cli.md` |

## Quick Keyword Lookups

### GraphQL Operations
- **Issues:** `createIssue`, `updateIssue`, `closeIssue`, `addComment`
- **PRs:** `createPullRequest`, `mergePullRequest`, `requestReviews`
- **Projects v2:** `addProjectV2ItemById`, `updateProjectV2ItemFieldValue`, `createProjectV2StatusUpdate`
- **Labels:** `addLabelsToLabelable`, `removeLabelsFromLabelable`

### REST Operations (no GraphQL)
- **Milestones:** `POST /repos/{owner}/{repo}/milestones`
- **Branch protection:** `PUT /repos/{owner}/{repo}/branches/{branch}/protection`
- **Rulesets:** `POST /repos/{owner}/{repo}/rulesets`
- **Actions:** `/repos/{owner}/{repo}/actions/...`
- **Secrets:** `/repos/{owner}/{repo}/actions/secrets/...`
- **Variables:** `/repos/{owner}/{repo}/actions/variables/...`
- **Releases:** `/repos/{owner}/{repo}/releases/...`

## GraphQL Schema Search

The schema file is 70k+ lines. Use grep patterns:

```bash
# Find type definition
grep -n "^type ProjectV2 " data/uploads/graphql-schema/schema.docs.graphql -A 50

# Find mutation
grep -n "createProjectV2StatusUpdate" data/uploads/graphql-schema/schema.docs.graphql -B 5 -A 30

# Find input type
grep -n "^input CreateIssueInput " data/uploads/graphql-schema/schema.docs.graphql -A 30

# Find enum
grep -n "^enum ProjectV2ItemFieldValueOrderField " data/uploads/graphql-schema/schema.docs.graphql -A 20
```

## Section Indices

For detailed file listings by domain:

- `data/sections/rest.md` - REST API endpoints
- `data/sections/graphql.md` - GraphQL guides
- `data/sections/issues.md` - Issues, milestones, labels, Projects v2
- `data/sections/pull-requests.md` - PR operations
- `data/sections/repositories.md` - Branches, protection, rulesets, releases
- `data/sections/actions.md` - Workflows, runs, jobs, secrets, variables
- `data/sections/organizations.md` - Orgs, teams, permissions
- `data/sections/github-cli.md` - gh CLI reference
- `data/sections/authentication.md` - Auth methods, PATs, SSH

## Source Path Reference

| Prefix | Path |
|--------|------|
| `docs:` | `.source/docs/content/{path}` |
| `graphql-schema:` | `data/uploads/graphql-schema/{file}` |
