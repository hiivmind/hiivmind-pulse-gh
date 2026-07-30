# Apply-Mode Production Wiring — Design Spec

**Date:** 2026-07-30
**Status:** Approved (brainstorm) — pending implementation plan
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

- The **landing half** — `apply_ops.provision_branch/commit_repos/push_repos` — operates on local
  git clones at `PULSE_PEN_ROOT/{owner}/{name}` (the contract `pen_clone_reader` reads, and the
  three `nave_adapter.*_apply_clones` git ops mutate).
- The **transformation half** — `nave_adapter.pen_exec(pen_name, argv, …)` at
  `pen_orchestrator.py:611` — runs the registered transformation inside a **Nave pen**, whose
  on-disk clone path Nave does not expose (`pen_orchestrator.py:36-49`: `pen show`/`pen status`
  carry no clone path; `pen exec` stdout is opaque-by-contract; `nave materialize` fetches from
  the GitHub API, not the working tree).

For a change to actually land, the transformation's output must reach the same clones that get
committed and pushed. The acceptance suite wires a fake `RecordingApplyOps` **and** a fake
`QueuedRunner` for `pen_exec`, fully decoupled — so **nothing verifies that the transformation's
output ever reaches the committed/pushed clone.** That "same on-disk clone" integration is the
core production-wiring gap (§A.3), and it forces a substrate decision F11 left implicit.

The merged code already committed to landing via **git-ops on local clones** (not `pen_exec`'s own
`--push-changes`) — a deliberate choice to get per-proposal branch targeting (C1) and per-repo
failure signal (I4, which `exec_pen`'s opaque first-failure bail cannot give). The only thing left
unresolved is where the transformation's file changes come from on those local clones.

## 2. Decision — local materialized clones (Fork B)

**Apply materializes its own real git clones at `PULSE_PEN_ROOT/{owner}/{name}` at the guarded base
SHA, runs the registered transformation applier directly in each clone, then commits and pushes.**

- **Propose** stays Nave-scale discovery (`pen_exec` scans/dry-runs the fleet — Nave's value).
- **Apply** operates on a handful of materialized clones for the already-selected, already-proposed
  selection — cheap to clone, guaranteed real worktrees with an `origin` push remote, fully
  attributable, and **entirely in pulse-gh** (no forked-Nave surface, no dependency on Nave's
  internal pen-storage layout).

Rejected alternative — **Nave-storage bridge** (make `PULSE_PEN_ROOT` resolve to Nave's real pen
clones): reuses the clone Nave already has, but is blocked on the `discreteds/nave` fork's
pen-storage internals, risks Nave clones not being pushable git worktrees, and makes this a 3-repo
effort. The pen-exec-native push variant was already rejected in F11 for C1/I4.

This makes the propose/apply substrate split explicit: **Nave pen for discovery, local clone for
landing.** Justified because apply acts on a narrow selection, and all apply gates
(expected-SHA, `paths_changed`, `json_schema` validation) already read the clone through
`pen_clone_reader`, which works identically on a locally materialized clone.

## 3. Components

All in `hiivmind-pulse-gh` unless noted. Each has one clear purpose and a well-defined interface.

### A. `pen_materialize.py` (new) — the clone bridge (§A.3)

`materialize(selection, base_shas, clone_root=None) -> dict[repo, {"state": "ok"|"failed", "reason"?}]`

For each repo in `selection`, ensure `{clone_root}/{owner}/{name}` (resolving `clone_root` /
`PULSE_PEN_ROOT` with the same precedence as `make_pen_clone_reader`) is a git clone of the repo,
fetched, and checked out **clean at the guarded base SHA** (`base_shas[repo]`). Idempotent: an
existing clone is fetched and hard-reset to the base; a missing clone is cloned. Fail-closed and
loud (never silently produces an empty/dirty/wrong-base clone). Pure I/O — no decision logic.

This replaces the F11 plan's "documented out-of-band materialize step" (`pen_clone_reader.py:13-17`
contract) with a real pulse implementation. It is the sole writer that establishes the contract the
reader and the `*_apply_clones` ops already assume.

### B. `run_transformation` seam + `make_apply_ops(clone_paths)` (new) + one `execute()` branch

- **Extend the `ApplyOps` protocol** with `run_transformation(argv) -> dict[repo, {"state": …}]`.
- **`execute()` change (contained):** in `allow-listed` mode, call `apply_ops.run_transformation(argv)`
  in place of the `pen_exec` call at `pen_orchestrator.py:611`, between provision-branch and
  validate. **The `propose` path is byte-for-byte unchanged** (still `pen_exec`, still terminates at
  `proposed`). `execute()` stays subprocess-pure — it only calls the injected `apply_ops`.
- **Production `make_apply_ops(clone_paths)`** returns an `ApplyOps` binding:
  - `provision_branch` → `nave_adapter.provision_apply_branch(clone_paths, …)`
  - `commit_repos` → `nave_adapter.commit_apply_clones(clone_paths, …)`
  - `push_repos` → `nave_adapter.push_apply_clones(clone_paths, …)`
  - `run_transformation` → run the transformation's `command_argv` with `cwd=clone_paths[repo]`
    per selected repo. Per-ecosystem tool absence (formatter, `npm`, docs generator) → fail-closed
    `blocked` naming the missing tool (the T1 contract), never a silent success or a traceback.

### C. `apply_driver.py` (new) — Path A production driver (§A.1)

`uv run` CLI. Input: a recorded `allow-listed` proposal (proposal id + the proposal/result file it
was persisted in). Flow:

1. Resolve the proposal (built from the same `Proposal` that F6–F9 recorded — never reconstructed).
2. `pen_materialize.materialize(selection, expected_shas)` → clone paths.
3. `make_pen_clone_reader(clone_root, selection)` → the three readers; `make_apply_ops(clone_paths)`.
4. `pen_orchestrator.execute(plan, runner, read_repo_*, apply_ops=…)`.
5. On terminal `pushed`: create/resume the run-ledger step, then `apply_reconcile.open_apply_pr`.
6. Writes a validated `apply-status` result on **every** exit (including early `blocked`/ABORT).

The reconcile half (`open-pr` / `reconcile` CLI) already exists; the driver drives the *push* half
that had no production caller.

### D. `apply_advance_base.py` (new) + wire into the `reconcile` CLI (§A.2, folds in A.4-F5)

Concrete `advance_base(repo, merged_sha) -> {"state": "ok"|"blocked"|"failed", "reason"?}`,
**implemented by reusing `object_apply`'s `marker-advance` verb**: build the `ObjectWrite` +
`Precondition` (expected = current marker SHA) for the F5 `integration_tested_sha` marker / F8 base
off the **merged** SHA and call `apply_object_write`. Idempotent (re-advancing an already-advanced
marker is a no-op) and precondition-guarded (a drifted marker `blocks`, never blind-overwrites).

Wire it into `apply_reconcile.main()`'s `reconcile` subcommand, which currently passes
`advance_base=None` (base advancement deferred). With it wired, `reconcile_apply` advances the base
only after a **detected merge**, off the merged SHA (never the pushed SHA), gated by the existing
`merge_detected` evaluator reading the validated `apply-status` file.

This unifies §A.2 (real advance_base) with §A.4's F5-marker path — they are the same Path B write.

### E. `gh-apply` skill (new) — the interactive trigger (§A.1 trigger, v1)

Wraps the driver + reconcile loop behind `/gh apply <proposal>`. v1 is **interactive / PR-gated**:
the operator invokes apply on a specific recorded proposal; Pulse pushes the branch, opens the PR,
and (on a later invocation) reconciles the detected merge and advances the base. Scheduled
auto-apply stays v2 (needs the workspace apply-policy design).

### F. Workspace opt-in markers (`hiivmind/hiivmind-workspace` repo)

The per-transformation `allow-listed` opt-in and the F5 marker files live in the workspace repo. A
small enrollment PR (mirroring F10's `automation.scheduled_workflows` PR) turns on `allow-listed`
for the neutral transformation(s) apply is proven against, and seeds the marker(s) `advance_base`
maintains.

## 4. Scope boundary

**IN — the "apply runnable spine":** a validated `allow-listed` proposal for a **neutral**
transformation (`refresh-node-lockfile` / `regenerate-docs-index`) on a real fixture repo lands as a
pushed `pulse/apply/{proposal_id}` branch (never a base branch) + an opened PR; on a **detected
merge** (never a push), the F5/F8 base advances off the merged SHA; the result validates as
`apply-status`/`applied` with PR URL + merged SHA. Interactive trigger. All F11 pre-exec gates
still fire and fail closed.

**DEFERRED (captured, not built):**
- F9-marketplace + F2-profile Path B emitter wiring (the remainder of §A.4) — until those apply
  consumers are actually wanted. F5-marker Path B is in (it *is* advance_base).
- Scheduled auto-apply + `allow` (unattended direct push) — v2, behind an explicit workspace
  apply-policy + `allow_scheduled: true` (§B).
- F4 dependency-coherence apply — blocked on the unbuilt F4 adapters (§D.1).
- Auto-merge — permanent non-goal (§C); landing is always a reviewed merge.

## 5. Testing

Upgrade the neutral acceptance from the double-fake (`RecordingApplyOps` + `QueuedRunner`) to run
the **real materializer + real local transformation** against a temp-git fixture whose `origin` is a
local **bare** repo (no network):

- `pen_materialize` clones the fixture into `PULSE_PEN_ROOT/{owner}/{name}` at a base SHA.
- The real transformation runs locally in the clone and its output **actually reaches** the clone
  that `commit_apply_clones` / `push_apply_clones` land (the exact integration the fakes never
  checked); the push targets `pulse/apply/{id}` on the local bare `origin`.
- `object_apply` (advance_base) and the `gh` PR/merge seam stay **injected** — `apply_reconcile`
  already isolates `gh` behind `GhOps`, and `advance_base` behind `object_apply`'s `ObjectGhOps`.
- The bound-path guard (T2) and neutral bound-path assertion still fire on the neutral
  transformation. Anything still mocked (a real remote merge) is logged as a known coverage
  boundary, not silently skipped.

The structural neutrality guard (F11 T8) extends to the new modules: `pen_materialize`,
`apply_driver`, `apply_advance_base`, and `make_apply_ops` import nothing from `profile_dispatch` /
any claude-plugin adapter, and evaluate no `profile:claude-plugin` predicate.

## 6. Cross-repo & sequencing

Per the `docs/backlogs/README.md` dependency map, this decomposes as:

- **pulse-gh** (`feat/*` → `develop`): A, B, C, D, E, tests — the whole engine + trigger.
- **workspace** (`feat/*` → `main`, no `develop`): F — the enrollment/marker PR, landed **after**
  the pulse-gh engine merges so the opt-in points at a runnable applier.
- **nave fork:** **not touched** (the whole point of Fork B).

## 7. Phase gate

- A neutral `allow-listed` proposal on a real repo lands as a pushed `pulse/apply/{id}` branch +
  opened PR; on a detected merge the base advances off the merged SHA; result validates as
  `apply-status`/`applied`.
- The transformation's output demonstrably reaches the committed/pushed clone (real materializer +
  real local exec in the acceptance suite — the double-fake is gone for the neutral path).
- Every F11 pre-exec gate still fires and fails closed; no push on a failed gate; the push never
  targets a base branch.
- `advance_base` advances only on a detected merge, off the merged SHA, precondition-guarded and
  idempotent, via the reused Path B `marker-advance`.
- The apply engine carries no plugin imports and evaluates no `profile:claude-plugin` predicate.
- The `propose` path through `execute()` is byte-for-byte unchanged.
