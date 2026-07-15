# F9: Hiivmind and Claude Dogfood Overlays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add marketplace, Claude context, plugin layout, and corpus generated-skill behavior as explicitly enabled profiles and adapters without changing generic fleet semantics.

**Architecture:** `claude-plugin-v1` and hiivmind overlay scorecards extend neutral scorecards with plugin-specific adapters. Marketplace sync is a release-artifact adapter; Claude context currency is `not_applicable` without the capability; corpus regeneration is an F7 generator executed through F6. All overlay fixtures live separately from neutral fleet fixtures.

**Tech Stack:** Python 3.10+, PyYAML, pytest, gh CLI, F1/F3/F6/F7.

## Global Constraints

- No overlay runs without an explicit profile/capability.
- Missing `CLAUDE.md` is fail only when the selected scorecard requires Claude context; otherwise no check is dispatched.
- Marketplace sync applies only to repositories with configured marketplace binding.
- Generated-skill regeneration is one configured generator, not the generic F7 default.
- Overlay scores identify their scorecard and are never merged into a neutral scorecard denominator.

---

### Task 1: Add Claude plugin scorecards and adapters

**Files:**
- Modify: `templates/profiles.yaml.template`
- Create: `lib/pulse/scripts/adapters/claude_plugin.py`
- Create: `lib/pulse/scripts/tests/test_claude_plugin_adapter.py`
- Create: `lib/pulse/scripts/tests/fixtures/overlays/claude-plugin/`

**Interfaces:**
- Adapters: `claude.plugin_manifest`, `claude.skills`, `claude.context`.

- [ ] **Step 1: Add fixtures/tests** for valid plugin, missing manifest, malformed skill frontmatter, stale CLAUDE inventory, and normal Python repo without any Claude files.
- [ ] **Step 2: Verify red**, implement adapters with cited evidence.
- [ ] **Step 3: Assert normal Python repo receives no Claude check blocks**.
- [ ] **Step 4: Run tests and commit** with `feat: add explicit Claude plugin scorecard`.

---

### Task 2: Add marketplace release binding

**Files:**
- Create: `lib/pulse/scripts/marketplace_sync.py`
- Create: `lib/pulse/scripts/tests/test_marketplace_sync.py`
- Create: `skills/gh-marketplace-sync-headless/SKILL.md`
- Create: `templates/workflows/marketplace-sync.yaml`

**Interfaces:**
- Binding: `{plugin_id, repo, marketplace_repo, marketplace_file}`.
- Comparator emits guarded one-file F6 mutation proposal.

- [ ] **Step 1: Write tests** for stable release drift, prerelease/draft exclusion, missing binding not-applicable, missing entry, expected-base conflict, and no-op.
- [ ] **Step 2: Implement pure comparator and F6 proposal**.
- [ ] **Step 3: Write profile-gated skill/workflow**.
- [ ] **Step 4: Run tests and commit** with `feat: add profile-gated marketplace sync`.

---

### Task 3: Add Claude context currency adapter

**Files:**
- Create: `lib/pulse/scripts/repo_claims.py`
- Create: `lib/pulse/scripts/tests/test_repo_claims.py`
- Modify: `lib/pulse/scripts/adapters/claude_plugin.py`

**Interfaces:**
- Facts include configured claims only: skill paths, plugin files, declared commands.
- Inference output is validated and always `inferred: true`.

- [ ] **Step 1: Add tests** for missing claimed skill, stale command, unsupported evidence reference, missing CLAUDE under required/optional profiles, and inference failure unknown.
- [ ] **Step 2: Implement deterministic facts and inference validator**.
- [ ] **Step 3: Run tests and commit** with `feat: audit opt-in Claude context currency`.

---

### Task 4: Configure corpus generated-skill adapter

**Files:**
- Modify: `templates/generators.yaml.template`
- Modify: `templates/transformations.yaml.template`
- Create: `lib/pulse/scripts/tests/fixtures/overlays/corpus-generation/`
- Create: `lib/pulse/scripts/tests/test_corpus_generator_overlay.py`

**Interfaces:**
- Consumes: F7 generator schema and F6 transformation registry.
- Produces: explicit `hiivmind.corpus-navigate-skill` generator overlay and isolated fixtures.

- [ ] **Step 1: Define explicit generator** with source template path, fixed argv, output paths, and skill validation.
- [ ] **Step 2: Test F7 audit + F6 proposal**, including local customization conflict.
- [ ] **Step 3: Assert the generic generated-artifact workflow contains no corpus-specific branch**.
- [ ] **Step 4: Run tests and commit** with `feat: configure corpus skill generation overlay`.

---

### Task 5: Separate neutral and dogfood reporting

**Files:**
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `README.md`
- Modify: `SKILL.md`
- Create: `lib/pulse/scripts/tests/test_dogfood_isolation.py`

**Interfaces:**
- Consumes: F3 scorecard-grouped healthcheck output and all F9 adapters.
- Produces: separate overlay subtotals and regression proof that generic fleet behavior is overlay-independent.

- [ ] **Step 1: Add isolation test** proving removal of all overlay fixtures/adapters leaves neutral acceptance suite passing.
- [ ] **Step 2: Add report grouping** by `scorecard` and `overlay`; dogfood findings remain visible but separately subtotaled.
- [ ] **Step 3: Run `uv run pytest -q` and `git diff --check`** → clean.
- [ ] **Step 4: Commit** with `docs: expose dogfood overlays explicitly`.
