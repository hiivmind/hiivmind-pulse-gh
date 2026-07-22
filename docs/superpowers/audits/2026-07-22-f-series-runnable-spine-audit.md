# F-Series Runnable-Spine Audit: Library vs Driver vs Skill

**Date:** 2026-07-22
**Scope:** The F0–F9 fleet program (`docs/superpowers/plans/2026-07-*-f*.md`) as merged to `develop`, viewed as a runnable production system rather than as unit-tested modules.
**Question:** For each F-phase capability, is there an actual production path — a real trigger through a runnable driver to a validated result — or is the phase a tested library whose orchestration exists only as prose that an agent must improvise a driver for?

## How this surfaced

While dogfooding the F9 overlays against this repo, there was no shell entry point
that would score `claude-plugin-v1` or run marketplace-sync. The only way to
exercise the merged capability was to **hand-write a Python driver** that imported
the shipped functions (`profile_dispatch.dispatch`, `register_claude_adapters`,
`marketplace_sync.compare`) and assembled their inputs. That improvisation was
not an F9 quirk — it is the normal state of the entire propose/mutate half of the
program.

## Executive finding

Every F-phase capability is built from three layers:

1. **Library** — a pure, tested module (`marketplace_sync`, `pen_orchestrator`,
   `profile_dispatch`, `plan_sync`, `generator_dispatch`, …).
2. **Driver** — a CLI (`*.py` with a `__main__`/argparse entry) that assembles
   inputs, calls the library, and writes a validated `result.yaml`. This is the
   layer a `SKILL.md` or a scheduler can actually **run** (`uv run …`).
3. **Skill** — the `SKILL.md` orchestration document an agent or scheduler follows.

**The read/score half of the program (F0–F3, Pre-F4, F5) built all three layers
and is runnable. The propose/mutate half (F6–F9) built layers 1 and 3 but skipped
layer 2.** For those phases the `SKILL.md` substitutes a **function signature** for
a runnable command — `plan_sync.compute(...)`, `pen_orchestrator.execute(...)`,
`marketplace_sync.compare(...)` — which an agent cannot execute from prose without
writing glue. Consequently nothing (heartbeat, scheduler, or CLI) invokes F6–F9,
and the guarded mutation executor `pen_orchestrator.execute` has **no caller
anywhere but tests**.

This passed review because a skill that pastes the exact function contract *reads*
as a complete orchestration. It is not executable, and "propose-only / apply-mode
deferred" hid the gap rather than excusing it: a propose-only headless run still
needs a driver to emit its proposals into a validated result for review.

## What actually triggers work in production

| Trigger | Path | Reaches |
|---|---|---|
| Heartbeat (SessionStart) | `hooks/heartbeat.sh` → `lib/pulse/scripts/poll.py` | Detects due workflows / branch-head changes and **surfaces** them; runs no mutation itself |
| Scheduler (external `hiivmind-pulse-scheduler`) | `TEMPLATE-workspace-maintenance.md` composes **status → refresh → healthcheck → PR** | The read spine only |
| Interactive | `/gh` gateway → `gh-operations` | Direct GitHub operations |

No trigger composes impact (F5), pen (F6), generator (F7), plan-sync (F8), or
marketplace/overlays (F9).

## Phase matrix

| Phase | Library module | CLI driver? | Skill | Runnable unattended today? |
|---|---|---|---|---|
| F0 Nave evidence | `evidence_snapshot`, `nave_adapter` | ✅ CLI | `gh-fleet-evidence-headless` | ✅ |
| F1 profiles/scorecard | `profile_dispatch` | ✅ via `healthcheck_dispatch` | `gh-healthcheck-headless` | ✅ neutral only |
| F2 fleet membership | `fleet_membership`, `profile_proposals` | ✅ CLI | `gh-fleet-membership-headless` | ✅ (not scheduled) |
| F3 dispatched healthcheck | `healthcheck_dispatch` | ✅ CLI | `gh-healthcheck-headless` | ✅ scheduled |
| Pre-F4 dependency evidence | `dependency_evidence` | ✅ `validate_dependency_evidence` | (folded into evidence) | ✅ |
| F5 impact bindings | `impact`, `impact_snapshot` | ✅ CLI | `gh-impact-audit-headless` | ✅ (poll-surfaced trigger only) |
| **F6 pen mutations** | `pen_orchestrator`, `mutation_plan` | ❌ **none** | (used by gen/workflow skills) | ❌ improvise |
| **F7 generator dispatch** | `generator_dispatch`, `generated_artifacts` | ❌ **none** (only `validate_result`) | `gh-generated-artifact-headless` | ❌ improvise |
| **F8 plan sync** | `plan_sync`, `plan_sync_snapshot` | ❌ **none** (only `validate_result`) | `gh-plan-sync-headless` | ❌ improvise |
| **F9 overlays / marketplace** | `marketplace_sync`, `adapters/claude_plugin`, `repo_claims` | ❌ **none / not registered** | `gh-marketplace-sync-headless` | ❌ improvise |

### F9-specific wiring gaps (the concrete instance of the pattern)

1. `healthcheck_dispatch.py` registers `register_universal_adapters` only, never
   `register_claude_adapters` — a `claude-plugin-v1` repo run through it resolves
   all three `claude.*` checks to `unsupported` ("No adapter registered").
2. The F0 evidence snapshot carries file **paths** only, never `file_contents`;
   the claude adapters read content, so even if registered they return `unknown`.
   Nothing builds the overlay content channel.
3. `marketplace_sync` has an agent-runnable `SKILL.md` but no CLI and no
   scheduler/heartbeat trigger.
4. The `claude.context` inference step has no orchestration hook: the skill never
   instructs the agent to extract claims and feed `inferred_claims`, so it
   silently never runs — a headless run hands out a clean `pass` over stale docs
   (observed live: deterministic pass = A grade; with the inferred `stale_command`
   finding folded in the grade is B / 4-of-5).

## Root cause

1. **SDD rewards pure modules.** They unit-test cleanly and let the controller
   re-run gates, so every phase produced a pristine library first.
2. **Apply-mode was deferred.** The mutation phases are propose-only dead-ends, so
   a runnable driver felt premature — but propose-only still needs a driver to
   emit proposals for review, so this hid the missing layer rather than removing
   the need for it.
3. **Skills cite signatures instead of commands.** A `SKILL.md` that pastes
   `module.func(...)` reads as complete and passes review, but is not executable
   and forces per-run improvisation with no result-contract guarantee.

Charitable reading considered and rejected: "the agent is the runtime and writes
the glue each run." The read phases got real CLIs, so the intended pattern is a
driver; and an improvised per-run driver is unschedulable and has no validated
result contract. Under either reading, F6–F9 are not production-wired.

## Remediation shape (an F10 "runnable spine" phase)

The missing **driver layer**, applied uniformly:

- A CLI per mutation/sync module (or genuinely executable skills) that assembles
  inputs and emits the validated `result.yaml`:
  `marketplace_sync`, `plan_sync`, `generator_dispatch`, and the guarded executor
  `pen_orchestrator`.
- Overlay wiring in the dispatcher: opt `register_claude_adapters` into
  `healthcheck_dispatch.py` for overlay scorecards, and populate the overlay
  `file_contents` content channel in the F0 evidence build for opted-in repos.
- An inference hook in `gh-healthcheck-headless` (and/or the context adapter path)
  that records whether the inference step ran; a skipped step is `unknown`, never
  a silent `pass`.
- Scheduler-composition entries so a trigger actually invokes the propose/mutate
  phases (even in propose-only mode, to emit reviewable proposals).

## Evidence pointers

- `lib/pulse/scripts/healthcheck_dispatch.py` — `register_universal_adapters`
  only; the CLI driver for the F1/F3 read path.
- `lib/pulse/scripts/adapters/__init__.py` — `register_claude_adapters` exists and
  is lazy/isolated, but has no non-test caller.
- `skills/gh-marketplace-sync-headless/SKILL.md`, `…/gh-plan-sync-headless/…`,
  `…/gh-generated-artifact-headless/…` — cite `module.func(...)` signatures with
  no `uv run` driver.
- `lib/patterns/repository-mutations.md` — the only reference to running the
  mutation modules is a `pytest` command.
- `hooks/heartbeat.sh` → `lib/pulse/scripts/poll.py` — trigger-and-surface only.
