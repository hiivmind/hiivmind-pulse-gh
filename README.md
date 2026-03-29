# hiivmind-pulse-gh

A Claude Code plugin for deep GitHub automation — Projects v2, Milestones, Branch Protection, and more.

## The Problem

GitHub's APIs are powerful but painful:
- **GraphQL node IDs** — Every operation needs opaque IDs like `PVT_kwDOBx...`
- **Repeated lookups** — "What's the ID for the Status field? What's the option ID for 'In Progress'?"
- **Context amnesia** — Each Claude session starts fresh, forgetting your org structure

## The Solution

This plugin takes a **discover-once, use-forever** approach:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. DISCOVER                                                     │
│     Init skill inspects your GitHub org structure               │
│     → Projects, fields, options, repositories, milestones       │
│                                                                  │
│  2. CACHE                                                        │
│     Store discovered IDs in .hiivmind/github/config.yaml        │
│     → Committed to git, shared with team                        │
│                                                                  │
│  3. USE                                                          │
│     Gateway command routes to appropriate skill                 │
│     → Natural language intent detection, corpus-backed syntax   │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### 1. Install Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| **gh** | GitHub CLI | [cli.github.com](https://cli.github.com/) |
| **jq** | JSON processing | `apt install jq` / `brew install jq` |
| **yq** | YAML processing | [github.com/mikefarah/yq](https://github.com/mikefarah/yq) |

```bash
# Verify installation
gh auth status && jq --version && yq --version

# Ensure gh has required scopes
gh auth refresh -s read:project -s project -s repo
```

### 2. Install the Plugin

```bash
# Add the marketplace
/plugin marketplace add hiivmind/gh

# Install the plugin
/plugin install hiivmind-pulse-gh@hiivmind-pulse-gh
```

Run these commands in Claude Code (not in a terminal).

## Gateway Command

The primary entry point for all GitHub operations:

```
/gh [describe what you want]
```

### Examples

```
# Execute operations
/gh create issue for login timeout bug
/gh set milestone v2.0 on issue #42
/gh add PR to project
/gh protect main branch with required reviews
/gh trigger workflow ci.yml

# Discover capabilities
/gh discover
/gh what can I do with projects
/gh explore milestones
/gh help
```

### How It Works

1. **Intent Detection** — Parses natural language to determine domain + operation + target
2. **Context Check** — Verifies workspace is initialized (if needed)
3. **Confirmation** — Asks before mutations
4. **Execution** — Routes to appropriate skill with corpus-backed API syntax

### Interactive Menu

Run without arguments for a guided menu:

```
/gh
```

### Discovery Mode

Explore available operations across all 26 GitHub domains:

```
/gh discover
```

**What you get:**

1. **Quick Reference Table** — All domains with their API support (CLI, REST, GraphQL)
2. **Domain Drill-Down** — Select a domain to see its full operation matrix
3. **CLI Commands** — Ready-to-use `gh` commands for each operation
4. **Handoff to Execute** — When ready, seamlessly transition to the operations skill

**Example session:**

```
You: /gh discover

Claude: === GitHub Operations Quick Reference ===

        | Domain          | gh CLI | REST | GraphQL | Notes                    |
        |-----------------|--------|------|---------|--------------------------|
        | Issues          | ✓      | ✓    | ✓       | Full CRUD via all methods|
        | Pull Requests   | ✓      | ✓    | ✓       | Full CRUD via all methods|
        | Projects v2     | ✓      | Read | ✓       | Views UI-only            |
        | Milestones      | ✗      | ✓    | Read    | CRUD via REST            |
        ... [26 domains total]

        Which domain would you like to explore?

You: Projects v2

Claude: === Projects v2 Domain ===

        | Operation        | gh CLI | REST | GraphQL | Notes                   |
        |------------------|--------|------|---------|-------------------------|
        | Add item         | ✓      | ✗    | ✓       | addProjectV2ItemById    |
        | Update field     | ✓      | ✗    | ✓       | updateProjectV2ItemField|
        | Archive item     | ✓      | ✗    | ✓       |                         |
        ...

        CLI Commands:
        | Operation   | Command                                              |
        |-------------|------------------------------------------------------|
        | Add item    | gh project item-add {number} --owner {o} --url {url} |
        | Edit field  | gh project item-edit --id {id} --field-id {f} ...    |

        What would you like to do?
        1. Execute an operation now
        2. Explore another domain
        3. Done
```

## Skills

The plugin provides **seven skills** with a clear dependency structure:

### Skill Overview

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `gh-init` | Validate environment, discover org structure, create config.yaml | First-time setup (once per workspace) |
| `gh-refresh` | Sync cached config with GitHub | Periodically, or when "ID not found" errors occur |
| `gh-operations` | Execute GitHub operations (all domains) | Via gateway command |
| `gh-discover` | Explore available operations across all 26 domains | Find the right operation, learn what's possible |
| `gh-healthcheck` | On-demand governance audit for repository maturity | Evaluate branch protection, CI/CD, docs, security policy, etc. |
| `gh-heartbeat` | Process triggered workflows on session wake-up | Automatically on session start when pending work is detected |
| `gh-workflows` | Manage event-driven workflows for GitHub automation | List, enable, disable, run, or create workflows |
| `hiivmind-corpus-github-docs-navigate` | Look up GitHub API syntax (GraphQL/REST) | When uncertain about exact API syntax (external corpus) |

### Skill Hierarchy

```
gh-init            ← Run FIRST (creates config.yaml)
       │
       ▼
gh-operations      ← Requires init completed
gh-refresh         ← Requires init completed
gh-healthcheck     ← Requires init completed (read-only audit)
       │
       ├── hiivmind-corpus-github-docs-navigate ← External corpus (syntax lookup)
       │
gh-discover        ← Independent (explore capabilities)
gh-workflows       ← Independent (manage automation)
gh-heartbeat       ← Triggered by SessionStart hook
```

## Supported Domains

| Domain | Operations | API |
|--------|------------|-----|
| **Issues** | create, update, close, comment, label | GraphQL |
| **Pull Requests** | create, merge, review, comment | GraphQL |
| **Milestones** | create, update, delete, assign | REST (CRUD), GraphQL (assign) |
| **Labels** | create, update, delete, add/remove | REST (CRUD), GraphQL (assign) |
| **Projects v2** | add item, update field, archive | GraphQL |
| **Branch Protection** | set, update, delete | REST |
| **Rulesets** | create, update, delete | REST |
| **Actions** | trigger, cancel, rerun, list | REST |
| **Secrets** | set, delete, list | REST |
| **Variables** | set, update, delete, list | REST |
| **Releases** | create, update, delete, upload | REST |

> **Note:** This table shows commonly used domains for quick reference. The plugin supports **26 domains** via corpus lookup — if you have permissions, it can help. Some dangerous operations (delete repository, transfer ownership) are blocked for safety. See `lib/references/operation-blocklist.md`.

## Quick Start

### First-Time Setup

```
You: /gh create issue for new feature

Claude: This workspace hasn't been initialized for GitHub operations.
        Would you like to initialize now?

You: Yes

Claude: [Runs gh-init]

        GitHub workspace initialized!
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Workspace: acme-corp (organization)

        Projects cached: 2
          #1 - Engineering Backlog (5 fields)
          #2 - Product Roadmap (7 fields) [default]

        Config saved:
          .hiivmind/github/config.yaml (commit this)

        Now proceeding with your original request...
```

### Daily Usage

```
You: /gh create issue for authentication timeout

Claude: Create issue in acme-corp/api?
        Title: "Authentication timeout"

        Proceed? [Yes / Edit / Cancel]

You: Yes

Claude: Issue #143 created: https://github.com/acme-corp/api/issues/143
```

## Workspace Configuration

### Philosophy

The workspace config separates **shared team knowledge** from **personal user data**:

```
.hiivmind/
└── github/
    ├── config.yaml      # SHARED — commit to git
    │                    # Org structure, project IDs, field mappings
    │
    ├── freshness.yaml   # SHARED — tracks config staleness
    │
    └── user.yaml        # PERSONAL — add to .gitignore
                         # Your identity, cached permissions
```

### What Gets Cached

**config.yaml** (shared):
```yaml
workspace:
  type: organization
  login: acme-corp
  id: O_kgDOxxxxxxx

projects:
  default: 2
  catalog:
    - number: 2
      id: PVT_kwDOxxxxxxx
      title: Product Roadmap
      fields:
        Status:
          id: PVTSSF_xxxxxxx
          options:
            Backlog: PVTSSFO_xxx1
            In Progress: PVTSSFO_xxx2
            Done: PVTSSFO_xxx3

cache:
  last_synced_at: "2025-12-08T22:05:29Z"
```

### Multi-Repository Setup

For organizations with multiple repos, use symlinks to share config:

```bash
# Create centralized config
mkdir -p ~/github-workspaces/acme-corp
cd ~/github-workspaces/acme-corp
# Run /gh init here

# Symlink from each repository
cd ~/projects/api
ln -s ~/github-workspaces/acme-corp .hiivmind

cd ~/projects/frontend
ln -s ~/github-workspaces/acme-corp .hiivmind
```

## Architecture

```
hiivmind-pulse-gh/
├── .claude-plugin/
│   └── plugin.json                       # Plugin manifest
│
├── commands/
│   ├── gh.md                             # Gateway command
│   └── intent-mapping.yaml               # Intent detection rules
│
├── skills/
│   ├── gh-init/           # Workspace initialization
│   ├── gh-refresh/        # Config sync
│   ├── gh-operations/     # Execute operations
│   ├── gh-discover/       # Explore capabilities
│   ├── gh-healthcheck/    # Repository governance audit
│   ├── gh-heartbeat/      # Session wake-up handler
│   └── gh-workflows/      # Workflow management
│
├── hooks/
│   ├── hooks.json                        # Hook configuration
│   ├── heartbeat.sh                      # Heartbeat polling logic
│   ├── post-operation-check.sh           # Post-operation validation
│   └── validate-gh-operation.sh          # Operation validation
│
├── lib/
│   ├── patterns/                         # HOW to do things (executable guides)
│   │   ├── authentication.md
│   │   ├── config-parsing.md
│   │   ├── corpus-lookup.md
│   │   ├── error-handling.md             # Error handling overview
│   │   ├── error-auth.md                 # Auth-specific errors
│   │   ├── error-graphql.md              # GraphQL-specific errors
│   │   ├── error-rest.md                 # REST-specific errors
│   │   ├── error-local.md                # Local/tool errors
│   │   ├── graphql-execution.md
│   │   ├── graphql-queries.md
│   │   ├── healthcheck-evaluation.md
│   │   ├── id-resolution.md
│   │   ├── poll-state.md
│   │   ├── tool-detection.md
│   │   ├── workflow-execution.md
│   │   └── workspace-detection.md
│   │
│   └── references/                       # WHAT exists (static lookup data)
│       ├── api-routing.md                # GraphQL vs REST decisions
│       ├── config-schema.md              # Config file schema
│       ├── healthcheck-checks.md         # Healthcheck check catalog
│       ├── operation-blocklist.md        # Blocked dangerous operations
│       ├── token-permissions.md          # Token permission requirements
│       ├── workflow-triggers.md          # Workflow trigger events
│       └── domains/                      # Per-domain API syntax (26 files)
│
├── docs/
│   └── quickstart.md                     # Quick start guide
│
├── templates/
│   ├── config.yaml.template
│   ├── freshness.yaml.template
│   ├── healthcheck.yaml.template
│   ├── user.yaml.template
│   ├── repo.yaml.template
│   ├── teams.yaml.template
│   ├── views.yaml.template
│   ├── relationships.yaml.template
│   ├── automations.yaml.template
│   ├── poll-state.yaml.template
│   ├── workflow.yaml.template
│   ├── gitignore.template
│   └── workflows/                        # 10 pre-built workflow templates
│       ├── auto-refresh.yaml
│       ├── ci-monitor.yaml
│       ├── issue-triage.yaml
│       ├── pr-lifecycle.yaml
│       └── ...
│
└── # External dependency: hiivmind-corpus-github
```

### Design Principles

1. **Skills over MCP** — Load on-demand, not all upfront. Better context efficiency.
2. **Pattern library** — Reusable markdown patterns, not embedded shell scripts.
3. **Corpus lookup** — Just-in-time API syntax from bundled documentation.
4. **Cache structure, not data** — IDs are stable; item data changes constantly.
5. **Shared config, personal permissions** — Team collaborates; permissions are individual.
6. **Graceful degradation** — Works without config (explicit params required).

### How Operations Work

```
1. ROUTE       →   2. RESOLVE   →   3. EXECUTE
   (API choice)      (IDs)           (run)
     │                 │                │
lib/references/    config.yaml      gh api graphql
api-routing.md     cache            or gh api REST
                     │
                  corpus (if uncertain about syntax)
```

1. **Route** — Consult `lib/references/api-routing.md` for GraphQL vs REST decision
2. **Resolve** — Get IDs from cached config; if uncertain about syntax, query the external GitHub API corpus
3. **Execute** — Run the operation via `gh api` with temp file for complex queries

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No workspace configuration found" | Run `/hiivmind-pulse-gh` and accept init prompt |
| "Field ID not found" | Run `/gh refresh` to sync with GitHub |
| "Config is stale" | Run `/gh refresh` |
| `gh: command not found` | Install GitHub CLI: [cli.github.com](https://cli.github.com/) |
| `yq: command not found` | Install yq v4+: [github.com/mikefarah/yq](https://github.com/mikefarah/yq) |
| Permission errors | `gh auth refresh -s read:project -s project -s repo` |
| "Resource not accessible" | Check access: `gh repo view owner/repo` |

## Limitations

- **Claude Code only** — This is a Claude Code plugin (skills), not an MCP server. Won't work with VS Code Copilot, Cursor, or other LLM tools.
- **Requires local tools** — `gh`, `jq`, `yq` must be installed on the machine where Claude Code runs.
- **Inherits gh permissions** — Can only access what your `gh` CLI can access. No elevation, no bypass.

## Testing

Tests are maintained in a separate repository to keep the plugin installation lean:

**[hiivmind-pulse-gh-tests](https://github.com/hiivmind/hiivmind-pulse-gh-tests)**

```bash
# Clone test repo
git clone https://github.com/hiivmind/hiivmind-pulse-gh-tests.git
cd hiivmind-pulse-gh-tests

# Setup (clones this repo + installs deps)
./scripts/setup.sh

# Run tests
./node_modules/.bin/bats e2e/smoke/   # Quick smoke tests
./node_modules/.bin/bats unit/        # Full unit tests
./node_modules/.bin/bats integration/ # Integration tests
```

## Contributing

```
commands/*.md                              → Gateway and slash commands
skills/*/SKILL.md                          → Skill documentation
hooks/                                     → Event-driven hook scripts
lib/patterns/*.md                          → Executable patterns (HOW to do things)
lib/references/*.md                        → Static lookup data (WHAT exists)
templates/                                 → Config and workflow templates
docs/                                      → Quick start and documentation
```

## License

MIT
