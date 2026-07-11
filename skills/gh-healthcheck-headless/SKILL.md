---
name: gh-healthcheck-headless
description: >
  Headless multi-repo governance audit. Fetches per-repo API data, evaluates the 11-check catalog
  deterministically via evaluate_checks.py honoring team dismissals, writes healthcheck-result.yaml
  (kind: healthcheck) and updates the committed healthcheck.yaml governance record. Zero prompts;
  explicit inputs only. Use when: a scheduled fleet audit runs, an orchestrator needs repo grades.
  Trigger phrases: "headless healthcheck", "fleet healthcheck", "scheduled governance audit".
inputs:
  workspace_path: "required — absolute path to the workspace root (directory containing .hiivmind/github/)"
  repos: "optional — comma-separated repo filter (full owner/name or short names); default: every entry in the config repositories[] catalog"
  result_path: "optional — where to write the result (default: {workspace_path}/.hiivmind/github/healthcheck-result.yaml)"
  update_governance: "optional — also update the committed healthcheck.yaml (default: true)"
  mode: "optional — actor mode recorded in the result: interactive | scheduled (default: scheduled)"
outputs:
  result_file: "healthcheck-result.yaml conforming to lib/patterns/headless-contract.md (kind: healthcheck)"
  governance: "updated {workspace_path}/.hiivmind/github/healthcheck.yaml (unless update_governance: false)"
author: hiivmind
---

# Headless Fleet Healthcheck

The 11-check governance catalog (`lib/references/healthcheck-checks.md`) evaluated per repo,
deterministically, with dismissals honored. Read-only against GitHub — fixes are never applied.

## Path Convention

`{PLUGIN_ROOT}` = plugin root (where plugin.json lives).

## Contract

- **Zero prompts. Explicit inputs only (D4). Every exit writes a result file.**
- A repo that fails to evaluate does not abort the run: record an `errors[]` entry and
  continue with the remaining repos (partial fleets are valid results).

## State

```
computed:
  CONFIG_DIR   = {workspace_path}/.hiivmind/github
  RESULT_PATH  = {result_path input, or CONFIG_DIR/healthcheck-result.yaml}
  RUN_AT       = $(date -u +%Y-%m-%dT%H:%M:%SZ)
  LOGIN        = yq -r '.workspace.login' CONFIG_DIR/config.yaml
  GH_LOGIN     = $(gh api user --jq .login)   ("unknown" on failure, + errors[] entry)
  MACHINE      = $(hostname -s)
  MODE         = {mode input, default "scheduled"}
  REPOS        = resolved full_name list (Phase 1)
  REPO_RESULTS = []   (per-repo JSON blocks from evaluate_checks.py)
  ERRORS       = []
```

## Phase 1: VALIDATE + SCOPE

**Outputs:** REPOS.

1. `workspace_path` missing → ABORT `"missing required input: workspace_path"`.
2. `CONFIG_DIR/config.yaml` missing or lacking a top-level `workspace:` key →
   ABORT `"not a workspace root: {workspace_path}"`.
3. `gh` unavailable → ABORT `"gh CLI not found"`.
4. Catalog:

```bash
yq -r '.repositories[].full_name' "${CONFIG_DIR}/config.yaml"
```

   Empty catalog and no `repos` input → ABORT `"repositories catalog is empty"`.
5. If `repos` input given: match each entry against catalog `full_name` or `name`;
   entries with no catalog match are still evaluated if they look like `owner/name`
   (API-only repos are legitimate — see spec Part 9), otherwise append
   `"unknown repo: {entry}"` to ERRORS and drop it. REPOS = the resolved full names.
6. Verify gitignore coverage: append `*-result.yaml` to `CONFIG_DIR/.gitignore` if missing.

## Phase 2: EVALUATE (per repo)

**Outputs:** REPO_RESULTS.

For each `FULL` (owner/name) in REPOS:

1. Fetch API data into a fresh temp dir (404s are expected for some endpoints —
   a missing file is how evaluate_checks.py learns the resource is absent):

```bash
DATA_DIR=$(mktemp -d)
fetch() { gh api "$1" > "$DATA_DIR/$2" 2>/dev/null || rm -f "$DATA_DIR/$2"; }

fetch "repos/${FULL}" repo.json
DEFAULT_BRANCH=$(jq -r '.default_branch // "main"' "$DATA_DIR/repo.json" 2>/dev/null || echo main)
fetch "repos/${FULL}/branches/${DEFAULT_BRANCH}/protection" protection.json
fetch "repos/${FULL}/rulesets" rulesets.json
fetch "repos/${FULL}/labels?per_page=100" labels.json
fetch "repos/${FULL}/actions/workflows" workflows.json
fetch "repos/${FULL}/releases?per_page=30" releases.json
fetch "repos/${FULL}/tags?per_page=30" tags.json
fetch "repos/${FULL}/contents/" root-contents.json
fetch "repos/${FULL}/contents/.github" github-contents.json
```

   If `repo.json` is missing after the fetch (repo inaccessible), append
   `"{FULL}: repo metadata unavailable"` to ERRORS and continue to the next repo.

2. Evaluate deterministically:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/evaluate_checks.py" \
  --repo "$FULL" --data-dir "$DATA_DIR" \
  --relationships "${CONFIG_DIR}/relationships.yaml" \
  --dismissals "${CONFIG_DIR}/healthcheck.yaml"
```

   Append the printed JSON object to REPO_RESULTS. Non-zero exit → append
   `"{FULL}: evaluate_checks failed"` to ERRORS, continue.

3. Space repos out (fleet politeness): no parallel fetching; sequential per repo.

## Phase 3: AGGREGATE + WRITE RESULT

**Outputs:** RESULT_PATH written and validated.

1. Aggregate: `score` = sum of repo scores, `total` = sum of repo totals, `grade` from
   score/total fraction — A ≥ 0.90, B ≥ 0.72, C ≥ 0.54, D ≥ 0.36, F below (same table
   evaluate_checks.py uses; total 0 → F).
2. Write RESULT_PATH:

```yaml
contract_version: 1
kind: healthcheck
workspace: {LOGIN}
run_at: {RUN_AT}
actor: { gh_login: {GH_LOGIN}, machine: {MACHINE}, mode: {MODE} }
repos: {REPO_RESULTS}          # each: {repo, score, total, grade, checks}
aggregate: { score: {sum}, total: {sum}, grade: {computed} }
errors: {ERRORS}
```

3. Validate:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind healthcheck
```

   Exit ≠ 0 → skill bug; report validator stderr verbatim.

## Phase 4: UPDATE GOVERNANCE RECORD

**Outputs:** updated `CONFIG_DIR/healthcheck.yaml` (skip entirely if `update_governance: false`).

1. Create from `{PLUGIN_ROOT}/templates/healthcheck.yaml.template` if missing.
2. Set `last_run`: `timestamp: RUN_AT`, `scope:` comma-joined short names (or `fleet`
   when the whole catalog ran), `aggregate_score / aggregate_total / aggregate_grade`.
3. For each repo result, write `repos.{short-name}` (short name = part after `/`):
   `score`, `total`, `grade`, and each check with `status`, `detail`, `data`, plus
   `last_evaluated: RUN_AT` (the governance record keeps timestamps; the result file
   does not need them).
4. **Preserve `dismissals:` untouched** — merge, never overwrite. Repos not evaluated
   this run keep their existing blocks.
5. Do NOT commit or push — the orchestrator (P5) owns the commit/PR step.

## ABORT semantics

On ABORT: write RESULT_PATH with `repos: []`, `aggregate: {score: 0, total: 0, grade: F}`,
`errors: [<reason>, ...]`, all common fields populated; validate; stop. Fallback write
locations as in gh-status-headless.

## Related

- `lib/patterns/headless-contract.md` — schema
- `lib/references/healthcheck-checks.md` — the catalog evaluate_checks.py implements
- `skills/gh-healthcheck/` — the interactive sibling (fix/dismiss flows live there)
