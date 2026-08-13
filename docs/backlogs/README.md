# hiivmind-pulse-gh — fleet program roadmap & backlog index

**Updated:** 2026-08-13 (F4 closed) · **One-page map of what is built, what is left, and where each item lives.**

> Read in this order: **Status at a glance** (what shipped) → **Layer-completeness matrix**
> (is it actually *runnable*) → **Cross-repo dependency map** (which repos an item spans) →
> **prioritized backlog**. The two matrices exist because "merged" kept hiding unbuilt runnable
> layers and cross-repo assumptions — see each section's callout.

The "F-series" fleet program built a control plane that reads/scores a repo fleet, proposes
guarded mutations, and (now) lands them. Most phases shipped as **tested libraries**; the
open work is about **making those libraries actually run end-to-end in production**, not just
pass in fixtures. The **propose** side now does (F10 closed 2026-07-30 — the F5–F9 audits run
on cadence and surface proposals in the maintenance PR); the remaining gap is the **apply**
side (F11 production wiring).

---

## Status at a glance

| Phase | What it does | State |
|---|---|---|
| F0 | Nave fleet evidence snapshot | ✅ merged (#124) |
| F1 | Profiles / scorecards / adapters | ✅ merged (#125) |
| F2 | Fleet membership + profile metadata | ✅ merged (#126) |
| F3 | Dispatched healthchecks | ✅ merged (#127) |
| Pre-F4 | Nave dependency **evidence** | ✅ merged (#128) |
| **F4** | Dependency-**coherence adapters** (consume the evidence) | ✅ merged (#142) |
| F5 | Impact bindings / `integration_tested_sha` markers | ✅ merged (#129) |
| F6 | Nave pen mutations (propose) | ✅ merged (#130/#132) |
| F7 | Binding specializations / generated artifacts | ✅ merged (#133) |
| F8 | Generic plan sync | ✅ merged (#134) |
| F9 | Dogfood overlays (Claude plugin/corpus) | ✅ merged (#136) |
| **F10** | **Runnable spine** (CLI drivers + triggers for F6–F9) | ✅ **complete** — spine #139; proposal fold #140; enrolled live (workspace #2). "Triggered end-to-end" gate **closed**. |
| F11 | Apply-mode (land a validated proposal) | ✅ merged (#138) — **library+tests; production wiring open** |

> **What "merged ✅" does and does not mean.** It means layers 1–3 (library →
> driver → skill) landed in **this repo**. It says nothing about whether the phase is
> *triggered* or *deployed to the live fleet* — the two layers that make it actually run.
> "F9 complete" read as done for weeks while F6–F9 had no driver at all. Read the
> **Layer-completeness matrix** below before trusting a ✅.

---

## Layer completeness — the "is it actually runnable?" matrix

Every phase is a five-layer ladder. A phase **runs in production** only when all five exist;
`merged ✅` above only asserts the first three, and only in `hiivmind-pulse-gh`.

1. **Library** — pure Python that owns the decisions (classify / count / gate / build proposal).
2. **Driver** — an argparse CLI (`*_run.py`) that assembles inputs, calls the library, writes + validates a result file.
3. **Skill** — a headless `SKILL.md` that *shells* the driver (`uv run …`), zero prompts. (A skill that cites a *function signature* instead of a command is not this layer — that was the F6–F9 trap.)
4. **Trigger** — a workflow definition (`session_poll` / `freshness` / `periodic`) or scheduler phase that invokes the skill unattended.
5. **Deployed** — that trigger **and** its config actually present in the **live workspace repo** (`hiivmind/hiivmind-workspace`, i.e. `~/git/hiivmind/.hiivmind/github/`), so a real cadence run exercises it.

| Phase | 1 Lib | 2 Driver | 3 Skill | 4 Trigger | 5 Deployed | Runs in prod? |
|---|:--:|:--:|:--:|:--:|:--:|---|
| F0 evidence | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (via healthcheck) |
| F1 profiles / scorecards | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (via healthcheck) |
| F2 fleet membership | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| F3 dispatched healthchecks | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (dogfooded) |
| Pre-F4 dependency **evidence** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (evidence only) |
| **F4 dependency-coherence adapters** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (via healthcheck; `python_manifest_lock_consistency` / `node_manifest_lock_consistency` / `fleet_dependency_coherence` scored) |
| F5 impact bindings | ✅ | ✅ | ✅ | ✅ `periodic` | ✅ (#2) | ✅ — `impact-audit` on cadence |
| F6 pen mutations | ✅ | ✅ (F10) | ✅ (F10) | ✅ `periodic` | ✅ (#2) | ✅ — proposals fold to PR body (#140) |
| F7 generated artifacts | ✅ | ✅ (F10) | ✅ (F10) | ✅ `periodic` | ✅ (#2) | ⚠️ enrolled; validated-abort until `generated.yaml` binding exists |
| F8 plan sync | ✅ | ✅ (F10) | ✅ (F10) | ✅ `periodic` | ✅ (#2) | ⚠️ enrolled; validated-abort until `plan-sync.yaml` binding exists |
| F9 dogfood overlays | ✅ | ✅ (F10) | ✅ (F10) | ✅ `periodic` | ✅ (#2) | ✅ — via healthcheck + `marketplace-sync` |
| **F10 runnable spine** | ✅ | ✅ | ✅ | ✅ `periodic` + 4 flips | ✅ (#2) | ✅ — **gate closed** (fold #140 + enroll #2) |
| F11 apply-mode | ✅ | ❌ no prod driver | ⚠️ entry points | ❌ | ❌ | ❌ — seams ship; nothing assembles `execute → reconcile` |

**Legend:** ✅ built & deployed · ⚠️ exists but not fully exercised yet · ❌ absent.

**F10 is closed: F5–F10 column 5 is now live** (proposal fold `hiivmind-pulse-gh` #140 +
enrollment `hiivmind/hiivmind-workspace` #2, both merged 2026-07-30). The remaining ⚠️ on F7/F8
is a *data* gap, not a code gap — the trigger fires but there is no bound work until the
`generated.yaml` / `plan-sync.yaml` binding files are added to the workspace (non-destructive
validated-abort until then). F11 is the only phase still dark on the runnable ladder.

### Two flow facts that broke specs on contact (record so they stop recurring)

Both are now resolved, but kept here because the *pattern* is the lesson.

- **The `automation.scheduled_workflows` list lives in the WORKSPACE repo, not the scheduler
  repo.** The scheduler's `TEMPLATE-workspace-maintenance.md` Phase 5b was already *generic*
  over that list; composing F6–F9 onto the cadence was a **workspace-config** edit (+ deploying
  the 4 YAMLs, #2), not a scheduler-repo change. The F10 scheduler-composition spec assumed the
  opposite — the whole "scheduler PR" was actually a pulse-gh + workspace change.
- **`gh-workflow-run-headless` did not fold an inner driver's `proposals[]` / `findings` into
  the outer `workflow-run-result.yaml`.** The executor's `INVOKE skill X` projection invoked the
  sibling and discarded its result envelope, so a scheduled F6–F9 run surfaced **zero**
  proposals. Fixed in #140 (`lib/pulse/scripts/subresult_fold.py` + executor prose) — a small
  **`hiivmind-pulse-gh`** change, exactly as the "layer 4 defect, not a scheduler change"
  diagnosis predicted.

---

## Cross-repo dependency map

Pulse spans **four repos with three different branch flows**. A spec authored in one repo that
assumes a sibling's shape is the second recurring failure mode; this map is the antidote.

```mermaid
graph LR
  PG["hiivmind-pulse-gh<br/>libraries · drivers · skills · executor<br/>workflow + config TEMPLATES<br/>flow: feature → develop → release → main"]
  SC["hiivmind-pulse-scheduler<br/>maintenance TEMPLATE (Phase 5b/6) · stubs<br/>prose-only, no test harness<br/>flow: feature → main"]
  WS["hiivmind/hiivmind-workspace<br/>~/git/hiivmind/.hiivmind/github/<br/>DEPLOYMENT TARGET — layer 5 lives here<br/>LIVE config · scheduled_workflows · deployed workflows/<br/>healthcheck.yaml · poll-state · gitignore<br/>flow: feature → main"]
  NV["discreteds/nave (fork)<br/>CLI evidence source · pen-clone substrate<br/>lifecycle protocol (upstream)"]

  PG -- "templates copied into" --> WS
  SC -- "Phase 5b iterates scheduled_workflows in" --> WS
  SC -- "CALL_SKILL into" --> PG
  PG -- "reads fleet evidence from" --> NV
```

**Repo nodes**

| Repo | Role | Branch flow | Test harness |
|---|---|---|---|
| `hiivmind-pulse-gh` (this) | Libraries, drivers, skills, executor, workflow/config **templates** | `feature → develop → release → main` (three-tier) | ✅ `lib/pulse/scripts/tests/` |
| `hiivmind-pulse-scheduler` | Maintenance **template** (Phase 5b runs `scheduled_workflows`; Phase 6 renders `proposed_actions`) + per-workspace stubs | `feature → main` | ❌ prose-only |
| `hiivmind/hiivmind-workspace` (`~/git/hiivmind/.hiivmind/github/`) | **Live** config: catalog, `automation.scheduled_workflows`, deployed `workflows/`, `healthcheck.yaml`, `poll-state`, `*-result.yaml` gitignore | `feature → main` | ❌ data repo |
| `discreteds/nave` (fork) | Fleet evidence source (F0); pen-clone substrate (apply-mode); lifecycle protocol | fork PRs | n/a |

**Item → repos it spans** (the decomposition to do *before* branching):

| Open item | pulse-gh | scheduler | workspace | nave | The gotcha |
|---|:--:|:--:|:--:|:--:|---|
| **F10 triggered end-to-end** | ✅ **folding fix (real work)** | ○ generic already; doc-only | ✅ enroll list + deploy 4 YAMLs | — | list + deploy live in **workspace**; the code fix is in **pulse-gh** |
| **Apply-mode production wiring** | ✅ assembly driver | — | ✅ real F5/F8 base-writer | ✅ pen-clone → `PULSE_PEN_ROOT/{owner}/{name}` bridge | 3-repo; no single-repo PR closes it |
| ~~**F4 dependency-coherence adapters**~~ ✅ **DONE** | ✅ adapters | — | ○ evidence already present | ○ evidence source | mostly pulse-gh; evidence already flows |
| **`relationships.yaml` schema drift** | ✅ | — | — | — | 1-repo (needs schema-vs-evaluator ruling) |
| **Stale workspace catalog** | — | — | ✅ data fix | — | 1-repo, **data not code** |
| **Nave lifecycle protocol** | — | — | — | ✅ upstream | 1-repo, gated on nave |

---

## The open backlog, prioritized

### 🔴 P1 — "Make it run in production" (the dominant gap)
The libraries exist; the *propose* side now runs on cadence (F10 closed 2026-07-30). The
**apply** side is the remaining production-wiring gap.

| Item | Why it matters | Source |
|---|---|---|
| ~~**F10 last mile: proposal folding + live enrollment**~~ ✅ **DONE 2026-07-30** | Proposal fold (#140) + live enrollment (workspace #2) merged; F10's "triggered end-to-end" gate is closed. The propose/mutate phases F5–F9 now run daily and surface proposals in the maintenance PR body. | `2026-07-29-f10-scheduler-composition.md` · `2026-07-30-f10-followups.md` |
| **Apply-mode production wiring** | F11's apply side still has the gap: real seams ship (`apply_ops`, `advance_base`, clone reader, `gh` ops) but no driver assembles them into a live `execute → reconcile` run; no real F5/F8 base-writer; no bridge from Nave pen clones to the `PULSE_PEN_ROOT` contract. **The top P1.** A single-mutator (PR #141 decision, "Nave owns all clone writes") implementation plan for the pulse-gh half is written and reviewed: `2026-07-30-apply-mode-pulse-wiring.md`; the Nave-verb half is a separate `discreteds/nave` fork plan the pulse-gh plan's Task 1 contract is written against. | [`2026-07-30-apply-mode-pulse-wiring.md`](../superpowers/plans/2026-07-30-apply-mode-pulse-wiring.md) · [`2026-07-30-apply-mode-production-wiring-design.md`](../superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md) · [`2026-07-30-f11-apply-git-consolidation-note.md`](../superpowers/specs/2026-07-30-f11-apply-git-consolidation-note.md) · [`2026-07-29-apply-mode-v2-deferrals.md`](2026-07-29-apply-mode-v2-deferrals.md) § A
| ~~**F4 dependency-coherence adapters**~~ ✅ **DONE 2026-08-13** | Pre-F4 materialized the evidence; the coherence adapters that consume it are merged (#142). Closed the read-spine gap and unlocked the flagship neutral apply use-case (fleet-wide dependency bump + lockfile landing) as a future apply-mode consumer. | [`2026-07-13-f4-dependency-adapters.md`](../superpowers/plans/2026-07-13-f4-dependency-adapters.md) · [`2026-08-13-f4-deferred-scope.md`](2026-08-13-f4-deferred-scope.md)

### 🟠 P2 — Correctness / data (cheap, one is a real bug)
| Item | Why it matters | Source |
|---|---|---|
| **`relationships.yaml` schema drift** | Produces a **wrong healthcheck result** — the only active correctness bug. Needs a decision on which side (schema vs `evaluate_checks.py`) is authoritative. | [`2026-07-11-relationships-schema-drift.md`](2026-07-11-relationships-schema-drift.md) |
| **Stale workspace repo catalog** | Wrong repo catalog in the dogfood workspace config (`~/git/hiivmind/.hiivmind/github/config.yaml`) — data, not code. | [`2026-07-11-workspace-config-stale-catalog.md`](2026-07-11-workspace-config-stale-catalog.md) |

### 🟡 P3 — Nave / upstream / installability
| Item | Why it matters | Source |
|---|---|---|
| **Nave machine-readable lifecycle protocol** | Upstream proposal to the nave fork (`capabilities`/`scan`/`pull --json`). Depends on nave, not pure pulse work. | [`2026-07-13-nave-json-lifecycle-protocol.md`](2026-07-13-nave-json-lifecycle-protocol.md) |
| **Nave release pinning** | Tag a `discreteds/nave` release + fill `Minimum Nave version: TBD`. Needed only before external installability (single-developer today). | [`2026-07-22-f1-f8-phase-deferrals.md`](2026-07-22-f1-f8-phase-deferrals.md) § 2 |

### 🟢 P4 — Small cleanups (no real consumer yet)
| Item | Source |
|---|---|
| **F7 validator/manifest follow-ups** — 3a manifest-validity enforcement (best small cleanup), 3b–3d validator edge limits | [`2026-07-22-f1-f8-phase-deferrals.md`](2026-07-22-f1-f8-phase-deferrals.md) § 3 |
| **F8 milestone dead-field** — cosmetic forward hook (dead-carried catalog tuple) | [`2026-07-22-f1-f8-phase-deferrals.md`](2026-07-22-f1-f8-phase-deferrals.md) § 4 |

### 🔵 v2 — deferred by design boundary
| Item | Source |
|---|---|
| **`allow` (unattended direct push) + scheduled auto-apply** — behind `allow_scheduled` + a workspace apply policy; the confirmation model changes, so **design first** | [`2026-07-29-apply-mode-v2-deferrals.md`](2026-07-29-apply-mode-v2-deferrals.md) § B |
| **Single-repo-atomic Path A push** — only if a future Nave surface yields per-repo exec signal | [`2026-07-29-apply-mode-v2-deferrals.md`](2026-07-29-apply-mode-v2-deferrals.md) § B |

### ⚪ Non-goals & tooling (recorded so they aren't re-proposed)
- **Auto-merge** — permanent non-goal; Pulse opens PRs and detects merges, never merges. ([apply-mode v2](2026-07-29-apply-mode-v2-deferrals.md) § C)
- **agy `write_file` permission drift** — a `swingle-verify agy` item in the sdd-dispatch plugin, **not** a hiivmind-pulse-gh change. ([apply-mode v2](2026-07-29-apply-mode-v2-deferrals.md) § E)

---

## Suggested sequencing

1. ~~**F10 last mile**~~ — ✅ done 2026-07-30 (fold #140 + enroll #2); the propose side runs on cadence.
2. ~~**F4 adapters**~~ — ✅ done 2026-08-13 (#142); read-spine gap closed.
3. **Apply-mode production wiring** — the apply-side spine (3-repo: pulse-gh driver + nave clone bridge + workspace base-writer). **The top open item.** The pulse-gh-half implementation plan is written and reviewed (`2026-07-30-apply-mode-pulse-wiring.md`); the Nave-verb half needs its own fork plan against that plan's Task 1 contract before the pulse-gh driver can land end-to-end.
4. **`relationships.yaml` schema drift** — cheap, and the one live correctness bug.
5. **Binding files for the enrolled F7/F8 audits** — add `generated.yaml` / `plan-sync.yaml` to the workspace so `generated-artifact-audit` / `plan-sync` have real work instead of validated-abort. Data, when there's something to bind.
6. Everything else as its feature gains a real consumer.

> **Before branching any multi-repo item, decompose it through the Cross-repo dependency map
> above** — which repos it spans, which sibling shape it assumes, and which branch flow each PR
> targets. The two recurring failures (a whole runnable layer silently unbuilt; a spec assuming
> the wrong repo) both come from skipping this step.

## Backlog docs (full detail lives here)
- [`2026-08-13-f4-deferred-scope.md`](2026-08-13-f4-deferred-scope.md) — F4 v1 scope cuts (Conda, cardinality, F11 handoff, per-package overrides) deferred from the post-review plan revision
- [`2026-07-29-apply-mode-v2-deferrals.md`](2026-07-29-apply-mode-v2-deferrals.md) — apply-mode (F11) v2 / production-wiring / dependent items
- [`2026-07-22-f1-f8-phase-deferrals.md`](2026-07-22-f1-f8-phase-deferrals.md) — F1–F8 roll-up (apply-mode #1 now ✅ resolved; #2–#4 open)
- [`2026-07-13-nave-json-lifecycle-protocol.md`](2026-07-13-nave-json-lifecycle-protocol.md) — upstream Nave protocol proposal
- [`2026-07-11-relationships-schema-drift.md`](2026-07-11-relationships-schema-drift.md) — schema-drift correctness bug
- [`2026-07-11-workspace-config-stale-catalog.md`](2026-07-11-workspace-config-stale-catalog.md) — stale workspace data

> Design-of-record for built/planned phases lives under `../superpowers/plans/` and
> `../superpowers/specs/`; audits under `../superpowers/audits/`. This index only tracks
> **open work**; per-phase "what/how" is in `../f-series-explained.md`.
