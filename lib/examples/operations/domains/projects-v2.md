# Projects v2

**Full CLI + GraphQL support. REST is read-only (list/get). Views are UI-only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | REST: `/orgs/{org}/projectsV2`, `/users/{username}/projectsV2` |
| Get/View | ✓ | ✓ | ✓ | ✓ | REST: `GET .../projectsV2/{number}` |
| Create | ✓ | ✗ | ✓ | ✓ | `createProjectV2` |
| Edit | ✓ | ✗ | ✓ | ✓ | `updateProjectV2` - title, description, visibility |
| Delete | ✓ | ✗ | ✓ | ✓ | `deleteProjectV2` |
| Close | ✓ | ✗ | ✓ | ✓ | `updateProjectV2` with closed:true |
| Copy | ✓ | ✗ | ✓ | ✓ | `copyProjectV2` |
| Add item | ✓ | ✗ | ✓ | ✓ | `addProjectV2ItemById` - issue or PR |
| Create draft item | ✓ | ✗ | ✓ | ✓ | `addProjectV2DraftIssue` |
| Edit draft item | ✗ | ✗ | ✓ | ✓ | `updateProjectV2DraftIssue` |
| Convert draft to issue | ✗ | ✗ | ✓ | ✓ | `convertProjectV2DraftIssueItemToIssue` |
| Update item field | ✓ | ✗ | ✓ | ✓ | `updateProjectV2ItemFieldValue` |
| Clear item field | ✗ | ✗ | ✓ | ✓ | `clearProjectV2ItemFieldValue` |
| Move item position | ✗ | ✗ | ✓ | ✓ | `updateProjectV2ItemPosition` |
| Archive item | ✓ | ✗ | ✓ | ✓ | `archiveProjectV2Item` |
| Unarchive item | ✗ | ✗ | ✓ | ✓ | `unarchiveProjectV2Item` |
| Delete item | ✓ | ✗ | ✓ | ✓ | `deleteProjectV2Item` |
| List items | ✓ | ✗ | ✓ | ✓ | Query: `projectV2.items` |
| Create field | ✓ | ✗ | ✓ | ✓ | `createProjectV2Field` |
| Update field | ✗ | ✗ | ✓ | ✓ | `updateProjectV2Field` - replaces all options |
| Delete field | ✓ | ✗ | ✓ | ✓ | `deleteProjectV2Field` |
| List fields | ✓ | ✗ | ✓ | ✓ | Query: `projectV2.fields` |
| Link repository | ✓ | ✗ | ✓ | ✓ | `linkProjectV2ToRepository` |
| Unlink repository | ✓ | ✗ | ✓ | ✓ | `unlinkProjectV2FromRepository` |
| Link team | ✗ | ✗ | ✓ | ✓ | `linkProjectV2ToTeam` |
| Unlink team | ✗ | ✗ | ✓ | ✓ | `unlinkProjectV2FromTeam` |
| Update collaborators | ✗ | ✗ | ✓ | ✓ | `updateProjectV2Collaborators` |
| Mark as template | ✓ | ✗ | ✓ | ✓ | `markProjectV2AsTemplate` |
| Create status update | ✗ | ✗ | ✓ | ✓ | `createProjectV2StatusUpdate` |
| Update status update | ✗ | ✗ | ✓ | ✓ | `updateProjectV2StatusUpdate` |
| Delete status update | ✗ | ✗ | ✓ | ✓ | `deleteProjectV2StatusUpdate` |
| Delete workflow | ✗ | ✗ | ✓ | ✓ | `deleteProjectV2Workflow` |
| Create view | ✗ | ✗ | ✗ | ✓ | UI-only, no API |
| Delete view | ✗ | ✗ | ✗ | ✓ | UI-only, no API |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh project list --owner {owner}` | |
| View | `gh project view {number} --owner {owner}` | |
| Create | `gh project create --owner {owner} --title {title}` | |
| Edit | `gh project edit {number} --title {title}` | |
| Delete | `gh project delete {number}` | |
| Close | `gh project close {number}` | |
| Copy | `gh project copy {number} --target-owner {owner}` | |
| Add item | `gh project item-add {number} --owner {owner} --url {issue-url}` | |
| Create draft | `gh project item-create {number} --owner {owner} --title {title}` | |
| Edit item | `gh project item-edit --id {item-id} --field-id {field-id} --text {value}` | |
| Archive item | `gh project item-archive {number} --owner {owner} --id {item-id}` | |
| Delete item | `gh project item-delete {number} --owner {owner} --id {item-id}` | |
| List items | `gh project item-list {number} --owner {owner}` | |
| Create field | `gh project field-create {number} --owner {owner} --name {name} --data-type {type}` | |
| Delete field | `gh project field-delete --id {field-id}` | |
| List fields | `gh project field-list {number} --owner {owner}` | |
| Link repo | `gh project link {number} --owner {owner} --repo {repo}` | |
| Unlink repo | `gh project unlink {number} --owner {owner} --repo {repo}` | |
| Mark template | `gh project mark-template {number} --owner {owner}` | |

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /orgs/{org}/projectsV2`, `GET /orgs/{org}/projectsV2/{number}`, `GET /users/{username}/projectsV2`, `GET /users/{username}/projectsV2/{number}` | `GET /projectsV2`, `list projects`, `project number` |
| GraphQL Queries | `projectsV2`, `projectV2`, `projectV2.items`, `projectV2.fields` | `query { organization { projectsV2 } }`, `query { node(id: ...) { ... on ProjectV2 } }` |
| GraphQL Mutations | `createProjectV2`, `updateProjectV2`, `deleteProjectV2`, `copyProjectV2`, `addProjectV2ItemById`, `addProjectV2DraftIssue`, `updateProjectV2DraftIssue`, `convertProjectV2DraftIssueItemToIssue`, `updateProjectV2ItemFieldValue`, `clearProjectV2ItemFieldValue`, `updateProjectV2ItemPosition`, `archiveProjectV2Item`, `unarchiveProjectV2Item`, `deleteProjectV2Item`, `createProjectV2Field`, `updateProjectV2Field`, `deleteProjectV2Field`, `linkProjectV2ToRepository`, `unlinkProjectV2FromRepository`, `linkProjectV2ToTeam`, `unlinkProjectV2FromTeam`, `updateProjectV2Collaborators`, `markProjectV2AsTemplate`, `createProjectV2StatusUpdate`, `updateProjectV2StatusUpdate`, `deleteProjectV2StatusUpdate`, `deleteProjectV2Workflow` | `mutation { addProjectV2ItemById }`, `mutation { updateProjectV2ItemFieldValue }` |

## Prerequisites

**Config prereqs:** Project ID, Field ID, Option ID from `.hiivmind/github/config.yaml`

## Limitations

- Views: UI-only, no API support for create/delete
- Field options: `updateProjectV2Field` mutation replaces all options at once
- Status updates: Requires project admin permissions
- Workflows: Can only delete, not create/update via API
