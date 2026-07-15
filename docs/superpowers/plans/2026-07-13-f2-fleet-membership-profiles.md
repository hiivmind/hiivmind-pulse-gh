# F2: Generic Fleet Membership and Profile Proposals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the live GitHub repository set with the workspace catalog while proposing evidence-backed profiles without silently applying onboarding policy.

**Architecture:** A pure membership diff matches repositories by node ID and reports create/rename/archive/transfer changes. Nave evidence plus deterministic signals generate ranked profile proposals; optional LLM explanation is inferred and cannot alter candidates. Catalog registration and profile confirmation are separate PR-based actions.

**Tech Stack:** Python 3.10+ PEP 723, PyYAML, pytest, gh CLI, F0 evidence, F1 profiles.

## Global Constraints

- Registration is generic; governance, labels, milestones, schedulers, and checklists are separate profile actions.
- GitHub node ID is the rename-stable identity.
- Archived, forks, mirrors, and transferred repositories obey workspace discovery policy.
- Profile proposals include evidence and confidence but remain `asks_recorded` until confirmed.
- `apply: true` may patch catalog entries only; it never applies profile-dependent onboarding actions.

---

### Task 1: Add the generic membership result kind

**Files:**
- Modify: `lib/pulse/scripts/validate_result.py`
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`
- Modify: `lib/patterns/headless-contract.md`

**Interfaces:**
- Kind `fleet-membership`: `org_repos`, `catalog_repos`, `catalog_updated`, `profile_proposals`, findings/actions/asks.

- [ ] **Step 1: Write a failing valid-result test** where `profile_proposals` is a list of `{repo, candidates, evidence}` mappings.
- [ ] **Step 2: Verify red**, add validator branch and shared findings validation.
- [ ] **Step 3: Run focused tests** → PASS.
- [ ] **Step 4: Commit** with `feat(contract): add fleet membership result`.

---

### Task 2: Implement identity-safe membership diff

**Files:**
- Create: `lib/pulse/scripts/fleet_membership.py`
- Create: `lib/pulse/scripts/tests/test_fleet_membership.py`

**Interfaces:**
- CLI: `fleet_membership.py --org-repos FILE --config FILE`.
- Output: `{findings, catalog_patch, org_repos, catalog_repos}`.

- [ ] **Step 1: Write failing tests** for new, renamed, archived, transferred/missing, fork-excluded, and id-less catalog entries.
- [ ] **Step 2: Verify red**, implement deterministic node-ID matching and policy filters.
- [ ] **Step 3: Assert catalog patch contains only stable facts**: `name`, `id`, `full_name`, `default_branch`, `is_public`, `archived`, `fork`, `mirror_url`; it contains no profile guess.
- [ ] **Step 4: Run tests and commit** with `feat: diff live fleet membership`.

---

### Task 3: Generate deterministic profile candidates

**Files:**
- Create: `lib/pulse/scripts/profile_proposals.py`
- Create: `lib/pulse/scripts/tests/test_profile_proposals.py`

**Interfaces:**
- CLI: `profile_proposals.py --evidence FILE --profiles FILE --repos FILE`.
- Candidate: `{profile, confidence, evidence, rule_ids}`.

- [ ] **Step 1: Write failing candidate tests**

```python
def test_plugin_is_additive_to_python(tmp_path):
    out = propose(evidence(paths=["pyproject.toml", ".claude-plugin/plugin.json", "skills/a/SKILL.md"]))
    assert [c["profile"] for c in out["candidates"]] == ["python", "claude-plugin"]

def test_unknown_repo_has_no_guessed_profile(tmp_path):
    out = propose(evidence(paths=["README.md"]))
    assert out["candidates"] == []
```

- [ ] **Step 2: Verify red**, implement declarative proposal rules from `profiles.yaml`; confidence is rule-defined, not LLM-generated.
- [ ] **Step 3: Add optional inferred explanation field** that cannot create/remove/reorder candidates.
- [ ] **Step 4: Verify and commit** with `feat: propose repository profiles from evidence`.

---

### Task 4: Add org polling and the headless membership skill

**Files:**
- Modify: `lib/pulse/scripts/poll.py`
- Modify: `lib/pulse/scripts/tests/test_poll.py`
- Create: `skills/gh-fleet-membership-headless/SKILL.md`
- Create: `templates/workflows/fleet-watch.yaml`

**Interfaces:**
- Poll source `org_repos` stores a signature trigger only.
- Skill inputs: `workspace_path`, `apply_catalog=false`, `mode`.

- [ ] **Step 1: Add poll tests** proving first sight baselines and subsequent org signature changes trigger.
- [ ] **Step 2: Implement source through existing `gh_api` fixture seam**.
- [ ] **Step 3: Write skill phases** FETCH → DIFF → LOAD F0 EVIDENCE → PROPOSE PROFILES → optionally APPLY CATALOG → WRITE/VALIDATE RESULT.
- [ ] **Step 4: Assert the skill never seeds labels/milestones/schedulers**; those appear as profile-dependent proposed actions after confirmation.
- [ ] **Step 5: Run full suite and commit** with `feat: reconcile fleet membership and propose profiles`.

---

### Task 5: Add profile confirmation as a workspace PR patch

**Files:**
- Modify: `lib/pulse/scripts/profile_proposals.py`
- Modify: `lib/pulse/scripts/tests/test_profile_proposals.py`
- Modify: `lib/patterns/repository-profiles.md`

**Interfaces:**
- CLI: `profile_proposals.py confirm --profiles FILE --repo OWNER/NAME --expected-scorecard VALUE --profiles-list CSV --scorecard ID`.

- [ ] **Step 1: Test expected-base conflict and idempotent repeat**.
- [ ] **Step 2: Implement atomic patch** of workspace metadata only; never commit/push.
- [ ] **Step 3: Verify focused/full tests and commit** with `feat: confirm repository profiles safely`.
