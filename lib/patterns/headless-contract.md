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
| impact | impact-result.yaml | `{workspace_root}/.hiivmind/github/impact-result.yaml` |
| repo-mutation | repo-mutation-result.yaml | `{workspace_root}/.hiivmind/github/repo-mutation-result.yaml` |
| generated-artifact | generated-artifact-result.yaml | `{workspace_root}/.hiivmind/github/generated-artifact-result.yaml` |
| plan-sync | plan-sync-result.yaml | `{workspace_root}/.hiivmind/github/plan-sync-result.yaml` |
| apply-status | apply-status-result.yaml | `{workspace_root}/.hiivmind/github/apply-status-result.yaml` |

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
kind: status | healthcheck | fleet-membership | refresh | workflow-run | impact | repo-mutation | apply-status | generated-artifact | plan-sync
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
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py impact-result.yaml --kind impact
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py repo-mutation-result.yaml --kind repo-mutation
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py generated-artifact-result.yaml --kind generated-artifact
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py plan-sync-result.yaml --kind plan-sync
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py apply-status-result.yaml --kind apply-status

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
    score: <number>                   # finite, non-negative, and <= total
    total: <number>                   # finite, non-negative weighted denominator
    grade: A | B | C | D | F          # required enum
    coverage_supported: <number>      # finite, non-negative, and <= coverage_total
    coverage_total: <number>          # finite non-negative configured check weight
    checks:                           # dict, required: check_id -> result
      <check_id>:
        check_id: <check_id>          # str, required; must match the mapping key
        adapter: <adapter id>         # str, required
        weight: <number>              # finite and non-negative, required
        profile: <profile id>         # optional source profile
        status: pass | warn | fail | unknown | not_applicable | unsupported | error
        detail: <str>                 # required
        data:                         # dict, required
          evidence:                   # mapping, required on every check
            paths: [<str>, ...]
            refs: [<str>, ...]
        inferred: <bool>              # optional — true when LLM judgment produced it
aggregate:                            # dict, required
  by_scorecard:                       # dict, required; no mixed-scorecard fleet grade
    <scorecard id>:
      repos: <int>                    # repositories assigned to this scorecard
      repos_scored: <int>             # non-negative and <= repos
      average_percent: <number|null>  # finite 0..100, or null when unscoreable
coverage:                             # required; fleet adapter-coverage debt
  checks_total: <int>                 # resolved checks across profiled repositories
  checks_supported: <int>             # non-negative, <= checks_total
  unsupported_by_adapter:             # dict, required: adapter -> check count
    <adapter id>: <int>
  unprofiled_repos: [<owner/name>, ...]
  dependencies:                       # optional (F4); present whenever any repo
                                       # selected python.dependencies/node.dependencies/
                                       # fleet.dependencies.coherence — see
                                       # lib/patterns/dependency-coherence.md
    repositories_selected: <int>
    repositories_grouped: <int>
    repositories_ungrouped: <int>     # = repositories_selected - repositories_grouped
    groups_with_insufficient_members: [<group id>, ...]
    packages_matched: <int>
    packages_unmatched: <int>
    unsupported_by_adapter:
      <adapter id>: <int>
errors: []
```

The healthcheck top level and `aggregate` must not contain mixed fleet grade keys:
`score`, `total`, `grade`, `aggregate_score`, `aggregate_total`, or
`aggregate_grade`. Repository score/total/grade fields remain required because each is
paired with its repository's scorecard.

All result numeric fields reject booleans and non-finite values (`NaN` and positive or
negative infinity). Cross-field bounds prevent impossible summaries: repository score
cannot exceed total, supported coverage cannot exceed total coverage, supported check
count cannot exceed total check count, and scored repository count cannot exceed the
scorecard repository count.

`pass`, `warn`, and `fail` enter the weighted score denominator. `unknown`,
`not_applicable`, `unsupported`, and `error` do not. Coverage includes every
configured weight in `coverage_total`; only `unsupported` weight is excluded
from `coverage_supported`, so adapter gaps remain visible without becoming
false repository failures. A current dismissal is emitted as `not_applicable`
with `data.dismissed: true`, copied dismissal metadata, and its source citation;
the durable dismissal decision remains in `healthcheck.yaml`.
Copied dismissal metadata is recursively JSON-normalized; YAML dates and datetimes
become ISO strings before CLI JSON output.

Dismissal `review_after` is an ISO date for re-evaluation, not an inclusive dismissal
end date. The dispatcher compares it with the supplied as-of date: before
`review_after` the dismissal is current; on or after `review_after` the check is
evaluated normally. Null or missing `review_after` keeps the dismissal current. The
headless skill supplies its captured `run_at` as the deterministic as-of input; direct
API/CLI callers that omit it use the current UTC date.

Grades must always be presented with `scorecard`. A grade from one scorecard is
not directly compared with a grade from another scorecard because the checks,
weights, and applicability rules differ.

`aggregate.by_scorecard` averages only repositories with a non-zero scoring
denominator. `coverage` is separate from health: unsupported adapters are explicit
delivery debt and do not become false repository failures.

**F4 `deps-snapshot.json`** is a separate, transient, gitignored, run-scoped
artifact — never part of this `*-result.yaml` contract, never committed. It
carries the per-package fleet-comparison detail (`records`, `groups`,
`findings`, `unresolved`, `repository_evaluations`) behind
`coverage.dependencies`'s summary counters, validated by its own
`validate_dependency_snapshot.py` (not a `validate_result.py` `kind`). See
`lib/patterns/dependency-coherence.md`.

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

### impact-result.yaml (written by the impact audit, F5)

Reports path-scoped integration currency over `repo_dependencies` object
edges (`lib/references/config-schema.md` § depends_on edges). Currency is
`git diff integration_tested_sha..<watch_branch head> -- watch_paths`,
computed deterministically by `impact.py`; only *severity* (breaking vs.
additive) is LLM-judged, as an `inferred: true` finding — inference never
changes an edge's `state`.

```yaml
contract_version: 1
kind: impact
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
edges_checked: <int>                  # required — must equal len(edges)
edges_stale: <int>                    # required — must equal count of edges with state: stale
markers_updated: <int>                # required, non-negative — integration_tested_sha markers rewritten this run
edges:                                 # list, required (may be empty) — one entry per configured object edge
  - dependent: <owner/name>           # str, required — the repo carrying the depends_on entry
    upstream: <owner/name>            # str, required — the repo field of the edge
    watch_branch: <str>               # str, required
    state: current | stale | unknown  # required enum — unknown covers missing/unreachable baseline
    tested_sha: <str or null>         # required key, nullable — the edge's integration_tested_sha
    remote_head: <str or null>        # required key, nullable — resolved watch_branch head, null if unreachable
    changed_paths: [<str>, ...]       # list, required (may be empty) — watch_paths hits between tested_sha and remote_head
findings:                             # list, required (may be empty) — typed data, not prose
  - kind: <str>                       # required, e.g. integration-drift, unconfigured_edge,
                                       #   empty_watch_paths
    repo: <owner/name>                # str, required
    severity: low | medium | high     # required enum
    detail: <str>                     # optional human-readable
    ref: { type: <str>, id: <any>, url: <str> }   # optional locator
    inferred: <bool>                  # optional — true when severity was LLM-judged
proposed_actions: [<str>, ...]        # list, required — tracking issues/dispatches a headless run declined to apply directly
asks_recorded: [<str>, ...]           # list, required — ASKs that had no user
errors: []
```

Duplicate `(dependent, upstream, watch_branch)` identities are rejected —
each configured edge contributes exactly one `edges[]` entry per run.
`edges_checked` and `edges_stale` are reconciled against the `edges` list the
same way healthcheck reconciles repo score/grade against `checks`; a result
cannot forge a stale count that disagrees with its own evidence.

Legacy plain-string `depends_on` entries (pre-F5 shape, no watch metadata)
are not audited for currency — they never produce an `edges[]` entry.
Instead, each one surfaces as an `unconfigured_edge` finding on the
dependent repo (`severity: low`) so unmigrated edges stay visible without
blocking the audit or fabricating a current/stale verdict for data the
edge doesn't carry.

Local working-tree content is never a binding side: both `tested_sha` and
`remote_head` are committed/remote-published refs, never uncommitted state
on the machine running the audit. A missing or unreachable
`integration_tested_sha` (edge points at a SHA the audit cannot resolve)
blocks closed as `state: unknown`, not `current` — an unauditable edge is
never silently treated as safe.

An object edge with an empty or missing `watch_paths[]` is the same kind of
unauditable-by-construction edge: no path evidence can ever mark it stale,
so it blocks closed too — `state: unknown` plus an `empty_watch_paths`
finding (`severity: low`) — rather than defaulting to `current` for lack of
any hits to report.

### repo-mutation-result.yaml (written by the pen orchestrator, F6)

Carries the `PenRunResult` attribution record (`lib/pulse/scripts/pen_orchestrator.py`)
for one repository-file mutation run driven through a Nave pen. See
`lib/patterns/repository-mutations.md` for the mutation-policy vocabulary and
the pen state machine this result is the terminal record of.

```yaml
contract_version: 1
kind: repo-mutation
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
state: proposed | blocked | failed  # required enum — the run's terminal state
proposal_id: <str>                  # required — the mutation_plan.Proposal id
transformation: <str>               # required — registered transformation id
pen_name: <str>                     # required — the Nave pen this run used
selection: [<owner/name>, ...]      # list of str, required — repos targeted
nave_version: <str or null>         # required key, nullable — probed `nave --version`
repo_outcomes:                      # dict, required: owner/name -> outcome
  <owner/name>: ok | failed | blocked
reason: <str or null>               # required key, nullable — non-null when state
                                     #   is blocked or failed
errors: []
```

This orchestrator is propose-only: `state: proposed` is its only terminal
success, meaning a commit/push/PR action is proposed for something else to
apply later, never performed by the run itself. `reason` is required
(non-null) whenever `state` is `blocked` or `failed`, and optional (may be
null) when `state` is `proposed`.

### apply-status-result.yaml (written by apply reconcile loop, F11)

Carries the persisted apply lifecycle status for a proposal branch.

```yaml
contract_version: 1
kind: apply-status
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
state: pushed | pr_opened | applied | rejected  # required enum — apply lifecycle state
proposal_id: <str>                  # required — the proposal id
selection: [<owner/name>, ...]      # list of str, required — targeted repos
branch: <str>                       # required — branch name (pulse/apply/{proposal_id})
pushed_sha: <str or null>           # required key, nullable — branch head SHA (required for pushed/pr_opened/applied)
pr_url: <str or null>               # required key, nullable — pull request URL (required for pr_opened/applied)
merged_sha: <str or null>           # required key, nullable — merge commit SHA (required for applied)
reason: <str or null>               # required key, nullable — rejection reason (required for rejected)
errors: []
```

Lifecycle states and required fields:
- `pushed`: branch pushed to remote, no PR open yet. Requires `pushed_sha`. `pr_url` and `merged_sha` are null.
- `pr_opened`: pull request created. Requires `pushed_sha` and `pr_url`. `merged_sha` is null.
- `applied`: PR merged into default branch. Requires `pushed_sha`, `pr_url`, and `merged_sha`.
- `rejected`: PR closed unmerged. Requires `reason` (non-null). `merged_sha` is null.

### generated-artifact-result.yaml (written by the generation audit, F7)


Reports the drift state of committed generated-artifact bindings
(`templates/generated.yaml.template`). For each binding the audit compares the
source template tree SHA, the target file blobs recorded at generation time,
and the current state of the target repository. The manifest format and audit
rules are documented in `lib/patterns/generation-manifest.md`; this section only
covers the result shape.

```yaml
contract_version: 1
kind: generated-artifact
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
bindings_audited: <int>                # required, non-negative — total bindings audited
states:                                # required: binding id -> state
  <binding id>: current | template-drift | local-customization | conflict | error
findings:                              # list, required (may be empty) — typed data
  - kind: <str>                        # required, e.g. template-drift, local-customization,
                                       #   conflict, unresolvable_source
    repo: <owner/name>                 # str, required — target repository
    severity: low | medium | high        # required enum
    detail: <str>                      # optional human-readable
    ref: { type: <str>, id: <any>, url: <str> }   # optional locator
    inferred: <bool>                  # optional — true when LLM judgment produced it
proposals:                             # list, required (may be empty)
  - binding: <binding id>              # str, required — binding in template-drift state
    transformation: <generator id>     # str, required — registered generator to re-run
    proposal_id: <str>                 # str, required — stable proposal identifier
proposed_actions: [<str>, ...]        # list, required (may be empty) — withheld mutations, e.g. scheduled-gated regenerations awaiting human approval
errors: []
```

`states` keys must be strings and values must be one of the five allowed
states. `proposals` are emitted only for `template-drift` bindings, because only
template drift can be resolved by re-running a registered generator. Findings
for `local-customization`, `conflict`, and `error` states are surfaced without a
proposal.

### plan-sync-result.yaml (written by the plan synchronization audit, F8)

Reports one generic plan synchronization run. It records counts, typed findings,
and the deferred proposals/actions needed to perform reconciliation; the audit
itself remains propose-only.

```yaml
contract_version: 1
kind: plan-sync
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
docs_scanned: <int>                   # required, non-negative
in_sync: <int>                        # required, non-negative
doc_patches: <int>                    # required, non-negative
github_patches: <int>                 # required, non-negative
conflicts: <int>                      # required, non-negative
excluded: <int>                       # required, non-negative
findings:                             # list, required (may be empty)
  - kind: dirty_doc | local_ahead | rename_detected | base_conflict | <str>
    repo: <owner/name>                # str, required
    severity: low | medium | high     # required enum
    detail: <str>                     # optional
    ref: { type: <str>, id: <any>, url: <str> }   # optional locator
    inferred: <bool>                  # optional
proposals:                            # list, required (may be empty)
  - binding: <binding id>             # str, required
    transformation: plan-sync-doc-patch # str, required
    proposal_id: <str>                # str, required
proposed_actions: [<str>, ...]        # list, required (may be empty)
errors: []
```

## Related patterns

- `workspace-detection.md` — workspace root, multi-machine topology, D4
- `hiivmind-corpus/lib/corpus/patterns/headless-contract.md` — the ported original
