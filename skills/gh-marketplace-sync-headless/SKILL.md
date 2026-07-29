---
name: gh-marketplace-sync-headless
description: >
  Headless, generic marketplace entry version drift audit. Reads configured
  marketplace bindings, compares each plugin repo's newest stable release to
  the version recorded in the marketplace document, and records propose-only
  F6 proposals for any drift or missing entry. Never applies. Writes a
  marketplace-sync-result.yaml envelope. Zero prompts; explicit inputs only.
  Use when a scheduler detects a pushed plugin release, or when an
  orchestrator needs deterministic marketplace-sync proposals.
---

# Headless Marketplace Synchronization

Reconcile configured marketplace entries with their bound plugin repos'
newest stable release, recording propose-only F6 `marketplace-entry-update`
proposals for any drift or missing entry. This orchestrator never writes a
marketplace document, runs a pen, or applies a binding; F9 v1 is propose-only
end to end.

`{PLUGIN_ROOT}` is the directory containing `plugin.json`.

## Inputs and outputs

- `workspace_path` (required): absolute workspace root containing
  `.hiivmind/github/`.
- `repo` (optional): plugin repository full or short name; narrows the run
  to a single configured binding. Defaults to every configured binding.
- `result_path` (optional): workspace default when usable, otherwise
  `./marketplace-sync-result.yaml`.
- `mode` (optional): `interactive` or `scheduled`; defaults to `scheduled`.
  `marketplace-entry-update` is `allow_scheduled: false`, so scheduled runs
  are recorded as gated and never produce a runnable proposal.
- `mutation_policy` (optional): `propose` or `apply`; defaults to `propose`.
  V1 always records proposals. `apply` records the same deferred proposals
  and the V1 limitation; it never grants this orchestrator authority to
  mutate.
- Result: `marketplace-sync-result.yaml` envelope (`lib/patterns/headless-contract.md`
  § plan-sync-result.yaml shape, mirrored). It is validated by the
  `marketplace-sync` kind in `lib/pulse/scripts/validate_result.py` (see Phase 5).

## Contract

- Zero prompts. Explicit inputs only. Every exit writes a result file.
- The discovery source is `CONFIG_DIR/marketplace-sync.yaml`, whose
  `bindings[]` records carry only the binding locator (`plugin_id`, `repo`,
  `marketplace_repo`, `marketplace_file`). The marketplace document's parsed
  JSON and the plugin repo's release list are the only decision inputs.
- Only `marketplace_sync.compare` and `marketplace_sync.build_marketplace_proposal`
  determine the drift evidence and the proposal. Do not re-create their
  decision rules in this document.
- A binding is `not_applicable` (no output emitted for the bound repo) when
  the workspace config has no marketplace binding for the target plugin
  repo. This is a global F9 v1 constraint: marketplace sync applies only
  to repos with a configured binding. The result still records the run;
  the proposal count is zero.
- The discovery, comparison, and proposal paths remain separate. A
  marketplace proposal is an F6 `marketplace-entry-update` proposal; never
  combined with anything else; never applied here.
- Under `mutation_policy: propose`, drift and missing-entry outcomes become
  proposals and neither is applied. Under `mutation_policy: apply`, this V1
  orchestrator still records the same proposals as deferred and records
  the apply-mode limitation; it never grants this orchestrator authority
  to mutate.
- `unknown` outcomes (no stable release found, or unparseable marketplace
  document) are recorded as findings with a `severity: medium` typed
  `unknown_marketplace_doc` / `no_stable_release` finding. They never
  count as synchronized and never produce a proposal.
- Severity is deterministic and copied from `compare` evidence; no LLM
  judgment is involved at this layer.

## Execution

Execute the marketplace entry version drift audit by invoking the CLI driver:

```bash
uv run lib/pulse/scripts/marketplace_sync_run.py --workspace <workspace_path> [--repo <repo>] [--result <result_path>] [--mode scheduled|interactive]
```

The driver CLI handles workspace validation, binding loading, evidence collection via `gh`, delegation to `marketplace_sync.build_result`, writing the result YAML file, and self-validation via `validate_result.py`.

- If `--repo` is provided, it narrows the audit to matching configured bindings.
- If `--result` is provided, output is written to that path; otherwise to `.hiivmind/github/marketplace-sync-result.yaml` or `./marketplace-sync-result.yaml`.
- `--mode` controls scheduled vs interactive gating (`allow_scheduled: false` gated in scheduled mode).
- On any ABORT (e.g. invalid workspace or unknown repo), a valid `marketplace-sync` result file is written with the error recorded in `errors[]`.

Under `on_mutation: allow-listed`, marketplace entry writes land on GitHub via `lib/pulse/scripts/object_apply.py` (`apply_object_write`). The write is guarded by a typed `Precondition` (target file/version expected state) and verb `mutation_allowlist` check. Path B operates independently of Path A.

**See:** `lib/pulse/scripts/marketplace_sync.py`,
`lib/pulse/scripts/mutation_plan.py`,
`lib/patterns/repository-mutations.md`.

## Phase 5: RECORD

Write `RESULT_PATH` with:

```yaml
contract_version: 1
kind: marketplace-sync
workspace: {LOGIN}
run_at: "{RUN_AT}"
actor: { gh_login: {gh api user login or unknown}, machine: {hostname}, mode: {MODE} }
bindings_scanned: {COUNTS.bindings_scanned}
in_sync: {COUNTS.in_sync}
drift: {COUNTS.drift}
missing_entry: {COUNTS.missing_entry}
unknown: {COUNTS.unknown}
not_applicable: {COUNTS.not_applicable}
findings: {FINDINGS}
proposals: {PROPOSALS}
proposed_actions: {PROPOSED_ACTIONS}
errors: {ERRORS}
```

This envelope is validated by the `marketplace-sync` kind in
`lib/pulse/scripts/validate_result.py` (non-negative int counts +
`findings` + `proposals[]` with `binding`/`transformation`/`proposal_id`
+ string `proposed_actions`). Skills MUST write the file on every exit
(including early ABORT) so a missing file is never indistinguishable from
a crashed run.

Print one line:
`marketplace-sync: bindings={bindings_scanned} in_sync={in_sync} drift={drift} missing={missing_entry} unknown={unknown} not_applicable={not_applicable}`.

## ABORT semantics

Every ABORT appends its reason to `ERRORS` and falls through to Phase 5
with zeroed counts and empty findings, proposals, and proposed actions.
If `CONFIG_DIR` is unusable, write to the explicit `result_path`,
otherwise `marketplace-sync-result.yaml` in the current directory, and say
so.

## Related

- `lib/pulse/scripts/marketplace_sync.py` — decision and proposal builder
- `lib/pulse/scripts/mutation_plan.py` — F6 `Proposal` + registry
- `lib/patterns/headless-contract.md` — envelope shape (plan-sync mirror)
- `lib/patterns/repository-mutations.md` — F6 mutation vocabulary
- `lib/patterns/config-parsing.md` — workspace + binding config reads
