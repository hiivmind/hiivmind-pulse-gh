---
name: gh-generated-artifact-headless
description: >
  Headless generated-artifact binding audit over committed template bindings
  (F7). Collects remote template and output-file evidence, classifies each
  configured binding as current, template-drift, local-customization, conflict,
  or error, and records regeneration proposals for template-drift bindings.
  Writes a validated generated-artifact-result.yaml. Zero prompts; explicit
  inputs only. Never applies mutations itself — F6 pen runs are propose-only.
  Use when a scheduler audits generated files, or a release gate needs
  template-drift evidence.
---

# Headless Generated Artifact Audit

Audit whether each generated-artifact binding is still current against the
remote source template and the recorded output blobs. Drift and customization are
computed purely from remote evidence, never from the local working tree of the
caller. The skill records findings and regeneration proposals; it does not write
`generated.yaml` or dispatch actual mutations.

`{PLUGIN_ROOT}` is the directory containing `plugin.json`.

## Inputs and outputs

- `workspace_path` (required): absolute workspace root containing `.hiivmind/github/`.
- `repo` (optional): a repository full or short name; narrows the audit to
  bindings whose `source` or binding id matches that repo. Defaults to
  every configured binding.
- `result_path` (optional): workspace default when usable, otherwise
  `./generated-artifact-result.yaml`.
- `mode` (optional): `interactive` or `scheduled`; defaults to `scheduled`.
- Result: validated `generated-artifact-result.yaml` with kind `generated-artifact`
  (`lib/patterns/headless-contract.md` § generated-artifact-result.yaml).

## Contract

- Zero prompts. Explicit inputs only. Every exit writes a result file.
- Read-only against GitHub and against the generation manifest: this skill never
  writes `generated.yaml` markers and never applies generated files. Drift
  bindings become `proposals` entries — typed records an orchestrator or human
  reviews before acting.
- F6 pen orchestration used here is always `propose-only`. The skill may route a
  `template-drift` binding through `pen_orchestrator.execute`, but only with a
  `mutation_policy` of `propose`; a push/commit is never requested.
- The F10 driver is propose-only: it never calls `pen_orchestrator.execute`.
  Proposal summaries carry only `{binding, transformation, proposal_id}`; the
  ephemeral full Proposal (built inside `build_result`) carries `expected_shas`
  so a later apply-mode consumer can re-run the guard.
- Missing or unreachable source branches, templates, or output blobs block
  closed: a binding that cannot be resolved is `state: error`, not `current`.
  This mirrors `generated_artifacts.audit()`'s own fail-closed rule; the skill
  copies the audit engine's verdict into the result unchanged.
- Severity on any finding this skill adds is deterministic, `inferred: false`.
  No LLM judgment pass runs here.

## State

Determine `RESULT_PATH` before validating the workspace: explicit `result_path`;
otherwise the workspace default when `workspace_path` is non-empty and usable;
otherwise `./generated-artifact-result.yaml` in the current directory. This
fallback must be available for every early ABORT to write and validate its result.

```text
CONFIG_DIR      = {workspace_path}/.hiivmind/github
MANIFEST        = CONFIG_DIR/generated.yaml
RESULT_PATH     = {explicit result_path, workspace default, or current-directory fallback}
LOGIN           = unknown
RUN_AT          = current UTC timestamp
MODE            = {mode, default scheduled}
ERRORS          = []
PROPOSALS       = []
PROPOSED_ACTIONS = []
```

## Execution

Execute the generated-artifact binding audit by invoking the CLI driver:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/generated_artifact_run.py" --workspace <workspace_path> [--repo <repo>] [--result <result_path>] [--mode scheduled|interactive]
```

The driver CLI handles workspace validation, manifest loading, evidence
collection via `generated_artifacts.collect`, delegation to
`generated_artifacts.build_result` (audit classification, generator
applicability, allowlist checks, and scheduled gating), writing the result YAML
file, and self-validation via `validate_result.py`.

- If `--repo` is provided, it narrows the audit to matching binding `source`
  values or binding ids.
- If `--result` is provided, output is written to that path; otherwise to
  `.hiivmind/github/generated-artifact-result.yaml` or
  `./generated-artifact-result.yaml`.
- `--mode` controls scheduled vs interactive gating (`allow_scheduled: false`
  gated in scheduled mode).
- On any ABORT (e.g. invalid workspace, missing manifest, or unknown repo), a
  valid `generated-artifact` result file is written with the error recorded in
  `errors[]`.

## Phase 1: VALIDATE

1. Missing `workspace_path` → ABORT `"missing required input: workspace_path"`.
2. Missing `CONFIG_DIR/config.yaml` or its top-level `workspace` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. After config validation succeeds, replace `LOGIN` with the authoritative
   `.workspace.login` value from `CONFIG_DIR/config.yaml`.
4. Ensure `*-result.yaml` is present in `CONFIG_DIR/.gitignore`.
5. Missing `MANIFEST` → ABORT `"generated.yaml not found: {MANIFEST}"` (a
   generated-artifact audit with no manifest has nothing to audit; this is a
   workspace setup gap, not a valid empty run).
6. Load `MANIFEST`. When `repo` is given, resolve it against binding `source`
   values and binding ids; build `PREPARED_MANIFEST`, a temporary
   copy whose `bindings` contains only the matching entries. An unresolvable
   `repo` → ABORT `"unknown repo: {repo}"`. Otherwise `PREPARED_MANIFEST` is
   `MANIFEST` unchanged.
7. A malformed `generated.yaml` (missing required keys, empty/duplicate
   `files[].path`) is rejected by `generated_artifacts.validate_manifest` and
   yields a validated ABORT result — never an index crash inside `audit`.

## Phase 2: SNAPSHOT

Collect remote evidence for every binding in `PREPARED_MANIFEST`. For each
binding, fetch the current source repo/branch and resolve the template tree SHA
and every recorded output blob SHA.

**See:** `lib/patterns/generation-manifest.md`,
`lib/pulse/scripts/generated_artifacts.py`

Call `generated_artifacts.collect(PREPARED_MANIFEST)` to produce the snapshot.
A collector failure (non-zero exit, e.g. no network) → append its stderr to
`ERRORS` and continue to Phase 3 with whatever partial snapshot it produced (or
`{}` if it produced none). A collection gap on one binding still lets the audit
engine mark that binding `error` per its own fail-closed rule, rather than
aborting the whole run.

## Phase 3: AUDIT

Classify every binding in `PREPARED_MANIFEST` against the collected snapshot.
This is the pure engine — no network, no git commands, no arithmetic in this
skill:

**See:** `lib/pulse/scripts/generated_artifacts.py`

Call `generated_artifacts.audit` (via `build_result`) and copy the
returned report fields into the envelope: `bindings_audited`, `states`, and
`findings`. The skill does not recompute these values.

## Phase 4: CONFLICT/PROPOSE

All propose decisions live in `generated_artifacts.build_result` (not this
skill and not the driver assembler). For each binding result from the audit
engine:

- `state: current` → no finding, no proposal.
- `state: template-drift` → build a regeneration proposal. Look up the binding's
  `generator` id in the loaded generator registry, verify the generator applies to
  the binding's repository, then call `generator_dispatch.dispatch(...)` to
  produce a `mutation_plan.Proposal`. Route that proposal through
  `pen_orchestrator.execute(...)` with `mutation_policy: propose` only.

  **Scheduled gating:** Under mode: scheduled, a generator whose transformation
  has allow_scheduled: false MUST NOT be dispatched — record the drift as a
  `proposed_action`/finding requiring human approval. Only allow_scheduled: true
  transformations may be dispatched unattended.

  (F10: gating is enforced by threading the transformation registry into
  `dispatch`→`build_proposal`→`validate_proposal`. The driver never executes a
  pen; it persists only the `{binding, transformation, proposal_id}` summary.)

  On success, append the resulting `{binding, transformation, proposal_id}` to
  `PROPOSALS`. On failure (out-of-allowlist path, missing generator, etc.),
  append a typed finding and the error detail without mutating the manifest.

- `state: local-customization` → append a `local_customization` finding
  (`severity: medium`) and no proposal. Local edits must be reviewed by a human.
- `state: conflict` → append a `conflict` finding (`severity: high`) and no
  proposal. The binding has both template drift and local customization.
- `state: error` → the audit engine already produced a finding; copy it and add
  no proposal.

This phase never calls `gh` and never calls `generated_artifacts.advance()` —
proposals are data, not actions. An orchestrator or human decides whether to
run the proposed generator.

## Phase 5: RECORD

Write `RESULT_PATH`:

```yaml
contract_version: 1
kind: generated-artifact
workspace: {LOGIN}
run_at: "{RUN_AT}"                # quote: an unquoted ISO-8601 value parses as a YAML datetime
actor: { gh_login: {gh api user login or unknown}, machine: {hostname}, mode: {MODE} }
bindings_audited: {AUDIT_REPORT.bindings_checked}
states:
  {binding.id}: {binding.state}  # one entry per audited binding
findings: {AUDIT_REPORT.findings}
proposals: {PROPOSALS}
proposed_actions: {PROPOSED_ACTIONS}
errors: {ERRORS}
```

Validate:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind generated-artifact
```

Non-zero exit is a skill bug; report validator stderr verbatim.

Print a one-line log summary:
`generated-artifact-audit: bindings={bindings_audited} drift={bindings_drift} proposals={n}`

## ABORT semantics

Every ABORT above appends the reason to `ERRORS` and falls through to Phase 5
with `bindings_audited: 0`, `states: {}`, `findings: []`, `proposals: []`,
`proposed_actions: []`, `errors: [reason]` — the result file is always written and
validated. If `CONFIG_DIR` is unusable, write to the `result_path` input, else
`generated-artifact-result.yaml` in the current directory, and say so.

## Related

- `lib/pulse/scripts/generated_artifact_run.py` — propose-only CLI driver (F10)
- `lib/pulse/scripts/generated_artifacts.py` — collector + audit engine +
  pure `build_result` (F7 Task 2 / F10 Task 3)
- `lib/pulse/scripts/generator_dispatch.py` — generator adapter dispatch
  (F7 Task 3)
- `lib/pulse/scripts/pen_orchestrator.py` — propose-only F6 pen run driver
- `lib/pulse/scripts/validate_result.py` — result-kind validator
- `lib/patterns/headless-contract.md` § generated-artifact-result.yaml
- `lib/patterns/generation-manifest.md` — binding and state definitions
- `lib/patterns/repository-mutations.md` — mutation policy and scheduled gating
  vocabulary
