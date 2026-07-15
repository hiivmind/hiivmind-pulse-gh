# F5: Generic Impact Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect path-scoped upstream drift beyond each dependency edge's last validated SHA and expose reusable integration-currency findings and gates.

**Architecture:** Object-shaped relationship edges carry watched paths, branch, validated SHA, and optional validation workflow. `impact.py` consumes remote pushed refs and changed-file evidence, independent of repository profile. Pulse owns tracking issues/workflow dispatch and marker PR proposals; F0/Nave may supply cached path evidence but never marker authority.

**Tech Stack:** Python 3.10+, PyYAML, pytest, git, gh CLI.

## Global Constraints

- Currency is `git diff tested_sha..remote_head -- watch_paths`.
- `integration_tested_sha` is committed shared state.
- Missing/unreachable baselines block closed.
- Local working-tree content is never a binding side.
- Severity inference may annotate a finding but cannot change stale/current state.
- Marker updates are expected-base guarded and idempotent.

---

### Task 1: Define edge and result contracts

**Files:**
- Modify: `templates/relationships.yaml.template`
- Modify: `lib/references/config-schema.md`
- Modify: `lib/pulse/scripts/validate_result.py`
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`
- Modify: `lib/patterns/headless-contract.md`

**Interfaces:**
- Produces: dependency edge `{repo, watch_paths, watch_branch, integration_tested_sha, tested_at, integration_workflow}` and result kind `impact`.

- [ ] **Step 1: Add tests** for object edges and `impact` result fields `edges_checked`, `edges_stale`, `markers_updated`.
- [ ] **Step 2: Implement schema/validator**, retaining string edges as legacy `unconfigured_edge` findings.
- [ ] **Step 3: Run tests and commit** with `feat(contract): define impact binding edges`.

---

### Task 2: Implement pure impact audit

**Files:**
- Create: `lib/pulse/scripts/impact.py`
- Create: `lib/pulse/scripts/tests/test_impact.py`

**Interfaces:**
- `audit(relationships, snapshot) -> ImpactReport`.
- `mark(path, dependent, upstream, expected_sha, new_sha, tested_at) -> MarkerResult`.

- [ ] **Step 1: Write failing tests** for watched/unwatched changes, `**`, missing base, unreachable base, deterministic file evidence, expected-base marker conflict, and repeat no-op.
- [ ] **Step 2: Verify red**, implement pure audit and atomic marker patch.
- [ ] **Step 3: Run tests and commit** with `feat: audit path-scoped integration currency`.

---

### Task 3: Add remote branch polling and snapshot collection

**Files:**
- Modify: `lib/pulse/scripts/poll.py`
- Modify: `lib/pulse/scripts/tests/test_poll.py`
- Create: `lib/pulse/scripts/impact_snapshot.py`
- Create: `lib/pulse/scripts/tests/test_impact_snapshot.py`

**Interfaces:**
- Consumes: configured relationship edges and remote pushed refs.
- Produces: `branch_heads` trigger state and audit snapshot `{repo:{branch:{head,changed_files_by_base,base_missing}}}`.

- [ ] **Step 1: Add `branch_heads` poll tests** with GitHub ref fixture seam.
- [ ] **Step 2: Implement trigger-only branch state**.
- [ ] **Step 3: Implement snapshot collector** using `git ls-remote`/temporary bare fetch or verified F0 evidence; it must fall back to git when Nave sparse history cannot resolve the tested SHA.
- [ ] **Step 4: Verify and commit** with `feat: collect remote impact evidence`.

---

### Task 4: Add headless impact workflow and release gate

**Files:**
- Create: `skills/gh-impact-audit-headless/SKILL.md`
- Create: `templates/workflows/impact-audit.yaml`
- Modify: `lib/pulse/scripts/resolve_run.py`
- Modify: `lib/pulse/scripts/tests/test_resolve_run.py`

**Interfaces:**
- Consumes: F5 snapshot/audit and Pulse mutation policy.
- Produces: `impact-result.yaml`, tracking proposals, optional integration dispatch, and `binding_edges_current` gate evidence.

- [ ] **Step 1: Write gate tests** for current, stale, missing, and malformed impact results.
- [ ] **Step 2: Implement `binding_edges_current` fail-closed gate**.
- [ ] **Step 3: Write skill** SNAPSHOT → AUDIT → PROPOSE ISSUE/DISPATCH → RECORD; successful dispatch alone never advances markers.
- [ ] **Step 4: Run full suite and commit** with `feat: add generic impact audit workflow`.

---

### Task 5: Close the integration loop

**Files:**
- Modify: `lib/pulse/scripts/impact.py`
- Modify: `lib/pulse/scripts/tests/test_impact.py`
- Modify: `lib/patterns/workflow-execution.md`

**Interfaces:**
- Consumes: successful workflow-run evidence matching an edge's `integration_workflow`.
- Produces: exact expected-base `mark` proposal; failures and unrelated workflows produce no marker action.

- [ ] **Step 1: Add tests** proving only the configured successful integration workflow proposes marker advancement.
- [ ] **Step 2: Implement adapter from workflow-run evidence to exact `mark` proposal**.
- [ ] **Step 3: Verify idempotence/full suite and commit** with `feat: close impact validation loop`.
