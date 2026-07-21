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
- The binding source is `CONFIG_DIR/plan-sync.yaml`, whose `docs[]` records carry
  `id`, `repo`, `branch`, `path`, and `sync` data. A plan document remains the source
  of its own frontmatter, while the configuration supplies the discovery scope.
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
SNAPSHOT         = empty
FINDINGS         = []
PROPOSED_ACTIONS = []
ERRORS           = []
COUNTS           = {docs_scanned: 0, in_sync: 0, doc_patches: 0, github_patches: 0, conflicts: 0, excluded: 0}
```

## Phase 1: DISCOVER

1. Missing `workspace_path` → ABORT `"missing required input: workspace_path"`.
2. Missing `CONFIG_DIR/config.yaml` or its top-level `workspace` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. Read the authoritative `.workspace.login` from `CONFIG_DIR/config.yaml` into
   `LOGIN`.
4. Ensure `*-result.yaml` is present in `CONFIG_DIR/.gitignore`.
5. Missing `SYNC_CONFIG` → ABORT `"plan-sync.yaml not found: {SYNC_CONFIG}"`.
6. Load `SYNC_CONFIG.docs[]`. Validate every selected `sync:` mapping with
   `validate_result.validate_sync_binding`; invalid bindings append deterministic
   `snapshot_error` findings and are excluded from collection.
7. When `repo` is present, resolve it against configured document repository names.
   An unresolvable value → ABORT `"unknown repo: {repo}"`. Otherwise narrow
   `BINDINGS` to the matching records.
8. A valid empty selected set is a successful no-op, not an ABORT.

**See:** `lib/patterns/config-parsing.md`, `lib/patterns/plan-sync-binding.md`,
`lib/pulse/scripts/validate_result.py`.

## Phase 2: SNAPSHOT

Collect remote evidence for `BINDINGS`. The collector reads only pushed document
content; a local checkout contributes only dirty/ahead exclusion metadata.

Call `plan_sync_snapshot.collect(BINDINGS, workdir=workspace_path)` once and retain
its documents and findings unchanged. Collection gaps produce explicit `error`
documents and findings; do not assume a failed read is a no-op.

For every snapshot finding, append its typed form to `FINDINGS`. Increment
`docs_scanned` for every returned document. Documents whose state is `excluded` add
one to `excluded`; documents whose state is `in_sync` add one to `in_sync` and do not
enter COMPUTE.

**See:** `lib/pulse/scripts/plan_sync_snapshot.py`,
`lib/patterns/plan-sync-binding.md`.

## Phase 3: COMPUTE

For every changed snapshot document with complete document, GitHub, and body-base
evidence, call:

`plan_sync.compute(document.document, document.github, document.binding.sync, document.base_body)`.

Keep each returned reconciliation and its snapshot together for subsequent phases.

1. A reconciliation with conflicts increments `conflicts`; add a deterministic
   `base_conflict` finding for every conflicted field. It produces no apply proposal.
2. A reconciliation with no document patch and no GitHub patch increments `in_sync`.
   This covers both unchanged fields and concurrent equal edits.
3. Otherwise retain its independent document and GitHub patches. Do not count a
   patch until the corresponding APPLY phase builds its proposal.

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

## Phase 5: APPLY_DOC

For every non-conflicted reconciliation with a document patch, use the same
`plan_sync.build_apply_plans` result and retain only `repo_mutation` and `doc_patch`.

1. Verify that the repository mutation policy is `propose` and its expected head
   comes from the snapshot.
2. Increment `doc_patches` once for the F6 document proposal.
3. Append a proposed-action record that carries the proposal ID, document path, and
   expected head guard.
4. Never write `.hiivmind/plan-sync-patch.yaml`, run a pen, or apply a document
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

**See:** `lib/pulse/scripts/plan_sync.py`, `lib/patterns/plan-sync-binding.md` § V1 limitation.

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
errors: {ERRORS}
```

Validate the written result with:
`uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind plan-sync`.

Non-zero validation is an orchestrator defect; report validator stderr verbatim.
Print one line: `plan-sync: docs={docs_scanned} in_sync={in_sync} doc={doc_patches} github={github_patches} conflicts={conflicts} excluded={excluded}`.

## ABORT semantics

Every ABORT appends its reason to `ERRORS` and falls through to Phase 7 with zeroed
counts and empty findings. If `CONFIG_DIR` is unusable, write to the explicit
`result_path`, otherwise `plan-sync-result.yaml` in the current directory, and say so.

## Related

- `lib/pulse/scripts/plan_sync_snapshot.py` — pushed-document and issue evidence
- `lib/pulse/scripts/plan_sync.py` — merge, proposal, and finalization functions
- `lib/pulse/scripts/validate_result.py` — result and binding validation
- `lib/patterns/headless-contract.md` — result schema
- `lib/patterns/plan-sync-binding.md` — binding and V1 proposal limitation
