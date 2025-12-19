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
/plugin marketplace add hiivmind/hiivmind-pulse-gh

# Install the plugin
/plugin install hiivmind-pulse-gh@hiivmind-pulse-gh
```

Run these commands in Claude Code (not in a terminal).

## Gateway Command

The primary entry point for all GitHub operations:

```
/hiivmind-pulse-gh [describe what you want]
```

### Examples

```
/hiivmind-pulse-gh create issue for login timeout bug
/hiivmind-pulse-gh set milestone v2.0 on issue #42
/hiivmind-pulse-gh add PR to project
/hiivmind-pulse-gh protect main branch with required reviews
/hiivmind-pulse-gh trigger workflow ci.yml
```

### How It Works

1. **Intent Detection** — Parses natural language to determine domain + operation + target
2. **Context Check** — Verifies workspace is initialized (if needed)
3. **Confirmation** — Asks before mutations
4. **Execution** — Routes to appropriate skill with corpus-backed API syntax

### Interactive Menu

Run without arguments for a guided menu:

```
/hiivmind-pulse-gh
```

## Skills

The plugin provides **five skills** with a clear dependency structure:

### Skill Overview

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `hiivmind-pulse-gh-init` | Validate environment, discover org structure, create config.yaml | First-time setup (once per workspace) |
| `hiivmind-pulse-gh-refresh` | Sync cached config with GitHub | Periodically, or when "ID not found" errors occur |
| `hiivmind-pulse-gh-operations` | Execute GitHub operations (all domains) | Via gateway command |
| `hiivmind-corpus-github-docs` | Look up GitHub API syntax (GraphQL/REST) | When uncertain about exact API syntax (external corpus) |
| `hiivmind-pulse-gh-awareness` | Inject skill awareness into CLAUDE.md | Help Claude suggest this plugin proactively |

### Skill Hierarchy

```
hiivmind-pulse-gh-init            ← Run FIRST (creates config.yaml)
       │
       ▼
hiivmind-pulse-gh-operations      ← Requires init completed
hiivmind-pulse-gh-refresh         ← Requires init completed
       │
       ├── hiivmind-corpus-github-docs ← External corpus (syntax lookup)
       │
hiivmind-pulse-gh-awareness       ← Independent (edits CLAUDE.md)
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

> **Note:** This table shows commonly used domains for quick reference. The plugin supports **any GitHub domain** via corpus lookup — if you have permissions, it can help. Some dangerous operations (delete repository, transfer ownership) are blocked for safety. See `docs/operation-blocklist.md`.

## Quick Start

### First-Time Setup

```
You: /hiivmind-pulse-gh create issue for new feature

Claude: This workspace hasn't been initialized for GitHub operations.
        Would you like to initialize now?

You: Yes

Claude: [Runs hiivmind-pulse-gh-init]

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
You: /hiivmind-pulse-gh create issue for authentication timeout

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
# Run /hiivmind-pulse-gh init here

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
│   └── hiivmind-pulse-gh.md              # Gateway command
│
├── skills/
│   ├── hiivmind-pulse-gh-init/           # Workspace initialization
│   ├── hiivmind-pulse-gh-refresh/        # Config sync
│   ├── hiivmind-pulse-gh-operations/     # Execute operations
│   └── hiivmind-pulse-gh-awareness/      # CLAUDE.md injection
│
├── lib/
│   ├── patterns/                         # HOW to do things (executable guides)
│   │   ├── config-parsing.md
│   │   ├── workspace-detection.md
│   │   ├── authentication.md
│   │   ├── tool-detection.md
│   │   ├── id-resolution.md
│   │   ├── graphql-execution.md
│   │   ├── error-handling.md
│   │   └── corpus-lookup.md
│   │
│   └── references/                       # WHAT exists (static lookup data)
│       ├── api-routing.md                # GraphQL vs REST decisions
│       ├── token-permissions.md          # Token permission requirements
│       └── domains/                      # Per-domain API syntax (25 files)
│
├── docs/
│   ├── decisions/                        # Historical architecture decisions
│   ├── config-schema.md                  # Config.yaml schema
│   └── operation-blocklist.md            # Blocked dangerous operations
│
├── templates/
│   ├── config.yaml.template
│   ├── user.yaml.template
│   └── freshness.yaml.template
│
└── # External dependency: hiivmind-corpus-github-docs
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
1. ROUTE   →   2. CORPUS   →   3. EXECUTE
   (API)         (syntax)        (temp file)
     │              │               │
lib/references/ External         gh api graphql
api-routing.md  corpus skill     or gh api REST
                   ↓
               hiivmind-corpus-github-docs
```

1. **Route** — Consult `lib/references/api-routing.md` for GraphQL vs REST decision
2. **Corpus** — If uncertain about syntax, query the external GitHub API corpus
3. **Execute** — Run the operation via `gh api` with temp file for complex queries

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No workspace configuration found" | Run `/hiivmind-pulse-gh` and accept init prompt |
| "Field ID not found" | Run `/hiivmind-pulse-gh refresh` to sync with GitHub |
| "Config is stale" | Run `/hiivmind-pulse-gh refresh` |
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
lib/patterns/*.md                          → Executable patterns (HOW to do things)
lib/references/*.md                        → Static lookup data (WHAT exists)
docs/                                      → Architecture docs, schemas, templates
```

## License

MIT
