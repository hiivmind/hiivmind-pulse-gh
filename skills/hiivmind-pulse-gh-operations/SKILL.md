---
name: hiivmind-pulse-gh-operations
description: >
  Execute GitHub operations across all domains (issues, PRs, milestones, projects, protection,
  actions, releases). Receives intent from gateway command, consults routing guide and corpus,
  executes via gh CLI. Use when the gateway command routes an operation here after intent detection.
---

# GitHub Operations Execution

Execute GitHub operations across all domains.

## Scope

| Does | Does NOT |
|------|----------|
| Execute GitHub operations | Modify local config files |
| Resolve IDs from cached config | Initialize workspaces |
| Support all domains (issues, PRs, etc.) | Refresh stale configs |
| Report operation results | Detect user intent (gateway does this) |

## Expected Context

When invoked by the gateway command, expect:

- **Domain**: issues, pull_requests, milestones, labels, projects, branch_protection, rulesets, actions, secrets, variables, releases, repositories, collaborators, teams, checks, deployments, security, dependabot, search, gists, or **any unlisted domain**
- **Operation**: create, read, update, delete, link, trigger, merge
- **Target**: Specific entity (issue #42, milestone "v2.0", etc.)
- **Config**: `.hiivmind/github/config.yaml`

**Note:** For unlisted domains, the gateway passes the detected resource name. Use corpus lookup for API syntax.

## Phase Overview

```
1. CONTEXT → 2. RESOLVE → 3. ROUTE → 4. EXECUTE → 5. REPORT
   (load)      (IDs)       (API)      (run)        (result)
      │           │           │           │           │
   STOP if    From cache   Read full   Direct or   Display
   not init   via pattern  routing     corpus      result
```

---

## Phase 1: CONTEXT

**Goal:** Load workspace configuration.

**See:** `lib/github/patterns/config-parsing.md`

### What to Do

1. Check for `.hiivmind/github/config.yaml`
2. Load workspace info (owner, type, repositories)
3. Load default project if set

### STOP Point

**If not initialized:**

```
Workspace not initialized.

Config file not found: .hiivmind/github/config.yaml

Run: /hiivmind-pulse-gh init
```

---

## Phase 2: RESOLVE IDs

**Goal:** Resolve any IDs needed for the operation from cached config.

**See:** `lib/github/patterns/id-resolution.md`

### What to Do

Based on domain and operation, resolve:

| Domain | IDs Needed |
|--------|------------|
| Issues | Repository ID |
| PRs | Repository ID |
| Milestones | Repository name (REST uses name, not ID) |
| Labels | Repository name |
| Projects v2 | Project ID, Field ID, Option ID |
| Branch Protection | Repository name, branch name |
| Rulesets | Repository name |
| Actions | Repository name, workflow ID |
| Secrets | Repository name |
| Variables | Repository name |
| Releases | Repository name |
| Repositories | Repository name (or owner for org-level) |
| Collaborators | Repository name |
| Teams | Organization name |
| Checks | Repository name |
| Deployments | Repository name |
| Security | Repository name |
| Dependabot | Repository name |
| Search | Query string (no IDs needed) |
| Gists | Gist ID (if updating existing) |

### Unknown Domains

For domains not listed above:
1. Default to repository name from config
2. Corpus lookup will determine exact endpoint requirements

### Cache-First Strategy

1. Check config.yaml for cached ID
2. If not found, use corpus lookup to query and cache

---

## Phase 3: ROUTE

**Goal:** Determine the correct API (GraphQL vs REST) and get search keywords.

### PREREQUISITE: Read Routing Guide

**IMPORTANT:** Read the FULL `reference/api-routing.md` file.

- Do NOT grep or search - read it completely
- This gives you routing decisions for documented domains
- You need this context to make correct API decisions

```
Read: reference/api-routing.md (full file)
```

### Domain Quick Reference

| Domain | API | Key Operations |
|--------|-----|----------------|
| Issues | GraphQL | `createIssue`, `updateIssue`, `closeIssue`, `addLabelsToLabelable` |
| PRs | GraphQL | `createPullRequest`, `mergePullRequest`, `requestReviews` |
| Milestones | REST | `POST /milestones`, `PATCH /milestones/{number}` |
| Labels | REST | `POST /labels`, `PATCH /labels/{name}` |
| Projects v2 | GraphQL | `addProjectV2ItemById`, `updateProjectV2ItemFieldValue` |
| Branch Protection | REST | `PUT /branches/{branch}/protection` |
| Rulesets | REST | `POST /rulesets`, `PUT /rulesets/{id}` |
| Actions | REST | `POST /dispatches`, `GET /runs` |
| Secrets | REST | `PUT /secrets/{name}` (requires encryption) |
| Variables | REST | `POST /variables`, `PATCH /variables/{name}` |
| Releases | REST | `POST /releases` |
| Repositories | REST | `POST /user/repos`, `PATCH /repos/{owner}/{repo}` |
| Collaborators | REST | `PUT /collaborators/{username}` |
| Teams | REST | `POST /orgs/{org}/teams` |
| Checks | REST | `POST /check-runs`, `PATCH /check-runs/{id}` |
| Deployments | REST | `POST /deployments` |
| Security | REST | `GET /code-scanning/alerts`, `PATCH /code-scanning/alerts/{number}` |
| Dependabot | REST | `GET /dependabot/alerts`, `PATCH /dependabot/alerts/{number}` |
| Search | REST/GraphQL | `GET /search/{type}` (read-only) |
| Gists | REST | `POST /gists`, `PATCH /gists/{id}` |

### Unknown Domains (Fallback)

**If domain is not in routing guide:**

1. **Default to REST API** - Most GitHub features use REST for mutations
2. **Invoke corpus skill** for endpoint syntax:
   - `hiivmind-pulse-gh:hiivmind-corpus-github`
   - Search: `{domain} REST API endpoint`
3. **Confirm with user** before executing unknown patterns
4. **Endpoint pattern:** `gh api /repos/{owner}/{repo}/{resource}` or `gh api /{resource}`

---

## Phase 4: EXECUTE

**Goal:** Execute the operation using the appropriate API.

**See:** `lib/github/patterns/graphql-execution.md`
**See:** `lib/github/patterns/error-handling.md`

### Execution Approach

1. **Check routing guide** - `reference/api-routing.md` tells you GraphQL vs REST
2. **If syntax is clear** - Execute directly using `gh api` or `gh` CLI
3. **If uncertain** - Use corpus lookup for exact syntax

### Corpus Lookup (When Needed)

**See:** `lib/github/patterns/corpus-lookup.md`

Use corpus lookup when you need exact syntax:

- **Invoke:** `hiivmind-pulse-gh:hiivmind-corpus-github`
- **Query:** With keywords from routing guide
- **Get:** Exact mutation/endpoint syntax

### Execute Operation

- **GraphQL:** Write query to temp file, execute with `gh api graphql -f query="$(cat /tmp/query.graphql)"`
- **REST:** Use `gh api /repos/{owner}/{repo}/endpoint -X METHOD`
- **CLI shortcut:** Some operations have `gh` CLI equivalents

### Parse Response

- GraphQL: Check `.errors`, extract from `.data`
- REST: Check HTTP status, parse JSON response

---

## Phase 5: REPORT

**Goal:** Report operation result to user.

**See:** `lib/github/patterns/error-handling.md`

### Success Report

```
Operation successful!

{Domain}: {Operation}
Target: {entity}
Result: {summary}

{Link to GitHub if applicable}
```

### Error Report

```
Operation failed.

Error: {error message}
Domain: {domain}
Operation: {operation}

Suggested fix: {based on error-handling.md}
```

---

## Domain-Specific Notes

### Projects v2

**Required IDs:** Project ID, Field ID (for updates), Option ID (for single-select)

**See:** `lib/github/patterns/id-resolution.md` for resolving from config

**Special cases:**
- Status field: Single-select, needs Option ID
- Date fields: ISO 8601 format
- Iteration fields: Use iteration ID from config

### Milestones

**REST only** - No GraphQL mutations available.

**Assign to issue:** Use GraphQL `updateIssue` with `milestoneId`

### Secrets

**Requires encryption** - Must encrypt value with repository public key before setting.

**CLI shortcut:** `gh secret set NAME` handles encryption automatically.

### Actions

**Trigger workflow:** Requires `workflow_dispatch` event configured in workflow file.

**CLI shortcut:** `gh workflow run WORKFLOW` is simpler than REST API.

### Repositories

**Create:** `POST /user/repos` (personal) or `POST /orgs/{org}/repos` (organization)

**BLOCKED operations:** Delete, transfer, archive - see `reference/operation-blocklist.md`

### Collaborators

**Add:** `PUT /repos/{owner}/{repo}/collaborators/{username}` with permission level

**Remove:** `DELETE /repos/{owner}/{repo}/collaborators/{username}`

### Teams

**Requires org admin permissions** - Most team operations need `admin:org` scope.

### Search

**Read-only domain** - No mutations available.

**Endpoint:** `GET /search/issues`, `GET /search/code`, `GET /search/repositories`

### Unknown Domains

**Default approach for unlisted domains:**

1. Use corpus lookup for exact endpoint syntax
2. Default to REST API with repository scope
3. Confirm with user before execution
4. Report any errors with suggested fixes

---

## Quick Reference

### CLI Shortcuts (When Available)

| Operation | CLI Command |
|-----------|-------------|
| Create issue | `gh issue create` |
| Close issue | `gh issue close NUMBER` |
| Create PR | `gh pr create` |
| Merge PR | `gh pr merge NUMBER` |
| Set secret | `gh secret set NAME` |
| Trigger workflow | `gh workflow run WORKFLOW` |
| Create release | `gh release create TAG` |

**Note:** CLI commands handle authentication, pagination, and formatting automatically.

### Related Skills

- **init** - First-time workspace setup
- **refresh** - Update stale config sections
- **gateway** - Intent detection and routing

---

## Pattern Library

All implementation details are in the pattern library:

| Pattern | Purpose |
|---------|---------|
| `lib/github/patterns/config-parsing.md` | Read/write YAML config files |
| `lib/github/patterns/id-resolution.md` | Resolve names to IDs (cache-first) |
| `lib/github/patterns/corpus-lookup.md` | Look up API syntax when uncertain |
| `lib/github/patterns/graphql-execution.md` | Execute queries via temp file |
| `lib/github/patterns/error-handling.md` | Handle API errors |

### References

| Reference | Purpose |
|-----------|---------|
| `reference/api-routing.md` | API routing decisions (useful standalone) |
| `hiivmind-pulse-gh:hiivmind-corpus-github` | GitHub corpus skill for syntax lookup |
