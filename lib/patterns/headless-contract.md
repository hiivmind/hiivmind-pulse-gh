# Pattern: Headless Result Contract

Headless skills communicate with orchestrators through **result files written
to disk**, not by prose parsing. A printed `---headless-result` block is
retained for human-readable logs only — orchestrators MUST read the file.

## File locations

| Kind | File | Default path |
|------|------|--------------|
| status | status-result.yaml | `{workspace_root}/.hiivmind/github/status-result.yaml` |
| healthcheck | healthcheck-result.yaml | `{workspace_root}/.hiivmind/github/healthcheck-result.yaml` |
| fleet-membership | fleet-membership-result.yaml | `{workspace_root}/.hiivmind/github/fleet-membership-result.yaml` |
| refresh | refresh-result.yaml | `{workspace_root}/.hiivmind/github/refresh-result.yaml` |
| workflow-run | workflow-run-result.yaml | `{workspace_root}/.hiivmind/github/workflow-run-result.yaml` |

Result files are per-machine transient run artifacts (never authority — see
`workspace-detection.md` § Multi-machine topology). The workspace repo's
`.gitignore` covers them via `*-result.yaml`; skills MUST verify that line
exists before writing (append if missing). Orchestrators treat a file as
consumed after parsing; a subsequent run overwrites it.

## Versioning

`contract_version` is a required integer. Current version: **1**. Consumers
MUST reject versions they don't support (`validate_result.py` does). Additive
optional fields do not bump the version; renamed/removed/retyped fields do.
New kinds are backward-compatible: consumers reject only unknown versions,
not kinds they were not asked to validate.

## Common required fields (all kinds)

```yaml
contract_version: 1                   # int, required
kind: status | healthcheck | fleet-membership | refresh | workflow-run
workspace: <login>                    # str, required — org/user login
run_at: <ISO 8601 timestamp>          # str, required
actor:                                # required on ALL kinds (I4)
  gh_login: <gh auth identity>        # str, required
  machine: <hostname or alias>        # str, required
  mode: interactive | scheduled       # required enum
errors: [<str>, ...]                  # list, required (may be empty)
```

The `actor:` block exists because the team is M:M across humans, GitHub
profiles, and machines: identity-sensitive logic resolves against the
*recorded* actor, never against whatever profile the reading machine holds.

## Validation

    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py status-result.yaml --kind status
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py healthcheck-result.yaml --kind healthcheck
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py fleet-membership-result.yaml --kind fleet-membership
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py refresh-result.yaml --kind refresh
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py workflow-run-result.yaml --kind workflow-run

Orchestrators validate before consuming and treat exit 1/2 as a failed run
(report, do not commit). Exit codes: 0 valid, 1 invalid (errors on stderr),
2 file missing/unparseable.

Skills write the file **even on partial failure or early abort**: a missing
result file is indistinguishable from a crashed run.

## Schemas

### status-result.yaml (written by gh-status-headless, P3.1)

```yaml
contract_version: 1
kind: status
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
sections:                             # list, required (may be empty)
  - id: <freshness section id>        # str, required (workspace, projects, ...)
    stale: <bool>                     # required
    last_checked: <ISO 8601 or null>  # required key, nullable
rate_limit_remaining: <int or null>   # required key, nullable
refresh_needed: <bool>                # required — any section stale
errors: []
```

### healthcheck-result.yaml (written by gh-healthcheck-headless, P3.2)

Per-check shape mirrors the committed `healthcheck.yaml` so the transient
result and the governance record stay structurally aligned.

```yaml
contract_version: 1
kind: healthcheck
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
repos:                                # list, required (may be empty)
  - repo: <owner/name>                # str, required
    scorecard: <scorecard id>         # str, required — grades are scorecard-specific
    score: <number>                   # int or float, required
    total: <number>                   # required — weighted score denominator
    grade: A | B | C | D | F          # required enum
    coverage_supported: <number>      # adapter-supported weight, including not-applicable checks
    coverage_total: <number>          # all configured check weight
    checks:                           # dict, required: check_id -> result
      <check_id>:
        check_id: <check_id>          # str, required; must match the mapping key
        adapter: <adapter id>         # str, required
        weight: <number>              # non-negative, required
        profile: <profile id>         # optional source profile
        status: pass | warn | fail | unknown | not_applicable | unsupported | error
        detail: <str>                 # required
        data: {}                      # dict, required (may be empty)
        inferred: <bool>              # optional — true when LLM judgment produced it
aggregate:                            # dict, required
  by_scorecard:                       # dict, required; no mixed-scorecard fleet grade
    <scorecard id>:
      repos: <int>                    # repositories assigned to this scorecard
      repos_scored: <int>             # repositories with a non-zero denominator
      average_percent: <number|null>  # null when no repository was scoreable
coverage:                             # required; fleet adapter-coverage debt
  checks_total: <int>                 # resolved checks across profiled repositories
  checks_supported: <int>             # checks not in unsupported state
  unsupported_by_adapter:             # dict, required: adapter -> check count
    <adapter id>: <int>
  unprofiled_repos: [<owner/name>, ...]
errors: []
```

`pass`, `warn`, and `fail` enter the weighted score denominator. `unknown`,
`not_applicable`, `unsupported`, and `error` do not. Coverage includes every
configured weight in `coverage_total`; only `unsupported` weight is excluded
from `coverage_supported`, so adapter gaps remain visible without becoming
false repository failures. A current dismissal is emitted as `not_applicable`
with `data.dismissed: true`, copied dismissal metadata, and its source citation;
the durable dismissal decision remains in `healthcheck.yaml`.

Grades must always be presented with `scorecard`. A grade from one scorecard is
not directly compared with a grade from another scorecard because the checks,
weights, and applicability rules differ.

`aggregate.by_scorecard` averages only repositories with a non-zero scoring
denominator. `coverage` is separate from health: unsupported adapters are explicit
delivery debt and do not become false repository failures.

### fleet-membership-result.yaml (written by gh-fleet-membership-headless, F2)

```yaml
contract_version: 1
kind: fleet-membership
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
org_repos: [<owner/name>, ...]        # live repositories included by discovery policy
catalog_repos: [<owner/name>, ...]    # repositories present after any catalog patch
catalog_updated: <bool>               # true only when apply_catalog changed config.yaml
profile_proposals:                    # non-authoritative, evidence-backed suggestions
  - repo: <owner/name>
    candidates:
      - profile: <profile id>
        confidence: <0..1>
        evidence: [<observed fact>, ...]
        rule_ids: [<proposal rule id>, ...]
    evidence: {}                      # normalized evidence summary used for proposal
    explanation: <str>                # optional inferred prose; cannot alter candidates
    inferred: true                    # required when explanation is inferred
findings:
  - kind: <str>
    repo: <owner/name>
    severity: low | medium | high
    detail: <str>
proposed_actions: []                  # catalog/profile changes requiring a PR or confirmation
asks_recorded: []                     # profile confirmations deferred by headless execution
errors: []
```

Catalog registration and profile confirmation are separate operations. A
membership result may record both, but `catalog_updated: true` means only stable
repository facts were written to `config.yaml`; it never means profiles or
profile-dependent onboarding actions were applied.

### refresh-result.yaml (written by gh-refresh-headless, P3.3)

```yaml
contract_version: 1
kind: refresh
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
sections:                             # list, required (may be empty)
  - id: <freshness section id>        # str, required
    status: refreshed | skipped | failed   # required enum
config_updated: <bool>                # required — any catalog changed on disk
errors: []
```

### workflow-run-result.yaml (written by the executor in headless mode, P4.3)

```yaml
contract_version: 1
kind: workflow-run
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
workflow: <workflow name>             # str, required
repos: [<owner/name>, ...]            # list of str, required (may be empty)
run_id: <{date}-{gh_login}-{n}>       # str, required — actor-embedded, collision-free
outcome: success | failure | skipped-cooldown | aborted    # required enum
findings:                             # list, required (may be empty) — typed data, not prose
  - kind: <str>                       # required, e.g. ci-failure
    repo: <owner/name>                # str, required
    severity: low | medium | high     # required enum
    detail: <str>                     # optional human-readable
    ref: { type: <str>, id: <any>, url: <str> }   # optional locator
    classification: <str>             # optional INFER output
    inferred: <bool>                  # optional — LLM judgment flagged as such
proposed_actions: [<str>, ...]        # list, required — mutations a headless run declined
asks_recorded: [<str>, ...]           # list, required — ASKs that had no user
errors: []
```

`inferred: true`, `proposed_actions`, and `asks_recorded` are the items
needing human judgment — orchestrators surface them under a "Needs attention"
heading (P5.4) instead of burying them in logs.

## Related patterns

- `workspace-detection.md` — workspace root, multi-machine topology, D4
- `hiivmind-corpus/lib/corpus/patterns/headless-contract.md` — the ported original
