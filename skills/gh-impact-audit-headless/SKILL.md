---
name: gh-impact-audit-headless
description: >
  Headless path-scoped integration-currency audit over repo_dependencies object edges
  (F5). Collects remote branch-head and diff evidence, classifies every configured
  edge as current/stale/unknown, and records tracking-issue and integration-workflow
  dispatch proposals for stale bindings. Writes a validated impact-result.yaml. Zero
  prompts; explicit inputs only. Never advances integration_tested_sha markers itself
  — that only happens from confirmed workflow-run evidence (F5 follow-on). Use when a
  scheduler audits binding currency, or a release gate needs binding_edges_current
  evidence.
---

# Headless Impact Audit

Audit whether each dependent repository's pinned `integration_tested_sha` is still
current against its upstream's watched branch and paths. Currency is computed purely
from remote evidence — never from local working-tree content — and severity beyond the
deterministic current/stale/unknown verdict is out of scope: this skill records facts
and proposals, it never mutates `relationships.yaml` or GitHub.

`{PLUGIN_ROOT}` is the directory containing `plugin.json`.

## Inputs and outputs

- `workspace_path` (required): absolute workspace root containing `.hiivmind/github/`.
- `repo` (optional): a dependent repo's full or short name; narrows the audit to that
  repo's `repo_dependencies` entry. Defaults to every configured dependent.
- `result_path` (optional): workspace default when usable, otherwise
  `./impact-result.yaml`.
- `mode` (optional): `interactive` or `scheduled`; defaults to `scheduled`.
- Result: validated `impact-result.yaml` with kind `impact`
  (`lib/patterns/headless-contract.md` § impact-result.yaml).

## Contract

- Zero prompts. Explicit inputs only. Every exit writes a result file.
- Read-only against GitHub and against `relationships.yaml`: this skill never writes
  `integration_tested_sha` markers (`impact.py::mark`) and never opens issues or
  dispatches workflows. Stale bindings become `proposed_actions` entries — typed
  strings an orchestrator or human reviews before acting.
- **A successful integration-workflow dispatch proposal, even if a human or automation
  later runs it, does not by itself advance any marker.** Markers only ever move from
  confirmed workflow-run evidence consumed by a later run (F5 follow-on work) — this
  skill's dispatch proposal is a suggestion, not evidence of a passing run.
- Missing or unreachable baselines block closed: an edge whose `integration_tested_sha`
  cannot be resolved on the remote is `state: unknown`, never `current`. This mirrors
  `impact.py`'s own binding rule; the skill performs no arithmetic of its own here — it
  copies the audit engine's verdict into the result unchanged.
- Severity on any finding this skill adds is deterministic, `inferred: false`. No LLM
  judgment pass runs here.

## State

Determine `RESULT_PATH` before validating the workspace: explicit `result_path`;
otherwise the workspace default when `workspace_path` is non-empty and usable;
otherwise `./impact-result.yaml` in the current directory. This fallback must be
available for every early ABORT to write and validate its result.

```text
CONFIG_DIR      = {workspace_path}/.hiivmind/github
RELATIONSHIPS   = CONFIG_DIR/relationships.yaml
RESULT_PATH     = {explicit result_path, workspace default, or current-directory fallback}
LOGIN           = unknown
RUN_AT          = current UTC timestamp
MODE            = {mode, default scheduled}
ERRORS          = []
PROPOSED_ACTIONS = []
```

## Phase 1: VALIDATE

1. Missing `workspace_path` → ABORT `"missing required input: workspace_path"`.
2. Missing `CONFIG_DIR/config.yaml` or its top-level `workspace` → ABORT
   `"not a workspace root: {workspace_path}"`.
3. After config validation succeeds, replace `LOGIN` with the authoritative
   `.workspace.login` value from `CONFIG_DIR/config.yaml`.
4. Ensure `*-result.yaml` is present in `CONFIG_DIR/.gitignore`.
5. Missing `RELATIONSHIPS` → ABORT `"relationships.yaml not found: {RELATIONSHIPS}"`
   (an impact audit with no dependency config has nothing to audit; this is a workspace
   setup gap, not a valid empty run).
6. Load `RELATIONSHIPS`. When `repo` is given, resolve it against
   `repo_dependencies` full/short names and build `PREPARED_RELATIONSHIPS`, a temporary
   copy whose `repo_dependencies` contains exactly that one entry. An unresolvable
   `repo` → ABORT `"unknown repo: {repo}"`. Otherwise `PREPARED_RELATIONSHIPS` is
   `RELATIONSHIPS` unchanged.

## Phase 2: SNAPSHOT

Collect remote branch-head and changed-path evidence for every watched object
`depends_on` edge in `PREPARED_RELATIONSHIPS`. Legacy string edges carry no watch
metadata and contribute no snapshot entries — they surface later as
`unconfigured_edge` findings, not audit failures.

When `CONFIG_DIR/poll-state.yaml` exists and its `.state.branch_heads` section is
non-empty (`lib/pulse/scripts/poll.py`'s `branch_heads` trigger — `{repo: {branch:
head_sha}}`), extract just that section — not the whole poll-state file — write it to
`$KNOWN_HEADS_PATH`, and pass it as `--known-heads` to save a redundant `git ls-remote`
round trip. `impact_snapshot.py --known-heads` parses YAML or JSON (`yaml.safe_load`
accepts both), so `.state.branch_heads` can be extracted and written as either — no
reserialization required. Skipping `ls-remote` never substitutes for the diff evidence
itself or for the diff endpoint: the collector always fetches the branch fresh and
resolves the actual current head from that fetch, so a stale `branch_heads` entry
cannot under-report staleness — it only saves the redundant head-resolution round trip.

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/impact_snapshot.py" \
  --relationships "$PREPARED_RELATIONSHIPS_PATH" \
  [--known-heads "$KNOWN_HEADS_PATH"] > "$SNAPSHOT_JSON"
```

A collector failure (non-zero exit, e.g. no network) → append its stderr to `ERRORS`
and continue to Phase 3 with whatever partial snapshot it produced (or `{}` if it
produced none) — a collection gap on one edge still lets the audit engine mark that
edge `unknown` per its own fail-closed rule, rather than aborting the whole run.

## Phase 3: AUDIT

Classify every configured edge from the collected snapshot. This is the pure engine —
no network, no git commands, no arithmetic in this skill:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/impact.py" audit \
  --relationships "$PREPARED_RELATIONSHIPS_PATH" \
  --snapshot "$SNAPSHOT_JSON" > "$AUDIT_JSON"
```

`$AUDIT_JSON` carries `edges_checked`, `edges_stale`, `edges[]`, and `findings[]`
verbatim into the result — copy, do not recompute.

## Phase 4: PROPOSE ISSUE/DISPATCH

For every edge in `$AUDIT_JSON.edges` with `state: stale`:

1. Append a tracking-issue proposal to `PROPOSED_ACTIONS`:
   `"open tracking issue on {dependent}: {upstream}@{watch_branch} changed "
   "{changed_paths} since {tested_sha} (binding stale)"`.
2. Look up that edge's `depends_on[]` entry in `PREPARED_RELATIONSHIPS`
   (`repo_dependencies.{dependent}.depends_on[]` matching `repo: {upstream}`). If it
   carries `integration_workflow`, append a second proposal:
   `"dispatch {integration_workflow} on {dependent} to re-verify against "
   "{upstream}@{remote_head}"`. No `integration_workflow` configured → no dispatch
   proposal; the tracking issue alone stands.

For every `unconfigured_edge` finding in `$AUDIT_JSON.findings`, append a migration
proposal: `"migrate legacy depends_on edge on {repo} to the object edge shape "
"(lib/references/config-schema.md § depends_on edges) so impact audit can track it"`.

This phase never calls `gh` and never invokes `impact.py mark` — proposals are data,
not actions. An orchestrator or human decides whether to open the issue or run the
dispatch; running it is still not evidence of currency (see Contract).

## Phase 5: RECORD

Write `RESULT_PATH`:

```yaml
contract_version: 1
kind: impact
workspace: {LOGIN}
run_at: "{RUN_AT}"                # quote: an unquoted ISO-8601 value parses as a YAML datetime
actor: { gh_login: {gh api user login or unknown}, machine: {hostname}, mode: {MODE} }
edges_checked: {AUDIT_JSON.edges_checked}
edges_stale: {AUDIT_JSON.edges_stale}
markers_updated: 0                # this skill never calls impact.py mark; see Contract
edges: {AUDIT_JSON.edges}
findings: {AUDIT_JSON.findings}
proposed_actions: {PROPOSED_ACTIONS}
asks_recorded: []                 # every gap this skill hits is deterministic; nothing to ask
errors: {ERRORS}
```

Validate:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" "$RESULT_PATH" --kind impact
```

Non-zero exit is a skill bug; report validator stderr verbatim.

Print a one-line log summary:
`impact-audit: edges={edges_checked} stale={edges_stale} proposed={n}`

## ABORT semantics

Every ABORT above appends the reason to `ERRORS` and falls through to Phase 5 with
`edges_checked: 0`, `edges_stale: 0`, `markers_updated: 0`, `edges: []`,
`findings: []`, `proposed_actions: []`, `asks_recorded: []` — the result file is
always written and validated. If `CONFIG_DIR` is unusable, write to the `result_path`
input, else `impact-result.yaml` in the current directory, and say so.

## Related

- `lib/pulse/scripts/impact_snapshot.py` — remote-evidence collector (F5 Task 3)
- `lib/pulse/scripts/impact.py` — pure audit engine + marker writer (F5 Task 1/2)
- `lib/patterns/headless-contract.md` — the impact-result schema
- `lib/references/config-schema.md` § depends_on edges — `repo_dependencies` shape
- `lib/patterns/run-ledger.md` — the `binding_edges_current` release gate that consumes
  this skill's `impact-result.yaml` via `resolve_run.py check-gate`
