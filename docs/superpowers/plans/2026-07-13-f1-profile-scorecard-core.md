# F1: Repository Profiles and Scorecard Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make repository intent, scorecard selection, applicability, and coverage debt explicit and deterministic.

**Architecture:** Workspace YAML stores authoritative profiles and scorecards. A pure dispatcher resolves inheritance, rejects duplicate checks, evaluates applicability against normalized evidence, and returns an execution plan. Scoring is computed centrally from typed check states; profile proposals remain separate from authoritative metadata.

**Tech Stack:** Python 3.10+ PEP 723, PyYAML, pytest.

## Global Constraints

- Authoritative profiles live in committed workspace metadata.
- Detectors cannot change profiles or scorecards; they emit proposals only.
- Check states are exactly `pass`, `warn`, `fail`, `unknown`, `not_applicable`, `unsupported`, `error`.
- `not_applicable` and `unsupported` are excluded from score denominators.
- `unsupported` increments coverage debt.
- Child scorecards may replace a parent check only with `replace: true`.
- One resolved check ID is evaluated once per repository.

---

### Task 1: Define workspace profile and scorecard schemas

**Files:**
- Create: `lib/patterns/repository-profiles.md`
- Create: `templates/profiles.yaml.template`
- Modify: `lib/references/config-schema.md`
- Create: `lib/pulse/scripts/profile_dispatch.py`
- Create: `lib/pulse/scripts/tests/test_profile_dispatch.py`

**Interfaces:**
- `load_profiles(path) -> ProfileConfig`.
- Profile config keys: `repository_profiles`, `scorecards`, `adapters`.

- [ ] **Step 1: Write failing schema-load tests**

```python
def test_loads_explicit_repo_profile(tmp_path):
    path = write_yaml(tmp_path, {
        "repository_profiles": {"acme/api": {"profiles": ["python", "service"],
                                                 "scorecard": "python-service-v1"}},
        "scorecards": {"python-service-v1": {"checks": []}},
        "adapters": {},
    })
    cfg = load_profiles(path)
    assert cfg.repositories["acme/api"].scorecard == "python-service-v1"

def test_rejects_unknown_scorecard(tmp_path):
    path = write_yaml(tmp_path, {"repository_profiles": {"acme/api": {
        "profiles": ["python"], "scorecard": "missing"}}, "scorecards": {}, "adapters": {}})
    with pytest.raises(ConfigError, match="unknown scorecard: missing"):
        load_profiles(path)
```

- [ ] **Step 2: Verify red**, implement dataclasses `RepositoryProfile`, `CheckDefinition`, `Scorecard`, `ProfileConfig`, and strict YAML validation.
- [ ] **Step 3: Run tests**: `uv run pytest lib/pulse/scripts/tests/test_profile_dispatch.py -v` → PASS.
- [ ] **Step 4: Commit** with `feat: define repository profile metadata`.

---

### Task 2: Resolve scorecard inheritance and applicability

**Files:**
- Modify: `lib/pulse/scripts/profile_dispatch.py`
- Modify: `lib/pulse/scripts/tests/test_profile_dispatch.py`

**Interfaces:**
- `resolve_scorecard(config, scorecard_id) -> tuple[CheckDefinition, ...]`.
- `dispatch(repo, evidence, config) -> DispatchPlan`.

- [ ] **Step 1: Add inheritance tests**

```python
def test_child_must_explicitly_replace_parent_check(config):
    config.scorecards["child"].extends = "base"
    config.scorecards["child"].checks = [check("ci", "other.adapter")]
    with pytest.raises(ConfigError, match="duplicate check ci requires replace: true"):
        resolve_scorecard(config, "child")

def test_applicability_excludes_absent_capability(config):
    plan = dispatch("acme/lib", evidence(capabilities=["python"]), config)
    assert plan.checks["claude-context"].state == "not_applicable"
```

- [ ] **Step 2: Verify red**, then implement applicability predicates `always`, `profile:<id>`, `capability:<id>`, and `evidence_path:<glob>`. Unsupported predicates are configuration errors.
- [ ] **Step 3: Verify green and commit** with `feat: dispatch scorecards by repository intent`.

---

### Task 3: Extend healthcheck result states and centralized scoring

**Files:**
- Modify: `lib/pulse/scripts/validate_result.py`
- Modify: `lib/pulse/scripts/evaluate_checks.py`
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`
- Modify: `lib/pulse/scripts/tests/test_evaluate_checks.py`
- Modify: `lib/patterns/headless-contract.md`

**Interfaces:**
- Check block adds required `check_id`, `adapter`, and optional `profile`.
- Repo block adds `scorecard`, `coverage_supported`, `coverage_total`.

- [ ] **Step 1: Add failing state/scoring tests**

```python
def test_non_applicable_and_unsupported_do_not_enter_denominator():
    checks = {
        "ci": block("pass", weight=2),
        "claude": block("not_applicable", weight=1),
        "cargo": block("unsupported", weight=2),
    }
    out = score_checks(checks)
    assert out.score == 2 and out.total == 2
    assert out.coverage_supported == 3 and out.coverage_total == 5
```

- [ ] **Step 2: Verify red**, extend `CHECK_STATUSES`, then move all score/coverage arithmetic into `evaluate_checks.py`.
- [ ] **Step 3: Run focused tests** → all PASS.
- [ ] **Step 4: Document scorecard-specific grades** and the prohibition on comparing grades without scorecard IDs.
- [ ] **Step 5: Commit** with `feat: score profile checks with coverage debt`.

---

### Task 4: Add neutral scorecard fixtures

**Files:**
- Create: `lib/pulse/scripts/tests/fixtures/profiles/profiles.yaml`
- Create: `lib/pulse/scripts/tests/fixtures/profiles/evidence.yaml`
- Create: `lib/pulse/scripts/tests/test_profile_acceptance.py`

**Interfaces:**
- Fixture repos: `acme/python-lib`, `acme/python-service`, `acme/node-web`, `acme/docs`, `acme/terraform`, `acme/plugin`, `acme/unknown`.

- [ ] **Step 1: Write acceptance test** asserting each fixture resolves to the intended scorecard, plugin checks are `not_applicable` outside `acme/plugin`, and Terraform dependency adapter is `unsupported` rather than fail.
- [ ] **Step 2: Run test to verify fixture/schema gaps**, add exact scorecard definitions, rerun to PASS.
- [ ] **Step 3: Run full suite**: `uv run pytest -q` → PASS.
- [ ] **Step 4: Commit** with `test: cover heterogeneous repository scorecards`.
