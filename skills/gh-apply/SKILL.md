---
name: gh-apply
description: >
  Interactive apply-mode trigger. Lands one recorded, workspace-authorized
  allow-listed proposal end-to-end through Nave verbs (no clone-write git): the
  apply driver re-derives the proposal from fresh source state, authorizes it,
  fences + journals a crash-resumable phase sequence, pushes a pulse/apply/{id}
  branch, and opens a PR; reconcile then detects the merge and advances the base
  through the F8 finalizer. Use when a user asks to "apply <proposal>", "land
  <proposal>", or "run the apply" for a recorded proposal. Orchestration only —
  it sequences existing driver/reconcile entry points, no new code paths.
---

# Apply a proposal (interactive, PR-gated)

Land one recorded allow-listed proposal against a single repository. The heavy
lifting lives in `lib/pulse/scripts/apply_driver.py` (`run_apply`) and
`lib/pulse/scripts/apply_reconcile.py` (the `reconcile` CLI); this skill gathers
the inputs, confirms before the first mutation, and sequences the two phases.

`{PLUGIN_ROOT}` is the directory containing `plugin.json`.

## Phase 0 — CONTEXT (no mutation)

Resolve the four inputs `run_apply` needs:

- `source_kind`: `plan-sync` | `generated-artifact` | `marketplace-sync`.
- `binding_ref`: the parsed binding mapping for the target (e.g. from the
  workspace's configured bindings, `{PLUGIN_ROOT}`/`.hiivmind/github/`).
- `recorded_summary`: the previously recorded proposal summary — the
  `{binding, transformation, proposal_id}` triple from the source's proposal
  record (summaries only; apply re-derives).
- `authorization_path`: the workspace `ApplyAuthorization` policy file
  (`{PLUGIN_ROOT}`/`.hiivmind/github/apply-authorization.yaml`) scoped to the
  transformation.
- `ledger_path` + `step_id`: the run ledger (`resolve_run`) step for this apply.

Do not re-derive or mutate here — `run_apply` re-derives from fresh source state
and fails closed on any authorization/summary mismatch.

## Phase 1 — RESOLVE + STOP (confirm before the first mutation)

Show the operator:

1. the transformation and its single target repository,
2. the intended base branch (resolved per source — never a `main` default),
3. the bound paths that will be committed.

**STOP and confirm** — `run_apply` provisions a branch, runs the transformation,
commits, and pushes, so the confirmation gate sits here, before any Nave verb.
Abort cleanly if the operator declines.

## Phase 2 — EXECUTE (the driver, fenced + journaled)

Invoke the driver (single repo per run — a multi-repo selection is blocked
before mutation):

```bash
uv run python lib/pulse/scripts/apply_driver.py \
  --source-kind "<source_kind>" \
  --binding-ref '<binding_ref_json>' \
  --recorded-summary '{"binding":"<b>","transformation":"<t>","proposal_id":"<p>"}' \
  --authorization "<authorization_path>" \
  --ledger "<ledger_path>" --step "<step_id>" \
  --actor "<login>@<machine>" \
  --result "<result_path>" --workspace "<workspace>"
```

The driver pre-mutation-gates (re-derive → authorize → single-repo → audit →
capability handshake → lease + flock) before the first Nave verb, journals every
boundary write-ahead, and writes a durable `pushed` apply-status before opening
the PR. On success `result["state"] == "pr_opened"`; a block/fail returns
`blocked`/`failed` with a `reason`.

## Phase 3 — RECONCILE (detect merge → advance base)

After the PR is reviewed and merged, reconcile detects the merge and (for
`plan-sync`) advances the base through the F8 finalizer:

```bash
uv run python lib/pulse/scripts/apply_reconcile.py reconcile \
  --ledger "<ledger_path>" --step "<step_id>" --proposal-id "<p>" --repo "<repo>" \
  --branch "pulse/apply/<p>" --result "<result_path>" \
  --recorded-proposal-id "<p>" \
  --proposal-digest "<proposal_digest>" --authorization-digest "<authorization_digest>" \
  --intended-base "<base>" --expected-head-sha "<remote_sha>" \
  --finalizer-record "<finalizer_record_file>" \
  --actor "<login>@<machine>" --workspace "<workspace>"
```

- `--finalizer-record` is required only for `plan-sync` (the F8 doc-blob
  finalizer); the driver persists it to `<result_path>.finalizer.yaml` on a
  successful run. Omit it for pure-neutral transformations, whose merge is
  terminal.
- The merge gate verifies BOTH base and head; a retargeted or force-pushed PR is
  rejected, never finalized. Pulse never merges — it only advances the base via
  a PR-gated bookkeeping PR (`blocked-on-gate` until that PR merges).

## Phase 4 — REPORT

Report the terminal `apply-status` (`result_path`): state (`pushed` /
`pr_opened` / `applied`), the pushed SHA and branch, the intended base, and any
`reason` on a block/fail. On `applied`, note the advanced base blob.

## Safety invariants (do not bypass)

- No clone-write git in Pulse: every branch/commit/push/reset is a Nave verb.
- Authorize before any mutation; single repo per run (v1).
- The STOP/confirm in Phase 1 is mandatory — never skip it for a mutation.
- Every run writes a validated result (`repo-mutation` pre-push, `apply-status`
  from `pushed` onward).
