# GitHub API Routing Guide

> **Purpose:** Quick reference for which API (GraphQL vs REST) to use for each domain.
> **Standalone:** This guide is useful on its own - you do not need corpus lookup for every operation.
> **When uncertain:** If you need exact syntax, use `lib/examples/operations/corpus-lookup.md`

---

## Quick Reference

**Legend:** ✓ = Supported | ✗ = Not available | ⊗ = Blocked for safety | See domain files for CLI commands

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

For detailed operation tables, CLI commands, and corpus lookup keywords, see the domain-specific files:

| Domain | File |
|--------|------|
| Issues | `domains/issues.md` |
| Pull Requests | `domains/pull-requests.md` |
| Milestones | `domains/milestones.md` |
| Labels | `domains/labels.md` |
| Projects v2 | `domains/projects-v2.md` |
| Branch Protection | `domains/branch-protection.md` |
| Rulesets | `domains/rulesets.md` |
| Actions | `domains/actions.md` |
| Secrets | `domains/secrets.md` |
| Variables | `domains/variables.md` |
| Releases | `domains/releases.md` |
| Repository | `domains/repository.md` |
| Gists | `domains/gists.md` |
| Search | `domains/search.md` |
| Collaborators | `domains/collaborators.md` |
| Teams | `domains/teams.md` |
| Webhooks | `domains/webhooks.md` |
| Checks | `domains/checks.md` |
| Deployments | `domains/deployments.md` |
| Environments | `domains/environments.md` |
| Dependabot | `domains/dependabot.md` |
| Code Scanning | `domains/code-scanning.md` |
| Secret Scanning | `domains/secret-scanning.md` |
| Notifications | `domains/notifications.md` |
| Reactions | `domains/reactions.md` |

Each domain file contains:
- **Support matrix table** - Operations × 4 methods (✓/✗/⊗)
- **CLI command reference** - Exact `gh` commands
- **Corpus lookup guide** - REST endpoints and GraphQL mutations/queries

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

1. **Identify operation** from quick reference table above
2. **Read domain file** for detailed support matrix and keywords
3. **Search corpus** using keywords from domain file:
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
