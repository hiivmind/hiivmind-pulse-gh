# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## System Overview

This is **hiivmind-pulse-gh** - a Claude Code plugin for GitHub API operations. It provides:

- **Gateway command** - Single entry point for all GitHub operations
- **Workspace initialization** - Cache project/repo IDs to config.yaml
- **Operations execution** - All domains: issues, PRs, milestones, projects, protection, actions, releases
- **API routing** - Automatic GraphQL vs REST selection
- **Documentation corpus** - Keyword-tagged GitHub API docs for JIT syntax lookup

---

## Gateway Command

**Primary entry point:** `/hiivmind-pulse-gh`

Use natural language to describe any GitHub operation:

```bash
# Examples
/hiivmind-pulse-gh create issue for login bug
/hiivmind-pulse-gh set milestone v2.0 on issue #42
/hiivmind-pulse-gh add PR to project
/hiivmind-pulse-gh trigger workflow ci.yml
/hiivmind-pulse-gh create milestone v3.0 due June 2025
/hiivmind-pulse-gh set up branch protection on main
```

### What the Gateway Does

1. **Context Check** - Verifies workspace is initialized
2. **Freshness Check** - Offers refresh if config is stale (configurable threshold)
3. **Intent Detection** - Parses natural language → domain + operation + target
4. **Confirmation** - Asks before mutations (configurable)
5. **Execution** - Routes to `hiivmind-pulse-gh-operations` skill

**No arguments:** Shows interactive menu of available operations.

---

## Architecture

```
/hiivmind-pulse-gh [request]
    │
    ├── Context Check
    │   ├── Initialized? → if not, invoke init skill
    │   └── Fresh? → if stale, offer refresh skill
    │
    ├── Intent Detection
    │   ├── Domain: issues, PRs, milestones, projects, etc.
    │   ├── Operation: create, update, delete, list, link
    │   └── Target: issue #42, milestone "v2.0", etc.
    │
    └── Execution
        └── hiivmind-pulse-gh-operations skill
            ├── Consults: api-routing.md
            ├── References: workflow examples
            ├── Searches: corpus for syntax
            └── Executes: gh CLI commands
```

---

## Skills

| Skill | Purpose | Invoked By |
|-------|---------|------------|
| `hiivmind-pulse-gh-init` | First-time workspace setup | Gateway (if not initialized) |
| `hiivmind-pulse-gh-refresh` | Sync config with GitHub | Gateway (if stale) |
| `hiivmind-pulse-gh-operations` | Execute GitHub operations | Gateway (after intent detection) |

### When Skills Are Used

- **init**: Called automatically when config.yaml doesn't exist
- **refresh**: Offered when config exceeds freshness threshold (default: 7 days)
- **operations**: Called for all GitHub operations after intent is detected

---

## Configuration

### Team Config: `.hiivmind/github/config.yaml`

Shared across team, committed to git:

```yaml
workspace:
  type: organization
  login: hiivmind
  id: O_kgDO...

projects:
  default: 2
  catalog:
    - number: 2
      id: PVT_kwDO...
      fields:
        Status:
          id: PVTSSF_...
          options:
            Backlog: f75ad846
            "In progress": 47fc9ee4

cache:
  last_synced_at: "2025-12-08T22:05:29Z"
  last_freshness_check: null
```

### User Config: `.hiivmind/github/user.yaml`

User-specific, NOT committed (add to .gitignore):

```yaml
user:
  login: username
  id: U_kgDO...

preferences:
  freshness_threshold_days: 7    # Days before config is stale
  confirm_mutations: true        # Ask before create/update/delete
  default_project: null          # Override team default
```

---

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

This plugin includes an embedded GitHub API corpus at `skills/hiivmind-corpus-github/`.

### How to Use the Corpus

**Do NOT grep the corpus directly.** Use the proper flow:

1. **Read routing guide** - `reference/api-routing.md` has routing decisions + search keywords
2. **Navigate corpus** - Use the corpus's navigate skill with those keywords
3. **Get syntax** - Corpus returns paths to source docs with current syntax

### Lookup Flow

```
reference/api-routing.md          →  "Milestones create → REST"
                                      Keywords: milestones, POST, create, title, due_on
                                              ↓
corpus navigate skill             →  Searches index for keywords
                                              ↓
corpus index                      →  Returns: rest:repos/milestones.md#create
                                              ↓
source doc                        →  Current syntax (POST /repos/{owner}/{repo}/milestones)
```

### Why This Matters

- **Routing guide** owns the decisions and keywords (updated manually when API changes)
- **Corpus index** owns the locations (updated by corpus refresh)
- **Source docs** own the syntax (always current from upstream)

Each layer manages its own concerns. No hardcoded paths in CLAUDE.md.

---

## File Structure

```
hiivmind-pulse-gh/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── hiivmind-pulse-gh.md              # Gateway command
├── skills/
│   ├── hiivmind-corpus-github/           # GitHub API corpus
│   ├── hiivmind-pulse-gh-init/           # Workspace initialization
│   ├── hiivmind-pulse-gh-refresh/        # Config sync
│   └── hiivmind-pulse-gh-operations/     # Execute operations
├── reference/
│   ├── api-routing.md                    # API routing decisions
│   ├── config-schema.md                  # Config.yaml schema
│   └── workflows/                        # Multi-step examples
├── templates/
│   ├── config.yaml.template
│   └── user.yaml.template
├── _deprecated/github/                   # Legacy bash functions (reference only)
└── docs/
    └── architecture-v3-proposal.md
```

---

## Dependencies

- **gh** - GitHub CLI, authenticated with scopes: `repo`, `read:org`, `read:project`, `project`
- **jq** (1.6+) - JSON processing
- **yq** (4.0+) - YAML processing

Run `hiivmind-pulse-gh-init` to verify all dependencies.

---

## Testing

Tests are maintained in a separate repository: [hiivmind-pulse-gh-tests](https://github.com/hiivmind/hiivmind-pulse-gh-tests)

This keeps the plugin lean for distribution while allowing comprehensive test coverage.

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
