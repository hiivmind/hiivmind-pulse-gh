# Apply-Mode Pulse-Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a re-derived, workspace-authorized `allow-listed` proposal for a **single repo** end-to-end — **through Nave verbs only** (no clone-write git in Pulse) — with a driver-owned, crash-resumable phase sequence, a base-and-head-verified merge gate, and a PR-gated F8 base advance.

**Architecture:** Single-mutator (PR #141): Nave owns all clone writes; Pulse keeps orchestration, policy, and read-only verification. This is the **`hiivmind-pulse-gh` half**. Two decisions from the plan review (Codex `gpt-5.6-sol`, 2026-07-30) shape it: **(1) driver-owned phase functions** — the allow-listed landing is extracted out of `execute()` into resumable phase callables the driver sequences and journals; `execute()`'s propose path is untouched. **(2) single-repo v1** — one repo per proposal; a multi-repo proposal is blocked with a reason; per-repo children + aggregate are deferred to v2. The Nave verbs land in a **separate `discreteds/nave` fork plan** that conforms to Task 1's contract; workspace enrollment is a follow-up.

**Tech Stack:** Python 3.10+ PEP 723 scripts, PyYAML, pytest, `gh` CLI, `nave` CLI (new verbs), git (read-only in Pulse). No new library dependencies.

**Source spec:** `docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md`. Read it and this plan's **Authoritative Interfaces** table before starting.

## Global Constraints

- **No clone-write git in Pulse.** Every branch/commit/push/reset is a Nave verb via `nave_adapter`. Read-only `git rev-parse`/`status` in `pen_clone_reader` stays. The F8 bookkeeping PR uses the GitHub Contents API (not a clone write).
- **`execute()`'s propose path is byte-for-byte unchanged.** The allow-listed landing is **removed** from `execute()` and relocated to driver-owned phase functions (Task 3). `execute()` remains propose-only.
- **Single repo per apply run (v1).** A proposal whose `selection` has >1 repo is `blocked` with reason `"multi-repo apply is v2"` before any mutation.
- **Fail closed** on any missing verb/reader/tool, stale base, out-of-allowlist change, unauthorized proposal, or evidence mismatch.
- **Every apply run writes a validated result on every exit.** Pre-push exits write `repo-mutation`; `apply-status` is remote-lifecycle only. A non-zero `validate_result.py` exit is a bug.
- **Values are built from the re-derived `Proposal` + observed facts — never reconstructed.**
- **Nave contract is versioned** (`protocol_version: 1` on every request and result); a capability handshake fails closed before any mutation against an incompatible Nave.
- **Real exception type:** `mutation_plan` raises `MutationPlanError` (not bare `ValueError`) — tests assert that.
- `uv run pytest -q` and `git diff --check` pass before each task closes; **each task's commit leaves the whole suite green** (fixture migrations land in the same task that breaks them).

## Authoritative Interfaces (single source of truth — every task and test uses these verbatim)

```
# nave_adapter.py (Task 1)
NAVE_APPLY_PROTOCOL = 1
pen_capabilities(runner) -> {"protocol_version": int|None, "verbs": list[str], "adapter_state": str, "reason": str|None}
pen_branch(runner, name, request: list[dict]) -> {"adapter_state","repos":[{repo,base_ref,expected_base_sha,observed_base_sha,apply_ref,state,reason?}]}
pen_commit(runner, name, request: list[dict], message) -> {"adapter_state","repos":[{repo,local_commit_sha,state,reason?}]}
pen_push(runner, name, branch)   -> {"adapter_state","repos":[{repo,remote,remote_ref,remote_sha,upstream,local_commit_sha,state,reason?}]}
pen_reset(runner, name, branch, request: list[dict]) -> {"adapter_state","repos":[{repo,local_reset,remote_deleted,state,reason?}]}
pen_status(runner, name)  # existing owner/name shape UNCHANGED; each repo entry GAINS clone_path
# request envelopes are versioned: {"protocol_version":1,"repos":[...]}

# apply_rederive.py (Task 2)
RederivedProposal(binding_id: str, proposal: Proposal, source_kind: str, finalizer_record: dict|None)
rederive(source_kind, binding_ref, recorded_summary, *, read_repo_head, actor, registry) -> RederivedProposal
mutation_plan.proposal_digest(proposal) -> str          # versioned, domain-separated
apply_authorization.authorization_digest(auth) -> str    # versioned
apply_authorization.load_authorization(path, transformation) -> ApplyAuthorization
apply_authorization.authorize(rederived: RederivedProposal, auth, recorded_summary) -> None  # raises AuthorizationError

# apply_phases.py (Task 3) — driver-owned, each returns typed per-repo evidence
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

# resolve_run.py (Task 6)
acquire_lease(path, step_id, by, ttl_minutes=120) -> {"leased_by","leased_at","token"}   # token = fencing generation
renew_lease(path, step_id, by, token) -> lease            # raises LeaseError if token/owner changed
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

- [ ] **Step 1: Write failing tests** — for each verb: happy path; **required-field missing** → error; **state enum invalid** → error; **wrong `protocol_version`** → error; **absent `adapter_state`** → error (never invent `"ok"`); **repo coverage mismatch** (extra/missing/duplicate repo vs request) → error; **echoed mismatch** (`pen_branch` returns `expected_base_sha` ≠ requested) → error; **nonzero returncode with valid partial-failure JSON** → surfaced as per-repo `failed`, not a hard error; **malformed JSON** → error. Plus `test_trio_is_deleted` (no `provision_apply_branch`/`commit_apply_clones`/`push_apply_clones`).

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

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** a `_validate_apply_result(data, *, request_repos, required_fields, state_field="state")` helper that enforces protocol, envelope, `adapter_state` presence, per-repo required fields + `state` enum, exact coverage against `request_repos`, and echoed-field equality; each `pen_*` builds its argv (writing a **versioned** request envelope), calls the real `_decode_json(command, completed)`, and returns the validated dict (or `{"adapter_state":"error","reason":...,"repos":[]}`). `pen_reset` returns per-repo `local_reset`/`remote_deleted` separately. Preserve `Completed.returncode`; accept nonzero **only** with a valid partial-failure document. Extend `pen_status` decode to pass through `clone_path`. **Delete** the trio (`nave_adapter.py:500-616`) and its tests (incl. `:724`).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: strict versioned nave apply-verb adapters; delete raw-git trio`.

---

### Task 2: Re-derivation provider registry + ApplyAuthorization + digests + mandatory bounds (with fixture migration)

Re-derivation must invoke the **real, source-specific** proposal builders (a generic function cannot reproduce F8/generated/marketplace decisions).

**Files:** Modify `lib/pulse/scripts/mutation_plan.py` (mandatory bounds for allow-listed; `proposal_digest`); Create `lib/pulse/scripts/apply_rederive.py`, `lib/pulse/scripts/apply_authorization.py`; Modify the allow-listed fixtures **in this task** — `test_apply_acceptance.py:476,590`, `test_pen_orchestrator.py:67`, `test_mutation_plan.py:291` — to supply `bound_paths`; Create `test_apply_rederive.py`, `test_apply_authorization.py`.

**Interfaces:** see table. `rederive` dispatches on `source_kind ∈ {"plan-sync","generated-artifact","marketplace-sync"}`:
- `plan-sync` → calls `plan_sync.build_apply_plans(reconciliation, binding, snapshot, actor, registry)` (`plan_sync.py:249`) with fresh reconciliation, sets `mutation_policy="allow-listed"`, and captures the F8 `finalizer_record` (`{repo, base_ref, doc_path, expected_prior_blob, proposal_id, binding_id}`);
- `generated-artifact` → `generator_dispatch` build path (`generator_dispatch.py:300`);
- `marketplace-sync` → `marketplace_sync` build path (`marketplace_sync.py:253`).
Each supplies the required `id` + `actor` (and `registry`) that `build_proposal` needs (`mutation_plan.py:318`). `binding_id` is carried on `RederivedProposal` (Proposal has no binding field), and `authorize` compares **all three** recorded-summary fields (binding/transformation/proposal_id).

- [ ] **Step 1: Write failing tests** — `rederive("plan-sync", …)` returns a `RederivedProposal` whose `proposal.mutation_policy=="allow-listed"`, `bound_paths` non-empty, and `finalizer_record` populated; `authorize` refuses transformation/selection/binding/proposal_id mismatch; `proposal_digest`/`authorization_digest` are stable + versioned; `build_proposal(mutation_policy="allow-listed", bound_paths={})` raises `MutationPlanError`; migrated fixtures still pass.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement.** In `build_proposal`, after existing validation, `raise MutationPlanError(...)` when allow-listed and `bound_paths` is empty or does not cover `selection` exactly. Add versioned `proposal_digest` (`"v1|"` prefix + sorted-JSON sha256 over transformation/selection/expected_shas/bound_paths/policy/id/actor). Implement the provider registry in `apply_rederive.py` (each provider imports and calls its real builder). Implement `apply_authorization.py` (`ApplyAuthorization`, `load_authorization(path, transformation)`, `authorization_digest`, `authorize(rederived, auth, recorded_summary)` comparing binding/transformation/proposal_id + `selection ⊆ permitted_repos` + `policy=="allow-listed"`). Migrate the four fixtures to supply `bound_paths`.
- [ ] **Step 4: Run, verify pass** (`uv run pytest -q` fully green).
- [ ] **Step 5: Commit** — `feat: re-derivation provider registry, ApplyAuthorization, digests, mandatory bounds`.

---

### Task 3: Extract driver-owned allow-listed phase functions + evolve ApplyOps + landing invariants

Remove the allow-listed landing from `execute()`; make each boundary a standalone callable with typed evidence and full invariants.

**Files:** Modify `lib/pulse/scripts/pen_orchestrator.py` (remove the allow-listed branch from `execute()`, keep propose-only; extend `ApplyOps` protocol; add `PenRunResult.repo_landings`); Create `lib/pulse/scripts/apply_phases.py`, `lib/pulse/scripts/apply_ops.py`; Modify `tests/test_pen_orchestrator.py` (assert `execute()` blocks allow-listed with "use apply_driver"); Create `tests/test_apply_phases.py`, `tests/test_apply_ops.py`.

**Interfaces:** the `apply_phases.*` and `apply_ops.make_apply_ops` entries in the table. Invariants enforced in the phases:
- `provision_phase`: per-repo `state=="ok"` **and** echoed `base_ref`/`expected_base_sha`/`apply_ref` match request **and** `observed_base_sha == expected` (remote-base CAS — else stale-base `blocked`).
- `commit_phase`: passes `proposal.bound_paths`; returns `local_commit_sha`.
- `push_phase`: requires `remote_sha == expected_local_shas[repo]` (the commit SHA) **and** `remote_ref == pulse/apply/{id}`; and the reader's post-commit HEAD equals `local_commit_sha` — any mismatch → `failed` (no PR).
- `cleanup`: called after **any** post-provision failure (provision-partial, exec, validate, commit, push), CAS-guarded via `reset_repos`.

- [ ] **Step 1: Write failing tests** — `execute()` with an allow-listed plan returns `blocked` ("use apply_driver"); `provision_phase` blocks on `observed_base_sha` drift and on echoed-field mismatch; `push_phase` fails on `remote_sha != local_commit_sha`, on wrong `remote_ref`, and on reader-HEAD ≠ commit SHA; `cleanup` issues `reset_repos` with only confirmed-pushed SHAs.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `apply_phases.py` (the six callables + `cleanup`), evolve the `ApplyOps` protocol + `make_apply_ops` (4 args incl. `base_refs`), add `PenRunResult.repo_landings`, and make `execute()` return `blocked` for any non-propose policy (the landing logic now lives in `apply_phases`, called by the driver). Keep every propose-path gate intact.
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

**Files:** Modify `lib/pulse/scripts/apply_reconcile.py` (`view_pr` requests `baseRefName,headRefOid`; **mismatch control flow** — do not write `applied` before the gate; on base/head mismatch persist evidence + reason and mark the step `blocked`/`failed`, never finalize; remove the CLI `main` default; add a typed intended-base resolver per source); Modify `lib/pulse/scripts/resolve_run.py` (`evaluate_merge_detected_gate` base+head; `acquire_lease` returns a `token`; add `renew_lease(path, step, by, token)`); Modify `tests/test_apply_reconcile.py`, `tests/test_resolve_run.py`.

**Interfaces:** see table. Fencing: `acquire_lease` mints a fresh `token` (a monotonic counter or content hash of prior lease + `now`) each acquisition; `renew_lease` raises `LeaseError` unless `(leased_by, token)` still match. (v1 relies on single-writer + atomic file replace; **cross-machine git-CAS acquisition is a documented v2 extension**.)

- [ ] **Step 1: Write failing tests** — gate rejects wrong base and wrong head; reconcile on mismatch marks the step `blocked` and does **not** call the finalizer; a stolen lease makes `renew_lease` on the original raise; the base resolver returns `develop` for a develop-based binding (no `main` default).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** the gate additions, the reconcile mismatch branch, the base resolver, and the token-bearing lease.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: base+head merge gate, mismatch handling, fencing-token lease`.

---

### Task 7: Write-ahead phase journal

**Files:** Create `lib/pulse/scripts/apply_journal.py`, `tests/test_apply_journal.py`.

**Interfaces:** `Journal.begin(repo, phase, token, **evidence)` writes an **intent** record before an irreversible boundary; `Journal.complete(repo, phase, **evidence)` records success after; `state(repo)` returns `{phase, in_progress, evidence, token}`. So a crash between `begin` and `complete` is detectable (`in_progress != None`) and reconcilable against live Nave/GitHub. Atomic writes (temp + rename). Evidence includes the F8 finalizer fields + apply/audit identity + fencing token.

- [ ] **Step 1: Write failing tests** — `begin` then reload shows `in_progress`; `complete` clears it and advances `phase`; evidence survives reload; token persisted.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** atomic YAML journal with begin/complete/state.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: write-ahead apply phase journal`.

---

### Task 8: `apply_driver.py` — sequence the phases, journaled + fenced (single-repo v1)

**Files:** Create `lib/pulse/scripts/apply_driver.py`, `tests/test_apply_driver.py`.

**Interfaces:** `run_apply(...)` per the table. Order: **handshake → lease(token) → pen_create/pen_status → build reader (identity-checked) → re-derive + authorize → write F8 finalizer record → phase sequence (each: `Journal.begin(token)` → verify ownership via `renew_lease(token)` → phase call → `Journal.complete`) → durable `pushed` apply-status BEFORE PR → `open_apply_pr`**. Resume reads the journal, reconciles each `in_progress`/completed phase against live Nave (`pen_status`, reused-branch exact-match) + GitHub, and restarts at the first unverified phase. A multi-repo `selection` → `blocked` ("multi-repo apply is v2") before any mutation. Every mutation boundary re-checks the fencing token; a fenced-out driver stops.

- [ ] **Step 1: Write failing tests** — handshake fail → `blocked` no mutation; unauthorized → `blocked` no mutation; multi-repo selection → `blocked` no mutation; lease held by another → blocks before `pen_branch`; a token stolen between phases → driver stops before the next Nave/GitHub call; happy path reaches `pushed` with `expected_head_sha == remote_sha` and writes durable apply-status before `open_apply_pr`.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `run_apply` sequencing `apply_phases` with the journal + fencing, writing `repo-mutation` on any pre-push exit (with audit fields) and durable `apply-status` at `pushed` (with `intended_base`, `expected_head_sha = remote_sha`). `main()` CLI.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: apply_driver — journaled, fenced, single-repo Path A run`.

---

### Task 9: F8 finalizer — Contents adapter + pure finalization + bookkeeping-PR-merged semantics

**Files:** Create `lib/pulse/scripts/apply_advance_base.py` (pure finalization + `make_f8_advance_base`), `lib/pulse/scripts/gh_contents_ops.py` (`GhContentsCliOps`: get file@ref → `{content,file_sha}`, create branch@base, PUT with `file_sha` CAS, open PR, view PR merged-state), `tests/test_apply_advance_base.py`, `tests/test_gh_contents_ops.py`; Modify `lib/pulse/scripts/apply_reconcile.py` (`reconcile` CLI builds `advance_base=make_f8_advance_base(record, GhContentsCliOps(), gh_ops)`).

**Interfaces:** `advance_base(repo, merged_sha) -> {"state": "ok"|"blocked"|"failed"|"blocked-on-gate", "reason"?}`. **"ok" is returned ONLY when the bookkeeping PR is observed MERGED** (base truly advanced). On first pass it opens the bookkeeping PR and returns `blocked-on-gate` (a later reconcile re-checks); Pulse never merges. Finalization uses `plan_sync.parse_document`/`patch_document` (`plan_sync.py:514,559`) to preserve frontmatter/body formatting. Dual CAS: semantic (parsed `sync.base.blob == expected_prior_blob`) **and** Contents API `file_sha`.

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
- [ ] **Step 3: Robustness** — parametrized crash at **every** journal boundary (resume completes without repeating a non-idempotent step); a **fenced-out** driver emits no further Nave/GitHub mutation; wrong-base and wrong-head merges rejected + step blocked (not finalized); `develop`-base resolution; strict adapter corruption/evidence-mismatch fixtures (missing field, duplicate/extra repo, echoed mismatch, nonzero-with-valid-JSON).
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
