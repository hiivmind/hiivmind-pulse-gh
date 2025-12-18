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

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| List | (Not available) | Use REST or GraphQL |
| Get | (Not available) | Use REST or GraphQL |
| Create | (Not available) | Use REST API |
| Update | (Not available) | Use REST API |
| Close | (Not available) | Use REST API |
| Delete | (Not available) | Use REST API |
| Set on issue | `gh issue edit {number} --milestone {milestone}` | Via issue edit |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/milestones`, `GET /milestones/{number}`, `POST /milestones`, `PATCH /milestones/{number}`, `DELETE /milestones/{number}` | `GET /repos`, `POST /milestones`, `PATCH /milestones/{number}`, `DELETE /milestones/{number}` |
| GraphQL | `milestones` (query), `updateIssue` with `milestoneId` (mutation) | `query { repository { milestones } }`, `mutation { updateIssue(input: {milestoneId: }) }` |

---

### Labels

**Hybrid: Read via GraphQL, CRUD via REST. Add/remove via GraphQL.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | No CLI direct support |
| Create | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Add to issue | ✓ | ✓ | ✓ | ✓ | Via gh issue edit or GraphQL |
| Remove from issue | ✓ | ✓ | ✓ | ✓ | Via gh issue edit or GraphQL |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| List | (Not available) | Use REST or GraphQL |
| Create | (Not available) | Use REST API |
| Update | (Not available) | Use REST API |
| Delete | (Not available) | Use REST API |
| Add to issue | `gh issue edit {number} --add-label {label}` | |
| Remove from issue | `gh issue edit {number} --remove-label {label}` | |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/labels`, `POST /labels`, `PATCH /labels/{name}`, `DELETE /labels/{name}`, `POST /issues/{number}/labels`, `DELETE /issues/{number}/labels/{name}` | `GET /repos`, `POST /labels`, `PATCH /labels/{name}`, `issues/{number}/labels` |
| GraphQL | `labels` (query), `addLabelsToLabelable`, `removeLabelsFromLabelable` (mutations) | `query { repository { labels } }`, `mutation { addLabelsToLabelable }`, `mutation { removeLabelsFromLabelable }` |

---

### Projects v2

**Everything via GraphQL except views (UI-only). REST has no project v2 support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✗ | ✓ | ✓ | GraphQL only |
| Get | ✗ | ✗ | ✓ | ✓ | GraphQL only |
| Create | ✗ | ✗ | ✓ | ✓ | GraphQL only |
| Add item | ✗ | ✗ | ✓ | ✓ | GraphQL only |
| Update field | ✗ | ✗ | ✓ | ✓ | GraphQL only |
| Archive item | ✗ | ✗ | ✓ | ✓ | GraphQL only |
| Create view | ✗ | ✗ | ✗ | ✓ | UI-only, no API |
| Delete view | ✗ | ✗ | ✗ | ✓ | UI-only, no API |
| Link repository | ✗ | ✗ | ✓ | ✓ | GraphQL only |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use GraphQL API or Web UI |

**Corpus Lookup Guide** (for exact API syntax):

| API | Mutations/Queries | Search Keywords |
|-----|-------------------|-----------------|
| GraphQL | `projectsV2`, `projectV2` (queries), `createProjectV2`, `updateProjectV2ItemFieldValue`, `archiveProjectV2Item`, `addProjectV2ItemById`, `linkProjectV2ToRepository` (mutations) | `query { organization { projectsV2 } }`, `mutation { addProjectV2ItemById }`, `mutation { updateProjectV2ItemFieldValue }` |

**Config prereqs:** Project ID, Field ID, Option ID from `.hiivmind/github/config.yaml`

**Limitations:**
- Views: UI-only, no API support for create/delete
- Field options: `updateProjectV2Field` mutation replaces all options at once

---

### Branch Protection (Legacy)

**REST API only. GraphQL read-only. For new repos, use Rulesets instead.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Get | ✗ | ✓ | ✓ | ✓ | GraphQL read-only |
| Set | ✗ | ✓ | ✗ | ✓ | REST only |
| Delete | ✗ | ✓ | ✗ | ✓ | REST only |
| Update status checks | ✗ | ✓ | ✗ | ✓ | REST only |
| Update PR reviews | ✗ | ✓ | ✗ | ✓ | REST only |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or Web UI |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/branches/{branch}/protection`, `PUT /branches/{branch}/protection`, `DELETE /branches/{branch}/protection` | `GET /repos`, `PUT /branches/{branch}/protection`, `required_status_checks`, `required_pull_request_reviews` |
| GraphQL | `branchProtectionRule` (read-only query) | `query { repository { branchProtectionRules } }` |

**Note:** `BranchProtectionRule` GraphQL type is read-only. Use REST for mutations or prefer Rulesets for new repos.

---

### Repository Rulesets (Modern)

**Hybrid: Read via both, mutations via REST only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | Both support reading |
| Get | ✗ | ✓ | ✓ | ✓ | Both support reading |
| Create | ✗ | ✓ | ✗ | ✓ | REST only |
| Update | ✗ | ✓ | ✗ | ✓ | REST only |
| Delete | ✗ | ✓ | ✗ | ✓ | REST only |
| Test rule | ✗ | ✓ | ✗ | ✓ | REST only |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or Web UI |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/rulesets`, `GET /rulesets/{ruleset_id}`, `POST /rulesets`, `PUT /rulesets/{ruleset_id}`, `DELETE /rulesets/{ruleset_id}`, `POST /rulesets/test` | `GET /repos`, `POST /rulesets`, `enforcement`, `conditions`, `rules` |
| GraphQL | `repository { rulesets }` (read-only query) | `query { repository { rulesets { edges { node } } } }` |

**Key concepts:** `target`, `enforcement` level, `conditions`, `ref_name` pattern, `rules` array

---

### Actions (Workflows, Runs, Jobs)

**REST API + gh CLI. No GraphQL support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List workflows | ✓ | ✓ | ✗ | ✓ | Full support |
| Get workflow | ✓ | ✓ | ✗ | ✓ | Full support |
| List runs | ✓ | ✓ | ✗ | ✓ | Full support |
| Get run | ✓ | ✓ | ✗ | ✓ | Full support |
| Trigger workflow | ✓ | ✓ | ✗ | ✓ | Full support |
| Cancel run | ✓ | ✓ | ✗ | ✓ | Full support |
| Re-run job | ✓ | ✓ | ✗ | ✓ | Full support |
| Re-run failed | ✓ | ✓ | ✗ | ✓ | Full support |

**CLI Command Reference:**

| Operation | Command |
|-----------|---------|
| List workflows | `gh workflow list` |
| Get workflow | `gh workflow view {workflow-id}` |
| List runs | `gh run list` |
| Get run | `gh run view {run-id}` |
| Trigger workflow | `gh workflow run {workflow-name}` |
| Cancel run | `gh run cancel {run-id}` |
| Re-run job | `gh run rerun {run-id}` |
| Re-run failed | `gh run rerun {run-id} --failed` |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/actions/workflows`, `GET /actions/workflows/{workflow_id}`, `GET /actions/runs`, `POST /actions/workflows/{workflow_id}/dispatches`, `POST /actions/runs/{run_id}/cancel`, `POST /actions/runs/{run_id}/rerun` | `GET /actions/workflows`, `GET /actions/runs`, `POST /dispatches`, `workflow_dispatch`, `run_id` |

**Note:** No GraphQL support for Actions. Use gh CLI (simpler) or REST API.

---

### Secrets

**REST API + gh CLI. No GraphQL support. Requires encryption.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✗ | ✓ | Full support |
| Get | ✓ | ✓ | ✗ | ✓ | Full support |
| Set/Create | ✓ | ✓ | ✗ | ✓ | Full support (gh CLI handles encryption) |
| Update | ✓ | ✓ | ✗ | ✓ | Same as set |
| Delete | ✓ | ✓ | ✗ | ✓ | Full support |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh secret list` | Repository secrets only |
| Get | `gh secret view {secret-name}` | Shows value (use carefully) |
| Set | `gh secret set {name} < value.txt` | Handles encryption automatically |
| Delete | `gh secret delete {name}` | |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/actions/secrets`, `GET /secrets/{secret_name}`, `PUT /secrets/{name}`, `DELETE /secrets/{name}` | `GET /actions/secrets`, `PUT /secrets/{name}`, `encrypted_value`, `key_id`, `public_key` |

**Key concept:** Secrets require encryption with repository public key. gh CLI handles this automatically. For REST API, must encrypt value with libsodium before sending.

**Scopes:** Repository, Environment (via `/environments/{env_name}/secrets`), Organization (via `/orgs/{org}/secrets`)

---

### Variables

**REST API + gh CLI only. No GraphQL support. No encryption needed (unlike Secrets).**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (repo) | ✓ | ✓ | ✗ | ✓ | Repository variables |
| Get (repo) | ✓ | ✓ | ✗ | ✓ | By name |
| Create (repo) | ✓ | ✓ | ✗ | ✓ | Via POST |
| Update (repo) | ✓ | ✓ | ✗ | ✓ | Via PATCH |
| Delete (repo) | ✓ | ✓ | ✗ | ✓ | |
| List (org) | ✗ | ✓ | ✗ | ✓ | Organization level |
| Create (org) | ✗ | ✓ | ✗ | ✓ | With visibility control |
| Update (org) | ✗ | ✓ | ✗ | ✓ | With visibility control |
| Delete (org) | ✗ | ✓ | ✗ | ✓ | |
| List (env) | ✗ | ✓ | ✗ | ✓ | Environment scope |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh variable list` | Repository only |
| Get | `gh variable get {name}` | Repository only |
| Set | `gh variable set {name} {value}` | Repository only; creates or updates |
| Delete | `gh variable delete {name}` | Repository only |
| Org operations | (Not available) | Use REST API |
| Env operations | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | Repository: `GET /repos/{owner}/{repo}/actions/variables`, `POST /variables`, `PATCH /variables/{name}`, `DELETE /variables/{name}` | Organization: `GET /orgs/{org}/actions/variables`, `POST /variables` | Environment: `GET /repos/{owner}/{repo}/environments/{env_name}/variables` | `GET /actions/variables`, `POST /variables`, `PATCH /variables/{name}`, `visibility`, `selected_repository_ids` |

**Key difference from Secrets:**
- **No encryption needed** - Variables are plain text
- **Org-level visibility control** - Can be marked `all`, `private`, or `selected` repositories
- **No GraphQL support** - Variables are REST-only

---

### Releases

**Hybrid: Read via REST + GraphQL, mutations via REST + gh CLI only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All support reading |
| Get by ID | ✓ | ✓ | ✓ | ✓ | All support reading |
| Get by tag | ✓ | ✓ | ✗ | ✓ | GraphQL requires ID lookup first |
| Get latest | ✓ | ✓ | ✓ | ✓ | All support reading |
| Create | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Upload asset | ✓ | ✓ | ✗ | ✓ | Special uploads.github.com endpoint |
| Update asset | ✗ | ✓ | ✗ | ✓ | Metadata only, no CLI support |
| Delete asset | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Generate notes | ✗ | ✓ | ✗ | ✓ | REST only, no CLI direct support |
| Verify attestation | ✓ | ✗ | ✗ | ✓ | CLI only, no REST endpoint |

**CLI Command Reference:**

| Operation | Command |
|-----------|---------|
| List | `gh release list` |
| Get | `gh release view {tag}` |
| Create | `gh release create {tag}` |
| Update | `gh release edit {tag}` |
| Delete | `gh release delete {tag}` |
| Upload asset | `gh release upload {tag} {file}` |
| Delete asset | `gh release delete-asset {tag} {asset-name}` |
| Download | `gh release download {tag}` |
| Verify attestation | `gh release verify {tag}` |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/releases`, `GET /releases/{release_id}`, `GET /releases/tags/{tag}`, `GET /releases/latest`, `POST /releases`, `PATCH /releases/{release_id}`, `DELETE /releases/{release_id}`, `POST /releases/generate-notes`, `POST https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets` | `GET /releases`, `POST /releases`, `tag_name`, `target_commitish`, `uploads.github.com`, `generate-notes` |
| GraphQL | `releases` (query), `release` (query) - No mutations available | `query { repository { releases { edges { node } } } }` |

**Note:** GraphQL has no mutations for release management. Upload asset uses special `uploads.github.com` endpoint.

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
