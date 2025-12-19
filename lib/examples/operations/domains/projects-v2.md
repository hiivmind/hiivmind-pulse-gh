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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (org) | GET | `/orgs/{org}/projectsV2` | Read-only |
| Get (org) | GET | `/orgs/{org}/projectsV2/{number}` | Read-only |
| List (user) | GET | `/users/{username}/projectsV2` | Read-only |
| Get (user) | GET | `/users/{username}/projectsV2/{number}` | Read-only |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `organization.projectsV2` | Or `user.projectsV2` |
| Get | Query | `node(id:)` | Use `ProjectV2` type |
| List items | Query | `projectV2.items` | |
| List fields | Query | `projectV2.fields` | |
| Create | Mutation | `createProjectV2` | |
| Edit | Mutation | `updateProjectV2` | Title, description, visibility |
| Delete | Mutation | `deleteProjectV2` | |
| Copy | Mutation | `copyProjectV2` | |
| Add item | Mutation | `addProjectV2ItemById` | Issue or PR |
| Create draft | Mutation | `addProjectV2DraftIssue` | |
| Edit draft | Mutation | `updateProjectV2DraftIssue` | |
| Convert draft | Mutation | `convertProjectV2DraftIssueItemToIssue` | |
| Update field value | Mutation | `updateProjectV2ItemFieldValue` | |
| Clear field value | Mutation | `clearProjectV2ItemFieldValue` | |
| Move item | Mutation | `updateProjectV2ItemPosition` | |
| Archive item | Mutation | `archiveProjectV2Item` | |
| Unarchive item | Mutation | `unarchiveProjectV2Item` | |
| Delete item | Mutation | `deleteProjectV2Item` | |
| Create field | Mutation | `createProjectV2Field` | |
| Update field | Mutation | `updateProjectV2Field` | Replaces all options |
| Delete field | Mutation | `deleteProjectV2Field` | |
| Link repo | Mutation | `linkProjectV2ToRepository` | |
| Unlink repo | Mutation | `unlinkProjectV2FromRepository` | |
| Link team | Mutation | `linkProjectV2ToTeam` | |
| Unlink team | Mutation | `unlinkProjectV2FromTeam` | |
| Update collaborators | Mutation | `updateProjectV2Collaborators` | |
| Mark template | Mutation | `markProjectV2AsTemplate` | |
| Create status update | Mutation | `createProjectV2StatusUpdate` | |
| Update status update | Mutation | `updateProjectV2StatusUpdate` | |
| Delete status update | Mutation | `deleteProjectV2StatusUpdate` | |
| Delete workflow | Mutation | `deleteProjectV2Workflow` | |

## Prerequisites

**Config prereqs:** Project ID, Field ID, Option ID from `.hiivmind/github/config.yaml`

## Limitations

- Views: UI-only, no API support for create/delete
- Field options: `updateProjectV2Field` mutation replaces all options at once
- Status updates: Requires project admin permissions
- Workflows: Can only delete, not create/update via API
