# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## System Overview

This is **hiivmind-pulse-gh** - a Claude Code plugin that enriches ALL GitHub operations with cached workspace context.


### Why Use This Plugin (Even for Simple Operations)

Direct `gh` CLI commands miss context enrichment:

| Direct CLI | via hiivmind-pulse-gh |
|------------|----------------------|
| `gh issue create` | Issue + auto-link to project + Status set |
| `gh issue close 42` | Issue closed + project Status → Done |
| Milestone ID lookup required | Milestone name resolves from cache |

**Rule of thumb:** If a workspace root resolves above cwd (a `.hiivmind/github/config.yaml` with a top-level `workspace:` section, at any parent depth — see `lib/patterns/workspace-detection.md`), route ALL GitHub operations through this plugin.

### What This Plugin Provides

- **Context enrichment** - Cached project IDs, field IDs, milestone IDs enrich every operation
- **Gateway command** - Single entry point: `/gh [describe what you want]`
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
lib/references/    config.yaml      gh api graphql
api-routing.md     cache            or gh api REST
```

### How It Works

1. **Route** - Read `lib/references/api-routing.md` for API choice (GraphQL vs REST)
   - This guide is useful on its own - not every operation needs corpus lookup

2. **Resolve** - Get IDs from cached config (`lib/patterns/id-resolution.md`)
   - Cache-first strategy avoids unnecessary API calls

3. **Execute** - Run the operation:
   - If syntax is clear: Execute directly
   - If uncertain: Use corpus lookup (`lib/patterns/corpus-lookup.md`)

### Corpus Lookup (When Needed)

Use corpus lookup when you have a knowledge gap about exact syntax:

- **Invoke:** `hiivmind-corpus-github-docs-navigate`
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

## Context Enrichment (The Core Value)

Every operation benefits from cached context, not just complex ones.

### What Gets Enriched

| Operation | Without Plugin | With Plugin |
|-----------|---------------|-------------|
| Create issue | Orphan issue | Linked to default project + Status set |
| Close issue | Just closes | Updates project Status to "Done" |
| Create PR | Basic PR | Linked to project, milestone applied |
| Set milestone | Need to look up ID | Uses cached milestone ID |
| Add label | Type exact name | Uses team labels from config |

### When to Bypass the Plugin

Only bypass if:
1. Workspace is NOT initialized (no workspace root resolvable above cwd)
2. You need raw, unenriched output
3. User explicitly requests `gh` CLI

Otherwise, **always route through hiivmind-pulse-gh**.

---

## Library Structure

Skills reference patterns and references instead of embedding code:

### Patterns (HOW to do things)

Executable guides with step-by-step instructions:

| Pattern | Purpose |
|---------|---------|
| `lib/patterns/config-parsing.md` | Read/write YAML config files |
| `lib/patterns/id-resolution.md` | Resolve names to IDs (cache-first) |
| `lib/patterns/graphql-execution.md` | Execute queries via temp file |
| `lib/patterns/error-handling.md` | Handle API errors |
| `lib/patterns/authentication.md` | Verify gh auth and scopes |
| `lib/patterns/tool-detection.md` | Check gh/jq/yq availability |
| `lib/patterns/workspace-detection.md` | Git remote → owner/repo |
| `lib/patterns/corpus-lookup.md` | Look up API syntax when uncertain |
| `lib/patterns/healthcheck-evaluation.md` | Healthcheck evaluation logic per check |
| `lib/patterns/workflow-execution.md` | THE workflow executor (single normative description; interactive + headless) |
| `lib/patterns/run-ledger.md` | Run ledger: resumable cross-repo runs |

### References (WHAT exists)

Static lookup data for routing and domain info:

| Reference | Purpose |
|-----------|---------|
| `lib/references/api-routing.md` | Quick reference + method selection guide |
| `lib/references/domains/*.md` | Per-domain detailed syntax (26 files) |
| `lib/references/token-permissions.md` | Token permission requirements |
| `lib/references/healthcheck-checks.md` | Healthcheck check catalog (11 checks) |

### Using Patterns

Skills use `See:` references:

```markdown
## Phase 1: CONTEXT

**See:** `lib/patterns/config-parsing.md`

1. Load config.yaml
2. Verify initialization
```

---

## Gateway Command

**Primary entry point:** `/hiivmind-pulse-gh`

Use natural language to describe any GitHub operation:

```bash
# Examples
/gh create issue for login bug
/gh set milestone v2.0 on issue #42
/gh add PR to project
/gh trigger workflow ci.yml
```

### What the Gateway Does

1. **Intent Detection** - Parses natural language → domain + operation + target
2. **Context Check** - Verifies workspace is initialized
3. **Freshness Check** - Offers refresh if config is stale
4. **Confirmation** - Asks before mutations
5. **Execution** - Routes to appropriate skill

---

## Skills

| Skill | Purpose |
|-------|---------|
| `gh-init` | First-time workspace setup (workspace-root placement, workspace repo init) |
| `gh-refresh` | Sync config with GitHub |
| `gh-operations` | Execute GitHub operations |
| `gh-healthcheck` | Repository governance audit |
| `gh-heartbeat` | Present/execute heartbeat-triggered workflows |
| `gh-workflows` | Manage and run workflow definitions |
| `gh-discover` | Discover workspace resources |
| `gh-status-headless` | Headless status pre-check → status-result.yaml (zero prompts) |
| `gh-healthcheck-headless` | Headless fleet governance audit → healthcheck-result.yaml |
| `gh-refresh-headless` | Headless config sync (replays recorded decisions) → refresh-result.yaml |
| `gh-workflow-run-headless` | Run a v2 workflow unattended under its headless policy → workflow-run-result.yaml |

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

### Team Config: `{workspace_root}/.hiivmind/github/config.yaml`

The workspace root is typically the parent folder of an org's repo clones;
`.hiivmind/github/` there is its own small git repo shared by the team
(remote `{login}-workspace`). Per-machine transients are gitignored:

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

> **Note:** This table shows commonly used domains. For complete routing decisions, see `lib/references/api-routing.md`. The plugin supports **any GitHub domain** via corpus lookup. For unlisted domains, the operations skill uses corpus lookup and defaults to REST API. Some dangerous operations are blocked — see `lib/references/operation-blocklist.md`.

---

## GitHub Documentation Corpus

This plugin uses an external GitHub API corpus (declared as dependency in plugin.json).

### Using the Corpus

Use the corpus when you need exact API syntax. See `lib/patterns/corpus-lookup.md`.

1. Read `lib/references/api-routing.md` for API choice (useful on its own)
2. If uncertain about syntax, invoke: `hiivmind-corpus-github-docs-navigate`
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
├── hooks/
│   └── heartbeat.sh                      # SessionStart poll (workspace-root walk-up)
├── skills/
│   ├── gh-init/           # Workspace initialization
│   ├── gh-refresh/        # Config sync
│   ├── gh-operations/     # Execute operations
│   ├── gh-healthcheck/    # Repository governance audit
│   ├── gh-heartbeat/      # Present/execute heartbeat-triggered workflows
│   ├── gh-workflows/      # Manage and run workflow definitions
│   ├── gh-discover/       # Discover workspace resources
│   ├── gh-status-headless/       # Headless status pre-check
│   ├── gh-healthcheck-headless/  # Headless fleet governance audit
│   ├── gh-refresh-headless/      # Headless config sync
│   └── gh-workflow-run-headless/ # Headless workflow run (policy-projected)
├── lib/
│   ├── patterns/                         # HOW to do things (executable guides)
│   │   ├── config-parsing.md
│   │   ├── id-resolution.md
│   │   ├── graphql-execution.md
│   │   ├── corpus-lookup.md
│   │   └── ...
│   ├── pulse/
│   │   └── scripts/                      # Deterministic Python (PEP 723, uv run)
│   │       ├── poll.py                   # Heartbeat engine (GraphQL + lakehouse)
│   │       ├── evaluate_checks.py        # Mechanical healthcheck evaluator
│   │       ├── freshness_status.py       # Staleness computation for headless status
│   │       ├── validate_result.py        # Headless result contract validator
│   │       ├── resolve_run.py            # Run-ledger operations
│   │       └── workflow_lint.py          # Workflow YAML lint
│   └── references/                       # WHAT exists (static lookup data)
│       ├── api-routing.md                # Quick reference + method selection
│       ├── token-permissions.md          # Token permission requirements
│       └── domains/                      # Per-domain detailed syntax (26 files)
│           ├── issues.md
│           ├── pull-requests.md
│           └── ...
├── docs/
│   ├── adrs/                             # Architecture decision records
│   └── (empty - files moved to lib/references/)
└── templates/
    ├── config.yaml.template
    └── user.yaml.template
```

---

## Dependencies

- **gh** - GitHub CLI, authenticated with scopes: `repo`, `read:org`, `read:project`, `project`
- **jq** (1.6+) - JSON processing
- **yq** (4.0+) - YAML processing

Run `gh-init` to verify all dependencies.

---

## Testing

Tests are maintained in a separate repository: [hiivmind-pulse-gh-tests](https://github.com/hiivmind/hiivmind-pulse-gh-tests)

This keeps the plugin lean for distribution while allowing comprehensive test coverage.

---

## Scheduled Maintenance

Unattended fleet maintenance lives in a separate repo:
[hiivmind-pulse-scheduler](https://github.com/hiivmind/hiivmind-pulse-scheduler) —
a shared `TEMPLATE-workspace-maintenance.md` composes the headless skills
(status pre-check → refresh → fleet healthcheck → PR on the workspace repo);
thin per-workspace stubs are symlinked into `~/.claude/scheduled-tasks/`.

---

## Plugin Development Resources

When working on plugin structure, use the `plugin-dev` skills:

| Skill | Use When |
|-------|----------|
| `plugin-dev:plugin-structure` | Plugin manifest, directory layout |
| `plugin-dev:skill-development` | Writing SKILL.md files |
| `plugin-dev:command-development` | Slash commands |
| `plugin-dev:hook-development` | Event hooks |
