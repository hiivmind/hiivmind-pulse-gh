# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## System Overview

This is **hiivmind-pulse-gh** - a Claude Code plugin for GitHub API operations. It provides:

- **Gateway command** - Single entry point for all GitHub operations
- **Workspace initialization** - Cache project/repo IDs to config.yaml
- **Operations execution** - All domains: issues, PRs, milestones, projects, protection, actions, releases
- **API routing** - Automatic GraphQL vs REST selection
- **Documentation corpus** - GitHub API docs for JIT syntax lookup

---

## Execution Architecture

Operations follow this approach:

```
1. ROUTE       →   2. RESOLVE   →   3. EXECUTE
   (API choice)      (IDs)           (run)
     │                 │                │
lib/examples/      config.yaml      gh api graphql
operations/        cache            or gh api REST
api-routing.md
```

### How It Works

1. **Route** - Read `lib/examples/operations/api-routing.md` for API choice (GraphQL vs REST)
   - This guide is useful on its own - not every operation needs corpus lookup

2. **Resolve** - Get IDs from cached config (`lib/examples/introspection/id-resolution.md`)
   - Cache-first strategy avoids unnecessary API calls

3. **Execute** - Run the operation:
   - If syntax is clear: Execute directly
   - If uncertain: Use corpus lookup (`lib/examples/operations/corpus-lookup.md`)

### Corpus Lookup (When Needed)

Use corpus lookup when you have a knowledge gap about exact syntax:

- **Invoke:** `hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs`
- **Query:** With keywords from routing guide
- **Get:** Exact mutation/endpoint definitions from schema

### Key Principle

**Skills are orchestration documents, NOT code repositories.**

- Skills are ~150-270 lines
- No embedded bash functions
- No hardcoded GraphQL queries
- Reference patterns via `See:` convention
- Corpus has the syntax, skills orchestrate the flow

---

## Examples Library

Skills reference examples instead of embedding code. The library is organized by purpose:

### Introspection Examples (HEAVY)

Detailed, repeatable examples for state-checking operations:

| Example | Purpose |
|---------|---------|
| `lib/examples/introspection/config-parsing.md` | Read/write YAML config files |
| `lib/examples/introspection/id-resolution.md` | Resolve names to IDs (cache-first) |
| `lib/examples/introspection/graphql-execution.md` | Execute queries via temp file |
| `lib/examples/introspection/error-handling.md` | Handle API errors |
| `lib/examples/introspection/authentication.md` | Verify gh auth and scopes |
| `lib/examples/introspection/tool-detection.md` | Check gh/jq/yq availability |
| `lib/examples/introspection/workspace-detection.md` | Git remote → owner/repo |

### Operations Examples (LIGHT)

Lightweight routing guidance (corpus provides JIT syntax):

| Example | Purpose |
|---------|---------|
| `lib/examples/operations/api-routing.md` | API routing decisions (THE canonical source) |
| `lib/examples/operations/corpus-lookup.md` | Look up API syntax when uncertain |

### Using Examples

Skills use `See:` references:

```markdown
## Phase 1: CONTEXT

**See:** `lib/examples/introspection/config-parsing.md`

1. Load config.yaml
2. Verify initialization
```

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
/hiivmind-pulse-gh document decision about using GraphQL
```

### What the Gateway Does

1. **Intent Detection** - Parses natural language → domain + operation + target
2. **Context Check** - Verifies workspace is initialized (skipped for ADR/awareness)
3. **Freshness Check** - Offers refresh if config is stale
4. **Confirmation** - Asks before mutations
5. **Execution** - Routes to appropriate skill (operations, ADR, or awareness)

---

## Skills

| Skill | Purpose | Structure |
|-------|---------|-----------|
| `hiivmind-pulse-gh-init` | First-time workspace setup | 6 phases (~150 lines) |
| `hiivmind-pulse-gh-refresh` | Sync config with GitHub | 6 phases (~200 lines) |
| `hiivmind-pulse-gh-operations` | Execute GitHub operations | 5 phases (~270 lines) |
| `hiivmind-pulse-gh-adr` | Architecture Decision Records | 6 phases with STOP points |
| `hiivmind-pulse-gh-awareness` | CLAUDE.md capability injection | 5 phases (What/When/How) |

### Skill Architecture

Each skill follows a phase-based structure:

```
CONTEXT → RESOLVE → ROUTE → EXECUTE → REPORT
   │         │        │        │         │
 config    IDs    api-routing  direct   result
 check    cache     guide    or corpus  display
```

**STOP Points:** Skills have explicit STOP conditions that halt execution and prompt user action.

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
```

### Freshness Tracking: `.hiivmind/github/freshness.yaml`

Per-section staleness tracking:

```yaml
sections:
  workspace:
    last_checked: "2025-12-16T12:00:00Z"
    threshold_hours: 168
    stale: false
  projects:
    last_checked: "2025-12-15T10:00:00Z"
    threshold_hours: 24
    stale: true
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

> **Note:** This table shows commonly used domains. For complete routing decisions, see `lib/examples/operations/api-routing.md`. The plugin supports **any GitHub domain** via corpus lookup. For unlisted domains, the operations skill uses corpus lookup and defaults to REST API. Some dangerous operations are blocked — see `docs/operation-blocklist.md`.

---

## GitHub Documentation Corpus

This plugin uses an external GitHub API corpus (declared as dependency in plugin.json).

### Using the Corpus

Use the corpus when you need exact API syntax. See `lib/examples/operations/corpus-lookup.md`.

1. Read `lib/examples/operations/api-routing.md` for API choice (useful on its own)
2. If uncertain about syntax, invoke: `hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs`
3. Search with keywords from routing guide
4. Get exact syntax from schema/docs

---

## File Structure

```
hiivmind-pulse-gh/
├── .claude-plugin/
│   └── plugin.json                       # Plugin manifest + dependencies
├── commands/
│   └── hiivmind-pulse-gh.md              # Gateway command
├── skills/
│   ├── hiivmind-pulse-gh-init/           # Workspace initialization
│   ├── hiivmind-pulse-gh-refresh/        # Config sync
│   ├── hiivmind-pulse-gh-operations/     # Execute operations
│   ├── hiivmind-pulse-gh-adr/            # Architecture Decision Records
│   └── hiivmind-pulse-gh-awareness/      # CLAUDE.md capability injection
│       └── examples/                     # Skill-local awareness patterns
├── lib/
│   └── examples/                         # Centralized examples library
│       ├── introspection/                # HEAVY - detailed state-checking
│       │   ├── config-parsing.md
│       │   ├── id-resolution.md
│       │   ├── graphql-execution.md
│       │   └── ...
│       └── operations/                   # LIGHT - routing (corpus has syntax)
│           ├── api-routing.md            # THE canonical routing source
│           └── corpus-lookup.md
├── docs/
│   ├── adr/                              # Architecture Decision Records
│   ├── config-schema.md                  # Config.yaml schema
│   └── operation-blocklist.md            # Dangerous operations blocked
└── templates/
    ├── config.yaml.template
    └── user.yaml.template
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
