# Apply-Mode Pulse-Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a re-derived, workspace-authorized `allow-listed` proposal for a **single repo** end-to-end — **through Nave verbs only** (no clone-write git in Pulse) — with a driver-owned, crash-resumable phase sequence, a base-and-head-verified merge gate, and a PR-gated F8 base advance.

**Architecture:** Single-mutator (PR #141): Nave owns all clone writes; Pulse keeps orchestration, policy, and read-only verification. This is the **`hiivmind-pulse-gh` half**. Two decisions from the plan review (Codex `gpt-5.6-sol`, 2026-07-30) shape it: **(1) driver-owned phase functions** — the allow-listed landing is extracted out of `execute()` into resumable phase callables the driver sequences and journals; `execute()`'s propose path is untouched. **(2) single-repo v1** — one repo per proposal; a multi-repo proposal is blocked with a reason; per-repo children + aggregate are deferred to v2. The Nave verbs land in a **separate `discreteds/nave` fork plan** that conforms to Task 1's contract; workspace enrollment is a follow-up.

**Tech Stack:** Python 3.10+ PEP 723 scripts, PyYAML, pytest, `gh` CLI, `nave` CLI (new verbs), git (read-only in Pulse). No new library dependencies.

**Source spec:** `docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md`. Read it and this plan's **Authoritative Interfaces** table before starting.

## Global Constraints

- **No clone-write git in Pulse.** Every branch/commit/push/reset is a Nave verb via `nave_adapter`. Read-only `git rev-parse`/`status` in `pen_clone_reader` stays. The F8 bookkeeping PR uses the GitHub Contents API (not a clone write).
- **`execute()`'s propose path is byte-for-byte unchanged.** The allow-listed landing is **removed** from `execute()` and relocated to driver-owned phase functions (Task 3). `execute()` remains propose-only.
- **Single repo per apply run (v1).** A proposal whose `selection` has >1 repo is `blocked` with reason `"multi-repo apply is v2"` **before any mutation (before `pen_create`)**. (Spec §6/§10 amended 2026-08-03 to define single-repo v1; per-repo children/aggregate are v2.)
- **Authorize before any mutation.** Re-derivation (from fresh source state), the recorded-summary-identity check, authorization, and the single-repo check ALL run **before `pen_create`** — `pen_create` mutates Nave-managed state, so nothing may create a pen for an unauthorized/multi-repo/mismatched proposal.
- **Transformations must be deterministic (v1).** On resume from an in-progress `transformed` phase the driver resets the clone to the provisioned base and re-runs the transform; non-deterministic appliers are out of scope. This is the only way begin/complete journaling can recover a crashed `pen_exec` safely.
- **Fencing is a same-machine OS advisory lock (flock)** held across the whole mutation sequence and threaded through `open_apply_pr` + the F8 finalizer (never independently reacquired). The ledger `token` is ownership *detection*, not a cross-process fence; cross-machine git-CAS is v2.
- **Fail closed** on any missing verb/reader/tool, stale base, out-of-allowlist change, unauthorized proposal, or evidence mismatch.
- **Every apply run writes a validated result on every exit.** Pre-push exits write `repo-mutation`; `apply-status` is remote-lifecycle only. A non-zero `validate_result.py` exit is a bug.
- **Values are built from the re-derived `Proposal` + observed facts — never reconstructed.**
- **Nave contract is versioned** (`protocol_version: 1` on every request and result); a capability handshake fails closed before any mutation against an incompatible Nave.
- **Real exception type:** `mutation_plan` raises `MutationPlanError` (not bare `ValueError`) — tests assert that.
- `uv run pytest -q` and `git diff --check` pass before each task closes; **each task's commit leaves the whole suite green** (fixture migrations land in the same task that breaks them).

## Authoritative Interfaces (single source of truth — every task and test uses these verbatim)

```
# nave_adapter.py (Task 1) — as shipped; see
# docs/superpowers/specs/2026-08-13-apply-verb-contract-handoff.md for the
# full wire contract (states, echo checks, CLI shapes) this table only summarizes.
NAVE_APPLY_PROTOCOL = 1
APPLY_VERBS = ("branch", "commit", "push", "reset")
pen_capabilities(runner) -> {"protocol_version": int|None, "verbs": list[str], "adapter_state": str, "reason": str|None}
pen_branch(runner, name, apply_ref, request: list[dict]) -> {"adapter_state","repos":[{repo,base_ref,expected_base_sha,observed_base_sha,apply_ref,state,reason?}]}
  # apply_ref is a single envelope-level field naming one branch across every repo, NOT per-repo
pen_commit(runner, name, branch, request: list[dict], message) -> {"adapter_state","repos":[{repo,local_commit_sha?,state,reason?}]}
  # branch is a positional (this table's original signature omitted it); request carries only {repo,paths}
pen_push(runner, name, branch, request: list[dict]) -> {"adapter_state","repos":[{repo,remote?,remote_ref?,remote_sha?,upstream?,local_commit_sha?,state,reason?}]}  # request=[{repo}] carries expected_repos so coverage can be enforced
pen_reset(runner, name, branch, request: list[dict]) -> {"adapter_state","repos":[{repo,local_reset,remote_deleted,state,reason?}]}
pen_status(runner, name)  # existing owner/name shape UNCHANGED; each repo entry GAINS clone_path
# request envelopes are versioned: {"protocol_version":1,"repos":[...]}; per-repo `state` values are
# closed, kebab-case sets that differ per verb (e.g. branch: stale-base/exists/evidence-unavailable/...)
# — NOT a generic "failed"; see the handoff doc's enumerated sets.

# apply_rederive.py (Task 2) — re-derives from FRESH SOURCE STATE (no pen), via typed provider inputs
RederivedProposal(binding_id: str, proposal: Proposal, source_kind: str, finalizer_record: dict|None)
# Per-source typed input contexts carry the real evidence + injected I/O seams (NOT read_repo_head):
#   PlanSyncProviderInputs(binding, document_snapshot, github_snapshot, actor, registry)
#   GeneratedProviderInputs(generator, binding, snapshot, actor, registry)
#   MarketplaceProviderInputs(binding, drift, head_sha, actor, registry)
collect_inputs(source_kind, binding_ref, recorded_summary, *, io_seams) -> ProviderInputs   # fresh source collection, no pen
rederive(inputs: ProviderInputs) -> RederivedProposal   # calls the REAL builder (amended to take mutation_policy + bound_paths)
mutation_plan.proposal_digest(proposal) -> str          # versioned, domain-separated
apply_authorization.authorization_digest(auth) -> str    # versioned
apply_authorization.load_authorization(path, transformation) -> ApplyAuthorization
apply_authorization.authorize(rederived: RederivedProposal, auth, recorded_summary) -> None  # raises AuthorizationError

# apply_phases.py (Task 3) — driver-owned, each returns typed per-repo evidence
preflight_phase(runner, pen, proposal, clone_paths) -> {repo: {state, reason?}}  # pen-selection match + status coverage + working_tree==clean + freshness==fresh + divergence==up-to-date + clone_path present
provision_phase(runner, pen, apply_ops, proposal, apply_branch, base_refs) -> {repo: {state, observed_base_sha, reason?}}
exec_phase(runner, pen, entry) -> {repo: {state, reason?}}
validate_phase(entry, reader, proposal) -> {repo: {state, reason?}}
commit_phase(apply_ops, proposal, message) -> {repo: {state, local_commit_sha, reason?}}
push_phase(apply_ops, reader, apply_branch, expected_local_shas) -> {repo: {state, remote_ref, remote_sha, upstream, reason?}}
cleanup(apply_ops, apply_branch, pushed_shas) -> None
# ApplyOps protocol (pen_orchestrator.py): provision_branch(branch,base_shas); commit_repos(message,bound_paths);
#   push_repos(branch); reset_repos(branch, expected_pushed_shas)
apply_ops.make_apply_ops(runner, pen_name, bound_paths_by_repo, base_refs) -> ApplyOps

# apply_journal.py (Task 7) — write-ahead
Journal(path); PHASES=("leased","pen_ready","branch_provisioned","transformed","validated","committed","pushed","pr_opened")
Journal.begin(repo, phase, token, **evidence); Journal.complete(repo, phase, **evidence)
Journal.state(repo) -> {"phase": str|None, "in_progress": str|None, "evidence": dict, "token": str|None}

# apply_lock.py (Task 6) — the real same-machine fence
apply_lock(lock_path) -> context manager holding an OS advisory lock (flock) for the whole mutation sequence

# resolve_run.py (Task 6)
acquire_lease(path, step_id, by, ttl_minutes=120) -> {"leased_by","leased_at","token"}   # token = ownership DETECTION (not a fence)
renew_lease(path, step_id, by, token) -> lease            # raises LeaseError if token/owner changed
snapshot_audit(path, step_id, *, recorded_proposal_id, proposal_digest, authorization_digest, policy_version) # into state_snapshot before first mutation
evaluate_merge_detected_gate(result_path) -> (bool, str)  # applied AND observed_base==intended_base AND observed_head_sha==expected_head_sha

# apply_driver.py (Task 8)
run_apply(*, source_kind, binding_ref, recorded_summary, authorization_path, ledger_path, step_id,
          actor_id, runner, gh_ops, result_path, workspace) -> dict

# apply_advance_base.py (Task 9) — advance_base(repo, merged_sha) "ok" ONLY when the bookkeeping PR is MERGED
make_f8_advance_base(finalizer_record, contents_ops, gh_ops) -> Callable[[str,str], dict]
```

---

### Task 1: Nave verb adapters — strict versioned contract + delete the raw-git trio

**Files:** Modify `lib/pulse/scripts/nave_adapter.py`; Modify `lib/pulse/scripts/tests/test_nave_adapter.py`; Create `lib/pulse/scripts/tests/fixtures/nave_apply/*.json`.

**Contract (protocol_version 1).** Verbs take `--name <pen> --json`; per-repo input via `--request <file>` where the file is `{"protocol_version":1,"repos":[...]}`. Results are `{"protocol_version":1,"adapter_state":"ok"|"error","repos":[...]}`. `pen_status` keeps its current **owner + repo-name** entry shape (which `execute()` combines at `pen_orchestrator.py:487-489`) and only **adds `clone_path`** per entry — do not switch to a combined `repo` field or preflight breaks.

**Interfaces:** Produces the `nave_adapter` functions in the Authoritative Interfaces table. Uses the real decode helper — note its signature is `_decode_json(command, completed)` (`nave_adapter.py:305`), not `_decode_json(raw)`.

- [x] **Step 1: Write failing tests** — for each verb: happy path; **required-field missing** → error; **state enum invalid** → error; **wrong `protocol_version`** → error; **absent `adapter_state`** → error (never invent `"ok"`); **repo coverage mismatch** (extra/missing/duplicate repo vs request) → error; **echoed mismatch** (`pen_branch` returns `expected_base_sha` ≠ requested) → error; **nonzero returncode with valid partial-failure JSON** → surfaced as per-repo `failed`, not a hard error; **malformed JSON** → error. Plus `test_trio_is_deleted` (no `provision_apply_branch`/`commit_apply_clones`/`push_apply_clones`).

```python
def test_pen_branch_rejects_echoed_expected_sha_mismatch():
    payload = {"protocol_version":1,"adapter_state":"ok","repos":[
        {"repo":"acme/docs","base_ref":"develop","expected_base_sha":"WRONG","observed_base_sha":"aaa",
         "apply_ref":"pulse/apply/p1","state":"ok"}]}
    runner = QueuedRunner([_json_ok(payload)])
    res = na.pen_branch(runner, "pen1", [{"repo":"acme/docs","base_ref":"develop","expected_base_sha":"aaa","apply_ref":"pulse/apply/p1"}])
    assert res["adapter_state"] == "error" and "echoed" in res["reason"].lower()

def test_missing_adapter_state_is_error_not_invented():
    runner = QueuedRunner([_json_ok({"protocol_version":1,"repos":[]})])  # no adapter_state
    assert na.pen_push(runner, "pen1", "b")["adapter_state"] == "error"
```

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement** a `_validate_apply_result(data, *, request_repos, required_fields, state_field="state")` helper that enforces protocol, envelope, `adapter_state` presence, per-repo required fields + `state` enum, exact coverage against `request_repos`, and echoed-field equality; each `pen_*` builds its argv (writing a **versioned** request envelope), calls the real `_decode_json(command, completed)`, and returns the validated dict (or `{"adapter_state":"error","reason":...,"repos":[]}`). **`pen_push` takes a `request: list[dict]` of `[{repo}]` so `request_repos` is authoritative for coverage** (never inferred from the response). `pen_reset` returns per-repo `local_reset`/`remote_deleted` separately. Preserve `Completed.returncode`; accept nonzero returncode with valid JSON as a normal decode (never a hard error keyed off exit status).

  **Revised against the actual shipped Nave contract** (`discreteds/nave` PR #2,
  `docs/superpowers/specs/2026-08-13-apply-verb-contract-handoff.md` — authoritative
  where it disagrees with this table): `pen_branch(runner, name, apply_ref, request)`
  — `apply_ref` is a single envelope-level field, not per-repo, so it's a distinct
  parameter, not folded into `request` as this table's original signature implied.
  `pen_commit(runner, name, branch, request, message)` gains the `branch` positional
  this table originally omitted. States are richer verb-specific closed sets
  (`stale-base`/`exists`/`evidence-unavailable` for branch, etc.), not a generic
  `"failed"`. `pen_status`/`pen_list --json` both gain `clone_path` (Task 2's own
  concern — cross-referenced here since the Nave-side handoff flagged it).
- [x] **Step 4: Run, verify pass.** `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py -q` — 86 passed. Full suite: `uv run pytest -q` — 1309 passed. `git diff --check` clean.
- [x] **Step 5: Commit** — `feat: strict versioned nave apply-verb adapters; delete raw-git trio`.

---

### Task 2: Re-derivation provider registry + ApplyAuthorization + digests + mandatory bounds (with fixture migration)

Re-derivation must invoke the **real, source-specific** proposal builders (a generic function cannot reproduce F8/generated/marketplace decisions).

**Files:** Modify `lib/pulse/scripts/mutation_plan.py` (mandatory bounds for allow-listed; `proposal_digest`); **Modify the three real builders to accept `mutation_policy` + `bound_paths`** — `plan_sync.build_apply_plans` (`plan_sync.py:249`, hardcodes `propose` at `:277`), `generator_dispatch.dispatch` (`generator_dispatch.py:279`, no bounds at `:329`), `marketplace_sync` builder (`marketplace_sync.py:253`, hardcodes `propose` at `:276`); Create `lib/pulse/scripts/apply_rederive.py` (provider input contexts + `collect_inputs` + `rederive`), `lib/pulse/scripts/apply_authorization.py`; Modify the allow-listed fixtures **in this task** — `test_apply_acceptance.py:476,590`, `test_pen_orchestrator.py:67`, `test_mutation_plan.py:291` — to supply `bound_paths`; Create `test_apply_rederive.py`, `test_apply_authorization.py`.

**Interfaces:** see table. **Re-derivation runs from FRESH SOURCE STATE via typed provider inputs — never from a pen and never from `read_repo_head` alone** (plan-review F1). `collect_inputs(source_kind, binding_ref, recorded_summary, *, io_seams)` gathers the real evidence each builder needs:
- `plan-sync` → collects a fresh `DocumentSnapshot` + `github_snapshot` (via `plan_sync_snapshot`, `plan_sync_snapshot.py:224`) + parsed binding, then `rederive` calls `plan_sync.build_apply_plans(reconciliation, binding, snapshot, actor, registry, mutation_policy="allow-listed", bound_paths=…)` and builds the F8 `finalizer_record` `{repo, base_ref, doc_path, expected_prior_blob, proposal_id, binding_id}` **directly from the fresh `DocumentSnapshot` + parsed binding** (`base_ref`/current blob/`sync.base.blob` live there — `plan_sync_snapshot.py:40,315` — not in `ApplyPlans`);
- `generated-artifact` → collects `Generator` + binding + nested snapshot, then the amended `generator_dispatch.dispatch(..., mutation_policy="allow-listed", bound_paths=…)`;
- `marketplace-sync` → computes fresh `MarketplaceDrift` + head SHA, then the amended marketplace builder.
The builders are **amended to take `mutation_policy` + `bound_paths`** (do not mutate a frozen `Proposal` afterward — it hardcodes `propose` today). `binding_id` is carried on `RederivedProposal` (Proposal has no binding field); `authorize` compares **all three** recorded-summary fields (binding/transformation/proposal_id).

- [ ] **Step 1: Write failing tests** — `rederive` on a `plan-sync` `ProviderInputs` returns a `RederivedProposal` whose `proposal.mutation_policy=="allow-listed"`, `bound_paths` non-empty, and `finalizer_record` populated from the snapshot; the **real** `build_apply_plans`/`generator_dispatch`/marketplace builders now emit an allow-listed proposal with bounds (not a substitute reconstruction); `authorize` refuses transformation/selection/binding/proposal_id mismatch; `proposal_digest`/`authorization_digest` are stable + versioned; `build_proposal(mutation_policy="allow-listed", bound_paths={})` raises `MutationPlanError`; migrated fixtures still pass.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement.** In `build_proposal`, after existing validation, `raise MutationPlanError(...)` when allow-listed and `bound_paths` is empty or does not cover `selection` exactly. Amend the three real builders to thread `mutation_policy` + `bound_paths` into their `build_proposal` call (default `propose`/`{}` keeps existing callers byte-for-byte). Add versioned `proposal_digest` (`"v1|"` + sorted-JSON sha256 over transformation/selection/expected_shas/bound_paths/policy/id/actor). Implement the provider input contexts + `collect_inputs` + `rederive` in `apply_rederive.py`. Implement `apply_authorization.py` (`ApplyAuthorization`, `load_authorization(path, transformation)`, `authorization_digest`, `authorize(...)`). Migrate the four fixtures to supply `bound_paths`.
- [ ] **Step 4: Run, verify pass** (`uv run pytest -q` fully green).
- [ ] **Step 5: Commit** — `feat: re-derivation provider registry, ApplyAuthorization, digests, mandatory bounds`.

---

### Task 3: Extract driver-owned allow-listed phase functions + evolve ApplyOps + landing invariants

Remove the allow-listed landing from `execute()`; make each boundary a standalone callable with typed evidence and full invariants.

**Files:** Modify `lib/pulse/scripts/pen_orchestrator.py` (remove the allow-listed branch from `execute()`, keep propose-only; extend `ApplyOps` protocol; add `PenRunResult.repo_landings`); Create `lib/pulse/scripts/apply_phases.py`, `lib/pulse/scripts/apply_ops.py`; Modify `tests/test_pen_orchestrator.py` (assert `execute()` blocks allow-listed with "use apply_driver"); Create `tests/test_apply_phases.py`, `tests/test_apply_ops.py`.

**Interfaces:** the `apply_phases.*` and `apply_ops.make_apply_ops` entries in the table. **Every F11 pre-exec gate is explicitly owned by a phase (plan-review F3 — no gate silently dropped in the move out of `execute()`):**
- `preflight_phase` (NEW): the pen-selection/pen-repo exact match (`pen_orchestrator.py:463`) **and** the stale/dirty preflight — exact status coverage + `working_tree=="clean"` + `freshness=="fresh"` + `divergence=="up-to-date"` (`pen_orchestrator.py:477`) + every selected repo has a `clone_path`. Runs after `pen_status`, before provision. Fail-closed `blocked`.
- `provision_phase`: per-repo `state=="ok"` **and** echoed `base_ref`/`expected_base_sha`/`apply_ref` match request **and** `observed_base_sha == expected` (remote-base CAS — else stale-base `blocked`).
- `exec_phase`: **runs the tool-presence probe (`executor_probe`, `executor_probe.py:40`) before `pen_exec`** — a missing formatter/`npm`/docs-generator → `blocked` naming the tool+ecosystem (this probe has no production caller today; wire it here).
- `validate_phase`: `paths_changed` (no-op/wrong-target) + `json_schema`, via the reader.
- `commit_phase`: passes `proposal.bound_paths`; returns `local_commit_sha`.
- `push_phase`: **verifies the reader's observed HEAD == `local_commit_sha` BEFORE calling `push_repos`** (an invalid local HEAD must be caught before a push, not after — spec §10 "no push on a failed gate"), then requires `remote_sha == local_commit_sha` **and** `remote_ref == pulse/apply/{id}` — any mismatch → `failed`.
- Reader lifecycle: build an **identity-only** reader after `preflight_phase` (no `expected_branch` yet — the apply branch doesn't exist); **re-check with `expected_branch=pulse/apply/{id}` + base HEAD after `provision_phase`**; verify post-commit HEAD in `push_phase`.
- `cleanup`: called after **any** post-provision failure (provision-partial, exec, validate, commit, push), CAS-guarded via `reset_repos` (only confirmed-pushed repos get a remote-CAS delete; local-only repos get a local reset).

- [ ] **Step 1: Write failing tests** — `execute()` with an allow-listed plan returns `blocked` ("use apply_driver"); `preflight_phase` blocks on dirty/stale/behind status, on a pen-selection mismatch, and on a missing `clone_path`; `exec_phase` blocks on a missing tool; `provision_phase` blocks on `observed_base_sha` drift and echoed-field mismatch; `push_phase` fails on pre-push reader-HEAD ≠ commit SHA **without calling `push_repos`**, and on `remote_sha != local_commit_sha` / wrong `remote_ref`; `cleanup` issues `reset_repos` with only confirmed-pushed SHAs.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `apply_phases.py` (`preflight_phase` + the six callables + `cleanup`), evolve the `ApplyOps` protocol + `make_apply_ops` (4 args incl. `base_refs`), add `PenRunResult.repo_landings`, and make `execute()` return `blocked` for any non-propose policy (landing now lives in `apply_phases`, called by the driver). Keep every propose-path gate intact.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: driver-owned allow-listed phase functions + landing invariants`.

---

### Task 4: Identity-hardened clone reader (repo→path map + expected branch/HEAD)

**Files:** Modify `lib/pulse/scripts/pen_clone_reader.py`; Modify `tests/test_pen_clone_reader.py`.

**Interfaces:** `make_pen_clone_reader(clone_paths: dict[str,str], selection, *, expected_remotes: dict[str,str]|None=None, expected_branch: str|None=None, expected_heads: dict[str,str]|None=None) -> PenCloneReaders`; raises `PenCloneReaderError` on missing coverage, duplicate paths, `.git` absence, wrong `origin`, wrong branch, or (post-commit) wrong HEAD.

- [ ] **Step 1: Write failing tests** — exact-coverage, duplicate-path, `origin` mismatch, `expected_branch` mismatch, and `expected_heads` mismatch each raise.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** the map-based signature + checks (`git -C <path> remote get-url origin` normalized to `owner/name`; `git -C <path> rev-parse --abbrev-ref HEAD`; HEAD compare when `expected_heads` given). Keep the three reader closures keyed off the map.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: identity-hardened pen clone reader`.

---

### Task 5: Result contract — apply-status base/head + required audit fields; evolve all writers

**Files:** Modify `lib/pulse/scripts/validate_result.py` (`apply-status` + `repo-mutation`); Modify `lib/pulse/scripts/apply_reconcile.py` (`write_apply_status`/`open_apply_pr` signatures + all callers to carry the new fields); Modify `lib/patterns/headless-contract.md`; Modify `tests/test_validate_result.py`.

**Interfaces:** `apply-status` gains required `recorded_proposal_id`, `proposal_digest`, `authorization_digest`; and `intended_base`, `expected_head_sha` **required (non-null) from `pushed` onward**, `observed_base` + `observed_head_sha` **required for `applied`**; cross-rule `pushed_sha == expected_head_sha`. `repo-mutation` gains the three required audit fields.

- [ ] **Step 1: Write failing tests** — audit fields required; `pushed` without `intended_base`/`expected_head_sha` rejected; `applied` without `observed_base`/`observed_head_sha` rejected; `pushed_sha != expected_head_sha` rejected.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** the validator additions and thread the fields through `write_apply_status`/`open_apply_pr` and every caller.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: apply-status base/head + required audit fields`.

---

### Task 6: Merge gate (base+head) + mismatch handling + typed base resolver + lease fencing token

**Files:** Create `lib/pulse/scripts/apply_lock.py` (the flock context manager); Modify `lib/pulse/scripts/apply_reconcile.py` (`view_pr` requests `baseRefName,headRefOid`; **mismatch control flow** — do not write `applied` before the gate; on base/head mismatch persist evidence + reason and mark the step `blocked`/`failed`, never finalize; remove the CLI `main` default; add a typed intended-base resolver per source; **`open_apply_pr` accepts and renews the caller's lease token instead of independently reacquiring** — `apply_reconcile.py:205`); Modify `lib/pulse/scripts/resolve_run.py` (`evaluate_merge_detected_gate` base+head; `acquire_lease` returns a `token`; add `renew_lease(path, step, by, token)`; add `snapshot_audit(...)` writing the audit block into `state_snapshot` — today an empty map, `resolve_run.py:152`); Modify `tests/test_apply_reconcile.py`, `tests/test_resolve_run.py`, Create `tests/test_apply_lock.py`.

**Interfaces:** see table. **Fencing is the real fix (plan-review F5):** `apply_lock(lock_path)` is an OS advisory lock (`fcntl.flock`) the driver holds across the **entire** mutation sequence — that, not the ledger token, provides same-machine mutual exclusion. The ledger `token` is **ownership detection** (`acquire_lease` mints a fresh token; `renew_lease` raises `LeaseError` unless `(leased_by, token)` match); `open_apply_pr`/reconcile/F8 take the existing token rather than reacquiring, so a takeover is detected. **Cross-machine git-CAS acquisition is v2.** `snapshot_audit` persists `recorded_proposal_id`/`proposal_digest`/`authorization_digest`/`policy_version` into `state_snapshot` before the first mutation (plan-review F7).

- [ ] **Step 1: Write failing tests** — `apply_lock` is mutually exclusive (a second holder blocks/raises); gate rejects wrong base and wrong head; reconcile on mismatch marks the step `blocked` and does **not** call the finalizer; `open_apply_pr` does not reacquire when given a token; a stolen lease makes `renew_lease` on the original raise; `snapshot_audit` writes the audit block; the base resolver returns `develop` for a develop-based binding (no `main` default).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `apply_lock.py`, the gate additions, the reconcile mismatch branch, the base resolver, the token-passing lease + `snapshot_audit`, and thread the token through `open_apply_pr`.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: flock fence, base+head gate, mismatch handling, audit snapshot`.

---

### Task 7: Write-ahead phase journal

**Files:** Create `lib/pulse/scripts/apply_journal.py`, `tests/test_apply_journal.py`.

**Interfaces:** `Journal.begin(repo, phase, token, **evidence)` writes an **intent** record before an irreversible boundary; `Journal.complete(repo, phase, **evidence)` records success after; `state(repo)` returns `{phase, in_progress, evidence, token}`. **Every boundary is journaled write-ahead — including `pen_ready` and `pr_opened`** (plan-review F4), so no call is made without a preceding intent record. Atomic writes (temp + rename). Evidence includes the F8 finalizer fields + apply/audit identity + fencing token.

**Crash recovery for the non-idempotent `transformed` boundary (plan-review F4).** Live status alone cannot tell "transform completed" from "partially applied then crashed". v1's contract requires **deterministic transformations** (Global Constraints), so the recovery is deterministic: on resume with `in_progress == "transformed"`, the driver **resets the clone to the provisioned base** (Nave `pen reset` local) and **re-runs the transform from clean** — the same base + argv yields the same output, so re-execution is safe and never duplicates or half-applies. Provision/commit/push/PR boundaries reconcile from exact remote evidence (branch/ref/SHA); only `transformed` needs the reset+re-exec path.

- [ ] **Step 1: Write failing tests** — `begin` then reload shows `in_progress`; `complete` clears it and advances `phase`; evidence + token survive reload; a `pen_ready`/`pr_opened` intent is recorded before its call; the resume helper, given `in_progress=="transformed"`, returns a "reset-then-re-exec" directive.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** atomic YAML journal with begin/complete/state + a `resume_action(repo)` that maps an `in_progress` phase to the recovery directive (`transformed` → reset+re-exec; others → verify-remote-evidence).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: write-ahead apply phase journal`.

---

### Task 8: `apply_driver.py` — sequence the phases, journaled + fenced (single-repo v1)

**Files:** Create `lib/pulse/scripts/apply_driver.py`, `tests/test_apply_driver.py`.

**Interfaces:** `run_apply(...)` per the table. **Order — every check that can block runs BEFORE the first mutation `pen_create` (plan-review F2):**

```
collect_inputs (fresh source state, no pen) → rederive → recorded-summary-identity check →
authorize → single-repo check → snapshot_audit(ledger) → capability handshake →
acquire_lease(token) + apply_lock(flock) →   # ── first mutation boundary ──
pen_create → pen_status → build identity reader → preflight_phase →
[Journal.begin/renew_lease/phase/Journal.complete for] provision → (re-check reader branch+base) →
exec (tool probe) → validate → commit → (verify HEAD) push →
durable `pushed` apply-status BEFORE PR → open_apply_pr(token)
```

Re-derivation + authorization + single-repo happen on **fresh source state** (Task 2's `collect_inputs`), so no pen is created for an unauthorized/multi-repo/mismatched proposal, and `snapshot_audit` records the audit block before any mutation — a handshake or pre-mutation failure still writes a valid `repo-mutation` with the audit digest. Resume reads the journal, uses `resume_action(repo)` (Task 7), reconciles remote-evidence boundaries against live Nave/GitHub and resets+re-execs a crashed `transformed`, and restarts at the first unverified phase. Every mutation boundary re-checks the token under the held flock; a fenced-out driver stops.

- [ ] **Step 1: Write failing tests** — unauthorized → `blocked`, **no `pen_create` called**; multi-repo selection → `blocked`, no `pen_create`; summary-identity mismatch → `blocked`, no `pen_create`; handshake fail → `blocked` with the audit block present, no `pen_branch`; a second driver holding the flock blocks the first before mutation; a token stolen between phases → driver stops before the next Nave/GitHub call; happy path reaches `pushed` with `expected_head_sha == remote_sha` and writes durable apply-status before `open_apply_pr`.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `run_apply` in the order above — pre-mutation gating on fresh source state, then the flock-held, journaled, token-fenced phase sequence — writing `repo-mutation` (with audit fields) on any pre-push exit and durable `apply-status` at `pushed` (`intended_base`, `expected_head_sha = remote_sha`). `main()` CLI.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: apply_driver — journaled, fenced, single-repo Path A run`.

---

### Task 9: F8 finalizer — Contents adapter + pure finalization + bookkeeping-PR-merged semantics

**Files:** Create `lib/pulse/scripts/apply_advance_base.py` (pure finalization + `make_f8_advance_base`), `lib/pulse/scripts/gh_contents_ops.py` (`GhContentsCliOps`: get file@ref → `{content,file_sha}`, create branch@base, PUT with `file_sha` CAS, open PR, view PR merged-state), `tests/test_apply_advance_base.py`, `tests/test_gh_contents_ops.py`; Modify `lib/pulse/scripts/apply_reconcile.py` (`reconcile` CLI builds `advance_base=make_f8_advance_base(record, GhContentsCliOps(), gh_ops)`).

**Interfaces:** `advance_base(repo, merged_sha) -> {"state": "ok"|"blocked"|"failed"|"blocked-on-gate", "reason"?}`. **The `ok` invariant (plan-review F9): `ok` means the intended-base document is observed to contain the desired merged-document blob** — normally this follows a merged bookkeeping PR; an already-advanced document is the idempotent equivalent (`ok` with no new PR). A first pass that must change the base opens the bookkeeping PR and returns `blocked-on-gate` (a later reconcile re-checks and returns `ok` once merged); Pulse never merges. Finalization uses `plan_sync.parse_document`/`patch_document` (`plan_sync.py:514,559`) to preserve frontmatter/body formatting. Dual CAS: semantic (parsed `sync.base.blob == expected_prior_blob`) **and** Contents API `file_sha`.

- [ ] **Step 1: Write failing tests** — semantic-CAS mismatch → `blocked`; already-advanced → `ok` (idempotent); first pass opens a PR → `blocked-on-gate` (not `ok`); PR observed merged → `ok`; the frontmatter patch preserves body formatting (via `patch_document`). Command-test `GhContentsCliOps` against real `gh` JSON shapes with an injected runner.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** the pure finalizer, `GhContentsCliOps`, and the reconcile wiring (load the finalizer record written by Task 8).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: F8 doc-blob finalizer (dual-CAS, bookkeeping-PR-merged)`.

---

### Task 10: `gh-apply` skill (interactive trigger)

**Files:** Create `skills/gh-apply/SKILL.md`; Modify `commands/hiivmind-pulse-gh.md`.

- [ ] **Step 1:** Write the skill (CONTEXT → RESOLVE → EXECUTE → REPORT) wrapping `apply_driver.run_apply` (open PR) + `apply_reconcile reconcile` (detect merge → advance base), with an explicit STOP/confirm before the first mutation. Orchestration only — no new code paths.
- [ ] **Step 2:** Route "apply <proposal>" intent in the gateway command.
- [ ] **Step 3: Commit** — `feat: gh-apply interactive trigger skill`.

---

### Task 11: Acceptance matrix (split) + neutrality/import-boundary guards

**Files:** Modify `tests/test_apply_acceptance.py`, `tests/test_apply_neutrality.py`; fixtures under `lib/pulse/scripts/tests/fixtures/nave_apply/` (single pinned path).

**Interfaces:** drives the **real `apply_driver`** against Nave-verb `--json` fixtures + injected `gh_ops`/`contents_ops`.

- [ ] **Step 1: Neutral lockfile lifecycle** — `refresh-node-lockfile` through `run_apply`, **terminal at merge** (pure-neutral has no base to advance); assert push targets `pulse/apply/{id}`, `expected_head_sha == remote_sha`, re-derivation+authorization (unauthorized + summary-identity-mismatch refused), capability handshake (absent verb → blocked pre-mutation), and the absent-tool gate (missing formatter/`npm` → `blocked` naming the tool).
- [ ] **Step 2: F8 plan-sync lifecycle** — a `plan-sync` doc-patch through `run_apply` **with** the finalizer record + bookkeeping-PR-merged advance (`blocked-on-gate` then `ok`).
- [ ] **Step 3: Robustness (driver-level, plan-review F3/F4/F5)** — parametrized crash at **every** journal boundary, incl. a `transformed` crash that resumes via **reset+re-exec** (asserting the transform is not duplicated and no partial output is committed); a **fenced-out** driver (token stolen / flock held) emits no further Nave/GitHub mutation; **pre-exec gate coverage through the driver**: dirty tree, stale base, behind divergence, malformed/missing `pen_status`, wrong pen selection, a missing tool, a wrong post-provision branch, and a **pre-push HEAD mismatch that blocks before `push_repos`** each `blocked`/`failed` with no push; wrong-base and wrong-head merges rejected + step blocked (not finalized); `develop`-base resolution; strict adapter corruption/evidence-mismatch fixtures (missing field, duplicate/extra repo, echoed mismatch, nonzero-with-valid-JSON, `pen_push` coverage gap).
- [ ] **Step 4: Guards** — extend the structural neutrality guard to `apply_driver`/`apply_advance_base`/`apply_phases`/`apply_ops` (no `profile_dispatch`/claude-plugin imports; no `profile:claude-plugin` predicate); flip the import-boundary test from "trio unreachable" to "`apply_phases`/`apply_ops` are the only modules passing commit/push/branch flags." Log any mocked boundary (real remote merge) as a known coverage note.
- [ ] **Step 5: Run** `uv run pytest -q` + `git diff --check` and **commit** — `test: gate apply-mode neutral end-to-end through the real driver`.

---

### Task 12: Close the propose-only doc debt (spec §9)

**Files:** Modify `pen_orchestrator.py:21` docstring + `:136` `PenPlan.request_push`; Modify `lib/patterns/repository-mutations.md` (C1 Implementation → Nave `pen branch` verb).

- [ ] **Step 1:** Update the two docstrings to reflect allow-listed landing living in `apply_phases`/`apply_driver` (propose control flow unchanged).
- [ ] **Step 2:** Update `repository-mutations.md` C1 Implementation line; leave the invariant text intact.
- [ ] **Step 3: Run** `uv run pytest lib/pulse/scripts/tests/test_pen_orchestrator.py -q` (green) and **commit** — `docs: retire propose-only wording; point C1 at the nave branch verb`.

---

## Completion note (per plan review Minor 13)

This plan's final verification is a **Pulse contract/fixture gate**, not the spec's real-repo phase gate. A green suite here means "Pulse half built and fixture-proven"; the production phase remains blocked on the Nave-fork verbs being installed and the workspace enrollment PR. Do not report a fixture-only PR as the complete apply phase.

## Follow-ups (out of this plan)

- **Nave fork plan** (`discreteds/nave`): implement the Task 1 verbs + post-exec repo-control invariants + the "output actually lands on real clones" integration proof + Rust tests. **Blocks production integration.**
- **Workspace enrollment PR** (`hiivmind/hiivmind-workspace` → main): `ApplyAuthorization` policy + a real neutral proposal source, gated on the installed engine.
- **Deferred (v2 / captured):** multi-repo apply (per-repo children + aggregate + partial-push independence), cross-machine git-CAS lease acquisition, F5-marker advance, F9/F2 Path B emitter wiring, scheduled auto-apply + `allow`, submodules/LFS.
