# hiivmind-pulse-gh — fleet program roadmap & backlog index

**Updated:** 2026-07-29 · **One-page map of what is built, what is left, and where each item lives.**

The "F-series" fleet program built a control plane that reads/scores a repo fleet, proposes
guarded mutations, and (now) lands them. Most phases shipped as **tested libraries**; the
open work is dominated by one theme — **making the propose/mutate/apply phases actually run
end-to-end in production**, not just pass in fixtures.

---

## Status at a glance

| Phase | What it does | State |
|---|---|---|
| F0 | Nave fleet evidence snapshot | ✅ merged (#124) |
| F1 | Profiles / scorecards / adapters | ✅ merged (#125) |
| F2 | Fleet membership + profile metadata | ✅ merged (#126) |
| F3 | Dispatched healthchecks | ✅ merged (#127) |
| Pre-F4 | Nave dependency **evidence** | ✅ merged (#128) |
| **F4** | Dependency-**coherence adapters** (consume the evidence) | ❌ **never built** — `dependency-updates` = `unsupported` |
| F5 | Impact bindings / `integration_tested_sha` markers | ✅ merged (#129) |
| F6 | Nave pen mutations (propose) | ✅ merged (#130/#132) |
| F7 | Binding specializations / generated artifacts | ✅ merged (#133) |
| F8 | Generic plan sync | ✅ merged (#134) |
| F9 | Dogfood overlays (Claude plugin/corpus) | ✅ merged (#136) |
| **F10** | **Runnable spine** (CLI drivers + triggers for F6–F9) | 📝 **planned, NOT built** |
| F11 | Apply-mode (land a validated proposal) | ✅ merged (#138) — **library+tests; production wiring open** |

---

## The open backlog, prioritized

### 🔴 P1 — "Make it run in production" (the dominant gap)
The libraries exist; nothing drives them against a live fleet. These three are related.

| Item | Why it matters | Source |
|---|---|---|
| **F10 runnable spine** | F6–F9 have **no CLI drivers, no triggers**; `pen_orchestrator.execute` has no production caller. The propose/mutate phases can't run outside tests. **Prerequisite for everything below.** | `../superpowers/plans/2026-07-22-f10-runnable-spine.md` · audit `../superpowers/audits/2026-07-22-f-series-runnable-spine-audit.md` |
| **Apply-mode production wiring** | F11's apply side has the same gap: real seams ship (`apply_ops`, `advance_base`, clone reader, `gh` ops) but no driver assembles them into a live `execute → reconcile` run; no real F5/F8 base-writer; no bridge from Nave pen clones to the `PULSE_PEN_ROOT` contract. | [`2026-07-29-apply-mode-v2-deferrals.md`](2026-07-29-apply-mode-v2-deferrals.md) § A |
| **F4 dependency-coherence adapters** | Never built — Pre-F4 materialized the evidence, the adapters that consume it were skipped. Closes a read-spine gap **and** unlocks the flagship neutral apply use-case (fleet-wide dependency bump + lockfile landing). | this index (row above) · [`2026-07-29-apply-mode-v2-deferrals.md`](2026-07-29-apply-mode-v2-deferrals.md) § D |

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

1. **F10 runnable spine** — unlocks running F6–F9 (and, with the apply wiring, F11) for real.
2. **Apply-mode production wiring** — the apply-side spine; pairs naturally with F10.
3. **F4 adapters** — read-spine gap + the flagship neutral apply use-case.
4. **`relationships.yaml` schema drift** — cheap, and the one live correctness bug.
5. Everything else as its feature gains a real consumer.

## Backlog docs (full detail lives here)
- [`2026-07-29-apply-mode-v2-deferrals.md`](2026-07-29-apply-mode-v2-deferrals.md) — apply-mode (F11) v2 / production-wiring / dependent items
- [`2026-07-22-f1-f8-phase-deferrals.md`](2026-07-22-f1-f8-phase-deferrals.md) — F1–F8 roll-up (apply-mode #1 now ✅ resolved; #2–#4 open)
- [`2026-07-13-nave-json-lifecycle-protocol.md`](2026-07-13-nave-json-lifecycle-protocol.md) — upstream Nave protocol proposal
- [`2026-07-11-relationships-schema-drift.md`](2026-07-11-relationships-schema-drift.md) — schema-drift correctness bug
- [`2026-07-11-workspace-config-stale-catalog.md`](2026-07-11-workspace-config-stale-catalog.md) — stale workspace data

> Design-of-record for built/planned phases lives under `../superpowers/plans/` and
> `../superpowers/specs/`; audits under `../superpowers/audits/`. This index only tracks
> **open work**; per-phase "what/how" is in `../f-series-explained.md`.
