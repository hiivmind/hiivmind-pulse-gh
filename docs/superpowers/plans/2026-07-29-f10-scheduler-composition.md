# F10 Task 6 — Scheduler composition + PR-body projection (cross-repo spec)

> **Authored in `hiivmind-pulse-gh` (this repo); executed as a separate PR in
> `hiivmind-pulse-scheduler`.** This is the F10 plan's Task 6 deliverable: the precise
> scheduler-side edit that composes the propose/mutate phases into the maintenance run,
> plus the PR-body projection and compatibility contract. It is a **design spec**, not code —
> F10's Task 7 acceptance covers only the in-repo drivers; scheduler acceptance is asserted
> in the scheduler repo. **F10's phase gate for "triggered end-to-end" closes only when the
> `hiivmind-pulse-scheduler` PR below merges.**

## Context — what already exists (verified 2026-07-29)

The scheduler's `TEMPLATE-workspace-maintenance.md` already composes
**status → refresh → healthcheck → PR** and, crucially, already has a **generic
scheduled-workflow phase and a PR-body projection** for exactly this shape of work:

- **Phase 5b: Scheduled Workflows (optional)** — reads `automation.scheduled_workflows`
  from `{config_dir}/config.yaml`; for each workflow name, `CALL_SKILL(
  "hiivmind-pulse-gh:gh-workflow-run-headless", {workspace_path, workflow, mode: scheduled})`;
  reads + validates `workflow-run-result.yaml` (`--kind workflow-run`) and appends to
  `computed.workflow_results`. It already **skips gracefully** when the section is
  absent/empty *or* when the plugin has no `gh-workflow-run-headless` skill.
- **Phase 6 PR body** already renders a **"Workflow runs"** table (`{name} | {outcome} |
  {findings count}`) and a **"Needs attention"** list carrying
  `proposed_actions: {workflow}: {action}  <!-- mutations withheld headless -->` and
  `asks_recorded: {workflow}: {question}`.
- **Result files are gitignored** (`*-result.yaml`) — so the maintenance PR never commits a
  result file; the **PR body is the only delivery channel** for each run's proposals/findings.

**Consequence:** F10 needs **no new scheduler phase**. The four F10 propose/mutate workflows
are already `periodic`-triggered workflow definitions (F10 Task 5); composing them is (1) a
config-list entry and (2) ensuring their proposals reach the existing PR-body projection.

## The edit (lands in `hiivmind-pulse-scheduler` + the workspace config)

### 1. Compose the four phases into Phase 5b (workspace config, not the template)

Add the F10 propose/mutate workflows to `automation.scheduled_workflows` in the **workspace
repo** config (`{WORKSPACE_PATH}/.hiivmind/github/config.yaml`) — the same list Phase 5b
already iterates. Order after healthcheck (read spine first), propose-only:

```yaml
automation:
  scheduled_workflows:
    - impact-audit
    - generated-artifact-audit
    - plan-sync
    - marketplace-sync
```

All four are `auto: false` + `trigger: {type: periodic, interval_minutes: 1440}` (F10 Task 5),
so Phase 5b runs them at most daily, `mode: scheduled`, and **cooldown/interval gating is
already enforced** by `gh-workflow-run-headless` + the poll cadence. No template edit is
required for the *composition* — Phase 5b is already generic over the list.

### 2. PR-body projection — ensure F10 proposals surface (the one real requirement)

Each F10 driver emits its own `*-result.yaml` of kind `marketplace-sync` / `plan-sync` /
`generated-artifact`, **not** `workflow-run`. Phase 5b consumes the outer
`workflow-run-result.yaml` produced by `gh-workflow-run-headless`. Therefore the projection
requirement is:

> **`gh-workflow-run-headless` must fold the inner F10 driver's `proposals[]` summaries and
> findings into the `workflow-run-result.yaml` it emits** — as `proposed_actions` (one per
> proposal summary: `{workflow}: propose {transformation} on {binding}`) and a `findings`
> count — so Phase 6 renders them in "Workflow runs" (count) and "Needs attention →
> `proposed_actions`" (per-proposal line). Because result files are gitignored, this
> projection is the **only** way an operator sees a scheduled F10 proposal.

The scheduler-repo PR must (a) verify `gh-workflow-run-headless` already surfaces inner
`proposed_actions`/findings for a driver-backed workflow, and (b) if it does not, that folding
is a small `gh-workflow-run-headless` change **in this plugin repo** (a follow-up task), not a
scheduler change. Either way, the scheduler template's Phase 6 needs **no new section** — the
existing `proposed_actions` line is the projection surface.

### 3. Compatibility contract (bidirectional, non-breaking)

- **New scheduler template + old plugin** (no F10 workflows / no `gh-workflow-run-headless`):
  Phase 5b already skips when the skill is absent or the workflow name is unknown → "phase
  unavailable" / workflow skipped, never an error.
- **Old scheduler template + new plugin** (F10 workflows exist, `scheduled_workflows` unset):
  Phase 5b skips an absent/empty list → the F10 phases simply don't run on cadence until the
  config gains the list. No error.
- **Per-workflow failure** is logged to `computed.errors` and the run continues (existing
  behavior). A propose-only F10 run is non-destructive, so a failed cadence run just waits a
  full interval (F10 Task 5 failure semantics).
- **Result files stay gitignored** — the composition never commits an F10 result file; the PR
  body is the contract surface.

## Scheduler-side acceptance (asserted in `hiivmind-pulse-scheduler`, not here)

The scheduler-repo PR lands these tests:

1. **Projection render:** a fixture `workflow-run-result.yaml` carrying F10-style
   `proposed_actions` + `findings` renders the expected "Workflow runs" row **and** the
   "Needs attention → `proposed_actions`" lines in the Phase 6 PR body.
2. **Unavailable workflow is skipped, not errored:** a `scheduled_workflows` entry naming a
   workflow the plugin doesn't expose → Phase 5b logs and continues (no ABORT).
3. **Result-file exclusion holds:** after a composed run, `git status --porcelain` in
   `{config_dir}` shows no `*-result.yaml` staged (only refreshed catalogs / freshness /
   healthcheck.yaml land).
4. **Compatibility:** an empty/absent `automation.scheduled_workflows` runs the maintenance
   flow unchanged (status → refresh → healthcheck → PR) with no Workflow-runs section.

## Open follow-up (tracked, not blocking this spec)

- Verify/implement `gh-workflow-run-headless` folding of inner driver `proposals[]` →
  `workflow-run-result.yaml` `proposed_actions`. If absent, it is a small **plugin-repo**
  task (not scheduler), because the projection surface (`proposed_actions`) already exists in
  Phase 6. Capture in the F10 backlog / `docs/backlogs/` if deferred.

## Provenance

Derived from `hiivmind-pulse-scheduler/TEMPLATE-workspace-maintenance.md` (Phase 5b, Phase 6
PR body, `*-result.yaml` gitignore) as of 2026-07-29, and F10 Tasks 1–5 in this repo
(`marketplace_sync_run.py`, `plan_sync_run.py`, `generated_artifact_run.py`, the overlay
wiring, and the `periodic` trigger + template flips).
