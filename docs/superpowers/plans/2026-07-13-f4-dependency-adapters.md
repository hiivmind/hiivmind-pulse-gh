# F4: Dependency Coherence Adapter Family Implementation Plan

> **Execution mode (finalized 2026-08-13, post 7-round Codex adversarial review — SHIP):**
> execute directly in a single thread across as many sessions as needed — no per-task
> subagents, no per-task reviewers. TDD per task, one commit per task. **Three mandatory
> checkpoints** (see below) plus the closing adversarial whole-branch review, before PR.
>
> **Status note:** F4 is NOT merged (develop's latest is PR #140). This plan went through 7
> rounds of adversarial design review (codex `gpt-5.6-sol`, high effort) before this session
> ended. Round 1 (2026-07-19 plan): BLOCK, 3 blocking/8 major/2 minor. Round 2: BLOCK, 3 new
> blocking/8 new major (no executable dataflow, dismissal-clobbers-fleet-input, undefined
> snapshot schema — 10 of 13 resolved cleanly). Round 3: BLOCK — root cause was a bare
> `tuple[PackageRecord, ...]` unable to carry per-declaration range facts; fixed via a typed
> `DependencyRepoEvaluation`. Round 4: BLOCK, narrower — coverage-reconciliation source was
> information-incomplete and never reached the snapshot builder; status/ecosystem literal
> mismatches; polyglot check-id collision; version-padding edge case; incomplete Poetry
> coverage. Round 5: BLOCK, narrower still — accumulator type conflation, comparable-membership
> definition gap, unsanitized pre-dispatch exception path. Round 6: BLOCK for one defect —
> `dependency_collector["report"]` undefined on the policy-present/no-fleet-check path. Round 7:
> **SHIP** — zero blocking/major/minor findings; two NIT wording issues fixed inline. Full
> reports (session-local, not committed): `/tmp/f4-plan-review-report.md` through
> `/tmp/f4-plan-review-round7-report.md`. This plan is approved for execution as written.
>
> **Checkpoint 1** — after Task 1: the typed evidence/record/evaluation/policy contracts,
> including `DependencyRepoEvaluation`, `RepositoryEvaluationSummary`'s per-group membership
> fields, and `reconcile_coverage`, are frozen. Do not start Task 2/3 adapter parsing until
> Task 1's tests are green.
> **Checkpoint 2** — after Task 4: the integrated two-pass pipeline, including the
> `dependency_collector` out-param that lets Task 6 build the snapshot from the exact same
> typed objects the durable `coverage["dependencies"]` was computed from, is green end-to-end.
> Do not start Task 5/6 until this checkpoint passes.
> **Checkpoint 3** — after Task 6's content-free canary suite passes and the snapshot
> validator's `coverage`-vs-`reconcile_coverage(repository_evaluations, groups)` reconciliation
> test passes for every counter, including `packages_unmatched` and
> `groups_with_insufficient_members` on an overlapping-groups fixture. Do not open the PR until
> this passes.

**Goal:** Detect repository-local manifest/lock inconsistency and policy-scoped fleet version
divergence through explicit Python and Node adapters, while reporting unsupported ecosystems,
ambiguous multi-resolution packages, and evidence gaps as typed coverage debt — never as a
guessed pass/fail.

**Architecture:** F4 consumes the temporary, blob-addressed dependency-evidence contract
delivered by Pre-F4 through a typed loader (`RepoEvidence`/`Artifact`); it never parses F0 path
observations as file contents and never reads Nave cache internals. A single orchestration
entry point resolves F1 scorecards, materializes evidence only for repositories with a
dependency check selected, and parses each selected `(repo, ecosystem)` **exactly once**,
before any dismissal logic runs, into one typed `DependencyRepoEvaluation` — the single object
that carries detection state, every per-declaration range fact, the collapsed fleet-comparison
records, and local findings. These evaluations live in a side channel
(`dependency_evaluations_by_repo`) that dismissals can never mutate. `evaluate_fleet` drives one
integrated pass: per-repository adapters build a JSON-safe local `CheckBlock` by reducing that
same evaluation's `local_findings`; a fleet placeholder is finalized for
`fleet_dependency_coherence` from the same side channel *inside the same pass*, immediately
before its own dismissal is applied; every repo whose fleet block changed has its `score`/
`total`/`grade`/`coverage_*` **recomputed in place**; only then does fleet-wide reconciliation
(`aggregate_by_scorecard`/`fleet_coverage`) run, exactly once. `evaluate_fleet` also
**optionally populates a caller-supplied collector** with the exact typed objects (`records`,
`groups`, `report`, `repository_evaluations`) it built internally, so the snapshot builder never
re-parses or reconstructs state from dismissible public blocks — it consumes the identical
objects the durable healthcheck coverage was computed from. There is no separate post-hoc
mutation step outside `evaluate_fleet`, and no reconciliation step that reads stale per-repo
summaries or fabricates snapshot content the validator cannot independently recompute. The
workflow emits a versioned, schema-validated, content-free BRONZE snapshot alongside the
healthcheck result, and the healthcheck result itself carries a durable `coverage.dependencies`
summary so policy debt survives past the transient snapshot — both computed by the same shared
`reconcile_coverage` function over the same collected inputs, so they cannot silently diverge.

**Tech Stack:** Python 3.10+, `packaging`, `semantic_version`, PyYAML, pytest, F1 profile
dispatch, F3 adapter/result contracts, Pre-F4 dependency evidence. No Rust/Nave work belongs in
this phase (Pre-F4 already shipped the protocol-v2 capability).

## Prerequisite

`2026-07-15-pre-f4-nave-dependency-evidence.md` is complete and merged (PR #128) against a
released Nave protocol-v2 CLI. F4 must not substitute raw GitHub manifest fetching or local
Nave-cache reads when that capability is missing; it emits `unsupported` dependency-evidence
coverage instead.

## Global Constraints

- Package identity is `(ecosystem, normalized_name)`; Python and npm display-name collisions
  are never compared. The canonical record identity is `(repo, ecosystem, normalized_name)`,
  and this identity is **unique across every `PackageRecord`, regardless of `resolution`** — a
  package that cannot be resolved unambiguously still gets exactly one collapsed record
  (`resolution="multiple"`), never more than one record sharing the same identity.
- **Two distinct ecosystem literals exist for two distinct domains — never conflated:**
  - **Adapter-selection ecosystem**, `Literal["python", "node"]` — which dependency adapter a
    scorecard selected for a repo (matches the check-adapter ids `python.dependencies`/
    `node.dependencies`). Used by `dependency_selected_repos`, the
    `dependency_evaluations_by_repo`/`entry["dependency_evaluations"]` outer-dict keys, and
    `RepositoryEvaluationSummary.ecosystem`.
  - **Package namespace ecosystem**, `Literal["python", "npm"]` — which packaging ecosystem a
    `PackageRecord` belongs to (npm packages are always in the `"npm"` namespace, regardless of
    which `"node"` adapter parsed them). Used by `PackageRecord.ecosystem`,
    `DivergenceFinding.ecosystem`, and the `"ecosystem:name"` glob-matching string (`"npm:
    @acme/widgets"`, never `"node:..."`).
- Supported Python v1: PEP 621 + `uv.lock`, Poetry + `poetry.lock`, PDM + `pdm.lock`, pip-tools
  `requirements.in`/`requirements*.txt`. Conda v1 scope is **narrowed**: only the nested `pip:`
  section of `environment.yml` is parsed into the `python` package namespace; native Conda
  channel/build-qualified specs and non-Python Conda packages are explicit `unsupported`
  coverage, never force-mapped into PEP 503/PEP 440 identity. When one `environment.yml`
  contains both parseable nested-`pip:` entries and native Conda specs, the nested-`pip:`
  entries still produce ordinary `PackageRecord`s and the native specs count toward
  `RepositoryEvaluationSummary.partial_unsupported` — one file can be partially supported, never
  all-or-nothing. Full Conda MatchSpec support is backlog item A in
  `docs/backlogs/2026-08-13-f4-deferred-scope.md`.
- Supported Node v1: `package.json` with `package-lock.json`, `pnpm-lock.yaml`, or Yarn v1
  `yarn.lock`; unparseable Yarn generations are explicit `unsupported`.
- Adapter selection comes from F1 scorecards and materialized file evidence, never repository
  names. A repository's resolved scorecard may legally select **both** the Python and Node
  dependency adapters (a polyglot repo) — see the distinct-check-id rule below. F4 evaluates
  each selected ecosystem independently, once each — the composable invariant is "parsed
  exactly once per `(repo, ecosystem)`," never "once per repo."
- **Local check ids are ecosystem-specific, never shared.** `python_manifest_lock_consistency`
  (adapter `python.dependencies`) and `node_manifest_lock_consistency` (adapter
  `node.dependencies`) are two distinct check ids. The real profile loader
  (`lib/pulse/scripts/profile_dispatch.py`, `_load_scorecard`/`resolve_scorecard`) rejects
  duplicate check ids within one resolved scorecard, so a polyglot repo's scorecard including
  both adapters under one shared id is not just stylistically wrong, it does not load — this is
  why two distinct ids are required, not a naming preference.
- **Multi-resolution cardinality (v1 scope cut, backlog item B) is about resolved versions,
  never about declaration count.** A package declared more than once for one repo (e.g. in both
  `[project.dependencies]` and an optional-dependency group) with a **single** resolved
  `locked_version` that the lockfile format represents unambiguously is `resolution="single"` —
  the collapsed `PackageRecord` carries that one locked version, and the local check separately
  verifies the resolved version against **every** declared range via `DeclaredRequirement`
  (below) — a violation on *any* one declaration is a real local defect, `fail`, even though the
  fleet-comparison record collapses cleanly to one version. `resolution="multiple"` is reserved
  for a genuinely ambiguous **resolution**: more than one locked version for the same normalized
  name (e.g. platform/marker-conditional distinct lock entries), or a lock format that cannot
  express a single resolution for that name. When that happens, `manifest_range=None`,
  `locked_version=None`, `unresolved_reason="multiple_resolutions"`, and the comparator treats
  it as unresolved coverage debt, never a guessed comparison.
- **Manager-declared workspaces are out of v1 comparison scope for every supported manager that
  has them, not partially modeled.** The static `DEPENDENCY_SELECTORS` catalog (Task 4) fetches
  only repo-root manifest/lock/sentinel files; it cannot see workspace-member manifests, so it
  cannot honestly detect per-member divergence. This applies to **both** ecosystems:
  - **Node**: a `package.json` `workspaces` key (npm/Yarn form), or a `pnpm-workspace.yaml`
    artifact whose state is `found`.
  - **Python**: a root `pyproject.toml` declaring `[tool.uv.workspace]` (uv's workspace table).
  In either case, that ecosystem's check reports the **whole check** `unsupported` with reason
  `"workspace_repository"` — never `resolution="multiple"` inferred from a manifest the adapter
  cannot actually see the members of, and never a root-manifest-only parse that would silently
  omit whatever the workspace actually manages. If the workspace-sentinel artifact
  (`pnpm-workspace.yaml`, or `pyproject.toml` for the `[tool.uv.workspace]` check) is **not**
  authoritatively resolvable — its materialized state is `unresolved`/`too_large`/`binary`/
  `error`, not `found` and not authoritatively `absent` — the whole check is `unknown` with
  reason `"workspace_sentinel_unresolved"`, since the adapter cannot rule out a workspace it
  simply couldn't confirm the absence of. Real per-member workspace modeling (a second
  materialize round-trip using discovered member globs) is backlog item B.
- Evidence state and format support are distinct: unavailable/incomplete materialized
  contents produce `unknown`; a detected unsupported/ambiguous manager (including a workspace
  repository, per above) produces `unsupported`; a recognized manager whose content is
  structurally invalid (malformed TOML/YAML/JSON/lock) produces `fail` with a bounded reason
  code — this is a real repository defect, not a coverage gap. `error` is reserved exclusively
  for adapter-internal/operational failure (an unhandled exception), never for a typed parse/
  format outcome. Absent exact paths are authoritative only when Pre-F4 marked the source tree
  complete. When `dependency_evidence` is `None` for the whole run, or a selected repo has no
  entry in it, that repo's evaluation is the same stable `unknown`/`"evidence_gap"`
  `DependencyRepoEvaluation` **without calling any parser** — this is a typed pre-dispatch
  branch (Task 4), never an unchecked `.get(repo)` fed into a parser expecting a real
  `RepoEvidence`. `capability` (whether F1 identifies the repo as belonging to that ecosystem
  at all) is always `True` when the pipeline calls a parser — `dependency_selected_repos`
  already filters to selected repos — but `detect_python`/`detect_node` still accept an explicit
  `capability: bool` parameter so their `not_applicable` branch remains directly unit-testable
  in isolation from the pipeline.
- Cross-repo divergence is evaluated only inside committed coherence groups from
  `.hiivmind/github/dependencies.yaml`. A selected `python_manifest_lock_consistency`/
  `node_manifest_lock_consistency` repository outside every group stays `not_applicable` for
  `fleet_dependency_coherence` (correct — no policy claim), but **this coverage debt is
  durable, not just visible in the transient snapshot**: `evaluate_fleet`'s returned
  `coverage.dependencies` object (Task 4) carries `repositories_ungrouped` and
  `groups_with_insufficient_members`, since `fleet_coverage`'s existing `checks_supported`
  counter treats `not_applicable` as supported and would otherwise hide this. The transient
  snapshot additionally serializes enough per-repository evaluation summary
  (`repository_evaluations`, Task 1) — including **per-group membership**, not just a single
  boolean — that its dedicated validator can *reconcile every counter*, including
  `packages_unmatched` and `groups_with_insufficient_members` on overlapping groups, against the
  serialized data by recomputation, not merely assert it.
- **A finding's `distance` is the coarsest pairwise distance across every fully-resolved
  (`resolution="single"`, parseable) member's `locked_version` in the group**, under the
  explicit ordering `major > minor > patch`: `distance = max(pairwise_distance(a, b) for a, b in
  combinations(resolved_versions, 2))`. A three-plus-member group where pairwise distances
  differ (e.g. `1.2.0`/`1.3.0`/`2.0.0`, giving both `minor` and `major` pairs) reports the
  coarsest tier, `major`, as the one serialized `distance` — policy violation/severity are then
  derived from that single reduced value, exactly as already specified for two-member groups.
- **The internal `DependencyRepoEvaluation` object bus is separate from the public JSON
  contract, and it — not a bare tuple of records — is the one object produced per
  `(repo, ecosystem)`.** `dependency_pipeline` parses each selected `(repo, ecosystem)` into a
  `DependencyRepoEvaluation` (Task 1) **exactly once**, before any per-repo dispatch or
  dismissal logic runs, and holds it in
  `dependency_evaluations_by_repo: dict[str, dict[Literal["python", "node"], DependencyRepoEvaluation]]`
  — a side channel dismissals never touch and the fleet pass reads directly (concatenating
  `.records` across every ecosystem a repo selected), never by extracting or hydrating records
  out of a (possibly-dismissed) public `CheckBlock`. The public `python_manifest_lock_consistency`/
  `node_manifest_lock_consistency` `CheckBlock.data` field is a **separate, JSON-safe
  projection** built from the same evaluation (`declarations` and `records` as plain dicts) for
  human/audit visibility — never literal dataclass instances, which are not JSON-native. **The
  same internal objects are made available to the snapshot builder through an optional
  collector out-param on `evaluate_fleet`** (Task 4) — never reconstructed after the fact.
- A fleet coherence check is finalized inside the same `evaluate_fleet` pass that runs local
  checks, reading only `dependency_evaluations_by_repo` — never the public, potentially-
  dismissed `checks[...]["data"]` of any repo. Dismissals for `fleet_dependency_coherence` are
  applied once, immediately after the fleet block is finalized (including the missing-policy
  case, which is *always* finalized to a **complete, normalized `CheckBlock`** — `check_id`,
  `adapter`, `weight`, `status`, `detail`, and `data.evidence`, not an abbreviated
  `status`/`data` fragment — never left as an undismissed placeholder). Every repo whose fleet
  block was replaced has `score`/`total`/`grade`/`coverage_supported`/`coverage_total`
  recomputed via `score_checks(repo["checks"])` and overwritten in place **before**
  `aggregate_by_scorecard`/`fleet_coverage` run. All other (non-fleet) checks keep their
  existing single-pass dismissal and scoring timing unchanged.
- **Content-free is an allow-list enforced at the actual dispatch boundary, including every
  output channel — never partially permitted.** The snapshot and every `CheckBlock`/
  `AdapterDetection` `detail` string are built exclusively from typed, structural facts (package
  name, normalized version, manager id, repo-relative path, bounded reason codes) and fixed
  message templates — including `AdapterRegistry.evaluate`'s own exception-handling path
  (`lib/pulse/scripts/check_adapters.py`), which today interpolates the raw caught-exception
  message into the public `detail` field for every adapter, not just dependency ones. **The
  caught exception's message is never written anywhere** — not the public `CheckBlock`, not
  stdout, not stderr, not a log file, with no exception for any channel. If future operator
  debugging needs the exception, that is a separate, explicitly secured diagnostic channel out
  of F4's scope — this phase does not invent one. Package names, normalized version strings, and
  repo-relative paths are legitimate structural output, not content leaks.
- Runtime dependencies (`packaging`, `semantic-version`) are declared in **both** places that
  need them: the `dev` dependency group in `pyproject.toml` (for `uv run pytest`) **and** the
  PEP 723 `# dependencies = [...]` header of `lib/pulse/scripts/healthcheck_dispatch.py` (the
  actual production entry point invoked via `uv run` by the headless skill). A dev-group-only
  addition ships a healthcheck run that `ImportError`s in production while tests stay green.
- Detection and severity have zero LLM involvement.

---

### Task 1: Define dependency-evidence indexing, evaluation objects, policy, comparator, and the snapshot envelope

**Files:**
- Modify: `pyproject.toml` (dev group)
- Modify: `lib/pulse/scripts/healthcheck_dispatch.py` (PEP 723 header only, in this task —
  wiring lands in Task 4)
- Modify: `lib/pulse/scripts/dependency_evidence.py` — add the typed evidence loader
- Create: `lib/pulse/scripts/dependencies.py`
- Create: `lib/pulse/scripts/dependency_policy.py`
- Create: `lib/pulse/scripts/tests/test_dependency_evidence_index.py`
- Create: `lib/pulse/scripts/tests/test_dependencies.py`
- Create: `lib/pulse/scripts/tests/test_dependency_policy.py`
- Create: `lib/patterns/dependency-coherence.md`
- Create: `templates/dependencies.yaml.template`

**Interfaces:**

```python
# lib/pulse/scripts/dependency_evidence.py — new additions

@dataclass(frozen=True)
class Artifact:
    selector_id: str
    path: str | None
    blob_sha: str | None
    size_bytes: int | None
    state: Literal[
        "found", "absent", "unresolved", "too_large", "binary", "unsupported", "error"
    ]
    encoding: str | None
    content: str | None
    detail: str | None

@dataclass(frozen=True)
class RepoEvidence:
    repo: str
    ref_name: str
    tree_sha: str | None
    tree_complete: bool
    artifacts: tuple[Artifact, ...]

    def by_selector(self, selector_id: str) -> tuple[Artifact, ...]: ...
    def by_path(self, path: str) -> Artifact | None: ...

def load_dependency_evidence(document: dict) -> dict[str, RepoEvidence]:
    """Load an ALREADY-VALIDATED (validate_dependency_evidence.validate(document) == [])
    normalized document into typed per-repo evidence, keyed by repo. Never called on
    unvalidated input — F4's driver validates first (Task 4)."""
```

```python
# lib/pulse/scripts/dependencies.py

@dataclass(frozen=True)
class ArtifactProvenance:
    role: Literal["manifest", "lock"]
    path: str                              # repo-relative
    blob_sha: str | None

@dataclass(frozen=True)
class PackageRecord:
    """The collapsed, fleet-comparison-ready record for one (repo, ecosystem, name). Always
    exactly one per identity — see Global Constraints. `ecosystem` here is the PACKAGE
    NAMESPACE literal (python|npm), never the adapter-selection literal (python|node)."""
    repo: str
    ecosystem: Literal["python", "npm"]
    name: str                              # normalized identity component
    resolution: Literal["single", "multiple"]
    manifest_range: str | None             # None unless resolution == "single" and parseable
    locked_version: str | None             # None unless resolution == "single" and parseable
    unresolved_reason: Literal[
        "multiple_resolutions", "unparseable_version", "non_range_spec",
    ] | None
    manager: str
    manifest_path: str | None              # repo-relative declaring file; None if resolution
                                            # == "multiple" (no single file to name)
    lock_path: str | None                  # repo-relative resolving file; None if lockless
                                            # or resolution == "multiple"
    tree_sha: str | None                   # from RepoEvidence, for F11 provenance
    provenance: tuple[ArtifactProvenance, ...]   # every contributing artifact, sorted by
                                                  # (role, path) — always complete, even when
                                                  # resolution == "multiple"

@dataclass(frozen=True)
class DeclaredRequirement:
    """One declaration of a package within one repo. A single PackageRecord's resolved
    version may be checked against several of these — this is what round-3 found the bare
    PackageRecord tuple could not carry."""
    name: str                              # normalized identity component
    manifest_path: str
    manifest_range: str | None             # None if unresolved_reason == "non_range_spec"
    unresolved_reason: Literal["non_range_spec"] | None
    group: Literal["main", "dev", "optional"]

@dataclass(frozen=True)
class LocalFinding:
    """The per-package local-check outcome — the reduction input for CheckBlock.status."""
    name: str
    status: Literal["pass", "fail", "warn", "unknown"]
    reason_code: str

@dataclass(frozen=True)
class DependencyRepoEvaluation:
    """The ONE object produced per (repo, ecosystem), exactly once, before any dispatch or
    dismissal logic runs. Every other output — the public local CheckBlock, the fleet
    comparator's input, the durable healthcheck coverage, and the snapshot — projects from
    this object. Never re-parsed; never reconstructed from a public, possibly-dismissed
    CheckBlock."""
    repo: str
    ecosystem: Literal["python", "node"]   # adapter-selection ecosystem — see the Global
                                            # Constraints literal-domain note
    detection: "AdapterDetection"          # Task 2/3 — forward-referenced here, defined there
    declarations: tuple[DeclaredRequirement, ...]
    records: tuple[PackageRecord, ...]     # fleet-comparison input; one per normalized name;
                                            # PackageRecord.ecosystem is the PACKAGE NAMESPACE
                                            # literal, independently of this field
    local_findings: tuple[LocalFinding, ...]
    local_status: Literal[
        "pass", "warn", "fail", "unknown", "not_applicable", "unsupported", "error",
    ]                                       # the full CheckBlock status literal — matches
                                            # check_adapters.CHECK_STATUSES exactly, not
                                            # AdapterDetection.state's smaller vocabulary
    local_reason_code: str | None
    coverage_state: Literal["complete", "incomplete"]
    partial_unsupported: int               # count of detected-but-unsupported items alongside
                                            # an otherwise applicable/pass/fail evaluation (e.g.
                                            # native Conda specs in a mixed environment.yml);
                                            # 0 whenever the whole check's status is itself
                                            # "unsupported" (that case is counted once, at the
                                            # evaluation level, not per-item)

@dataclass(frozen=True)
class CoherenceGroup:
    id: str
    repos: tuple[str, ...]
    packages: tuple[str, ...]              # ecosystem-qualified globs, e.g. "npm:@acme/*"
    exclude_packages: tuple[str, ...]
    policy: Literal["exact", "same-major", "same-minor"]

@dataclass(frozen=True)
class DependencyPolicy:
    groups: tuple[CoherenceGroup, ...]

@dataclass(frozen=True)
class DivergenceFinding:
    group: str
    ecosystem: Literal["python", "npm"]    # package namespace literal
    package: str
    versions: tuple[tuple[str, str | None], ...]   # (repo, locked_version|None)
    distance: Literal["major", "minor", "patch", "unresolved"]   # coarsest pairwise, see
                                                                  # Global Constraints

@dataclass(frozen=True)
class DivergenceReport:
    findings: tuple[DivergenceFinding, ...]
    unresolved: tuple[DivergenceFinding, ...]

@dataclass(frozen=True)
class RepositoryEvaluationSummary:
    """The per-selected-(repo,ecosystem) reconciliation input the snapshot validator needs.
    Redesigned this round to be information-complete: round 4 found the prior (grouped: bool,
    comparable_packages: int) shape could not distinguish inputs requiring different
    packages_unmatched or groups_with_insufficient_members values, especially for overlapping
    groups. This shape can — see reconcile_coverage below for exactly how each DependencyCoverage
    counter derives from it."""
    repo: str
    ecosystem: Literal["python", "node"]   # adapter-selection ecosystem
    adapter: Literal["python.dependencies", "node.dependencies"]
    status: Literal[
        "pass", "warn", "fail", "unknown", "not_applicable", "unsupported", "error",
    ]                                       # DependencyRepoEvaluation.local_status, carried
                                            # through unchanged
    reason_code: str | None
    total_packages: int                    # count of this evaluation's PackageRecords, ANY
                                            # resolution and ANY local_status — always
                                            # len(evaluation.records); NEVER forced to zero for
                                            # a non-pass status (an evaluation can BE `unknown`
                                            # precisely because it holds resolution="multiple"
                                            # records, which still count here)
    matched_packages: int                  # subset of total_packages that are (a)
                                            # resolution == "single" with a parseable
                                            # locked_version — only a fully-resolved record can
                                            # ever participate in a real cross-repo comparison
                                            # — AND (b) this repo is listed in >= 1
                                            # CoherenceGroup.repos whose glob matches the
                                            # record; summed across ALL groups combined (not
                                            # per-group — see group_memberships for the
                                            # per-group facet)
    partial_unsupported: int               # carried through from DependencyRepoEvaluation
    group_memberships: tuple[str, ...]     # CoherenceGroup ids for which this repo is BOTH
                                            # (a) listed in that group's `repos`, AND (b) has
                                            # >= 1 resolution=="single", parseable-locked-
                                            # version record matched by that group's own glob
                                            # — i.e. COMPARABLE membership, never a bare glob-
                                            # text hit against a group the repo isn't even
                                            # listed in, and never satisfied by a
                                            # resolution=="multiple" record. Sorted,
                                            # deduplicated — this is what makes
                                            # groups_with_insufficient_members derivable for
                                            # overlapping groups, which a single boolean cannot.

@dataclass(frozen=True)
class DependencyCoverage:
    repositories_selected: int
    repositories_grouped: int
    repositories_ungrouped: int
    groups_with_insufficient_members: tuple[str, ...]   # group ids with < 2 comparable repos
    packages_matched: int
    packages_unmatched: int
    unsupported_by_adapter: Mapping[str, int]

@dataclass(frozen=True)
class DependencySnapshot:
    records: tuple[PackageRecord, ...]
    groups: tuple[CoherenceGroup, ...]
    report: DivergenceReport
    coverage: DependencyCoverage
    repository_evaluations: tuple[RepositoryEvaluationSummary, ...]

@dataclass(frozen=True)
class DependencySnapshotDocument:
    """The versioned envelope wrapping DependencySnapshot for the wire format
    (deps-snapshot.json). Distinct from DependencySnapshot itself — see Task 6."""
    contract_version: int
    generated_at: str
    request_sha256: str
    snapshot: DependencySnapshot
    errors: tuple[str, ...]

def compare(
    records: Iterable[PackageRecord],
    groups: Iterable[CoherenceGroup],
) -> DivergenceReport: ...

def reconcile_coverage(
    evaluations: Iterable[RepositoryEvaluationSummary],
    groups: Iterable[CoherenceGroup],
) -> DependencyCoverage:
    """The single source of truth for every DependencyCoverage counter, derived ENTIRELY from
    RepositoryEvaluationSummary + CoherenceGroup — both Task 4 (building the durable healthcheck
    coverage) and Task 6 (serializing/validating the snapshot) call this over the SAME collected
    inputs, so the two can never silently diverge. Exact derivation, implement precisely:
      - repositories_selected: count of DISTINCT `repo` values across evaluations (a polyglot
        repo selecting both ecosystems counts once, not twice).
      - repositories_grouped: count of distinct `repo` values with a non-empty
        `group_memberships` in at least one of their ecosystem evaluations.
      - repositories_ungrouped: repositories_selected - repositories_grouped.
      - groups_with_insufficient_members: for each group in `groups`, count the DISTINCT repos
        in `group.repos` that appear in ANY evaluation whose `group_memberships` contains
        `group.id`; if that count is < 2, include `group.id`.
      - packages_matched: sum of `matched_packages` across all evaluations.
      - packages_unmatched: sum of `total_packages - matched_packages` across all evaluations.
      - unsupported_by_adapter[adapter]: sum, over evaluations with that `adapter`, of
        `(1 if status == "unsupported" else 0) + partial_unsupported`.
    """
```

**Version and distance semantics (implement exactly this table — resolves the "under-specified"
finding from round 1, the padding/epoch/Poetry gaps from rounds 2-4, and the multi-member
reduction gap from round 3):**

- **Python**, `locked_version` parsed with `packaging.version.Version` (PEP 440). To compute
  pairwise `distance` between two versions `a`, `b`:
  1. `Version(a).epoch != Version(b).epoch` → `major`, unconditionally, before any release
     comparison (an epoch bump is always a major-tier signal).
  2. Else, right-pad **both** release tuples with trailing zeros to length
     `max(3, len(release_a), len(release_b))` — **always at least 3, unconditionally, even when
     the two release tuples already have equal length** (this is the concrete fix for round 4's
     `2.dev1` vs `2` finding: both releases are `(2,)`, equal length, but the full versions
     differ via the `.dev1` suffix — padding only "to the longer of the two" would leave both at
     length 1 with no `release[1]` to inspect; padding unconditionally to at least 3 guarantees
     `release[1]` always exists).
  3. `release[0]` differs → `major`; `release[0]` equal, `release[1]` differs → `minor`;
     `release[0:2]` equal and anything else differs (release tail, pre/post/dev, local
     identifier) → `patch`.
  4. Equal per `Version.__eq__` → no violation (not a pairwise divergence).
  A `locked_version` that raises `InvalidVersion` gets `unresolved_reason="unparseable_version"`
  and never enters distance comparison.
- **npm**, `locked_version` parsed with `semantic_version.Version` (lockfiles always pin a
  concrete resolved version). Pairwise `distance` from `(major, minor, patch)`; a prerelease/
  build metadata-only difference at equal `(major, minor, patch)` is `patch`. An unparseable
  `locked_version` gets `unresolved_reason="unparseable_version"`.
- **Group-level `distance` reduction:** for a package inside a group with more than two fully-
  resolved (`resolution="single"`, parseable) members, compute the pairwise `distance` for
  every combination of members' `locked_version`s and take the coarsest under `major > minor >
  patch`. A group with members at `1.2.0`/`1.3.0`/`2.0.0` has pairwise distances `{minor, major,
  major}` → the finding's `distance` is `major`. Policy violation/severity (below) is derived
  from this single reduced value, exactly as for two-member groups. This reduction is part of
  `compare()`'s own specification, not a separate post-processing step.
- **Manifest ranges are never used for `distance`** — only `locked_version` is compared across
  repos, matching `DivergenceFinding.versions`. A `manifest_range` that is not a standard
  version-range form for its ecosystem — Python: a direct URL, VCS reference, or local path
  spec; npm: `*`, a dist-tag/alias, `workspace:`, or a git/tarball/file URL — gets
  `unresolved_reason="non_range_spec"` on the record, and the Task 2/3 **local** range-check
  (declared-vs-resolved, per `DeclaredRequirement`) is skipped for it, reported `unknown` with
  that reason code, never guessed pass/fail. An ordinary numeric range (Python: PEP 440
  specifiers including `~=`, plus Poetry's `^`/`~`/exact/wildcard forms once translated per
  Task 2's conversion algorithm; npm: any range `semantic_version.NpmSpec` accepts) is a
  standard form and goes through the local range-check normally.
- `exact` rejects any locked-version mismatch across group members (`distance != None` on the
  reduced group distance → `fail`); `same-minor` allows `patch`; `same-major` allows `minor`
  and `patch`. For a policy violation, `major` distance is `fail`; `minor`/`patch` is `warn`.
  No violation is `pass`. Every non-`"single"`-resolution or unresolved-version record for a
  package inside a group produces a `DivergenceFinding` in `DivergenceReport.unresolved`
  (never silently dropped), with `versions` carrying `None` for the unresolved participant(s).

Workspace (coherence-group) policy — unrelated to manager-declared package workspaces above,
this is the fleet comparison policy file:

```yaml
contract_version: 1
coherence_groups:
  core-runtime:
    repos: [acme/api, acme/worker]
    packages: ["python:requests", "npm:@acme/*"]
    exclude_packages: ["python:typing-extensions"]
    policy: same-minor
```

**Glob matching grammar and semantics (this is the full, unambiguous lexical grammar — resolves
round 1's overlap-precedence finding, round 3's "not a complete grammar" finding, and round 4's
"ASCII terminals and npm-scope placement still left to the implementer" finding):** normalize
`(ecosystem, name)` (PEP 503 for Python, lowercase-preserving-scope for npm) before matching,
producing a normalized `"ecosystem:name"` string (the **package namespace** ecosystem —
`"python"` or `"npm"`, never `"node"`), e.g. `"python:requests"`, `"npm:@acme/widgets"`. A
`packages`/`exclude_packages` glob is valid **only** if it matches this EBNF, split explicitly
by ecosystem prefix so scope placement is a lexical fact, not a semantic afterthought:

```ebnf
glob        = python_glob | npm_glob
python_glob = "python:" py_segment
npm_glob    = "npm:" (npm_scoped | npm_plain)
npm_scoped  = "@" plain_atom+ "/" plain_atom+
npm_plain   = plain_atom+
py_segment  = plain_atom+
plain_atom  = literal | star | question | bracket
literal     = letter | digit | "-" | "_" | "."
star        = "*"
question    = "?"
bracket     = "[" ["!"] rangeitem+ "]"
rangeitem   = letter | digit | letter "-" letter | digit "-" digit
letter      = "a".."z" | "A".."Z"          (* ASCII only; no Unicode letters in v1 *)
digit       = "0".."9"
```

`/` and `@` are **not** members of `literal`/`plain_atom` — they appear only in the fixed
`npm_scoped` production, at the fixed positions shown (a leading `@`, exactly one `/` between
the scope and name segments). `python:@foo/bar` is therefore rejected by the grammar (no
production admits `@`/`/` under `python_glob`), and an npm glob may only place `@`/`/` in the
scoped form's fixed shape — arbitrary placement elsewhere is rejected. A glob failing this
grammar (including an empty `py_segment`/`npm_plain`, an unbalanced `[`/`]`, or any character
outside the terminals above) is rejected at load time by this explicit grammar check — never by
relying on `fnmatch.translate` to raise (it does not, for most malformed-looking input).
Matching itself uses `fnmatch.fnmatchcase` (never the platform-normalizing `fnmatch.fnmatch`,
since matching must stay case-sensitive post-normalization) over the normalized
`"ecosystem:name"` string once the glob has passed this grammar check. A package is in-group if
it matches any `packages` glob; if it also matches any `exclude_packages` glob, **exclude always
wins**, unconditionally. A repository/package pair may belong to multiple groups; each group
emits an independent finding — the plan does not merge or rank overlapping groups. The loader
rejects duplicate `coherence_groups` keys and duplicate `repos` entries within one group using
a duplicate-key-detecting YAML loader (default PyYAML silently keeps the last key and would
hide this).

- [ ] **Step 1: Add `packaging` and `semantic-version`** to `pyproject.toml`'s dev dependency
      group **and** to `healthcheck_dispatch.py`'s PEP 723 `# dependencies = [...]` header.
- [ ] **Step 2: Write failing tests for the typed evidence loader** (`test_dependency_evidence_index.py`):
      `RepoEvidence.by_selector` fan-out (multiple artifacts, one selector), `by_path` lookup,
      multiple null-path (no-match) artifacts, and that loading an unvalidated/malformed
      document raises rather than silently producing a partial index.
- [ ] **Step 3: Write failing strict-loader tests** for duplicate groups/repos, unqualified
      packages, unknown keys/policies, empty groups, and every rejection case in the glob
      grammar above (`"python:@foo/bar"` rejected, an npm glob with `@`/`/` outside the fixed
      scoped shape rejected, empty segment, unbalanced brackets, an out-of-grammar character),
      plus accepted examples (`"npm:@acme/*"`, `"python:requests"`, `"python:type[i]ng*"`).
- [ ] **Step 4: Write failing comparator tests** for exact/major/minor/patch pairwise
      divergence (using the version table above — explicit expected outcomes for PEP 440
      epoch-only changes, pre/post/dev/local identifiers, the exact `2.dev1` vs `2` regression
      case, and SemVer prerelease/build cases — not just fixture examples), the group-level
      coarsest-pairwise-distance reduction for 3+ member groups, unparseable/non-range specs,
      cross-ecosystem same-name packages, repos outside a group, include/exclude overlap
      (exclude always wins), overlapping groups with different policies (independent findings),
      and deterministic finding identity `(group, ecosystem, package)`.
- [ ] **Step 5: Write failing serialization-shape and reconciliation tests** for
      `DependencySnapshotDocument` proving every `CoherenceGroup` field round-trips,
      `PackageRecord.provenance` preserves `(role, path, blob_sha)` association, and
      `reconcile_coverage` — given `RepositoryEvaluationSummary` fixtures including: a repo
      contributing zero records (unsupported/evidence-gap), a repo belonging to two overlapping
      groups with different `group_memberships` (one group has 2+ comparable repos, the other
      has only 1 → only the latter appears in `groups_with_insufficient_members`), and an
      evaluation with nonzero `partial_unsupported` alongside `status="pass"` (the mixed-Conda
      case) — produces the exact `DependencyCoverage` this specification predicts for each.
- [ ] **Step 6: Run focused tests and verify RED.**
- [ ] **Step 7: Implement the evidence loader, PEP 503 Python normalization, lowercase npm
      normalization preserving scopes, strict policy loading, `reconcile_coverage`, and pure
      comparison** exactly per the version/distance table and glob-matching grammar above.
- [ ] **Step 8: Run focused tests and commit** with `feat: index dependency evidence and
      compare records by coherence group`.

**Checkpoint 1.** Do not proceed to Task 2 until this task's tests are green.

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
    reason_code: str | None     # bounded enum-like string; never interpolates raw content
    source_files: tuple[str, ...]

def detect_python(
    repo: str, evidence: RepoEvidence, *, capability: bool
) -> AdapterDetection: ...
def parse_python(
    repo: str, evidence: RepoEvidence, *, capability: bool
) -> DependencyRepoEvaluation: ...
def project_evaluation(evaluation: DependencyRepoEvaluation) -> dict:
    """JSON-safe projection of a DependencyRepoEvaluation for CheckBlock.data — plain dicts/
    lists only, covering declarations and records. Shared by Task 2/3 (define once, e.g. in
    dependencies.py)."""
def evaluate_python(context: CheckContext) -> CheckBlock: ...
```

`capability` is the F1/F0 signal ("this repository's profile/scorecard resolution identifies
it as a Python repository") threaded explicitly through every layer — `detect_python`/
`parse_python` never infer it from evidence alone, since materialized evidence carries no
profile data. Task 4's pipeline always passes `capability=True` (it only calls `parse_python`
for repos `dependency_selected_repos` already selected); `capability=False` is exercised
directly by this task's own unit tests calling `detect_python`/`parse_python` in isolation, so
the `not_applicable` branch stays covered without ever being reachable through the real
pipeline. `not_applicable` is returned only when `capability` is `False`; when `capability` is
`True` and no manager evidence is found, the result is `unknown` (evidence gap) or
`unsupported` (recognized-but-unsupported/ambiguous manager, or a workspace repository per
Global Constraints), never `not_applicable`.

`parse_python` is called **exactly once** per selected `(repo, "python")`, by Task 4's
pipeline, before any dispatch/dismissal logic — never by `evaluate_python` itself.
`evaluate_python` reads `context.evidence["dependency_evaluations"]["python"]` — the already-
built `DependencyRepoEvaluation` Task 4's `_attach_dependency_evidence` computed — and projects
it with `project_evaluation` plus the `local_status`/`local_reason_code` fields already on the
evaluation. It never calls `parse_python` itself.

**Python manager-workspace detection:** before any manager-specific parsing, `detect_python`
inspects the materialized root `pyproject.toml` artifact:
- If its state is `found` and its content declares a `[tool.uv.workspace]` table → whole-check
  `unsupported`, reason `"workspace_repository"`, empty `declarations`/`records`.
- If its state is `unresolved`/`too_large`/`binary`/`error` (not `found`, not authoritatively
  `absent`) → whole-check `unknown`, reason `"workspace_sentinel_unresolved"` — the adapter
  cannot rule out a `[tool.uv.workspace]` declaration it couldn't read.
- Otherwise (authoritatively `absent`, or `found` without that table) proceed with normal
  single-project parsing below.

**Evidence-state → local-check lattice (implement exactly this; `local_status` values are the
full `CheckBlock` status vocabulary — `pass`/`warn`/`fail`/`unknown`/`not_applicable`/
`unsupported`/`error` — never `AdapterDetection.state`'s smaller vocabulary):**

| Situation | `AdapterDetection.state` | `local_status` |
|---|---|---|
| `capability=False` | `not_applicable` | `not_applicable` |
| `dependency_evidence` absent for this repo, or the whole run has none, per Global Constraints | n/a (no parse call; a synthetic `AdapterDetection(state="unknown", manager=None, reason_code="evidence_gap", source_files=())` is used) | `unknown` — reason `"evidence_gap"` |
| Workspace sentinel unresolved (see above) | `unknown` | `unknown` — reason `"workspace_sentinel_unresolved"` |
| Manager-declared workspace detected (see above) | `unsupported` | `unsupported` — reason `"workspace_repository"` |
| `capability=True`, no supported manager files found, tree complete | `unknown` | `unknown` — reason `"no_manager_evidence"` |
| Artifact `unresolved`/`too_large`/`binary` for the only candidate manager files | `unknown` | `unknown` — reason `"evidence_gap"` |
| Exactly one supported manager identified, content parses cleanly, all records `resolution="single"`, every `DeclaredRequirement` satisfied | `applicable` | `pass` |
| As above, at least one `DeclaredRequirement` violated by its package's single resolved version | `applicable` | `fail` — reason `"range_violation"` |
| Exactly one supported manager identified, content structurally invalid (malformed TOML/lock) | `applicable` | `fail` — reason `"malformed_source"` |
| A required lock is authoritatively missing for a manager that requires one | `applicable` | `fail` — reason `"missing_lock"` |
| A supported lockless form (pip-tools without a compiled `requirements.txt`) whose range cannot prove a single resolution | `applicable` | `warn` — reason `"unresolved_lockless"` |
| At least one record has `resolution="multiple"` and no other package independently fails | `applicable` | `unknown` — reason `"multiple_resolutions"`, `coverage_state="incomplete"` |
| At least one record has `resolution="multiple"` **and** another package independently fails | `applicable` | `fail` — the independent fail's reason **and** `coverage_state="incomplete"` — a known defect is never hidden behind an unrelated evidence gap |
| Multiple recognized-but-conflicting managers (e.g. both `poetry.lock` and `uv.lock`) | `unsupported` | `unsupported` — reason `"ambiguous_manager"` |
| A detected manager/format not in the v1 supported list | `unsupported` | `unsupported` — reason `"unsupported_manager"` |
| One `environment.yml` with both parseable nested-`pip:` records and native Conda specs | `applicable` | status from the nested-`pip:` records per the rows above; native specs each increment `DependencyRepoEvaluation.partial_unsupported` (never `PackageRecord`s, never silently dropped, never force the whole check `unsupported`) |
| Adapter raises an unhandled internal exception | `error` | `error` — reserved for this class only |

`local_status` is a **per-package-set reduction, precedence-ordered**: `error` (internal
failure) > `fail` (any `LocalFinding` with `status="fail"`, checked first over the full
`local_findings` set) > `unknown` (only `resolution="multiple"` or evidence-gap findings
remain, no independent `fail`) > `warn` > `pass`. A `resolution="multiple"` record never
suppresses a `fail` verdict earned by a different, fully-resolved package in the same repo; it
only sets `coverage_state="incomplete"` alongside whatever status the other packages earn.

**Local range-check semantics (this is what `DeclaredRequirement` exists to make possible):**
`parse_python` extracts every declaration of every package into a `DeclaredRequirement` (one
row per `(manifest_path, group)` a name appears in — e.g. a package declared in both
`[project.dependencies]` and `[project.optional-dependencies].test]` yields two
`DeclaredRequirement`s sharing one `name`), and separately collapses the package's single
resolved version into one `PackageRecord`. For each `DeclaredRequirement` with a standard-form
`manifest_range`, the local check tests whether the package's collapsed `PackageRecord.
locked_version` satisfies it, producing one `LocalFinding` per **package** (not per
declaration) whose `status` is `fail` if *any* of that package's declarations is violated,
`pass` if all are satisfied.

Poetry's constraint syntax is translated to an equivalent `packaging.specifiers.SpecifierSet`
before calling `.contains()`, using this general algorithm (covers every syntactically valid
Poetry version-constraint form — see the [Poetry dependency specification](https://python-poetry.org/docs/main/dependency-specification/#version-constraints)):
1. **Bare PEP 440 operators** (`==`, `>=`, `~=`, `!=`, `<`, `>`, `<=`) and **comma-separated
   compound constraints** (`">=1.2,<2.0"`) are already valid `SpecifierSet` syntax and pass
   through unchanged.
2. **`^` (caret):** lower bound is the literal given version, right-padded with `.0`
   components to at least three parts for the lower-bound string (e.g. `^1.2` → lower `1.2.0`).
   Upper bound: scan the *given* components left to right for the first nonzero one; increment
   it by one and drop everything after it (e.g. `^1.2.3` → `<2.0.0`; `^0.2.3` → `<0.3.0`;
   `^0.0.3` → `<0.0.4`; `^1.2` → `<2.0.0`; `^1` → `<2.0.0`). If every given component is zero
   (`^0`, `^0.0`, `^0.0.0`), increment the last given component (`^0.0.0` → `<0.0.1`; `^0` →
   `<1.0.0`, since a single given component `0` has no later component to increment, so the
   increment applies to that same, only, component).
3. **`~` (tilde):** lower bound is the literal given version, right-padded the same way. Upper
   bound: if two or more components are given, pin at the **second** component (increment it,
   drop the rest — `~1.2.3` → `<1.3.0`; `~1.2` → `<1.3.0`). If only one component is given
   (`~1`), it behaves like caret (`~1` → `<2.0.0`).
4. **Bare exact version** (no operator prefix, e.g. `1.2.3`) → `==1.2.3`.
5. **Prefix wildcard** (`1.*`, `1.2.*`) — PEP 440's own `==` operator natively supports a
   trailing `.*` for prefix matching (`SpecifierSet("==1.*")` is valid, unmodified PEP 440
   syntax), so this form needs no arithmetic conversion — it passes through as `==<form>`
   unchanged (`1.*` → `==1.*`; `1.2.*` → `==1.2.*`).
6. **Bare `*` alone** (no version prefix, the whole constraint) is Poetry's unconstrained/
   any-version wildcard, not an error — converts to an empty `SpecifierSet("")`, which PEP 440
   defines as satisfied by every version (a specifier set with zero clauses places no
   constraint). `manifest_range` still stores the literal `"*"` for the JSON-safe projection.
7. **Union (`||`, or the `|` synonym)** — Poetry's OR-combinator, e.g. `">=1.2,<1.3 ||
   >=1.4"`. Split the raw constraint string on `||`/`|`, apply this algorithm recursively to
   each branch (each branch is itself one of rules 1-6), and represent the declaration's range
   as a tuple of `SpecifierSet` branches rather than one `SpecifierSet`. A resolved version
   satisfies the declaration if it satisfies **any** branch —
   `any(branch.contains(version) for branch in branches)` — never `.contains()` on a single
   combined set (`SpecifierSet` itself is AND-only and cannot represent a union). This is the
   only case where the local range-check uses `any(...)` instead of one `.contains()` call.
8. Any other syntax (an unrecognized operator, malformed input) is
   `unresolved_reason="non_range_spec"`.
A `DeclaredRequirement` with `unresolved_reason="non_range_spec"` skips the range-check for
that one declaration (contributes no `fail`), and the package's `PackageRecord` still feeds
`compare()` normally if its resolution is otherwise `"single"`.

This is now a complete mapping of Poetry's documented constraint grammar (bare operators,
comma compounds, caret, tilde, exact, prefix wildcard, bare wildcard, and union) onto
`SpecifierSet`/`any(...)` semantics — no valid Poetry constraint form is left unmapped to
either a decidable range-check or an explicit `non_range_spec` classification.

- [ ] **Step 1: Create one neutral fixture per supported manager**: PEP 621 + uv, Poetry
      (including fixtures covering every branch of the algorithm above — `^1.2.3`, `^0.2.3`,
      `^0.0.3`, `^1.2`, `^1`, `^0`, `^0.0.0`, `~1.2.3`, `~1.2`, `~1`, a compound comma-separated
      constraint, a bare exact version, `1.*`, `1.2.*`), PDM, pip-tools, and Conda's nested
      `pip:` section only, plus a mixed nested-pip/native-spec `environment.yml` fixture, a
      uv-workspace root `pyproject.toml` fixture, and a fixture where the root `pyproject.toml`
      artifact state is `unresolved`. Include exact authoritative-absence records from Pre-F4,
      not just missing fixture files.
- [ ] **Step 2: Write failing tests** for every row of the evidence-state lattice above
      (including both `resolution="multiple"`-interaction rows, the workspace-detected row, and
      the workspace-sentinel-unresolved row, asserting `local_status` values from the full
      `pass`/`warn`/`fail`/`unknown`/`not_applicable`/`unsupported`/`error` vocabulary),
      package normalization, a package declared in multiple groups with **one** declaration
      violating its range while another is satisfied (asserting the package's
      `LocalFinding.status == "fail"`), `resolution="multiple"` for a genuinely multi-resolution
      record (platform/marker-conditional distinct lock entries — never merely multi-declaration
      with one resolution), every Poetry range-algorithm branch listed above, non-range specs
      (`file://`, VCS refs), a bare `*` (unconstrained, per algorithm point 6), a union
      constraint (`">=1.2,<1.3 || >=1.4"`, per algorithm point 7), missing lock, malformed
      TOML/lock data, the mixed-Conda `partial_unsupported` count, and `capability=False`
      (called directly, not through the pipeline).
- [ ] **Step 3: Run the focused tests and verify RED.**
- [ ] **Step 4: Implement deterministic parsing** exactly per the lattice, workspace detection,
      precedence-ordered reduction, and range-check semantics above, returning one
      `DependencyRepoEvaluation`.
- [ ] **Step 5: Run focused/full tests and commit** with `feat: parse Python dependency
      managers`.

---

### Task 3: Parse Node dependency managers from materialized evidence

**Files:**
- Create: `lib/pulse/scripts/adapters/node_dependencies.py`
- Create: `lib/pulse/scripts/tests/test_node_dependencies.py`
- Create: `lib/pulse/scripts/tests/fixtures/dependencies/node/`

**Interfaces:**

```python
def detect_node(
    repo: str, evidence: RepoEvidence, *, capability: bool
) -> AdapterDetection: ...
def parse_node(
    repo: str, evidence: RepoEvidence, *, capability: bool
) -> DependencyRepoEvaluation: ...
def evaluate_node(context: CheckContext) -> CheckBlock: ...
```

Same `RepoEvidence`/lattice/range-check/precedence-reduction/`DeclaredRequirement`/`capability`
contract as Task 2 (reusing `project_evaluation` from Task 1), `manager` values `npm`, `pnpm`,
`yarn1`; `PackageRecord.ecosystem` is always the package-namespace literal `"npm"`
(`DependencyRepoEvaluation.ecosystem`, separately, is the adapter-selection literal `"node"` —
see the Global Constraints literal-domain note). `parse_node` is called exactly once per
selected `(repo, "node")`, by Task 4's pipeline, mirror of Task 2's dispatch discipline.

**Node manager-workspace detection (this replaces any per-member `resolution="multiple"`
inference):** `detect_node` inspects, in order:
1. The materialized `pnpm-workspace.yaml` artifact's state (selector added in Task 4). If its
   state is `unresolved`/`too_large`/`binary`/`error` (not `found`, not authoritatively
   `absent`) → whole-check `unknown`, reason `"workspace_sentinel_unresolved"` — the adapter
   cannot rule out a pnpm workspace it couldn't confirm the absence of.
2. If that artifact is `found`, or the already-fetched root `package.json` content declares a
   `workspaces` key (npm/Yarn form) → whole-check `unsupported`, reason
   `"workspace_repository"`, empty `declarations`/`records`.
3. Otherwise (`pnpm-workspace.yaml` authoritatively `absent` and no `workspaces` key) proceed
   with normal single-project parsing.

Non-workspace repos parse normally; a `resolution="multiple"` record can still arise for a
non-workspace repo only from genuinely ambiguous lock data (e.g. a lockfile listing more than
one resolved version for a name that manifests as one declaration — rare, but typed rather than
assumed impossible).

Non-range npm forms (`*`, dist-tags, aliases, `workspace:`, git/tarball/file URLs) get
`unresolved_reason="non_range_spec"` on the relevant `DeclaredRequirement`, per Task 1's
version table.

- [ ] **Step 1: Create fixtures** for npm lockfile v2/v3, pnpm, Yarn v1, a `package.json` with
      a `workspaces` key (npm/Yarn form), a repo with `pnpm-workspace.yaml` present (`found`),
      a repo where `pnpm-workspace.yaml`'s materialized state is `unresolved`, an authoritative
      missing lock, conflicting multiple locks, malformed files, and Yarn modern/unsupported
      syntax.
- [ ] **Step 2: Write failing tests** for every row of the evidence-state lattice, runtime/dev/
      optional dependencies, scoped package normalization, the workspace-repository
      `unsupported` outcome for both the `workspaces`-key and `pnpm-workspace.yaml` `found`
      triggers, the `workspace_sentinel_unresolved` outcome, a package declared in multiple
      dependency groups with one violated/one satisfied range, manifest-range satisfaction,
      non-range forms, missing/conflicting locks, and `capability=False` (called directly).
- [ ] **Step 3: Run the focused tests and verify RED.**
- [ ] **Step 4: Implement deterministic parsing using `semantic_version.NpmSpec`** for range
      satisfaction where the range is a standard SemVer range; non-range forms are typed
      `non_range_spec`, never coerced. Multiple recognized lock managers are `unsupported`
      ambiguity, not an arbitrary precedence choice.
- [ ] **Step 5: Run focused/full tests and commit** with `feat: parse Node dependency
      managers`.

---

### Task 4: Wire materialization, dispatch, and the integrated two-pass pipeline

**Files:**
- Modify: `lib/pulse/scripts/adapters/__init__.py`
- Modify: `lib/pulse/scripts/healthcheck_dispatch.py`
- Modify: `lib/pulse/scripts/evaluate_checks.py`
- Create: `lib/pulse/scripts/dependency_pipeline.py`
- Create: `lib/pulse/scripts/tests/test_dependency_pipeline.py`
- Create: `lib/pulse/scripts/tests/test_healthcheck_dispatch_dependencies.py`

**Interfaces:**

```python
# lib/pulse/scripts/dependency_pipeline.py

DEPENDENCY_SELECTORS: tuple[dict, ...] = (
    # static, ecosystem-wide selectors covering every v1-supported manager file/glob —
    # not derived per-repo; feature detection happens from materialize's per-artifact
    # state (found/absent/unresolved/...), never from a repo-name or pre-scan heuristic.
    {"id": "python.pyproject", "pattern": "pyproject.toml"},
    {"id": "python.uv_lock", "pattern": "uv.lock"},
    {"id": "python.poetry_lock", "pattern": "poetry.lock"},
    {"id": "python.pdm_lock", "pattern": "pdm.lock"},
    {"id": "python.pip_tools_in", "pattern": "requirements*.in"},
    {"id": "python.pip_tools_txt", "pattern": "requirements*.txt"},
    {"id": "python.conda_env", "pattern": "environment.yml"},
    {"id": "node.package_json", "pattern": "package.json"},
    {"id": "node.npm_lock", "pattern": "package-lock.json"},
    {"id": "node.pnpm_lock", "pattern": "pnpm-lock.yaml"},
    {"id": "node.pnpm_workspace_yaml", "pattern": "pnpm-workspace.yaml"},
    {"id": "node.yarn_lock", "pattern": "yarn.lock"},
)

def dependency_selected_repos(
    config: ProfileConfig,
) -> dict[str, frozenset[Literal["python", "node"]]]:
    """repo -> the set of dependency ADAPTER-SELECTION ecosystems its resolved scorecard
    selects (via python_manifest_lock_consistency / node_manifest_lock_consistency, adapters
    python.dependencies / node.dependencies). A scorecard MAY legally select both — resolve_
    scorecard enforces no mutual exclusivity across DIFFERENT check ids, so this returns a set,
    never a single ecosystem string. Mirrors healthcheck_dispatch._overlay_opted_in_repos's
    scan of resolve_scorecard, generalized to preserve every selected ecosystem."""

def materialize_dependency_evidence(
    repos: Sequence[str], *, runner: NaveRunner
) -> dict:
    """build_request -> nave_adapter.materialize -> normalize -> validate (raise on any
    violation) -> return the validated normalized document. Never returns an unvalidated
    document to the caller."""

def evaluate_dependencies(
    repo: str, ecosystem: Literal["python", "node"], evidence: RepoEvidence | None,
) -> DependencyRepoEvaluation:
    """The one typed pre-dispatch entry point, and the SANITIZED BOUNDARY around parser
    invocation — this call happens BEFORE _repo_result dispatches through
    AdapterRegistry.evaluate, so AdapterRegistry's own exception handling (Task 6) does not
    cover it; evaluate_dependencies must catch internal exceptions itself, at this boundary.
    - If evidence is None (mapping-absent or repo-absent — both are the SAME missing-evidence
      case, never distinguished by an unchecked .get()), returns the stable unknown/
      evidence_gap evaluation WITHOUT calling a parser.
    - Otherwise, calls parse_python(..., capability=True) or parse_node(..., capability=True)
      exactly once, wrapped in try/except Exception. On success, returns the parser's
      DependencyRepoEvaluation unchanged. On an unhandled exception, the exception's message is
      NEVER interpolated anywhere (the same content-free rule as the AdapterRegistry.evaluate
      fix in Task 6) — returns a synthetic DependencyRepoEvaluation instead:
      detection=AdapterDetection(state="error", manager=None,
      reason_code="internal_parser_error", source_files=()), local_status="error",
      local_reason_code="internal_parser_error", empty declarations/records,
      coverage_state="complete", partial_unsupported=0.
    capability is always True here because the caller only invokes this for repos
    dependency_selected_repos already selected."""
```

```python
# lib/pulse/scripts/healthcheck_dispatch.py — evaluate_fleet gains three new optional params

def evaluate_fleet(
    *,
    evidence: Mapping[str, Any],
    profiles_path: str | Path,
    workspace: str | Path,
    dismissals_path: str | Path | None = None,
    as_of: str | date | datetime | None = None,
    gh_api: Any | None = None,
    dependency_evidence: Mapping[str, RepoEvidence] | None = None,
    dependency_policy: DependencyPolicy | None = None,
    dependency_collector: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """dependency_collector, if provided, is populated (as a side effect, before returning) with
    keys "records" (tuple[PackageRecord, ...] across every evaluated repo/ecosystem),
    "groups" (the resolved DependencyPolicy.groups, or () if no policy), "report"
    (the DivergenceReport from the single whole-run compare() call, or the empty default when
    no comparison runs — no policy, or a policy with zero fleet-check-selecting repos), and
    "repository_evaluations" (tuple[RepositoryEvaluationSummary, ...]) — the exact typed
    objects this call used internally to build the durable coverage["dependencies"]. This is
    an ADDITIVE, purely-optional out-param: every existing caller passing dependency_collector=
    None (the default) sees zero behavior change to evaluate_fleet's return value or signature
    otherwise. It exists so Task 6's snapshot builder consumes the identical objects the durable
    result was computed from, never re-parsing or reconstructing state from public CheckBlocks."""

def _apply_dismissals(
    repo: str,
    checks: dict[str, dict[str, Any]],
    dismissals: Mapping[str, Any],
    as_of: date,
    *,
    skip_check_ids: frozenset[str] = frozenset(),
) -> None: ...   # existing per-check dismissal logic extracted into a reusable single-check
                  # helper, called both from the existing loop (minus skip_check_ids) and once
                  # more, scoped to fleet_dependency_coherence, in step 4 below.
```

**Integrated pipeline (implement exactly this sequence):**

1. Before the per-repo loop, for every `repo, ecosystems in
   dependency_selected_repos(config).items()`, for every `ecosystem in ecosystems`:
   - Call `evaluate_dependencies(repo, ecosystem, dependency_evidence.get(repo) if
     dependency_evidence else None)` **exactly once per `(repo, ecosystem)`**, producing one
     `DependencyRepoEvaluation`. This is the single typed pre-dispatch path — there is no
     unchecked `Mapping.get` fed directly into a parser.
   - Store the evaluation in **three** places, and append its derived summary to a **fourth**
     accumulator: (a) `entry.setdefault("dependency_evaluations",
     {})[ecosystem] = evaluation` (so `evaluate_python`/`evaluate_node` — dispatched later,
     inside the loop — read it directly, never re-parsing); (b) a loop-local
     `dependency_evaluations_by_repo.setdefault(repo, {})[ecosystem] = evaluation` dict that is
     **never attached to `entry`** and is therefore untouched by anything `_repo_result`/
     `_apply_dismissals` subsequently does to that repo's public `checks`; (c) a loop-local
     `all_evaluations: list[DependencyRepoEvaluation]` accumulator (flat, across every repo and
     ecosystem — this is what feeds `dependency_collector["records"]` at the end); and (d) a
     loop-local `all_summaries: list[RepositoryEvaluationSummary]` accumulator — **built right
     here, unconditionally, for every evaluated `(repo, ecosystem)`**, never deferred to a
     later fleet-pass-only branch. Compute the summary immediately against
     `groups = dependency_policy.groups if dependency_policy is not None else ()` (already
     known at this point in the pipeline, before the per-repo loop even starts) — when there is
     no policy, `groups` is simply empty, so `matched_packages`/`group_memberships` correctly
     come out empty/zero for every summary, rather than the summary being skipped entirely.
     This is what makes every selected `(repo, ecosystem)` — including missing-policy runs and
     repos that never select `fleet_dependency_coherence` at all — contribute a complete
     `RepositoryEvaluationSummary`, per Global Constraints and Task 1's `reconcile_coverage`.
     This is the same pattern `_attach_overlay_content` already uses for evidence attachment,
     extended with three additional, dismissal-immune accumulators.
2. Inside the per-repo loop (`_repo_result`), `python_manifest_lock_consistency`/
   `node_manifest_lock_consistency` are dispatched and dismissed exactly like any other check
   — no change to existing per-repo dismissal timing, and `evaluate_python`/`evaluate_node`
   build their public `CheckBlock.data` from `context.evidence["dependency_evaluations"]
   [ecosystem]` (already built, never touching the dismissal-immune side channel). If the
   repo's scorecard also selects `fleet_dependency_coherence`, `_repo_result` emits an explicit
   **placeholder** block for it — a complete normalized `CheckBlock` (`check_id`,
   `adapter="fleet.dependencies.coherence"`, `weight`, `status="unknown"`, `detail="pending
   fleet pass"`, `data={"evidence": {"paths": [], "refs": []}, "coverage_state":
   "pending_fleet_pass"}`) — and this one check id is passed via
   `skip_check_ids={"fleet_dependency_coherence"}` to `_apply_dismissals` during this per-repo
   pass, so it is never dismissed here.
3. After the per-repo loop completes (all repos collected), initialize
   `report = DivergenceReport(findings=(), unresolved=())` — this stays the final value on
   every path except the one below that overwrites it. Then, for **every** repo that selected
   `fleet_dependency_coherence` (not conditioned on whether `dependency_policy` was supplied —
   the placeholder is *always* finalized to a complete, normalized `CheckBlock`):
   - If `dependency_policy` is `None`: replace the placeholder with a stable complete block —
     `status="unknown"`, `detail="dependencies.yaml missing"`, `data={"evidence": {"paths": [],
     "refs": []}, "reason_code": "missing_policy"}` — and append a run-level error to the fleet
     result's top-level `errors`. (`report` stays the empty default from above — there is no
     policy to compare against.)
   - Else (a policy exists and this repo selected the fleet check): **before processing any
     individual repo**, if `report` has not yet been overwritten this call, gather the full
     flattened record set from `dependency_evaluations_by_repo` — concatenating `.records`
     across every ecosystem, for every repo with an entry there (not only repos selecting the
     fleet check; a group's other member may be relevant via a different repo/ecosystem) — and
     call `compare(records, groups)` **exactly once for the whole run**, overwriting `report`
     with its result. (If a policy exists but zero repos select `fleet_dependency_coherence`,
     this line never executes and `report` correctly stays the empty default from above — this
     is the local-dependency-only-scorecard case, and its collector output must still carry
     complete `records`/`repository_evaluations` per step 5, just an empty `report`.) Build
     this repo's `fleet_dependency_coherence` `CheckBlock` from the subset of
     `report.findings`/`report.unresolved` whose `versions` include this repo (reading from
     `report` — never from any repo's public `checks` dict), and **replace** its placeholder in
     place. Reject (raise) rather than best-effort-mutate if a repo's placeholder is missing,
     duplicated, or carries the wrong adapter id. (`all_evaluations` and `all_summaries` were
     already fully populated in step 1 — this branch reads them, it never builds or appends to
     them.)
   - Either way, apply the scoped dismissal — `_apply_dismissals(repo, checks, dismissals,
     as_of, skip_check_ids=frozenset())` restricted to just this one check id via the reusable
     single-check helper — to the now-finalized block.
   - **Then recompute that repo's summary**: `summary = score_checks(repo["checks"])` and
     overwrite `repo["score"]`, `repo["total"]`, `repo["grade"]`, `repo["coverage_supported"]`,
     `repo["coverage_total"]` in place with the fresh values.
4. **Then**, exactly as today and unchanged, run `aggregate_by_scorecard(repos)` and
   `fleet_coverage(repos)` once, over the fully-finalized, fully-rescored `repos` list.
5. Call `reconcile_coverage(all_summaries, groups)` (Task 1 — the single shared implementation,
   `groups` being the same resolved-policy-or-empty tuple from step 1) to get
   `DependencyCoverage`. Attach it to the fleet result's existing `coverage` dict as
   `coverage["dependencies"]` (a JSON-safe projection of the dataclass), so this debt is
   durable on the healthcheck result, not only visible in the transient snapshot. This is
   separate from `fleet_coverage`'s existing generic-adapter counters, which are unchanged.
   **If `dependency_collector` was provided, populate it now** with `"records"` (the flattened
   `.records` from every `DependencyRepoEvaluation` in `all_evaluations`), `"groups"` (the same
   `groups` tuple), `"report"` (`report`, exactly as established in step 3 — the real
   `compare()` result when a policy existed and at least one repo selected the fleet check,
   otherwise the empty default), and `"repository_evaluations"` (`tuple(all_summaries)`)
   — the exact same objects `reconcile_coverage` was just called with. Task 6's snapshot
   builder reads this collector — the same objects, not a reconstruction — so the durable
   result and the transient snapshot are guaranteed to reconcile identically.

Ungrouped repos stay `not_applicable` for `fleet_dependency_coherence` (no policy claim); the
`DependencyCoverage` counters (durably, per step 5, and in Task 6's snapshot) are what make
that debt visible.

- [ ] **Step 1: Write a failing mixed-fleet test** with Python, Node, a polyglot repo selecting
      **both** `python_manifest_lock_consistency` and `node_manifest_lock_consistency`, docs,
      Terraform, and evidence-only unprofiled repositories, asserting: docs/Terraform never get
      dependency checks; each selected `(repo, ecosystem)` gets exactly one
      `evaluate_dependencies` call (assert a parse-call counter, not just output shape) with its
      evaluation attached; a repo with an **active dismissal** on
      `python_manifest_lock_consistency` (the local check) still contributes its full,
      undismissed-in-the-side-channel records to `fleet_dependency_coherence`'s comparison —
      this is the direct regression test for the dismissal-destroys-records finding; a repo with
      an active dismissal on `fleet_dependency_coherence` keeps that dismissal after the fleet
      pass replaces the placeholder; a repo's `score`/`total`/`grade` after the fleet pass
      reflects the real fleet block's contribution, not the pre-fleet-pass value — the direct
      regression test for the stale-score finding; a selected repo with `dependency_evidence`
      mapping entirely `None`, and a separate selected repo present in `dependency_evidence` but
      missing its own key, both produce the stable `unknown`/`"evidence_gap"` evaluation without
      a parser being called; `dependency_collector["repository_evaluations"]` and the durable
      `coverage["dependencies"]` from the same call, both fed through `reconcile_coverage`,
      produce byte-identical `DependencyCoverage` objects; rerunning the entire
      `evaluate_fleet(...)` call from the same inputs is byte-identical (idempotence is asserted
      at this boundary only, never by re-invoking an in-place mutation helper on an already-
      mutated result).
- [ ] **Step 2: Assert dispatch boundaries:** a group with a member missing evidence still
      surfaces a known major-distance divergence among its *available* members as `fail`,
      carrying `data.coverage_state: "incomplete"`; a selected fleet check with **no**
      `dependency_policy` supplied becomes the stable `missing_policy` block plus a run error,
      is still dismissal-checked, and still triggers score recomputation; two overlapping
      `CoherenceGroup`s where a repo is comparable in one but not the other produce a
      `RepositoryEvaluationSummary.group_memberships` containing only the group it's actually
      comparable in; a scorecard selecting only `python_manifest_lock_consistency`/
      `node_manifest_lock_consistency` (no repo selects `fleet_dependency_coherence`) with a
      valid `dependency_policy` supplied still produces a complete `dependency_collector` —
      non-empty `"records"`/`"repository_evaluations"`, `"groups"` matching the policy, and an
      explicitly **empty** `"report"` (`compare()` is never called on this path) — this is the
      direct regression test for the report-lifecycle finding.
- [ ] **Step 3: Write a failing two-pass integration test** proving: divergence is limited to
      group members and ecosystem-qualified packages; a placeholder missing/duplicated/wrong-
      adapter raises; local failures are preserved through the fleet pass; every repo's
      `score`/`total`/`grade`/`coverage_*` reflects the post-fleet-pass `checks` dict; the
      durable `coverage["dependencies"]` produced in this task matches exactly what Task 6's
      snapshot serializes for the same run (both via `dependency_collector`); repository/
      aggregate/coverage summaries are computed exactly once, after both passes and after every
      score recomputation.
- [ ] **Step 4: Implement `dependency_pipeline.py` and the `evaluate_fleet` wiring** exactly
      per the sequence above, including extracting `_apply_dismissals`'s per-check logic into
      the reusable single-check helper. Register `python.dependencies`/`node.dependencies` in
      `adapters/__init__.py`'s `register_universal_adapters` (they are neutral, not overlay).
- [ ] **Step 5: Run focused/full tests and commit** with `feat: dispatch dependency coherence
      through an integrated two-pass pipeline with typed per-repo evaluation, a shared
      coverage-reconciliation source, and score reconciliation`.

**Checkpoint 2.** Do not proceed to Task 5/6 until this task's mixed-fleet and two-pass tests
are green, including the polyglot-repo, missing-evidence, overlapping-groups, and both score/
dismissal/collector-consistency regression tests named in Step 1.

---

### Task 5: Add scorecards and strict dependency policy integration

**Files:**
- Modify: `templates/profiles.yaml.template`
- Modify: `lib/references/healthcheck-checks.md`
- Modify: `lib/patterns/repository-profiles.md`
- Create: `lib/pulse/scripts/tests/test_dependency_dispatch.py`

**Interfaces:**

- Check id `python_manifest_lock_consistency` uses adapter `python.dependencies`; check id
  `node_manifest_lock_consistency` uses adapter `node.dependencies` — **two distinct check ids,
  never one shared id**, because `resolve_scorecard` rejects duplicate ids within one resolved
  scorecard and a polyglot repo's scorecard legally selects both.
- Check id `fleet_dependency_coherence` uses `fleet.dependencies.coherence` and is finalized
  only by Task 4's fleet pass (always, whether or not a policy file exists — see Task 4 step 3).
- `.hiivmind/github/dependencies.yaml` is required only when a selected scorecard contains the
  fleet check. Missing policy produces the stable `missing_policy` block plus a run error, per
  Task 4 — it never compares the whole fleet implicitly and never leaves an undismissed
  placeholder.

- [ ] **Step 1: Add failing template-load and dispatch tests** for Python, Node, a polyglot
      (both-ecosystem) repository whose scorecard selects both
      `python_manifest_lock_consistency` and `node_manifest_lock_consistency`, docs, Terraform,
      unclassified, and unsupported-ecosystem repositories. Include a test asserting a
      scorecard defining both check ids under distinct ids loads successfully through
      `load_profiles`/`resolve_scorecard`.
- [ ] **Step 2: Add Python and Node scorecard examples by extending `generic-v1`; do not add
      language checks to `generic-v1` itself.** Register unsupported-ecosystem examples with
      reasons so coverage debt is visible.
- [ ] **Step 3: Document repository-local versus fleet-second-pass scope, the evidence-state
      lattice and precedence reduction, the manager-workspace `unsupported`/
      `workspace_sentinel_unresolved` rules for both ecosystems, the distinct-check-id rule for
      polyglot repos, and the v1 Conda/cardinality scope cuts (link
      `docs/backlogs/2026-08-13-f4-deferred-scope.md`).**
- [ ] **Step 4: Run focused/full tests and commit** with `feat: register dependency
      scorecards`.

---

### Task 6: Define, serialize, and validate the content-free snapshot; close the exception-boundary content leak; wire the healthcheck result and headless skill

**Files:**
- Create: `lib/pulse/scripts/dependency_snapshot.py`
- Create: `lib/pulse/scripts/validate_dependency_snapshot.py`
- Modify: `lib/pulse/scripts/check_adapters.py` — fix the exception-message content leak
- Modify: `lib/pulse/scripts/validate_result.py` — validate the new `coverage.dependencies`
  field on the `healthcheck` kind
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `templates/workspace-gitignore.template`
- Modify: `lib/patterns/headless-contract.md`
- Create: `lib/pulse/scripts/tests/test_dependency_snapshot.py`
- Create: `lib/pulse/scripts/tests/test_validate_dependency_snapshot.py`
- Create: `lib/pulse/scripts/tests/test_dependency_healthcheck_skill.py`
- Create: `lib/pulse/scripts/tests/test_dependency_acceptance.py`
- Create: `lib/pulse/scripts/tests/test_dependency_content_free.py`
- Create: `lib/pulse/scripts/tests/test_check_adapters_error_boundary.py`

**Interfaces:**

```python
# lib/pulse/scripts/dependency_snapshot.py

def build_document(
    *,
    contract_version: int,
    generated_at: str,
    request_sha256: str,
    collector: dict[str, Any],   # exactly the dict evaluate_fleet's dependency_collector
                                  # populated — "records", "groups", "report",
                                  # "repository_evaluations"
    errors: tuple[str, ...],
) -> DependencySnapshotDocument:
    """Assembles the envelope from evaluate_fleet's collector output, calling
    reconcile_coverage(collector["repository_evaluations"], collector["groups"]) for
    DependencySnapshot.coverage — the SAME function Task 4 step 5 called for the durable
    coverage["dependencies"], over the SAME collected inputs. This is the driver-level glue
    that keeps the durable result and the transient snapshot from silently diverging."""

def serialize(document: DependencySnapshotDocument) -> dict:
    """Deterministic dict matching the wire schema below field-for-field with
    DependencySnapshotDocument/DependencySnapshot/PackageRecord/DivergenceFinding/
    DependencyCoverage/CoherenceGroup/RepositoryEvaluationSummary — every dataclass field has a
    named wire field and vice versa; no envelope field lacks a dataclass source."""
```

```python
# lib/pulse/scripts/check_adapters.py — fix, do not add new public API

# AdapterRegistry.evaluate's except-clause changes from:
#   f"Adapter {name} failed: {exc}"
# to a fixed template that never interpolates the caught exception's message, on ANY channel:
#   f"Adapter {name} raised an internal error"
# The exception's message is NEVER written anywhere — not the returned CheckBlock, not stdout,
# not stderr, not a log file, with no exception for any channel. There is no "may still be
# logged" carve-out; a separately secured diagnostic channel is future scope, out of F4.
```

Wire schema (`deps-snapshot.json`), **exactly matching `DependencySnapshotDocument` and every
nested dataclass field, including the redesigned `repository_evaluations` reconciliation
input**:

```yaml
contract_version: 1
generated_at: <ISO-8601>
request_sha256: <hex>              # identifies the selector request that produced this run
records:
  - repo: acme/api
    ecosystem: python              # package-namespace ecosystem (python | npm)
    name: requests
    resolution: single              # single | multiple
    manifest_range: ">=2.31,<3"
    locked_version: 2.32.0
    unresolved_reason: null
    manager: uv
    manifest_path: pyproject.toml   # null when resolution == multiple
    lock_path: uv.lock              # null when resolution == multiple, or lockless-supported
    tree_sha: <hex|null>            # F11 provenance — repo tree this record was derived from
    provenance:                     # every contributing artifact, role-associated
      - {role: manifest, path: pyproject.toml, blob_sha: <hex|null>}
      - {role: lock, path: uv.lock, blob_sha: <hex|null>}
groups:
  core-runtime:
    policy: same-minor
    repos: [acme/api, acme/worker]
    packages: ["python:requests", "npm:@acme/*"]
    exclude_packages: ["python:typing-extensions"]
findings:                           # flattened DivergenceReport.findings, sorted by
                                     # (group, ecosystem, package) — non-empty example:
  - group: core-runtime
    ecosystem: python
    package: requests
    versions: [[acme/api, "2.32.0"], [acme/worker, "2.30.0"]]
    distance: minor
unresolved:                         # flattened DivergenceReport.unresolved, same shape,
                                     # versions entries may be null
  - group: core-runtime
    ecosystem: npm
    package: "@acme/widgets"
    versions: [[acme/api, null], [acme/worker, "1.4.0"]]
    distance: unresolved
repository_evaluations:              # one entry per selected (repo, ADAPTER-SELECTION
                                      # ecosystem), sorted by (repo, ecosystem) — the
                                      # reconciliation input for `coverage` below
  - repo: acme/api
    ecosystem: python               # adapter-selection ecosystem (python | node)
    adapter: python.dependencies
    status: pass
    reason_code: null
    total_packages: 5
    matched_packages: 3
    partial_unsupported: 0
    group_memberships: [core-runtime]
coverage:                            # MUST equal reconcile_coverage(repository_evaluations,
                                      # groups) exactly — the validator recomputes and compares
  repositories_selected: 2
  repositories_grouped: 2
  repositories_ungrouped: 0
  groups_with_insufficient_members: []
  packages_matched: 12
  packages_unmatched: 3
  unsupported_by_adapter: {}
errors: []
```

`validate_dependency_snapshot.py` mirrors `validate_dependency_evidence.py`'s pattern exactly:
exact top-level/nested keys (including every `CoherenceGroup` and `RepositoryEvaluationSummary`
field), hex-string checks for `tree_sha`/`blob_sha`, enum checks for `resolution`/`distance`/
`policy`/`role`/`status`/ecosystem literals (rejecting `"node"` where the package-namespace
literal is required and vice versa), uniqueness of `(repo, ecosystem, name)` across **every**
record regardless of `resolution` (no exception for `"multiple"`), `findings`/`unresolved` are
disjoint by `(group, ecosystem, package)`, every `group` referenced by a finding exists in
`groups`, deterministic list ordering (`records` sorted by `(repo, ecosystem, name)`;
`findings`/`unresolved` by `(group, ecosystem, package)`; `repository_evaluations` by `(repo,
ecosystem)`), **`coverage` recomputed via `reconcile_coverage(repository_evaluations, groups)`
and compared field-for-field against the serialized `coverage` block — a mismatch is a contract
violation, not a warning**, and exit `0`/`1`/`2` (valid / contract violation / unreadable),
errors on stderr as plain structural strings only. This is a **standalone versioned artifact
validator**, the same pattern Pre-F4 used for `dependency-evidence.json` — it is not registered
as a `validate_result.py` `kind` (the snapshot is not one of the `*-result.yaml` headless result
kinds; it is a transient, gitignored, run-scoped artifact alongside the healthcheck result). The
**healthcheck result's** `coverage.dependencies` field (Task 4 step 5) *is* validated inside
`validate_result.py`'s existing `kind == "healthcheck"` branch, since that field is part of the
durable result.

**Content-free enforcement (round 3/4's exception-boundary/stderr fix):**
`test_dependency_content_free.py` injects a unique canary string into malformed manifest
lines, comment text, and a forced parser exception path in each adapter's fixtures, **and**
`test_check_adapters_error_boundary.py` forces `AdapterRegistry.evaluate` itself to catch an
exception whose message contains the canary (via a fake adapter that raises), asserting the
canary appears in **none** of: the serialized snapshot, the healthcheck result, captured
stdout, captured stderr (no exception — this stream is not exempted), or `errors`. This is in
addition to — not instead of — the schema validator; a canary test proves the negative
property, the validator proves the positive schema.

- [ ] **Step 1: Write failing static skill tests** requiring the sequence: F0/profile
      resolution → `dependency_selected_repos` → `DEPENDENCY_SELECTORS` materialization via
      `nave_adapter.materialize` → strict dependency-evidence validation → `evaluate_fleet`
      with the integrated two-pass pipeline and a `dependency_collector` dict passed →
      `dependency_snapshot.build_document(collector=...)` → `dependency_snapshot.serialize` →
      `validate_dependency_snapshot` → temporary content deletion.
- [ ] **Step 2: Fix the `check_adapters.py` exception-message content leak** (failing test
      first, then the one-line template fix — no exception text on any channel, per Global
      Constraints). This is a general dispatch-boundary fix, not dependency-specific — it
      benefits every registered adapter's error path.
- [ ] **Step 3: Update the skill.** It invokes `nave_adapter.py materialize`; it never calls
      GitHub raw-content APIs and never reads Nave cache paths. Missing protocol v2 writes
      dependency `unsupported` coverage while unrelated healthchecks continue.
- [ ] **Step 4: Add `deps-snapshot.json` and `dependency-evidence.json` to the workspace
      ignore template.** The latter remains run-temporary even though ignored.
- [ ] **Step 5: Add end-to-end acceptance** for uv, Poetry (every range-algorithm branch), PDM,
      pip-tools, Conda (mixed nested-pip/native), npm, pnpm, Yarn v1, docs, Terraform, and
      unknown-ecosystem fixtures, plus a Node-workspace fixture, a Python uv-workspace fixture
      (both asserting whole-check `unsupported`), a polyglot repo selecting both ecosystems, an
      overlapping-groups fixture exercising `group_memberships`, and one Python-marker fixture
      exercising genuine `resolution="multiple"`.
- [ ] **Step 6: Run the content-free canary suite (including the exception-boundary test with
      no stderr exemption), skill schema validation, `uv run pytest -q`, Ruff on changed
      Python, and `git diff --check`.**
- [ ] **Step 7: Add the isolated `uv run` subprocess acceptance test** invoking the exact
      production `healthcheck_dispatch.py` command (not an in-process pytest import) to prove
      the PEP 723 header actually carries the new runtime dependencies.
- [ ] **Step 8: Commit** with `feat: report ecosystem-aware dependency coherence`.

**Checkpoint 3.** Do not open the PR until the content-free canary suite (Step 6, including the
`AdapterRegistry.evaluate` boundary test with no stderr exemption) and the snapshot validator's
`coverage`-vs-`reconcile_coverage` reconciliation test — including the overlapping-groups and
`packages_unmatched` fixtures — both pass.

## F4 completion gate

- The workflow parses only validated Pre-F4 contents (through the typed `RepoEvidence` loader),
  never observational F0 paths as content.
- Every local dependency check is selected by an explicit scorecard, with the F1 capability
  signal passed explicitly into detection — never inferred from evidence alone. A repo may
  select both ecosystems under two distinct check ids; each is parsed exactly once.
- Missing dependency evidence (mapping-absent or repo-absent) is a typed pre-dispatch branch,
  never an unchecked lookup fed into a parser.
- Cross-repo comparison occurs only inside committed groups and ecosystem namespaces; ungrouped
  repositories are visible as coverage debt on the **durable healthcheck result**
  (`coverage.dependencies`), not only in the transient snapshot — and both are guaranteed
  consistent because both call the single shared `reconcile_coverage` over the same collected
  `RepositoryEvaluationSummary` objects.
- `RepositoryEvaluationSummary` carries per-group membership, total/matched package counts, and
  partial-unsupported counts sufficient for the validator to *recompute* every
  `DependencyCoverage` counter from serialized data — including on overlapping groups and mixed
  Conda repos — never merely assert it.
- The internal object bus is one typed `DependencyRepoEvaluation` per `(repo, ecosystem)`,
  produced once before dismissal logic runs, carrying every per-declaration range fact the
  local check needs — never a bare tuple of collapsed records that cannot represent multiple
  declarations against one resolution.
- Multi-resolution packages are explicit coverage debt (`resolution="multiple"`), reserved for
  genuine resolution ambiguity, never multi-declaration-with-one-resolution; manager-declared
  workspace repositories (Node `workspaces`/`pnpm-workspace.yaml`, Python
  `[tool.uv.workspace]`) are explicit `unsupported` coverage, and an unresolved workspace
  sentinel is explicit `unknown` — never a guessed per-member comparison the static selector
  set cannot back with real evidence.
- Unsupported managers/ecosystems (including native Conda specs and workspace repositories) and
  unavailable materialization are visible coverage states; `error` is reserved for
  adapter-internal failure only.
- A fleet finding's `distance` is the coarsest pairwise distance across every fully-resolved
  member, for groups of any size — never left undefined for 3+ member groups.
- Every version-comparison edge case named across four review rounds — PEP 440 epoch, equal-
  length-but-unequal releases (`2.dev1` vs `2`), and every syntactically valid Poetry constraint
  form (caret, tilde, comma-compound, bare exact, prefix wildcard) — is decided by an explicit,
  executable rule, never left to implementer judgment.
- `fleet_dependency_coherence` is finalized inside the same `evaluate_fleet` pass as local
  checks — always, as a complete normalized `CheckBlock`, whether or not a policy file exists —
  with dismissals applied exactly once per check id, every affected repo's score/grade/coverage
  **recomputed in place**, and fleet-wide score/coverage arithmetic computed exactly once, after
  both passes and after every recomputation.
- `deps-snapshot.json` matches a versioned envelope schema 1:1 with its dataclasses (including
  full `CoherenceGroup` fields, role-associated artifact provenance, and per-repository
  evaluation summaries sufficient for its validator to *recompute and verify* every coverage
  counter), is built from `evaluate_fleet`'s own `dependency_collector` output (never
  reconstructed from public blocks), is validated by a dedicated validator, is content-free
  (schema-checked *and* canary-tested at every boundary including `AdapterRegistry.evaluate`'s
  exception path on every output channel), transient, and gitignored.
- The production `healthcheck_dispatch.py` entry point runs successfully as an isolated
  `uv run` script with the new runtime dependencies — not only inside the pytest dev
  environment.
- Neutral fixtures cover every supported manager family, including genuine multi-resolution,
  both ecosystems' workspace-unsupported handling, mixed Conda nested-pip/native, every branch
  of the Poetry range-conversion algorithm, overlapping coherence groups, and a polyglot repo;
  plugin-specific manifests remain deferred to F9.

## Deferred to backlog (not in this phase's scope — see `docs/backlogs/2026-08-13-f4-deferred-scope.md`)

- Full per-declaration/per-resolution `PackageRecord` cardinality modeling, including a real
  two-phase materialize round-trip for **both** ecosystems' manager-declared workspace members
  (npm/pnpm workspaces and Python uv workspaces — v1 marks whole workspace repos `unsupported`
  instead) and Python markers/extras/optional-groups beyond v1's "mark genuine multi-resolution
  as unresolved coverage debt."
- Full Conda ecosystem support (MatchSpec-aware channel/subdir/build identity, native
  non-Python packages), beyond v1's "parse only the nested `pip:` section, per-record."
- The F11 apply-mode handoff object (constructing a guarded fleet-bump proposal's `selection`/
  `expected_shas`/transformation strategy/`bound_paths` from a `DivergenceFinding`) — F4 v1
  now preserves role-associated provenance (`tree_sha`, `provenance: (role, path, blob_sha)`)
  that handoff will need; building the handoff object itself is F11's job.
- Per-package policy overrides beyond the narrower-coherence-group idiom, if that idiom proves
  insufficient in practice.
