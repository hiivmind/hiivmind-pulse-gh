---
name: gh-healthcheck-headless
description: >
  Headless multi-repo governance audit. Validates an F0 fleet-evidence snapshot,
  enriches it with optional GitHub-only governance facts, loads reviewed F1 repository
  profiles, and dispatches each repository to its authoritative scorecard. Writes a
  validated healthcheck-result.yaml and updates the committed healthcheck.yaml record.
  Zero prompts; explicit inputs only. Use when a scheduler or orchestrator needs
  profile-specific repo grades and separate adapter-coverage debt.
inputs:
  workspace_path: "required — absolute workspace root containing .hiivmind/github/"
  repos: "optional — comma-separated full or short repository names; default: reviewed F1 fleet"
  result_path: "optional — default: {workspace_path}/.hiivmind/github/healthcheck-result.yaml"
  update_governance: "optional — update healthcheck.yaml (default: true)"
  mode: "optional — interactive | scheduled (default: scheduled)"
outputs:
  result_file: "validated healthcheck-result.yaml (kind: healthcheck)"
  governance: "updated .hiivmind/github/healthcheck.yaml unless disabled"
author: hiivmind
---

# Headless Dispatched Fleet Healthcheck

Evaluate each repository against the scorecard selected by its reviewed F1 profile.
Repository grades are scorecard-specific. Fleet-wide adapter coverage is reported
separately and is not a mixed-scorecard fleet grade.

`{PLUGIN_ROOT}` is the directory containing `plugin.json`.

## Contract

- Zero prompts. Explicit inputs only. Every exit writes a result file.
- Read-only against GitHub; fixes are never applied.
- The skill performs no arithmetic and never edits individual check states. It copies
  deterministic dispatch output into the result and governance record.
- A failure to collect an optional GitHub fact leaves that fact absent. It does not
  imply a failing check. Nave does not provide license metadata, branch protection,
  or rulesets.

## State

```text
CONFIG_DIR  = {workspace_path}/.hiivmind/github
EVIDENCE    = CONFIG_DIR/fleet-evidence.yaml
PROFILES    = CONFIG_DIR/profiles.yaml
DISMISSALS  = CONFIG_DIR/healthcheck.yaml
RESULT_PATH = {result_path, or CONFIG_DIR/healthcheck-result.yaml}
RUN_AT      = current UTC timestamp
MODE        = {mode, default scheduled}
ERRORS      = []
```

## Phase 1: VALIDATE + OBTAIN F0 FLEET EVIDENCE

1. Missing `workspace_path` → ABORT `"missing required input: workspace_path"`.
2. Missing `CONFIG_DIR/config.yaml` or its top-level `workspace` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. Ensure `*-result.yaml` is present in `CONFIG_DIR/.gitignore`.
4. If `EVIDENCE` is absent or the caller requests a fresh snapshot, invoke
   `hiivmind-pulse-gh:gh-fleet-evidence-headless` with the same `workspace_path`.
5. Validate before consumption:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_evidence.py" "$EVIDENCE"
```

Validation failure → ABORT and record validator stderr verbatim in `errors`. Retain an
optional `repos` filter for resolution after F1 is loaded.

## Phase 2: ADD OPTIONAL GITHUB-ONLY FACTS + LOAD F1 PROFILES

For each in-scope F0 repository, use `gh api` only for facts Nave cannot observe:

```text
repos/{owner}/{repo}                                      -> github.repo
repos/{owner}/{repo}/branches/{default_branch}/protection -> github.protection
repos/{owner}/{repo}/rulesets                             -> github.rulesets
```

`github.repo` supplies GitHub license metadata and `default_branch`. Fetch protection
for that default branch. Merge successful responses into that repository's `github`
namespace in a temporary copy of the F0 document. Do not fetch root contents,
`.github` contents, labels, workflows, releases, or tags: the F0 projection replaces
manifest fetching. Record an authenticated protection 404 as
`github.protection: null` because it proves protection is absent. Other unavailable
optional facts leave their keys absent so adapters report the evidence gap accurately;
do not synthesize a healthy or unhealthy state.

Require `PROFILES` and load it as the authoritative F1 repository-profile and scorecard
configuration. Missing/invalid profiles → ABORT. Resolve `repos` against F0 full names
and F1 short/full names; unknown entries become errors and are excluded. Preserve
deterministic lexical order. If scope is narrowed, create a temporary profiles document
containing only matching `repository_profiles`; preserve the referenced profile,
scorecard, and adapter definitions unchanged.

## Phase 3: DISPATCH + APPLY DISMISSALS

Invoke the F3 engine exactly once over the prepared F0/F1 inputs:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/healthcheck_dispatch.py" \
  --evidence "$PREPARED_EVIDENCE" \
  --profiles "$PREPARED_PROFILES" \
  --workspace "$workspace_path" \
  --dismissals "$DISMISSALS" > "$DISPATCH_JSON"
```

Omit `--dismissals` when the governance record does not yet exist. Dispatch resolves
each repository's scorecard, evaluates only checks present in that resolved scorecard,
applies matching full-name or short-name dismissals as `not_applicable`, and calls the
centralized scorer. The skill must not re-score, add checks, or modify states.

Dispatch failure → ABORT with stderr included in `errors`.

## Phase 4: WRAP + VALIDATE RESULT

Write `RESULT_PATH` by adding common contract fields around the dispatch object. Copy
`repos`, `aggregate`, and `coverage` without transformation:

```yaml
contract_version: 1
kind: healthcheck
workspace: <config workspace login>
run_at: "<RUN_AT>"
actor: { gh_login: <gh api user login or unknown>, machine: <hostname>, mode: <MODE> }
repos: <DISPATCH_JSON.repos>
aggregate: <DISPATCH_JSON.aggregate>
coverage: <DISPATCH_JSON.coverage>
errors: <ERRORS>
```

There is no top-level mixed-scorecard score, total, or grade. Validate:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" \
  "$RESULT_PATH" --kind healthcheck
```

Non-zero exit is a skill bug; report validator stderr verbatim.

## Phase 5: UPDATE GOVERNANCE RECORD

Skip when `update_governance: false`. Create from
`templates/healthcheck.yaml.template` when missing.

1. Copy `run_at`, `aggregate.by_scorecard`, and `coverage` from the validated result
   into `last_run`; do not calculate replacements.
2. For each repo result, copy `scorecard`, `score`, `total`, `grade`,
   `coverage_supported`, `coverage_total`, and every emitted check block into the
   matching `repos.{short-name}` entry. Copy the result's `run_at` value to
   `last_evaluated` in the durable repo/check record.
3. Preserve `dismissals` and repositories outside this run untouched. Merge; never
   overwrite governance decisions.
4. Do not commit or push; the orchestrator owns that mutation.

## ABORT Semantics

Write common fields plus these already-defined empty engine values, validate, and stop:

```yaml
repos: []
aggregate: { by_scorecard: {} }
coverage:
  checks_total: 0
  checks_supported: 0
  unsupported_by_adapter: {}
  unprofiled_repos: []
errors: [<reason>, ...]
```

## Related

- `lib/patterns/nave-evidence-contract.md` — F0 evidence
- `lib/patterns/repository-profiles.md` — F1 profiles and scorecards
- `lib/patterns/headless-contract.md` — result schema
- `lib/pulse/scripts/healthcheck_dispatch.py` — deterministic F3 dispatch/scoring
