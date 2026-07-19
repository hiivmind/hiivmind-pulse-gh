# F7: Generated Artifact and Contract Binding Specializations Implementation Plan

> **Execution mode (revised 2026-07-19):** execute directly in a single session on the
> main thread — no per-task subagents, no per-task reviewers. TDD per task, one commit
> per task, one adversarial whole-branch review at the end of the phase, then PR.
> Stacked branch `feat/f7-binding-specializations` off the F6 head. The
> subagent-per-task pattern used for F1–F6 spent most of its tokens on cold-start
> context re-derivation and is retired.

**Goal:** Add generic generated-artifact drift and contract-version propagation as adapter-driven specializations of the shared binding and Nave mutation infrastructure.

**Architecture:** `generated.yaml` (workspace config repo, template `templates/generated.yaml.template`) records content-addressed template trees and generated-file blob bases. Generator adapters declare source/output paths and reference a registered F6 transformation; F6 pens execute them. Contract edges extend F5 impact edges with explicit producer/consumer version parsers. Claude/corpus examples are deferred to F9 overlays.

**Tech Stack:** Python 3.10+, PyYAML, `packaging` (+ `tomli; python_version<'3.11'` — declare in the PEP 723 header; `tomllib` is stdlib only from 3.11), pytest, git, Nave pens.

## What already exists (verified 2026-07-19, F6 head)

- `lib/pulse/scripts/impact.py` — `_glob_to_regex` (where `*` never crosses `/`, `**` does), `audit(relationships, snapshot) -> ImpactReport`, `mark(...)` with `_atomic_write_yaml` temp+rename CAS marker patch, `propose_marks`/`apply_proposals`. Reuse these idioms verbatim.
- `lib/pulse/scripts/impact_snapshot.py` — `default_runner` seam, `_valid_sha`/`_valid_branch` argv guards, `_resolve_fetched_head` (FETCH_HEAD is always the diff endpoint). Import `default_runner` from here; do not write a second runner.
- `lib/pulse/scripts/mutation_plan.py` — `load_registry`, `build_proposal(id, selection, transformation, expected_shas, actor, mutation_policy)` (requires exact `expected_shas` coverage of `selection`), `resolve_argv` (byte-verbatim, no interpolation), `ValidationSpec` kinds `{none, json_schema}`.
- `lib/pulse/scripts/pen_orchestrator.py` — `execute(plan, nave_adapter, *, read_repo_file=None, read_repo_head=None)`, propose-only, fail-closed; blocks on missing SHA coverage.
- `lib/pulse/scripts/profile_dispatch.py` — `_is_applicable` grammar: `always`, `profile:<id>`, `capability:<id>`, `evidence_path:<glob>` (fnmatchcase). Generators reuse this grammar for `applies_to`.
- `lib/pulse/scripts/validate_result.py` — kind-dispatched `validate(data, kind)`; common envelope (`contract_version`, `kind`, `workspace`, `run_at`, `actor`, `errors`) validated for every kind; no exact-top-level-key enforcement inside this file (deliberate — match siblings).
- Content-addressing primitive: `git rev-parse <sha>:<dir>` yields the **tree object SHA** for a directory at a commit; `git rev-parse <sha>:<file>` yields the **blob SHA**. These are the template-tree and file-base hashes — no bespoke hashing.

## Global Constraints

- Generated drift uses source directory tree hashes, never repository HEAD alone.
- Generated files record blob bases; both-sides-changed is a conflict.
- Generator identity, source paths, output paths, and validation are explicit configuration; the executed argv lives **only** in the F6 transformation registry (the generator references a `transformation:` id — one argv source, no duplication; this refines the roadmap's `command_argv` field into a registry reference).
- No LLM may infer or execute a generator.
- Contract versions come from explicit files/parsers; prose inference is forbidden.
- All repository-file application routes through F6 (`build_proposal` → `pen_orchestrator.execute`).

---

### Task 1: Define generic generation bindings

**Files:**
- Create: `lib/patterns/generation-manifest.md`
- Create: `templates/generated.yaml.template`
- Modify: `lib/pulse/scripts/validate_result.py`
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`

**Interfaces:**
- Manifest binding: `{id, source (owner/repo), branch, template_path, template_tree (tree SHA), generator (generator id), files: [{path, blob}], generated_at (ISO)}`. `files[].path` are repo-relative output paths; duplicate paths across one binding are invalid; a binding with empty `files` is invalid (nothing to guard).
- Result kind `generated-artifact`: envelope + `bindings_audited (int)`, `states (mapping binding id -> current|template-drift|local-customization|conflict|error)`, `findings (list, same finding shape as impact kind: {kind, repo, severity, detail})`, `proposals (list of {binding, transformation, proposal_id} — present only for template-drift)`.

**Steps:**
- [ ] **Step 1: Tests** — valid manifest passes; duplicate `files[].path` fails; missing `template_tree`/`blob` fails; unknown-generator reference is a *load-time* error surfaced by the Task 3 loader (result-kind tests here cover: valid result, each missing/mistyped field, invalid state enum, findings shape). Follow the `repo-mutation` test additions (fixture + parametrized missing-key/wrong-type) added in F6 Task 4 as the template.
- [ ] **Step 2: Implement** the `generated-artifact` branch in `validate_result.py` (style-match the `impact` and `repo-mutation` branches exactly) and write `generation-manifest.md` + the template with commented examples (mirror `relationships.yaml.template`'s comment-heavy style).
- [ ] **Step 3: Run tests and commit** with `feat(contract): define generated artifact bindings`.

---

### Task 2: Implement backfill, audit, and guarded advancement

**Files:**
- Create: `lib/pulse/scripts/generated_artifacts.py`
- Create: `lib/pulse/scripts/tests/test_generated_artifacts.py`

**Interfaces (all pure; snapshot injected; the only I/O lives in `collect` and `advance`):**
- `backfill(binding_input, snapshot) -> ManifestEntry` — resolves current tree/blob SHAs for a new binding from the snapshot (first registration records reality as the base).
- `audit(manifest, snapshot) -> GeneratedReport` — per binding, compare `template_tree` vs snapshot tree and each `files[].blob` vs snapshot blob. Classification (fail-closed): tree same + all blobs same → `current`; tree changed + blobs same → `template-drift` (regeneration proposal warranted); tree same + any blob changed → `local-customization` (finding, **no** proposal); tree changed + any blob changed → `conflict` (finding, no proposal); any output path missing from snapshot → `error` + `missing_output` finding (no proposal); binding's repo/branch absent from snapshot → `error` + `snapshot_gap` finding.
- `advance(path, binding_id, expected_tree, new_tree, files, generated_at) -> MarkerResult` — CAS marker patch: reject when the on-disk binding's `template_tree != expected_tree` (mirror `impact.mark()`'s guard + `_atomic_write_yaml` temp+rename exactly).
- Snapshot shape (extends the F5 convention): `{repo: {branch: {head, trees: {path: tree_sha}, blobs: {path: blob_sha}}}}`. Collection: `collect(manifest, workdir=None, runner=default_runner)` in this module, reusing `impact_snapshot.default_runner` and its argv-guard style, and `git rev-parse FETCH_HEAD:<path>` after a single fetch per repo/branch. A path that does not exist at the head resolves to absent (drives `missing_output`), never an exception.

**Steps:**
- [ ] **Step 1: Write failing tests** for every classification cell above, plus: no-op same-tree audit produces zero findings; `advance` guarded update (stale `expected_tree` rejected, matching one applied); repeat `advance` idempotence; `backfill` of a repo missing from snapshot fails closed.
- [ ] **Step 2: Verify red, implement.** Keep `audit` free of git calls.
- [ ] **Step 3: Run tests and commit** with `feat: audit generated artifact currency`.

---

### Task 3: Register generator adapters and Nave transformations

**Files:**
- Create: `templates/generators.yaml.template`
- Modify: `templates/transformations.yaml.template`
- Create: `lib/pulse/scripts/generator_dispatch.py`
- Create: `lib/pulse/scripts/tests/test_generator_dispatch.py`

**Interfaces:**
- Generator entry: `{id, applies_to (profile_dispatch grammar), transformation (registered F6 transformation id — the ONLY argv source), source_paths (list of globs), output_paths (list of globs — allowlist), validation (ValidationSpec shape)}`.
- `load_generators(data, registry) -> dict[str, Generator]` — fail-closed: unknown `transformation` id, empty `output_paths`, or a shell-string `command` key (explicitly rejected with a message pointing at the registry) are load errors.
- `dispatch(generator, binding, snapshot, actor, mutation_policy="propose") -> Proposal` — builds `mutation_plan.build_proposal` with `selection=[binding.source]`, `expected_shas={binding.source: snapshot head}`, the generator's `transformation`. Output-allowlist enforcement: the binding's `files[].path` must all match `output_paths` globs (share `impact._glob_to_regex` via a helper — do not re-implement glob matching); any path outside the allowlist is a dispatch-time error, no proposal.

**Steps:**
- [ ] **Step 1: Tests** — explicit selection happy path; missing generator id; binding output outside allowlist; shell-string rejection; `applies_to` profile mismatch produces no dispatch; the built Proposal round-trips through `pen_orchestrator.execute`'s expected-SHA guard with a matching `read_repo_head` stub.
- [ ] **Step 2: Implement** dispatcher producing an F6 mutation proposal. Register one neutral example transformation (e.g. `regenerate-from-template`) in `transformations.yaml.template` with `allow_scheduled: false`.
- [ ] **Step 3: Verify and commit** with `feat: dispatch configured generators through Nave`.

---

### Task 4: Add contract edge parsers

**Files:**
- Create: `lib/pulse/scripts/contract_versions.py`
- Create: `lib/pulse/scripts/tests/test_contract_versions.py`
- Modify: `templates/relationships.yaml.template`
- Modify: `lib/pulse/scripts/impact.py`

**Interfaces:**
- Edge extension (optional `contract:` block on a `depends_on` object edge):
  `contract: {producer: {path, parser}, consumer: {path, parser}, version_scheme: pep440}`.
- Parser spec (v1): `{kind: regex, pattern}` — exactly one capture group, enforced at load; `{kind: toml, key}` — dotted key; `{kind: json, pointer}` — RFC 6901 JSON pointer; `{kind: yaml, key}` — dotted key. Any parse/extract failure → `unknown`, never a guess.
- `extract(parser_spec, content_bytes) -> str | None` — pure.
- `evaluate(edge, read_file) -> ContractState` — `read_file(repo, path) -> bytes` is an injectable reader (same seam shape as `pen_orchestrator.read_repo_file`); returns `compatible | gap | unknown` plus extracted versions for attribution. Comparison uses `packaging.specifiers` **only** when `version_scheme: pep440` is declared; no scheme → string equality, documented.
- Composition with F5: `impact.audit` gains optional `contract_reader=None`; when an edge has a `contract:` block and a reader is supplied, the edge's result row gains `contract_state`; an edge BOTH path-stale and contract-gap yields **one** finding carrying both facts (dedupe test required). Contract block + no reader → `contract_state: unknown` + low-severity `unevaluated_contract` finding (fail-closed convention, mirrors `empty_watch_paths`).

**Steps:**
- [ ] **Step 1: Tests** for every parser kind (valid, invalid version, missing path/key/pointer), regex with ≠1 capture group rejected at load, compatible/gap/unknown, dual-finding dedupe, no-reader unknown.
- [ ] **Step 2: Implement pure extraction and compose with F5**; one edge counts stale once.
- [ ] **Step 3: Run tests and commit** with `feat: specialize impact edges for contracts`.

---

### Task 5: Add generic headless workflow

**Files:**
- Create: `skills/gh-generated-artifact-headless/SKILL.md`
- Create: `templates/workflows/generated-artifact-audit.yaml`
- Modify: `templates/workspace-gitignore.template`

**Interfaces:**
- Skill phases: SNAPSHOT → AUDIT → CONFLICT/PROPOSE → optional F6 PEN → RECORD, writing `generated-artifact-result.yaml` validated by Task 1's kind. Model on `skills/gh-impact-audit-headless/SKILL.md` (structure, STOP conditions, explicit inputs, `validate_result.py` invocation) — same length band, orchestration-only, `See:` references.
- Workflow template models on `templates/workflows/impact-audit.yaml`; must pass `workflow_lint.py`.

**Steps:**
- [ ] **Step 1: Write skill + workflow**; add the result file to `workspace-gitignore.template` (transient, like the other `*-result.yaml`).
- [ ] **Step 2: Neutrality test** — assert the strings `claude`, `corpus`, `plugin manifest`, `SKILL.md` do not appear (case-insensitive) in `generated_artifacts.py`, `generator_dispatch.py`, the new skill, or the new workflow. Overlay specifics belong to F9.
- [ ] **Step 3: Run full suite and commit** with `feat: add generic generated artifact workflow`.

---

### Task 6: Add split-repo configuration as an impact example

**Files:**
- Create: `templates/relationships/split-repo-tests.yaml`
- Modify: `lib/patterns/workflow-execution.md`
- Modify: `lib/pulse/scripts/tests/test_impact.py`

**Interfaces:**
- A reusable relationships overlay: test repo depends on source repo with `watch_paths: ["**"]` (full tree — `**` crosses `/` per `_glob_to_regex`) and a configured `integration_workflow`. No new workflow, no new result kind — this is configuration proving F5 already covers the split-repo case (e.g. `hiivmind-pulse-gh-tests` ← `hiivmind-pulse-gh`).

**Steps:**
- [ ] **Step 1: Fixture + tests** — full-tree edge goes stale on any upstream path change; successful configured-workflow evidence advances the marker via `propose_marks`/`apply_proposals`.
- [ ] **Step 2: Document** in `workflow-execution.md` § loop-closure that this is configuration, not a new workflow.
- [ ] **Step 3: Verify and commit** with `docs: add split repository impact binding`.
