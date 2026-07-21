# Backlog: F1–F8 phase deferrals (roll-up)

**Date:** 2026-07-22
**Status:** Open (index)
**Scope:** Every "deferred / out-of-scope / v1-limitation" item recorded in the
merged phase PRs #124–#134 (F0 → F8 of the fleet program). Captured so the
decisions survive outside PR history. Per-item severity noted inline.

This is an **index**, not a design doc. The one substantial cross-phase capability
(apply-mode) is called out first; the rest are small, additive, and mostly
inert until real adoption.

---

## 1. Apply-mode (the dominant deferral) — cross-phase, own future phase

**Severity:** Medium capability gap; **not** a correctness bug (propose-mode is
correct and safe).
**Source:** F6 (#130/#132), F7 (#133), F8 (#134) — the entire mutation stack is
**propose-only by explicit design**: "no commit or push ever happens without an
explicit later apply path."

F8 is the only phase that named the two concrete blockers for a real apply path:

1. **Apply-mode executor path** — the `plan-sync-doc-patch` transformation argv
   names a plugin-repo-relative script that will not resolve on `PATH` inside a
   doc pen checkout. Needs an installed entry point / `nave` subcommand.
2. **Apply-mode bound-path enforcement** — the F6 transformation registry
   allowlist + validation are static; the dynamic doc path is self-attested by
   the patch descriptor (`validation: none`). Needs an immutable per-proposal
   output allowlist enforced by the F6 orchestrator, plus a "path changed"
   validation kind.

Both are documented in `lib/patterns/plan-sync-binding.md`. **Recommendation:**
this is its own phase after F9, not a bolt-on — it touches F6 (orchestrator +
registry), the transformation packaging, and every propose-only consumer.

---

## 2. Nave release pinning — Pre-F4 (#128)

**Severity:** Low (local dogfooding unaffected).
Task 6 Step 4 (formal `discreteds/nave` release + pinning the minimum version)
is deferred; `dependency-evidence-contract.md` keeps `Minimum Nave version: TBD`.
A `cargo install --path` of the fork suffices locally (the runtime probe
auto-detects protocol 2). A tagged release must fill the pin **before any
capability needs to be installable elsewhere** (i.e. before there are external
consumers). Aligns with the current single-developer context.

---

## 3. F7 validator/manifest follow-ups (#133)

All additive, non-blocking; no real manifests exist pre-adoption.

- **3a. Manifest validity not enforced** *(Low; best small cleanup candidate)* —
  `generated.yaml` rules are documented (no duplicate `files[].path`, no empty
  `files[]`) but no loader/audit path rejects a malformed manifest.
- **3b. `proposals[].binding ∈ template-drift` cross-check** not enforced in the
  validator (plan scoped the validator without it).
- **3c. Standalone contract `gap` on a path-current edge** produces no finding
  (plan design; `contract_state` still carries the fact).
- **3d. `contract_versions` v1 limits** — RFC 6901 `~0`/`~1` escapes unhandled;
  PEP 440 `SpecifierSet` excludes prereleases by default.

---

## 4. F8 milestone dead-field (#134 review ledger, not in PR text)

**Severity:** Low (cosmetic / forward hook).
The `milestones` catalog tuple is fetched (and used as a fail-closed canary:
"catalog must be a list") but the tuple itself is dead-carried on
`DocumentSnapshot` — milestone is one-directional (GitHub→doc) in V1, so no
catalog-membership check is needed yet. Either consume it (a
milestone-not-in-catalog finding, needed if milestone becomes bidirectional) or
drop the field. Left as-is as a forward hook.

---

## Structural boundaries now satisfied (recorded, no action)

- **F0 (#124):** "repository and GitHub mutation out of scope for this phase" —
  later delivered by F6 (repo mutation) and F2+ (GitHub objects). ✅
- **F2 (#126):** "labels, milestones, schedulers, governance, checklists outside
  F2" — delivered across F3/F8 and the separate `hiivmind-pulse-scheduler` repo. ✅

---

## Not backlog (next phase)

F7's "Claude/corpus overlays are deferred to **F9**" is the **next planned
phase** (`docs/superpowers/plans/2026-07-13-f9-dogfood-overlays.md`), not a
backlog item.

---

## Suggested priority

1. **Apply-mode phase** — the one real capability gap (own phase, after F9).
2. **3a manifest validity** + **4 milestone dead-field** — cheap cleanup pass,
   whenever an F7/F8 file is next touched.
3. **2 Nave release pin** — when external installability first matters.
4. **3b–3d** — as the corresponding features gain real consumers.
