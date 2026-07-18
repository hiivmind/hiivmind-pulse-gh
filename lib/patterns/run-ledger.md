# Pattern: Run Ledger

Workflow runs persist as ledger records so runs survive sessions: a run started in
one session (or machine) is resumed by any later one. The LLM **never hand-edits
ledger YAML** — all reads/writes go through `resolve_run.py`.

## Location and placement

| Run kind | Path | Git status |
|---|---|---|
| cross-repo (v3 `steps:`, or >1 repo) | `{workspace_root}/.hiivmind/github/runs/{workflow}-{run_id}.yaml` | **committed** — the team's shared release-state view |
| single-repo / personal | `{workspace_root}/.hiivmind/github/runs/local/{workflow}-{run_id}.yaml` | gitignored (`runs/local/`) |

`run_id` = `{UTC date}-{gh_login}-{HHMMSS}` — actor-embedded so two machines cannot
mint colliding records. `resolve_run.py create` refuses to overwrite.

## Schema (`ledger_version: 1`)

```yaml
ledger_version: 1
workflow: release-train
run_id: 2026-07-11-octocat-093012
status: running | blocked-on-gate | done | failed
created_at: <ISO 8601>
updated_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: interactive | scheduled }   # creator
repos: [<owner/name or catalog name>, ...]
params: {}                       # resolved param values at creation
state_snapshot: {}               # v2 state vars at last suspension (informational)
steps:
  - id: tag-lib                  # unique
    repo: <name or [names]>
    depends_on: []               # step ids
    gate: <str or null>          # natural-language condition; null = no gate
    has_workflow: <bool>         # true if the step carries a workflow block; a satisfied
                                 # gate completes a gate-only step but leaves a gate+workflow
                                 # step runnable so its block still executes
    gate_satisfied: <bool|null>  # null until evaluated; set via resolve_run.py gate-result
    gate_checked_at: <ISO|null>
    status: pending | running | blocked-on-gate | done | failed | skipped
    actor: { gh_login, machine } | null    # who last advanced this step (I4)
    started_at: <ISO|null>
    finished_at: <ISO|null>
    lease: { leased_by: "<gh_login>@<machine>", leased_at: <ISO> } | null
    notes: []                    # free-form audit strings
```

v2 (flat) runs get a one-step ledger (`steps: [{id: run, ...}]`) in `runs/local/`
so every run leaves a record — the poll-state `last_result` enum stays for cheap
triggers; the ledger holds the real history.

## Run-status derivation (computed by resolve_run.py, never by hand)

any step `running` → `running`; else any `failed` → `failed`; else any step
runnable (deps met, gate cleared) → `running`; else any gate-waiting step →
`blocked-on-gate`; else all `done`/`skipped` → `done`.

## Resume protocol (multi-machine)

1. **Pull the workspace repo first** — the ledger is shared state; local copies are
   never authority.
2. `resolve_run.py next --file <ledger>` → runnable / blocked / done.
3. For each blocked step: evaluate the gate's truth against GitHub (`gh` queries
   derived from the condition text), then record it:
   `resolve_run.py gate-result --file <ledger> --step <id> --satisfied true|false`.
4. For each runnable step: acquire the lease
   (`resolve_run.py lease --file <ledger> --step <id> --by "<gh_login>@<machine>"`),
   execute, then `update --status done|failed`. Leases are **advisory**: an expired
   lease (default TTL 120 min) is stolen; execution must be idempotent.
5. Commit + push the ledger change (committed runs) so other machines see it.

## CLI reference

```
uv run {PLUGIN_ROOT}/lib/pulse/scripts/resolve_run.py <subcommand> ...

create      --runs-dir DIR --workflow W --run-id ID --actor-login L --actor-machine M
            [--mode interactive|scheduled] [--params JSON] [--repos CSV]
            [--steps JSON] [--local]        → validates DAG, writes ledger, prints path
next        --file LEDGER                   → JSON {status, runnable[], blocked[{id,gate}], done}
update      --file LEDGER --step ID --status S
            [--actor-login L --actor-machine M] [--note TEXT]
gate-result --file LEDGER --step ID --satisfied true|false [--note TEXT]
check-gate  --file LEDGER --step ID --result FILE --gate-type TYPE
                                             → deterministic evaluator counterpart to
                                               gate-result: reads a headless result file
                                               (lib/patterns/headless-contract.md), fails
                                               closed on missing/malformed/non-conforming
                                               evidence, records the verdict the same way,
                                               prints JSON {satisfied, detail}
lease       --file LEDGER --step ID --by WHO [--ttl-minutes 120]
```

`gate-result` is for prose gates a human/LLM adjudicates against live GitHub
state. `check-gate` is for gates a registered evaluator can compute
deterministically from an already-validated result file — e.g.
`binding_edges_current` (F5) reads an `impact-result.yaml` and is satisfied
only when it validates as kind `impact` with `edges_stale == 0` and no edge
in state `unknown`. New evaluators register by name in `resolve_run.py`'s
`GATE_EVALUATORS`; `--gate-type` naming an evaluator that isn't registered is
a usage error (exit 1), never silently treated as satisfied.

Exit codes: 0 ok, 1 validation/state error, 2 file missing/unparseable,
3 lease actively held by someone else.

## Related patterns

- `workflow-execution.md` — V3 Execution (who calls these commands, and when)
- `workspace-detection.md` — multi-machine topology, pull-before-reconcile
- `headless-contract.md` — the workflow-run result file (per-run report; the ledger
  is the durable history)
