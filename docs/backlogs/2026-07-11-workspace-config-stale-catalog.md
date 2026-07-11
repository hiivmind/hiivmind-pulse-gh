# Backlog: Stale repository catalog in the dogfood workspace config

**Date:** 2026-07-11
**Status:** Open
**Severity:** Medium (data, not code)
**Found in:** P3 dogfood verification (PR #120 — `gh-healthcheck-headless` / `gh-refresh-headless` run against `~/git/hiivmind`)
**Scope:** workspace data — `~/git/hiivmind/.hiivmind/github/config.yaml` (the `hiivmind-workspace` repo), not the plugin code

## Problem

The committed workspace `config.yaml` holds stale cached identifiers that no longer
match GitHub:

1. **`repositories[].full_name` for the plugin repo is wrong:** cached as
   `hiivmind/gh`, which 404s. The real repository is `hiivmind/hiivmind-pulse-gh`.
   `gh-healthcheck-headless` could not fetch repo metadata for that catalog entry —
   the dogfood run had to use the skill's `repos` override to evaluate the correct
   `owner/name` instead.
2. **`workspace.id` was stale** (`O_kgDODUFJxM4BKJj5` vs. the actual
   `O_kgDODUFJxA`). This one was **auto-corrected** by the `gh-refresh-headless`
   dogfood run when it refreshed the `workspace` section — noted here only so the
   correction is traceable and intentional, not a silent surprise on the next diff.

## Impact

- Any headless or interactive fleet audit that iterates the catalog by
  `full_name` silently skips or misreports the plugin repo until the catalog is
  fixed.
- `workspace.id` is now corrected in the working tree but that change is
  uncommitted (see below).

## Evidence

- `gh api repos/hiivmind/gh` → 404; `gh api repos/hiivmind/hiivmind-pulse-gh` → 200.
- `gh-healthcheck-headless` errors[] on the stale entry; grade produced only after
  the `repos` override.

## Proposed fix

- Refresh the `repositories` catalog for the dogfood workspace (interactive
  `gh-refresh`, or `gh-refresh-headless --sections repositories` once that section
  is refreshable) so `full_name` resolves to `hiivmind/hiivmind-pulse-gh`.
- Review, then commit the corrected `workspace.id` (and the refreshed catalog) to
  the `hiivmind-workspace` repo. The P3 dogfood runs left these as **uncommitted
  working-tree changes** in `~/git/hiivmind/.hiivmind/github/` — the headless
  skills deliberately never commit/push the workspace repo (the orchestrator owns
  that step).

## Notes

Not a defect in the P3 diff — the headless skills behaved correctly given bad
cached data (surfaced the 404 as an `errors[]` entry, corrected the org id on
refresh). This is workspace-state hygiene.
