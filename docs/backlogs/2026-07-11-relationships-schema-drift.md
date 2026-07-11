# Backlog: `relationships.yaml` schema drift vs. `evaluate_checks.py`

**Date:** 2026-07-11
**Status:** Open
**Severity:** Medium (produces a wrong check result)
**Found in:** P3 dogfood verification (PR #120 — `gh-healthcheck-headless` run against `~/git/hiivmind`)
**Scope:** contract between the real `relationships.yaml` and `lib/pulse/scripts/evaluate_checks.py` (P2)

## Problem

The shape of the real workspace's `relationships.yaml` does not match the shape
`evaluate_checks.py` reads when scoring the `project_linkage` check:

- **Real file:** `relationships: [{ repositories: [...] }]`
- **`evaluate_checks.py` expects:** `project_repo_links: [{ repos: [...] }]`

Because the reader looks for the key/shape it never finds, `project_linkage`
scores `fail` even when the repo IS linked to a project — a **false negative**
that drags down the repo and aggregate governance grade.

## Impact

- `project_linkage` under-reports for every repo in a workspace whose
  `relationships.yaml` uses the `relationships:`/`repositories:` shape.
- Aggregate grades from `gh-healthcheck-headless` (and the interactive
  `gh-healthcheck`) are pessimistic by up to one check per repo.
- Any policy gating on the healthcheck grade inherits the false negative.

## Decision needed (which side is authoritative)

One of:
1. **Fix the reader** — make `evaluate_checks.py` accept the
   `relationships: [{repositories:[...]}]` shape (and/or both shapes) — if
   `relationships.yaml` as written is the intended schema.
2. **Fix the data + document the schema** — normalize `relationships.yaml` to
   `project_repo_links: [{repos:[...]}]` and pin the schema in a template/pattern
   so future files match the reader.
3. **Align both to a single documented schema** and add a fixture-backed test in
   `lib/pulse/scripts/tests/` so the drift can't recur silently.

Preference: option 3 — pick one schema, document it (template + a line in the
healthcheck-checks reference), and add a `project_linkage` fixture test to
`evaluate_checks.py`'s suite so a mismatched shape fails CI instead of silently
scoring `fail`.

## Evidence

- Live P3 dogfood: `project_linkage` read `fail` for a repo known to be linked;
  inspection showed the key/shape mismatch above.

## Notes

Pre-existing P2/real-data drift, **not** introduced by the P3 diff — P3 only
consumes `evaluate_checks.py` as-is. Surfaced because P3 was the first run of the
evaluator against the real workspace's `relationships.yaml`.
