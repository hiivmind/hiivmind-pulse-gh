# F4: Dependency Coherence Adapter Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect manifest/lock inconsistency and fleet version divergence through explicit Python and Node adapters while reporting unsupported ecosystems as coverage debt.

**Architecture:** A generic dependency snapshot groups adapter-produced package records. Ecosystem adapters parse their own manifests and locks from F0 evidence; the generic comparator performs version divergence only within compatible package namespaces and policy groups. F3 dispatch applies results to repositories whose scorecards request dependency checks.

**Tech Stack:** Python 3.10+, `packaging`, `semantic_version`, PyYAML, pytest.

## Global Constraints

- Package identity is `(ecosystem, normalized_name)`; never compare Python and npm packages by display name alone.
- Supported Python v1: PEP 621 `pyproject.toml`, `uv.lock`, Poetry `pyproject.toml`/`poetry.lock`, PDM `pyproject.toml`/`pdm.lock`, pip-tools `requirements*.txt`, Conda `environment.yml`.
- Supported Node v1: `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock` when parseable by the adapter.
- Unsupported or ambiguous formats are visible; they are not silently ignored.
- Cross-repo divergence is evaluated only within configured coherence groups, not blindly across the entire fleet.
- Detection has zero LLM involvement.

---

### Task 1: Define generic dependency records and coherence groups

**Files:**
- Create: `lib/pulse/scripts/dependencies.py`
- Create: `lib/pulse/scripts/tests/test_dependencies.py`
- Create: `lib/patterns/dependency-coherence.md`

**Interfaces:**
- `PackageRecord(ecosystem, name, manifest_range, locked_version, source_files)`.
- `compare(records, groups) -> DivergenceReport`.
- Group: `{id, repos, packages, policy}`.

- [ ] **Step 1: Write failing comparator tests** for major/minor/patch divergence, cross-ecosystem same-name packages, repos outside a group, and deliberate excluded packages.
- [ ] **Step 2: Verify red**, implement normalized records and comparator.
- [ ] **Step 3: Run tests and commit** with `feat: compare dependency records by coherence group`.

---

### Task 2: Implement Python dependency adapters

**Files:**
- Create: `lib/pulse/scripts/adapters/python_dependencies.py`
- Create: `lib/pulse/scripts/tests/test_python_dependencies.py`
- Create: `lib/pulse/scripts/tests/fixtures/dependencies/python/`

**Interfaces:**
- `detect_python(files) -> AdapterDetection`.
- `parse_python(files) -> list[PackageRecord]`.

- [ ] **Step 1: Add one fixture/test per supported format** plus mixed-manager ambiguity and malformed lock cases.
- [ ] **Step 2: Verify red**, implement manager detection from file evidence rather than repo name/profile alone.
- [ ] **Step 3: Return `unsupported` with evidence** for a Python repo whose manager is not implemented; return `not_applicable` only when Python capability is absent.
- [ ] **Step 4: Run tests and commit** with `feat: parse Python dependency managers`.

---

### Task 3: Implement Node dependency adapters

**Files:**
- Create: `lib/pulse/scripts/adapters/node_dependencies.py`
- Create: `lib/pulse/scripts/tests/test_node_dependencies.py`
- Create: `lib/pulse/scripts/tests/fixtures/dependencies/node/`

**Interfaces:**
- Consumes: F0 file evidence for `package.json` and Node lockfiles.
- Produces: `list[PackageRecord]` or typed `not_applicable`/`unsupported` adapter result.

- [ ] **Step 1: Add fixtures/tests** for npm, pnpm, Yarn, workspaces, missing lock, and conflicting multiple locks.
- [ ] **Step 2: Verify red**, implement deterministic manager selection and package record parsing.
- [ ] **Step 3: Run tests and commit** with `feat: parse Node dependency managers`.

---

### Task 4: Register dispatched dependency checks

**Files:**
- Modify: `lib/pulse/scripts/check_adapters.py`
- Modify: `lib/pulse/scripts/healthcheck_dispatch.py`
- Modify: `lib/references/healthcheck-checks.md`
- Modify: `templates/profiles.yaml.template`
- Create: `lib/pulse/scripts/tests/test_dependency_dispatch.py`

**Interfaces:**
- Adapters: `python.dependencies`, `node.dependencies`.
- Check IDs: `manifest_lock_consistency`, `fleet_dependency_coherence`.

- [ ] **Step 1: Write failing dispatch test** where Python and Node repos use their adapters, docs is not applicable, Terraform is unsupported only if its scorecard requests a dependency check.
- [ ] **Step 2: Implement snapshot merge and centralized regrade**.
- [ ] **Step 3: Run focused/full tests and commit** with `feat: dispatch dependency coherence by ecosystem`.

---

### Task 5: Add BRONZE snapshot and fleet report

**Files:**
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `templates/workspace-gitignore.template`
- Modify: `lib/patterns/headless-contract.md`

**Interfaces:**
- Consumes: ecosystem-qualified package records and divergence report.
- Produces: transient `deps-snapshot.json` plus dependency check blocks in the healthcheck result.

- [ ] **Step 1: Define `.hiivmind/github/deps-snapshot.json`** with ecosystem-qualified keys and adapter coverage metadata.
- [ ] **Step 2: Update skill to emit snapshot from F0 evidence**, never refetch raw manifests.
- [ ] **Step 3: Run acceptance/full tests and commit** with `feat: report ecosystem-aware fleet dependency coherence`.
