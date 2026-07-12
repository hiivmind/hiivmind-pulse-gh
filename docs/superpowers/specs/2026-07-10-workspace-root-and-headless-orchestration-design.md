# Architectural Review: Workspace Root, Headless Skills, and Composable Orchestration

**Date:** 2026-07-10
**Status:** Proposed
**Scope:** hiivmind-pulse-gh capability upgrade, patterned on hiivmind-corpus and hiivmind-corpus-scheduler
**Companion spec:** `2026-07-10-lockstep-bindings-and-target-workflows-design.md`
(the workflow catalog this platform exists to run; its entries consume the
phases defined here and may add result kinds, poll sources, and scripts)

## Goals

1. Headless runs of maintenance and diagnostic checks across multiple repos.
2. Improved workflow definitions and statuses, especially for complex multi-repo
   releases and testing with cross-repo dependencies.

Derived capability asks:

- Headless versions of skills
- Composable orchestration skills, separate from the ops skills
- Metadata/status maintenance and explicit contracts between skills and workflows
- Deterministic Python-based ops where possible

---

## Part 1: The Reference Architecture (what corpus established)

The recent hiivmind-corpus / hiivmind-corpus-scheduler upgrades amount to five
reusable architectural moves. Each is directly portable to this plugin.

### 1.1 Headless sibling skills

Every automatable operation has a `-headless` variant (`refresh-headless`,
`status-headless`, `enrich-headless`, `build-headless`, `migrate`) with:

- `inputs:` / `outputs:` frontmatter (explicit `corpus_path`, `result_path` —
  no directory discovery in automation)
- An explicit `State:` block (`computed:` variables) at the top of the skill
- Numbered phases, each declaring its outputs
- ABORT semantics that still emit a valid result file rather than crashing
- No prompts; judgment calls are recorded, not asked

### 1.2 A versioned result-file contract

`patterns/headless-contract.md` defines per-kind YAML schemas written **to
disk**: "orchestrators MUST read the file, not the prose." Key properties:

- `contract_version` (integer, consumers reject unknown versions)
- `kind` discriminator; adding kinds is backward-compatible
- Precise status enums with operational semantics (`skipped-manual` = automation
  cannot silently never-refresh; `deferred` = downstream stage is mandatory)
- Result files are transient run artifacts, gitignored by the skill itself
- A deterministic validator (`validate_result.py --kind X`) with defined exit
  codes (0 valid / 1 invalid / 2 missing) gates consumption

### 1.3 Orchestration separated from ops, in its own repo

`hiivmind-corpus-scheduler` holds one shared `TEMPLATE-corpus-refresh.md`
(state block, constants, phases, `<run-summary>`) plus thin per-corpus stubs
supplying exactly three constants. The template **composes** headless skills:

```
status-headless (cheap pre-check, ls-remote only)
  → refresh-headless
  → enrich-headless (conditional on stale entries)
  → branch / commit / PR (+ superseded-PR cleanup)
```

Process changes edit the template only; stubs never change. The pre-check is
"an optimization, never a gate" — its failure falls through to the full run.

### 1.4 Deterministic Python where determinism matters

`lib/corpus/scripts/*.py` with PEP 723 inline metadata, invoked as
`uv run ${CLAUDE_PLUGIN_ROOT}/lib/corpus/scripts/<script>.py`, with tests and a
pyproject. The division of labor: **the LLM orchestrates; Python computes**
(validation, diffing, embedding, verification).

### 1.5 Decision capture and derivation DAG

- Interactive skills record decisions (`config.build`) so headless variants
  **replay** instead of guessing.
- `derivation-dag.md` declares sources of truth vs. derived/rendered artifacts.
- A cross-cutting-concerns table in CLAUDE.md keeps the skill family aligned.

---

## Part 2: Current State of hiivmind-pulse-gh

The plugin is further along than its CLAUDE.md admits — the doc lists 4 skills;
there are 7 (`gh-discover`, `gh-heartbeat`, `gh-workflows` undocumented), plus
hooks, 13 workflow templates, and the poll-state machinery.

### Strengths to build on

- **The v2 pseudocode workflow format is the best asset in the ecosystem.**
  `state:` + `params:` + FSM-style `workflow:` blocks with a documented
  interpretation table (`ASK`/`SHOW`/`INFER`/`GOTO`/`STOP`/`INVOKE`) is a
  cleaner workflow definition than anything in corpus. It is the right
  substrate for goal 2.
- The heartbeat pipeline (SessionStart hook → poll-state diff → triggered
  workflows → pre-approved execution) is a real event architecture with
  cooldowns and per-source dedup.
- The lib/patterns + lib/references discipline matches corpus quality.
- **The config schema is already org-shaped** (see Part 3) — `workspace.login`,
  a `repositories[]` catalog, `milestones` keyed by repo, `relationships.yaml`
  with `repo_dependencies` and `cross_project_coordination`, `teams.yaml`, and
  `healthcheck.yaml` scoring multiple repos per run.

### Gaps against the reference architecture

| Capability | corpus / scheduler | pulse-gh today |
|---|---|---|
| Headless skill variants | 5 skills + `--headless` flags | None — all 7 skills assume a user present |
| Result contract + validator | Versioned schemas, `validate_result.py` | poll-state.yaml records only `last_run_at` / `last_result` / `run_count`; findings evaporate into conversation |
| Orchestration/ops separation | Scheduler repo; template + stubs; CALL_SKILL composition | Orchestration smeared across gh-heartbeat (poll + present + execute), gh-workflows (manage + run), and workflow-execution.md (three near-duplicate execution descriptions) |
| Deterministic Python | 14 scripts, PEP 723, tests | Zero Python — heartbeat.sh is ~300 lines of bash doing GraphQL + jq diffing; healthcheck evaluation is prose-driven |
| Multi-repo scope | Registry + per-corpus repos + fleet of stubs | Config data is org-shaped but conventionally parked inside one repo; no fleet execution, no cross-repo workflows |
| Run-state persistence | Result files per run | v2 workflow state exists "only for the duration of the workflow run — no persistence across sessions" (workflow-execution.md) |

---

## Part 3: Step 0 — The Workspace Root

**Decision: `.hiivmind/github/` lives in the parent folder of the org's
clones — a sibling to every repo — not inside any single repo.**

```
~/git/hiivmind/                      ← workspace root
├── .hiivmind/github/                ← workspace config, workflows, state, runs
├── hiivmind-pulse-gh/               ← repo clone
├── hiivmind-corpus/                 ← repo clone
├── hiivmind-corpus-scheduler/       ← repo clone
└── ...
```

This is a promotion, not a redesign:

- The config schema was never repo-shaped. Every workspace-level section
  (`repositories[]` catalog, per-repo `milestones`, `relationships.yaml`,
  `teams.yaml`, multi-repo `healthcheck.yaml`) already models the org.
- `workspace-detection.md` already documents the parent-directory search order
  and the "Multi-Repo Parent Directory" scenario (Example 2).
- `heartbeat.sh` and `gh-workflows` already check `../.hiivmind/github/`.

It also **supersedes the alternative** of designating an "orchestration repo":
cross-repo workflows, the run ledger, and fleet state get a home that is
sibling to every repo they orchestrate, with no arbitrary "which repo hosts the
release workflow?" question. Repos are reachable by relative path — the same
trick corpus-scheduler uses for its sibling symlinks.

What the placement resolves:

- **Goal 1 nearly falls out for free.** `repositories[]` *is* the fleet
  manifest. A scheduled maintenance task needs one constant (`WORKSPACE_PATH`).
  `healthcheck.yaml` already aggregates per-repo scores at exactly this level.
- **Goal 2 gets a coherent home.** Cross-repo release workflows live in
  `{workspace}/.hiivmind/github/workflows/`, run records in
  `{workspace}/.hiivmind/github/runs/`.
- **One heartbeat for the org** instead of N per-repo heartbeats re-polling
  overlapping state; the poll-state source-dedup logic becomes genuinely
  effective.

### 3.1 Required decisions

**D1 — The workspace is a git repo of its own ("workspace repo").**
The current premise "config.yaml committed to git, shared across team" breaks
when the parent folder isn't a repo. Resolution: initialize the workspace root
(or just its `.hiivmind/` directory) as a small git repository, with repo clone
directories ignored. **Resolved during P0: the workspace repo is rooted at
`.hiivmind/github/` itself (not the whole parent folder — avoids nested-clone
hazards and respects the multi-plugin `.hiivmind/` namespace); default remote
`{login}-workspace`, private.** This:

- restores team sharing and versioning for the human-authored assets
  (workflow definitions, healthcheck dismissals, `repo_dependencies`,
  cross-repo coordination docs);
- gives the scheduler something to branch/commit/PR against (the
  corpus-scheduler template assumes a git target);
- *is* the orchestration repo, reunified with the workspace.

Everything else in config is API-derivable cache — cattle, regenerated by
`gh-refresh`. The derivation DAG (Part 5.3) makes this split explicit.

**D2 — Layering rule: workspace base, repo overlay.**
Repo-level `.hiivmind/github/` remains legitimate (repo-specific workflows,
overrides). The current search order finds *nearest first and stops*; the
correct semantics are the opposite for context:

1. Resolve `workspace_root` by walking up from cwd to the first directory
   containing `.hiivmind/github/config.yaml` **with a `workspace:` section**.
2. Workspace config is the base layer (workspace identity, catalogs, teams,
   relationships, org-wide workflows, poll-state, runs).
3. A repo-level `.hiivmind/github/` is an optional overlay: repo-scoped
   workflows and setting overrides. It never carries workspace identity.
4. Precedence for scalar conflicts: repo overlay wins within its repo's scope.

Document this in `workspace-detection.md` as the normative resolution
algorithm; all skills and hooks use it.

**D3 — Hook must walk up; heartbeat scope is filtered by default.**
`heartbeat.sh` currently checks exactly two levels (`.` and `..`). That works
when a session starts at a repo root directly under the workspace, and fails
anywhere deeper. Replace with the full `find_config` walk-up. Sessions inside
repo X get an X-filtered slice of the org heartbeat by default, with the org
summary offered as a follow-up (`/gh org status`).

**D4 — Headless never discovers; interactive may.**
In CI or a scheduled runtime, a single repo is checked out and no parent
workspace exists. Every headless skill therefore takes explicit
`workspace_path` / `repo` inputs (corpus convention). Directory discovery is an
interactive-only convenience.

### 3.2 Workspace directory layout (target)

```
{workspace}/.hiivmind/github/
├── config.yaml            # workspace identity + catalogs (committed; cache sections regenerable)
├── freshness.yaml         # per-section staleness (committed)
├── user.yaml              # personal (gitignored)
├── poll-state.yaml        # trigger/cooldown bookkeeping (gitignored — derived)
├── project-snapshot.json  # BRONZE snapshot (gitignored — derived)
├── workflows/             # workspace + cross-repo workflow definitions (committed)
├── runs/                  # run ledger: {workflow}-{run_id}.yaml (committed or gitignored — see 6.2)
├── views/  repos/  automations/  teams.yaml  relationships.yaml  healthcheck.yaml
├── *-result.yaml          # headless result files (gitignored, transient)
└── log/
```

### 3.3 Multi-machine, multi-actor topology

The companion catalog spec's invariants I1–I6 (§2.5 there) constrain this
platform; the load-bearing consequence for Part 3 is:

**The workspace root is a per-machine instance of a shared workspace repo.**
The team is M:M across individuals, GitHub profiles, and physical machines —
each machine's parent folder holds its own clone of the workspace repo (D1)
and its own set of repo clones, possibly at different states. Therefore:

- **Shared vs. per-machine split (I2):** committed workspace-repo content
  (config catalogs, workflow definitions, dismissals, run ledger, binding
  markers) is the *only* shared state. `poll-state.yaml`, snapshots, and
  result files are per-machine advisory caches — two machines legitimately
  hold different poll-state.
- **Pull-before-reconcile (I2):** any run that reads or writes shared
  markers pulls the workspace repo first; local caches are never authority.
- **Cooldowns are per-machine (I3):** poll-state cooldown bookkeeping cannot
  enforce a global rate across machines. Global correctness comes from
  idempotent runs plus the supersede pattern (Part 6.2), not from cooldowns
  — cooldowns are a politeness optimization only.
- **Actor attribution (I4):** every run records human, GitHub profile
  (`gh auth` identity), and machine — in run records and result files
  (Part 5.1). Identity-sensitive workflow logic ("you touched this",
  self-assignment) resolves against the recorded actor, not against
  whatever profile the current machine happens to hold.
- **Local clones are never sync sources (I6):** skills read pushed commits
  and API state; a dirty or unpushed repo clone is surfaced as a finding,
  not consumed.

---

## Part 4: Headless Skills

Straight port of the corpus pattern. Each headless skill: `inputs:` frontmatter
(explicit paths), State block, numbered phases with declared outputs,
ABORT-still-emits-result, result file gitignored, no prompts.

Priority order (by value toward goal 1):

| Skill | Result file | Purpose |
|---|---|---|
| `gh-status-headless` | `status-result.yaml` | Cheap pre-check: config freshness + poll snapshot → `refresh_needed: bool`. What a scheduler gates on. Analog of corpus `status-headless`. |
| `gh-healthcheck-headless` | `healthcheck-result.yaml` | The 11-check catalog (`healthcheck-checks.md`) per repo or per fleet, honoring dismissals in `healthcheck.yaml`. The core multi-repo diagnostic. |
| `gh-refresh-headless` | `refresh-result.yaml` | Sync config catalogs with GitHub, no prompts. |
| `gh-workflow-run-headless` | `workflow-run-result.yaml` | Run a v2 workflow non-interactively under its headless policy (Part 6.1). |

Interactive skills stay as-is; where an interactive skill makes choices a
headless run must replay (e.g., which checks to evaluate, which repos are in
scope), record them in config — the pulse analog of corpus `config.build`
decision capture.

---

## Part 5: Contracts, Metadata, and Status

### 5.1 `lib/patterns/headless-contract.md` (new)

Port the corpus pattern with `contract_version: 1` and kinds `status`,
`healthcheck`, `refresh`, `workflow-run`. Rules identical to corpus:
orchestrators read the file, validate before consuming, treat as consumed after
parse; skills ensure gitignore coverage; additive optional fields don't bump
the version.

The central schema-design decision: **findings are typed data, not prose.**

```yaml
contract_version: 1
kind: workflow-run
workflow: ci-monitor
workspace: hiivmind
repos: [hiivmind/hiivmind-pulse-gh]
run_id: 2026-07-10-a3f
run_at: 2026-07-10T09:00:00Z
actor:                             # required on ALL kinds (I4 — M:M actors/profiles/machines)
  gh_login: nathanielramm
  machine: mba-m4
  mode: interactive | scheduled
outcome: success | failure | skipped-cooldown | aborted
findings:
  - kind: ci-failure
    repo: hiivmind/hiivmind-pulse-gh
    ref: { type: run, id: 12345, url: ... }
    severity: high
    classification: flaky          # INFER output
    inferred: true                 # LLM judgment flagged as such
proposed_actions: []               # mutations a headless run declined to take
asks_recorded: []                  # ASK statements that had no user (see 6.1)
errors: []
```

`healthcheck` kind mirrors the existing `healthcheck.yaml` per-check shape
(`pass | warn | fail | unknown | dismissed` + detail + data) so the result file
and the committed governance record stay structurally aligned.

`inferred: true` and `asks_recorded` are the pulse analog of corpus
`new_concept_candidates`: the only items needing human judgment, called out
explicitly for the reviewer.

### 5.2 Two-tier state separation

`poll-state.yaml` shrinks to trigger/cooldown bookkeeping plus a pointer to the
latest run record. Rich per-run outcomes move to the run ledger
(`runs/{workflow}-{run_id}.yaml`) and transient result files. This fixes the
current situation where workflow findings are recorded as a single
`success|failure|skipped` enum.

### 5.3 `lib/patterns/derivation-dag.md` (new)

Declare sources of truth vs. derived artifacts:

- **Sources of truth (committed):** workflow definitions, healthcheck
  dismissals, `repo_dependencies`, cross-project coordination, workspace
  identity.
- **Derived cache (regenerable, committed for team benefit):** catalogs in
  config.yaml, views/, repos/, teams.yaml, automations/.
- **Derived transient (gitignored):** poll-state, snapshots, `*-result.yaml`,
  logs.

### 5.4 CLAUDE.md alignment

CLAUDE.md is materially stale (3 undocumented skills, hooks, workflow system,
poll-state). Update it and add a corpus-style **cross-cutting concerns table**
(workflow format v1/v2, headless contract, workspace-root resolution, poll
sources, pre-approval semantics → which skills/patterns each touches).

---

## Part 6: Composable Orchestration

### 6.1 In-plugin: split executor from presenter

gh-heartbeat currently does polling, presentation, execution, and next-step
suggestion; gh-workflows and workflow-execution.md re-describe execution twice
more. Extract **one executor** (load workflow → resolve params → follow FSM →
write result file) callable by heartbeat, `gh-workflows run`, and any
scheduler. Heartbeat becomes: obtain poll JSON → present → select → delegate to
executor → summarize from result files.

**Headless projection of v2 workflows.** The FSM format is interactive by
design (`ASK` everywhere). Rather than forking every template, one definition
serves both modes via a per-workflow policy block:

```yaml
headless:
  enabled: true
  on_ask: record        # record | default | abort — ASK becomes an asks_recorded finding
  on_mutation: propose  # propose | allow-listed | allow — mutations become proposed_actions
  mutation_allowlist: [comment, label]   # when allow-listed
```

Unanswerable ASKs and withheld mutations surface as structured findings in the
result file — the run completes and reports instead of blocking. This is
decision-capture applied to approvals: headless runs **replay policy** instead
of guessing.

### 6.2 Out-of-plugin: `hiivmind-pulse-scheduler`

New repo mirroring corpus-scheduler:

- One `TEMPLATE-workspace-maintenance.md` composing:
  `gh-status-headless` (pre-check, optimization-never-gate) →
  `gh-refresh-headless` → `gh-healthcheck-headless` (fleet iteration over
  `repositories[]`) → commit/PR against the **workspace repo** (D1) with the
  corpus template's superseded-PR cleanup.
- Thin stubs supplying `WORKSPACE_PATH`, `WORKSPACE_REPO`, `BRANCH_PREFIX`.
  Because the workspace *is* the fleet, one stub covers the org; per-repo stubs
  exist only for repos needing distinct schedules or policies.
- The template writes an **aggregated fleet report** (roll-up of per-repo
  result files) into the PR body: grades per repo, deltas since last run,
  `asks_recorded` / `proposed_actions` called out as the human-judgment items.

### 6.3 Workflow schema v3 (goal 2)

The largest new design, with no corpus precedent to copy. Additions to the v2
format, all backward-compatible:

- **`repos:` scope** — a workflow declares the repos it spans (names resolve
  through the workspace catalog; `depends_on` context available from
  `relationships.yaml`).
- **`steps:` with `depends_on:` and gates** — for release orchestration the
  flat FSM gains a DAG layer: steps bound to repos, each step itself a v2-style
  phase block, with cross-repo gates expressible as conditions
  (e.g., `gate: repo-a release published AND repo-b checks green on main`).
- **Run ledger** — `runs/{workflow}-{run_id}.yaml` capturing params, per-step
  status (`pending | running | blocked-on-gate | done | failed | skipped`),
  state snapshot, timestamps, and the **actor per step** (I4). Workflows
  become **resumable**: a new session (or scheduled run) picks up a run in
  `blocked-on-gate`, re-evaluates gates, and continues. This directly fixes
  the "no persistence across sessions" limitation and is the "improved
  statuses" ask. Multi-machine rules (Part 3.3): `run_id` embeds the actor
  (`{date}-{gh_login}-{n}`) so two machines can't mint colliding records;
  the ledger lives in the workspace repo, so resuming a run means pulling
  first; a step may carry a **soft lease** (`leased_by`, `leased_at`) so
  concurrent sessions avoid duplicating work, but leases are advisory —
  expired leases are stolen, and step application must be idempotent (I3).
- Gates are natural poll targets: the heartbeat can watch `runs/` for
  gate-blocked runs and re-evaluate their gates as part of the session poll —
  releases advance as a side effect of normal session starts, and scheduled
  runs advance them unattended.

Example sketch:

```yaml
name: release-train
repos: [hiivmind-corpus, hiivmind-corpus-scheduler, hiivmind-pulse-gh]
params:
  version: { type: string, default: null }   # required
steps:
  - id: tag-lib
    repo: hiivmind-corpus
    workflow: |
      EXECUTE: create release {params.version} on hiivmind-corpus
  - id: verify-lib
    repo: hiivmind-corpus
    depends_on: [tag-lib]
    gate: release {params.version} published AND checks green on main
  - id: bump-consumers
    repo: [hiivmind-corpus-scheduler, hiivmind-pulse-gh]
    depends_on: [verify-lib]
    workflow: |
      GATHER: open PR bumping corpus dependency to {params.version}
      ...
```

---

## Part 7: Deterministic Python

Create `lib/pulse/scripts/` with corpus conventions copied exactly: PEP 723
inline metadata, `uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/<script>.py`,
pyproject + tests.

| Script | Replaces / enables |
|---|---|
| `validate_result.py` | Port from corpus; kinds `status`, `healthcheck`, `refresh`, `workflow-run`. Foundation for everything. |
| `poll.py` | Extracts heartbeat.sh's GraphQL + jq diffing. The lakehouse plan (`docs/polymorphic-giggling-bentley.md`, RAW→BRONZE→SILVER→GOLD) is precisely a deterministic-Python job: one batched query → full snapshot → derived views → change-set. The hook becomes a thin wrapper. |
| `evaluate_checks.py` | The mechanical healthcheck checks (protection present, required files, label taxonomy, merge settings) are pure data comparisons against `repos/*.yaml` + live API. LLM judgment retained only for checks that need it, flagged `inferred`. |
| `workflow_lint.py` | Validate workflow YAML: v2/v3 schema, state/params referenced by the FSM, phase labels resolvable, headless policy well-formed, step DAG acyclic. Run as a PR check on the workspace repo (analog of `graph --headless`). |
| `resolve_run.py` | Run-ledger helpers: create/advance/gate-evaluate run records deterministically so the LLM never hand-edits ledger YAML. |

---

## Part 8: Phased Delivery Plan

Ordering principle: contracts before consumers — the order the corpus work
landed in. Each phase lists its deliverables, hard dependencies, and exit
criteria. A phase is **done** only when its exit criteria are verified, its
deliverables are merged, and the progress table (8.9) is updated in this spec.

### Dependency graph

```
P0 workspace root
 ├──► P1 contract + validator ──► P3 headless skills ──► P5 scheduler   (goal 1)
 │            │                        ▲
 ├──► P2 python extraction ────────────┘
 │            │
 └──► P4 executor split + headless policy ──► P6 workflow v3            (goal 2)
                                                   ▲
P1 ────────────────────────────────────────────────┘
P7 housekeeping (rolls up: after P0 minimum, finalized after P6)
```

Parallelizable: P1 ∥ P2 (both depend only on P0); P4 ∥ P3 (P4 needs P1, not
P2/P3); P5 and P6 are independent of each other.

### P0 — Workspace root formalization

**Depends on:** nothing (blocks everything).
**Decisions closed in this phase:** D1 (workspace repo layout: root vs
`.hiivmind/`-only), D2 (layering), D3 (heartbeat scope), plus the risk items
"workspace repo hygiene" and "heartbeat scope" from Part 9.

Deliverables:

- [x] P0.1 `workspace-detection.md` rewritten: normative `workspace_root`
      resolution algorithm (walk-up, `workspace:` section marker), D2 layering
      rule (workspace base, repo overlay), D4 explicit-inputs rule stated as a
      convention for all future headless skills.
- [x] P0.2 `heartbeat.sh` config discovery replaced with the full walk-up;
      two-level check removed. Scope behavior per D3 decision.
- [x] P0.3 Workspace repo initialized (per D1): gitignore strategy
      implemented, `.hiivmind/github/` migrated from this repo's copy,
      derivation split applied (committed vs gitignored per Part 3.2 layout).
- [x] P0.4 `gh-init` updated: offers workspace-root placement as the default
      for multi-repo parents; repo-local placement demoted to overlay case.
- [x] P0.5 Multi-machine topology (Part 3.3) documented in
      `workspace-detection.md`: shared vs per-machine state split,
      pull-before-reconcile rule, cooldowns-are-advisory.

Exit criteria: a session started in any subdirectory of any repo under
`~/git/hiivmind/` resolves the same `workspace_root` and heartbeat runs
against it; `gh-init` on a fresh parent folder produces the Part 3.2 layout.

### P1 — Result contract + validator

**Depends on:** P0 (result-file paths key off `workspace_root`).

Deliverables:

- [x] P1.1 `lib/patterns/headless-contract.md` — kinds `status`,
      `healthcheck`, `refresh`, `workflow-run`; `contract_version: 1`;
      required `actor:` block on all kinds (Part 3.3 / I4);
      gitignore + consumption rules ported from corpus.
- [x] P1.2 `lib/pulse/scripts/validate_result.py` (PEP 723, `uv run`) with
      exit codes 0/1/2; pyproject + tests scaffolded (first Python in repo —
      copy corpus `pyproject.toml` conventions).
- [x] P1.3 Schema fixtures: one valid + one invalid example per kind, used by
      tests.

Exit criteria: `uv run .../validate_result.py <fixture> --kind <k>` passes/
fails correctly for all eight fixtures in CI-runnable tests.

### P2 — Deterministic Python extraction

**Depends on:** P0 (paths); P1.2 for shared pyproject/test scaffolding
(soft — can start in parallel once scaffolding exists).

Deliverables:

- [x] P2.1 `poll.py`: heartbeat GraphQL + diff logic extracted; implements the
      lakehouse plan (RAW→BRONZE `project-snapshot.json`→SILVER poll-state
      →GOLD changeset JSON). Includes the shared rate-limit pre-check.
- [x] P2.2 `heartbeat.sh` reduced to a thin wrapper invoking `poll.py`;
      output JSON contract to gh-heartbeat unchanged (no skill edits needed).
- [x] P2.3 `evaluate_checks.py`: mechanical healthcheck checks as pure data
      comparisons; emits per-check results in the `healthcheck` kind's shape;
      LLM-judgment checks explicitly listed as out of scope and flagged
      `inferred` by the calling skill.
- [x] P2.4 Tests for both scripts against recorded API fixtures.

Exit criteria: heartbeat output byte-compatible (same JSON keys) with the bash
implementation on the same inputs; `evaluate_checks.py` reproduces the current
check catalog's mechanical subset on a fixture repo.

### P3 — Headless skills

**Depends on:** P1 (contract), P2 (P3.2 needs `evaluate_checks.py`; P3.1
needs `poll.py`'s rate-limit/status helpers).

Deliverables (each: `inputs:` frontmatter, State block, ABORT-emits-result,
result gitignored, zero prompts):

- [x] P3.1 `gh-status-headless` → `status-result.yaml` (`refresh_needed`).
- [x] P3.2 `gh-healthcheck-headless` → `healthcheck-result.yaml`; iterates
      `repositories[]` or a passed repo filter; honors dismissals; updates
      committed `healthcheck.yaml`.
- [x] P3.3 `gh-refresh-headless` → `refresh-result.yaml`; replays recorded
      init/refresh decisions (decision-capture fields added to config where
      needed).

Exit criteria: each skill run end-to-end against the live hiivmind workspace
produces a result file that passes `validate_result.py`; a deliberately broken
input still yields a valid result file with `errors[]` populated.

### P4 — Workflow executor split + headless policy

**Depends on:** P1 (workflow-run contract). Independent of P2/P3.

Deliverables:

- [x] P4.1 Single executor pattern: `workflow-execution.md` becomes the one
      normative execution description; gh-heartbeat §4/§5 and gh-workflows
      "Run" reduced to delegation stubs referencing it.
- [x] P4.2 `headless:` policy block added to the workflow schema
      (`on_ask`, `on_mutation`, `mutation_allowlist`); documented in
      `workflow-execution.md`; `operation-blocklist.md` declared
      unconditional in headless mode.
- [x] P4.3 `gh-workflow-run-headless` → `workflow-run-result.yaml` with
      `findings` / `proposed_actions` / `asks_recorded`.
- [x] P4.4 Two shipped templates annotated with `headless:` blocks as
      reference implementations (suggest: repo-healthcheck, stale-check).

Exit criteria: the same workflow YAML runs interactively (ASKs prompt) and
headlessly (ASKs recorded, mutations proposed) with no definition changes;
headless run of stale-check on this workspace yields a valid result file.

### P5 — hiivmind-pulse-scheduler  ▸ **completes goal 1**

**Depends on:** P3 (skills it composes), P4.3 (only if scheduled workflow
runs are in scope for v1 of the template — otherwise P3 alone).

Deliverables:

- [x] P5.1 New repo `hiivmind-pulse-scheduler`: CLAUDE.md, symlink deployment
      docs (copy corpus-scheduler conventions).
- [x] P5.2 `TEMPLATE-workspace-maintenance.md`: status pre-check
      (optimization-never-gate) → refresh → fleet healthcheck → commit/PR to
      workspace repo, with superseded-PR cleanup.
- [x] P5.3 One stub (`workspace-maintenance-hiivmind/`) with
      `WORKSPACE_PATH` / `WORKSPACE_REPO` / `BRANCH_PREFIX`; symlinked into
      `~/.claude/scheduled-tasks/`.
- [x] P5.4 Fleet report format in the PR body: per-repo grades + deltas,
      `asks_recorded` / `proposed_actions` under a "Needs attention" heading.

Exit criteria: one unattended scheduled run against the hiivmind workspace
produces a PR on the workspace repo containing the fleet report; a second run
with no upstream changes exits at the pre-check without a PR.

### P6 — Workflow schema v3  ▸ **completes goal 2**

**Depends on:** P4 (executor + policy). P6.1–P6.2 have no dependency on P5.
Sub-phased because the run ledger is independently useful:

- [x] P6.1 Run ledger: `runs/{workflow}-{run_id}.yaml` schema; executor writes
      it for every run; committed-vs-transient split per Part 9 decision.
- [x] P6.2 `resolve_run.py`: create/advance/gate-evaluate ledger records
      deterministically; tests.
- [x] P6.3 Schema v3: `repos:` scope + `steps:`/`depends_on:`/`gate:`;
      documented in `workflow-execution.md`; `workflow_lint.py` extended for
      DAG acyclicity and gate syntax.
- [x] P6.4 Resumability: executor picks up `blocked-on-gate` runs,
      re-evaluates gates, continues; heartbeat watches `runs/` for
      gate-blocked runs as a poll source.
- [ ] P6.5 Reference workflow: `release-train.yaml` for the corpus →
      scheduler → pulse-gh dependency chain, exercised end-to-end on a real
      minor release.

Exit criteria: a release-train run started in one session, blocked on a gate,
is resumed and completed by a later session (or scheduled run) with the ledger
showing the full step history.

### P7 — Housekeeping (continuous, finalized after P6)

**Depends on:** P0 minimum; items land alongside the phase that makes them
true, final pass after P6.

- [ ] P7.1 CLAUDE.md rewrite: 7 skills, hooks, workflow system, workspace
      root, Python scripts. (Stale-skills interim fix landed with P1; full
      rewrite after P6.)
- [ ] P7.2 Cross-cutting concerns table in CLAUDE.md.
- [ ] P7.3 `lib/patterns/derivation-dag.md`.
- [ ] P7.4 `workflow_lint.py` v1 (schema + FSM references + headless policy)
      as a workspace-repo PR check — deliverable after P4, extended in P6.3.

### 8.9 Progress tracking

Single source of truth for status is **this table**; the per-phase checkboxes
above track deliverables within a phase. Update both in the same commit as the
work. Status values: `not-started | in-progress | blocked({on}) | done`.

| Phase | Title | Depends on | Status | Completed |
|-------|-------|------------|--------|-----------|
| P0 | Workspace root formalization | — | ✅ done | 2026-07-10 |
| P1 | Result contract + validator | P0 | ✅ done | 2026-07-10 |
| P2 | Python extraction (poll, checks) | P0 | ✅ done | 2026-07-11 |
| P3 | Headless skills (status/healthcheck/refresh) | P1, P2 | ✅ done | 2026-07-11 |
| P4 | Executor split + headless policy | P1 | ✅ done | 2026-07-11 |
| P5 | pulse-scheduler + fleet report **(goal 1)** | P3 (opt. P4.3) | ✅ done | 2026-07-12 |
| P6 | Workflow v3: ledger, steps, gates **(goal 2)** | P4 | in-progress (P6.5 pending live release) | |
| P7 | Housekeeping (CLAUDE.md, DAG doc, lint) | P0+ (final: P6) | not-started | |

## Part 9: Risks and open questions

- **Workspace repo hygiene (D1):** a git repo whose working tree contains
  other git clones requires a disciplined `.gitignore` (ignore-all +
  whitelist `.hiivmind/`). Alternative: make only `.hiivmind/` the repo.
  Decide during step 0.
- **Runs ledger committed vs. gitignored:** committed gives the team a shared
  release-state view (recommended for v3 cross-repo runs); gitignored keeps
  noise down for personal workflow runs. Suggested split: cross-repo runs
  committed, single-repo runs transient.
- **Heartbeat scope (D3):** filtered-per-repo default needs a `repo:` filter
  concept in poll sources that doesn't exist yet; org-wide-always is simpler
  and may be acceptable for small orgs. Decide at step 0, revisit at step 4.
- **Mutation safety headless:** `on_mutation: propose` must be the default;
  `allow` should require the allowlist. The existing
  `operation-blocklist.md` applies unconditionally in headless mode.
- **Rate limits:** an org-wide heartbeat plus scheduled fleet healthchecks
  multiplies API calls; the heartbeat's existing rate-limit skip guard should
  become a shared pre-check in `poll.py` honored by all headless skills.
  Multiplied further by M:M — every teammate's machine polls independently
  and per-machine cooldowns don't coordinate (Part 3.3); if this bites,
  the mitigation is committing a coarse last-fleet-sweep marker to the
  workspace repo, not distributed locking.
- **Concurrent mutation races:** idempotence + supersede covers marker/PR
  writes, but direct API mutations from two simultaneous runs (e.g. both
  commenting on the same issue) can duplicate. Mutating workflows should
  check-before-write (does an equivalent comment/issue already exist?) —
  cheap because idempotence is already required by I3.
- **Repos not cloned locally:** the fleet catalog may list repos with no local
  clone; healthcheck-headless works API-only, but release workflows requiring
  local git need a `clone-on-demand` decision (corpus clones into `.source/`;
  the analog here would be cloning into the workspace root, which is exactly
  where a clone belongs).
