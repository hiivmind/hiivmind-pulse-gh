# Heterogeneous Fleet Management Program Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a general GitHub multi-repo fleet manager whose generic workflows dispatch through explicit repository profiles, Nave-backed evidence adapters, and separately enabled dogfood overlays.

**Architecture:** Pulse owns orchestration, bindings, profiles, scorecards, GitHub mutations, and result contracts. The installed `nave` CLI owns fleet projection, structural evidence, schema checks, and pen workspaces for repository-file transactions. Generic workflows load authoritative workspace profiles and dispatch adapter-specific checks; detected profiles remain proposals until merged as workspace metadata.

**Tech Stack:** Python 3.10+ PEP 723 scripts, PyYAML, pytest, `nave` CLI, gh CLI, git.

## Global Constraints

- Generic workflows never assume `.claude-plugin/`, `CLAUDE.md`, `SKILL.md`, `skills/`, `pyproject.toml`, or `package.json` exists.
- Workspace profile metadata is authoritative; detection may only emit `profile_proposal` plus `asks_recorded`.
- Result states are `pass | warn | fail | unknown | not_applicable | unsupported | error`; `not_applicable` and `unsupported` are excluded from score denominators.
- `unsupported` contributes to fleet coverage debt; it is never silently skipped.
- Nave is invoked as an external CLI. Pulse consumes only a versioned normalized JSON contract and supports fixture mode.
- Nave scan/pull are lifecycle commands; current Nave exposes JSON for search/build/check and pen state, but not scan/pull. Plans must not assume nonexistent `scan --json` or `pull --json` flags.
- Nave pens are the sole default transaction boundary for repository-file changes. Pulse remains the owner of GitHub API and workspace metadata mutations.
- Dogfood overlays are opt-in profiles and cannot affect repositories without those profiles.
- Durable markers live in committed workspace/artifact state; local Nave/Pulse caches are projections only.
- Every phase must add neutral fixtures, not only hiivmind plugin fixtures.
- `uv run pytest -q` and `git diff --check` must pass before each phase closes.

---

## Priority and order of operations

| Order | Plan | Priority | Why now | Unlocks |
|---:|---|---|---|---|
| F0 | Nave CLI protocol and evidence adapter | P0 | Establishes the real evidence boundary and removes duplicated fleet fetching | F1–F9 |
| F1 | Profiles, scorecards, applicability states | P0 | Makes repository intent explicit before any scoring or onboarding | F2–F9 |
| F2 | Generic fleet membership and profile proposals | P0 | Keeps fleet scope honest and assigns reviewed intent metadata | F3–F9 |
| F3 | Dispatched healthcheck shell and coverage report | P0 | Proves generic top-level dispatch without language assumptions | F4, F9 |
| Pre-F4 | Nave dependency evidence materialization | P0 | Adds authoritative, bounded file contents without exposing Nave cache internals or duplicating GitHub retrieval | F4 |
| F4 | Dependency coherence adapter family | P1 | First real language-dispatched workflow; validates Python/Node adapters over authoritative content evidence | future ecosystems |
| F5 | Generic impact bindings and branch currency | P1 | Highest-value generic cross-repo workflow; independent of repo language | F7, release gates |
| F6 | Nave pen mutation orchestration | P1 | Adds safe repository-file writes only after read/evaluate paths are stable | F7–F9 apply paths |
| F7 | Generic generated-artifact and contract specializations | P2 | Reuses F5 bindings and F6 pens; generator/parser behavior is adapter-driven | corpus overlay |
| F8 | Generic plan synchronization | P2 | Adds multi-master reconciliation after mutation and binding conventions prove out | milestone alignment |
| F9 | Hiivmind/Claude dogfood overlays | P2 | Exercises plugin-specific marketplace, Claude context, and generated-skill behavior without polluting core | self-governance |

### Dependency graph

```text
F0 Nave evidence ─────┐
                     ├─► F2 membership/profile proposals ─► F3 healthcheck dispatch ─► Pre-F4 materialization ─► F4 dependency adapters
F1 profiles/scorecards┘                                  └─► F9 dogfood checks

F5 impact bindings ────────────────┐
F6 Nave pen mutations ─────────────┼─► F7 generated artifacts/contracts
                                   └─► F8 plan sync

F2 + F3 + F6 ─────────────────────────► F9 dogfood overlays
```

F0 and F1 may be developed in parallel after their shared normalized evidence/profile interfaces are reviewed. F5 may begin after F1 because it is language-neutral, but it must not add a second repository checkout/cache mechanism. F6 waits for F0 so it can use Nave pens deliberately.

## Plans in this program

1. `2026-07-13-f0-nave-cli-evidence.md`
2. `2026-07-13-f1-profile-scorecard-core.md`
3. `2026-07-13-f2-fleet-membership-profiles.md`
4. `2026-07-13-f3-dispatched-healthchecks.md`
5. `2026-07-15-pre-f4-nave-dependency-evidence.md`
6. `2026-07-13-f4-dependency-adapters.md`
7. `2026-07-13-f5-impact-bindings.md`
8. `2026-07-13-f6-nave-pen-mutations.md`
9. `2026-07-13-f7-binding-specializations.md`
10. `2026-07-13-f8-plan-sync.md`
11. `2026-07-13-f9-dogfood-overlays.md`

The earlier W1–W9 plans are source material, not executable program order. W1/W2 assumed profile infrastructure that did not exist; W3/W8 were dogfood overlays presented as fleet defaults; W5 mixed a generic manifest with a Claude-skill generator. The F-series supersedes them.

## Phase gates

### Foundation gate — after F0–F3

- A fleet with Python, Node, documentation-only, infrastructure, archived, forked, and unclassified fixtures can be scanned and reported.
- Missing Nave degrades predictably.
- Every repository has an explicit scorecard or a pending profile proposal.
- No plugin-specific check runs on a repository without the corresponding profile.
- Fleet report separates score, scorecard identity, `not_applicable`, and coverage debt.

### General workflow gate — after F4–F6

- Dependency manifests and locks are materialized through a released Nave protocol-v2 capability; Pulse does not read Nave cache internals.
- Dependency coherence dispatches by ecosystem adapter.
- Unsupported ecosystems are visible without false failures.
- Impact audit detects path-scoped remote drift independent of language.
- Repository-file changes occur only inside Nave pens; GitHub mutations remain Pulse-owned.

### Binding/application gate — after F7–F8

- Generated-artifact drift uses configured generators rather than inferred skill layouts.
- Contract propagation reuses impact edges.
- Plan sync proves three-way reconciliation and idempotent marker advancement.

### Dogfood gate — after F9

- Marketplace, `CLAUDE.md`, plugin manifest, skill layout, and corpus generation checks apply only to explicit dogfood profiles.
- The plugin can score itself without changing the generic fleet scorecards.

## Deferred work requiring separate design approval

- Governance parity needs a golden governance specification and profile overlay design.
- Milestone alignment and changelog rollup remain gated on release-train P6.
- Private-repository Nave support is currently outside Nave's documented scope; Pulse must retain its GitHub-only path or contribute upstream support before claiming private-fleet evidence parity.
- Native Rust/library integration with Nave is deferred until the CLI protocol has proven stable and licensing/packaging are reviewed.

## Program close-out

- [ ] **Step 1: Verify every F-series plan has completed its own test and acceptance gates.**

Run: `uv run pytest -q`
Expected: all tests PASS.

- [ ] **Step 2: Verify no old universal plugin assumptions remain.**

Run: `rg -n 'Missing `CLAUDE.md` is a deterministic fail|classification.*plugin \| corpus-data|every repo.*skills' skills lib templates docs --glob '!docs/superpowers/plans/2026-07-13-w*.md'`
Expected: no matches.

- [ ] **Step 3: Verify documentation consistency.**

Run: `git diff --check`
Expected: no output and exit 0.

- [ ] **Step 4: Commit the program close-out.**

```bash
git add docs README.md SKILL.md
git commit -m "docs: complete heterogeneous fleet program"
```
