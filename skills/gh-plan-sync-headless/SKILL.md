---
name: gh-plan-sync-headless
description: >
  Headless, generic plan-document synchronization audit. Reads configured plan
  bindings, snapshots pushed documents and GitHub issues, computes a three-way
  reconciliation, and records document and issue proposals without applying either
  path. Writes a validated plan-sync-result.yaml. Zero prompts; explicit inputs only.
  Use when a scheduler detects a pushed bound document, or when an orchestrator needs
  deterministic plan-sync proposals.
---

# Headless Plan Synchronization

Reconcile configured plan documents with their bound GitHub issues using only pushed
document bytes and remote issue evidence. The result is an auditable count summary;
all V1 mutations remain proposals. This orchestrator never changes a document,
issues an issue mutation, or advances a stored base.

`{PLUGIN_ROOT}` is the directory containing `plugin.json`.

## Inputs and outputs

- `workspace_path` (required): absolute workspace root containing `.hiivmind/github/`.
- `repo` (optional): document repository full or short name; narrows the run to
  configured bindings for that repository. Defaults to every bound document.
- `result_path` (optional): workspace default when usable, otherwise
  `./plan-sync-result.yaml`.
- `mode` (optional): `interactive` or `scheduled`; defaults to `scheduled`.
- `mutation_policy` (optional): `propose` or `apply`; defaults to `propose`.
  V1 always records proposals. `apply` records the same deferred proposals and the
  V1 limitation; it never grants this orchestrator authority to mutate.
- Result: validated `plan-sync-result.yaml` with kind `plan-sync`
  (`lib/patterns/headless-contract.md` § plan-sync-result.yaml).

## Contract

- Zero prompts. Explicit inputs only. Every exit writes a result file.
- The discovery source is `CONFIG_DIR/plan-sync.yaml`, whose `docs[]` records carry
  only the binding locator (`id`, `repo`, `branch`, and `path`). The pushed plan
  document's parsed `sync:` frontmatter is the sole source of issue, policy, and
  base reconciliation state; similarly named configuration data is never passed to
  the merge engine.
- Only `plan_sync_snapshot.collect`, `plan_sync.compute`,
  `plan_sync.build_apply_plans`, and `plan_sync.finalize` determine the sync
  evidence, merge, proposals, and safe base advancement candidates. Do not re-create
  their decision rules in this document.
- The document and GitHub paths remain separate. A document proposal is an F6
  `plan-sync-doc-patch` proposal; an issue patch is a Pulse proposed action. Neither
  path is an API call or a pen execution here.
- Under `mutation_policy: propose`, both paths become proposals and neither is
  applied. Under `mutation_policy: apply`, this V1 orchestrator still records both
  proposals as deferred and records the apply-mode limitation from
  `lib/patterns/plan-sync-binding.md` § V1 limitation.
- Local dirty documents, local-ahead branches, and detected renames are excluded.
  Snapshot errors remain explicit findings and never count as synchronized.
- Severity is deterministic and copied from snapshot or finalize evidence;
  `inferred: false` when this orchestrator adds a finding.

## State

Determine `RESULT_PATH` before validating the workspace: explicit `result_path`;
otherwise the workspace default when `workspace_path` is non-empty and usable;
otherwise `./plan-sync-result.yaml` in the current directory. This fallback must be
available for every early ABORT to write and validate its result.

```text
CONFIG_DIR       = {workspace_path}/.hiivmind/github
SYNC_CONFIG      = CONFIG_DIR/plan-sync.yaml
RESULT_PATH      = {explicit result_path, workspace default, or current-directory fallback}
LOGIN            = unknown
RUN_AT           = current UTC timestamp
MODE             = {mode, default scheduled}
MUTATION_POLICY  = {mutation_policy, default propose}
BINDINGS         = []
BINDING_CHECKOUTS = {}
SNAPSHOT         = empty
FINDINGS         = []
PROPOSALS        = []
PROPOSED_ACTIONS = []
ERRORS           = []
COUNTS           = {docs_scanned: 0, in_sync: 0, doc_patches: 0, github_patches: 0, conflicts: 0, excluded: 0}
```

## Execution

Execute the plan document synchronization audit by invoking the CLI driver:

```bash
uv run lib/pulse/scripts/plan_sync_run.py --workspace <workspace_path> [--repo <repo>] [--result <result_path>] [--mode scheduled|interactive]
```

The driver CLI handles workspace validation, binding loading, evidence collection via `plan_sync_snapshot.collect`, delegation to `plan_sync.build_result`, writing the result YAML file, and self-validation via `validate_result.py`.

- If `--repo` is provided, it narrows the audit to matching configured document bindings.
- If `--result` is provided, output is written to that path; otherwise to `.hiivmind/github/plan-sync-result.yaml` or `./plan-sync-result.yaml`.
- `--mode` controls scheduled vs interactive gating (`allow_scheduled: false` gated in scheduled mode).
- On any ABORT (e.g. invalid workspace or unknown repo), a valid `plan-sync` result file is written with the error recorded in `errors[]`.

## Phase 1: DISCOVER

1. Missing `workspace_path` → ABORT `"missing required input: workspace_path"`.
2. Missing `CONFIG_DIR/config.yaml` or its top-level `workspace` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. Read the authoritative `.workspace.login` from `CONFIG_DIR/config.yaml` into
   `LOGIN`.
4. Ensure `*-result.yaml` is present in `CONFIG_DIR/.gitignore`.
5. Missing `SYNC_CONFIG` → ABORT `"plan-sync.yaml not found: {SYNC_CONFIG}"`.
6. Load `SYNC_CONFIG.docs[]` and validate only each discovery locator (`id`, `repo`,
   `branch`, and `path`). Do not use or validate configuration `sync:` data as
   reconciliation authority. The collector parses and validates the pushed
   document's `sync:` mapping with `validate_result.validate_sync_binding`.
7. When `repo` is present, resolve it against configured document repository names.
   An unresolvable value → ABORT `"unknown repo: {repo}"`. Otherwise narrow
   `BINDINGS` to the matching records.
8. A valid empty selected set is a successful no-op, not an ABORT.
9. For each selected binding, resolve a local checkout only when its repository
   identity is verified to match that binding. Store that explicit per-binding path
   in `BINDING_CHECKOUTS`; absence of a verified checkout stores no path. Never use
   the workspace root itself as a document checkout.

**See:** `lib/patterns/config-parsing.md`, `lib/patterns/plan-sync-binding.md`,
`lib/pulse/scripts/validate_result.py`.

## Phase 2: SNAPSHOT

Collect remote evidence for `BINDINGS`. The collector reads only pushed document
content; a local checkout contributes only dirty/ahead exclusion metadata.

For each binding call `plan_sync_snapshot.collect([binding], workdir=checkout_path)`
with its verified `BINDING_CHECKOUTS` value, or `workdir=None` when no matching
checkout exists, then combine the returned documents and findings. The collector
always fetches remote evidence into an isolated temporary bare repository; the
checkout is consulted only for dirty/ahead metadata. Collection gaps produce
explicit `error` documents and findings; do not assume a failed read is a no-op.

For every snapshot finding, append its typed form to `FINDINGS`. Increment
`docs_scanned` for every returned document. Documents whose state is `excluded` or
`error` add one to `excluded`; documents whose state is `in_sync` add one to
`in_sync` and do not enter COMPUTE. The collector snapshots GitHub even when the
document blob equals `sync.base.blob`; it labels `in_sync` only after both peers
equal their bases.

**See:** `lib/pulse/scripts/plan_sync_snapshot.py`,
`lib/patterns/plan-sync-binding.md`.

## Phase 3: COMPUTE

For every changed snapshot document with complete document, GitHub, and body-base
evidence, call:

`plan_sync.compute(document.document, document.github,`
`document.document.binding, document.base_body, document_blob=document.blob)`.

Keep each returned reconciliation and its snapshot together for subsequent phases.

1. A reconciliation with conflicts increments `conflicts`; add a deterministic
   `base_conflict` finding for every conflicted field. It produces no apply proposal.
2. A reconciliation with no document patch, GitHub patch, or base-advance proposal
   increments `in_sync`. Concurrent equal edits require a frontmatter base proposal
   and are not `in_sync` until that proposal is confirmed.
3. Otherwise retain its independent document, GitHub, and frontmatter-base patches.
   Do not count a patch until the corresponding APPLY phase builds its proposal.

**See:** `lib/pulse/scripts/plan_sync.py`.

## Phase 4: APPLY_GITHUB

For every non-conflicted reconciliation with a GitHub patch, call
`plan_sync.build_apply_plans(reconciliation, binding, snapshot, actor)` and use only
its `github_mutation` output.

1. Verify that its mutation policy is `propose`.
2. Increment `github_patches` once for the proposed issue patch.
3. Append its `proposed_actions` values to `PROPOSED_ACTIONS`.
4. Never call GitHub to apply the patch. With `mutation_policy: apply`, append a
   deferred-action note naming the V1 limitation instead of applying it.

Under `on_mutation: allow-listed`, GitHub object-side writes (issue/milestone field patches) are executed through `lib/pulse/scripts/object_apply.py` (`apply_object_write` / `apply_issue_field_patch`). The write is guarded by a typed `Precondition` descriptor matching expected live state, checked for verb `mutation_allowlist` membership, and evaluated for idempotency before writing. Path B operates independently of Path A.

## Phase 5: APPLY_DOC

For every non-conflicted reconciliation with a document or frontmatter-base patch,
use the same `plan_sync.build_apply_plans` result and retain only `repo_mutation`
and `doc_patch`.

1. Verify that the repository mutation policy is `propose` and its expected head
   comes from the snapshot.
2. Increment `doc_patches` once for the F6 document proposal.
3. Append a proposed-action record that carries the proposal ID, document path, and
   expected head guard.
4. Append a `PROPOSALS` record carrying `binding`, `transformation`, and
   `proposal_id` from the built repository proposal. A GitHub-only
   state/assignees/milestone delta still enters this phase because its document
   proposal advances the corresponding `sync.base` scalar without changing the
   Markdown body.
5. Never write `.hiivmind/plan-sync-patch.yaml`, run a pen, or apply a document
   patch. With `mutation_policy: apply`, append a deferred-action note naming the
   V1 limitation instead.

**See:** `lib/pulse/scripts/plan_sync.py`, `lib/patterns/repository-mutations.md`,
`lib/patterns/plan-sync-binding.md` § V1 limitation.

## Phase 6: FINALIZE

Call `plan_sync.finalize` for every computed reconciliation with
`doc_applied: false` and `github_applied: false`. This V1 orchestrator has applied
neither path, so it never persists `base_patch` or advances `sync.base.blob`.

Copy any returned finalization findings into `FINDINGS`. A later apply-capable
consumer must re-snapshot and pass confirmed outcomes before it may persist bases.

Under allow-listed apply mode, `apply_reconcile.py` drives the resumable two-phase loop per repo:
1. `open_apply_pr`: Opens a PR (`create_or_get_pr`), writes `apply-status` at state `pr_opened`, and updates the run ledger step to `blocked-on-gate`.
2. `reconcile_apply`: Checks PR state via `view_pr`. On `MERGED`, writes `apply-status` state `applied` with `merged_sha`, clears the `merge_detected` gate, and advances base off `merged_sha`. On `CLOSED` unmerged, writes `state: rejected`, deletes the remote branch, and marks the ledger step `failed` (terminal).

**See:** `lib/pulse/scripts/plan_sync.py`, `lib/pulse/scripts/apply_reconcile.py`, `lib/patterns/plan-sync-binding.md` § V1 limitation.

## Phase 7: RECORD

Write `RESULT_PATH` with:

```yaml
contract_version: 1
kind: plan-sync
workspace: {LOGIN}
run_at: "{RUN_AT}"
actor: { gh_login: {gh api user login or unknown}, machine: {hostname}, mode: {MODE} }
docs_scanned: {COUNTS.docs_scanned}
in_sync: {COUNTS.in_sync}
doc_patches: {COUNTS.doc_patches}
github_patches: {COUNTS.github_patches}
conflicts: {COUNTS.conflicts}
excluded: {COUNTS.excluded}
findings: {FINDINGS}
proposals: {PROPOSALS}
proposed_actions: {PROPOSED_ACTIONS}
errors: {ERRORS}
```

Validate the written result with:
`uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind plan-sync`.

Non-zero validation is an orchestrator defect; report validator stderr verbatim.
Print one line: `plan-sync: docs={docs_scanned} in_sync={in_sync} doc={doc_patches} github={github_patches} conflicts={conflicts} excluded={excluded}`.

## ABORT semantics

Every ABORT appends its reason to `ERRORS` and falls through to Phase 7 with zeroed
counts and empty findings, proposals, and proposed actions. If `CONFIG_DIR` is
unusable, write to the explicit `result_path`, otherwise `plan-sync-result.yaml` in
the current directory, and say so.

## Related

- `lib/pulse/scripts/plan_sync_snapshot.py` — pushed-document and issue evidence
- `lib/pulse/scripts/plan_sync.py` — merge, proposal, and finalization functions
- `lib/pulse/scripts/validate_result.py` — result and binding validation
- `lib/patterns/headless-contract.md` — result schema
- `lib/patterns/plan-sync-binding.md` — binding and V1 proposal limitation
