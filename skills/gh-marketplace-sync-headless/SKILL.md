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
  § plan-sync-result.yaml shape, mirrored). No result-validator kind is
  registered for `marketplace-sync` in F9 v1; the controller decides when
  to validate and what to do with the envelope.

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

## State

Determine `RESULT_PATH` before validating the workspace: explicit
`result_path`; otherwise the workspace default when `workspace_path` is
non-empty and usable; otherwise `./marketplace-sync-result.yaml` in the
current directory. This fallback must be available for every early ABORT
to write its result.

```text
CONFIG_DIR         = {workspace_path}/.hiivmind/github
SYNC_CONFIG        = CONFIG_DIR/marketplace-sync.yaml
RESULT_PATH        = {explicit result_path, workspace default, or current-directory fallback}
LOGIN              = unknown
RUN_AT             = current UTC timestamp
MODE               = {mode, default scheduled}
MUTATION_POLICY    = {mutation_policy, default propose}
BINDINGS           = []
SNAPSHOT           = empty    # releases + marketplace_doc per binding
FINDINGS           = []
PROPOSALS          = []
PROPOSED_ACTIONS   = []
ERRORS             = []
COUNTS             = {bindings_scanned: 0, in_sync: 0, drift: 0, missing_entry: 0, unknown: 0, not_applicable: 0}
```

## Phase 1: CONTEXT

1. Missing `workspace_path` → ABORT `"missing required input: workspace_path"`.
2. Missing `CONFIG_DIR/config.yaml` or its top-level `workspace` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. Read the authoritative `.workspace.login` from `CONFIG_DIR/config.yaml`
   into `LOGIN`.
4. Ensure `*-result.yaml` is present in `CONFIG_DIR/.gitignore`.
5. Read the marketplace-sync bindings list from `SYNC_CONFIG.bindings[]`
   and validate each binding's locator (`plugin_id`, `repo`,
   `marketplace_repo`, `marketplace_file`). Do not use configuration
   `metadata` blocks as decision authority.
6. When `repo` is present, resolve it against configured binding `repo`
   values. An unresolvable value → ABORT `"unknown repo: {repo}"`.
   Otherwise narrow `BINDINGS` to the matching records.
7. A valid empty selected set is a successful no-op, not an ABORT.
8. For each binding, if the binding locator is malformed (missing required
   fields, non-string `repo` / `marketplace_repo`, etc.) → append a typed
   `invalid_binding` finding (`severity: medium`) and skip the binding;
   do not count it as scanned.

**See:** `lib/patterns/config-parsing.md`,
`lib/patterns/headless-contract.md`.

## Phase 2: DISCOVER

For each selected binding, fetch the remote evidence into `SNAPSHOT[binding]`.

1. Resolve the binding's `marketplace_repo` and `marketplace_file`. Use the
   `gh api` REST surface to read the file at the binding's default branch
   HEAD; parse the response body as JSON. A fetch or parse failure → set
   `marketplace_doc = None` and record a typed `unreadable_marketplace_file`
   finding (`severity: medium`) on the binding. The discoverer never
   fabricates a `marketplace_doc` from cached bytes.
2. Resolve the binding's `repo` and run
   `gh release list --json tagName,isPrerelease,isDraft --limit 100 --repo
   {owner}/{name}` (or the equivalent `gh api` route) to fetch the release
   list. A fetch failure → set `releases = []` and record a typed
   `unreadable_release_list` finding (`severity: medium`) on the binding.
3. Increment `bindings_scanned` once per binding whose `DISCOVER` step
   returned (any outcome). Bindings with a malformed locator counted in
   Phase 1 do not enter `DISCOVER` and do not increment `bindings_scanned`.

**See:** `lib/references/api-routing.md`, `lib/patterns/id-resolution.md`.

## Phase 3: COMPARE

For each selected binding, call
`marketplace_sync.compare(binding, releases, marketplace_doc)` and store
the returned `MarketplaceDrift` keyed by binding.

1. A `not_applicable` drift means the binding was not configured for the
   target repo. Increment `not_applicable`; do not enter Phase 4.
2. An `unknown` drift (no stable release, or unparseable
   `marketplace_doc`) increments `unknown`; record a typed finding with
   `drift.reason` in the finding's `detail`. Do not enter Phase 4.
3. An `in_sync` drift increments `in_sync`; do not enter Phase 4.
4. A `drift` or `missing_entry` drift increments the matching counter and
   enters Phase 4.

**See:** `lib/pulse/scripts/marketplace_sync.py`.

## Phase 4: PROPOSE

For every non-`in_sync` / non-`not_applicable` / non-`unknown` drift (so
`drift` or `missing_entry` only):

1. Resolve the binding's `marketplace_repo` HEAD SHA via
   `gh api repos/{owner}/{repo}/commits/HEAD --jq .sha`. A failure →
   append a typed `unreadable_head` finding (`severity: high`) and skip
   the binding; do not build a proposal without an `expected_shas`
   entry — the F6 guard requires it.
2. Call
   `marketplace_sync.build_marketplace_proposal(drift, head_sha, actor,
   registry=...)`. The proposal selects `drift.marketplace_repo` and
   carries `expected_shas={marketplace_repo: head_sha}`. `mutation_policy`
   is always `propose` (this orchestrator is propose-only).
3. Append a `PROPOSALS` record carrying `binding` (the binding's
   `plugin_id`), `transformation` (`marketplace-entry-update`), and
   `proposal_id` from the built proposal.
4. Append a `PROPOSED_ACTIONS` record naming the proposal ID, the
   marketplace repo, and the planned target version.
5. Never call `gh api` to apply the patch, write the marketplace document,
   or run a pen. With `mutation_policy: apply`, append a deferred-action
   note naming the F9 v1 limitation instead of applying.

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
