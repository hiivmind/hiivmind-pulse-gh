# F6: Nave Pen Mutation Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route repository-file mutations through Nave pen workspaces with freshness, cleanliness, validation, attribution, and mutation-policy gates.

**Architecture:** Pulse creates a typed mutation proposal, selects repositories through Nave queries, creates a pen, executes a pinned transformation command, validates pen state and schemas, and only then proposes commit/push/PR actions. Arbitrary commands require explicit approval; automatic mode permits only registered transformation IDs.

**Tech Stack:** Python 3.10+, PyYAML, pytest, `nave pen`, git, gh CLI.

## Global Constraints

- Repository-file mutations use Nave pens; no workflow creates a second multi-repo checkout system.
- `nave pen exec` arbitrary commands are user-gated unless mapped to a registered transformation.
- Default mutation policy is propose-only: create/run locally, no push.
- Stale or dirty pens block application.
- Pulse records actor, machine, Nave version, pen name, selection, command ID, and per-repo outcome.
- Pulse does not parse human pen status; require supported `--json` output.

---

### Task 1: Extend the Nave adapter with pen JSON operations

**Files:**
- Modify: `lib/pulse/scripts/nave_adapter.py`
- Modify: `lib/pulse/scripts/tests/test_nave_adapter.py`
- Create: `lib/pulse/scripts/tests/fixtures/nave/pen/`

**Interfaces:**
- `pen_create(runner, query, name) -> PenHandle`.
- `pen_show`, `pen_status`, `pen_exec` return normalized JSON.

- [ ] **Step 1: Add command-array and JSON tests** for create/show/status/exec; assert no `--push-changes` unless explicitly requested.
- [ ] **Step 2: Verify red**, implement supported commands and capability checks.
- [ ] **Step 3: Run tests and commit** with `feat: control Nave pen lifecycle`.

---

### Task 2: Define mutation proposal and transformation registry

**Files:**
- Create: `lib/patterns/repository-mutations.md`
- Create: `templates/transformations.yaml.template`
- Create: `lib/pulse/scripts/mutation_plan.py`
- Create: `lib/pulse/scripts/tests/test_mutation_plan.py`

**Interfaces:**
- Proposal: `{id, selection, transformation, expected_shas, mutation_policy, actor}`.
- Registry entry: `{id, command_argv, applies_to, validation, allow_scheduled}`.

- [ ] **Step 1: Test registry loading**, unknown transformation, shell metacharacters as literal argv, scheduled disallow, and expected SHA requirements.
- [ ] **Step 2: Implement strict argv registry**; no shell strings or template command substitution.
- [ ] **Step 3: Run tests and commit** with `feat: define safe repository transformations`.

---

### Task 3: Implement pen execution state machine

**Files:**
- Create: `lib/pulse/scripts/pen_orchestrator.py`
- Create: `lib/pulse/scripts/tests/test_pen_orchestrator.py`

**Interfaces:**
- States: `planned -> created -> executed -> validated -> proposed | blocked | failed`.
- `execute(plan, nave_adapter) -> PenRunResult`.

- [ ] **Step 1: Write failing state tests** for stale pen, dirty-before-run, command failure in one repo, schema failure, propose-only success, and forbidden push.
- [ ] **Step 2: Verify red**, implement fail-closed state transitions and per-repo outcomes.
- [ ] **Step 3: Run tests and commit** with `feat: orchestrate Nave pen mutations safely`.

---

### Task 4: Connect mutation policy and result contracts

**Files:**
- Modify: `lib/patterns/headless-contract.md`
- Modify: `lib/pulse/scripts/validate_result.py`
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`
- Modify: `skills/gh-operations/SKILL.md`

**Interfaces:**
- Consumes: `PenRunResult` and Pulse headless mutation policy.
- Produces: validated result kind `repo-mutation` and operation routing by mutation state type.

- [ ] **Step 1: Add result kind `repo-mutation`** with pen/run/actor/outcome fields.
- [ ] **Step 2: Update operations routing**: repo-file proposal → pen orchestrator; GitHub object mutation → existing gh operation.
- [ ] **Step 3: Run full suite and commit** with `feat: route repository writes through Nave pens`.

---

### Task 5: Add fixture end-to-end transaction

**Files:**
- Create: `lib/pulse/scripts/tests/test_pen_acceptance.py`

**Interfaces:**
- Consumes: fixture Nave pen responses and registered transformation plans.
- Produces: end-to-end regression proof for local-only, stale-blocked, attributed pen transactions.

- [ ] **Step 1: Simulate a two-repo pen** where one repo changes and one no-ops; assert no push, valid result, exact attribution, and repeat idempotence.
- [ ] **Step 2: Simulate stale remote SHA** and assert block before exec.
- [ ] **Step 3: Run `uv run pytest -q` and commit** with `test: gate Nave pen transactions`.
