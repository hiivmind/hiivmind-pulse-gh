# F3: Dispatched Fleet Healthchecks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn healthcheck into a generic fleet shell that evaluates explicit scorecards through registered adapters and reports profile-specific scores plus fleet coverage debt.

**Architecture:** `healthcheck_dispatch.py` consumes F0 evidence and F1 dispatch plans, invokes pure adapter entry points, and sends normalized check blocks to `evaluate_checks.py`. Universal adapters cover GitHub governance facts; profile adapters are registered separately. The headless skill performs orchestration only and never computes scores.

**Tech Stack:** Python 3.10+ PEP 723, PyYAML, pytest, F0/F1 contracts.

## Global Constraints

- A check runs only when present in the resolved scorecard and applicable.
- Adapter failures become `error`; missing adapter implementation becomes `unsupported`.
- The skill never performs arithmetic or changes check states.
- Adapter output must cite evidence paths/refs and contain `check_id`, `adapter`, `status`, `detail`, `data`, `weight`.
- Fleet aggregate groups results by scorecard and reports coverage debt separately.

---

### Task 1: Define adapter registry and output contract

**Files:**
- Create: `lib/pulse/scripts/check_adapters.py`
- Create: `lib/pulse/scripts/tests/test_check_adapters.py`
- Modify: `lib/patterns/healthcheck-evaluation.md`

**Interfaces:**
- `AdapterRegistry.register(name, fn)`.
- `AdapterRegistry.evaluate(name, context) -> CheckBlock`.
- `CheckContext(repo, evidence, check, workspace)`.

- [ ] **Step 1: Write failing registry tests**

```python
def test_missing_adapter_is_unsupported():
    out = AdapterRegistry().evaluate("rust.lockfiles", context())
    assert out["status"] == "unsupported"
    assert out["adapter"] == "rust.lockfiles"

def test_adapter_exception_is_error():
    registry = AdapterRegistry()
    registry.register("broken", lambda _: 1 / 0)
    assert registry.evaluate("broken", context())["status"] == "error"
```

- [ ] **Step 2: Verify red**, implement immutable context and normalized output validation.
- [ ] **Step 3: Run tests and commit** with `feat: add healthcheck adapter registry`.

---

### Task 2: Implement universal GitHub adapters

**Files:**
- Create: `lib/pulse/scripts/adapters/generic.py`
- Create: `lib/pulse/scripts/adapters/__init__.py`
- Create: `lib/pulse/scripts/tests/test_generic_adapters.py`

**Interfaces:**
- Adapters: `generic.ci`, `generic.documentation`, `generic.license`, `github.branch_protection`, `github.security_policy`.

- [ ] **Step 1: Write failing tests** for pass/warn/fail/unknown using existing `checks/good` and `checks/bare` fixtures plus documentation-only and archived fixtures.
- [ ] **Step 2: Verify red**, move existing generic logic from `evaluate_checks.py` into pure adapter functions without changing outcomes.
- [ ] **Step 3: Assert no adapter references Claude/plugin paths**.
- [ ] **Step 4: Run focused/full tests and commit** with `refactor: extract universal healthcheck adapters`.

---

### Task 3: Build the dispatch engine

**Files:**
- Create: `lib/pulse/scripts/healthcheck_dispatch.py`
- Create: `lib/pulse/scripts/tests/test_healthcheck_dispatch.py`

**Interfaces:**
- CLI: `healthcheck_dispatch.py --evidence FILE --profiles FILE --workspace FILE`.
- Output: `{repos, aggregate, coverage}` ready for healthcheck result wrapping.

- [ ] **Step 1: Write failing heterogeneous dispatch test** asserting Python, Node, docs, Terraform, plugin, and unknown fixtures receive only their resolved checks.
- [ ] **Step 2: Verify red**, implement `dispatch -> registry.evaluate -> score_checks` pipeline.
- [ ] **Step 3: Implement aggregate shape**:

```yaml
coverage:
  checks_total: 20
  checks_supported: 16
  unsupported_by_adapter: {terraform.lockfiles: 2, rust.lockfiles: 2}
  unprofiled_repos: [acme/unknown]
by_scorecard:
  python-service-v1: {repos: 3, average_percent: 82.5}
```

- [ ] **Step 4: Verify deterministic ordering and commit** with `feat: dispatch heterogeneous fleet healthchecks`.

---

### Task 4: Rewire the headless healthcheck skill

**Files:**
- Modify: `skills/gh-healthcheck-headless/SKILL.md`
- Modify: `lib/patterns/headless-contract.md`
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `healthcheck_dispatch.py` JSON and F0/F1 contracts.
- Produces: validated `healthcheck-result.yaml` with per-repo scorecard and fleet coverage.

- [ ] **Step 1: Add contract tests** for required repo `scorecard` and fleet `coverage` fields.
- [ ] **Step 2: Update skill phases**: obtain F0 evidence → load F1 profiles → run F3 dispatch → apply dismissals → validate result. Remove raw manifest fetching duplicated by Nave.
- [ ] **Step 3: Run `uv run pytest -q`** → PASS.
- [ ] **Step 4: Commit** with `feat: dispatch fleet healthchecks by scorecard`.

---

### Task 5: Add acceptance and regression gates

**Files:**
- Create: `lib/pulse/scripts/tests/test_fleet_healthcheck_acceptance.py`

**Interfaces:**
- Consumes: the complete F3 adapter/dispatch path.
- Produces: regression gate proving profile-safe behavior across neutral repository fixtures.

- [ ] **Step 1: Add acceptance cases**: missing `CLAUDE.md` outside plugin profile is absent/not-applicable; missing `pyproject.toml` outside Python is absent/not-applicable; unsupported Terraform adapter creates coverage debt; unknown profile runs universal checks only.
- [ ] **Step 2: Run acceptance test** → PASS.
- [ ] **Step 3: Run full suite and `git diff --check`** → clean.
- [ ] **Step 4: Commit** with `test: gate profile-safe fleet healthchecks`.
