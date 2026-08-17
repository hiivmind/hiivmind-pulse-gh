# Backlog: F8 plan-sync — GitHub Projects (v2) field sync

**Date:** 2026-08-17
**Status:** Open, no spec
**Severity:** Feature gap (not a bug) — F8 is deliberately V1-scoped to exclude this
**Found in:** F8 plan-sync live-proof (2026-08-16, `hiivmind-pulse-gh#151`/`#152`); raised
by user follow-up during the live-proof debrief
**Scope:** `lib/pulse/scripts/plan_sync.py`, `plan_sync_snapshot.py`, `plan_sync_run.py`
(pulse-gh); a materially different API surface (GraphQL) than F8's current REST reads

## Problem

F8 reconciles a bound Markdown doc against exactly one thing: a plain repo
**Issue**, on five REST-level fields (`title`, `state`, `assignees`, `milestone`,
`body`). This is explicit, documented V1 scope
(`lib/patterns/plan-sync-binding.md` § V1 exclusions): *"V1 does not synchronize
GitHub Projects custom fields, labels, or comments."*

An Issue and a Projects v2 **item** are separate objects. An item can wrap an
Issue (or exist standalone as a project-only draft, no linked issue at all) and
carries board-scoped fields — Status (single-select), Priority, Iteration,
custom text/number/user fields — that live on the *item*, not the *issue*. F8
has zero awareness of any of this: `_github_snapshot()` only calls
`/repos/{repo}/issues/{number}` and `/milestones`; it doesn't know whether the
bound issue is on a project board, which project, or what its item fields say.

## Motivating use cases (user-identified, non-exhaustive)

- **Write**: a doc's status section drives a linked project item's Status field
  (e.g. doc marked "in progress" → move the board card to "In Progress"), or the
  reverse (card moved → doc reflects it) — the same bidirectional reconciliation
  F8 already does for `state`, just scoped to a project's custom field instead
  of the issue's own open/closed.
- **Read**: surface a linked item's prioritization/assignment fields (Priority,
  Iteration, a project-specific "Owner" field) into the doc or into plan-sync's
  findings, for triage/context — doesn't require writing anything back.
- **Explicitly flagged as non-exhaustive** — "there could be many more." Projects
  v2 fields are user-defined per project (arbitrary single-select options,
  iterations, numbers, text, user references); this is a **general custom-field
  sync capability**, not a fixed 2-field extension. Any design should treat the
  field set as configurable per binding, not hardcode Status/Priority.

## Why this is a real fork, not a small addition

- **Different API surface entirely.** Projects v2 items/fields are GraphQL-only
  — no REST equivalent. F8's current `GhApi = Callable[[str], Any]` seam
  (`gh api <path>`) doesn't cover this; would need a GraphQL seam alongside it.
  (Precedent already exists in this codebase: `lib/pulse/scripts/poll.py`'s
  `check_projects()` builds `ProjectV2` GraphQL queries for read-only
  session-wake change detection — reusable query shape, but that code path is
  read-only and entirely separate from F8's reconciliation engine.)
- **Cardinality.** An issue can belong to 0, 1, or many projects. F8's binding
  (`sync.issue: {repo, number}`) has no way to say *which* project's item to
  sync — needs a new `sync.project` shape (org/user + project number, or a
  resolved item id) alongside the existing issue binding.
- **Field-type diversity.** F8's current merge logic (`merge_field` /
  `_SYNC_FIELDS`) assumes a fixed, small set of scalar/list fields. Projects v2
  fields are heterogeneous (single-select options, iteration objects with
  start/duration, user lists, free text, numbers) and per-project-configurable
  — the three-way merge and validation would need to generalize to an
  open field set, not just add two more names to `_SYNC_FIELDS`.
- **No write path exists anywhere yet.** `object_apply.py` (F8's GitHub-write
  path under `allow-listed` mode) has no Projects v2 mutation support today —
  this would be new, not a reuse of an existing writer.

## Recommendation

Design-first, not a quick patch — same bucket as the `allow` confirmation-model
item in `2026-07-29-apply-mode-v2-deferrals.md` § B. Suggested shape to explore
in a future brainstorm:

- `sync.project: {org_or_user, number, fields: {<field name>: <policy>}}` as an
  addition alongside (not a replacement for) `sync.issue`.
- Reuse `poll.py`'s `ProjectV2` GraphQL query shape as the read-side seam;
  build a parallel GraphQL mutation seam for writes (`updateProjectV2ItemFieldValue`).
- Resolve the item id for a bound issue at snapshot time (an issue's
  `projectItems` connection), erroring explicitly (not silently) if the issue
  isn't on the named project.
- Keep the existing issue-level sync (`title`/`state`/`assignees`/`milestone`/`body`)
  and the new project-field sync as independently gate-able policies — a doc
  might bind to an issue only, a project only (rare), or both.

## Evidence

- `lib/patterns/plan-sync-binding.md` § V1 exclusions (explicit scope line).
- `lib/pulse/scripts/plan_sync_snapshot.py::_github_snapshot` — REST-only,
  `/repos/{repo}/issues/{number}` + `/milestones`, no project awareness.
- `lib/pulse/scripts/poll.py::check_projects` / `_build_query` — existing
  read-only `ProjectV2` GraphQL precedent, unconnected to F8.
- `lib/pulse/scripts/object_apply.py` — no `project`/`Project` references;
  confirms no write path exists.

## Notes

Not a regression or a bug — F8 shipped this way deliberately (V1 scope cut).
Captured now because the live-proof made the gap concrete and the user named
real consumer intent (status-driven board updates, prioritization/assignment
visibility) beyond the original propose-only issue-sync use case.
