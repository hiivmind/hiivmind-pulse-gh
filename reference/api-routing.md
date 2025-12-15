# GitHub API Routing Guide

> **Purpose:** Routing decisions + search keywords for corpus lookup.
> **Usage:** Read this to choose the right API, then search corpus using the keywords.

---

## Quick Reference

| Domain | Read | Create | Update | Delete | Notes |
|--------|------|--------|--------|--------|-------|
| **Issues** | GraphQL | GraphQL | GraphQL | GraphQL | Full support |
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

**All operations via GraphQL.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| Get issue | GraphQL | `issue`, `repository`, `query`, `number` |
| List issues | GraphQL | `issues`, `repository`, `filter`, `states` |
| Create issue | GraphQL | `createIssue`, `mutation`, `repositoryId` |
| Update issue | GraphQL | `updateIssue`, `mutation`, `title`, `body`, `state` |
| Close issue | GraphQL | `closeIssue`, `mutation`, `stateReason` |
| Add comment | GraphQL | `addComment`, `mutation`, `subjectId` |
| Add labels | GraphQL | `addLabelsToLabelable`, `mutation`, `labelIds` |
| Set milestone | GraphQL | `updateIssue`, `milestoneId` |

---

### Pull Requests

**All operations via GraphQL.**

| Operation | API | Search Keywords |
|-----------|-----|-----------------|
| Get PR | GraphQL | `pullRequest`, `repository`, `query`, `number` |
| List PRs | GraphQL | `pullRequests`, `repository`, `states`, `filter` |
| Create PR | GraphQL | `createPullRequest`, `mutation`, `baseRefName`, `headRefName` |
| Update PR | GraphQL | `updatePullRequest`, `mutation`, `title`, `body` |
| Merge PR | GraphQL | `mergePullRequest`, `mutation`, `mergeMethod` |
| Request review | GraphQL | `requestReviews`, `mutation`, `userIds`, `teamIds` |
| Add comment | GraphQL | `addComment`, `mutation`, `subjectId` |

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
