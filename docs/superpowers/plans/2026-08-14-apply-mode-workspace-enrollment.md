# Apply-Mode Workspace Enrollment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the 4th `"neutral"` source kind in the apply re-derivation provider, wire the driver contract for it, and enroll the workspace with a `format-python` binding + authorization so `gh-apply` can land `ruff format .` on `hiivmind/agent-kernel`.

**Architecture:** Two-repo change. pulse-gh gains a neutral provider (`apply_rederive` collect/rederive + `apply_reconcile.resolve_intended_base` + `apply_driver` contract); the workspace repo gains two config files (`apply-neutral.yaml` binding, `apply-authorization.yaml` policy). The provider is a degenerate case of the existing collect→rederive split: collect fetches the live `base_ref` HEAD via `gh_api`, rederive builds an allow-listed single-repo `Proposal` via `mutation_plan.build_proposal`. Pure-neutral → terminal at merge (no finalizer).

**Tech Stack:** Python ≥3.10 (PEP 723 scripts + pyproject dev env), pytest, `gh` CLI, `uv`.

## Global Constraints

- **Single-mutator:** no clone-write git in Pulse — every branch/commit/push/reset is a Nave verb. Pulse orchestrates + reads.
- **v1 single-repo-per-run:** the driver blocks `selection > 1` with "multi-repo apply is v2".
- **Deterministic transformations only** (v1 crash-resume reset+re-exec contract).
- **Neutral transformations are exactly** `format-python`, `refresh-node-lockfile`, `regenerate-docs-index` (the `NEUTRAL_TRANSFORMATIONS` allowlist). `regenerate-from-template` and the two F9 overlays are NOT neutral.
- **`authorize()` always runs its full identity + scope check** — no self-elevating binding.
- **pulse-gh flow:** `feature/* → develop → release/* → main`. Code lands on a feature branch off `develop`; PR targets `develop`.
- **workspace flow:** `feature/* → main`.
- **Tests:** `uv run pytest` from the repo root; `testpaths = ["lib/pulse/scripts/tests"]`, `pythonpath = ["."]`.
- **No new dependencies** in pulse-gh — the neutral provider uses the existing `io_seams.gh_api` seam (`Callable[[str], Any]`).

---

### Task 1: Neutral provider interfaces — constants, dataclass, helpers

**Files:**
- Modify: `lib/pulse/scripts/apply_rederive.py` (constants ~line 44; dataclass after `MarketplaceProviderInputs` ~line 120; helpers after `RederivedProposal` ~line 141)
- Test: `lib/pulse/scripts/tests/test_apply_rederive.py` (append a "neutral fixtures" section + helper tests)

**Interfaces:**
- Produces (used by Tasks 2–3):
  - `SOURCE_KINDS = ("plan-sync", "generated-artifact", "marketplace-sync", "neutral")`
  - `NEUTRAL_TRANSFORMATIONS = ("format-python", "refresh-node-lockfile", "regenerate-docs-index")`
  - `@dataclass(frozen=True) class NeutralProviderInputs` with fields `binding: Mapping[str, Any]`, `head_sha: str | None`, `actor: Mapping[str, Any] | mutation_plan.Actor`, `registry: mutation_plan.TransformationRegistry | None = None`
  - `ProviderInputs = PlanSyncProviderInputs | GeneratedProviderInputs | MarketplaceProviderInputs | NeutralProviderInputs`
  - `def _validate_neutral_binding(binding: Mapping[str, Any]) -> tuple[str, str]` — returns `(owner, name)`, raises `RederiveError` on missing/slashless `repo` or missing `transformation`
  - `def neutral_proposal_id(binding: Mapping[str, Any]) -> str` — `f"apply-{transformation}-{owner}-{name}"`
  - `def neutral_summary(binding: Mapping[str, Any]) -> dict[str, str]` — `{binding, transformation, proposal_id}`

- [ ] **Step 1: Write the failing tests** — append to `test_apply_rederive.py`:

```python
# --- neutral fixtures ---------------------------------------------------------

NEUTRAL_REPO = "hiivmind/agent-kernel"
NEUTRAL_HEAD = "d" * 40


def neutral_binding(**overrides):
    value = {
        "repo": NEUTRAL_REPO,
        "transformation": "format-python",
        "base_ref": "main",
        "bound_paths": ["src/**", "tests/**", "examples/**"],
    }
    value.update(overrides)
    return value


def test_neutral_proposal_id_is_deterministic():
    assert apply_rederive.neutral_proposal_id(neutral_binding()) == (
        "apply-format-python-hiivmind-agent-kernel"
    )


def test_neutral_proposal_id_rejects_missing_repo():
    with pytest.raises(apply_rederive.RederiveError, match="repo"):
        apply_rederive.neutral_proposal_id({"transformation": "format-python"})


def test_neutral_proposal_id_rejects_slashless_repo():
    with pytest.raises(apply_rederive.RederiveError, match="repo"):
        apply_rederive.neutral_proposal_id(
            {"repo": "agent-kernel", "transformation": "format-python"}
        )


def test_neutral_proposal_id_rejects_missing_transformation():
    with pytest.raises(apply_rederive.RederiveError, match="transformation"):
        apply_rederive.neutral_proposal_id({"repo": NEUTRAL_REPO})


def test_neutral_summary_matches_binding_and_proposal_id():
    summary = apply_rederive.neutral_summary(neutral_binding())
    assert summary == {
        "binding": NEUTRAL_REPO,
        "transformation": "format-python",
        "proposal_id": "apply-format-python-hiivmind-agent-kernel",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k neutral -v`
Expected: FAIL — `AttributeError: module 'apply_rederive' has no attribute 'neutral_proposal_id'`

- [ ] **Step 3: Write the implementation**

In `apply_rederive.py`, update the constants (line 44) and add the dataclass + helpers. Replace line 44 and insert after `RederivedProposal` (line 141):

```python
SOURCE_KINDS = ("plan-sync", "generated-artifact", "marketplace-sync", "neutral")

# Neutral transformations are the standalone, self-contained executable
# entries with no propose driver. `regenerate-from-template` (a `nave
# generate --from-template` argv) belongs to generated-artifact, not here;
# the F9 overlays are profile:claude-plugin, never neutral.
NEUTRAL_TRANSFORMATIONS = ("format-python", "refresh-node-lockfile", "regenerate-docs-index")
```

Insert after `MarketplaceProviderInputs` (before the `ProviderInputs` union at line 123):

```python
@dataclass(frozen=True)
class NeutralProviderInputs:
    """Fresh neutral evidence: `binding` is the caller-supplied `binding_ref`
    (validated); `head_sha` is the live HEAD of the binding's `base_ref` branch."""

    binding: Mapping[str, Any]
    head_sha: str | None
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None
```

Update the union (line 123):

```python
ProviderInputs = (
    PlanSyncProviderInputs
    | GeneratedProviderInputs
    | MarketplaceProviderInputs
    | NeutralProviderInputs
)
```

Insert after `RederivedProposal` (after line 141):

```python
def _validate_neutral_binding(binding: Mapping[str, Any]) -> tuple[str, str]:
    """Validate a neutral binding's `repo` + `transformation`; return (owner, name).

    Raises `RederiveError` (never KeyError/ValueError) so a malformed binding
    blocks (the driver turns it into a `blocked` result), never crashes.
    """
    repo = binding.get("repo")
    if not isinstance(repo, str) or not repo or repo.count("/") != 1:
        raise RederiveError(
            f"apply_rederive: neutral binding requires repo 'owner/name', got {repo!r}"
        )
    transformation = binding.get("transformation")
    if not isinstance(transformation, str) or not transformation:
        raise RederiveError(
            "apply_rederive: neutral binding requires a non-empty transformation, "
            f"got {transformation!r}"
        )
    return repo.split("/", 1)


def neutral_proposal_id(binding: Mapping[str, Any]) -> str:
    """Deterministic neutral proposal id: `apply-{transformation}-{owner}-{name}`.

    Single source of the id, shared by `neutral_summary` and `_rederive_neutral`
    so the synthesized `recorded_summary.proposal_id` can never drift from the
    re-derived proposal's id.
    """
    owner, name = _validate_neutral_binding(binding)
    return f"apply-{binding['transformation']}-{owner}-{name}"


def neutral_summary(binding: Mapping[str, Any]) -> dict[str, str]:
    """Synthesize the `recorded_summary` for a neutral apply (no propose phase)."""
    proposal_id = neutral_proposal_id(binding)  # validates repo + transformation first
    return {
        "binding": binding["repo"],
        "transformation": binding["transformation"],
        "proposal_id": proposal_id,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k neutral -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add lib/pulse/scripts/apply_rederive.py lib/pulse/scripts/tests/test_apply_rederive.py
git commit -m "feat(apply): add neutral provider interfaces (constants, inputs, helpers)"
```

---

### Task 2: `_collect_neutral` + `collect_inputs` identity/dispatch branches

**Files:**
- Modify: `lib/pulse/scripts/apply_rederive.py` (`collect_inputs` ~line 166 and ~177; add `_collect_neutral` after `_collect_marketplace` ~line 270)
- Test: `lib/pulse/scripts/tests/test_apply_rederive.py` (neutral collect tests)

**Interfaces:**
- Consumes: `NeutralProviderInputs`, `_validate_neutral_binding` (Task 1).
- Produces: `def _collect_neutral(binding_ref, actor, io_seams) -> NeutralProviderInputs`; `collect_inputs("neutral", …)` returns it.

- [ ] **Step 1: Write the failing tests**:

```python
def _neutral_gh_api(head_sha=NEUTRAL_HEAD):
    def gh_api(path):
        if path == f"repos/{NEUTRAL_REPO}/branches/main":
            return {"commit": {"sha": head_sha}}
        return None
    return gh_api


def neutral_registry():
    return mutation_plan.load_registry({
        "transformations": {
            "format-python": {
                "id": "format-python",
                "command_argv": ["ruff", "format", "."],
                "applies_to": ["profile:python"],
                "validation": {"kind": "none"},
                "allow_scheduled": True,
            },
        },
    })


def test_collect_inputs_neutral_fetches_live_head():
    io_seams = apply_rederive.IoSeams(gh_api=_neutral_gh_api(), registry=neutral_registry())
    inputs = apply_rederive.collect_inputs(
        "neutral", neutral_binding(),
        {"binding": NEUTRAL_REPO, "transformation": "format-python",
         "proposal_id": "apply-format-python-hiivmind-agent-kernel"},
        actor=ACTOR, io_seams=io_seams,
    )
    assert isinstance(inputs, apply_rederive.NeutralProviderInputs)
    assert inputs.head_sha == NEUTRAL_HEAD
    assert inputs.registry is io_seams.registry


def test_collect_inputs_neutral_rejects_missing_base_ref():
    io_seams = apply_rederive.IoSeams(gh_api=_neutral_gh_api())
    with pytest.raises(apply_rederive.RederiveError, match="base_ref"):
        apply_rederive.collect_inputs(
            "neutral", {"repo": NEUTRAL_REPO, "transformation": "format-python"},
            {"binding": NEUTRAL_REPO, "transformation": "format-python",
             "proposal_id": "apply-format-python-hiivmind-agent-kernel"},
            actor=ACTOR, io_seams=io_seams,
        )


def test_collect_inputs_neutral_rejects_missing_head_evidence():
    io_seams = apply_rederive.IoSeams(gh_api=lambda path: None)
    with pytest.raises(apply_rederive.RederiveError, match="HEAD"):
        apply_rederive.collect_inputs(
            "neutral", neutral_binding(),
            {"binding": NEUTRAL_REPO, "transformation": "format-python",
             "proposal_id": "apply-format-python-hiivmind-agent-kernel"},
            actor=ACTOR, io_seams=io_seams,
        )


def test_collect_inputs_neutral_rejects_binding_identity_mismatch():
    io_seams = apply_rederive.IoSeams(gh_api=_neutral_gh_api())
    with pytest.raises(apply_rederive.RederiveError, match="binding"):
        apply_rederive.collect_inputs(
            "neutral", neutral_binding(),
            {"binding": "someone/else", "transformation": "format-python",
             "proposal_id": "apply-format-python-hiivmind-agent-kernel"},
            actor=ACTOR, io_seams=io_seams,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k neutral -v`
Expected: FAIL — `_collect_neutral` not called / `KeyError` on `base_ref` (identity mismatch test may pass already if the shared pre-check resolves `repo`; the collect-specific tests fail).

- [ ] **Step 3: Write the implementation**

In `collect_inputs`, change the identity resolution (lines 166–168) to add a `neutral` key:

```python
    binding_id = binding_ref.get(
        "repo" if source_kind == "neutral"
        else ("plugin_id" if source_kind == "marketplace-sync" else "id")
    )
```

And add the dispatch branch before the marketplace fallthrough (lines 177–181):

```python
    if source_kind == "plan-sync":
        return _collect_plan_sync(binding_ref, actor, io_seams)
    if source_kind == "generated-artifact":
        return _collect_generated(binding_ref, actor, io_seams)
    if source_kind == "neutral":
        return _collect_neutral(binding_ref, actor, io_seams)
    return _collect_marketplace(binding_ref, actor, io_seams)
```

Add `_collect_neutral` after `_collect_marketplace` (after line 270):

```python
def _collect_neutral(
    binding_ref: Mapping[str, Any],
    actor: Mapping[str, Any] | mutation_plan.Actor,
    io_seams: IoSeams,
) -> NeutralProviderInputs:
    owner, name = _validate_neutral_binding(binding_ref)  # repo + transformation
    base_ref = binding_ref.get("base_ref")
    if not isinstance(base_ref, str) or not base_ref:
        raise RederiveError(
            f"apply_rederive: neutral binding requires a non-empty base_ref, got {base_ref!r}"
        )
    if io_seams.gh_api is None:
        raise RederiveError("apply_rederive: neutral requires io_seams.gh_api")
    try:
        payload = io_seams.gh_api(f"repos/{owner}/{name}/branches/{base_ref}")
    except Exception as exc:
        raise RederiveError(
            f"apply_rederive: neutral HEAD fetch failed for {owner}/{name}: {exc}"
        ) from exc
    head_sha = None
    if isinstance(payload, Mapping):
        commit = payload.get("commit")
        if isinstance(commit, Mapping) and isinstance(commit.get("sha"), str):
            head_sha = commit["sha"] or None
    if head_sha is None:
        raise RederiveError(
            f"apply_rederive: neutral could not resolve HEAD for {owner}/{name}@{base_ref}"
        )
    return NeutralProviderInputs(
        binding=binding_ref,
        head_sha=head_sha,
        actor=actor,
        registry=io_seams.registry,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k neutral -v`
Expected: PASS (Task 1's 5 + these 4)

- [ ] **Step 5: Commit**

```bash
git add lib/pulse/scripts/apply_rederive.py lib/pulse/scripts/tests/test_apply_rederive.py
git commit -m "feat(apply): add neutral collection (live HEAD via gh_api) + collect_inputs dispatch"
```

---

### Task 3: `_rederive_neutral` + `rederive` isinstance dispatch

**Files:**
- Modify: `lib/pulse/scripts/apply_rederive.py` (`rederive` ~line 288; add `_rederive_neutral` after `_rederive_marketplace` ~line 410)
- Test: `lib/pulse/scripts/tests/test_apply_rederive.py` (neutral rederive tests)

**Interfaces:**
- Consumes: `NeutralProviderInputs`, `neutral_proposal_id` (Task 1).
- Produces: `def _rederive_neutral(inputs: NeutralProviderInputs) -> RederivedProposal`; `rederive(NeutralProviderInputs)` returns it.

- [ ] **Step 1: Write the failing tests**:

```python
def test_rederive_neutral_builds_allow_listed_proposal():
    registry = neutral_registry()
    inputs = apply_rederive.collect_inputs(
        "neutral", neutral_binding(),
        {"binding": NEUTRAL_REPO, "transformation": "format-python",
         "proposal_id": "apply-format-python-hiivmind-agent-kernel"},
        actor=ACTOR, io_seams=apply_rederive.IoSeams(gh_api=_neutral_gh_api(), registry=registry),
    )
    rederived = apply_rederive.rederive(inputs)
    assert rederived.binding_id == NEUTRAL_REPO
    assert rederived.source_kind == "neutral"
    assert rederived.finalizer_record is None
    assert rederived.proposal.id == "apply-format-python-hiivmind-agent-kernel"
    assert rederived.proposal.selection == (NEUTRAL_REPO,)
    assert rederived.proposal.transformation == "format-python"
    assert rederived.proposal.expected_shas == {NEUTRAL_REPO: NEUTRAL_HEAD}
    assert rederived.proposal.bound_paths == {
        NEUTRAL_REPO: ("src/**", "tests/**", "examples/**")
    }


def test_rederive_neutral_rejects_non_neutral_transformation():
    inputs = apply_rederive.NeutralProviderInputs(
        binding=neutral_binding(transformation="plan-sync-doc-patch"),
        head_sha=NEUTRAL_HEAD, actor=ACTOR,
    )
    with pytest.raises(apply_rederive.RederiveError, match="neutral transformation"):
        apply_rederive.rederive(inputs)


def test_rederive_neutral_rejects_unresolved_head_sha():
    inputs = apply_rederive.NeutralProviderInputs(
        binding=neutral_binding(), head_sha=None, actor=ACTOR,
    )
    with pytest.raises(apply_rederive.RederiveError, match="head_sha"):
        apply_rederive.rederive(inputs)


def test_rederive_neutral_rejects_empty_bound_paths():
    inputs = apply_rederive.NeutralProviderInputs(
        binding=neutral_binding(bound_paths=[]), head_sha=NEUTRAL_HEAD, actor=ACTOR,
    )
    with pytest.raises(apply_rederive.RederiveError, match="build failed"):
        apply_rederive.rederive(inputs)


def test_neutral_result_round_trips_through_authorization():
    registry = neutral_registry()
    inputs = apply_rederive.collect_inputs(
        "neutral", neutral_binding(),
        {"binding": NEUTRAL_REPO, "transformation": "format-python",
         "proposal_id": "apply-format-python-hiivmind-agent-kernel"},
        actor=ACTOR, io_seams=apply_rederive.IoSeams(gh_api=_neutral_gh_api(), registry=registry),
    )
    rederived = apply_rederive.rederive(inputs)
    auth = apply_authorization.ApplyAuthorization(
        transformation="format-python", mutation_policy="allow-listed",
        permitted_repos=(NEUTRAL_REPO,),
        bound_paths={NEUTRAL_REPO: ("src/**", "tests/**", "examples/**")},
    )
    apply_authorization.authorize(rederived, auth, {
        "binding": NEUTRAL_REPO, "transformation": "format-python",
        "proposal_id": "apply-format-python-hiivmind-agent-kernel",
    })


def test_neutral_transformations_are_self_contained_in_template_registry():
    """The allowlist is fail-safe only if its entries are truly standalone:
    no `nave generate` argv and no `profile:claude-plugin` predicate."""
    template = Path(__file__).resolve().parents[4] / "templates" / "transformations.yaml.template"
    registry = mutation_plan.load_registry(template)
    for entry_id in apply_rederive.NEUTRAL_TRANSFORMATIONS:
        entry = registry.get(entry_id)
        assert not entry.command_argv[0:1] == ("nave",), (
            f"{entry_id} argv must be self-contained (no nave generate dispatch)"
        )
        assert all(not p.startswith("profile:claude-plugin") for p in entry.applies_to), (
            f"{entry_id} must not carry a profile:claude-plugin predicate"
        )

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k neutral -v`
Expected: FAIL — `rederive` raises `RederiveError: unsupported provider inputs` for `NeutralProviderInputs`.

- [ ] **Step 3: Write the implementation**

Add the isinstance dispatch in `rederive` (before the final raise, ~line 290):

```python
    if isinstance(inputs, MarketplaceProviderInputs):
        return _rederive_marketplace(inputs)
    if isinstance(inputs, NeutralProviderInputs):
        return _rederive_neutral(inputs)
    raise RederiveError(f"apply_rederive: unsupported provider inputs: {type(inputs)!r}")
```

Add `_rederive_neutral` after `_rederive_marketplace` (after line 410):

```python
def _rederive_neutral(inputs: NeutralProviderInputs) -> RederivedProposal:
    binding = inputs.binding
    transformation = binding.get("transformation")
    if transformation not in NEUTRAL_TRANSFORMATIONS:
        raise RederiveError(
            f"apply_rederive: transformation {transformation!r} is not a neutral transformation"
        )
    head_sha = inputs.head_sha
    if not isinstance(head_sha, str) or not head_sha:
        raise RederiveError("apply_rederive: neutral requires a resolved head_sha")
    try:
        proposal = mutation_plan.build_proposal(
            id=neutral_proposal_id(binding),
            selection=[binding["repo"]],
            transformation=transformation,
            expected_shas={binding["repo"]: head_sha},
            actor=inputs.actor,
            mutation_policy="allow-listed",
            bound_paths={binding["repo"]: binding["bound_paths"]},
            registry=inputs.registry,
        )
    except mutation_plan.MutationPlanError as exc:
        raise RederiveError(f"apply_rederive: neutral build failed: {exc}") from exc
    return RederivedProposal(
        binding_id=str(binding["repo"]),
        proposal=proposal,
        source_kind="neutral",
        finalizer_record=None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k neutral -v`
Expected: PASS (5 + 4 + 6)

- [ ] **Step 5: Commit**

```bash
git add lib/pulse/scripts/apply_rederive.py lib/pulse/scripts/tests/test_apply_rederive.py
git commit -m "feat(apply): add neutral re-derivation (build_proposal degenerate case)"
```

---

### Task 4: `resolve_intended_base` neutral branch

**Files:**
- Modify: `lib/pulse/scripts/apply_reconcile.py` (`resolve_intended_base` ~line 230, before the final `raise`)
- Test: `lib/pulse/scripts/tests/test_apply_reconcile.py` (append next to the existing `test_resolve_intended_base_*` tests ~line 1196)

**Interfaces:**
- Produces: `resolve_intended_base("neutral", {"base_ref": "main"}, None) == "main"`; raises `ValueError("cannot resolve intended base for neutral: no base_ref")` on missing/non-string `base_ref`.

- [ ] **Step 1: Write the failing tests**:

```python
def test_resolve_intended_base_neutral_uses_binding_base_ref():
    assert apply_reconcile.resolve_intended_base(
        "neutral", {"base_ref": "main"}, None
    ) == "main"


def test_resolve_intended_base_neutral_rejects_missing_base_ref():
    with pytest.raises(ValueError, match="cannot resolve intended base for neutral"):
        apply_reconcile.resolve_intended_base("neutral", {}, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -k neutral -v`
Expected: FAIL — `ValueError: unknown source_kind: neutral`.

- [ ] **Step 3: Write the implementation**

Insert before the final `raise ValueError(f"unknown source_kind: {source_kind}")` (line 237):

```python
    if source_kind == "neutral":
        base = binding_ref.get("base_ref")
        if not isinstance(base, str) or not base:
            raise ValueError("cannot resolve intended base for neutral: no base_ref")
        return base
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -k neutral -v`
Expected: PASS (2 tests). Also run the full reconcile file to confirm no regression: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -q`.

- [ ] **Step 5: Commit**

```bash
git add lib/pulse/scripts/apply_reconcile.py lib/pulse/scripts/tests/test_apply_reconcile.py
git commit -m "feat(apply): resolve intended base for the neutral source kind"
```

---

### Task 5: Driver contract — optional `recorded_summary`, neutral synthesis, `gh_api` seam

**Files:**
- Modify: `lib/pulse/scripts/apply_driver.py` (`run_apply` signature + top of try ~line 104–116; `IoSeams` construction ~line 115; add `_default_gh_api` helper; `main` CLI ~line 355 + call ~line 366)
- Test: `lib/pulse/scripts/tests/test_apply_driver.py` (two new tests)

**Interfaces:**
- Consumes: `apply_rederive.neutral_summary` (Task 1).
- Produces: `run_apply(*, …, recorded_summary: Mapping[str, Any] | None = None, gh_api: Callable[[str], Any] | None = None, …)`; `main` passes a production `gh_api` and makes `--recorded-summary` conditional.

- [ ] **Step 1: Write the failing tests**:

```python
def test_run_apply_neutral_synthesizes_summary_and_threads_gh_api(tmp_path, monkeypatch):
    from lib.pulse.scripts.apply_authorization import AuthorizationError

    captured = {}

    def fake_collect(source_kind, binding_ref, recorded_summary, *, actor, io_seams):
        captured["recorded_summary"] = recorded_summary
        captured["gh_api"] = io_seams.gh_api
        return SimpleNamespace(registry=None)

    def fake_rederive(inputs):
        prop = mutation_plan.build_proposal(
            id="apply-format-python-hiivmind-agent-kernel",
            selection=["hiivmind/agent-kernel"], transformation="format-python",
            expected_shas={"hiivmind/agent-kernel": "e" * 40},
            actor={"gh_login": "octocat", "machine": "host", "mode": "interactive"},
            mutation_policy="allow-listed",
            bound_paths={"hiivmind/agent-kernel": ("src/**",)},
        )
        return apply_rederive.RederivedProposal("hiivmind/agent-kernel", prop, "neutral", None)

    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", fake_collect)
    monkeypatch.setattr(apply_driver.apply_rederive, "rederive", fake_rederive)
    monkeypatch.setattr(apply_driver.apply_authorization, "load_authorization", lambda *a: object())
    monkeypatch.setattr(apply_driver.apply_authorization, "authorization_digest", lambda a: "v1|" + "b" * 64)
    monkeypatch.setattr(apply_driver.apply_authorization, "authorize",
                        lambda *a: (_ for _ in ()).throw(AuthorizationError("stop")))

    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml.safe_dump({
        "ledger_version": 1, "run_id": "r", "workflow": "w", "status": "running",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "host"}, "params": {},
        "repos": ["hiivmind/agent-kernel"],
        "steps": [{"id": "step", "repo": "hiivmind/agent-kernel", "depends_on": [],
                   "gate": None, "status": "pending", "notes": []}],
    }, sort_keys=False))
    result = tmp_path / "result.yaml"
    fake_gh_api = lambda path: {"commit": {"sha": "e" * 40}}

    out = apply_driver.run_apply(
        source_kind="neutral",
        binding_ref={"repo": "hiivmind/agent-kernel", "transformation": "format-python",
                     "base_ref": "main", "bound_paths": ["src/**"]},
        recorded_summary=None,
        authorization_path=tmp_path / "auth.yaml", ledger_path=ledger, step_id="step",
        actor_id="octocat@host", runner=RecordingRunner(), gh_api=fake_gh_api,
        gh_ops=FakeGhOps(), result_path=result, workspace=str(tmp_path),
    )

    assert out["state"] == "blocked"
    assert captured["recorded_summary"] == {
        "binding": "hiivmind/agent-kernel",
        "transformation": "format-python",
        "proposal_id": "apply-format-python-hiivmind-agent-kernel",
    }
    assert captured["gh_api"] is fake_gh_api


def test_run_apply_rejects_missing_summary_for_non_neutral(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not collect")))
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml.safe_dump({
        "ledger_version": 1, "run_id": "r", "workflow": "w", "status": "running",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "host"}, "params": {},
        "repos": ["acme/widget"],
        "steps": [{"id": "step", "repo": "acme/widget", "depends_on": [],
                   "gate": None, "status": "pending", "notes": []}],
    }, sort_keys=False))
    result = tmp_path / "result.yaml"
    out = apply_driver.run_apply(
        source_kind="generated-artifact",
        binding_ref={"id": "binding", "branch": "main"},
        recorded_summary=None,
        authorization_path=tmp_path / "auth.yaml", ledger_path=ledger, step_id="step",
        actor_id="octocat@host", runner=RecordingRunner(), gh_ops=FakeGhOps(),
        result_path=result, workspace=str(tmp_path),
    )
    assert out["state"] == "blocked"
    assert "recorded_summary" in out["reason"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k "neutral_synthesizes or rejects_missing_summary" -v`
Expected: FAIL — `TypeError: run_apply() missing 1 required keyword-only argument: 'recorded_summary'` (for the neutral test, since `gh_api` is also not yet a kwarg).

- [ ] **Step 3: Write the implementation**

Change `run_apply` signature (line 104) and the top of its body:

```python
def run_apply(*, source_kind, binding_ref, recorded_summary=None, authorization_path, ledger_path,
              step_id, actor_id, runner, gh_api=None, gh_ops, result_path, workspace) -> dict:
    """Run one single-repository apply; return apply-status or repo-mutation."""
    proposal = None
    proposal_digest = None
    authorization_digest = None
    actor = _actor(actor_id)

    try:
        if source_kind == "neutral":
            recorded_summary = apply_rederive.neutral_summary(binding_ref)
        elif not recorded_summary:
            raise apply_rederive.RederiveError(
                f"recorded_summary is required for source_kind={source_kind!r}"
            )
        inputs = apply_rederive.collect_inputs(
            source_kind, binding_ref, recorded_summary, actor=actor,
            io_seams=apply_rederive.IoSeams(runner=runner, gh_api=gh_api, registry=None),
        )
```

Add the production `gh_api` helper near `_actor` (after line 31):

```python
def _default_gh_api(path: str):
    """Production `gh api` seam — parsed JSON, or None on any failure."""
    import json
    import subprocess
    res = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except ValueError:
        return None
```

Update `main`: relax the `--recorded-summary` argument (line 355), add the post-parse guard, and pass `gh_api`:

```python
    parser.add_argument("--recorded-summary", required=False, default=None,
                        help="JSON {binding, transformation, proposal_id}; omit for --source-kind neutral")
    ...
    if args.source_kind != "neutral" and not args.recorded_summary:
        parser.error("--recorded-summary is required unless --source-kind is neutral")

    runner = nave_adapter.NaveRunner(fixtures=args.fixtures)
    result = run_apply(
        source_kind=args.source_kind,
        binding_ref=json.loads(args.binding_ref),
        recorded_summary=json.loads(args.recorded_summary) if args.recorded_summary else None,
        authorization_path=args.authorization,
        ledger_path=args.ledger,
        step_id=args.step,
        actor_id=args.actor,
        runner=runner,
        gh_api=_default_gh_api,
        gh_ops=apply_reconcile.GhCliOps(),
        result_path=args.result,
        workspace=args.workspace,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k "neutral_synthesizes or rejects_missing_summary" -v`
Expected: PASS (2 tests). Then run the full driver suite to confirm no regression from the optional kwarg: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -q`.

- [ ] **Step 5: Commit**

```bash
git add lib/pulse/scripts/apply_driver.py lib/pulse/scripts/tests/test_apply_driver.py
git commit -m "feat(apply): synthesize neutral recorded_summary in the driver; thread gh_api"
```

---

### Task 6: Workspace config — binding + authorization (separate repo)

**Files (in `~/git/hiivmind/hiivmind-workspace`):**
- Create: `apply-neutral.yaml`
- Create: `apply-authorization.yaml`

**Interfaces:**
- Produces: the two config files consumed by the driver/skill at apply time (`apply-authorization.yaml` shape is pinned by `apply_authorization.load_authorization`).

- [ ] **Step 1: Create `apply-neutral.yaml`** (at the repo root, alongside `config.yaml`):

```yaml
# Neutral apply bindings — one entry per (repo, transformation). Each binding is
# single-repo: a multi-repo intent is expressed as multiple list entries.
bindings:
  - repo: hiivmind/agent-kernel
    transformation: format-python
    base_ref: main
    bound_paths:
      - src/**
      - tests/**
      - examples/**
```

- [ ] **Step 2: Create `apply-authorization.yaml`** (same directory):

```yaml
# Apply-mode authorization policy — consumed verbatim by
# apply_authorization.load_authorization (mutation_policy / permitted_repos /
# bound_paths). The scope gate for allow-listed neutral applies.
authorizations:
  format-python:
    mutation_policy: allow-listed
    permitted_repos:
      - hiivmind/agent-kernel
    bound_paths:
      hiivmind/agent-kernel:
        - src/**
        - tests/**
        - examples/**
```

- [ ] **Step 3: Commit on a feature branch and open a PR**

```bash
cd ~/git/hiivmind/hiivmind-workspace
git checkout -b feature/apply-mode-enrollment
git add apply-neutral.yaml apply-authorization.yaml
git commit -m "feat: enroll format-python neutral apply (binding + authorization)"
git push -u origin feature/apply-mode-enrollment
gh pr create --base main --title "Apply-mode workspace enrollment" \
  --body "Adds the neutral apply binding (format-python on hiivmind/agent-kernel) and its apply-authorization policy. Gated on the installed Nave apply verbs + pulse-gh (F11 §5F)."
```

- [ ] **Step 4: Verify**

Run: `gh pr view --json state,baseRefName -q '"\(.state) \(.baseRefName)"'`
Expected: `OPEN main`.

---

### Task 7: Live proof (gated on the installed engine — NOT a code deliverable)

**Files:** none (verification only).

**Gating:** Nave apply verbs (merged `discreteds/nave` PR #2) and pulse-gh must be `uv`-installed locally. If the capability handshake fails, the driver returns `blocked` — that is the expected fail-closed behavior, not a defect.

- [ ] **Step 1: Check `hiivmind/agent-kernel` for real ruff drift.**

Run (in `~/git/hiivmind/agent-kernel`):
```bash
ruff format --check . 2>&1 | head -20
```
Expected: either "would reformat N files" (real drift) or "All checks passed" (no drift).

- [ ] **Step 2: If no drift, introduce a deliberate inconsistency in a scratch clone** (never committed upstream). `format-python` validates with `kind: none`, so a no-op run fails at the `commit` boundary (nothing to stage → `git commit` nonzero) and never reaches push/PR/merge-detect. The proof must land a real diff to exercise the full spine.

- [ ] **Step 3: Run the apply** via the `gh-apply` skill with `source_kind=neutral`, the `apply-neutral.yaml` binding, and `authorization_path=<workspace>/apply-authorization.yaml`. Confirm the terminal `apply-status` reaches `applied` after the PR is reviewed + merged (base + head verified by the merge gate; no base advance for pure-neutral).

- [ ] **Step 4: Confirm the ledger step is `done`** (no "base advance deferred" bookkeeping PR — terminal at merge).

---

## Self-Review

**Spec coverage:**
- §4.1 interfaces → Task 1 (constants, dataclass, helpers). ✓
- §4.2 collection → Task 2 (`_collect_neutral` + `collect_inputs` identity/dispatch). ✓
- §4.3 re-derivation → Task 3 (`_rederive_neutral` + allowlist + head_sha + bound_paths). ✓
- §4.4 finalizer `None` → Task 3 asserts `finalizer_record is None`. ✓
- §4.5 recorded-summary synthesis + single-source id → Task 1 (`neutral_summary`/`neutral_proposal_id`) + Task 5 (driver synthesizes). ✓
- §4.6 shared-dispatcher branches (C1/C2) → Task 2 (`collect_inputs`) + Task 4 (`resolve_intended_base`). ✓
- §5 workspace config → Task 6. ✓
- §6 installed-engine gate → Task 7 gating note. ✓
- §7 acceptance → Tasks 1–3 unit tests (fail-closed list + the registry cross-check, added to Task 3 Step 1); Task 7 live proof. ✓

**Placeholder scan:** no `TBD`/`TODO`; every code step includes actual code; every test step includes actual test code. ✓

**Type consistency:** `NeutralProviderInputs` fields (`binding`, `head_sha`, `actor`, `registry`) are used consistently across Tasks 2–3; `neutral_proposal_id`/`neutral_summary`/`_validate_neutral_binding` signatures match their call sites; `run_apply`'s new kwargs (`recorded_summary=None`, `gh_api=None`) match the `main` call site. ✓
