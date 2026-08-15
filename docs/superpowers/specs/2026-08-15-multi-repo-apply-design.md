# Multi-Repo Apply (v2) — Design Spec

**Date:** 2026-08-15
**Status:** Approved (brainstorm)
**Origin:** `lib/pulse/scripts/apply_driver.py` — the `raise RederiveError("multi-repo apply is v2")`
guard; the apply-mode production-wiring spec's single-mutator / single-repo v1 scope
(`docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md`).

**Read alongside:** the production-wiring spec (§ 4 authorization model, § 5A–E components), the
workspace-enrollment design (`docs/superpowers/specs/2026-08-14-apply-mode-workspace-enrollment-design.md`),
`lib/pulse/scripts/apply_rederive.py` (re-derivation providers), `lib/pulse/scripts/apply_driver.py`
(the fenced sequencer), `lib/pulse/scripts/apply_reconcile.py` (status + reconcile), and
`docs/backlogs/README.md` (cross-repo dependency map).

---

## 1. Problem — one repo at a time

Apply-mode today lands one allow-listed mutation on **one** repository per run. The driver's
`run_apply` hard-blocks at `len(proposal.selection) > 1` with `RederiveError("multi-repo apply is
v2")`. For fleet-of-repos management — the flagship use case the harness exists for — that means a
fleet-wide sweep (e.g. `format-python` across every hiivmind Python repo) is N manual single-repo
invocations with no shared proposal, fence, journal, or rollup. One repo's outcome is invisible to
the others, and there is no fleet-level terminal state.

This closes the gap: **one proposal → N repositories**, driven through the existing already-multi-
repo spine, with per-repo independent outcomes and a fleet-level rollup.

## 2. Decisions (settled in brainstorm)

1. **One proposal, N repos** — a single proposal id + one fence/lease/journal spans all repos; one
   pen holds N clones; N branches/PRs (one per repo); per-repo reconcile with a fleet rollup. This
   is the literal `multi-repo is v2` stub, not an orchestration fan-out of the single-repo driver.
2. **Fleet naming = explicit list + optional selector.** A binding names `repos: [...]`
   explicitly, and may add a `repo_selector` resolved at collect-time against nave's fleet cache.
   The two union (de-duplicated, sorted) and the resolved list is recorded in the proposal for
   audit.
3. **Per-repo independent failure.** A repo failing at provision/transform/commit/push is recorded
   `failed`/`blocked` in its own outcome; the rest continue. Terminal is per-repo.
4. **Nave owns fleet discovery.** Selector resolution shells out to nave (per F11: "nave owns the
   clone lifecycle end-to-end — fleet discovery, refresh, pen creation"). pulse-gh never
   re-implements repo enumeration; it consumes a nave fleet-query result.
5. **Fleet id is deterministic over the resolved repo set.** Single-repo bindings keep the existing
   `apply-{transformation}-{owner}-{name}` id (stable — referenced in existing ledgers/audit
   trails); fleet bindings use `apply-{transformation}-{owner}-{sha256(sorted repos)[:12]}` so a
   membership change yields a new proposal id.

## 3. Architecture — what already works vs. what changes

The mutation spine is **already multi-repo**. Verified against current code:

| Layer | Shape today | Change needed |
|-------|-------------|---------------|
| `mutation_plan.Proposal` | `selection: tuple`, `expected_shas: dict[repo,sha]`, `bound_paths: dict[repo,paths]` | none |
| `mutation_plan.build_proposal` | cross-repo validation (no dupes, shas/bounds cover selection exactly) | none |
| `apply_authorization.authorize` | iterates every selected repo against `permitted_repos` + per-repo `bound_paths` | none |
| `apply_journal.Journal` | records keyed `repos[repo]` with per-repo phase/evidence | none |
| `apply_phases.{preflight,provision,exec,validate,commit,push}` | all loop `for repo in proposal.selection`, return `dict[repo, outcome]` | none |
| `nave_pen` / `nave_apply` | one pen ↔ N clones; verbs take per-repo request maps | none |
| `apply_rederive._collect_neutral` / `_rederive_neutral` | single `repo`, single `head_sha` | **fleet expansion + per-repo HEAD** |
| `apply_reconcile.resolve_intended_base` | returns one `base_ref` string | **per-repo base refs** |
| `apply_driver.run_apply` | `>1` guard + scalar `repo`/`base_refs`/`_finish_push` | **per-repo iteration + outcomes** |
| `apply_reconcile.write_apply_status` / `open_apply_pr` / `reconcile_apply` | scalar `branch`/`pushed_sha`/`pr_url`/`merged_sha` | **per-repo `repos` map + rollup** |
| `resolve_run` ledger step | scalar `repo` (run-level `repos` already a list) | **step `repos: [...]`** |

Four files carry the scalar assumptions; the rest is untouched.

## 4. pulse-gh changes

### 4.1 Binding schema + fleet expansion (`apply_rederive.py`)

A neutral binding is exactly one of single-repo or fleet:

```yaml
# single (unchanged)                 # fleet (new)
- repo: hiivmind/agent-kernel        - repos: [hiivmind/a, hiivmind/b]
  transformation: format-python        repo_selector:            # optional; unions in
  base_ref: main                         term: "pyproject:true"  # resolved via nave fleet
  bound_paths: [src/**]                transformation: format-python
                                       bound_paths: [src/**]
```

- `_validate_neutral_binding` accepts exactly one of `repo` (single) or `repos`/`repo_selector`
  (fleet) — both present, or neither, is a `RederiveError` (fail-closed).
- `_collect_neutral` resolves the fleet: explicit `repos` ∪ selector results, de-duplicated and
  sorted, then fetches live HEAD **per repo** via `io_seams.gh_api(repos/{o}/{n}/branches/{base})`,
  returning `head_shas: dict[repo, sha]` (replacing the single `head_sha`). A per-repo HEAD fetch
  failure is a per-repo blocked outcome, not a whole-run abort — see § 5.1 for the collect/fence
  split.
- **Selector resolution** uses nave as the fleet source of truth: pulse-gh shells out to
  `nave fleet list --json` (new, § 8) and parses `[{owner, name, default_branch}]`. A selector is
  a nave search term (the same term syntax `nave search` uses). The resolved list is captured in the
  proposal for audit (§ 4.3).
- **Per-repo base ref**: each repo's base is its resolved default branch (from fleet meta), with the
  binding's explicit `base_ref` as a global override (or a per-repo `base_refs` map for
  heterogeneous fleets). `resolve_intended_base("neutral", …)` returns `dict[repo, base_ref]`.

### 4.2 Re-derivation (`_rederive_neutral`)

Builds one multi-repo proposal from the binding + per-repo HEADs:

```python
selection = tuple(sorted(resolved_repos))
id = neutral_proposal_id(binding)          # single-repo: apply-{t}-{owner}-{name};
                                            # fleet:      apply-{t}-{owner}-{sha256(selection)[:12]}
mutation_plan.build_proposal(
    id=id,
    selection=selection,
    transformation=binding["transformation"],
    expected_shas=head_shas,               # dict[repo, sha] — every repo covered
    bound_paths={repo: binding["bound_paths"] for repo in selection},
    mutation_policy="allow-listed",
    actor=actor,
    registry=inputs.registry,
)
```

The neutral transformation allowlist (`NEUTRAL_TRANSFORMATIONS`) and `build_proposal`'s exact
per-repo `bound_paths` coverage checks are unchanged — they now fire per repo. `NeutralProviderInputs`
gains `head_shas: dict[str, str]` and a resolved `selection: tuple[str, ...]` (replacing the single
`head_sha`; the single-repo path is a degenerate one-element fleet). `binding_id` for `authorize()`
identity becomes the fleet id (single-repo keeps `binding["repo"]`).

### 4.3 Audit of the resolved fleet

Selector expansion is **dynamic**, so the proposal must record what it actually resolved. The
resolved, sorted `selection` is:
- the `Proposal.selection` (already part of the proposal → already in the proposal digest), and
- captured in `recorded_summary["selection"]` so the synthesized-summary identity check (§ 4.5 of
  the enrollment spec) pins the exact membership the run is authorized for.

A selector that resolves to an empty set is a `RederiveError` (fail-closed: "nothing to do" is
never silently a no-op apply).

## 5. Driver (`apply_driver.py`)

### 5.1 Fence + collection split

The current driver collects/re-derives/authorizes **before** acquiring the lease, and a collect
failure returns a whole-run `blocked` status. For multi-repo this is wrong: one repo's missing HEAD
must not block the other N. Split:

- **Collect + re-derive + authorize** (pre-fence): fleet resolution must succeed as a whole —
  selector expansion, proposal construction, and `authorize()` are whole-run gates (a bad binding,
  an unauthorized repo, or an empty selector is a whole-run `blocked`, because the proposal itself
  is the unit of authorization). A per-repo HEAD fetch that fails here is recorded as a **per-repo
  blocked outcome** and the repo is dropped from `selection` — not a whole-run abort — because the
  remaining repos still form a valid, authorized proposal.
- **Fenced mutation** (post-lease): per-repo independent. The existing phases already return
  per-repo outcomes; the driver loops, records each repo's outcome in the journal, and continues on
  failure.

### 5.2 Iteration

- Delete the `len(selection) > 1` guard. `apply_branch = pulse/apply/{id}` and
  `pen_name = pulse-apply-{id}` stay scalar — one proposal, one pen, one branch name per repo
  (branches live in different repos, so the shared name does not collide).
- `base_refs` becomes `dict[repo, base_ref]` (from § 4.1); `bound_paths` stays `dict[repo, paths]`
  (already per-repo; the existing `_expand_bound_globs` already iterates repos).
- Drive the phases once per proposal (they already loop repos internally); the driver's job is to
  interpret the per-repo outcome dict and record each repo's journal state.
- **`_finish_push` → per repo**: `open_apply_pr` is called once per repo that reached `pushed`;
  each PR is recorded in that repo's outcome. Repos that failed earlier are already recorded and
  skipped.

### 5.3 Crash-resume

The existing resume contract holds per repo: the journal is keyed per repo, and a crash between a
phase and its completion receipt resumes that repo (reset + re-exec for `transformed`, remote
reconciliation for `pushed`) without touching repos that already completed. The driver's resume
logic iterates the same per-repo records it already reads; the only change is looping over the
selection instead of a single `repo`.

## 6. Status + reconcile (`apply_reconcile.py`)

### 6.1 Multi-repo apply-status

`write_apply_status` gains a per-repo map while keeping the top-level summary fields:

```yaml
kind: apply-status
contract_version: 1
state: pr_opened                    # fleet rollup (§ 6.2)
proposal_id: apply-format-python-hiivmind-<hash12>
selection: [hiivmind/a, hiivmind/b]   # was [repo]; now the full fleet
repos:
  hiivmind/a:
    state: pr_opened
    branch: pulse/apply/apply-format-python-hiivmind-<hash12>
    intended_base: main
    expected_head_sha: 5be8f8f…
    pushed_sha: 5be8f8f…
    pr_url: https://github.com/hiivmind/a/pull/1
    merged_sha: null
    observed_base: main
    observed_head_sha: 5be8f8f…
    reason: null
  hiivmind/b:
    state: applied
    # … same shape, merged_sha set
```

Backward compatibility: `load_apply_status` accepts the v1 single-repo shape (no `repos` map) and
normalizes it to a one-element fleet in memory, so an in-flight v1 result file is still reconcilable.
New writes always emit the multi-repo shape.

### 6.2 Fleet rollup state

The top-level `state` is a pure function of the per-repo states, in precedence order (first match
wins — this is total over every combination):

```
any repo state in {pr_opened, pushed}            -> pr_opened
all repos applied                                -> applied
all repos rejected                               -> rejected
all repos in {failed, blocked}                   -> failed
otherwise (mixed applied/rejected/failed/blocked) -> partial
```

Whole-run `blocked`/`failed` statuses from the pre-fence gates (§ 5.1) are not a rollup — they are
written directly, before any per-repo outcome exists.

### 6.3 Reconcile loop

`reconcile_apply` re-runs per repo: for each repo in the `repos` map, it checks that repo's PR merge
state (base + head verified, same CAS as today), updates that repo's `state`/`merged_sha`, then
recomputes the rollup. Pure-neutral means no base advance per repo (§ 4.4 of the enrollment spec);
the `applied` terminal needs **all** repos merged. `open_apply_pr` and the CLI surface are per-repo:
the driver calls them per repo; the reconcile CLI takes the same fleet-scoped proposal id and
reconciles every repo in the result's `repos` map in one pass.

## 7. Ledger (`resolve_run.py`)

The ledger step's scalar `repo` becomes `repos: [...]` (the run-level `repos` is already a list; the
step now mirrors it so one step = one fleet proposal). Single-repo steps keep `repos: [one]`.
`find_step`/`check_dag`/`recompute_status` are unchanged (they already treat `repos` as opaque at the
run level; the step field is additive). The `--repos` create flag already accepts a comma-separated
list, so `cmd_create` needs only to write the step's `repos` from the same source.

## 8. nave — fleet query (`nave fleet list --json`)

- A dedicated `nave fleet list --json` subcommand (chosen over a `--json` flag on `nave search`:
  a stable, search-syntax-independent contract the driver depends on; `nave search`'s term syntax
  remains free to evolve). It resolves a term against the fleet cache and emits:

```json
[{"owner": "hiivmind", "name": "agent-kernel", "default_branch": "main"}]
```

- Reuses the existing `nave_search` matcher against the scanned fleet cache; no new discovery logic.
- Deterministic output (sorted) so the resolved selection is stable and the fleet id is reproducible.
- Missing/empty fleet cache → non-zero exit; the driver surfaces that as a `blocked` outcome
  ("selector resolution requires a prior `nave scan`"), matching the F11 "scan before pen" lifecycle.

## 9. Testing

1. **Re-derive** (`test_apply_rederive_neutral`): fleet expansion from explicit `repos`; selector
   union + dedup + sort; per-repo HEAD fetch into `head_shas`; fleet id determinism (same sorted
   set → same id; different set → different id); empty selector → `RederiveError`; single-repo id
   unchanged for backward compatibility.
2. **Driver**: N repos through the full phase sequence; one repo failing at provision/transform/
   commit leaves the others proceeding; per-repo journal states; `_finish_push` opens N PRs.
3. **Reconcile**: multi-repo status schema round-trip; v1 single-repo normalization; rollup
   transitions (`pr_opened` → `partial` → `applied`); per-repo merge detection.
4. **Live proof**: a 2-repo `format-python` run (bindings for two real hiivmind repos) driving the
   real `apply_driver` → one pen/two clones → two branches → two PRs → merge one → `partial` →
   merge both → `applied`. Then the selector path against the real fleet (post `nave scan`).

## 10. Non-goals (v2 scope guard)

- **Scheduled multi-repo applies** (sweeps on a cron) — the ledger already carries scheduled mode,
  but the fleet run is still triggered interactively here; a scheduled sweep workflow is a follow-up.
- **Merge-on-green auto-merge policy** — reconcile still waits for manual merge per repo (as v1).
- **Cross-repo atomicity** — PRs are independent by nature; there is no all-or-nothing rollback.
- **Non-neutral sources' multi-repo** — plan-sync / generated-artifact / marketplace-sync remain
  single-repo (their bindings are single-repo by shape); this spec generalizes the neutral provider
  only. The driver/reconcile/status changes are source-agnostic, so the other providers gain the
  capability for free when their bindings grow a fleet shape — but that is out of scope here.
