# Backlog: fleet-wide branch-protection / ruleset governance parity

**Date:** 2026-08-17
**Status:** Open, no spec
**Severity:** Governance gap — repos can silently diverge from any intended protection
standard; not a bug in existing code
**Found in:** review of an orphaned design idea (§3.6.3 `governance-parity`,
`docs/superpowers/specs/2026-07-10-lockstep-bindings-and-target-workflows-design.md`,
now retired to `docs/superpowers/archive/specs/`) against the actual gap surfaced by
today's branch-protection/branch-name-filter investigation
**Scope:** `gh-healthcheck` (upgrades the existing read-only check), a new "golden spec"
config artifact in the workspace repo, `skills/gh-operations` (existing write routes
already suffice — see below)

## Problem

`gh-healthcheck` (`evaluate_checks.check_branch_protection`,
`adapters/generic.py:branch_protection`) only ever answers "is the default
branch protected, yes/no/how" for one repo at a time. It cannot answer "does
`release/*` require the same protection as `main`, and is that consistent
across the fleet" — there is no concept of a declared standard to check
against, only a per-repo pass/warn/fail.

## The idea, and what's still good about it

An earlier design (§3.6.3 `governance-parity`, written 2026-07-10) proposed
exactly the right shape: a **golden governance spec** (declared standard,
living in the workspace repo alongside the rest of live fleet config) ↔ each
repo's live settings, reconciled the same way this program already
reconciles dep-coherence, plan-sync, and scaffold-drift — by upgrading
healthcheck from "score" to "diff against a standard and propose fixes."
That core shape is correct and matches this program's established pattern;
no reason to invent something different.

It never shipped. Its own tracking table left it `status: proposed`, and it
sat un-cross-referenced from the active backlog index until today.

## What's now known that the original design didn't have

- **Its stated blockers are gone.** The design listed prereqs `P3.2`
  (healthcheck-headless) and `P4` (executor + headless mutation policy) as
  open. Both shipped 2026-07-11/12 — over a month before this review. The
  design reads as blocked; it isn't. The only real blocker was always "needs
  the design conversation," which is what this document is.
- **No `repo-class` taxonomy exists to build "overlays" on.** The design
  assumed "org base + repo-class overlays" (per-class policy variants) as if
  repo classification data already existed. It doesn't — grepped
  `lib/pulse/scripts/adapters/`, `poll.py`, and the config schema: nothing
  classifies a repo as plugin/app/data/etc. today. Per-class overlays are a
  from-scratch design decision now, not a detail to fill in.
- **The write primitive already exists.** `skills/gh-operations`'s domain
  routing table (`lib/references/domains/branch-protection.md`) already
  documents `GET`/`PUT`/`DELETE
  /repos/{owner}/{repo}/branches/{branch}/protection` for **any named
  branch**, not just the default — and `rulesets` create/update via `gh
  ruleset` is likewise already an operations domain. A reconciliation
  mutation doesn't need new API plumbing, just a proposal-generation layer
  that calls what already exists, under the same `propose`/`allow-listed`
  headless mutation policy every other apply-mode surface uses.
- **The evaluator already treats classic protection and rulesets as
  competing, mutually-substitutable mechanisms** (`adapters/generic.py`:
  ruleset OR classic protection, whichever's active, is sufficient). A golden
  spec needs to declare policy in a mechanism-agnostic way (e.g. "N required
  reviews on `main`" — not "a classic-protection object with these exact
  fields") so it doesn't force every repo onto one mechanism. The original
  design never addressed this.
- **The bundle scope (protection + rulesets + merge settings + label
  taxonomy in one golden spec) was never validated against a real gap.**
  Only the protection/rulesets slice has a demonstrated, concrete failure
  mode (branch-name-filter drift, found today). Merge settings (squash
  policy, delete-on-merge) and label taxonomy were carried over from the
  original design without evidence they're under-covered the same way — v1
  scope should be revisited rather than assumed.

## What this would require (real scope, not exhaustive by design)

- **A golden-spec schema and location** — living in the workspace repo
  (`~/git/hiivmind/.hiivmind/github/`, alongside `automation.scheduled_workflows`,
  the repo catalog, `relationships.yaml`), declaring policy per branch-name
  pattern (not just "the default branch"), mechanism-agnostically.
- **A decision on v1 scope** — branch protection/rulesets only (matches the
  demonstrated gap), vs. the original full bundle (protection + rulesets +
  merge settings + label taxonomy). Recommend starting narrow; the wider
  bundle can be a follow-up entry once this proves out, same as every other
  workflow in this program's catalog convention.
- **A decision on `repo-class` overlays** — build a real taxonomy now
  (which classes, who assigns them, where they live), or ship v1 as one
  global policy and add overlays only once a concrete need for per-class
  variance appears (this program's F-series has consistently proven out
  narrow-then-general working better than speculative generality up front).
- **The reconciliation/mutation layer** — a new healthcheck-adjacent check
  (or a dedicated workflow) that diffs live settings against the golden spec
  and emits `proposed_actions`, applied via the existing `gh-operations`
  branch-protection/rulesets write routes under `propose`/`allow-listed`
  mutation policy — never `auto` for something that gates who can merge.
- **Fleet-wide reporting** — one roll-up across the repo catalog (which
  repos are compliant, which drifted, on which branch pattern), not a
  per-repo-only view.

## Evidence

- `lib/pulse/scripts/evaluate_checks.py:183-197` (`check_branch_protection`)
  and `lib/pulse/scripts/adapters/generic.py:225-307` (`branch_protection`) —
  both scoped to the default branch only; confirmed via
  `gh-healthcheck`'s own documented output format, `"main: 1 required
  review"` (`skills/gh-healthcheck/SKILL.md:214`).
- `lib/pulse/scripts/adapters/generic.py:167-222`
  (`_default_branch_ruleset_match`) — full GitHub ruleset glob matcher
  (`*`, `**`, `?`, exclude-overrides, tested in
  `tests/test_generic_adapters.py`), used solely to confirm an active
  ruleset covers the default branch; never surfaces the configured patterns
  as a fact, never checks any other branch.
- `lib/references/domains/branch-protection.md:22-29` — the write routes
  this reconciliation layer would call already exist and are documented,
  including per-named-branch (not just default) protection endpoints.
- `docs/superpowers/archive/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
  §8.9 tracking table — `P4` done 2026-07-11; `P3.2` (part of `P3`) done
  2026-07-11. Confirms governance-parity's stated blockers cleared over a
  month ago.
- Grepped `repo_class`/`kind`/profile-taxonomy across
  `lib/pulse/scripts/adapters/`, `poll.py`: zero matches — no existing
  foundation for "repo-class overlays."

## Notes

No-spec. This document supersedes the retired §3.6.3 as the live record of
this idea — the original is archived at
`docs/superpowers/archive/specs/2026-07-10-lockstep-bindings-and-target-workflows-design.md`
for historical reference, not deleted. Needs a `brainstorming` pass to settle
v1 scope (protection/rulesets-only vs. full bundle) and the repo-class
overlay question before a spec is written.
