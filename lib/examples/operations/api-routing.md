# GitHub API Routing Guide

> **Purpose:** Quick reference for which API (GraphQL vs REST) to use for each domain.
> **Standalone:** This guide is useful on its own - you do not need corpus lookup for every operation.
> **When uncertain:** If you need exact syntax, use `lib/examples/operations/corpus-lookup.md`

---

## Quick Reference

**Legend:** ✓ = Supported | ✗ = Not available | ⊗ = Blocked for safety | See domain sections for CLI commands

| Domain | gh CLI | REST | GraphQL | Web UI | Notes |
|--------|--------|------|---------|--------|-------|
| **Issues** | ✓ | ✓ | ✓ | ✓ | Full CRUD via all 4 methods |
| **Pull Requests** | ✓ | ✓ | ✓ | ✓ | Full CRUD via all 4 methods |
| **Milestones** | ✗ | ✓ | Read only | ✓ | CRUD via REST, assign via GraphQL |
| **Labels** | ✓ | ✓ | Add/remove only | ✓ | CLI has full CRUD |
| **Projects v2** | ✓ | ✗ | ✓ | ✓ | CLI has items/fields, views UI-only |
| **Branch Protection** | ✗ | ✓ | Read only | ✓ | Prefer Rulesets for new repos |
| **Rulesets** | Read only | ✓ | Read only | ✓ | Mutations via REST |
| **Actions** | ✓ | ✓ | ✗ | ✓ | Workflows, runs, jobs |
| **Secrets** | ✓ | ✓ | ✗ | ✓ | CLI handles encryption |
| **Variables** | ✓ | ✓ | ✗ | ✓ | No encryption needed |
| **Releases** | ✓ | ✓ | Read only | ✓ | Mutations via REST + CLI |
| **Repository** | ✓ | ✓ | ✓ | ✓ | Some ops ⊗ blocked |
| **Gists** | ✓ | ✓ | Read only | ✓ | No GraphQL mutations |
| **Search** | ✓ | ✓ | ✓ | ✓ | Read-only operations |
| **Collaborators** | ✗ | ✓ | Read only | ✓ | REST for mutations |
| **Teams** | ✗ | ✓ | Read + discussions | ✓ | REST for CRUD |
| **Webhooks** | ✗ | ✓ | ✗ | ✓ | REST only |
| **Checks** | ✗ | ✓ | ✓ | ✓ | GitHub App required |
| **Deployments** | ✗ | ✓ | ✓ | ✓ | Full GraphQL support |
| **Environments** | ✗ | ✓ | ✓ | ✓ | Full GraphQL support |
| **Dependabot** | ✗ | ✓ | ✗ | ✓ | REST only |
| **Code Scanning** | ✗ | ✓ | ✗ | ✓ | REST only |
| **Secret Scanning** | ✗ | ✓ | ✗ | ✓ | REST only |
| **Notifications** | ✗ | ✓ | ✗ | ✓ | REST only |
| **Reactions** | ✗ | ✓ | ✓ | ✓ | Full GraphQL support |

---

## How to Choose an API Method

Use this guide to select the right method for your operation:

### 1. gh CLI (Try First)

**When:** Operation has CLI support (check ✓ in gh CLI column)

**Pros:** Simple syntax, handles auth/pagination automatically, human-readable output

**Example:** `gh issue create --title "Bug" --body "Description"`

### 2. REST API (CRUD Operations)

**When:** Creating/updating/deleting resources, or CLI not available

**Pros:** Full CRUD support, well-documented, predictable endpoints

**Example:** `gh api POST /repos/{owner}/{repo}/milestones -f title="v2.0"`

### 3. GraphQL (Complex Queries)

**When:** Reading nested data, need field selection, batch operations, or Projects v2

**Pros:** Get exactly what you need, fewer roundtrips, powerful filtering

**Example:** `gh api graphql -f query='{ repository(owner:"cli",name:"cli") { issues(first:10) { nodes { title } } } }'`

### 4. Web UI (Fallback)

**When:** Operation marked ⊗ (blocked) or ✓ only in Web UI column

**Why:** Some features are UI-only (e.g., Projects v2 views), dangerous operations require manual confirmation

**Example:** Project view creation, repository deletion

### Symbol Reference

| Symbol | Meaning |
|--------|---------|
| ✓ | Method is supported and available |
| ✗ | Method not available for this operation |
| ⊗ | Method exists but blocked for safety (see `docs/operation-blocklist.md`) |
| Read only | Can query but not mutate |

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

**Full CLI + REST support. GraphQL for read and add/remove only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All methods work |
| Create | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Clone | ✓ | ✗ | ✗ | ✗ | CLI-only bulk copy |
| Add to issue | ✓ | ✓ | ✓ | ✓ | Via gh issue edit or GraphQL |
| Remove from issue | ✓ | ✓ | ✓ | ✓ | Via gh issue edit or GraphQL |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh label list` | |
| Create | `gh label create {name} --color {hex}` | Color without # prefix |
| Update | `gh label edit {name} --name {new-name}` | Rename, change color/description |
| Delete | `gh label delete {name}` | |
| Clone | `gh label clone {source-repo}` | Copy all labels from another repo |
| Add to issue | `gh issue edit {number} --add-label {label}` | |
| Remove from issue | `gh issue edit {number} --remove-label {label}` | |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/labels`, `POST /labels`, `PATCH /labels/{name}`, `DELETE /labels/{name}`, `POST /issues/{number}/labels`, `DELETE /issues/{number}/labels/{name}` | `GET /repos`, `POST /labels`, `PATCH /labels/{name}`, `issues/{number}/labels` |
| GraphQL | `labels` (query), `addLabelsToLabelable`, `removeLabelsFromLabelable` (mutations) | `query { repository { labels } }`, `mutation { addLabelsToLabelable }`, `mutation { removeLabelsFromLabelable }` |

---

### Projects v2

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

**CLI Command Reference:**

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

**Corpus Lookup Guide** (for exact API syntax):

| API | Mutations/Queries | Search Keywords |
|-----|-------------------|-----------------|
| GraphQL | `projectsV2`, `projectV2` (queries), `createProjectV2`, `updateProjectV2`, `deleteProjectV2`, `copyProjectV2`, `updateProjectV2ItemFieldValue`, `archiveProjectV2Item`, `addProjectV2ItemById`, `addProjectV2DraftIssue`, `deleteProjectV2Item`, `linkProjectV2ToRepository`, `unlinkProjectV2FromRepository`, `markProjectV2AsTemplate` (mutations) | `query { organization { projectsV2 } }`, `mutation { addProjectV2ItemById }`, `mutation { updateProjectV2ItemFieldValue }` |

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

### Repository

**Full CLI support. REST and GraphQL both support most operations. Some operations blocked for safety.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | User or org repos |
| Get | ✓ | ✓ | ✓ | ✓ | |
| Create | ✓ | ✓ | ✓ | ✓ | |
| Update/Edit | ✓ | ✓ | ✓ | ✓ | Settings, description, visibility |
| Delete | ✓ | ✓ | ✗ | ✓ | ⊗ Blocked for safety |
| Archive | ✓ | ✗ | ✓ | ✓ | ⊗ Blocked for safety |
| Unarchive | ✓ | ✗ | ✓ | ✓ | |
| Fork | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Clone | ✓ | ✗ | ✗ | ✗ | CLI only (git operation) |
| Rename | ✓ | ✓ | ✓ | ✓ | Via PATCH or updateRepository |
| Transfer | ✗ | ✓ | ✗ | ✓ | ⊗ Blocked for safety |
| Sync (fork) | ✓ | ✓ | ✗ | ✓ | Sync fork with upstream |
| Update topics | ✗ | ✓ | ✓ | ✓ | Via updateTopics mutation |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh repo list [owner]` | List repos for user/org |
| Get | `gh repo view [repo]` | View repo details |
| Create | `gh repo create [name]` | Interactive or with flags |
| Edit | `gh repo edit [repo]` | Update settings |
| Delete | `gh repo delete [repo]` | ⊗ Blocked |
| Archive | `gh repo archive [repo]` | ⊗ Blocked |
| Unarchive | `gh repo unarchive [repo]` | |
| Fork | `gh repo fork [repo]` | |
| Clone | `gh repo clone [repo]` | |
| Rename | `gh repo rename [new-name]` | |
| Sync | `gh repo sync [repo]` | Sync fork with upstream |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}`, `GET /user/repos`, `GET /orgs/{org}/repos`, `POST /user/repos`, `POST /orgs/{org}/repos`, `PATCH /repos/{owner}/{repo}`, `DELETE /repos/{owner}/{repo}`, `POST /repos/{owner}/{repo}/forks`, `POST /repos/{owner}/{repo}/transfer`, `POST /repos/{owner}/{repo}/merge-upstream`, `PUT /repos/{owner}/{repo}/topics` | `GET /repos`, `POST /user/repos`, `PATCH /repos/{owner}/{repo}`, `POST /forks`, `PUT /topics` |
| GraphQL | `repository`, `repositories` (queries), `createRepository`, `updateRepository`, `archiveRepository`, `unarchiveRepository`, `updateTopics` (mutations) | `query { repository }`, `mutation { createRepository }`, `mutation { updateRepository }`, `mutation { archiveRepository }` |

**Note:** No GraphQL mutation for delete, fork, or transfer. Archive/unarchive use REST-like patterns but via GraphQL mutations. Repository delete/transfer/archive blocked for safety - see `docs/operation-blocklist.md`.

---

### Gists

**Full CLI + REST support. GraphQL read-only. No authentication required to read public gists.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | User's gists |
| Get | ✓ | ✓ | ✓ | ✓ | By ID |
| Create | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update/Edit | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Clone | ✓ | ✗ | ✗ | ✗ | CLI only (git operation) |
| Rename file | ✓ | ✓ | ✗ | ✓ | Rename file within gist |
| Fork | ✗ | ✓ | ✗ | ✓ | No CLI support |
| Star | ✗ | ✓ | ✗ | ✓ | No CLI support |
| Unstar | ✗ | ✓ | ✗ | ✓ | No CLI support |
| List starred | ✗ | ✓ | ✓ | ✓ | Via user gists query |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh gist list` | Your gists |
| Get | `gh gist view {id}` | View gist contents |
| Create | `gh gist create {file}` | Use `--public` for public gists |
| Edit | `gh gist edit {id}` | Opens editor |
| Delete | `gh gist delete {id}` | |
| Clone | `gh gist clone {id}` | Clone to local directory |
| Rename | `gh gist rename {id} {old} {new}` | Rename file in gist |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /gists`, `GET /gists/{gist_id}`, `GET /users/{username}/gists`, `POST /gists`, `PATCH /gists/{gist_id}`, `DELETE /gists/{gist_id}`, `POST /gists/{gist_id}/forks`, `PUT /gists/{gist_id}/star`, `DELETE /gists/{gist_id}/star`, `GET /gists/starred` | `GET /gists`, `POST /gists`, `PATCH /gists/{gist_id}`, `PUT /star`, `DELETE /star` |
| GraphQL | `gist`, `gists` (queries via user/viewer) - No mutations available | `query { viewer { gists } }`, `query { user { gists } }` |

**Note:** GraphQL has no mutations for gist management. Use CLI (simplest) or REST API.

---

### Search

**Full CLI + REST + GraphQL support. Read-only operations (search is inherently read-only).**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Search repos | ✓ | ✓ | ✓ | ✓ | Full search syntax support |
| Search issues | ✓ | ✓ | ✓ | ✓ | Full search syntax support |
| Search PRs | ✓ | ✓ | ✓ | ✓ | Full search syntax support |
| Search code | ✓ | ✓ | ✓ | ✓ | Rate limited |
| Search commits | ✓ | ✓ | ✗ | ✓ | No GraphQL support |
| Search users | ✗ | ✓ | ✓ | ✓ | No CLI support |
| Search topics | ✗ | ✓ | ✗ | ✓ | REST only |
| Search labels | ✗ | ✓ | ✗ | ✓ | REST only |
| Search discussions | ✗ | ✗ | ✓ | ✓ | GraphQL only |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| Search repos | `gh search repos {query}` | Rich filtering flags |
| Search issues | `gh search issues {query}` | Use `--` for queries with `-` |
| Search PRs | `gh search prs {query}` | Same syntax as issues |
| Search code | `gh search code {query}` | Rate limited |
| Search commits | `gh search commits {query}` | |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /search/repositories`, `GET /search/issues`, `GET /search/code`, `GET /search/commits`, `GET /search/users`, `GET /search/topics`, `GET /search/labels` | `GET /search/repositories`, `q=`, `sort=`, `order=`, `per_page` |
| GraphQL | `search(query: String!, type: SearchType!, first: Int)` - Types: REPOSITORY, ISSUE, ISSUE_ADVANCED, DISCUSSION, USER | `query { search(query: "...", type: REPOSITORY) { ... } }` |

**Note:** Search is read-only. GraphQL search returns a union type that includes Repository, Issue, PullRequest, Discussion, User. Code search is heavily rate limited.

---

### Collaborators

**REST API only for mutations. GraphQL read-only. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | Via repository.collaborators |
| Get | ✗ | ✓ | ✓ | ✓ | Check permission level |
| Add | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Remove | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Check permission | ✗ | ✓ | ✓ | ✓ | Permission level for user |
| List invitations | ✗ | ✓ | ✗ | ✓ | Pending invites |
| Update invitation | ✗ | ✓ | ✗ | ✓ | Change permission |
| Delete invitation | ✗ | ✓ | ✗ | ✓ | Cancel invite |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/collaborators`, `GET /collaborators/{username}`, `PUT /collaborators/{username}`, `DELETE /collaborators/{username}`, `GET /collaborators/{username}/permission`, `GET /repos/{owner}/{repo}/invitations`, `PATCH /invitations/{invitation_id}`, `DELETE /invitations/{invitation_id}` | `GET /collaborators`, `PUT /collaborators/{username}`, `permission`, `invitations` |
| GraphQL | `repository { collaborators }` (read-only query) | `query { repository { collaborators { edges { permission } } } }` |

**Note:** No GraphQL mutations for collaborator management. Use REST API for all write operations.

---

### Teams

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

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /orgs/{org}/teams`, `GET /orgs/{org}/teams/{team_slug}`, `POST /orgs/{org}/teams`, `PATCH /teams/{team_id}`, `DELETE /teams/{team_id}`, `GET /teams/{team_id}/members`, `PUT /teams/{team_id}/memberships/{username}`, `DELETE /teams/{team_id}/memberships/{username}`, `GET /teams/{team_id}/repos`, `PUT /teams/{team_id}/repos/{owner}/{repo}`, `DELETE /teams/{team_id}/repos/{owner}/{repo}` | `GET /orgs/{org}/teams`, `POST /teams`, `PUT /memberships`, `PUT /repos` |
| GraphQL | `team`, `teams` (queries), `createTeamDiscussion`, `updateTeamDiscussion`, `deleteTeamDiscussion`, `updateTeamsRepository` (mutations) | `query { organization { teams } }`, `mutation { updateTeamsRepository }` |

**Note:** Team CRUD and membership mutations are REST-only. GraphQL supports team discussions and repository assignments.

---

### Webhooks

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (repo) | ✗ | ✓ | ✗ | ✓ | Repository webhooks |
| Get | ✗ | ✓ | ✗ | ✓ | By ID |
| Create | ✗ | ✓ | ✗ | ✓ | |
| Update | ✗ | ✓ | ✗ | ✓ | |
| Delete | ✗ | ✓ | ✗ | ✓ | |
| Test (ping) | ✗ | ✓ | ✗ | ✓ | Trigger ping event |
| List deliveries | ✗ | ✓ | ✗ | ✓ | Delivery history |
| Get delivery | ✗ | ✓ | ✗ | ✓ | Specific delivery |
| Redeliver | ✗ | ✓ | ✗ | ✓ | Retry delivery |
| List (org) | ✗ | ✓ | ✗ | ✓ | Organization webhooks |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/hooks`, `GET /hooks/{hook_id}`, `POST /repos/{owner}/{repo}/hooks`, `PATCH /hooks/{hook_id}`, `DELETE /hooks/{hook_id}`, `POST /hooks/{hook_id}/pings`, `GET /hooks/{hook_id}/deliveries`, `GET /hooks/{hook_id}/deliveries/{delivery_id}`, `POST /hooks/{hook_id}/deliveries/{delivery_id}/attempts`, `GET /orgs/{org}/hooks` | `GET /hooks`, `POST /hooks`, `PATCH /hooks`, `pings`, `deliveries` |

**Note:** Webhooks are entirely REST-based. No GraphQL schema coverage for webhook management.

---

### Checks

**REST + GraphQL support. No CLI support. Used by GitHub Apps for CI status reporting.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Create check run | ✗ | ✓ | ✓ | ✗ | GitHub App only |
| Update check run | ✗ | ✓ | ✓ | ✗ | GitHub App only |
| Get check run | ✗ | ✓ | ✓ | ✓ | |
| List check runs | ✗ | ✓ | ✓ | ✓ | For ref or check suite |
| Rerequest check run | ✗ | ✓ | ✓ | ✓ | rerequestCheckSuite mutation |
| Create check suite | ✗ | ✓ | ✗ | ✗ | REST only |
| Get check suite | ✗ | ✓ | ✓ | ✓ | |
| List check suites | ✗ | ✓ | ✓ | ✓ | For ref |
| Set preferences | ✗ | ✓ | ✗ | ✓ | Auto-trigger settings |
| List annotations | ✗ | ✓ | ✓ | ✓ | Per check run |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| View PR checks | `gh pr checks {number}` | View check status only |
| All mutations | (Not available) | Use REST API or GraphQL |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `POST /repos/{owner}/{repo}/check-runs`, `PATCH /check-runs/{check_run_id}`, `GET /check-runs/{check_run_id}`, `GET /repos/{owner}/{repo}/commits/{ref}/check-runs`, `POST /check-suites`, `GET /check-suites/{check_suite_id}`, `GET /commits/{ref}/check-suites`, `PATCH /repos/{owner}/{repo}/check-suites/preferences`, `GET /check-runs/{check_run_id}/annotations` | `POST /check-runs`, `PATCH /check-runs`, `check-suites`, `annotations` |
| GraphQL | `checkRun`, `checkSuite` (queries), `createCheckRun`, `updateCheckRun`, `rerequestCheckSuite` (mutations) | `query { repository { checkSuites } }`, `mutation { createCheckRun }`, `mutation { updateCheckRun }` |

**Note:** Check run creation/updates require a GitHub App installation. PATs cannot create checks. CLI can only view check status via `gh pr checks`.

---

### Deployments

**REST + GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | |
| Get | ✗ | ✓ | ✓ | ✓ | |
| Create | ✗ | ✓ | ✓ | ✗ | createDeployment mutation |
| Delete | ✗ | ✓ | ✗ | ✗ | REST only, inactive only |
| Create status | ✗ | ✓ | ✓ | ✗ | createDeploymentStatus mutation |
| List statuses | ✗ | ✓ | ✓ | ✓ | |
| Get status | ✗ | ✓ | ✓ | ✓ | |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or GraphQL |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/deployments`, `GET /deployments/{deployment_id}`, `POST /repos/{owner}/{repo}/deployments`, `DELETE /deployments/{deployment_id}`, `POST /deployments/{deployment_id}/statuses`, `GET /deployments/{deployment_id}/statuses` | `GET /deployments`, `POST /deployments`, `POST /statuses`, `environment`, `ref`, `task` |
| GraphQL | `deployment`, `deployments` (queries), `createDeployment`, `createDeploymentStatus` (mutations) | `query { repository { deployments } }`, `mutation { createDeployment }`, `mutation { createDeploymentStatus }` |

**Note:** Deployments track code being deployed to environments. Use with environments for full deployment workflow.

---

### Environments

**Full GraphQL support. REST API available. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | |
| Get | ✗ | ✓ | ✓ | ✓ | By name |
| Create | ✗ | ✓ | ✓ | ✓ | createEnvironment mutation |
| Update | ✗ | ✓ | ✓ | ✓ | updateEnvironment mutation |
| Delete | ✗ | ✓ | ✓ | ✓ | deleteEnvironment mutation |
| Get secrets | ✗ | ✓ | ✗ | ✓ | Via secrets endpoints |
| Set secret | ✗ | ✓ | ✗ | ✓ | Via secrets endpoints |
| Get variables | ✗ | ✓ | ✗ | ✓ | Via variables endpoints |
| Set variable | ✗ | ✓ | ✗ | ✓ | Via variables endpoints |
| Set protection rules | ✗ | ✓ | ✓ | ✓ | Reviewers, wait timer, branch policy |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or GraphQL |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/environments`, `GET /environments/{environment_name}`, `PUT /environments/{environment_name}`, `DELETE /environments/{environment_name}`, `GET /environments/{environment_name}/secrets`, `PUT /environments/{environment_name}/secrets/{secret_name}`, `GET /environments/{environment_name}/variables` | `GET /environments`, `PUT /environments`, `DELETE /environments`, `secrets`, `variables`, `protection_rules` |
| GraphQL | `environment` (query), `createEnvironment`, `updateEnvironment`, `deleteEnvironment` (mutations) | `query { repository { environments } }`, `mutation { createEnvironment }`, `mutation { updateEnvironment }` |

**Note:** Environments provide deployment targets with protection rules (required reviewers, wait timers, branch policies). Environment secrets/variables use REST endpoints under `/environments/{name}/secrets` and `/environments/{name}/variables`.

---

### Dependabot

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List alerts | ✗ | ✓ | ✗ | ✓ | |
| Get alert | ✗ | ✓ | ✗ | ✓ | |
| Update alert | ✗ | ✓ | ✗ | ✓ | Dismiss/reopen |
| List org alerts | ✗ | ✓ | ✗ | ✓ | Enterprise scope |
| Enable/disable | ✗ | ✓ | ✗ | ✓ | Via repo settings |
| List secrets | ✗ | ✓ | ✗ | ✓ | Dependabot secrets |
| Set secret | ✗ | ✓ | ✗ | ✓ | Encrypted |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/dependabot/alerts`, `GET /dependabot/alerts/{alert_number}`, `PATCH /dependabot/alerts/{alert_number}`, `GET /orgs/{org}/dependabot/alerts`, `GET /repos/{owner}/{repo}/dependabot/secrets`, `PUT /dependabot/secrets/{secret_name}` | `GET /dependabot/alerts`, `PATCH /dependabot/alerts`, `state`, `dismissed_reason`, `dependabot/secrets` |

**Note:** Dependabot alerts are REST-only. No GraphQL schema coverage for security alerts.

---

### Code Scanning

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List alerts | ✗ | ✓ | ✗ | ✓ | |
| Get alert | ✗ | ✓ | ✗ | ✓ | |
| Update alert | ✗ | ✓ | ✗ | ✓ | Dismiss/reopen |
| List instances | ✗ | ✓ | ✗ | ✓ | Alert instances |
| List analyses | ✗ | ✓ | ✗ | ✓ | |
| Get analysis | ✗ | ✓ | ✗ | ✓ | |
| Delete analysis | ✗ | ✓ | ✗ | ✗ | REST only |
| Upload SARIF | ✗ | ✓ | ✗ | ✗ | For custom tools |
| Get SARIF | ✗ | ✓ | ✗ | ✗ | Upload status |
| List org alerts | ✗ | ✓ | ✗ | ✓ | Enterprise scope |
| Get default setup | ✗ | ✓ | ✗ | ✓ | CodeQL config |
| Update default setup | ✗ | ✓ | ✗ | ✓ | Enable/configure |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/code-scanning/alerts`, `GET /code-scanning/alerts/{alert_number}`, `PATCH /code-scanning/alerts/{alert_number}`, `GET /code-scanning/alerts/{alert_number}/instances`, `GET /repos/{owner}/{repo}/code-scanning/analyses`, `DELETE /code-scanning/analyses/{analysis_id}`, `POST /repos/{owner}/{repo}/code-scanning/sarifs`, `GET /code-scanning/sarifs/{sarif_id}`, `GET /repos/{owner}/{repo}/code-scanning/default-setup`, `PATCH /repos/{owner}/{repo}/code-scanning/default-setup` | `GET /code-scanning/alerts`, `PATCH /code-scanning/alerts`, `sarifs`, `default-setup`, `state`, `dismissed_reason` |

**Note:** Code scanning alerts are REST-only. SARIF upload enables integration with third-party security tools.

---

### Secret Scanning

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List alerts | ✗ | ✓ | ✗ | ✓ | |
| Get alert | ✗ | ✓ | ✗ | ✓ | |
| Update alert | ✗ | ✓ | ✗ | ✓ | Resolve/reopen |
| List locations | ✗ | ✓ | ✗ | ✓ | Where secret found |
| List org alerts | ✗ | ✓ | ✗ | ✓ | Enterprise scope |
| Enable push protection | ✗ | ✓ | ✗ | ✓ | Via repo settings |
| Bypass push protection | ✗ | ✓ | ✗ | ✗ | Requires reason |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/secret-scanning/alerts`, `GET /secret-scanning/alerts/{alert_number}`, `PATCH /secret-scanning/alerts/{alert_number}`, `GET /secret-scanning/alerts/{alert_number}/locations`, `GET /orgs/{org}/secret-scanning/alerts` | `GET /secret-scanning/alerts`, `PATCH /secret-scanning/alerts`, `locations`, `state`, `resolution` |

**Note:** Secret scanning alerts are REST-only. No GraphQL schema coverage for security alerts.

---

### Notifications

**REST API only. No GraphQL support. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✗ | ✓ | All notifications |
| Mark as read | ✗ | ✓ | ✗ | ✓ | Single notification |
| Mark all read | ✗ | ✓ | ✗ | ✓ | All or per-repo |
| Get thread | ✗ | ✓ | ✗ | ✓ | |
| Mark thread read | ✗ | ✓ | ✗ | ✓ | |
| Get subscription | ✗ | ✓ | ✗ | ✓ | Thread subscription |
| Set subscription | ✗ | ✓ | ✗ | ✓ | Subscribe/ignore |
| Delete subscription | ✗ | ✓ | ✗ | ✓ | Unsubscribe |
| List repo notifications | ✗ | ✓ | ✗ | ✓ | Scoped to repo |
| Mark repo read | ✗ | ✓ | ✗ | ✓ | All in repo |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| View status | `gh status` | Shows notifications summary |
| All mutations | (Not available) | Use REST API |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /notifications`, `PUT /notifications`, `GET /notifications/threads/{thread_id}`, `PATCH /notifications/threads/{thread_id}`, `GET /notifications/threads/{thread_id}/subscription`, `PUT /notifications/threads/{thread_id}/subscription`, `DELETE /notifications/threads/{thread_id}/subscription`, `GET /repos/{owner}/{repo}/notifications`, `PUT /repos/{owner}/{repo}/notifications` | `GET /notifications`, `PUT /notifications`, `threads`, `subscription`, `all`, `participating` |

**Note:** Notifications are REST-only. The `gh status` command shows a summary but doesn't support mutations.

---

### Reactions

**Full GraphQL support. REST API available. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (issue) | ✗ | ✓ | ✓ | ✓ | |
| List (comment) | ✗ | ✓ | ✓ | ✓ | |
| List (PR) | ✗ | ✓ | ✓ | ✓ | |
| Add | ✗ | ✓ | ✓ | ✓ | addReaction mutation |
| Remove | ✗ | ✓ | ✓ | ✓ | removeReaction mutation |
| Delete (by ID) | ✗ | ✓ | ✗ | ✗ | REST only |

**CLI Command Reference:**

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API or GraphQL |

**Corpus Lookup Guide** (for exact API syntax):

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/issues/{issue_number}/reactions`, `POST /issues/{issue_number}/reactions`, `DELETE /reactions/{reaction_id}`, `GET /issues/comments/{comment_id}/reactions`, `POST /issues/comments/{comment_id}/reactions`, `GET /pulls/comments/{comment_id}/reactions` | `GET /reactions`, `POST /reactions`, `DELETE /reactions`, `content` (+1, -1, laugh, confused, heart, hooray, rocket, eyes) |
| GraphQL | `reactions` (query on Reactable types), `addReaction`, `removeReaction` (mutations) | `query { issue { reactions } }`, `mutation { addReaction(input: {subjectId: ..., content: THUMBS_UP}) }` |

**Reaction types:** `+1`, `-1`, `laugh`, `confused`, `heart`, `hooray`, `rocket`, `eyes`. GraphQL uses enum: `THUMBS_UP`, `THUMBS_DOWN`, `LAUGH`, `CONFUSED`, `HEART`, `HOORAY`, `ROCKET`, `EYES`.

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
