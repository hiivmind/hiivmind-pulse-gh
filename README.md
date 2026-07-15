# hiivmind-pulse-gh

A Claude Code plugin that enriches **every** GitHub operation with cached workspace
context — Projects v2, milestones, branch protection, and more — and layers on a
headless automation engine for unattended fleet maintenance and resumable,
cross-repo workflows.

## The Problem

GitHub's APIs are powerful but painful:
- **GraphQL node IDs** — every operation needs opaque IDs like `PVT_kwDOBx...`
- **Repeated lookups** — "What's the ID for the Status field? The option ID for 'In Progress'?"
- **Context amnesia** — each Claude session starts fresh, forgetting your org structure
- **No unattended path** — scheduled or headless maintenance needs zero-prompt skills and
  a machine-readable result contract, not interactive prose

## The Solution

A **discover-once, use-forever** cache plus a deterministic Python engine:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. DISCOVER                                                     │
│     Init inspects your GitHub org structure                     │
│     → projects, fields, options, repositories, milestones       │
│                                                                  │
│  2. CACHE                                                        │
│     Store discovered IDs in {workspace_root}/.hiivmind/github/   │
│     → committed to a shared workspace repo, synced across team   │
│                                                                  │
│  3. USE                                                          │
│     Gateway routes intent → skill; every op is enriched with     │
│     cached IDs. Headless skills + workflows automate the rest.   │
└─────────────────────────────────────────────────────────────────┘
```

**Rule of thumb:** if a workspace root resolves above your cwd (a
`.hiivmind/github/config.yaml` with a top-level `workspace:` section, at any parent
depth), route **all** GitHub operations through this plugin — even simple ones —
so they pick up context enrichment (auto-link to project, set Status, resolve
milestone names, etc.).

## Installation

### 1. Install prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| **gh** | GitHub CLI | [cli.github.com](https://cli.github.com/) |
| **jq** | JSON processing | `apt install jq` / `brew install jq` |
| **yq** (v4+) | YAML processing | [github.com/mikefarah/yq](https://github.com/mikefarah/yq) |
| **uv** | runs the bundled Python scripts (PEP 723) | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |

```bash
# Verify installation
gh auth status && jq --version && yq --version && uv --version

# Ensure gh has required scopes
gh auth refresh -s read:project -s project -s repo -s read:org
```

### 2. Install the plugin

Run these in Claude Code (not a terminal):

```
# Add the marketplace
/plugin marketplace add hiivmind/hiivmind-pulse-gh

# Install the plugin (plugin name `gh`, marketplace `hiivmind-pulse-gh`)
/plugin install gh@hiivmind-pulse-gh
```

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

# Discover / explore
/gh discover
/gh what can I do with projects
/gh help
```

### How it works

1. **Intent detection** — parses natural language → domain + operation + target
2. **Context check** — verifies a workspace is initialized; offers init if not
3. **Freshness check** — offers a refresh if the cached config is stale
4. **Confirmation** — asks before mutations
5. **Execution** — routes to the right skill with corpus-backed API syntax

## Skills

The plugin ships **12 skills** — seven interactive, five headless (zero-prompt,
for schedulers and orchestrators).

### Interactive

| Skill | Purpose |
|-------|---------|
| `gh-init` | First-time setup: validate environment, discover org structure, place the workspace root, write `config.yaml` |
| `gh-refresh` | Sync cached config with GitHub |
| `gh-operations` | Execute GitHub operations across all domains |
| `gh-discover` | Explore available operations across every domain |
| `gh-healthcheck` | On-demand repository governance audit |
| `gh-heartbeat` | Present/execute heartbeat-triggered workflows on session start |
| `gh-workflows` | Manage and run workflow definitions |

### Headless (zero prompts, explicit inputs only, every exit writes a result file)

| Skill | Purpose |
|-------|---------|
| `gh-status-headless` | Status pre-check → `status-result.yaml` (is a refresh warranted?) |
| `gh-refresh-headless` | Config sync replaying recorded decisions → `refresh-result.yaml` |
| `gh-healthcheck-headless` | Profile-dispatched fleet governance audit + coverage debt → `healthcheck-result.yaml` |
| `gh-workflow-run-headless` | Run a workflow unattended under its headless policy → `workflow-run-result.yaml` |
| `gh-fleet-evidence-headless` | Nave-backed structural projection → `fleet-evidence.yaml` |

> Syntax lookup uses an external corpus, `hiivmind-corpus-github-docs-navigate`
> (declared as a plugin dependency), for exact GraphQL/REST definitions when needed.

## Headless orchestration & the result contract

Every headless skill is **read-only against GitHub** (except committed workspace
files), takes **explicit inputs only** (never discovers a workspace), and writes a
versioned machine-readable artifact. Status, refresh, healthcheck, and workflow-run
use `lib/patterns/headless-contract.md`:

```yaml
contract_version: 1
kind: status | healthcheck | refresh | workflow-run
workspace: <login>
run_at: "<ISO 8601>"          # always a quoted string
actor: { gh_login: <str>, machine: <str>, mode: interactive | scheduled }
# ...kind-specific fields...
errors: []
```

Result files are validated mechanically:

```bash
uv run lib/pulse/scripts/validate_result.py <file> --kind <kind>   # exit 0/1/2
```

Fleet evidence has a separate provider contract because tooling capability is not
repository health. Validate it with:

```bash
uv run lib/pulse/scripts/validate_evidence.py .hiivmind/github/fleet-evidence.yaml
```

Nave evidence is a tracked structural projection, not authoritative fleet
membership. Repositories not present are unobserved; later profile/membership
workflows resolve workspace scope independently.

Fleet healthchecks combine that F0 projection with reviewed F1 repository profiles.
Each repository is evaluated only against its assigned scorecard, so its grade is
reported with the scorecard ID. Fleet aggregation stays within scorecards; adapter
coverage and unprofiled repositories are reported separately as coverage debt. There
is no universal 11-check audit or mixed-scorecard fleet grade.

Orchestrators read the result **file**, never the skill's prose — so a scheduled run
is deterministic and auditable.

## Workflows (v1 → v3)

Workflows are declarative YAML in `{workspace_root}/.hiivmind/github/workflows/`.
Three formats coexist and are fully backward-compatible (a file has exactly one of
`actions:` / `workflow:` / `steps:`):

| Version | Shape | Use |
|---------|-------|-----|
| **v1** | `actions:` — sequential dispatch | Simple linear automations (legacy) |
| **v2** | `workflow:` — a pseudocode FSM with `state:`, phases, `GOTO` | Interactive, single-repo triggered workflows |
| **v3** | `steps:` — a DAG over v2 blocks with `repos:`, `depends_on:`, `gate:` | Cross-repo, resumable, gate-driven releases |

**v3 run ledger.** A v3 run persists as a ledger record so it survives sessions — a
run started in one session (or on one machine) is resumed by any later session or
scheduled run:

- Cross-repo runs → `{workspace_root}/.hiivmind/github/runs/{workflow}-{run_id}.yaml`
  (**committed** — the team's shared release-state view)
- Single-repo/personal runs → `runs/local/` (gitignored)

The ledger is only ever read/written through `resolve_run.py` (the LLM never
hand-edits it); the LLM evaluates each **gate's** truth against GitHub and records
it. Gate-blocked runs surface in the heartbeat so releases advance as a side effect
of normal session starts. Lint any workflow file with:

```bash
uv run lib/pulse/scripts/workflow_lint.py path/to/workflow.yaml
```

A `release-train.yaml` reference workflow ships in `templates/workflows/`.

## The Python engine

Deterministic, mechanical work lives in self-contained PEP 723 scripts
(`lib/pulse/scripts/`, run via `uv run`) so skills stay orchestration documents:

| Script | Responsibility |
|--------|----------------|
| `poll.py` | Heartbeat engine — GraphQL polling + workflow trigger detection; surfaces gate-blocked runs |
| `evaluate_checks.py` | Legacy mechanical evaluator and centralized weighted scorer |
| `healthcheck_dispatch.py` | F0/F1 profile dispatch, adapters, dismissals, scorecard aggregation, and coverage |
| `freshness_status.py` | Per-section staleness computation for the status pre-check |
| `validate_result.py` | Headless result-contract validator |
| `nave_adapter.py` | Fixture-testable external Nave CLI boundary |
| `evidence_snapshot.py` | Normalize Nave JSON into profile-neutral fleet evidence |
| `validate_evidence.py` | Fleet evidence contract validator |
| `resolve_run.py` | Deterministic run-ledger operations (create/advance/gate/lease) |
| `workflow_lint.py` | Workflow YAML lint (v1/v2/v3 schema, FSM refs, headless policy, DAG acyclicity) |

## Scheduled fleet maintenance

Unattended maintenance lives in a separate repo,
[hiivmind-pulse-scheduler](https://github.com/hiivmind/hiivmind-pulse-scheduler):
a shared `TEMPLATE-workspace-maintenance.md` composes the headless skills
(status pre-check → refresh → fleet healthcheck → PR on the workspace repo), and
thin per-workspace stubs are symlinked into `~/.claude/scheduled-tasks/`.

## Supported domains

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

> This table shows commonly used domains. The plugin supports **any** GitHub domain
> via corpus lookup — **26 domains** have dedicated syntax references under
> `lib/references/domains/`. Some dangerous operations (delete repository, transfer
> ownership) are blocked for safety; see `lib/references/operation-blocklist.md`.

## Quick Start

### First-time setup

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

### Daily usage

```
You: /gh create issue for authentication timeout

Claude: Create issue in acme-corp/api?
        Title: "Authentication timeout"

        Proceed? [Yes / Edit / Cancel]

You: Yes

Claude: Issue #143 created: https://github.com/acme-corp/api/issues/143
        Linked to Product Roadmap · Status → Backlog
```

## Workspace configuration

### The workspace-root model

The **workspace root** is typically the parent folder holding an org's repo clones.
`.hiivmind/github/` there is its own small **git repo** shared by the team (remote
`{login}-workspace`) — it holds shared structure, and gitignores per-machine
transients. Any operation whose cwd is at or below the workspace root is enriched.

```
{workspace_root}/                    ← parent of repo clones
├── api/                             ← a repo clone
├── frontend/                        ← a repo clone
└── .hiivmind/
    └── github/                      ← its own git repo (the "workspace repo")
        ├── config.yaml              # SHARED — org structure, project/field/milestone IDs
        ├── freshness.yaml           # SHARED — per-section staleness tracking
        ├── healthcheck.yaml         # SHARED — fleet governance record
        ├── workflows/               # SHARED — workflow definitions
        ├── runs/                    # SHARED — committed cross-repo run ledgers
        ├── runs/local/              # gitignored — per-machine single-repo runs
        ├── user.yaml                # PERSONAL — gitignored
        └── *-result.yaml            # gitignored — headless result files
```

### What gets cached

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

## Architecture

```
hiivmind-pulse-gh/
├── .claude-plugin/
│   ├── plugin.json                       # Plugin manifest + dependencies
│   └── marketplace.json                  # Marketplace manifest
├── commands/
│   ├── gh.md                             # Gateway command
│   └── intent-mapping.yaml               # Intent detection rules
├── skills/
│   ├── gh-init/  gh-refresh/  gh-operations/  gh-discover/
│   ├── gh-healthcheck/  gh-heartbeat/  gh-workflows/
│   ├── gh-status-headless/       # Headless status pre-check
│   ├── gh-refresh-headless/      # Headless config sync
│   ├── gh-healthcheck-headless/  # Headless fleet audit
│   ├── gh-workflow-run-headless/ # Headless workflow run
│   └── gh-fleet-evidence-headless/ # Nave structural evidence
├── hooks/
│   ├── hooks.json                        # Hook configuration
│   ├── heartbeat.sh                      # SessionStart poll (workspace-root walk-up)
│   ├── post-operation-check.sh           # Post-operation validation
│   └── validate-gh-operation.sh          # Operation validation
├── lib/
│   ├── patterns/                         # HOW to do things (executable guides)
│   │   ├── config-parsing.md  id-resolution.md  graphql-execution.md
│   │   ├── workspace-detection.md  corpus-lookup.md  error-*.md
│   │   ├── headless-contract.md          # The headless result schema
│   │   ├── nave-evidence-contract.md     # Nave evidence projection schema
│   │   ├── workflow-execution.md         # THE workflow executor (v1/v2/v3)
│   │   └── run-ledger.md                 # Run-ledger schema + resume protocol
│   ├── pulse/
│   │   └── scripts/                      # Deterministic Python (PEP 723, uv run)
│   │       ├── poll.py  evaluate_checks.py  freshness_status.py
│   │       ├── validate_result.py  resolve_run.py  workflow_lint.py
│   │       ├── nave_adapter.py  evidence_snapshot.py  validate_evidence.py
│   │       └── tests/                    # pytest suite
│   └── references/                       # WHAT exists (static lookup data)
│       ├── api-routing.md  config-schema.md  healthcheck-checks.md
│       ├── operation-blocklist.md  token-permissions.md  workflow-triggers.md
│       └── domains/                      # Per-domain API syntax (26 files)
├── templates/
│   ├── config.yaml.template  freshness.yaml.template  healthcheck.yaml.template
│   ├── user.yaml.template  workspace-gitignore.template  ...
│   └── workflows/                        # Pre-built workflow templates (incl. release-train.yaml)
├── docs/
│   ├── superpowers/                      # Specs and phased implementation plans
│   └── backlogs/                         # Tracked follow-ups
├── pyproject.toml  uv.lock               # Python dev/test env
└── # External dependency: hiivmind-corpus-github
```

### Design principles

1. **Skills over MCP** — load on-demand, better context efficiency.
2. **Skills orchestrate, scripts compute** — deterministic work lives in Python
   (PEP 723, `uv run`), not embedded shell in skills.
3. **Pattern library** — reusable markdown patterns referenced via `See:`.
4. **Corpus lookup** — just-in-time API syntax from bundled documentation.
5. **Cache structure, not data** — IDs are stable; item data changes constantly.
6. **Shared config, personal transients** — team collaborates; per-machine state is gitignored.
7. **Result files, not prose** — headless runs communicate via a validated contract.
8. **Graceful degradation** — works without config (explicit params required).

### How operations work

```
1. ROUTE       →   2. RESOLVE   →   3. EXECUTE
   (API choice)      (IDs)           (run)
     │                 │                │
lib/references/    config.yaml      gh api graphql
api-routing.md     cache            or gh api REST
                     │
                  corpus (if uncertain about syntax)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No workspace configuration found" | Run `/gh` and accept the init prompt |
| "Field ID not found" | Run `/gh refresh` to sync with GitHub |
| "Config is stale" | Run `/gh refresh` |
| `gh: command not found` | Install GitHub CLI: [cli.github.com](https://cli.github.com/) |
| `yq: command not found` | Install yq v4+: [github.com/mikefarah/yq](https://github.com/mikefarah/yq) |
| `uv: command not found` | Install uv: [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| Permission errors | `gh auth refresh -s read:project -s project -s repo -s read:org` |
| "Resource not accessible" | Check access: `gh repo view owner/repo` |

## Limitations

- **Claude Code only** — this is a Claude Code plugin (skills), not an MCP server.
- **Requires local tools** — `gh`, `jq`, `yq`, and `uv` must be installed where Claude Code runs.
- **Inherits gh permissions** — can only access what your `gh` CLI can. No elevation, no bypass.

## Testing

Two suites:

**Python unit tests (in-repo)** cover the deterministic engine:

```bash
uv run pytest          # 47 tests across lib/pulse/scripts/tests/
```

**End-to-end / integration tests** live in a separate repository to keep the plugin
lean for distribution:
[hiivmind-pulse-gh-tests](https://github.com/hiivmind/hiivmind-pulse-gh-tests).

```bash
git clone https://github.com/hiivmind/hiivmind-pulse-gh-tests.git
cd hiivmind-pulse-gh-tests
./scripts/setup.sh                     # clones this repo + installs deps
./node_modules/.bin/bats e2e/smoke/    # smoke tests
```

## Contributing

```
commands/*.md                              → Gateway and slash commands
skills/*/SKILL.md                          → Skill documentation
hooks/                                     → Event-driven hook scripts
lib/patterns/*.md                          → Executable patterns (HOW to do things)
lib/pulse/scripts/*.py                     → Deterministic Python (PEP 723)
lib/references/*.md                        → Static lookup data (WHAT exists)
templates/                                 → Config and workflow templates
docs/superpowers/                          → Specs and phased implementation plans
```

When working on plugin structure, use the `plugin-dev` skills (plugin-structure,
skill-development, command-development, hook-development).

## License

MIT
