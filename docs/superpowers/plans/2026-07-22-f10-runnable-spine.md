# F10: Runnable Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Origin:** `docs/superpowers/audits/2026-07-22-f-series-runnable-spine-audit.md`. The audit found that F6–F9 shipped as pure libraries + prose skills with **no driver layer**, so nothing triggers them and every headless run requires an improvised driver. This plan builds the missing layer.
>
> **Revised 2026-07-29** against an adversarial design review run after the F9 (#136) and F11 apply-mode (#138) merges. Eight findings folded in: pure result-builders precede their drivers (drivers stay thin), scheduled-gating is enforced in the library, the overlay content channel is fully specified, Task 5 is split into an in-repo trigger task and a cross-repo scheduler task, the anti-improvisation guard is a machine-readable capability→driver mapping, and the F6 phase-gate wording is corrected. **Handoff decision (settled):** F10 emits **review summaries only**; apply-mode (F11) **re-derives** the full proposal from a fresh snapshot at apply time — F10 stays stateless and needs no `validate_result.py` schema change.
>
> **Second revision pass (2026-07-29)** against a focused re-review of the above. Closed the residual gaps: Task 2 now **extends `plan_sync.build_result`** to accept `mode`+registry (it had neither, so `allow_scheduled: false` couldn't gate); the overlay collector **resolves its own remote SHA** (F0 leaves `remote_sha: None`); the `periodic` cadence is reconciled with the real first-poll bootstrap (`poll.py:548`) and the last-run-advances-on-failure recorder; proposal-summary tests assert the **persisted** summary is 3-field while the *ephemeral* Proposal carries `expected_shas`; `--repo` restored on the plan-sync/generated drivers; and Task 7 gains an explicit **import-boundary AST test** plus an **enrollment-based** guard (every headless skill must be `driver`-mapped or `exempt`, so a new bare-signature skill fails without any prose scan).

**Goal:** Make every propose/mutate F-phase (F5 completion, F6–F9) runnable end-to-end from a real trigger to a validated `result.yaml`, with **no improvised glue** — by adding the missing **driver layer** (a `uv run` CLI per phase over a *pure result-builder*), wiring the F9 overlay into the dispatcher and evidence build, adding a `periodic` trigger type, and composing the new runs into the scheduler.

**Non-goal (explicitly out of scope):** apply-mode. Every driver here is **propose-only** and emits reviewable proposal *summaries* into a validated result; none pushes, applies, or executes a Nave pen. **No F10 driver calls `pen_orchestrator.execute`** — the drivers call the pure propose libraries (`build_marketplace_proposal`, `generator_dispatch.dispatch`, `build_apply_plans`) which return `Proposal` records; those records merely *would* pass `execute`'s expected-SHA guard if later applied. Executing a recorded proposal (`pen_orchestrator.execute` with `apply_ops`, push, base advance) is F11 apply-mode and its production wiring — see `docs/backlogs/2026-07-29-apply-mode-v2-deferrals.md` § A. F10 closes the *runnable-and-triggered* gap, not the *applies-changes* gap.

**Architecture:** Each phase already owns a pure library (`marketplace_sync`, `plan_sync`, `generated_artifacts`/`generator_dispatch`, the F9 `claude_plugin` adapters) and a `SKILL.md`. F10 inserts a thin **CLI driver** between them — but only after the library exposes a **pure `build_result(...)` function** that owns every classification/count/finding/gating decision (mirroring the one `plan_sync.build_result` already ships, `plan_sync.py:366`). The driver then only: parses argv (reusing the `_valid_sha`/`_valid_branch` guards), assembles inputs (workspace config + a snapshot via the phase's existing `collect` + actor + registries + mode), calls `build_result`, validates the envelope with `validate_result.py`, and writes the phase's `*-result.yaml`. This is the same pattern the F0–F5 read spine already uses (`healthcheck_dispatch.py`, `impact.py`, `impact_snapshot.py`). The F9 overlay is wired into `healthcheck_dispatch.py` via an **overlay-only content collector** (adapter registration + bounded `file_contents` channel + inference hook + `inference_status` marker). A new `periodic` trigger type in `poll.py` plus template flips make the phases due on a cadence; the scheduler maintenance template (a **separate repo**) gains a PR-body projection.

**Tech Stack:** Python 3.10+ PEP 723 scripts, PyYAML, pytest, `gh` CLI, git. (No new library dependencies — drivers only assemble and call existing pure modules; new *pure* `build_result` helpers live in the existing phase libraries, not the drivers.)

## What already exists (verified 2026-07-29, develop head `c1960b3`)

- **Pure libraries, tested, with no CLI driver:**
  - `marketplace_sync.compare(binding, releases, marketplace_doc) -> MarketplaceDrift` (`marketplace_sync.py:151`) returns raw drift + reason strings — **not** typed findings/severities/counters; `build_marketplace_proposal(drift, head_sha, actor, registry=None) -> Proposal` (`:251`) enforces `allow_scheduled` gating **only when a registry is supplied** (`:274`). **No pure `build_result`.**
  - `plan_sync.parse_document/patch_document/merge_field/compute/build_apply_plans/finalize`; **`plan_sync.build_result(...)` already exists** (`plan_sync.py:366`) — a pure, propose-only result builder that owns the count/finding/proposal loop. `plan_sync_snapshot.collect(bindings, workdir, runner, gh_api)` (`:224`).
  - `generated_artifacts.backfill/audit/advance` + `collect(manifest, workdir, runner)` (`:364`/`:506`); `audit` indexes required binding keys directly with **no manifest validator** (`:204`). `generator_dispatch.load_generators` + `dispatch(...)` (`:279`) **raises** on an out-of-allowlist path (`:319`) and applicability is a **separate** `generator_applies` call (`:258`); `dispatch` builds the proposal **without** passing a transformation registry (`:326`). **No pure `build_result`.**
  - `mutation_plan.build_proposal(...)` gates on `allow_scheduled` **only when a registry is passed** (`:391`,`:404`); `pen_orchestrator.execute(...)` (`:373`) is now **policy-aware** — F11 added an optional `apply_ops` param; propose mode omits it (`:415`), only `allow-listed` requires it (`:426`). **No caller outside tests; F10 never calls it.**
- **The read-spine drivers to model on:** `healthcheck_dispatch.py` (`--evidence --profiles --workspace`, driver at `:308`), `impact.py` (`:520`), `impact_snapshot.py` (`default_runner` `:60`, `_valid_sha` `:139`/`_valid_branch` `:143`, fetch-then-`FETCH_HEAD`), `evidence_snapshot.py`.
- **Result validators already registered** for every kind: `validate_result.py` kinds `marketplace-sync` (`:596`), `plan-sync`, `generated-artifact` (`:616`/`:635`), `repo-mutation`, `impact`, `healthcheck`, and F11's `apply-status` (`:654`, distinct branch — no collision). The `proposals[]` summary schema validates `{binding, transformation, proposal_id}` (`:624`) — **sufficient for review summaries; no schema change needed** under the settled handoff decision. The drivers must produce envelopes these already accept.
- **The F9 overlay pieces, unwired:** `adapters/__init__.register_claude_adapters` (lazy `:21`, isolated, no non-test caller); the `claude-plugin-v1` scorecard in `templates/profiles.yaml.template`; `repo_claims.validate_inferred_findings` (`:232`, the inference schema guard). `healthcheck_dispatch.py` registers only `register_universal_adapters` (`:265`); the F0 evidence snapshot carries file paths only, no `file_contents` (`evidence_snapshot.py:182`), and `healthcheck_dispatch` accepts only evidence/profile/workspace files with no content-fetch seam (`:308`). **`claude_plugin.py` treats an absent `inferred_claims` as an empty list (`:280`) and can return `pass` (`:316`)** — this is the "skip → silent pass" bug the inference hook must close.
- **Trigger model:** `poll.py` handles only `session_poll` and `freshness` trigger types (`:582`,`:588`); it **already implements** `branch_heads` (F5, `:219`) and `docs` (F8, `:260`) sources and dispatches them (`:310`) — so that portion of the original Task 5 is **stale/done**. There is **no `periodic` trigger type**. The four phase templates (`templates/workflows/{marketplace-sync,generated-artifact-audit,impact-audit,plan-sync}.yaml`) all carry `trigger.type: on_demand`. Cadence state already lives in `poll_state.workflows[name].last_run_at` + `cooldown_minutes` (`:575`).
- **The scheduler is a separate repo:** `../hiivmind-pulse-scheduler/TEMPLATE-workspace-maintenance.md` composes **status → refresh → healthcheck → PR** and **explicitly excludes `*-result.yaml` from commits** (`:171`) — so results reach a PR only via an explicit **PR-body projection**, never as committed files.
- **Headless skills that cite signatures instead of a driver:** `gh-marketplace-sync-headless`, `gh-plan-sync-headless`, `gh-generated-artifact-headless`. F11 inserted apply-mode prose into two of them (`gh-plan-sync-headless/SKILL.md:163`, `gh-marketplace-sync-headless/SKILL.md:187`) — skill rewrites must be **surgical** and preserve those sections.

## Global Constraints

- Every driver is **propose-only**: it may read, compare, and emit proposal *summary* records; it MUST NOT push, apply, or execute a Nave pen. `mutation_policy` is always `propose`. **No F10 driver may import or call any apply-mode module** (`pen_orchestrator.execute`'s apply path, `object_apply`, `apply_reconcile`, `pen_clone_reader`, `nave_adapter.provision/commit/push_apply_*`) — a test asserts this import boundary.
- **Drivers add no new decision logic.** Every classification / merge / drift / count / finding / gating decision lives in a **pure library `build_result(...)`** (existing for plan-sync; added for marketplace and generated). A driver only parses argv, assembles inputs, calls `build_result`, validates, and serialises. If a decision would otherwise land in a driver (e.g. mapping `dispatch`'s out-of-allowlist `raise` to a finding, or translating raw `compare` drift into typed findings/counts), it goes in the library instead.
- **Scheduled-gating is enforced in the library, both modes tested.** Each `build_result` takes the transformation registry, the generator registry (where applicable), the repository profile/evidence, and `mode` (`scheduled|interactive`). In `scheduled` mode a transformation whose `allow_scheduled` is false MUST yield a **finding / proposed-action summary, never a runnable `Proposal`** — the registry is passed through to `build_marketplace_proposal` / `mutation_plan.build_proposal` so the existing gate fires. Every driver task tests **both** modes and proves the scheduled-gated case produces no runnable proposal.
- Every driver writes its `*-result.yaml` on **every exit** (including early ABORT and a **malformed-manifest/binding** ABORT) and self-validates via `validate_result.py`; a non-zero validator exit is a driver bug.
- Drivers reuse existing seams verbatim: `impact_snapshot.default_runner`, the `_valid_sha`/`_valid_branch` argv guards, the `gh_api` seam. No second runner, no second checkout mechanism.
- The overlay remains opt-in: the dispatcher registers claude adapters and attaches the `file_contents` channel **only** to the entries of repositories whose reviewed profile selects an overlay scorecard. Neutral fleet behaviour stays provably unchanged (`test_dogfood_isolation.py` must still pass); a neutral run never attaches content and never grades an overlay check anything but its neutral result.
- **Inference is status-marked, never silently passing.** The `claude.context` step records `inference_status ∈ {ran, skipped, failed}`. Only `ran` may produce `pass`/`fail`; `skipped` and `failed` force the check to `unknown`. `claude_plugin.py` is edited so an absent/empty `inferred_claims` under `skipped`/`failed` cannot return `pass`.
- **F10 outputs are review summaries, not durable executable proposals.** Results carry counts, findings, and `{binding, transformation, proposal_id}` proposal summaries only. Apply-mode re-derives the full `Proposal` from a fresh snapshot at apply time; F10 persists no selection/expected-SHA/bound-path/patch payload and requires no `validate_result.py` schema change.
- `uv run pytest -q` and `git diff --check` pass before each task closes. Every task adds **neutral** fixtures, not only hiivmind/plugin fixtures.

---

### Task 1: Marketplace-sync — pure result-builder, driver, skill

**Files:**
- Modify: `lib/pulse/scripts/marketplace_sync.py` (add pure `build_result`)
- Create: `lib/pulse/scripts/marketplace_sync_run.py`
- Create: `lib/pulse/scripts/tests/test_marketplace_sync_run.py` (+ extend `test_marketplace_sync.py` for `build_result`)
- Modify: `skills/gh-marketplace-sync-headless/SKILL.md` (surgical — preserve F11 apply section at `:187`)

**Interfaces:**
- **Library:** `marketplace_sync.build_result(bindings, *, releases_by_repo, docs_by_repo, head_shas, actor, registry, mode) -> dict` — the pure envelope owner: translates each binding's `compare` drift into typed findings + counters, handles `invalid_binding`, `no stable release → unknown`, and fetch-error mapping, and calls `build_marketplace_proposal(..., registry=registry)` so `allow_scheduled` gating fires in `scheduled` mode. Returns a `kind: marketplace-sync` envelope body. No I/O.
- **Driver CLI:** `marketplace_sync_run.py --workspace <path> [--repo <full|short>] [--result <path>] [--mode scheduled|interactive]`. Consumes `CONFIG_DIR/marketplace-sync.yaml` bindings; per binding, the marketplace doc (`gh api` REST, injected seam mirroring `impact_snapshot`'s runner) and `gh release list --json tagName,isPrerelease,isDraft`; resolves the transformation registry. Assembles → `build_result` → validate → write. Never executes a pen.
- Produces: `marketplace-sync-result.yaml` (kind `marketplace-sync`) with counts, findings, and `proposals[]` summaries for drift/missing-entry (interactive) or gated proposed-actions (scheduled + `allow_scheduled: false`).

**Steps:**
- [ ] **Step 1: Write failing tests** — (a) `build_result` unit tests over injected release lists / marketplace docs / HEAD SHAs: `in_sync` → zero proposals; `drift`/`missing_entry` interactive → one proposal summary each — assert the **ephemeral full `Proposal`** carries `expected_shas` (proof it *would* pass `execute`'s guard), then assert the **persisted summary contains only `{binding, transformation, proposal_id}`** (no `expected_shas`/selection/payload — the settled handoff contract); **`scheduled` + `allow_scheduled: false` → a proposed-action finding, no runnable proposal**; `no stable release` → `unknown` finding, no proposal; malformed binding → `invalid_binding` finding, not counted. (b) driver tests: unresolvable `--repo` → ABORT still writes a result; emitted file passes `validate_result.py --kind marketplace-sync` in every case.
- [ ] **Step 2: Implement** `build_result` (all decisions) then the driver as a pure assembler over it with a `gh` seam mirroring `impact_snapshot`'s runner injection. No decision logic in the driver.
- [ ] **Step 3: Rewrite the skill** to shell `uv run …/marketplace_sync_run.py` with resolved inputs; replace the function-signature contract with the command; keep STOP/ABORT semantics; **preserve the F11 apply-mode section verbatim**.
- [ ] **Step 4: Run tests and commit** with `feat: add runnable marketplace-sync driver`.

---

### Task 2: Plan-sync driver (over the existing `build_result`)

**Files:**
- Modify: `lib/pulse/scripts/plan_sync.py` (extend `build_result` to accept `mode` + transformation registry and thread the registry into `build_apply_plans`→`build_proposal`)
- Create: `lib/pulse/scripts/plan_sync_run.py`
- Create: `lib/pulse/scripts/tests/test_plan_sync_run.py` (+ extend `test_plan_sync.py` for the gating parameters)
- Modify: `skills/gh-plan-sync-headless/SKILL.md` (surgical — preserve F11 apply section at `:163`)

**Interfaces:**
- CLI: `plan_sync_run.py --workspace <path> [--repo <full|short>] [--result <path>] [--mode scheduled|interactive]` (`--repo` mirrors the `plan-sync.yaml` template's repo param).
- Consumes: bound docs from workspace config; `plan_sync_snapshot.collect` (git via `default_runner`, GitHub via `gh_api` seam); resolves the transformation registry.
- **Library change (required for gating):** `plan_sync.build_result` (`plan_sync.py:366`) currently accepts **neither `mode` nor a registry**, and `build_apply_plans` calls `build_proposal` with **no registry** (`plan_sync.py:267`) — but `plan-sync-doc-patch` is `allow_scheduled: false` (`transformations.yaml.template:88`). So Task 2 **extends `build_result`** to accept `mode` and the registry and thread the registry through `build_apply_plans`→`build_proposal`, so a `scheduled` run gates the doc-patch to a proposed-action finding. The driver still does NOT reconstruct the count/proposal loop — the gating decision stays in the library. `build_result` keeps owning counts (`in_sync`, `doc_patches`, `github_patches`, `conflicts`, `excluded`), findings, and the 3-field proposal summaries.
- Produces: `plan-sync-result.yaml` (kind `plan-sync`). Bases advance only on confirmed application, which never happens in propose mode.

**Steps:**
- [ ] **Step 1: Write failing tests** — reuse `test_plan_sync_acceptance.py` fixtures: each merge outcome lands in the right count bucket; conflict withholds base; `dirty_doc`/`local_ahead` exclusion + finding; **`scheduled` mode gates the `allow_scheduled: false` doc-patch to a proposed-action finding with no runnable proposal, while `interactive` mode yields the proposal** (proves the new `mode`/registry parameters work); repeat run after sync is a no-op with identical counts; persisted proposal summaries carry only `{binding, transformation, proposal_id}`; emitted file passes `validate_result.py --kind plan-sync`.
- [ ] **Step 2: Implement** the `build_result` `mode`/registry extension, then the driver as an assembler over `collect` + `plan_sync.build_result`; propose-only, no pen exec, no `gh` writes, no reconstructed decision loop.
- [ ] **Step 3: Rewrite the skill** to shell the driver; **preserve the F11 apply-mode section verbatim**.
- [ ] **Step 4: Run tests and commit** with `feat: add runnable plan-sync driver`.

---

### Task 3: Generated-artifact — pure result-builder, manifest guard, driver, skill

**Files:**
- Modify: `lib/pulse/scripts/generated_artifacts.py` (add pure `build_result` + a manifest-validation seam) OR `generator_dispatch.py` (whichever owns dispatch) — put `build_result` where `audit` + `dispatch` compose
- Create: `lib/pulse/scripts/generated_artifact_run.py`
- Create: `lib/pulse/scripts/tests/test_generated_artifact_run.py` (+ extend the library test for `build_result` + manifest guard)
- Modify: `skills/gh-generated-artifact-headless/SKILL.md` (preserve any F11 references at `:126`)

**Interfaces:**
- **Library:** `build_result(manifest, snapshot, *, generators, registry, actor, mode) -> dict` — owns the audit→propose loop: for `template-drift` bindings, checks `generator_applies` **and** calls `generator_dispatch.dispatch` with the transformation `registry` so `allow_scheduled` gating fires in `scheduled` mode; **catches `dispatch`'s out-of-allowlist `raise` and turns it into a finding** (no proposal); `local-customization`/`conflict`/`error` → findings, no proposal. A **manifest-validation seam** rejects a malformed `generated.yaml` (missing required keys, empty/duplicate `files[].path`) and returns a validated ABORT body rather than letting `audit` index-crash (`:204`) — closes backlog `2026-07-22-f1-f8-phase-deferrals.md` § 3a for this path.
- **Driver CLI:** `generated_artifact_run.py --workspace <path> [--repo <full|short>] [--result <path>] [--mode …]`. Consumes `generated.yaml`; `generated_artifacts.collect` snapshot (`git rev-parse FETCH_HEAD:<path>` tree/blob SHAs). Assembles → `build_result` → validate → write. (`--repo` mirrors the workflow template's repo param, `generated-artifact-audit.yaml`.)
- Produces: `generated-artifact-result.yaml` (kind `generated-artifact`) with `bindings_audited`, `states`, findings, and `proposals[]` summaries for `template-drift` only.

**Steps:**
- [ ] **Step 1: Write failing tests** — fixture manifest + snapshot covering every `audit` classification cell; `template-drift` interactive → exactly one proposal summary — assert the **ephemeral full `Proposal`** carries `expected_shas` (proof it would round-trip `pen_orchestrator.execute`'s guard, **without calling `execute`**), then assert the **persisted summary contains only `{binding, transformation, proposal_id}`**; `scheduled` + `allow_scheduled: false` → proposed-action finding, no proposal; output outside the generator allowlist → a finding, no proposal; **malformed manifest → validated ABORT result, no crash**; emitted file passes `validate_result.py --kind generated-artifact`.
- [ ] **Step 2: Implement** `build_result` + manifest guard (all decisions) then the driver as a pure assembler; keep it neutral (the F7 neutrality test — no `claude`/`corpus`/`plugin`/`SKILL.md` strings — extends to this driver).
- [ ] **Step 3: Rewrite the skill** to shell the driver.
- [ ] **Step 4: Run tests and commit** with `feat: add runnable generated-artifact driver`.

---

### Task 4: Wire the F9 overlay into the dispatcher (content channel + inference status)

**Files:**
- Modify: `lib/pulse/scripts/healthcheck_dispatch.py`
- Create: `lib/pulse/scripts/overlay_content.py` (the overlay-only content collector) + its test
- Modify: `lib/pulse/scripts/adapters/claude_plugin.py` (inference-status gate)
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `lib/pulse/scripts/tests/test_healthcheck_dispatch.py`, `test_dogfood_isolation.py`

**Interfaces:**
- **Opt-in registration:** when any profiled repo's resolved scorecard contains a `claude.*` adapter, `healthcheck_dispatch` calls `register_claude_adapters(registry)` in addition to `register_universal_adapters`. A neutral-only run never triggers the lazy import (isolation test holds). Global registration alone is safe *provided content is attached only to opted-in repo entries* — the attachment, not the registration, is the neutral-preserving boundary.
- **Overlay content collector (`overlay_content.py`):** an explicit, overlay-only collector with an **injected `gh_api`/content-reader seam** (no new runner). Contract: reads the overlay-relevant paths (`.claude-plugin/plugin.json`, `CLAUDE.md`, every `skills/*/SKILL.md`) at an **immutable remote ref**; enforces a **per-file byte limit and a total byte budget**; returns explicit **unavailable states** (`missing`, `too_large`, `fetch_error`) per path rather than omitting silently; attaches the result to `evidence["file_contents"]` **only on the opted-in repo's entry**. The neutral snapshot stays content-free (`evidence_snapshot.py:182` unchanged for neutral repos).
- **Ref resolution (required — no resolved SHA exists yet):** F0 currently sets every repo's `remote_sha` to `None` (`evidence_snapshot.py:182`), so there is nothing to pin reads to. The collector **resolves the overlay repo's default-branch head SHA once** via the injected `gh_api` seam (`gh api repos/{repo}/commits/{branch}` → sha) and reads every path at that SHA — a `fetch_error` on resolution marks **all** paths unavailable (and the check `unknown`), never an unpinned branch read. This resolution is overlay-scoped only; it does not change the neutral F0 snapshot's `remote_sha: None`.
- **Inference hook + status:** `gh-healthcheck-headless` performs the `claude.context` inference step for opted-in repos (extract candidate `stale_command`/`missing_claimed_skill`/`unsupported_evidence` claims from `CLAUDE.md`, feed as `evidence["inferred_claims"]`, schema-guarded by `repo_claims.validate_inferred_findings`) and **records `inference_status ∈ {ran, skipped, failed}`**. `claude_plugin.py` is edited so only `inference_status: ran` may yield `pass`/`fail`; `skipped`/`failed` (or absent status) force `claude.context` to `unknown` — the current absent-`inferred_claims`→empty-list→`pass` path (`:280`,`:316`) is removed.

**Steps:**
- [ ] **Step 1: Tests** — a fixture fleet with one overlay repo + neutral repos: overlay checks resolve to real `pass`/`fail`/`unknown` (not `unsupported`); neutral repos never load the overlay module and never gain `file_contents` (extend `test_dogfood_isolation.py`); a run with the inference step absent grades `claude.context` `unknown` (status `skipped`); a `fetch_error`/`too_large` path yields `unknown`, not a crash; overlay subtotal stays in its own `by_scorecard` key.
- [ ] **Step 2: Implement** the opt-in registration + `overlay_content.py` collector + `claude_plugin.py` inference-status gate; keep isolation green.
- [ ] **Step 3: Update the skill** — the "Overlay scorecards (dogfood)" subsection gains the inference-step instruction, the `inference_status` recording, and the `unknown`-on-skip/fail rule.
- [ ] **Step 4: Run full suite and commit** with `feat: wire claude overlay into the dispatcher`.

---

### Task 5: Add a `periodic` trigger type and make the propose/mutate phases due

**Files:**
- Modify: `lib/pulse/scripts/poll.py` (+ `test_poll.py`)
- Modify: `templates/workflows/{marketplace-sync,generated-artifact-audit,impact-audit,plan-sync}.yaml`

**Interfaces:**
- **New `periodic` trigger type** in `poll.py`'s dispatch loop (`:581`), alongside `session_poll`/`freshness`. Cadence algorithm, reconciled with the existing seams: a `periodic` workflow declares `trigger: {type: periodic, interval_minutes: N}`; it is **due** when `last_run_at is None` **or** `now - last_run_at >= interval_minutes`. Note the first-poll bootstrap: when `poll-state.yaml` does not exist yet, poll seeds it and returns **before evaluating any workflow** (`poll.py:548`), so a periodic workflow first becomes due on the **first poll after state bootstrap** (its seeded `last_run_at` is absent → due) — not on the very first poll. The existing `cooldown_minutes` short-circuit (`:577`) still applies as a floor. **Failure semantics (aligned to the existing recorder):** the workflow executor advances `last_run_at` after every execution, success or failure (`lib/patterns/workflow-execution.md` Result Recording) — F10 does **not** change that seam; a failed periodic run therefore waits a full `interval_minutes` before becoming due again, which is acceptable for propose-only audits (no urgency, and the surfacing is non-destructive). Do **not** claim failure-non-advance. `periodic` sources are **not** repo-scoped (no `REPO_SCOPED_SOURCES` gate). The original Task-5 `branch_heads`/`docs` surfacing is **already implemented** (`poll.py:219`,`:260`,`:310`) — do not rebuild it.
- **Template flips:** the four phase templates change `trigger.type: on_demand` → `trigger: {type: periodic, interval_minutes: …}` (reuse each template's existing `cooldown_minutes` as the interval basis — marketplace/generated at 1440, impact/plan-sync per their current cadence). They stay `auto: false` — poll **surfaces** them as due; it never auto-runs a mutation.

**Steps:**
- [ ] **Step 1: Tests** — `poll.py` emits due-workflow state for a `periodic` workflow: due when `last_run_at` absent (first evaluated poll after bootstrap), not-due within `interval`, due again after `interval`, cooldown floor respected; a seeded-but-unrun workflow stays due across polls (poll does not advance `last_run_at`). Assert all four flipped templates parse and surface.
- [ ] **Step 2: Implement** the `periodic` type + flip the templates; keep triggers propose-only (`auto: false`).
- [ ] **Step 3: Run tests and commit** with `feat: add periodic trigger for the propose/mutate phases`.

---

### Task 6: Scheduler composition + PR-body projection (cross-repo — lands in `hiivmind-pulse-scheduler`)

> **Cross-repo task — cannot be tested from this repo.** The scheduler template lives in `../hiivmind-pulse-scheduler`. This task produces the exact edit + a compatibility contract here, and **lands as its own PR in that repo with its own tests**. Task 7's acceptance covers only the in-repo drivers; scheduler acceptance is asserted in the scheduler repo. Do not mark F10's phase gate "triggered end-to-end" complete until the scheduler PR merges.

**Files:**
- Create: `docs/superpowers/plans/2026-07-29-f10-scheduler-composition.md` (the precise scheduler-side edit + PR-body projection spec, authored here)
- (Landed separately) `../hiivmind-pulse-scheduler/TEMPLATE-workspace-maintenance.md` + scheduler-repo tests

**Interfaces:**
- Scheduler composition extends **status → refresh → healthcheck** with **impact-audit → generated-artifact → plan-sync → marketplace-sync** (all propose-only), run after healthcheck.
- **PR-body projection (required):** the scheduler **excludes `*-result.yaml` from commits** (`TEMPLATE-workspace-maintenance.md:171`), so each phase's validated result reaches the maintenance PR as an **explicit PR-body section** — per phase: counts, findings, and proposal summaries (never the result file itself). Define the projection format and a scheduler-side test that a fixture result renders the expected PR-body block. State the compatibility contract: a scheduler running the new template against an old plugin (or vice-versa) degrades to "phase unavailable", never errors.

**Steps:**
- [ ] **Step 1: Author** `2026-07-29-f10-scheduler-composition.md` here — the exact template diff, the PR-body projection format, the compatibility contract, and the scheduler-side test list.
- [ ] **Step 2: Commit** the spec with `docs: specify F10 scheduler composition + PR-body projection`. (The scheduler-repo PR is executed separately against that repo.)

---

### Task 7: End-to-end acceptance and the anti-improvisation guard

**Files:**
- Create: `lib/pulse/scripts/tests/test_runnable_spine_acceptance.py`
- Create: `lib/pulse/scripts/tests/test_skills_shell_drivers.py`
- Create: `lib/pulse/scripts/tests/test_driver_import_boundary.py`
- Create: `skills/headless-driver-map.yaml` (machine-readable capability→driver mapping)

**Interfaces:**
- **Acceptance:** for each of marketplace-sync, plan-sync, generated-artifact, and the overlay healthcheck, a fixture-driven `trigger → driver → validated result` run (no network), asserting the result validates and the counts match the fixture's expected outcome. Compose the real public functions (the F6/F8 acceptance-test style). Include one scheduled-gated case per driver proving no runnable proposal is emitted.
- **Anti-improvisation guard (enrollment, not prose-scan):** `skills/headless-driver-map.yaml` enrolls **every** `skills/*-headless/SKILL.md` under exactly one of two keys — `driver:` (its authorized `uv run …` command + `validator_kind:`) or `exempt:` (a one-line reason, e.g. read-only status skills). `test_skills_shell_drivers.py` asserts: (1) the map's coverage set **equals the on-disk set of `skills/*-headless/SKILL.md`** — a **new** headless skill that is neither `driver`-mapped nor `exempt`-listed **fails the test** (this is the regression gate, and it needs no prose predicate — enrollment is by directory existence, not by scanning a skill for a `module.func(` reference); (2) each `driver`-mapped script exists and exposes the documented CLI (argparse defines the flags); (3) each `driver` writes a result on ABORT; (4) each `driver` invokes its declared `validator_kind`. Legitimate explanatory references to `pen_orchestrator.execute`/`object_apply`/`apply_reconcile` in F11 prose never false-positive, because the guard checks *enrollment*, not the absence of a function name.
- **Import-boundary test (`test_driver_import_boundary.py`):** an AST test over every `*_run.py` driver asserting it **does not import** any apply-mode module (`object_apply`, `apply_reconcile`, `pen_clone_reader`, `apply_doc_patch`, and the `provision_apply_branch`/`commit_apply_clones`/`push_apply_clones` names from `nave_adapter`) and **never calls `pen_orchestrator.execute`**. Enforcement is **direct** (the driver module's own `import`/`ImportFrom`/`Call` nodes — a driver that imports a pure library which transitively touches apply code is fine; the boundary is the driver's own surface). This is the concrete realization of the "no F10 driver imports an apply-mode module" global constraint.

**Steps:**
- [ ] **Step 1: Write the acceptance matrix** across all four phases (incl. scheduled-gated cases).
- [ ] **Step 2: Author `headless-driver-map.yaml`** (enroll every headless skill as `driver` or `exempt`) and the enrollment-lint test; add the import-boundary AST test.
- [ ] **Step 3: Run `uv run pytest -q` + `git diff --check` and commit** with `test: gate the runnable spine end-to-end`.

---

## Phase gate — after F10

- Each of impact (F5), generated-artifact (F7), plan-sync (F8), and marketplace/overlay (F9) runs unattended from a trigger to a validated `result.yaml` with **zero hand-written glue**.
- Every driver is a thin assembler over a pure library `build_result`; **no F10 driver calls `pen_orchestrator.execute`** and none imports an apply-mode module (import-boundary test green). Emitted proposals are review summaries that *would* pass `execute`'s guard; applying them stays F11/apply-mode work.
- Scheduled runs gate `allow_scheduled: false` transformations to findings/proposed-actions, proven in both modes per driver.
- The `claude-plugin-v1` overlay scores an opted-in repo with real `pass`/`fail`/`unknown` per check (not `unsupported`); neutral fleet behaviour and the isolation proof are unchanged; the overlay content channel attaches only to opted-in entries with bounded, ref-pinned, unavailable-state-explicit reads.
- The `claude.context` inference step is `inference_status`-marked; `skipped`/`failed` grade `unknown`, never a silent `pass`.
- A `periodic` trigger surfaces every propose/mutate phase as due; the scheduler composition (separate PR) projects each validated result into the maintenance PR body. **This gate closes only when the `hiivmind-pulse-scheduler` PR merges.**

## Explicitly deferred (still gated on separate design)

- **Apply-mode production wiring:** executing a recorded proposal (pen push / GitHub write / base advance) — F11 shipped the library + seams; the driver that assembles `apply_ops` over real clones and calls `execute` → `reconcile_apply`, plus the real `advance_base`, remains open. See `docs/backlogs/2026-07-29-apply-mode-v2-deferrals.md` § A.
- **F4 dependency-coherence adapters:** Pre-F4 materialised the evidence but the coherence adapter family (P1) was never built; an open read-spine gap independent of F10.
