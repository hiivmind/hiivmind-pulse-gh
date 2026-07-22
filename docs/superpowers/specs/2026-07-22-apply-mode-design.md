# Apply-Mode Design: A Repository-Neutral Landing Path

**Date:** 2026-07-22
**Status:** design / scoping — pre-plan; one open decision flagged in § Design forks.
**Scope:** The deferred "apply-mode" that F6–F9 (and F10's drivers) all stop short of. What it is, why it is blocked, and — the load-bearing question — whether it is a plugin feature or a general one.
**Related:** `docs/superpowers/audits/2026-07-22-f-series-runnable-spine-audit.md` (the driver-layer gap), `docs/superpowers/plans/2026-07-22-f10-runnable-spine.md` (makes phases *run*; this makes them *land*), `docs/superpowers/audits/2026-07-13-fleet-scope-audit.md` (the neutral-control-plane mandate this design honors).

---

## 1. The headline: apply-mode is repository-neutral, and must stay that way

The first question to answer, because it governs everything else: **is apply-mode geared toward plugins, or set up for any repository?** The 2026-07-13 fleet-scope audit's mandate was explicit — *"establish a neutral fleet control plane, then attach ecosystem and organization profiles, and finally run the existing plugin/corpus workflows as one dogfood profile."*

Apply-mode is squarely on the neutral side of that line, and the evidence is already in the tree:

- **The apply machinery has zero plugin knowledge.** A proposal is `{id, selection (owner/name…), transformation (registry id), expected_shas, mutation_policy, actor}`. The pen orchestrator, the transformation registry, the expected-SHA guard, the `propose|allow-listed|allow` policy, and the eventual push/PR flow operate on those primitives alone. None of them reads `.claude-plugin/`, `CLAUDE.md`, or `skills/`.
- **The registry is already 5-of-7 neutral.** `format-python`, `refresh-node-lockfile`, `regenerate-docs-index`, `regenerate-from-template`, and `plan-sync-doc-patch` are repo-agnostic. Only `marketplace-entry-update` and `regenerate-corpus-navigate-skill` are plugin/corpus-specific — and both are **opt-in F9 overlay entries** (`applies_to: profile:claude-plugin`) that merely *use* the neutral apply machinery. Apply-mode does not know or care that they are plugin-related.
- **`applies_to` is the general applicability grammar** (`always | profile:<id> | capability:<id> | evidence_path:<glob>`), the same one scorecard dispatch uses — not a plugin gate.

So the design principle is inherited, not invented: **apply-mode is a neutral landing path for any registered transformation on any bound repository. Plugin-specific transformations are just registry entries behind a `profile:claude-plugin` predicate — one dogfood profile among many, exactly as the fleet-scope audit prescribed.**

### The neutrality trap to avoid (the audit's real warning)

The fleet-scope audit's sharpest point was not about the mechanics — those are neutral — but about **what gets demonstrated**. A green suite that only exercises the plugin's own `marketplace-entry-update` "can prove the overlay works but cannot prove general fleet behavior." Apply-mode must not fall into that: its acceptance matrix has to land at least one **neutral transformation on a non-plugin repository** (e.g. `refresh-node-lockfile` on a Node repo, `regenerate-docs-index` on a docs repo), with the two overlay transformations as a *separate* dogfood demonstration. Two suites, per the audit — `applies` for neutral repos, plus an opt-in overlay demonstration — and coverage that distinguishes "not applicable" from "not tested."

This also surfaces a neutral executor concern the plugin-only view would miss: neutral transformations need the **target repo's own toolchain** present in the pen (a Python formatter for `format-python`, `npm` for `refresh-node-lockfile`, a docs generator for `regenerate-docs-index`). Apply-mode's executor-delivery story must therefore handle *arbitrary ecosystem tooling*, and treat "required tool absent in this pen" as a fail-closed `blocked`, per ecosystem — not assume a single applier.

---

## 2. What apply-mode is: two paths plus one trust model

Today `pen_orchestrator.execute` blocks any `mutation_policy` other than `propose` before making a single Nave call. The `allow-listed` and `allow` semantics are defined but unimplemented. Apply-mode is the machinery behind them, across two independent paths:

- **Path A — repository-file apply (through a Nave pen).** F7 regeneration, F8 doc patches, F9 corpus/manifest regen. A validated pen exec becomes a commit + a pushed branch + a PR.
- **Path B — GitHub-object apply (through the `gh` API under `on_mutation`).** F5 marker updates, F8 issue/milestone patches, F9 marketplace-entry patch, F2 profile-metadata commits. A validated proposal becomes a guarded `gh` write.

Both share one **trust model**: registered transformation + `expected_shas`/precondition guard + post-exec validation + `allow_scheduled` gate + attribution. Apply changes *what happens after validation succeeds*, never the gates before it.

---

## 3. Concrete blockers (documented, real)

**B1 — Executor delivery (Path A), generalized.** A transformation's argv must run *inside the target repo's pen checkout*. `regenerate-from-template` calls the installed `nave` CLI and is fine; `plan-sync-doc-patch` runs `apply_doc_patch.py` by a **plugin-repo-relative path that does not resolve in a doc-repo pen** (per `lib/patterns/plan-sync-binding.md`). Apply needs every applier reachable on `PATH` in the checkout — a console entry point or a `nave` subcommand — and, neutrally, needs each ecosystem transformation's tool present or a clean `blocked`.

**B2 — Bound-path enforcement (Path A).** The output allowlist is per-binding *dynamic* (the specific doc/output path) but the F6 registry allowlist and `validation` are *static* (`{kind: none}`), so the bound path is currently **self-attested** by the caller-authored patch descriptor. Apply needs the bound path carried as **immutable proposal metadata the orchestrator enforces**, plus a `validation: {kind: paths_changed, paths:[…]}` kind asserting exactly those paths changed — moving the guard from script-level to orchestrator-level.

**B3 — Confirmation & base advancement (both paths).** F5/F8 bases advance "only after both sides confirm application." A push is not confirmation — a **merge** is. Base/marker advancement must key off the merged commit via a two-phase *propose-PR → detect-merge → advance-base* loop, using the existing run ledger (`resolve_run.py`) for the resumable cross-repo state.

**B4 — Partial-failure independence.** The doc-pen path and the GitHub path fail independently; `finalize` already advances only confirmed values. Apply must preserve that and be resumable.

**B5 — Result contract.** `repo-mutation` (and the object-side results) need `applied`/`pr_opened` states, the PR URL, and the pushed/merged SHA — built from the same `Proposal` that gated execution, never reconstructed.

---

## 4. Design forks

| Fork | Options | Recommendation |
|---|---|---|
| **Repo-file apply granularity** | push branch + open PR (human merges) · direct push to branch · auto-merge | **PR-first** — apply = push a branch + open a PR (Path A) / `gh` write (Path B); a human or CI merges; base advances on merge detection. Keeps a review gate and closes the improvisation gap. |
| **Scheduled auto-apply** | in v1 · deferred | **Defer** — v1 apply is interactive / PR-gated; `allow` (unattended direct push) is a bounded v2 behind `allow_scheduled: true` + a workspace apply policy. |
| **Executor delivery** | plugin console entry points · `nave` subcommands · Nave injects the applier | **Console entry points**, preferring a `nave` subcommand where one exists (as `regenerate-from-template` already does); each ecosystem tool must be present in the pen or the run is `blocked`. |

> **Open decision (flagged for the author):** the v1 boundary above assumes **PR-first, human-merges, scheduled auto-apply deferred**. That is the recommendation; if you want v1 to push directly or to include scheduled auto-apply, the confirmation model (B3) and the authority model change accordingly, and the phase below re-shapes.

---

## 5. Proposed phase shape — F11 apply-mode

F10 makes phases *run* (propose-only, triggered); **F11 makes them *land***. Task sketch, all under the PR-first recommendation:

- **T1 — Executor on PATH.** Ship plugin appliers (e.g. `apply_doc_patch`) as installed console entry points / `nave` subcommands; registry argv references the installed name, never a repo-relative path. Per-ecosystem "tool absent → `blocked`" handling.
- **T2 — Orchestrator-enforced bound paths.** Carry `bound_paths` as immutable proposal metadata; add `validation: {kind: paths_changed}`; the orchestrator (not a script) rejects any out-of-allowlist change.
- **T3 — `allow-listed` commit/push in `pen_orchestrator`.** Implement the reserved policy: on a validated pen, `pen_exec(commit=True, push_changes=True)` to a per-proposal branch; still fail-closed on stale/dirty/validation.
- **T4 — PR open + merge detection + two-phase base advance.** Pulse opens the PR; a follow-up reconciliation detects the merge and advances the F5/F8 base off the merged SHA via the run ledger. Resumable; partial-application-safe.
- **T5 — GitHub-object apply under `on_mutation`.** `allow-listed`/`allow` `gh` writes for F5 markers, F8 issue/milestone patches, F9 marketplace entry, precondition-guarded and idempotent.
- **T6 — Result states + neutral acceptance matrix.** `applied`/`pr_opened` states; acceptance **must** include a neutral transformation on a non-plugin fixture repo, with the overlay transformations demonstrated separately (two-suite discipline). Anti-regression: a test that apply-mode carries no `claude`/`plugin`/`skills`/`SKILL.md`/`CLAUDE.md`/`marketplace` string outside the F9 overlay entries.

## 6. Explicitly deferred / dependent

- **`allow` (unattended direct push) and scheduled auto-apply** — v2, behind an explicit workspace apply policy.
- **Auto-merge** — out of scope; landing is a reviewed merge.
- **F4 dependency-coherence apply.** The richest *neutral* apply use-case — bumping a dependency across the fleet and landing the lockfile change — depends on the **unbuilt F4 dependency-coherence adapters**. `refresh-node-lockfile`/`format-python` give apply-mode neutral proof today; fleet-wide coherence apply waits on F4. This dependency is a feature of honest scope, not a blocker for F11.
