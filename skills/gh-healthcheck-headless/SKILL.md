---
name: gh-healthcheck-headless
description: >
  Headless multi-repo governance audit. Validates an F0 fleet-evidence snapshot,
  enriches it with optional GitHub-only governance facts, loads reviewed F1 repository
  profiles, and dispatches each repository to its authoritative scorecard. Writes a
  validated healthcheck-result.yaml and updates the committed healthcheck.yaml record.
  Zero prompts; explicit inputs only. Use when a scheduler or orchestrator needs
  profile-specific repo grades and separate adapter-coverage debt.
---

# Headless Dispatched Fleet Healthcheck

Evaluate each repository against the scorecard selected by its reviewed F1 profile.
Repository grades are scorecard-specific. Fleet-wide adapter coverage is reported
separately and is not a mixed-scorecard fleet grade.

`{PLUGIN_ROOT}` is the directory containing `plugin.json`.

## Inputs and outputs

- `workspace_path` (required): absolute workspace root containing `.hiivmind/github/`.
- `repos` (optional): comma-separated full or short repository names; defaults to
  the reviewed F1 fleet.
- `result_path` (optional): workspace default when usable, otherwise
  `./healthcheck-result.yaml`.
- `update_governance` (optional): update `healthcheck.yaml`; defaults to `true`.
- `mode` (optional): `interactive` or `scheduled`; defaults to `scheduled`.
- Result: validated `healthcheck-result.yaml` with kind `healthcheck`.
- Governance output: updated `.hiivmind/github/healthcheck.yaml` unless disabled.

## Contract

- Zero prompts. Explicit inputs only. Every exit writes a result file.
- Read-only against GitHub; fixes are never applied.
- The skill performs no arithmetic and never edits individual check states. It copies
  deterministic dispatch output into the result and governance record.
- A failure to collect an optional GitHub fact leaves that fact absent, except for the
  explicit incomplete ruleset evidence required in Phase 2. It does not imply a
  failing check. Nave does not provide license metadata, branch protection, or
  rulesets.

## State

Determine `RESULT_PATH` before validating the workspace: explicit `result_path`;
otherwise the workspace default when `workspace_path` is non-empty and usable;
otherwise `./healthcheck-result.yaml` in the current directory. This fallback must be
available for every early ABORT to write and validate its result.

```text
CONFIG_DIR  = {workspace_path}/.hiivmind/github
EVIDENCE    = CONFIG_DIR/fleet-evidence.yaml
PROFILES    = CONFIG_DIR/profiles.yaml
DISMISSALS  = CONFIG_DIR/healthcheck.yaml
RESULT_PATH = {explicit result_path, workspace default, or current-directory fallback}
LOGIN = unknown
RUN_AT      = current UTC timestamp
MODE        = {mode, default scheduled}
ERRORS      = []
```

## Phase 1: VALIDATE + OBTAIN F0 FLEET EVIDENCE

1. Missing `workspace_path` → ABORT `"missing required input: workspace_path"`.
2. Missing `CONFIG_DIR/config.yaml` or its top-level `workspace` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. After config validation succeeds, replace `LOGIN` with the authoritative
   `.workspace.login` value from `CONFIG_DIR/config.yaml`.
4. Ensure `*-result.yaml` is present in `CONFIG_DIR/.gitignore`.
5. If `EVIDENCE` is absent or the caller requests a fresh snapshot, invoke
   `hiivmind-pulse-gh:gh-fleet-evidence-headless` with the same `workspace_path`.
6. Validate before consumption:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_evidence.py" "$EVIDENCE"
```

Validation failure → ABORT and record validator stderr verbatim in `errors`. Retain an
optional `repos` filter for resolution after F1 is loaded.

## Phase 2: ADD OPTIONAL GITHUB-ONLY FACTS + LOAD F1 PROFILES

Require `PROFILES` and load it as the authoritative F1 repository-profile and scorecard
configuration. Missing/invalid profiles → ABORT. Resolve `repos` against F0 full names
and F1 short/full names; unknown entries become errors and are excluded. Preserve
deterministic lexical order.

When `repos` narrows scope, `PREPARED_EVIDENCE` must be a temporary copy whose `repos`
list contains exactly the selected authoritative repositories' available F0 entries,
in lexical order. `PREPARED_PROFILES` must contain exactly the selected
`repository_profiles`; preserve the referenced profile, scorecard, and adapter
definitions unchanged. A selected authoritative repository with no F0 entry remains
absent from `PREPARED_EVIDENCE`; do not synthesize an empty F0 entry. The F3 engine
still evaluates it from its profile as an evidence gap. Filtering both inputs prevents
excluded F0 repositories from becoming unprofiled coverage debt.

Enrich only that same selected repository set, and only entries available in
`PREPARED_EVIDENCE`. Use `gh api` only for facts Nave cannot observe:

```text
repos/{owner}/{repo}                                      -> github.repo
repos/{owner}/{repo}/branches/{default_branch}/protection -> github.protection
repos/{owner}/{repo}/rulesets                             -> ruleset summaries
repos/{owner}/{repo}/rulesets/{ruleset_id}                -> github.rulesets[]
```

`github.repo` supplies GitHub license metadata and `default_branch`. Fetch protection
for that default branch. The ruleset list response does not establish `target` or
`conditions`. After fetching the list, fetch the detail endpoint for every relevant
active ruleset ID in ascending numeric ID order. Store `github.rulesets` as the
deterministic list of hydrated detail objects in that same order; never copy the list
response directly into `github.rulesets`.

If the ruleset list request fails, record `github.rulesets` as an explicit incomplete
evidence mapping rather than an empty list. If an active detail request fails, retain
an explicit incomplete evidence object containing its `id`, `name`, `enforcement`,
and detail error in the deterministic list, but omit `target` and `conditions` even if
the list summary happened to include them. This ensures the adapter returns `unknown`:
a collection failure never establishes a pass or fail. Disabled or evaluating
summaries need not be hydrated because they cannot establish active protection.

Merge successful responses into that repository's `github` namespace in a temporary
copy of the F0 document. Do not fetch root contents,
`.github` contents, labels, workflows, releases, or tags: the F0 projection replaces
manifest fetching. Record an authenticated protection 404 as
`github.protection: null` because it proves protection is absent. Other unavailable
optional facts leave their keys absent so adapters report the evidence gap accurately;
do not synthesize a healthy or unhealthy state.

## Phase 3: DISPATCH + APPLY DISMISSALS

Invoke the F3 engine exactly once over the prepared F0/F1 inputs:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/healthcheck_dispatch.py" \
  --evidence "$PREPARED_EVIDENCE" \
  --profiles "$PREPARED_PROFILES" \
  --workspace "$workspace_path" \
  --dismissals "$DISMISSALS" \
  --as-of "$RUN_AT" > "$DISPATCH_JSON"
```

Omit `--dismissals` when the governance record does not yet exist. Dispatch resolves
each repository's scorecard, evaluates only checks present in that resolved scorecard,
applies matching full-name or short-name dismissals as `not_applicable`, and calls the
centralized scorer. A dismissal with a non-null `review_after` applies only while the
date captured in `RUN_AT` is before that ISO date; on or after it, the check is
re-evaluated normally. The skill must not re-score, add checks, or modify states.

Dispatch failure → ABORT with stderr included in `errors`.

## Phase 4: WRAP + VALIDATE RESULT

Write `RESULT_PATH` by adding common contract fields around the dispatch object. All
result wrapping, including ABORT, must use `LOGIN`. Copy `repos`, `aggregate`, and
`coverage` without transformation:

```yaml
contract_version: 1
kind: healthcheck
workspace: <LOGIN>
run_at: "<RUN_AT>"
actor: { gh_login: <gh api user login or unknown>, machine: <hostname>, mode: <MODE> }
repos: <DISPATCH_JSON.repos>
aggregate: <DISPATCH_JSON.aggregate>
coverage: <DISPATCH_JSON.coverage>
errors: <ERRORS>
```

There is no top-level mixed-scorecard score, total, or grade.

### Overlay scorecards (dogfood)

Some scorecards are **dogfood overlays** — plugin-specific scorecards that extend
the neutral set (e.g. `claude-plugin-v1`, which adds the `claude.plugin_manifest`,
`claude.skills`, and `claude.context` checks) and apply only to repositories whose
reviewed F1 profile opts in (`profile:claude-plugin`). Grades in
`aggregate.by_scorecard` are already scorecard-specific, so an overlay scorecard's
subtotal is presented under its own key exactly like any neutral scorecard and is
**never merged into a neutral scorecard's `score`/`total` denominator or into fleet
`coverage`**. When rendering or grouping this result, mark each overlay scorecard's
subtotal `overlay: true` and keep it in its own block; a repository graded under an
overlay scorecard contributes only to that overlay's subtotal. The overlay scorecard
set is documented in `README.md` § Dogfood overlays; neutral fleet behavior is
provably independent of the overlays (`lib/pulse/scripts/tests/test_dogfood_isolation.py`).

**Content channel (opt-in only).** For each repository whose resolved scorecard
contains a `claude.*` overlay adapter, attach bounded, SHA-pinned file contents
before dispatch — either by invoking the collector
(`lib/pulse/scripts/overlay_content.py` via the injected `gh_api` seam) and writing
`file_contents` onto that repo's F0 entry, or by running dispatch with
`--fetch-overlay-content`. Paths: `.claude-plugin/plugin.json`, `CLAUDE.md`, and
every `skills/*/SKILL.md`. Neutral repo entries must never receive `file_contents`.
Unavailable paths are explicit (`missing` / `too_large` / `fetch_error`); never
omit silently. A SHA resolution failure marks all paths unavailable (check
`unknown`) — never read an unpinned branch.

**Inference step + status (`claude.context`).** For each overlay-opted-in repo,
after content is attached and before dispatch:

1. Read `CLAUDE.md` from that repo's `file_contents`.
2. Extract candidate claims of kinds `stale_command`, `missing_claimed_skill`,
   and `unsupported_evidence` (prose references the deterministic checker does
   not fully model). Feed them as `evidence["inferred_claims"]`.
3. Schema-guard with `repo_claims.validate_inferred_findings` (invalid payload
   → do not invent findings; the adapter will grade `unknown` on validation
   failure).
4. Record `evidence["inference_status"]` as exactly one of:
   - `ran` — inference completed and (possibly empty) candidates were attached
   - `skipped` — inference was not attempted
   - `failed` — inference attempted but aborted (tool error, empty content, etc.)

Only `inference_status: ran` may yield `pass`/`fail` for `claude.context`.
`skipped`, `failed`, or an absent status force `unknown` — never a silent
`pass` over stale docs. Dispatch registers Claude adapters only when at least
one profiled scorecard needs them; content attachment remains the
neutral-preserving boundary.

Validate:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" \
  "$RESULT_PATH" --kind healthcheck
```

Non-zero exit is a skill bug; report validator stderr verbatim.

## Phase 5: UPDATE GOVERNANCE RECORD

Skip when `update_governance: false`. Create from
`templates/healthcheck.yaml.template` when missing.

1. Replace `last_run` with exactly `last_run.run_at`, `last_run.by_scorecard`, and
   `last_run.coverage`, copied respectively from validated `run_at`,
   `aggregate.by_scorecard`, and `coverage`. Never retain legacy `timestamp`, `scope`,
   `score`, `total`, `grade`, `aggregate_score`, `aggregate_total`, or
   `aggregate_grade` fields in `last_run`.
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
