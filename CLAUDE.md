# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## System Overview

This is **hiivmind-pulse-gh** - a Claude Code plugin for GitHub API operations. It provides:

- **Workspace initialization** - Cache project/repo IDs to config.yaml
- **API routing guide** - Which API (GraphQL vs REST) for each operation
- **Documentation corpus** - Keyword-tagged GitHub API docs for JIT lookup
- **Workflow examples** - Multi-step patterns for common operations

## Getting Started

### First Time Setup

Run `hiivmind-pulse-gh-init` to initialize your workspace. This:
1. Verifies CLI tools (gh, jq, yq)
2. Validates GitHub authentication
3. Discovers projects and caches field IDs
4. Creates `.hiivmind/github/config.yaml`

### After Initialization

Once initialized, use `gh` CLI directly with cached context:

```bash
# 1. Load context
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT=$(yq '.projects.default' "$CONFIG")

# 2. Check routing guide for which API
#    → reference/api-routing.md

# 3. Search corpus for syntax
#    → Use keywords from routing guide

# 4. Execute with gh
gh issue create -R "$OWNER/repo" --title "..."
gh project item-add "$PROJECT" --owner "$OWNER" --url "..."
```

---

## Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `hiivmind-pulse-gh-init` | Initialize workspace | First time setup per repo |
| `hiivmind-pulse-gh-refresh` | Sync config with GitHub | When config is stale |

**After init, you don't need specialized skills.** Use `gh` directly with:
- Config for cached IDs
- Routing guide for API decisions
- Corpus for exact syntax

---

## Reference Documentation

| Document | Purpose |
|----------|---------|
| `reference/api-routing.md` | Which API (GraphQL vs REST) for each operation |
| `reference/config-schema.md` | How to read and use config.yaml |
| `reference/workflows/` | Multi-step workflow examples |

### Workflow Examples

| File | Operations |
|------|------------|
| `issue-to-project.md` | Create issue, add to project, set status |
| `manage-milestones.md` | Milestone CRUD, assign to issues |
| `setup-branch-protection.md` | Branch protection + rulesets |
| `project-status-update.md` | Update fields, project status |
| `bulk-operations.md` | Batch operations with rate limiting |

---

## GitHub Documentation Corpus

Embedded at `.claude-plugin/skills/hiivmind-corpus-github/` with specialized GitHub API docs.

### Usage Flow

1. **Check routing:** `reference/api-routing.md` → which API
2. **Search corpus:** Use keywords from routing guide
3. **Get syntax:** Corpus points to exact documentation

### Keyword Lookup

Search the corpus index using keywords:

| Domain | Keywords |
|--------|----------|
| Issues | `createIssue`, `updateIssue`, `closeIssue`, `subjectId` |
| PRs | `createPullRequest`, `mergePullRequest`, `requestReviews` |
| Projects v2 | `addProjectV2ItemById`, `updateProjectV2ItemFieldValue`, `createProjectV2StatusUpdate` |
| Milestones | `milestones`, `due_on`, `milestoneId` (REST for CRUD) |
| Labels | `addLabelsToLabelable`, `removeLabelsFromLabelable`, `labelIds` |
| Branch Protection | `required_status_checks`, `enforce_admins` (REST) |
| Rulesets | `rulesets`, `enforcement`, `conditions` (REST) |
| Actions | `workflows`, `runs`, `dispatches`, `cancel`, `rerun` |
| Secrets | `secrets`, `encrypted_value`, `public-key` |
| Variables | `variables`, `visibility` |
| Releases | `releases`, `tag_name`, `assets`, `generate-notes` |

### GraphQL Schema Search

For type definitions and mutations (70k+ line schema):

```bash
# Find type
grep -n "^type ProjectV2 " .claude-plugin/skills/hiivmind-corpus-github/data/uploads/graphql-schema/schema.docs.graphql -A 50

# Find mutation
grep -n "createProjectV2StatusUpdate" .claude-plugin/skills/hiivmind-corpus-github/data/uploads/graphql-schema/schema.docs.graphql -B 5 -A 30
```

---

## File Structure

```
hiivmind-pulse-gh/
├── .claude-plugin/
│   ├── plugin.json
│   └── skills/hiivmind-corpus-github/    # Embedded corpus
├── skills/
│   ├── hiivmind-pulse-gh-init/           # Workspace initialization
│   └── hiivmind-pulse-gh-refresh/        # Config sync
├── reference/
│   ├── api-routing.md                    # API routing decisions
│   ├── config-schema.md                  # Config.yaml schema
│   └── workflows/                        # Multi-step examples
├── templates/
│   ├── config.yaml.template
│   └── user.yaml.template
├── _deprecated/github/                   # Legacy bash functions (reference only)
└── docs/
    ├── v3-migration-plan.md
    └── architecture-v3-proposal.md
```

---

## Dependencies

- **gh** - GitHub CLI, authenticated with scopes: `repo`, `read:org`, `read:project`, `project`
- **jq** (1.6+) - JSON processing
- **yq** (4.0+) - YAML processing

Run `hiivmind-pulse-gh-init` to verify all dependencies.

---

## Function Libraries (Reference Only)

The `_deprecated/github/` directory contains bash function implementations from v2 architecture. These are **reference only** - not required for v3 operations.

For v3, use:
- `reference/api-routing.md` for API decisions
- Corpus keywords for exact syntax
- `gh api` or `gh` commands directly

---

## Plugin Development Resources

When working on plugin structure, use the `plugin-dev` skills:

| Skill | Use When |
|-------|----------|
| `plugin-dev:plugin-structure` | Plugin manifest, directory layout |
| `plugin-dev:skill-development` | Writing SKILL.md files |
| `plugin-dev:command-development` | Slash commands |
| `plugin-dev:hook-development` | Event hooks |
| `plugin-dev:mcp-integration` | MCP server configuration |
