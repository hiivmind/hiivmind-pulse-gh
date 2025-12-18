# GitHub API Routing Guide

> **Purpose:** Quick reference for which API (GraphQL vs REST) to use for each domain.
> **Standalone:** This guide is useful on its own - you do not need corpus lookup for every operation.
> **When uncertain:** If you need exact syntax, use `lib/examples/operations/corpus-lookup.md`

---

## Quick Reference

| Domain | Read | Create | Update | Delete | Notes |
|--------|------|--------|--------|--------|-------|
| **Issues** | CLI/REST/GraphQL/UI | CLI/REST/GraphQL/UI | CLI/REST/GraphQL/UI | REST/UI | All 4 methods supported (see details) |
| **Pull Requests** | GraphQL | GraphQL | GraphQL | GraphQL | Full support |
| **Milestones** | GraphQL | REST | REST | REST | CRUD is REST-only |
| **Labels** | GraphQL | REST | REST | REST | CRUD is REST-only |
| **Projects v2** | GraphQL | GraphQL | GraphQL | GraphQL | Except views (UI only) |
| **Branch Protection** | REST | REST | REST | REST | GraphQL is read-only |
| **Rulesets** | Both | REST | REST | REST | GraphQL for queries |
| **Actions** | REST | REST | REST | REST | No GraphQL support |
| **Secrets** | REST | REST | REST | REST | No GraphQL support |
| **Releases** | Both | REST | REST | REST | GraphQL for queries |

---

## Domain Details

### Issues

**All 4 methods fully supported for core operations.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All methods work |
| Get | ✓ | ✓ | ✓ | ✓ | |
| Create | ✓ | ✓ | ✓ | ✓ | |
| Update | ✓ | ✓ | ✓ | ✓ | |
| Close | ✓ | ✓ | ✓ | ✓ | |
| Add comment | ✓ | ✓ | ✓ | ✓ | |
| Add labels | ✓ | ✓ | ✓ | ✓ | Separate endpoint in REST |
| Set milestone | ✓ | ✓ | ✓ | ✓ | Via PATCH in REST |
| Lock | ✗ | ✓ | ✗ | ✓ | REST-only, no GraphQL |
| Unlock | ✗ | ✓ | ✗ | ✓ | REST-only, no GraphQL |

**CLI Command Reference:**

| Operation | Command |
|-----------|---------|
| List | `gh issue list` |
| Get | `gh issue view {number}` |
| Create | `gh issue create --title {title}` |
| Update | `gh issue edit {number}` |
| Close | `gh issue close {number}` |
| Add comment | `gh issue comment {number} --body {body}` |
| Add labels | `gh issue edit {number} --add-label {label}` |
| Set milestone | `gh issue edit {number} --milestone {milestone}` |
| Lock | (Web UI only) |
| Unlock | (Web UI only) |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/issues`, `GET /issues/{number}`, `POST /issues`, `PATCH /issues/{number}`, `POST /issues/{number}/comments`, `POST /issues/{number}/labels` | `GET /repos`, `POST /issues`, `PATCH /issues/{number}`, `issues/{number}/comments`, `issues/{number}/labels` |
| GraphQL | `issue`, `issues` (queries), `createIssue`, `updateIssue`, `closeIssue`, `addComment`, `addLabelsToLabelable`, `removeLabelsFromLabelable` (mutations) | `query { issue }`, `query { repository { issues } }`, `mutation { createIssue }`, `mutation { updateIssue }` |

---

### Pull Requests

**All 4 methods fully supported for core operations.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All methods work |
| Get | ✓ | ✓ | ✓ | ✓ | |
| Create | ✓ | ✓ | ✓ | ✓ | |
| Update | ✓ | ✓ | ✓ | ✓ | |
| Merge | ✓ | ✓ | ✓ | ✓ | |
| Close | ✓ | ✓ | ✓ | ✓ | |
| Request review | ✓ | ✓ | ✓ | ✓ | |
| Add comment | ✓ | ✓ | ✓ | ✓ | |
| Dismiss review | ✗ | ✓ | ✓ | ✓ | CLI not available |
| Lock | ✗ | ✓ | ✗ | ✓ | REST-only |
| Unlock | ✗ | ✓ | ✗ | ✓ | REST-only |

**CLI Command Reference:**

| Operation | Command |
|-----------|---------|
| List | `gh pr list` |
| Get | `gh pr view {number}` |
| Create | `gh pr create --title {title}` |
| Update | `gh pr edit {number}` |
| Merge | `gh pr merge {number}` |
| Close | `gh pr close {number}` |
| Request review | `gh pr review --request-review {reviewer}` |
| Add comment | `gh pr comment {number} --body {body}` |
| Dismiss review | (Web UI only) |
| Lock | (Web UI only) |
| Unlock | (Web UI only) |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/pulls`, `GET /pulls/{number}`, `POST /pulls`, `PATCH /pulls/{number}`, `PUT /pulls/{number}/merge`, `POST /pulls/{number}/comments`, `DELETE /pulls/{number}/requested_reviewers` | `GET /repos`, `POST /pulls`, `PATCH /pulls/{number}`, `PUT /pulls/{number}/merge`, `pulls/{number}/comments`, `pulls/{number}/requested_reviewers` |
| GraphQL | `pullRequest`, `pullRequests` (queries), `createPullRequest`, `updatePullRequest`, `mergePullRequest`, `closePullRequest`, `requestReviews`, `addComment`, `dismissPullRequestReview` (mutations) | `query { pullRequest }`, `query { repository { pullRequests } }`, `mutation { createPullRequest }`, `mutation { mergePullRequest }` |

---

### Milestones

**Read via GraphQL. CRUD via REST.**

| Operation | API | Why | Search Keywords |
|-----------|-----|-----|-----------------|
| List | GraphQL | Better pagination | `milestones`, `repository`, `states`, `query` |
| Get | GraphQL | Field selection | `milestone`, `repository`, `number` |
| Create | REST | Not in GraphQL | `milestones`, `POST`, `create`, `title`, `due_on` |
| Update | REST | Not in GraphQL | `milestones`, `PATCH`, `update`, `state` |
| Close | REST | Not in GraphQL | `milestones`, `PATCH`, `state`, `closed` |
| Delete | REST | Not in GraphQL | `milestones`, `DELETE` |
| Set on issue | GraphQL | Via updateIssue | `updateIssue`, `milestoneId` |

---

### Labels

**Read via GraphQL. CRUD via REST.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| List | GraphQL | `labels`, `repository`, `query` |
| Create | REST | `labels`, `POST`, `create`, `name`, `color` |
| Update | REST | `labels`, `PATCH`, `update`, `new_name` |
| Delete | REST | `labels`, `DELETE` |
| Add to issue | GraphQL | `addLabelsToLabelable`, `mutation`, `labelIds` |
| Remove from issue | GraphQL | `removeLabelsFromLabelable`, `mutation` |

---

### Projects v2

**Everything via GraphQL. Views are UI-only.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| List projects | GraphQL | `projectsV2`, `organization`, `user`, `query` |
| Get project | GraphQL | `projectV2`, `number`, `query` |
| Get items | GraphQL | `projectV2`, `items`, `fieldValues` |
| Add item | GraphQL | `addProjectV2ItemById`, `mutation`, `contentId` |
| Update field | GraphQL | `updateProjectV2ItemFieldValue`, `mutation`, `fieldId`, `value` |
| Archive item | GraphQL | `archiveProjectV2Item`, `mutation` |
| Status update | GraphQL | `createProjectV2StatusUpdate`, `mutation`, `status`, `ON_TRACK` |
| Link repository | GraphQL | `linkProjectV2ToRepository`, `mutation`, `repositoryId` |

**Limitations (search if unsure):**
- Views: `projectV2`, `views`, `create` → will confirm UI-only
- Field options: `updateProjectV2Field`, `singleSelectOptions` → replaces all

**Config prereqs:** Project ID, Field ID, Option ID from `.hiivmind/github/config.yaml`

---

### Branch Protection (Legacy)

**REST API only. GraphQL is read-only.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| Get | REST | `branch protection`, `GET`, `branches`, `protection` |
| Set | REST | `branch protection`, `PUT`, `required_status_checks`, `enforce_admins` |
| Delete | REST | `branch protection`, `DELETE` |
| Status checks | REST | `required_status_checks`, `contexts`, `strict` |
| PR reviews | REST | `required_pull_request_reviews`, `approving_review_count` |

**Why REST:** `BranchProtectionRule` GraphQL type is read-only for mutations.

---

### Repository Rulesets (Modern)

**Queries: both. Mutations: REST.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| List | Both | `rulesets`, `repository`, `GET` |
| Get | Both | `rulesets`, `ruleset_id` |
| Create | REST | `rulesets`, `POST`, `create`, `enforcement`, `conditions` |
| Update | REST | `rulesets`, `PUT`, `update` |
| Delete | REST | `rulesets`, `DELETE` |
| Check branch | REST | `rules`, `branches`, `branch_name` |

**Key concepts:** `target`, `enforcement`, `conditions`, `ref_name`, `rules`

---

### Actions (Workflows, Runs, Jobs)

**REST API only. No GraphQL support.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| List workflows | REST | `workflows`, `GET`, `actions` |
| Get workflow | REST | `workflows`, `workflow_id` |
| List runs | REST | `runs`, `GET`, `actions`, `workflow_runs` |
| Get run | REST | `runs`, `run_id` |
| Trigger | REST | `dispatches`, `POST`, `workflow_dispatch`, `inputs` |
| Cancel | REST | `runs`, `cancel`, `POST` |
| Re-run | REST | `runs`, `rerun`, `POST` |
| Re-run failed | REST | `rerun-failed-jobs`, `POST` |

**CLI alternative:** Search `gh run`, `gh workflow` for simpler syntax.

---

### Secrets

**REST API only. No GraphQL support.**

| Scope | Operation | Search Keywords |
|-------|-----------|-----------------|
| Repo | List | `secrets`, `actions`, `GET`, `repository` |
| Repo | Set | `secrets`, `PUT`, `encrypted_value`, `key_id` |
| Repo | Delete | `secrets`, `DELETE` |
| Env | * | `environments`, `secrets`, `environment_name` |
| Org | * | `orgs`, `secrets`, `visibility`, `selected_repositories` |

**Key concept:** Secrets require encryption. Search `public-key`, `encrypt`, `libsodium`.

**CLI alternative:** Search `gh secret` for automatic encryption.

---

### Variables

**REST API only. No GraphQL support.**

| Scope | Operation | Search Keywords |
|-------|-----------|-----------------|
| Repo | List | `variables`, `actions`, `GET` |
| Repo | Create | `variables`, `POST`, `name`, `value` |
| Repo | Update | `variables`, `PATCH` |
| Repo | Delete | `variables`, `DELETE` |
| Env | * | `environments`, `variables` |
| Org | * | `orgs`, `variables`, `visibility` |

**No encryption needed** (unlike secrets).

---

### Releases

**Queries: both. Mutations: REST.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| List | Both | `releases`, `repository`, `GET` |
| Get | Both | `releases`, `release`, `tag_name` |
| Get latest | Both | `releases`, `latest` |
| Create | REST | `releases`, `POST`, `tag_name`, `target_commitish` |
| Update | REST | `releases`, `PATCH`, `release_id` |
| Delete | REST | `releases`, `DELETE` |
| Upload asset | REST | `assets`, `uploads.github.com`, `POST` |
| Generate notes | REST | `generate-notes`, `POST`, `previous_tag_name` |

**CLI alternative:** Search `gh release` for simpler syntax.

---

## Loading Context

Before any operation, load from `.hiivmind/github/config.yaml`:

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
DEFAULT_PROJECT=$(yq '.projects.default' "$CONFIG")
```

For Projects v2, also need:
- Project ID: `.projects.catalog[].id`
- Field ID: `.projects.catalog[].fields.{Name}.id`
- Option ID: `.projects.catalog[].fields.{Name}.options.{Value}`

---

## Using Search Keywords

1. **Identify operation** from tables above
2. **Note the API** (GraphQL or REST)
3. **Search corpus** using keywords:
   - For GraphQL: search schema for type/mutation names
   - For REST: search REST docs for endpoint keywords
4. **Read source doc** for exact syntax

---

## Unlisted Domains

This guide covers common domains. For domains not listed:

1. **Default to REST API** - Most GitHub features have REST endpoints
2. **Use corpus lookup** - Search corpus for endpoint path and parameters
3. **Check permissions** - Ensure `gh auth status` shows required scopes

To search corpus for unlisted domain:
- Invoke: `hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs`
- Search: "[domain name] REST endpoint" or "[domain name] API"
