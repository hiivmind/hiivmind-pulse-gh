---
name: hiivmind-pulse-gh
description: >
  GitHub operations with automatic context enrichment. Create issues, merge PRs,
  set milestones, manage projects, trigger workflows, and more across 25 GitHub
  domains. Caches workspace context (project IDs, field configs, milestones) so
  every operation is enriched automatically. Use when: creating issues, closing
  issues, merging PRs, setting milestones, adding labels, managing projects,
  triggering workflows, or any GitHub API operation. Trigger phrases: "create issue",
  "close issue", "merge PR", "set milestone", "add to project", "trigger workflow",
  "GitHub", "gh".
compatibility: Requires gh CLI (authenticated), jq 1.6+, yq 4.0+. Token scopes: repo, read:org, read:project, project.
trigger: "create issue|close issue|merge PR|set milestone|add label|trigger workflow|GitHub|gh|project board|branch protection|create release|manage secrets"
tools: [shell, filesystem]
metadata:
  author: hiivmind
  version: "4.0.0"
  repository: "https://github.com/hiivmind/hiivmind-pulse-gh"
---

# hiivmind-pulse-gh

GitHub operations plugin with automatic context enrichment. Every operation — from creating a simple issue to managing project boards — is enriched with cached workspace context: project IDs, field configurations, milestone mappings, and team labels.

## Why Context Enrichment Matters

| Without this plugin | With this plugin |
|---------------------|------------------|
| `gh issue create` → orphan issue | Issue + auto-link to project + Status set |
| `gh issue close 42` → just closes | Issue closed + project Status → Done |
| Milestone requires ID lookup | Milestone name resolves from cache |
| Labels typed manually | Team labels available from config |

## Prerequisites

- **gh** CLI, authenticated: `gh auth login`
- **jq** 1.6+
- **yq** 4.0+
- Token scopes: `repo`, `read:org`, `read:project`, `project`

Verify: `gh auth status` should show all required scopes.

## Quick Start

### 1. Initialize Workspace

Run the init skill to discover and cache your workspace context:

**See:** `skills/gh-init/SKILL.md`

This creates `.hiivmind/github/config.yaml` with cached IDs for your organization, projects, fields, milestones, and labels.

### 2. Execute Operations

Use the operations skill for any GitHub action:

**See:** `skills/gh-operations/SKILL.md`

The operations skill:
1. Reads cached config from `.hiivmind/github/config.yaml`
2. Consults `lib/references/api-routing.md` for API method selection (GraphQL vs REST)
3. Resolves names to IDs using `lib/patterns/id-resolution.md`
4. Executes with full context enrichment

## Available Skills

| Skill | Path | Purpose |
|-------|------|---------|
| **gh-init** | `skills/gh-init/SKILL.md` | First-time workspace setup, cache project/field IDs |
| **gh-refresh** | `skills/gh-refresh/SKILL.md` | Sync cached config when stale or IDs not found |
| **gh-operations** | `skills/gh-operations/SKILL.md` | Execute any GitHub operation with enrichment |
| **gh-discover** | `skills/gh-discover/SKILL.md` | Explore available operations and domains |
| **gh-workflows** | `skills/gh-workflows/SKILL.md` | Manage event-driven automation workflows |
| **gh-heartbeat** | `skills/gh-heartbeat/SKILL.md` | Session wake-up, process pending work |

## Supported Domains

| Domain | Operations | API |
|--------|-----------|-----|
| **Issues** | create, update, close, comment, label, assign | GraphQL |
| **Pull Requests** | create, merge, review, comment, request reviewers | GraphQL |
| **Projects v2** | add item, update field, archive, view board | GraphQL |
| **Milestones** | create, update, delete, assign to issue/PR | REST + GraphQL |
| **Labels** | create, update, delete, add/remove from items | REST + GraphQL |
| **Branch Protection** | set rules, require reviews, status checks | REST |
| **Rulesets** | create, update, delete | REST |
| **Actions** | trigger workflow, cancel, rerun, list runs | REST |
| **Secrets** | set, delete, list | REST |
| **Variables** | set, update, delete, list | REST |
| **Releases** | create, update, delete, upload assets | REST |
| **Environments** | create, configure, manage | REST |
| **Deploy Keys** | add, remove, list | REST |
| **Webhooks** | create, update, delete, test | REST |
| **Teams** | list, add/remove members, manage permissions | REST |
| **Collaborators** | invite, remove, check permissions | REST |
| **Code Scanning** | list alerts, get details | REST |
| **Dependabot** | list alerts, manage | REST |
| **Pages** | configure, check status | REST |
| **Discussions** | create, comment, manage categories | GraphQL |
| **Packages** | list, delete versions | REST |
| **Codespaces** | create, manage, list | REST |
| **Notifications** | list, mark read | REST |
| **Repository** | settings, topics, visibility | REST |
| **Git Refs** | create/delete branches, tags | REST |

For unlisted domains, the operations skill uses corpus lookup to find the correct API syntax.

## Key Library Files

### Patterns (how to do things)

| File | Purpose |
|------|---------|
| `lib/patterns/config-parsing.md` | Read/write YAML config |
| `lib/patterns/id-resolution.md` | Resolve names to cached IDs |
| `lib/patterns/graphql-execution.md` | Execute GraphQL via temp file |
| `lib/patterns/corpus-lookup.md` | Look up API syntax when uncertain |
| `lib/patterns/error-handling.md` | Handle API errors |
| `lib/patterns/authentication.md` | Verify gh auth and scopes |

### References (what exists)

| File | Purpose |
|------|---------|
| `lib/references/api-routing.md` | GraphQL vs REST decision guide |
| `lib/references/domains/*.md` | Per-domain detailed syntax (25 files) |
| `lib/references/token-permissions.md` | Required token scopes |

## Execution Flow

For any GitHub operation:

```
1. CONFIG        Read .hiivmind/github/config.yaml
2. ROUTE         Consult lib/references/api-routing.md for API choice
3. RESOLVE       Map names → IDs via lib/patterns/id-resolution.md
4. EXECUTE       Run via gh api (GraphQL or REST)
5. ENRICH        Auto-link to project, set status fields
```

## Configuration

The workspace config lives at `.hiivmind/github/config.yaml` and contains:

- **workspace** — org/user login, type, ID
- **projects** — default project, catalog with field IDs and option mappings
- **milestones** — name-to-number mappings
- **labels** — team label definitions
- **cache** — last sync timestamp

Run the refresh skill when config becomes stale or IDs are not found.

## Installation

See `install.md` for per-agent installation instructions.
