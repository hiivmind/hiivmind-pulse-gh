# GitHub CLI Toolkit

A Claude Code plugin providing deep GitHub Projects v2 automation through structured wrappers around the GitHub CLI (`gh`).

## What This Is

This toolkit provides **shell functions that wrap `gh` CLI commands** — giving Claude the ability to perform complex GitHub operations through your already-authenticated GitHub CLI installation.

```
┌─────────────────────────────────────────────────┐
│  Claude Code                                    │
│  └─► Skill (loads on demand)                    │
│      └─► Shell functions                        │
│          └─► gh CLI (your existing auth)        │
│              └─► GitHub API                     │
└─────────────────────────────────────────────────┘
```

**This is deliberately NOT an MCP server.** The design prioritizes:

- **Context efficiency** — Skills load on-demand. Unlike MCP servers that expose all tools upfront, Claude only loads what it needs.
- **Zero authentication overhead** — Inherits your existing `gh` CLI authentication. No tokens to configure, no OAuth flows, no secrets management.
- **Composability** — Pipeline-based functions that work with standard Unix tools and existing scripts.
- **Simplicity** — No server process, no transport layer. Just shell functions calling `gh`.

## What You Get

Deep coverage of GitHub features that are underserved by other tools:

| Feature | Coverage | Why It Matters |
|---------|----------|----------------|
| **GitHub Projects v2** | ~95 functions | Most tools have minimal Projects v2 support |
| **Milestones** | Full lifecycle | GraphQL queries + REST mutations |
| **Branch Protection** | Legacy + Rulesets | Both APIs with smart templates |
| **REST API** | Foundation layer | Extensible for other operations |

## Prerequisites

**Required tools must be installed and working before using this plugin:**

| Tool | Purpose | Install | Verify |
|------|---------|---------|--------|
| **gh** | GitHub CLI (authenticated) | [cli.github.com](https://cli.github.com/) | `gh auth status` |
| **jq** | JSON processing (1.6+) | `apt install jq` / `brew install jq` | `jq --version` |
| **yq** | YAML processing (4.0+) | [github.com/mikefarah/yq](https://github.com/mikefarah/yq) | `yq --version` |

```bash
# Quick verification
gh auth status && jq --version && yq --version
```

### GitHub CLI Authentication

Your `gh` CLI must be authenticated with sufficient scopes:

```bash
# Check current auth
gh auth status

# Add required scopes if needed
gh auth refresh -s read:project -s project -s repo
```

## Limitations

- **Claude Code only** — This is a Claude Code plugin, not an MCP server. It won't work with VS Code Copilot, Cursor, or other LLM tools.
- **Requires local tools** — `gh`, `jq`, and `yq` must be installed on the machine where Claude Code runs.
- **Inherits gh permissions** — Can only access what your `gh` CLI can access. No elevation, no bypass.
- **No deletion operations** — Destructive operations (delete project, delete ruleset) are intentionally excluded for safety.

## Installation

```bash
# Install the plugin
claude plugin add https://github.com/hiivmind/hiivmind-github-projects
```

## Skills

This plugin provides four skills that Claude invokes on-demand:

| Skill | Trigger Examples |
|-------|------------------|
| `github-projects` | "Show me project 2", "Filter by assignee", "Create a status update" |
| `github-milestones` | "List milestones", "Set milestone on issue #42", "Create v2.0 milestone" |
| `github-branch-protection` | "Protect main branch", "Set up branch naming rules", "List rulesets" |

Skills load only when needed — Claude doesn't carry the full function library in context until you ask for something relevant.

## Usage

Once installed, ask Claude about your GitHub resources in natural language:

```
> What projects do I have in acme-org?
> Show me all in-progress items assigned to @john in project 2
> Create a status update for the project saying we're on track for the release
> List open milestones for acme/api-server
> Protect the main branch with required reviews
```

## Direct Shell Usage

The functions can also be used directly in scripts or terminals:

```bash
# Source the functions
source lib/github/gh-project-functions.sh
source lib/github/gh-rest-functions.sh

# Pipeline pattern: fetch | filter | format
fetch_org_project 2 "acme-corp" | apply_assignee_filter "john"
fetch_org_project 2 "acme-corp" | list_repositories

# Milestones
list_milestones "acme" "api" | format_milestones
create_milestone "acme" "api" "v2.0" "Q1 Release" "2025-03-31"

# Branch Protection (auto-detects org vs personal repo)
apply_main_branch_protection "acme" "api"
apply_branch_naming_ruleset "acme" "api"
```

## Key Capabilities

### Projects v2 (GraphQL)
- Fetch and filter project items by assignee, status, repository, priority
- Status updates (ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, INACTIVE)
- View management (TABLE, BOARD, ROADMAP)
- Field management and single-select options
- Repository linking
- Pagination with auto-fetch variants

### Milestones (Mixed GraphQL/REST)
- Query via GraphQL, create/update/close via REST
- Set milestones on issues and PRs
- Progress tracking

### Branch Protection (REST)
- Per-branch protection rules with preset templates
- Repository rulesets for pattern-based protection (`feature/*`, `release/*`)
- Auto-detection of org vs personal repository differences

## Architecture

```
lib/github/
├── gh-project-functions.sh          # Shell functions (pipeable)
├── gh-project-graphql-queries.yaml  # GraphQL query templates
├── gh-project-jq-filters.yaml       # jq filter templates
├── gh-rest-functions.sh             # REST wrapper functions
├── gh-rest-endpoints.yaml           # REST endpoint documentation
└── gh-branch-protection-templates.yaml  # Protection presets
```

Functions follow a pipeline pattern — they read JSON from stdin and write to stdout:

```bash
fetch_org_project 2 "org" | apply_status_filter "In Progress" | list_assignees
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `gh: command not found` | Install GitHub CLI: [cli.github.com](https://cli.github.com/) |
| `yq: command not found` | Install yq v4+: [github.com/mikefarah/yq](https://github.com/mikefarah/yq) |
| `jq: command not found` | `apt install jq` or `brew install jq` |
| Permission/scope errors | `gh auth refresh -s read:project -s project -s repo` |
| "Resource not accessible" | Check you have access to the org/repo via `gh repo view owner/repo` |

## Contributing

```
lib/github/gh-project-*.yaml     → GraphQL queries and jq filters
lib/github/gh-*-functions.sh     → Shell function implementations
lib/github/gh-rest-*.yaml        → REST endpoints and templates
skills/*/SKILL.md                → Skill documentation
```

## License

MIT
