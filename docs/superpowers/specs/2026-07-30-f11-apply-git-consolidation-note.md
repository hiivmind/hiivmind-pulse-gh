# F11 design note: consolidate apply-mode git mutation into Nave

**Status:** proposed · **Date:** 2026-07-30 · **Amends:** `2026-07-22-apply-mode-design.md` (Path A)
**Related:** `lib/patterns/repository-mutations.md` (C1, C2), `nave_adapter.py`, `pen_clone_reader.py`

## Problem

Path A apply currently plans to mutate fleet clones through two independent systems:

1. **Nave** owns the clone lifecycle end to end — fleet discovery (`scan`), refresh
   (`pull`), pen creation, and command execution inside pen checkouts (`pen exec`,
   including its own `--commit` / `--push-changes` flags).
2. **Raw git in Python** — the apply trio in `nave_adapter.py`
   (`provision_apply_branch`, `commit_apply_clones`, `push_apply_clones`) runs
   `git checkout -b` / `git add -A && git commit` / `git push origin` directly against
   the same clones, beside Nave's back.

Two writers over one set of clones is a structural hazard, independent of either
writer's correctness:

- **State divergence.** Nave's pen state (`pen status`) is derived from its own view of
  each checkout. Branches created and commits made by raw git are invisible to that
  model until the next status read, and a mid-apply failure leaves clones in a state
  neither system claims (e.g. three repos on `pulse/apply/{id}`, one still on the base
  branch — `provision_apply_branch` has no rollback).
- **Duplicate policy enforcement.** The propose-only default is enforced twice with
  different mechanisms: `pen_exec` refuses to emit `--commit`/`--push-changes`, while
  the raw-git trio is kept unreachable by the F10 import-boundary test. Every future
  policy change must be made twice, consistently.
- **Blunt staging.** `commit_apply_clones` uses `git add -A`, committing anything dirty
  or untracked in the clone — not just the proposal's `bound_paths`. The
  `paths_changed` validation upstream mitigates this only when it is guaranteed to run
  first; the commit step itself has no bound-path knowledge.

The trio has **no production callers today** (F11 wiring is pending; only tests and
`repository-mutations.md` reference it), so this is the cheapest moment to change
course.

## Recommendation

**Exactly one system mutates fleet clones: Nave.** Extend Nave's pen surface to cover
the three apply-mode needs the trio was written for, then delete the trio. Pulse's
Python keeps orchestration, policy, and read-only verification; it stops running write
git commands entirely.

### Required Nave capabilities

These are pen-domain capabilities in their own right — any multi-repo pen consumer
that wants guarded, reviewable mutation needs them, not just Pulse:

1. **Branch provisioning at a guarded base** —
   `nave pen branch <pen> --name pulse/apply/{proposal_id} --at <sha-per-repo>` (or a
   `--base-sha-file` mapping for per-repo SHAs). Semantics per C1: create the branch off
   the expected base SHA in every selected repo; fail closed per repo if the branch
   exists or the SHA is missing, reporting per-repo results as JSON (`--json`). This is
   the one capability the current `pen exec --commit` path cannot express and the
   reason the raw-git trio was written.
2. **Bounded staging on commit** —
   `pen exec --commit --paths <repo-relative-glob>...` (or accept the proposal's
   `bound_paths` as an explicit stage list). Replaces `add -A` semantics: only bound
   paths are staged; anything else dirty in the clone fails the commit closed rather
   than riding along.
3. **Structured commit/push results** — `pen exec --commit`/`--push-changes` (and the
   new `branch` subcommand) emit per-repo machine-readable outcomes (`--json`), so the
   orchestrator's attribution record is built from typed results, not exit codes plus
   opaque stdout. This matches the existing adapter contract (stdout of non-`--json`
   commands is never parsed as data).
4. **Cross-repo atomicity story** — at minimum, a documented `--keep-going`/fail-fast
   choice plus a `nave pen reset <pen> --branch <name>` cleanup verb so a partial
   provision or partial push can be unwound deterministically. Full transactional
   apply across repos is out of scope; deterministic cleanup is not.

### Pulse-side changes once Nave lands these

- **Delete** `provision_apply_branch`, `commit_apply_clones`, `push_apply_clones`
  (`nave_adapter.py:500–616`) and their tests; add thin adapter functions for the new
  Nave verbs following the existing `pen_exec`/`pen_status` idiom (argv construction +
  `--json` decode, fixture-testable via `PULSE_NAVE_FIXTURES`).
- **Policy gate stays in one place:** the orchestrator remains propose-only
  unconditionally; the F11 apply driver is the sole caller allowed to pass
  commit/push/branch flags, authorized by a validated `mutation_policy`. The
  import-boundary test contracts from guarding four raw-git names to guarding the
  single apply driver.
- **`repository-mutations.md` C1** updates its *Implementation* line from
  `nave_adapter.provision_apply_branch(...)` to the Nave verb; the invariant text
  (per-proposal branch `pulse/apply/{proposal_id}` off `expected_shas[repo]`, pushes
  never target a default branch) is unchanged.

### What stays in Python, deliberately

- **`pen_clone_reader.py`** — read-only seams (`rev-parse HEAD`, `status --porcelain`,
  bounded file reads). These exist so the orchestrator's fail-closed guards
  (expected-SHA, `paths_changed`, `json_schema`) verify clones *independently of the
  system that mutates them*. Keeping verification out-of-band of Nave is a feature:
  the checker and the writer should not share an implementation. No change.
- **`pen_orchestrator.py`** — pure state machine, no subprocess; unchanged.
- **Path B (`object_apply.py`)** — GitHub-object writes via `gh`; no local git,
  independent of this note per B4.

## Interim rule (until the Nave verbs exist)

If F11 wiring must land before Nave grows the capabilities above, the trio may be
wired as specified in `repository-mutations.md` — but treat it as a tracked stopgap:

- Fix `commit_apply_clones` to stage `bound_paths` explicitly instead of `add -A`.
- File the Nave feature request (capabilities 1–4 above) at the same time the driver
  lands, and record the trio's deletion as the closing task of that issue.

## Explicit non-goals

- Moving apply-mode git into the interactive LLM session. Headless apply is
  deliberately model-free: deterministic, fixture-testable, fail-closed. The
  interactive skills already let the model drive git directly; that split stands.
- Replacing Nave pens with `git worktree` / the superpowers worktrees plugin. Worktrees
  give single-repo, single-session isolation; pens are cross-repo fleet checkouts for
  unattended runs. Different domain, no overlap to consolidate.

## Open questions

1. Should branch provisioning be a new `pen branch` subcommand or flags on
   `pen exec` (`--branch <name> --at <sha>` provisioning before the exec)? A separate
   verb keeps provisioning independently retryable and separately reportable, and is
   the recommended shape.
2. Per-repo base SHAs: flag-per-repo is awkward at fleet scale — is a JSON/YAML
   request file (mirroring `materialize --request`) the right carrier?
3. Does `pen exec --push-changes` today set an upstream and report the remote branch
   ref, which the PR-first step (apply = branch + PR per the F11 decision table)
   needs as input?
