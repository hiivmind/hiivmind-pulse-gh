# Apply-Mode Production Wiring — Design Spec

**Date:** 2026-07-30
**Status:** Approved (brainstorm) — revised after adversarial design review (Codex `gpt-5.6-sol`,
2026-07-30, `REQUEST CHANGES` fully incorporated) — pending implementation plan
**Origin:** `docs/backlogs/2026-07-29-apply-mode-v2-deferrals.md` § A ("Production wiring — apply-mode
is built, not yet *runnable end-to-end*"). F11 (PR #138, merged 2026-07-29) shipped the apply
**library + tests + docs**; every seam exists and is fake-tested, but nothing assembles them
against a real repo. This is the apply analogue of F10's "runnable spine" — its own small phase.

**Read alongside:** `docs/superpowers/plans/2026-07-22-f11-apply-mode.md` (design-of-record for the
library), `docs/backlogs/README.md` (cross-repo dependency map + layer-completeness matrix).

---

## 1. Problem — the integration the fakes never checked

F11's `execute()` (`lib/pulse/scripts/pen_orchestrator.py`) owns the apply state machine:

```
provision-branch → exec (transformation) → validate → commit-all → push-all → (pushed)
```

Two halves address **different clone sets**:

- The **landing half** — `apply_ops.provision_branch/commit_repos/push_repos`
  (`pen_orchestrator.py:580,642,670`) — operates on local git clones at
  `PULSE_PEN_ROOT/{owner}/{name}` (what `pen_clone_reader` reads and the three
  `nave_adapter.*_apply_clones` git ops mutate).
- The **transformation half** — `nave_adapter.pen_exec(pen_name, argv, …)`
  (`pen_orchestrator.py:609`) — runs the registered transformation inside a **Nave pen**, whose
  on-disk clone path Nave does not expose (`pen_orchestrator.py:36-49`: `pen show`/`pen status`
  carry no clone path; `pen exec` stdout is opaque-by-contract; `nave materialize` fetches from
  the GitHub API, not the working tree).

For a change to land, the transformation's output must reach the same clones that get committed and
pushed. The acceptance suite wires a fake `RecordingApplyOps` **and** a fake `QueuedRunner` for
`pen_exec`, fully decoupled — so **nothing verifies that the transformation's output ever reaches
the committed/pushed clone.** That "same on-disk clone" integration is the core production-wiring
gap (§A.3), and it forces a substrate decision F11 left implicit.

The merged code already committed to landing via **git-ops on local clones** (not `pen_exec`'s own
`--push-changes`) — deliberately, to get per-proposal branch targeting (C1) and per-repo failure
signal (I4, which `exec_pen`'s opaque first-failure bail cannot give). The only unresolved question
is where the transformation's file changes come from on those local clones.

## 2. Decision — local materialized clones (Fork B)

**Apply materializes its own real git clones at `PULSE_PEN_ROOT/{owner}/{name}` at the guarded base
SHA, runs the registered transformation applier directly in each clone, then commits and pushes.**

- **Propose** stays Nave-scale discovery (`pen_exec` scans/dry-runs the fleet — Nave's value).
- **Apply** operates on a handful of materialized clones for the already-selected selection — cheap
  to clone, guaranteed real worktrees with an `origin` push remote, fully attributable, and
  **entirely in pulse-gh** (no forked-Nave surface, no dependency on Nave's pen-storage layout).

Rejected — **Nave-storage bridge** (`PULSE_PEN_ROOT` → Nave's real pen clones): blocked on the
`discreteds/nave` fork's pen-storage internals, risks Nave clones not being pushable worktrees, and
makes this a 3-repo effort. The pen-exec-native push variant was already rejected in F11 for C1/I4.

The propose/apply substrate split becomes explicit: **Nave pen for discovery, local clone for
landing.** Apply acts on a narrow selection, and all apply gates (expected-SHA, `paths_changed`,
`json_schema`) already read the clone through `pen_clone_reader`, which works identically on a
locally materialized clone.

**Consequence made explicit (review I1):** the allow-listed path is a *distinct execution branch*
in `execute()`, not a one-call swap. In allow-listed mode the **materialized local clone is the
authoritative preflight substrate** — cleanliness, base-SHA, and identity are checked against it,
**not** against an unrelated Nave pen. `execute()` in allow-listed mode does **not** run
`pen_create`/stale-dirty `pen_status` against a Nave pen (`pen_orchestrator.py:452,477`); those
would block on irrelevant Nave dirt while leaving the real landing substrate unchecked. The
`propose` path is byte-for-byte unchanged (Nave create/status/exec, terminates at `proposed`).

## 3. Proposal & authorization model (review C1)

**The driver never "loads a recorded proposal."** F6–F9 producers persist only
`{binding, transformation, proposal_id}` summaries (`plan_sync.py:472`, `validate_result.py:624`);
they discard `selection`, `expected_shas`, `actor`, `bound_paths`, and `mutation_policy` — the
load-bearing `Proposal` fields (`mutation_plan.py:279`). This matches the **settled F10→F11 handoff:
"summaries only; apply re-derives."**

So apply obtains an authorized Proposal in two independent pieces:

1. **Re-derivation.** The driver re-runs the *propose* logic for the target binding (the same
   `build_proposal` path the F6–F9 producer used) to mint a **fresh** `Proposal` off **current**
   repository state — current `expected_shas`, current `selection`, current `bound_paths`. A base
   that moved since the original propose is reflected now, not stale. The fresh proposal is minted
   directly with `mutation_policy="allow-listed"` (an authorized proposal), never by mutating a
   frozen propose-mode one.
2. **`ApplyAuthorization` (new, workspace-repo policy).** A workspace apply-policy document
   enumerates, per transformation: `{transformation, permitted_repos, policy: allow-listed}`. The
   driver checks the re-derived proposal against it — transformation is authorized **and**
   `selection ⊆ permitted_repos` — before execution. The recorded `proposal_id` (and a content
   digest of the re-derived proposal) is carried into the run ledger and the result for
   audit/traceability. No apply runs without a matching authorization; the registry gains no
   per-transformation "allow-listed" flag (authorization lives in the workspace policy, not the
   shared registry).

This removes the review's central contradiction ("load the recorded proposal … never
reconstructed") — apply **re-derives** by design, and authorization is explicit and workspace-owned.

## 4. Components

All in `hiivmind-pulse-gh` unless noted. Each has one purpose and a well-defined interface.

### A. `pen_materialize.py` (new) — the clone bridge (§A.3, hardened per review I2)

`materialize(selection, base_shas, clone_root, *, clone_urls) -> dict[repo, {"state": …, "reason"?}]`

For each repo, ensure a **Pulse-owned, proposal-scoped** clone under
`{clone_root}/{proposal_id}/{owner}/{name}` (proposal-scoped so distinct proposals/processes never
share a mutable checkout — review C3/I2). Contract:

- **Ownership + atomicity:** clone into a temp dir, then atomically promote; drop a Pulse ownership
  marker. Never hard-reset a path Pulse cannot prove it owns.
- **Identity:** validate normalized repo names (reject `.`/`..` path components — `mutation_plan.py:299`
  checks only slash count); canonicalize and verify `origin` matches the expected repo; the reader's
  `.git`-only check (`pen_clone_reader.py:67`) is not sufficient identity on its own.
- **Base guarantee:** fetch the required refs, verify `git cat-file -e <base>^{commit}`, check out
  clean at `base_shas[repo]`; establish *clean* (remove/reject untracked+ignored — a hard-reset
  alone does not) so `paths_changed` sees only the transformation's diff.
- **Auth:** an authenticated clone/fetch strategy that supports private repos **without embedding
  credentials** in the path or remote URL.
- **Commit identity:** configure a deterministic `user.name`/`user.email` in the clone (a clean CI
  machine may have none), so attribution is reproducible.
- **Retry / branch reuse:** a leftover `pulse/apply/{id}` from an aborted run makes `provision_apply_branch`'s
  `checkout -b` fail (tested — `test_nave_adapter.py:724`); materialize resets to a known-clean base
  and the substrate reuses-or-fails-closed the existing branch (never blind force-push).
- **Partial failure:** any repo failing materialization fails the **whole selection** before any
  execution (no half-materialized run proceeds).
- **Submodules/LFS:** explicitly out of scope for v1 — documented as unsupported, not silently
  mishandled.

Pure I/O; no decision logic. This is the sole writer that establishes the contract the reader and
the `*_apply_clones` ops assume.

### B. `run_transformation` seam + `make_apply_ops(clone_paths, entry)` (new) + explicit `execute()` allow-listed branch (review I1)

- **Extend the `ApplyOps` protocol** with `run_transformation(argv) -> dict[repo, {"state": …, "reason"?, "commit_sha"?}]`.
- **`execute()` allow-listed branch:** validate the immutable proposal + authorization; validate
  local clone identity/cleanliness/base against the **materialized clone** (not a Nave pen);
  provision branches; run `apply_ops.run_transformation(argv)` (subprocess of `command_argv`,
  `cwd=clone`, `shell=False`) in place of `pen_exec`; validate; commit-all; push-all. Per-repo
  result semantics are exact: **missing tool → `blocked`** (naming tool+ecosystem, the T1 contract);
  **nonzero exec → `failed`**; **any repo failing prevents validation/commit everywhere**;
  unknown/missing result keys **fail closed**. The `propose` path is untouched.
- **`make_apply_ops(clone_paths, entry)`** binds `provision_branch/commit_repos/push_repos` to the
  existing `nave_adapter.*_apply_clones` fns and `run_transformation` to the local runner. The
  landing ops must additionally **return the local commit SHA and the verified remote-ref SHA**
  per repo (review C4) — `commit_apply_clones`/`push_apply_clones` today return only `{state}`
  (`nave_adapter.py:538,591`); they are extended to surface SHAs so the driver can open a correct PR
  and write a valid result.

### C. `apply_driver.py` (new) — Path A production driver (§A.1), lease-first (review C3/C4)

`uv run` CLI. Flow, **lease before any mutation**:

1. Resolve the target binding + recorded `proposal_id`; load the workspace `ApplyAuthorization`.
2. **Create/resume the run-ledger step and acquire its lease** (`resolve_run.acquire_lease`,
   `resolve_run.py:337`) — *before* materialization or any git mutation. Every retry inspects
   persisted step state before acting; the lease is held/renewed through push and PR creation.
3. **Re-derive** the fresh `allow-listed` Proposal (§3); authorize it against the policy; resolve
   the **intended base branch** per repo from the binding/repo metadata (never a `main` default —
   `apply_reconcile.py:432`).
4. `pen_materialize.materialize(...)` → proposal-scoped clone paths.
5. `make_pen_clone_reader(clone_root, selection)` + `make_apply_ops(clone_paths, entry)`.
6. `pen_orchestrator.execute(plan, runner, read_repo_*, apply_ops=…)`.
7. On terminal `pushed`: with the per-repo pushed SHA + intended base branch in hand,
   `apply_reconcile.open_apply_pr` (which needs both — `apply_reconcile.py:205`).
8. **Result on every exit:** a **pre-push** exit (`blocked`/`failed`/ABORT) writes a validated
   `repo-mutation` result; `apply-status` (`pushed|pr_opened|applied|rejected` —
   `validate_result.py:41`) is reserved for the remote lifecycle only. Per-repo vs aggregate is
   defined explicitly: `apply-status` is **per repo** (its `selection` is one repo — `apply_reconcile.py:160`),
   and a multi-repo selection produces one `apply-status` per repo plus an aggregate ledger step.

### D. `apply_advance_base.py` (new) — F8 doc-blob finalizer only + wire into `reconcile` CLI (review C2)

v1 base advancement is the **F8 plan-sync doc-blob finalizer** — a *typed* operation, not a generic
`(repo, merged_sha)` callback:

- On a detected merge, read the **merged document's git blob SHA** at `merged_sha` (F8 `base.blob`
  is a blob SHA of confirmed document content — `plan_sync.py:329` requires `confirmed_document_blob`
  — **not** the merge commit SHA), then **compare-and-swap** the plan-sync binding's `base.blob`:
  the *expected* prior blob is the value recorded **before** the run (a stale-state guard is only
  meaningful if read before, not at reconcile time — review C2).
- Idempotent (re-advancing an already-advanced base is a no-op) and precondition-guarded (a drifted
  base blocks, never blind-overwrites). The finalizer translates its own success/no-op into the
  `{"state": "ok"}` contract `reconcile_apply` requires (`apply_reconcile.py:349`) — the review found
  `object_apply` returns `applied`, and its `owner/repo:marker` target isn't a real REST endpoint
  (`object_apply.py:120,186`), so this finalizer uses **dedicated GitHub-contents read/modify/PUT
  logic keyed on the contents blob SHA**, or lands the change as a workspace-repo commit/PR — it does
  **not** route through `object_apply`'s unimplemented `marker-advance` transport.
- Wired into `apply_reconcile.main()`'s `reconcile` subcommand (today `advance_base=None`).

**Not in this phase:** F5-marker advancement is **not apply's job** — F5 markers advance off the
*upstream integration-validated `head_sha`* (`impact.py:456,493`), which is an F5 concern keyed off
integration evidence, not an apply PR's merge commit. It is removed from this phase entirely (it was
mis-scoped into apply in the first draft). Pure-neutral transformations (`refresh-node-lockfile`)
have **no base to advance** — the detected merge is terminal.

### E. `gh-apply` skill (new) — the interactive trigger (§A.1 trigger, v1)

Wraps the driver + reconcile loop behind `/gh apply <proposal>`. v1 is **interactive / PR-gated**;
scheduled auto-apply stays v2 (needs the workspace apply-policy design).

### F. Workspace enrollment (`hiivmind/hiivmind-workspace` repo) — gated on an installed engine (review I6)

A small PR that lands the **`ApplyAuthorization` policy** (§3) and a **real neutral proposal
source** (a neutral binding that produces a `refresh-node-lockfile` / `regenerate-docs-index`
proposal — none exists in the template today; the generator template holds only the plugin dogfood
generator — review I6). Enrollment is gated on the **engine being installed in the workspace's
plugin** (per the single-developer context, a local install of the merged plugin suffices — a formal
release is not required), **not** merely on the pulse-gh `develop` merge, because a `develop` merge
does not put the engine in an installed plugin (`docs/backlogs/README.md:120`, feature→develop→
release→main).

## 5. Lifecycle, concurrency & result contracts (review C3/C4/I3/I4)

- **Lease ordering:** lease acquired before materialize/mutation, held through push + PR (§4C).
- **SHAs threaded:** landing ops return per-repo local commit SHA + verified remote-ref SHA; the
  driver passes the real pushed SHA to `open_apply_pr` (never the base SHA — the current acceptance
  wrongly passes the base as `pushed_sha`, `test_apply_acceptance.py:338`).
- **Base branch verified end-to-end:** intended base is resolved per repo (not defaulted), persisted
  into `apply-status`, and the merge gate requires it. `GhCliOps.view_pr` gains `baseRefName`
  (`apply_reconcile.py:87` omits it today); `evaluate_merge_detected_gate` (`resolve_run.py:300`)
  advances only when the observed base equals the intended base — a retargeted PR cannot advance the
  wrong base.
- **Push atomicity — claimed honestly (review I3):** commit-all-then-push protects against a
  mid-commit failure but **not** a mid-push failure (`push_apply_clones` pushes sequentially —
  `nave_adapter.py:602`; A can be pushed when B fails). v1 models each repo as an **independent
  per-repo ledger state + independent PR** and finalizes them independently; the design does **not**
  claim cross-repo push atomicity. (The v1 neutral proof is single-repo, so this is bounded; the
  multi-repo partial-push case is a tested acceptance scenario, not an atomicity guarantee.)

## 6. Scope boundary

**IN — the "apply runnable spine":** a re-derived, workspace-authorized `allow-listed` proposal for
a **neutral** transformation on a real fixture repo lands as a pushed `pulse/apply/{proposal_id}`
branch (never a base branch) + an opened PR against the **intended** base; on a **detected merge**
into that base (never a push), the **F8 plan-sync base.blob** advances off the merged document's
blob (for the doc-binding case); the result validates as `apply-status`/`applied` with PR URL +
merged SHA. Interactive trigger. All F11 pre-exec gates still fire and fail closed against the
**local materialized clone**.

**DEFERRED (captured, not built):**
- **F5-marker advancement** — an F5 concern (keyed off integration evidence, not an apply merge);
  not apply's job.
- **F9-marketplace + F2-profile Path B emitter wiring** (the rest of §A.4) — until those apply
  consumers are wanted.
- **Scheduled auto-apply + `allow`** (unattended direct push) — v2, behind an explicit workspace
  apply-policy + `allow_scheduled: true` (§B).
- **F4 dependency-coherence apply** — blocked on the unbuilt F4 adapters (§D.1).
- **Submodules/LFS, cross-repo push atomicity** — documented boundaries (§4A, §5).
- **Auto-merge** — permanent non-goal (§C); landing is always a reviewed merge.

## 7. Testing (review I5)

Drive acceptance through the **real `apply_driver` and production factories** (not a hand-assembled
sequence), against a temp-git fixture whose `origin` is a local **bare** repo (no network):

- `pen_materialize` clones the fixture into a proposal-scoped `PULSE_PEN_ROOT` at a base SHA; the
  real transformation runs locally; its output **actually reaches** the clone that
  `commit_apply_clones`/`push_apply_clones` land — assert the pushed commit **differs from the base**
  and **matches the bare remote ref** (the integration the double-fake never checked).
- **Re-derivation + authorization:** a proposal not covered by the `ApplyAuthorization` is refused;
  a covered one proceeds.
- **Lease ordering + contention:** a second competing actor is lease-blocked *before* it mutates;
  real `resolve_run` files, not hand-edited YAML.
- **Base-branch correctness:** a wrong-base (retargeted) merge is **rejected** by the gate;
  default-branch resolution is asserted (a `develop`-based repo does not default to `main`).
- **F8 finalizer:** command-test the **real** GitHub-contents adapter's request/response against
  actual `gh` JSON shapes; assert compare-and-swap on the recorded prior blob and idempotent re-run.
- **Crash/resume, local branch reuse, partial materialization, multi-repo partial-push** each have
  a case. The `gh` PR/merge transport stays an injected offline boundary, but its request/response
  contract is tested against real `gh` JSON shapes.

The structural neutrality guard (F11 T8) extends to `pen_materialize`, `apply_driver`,
`apply_advance_base`, and `make_apply_ops`: no imports from `profile_dispatch` / any claude-plugin
adapter, and no `profile:claude-plugin` predicate evaluated in the apply path.

## 8. Cross-repo & sequencing

Per the `docs/backlogs/README.md` dependency map:

- **pulse-gh** (`feat/*` → `develop`): components A–E + tests + the docstring fixes (§9) — the whole
  engine + trigger.
- **workspace** (`feat/*` → `main`, no `develop`): component F — the `ApplyAuthorization` policy +
  neutral proposal source + marker records, landed **after** the engine is installed in the
  workspace's plugin (not merely merged to `develop`).
- **nave fork:** **not touched** (the point of Fork B).

## 9. Doc debt to close while wiring (review Minor)

The orchestrator module docstring still says "propose-only, unconditionally"
(`pen_orchestrator.py:21`) and `PenPlan.request_push` says a push is always forbidden
(`pen_orchestrator.py:136`), though merged code already supports allow-listed landing. These are
corrected as part of B, preserving the actual propose control flow.

## 10. Phase gate

- A re-derived, workspace-authorized neutral `allow-listed` proposal on a real repo lands as a
  pushed `pulse/apply/{id}` branch + opened PR against the **intended** base; on a detected merge
  into that base the F8 plan-sync base advances off the merged document's blob; result validates as
  `apply-status`/`applied`.
- The transformation's output demonstrably reaches the committed/pushed clone (real materializer +
  real local exec, asserting pushed ≠ base and pushed = remote ref — the double-fake is gone for the
  neutral path).
- The **lease is acquired before any mutation**; a competing actor is blocked before it acts.
- Every F11 pre-exec gate fires and fails closed **against the local materialized clone**; no push
  on a failed gate; the push never targets a base branch; a wrong-base merge is rejected.
- `advance_base` is the typed F8 doc-blob finalizer — compare-and-swap on the recorded prior blob,
  idempotent, off the merged document's blob — and returns `{"state": "ok"}`. F5-marker advance is
  out of scope.
- The apply engine carries no plugin imports and evaluates no `profile:claude-plugin` predicate.
- The `propose` path through `execute()` is byte-for-byte unchanged.
