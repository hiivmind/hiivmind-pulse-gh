# hiivmind-github-skills

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
/plugin marketplace add hiivmind/hiivmind-github-skills

# Install the plugin
/plugin install hiivmind-github-skills@hiivmind-github-skills
```

Run these commands in Claude Code (not in a terminal).

## Skills

The toolkit provides **six skills** in two categories:

### Meta-Skills (Setup & Maintenance)

These skills discover your GitHub structure and cache it locally:

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `hiivmind-github-workspace-init` | Create `.hiivmind/github/` config structure | First-time setup in a repository |
| `hiivmind-github-workspace-analyze` | Discover projects, fields, repos, cache IDs | After init, or when structure changes |
| `hiivmind-github-workspace-refresh` | Sync cached config with GitHub state | Periodically, or when operations fail |

### Operational Skills (GitHub Operations)

These skills perform GitHub operations, using cached config when available:

| Skill | Coverage | Example Prompts |
|-------|----------|-----------------|
| `hiivmind-github-projects` | Projects v2, items, fields, status updates, views | "Show project items assigned to @alice", "Is this repo linked to a project?" |
| `hiivmind-github-milestones` | Repository milestones, issue/PR assignment | "Create a v2.0 milestone for the api repo" |
| `hiivmind-github-branch-protection` | Branch rules, rulesets, naming conventions | "Protect main with required reviews" |

## Quick Start

### First-Time Setup

```
You: Set up GitHub workspace for my current project

Claude: I'll initialize the workspace configuration.
        [Runs hiivmind-github-workspace-init]

        Created .hiivmind/github/config.yaml
        Workspace: acme-corp (organization)

        Now discovering projects and caching structure...
        [Runs hiivmind-github-workspace-analyze]

        Cached:
        - 2 projects (Engineering Backlog, Product Roadmap)
        - 15 fields with option IDs
        - 5 repositories with milestones

        Add to .gitignore: .hiivmind/github/user.yaml
```

### Daily Usage

```
You: Show me in-progress items in the roadmap project

Claude: [Uses cached org/project context]
        Found 12 items with status "In Progress"...

You: Move issue #42 to "In Review"

Claude: [Uses cached Status field ID and "In Review" option ID]
        Updated issue #42 status to "In Review"
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

**user.yaml** (personal):
```yaml
user:
  login: your-username
  id: U_kgDOxxxxxxx

permissions:
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
# Run hiivmind-github-workspace-init and hiivmind-github-workspace-analyze here

# Symlink from each repository
cd ~/projects/api
ln -s ~/github-workspaces/acme-corp .hiivmind

cd ~/projects/frontend
ln -s ~/github-workspaces/acme-corp .hiivmind
```

## Architecture

```
hiivmind-github-skills/
├── skills/
│   ├── github-workspace-init/      # Meta: create config structure
│   ├── github-workspace-analyze/   # Meta: discover and cache
│   ├── github-workspace-refresh/   # Meta: sync with GitHub
│   ├── github-projects/            # Ops: Projects v2
│   ├── github-milestones/          # Ops: Milestones
│   └── github-branch-protection/   # Ops: Branch rules
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
| "No workspace configuration found" | Run `hiivmind-github-workspace-init` then `hiivmind-github-workspace-analyze` |
| "Field ID not found" | Run `hiivmind-github-workspace-refresh` to sync with GitHub |
| `gh: command not found` | Install GitHub CLI: [cli.github.com](https://cli.github.com/) |
| `yq: command not found` | Install yq v4+: [github.com/mikefarah/yq](https://github.com/mikefarah/yq) |
| Permission errors | `gh auth refresh -s read:project -s project -s repo` |
| "Resource not accessible" | Check access: `gh repo view owner/repo` |

## Limitations

- **Claude Code only** — This is a Claude Code plugin (skills), not an MCP server. Won't work with VS Code Copilot, Cursor, or other LLM tools.
- **Requires local tools** — `gh`, `jq`, `yq` must be installed on the machine where Claude Code runs.
- **Inherits gh permissions** — Can only access what your `gh` CLI can access. No elevation, no bypass.
- **No destructive operations** — Delete operations (delete project, delete ruleset) intentionally excluded for safety.

## Contributing

```
skills/*/SKILL.md                → Skill documentation
lib/github/*-functions.sh        → Shell function implementations
lib/github/*.yaml                → GraphQL queries, jq filters, templates
docs/                            → Architecture and design docs
```

## License

MIT
