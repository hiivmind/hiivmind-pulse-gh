# Apply-Mode Production Wiring — Design Spec

**Date:** 2026-07-30
**Status:** Approved (brainstorm) — revised after two adversarial design reviews (Codex `gpt-5.6-sol`,
rounds 1 & 2 fully incorporated) and **PR #141's single-mutator design note**
(`docs/superpowers/specs/2026-07-30-f11-apply-git-consolidation-note.md`). Pending implementation plan.
**Origin:** `docs/backlogs/2026-07-29-apply-mode-v2-deferrals.md` § A. F11 (PR #138, merged) shipped the
apply **library + tests + docs**; every seam exists and is fake-tested, but nothing assembles them
against a real repo. This is the apply analogue of F10's "runnable spine" — its own phase, spanning
the `discreteds/nave` fork and `hiivmind-pulse-gh`.

**Read alongside:** PR #141 note (substrate decision-of-record), F11 plan
(`docs/superpowers/plans/2026-07-22-f11-apply-mode.md`), `docs/backlogs/README.md` (cross-repo map).

---

## 1. Problem — the substrate split and the two-writers hazard

F11's `execute()` (`lib/pulse/scripts/pen_orchestrator.py`) owns the apply state machine
(`provision → exec → validate → commit → push → pushed`), but its two halves address **different
clone sets**: the transformation via `nave_adapter.pen_exec(pen_name, …)` (`pen_orchestrator.py:609`)
inside a **Nave pen**, and the landing via the raw-git apply trio (`nave_adapter.py:500–616`) against
separate `PULSE_PEN_ROOT/{owner}/{name}` clones. The acceptance fakes both halves independently
(`RecordingApplyOps` + `QueuedRunner`), so nothing verifies the transformation's output reaches the
committed/pushed clone.

**PR #141's deeper diagnosis:** the trio is a **second independent writer** over clones Nave already
owns — a structural hazard (state divergence from `pen status`, propose-only enforced twice, blunt
`add -A` staging). The trio has **no production callers yet**; the apply driver would be its first.
Cheapest moment to change course.

## 2. Decision — Nave is the single mutator (PR #141)

**Exactly one system performs clone-write git: Nave.** Extend Nave's pen surface with the apply
verbs, then **delete the raw-git trio**. Pulse keeps orchestration, policy, and **read-only**
verification (`pen_clone_reader` still runs read-only `git rev-parse`/`status` — so the precise rule
is "no *clone-write* git in Pulse", not "no git in Pulse" — review M2). This **resolves the substrate
split by construction**: transformation (`pen exec`) and landing (Nave verbs) operate on the one Nave
pen; `pen status` is once again the authoritative preflight substrate.

**Rejected — Fork B** (Pulse materializes/mutates its own clones): two clone-management systems;
violates the single-mutator rule. The first draft chose Fork B and is superseded.

**Non-goals (PR #141):** apply git never moves into the interactive LLM session (headless apply stays
deterministic, model-free, fixture-testable, fail-closed); Nave pens are not replaced by `git
worktree` / the worktrees plugin.

## 3. Nave pen-surface extensions (the `discreteds/nave` deliverable)

Pen-domain capabilities in their own right. **Every request and result is a versioned, schema'd
contract** (review I6): a `protocol_version`, strict per-repo result enums with required fields per
state, an **exact-selection coverage** rule, and a defined relationship between process exit status
and valid JSON (partial failure returns valid JSON + nonzero exit, never opaque). Non-`--json` stdout
is never parsed as data.

1. **Branch provisioning as a *remote-base* guard (review C1).** The provisioning request carries
   per repo `{repo, base_ref, expected_base_sha, apply_ref}`. Nave **fetches the named remote base
   ref immediately before provisioning, requires its observed SHA to equal `expected_base_sha`**,
   verifies the object is a commit, then creates `apply_ref` (= `pulse/apply/{proposal_id}`) off it;
   fail closed per repo if the branch exists (see reuse rule in § 5C), the ref is missing, or
   observed ≠ expected. The JSON reports `{base_ref, expected_base_sha, observed_base_sha, apply_ref}`,
   which Pulse checks exactly. *"The SHA exists locally" is not a stale-base guard* — only a
   remote-ref comparison is (`mutation_plan.py:283`, `repository-mutations.md:117`). Per-repo base
   SHAs travel in a request file (JSON/YAML, mirroring `materialize --request` — PR #141 Q2).
2. **Bounded staging on commit.** Stage **only** the proposal's `bound_paths`; **any** tracked or
   untracked path dirty outside them fails the commit closed. A post-validation step distinct from
   the transformation `pen exec` (PR #141 Q1).
3. **Structured commit/push results.** Per-repo `--json` carrying `{local_commit_sha, remote,
   remote_ref, remote_sha, upstream}` — the PR-first step needs the remote ref/SHA, which
   `pen exec --push-changes` does not report today (PR #141 Q3).
4. **Deterministic, CAS-guarded cleanup.** `nave pen reset <pen> --branch <name>` unwinds a partial
   provision/push; **a remote ref is deleted only if it still points at the recorded pushed SHA**
   (compare-and-swap — otherwise cleanup can delete someone else's replacement branch, review
   C3/I5). Local reset and remote deletion are separately specified; `--keep-going`/fail-fast default
   is documented.
5. **Post-exec repository-control invariants (review I7).** Because `pen exec` runs the registry argv
   directly in the repo (`nave_adapter.py:455`) and a command or ecosystem lifecycle hook could
   switch branches, commit, edit remotes, or push, Nave **enforces before commit**: the apply branch
   is still checked out, HEAD still equals the provisioned base, configured remotes are unchanged,
   and there are no unexpected commits — else fail closed. Neutral ecosystem commands (e.g. `npm`)
   run with repository lifecycle scripts disabled where applicable. Bounded staging alone is *not*
   the full blast-radius guard; a command that self-commits leaves a clean tree, and one that pushes
   has already escaped — these invariants are the guard.
6. **Expose the pen clone root (the read-path capability).** `pen status --json` reports each repo's
   canonical clone path so `pen_clone_reader` can locate clones for **independent** read-only
   verification (checker ≠ writer). Identity is hardened Pulse-side (§ 5B / review I4), so a
   path-reporting bug cannot silently point the checker at a decoy.

Guard migration: the expected-SHA stale-base guard moves into verb 1 (remote-ref CAS); the
blast-radius guard is verbs 2 + 5. Pulse's read-side `paths_changed` (no-op / wrong-target detection)
and `json_schema` (content) validations stay, verified via verb 6.

## 4. Proposal & authorization model (review C1, M1 — substrate-independent)

F6–F9 persist only `{binding, transformation, proposal_id}` summaries (`plan_sync.py:472`,
`validate_result.py:624`) — the settled "summaries only; apply re-derives" handoff. Apply obtains an
authorized Proposal in two pieces:

1. **Re-derivation.** The driver re-runs the *propose* `build_proposal` path for the target binding
   to mint a **fresh** `Proposal` off **current** state (`expected_shas`, `selection`, `bound_paths`),
   minted directly with `mutation_policy="allow-listed"`. The re-derived summary identity — binding,
   transformation, proposal_id — **must match the selected recorded summary** before authorization
   (review M1).
2. **`ApplyAuthorization` (new, workspace-repo policy):** `{transformation, permitted_repos, policy:
   allow-listed}`. The driver requires the re-derived proposal to match (transformation authorized
   **and** `selection ⊆ permitted_repos`). The registry gains no allow-listed flag.

**Audit fields are contractually required (review M1):** the `repo-mutation` / `apply-status` result
and the ledger snapshot carry **required** `recorded_proposal_id`, `proposal_digest`, and
`authorization_digest`/policy version — not merely permitted extras.

## 5. Pulse components (`hiivmind-pulse-gh`)

### A. Thin Nave-verb adapters + delete the trio + capability handshake

Add adapters for the § 3 verbs (argv + strict `--json` decode with **field/version validation**, not
just root-type — `nave_adapter.py:305` today checks only root type; fixture-testable via
`PULSE_NAVE_FIXTURES`). **Delete** the trio (`nave_adapter.py:500–616`) + its tests. Before any
mutation, a **capabilities/protocol-version handshake** (before `pen_create`) confirms the installed
Nave exposes the required verbs at a compatible version; a stale Nave on `PATH` makes the run **fail
closed before mutating** (review I6 — "install Nave first" is operational, not a runtime guard).

### B. Evolved `ApplyOps`/`PenRunResult` contract + mandatory bounds + identity-hardened reader

The `ApplyOps` protocol **evolves** (review C2 — the current three methods cannot carry the data
flow):
- `commit_repos(message, bound_paths)` (bounded staging);
- `push_repos(branch) -> {repo: {local_commit_sha, remote, remote_ref, remote_sha, upstream}}`;
- **`reset_repos(branch, expected_pushed_shas)`** (CAS cleanup — new method);
- `PenRunResult.repo_landings`: **per-repo phase + SHA/ref evidence, including partial successes**
  (today `execute()` checks only push `state` and discards the result — `pen_orchestrator.py:670`;
  `PenRunResult` carries no SHA/ref — `:160`).
Pulse verifies `remote_sha == local_commit_sha` and `remote_ref == pulse/apply/{id}` before opening a
PR. `make_apply_ops(...)` binds these to the § 5A adapters. `execute()` allow-listed flow: validate
proposal+authorization → provision (verb 1) → `pen_exec` transformation → validate via the reader
(verb 6) → bounded commit (verb 2) → push (verb 3), with `reset_repos` (verb 4) on partial failure.
The `propose` path is byte-for-byte unchanged; `execute()` stays subprocess-free.

**Mandatory bound_paths for every allow-listed proposal (review I1).** `bound_paths` is currently
required only for `paths_changed` validation (`mutation_plan.py:396`); the neutral
`refresh-node-lockfile` uses `json_schema` with **no** bounds (`test_apply_acceptance.py:476`) — under
bounded staging it would stage nothing or fall back to `add -A`. So: **allow-listed re-derivation
requires exact, non-empty `bound_paths` regardless of validation kind** (e.g. `package-lock.json` for
`refresh-node-lockfile`); Nave rejects empty bounds and any dirty path outside them.

**Identity-hardened clone reader (review I4).** `make_pen_clone_reader` changes from *(one root,
derive owner/name)* (`pen_clone_reader.py:42`) to accept an **exact `repo -> canonical_clone_path`
map** from verb 6, and validates: exact selection coverage, unique canonical paths, expected remote
identity, expected apply branch checked out, expected HEAD. After commit, the reader-observed HEAD is
compared to Nave's reported `local_commit_sha`. The check stays independent (Pulse does its own git
reads) but no longer trusts a bare `.git` existence check (`pen_clone_reader.py:67`).

### C. `apply_driver.py` (new) — driver with a persisted phase journal + lease fencing (review C3)

`uv run` CLI. Because `execute()` is one-shot and the branch verb fails on an existing branch, a
crash mid-flight otherwise strands unrecoverable state. The driver therefore **persists a per-repo
phase journal before/after every irreversible boundary**:

```
leased → pen_ready → branch_provisioned → transformed → validated → committed(local_sha)
       → pushed(remote_ref, remote_sha) → pr_opened
```

- **Lease first + fencing:** acquire the ledger lease (`resolve_run.py:337`) before any mutation;
  **renew it and check ownership** on a real protocol — the 120-min TTL permits takeover after
  expiry, so a long-running original process **must stop mutating once fenced out** (review C3).
- **Resume reconciles the journal with live Nave + GitHub state.** An existing `pulse/apply/{id}`
  branch is reused **only** when owner/proposal metadata, base, ref, and SHA match exactly (else fail
  closed — never blind reuse or force-push). Remote cleanup deletes a ref only if it still points at
  the recorded pushed SHA (verb 4 CAS). **Durable `pushed` evidence is written before PR creation**,
  so a crash between push and PR does not lose the only input `open_apply_pr` needs.
- **Re-derive** the authorized proposal (§ 4); resolve the **intended base branch per repo** from
  binding/repo metadata (never a `main` default — `apply_reconcile.py:432`); pass it into verb 1.
- On terminal `pushed`: `open_apply_pr` with the verb-reported pushed SHA + intended base
  (`apply_reconcile.py:205`).
- **Result on every exit:** pre-push exits write a validated `repo-mutation`; `apply-status`
  (`validate_result.py:41`) is remote-lifecycle only.

### D. `apply_advance_base.py` (new) — F8 doc-blob finalizer, PR-gated, dual-CAS (review C2/I3)

v1 base advancement is the typed **F8 plan-sync doc-blob finalizer** — the `sync:` binding
(incl. `base.blob`) lives in the **bound document's own frontmatter** (`plan_sync.py:519`), and
`finalize` sets `base_patch["blob"] = confirmed_document_blob` post-merge (`:348-349`), so advancing
the base is itself a **doc edit → PR-gated**, never a direct push to a base branch (which would
violate "landing is always PR-gated" — `plan-sync-binding.md:46` — and hit protected branches).

- **Persist a typed finalizer record before mutation** carrying the document repo, intended base
  branch, document path, expected prior `sync.base.blob`, and apply/proposal identity — the current
  `(repo, merged_sha)` callback (`apply_reconcile.py:268`) has none of this.
- At reconcile: read the desired document blob at `merged_sha`, read the current document on the
  intended base, require **semantic CAS** (parsed `sync.base.blob == expected_prior_blob`) **and**
  **Contents-API file-SHA CAS** (the two are distinct; both required), then land the frontmatter
  advance via a **dedicated bookkeeping branch/PR**. Idempotent; returns `{"state": "ok"}` as
  `reconcile_apply` requires (`apply_reconcile.py:349`). **Not** via `object_apply.marker-advance`
  (wrong target/return — `object_apply.py:120,250`). *The plan pins whether the frontmatter advance
  folds into the apply patch or is a separate bookkeeping PR, by reading `plan_sync.finalize`.*

**Not in this phase:** F5-marker advancement (an F5 concern keyed off upstream integration-validated
`head_sha` — `impact.py:456`, not an apply merge). Pure-neutral transformations have no base to
advance — the merge is terminal.

### E. `gh-apply` skill (new) — interactive trigger, v1 (PR-gated). Scheduled auto-apply is v2.

### F. Workspace enrollment (`hiivmind/hiivmind-workspace`) — gated on an installed engine (review I6)

A PR landing the `ApplyAuthorization` policy (§ 4) + a **real neutral proposal source** (a neutral
binding producing a `refresh-node-lockfile` / `regenerate-docs-index` proposal — none exists in the
template today). Gated on the § 3 Nave verbs **and** the pulse-gh engine being **installed** in the
workspace's plugin (local install suffices per the single-developer context), not merely a `develop`
merge (`docs/backlogs/README.md:120`).

## 6. Lifecycle, concurrency & result contracts (review I2/I5/C3)

- **Merge gate — base *and* head verified (review I2).** `GhCliOps.view_pr` and `apply-status` gain
  `intended_base`, `observed_base` (`baseRefName`), `expected_head_sha`, `observed_head_sha`
  (`headRefOid`). `evaluate_merge_detected_gate` (`resolve_run.py:300`) accepts a merge **only** when
  observed base == intended base **and** the merged PR head == the expected pushed SHA — a retargeted
  PR or a force-push/late commit to the apply branch cannot land unvalidated content. Both
  observations are persisted so retry stays fail-closed; the resume path re-reads GitHub rather than
  fabricating evidence from a prior `applied` result (`apply_reconcile.py:300`).
- **Single repo per apply run (v1 scope — amended 2026-08-03 after the plan review).** v1 lands
  **one repo per proposal**: a proposal whose `selection` has more than one repo is `blocked`
  (reason `"multi-repo apply is v2"`) **before any mutation** (before `pen_create`). This avoids a
  premature-completion defect (`reconcile_apply` marks the step done on the *first* repo's success —
  `apply_reconcile.py:349`) without building the full multi-repo ledger now. **Deferred to v2
  (captured):** per-repo child ledger steps + aggregate-parent folding, one `apply-status` per repo,
  and partial-push independence/cleanup across a multi-repo selection. The neutral proof is
  single-repo, so v1 is complete without them.
- **Transformations must be deterministic (apply contract).** A crash between `pen_exec` and the
  journal's completion receipt cannot be distinguished from live status alone. v1 therefore requires
  apply transformations to be **deterministic** (same base + argv → same output): on resume from an
  in-progress `transformed` phase, the driver resets the clone to the provisioned base (Nave `pen
  reset` local) and **re-runs** the transformation from clean — safe by determinism. Non-deterministic
  appliers are out of scope for v1.
- **Fencing — same-machine advisory lock (v1).** Concurrency is fenced by an **OS advisory lock
  (flock)** held across the whole mutation sequence and passed through to `open_apply_pr` and the F8
  finalizer (never independently reacquired). The run-ledger `token` is **ownership *detection***, not
  a cross-process fence. **Cross-machine git-CAS lease acquisition is a documented v2 extension.**

## 7. Testing (review I5)

- **Pulse layer** drives acceptance through the **real `apply_driver` + production factories** against
  **Nave-verb `--json` fixtures** (`PULSE_NAVE_FIXTURES`): re-derivation + authorization (unauthorized
  refused; summary-identity mismatch refused), the capability handshake (stale/absent Nave fails
  before mutation), lease ordering **and fencing** (a competing actor blocks the original *before* it
  mutates; a fenced-out original stops), **phase-journal crash/resume** (a crash at each boundary
  resumes correctly; existing-branch reuse only on exact match), pushed-SHA correctness (result carries
  the verb-reported remote-ref SHA, not the base — the current acceptance wrongly passes base as
  `pushed_sha`, `test_apply_acceptance.py:338`), base **and head** merge-gate correctness (wrong-base
  and force-pushed-head merges rejected; a `develop` repo does not default to `main`), the F8 finalizer
  (real GitHub-contents adapter command-tested against actual `gh` JSON; dual-CAS; idempotent), and the
  cross-repo contract (malformed / missing-field / duplicate-path / extra-repo / nonzero-exit-with-valid-JSON
  fixtures).
- **The "output actually lands on real clones" proof lives in the Nave fork's suite** — the verbs are
  where branch/commit/push + the post-exec invariants against real clones are exercised. Pulse asserts
  the adapter contract; the fork asserts git reality.
- **Import-boundary/neutrality guard (PR #141):** the F10 import-boundary test moves from guarding the
  four raw-git names to guarding that the **single apply driver** is the sole flag-bearing caller; the
  structural neutrality guard extends to `apply_driver` / `apply_advance_base` (no `profile_dispatch` /
  claude-plugin imports; no `profile:claude-plugin` predicate).

## 8. Cross-repo & sequencing

Ordered by dependency; every cross-repo edge is a **versioned contract** with a runtime handshake, not
just an install order (review I6):

1. **`discreteds/nave` fork** (feature → main): § 3 verbs + versioned `--json` request/result schemas +
   post-exec invariants + Rust tests; install locally. **First.**
2. **`hiivmind-pulse-gh`** (`feat/*` → `develop`): § 5 A–E + § 4/§ 6 + delete the trio + § 9 doc debt +
   tests + the capability handshake that fails closed against an old Nave. Depends on 1.
3. **`hiivmind/hiivmind-workspace`** (`feat/*` → `main`): § 5F enrollment. **Last**, after the engine is
   installed.

## 9. Doc debt (review Minor)

Update the orchestrator docstring's "propose-only, unconditionally" (`pen_orchestrator.py:21`) and
`PenPlan.request_push` "always forbidden" (`pen_orchestrator.py:136`) to reflect allow-listed landing
(propose control flow unchanged), and `repository-mutations.md` C1's *Implementation* line to the Nave
verb. Phase-gate wording is "no clone-write git in Pulse" (read-only verification remains — review M2).

## 10. Phase gate

- A re-derived, workspace-authorized neutral `allow-listed` proposal (with mandatory `bound_paths`) on
  a real repo lands — **through Nave verbs, with no clone-write git in Pulse** — as a pushed
  `pulse/apply/{id}` branch (provisioned only after a **remote-base CAS**) + an opened PR against the
  **intended** base; on a detected merge whose **base and head both match**, the F8 plan-sync base
  advances off the merged document's blob via a PR-gated dual-CAS bookkeeping change; result validates
  as `apply-status`/`applied` with required audit fields.
- The raw-git trio is **deleted**; Nave is the sole clone mutator; a capability handshake fails closed
  against an incompatible Nave; the import-boundary guard enforces the single apply driver as the only
  flag-bearing caller.
- The **lease is acquired before any mutation and fenced on takeover**; a **phase journal** makes every
  boundary crash-resumable; a competing actor is blocked before it acts; cleanup is CAS-guarded.
- Every F11 pre-exec gate fires and fails closed against the **Nave pen**; post-exec repo-control
  invariants hold; bounded staging commits only `bound_paths`; no push on a failed gate; the push never
  targets a base branch.
- v1 lands **one repo per proposal**; a multi-repo proposal is `blocked` before any mutation
  (per-repo children + aggregate deferred to v2). Fencing is a same-machine advisory lock; transforms
  are deterministic (reset+re-exec on resume). F5-marker advance is out of scope.
- The apply engine carries no plugin imports and evaluates no `profile:claude-plugin` predicate; the
  `propose` path through `execute()` is byte-for-byte unchanged.
