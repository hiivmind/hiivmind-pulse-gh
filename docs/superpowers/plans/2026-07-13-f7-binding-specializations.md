# F7: Generated Artifact and Contract Binding Specializations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic generated-artifact drift and contract-version propagation as adapter-driven specializations of the shared binding and Nave mutation infrastructure.

**Architecture:** `.generated.yaml` records content-addressed template trees and generated-file bases. Generator adapters declare commands and outputs; F6 pens execute them. Contract edges extend F5 impact edges with explicit producer/consumer version parsers. Claude/corpus examples are deferred to F9 overlays.

**Tech Stack:** Python 3.10+, PyYAML, `packaging`, pytest, git, Nave pens.

## Global Constraints

- Generated drift uses source directory tree hashes, never repository HEAD alone.
- Generated files record blob bases; both-sides-changed is a conflict.
- Generator identity, argv, source paths, output paths, and validation are explicit configuration.
- No LLM may infer or execute a generator.
- Contract versions come from explicit files/parsers; prose inference is forbidden.
- All repository-file application routes through F6.

---

### Task 1: Define generic generation bindings

**Files:**
- Create: `lib/patterns/generation-manifest.md`
- Create: `templates/generated.yaml.template`
- Modify: `lib/pulse/scripts/validate_result.py`
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`

**Interfaces:**
- Binding: `{id, source, branch, template_path, template_tree, generator, files, generated_at}`.
- File: `{path, blob}`.
- Result kind `generated-artifact`.

- [ ] **Step 1: Add manifest/result tests** for valid, duplicate paths, missing tree/blob, and unknown generator.
- [ ] **Step 2: Implement schema/validator and docs**.
- [ ] **Step 3: Run tests and commit** with `feat(contract): define generated artifact bindings`.

---

### Task 2: Implement backfill, audit, and guarded advancement

**Files:**
- Create: `lib/pulse/scripts/generated_artifacts.py`
- Create: `lib/pulse/scripts/tests/test_generated_artifacts.py`

**Interfaces:**
- `backfill(binding_input) -> ManifestEntry`.
- `audit(manifest, snapshot) -> GeneratedReport`.
- `advance(path, binding_id, expected_tree, new_tree, files, generated_at) -> MarkerResult`.

- [ ] **Step 1: Write failing tests** for template-only drift, local-only customization, both-sides conflict, missing output, no-op same tree, guarded update, and repeat idempotence.
- [ ] **Step 2: Verify red**, implement deterministic classification and atomic marker patch.
- [ ] **Step 3: Run tests and commit** with `feat: audit generated artifact currency`.

---

### Task 3: Register generator adapters and Nave transformations

**Files:**
- Create: `templates/generators.yaml.template`
- Modify: `templates/transformations.yaml.template`
- Create: `lib/pulse/scripts/generator_dispatch.py`
- Create: `lib/pulse/scripts/tests/test_generator_dispatch.py`

**Interfaces:**
- Generator: `{id, applies_to, command_argv, source_paths, output_paths, validation}`.

- [ ] **Step 1: Test explicit selection**, missing generator, output outside allowlist, shell string rejection, and profile mismatch.
- [ ] **Step 2: Implement dispatcher producing an F6 mutation proposal**.
- [ ] **Step 3: Verify and commit** with `feat: dispatch configured generators through Nave`.

---

### Task 4: Add contract edge parsers

**Files:**
- Create: `lib/pulse/scripts/contract_versions.py`
- Create: `lib/pulse/scripts/tests/test_contract_versions.py`
- Modify: `templates/relationships.yaml.template`
- Modify: `lib/pulse/scripts/impact.py`

**Interfaces:**
- Parsers v1: `regex` with one capture group; `toml` dotted key; `json` JSON pointer; `yaml` dotted key.
- Consumer constraint uses PEP 440 only when parser declares `version_scheme: pep440`; adapters may later add semver.

- [ ] **Step 1: Add parser/compatibility tests** for every parser, invalid version, missing path/key, compatible/gap, and dual impact finding de-duplication.
- [ ] **Step 2: Implement pure extraction and compose with F5**; one edge counts stale once.
- [ ] **Step 3: Run tests and commit** with `feat: specialize impact edges for contracts`.

---

### Task 5: Add generic headless workflow

**Files:**
- Create: `skills/gh-generated-artifact-headless/SKILL.md`
- Create: `templates/workflows/generated-artifact-audit.yaml`
- Modify: `templates/workspace-gitignore.template`

**Interfaces:**
- Consumes: F7 audit report, configured generator, F6 mutation proposal/result.
- Produces: `generated-artifact-result.yaml` and conflict/proposal records.

- [ ] **Step 1: Write skill** SNAPSHOT → AUDIT → CONFLICT/PROPOSE → optional F6 PEN → RECORD.
- [ ] **Step 2: Assert no references to Claude, corpus, skills, or plugin manifests** in generic files.
- [ ] **Step 3: Run full suite and commit** with `feat: add generic generated artifact workflow`.

---

### Task 6: Add split-repo configuration as an impact example

**Files:**
- Create: `templates/relationships/split-repo-tests.yaml`
- Modify: `lib/patterns/workflow-execution.md`
- Modify: `lib/pulse/scripts/tests/test_impact.py`

**Interfaces:**
- Consumes: F5 object edge and close-loop semantics.
- Produces: reusable full-tree test-repository relationship overlay; no new workflow/result kind.

- [ ] **Step 1: Add full-tree `watch_paths: ["**"]` fixture** and successful configured-workflow marker test.
- [ ] **Step 2: Document this as configuration, not a new workflow**.
- [ ] **Step 3: Verify and commit** with `docs: add split repository impact binding`.
