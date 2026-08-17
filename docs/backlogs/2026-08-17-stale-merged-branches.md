# Backlog: detect and clean up already-merged branches left behind

**Date:** 2026-08-17
**Status:** Open, no spec
**Severity:** Operational hygiene — repo clutter / drift signal, not a bug
**Found in:** user request, exploring workflow-coverage gaps alongside branch-protection
governance-parity and stale-release-candidate detection
**Scope:** a new fleet check (or workflow) distinct from `stale-check.yaml`; needs a new
API-routing entry in `skills/gh-operations`; `lib/pulse/scripts` (no existing module owns this)

## Problem

A GitHub branch whose PR has already merged is frequently left behind: "delete
branch on merge" is a per-repo GitHub setting, not always enabled, and even
when it is, force-pushes, squash-merge edge cases, or PRs merged via `gh`/API
outside the UI can leave the branch alive with no PR referencing it as open.
Over time this accumulates dead branches nobody prunes. Nothing in this
program detects it, per-repo or fleet-wide.

**This is not `stale-check.yaml`.** That workflow's staleness condition is
"open PR/issue, not updated in N days" — an item still awaiting action. A
merged-and-abandoned branch is the opposite: the PR is already **closed**
(merged), there is nothing left to act on except delete the ref. Zero overlap
in trigger condition, data source, or remediation.

## What this would require (real scope, not exhaustive by design)

- **Detection data**: for each branch in a repo, whether it is an ancestor of
  the default branch (or another declared base) — via the compare API
  (`GET /repos/{o}/{r}/compare/{base}...{branch}`, `status: identical` or
  `behind` means fully merged) or, since a PR's `merged_at` + `head.ref` is
  already fetchable via `GET /repos/{o}/{r}/pulls?state=closed`, cross-referencing
  closed-merged PRs against the live branch list (`GET /repos/{o}/{r}/branches`)
  is the cheaper join (no per-branch compare call needed).
- **A write primitive this program doesn't have yet**: branch ref deletion
  (`DELETE /repos/{o}/{r}/git/refs/heads/{branch}`) is not in
  `skills/gh-operations`'s domain-routing table at all today — only branch
  *protection* routes exist (`skills/gh-operations` `domains/branch-protection.md`).
  Needs adding as its own domain/operation before this can mutate anything.
- **A staleness threshold and exclusion policy** — flag immediately on merge,
  or only after N days (mirrors the same open question in `stale-check.yaml`'s
  7d/14d thresholds)? Must exclude intentionally long-lived branches that can
  legitimately show as "merged into main" transiently or by design
  (`develop`, `release/*` in the mountainash three-tier flow — see the sibling
  `2026-08-17-stale-release-candidates.md` item, which audits `release/*`
  branches from the opposite direction: not-yet-merged, not already-merged).
- **Mutation policy** — per this program's headless-contract convention
  (`lib/patterns/headless-contract.md`), branch deletion is a real,
  irreversible mutation; default posture should be `propose` or
  `allow-listed`, never `auto`, mirroring `stale-check.yaml`'s
  `mutation_allowlist: [comment, label]` pattern (deletion would need its own
  explicit allow-list entry or stay ask-gated).
- **Fleet aggregation** — one report/workflow across the configured repo
  catalog, not a single-repo script; likely fits the existing
  `templates/workflows/` + `skills/gh-workflows` pattern as a new template
  (e.g. `stale-branch-cleanup.yaml`) rather than folding into
  `stale-check.yaml`, since the trigger condition, data source, and mutation
  are all disjoint from that workflow.

## Evidence

- `templates/workflows/stale-check.yaml` (read in full) — `GATHER` step is
  `list open PRs not updated in the last 7 days` / `list open issues not
  updated in the last 14 days`; no branch-lifecycle awareness anywhere in the
  file.
- Grepped `stale_branch|merged_branch|delete_branch|branch_cleanup|dangling`
  across `lib/pulse/scripts/`, `skills/`, `docs/backlogs/`: zero matches.
- `docs/superpowers/archive/plans/2026-07-10-p5-pulse-scheduler.md:181-183`
  (archived 2026-08-17; original path
  `docs/superpowers/plans/2026-07-10-p5-pulse-scheduler.md:175-177`) —
  `stale_branches: [] # [{branch, pr_number, pr_age_days}] — unmerged
  {BRANCH_PREFIX}* branches` is the only near-hit in this repo's design
  history, but it's scoped exclusively to the pulse scheduler's own
  `.hiivmind/github` self-management branches (automation-config proposal
  branches), never a fleet-wide consumer-repo check — and it was never
  implemented (zero code references the field or the concept it names).
- `skills/gh-operations/SKILL.md`'s domain-routing table
  (`domains/branch-protection.md`) documents only
  `GET|PUT|DELETE /repos/{o}/{r}/branches/{branch}/protection` and its
  sub-resources — no `List branches`, `compare`, or `DELETE .../git/refs/`
  route exists anywhere in this skill's reference docs.
- `~/.claude/CLAUDE.md` (global rules, this session) — "Post-merge hygiene:
  `git checkout <base> && git pull --ff-only && git branch -d
  <feature-branch>` in both repos after every merge." This backlog item is
  exactly that manual per-session habit, surfaced and automated at fleet
  scale — catching branches a human or another agent's session forgot to
  clean up.

## Notes

No-spec. Needs a `brainstorming` pass to settle: (1) the staleness threshold
(immediate-on-merge vs. N-day grace period), (2) exclusion rules for
intentionally long-lived branch name patterns, and (3) whether this ships as
its own workflow template or as a new `stale-check.yaml` mode — the trigger
and data source argue for a separate template, but the UX ("stale things to
clean up") is conceptually adjacent enough to be worth deciding explicitly
rather than defaulting.
