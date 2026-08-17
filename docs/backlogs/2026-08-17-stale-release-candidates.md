# Backlog: detect stale/abandoned release-candidate releases and branches

**Date:** 2026-08-17
**Status:** Open, no spec
**Severity:** Operational hygiene / release-process hygiene, not a bug
**Found in:** user request, same batch as `2026-08-17-stale-merged-branches.md` and the
branch-protection governance-parity exploration
**Scope:** a new fleet check distinct from `release-monitor.yaml`/`release-train.yaml`;
`lib/pulse/scripts/marketplace_sync.py` (adjacent, different purpose, not reusable as-is)

## Problem

Two related but distinct "stale RC" signals exist in this program's domain,
and neither is audited today:

1. **A GitHub Release object marked `prerelease` or `draft`** can sit
   indefinitely without ever being promoted to a stable release or removed.
   Nothing computes its age or flags abandonment.
2. **A `release/*` branch** (this repo's own documented mountainash
   three-tier flow: `feature/* → develop → release/* → main + CalVer tag`,
   per `~/.claude/CLAUDE.md`) can go stale if its PR into `main` stalls —
   distinct from an already-merged branch (the sibling
   `2026-08-17-stale-merged-branches.md` item) and from a normal open PR
   (`stale-check.yaml`'s existing 7-day threshold does technically cover *a
   PR* going stale, but nothing treats a release-branch PR as a distinguished
   category worth its own signal, e.g. "an RC has been open N days without
   shipping" as opposed to any generic PR).

## What this would require (real scope, not exhaustive by design)

- **Release-object staleness**: `GET /repos/{o}/{r}/releases` is already
  fetched (`evaluate_checks.py`'s `releases.json` data-dir file, and
  `marketplace_sync.py`'s live GraphQL query) — but only ever consulted for
  "what is the current latest stable," never for the age of a
  `prerelease`/`draft` entry itself. Would need: age computation from
  `created_at`/`published_at`, a threshold, and a decision on whether a
  `draft` (never published) and a `prerelease` (published but not
  promoted) are the same check or two.
- **Release-branch staleness**: needs branch age (last-commit timestamp) plus
  whether an open PR targets `main` from it and that PR's own age/CI state —
  effectively a specialized instance of "stale PR" scoped to
  release-branch-shaped heads, which argues for reusing
  `stale-check.yaml`'s existing PR-staleness machinery with a
  release-branch filter rather than inventing a second PR-age computation.
- **A staleness threshold and mutation policy** — mirrors the same open
  question in the sibling stale-merged-branches item; likely propose-only
  (ping the release owner, surface in a workflow's `PRESENT` step) — no
  auto-deleting a release or force-merging a release branch. Matches
  `release-monitor.yaml`'s existing `auto: false` posture.
- **Scope decision**: this may be one workflow with two `GATHER` sources
  (release objects + release-shaped branches) or two separate checks: a
  `brainstorming` pass should settle this rather than assuming.

## Evidence

- `templates/workflows/release-monitor.yaml` (read in full) — `trigger:
  {type: session_poll, source: releases, condition: state_changed}`; reacts
  only to a *newly published* release (`GATHER: release = show latest
  release...`), never computes age of an existing prerelease/draft, no
  staleness logic anywhere in the file.
- `templates/workflows/release-train.yaml` (read in full) — a one-shot,
  on-demand version-bump DAG (`tag-lib → verify-lib → bump-consumers →
  verify-consumers`) with completion `gate:` conditions per step
  (e.g. `"release {params.version} published AND checks green"`), but no
  age-based abandonment/timeout handling anywhere in the DSL shown; a stalled
  gate just sits with no escalation defined at this layer.
- `lib/pulse/scripts/marketplace_sync.py:83-108` — `isPrerelease`/`isDraft`
  releases are explicitly *excluded* when selecting the newest stable tag
  (fail-closed: any non-`False` or missing flag value is treated as
  excluded), confirmed by
  `tests/test_marketplace_sync.py::test_compare_excludes_prerelease_and_draft_releases`
  and `::test_compare_excludes_draft_only_release_when_no_stable_present`.
  This is a **selection filter**, not a **staleness detector** — it answers
  "which release is the current stable," never "has this prerelease been
  sitting too long."
- Grepped `release` + `stale`/`abandoned` across `docs/backlogs/` and
  `docs/superpowers/`: zero matches — no prior design captured this gap.
- `~/.claude/CLAUDE.md` (global rules, this session) — the mountainash
  `release/*` → `main` three-tier flow this item's second sub-signal would
  audit for abandonment.

## Notes

No-spec. Two sub-signals (release-object staleness vs. release-branch
staleness) sharing a name but not obviously one mechanism — a
`brainstorming` pass should settle whether they ship as one workflow or two,
the staleness threshold(s), and whether release-branch staleness is better
expressed as a `stale-check.yaml` filter extension rather than new machinery,
since it is structurally "a stale PR, scoped to a branch-name pattern."
