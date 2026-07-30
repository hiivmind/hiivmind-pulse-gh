# Apply-Mode Production Wiring — Design Spec

**Date:** 2026-07-30
**Status:** Approved (brainstorm) — revised after (1) an adversarial design review (Codex
`gpt-5.6-sol`, `REQUEST CHANGES` incorporated) and (2) **PR #141's single-mutator design note**
(`docs/superpowers/specs/2026-07-30-f11-apply-git-consolidation-note.md`), which supersedes the
first-draft substrate choice. Pending implementation plan.
**Origin:** `docs/backlogs/2026-07-29-apply-mode-v2-deferrals.md` § A ("Production wiring — apply-mode
is built, not yet *runnable end-to-end*"). F11 (PR #138, merged 2026-07-29) shipped the apply
**library + tests + docs**; every seam exists and is fake-tested, but nothing assembles them against
a real repo. This is the apply analogue of F10's "runnable spine" — its own small phase, spanning
the `discreteds/nave` fork and `hiivmind-pulse-gh`.

**Read alongside:** PR #141 note (the substrate decision-of-record), F11 plan
(`docs/superpowers/plans/2026-07-22-f11-apply-mode.md`), `docs/backlogs/README.md` (cross-repo map).

---

## 1. Problem — the substrate split and the two-writers hazard

F11's `execute()` (`lib/pulse/scripts/pen_orchestrator.py`) owns the apply state machine
(`provision-branch → exec → validate → commit-all → push-all → pushed`), but its two halves address
**different clone sets**:

- **Transformation half** — `nave_adapter.pen_exec(pen_name, argv, …)` (`pen_orchestrator.py:609`)
  runs the registered transformation inside a **Nave pen**.
- **Landing half** — the raw-git apply trio `provision_apply_branch` / `commit_apply_clones` /
  `push_apply_clones` (`nave_adapter.py:500–616`) runs `git checkout -b` / `git add -A && commit` /
  `git push` directly against clones at a separate `PULSE_PEN_ROOT/{owner}/{name}` root.

The acceptance suite fakes **both** halves independently (`RecordingApplyOps` + `QueuedRunner`), so
nothing verifies the transformation's output reaches the committed/pushed clone.

**PR #141 identifies the deeper flaw:** the trio is a **second independent writer** over fleet
clones Nave already owns, and that is a structural hazard regardless of correctness — state
divergence from Nave's `pen status` model, propose-only policy enforced twice by two mechanisms, and
blunt `add -A` staging that commits anything dirty rather than the proposal's `bound_paths`. The trio
has **no production callers yet**; the F11 apply driver would be its first. This is the cheapest
moment to change course.

## 2. Decision — Nave is the single mutator (PR #141)

**Exactly one system mutates fleet clones: Nave.** Extend Nave's pen surface to cover the apply-mode
needs, then **delete the raw-git trio**. Pulse's Python keeps orchestration, policy, and read-only
verification; it stops running write-git entirely.

This **resolves the substrate split by construction**: the transformation (`pen exec`) and the
landing (new Nave verbs) both operate on the **one** Nave pen — there is no second clone set, no
`pen_materialize` bridge, no double-clone. Nave's `pen status` is once again the authoritative
preflight substrate (F11's stale/dirty/expected-SHA guards check the pen that actually gets
mutated), so the earlier "wrong preflight substrate" concern dissolves.

**Rejected — Fork B** (Pulse materializes and mutates its own clones): doubles down on exactly what
PR #141 wants Pulse out of; two clone-management systems; violates the single-mutator rule. The
first draft of this spec chose Fork B and is superseded here.

**Non-goals carried from PR #141:** apply-mode git never moves into the interactive LLM session
(headless apply stays deterministic, model-free, fixture-testable, fail-closed); Nave pens are not
replaced by `git worktree` / the superpowers worktrees plugin (different domain — single-repo
session isolation vs cross-repo unattended fleet checkouts).

## 3. Nave pen-surface extensions (the `discreteds/nave` deliverable)

These are pen-domain capabilities in their own right — any multi-repo pen consumer wanting guarded,
reviewable mutation needs them. Each emits **per-repo machine-readable `--json`** (the adapter
contract: non-`--json` stdout is never parsed as data).

1. **Branch provisioning at a guarded base** — provision `pulse/apply/{proposal_id}` off the
   expected base SHA **per repo** across the selection; fail closed per repo if the branch exists or
   the SHA is missing. Shape (PR #141 open Q1, recommended): a dedicated `nave pen branch` subcommand
   (independently retryable/reportable), taking per-repo base SHAs via a **request file**
   (JSON/YAML, mirroring `materialize --request` — PR #141 open Q2), not flag-per-repo.
2. **Bounded staging on commit** — stage only the proposal's `bound_paths`; anything else dirty in
   the clone fails the commit closed rather than riding along (replaces `add -A`). Post-validation,
   so it is a commit step distinct from the transformation `pen exec` (PR #141 open Q1).
3. **Structured commit/push results** — `--json` per-repo outcomes for commit and push, including the
   **local commit SHA and the pushed remote-ref SHA + upstream** (PR #141 open Q3 — the PR-first step
   needs the remote ref as input; today `pen exec --push-changes` does not report it).
4. **Deterministic cleanup + fail-mode** — `nave pen reset <pen> --branch <name>` to unwind a partial
   provision/push, plus a documented `--keep-going`/fail-fast choice. Full cross-repo transactional
   apply is out of scope; deterministic cleanup is not.
5. **Expose the pen clone root (the read-path capability)** — a surface (e.g. `pen status --json`
   carrying each repo's clone path) so `pen_clone_reader` can locate clones for **independent**
   read-only verification. PR #141 keeps verification out-of-band of the writer deliberately (checker
   ≠ writer); that only works if Nave exposes the path. This closes the gap the note left open.

Base-guard migration: the expected-SHA guard is enforced by provisioning **at** `expected_shas[repo]`
(capability 1); the blast-radius guard is enforced by **bounded staging** (capability 2). Pulse's
read-side `paths_changed` (no-op / wrong-target detection) and `json_schema` (content) validations
stay — verified via capability 5.

## 4. Proposal & authorization model (Codex review C1 — substrate-independent)

**The driver never "loads a recorded proposal."** F6–F9 persist only
`{binding, transformation, proposal_id}` summaries (`plan_sync.py:472`, `validate_result.py:624`),
discarding `selection`, `expected_shas`, `actor`, `bound_paths`, `mutation_policy`
(`mutation_plan.py:279`) — matching the **settled F10→F11 handoff: "summaries only; apply re-derives."**
Apply obtains an authorized Proposal in two pieces:

1. **Re-derivation.** The driver re-runs the *propose* logic for the target binding (the same
   `build_proposal` path the F6–F9 producer used) to mint a **fresh** `Proposal` off **current**
   state — current `expected_shas`, `selection`, `bound_paths` — minted directly with
   `mutation_policy="allow-listed"`, never by mutating a frozen propose-mode proposal.
2. **`ApplyAuthorization` (new, workspace-repo policy).** A workspace apply-policy enumerating, per
   transformation, `{transformation, permitted_repos, policy: allow-listed}`. The driver requires the
   re-derived proposal to match — transformation authorized **and** `selection ⊆ permitted_repos` —
   before execution. The recorded `proposal_id` + a digest of the re-derived proposal is carried into
   the ledger/result for audit. The shared registry gains **no** per-transformation allow-listed flag
   (authorization lives in the workspace policy).

## 5. Pulse components (`hiivmind-pulse-gh`)

### A. Thin Nave-verb adapters + delete the trio (PR #141)

Add adapter functions for the § 3 verbs following the existing `pen_exec` / `pen_status` idiom (argv
construction + `--json` decode, fixture-testable via `PULSE_NAVE_FIXTURES`). **Delete**
`provision_apply_branch` / `commit_apply_clones` / `push_apply_clones` (`nave_adapter.py:500–616`)
and their tests. Pulse runs no write-git commands.

### B. `apply_ops` bound to Nave verbs + `execute()` allow-listed branch

The injectable `ApplyOps` protocol (`provision_branch` / `commit_repos` / `push_repos`) **stays** —
only its production binding changes: `make_apply_ops(...)` now binds to the § 5A Nave-verb adapters
(not raw git). `commit_repos` passes the proposal's `bound_paths` for bounded staging; `push_repos`
returns the per-repo commit + remote-ref SHAs from `--json` (Codex review C4). `execute()` in
allow-listed mode: validate proposal + authorization → provision branch (verb 1) → `pen_exec`
transformation (unchanged) → validate against the Nave pen via `pen_clone_reader` (verb 5) →
bounded commit (verb 2) → push (verb 3), with `pen reset` (verb 4) on partial failure. Preflight
(`pen_create` / stale-dirty `pen_status`) runs against the **Nave pen** — now correct, since the pen
is the mutated substrate. The `propose` path is byte-for-byte unchanged. `execute()` stays
subprocess-free (all Nave I/O via the injected runner).

### C. `apply_driver.py` (new) — Path A production driver, lease-first (Codex C3/C4)

`uv run` CLI. **Lease before any mutation:**
1. Resolve target binding + recorded `proposal_id`; load the workspace `ApplyAuthorization`.
2. **Create/resume the run-ledger step and acquire its lease** (`resolve_run.acquire_lease`,
   `resolve_run.py:337`) *before* any Nave mutation; held/renewed through push + PR; every retry
   inspects persisted step state first.
3. **Re-derive** the fresh allow-listed Proposal (§ 4); authorize it; resolve the **intended base
   branch** per repo from binding/repo metadata (never a `main` default — `apply_reconcile.py:432`).
4. `execute(plan, runner, read_repo_*, apply_ops=make_apply_ops(...))`.
5. On terminal `pushed`: with the per-repo pushed SHA + intended base in hand,
   `apply_reconcile.open_apply_pr` (needs both — `apply_reconcile.py:205`).
6. **Result on every exit:** pre-push exits (`blocked`/`failed`/ABORT) write a validated
   `repo-mutation` result; `apply-status` (`pushed|pr_opened|applied|rejected` —
   `validate_result.py:41`) is remote-lifecycle only, **per repo** (`apply_reconcile.py:160`); a
   multi-repo selection yields one `apply-status` per repo + an aggregate ledger step.

### D. `apply_advance_base.py` (new) — F8 doc-blob finalizer only + wire into `reconcile` (Codex C2)

v1 base advancement is the **F8 plan-sync doc-blob finalizer**, a *typed* op (not a generic
`(repo, merged_sha)` callback). On a detected merge, read the **merged document's git blob SHA** at
`merged_sha` (F8 `base.blob` is a blob SHA of confirmed content — `plan_sync.py:329` requires
`confirmed_document_blob` — not the merge commit SHA) and **compare-and-swap** the plan-sync binding's
`base.blob`, where the *expected prior blob* was recorded **before** the run (a guard is only
meaningful read-before, not at reconcile time). Idempotent + precondition-guarded; translates its own
success/no-op into the `{"state": "ok"}` contract `reconcile_apply` requires (`apply_reconcile.py:349`).
Uses **dedicated GitHub-contents read/modify/PUT logic keyed on the contents blob SHA** (or a
workspace-repo commit/PR) — **not** `object_apply`'s `marker-advance`, whose `owner/repo:marker`
target is not a REST endpoint and which returns `applied`, not `ok` (`object_apply.py:120,186,250`).
Wired into `apply_reconcile.main()`'s `reconcile` subcommand (today `advance_base=None`).

**Not in this phase:** F5-marker advancement — F5 markers advance off the *upstream
integration-validated `head_sha`* (`impact.py:456,493`), an F5 concern keyed off integration
evidence, not an apply merge. Pure-neutral transformations (`refresh-node-lockfile`) have **no base
to advance** — the merge is terminal.

### E. `gh-apply` skill (new) — interactive trigger, v1 (PR-gated)

Wraps the driver + reconcile loop behind `/gh apply <proposal>`. Scheduled auto-apply stays v2.

### F. Workspace enrollment (`hiivmind/hiivmind-workspace`) — gated on an installed engine (Codex I6)

A PR landing the **`ApplyAuthorization` policy** (§ 4) and a **real neutral proposal source** (a
neutral binding producing a `refresh-node-lockfile` / `regenerate-docs-index` proposal — none exists
in the template today). Gated on the § 3 Nave verbs **and** the pulse-gh engine being **installed** in
the workspace's plugin (per the single-developer context, a local install suffices), not merely a
`develop` merge (`docs/backlogs/README.md:120`).

## 6. Lifecycle, concurrency & result contracts (Codex C3/C4/I3/I4)

- **Lease before mutation**, held through push + PR (§ 5C).
- **SHAs from Nave `--json`:** commit + remote-ref SHAs flow from verb 3 (§ 3) through `push_repos`
  to the driver, which passes the real pushed SHA to `open_apply_pr` (never the base — the current
  acceptance wrongly passes base as `pushed_sha`, `test_apply_acceptance.py:338`).
- **Base branch verified end-to-end:** intended base resolved per repo, persisted into `apply-status`,
  required by the merge gate. `GhCliOps.view_pr` gains `baseRefName` (`apply_reconcile.py:87` omits
  it); `evaluate_merge_detected_gate` (`resolve_run.py:300`) advances only when observed base == intended
  base — a retargeted PR cannot advance the wrong base.
- **Push atomicity — claimed honestly:** even through Nave, multi-repo push is not transactional; v1
  models each repo as an independent per-repo ledger state + independent PR and finalizes
  independently, with `pen reset` (verb 4) for deterministic cleanup of a partial push. No cross-repo
  atomicity is claimed. (The v1 neutral proof is single-repo.)

## 7. Testing (Codex I5)

- **Pulse layer** drives acceptance through the **real `apply_driver` + production factories**
  against **Nave-verb `--json` fixtures** (`PULSE_NAVE_FIXTURES`): re-derivation + authorization
  (an unauthorized proposal is refused), lease ordering + contention (a competing actor is
  lease-blocked *before* it mutates, real `resolve_run` files), pushed-SHA correctness (assert the
  result carries the verb-reported remote-ref SHA, not the base), base-branch correctness (a
  retargeted/wrong-base merge is rejected; a `develop` repo does not default to `main`), the F8
  finalizer (command-test the **real** GitHub-contents adapter against actual `gh` JSON shapes;
  compare-and-swap on the recorded prior blob; idempotent re-run), and crash/resume.
- **The cross-substrate "output actually lands" proof moves to the Nave fork's suite** — the verbs
  are where branch/commit/push against real clones are exercised end-to-end. Pulse asserts the
  adapter's argv + `--json` decode contract; the fork asserts the git reality. This is the clean
  consequence of single-mutator: the writer's integration test lives with the writer.
- **Import-boundary/neutrality guard (PR #141):** the F10 import-boundary test moves from guarding
  four raw-git names to guarding that the **single apply driver** is the sole caller authorized to
  pass commit/push/branch flags; the structural neutrality guard extends to `apply_driver` /
  `apply_advance_base` (no `profile_dispatch` / claude-plugin imports; no `profile:claude-plugin`
  predicate in the apply path). The `gh` PR/merge transport stays an injected offline boundary tested
  against real `gh` JSON shapes.

## 8. Cross-repo & sequencing

Ordered by dependency (`docs/backlogs/README.md` map):

1. **`discreteds/nave` fork** (feature → main): the § 3 verbs + their `--json` contracts + Rust
   tests; install locally. **First** — Pulse cannot call verbs that do not exist.
2. **`hiivmind-pulse-gh`** (`feat/*` → `develop`): § 5 components A–E + § 4/§ 6 + delete the trio +
   § 9 doc debt + tests. Depends on 1.
3. **`hiivmind/hiivmind-workspace`** (`feat/*` → `main`): § 5F enrollment. **Last**, after the engine
   is installed.

## 9. Doc debt to close while wiring (Codex Minor)

Update the orchestrator docstring's "propose-only, unconditionally" (`pen_orchestrator.py:21`) and
`PenPlan.request_push` "always forbidden" (`pen_orchestrator.py:136`) to reflect allow-listed
landing (preserving the actual propose control flow), and `repository-mutations.md` C1's
*Implementation* line from `nave_adapter.provision_apply_branch(...)` to the Nave verb (the invariant
text — per-proposal branch off `expected_shas[repo]`, pushes never target a base branch — is
unchanged).

## 10. Phase gate

- A re-derived, workspace-authorized neutral `allow-listed` proposal on a real repo lands — **through
  Nave verbs, with no raw-git in Pulse** — as a pushed `pulse/apply/{id}` branch + opened PR against
  the **intended** base; on a detected merge into that base, the F8 plan-sync base advances off the
  merged document's blob (doc-binding case); result validates as `apply-status`/`applied`.
- The raw-git trio is **deleted**; Nave is the sole clone mutator; the import-boundary guard enforces
  the single apply driver as the only flag-bearing caller.
- The **lease is acquired before any mutation**; a competing actor is blocked before it acts.
- Every F11 pre-exec gate fires and fails closed against the **Nave pen**; no push on a failed gate;
  the push never targets a base branch; a wrong-base merge is rejected; bounded staging commits only
  `bound_paths`.
- `advance_base` is the typed F8 doc-blob finalizer (compare-and-swap on the recorded prior blob,
  idempotent, off the merged document's blob), returning `{"state": "ok"}`. F5-marker advance is out
  of scope.
- The apply engine carries no plugin imports and evaluates no `profile:claude-plugin` predicate; the
  `propose` path through `execute()` is byte-for-byte unchanged.
