# Backlog: remaining unbuilt ideas rescued from the retired lockstep-bindings catalog

**Date:** 2026-08-17
**Status:** Open, no spec (five small, independent items)
**Severity:** Low — none block anything shipped; each is a standalone future workflow/check
**Found in:** archiving `docs/superpowers/specs/2026-07-10-lockstep-bindings-and-target-workflows-design.md`
and its companion `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
(+ `docs/superpowers/plans/2026-07-10-p0..p6-*.md`) to
`docs/superpowers/archive/` — most of that catalog's ideas already shipped
under F-series numbers (verified below); these five did not and would
otherwise have been silently lost
**Scope:** five independent, small items — see each subsection

## Why this doc exists

Before archiving the 2026-07-10 doc family, every one of its catalog entries
(§3.1–§3.7) and the companion spec's P7 housekeeping phase was checked
against the current codebase, not assumed. Most shipped — just under F-series
numbers, with the 2026-07-10 doc's own tracking table never updated to say
so:

| Original entry | Shipped as | Evidence |
|---|---|---|
| 3.1 plan-sync | F8 (merged #134) | `lib/pulse/scripts/plan_sync.py` |
| 3.2 impact-audit | F5 (merged #129) | `lib/pulse/scripts/impact.py`, `impact_snapshot.py` |
| 3.3 dep-coherence | F4/Pre-F4 (merged #128/#142) | `lib/pulse/scripts/dependencies.py` + adapters |
| 3.5 scaffold-drift | F7 (merged #133) | already tracked as open (binding-data gap) in `docs/backlogs/README.md` |
| 3.6.1 marketplace-sync | F9 (merged #136) | `lib/pulse/scripts/marketplace_sync.py` |
| 3.6.2 split-repo-currency | Built under F5's impact bindings | `hiivmind-pulse-gh-tests` `integration_tested_sha` edge, confirmed in `lib/pulse/scripts/tests/test_impact.py:696-742` |
| 3.6.4 contract-propagation | Built | `lib/pulse/scripts/contract_versions.py` — producer-version/consumer-requirement edge evaluation, generic (not `headless-contract.md`-specific, but the same mechanism) |
| 3.6.7 claude-md-currency | Built | `lib/pulse/scripts/adapters/claude_plugin.py:242` (`context()` — "Audit CLAUDE.md for claim currency") |
| P7.4 workflow lint | Built | `lib/pulse/scripts/workflow_lint.py` exists |
| P0–P6 (platform machinery) | All done | companion spec's own §8.9 table: P0–P5 done 2026-07-10/12; P6 marked "in-progress" in the doc but its deliverables (run ledger, `resolve_run.py`, `depends_on`/`gate` DSL) are confirmed live in `lib/pulse/scripts/resolve_run.py` and `templates/workflows/release-train.yaml` |

`docs/backlogs/2026-08-17-branch-protection-governance-parity.md` captures
3.6.3 (governance-parity), the one genuinely unbuilt full catalog entry with
real, demonstrated need.

**Five items checked and confirmed still unbuilt, with real (if smaller)
standalone value** — captured below rather than lost when the source doc
moves to `docs/superpowers/archive/`.

## 1. Repo onboarding cascade (beyond bare membership detection)

F2 (`lib/pulse/scripts/fleet_membership.py:reconcile_membership`) only diffs
the org's live repo list against the workspace `repositories[]` catalog. The
original design's richer scope — what a *new* repo should trigger beyond
catalog registration (apply a governance baseline once
`branch-protection-governance-parity.md` exists, seed default
labels/milestones, create a scheduler stub if the repo class warrants one,
open a checklist issue for non-automatable onboarding steps) — was never
built. No `seed_labels`/`create_stub`/`checklist_issue` function exists
anywhere in `lib/pulse/scripts/`.

**Depends on** the governance-parity item above for its first cascade step.

## 2. `watch_paths` dead-glob detection

Open question from the retired doc: impact-audit and scaffold-drift edges
declare `watch_paths` globs to scope what counts as an interface-surface
change. Nobody currently flags an edge whose `watch_paths` matched zero
files across the last N diffs — a silently-dead glob (e.g. after a rename)
would make an edge permanently inert with no signal. Candidate: a
healthcheck check reusing the same evidence impact-audit already scans.

## 3. Milestone alignment across train-scoped repos

Milestone "vX" in one repo ↔ same-named milestones in other repos scoped to
the same release train (via `cross_project_coordination`, today purely
documentary — no enforcement). Staleness signal: due dates diverge, or a
blocking issue sits in an already-closed milestone. Value rises once
`release-train.yaml`-style multi-repo runs are exercised more (the DSL
exists and is confirmed live per the P6 table above, but real usage is
still early).

## 4. Changelog rollup

Constituent repos' releases since the last release-train run ↔ an org-level
release note drafted in the central repo. LLM-drafted (`inferred`), applied
by PR, never pushed direct. Natural final step of a release-train run once
those runs are common enough to be worth summarizing.

## 5. CLAUDE.md housekeeping (P7.1–P7.3, never finished)

The companion spec's P7 "Housekeeping" phase shipped its script deliverable
(`workflow_lint.py`, confirmed present) but not its two documentation
deliverables:
- **P7.2** — a "cross-cutting concerns" table in this repo's own
  `CLAUDE.md` was never added (grepped `CLAUDE.md` for "cross-cutting":
  zero matches).
- **P7.3** — `lib/patterns/derivation-dag.md` was never written (file does
  not exist; referenced only by the two now-archived spec docs themselves).

Both are small, self-contained documentation tasks with no code dependency —
candidates for the existing P4 "small cleanups" backlog tier
(`docs/backlogs/README.md`) rather than their own design pass.

## Notes

No-spec, five independent items, none blocking. Priority is low across the
board — this document exists to prevent silent loss during the archive move,
not to argue any of these are urgent. `claude-md-currency` (already built)
is a plausible detection mechanism a future pass could point at items 5's
own drift (self-referential: this exact review found the CLAUDE.md/pattern-doc
gap the built check exists to catch — worth confirming the check is
actually wired into a fleet sweep, not just implemented and dormant).
