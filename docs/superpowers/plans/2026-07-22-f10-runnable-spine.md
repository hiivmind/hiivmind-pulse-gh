# F10: Runnable Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Origin:** `docs/superpowers/audits/2026-07-22-f-series-runnable-spine-audit.md`. The audit found that F6–F9 shipped as pure libraries + prose skills with **no driver layer**, so nothing triggers them and every headless run requires an improvised driver. This plan builds the missing layer.

**Goal:** Make every propose/mutate F-phase (F5 completion, F6–F9) runnable end-to-end from a real trigger to a validated `result.yaml`, with **no improvised glue** — by adding the missing **driver layer** (a `uv run` CLI per phase), wiring the F9 overlay into the dispatcher and evidence build, and composing the new runs into the scheduler.

**Non-goal (explicitly out of scope):** apply-mode. Every driver here is **propose-only** and emits reviewable proposals into a validated result; none pushes, and none newly executes a Nave pen. Executing a recorded proposal through `pen_orchestrator.execute` (which needs Nave + the transformation executor on PATH in the pen checkout) remains the deferred apply-mode phase — see `docs/backlogs/2026-07-22-f1-f8-phase-deferrals.md`. F10 closes the *runnable-and-triggered* gap, not the *applies-changes* gap.

**Architecture:** Each phase already owns a pure library (`marketplace_sync`, `plan_sync`, `generated_artifacts`/`generator_dispatch`, the F9 `claude_plugin` adapters) and a `SKILL.md`. F10 inserts a thin **CLI driver** between them: a PEP 723 script that assembles the phase's inputs (workspace config + a snapshot via the phase's existing `collect`, + actor), calls the pure library, validates the envelope with `validate_result.py`, and writes the phase's `*-result.yaml`. Each headless `SKILL.md` changes from *citing a function signature* to *shelling the driver* (`uv run …`) — the same pattern the F0–F5 read spine already uses (`healthcheck_dispatch.py`, `impact.py`, `impact_snapshot.py`). The F9 overlay is wired into `healthcheck_dispatch.py` (adapter registration + evidence content channel + inference hook). The scheduler maintenance template gains composition entries so a trigger invokes the propose/mutate phases.

**Tech Stack:** Python 3.10+ PEP 723 scripts, PyYAML, pytest, `gh` CLI, git. (No new library dependencies — drivers only assemble and call existing pure modules.)

## What already exists (verified 2026-07-22, develop head)

- **Pure libraries, fully tested, with no CLI driver:**
  - `marketplace_sync.compare(binding, releases, marketplace_doc) -> MarketplaceDrift`; `build_marketplace_proposal(drift, head_sha, actor, registry=None) -> Proposal`.
  - `plan_sync.parse_document/patch_document/merge_field/compute/build_apply_plans/finalize`; `plan_sync_snapshot.collect(bindings, workdir, runner, gh_api) -> SyncSnapshot`.
  - `generated_artifacts.backfill/audit/advance` + `collect(manifest, workdir, runner)`; `generator_dispatch.load_generators(data, registry)` + `dispatch(generator, binding, snapshot, actor, mutation_policy="propose") -> Proposal`.
  - `mutation_plan.build_proposal(...)`; `pen_orchestrator.execute(...)` — propose-only, expected-SHA guarded. **No caller outside tests.**
- **The read-spine drivers to model on:** `healthcheck_dispatch.py` (`--evidence --profiles --workspace`), `impact.py`, `impact_snapshot.py` (`default_runner`, `_valid_sha`/`_valid_branch` argv guards, fetch-then-`FETCH_HEAD`), `evidence_snapshot.py`.
- **Result validators already registered** for every kind: `validate_result.py` kinds `marketplace-sync`, `plan-sync`, `generated-artifact`, `repo-mutation`, `impact`, `healthcheck` (+ envelope). The drivers must produce envelopes these already accept — no validator changes expected.
- **The F9 overlay pieces, unwired:** `adapters/__init__.register_claude_adapters` (lazy, isolated, no non-test caller); the `claude-plugin-v1` scorecard in `templates/profiles.yaml.template`; `repo_claims.validate_inferred_findings` (the inference schema guard). `healthcheck_dispatch.py` registers only `register_universal_adapters`; the F0 evidence snapshot carries file paths only (no `file_contents`).
- **Headless skills that cite signatures instead of a driver:** `gh-marketplace-sync-headless`, `gh-plan-sync-headless`, `gh-generated-artifact-headless`.

## Global Constraints

- Every driver is **propose-only**: it may read, compare, and emit proposal records; it MUST NOT push, apply, or newly execute a Nave pen. `mutation_policy` is always `propose`.
- Every driver writes its `*-result.yaml` on **every exit** (including early ABORT) and self-validates via `validate_result.py`; a non-zero validator exit is a driver bug.
- Drivers add **no new decision logic** — all classification/merge/drift rules stay in the pure libraries. A driver only assembles inputs, calls the library, and serialises the result.
- Drivers reuse existing seams verbatim: `impact_snapshot.default_runner`, the `_valid_sha`/`_valid_branch` argv guards, the `gh_api` seam. No second runner, no second checkout mechanism.
- The overlay remains opt-in: the dispatcher registers claude adapters and builds the content channel **only** for repositories whose reviewed profile selects an overlay scorecard. Neutral fleet behaviour stays provably unchanged (`test_dogfood_isolation.py` must still pass).
- A skipped inference step is recorded as `unknown`, never a silent `pass`.
- `uv run pytest -q` and `git diff --check` pass before each task closes. Every task adds neutral fixtures, not only hiivmind/plugin fixtures.

---

### Task 1: Marketplace-sync driver

**Files:**
- Create: `lib/pulse/scripts/marketplace_sync_run.py`
- Create: `lib/pulse/scripts/tests/test_marketplace_sync_run.py`
- Modify: `skills/gh-marketplace-sync-headless/SKILL.md`

**Interfaces:**
- CLI: `marketplace_sync_run.py --workspace <path> [--repo <full|short>] [--result <path>] [--mode scheduled|interactive]`.
- Consumes: `CONFIG_DIR/marketplace-sync.yaml` bindings; per binding, the marketplace doc (via `gh api` REST, injected seam) and `gh release list --json tagName,isPrerelease,isDraft`.
- Produces: `marketplace-sync-result.yaml` (kind `marketplace-sync`) with counts, findings, and `proposals[]` for drift/missing-entry. Never executes a pen.
- Drives the exact Phase 1–5 flow already written in `gh-marketplace-sync-headless/SKILL.md`; the skill's `marketplace_sync.compare` / `build_marketplace_proposal` references become the driver's internals.

**Steps:**
- [ ] **Step 1: Write failing tests** — fixture bindings + injected release list / marketplace doc / HEAD SHA seams: `in_sync` → zero proposals; `drift`/`missing_entry` → one proposal each with `expected_shas`; `no stable release` → `unknown` finding, no proposal; malformed binding → `invalid_binding` finding, not counted; unresolvable `--repo` → ABORT writes a result. Assert the emitted file passes `validate_result.py --kind marketplace-sync`.
- [ ] **Step 2: Implement** the driver as an assembler over `marketplace_sync.compare`/`build_marketplace_proposal` with a `gh` seam mirroring `impact_snapshot`'s runner injection. No decision logic in the driver.
- [ ] **Step 3: Rewrite the skill** to shell `uv run …/marketplace_sync_run.py` with the resolved inputs; replace the function-signature contract with the command; keep the STOP/ABORT semantics.
- [ ] **Step 4: Run tests and commit** with `feat: add runnable marketplace-sync driver`.

---

### Task 2: Plan-sync driver

**Files:**
- Create: `lib/pulse/scripts/plan_sync_run.py`
- Create: `lib/pulse/scripts/tests/test_plan_sync_run.py`
- Modify: `skills/gh-plan-sync-headless/SKILL.md`

**Interfaces:**
- CLI: `plan_sync_run.py --workspace <path> [--result <path>] [--mode …]`.
- Consumes: bound docs from workspace config; `plan_sync_snapshot.collect` (git via `default_runner`, GitHub via `gh_api` seam).
- Produces: `plan-sync-result.yaml` (kind `plan-sync`) with counts (`in_sync`, `doc_patches`, `github_patches`, `conflicts`, `excluded`), findings, and up to two **separate** propose-only proposals per doc (`build_apply_plans`): the doc-patch (F6 `Proposal`, recorded — not executed) and the GitHub patch (proposed action). Bases advance only on confirmed application, which never happens in propose mode.
- Drives the skill's DISCOVER → SNAPSHOT → COMPUTE → (propose) → RECORD flow.

**Steps:**
- [ ] **Step 1: Write failing tests** — reuse `test_plan_sync_acceptance.py` fixtures: each merge outcome lands in the right count bucket; conflict withholds base; `dirty_doc`/`local_ahead` exclusion + finding; repeat run after sync is a no-op with identical counts; emitted file passes `validate_result.py --kind plan-sync`.
- [ ] **Step 2: Implement** the assembler over `collect` + `compute` + `build_apply_plans`; propose-only, no pen exec, no `gh` writes.
- [ ] **Step 3: Rewrite the skill** to shell the driver.
- [ ] **Step 4: Run tests and commit** with `feat: add runnable plan-sync driver`.

---

### Task 3: Generated-artifact driver

**Files:**
- Create: `lib/pulse/scripts/generated_artifact_run.py`
- Create: `lib/pulse/scripts/tests/test_generated_artifact_run.py`
- Modify: `skills/gh-generated-artifact-headless/SKILL.md`

**Interfaces:**
- CLI: `generated_artifact_run.py --workspace <path> [--result <path>] [--mode …]`.
- Consumes: `generated.yaml` manifest; `generated_artifacts.collect` snapshot (`git rev-parse FETCH_HEAD:<path>` tree/blob SHAs).
- Produces: `generated-artifact-result.yaml` (kind `generated-artifact`) with `bindings_audited`, `states`, findings, and `proposals[]` — a `generator_dispatch.dispatch` F6 proposal **only** for `template-drift` bindings (recorded, not executed). `local-customization`/`conflict`/`error` produce findings and no proposal.
- Drives the skill's SNAPSHOT → AUDIT → PROPOSE → RECORD flow.

**Steps:**
- [ ] **Step 1: Write failing tests** — fixture manifest + snapshot covering every `audit` classification cell; `template-drift` yields exactly one dispatched proposal that round-trips `pen_orchestrator.execute`'s expected-SHA guard; output outside the generator allowlist is a finding, no proposal; emitted file passes `validate_result.py --kind generated-artifact`.
- [ ] **Step 2: Implement** the assembler over `collect` + `audit` + `generator_dispatch.dispatch`; keep it neutral (the F7 neutrality test — no `claude`/`corpus`/`plugin`/`SKILL.md` strings — extends to this driver).
- [ ] **Step 3: Rewrite the skill** to shell the driver.
- [ ] **Step 4: Run tests and commit** with `feat: add runnable generated-artifact driver`.

---

### Task 4: Wire the F9 overlay into the dispatcher

**Files:**
- Modify: `lib/pulse/scripts/healthcheck_dispatch.py`
- Modify: `lib/pulse/scripts/evidence_snapshot.py` (or the overlay evidence build it feeds)
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `lib/pulse/scripts/tests/test_healthcheck_dispatch.py`, `test_dogfood_isolation.py`

**Interfaces:**
- Dispatcher opt-in: when any profiled repo's resolved scorecard contains a `claude.*` adapter (i.e. an overlay scorecard is in play), `healthcheck_dispatch` calls `register_claude_adapters(registry)` in addition to `register_universal_adapters`. Neutral-only runs never import the overlay (the lazy import + isolation test still hold).
- **Overlay content channel:** for a repo whose reviewed profile opts into an overlay scorecard, the evidence build populates `evidence["file_contents"]` for the overlay-relevant paths (`.claude-plugin/plugin.json`, `CLAUDE.md`, every `skills/*/SKILL.md`) — bounded, explicit, overlay-scoped. The neutral snapshot stays content-free (the F9 architecture invariant).
- **Inference hook:** `gh-healthcheck-headless` performs the `claude.context` inference step for opted-in repos (extract candidate `stale_command`/`missing_claimed_skill`/`unsupported_evidence` claims from `CLAUDE.md`, feed as `evidence["inferred_claims"]`, schema-guarded by `repo_claims.validate_inferred_findings`) and **records whether it ran**. A skipped/failed inference step forces the `claude.context` result to `unknown`, never a silent `pass`.

**Steps:**
- [ ] **Step 1: Tests** — a fixture fleet with one overlay repo + neutral repos: overlay checks resolve to real `pass`/`fail`/`unknown` (not `unsupported`); neutral repos never load the overlay module (extend `test_dogfood_isolation.py`); a run with the inference step absent grades `claude.context` `unknown`; overlay subtotal stays in its own `by_scorecard` key.
- [ ] **Step 2: Implement** the opt-in registration + content channel + inference-recording; keep isolation green.
- [ ] **Step 3: Update the skill** — the "Overlay scorecards (dogfood)" subsection gains the inference-step instruction and the `unknown`-on-skip rule.
- [ ] **Step 4: Run full suite and commit** with `feat: wire claude overlay into the dispatcher`.

---

### Task 5: Complete F5 scheduling and compose the propose/mutate phases into triggers

**Files:**
- Modify: `lib/pulse/scripts/poll.py` (+ `test_poll.py`)
- Modify: the scheduler maintenance composition (`hiivmind-pulse-scheduler` `TEMPLATE-workspace-maintenance.md` — cross-repo; document the required edit here and land it in that repo)
- Modify: `lib/patterns/run-ledger.md` / `lib/patterns/workflow-execution.md` as needed for the new run kinds

**Interfaces:**
- `poll.py` surfaces the `docs` (F8) and `branch_heads` (F5) trigger sources as due workflows the heartbeat/`gh-heartbeat` presents, and adds a periodic trigger for marketplace-sync and generated-artifact audits (mirroring the existing workflow cadence state).
- Scheduler composition extends **status → refresh → healthcheck** with **impact-audit → generated-artifact → plan-sync → marketplace-sync** (all propose-only), each writing its validated result into the maintenance PR.

**Steps:**
- [ ] **Step 1: Tests** — `poll.py` emits due-workflow state for the new sources (mirror the `branch_heads` round-trip tests); the maintenance composition lists every propose/mutate run.
- [ ] **Step 2: Implement** the poll sources and document the scheduler composition edit; keep triggers propose-only.
- [ ] **Step 3: Run tests and commit** with `feat: trigger the propose/mutate phases`.

---

### Task 6: End-to-end acceptance and the anti-improvisation guard

**Files:**
- Create: `lib/pulse/scripts/tests/test_runnable_spine_acceptance.py`
- Create: `lib/pulse/scripts/tests/test_skills_shell_drivers.py`

**Interfaces:**
- Acceptance: for each of marketplace-sync, plan-sync, generated-artifact, and the overlay healthcheck, a fixture-driven `trigger → driver → validated result` run (no network), asserting the result validates and the counts match the fixture's expected outcome. Compose the real public functions (the F6/F8 acceptance-test style).
- **Anti-improvisation guard:** a test asserting that every headless `SKILL.md` that references a propose/mutate library either shells a `uv run …_run.py`/dispatcher driver or is explicitly exempt — i.e. no `SKILL.md` presents a bare `module.func(` contract as its execution path without a driver. This is the regression that keeps the runnable-spine gap from reopening.

**Steps:**
- [ ] **Step 1: Write the acceptance matrix** across all four phases.
- [ ] **Step 2: Write the anti-improvisation guard** (grep/AST over `skills/*/SKILL.md`).
- [ ] **Step 3: Run `uv run pytest -q` + `git diff --check` and commit** with `test: gate the runnable spine end-to-end`.

---

## Phase gate — after F10

- Each of impact (F5), generated-artifact (F7), plan-sync (F8), and marketplace/overlay (F9) runs unattended from a trigger to a validated `result.yaml` with **zero hand-written glue**.
- The `claude-plugin-v1` overlay scores an opted-in repo with real `pass`/`fail`/`unknown` per check (not `unsupported`); neutral fleet behaviour and the isolation proof are unchanged.
- The `claude.context` inference step's presence is recorded; its absence grades `unknown`.
- The scheduler composition invokes every propose/mutate phase; each emits reviewable proposals into the maintenance PR.
- `pen_orchestrator.execute` gains its first non-test caller **only** in propose-only mode (create/validate/propose locally); pushing/applying remains deferred to the apply-mode phase.

## Explicitly deferred (still gated on separate design)

- **Apply-mode:** executing a recorded proposal (pen push / GitHub write / base advance). Needs Nave + the transformation executor resolvable on PATH in the pen checkout, and a review-and-apply authority model. Its own phase.
- **F4 dependency-coherence adapters:** Pre-F4 materialised the evidence but the coherence adapter family (P1) was never built; it remains an open read-spine gap independent of F10.
