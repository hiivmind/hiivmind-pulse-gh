# GitHub API Documentation Corpus (Pulse Edition)

> **Purpose:** JIT specifics for hiivmind-pulse-gh operations
> **Usage:** Search using keywords from `reference/api-routing.md`, then read source docs
> **Source:** github/docs @ 93fb820
> **Last updated:** 2025-12-15

---

## Quick Reference: GraphQL Schema

**File:** `data/uploads/graphql-schema/schema.docs.graphql`

Search patterns for the schema (70k lines):
- Find type: `grep -n "^type {Name} " schema.docs.graphql -A 50`
- Find input: `grep -n "^input {Name} " schema.docs.graphql -A 30`
- Find enum: `grep -n "^enum {Name} " schema.docs.graphql -A 20`
- Find mutation: `grep -n "{mutationName}" schema.docs.graphql -B 5 -A 30`

---

## Keyword-Tagged Index

### Issues

**Keywords:** `issue`, `issues`, `createIssue`, `updateIssue`, `closeIssue`, `addComment`, `subjectId`

| Topic | Path | Keywords |
|-------|------|----------|
| About issues | `.source/docs/content/issues/tracking-your-work-with-issues/about-issues.md` | `issue`, `tracking` |
| Create issue | `.source/docs/content/rest/issues/issues.md` | `createIssue`, `POST`, `create` |
| Update issue | `.source/docs/content/rest/issues/issues.md` | `updateIssue`, `PATCH`, `state` |
| GraphQL Issue type | `graphql-schema:schema.docs.graphql` | `type Issue`, `number`, `state` |
| GraphQL mutations | `graphql-schema:schema.docs.graphql` | `createIssue`, `updateIssue`, `closeIssue` |

**Section index:** → `sections/issues.md`

---

### Pull Requests

**Keywords:** `pullRequest`, `pullRequests`, `createPullRequest`, `updatePullRequest`, `mergePullRequest`, `requestReviews`

| Topic | Path | Keywords |
|-------|------|----------|
| About PRs | `.source/docs/content/pull-requests/collaborating-with-pull-requests/proposing-changes/about-pull-requests.md` | `pullRequest`, `review` |
| Create PR | `.source/docs/content/rest/pulls/pulls.md` | `createPullRequest`, `POST`, `head`, `base` |
| Merge PR | `.source/docs/content/rest/pulls/pulls.md` | `mergePullRequest`, `PUT`, `merge_method` |
| GraphQL PR type | `graphql-schema:schema.docs.graphql` | `type PullRequest`, `mergeable` |
| GraphQL mutations | `graphql-schema:schema.docs.graphql` | `createPullRequest`, `mergePullRequest`, `requestReviews` |

**Section index:** → `sections/pull-requests.md`

---

### Milestones

**Keywords:** `milestone`, `milestones`, `due_on`, `updateIssue`, `milestoneId`

| Topic | Path | Keywords |
|-------|------|----------|
| About milestones | `.source/docs/content/issues/using-labels-and-milestones/about-milestones.md` | `milestone`, `tracking` |
| REST CRUD | `.source/docs/content/rest/issues/milestones.md` | `milestones`, `POST`, `PATCH`, `DELETE`, `due_on` |
| GraphQL query | `graphql-schema:schema.docs.graphql` | `type Milestone`, `milestones`, `repository` |
| Set on issue | `graphql-schema:schema.docs.graphql` | `updateIssue`, `milestoneId` |

**REST endpoints:**
- `POST /repos/{owner}/{repo}/milestones` - create
- `PATCH /repos/{owner}/{repo}/milestones/{number}` - update
- `DELETE /repos/{owner}/{repo}/milestones/{number}` - delete

---

### Labels

**Keywords:** `label`, `labels`, `addLabelsToLabelable`, `removeLabelsFromLabelable`, `labelIds`

| Topic | Path | Keywords |
|-------|------|----------|
| Managing labels | `.source/docs/content/issues/using-labels-and-milestones/managing-labels.md` | `labels`, `create`, `edit` |
| REST CRUD | `.source/docs/content/rest/issues/labels.md` | `labels`, `POST`, `PATCH`, `DELETE`, `color` |
| GraphQL mutations | `graphql-schema:schema.docs.graphql` | `addLabelsToLabelable`, `removeLabelsFromLabelable` |

---

### Projects v2

**Keywords:** `projectV2`, `projectsV2`, `addProjectV2ItemById`, `updateProjectV2ItemFieldValue`, `archiveProjectV2Item`, `createProjectV2StatusUpdate`, `linkProjectV2ToRepository`

| Topic | Path | Keywords |
|-------|------|----------|
| About Projects | `.source/docs/content/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects.md` | `projectV2`, `planning` |
| Managing items | `.source/docs/content/issues/planning-and-tracking-with-projects/managing-items-in-your-project/` | `items`, `add`, `archive` |
| Fields | `.source/docs/content/issues/planning-and-tracking-with-projects/understanding-fields/` | `fields`, `fieldId`, `singleSelectOptions` |
| Views | `.source/docs/content/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/` | `views`, `layout`, `filter` |
| GraphQL types | `graphql-schema:schema.docs.graphql` | `type ProjectV2`, `ProjectV2Item`, `ProjectV2Field` |
| GraphQL mutations | `graphql-schema:schema.docs.graphql` | `addProjectV2ItemById`, `updateProjectV2ItemFieldValue`, `archiveProjectV2Item` |
| Status updates | `graphql-schema:schema.docs.graphql` | `createProjectV2StatusUpdate`, `ON_TRACK`, `AT_RISK` |
| Link repo | `graphql-schema:schema.docs.graphql` | `linkProjectV2ToRepository`, `repositoryId` |

**Known limitations:**
- Views: create/update is UI-only (no `createProjectV2View` mutation)
- Field options: `updateProjectV2Field` replaces ALL options

**Section index:** → `sections/issues.md` (Projects subsection)

---

### Branch Protection (Legacy)

**Keywords:** `branch protection`, `required_status_checks`, `enforce_admins`, `required_pull_request_reviews`, `BranchProtectionRule`

| Topic | Path | Keywords |
|-------|------|----------|
| About protection | `.source/docs/content/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches.md` | `protection`, `branch` |
| REST endpoints | `.source/docs/content/rest/branches/branch-protection.md` | `PUT`, `GET`, `DELETE`, `protection` |
| Status checks | `.source/docs/content/rest/branches/branch-protection.md` | `required_status_checks`, `contexts`, `strict` |
| PR reviews | `.source/docs/content/rest/branches/branch-protection.md` | `required_pull_request_reviews`, `approving_review_count` |
| GraphQL (read-only) | `graphql-schema:schema.docs.graphql` | `type BranchProtectionRule` |

**REST endpoints:**
- `GET /repos/{owner}/{repo}/branches/{branch}/protection`
- `PUT /repos/{owner}/{repo}/branches/{branch}/protection`
- `DELETE /repos/{owner}/{repo}/branches/{branch}/protection`

---

### Repository Rulesets (Modern)

**Keywords:** `rulesets`, `ruleset`, `enforcement`, `conditions`, `ref_name`, `target`

| Topic | Path | Keywords |
|-------|------|----------|
| About rulesets | `.source/docs/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets.md` | `rulesets`, `conditions` |
| Available rules | `.source/docs/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md` | `rules`, `creation`, `deletion` |
| REST endpoints | `.source/docs/content/rest/repos/rules.md` | `rulesets`, `POST`, `PUT`, `DELETE` |
| GraphQL query | `graphql-schema:schema.docs.graphql` | `type RepositoryRuleset`, `rulesets` |

**REST endpoints:**
- `GET /repos/{owner}/{repo}/rulesets`
- `POST /repos/{owner}/{repo}/rulesets`
- `GET /repos/{owner}/{repo}/rulesets/{id}`
- `PUT /repos/{owner}/{repo}/rulesets/{id}`
- `DELETE /repos/{owner}/{repo}/rulesets/{id}`
- `GET /repos/{owner}/{repo}/rules/branches/{branch}` - check what applies

---

### Actions (Workflows, Runs, Jobs)

**Keywords:** `workflows`, `runs`, `jobs`, `actions`, `workflow_dispatch`, `dispatches`, `cancel`, `rerun`

| Topic | Path | Keywords |
|-------|------|----------|
| Understanding Actions | `.source/docs/content/actions/learn-github-actions/understanding-github-actions.md` | `actions`, `workflows` |
| Workflow syntax | `.source/docs/content/actions/using-workflows/workflow-syntax-for-github-actions.md` | `workflow`, `jobs`, `steps` |
| REST workflows | `.source/docs/content/rest/actions/workflows.md` | `workflows`, `GET`, `workflow_id` |
| REST runs | `.source/docs/content/rest/actions/workflow-runs.md` | `runs`, `run_id`, `cancel`, `rerun` |
| REST jobs | `.source/docs/content/rest/actions/workflow-jobs.md` | `jobs`, `job_id` |
| Trigger workflow | `.source/docs/content/rest/actions/workflows.md` | `dispatches`, `POST`, `workflow_dispatch` |

**REST endpoints:**
- `GET /repos/{owner}/{repo}/actions/workflows`
- `GET /repos/{owner}/{repo}/actions/runs`
- `POST /repos/{owner}/{repo}/actions/workflows/{id}/dispatches`
- `POST /repos/{owner}/{repo}/actions/runs/{id}/cancel`
- `POST /repos/{owner}/{repo}/actions/runs/{id}/rerun`

**CLI alternative:** `gh run`, `gh workflow`

---

### Secrets

**Keywords:** `secrets`, `encrypted_value`, `key_id`, `public-key`, `environments`

| Topic | Path | Keywords |
|-------|------|----------|
| Using secrets | `.source/docs/content/actions/security-guides/using-secrets-in-github-actions.md` | `secrets`, `encrypted` |
| REST repo secrets | `.source/docs/content/rest/actions/secrets.md` | `secrets`, `PUT`, `DELETE`, `key_id` |
| REST org secrets | `.source/docs/content/rest/actions/secrets.md` | `orgs`, `secrets`, `visibility` |
| Public key | `.source/docs/content/rest/actions/secrets.md` | `public-key`, `encrypt` |

**REST endpoints:**
- `GET /repos/{owner}/{repo}/actions/secrets`
- `GET /repos/{owner}/{repo}/actions/secrets/public-key`
- `PUT /repos/{owner}/{repo}/actions/secrets/{name}`
- `DELETE /repos/{owner}/{repo}/actions/secrets/{name}`

**Encryption required.** CLI alternative: `gh secret` (handles encryption automatically)

---

### Variables

**Keywords:** `variables`, `actions`, `environments`, `visibility`

| Topic | Path | Keywords |
|-------|------|----------|
| Using variables | `.source/docs/content/actions/learn-github-actions/variables.md` | `variables`, `env` |
| REST repo vars | `.source/docs/content/rest/actions/variables.md` | `variables`, `POST`, `PATCH`, `DELETE` |
| REST org vars | `.source/docs/content/rest/actions/variables.md` | `orgs`, `variables`, `visibility` |

**REST endpoints:**
- `GET /repos/{owner}/{repo}/actions/variables`
- `POST /repos/{owner}/{repo}/actions/variables`
- `PATCH /repos/{owner}/{repo}/actions/variables/{name}`
- `DELETE /repos/{owner}/{repo}/actions/variables/{name}`

**No encryption needed** (unlike secrets).

---

### Releases

**Keywords:** `releases`, `release`, `tag_name`, `target_commitish`, `assets`, `generate-notes`

| Topic | Path | Keywords |
|-------|------|----------|
| About releases | `.source/docs/content/repositories/releasing-projects-on-github/about-releases.md` | `releases`, `tag` |
| Managing releases | `.source/docs/content/repositories/releasing-projects-on-github/managing-releases-in-a-repository.md` | `create`, `edit`, `delete` |
| REST endpoints | `.source/docs/content/rest/releases/releases.md` | `releases`, `POST`, `PATCH`, `DELETE` |
| REST assets | `.source/docs/content/rest/releases/assets.md` | `assets`, `uploads.github.com` |
| GraphQL query | `graphql-schema:schema.docs.graphql` | `type Release`, `releases`, `latestRelease` |

**REST endpoints:**
- `GET /repos/{owner}/{repo}/releases`
- `GET /repos/{owner}/{repo}/releases/latest`
- `POST /repos/{owner}/{repo}/releases`
- `PATCH /repos/{owner}/{repo}/releases/{id}`
- `DELETE /repos/{owner}/{repo}/releases/{id}`
- `POST /repos/{owner}/{repo}/releases/generate-notes`

**CLI alternative:** `gh release`

---

### Identity & Organizations

**Keywords:** `viewer`, `user`, `organization`, `teams`, `members`

| Topic | Path | Keywords |
|-------|------|----------|
| About orgs | `.source/docs/content/organizations/collaborating-with-groups-in-organizations/about-organizations.md` | `organization`, `teams` |
| REST users | `.source/docs/content/rest/users/users.md` | `users`, `GET` |
| REST orgs | `.source/docs/content/rest/orgs/orgs.md` | `orgs`, `GET` |
| GraphQL viewer | `graphql-schema:schema.docs.graphql` | `Query`, `viewer`, `User` |
| GraphQL org | `graphql-schema:schema.docs.graphql` | `type Organization`, `teams`, `projectsV2` |

**Section index:** → `sections/organizations.md`

---

### GitHub CLI

**Keywords:** `gh`, `cli`, `api`, `issue`, `pr`, `run`, `workflow`, `secret`, `release`

| Topic | Path | Keywords |
|-------|------|----------|
| CLI manual | `.source/docs/content/github-cli/github-cli/about-github-cli.md` | `gh`, `cli` |
| gh api | `.source/docs/content/github-cli/github-cli/using-github-cli-in-workflows.md` | `gh api`, `REST`, `GraphQL` |

**Common commands:**
- `gh api /repos/{owner}/{repo}/...` - REST API calls
- `gh api graphql -f query='...'` - GraphQL queries
- `gh issue`, `gh pr`, `gh run`, `gh workflow`, `gh secret`, `gh release`

**Section index:** → `sections/github-cli.md`

---

## Section Indices

Detailed indices for each domain:

| Section | File |
|---------|------|
| REST API | `sections/rest.md` |
| GraphQL | `sections/graphql.md` |
| Issues | `sections/issues.md` |
| Pull Requests | `sections/pull-requests.md` |
| Repositories | `sections/repositories.md` |
| Actions | `sections/actions.md` |
| Organizations | `sections/organizations.md` |
| GitHub CLI | `sections/github-cli.md` |
| Authentication | `sections/authentication.md` |

---

## Path Reference

| Source ID | Local Path |
|-----------|------------|
| `docs` | `.source/docs/content/` |
| `graphql-schema` | `data/uploads/graphql-schema/` |
