# F4: Dependency Coherence Adapter Family Implementation Plan

> **Execution mode (revised 2026-07-19):** execute directly in a single session on the
> main thread — no per-task subagents, no per-task reviewers. TDD per task, one commit
> per task, one adversarial whole-branch review at the end of the phase, then PR.
> **Status note:** F4 is NOT merged (develop's latest is PR #128 "Pre-F4"); this plan is
> still outstanding and should be sequenced after F9 or on user request.

**Goal:** Detect repository-local manifest/lock inconsistency and policy-scoped fleet version divergence through explicit Python and Node adapters while reporting unsupported ecosystems and evidence gaps as coverage debt.

**Architecture:** F4 consumes the temporary, blob-addressed dependency-evidence contract delivered by Pre-F4; it never parses F0 path observations as file contents and never reads Nave cache internals. Repository adapters produce ecosystem-qualified package records and local consistency blocks in pass one. A separate fleet postprocessor compares records only inside committed coherence groups, replaces requested fleet check blocks, centrally regrades repository results, and emits a content-free BRONZE snapshot.

**Tech Stack:** Python 3.10+, `packaging`, `semantic_version`, PyYAML, pytest, F1 profile dispatch, F3 adapter/result contracts, Pre-F4 dependency evidence.

## Prerequisite

`2026-07-15-pre-f4-nave-dependency-evidence.md` must be complete against a released Nave protocol-v2 CLI. F4 must not substitute raw GitHub manifest fetching or local Nave-cache reads when that capability is missing; it emits `unsupported` dependency-evidence coverage instead.

## Global Constraints

- Package identity is `(ecosystem, normalized_name)`; Python and npm display-name collisions are never compared.
- Every package record includes its repository. The canonical identity is `(repo, ecosystem, normalized_name)`.
- Supported Python v1: PEP 621 + `uv.lock`, Poetry + `poetry.lock`, PDM + `pdm.lock`, pip-tools `requirements.in`/`requirements*.txt`, and Conda `environment.yml`.
- Supported Node v1: `package.json` with `package-lock.json`, `pnpm-lock.yaml`, or Yarn v1 `yarn.lock`; unparseable Yarn generations are explicit `unsupported`.
- Adapter selection comes from F1 scorecards and materialized file evidence, never repository names.
- Evidence state and format support are distinct: unavailable/incomplete contents produce `unknown`; detected unsupported/ambiguous managers produce `unsupported`; absent exact paths are used only when Pre-F4 marked them authoritative.
- Cross-repo divergence is evaluated only inside committed coherence groups from `.hiivmind/github/dependencies.yaml`.
- A fleet coherence check is a second-pass operation. The skill performs no arithmetic and never edits check states.
- Raw materialized contents never enter `deps-snapshot.json`, healthcheck results, logs, or committed workspace state.
- Detection and severity have zero LLM involvement.

---

### Task 1: Define package records, policy groups, and comparator

**Files:**
- Modify: `pyproject.toml`
- Create: `lib/pulse/scripts/dependencies.py`
- Create: `lib/pulse/scripts/dependency_policy.py`
- Create: `lib/pulse/scripts/tests/test_dependencies.py`
- Create: `lib/pulse/scripts/tests/test_dependency_policy.py`
- Create: `lib/patterns/dependency-coherence.md`
- Create: `templates/dependencies.yaml.template`

**Interfaces:**

```python
@dataclass(frozen=True)
class PackageRecord:
    repo: str
    ecosystem: Literal["python", "npm"]
    name: str
    manifest_range: str | None
    locked_version: str | None
    manager: str
    source_files: tuple[str, ...]

@dataclass(frozen=True)
class CoherenceGroup:
    id: str
    repos: tuple[str, ...]
    packages: tuple[str, ...]          # ecosystem-qualified globs
    exclude_packages: tuple[str, ...]
    policy: Literal["exact", "same-major", "same-minor"]

@dataclass(frozen=True)
class DependencyPolicy:
    groups: tuple[CoherenceGroup, ...]

@dataclass(frozen=True)
class DivergenceFinding:
    group: str
    ecosystem: Literal["python", "npm"]
    package: str
    versions: tuple[tuple[str, str], ...]  # (repo, locked_version)
    distance: Literal["major", "minor", "patch", "unresolved"]

@dataclass(frozen=True)
class DivergenceReport:
    findings: tuple[DivergenceFinding, ...]
    unresolved: tuple[DivergenceFinding, ...]

@dataclass(frozen=True)
class DependencySnapshot:
    records: tuple[PackageRecord, ...]
    groups: tuple[CoherenceGroup, ...]
    report: DivergenceReport
    coverage: Mapping[str, object]

def compare(
    records: Iterable[PackageRecord],
    groups: Iterable[CoherenceGroup],
) -> DivergenceReport: ...
```

`exact` rejects every locked-version mismatch, `same-minor` allows patch differences, and `same-major` allows minor/patch differences. For a policy violation, major distance is `fail`; minor or patch distance is `warn`. No violation is `pass`. Missing/unparseable locked versions are excluded from version comparison and recorded as `unresolved`.

Workspace policy:

```yaml
contract_version: 1
coherence_groups:
  core-runtime:
    repos: [acme/api, acme/worker]
    packages: ["python:requests", "npm:@acme/*"]
    exclude_packages: ["python:typing-extensions"]
    policy: same-minor
```

- [ ] **Step 1: Add `packaging` and `semantic-version` to the dev dependency group.**
- [ ] **Step 2: Write failing strict-loader tests** for duplicate groups/repos, unqualified packages, unknown keys/policies, empty groups, and invalid glob syntax.
- [ ] **Step 3: Write failing comparator tests** for exact/major/minor/patch divergence, prereleases, unparseable versions, cross-ecosystem same-name packages, repos outside a group, exclusions, overlapping groups, and deterministic finding identity `(group, ecosystem, package)`.
- [ ] **Step 4: Run focused tests and verify RED.**
- [ ] **Step 5: Implement PEP 503 Python normalization, lowercase npm normalization preserving scopes, strict policy loading, and pure comparison.** Unparseable locked versions produce unresolved findings, never guessed severity.
- [ ] **Step 6: Run focused tests and commit** with `feat: compare dependency records by coherence group`.

---

### Task 2: Parse Python dependency managers from materialized evidence

**Files:**
- Create: `lib/pulse/scripts/adapters/python_dependencies.py`
- Create: `lib/pulse/scripts/tests/test_python_dependencies.py`
- Create: `lib/pulse/scripts/tests/fixtures/dependencies/python/`

**Interfaces:**

```python
@dataclass(frozen=True)
class AdapterDetection:
    state: Literal["applicable", "not_applicable", "unsupported", "unknown", "error"]
    manager: str | None
    detail: str
    source_files: tuple[str, ...]

def detect_python(repo: str, artifacts: Mapping[str, Artifact]) -> AdapterDetection: ...
def parse_python(repo: str, artifacts: Mapping[str, Artifact]) -> list[PackageRecord]: ...
def evaluate_python(context: CheckContext) -> CheckBlock: ...
```

`Artifact` is the validated JSON-native artifact type loaded by Pre-F4's `dependency_evidence.py`; adapters never accept raw Nave output.

- [ ] **Step 1: Create one neutral fixture per supported manager**: PEP 621 + uv, Poetry, PDM, pip-tools, and Conda. Include exact authoritative absence records from Pre-F4, not just missing fixture files.
- [ ] **Step 2: Write failing tests** for manager detection, package normalization, optional/development groups, compatible and incompatible manifest ranges, missing lock, mixed-manager ambiguity, malformed TOML/YAML/lock data, materialization `unknown`, unimplemented manager, and Python capability absent.
- [ ] **Step 3: Run the focused tests and verify RED.**
- [ ] **Step 4: Implement deterministic parsing.** `not_applicable` is allowed only when the F0/P1 context lacks Python capability; missing/unavailable materialized evidence is `unknown`; an identified unsupported or conflicting manager is `unsupported` with citations.
- [ ] **Step 5: Make local consistency semantics explicit:** compatible resolved versions pass; a resolved version outside its declared range fails; an authoritatively missing required lock fails; supported lockless Conda/pip-tools forms warn only when their ranges cannot prove a single resolution.
- [ ] **Step 6: Run focused/full tests and commit** with `feat: parse Python dependency managers`.

---

### Task 3: Parse Node dependency managers from materialized evidence

**Files:**
- Create: `lib/pulse/scripts/adapters/node_dependencies.py`
- Create: `lib/pulse/scripts/tests/test_node_dependencies.py`
- Create: `lib/pulse/scripts/tests/fixtures/dependencies/node/`

**Interfaces:**

```python
def detect_node(repo: str, artifacts: Mapping[str, Artifact]) -> AdapterDetection: ...
def parse_node(repo: str, artifacts: Mapping[str, Artifact]) -> list[PackageRecord]: ...
def evaluate_node(context: CheckContext) -> CheckBlock: ...
```

`Artifact` has the same Pre-F4 validated boundary as Task 2.

- [ ] **Step 1: Create fixtures** for npm lockfile v2/v3, pnpm, Yarn v1, npm/pnpm workspaces, authoritative missing lock, conflicting multiple locks, malformed files, and Yarn modern/unsupported syntax.
- [ ] **Step 2: Write failing tests** for manager selection, runtime/dev/optional dependencies, scoped package normalization, workspace aggregation, manifest-range satisfaction, missing/conflicting locks, evidence gaps, and Node capability absent.
- [ ] **Step 3: Run the focused tests and verify RED.**
- [ ] **Step 4: Implement deterministic parsing using `semantic_version.NpmSpec`.** Multiple recognized lock managers are `unsupported` ambiguity, not an arbitrary precedence choice.
- [ ] **Step 5: Run focused/full tests and commit** with `feat: parse Node dependency managers`.

---

### Task 4: Build the two-pass dependency pipeline

**Files:**
- Modify: `lib/pulse/scripts/adapters/__init__.py`
- Create: `lib/pulse/scripts/dependency_pipeline.py`
- Modify: `lib/pulse/scripts/healthcheck_dispatch.py`
- Modify: `lib/pulse/scripts/evaluate_checks.py`
- Create: `lib/pulse/scripts/tests/test_dependency_pipeline.py`

**Interfaces:**

```python
def evaluate_dependencies(
    healthcheck: dict,
    dependency_evidence: dict,
    policy: DependencyPolicy,
) -> tuple[dict, DependencySnapshot]: ...
```

Pass one registers `python.dependencies` and `node.dependencies`. Their `manifest_lock_consistency` blocks contain JSON-native `records` plus evidence citations. Pass two extracts only validated records, calls `compare`, replaces already-resolved `fleet_dependency_coherence` blocks, and calls the shared repository/aggregate reconciliation functions from F3.

- [ ] **Step 1: Write a failing mixed-fleet test** with Python, Node, docs, Terraform, and evidence-only unprofiled repositories.
- [ ] **Step 2: Assert dispatch boundaries:** Python/Node receive their selected local adapters; docs has no dependency checks; Terraform is `unsupported` only when its scorecard explicitly requests a dependency adapter; absent dependency evidence makes selected checks `unknown`, not fail.
- [ ] **Step 3: Write a failing two-pass test** proving divergence is limited to group members and ecosystem-qualified packages, local failures are preserved, fleet blocks are replaced once, and repository/aggregate/coverage summaries are centrally recomputed.
- [ ] **Step 4: Implement the minimal pipeline and register adapters without import side effects.** A fleet block outside every configured group is `not_applicable`; group evidence gaps are `unknown`; configured divergence maps exact/same-major/same-minor policy to deterministic pass/warn/fail detail.
- [ ] **Step 5: Run focused/full tests and commit** with `feat: dispatch dependency coherence by ecosystem`.

---

### Task 5: Add scorecards and strict dependency policy integration

**Files:**
- Modify: `templates/profiles.yaml.template`
- Modify: `lib/references/healthcheck-checks.md`
- Modify: `lib/patterns/repository-profiles.md`
- Create: `lib/pulse/scripts/tests/test_dependency_dispatch.py`

**Interfaces:**

- Check ID `manifest_lock_consistency` uses `python.dependencies` or `node.dependencies` according to the selected scorecard.
- Check ID `fleet_dependency_coherence` uses `fleet.dependencies.coherence` and is finalized only by Task 4's second pass.
- `.hiivmind/github/dependencies.yaml` is required only when a selected scorecard contains the fleet check. Missing policy then produces an explicit `unknown` fleet block and run error; it never compares the whole fleet implicitly.

- [ ] **Step 1: Add failing template-load and dispatch tests** for Python, Node, docs, Terraform, unclassified, and unsupported ecosystems.
- [ ] **Step 2: Add Python and Node scorecard examples by extending `generic-v1`; do not add language checks to `generic-v1` itself.** Register unsupported ecosystem examples with reasons so coverage debt is visible.
- [ ] **Step 3: Document repository-local versus fleet-second-pass scope and evidence state semantics.**
- [ ] **Step 4: Run focused/full tests and commit** with `feat: register dependency scorecards`.

---

### Task 6: Emit the content-free BRONZE snapshot and headless report

**Files:**
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `templates/workspace-gitignore.template`
- Modify: `lib/patterns/headless-contract.md`
- Create: `lib/pulse/scripts/tests/test_dependency_healthcheck_skill.py`
- Create: `lib/pulse/scripts/tests/test_dependency_acceptance.py`

**Interfaces:**

```yaml
contract_version: 1
generated_at: <ISO-8601>
source_request_sha256: <hex>
records:
  - repo: acme/api
    ecosystem: python
    name: requests
    manifest_range: ">=2.31,<3"
    locked_version: 2.32.0
    manager: uv
    source_files: [pyproject.toml, uv.lock]
groups:
  core-runtime:
    policy: same-minor
    repos: [acme/api, acme/worker]
findings: []
coverage:
  repositories_selected: 2
  repositories_parsed: 2
  unsupported_by_adapter: {}
  unresolved_repositories: []
errors: []
```

- [ ] **Step 1: Write failing static skill tests** requiring the sequence: F0/profile resolution → adapter selector request → Nave protocol-v2 materialization → strict dependency-evidence validation → F3 pass one → fleet pass two → content-free snapshot/result validation → temporary content deletion.
- [ ] **Step 2: Update the skill.** It invokes `nave_adapter.py materialize`; it never calls GitHub raw-content APIs and never reads Nave cache paths. Missing protocol v2 writes dependency `unsupported` coverage while unrelated healthchecks continue.
- [ ] **Step 3: Add `deps-snapshot.json` and `dependency-evidence.json` to the workspace ignore template.** The latter remains run-temporary even though ignored.
- [ ] **Step 4: Add end-to-end acceptance** for uv, Poetry, PDM, pip-tools, Conda, npm, pnpm, Yarn v1, docs, Terraform, and unknown ecosystem fixtures. Assert raw manifest strings do not occur in the snapshot or healthcheck result.
- [ ] **Step 5: Run skill schema validation, `uv run pytest -q`, Ruff on changed Python, and `git diff --check`.**
- [ ] **Step 6: Commit** with `feat: report ecosystem-aware dependency coherence`.

## F4 completion gate

- The workflow parses only validated Pre-F4 contents, never observational F0 paths as content.
- Every local dependency check is selected by an explicit scorecard.
- Cross-repo comparison occurs only inside committed groups and ecosystem namespaces.
- Unsupported managers/ecosystems and unavailable materialization are visible coverage states.
- All score and coverage arithmetic is centrally reconciled.
- `deps-snapshot.json` is content-free, transient, deterministic, and gitignored.
- Neutral fixtures cover every supported manager family; plugin-specific manifests remain deferred to F9.
