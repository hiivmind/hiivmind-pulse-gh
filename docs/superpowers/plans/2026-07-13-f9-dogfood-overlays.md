# F9: Hiivmind and Claude Dogfood Overlays Implementation Plan

> **Execution mode (revised 2026-07-19):** execute directly in a single session on the
> main thread — no per-task subagents, no per-task reviewers. TDD per task, one commit
> per task, one adversarial whole-branch review at the end of the phase, then PR.
> Stacked branch `feat/f9-dogfood-overlays` off the F8 head.

**Goal:** Add marketplace, Claude context, plugin layout, and corpus generated-skill behavior as explicitly enabled profiles and adapters without changing generic fleet semantics.

**Architecture:** A `claude-plugin-v1` scorecard extends the neutral scorecard set with plugin-specific adapters. Marketplace sync is a release-artifact comparator emitting an F6 mutation proposal; Claude context currency is `not_applicable` without the capability; corpus regeneration is one configured F7 generator executed through F6. All overlay fixtures live under `tests/fixtures/overlays/`, separate from neutral fleet fixtures.

**Tech Stack:** Python 3.10+, PyYAML, pytest, gh CLI, F1/F3/F6/F7.

## What already exists (verified 2026-07-19, F6 head)

- `lib/pulse/scripts/profile_dispatch.py` — `load_profiles`, `resolve_scorecard`, `dispatch(repo, evidence, config) -> DispatchPlan`; applicability grammar `always | profile:<id> | capability:<id> | evidence_path:<glob>`.
- `lib/pulse/scripts/adapters/` — `generic.py` (adapters take `CheckContext`, return dicts folded into `CheckBlock` with evidence citations); explicit registration in `adapters/__init__.py::register_universal_adapters(registry)`. New overlay adapters follow this exact registration pattern — a separate `register_claude_adapters(registry)` entry point, called only when the overlay is enabled.
- `templates/profiles.yaml.template` — `scorecards:` with per-check `{id, adapter, applicability, weight}`; `proposal_rules:` already contains `claude-plugin-layout` (profile `claude-plugin`, `all_paths: [.claude-plugin/plugin.json, "skills/*/SKILL.md"]`) — Task 1 gives that profile its scorecard.
- `lib/pulse/scripts/check_adapters.py` — `AdapterRegistry.evaluate` wraps adapter output into `CheckBlock`; `status` vocabulary includes `not_applicable`.
- F6: `mutation_plan.build_proposal` / `pen_orchestrator.execute`; F7 (once landed): `generators.yaml.template` + `generator_dispatch.dispatch`, `generated_artifacts.audit`.

## Global Constraints

- No overlay runs without an explicit profile/capability — nothing in the neutral path may import an overlay module.
- Missing `CLAUDE.md` fails only when the selected scorecard requires Claude context; otherwise no Claude check block is dispatched at all (not even `not_applicable` noise on non-Claude repos — the dispatch filter handles it).
- Marketplace sync applies only to repositories with a configured marketplace binding.
- Generated-skill regeneration is one configured F7 generator, not a generic default.
- Overlay scores identify their scorecard and are never merged into a neutral scorecard denominator.

---

### Task 1: Add Claude plugin scorecards and adapters

**Files:**
- Modify: `templates/profiles.yaml.template`
- Create: `lib/pulse/scripts/adapters/claude_plugin.py`
- Modify: `lib/pulse/scripts/adapters/__init__.py`
- Create: `lib/pulse/scripts/tests/test_claude_plugin_adapter.py`
- Create: `lib/pulse/scripts/tests/fixtures/overlays/claude-plugin/`

**Interfaces:**
- Adapters (each `(context: CheckContext) -> dict`, registered via a new `register_claude_adapters(registry)`):
  - `claude.plugin_manifest` — `.claude-plugin/plugin.json` exists, parses, has `name` + `version`; malformed JSON → fail with cited evidence path.
  - `claude.skills` — every `skills/*/SKILL.md` has frontmatter with `name` + `description`; malformed frontmatter → fail citing the file; no skills dir on a plugin repo → fail (a plugin claims skills by layout).
  - `claude.context` — `CLAUDE.md` present and its inventory claims current (delegates detail to Task 3; in Task 1 it checks presence only, returns `not_applicable` when the scorecard doesn't require it).
- Scorecard `claude-plugin-v1` in the template: extends the generic checks (documentation, ci, license…) plus the three adapters above with `applicability: profile:claude-plugin`.
- Evidence source: the same evidence snapshot shape `dispatch` already consumes (file lists + file content via `CheckContext`); fixtures provide it — no live git/gh in tests.

**Steps:**
- [ ] **Step 1: Fixtures/tests** — valid plugin; missing manifest; malformed skill frontmatter; stale CLAUDE inventory (Task 3 wires the real check; here a placeholder fixture); plain Python repo.
- [ ] **Step 2: Verify red, implement** adapters with cited evidence (match `generic.py`'s `_result`/citation idioms).
- [ ] **Step 3: Isolation assertion** — dispatch a plain Python repo (profile `python`) against the full config: the DispatchPlan contains zero `claude.*` checks.
- [ ] **Step 4: Run tests and commit** with `feat: add explicit Claude plugin scorecard`.

---

### Task 2: Add marketplace release binding

**Files:**
- Create: `lib/pulse/scripts/marketplace_sync.py`
- Create: `lib/pulse/scripts/tests/test_marketplace_sync.py`
- Create: `skills/gh-marketplace-sync-headless/SKILL.md`
- Create: `templates/workflows/marketplace-sync.yaml`
- Modify: `templates/transformations.yaml.template`

**Interfaces:**
- Binding (workspace config): `{plugin_id, repo (owner/name), marketplace_repo, marketplace_file}`.
- `compare(binding, releases, marketplace_doc) -> MarketplaceDrift` — pure. `releases` is the plugin repo's release list (gh shapes, fixture-driven); the newest **stable** release (exclude `prerelease: true` and `draft: true`) is compared to the version recorded for `plugin_id` in `marketplace_doc` (parsed YAML/JSON of `marketplace_file`). Outcomes: `in_sync`, `drift` (+ F6 proposal), `missing_entry` (plugin absent from the file → drift with an add), `not_applicable` (no binding for the repo), `unknown` (no stable release / unparseable file — fail closed, no proposal).
- Drift proposal: `build_proposal` with `selection=[marketplace_repo]`, `expected_shas={marketplace_repo: current head}` (expected-base conflict → blocked by F6's guard — test it), transformation `marketplace-entry-update` registered with fixed argv + patch-file convention (same pattern as F8's `plan-sync-doc-patch`; if F8 hasn't landed yet, this task establishes the pattern), output allowlist `[marketplace_file]`, `allow_scheduled: false`.

**Steps:**
- [ ] **Step 1: Tests** — stable release drift; prerelease/draft excluded; missing binding → `not_applicable`; missing entry; expected-base conflict blocks; no-op.
- [ ] **Step 2: Implement pure comparator + proposal builder.**
- [ ] **Step 3: Profile-gated skill/workflow** (`applies_to: profile:claude-plugin` or explicit binding presence; workflow passes `workflow_lint.py`).
- [ ] **Step 4: Run tests and commit** with `feat: add profile-gated marketplace sync`.

---

### Task 3: Add Claude context currency adapter

**Files:**
- Create: `lib/pulse/scripts/repo_claims.py`
- Create: `lib/pulse/scripts/tests/test_repo_claims.py`
- Modify: `lib/pulse/scripts/adapters/claude_plugin.py`

**Interfaces:**
- `facts(evidence) -> RepoFacts` — deterministic, from **configured claims only**: skill paths that exist, plugin manifest fields, declared commands (`commands/*.md`). No inference here.
- `check_claims(claude_md_text, facts) -> list[ClaimFinding]` — verifies CLAUDE.md's checkable claims against facts: a referenced skill path that doesn't exist → `missing_claimed_skill`; a documented command absent from `commands/` → `stale_command`; a claim referencing an evidence kind the checker doesn't support → `unsupported_evidence` (surfaced, never guessed at).
- Inference (extracting claims from CLAUDE.md prose) is the one non-deterministic step: its output is validated against the same `ClaimFinding` schema and every finding it produces carries `inferred: true`; a validation failure of inferred output → adapter status `unknown`, never a fabricated pass/fail.
- `claude.context` adapter wiring: scorecard `applicability` decides requiredness — under `profile:claude-plugin` a missing `CLAUDE.md` fails; under an optional capability it's `not_applicable`.

**Steps:**
- [ ] **Step 1: Tests** — missing claimed skill; stale command; unsupported evidence reference; missing CLAUDE.md under required vs optional applicability; inference-validation failure → `unknown`.
- [ ] **Step 2: Implement deterministic facts + inference validator.**
- [ ] **Step 3: Run tests and commit** with `feat: audit opt-in Claude context currency`.

---

### Task 4: Configure corpus generated-skill adapter

**Files:**
- Modify: `templates/generators.yaml.template`
- Modify: `templates/transformations.yaml.template`
- Create: `lib/pulse/scripts/tests/fixtures/overlays/corpus-generation/`
- Create: `lib/pulse/scripts/tests/test_corpus_generator_overlay.py`

**Interfaces:**
- Generator overlay entry `hiivmind.corpus-navigate-skill`: `applies_to: profile:claude-plugin` (or a dedicated `capability:corpus`), explicit `source_paths` (corpus template tree), `output_paths` (the generated navigate SKILL.md), `transformation` referencing a registered fixed-argv entry, `validation: {kind: json_schema | none}` per F7's spec. This is **configuration of F7 machinery** — zero new engine code; the test proves the F7 generic path handles it.

**Steps:**
- [ ] **Step 1: Define the generator** in the template with source template path, fixed argv (via its transformation), output paths, and skill validation.
- [ ] **Step 2: Tests** — F7 `audit` classifies corpus fixture drift correctly (template-drift → proposal; local customization → conflict, no proposal); `generator_dispatch.dispatch` builds a valid F6 proposal for it.
- [ ] **Step 3: Neutrality assertion** — the generic generated-artifact workflow/skill files contain no corpus-specific branch (extend F7 Task 5's neutrality test to cover the overlay id).
- [ ] **Step 4: Run tests and commit** with `feat: configure corpus skill generation overlay`.

---

### Task 5: Separate neutral and dogfood reporting

**Files:**
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `README.md`
- Modify: `SKILL.md` (root, if present — else the healthcheck skill only)
- Create: `lib/pulse/scripts/tests/test_dogfood_isolation.py`

**Interfaces:**
- Report grouping: healthcheck output groups by `scorecard`; overlay scorecards (`claude-plugin-v1`) get their own subtotal block, never merged into a neutral scorecard's denominator (the F3 scorecard-grouped output already keeps grades scorecard-specific — this task adds the explicit `overlay: true` marking and subtotals in the skill's REPORT phase).
- Isolation proof: neutral behavior must be provably overlay-independent.

**Steps:**
- [ ] **Step 1: Isolation test** — two assertions: (a) no neutral module (`profile_dispatch`, `check_adapters`, `adapters/generic.py`, `evaluate_checks.py`, `generated_artifacts.py`, `generator_dispatch.py`) imports `adapters.claude_plugin`, `marketplace_sync`, or `repo_claims` (walk the import graph via `ast`); (b) running the neutral acceptance tests with the overlay fixture directories absent (tmp copy minus `fixtures/overlays/`) passes — proving no neutral test depends on overlay fixtures.
- [ ] **Step 2: Report grouping** in the healthcheck skill: subtotals by `scorecard`, overlay findings visible but separately subtotaled; document the overlay model in README.
- [ ] **Step 3: Run `uv run pytest -q` and `git diff --check`** → clean.
- [ ] **Step 4: Commit** with `docs: expose dogfood overlays explicitly`.
