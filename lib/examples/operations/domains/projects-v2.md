# Projects v2

**Full CLI + GraphQL support. REST has no project v2 support. Views are UI-only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✗ | ✓ | ✓ | |
| Get/View | ✓ | ✗ | ✓ | ✓ | |
| Create | ✓ | ✗ | ✓ | ✓ | |
| Edit | ✓ | ✗ | ✓ | ✓ | Title, description, visibility |
| Delete | ✓ | ✗ | ✓ | ✓ | |
| Close | ✓ | ✗ | ✓ | ✓ | |
| Copy | ✓ | ✗ | ✓ | ✓ | |
| Add item | ✓ | ✗ | ✓ | ✓ | Issue or PR |
| Create draft item | ✓ | ✗ | ✓ | ✓ | Draft issue in project |
| Edit item | ✓ | ✗ | ✓ | ✓ | Update field value |
| Archive item | ✓ | ✗ | ✓ | ✓ | |
| Delete item | ✓ | ✗ | ✓ | ✓ | |
| List items | ✓ | ✗ | ✓ | ✓ | |
| Create field | ✓ | ✗ | ✓ | ✓ | |
| Delete field | ✓ | ✗ | ✓ | ✓ | |
| List fields | ✓ | ✗ | ✓ | ✓ | |
| Link repository | ✓ | ✗ | ✓ | ✓ | |
| Unlink repository | ✓ | ✗ | ✓ | ✓ | |
| Mark as template | ✓ | ✗ | ✓ | ✓ | |
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

| API | Mutations/Queries | Search Keywords |
|-----|-------------------|-----------------|
| GraphQL | `projectsV2`, `projectV2` (queries), `createProjectV2`, `updateProjectV2`, `deleteProjectV2`, `copyProjectV2`, `updateProjectV2ItemFieldValue`, `archiveProjectV2Item`, `addProjectV2ItemById`, `addProjectV2DraftIssue`, `deleteProjectV2Item`, `linkProjectV2ToRepository`, `unlinkProjectV2FromRepository`, `markProjectV2AsTemplate` (mutations) | `query { organization { projectsV2 } }`, `mutation { addProjectV2ItemById }`, `mutation { updateProjectV2ItemFieldValue }` |

## Prerequisites

**Config prereqs:** Project ID, Field ID, Option ID from `.hiivmind/github/config.yaml`

## Limitations

- Views: UI-only, no API support for create/delete
- Field options: `updateProjectV2Field` mutation replaces all options at once
