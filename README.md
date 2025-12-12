# hiivmind-pulse-gh

A Claude Code plugin for deep GitHub automation — Projects v2, Milestones, Branch Protection, and more.

## The Problem

GitHub's APIs are powerful but painful:
- **GraphQL node IDs** — Every operation needs opaque IDs like `PVT_kwDOBx...`
- **Repeated lookups** — "What's the ID for the Status field? What's the option ID for 'In Progress'?"
- **Context amnesia** — Each Claude session starts fresh, forgetting your org structure

## The Solution

This toolkit takes a **discover-once, use-forever** approach:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. DISCOVER                                                     │
│     Meta-skills inspect your GitHub org structure               │
│     → Projects, fields, options, repositories, milestones       │
│                                                                  │
│  2. CACHE                                                        │
│     Store discovered IDs in .hiivmind/github/config.yaml        │
│     → Committed to git, shared with team                        │
│                                                                  │
│  3. USE                                                          │
│     Operational skills read cached config                       │
│     → No repeated lookups, simplified commands                  │
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

## Skills

The toolkit provides **seven skills** with a clear dependency hierarchy:

### Skill Hierarchy

```
hiivmind-pulse-gh-user-init          ← Run FIRST (validates env, creates user.yaml)
       │
       ▼
hiivmind-pulse-gh-workspace-init     ← Run SECOND (discovers org, creates config.yaml)
       │
       ▼
All other skills                     ← Require both init skills completed
```

### Setup & Maintenance

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `hiivmind-pulse-gh-user-init` | Validate gh CLI, auth, deps; persist user identity | First-time setup (run once globally) |
| `hiivmind-pulse-gh-workspace-init` | Create config, discover projects, cache IDs | First-time setup (once per repo) |
| `hiivmind-pulse-gh-workspace-refresh` | Sync structural metadata with GitHub | Periodically, or when "ID not found" errors occur |

### Investigation

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `hiivmind-pulse-gh-investigate` | Deep-dive into issues, PRs, project items | "What's the full story on #42?", standup prep, audits |

### Operations

| Skill | Coverage | Example Prompts |
|-------|----------|-----------------|
| `hiivmind-pulse-gh-projects` | Projects v2, items, fields, status updates, views | "Show items assigned to @alice", "Is this repo linked to a project?" |
| `hiivmind-pulse-gh-milestones` | Repository milestones, issue/PR assignment | "Create a v2.0 milestone for the api repo" |
| `hiivmind-pulse-gh-branch-protection` | Branch rules, rulesets, naming conventions | "Protect main with required reviews" |

## Quick Start

### First-Time Setup

**Step 1: User Init** (run once globally)
```
You: Set up my GitHub environment

Claude: [Runs hiivmind-pulse-gh-user-init]

        === hiivmind-pulse-gh User Setup ===

        GitHub CLI (gh): gh version 2.40.0
        jq: jq-1.7
        yq: yq v4.40.5
        GitHub auth: Logged in as your-username
        Token scopes: 'read:org', 'read:project', 'repo', 'project'
        Projects v2 access: OK

        Fetching user identity...
          Login: your-username
          ID: U_kgDOxxxxxxx

        User setup complete!
        Created: .hiivmind/github/user.yaml
```

**Step 2: Workspace Init** (run once per repo)
```
You: Set up GitHub workspace for my current project

Claude: [Runs hiivmind-pulse-gh-workspace-init]

        GitHub workspace initialized!
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Workspace: acme-corp (organization)

        Projects cached: 2
          #1 - Engineering Backlog (5 fields)
          #2 - Product Roadmap (7 fields) [default]

        Repositories cached: 3
          acme-corp/api (2 milestones)
          acme-corp/frontend (1 milestone)

        Config saved:
          .hiivmind/github/config.yaml (commit this)
          .hiivmind/github/user.yaml (enriched with permissions)
```

### Daily Usage

```
You: Show me in-progress items in the roadmap project

Claude: [Uses cached org/project context]
        Found 12 items with status "In Progress"...

You: What's the full story on issue #42?

Claude: [Runs hiivmind-pulse-gh-investigate]

        Issue #42: "Fix authentication timeout"
        ├── Status: In Progress | Assignee: @alice
        ├── Milestone: v2.1.0 (due Jan 15)
        ├── Comments: 5 (last: @bob, 2 hours ago)
        └── Linked PR: #87 "Add retry logic" (draft, CI passing)
```

## Workspace Configuration

### Philosophy

The workspace config separates **shared team knowledge** from **personal user data**:

```
.hiivmind/
└── github/
    ├── config.yaml    # SHARED — commit to git
    │                  # Org structure, project IDs, field mappings
    │
    └── user.yaml      # PERSONAL — add to .gitignore
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

repositories:
  - name: api
    id: R_kgDOxxxxxxx
    default_branch: main

milestones:
  api:
    - number: 1
      title: v1.0.0
      id: MI_xxxxxxx
```

**user.yaml** (personal - created by user-init, enriched by workspace-init):
```yaml
user:                           # ← Created by user-init
  login: your-username
  id: U_kgDOxxxxxxx

permissions:                    # ← Added by workspace-init
  org_role: member
  project_roles:
    2: admin
  repo_roles:
    api: maintain
```

### Multi-Repository Setup

For organizations with multiple repos, use symlinks to share config:

```bash
# Create centralized config
mkdir -p ~/github-workspaces/acme-corp
cd ~/github-workspaces/acme-corp
# Run hiivmind-pulse-gh-workspace-init here

# Symlink from each repository
cd ~/projects/api
ln -s ~/github-workspaces/acme-corp .hiivmind

cd ~/projects/frontend
ln -s ~/github-workspaces/acme-corp .hiivmind
```

## Architecture

```
hiivmind-pulse-gh/
├── skills/
│   ├── hiivmind-pulse-gh-user-init/           # Setup: validate env, create user.yaml
│   ├── hiivmind-pulse-gh-workspace-init/      # Setup: discover structure, create config.yaml
│   ├── hiivmind-pulse-gh-workspace-refresh/   # Maintenance: sync structural metadata
│   ├── hiivmind-pulse-gh-investigate/         # Investigation: deep-dive into entities
│   ├── hiivmind-pulse-gh-projects/            # Operations: Projects v2
│   ├── hiivmind-pulse-gh-milestones/          # Operations: Milestones
│   └── hiivmind-pulse-gh-branch-protection/   # Operations: Branch rules
│
├── templates/                      # Config file templates
│   ├── config.yaml.template
│   ├── user.yaml.template
│   └── gitignore.template
│
├── lib/github/
│   ├── gh-project-functions.sh     # ~95 shell functions
│   ├── gh-project-graphql-queries.yaml
│   ├── gh-project-jq-filters.yaml
│   ├── gh-rest-functions.sh
│   └── gh-branch-protection-templates.yaml
│
└── docs/
    └── meta-skill-architecture.md  # Detailed design docs
```

### Design Principles

1. **Skills over MCP** — Load on-demand, not all upfront. Better context efficiency.
2. **Shell functions over API wrappers** — Composable pipelines, Unix philosophy.
3. **Cache structure, not data** — IDs are stable; item data changes constantly.
4. **Shared config, personal permissions** — Team collaborates; permissions are individual.
5. **Graceful degradation** — Works without config (explicit params required).

## Function Reference

### Projects v2 (GraphQL)

```bash
# Fetch and filter
fetch_org_project 2 "acme" | apply_assignee_filter "alice"
fetch_org_project 2 "acme" | apply_status_filter "In Progress"
fetch_org_project 2 "acme" | list_repositories

# Status updates
create_status_update "PVT_xxx" "ON_TRACK" "Sprint on schedule"
get_latest_status_update "PVT_xxx"

# Views
fetch_project_views "PVT_xxx"
create_project_view "PVT_xxx" "Sprint Board" "BOARD"

# Field updates (with cached IDs)
update_item_single_select "$PROJECT_ID" "$ITEM_ID" "$FIELD_ID" "$OPTION_ID"
```

### Milestones (GraphQL + REST)

```bash
# Query
list_milestones "acme" "api" | format_milestones
get_milestone_progress "acme" "api" 3

# Create/manage (REST)
create_milestone "acme" "api" "v2.0" "Q1 Release" "2025-03-31"
close_milestone "acme" "api" 3

# Assign to issues (GraphQL)
set_issue_milestone "$ISSUE_ID" "$MILESTONE_ID"
```

### Branch Protection (REST)

```bash
# Smart templates (auto-detect org vs personal)
apply_main_branch_protection "acme" "api"
apply_develop_branch_protection "acme" "api"

# Rulesets (org repos only)
apply_branch_naming_ruleset "acme" "api"
list_rulesets "acme" "api" | format_rulesets
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No workspace configuration found" | Run `hiivmind-pulse-gh-workspace-init` |
| "Field ID not found" | Run `hiivmind-pulse-gh-workspace-refresh` to sync with GitHub |
| `gh: command not found` | Install GitHub CLI: [cli.github.com](https://cli.github.com/) |
| `yq: command not found` | Install yq v4+: [github.com/mikefarah/yq](https://github.com/mikefarah/yq) |
| Permission errors | `gh auth refresh -s read:project -s project -s repo` |
| "Resource not accessible" | Check access: `gh repo view owner/repo` |

## Limitations

- **Claude Code only** — This is a Claude Code plugin (skills), not an MCP server. Won't work with VS Code Copilot, Cursor, or other LLM tools.
- **Requires local tools** — `gh`, `jq`, `yq` must be installed on the machine where Claude Code runs.
- **Inherits gh permissions** — Can only access what your `gh` CLI can access. No elevation, no bypass.
- **No destructive operations** — Delete operations (delete project, delete ruleset) intentionally excluded for safety.

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

For local development, point tests at your local checkout:
```bash
export MAIN_REPO_PATH=/path/to/your/hiivmind-pulse-gh
./node_modules/.bin/bats unit/
```

## Contributing

```
skills/*/SKILL.md                → Skill documentation
lib/github/*-functions.sh        → Shell function implementations
lib/github/*.yaml                → GraphQL queries, jq filters, templates
docs/                            → Architecture and design docs
```

## License

MIT
