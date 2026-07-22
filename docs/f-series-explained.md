# The F-Series, Explained

A guided reference to the heterogeneous fleet-management program that hiivmind-pulse-gh
implements — **what** each phase is for (what it looks at, what it detects, what risk it
mitigates) and **how** it works (skill, Python, Nave, config, persisted evidence).

For the architecture *health* of this program — which phases are actually runnable in
production — see the companion audit `docs/superpowers/audits/2026-07-22-f-series-runnable-spine-audit.md`
and the remediation plan `docs/superpowers/plans/2026-07-22-f10-runnable-spine.md`. This
document explains what the phases *do*; the audit explains what currently *runs*.

---

## 1. The system in one paragraph

hiivmind-pulse-gh is a **general GitHub multi-repo fleet manager**. It looks at a
workspace of many repositories, decides what each repository *is* (its profile), scores
each against the scorecard for that profile, watches cross-repo dependency edges for
drift, and proposes safe, guarded changes — GitHub-object changes through the `gh` API and
repository-file changes through Nave pen workspaces. Everything it changes it proposes for
review first; nothing about a repository's language or layout is assumed.

### The Pulse / Nave split

- **Pulse** (this plugin) owns orchestration, repository **profiles**, **scorecards**,
  GitHub mutations, cross-repo **bindings**, and the **result contract**.
- **Nave** (an external CLI, consumed as versioned normalized JSON) owns fleet
  projection, structural **evidence**, schema checks, and **pen** workspaces — the
  transaction boundary for repository-file changes. Pulse never reads Nave's cache
  internals; it consumes only Nave's documented JSON and supports a fixture mode.

### Five invariants that run through every phase

1. **Authoritative intent, not inference.** A repository's profile is *reviewed workspace
   metadata*. Detection may only ever emit a `profile_proposal` — it never silently
   reclassifies a repository.
2. **Typed result states.** Every check is `pass | warn | fail | unknown | not_applicable
   | unsupported | error`. `not_applicable`/`unsupported` are excluded from the score
   denominator; `unsupported` is counted as *coverage debt*, never silently skipped.
3. **Fail-closed.** A missing baseline, an unreadable file, an unparseable document → the
   phase degrades to `unknown`/`blocked`, never a fabricated pass or a guessed value.
4. **Propose-only by default.** Mutations are created and validated locally; pushing/
   applying is a separate, gated step. Repository-file writes happen only inside Nave
   pens; GitHub-object writes stay Pulse-owned.
5. **Guarded, idempotent advancement.** Every marker/base advance is guarded by an
   expected SHA (or blob) and is a no-op on repeat — concurrent runs cannot race a marker
   forward.

### The three layers (how to read each phase's "How")

Every phase is built from a **library** (pure, tested Python), a **driver** (a runnable
CLI that assembles inputs and writes a result), and a **skill** (`SKILL.md` orchestration).
The read/score phases have all three; the propose/mutate phases (F6–F9) are missing the
driver layer today — that is exactly what F10 adds. Where a phase's driver is missing, the
"How" below says so.

### Quick map

| Phase | Core Python | Config it reads | Evidence it persists | Nave? |
|---|---|---|---|---|
| F0 | `evidence_snapshot`, `nave_adapter` | fleet projection | F0 evidence snapshot (files, capabilities) | ✅ projection/structure |
| F1 | `profile_dispatch` | `profiles.yaml` scorecards/adapters | — (resolves a plan) | — |
| F2 | `fleet_membership`, `profile_proposals` | `profiles.yaml` `repository_profiles` | reviewed profile metadata | — |
| F3 | `healthcheck_dispatch` | `profiles.yaml` | `healthcheck.yaml` governance record | — |
| Pre-F4 | `dependency_evidence`, `validate_dependency_evidence` | dependency-evidence contract | materialized manifest/lock contents | ✅ `materialize_json` |
| F4 | *(deferred — not built)* | — | — | — |
| F5 | `impact`, `impact_snapshot` | `relationships.yaml` edges | `integration_tested_sha` markers | optional path evidence |
| F6 | `mutation_plan`, `pen_orchestrator` | `transformations.yaml` registry | `repo-mutation` result | ✅ pens |
| F7 | `generated_artifacts`, `generator_dispatch`, `contract_versions` | `generated.yaml`, `generators.yaml`, contract edges | template-tree/blob bases | ✅ pens (regen) |
| F8 | `plan_sync`, `plan_sync_snapshot`, `apply_doc_patch` | doc frontmatter `sync:` block | per-field reconciliation bases | ✅ pen (doc patch) |
| F9 | `marketplace_sync`, `adapters/claude_plugin`, `repo_claims` | `claude-plugin-v1` scorecard, `marketplace-sync.yaml` | overlay subtotals | ✅ pen (regen) |

---

## 2. The read / score spine

### F0 — Nave CLI evidence

**Goal.** Establish one authoritative evidence boundary for the fleet and remove
duplicated fetching.

**What it looks at.** The fleet projection and per-repository structural facts Nave
reports — the file list and capability signals for each repository.

**What it detects.** Which repositories exist in the fleet; each repository's structural
shape (does it have workflows, a README, the files a later check will key on).

**Risk it mitigates.** Every later phase inventing its own repo-fetching path; coupling
Pulse to Nave's cache internals; unpredictable failure when Nave is absent.

**How.** `evidence_snapshot.py` (CLI) drives `nave_adapter.py`, which shells the Nave CLI
(`search`/`build`/`check --json`) and normalizes the output to a versioned JSON contract;
a fixture mode substitutes recorded JSON. The persisted artifact is the **F0 evidence
snapshot** — a `{repos: [{repo, files, capabilities, …}]}` structure that F1/F3/F5/F9 all
consume. Deliberately **content-free**: it carries file *paths*, never file *bytes* (the
content channel is a bounded, phase-specific concern — see Pre-F4 and F9). Skill:
`gh-fleet-evidence-headless`.

### F1 — Profiles, scorecards, applicability

**Goal.** Make each repository's *intent* explicit before anything is scored.

**What it looks at.** The authoritative `repository_profiles` map plus the scorecard
catalog in `templates/profiles.yaml.template`.

**What it detects.** Which **scorecard** governs a repository (`generic-v1`,
`python-library-v1`, `claude-plugin-v1`, …), and for each check whether it is applicable
(`always`, `profile:<id>`, `capability:<id>`, `evidence_path:<glob>`), `not_applicable`,
or `unsupported` (adapter not implemented).

**Risk it mitigates.** Running language- or plugin-specific checks against repositories
that aren't those things; conflating "check failed" with "check doesn't apply here".

**How.** `profile_dispatch.py` (library) resolves a scorecard (with inheritance via
`extends`) into a `DispatchPlan` of `PlannedCheck`s, each carrying an adapter id, weight,
and applicability state. Pure — no I/O; it turns config + evidence into a plan the
dispatcher executes.

### F2 — Fleet membership and profile proposals

**Goal.** Keep fleet scope honest and assign *reviewed* intent metadata.

**What it looks at.** The set of repositories in the workspace versus the
`repository_profiles` already recorded; evidence signals (`proposal_rules`) that suggest a
profile.

**What it detects.** Repositories in/out of the managed fleet; **candidate** profiles for
unclassified repositories (e.g. `pyproject.toml` → `python`, `.claude-plugin/plugin.json`
+ `skills/*/SKILL.md` → `claude-plugin`), each emitted as a `profile_proposal` with a
confidence and the evidence that triggered it.

**Risk it mitigates.** Scope creep (untracked repos silently ignored or silently
managed); auto-classification that changes behaviour without a human reviewing the intent.

**How.** `fleet_membership.py` + `profile_proposals.py` (CLIs). Proposals are output;
they become authoritative only when merged into `repository_profiles` as a reviewed
workspace commit. Skill: `gh-fleet-membership-headless`.

### F3 — Dispatched healthcheck and coverage

**Goal.** Prove generic top-level dispatch across a heterogeneous fleet without any
language assumption, and report coverage honestly.

**What it looks at.** The F0 evidence for every profiled repository, run through that
repository's resolved scorecard.

**What it detects.** Per-repository weighted **grade** (A–F), and fleet **coverage debt**
— the weight of checks that are `unsupported` because their adapter isn't implemented.

**Risk it mitigates.** A fleet report that mixes scorecard populations (a docs repo's
"grade" averaged against a service's); silent gaps where an unimplemented check is dropped
rather than surfaced as debt.

**How.** `healthcheck_dispatch.py` (CLI) is the read-spine's orchestrator:
`--evidence <F0 snapshot> --profiles <config> --workspace <path>`. It registers the
universal adapters, dispatches each repo's plan, evaluates each applicable check through
`AdapterRegistry`, and aggregates **by scorecard** (never mixing populations). The
persisted artifact is the governance record `templates/healthcheck.yaml.template`
(`last_run.by_scorecard`, `coverage`, durable per-repo/check records, and `dismissals`).
Skill: `gh-healthcheck-headless`. *(Note: this dispatcher registers only the universal
adapters today — the F9 overlay is not wired in; F10 Task 4 fixes that.)*

### Pre-F4 — Nave dependency evidence

**Goal.** Give dependency checks authoritative, **bounded** file contents without exposing
Nave cache internals or re-fetching from GitHub.

**What it looks at.** The dependency manifests and locks Nave can materialize (Python and,
per Nave's tracked paths, pre-commit/Dependabot/Actions; arbitrary Node/docs are not yet
covered).

**What it detects.** The exact, current contents of those files at a pinned point — the
raw material a coherence check would compare.

**Risk it mitigates.** Reading Nave's private cache; duplicating GitHub retrieval;
unbounded content pulls.

**How.** Nave protocol-v2 `materialize_json` exposes the bytes; `nave_adapter.py`
consumes it; `dependency_evidence.py` shapes it and `validate_dependency_evidence.py`
gates the contract. Persisted as materialized manifest/lock content keyed to a repo/ref.
This is code-complete; the remaining task is releasing Nave and pinning its minimum
version.

### F4 — Dependency-coherence adapters *(deferred — not built)*

**Intended goal.** The first language-*dispatched* workflow: consume Pre-F4's materialized
manifests/locks and check dependency coherence per ecosystem (Python `pyproject`/`uv.lock`,
Node `package.json`), surfacing unsupported ecosystems as coverage debt rather than false
failures.

**Status.** Pre-F4 (the evidence) merged; **F4 (the adapters that would consume it) was
never implemented.** The `dependency-updates` check therefore reports `unsupported` /
"not implemented." This is an open read-spine gap, independent of the F6–F9 driver gap.

---

## 3. The propose / mutate spine

These phases decide *what should change* and record guarded, propose-only proposals. They
share the mutation machinery (F6) and the binding conventions (F5). All four currently
lack a runnable driver — their skills describe the orchestration but cite library function
signatures rather than shelling a CLI, so a headless run requires improvised glue (see the
audit; F10 supplies the drivers).

### F5 — Generic impact bindings and branch currency

**Goal.** Detect path-scoped upstream drift beyond each dependency edge's last validated
commit — language-independent integration currency.

**What it looks at.** Object-shaped relationship **edges**
(`templates/relationships.yaml.template`): `{repo, watch_paths, watch_branch,
integration_tested_sha, tested_at, integration_workflow}`. The currency test is
`git diff integration_tested_sha..remote_head -- watch_paths`.

**What it detects.** Edges gone **stale** — an upstream dependency has changed files under
the watched paths since the last SHA the dependent was validated against. Missing or
unreachable baselines **block closed** (never silently pass).

**Risk it mitigates.** Silent integration drift; cutting a release against a dependency
that moved under you; markers racing forward under concurrency.

**How.** `impact.py` (`audit`, `mark`) is pure; `impact_snapshot.py` collects remote
evidence (`git ls-remote` / bare fetch, `FETCH_HEAD` discipline, argv-guarded).
`poll.py`'s `branch_heads` source is trigger-only — it notices an upstream head moved and
wakes the workflow; it never diffs content itself. The persisted artifact is the
committed `integration_tested_sha` marker, advanced only by expected-base-guarded,
idempotent patches, and only from evidence of the edge's configured `integration_workflow`
succeeding. Skill: `gh-impact-audit-headless`. Also contributes a `binding_edges_current`
release gate.

### F6 — Nave pen mutation orchestration

**Goal.** Route every repository-file change through a Nave pen with freshness,
cleanliness, validation, attribution, and mutation-policy gates.

**What it looks at.** A typed **mutation proposal** (`{id, selection, transformation,
expected_shas, mutation_policy, actor}`) and the **transformation registry**
(`templates/transformations.yaml.template`: `{id, command_argv, applies_to, validation,
allow_scheduled}`).

**What it detects / enforces.** Stale pens (remote moved since selection) and dirty pens
block *before* execution; schema validation gates the result; a forbidden push is
refused; `allow_scheduled: false` transformations are refused for scheduled actors. Only
**registered** transformation IDs run automatically; arbitrary `nave pen exec` commands
are user-gated.

**Risk it mitigates.** Unsafe or unattributed repository-file writes; shell injection
(the registry is strict `argv`, never a shell string, never templated); pushing without
review; a second multi-repo checkout system competing with Nave.

**How.** `mutation_plan.py` (proposal + registry, `build_proposal` requiring exact
`expected_shas` coverage of the selection) and `pen_orchestrator.py` (the state machine
`planned → created → executed → validated → proposed | blocked | failed`, propose-only,
fail-closed) over `nave_adapter.py`'s pen JSON ops. Pulse records actor, machine, Nave
version, pen name, selection, command ID, and per-repo outcome as the `repo-mutation`
result. **`pen_orchestrator.execute` has no caller outside tests today** — F6 is the
engine the other mutate phases build proposals *for*, but nothing runs them.

### F7 — Generated-artifact drift and contract propagation

**Goal.** Detect when a generated file has drifted from its template, and when a
producer/consumer contract version has skewed — using explicit configuration, never
inferred layouts.

**What it looks at.** `generated.yaml` bindings (`{source, template_path, template_tree
(tree SHA), generator, files:[{path, blob}]}`), `generators.yaml` generator adapters
(source/output paths + a referenced F6 transformation), and optional `contract:` blocks on
F5 edges (producer/consumer `{path, parser}`, `version_scheme: pep440`).

**What it detects.** Per binding, comparing content-addressed tree/blob SHAs:
`current` (nothing moved); **`template-drift`** (template tree changed, outputs unchanged →
a regeneration is warranted → an F6 proposal); **`local-customization`** (outputs changed
but template didn't → a finding, deliberately **no** proposal, so local edits aren't
clobbered); **`conflict`** (both changed). For contracts: `compatible | gap | unknown`
between a producer's declared version and a consumer's.

**Risk it mitigates.** Blindly regenerating over intentional local edits; letting a
generated file silently rot behind its template; producer/consumer version skew; an LLM
inferring *what* to regenerate or *how* (forbidden — generators are explicit config, argv
lives only in the F6 registry).

**How.** `generated_artifacts.py` (`backfill`/`audit`/`advance`, pure; `collect` does the
git reads via `git rev-parse FETCH_HEAD:<path>` for tree/blob SHAs) + `generator_dispatch.py`
(`load_generators`, `dispatch` → an F6 proposal with output-allowlist enforcement) +
`contract_versions.py` (regex/toml/json/yaml parsers, `packaging` comparison). Skill:
`gh-generated-artifact-headless`.

### F8 — Generic plan synchronization

**Goal.** Keep planning documents and their GitHub issues/milestones in agreement, in
*both* directions, without either side being "primary".

**What it looks at.** A planning doc's artifact-carried frontmatter `sync:` block
(`issue: {repo, number}`, per-field `policy`, and a per-field `base` — the three-way merge
base) versus the live GitHub issue. V1 fields: `title`, `state`, `assignees`, `milestone`,
`body`. The body base is fetched by reconciled blob SHA from **pushed** git history, never
a working tree.

**What it detects.** Per field: `noop`, `apply_to_github` (doc changed), `apply_to_doc`
(GitHub changed), `agree` (both to the same value), or **`conflict`** (both changed
differently, no resolving policy). Local dirty/unpushed docs are reported and **excluded**,
never merged.

**Risk it mitigates.** Doc/issue drift; a lossy edit destroying frontmatter comments or
ordering; one side clobbering the other; a base advancing before both sides confirm.

**How.** `plan_sync.py` (lossless `ruamel` parse/patch — a no-op patch is byte-identical;
per-field three-way `merge_field`/`compute`; `build_apply_plans` produces up to two
*separate* proposals) + `plan_sync_snapshot.py` (`collect` via git + `gh_api` seams;
rename detection via `git log --follow`) + `apply_doc_patch.py` (the tiny script the
`plan-sync-doc-patch` F6 transformation runs inside a pen, reading its patch from a
well-known repo-relative path since F6 forbids argv templating). `poll.py`'s `docs` source
is the trigger. Skill: `gh-plan-sync-headless`.

### F9 — Hiivmind / Claude dogfood overlays

**Goal.** Let the plugin govern *itself* — score its own manifest, skills, and context —
without polluting the neutral fleet scorecards.

**What it looks at.** Only repositories whose reviewed profile opts in
(`profile:claude-plugin`). It reads `.claude-plugin/plugin.json`, every `skills/*/SKILL.md`,
`CLAUDE.md`, the `claude-plugin-v1` scorecard, and `marketplace-sync.yaml` bindings.

**What it detects.** A malformed/absent plugin manifest; skills with invalid frontmatter;
**stale `CLAUDE.md` claims** (a referenced skill/command that no longer exists) via a
deterministic scan plus a schema-guarded inference step; **marketplace version drift**
(the plugin's newest stable release vs the version recorded in `marketplace.json`); corpus
generated-skill drift (reusing F7). Overlay subtotals are reported under their own
scorecard key — **never merged into a neutral denominator**.

**Risk it mitigates.** The plugin's self-documentation silently rotting; the plugin's
marketplace entry lagging its releases; and — critically — the overlay's plugin-specific
assumptions leaking into how it scores *other* repositories. The engine imports **no**
overlay module at load time; overlay adapters register through a lazily-imported
`register_claude_adapters`, and an isolation test (`test_dogfood_isolation.py`) proves the
neutral fleet is unaffected.

**How.** `marketplace_sync.py` (`compare` → `MarketplaceDrift`, `build_marketplace_proposal`
→ F6 proposal), `adapters/claude_plugin.py` (the `plugin_manifest`/`skills`/`context`
adapters), and `repo_claims.py` (the deterministic claim scan + the
`validate_inferred_findings` schema guard that keeps the one non-deterministic step — an
agent extracting claims from prose — from ever fabricating a pass/fail). All mutations are
propose-only and expected-SHA guarded. Skills: `gh-marketplace-sync-headless`, and the
overlay subsection of `gh-healthcheck-headless`. *(The overlay adapters are not yet
registered by the dispatcher, and marketplace-sync has no driver — F10 Tasks 1 and 4.)*

---

## 4. What actually runs today

The read/score spine (F0–F3) runs from the scheduler (**status → refresh → healthcheck →
PR**) and on demand. The propose/mutate spine (F5–F9) is built and tested but only F5 has
a partial trigger (poll-surfaced); F6–F9 have no driver and no trigger. F4 is unbuilt. The
gap and its fix are the subject of the audit and the F10 plan referenced at the top of this
document.
