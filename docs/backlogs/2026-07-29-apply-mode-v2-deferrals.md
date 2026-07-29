# Backlog: apply-mode (F11) — v2 features, production wiring, and dependent work

**Date:** 2026-07-29
**Status:** Open (index)
**Source:** F11 apply-mode (PR #138, merged to `develop` 2026-07-29). F11 delivered the
**library + tests + docs** for landing a validated proposal, with a whole-branch review
verdict of SHIP. What it deliberately did **not** deliver — by design boundary, by injected
seam, or by dependence on other unbuilt work — is captured here so the decisions survive
outside PR history.

**Read first:** `docs/superpowers/plans/2026-07-22-f11-apply-mode.md` § "Explicitly deferred"
and § "Global Constraints"; `docs/superpowers/specs/2026-07-22-apply-mode-design.md` § 4/§ 6.
This index rolls those up and adds the production-wiring gap the plan implied but did not
itemize.

---

## A. Production wiring — apply-mode is built, not yet *runnable end-to-end* [HIGH]

This is the same three-layer gap the F-series hit before (see the 2026-07-22 runnable-spine
audit): the **library** and **tests** exist, but nothing assembles the real seams into a
production apply run. Every seam below has a real implementation shipped in F11 — they are
just not wired together by a driver/trigger.

1. **The Path A apply driver.** `pen_orchestrator.execute` takes an injected `apply_ops`
   (provision / commit / push). F11 ships the real ops (`nave_adapter.provision_apply_branch`,
   `commit_apply_clones`, `push_apply_clones`) and the real clone reader
   (`pen_clone_reader.make_pen_clone_reader`), but **no driver binds `apply_ops` over a
   pen's resolved clone paths and calls `execute` → then `apply_reconcile`** in production.
   Tests inject fakes; production has no caller. Needs a `uv run` driver (and a trigger:
   heartbeat / scheduler / CLI) that: resolves an `allow-listed` proposal → builds the real
   reader + `apply_ops` from the clone root → `execute` → on `pushed`, `open_apply_pr` →
   `reconcile_apply`.

2. **Real `advance_base` implementation.** `apply_reconcile.reconcile_apply` advances the
   base through an **injected `advance_base(repo, merged_sha)` seam**; the real F5-marker /
   F8-`base.blob` mutation is not written. Needs a concrete `advance_base` that lands the
   `integration_tested_sha` marker (F5) / plan-sync base (F8) off the **merged** SHA,
   guarded and idempotent. Until then the bare `reconcile` CLI runs with `advance_base=None`
   (marks the step done, delegates base advancement).

3. **Clone-root materialization bridge.** The reader resolves clones from `PULSE_PEN_ROOT`
   with a `{owner}/{name}` layout — a *contract*, because Nave exposes no local clone path
   (`pen_orchestrator.py` docstring). Nothing bridges a real Nave pen's on-disk layout to
   that contract. Needs either a Nave surface that prints clone roots (probe it, prefer it)
   or a documented out-of-band materialize step that lays clones out per the contract.

4. **Path B emitter wiring beyond the demonstrator.** `object_apply` is the complete Path B
   engine; F11 wired the **F8 issue-field patch** as the concrete demonstrator and
   *documented* the F5-marker and F9-marketplace integration points. Those two are not yet
   concretely wired to construct their `ObjectWrite` + `Precondition` and call
   `apply_object_write`.

**Recommendation:** A. is the "runnable spine for apply" — its own small phase, mirroring F10.
Until it lands, apply-mode is exercised only through fixtures, never against a real repo.

---

## B. v2 features — deferred by explicit design boundary [MEDIUM]

The v1 boundary was settled as **PR-first, human/CI merges**. These change the confirmation
model and are their own scope.

1. **`allow` (unattended direct push).** `mutation_policy: allow` is reserved and **blocked in
   v1** (`pen_orchestrator` and `object_apply` both return `blocked`). v2 unblocks it behind
   `allow_scheduled: true` **and** an explicit workspace apply policy. No PR review gate, so
   the whole trust argument shifts — design it before building.

2. **Scheduled auto-apply.** v1 apply is interactive / PR-gated. Unattended scheduled apply
   pairs with (1) and the workspace apply policy. Deferred with it.

3. **Single-repo-atomic Path A push.** v1 uses **commit-all-then-push** over the whole
   selection (so a mid-selection failure leaves unpushed local commits, never a stranded
   remote push). A per-repo-atomic push is only revisitable **if** a future Nave surface
   yields per-repo `pen exec` signal (today `exec_pen` bails at the first failing repo with
   opaque, non-attributable output).

---

## C. Out of scope by design (not backlog) — recorded so it is not re-proposed

- **Auto-merge.** Pulse **never merges** — landing is always a reviewed merge (human/CI).
  Pulse opens the PR and detects the merge; it does not close the loop itself. This is a
  permanent non-goal, not a deferral.

---

## D. Dependent on other unbuilt work [MEDIUM]

1. **F4 dependency-coherence apply.** The richest *neutral* apply use-case — bump a dependency
   across the fleet and land the lockfile change — depends on the **unbuilt F4
   dependency-coherence adapters** (Pre-F4 #128 materialized the evidence; the adapters that
   consume it were never built; `dependency-updates` reports `unsupported`).
   `refresh-node-lockfile` / `regenerate-docs-index` already give apply-mode its neutral proof;
   fleet-wide coherence apply waits on F4. See
   `docs/backlogs/2026-07-22-f1-f8-phase-deferrals.md` and the F-series notes.

---

## E. Tooling note (not this repo) [LOW]

- **agy `write_file` permission drift.** F11's SDD execution ran on the `swingle` agy pack;
  agy **1.1.8** gates the `write_file` tool that the pack (verified 1.1.5) assumed passed under
  default policy, so the run used `--dangerously-skip-permissions`. Worth a `swingle-verify agy`
  in the sdd-dispatch plugin — not a hiivmind-pulse-gh change.

---

## Suggested priority

1. **A. Production wiring** — the apply "runnable spine" (driver + real `advance_base` +
   clone-root bridge). Without it, apply-mode never runs against a real repo.
2. **D.1 F4 adapters** — unlocks the flagship neutral apply use-case (and closes a standing
   read-spine gap independent of apply-mode).
3. **B.1/B.2 `allow` + scheduled auto-apply** — when unattended landing is actually wanted;
   needs the workspace apply-policy design first.
4. **A.4 Path B emitter wiring** — as F5-marker / F9-marketplace object landing gains a consumer.
