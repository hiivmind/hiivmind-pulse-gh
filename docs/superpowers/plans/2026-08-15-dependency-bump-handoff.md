# Dependency-Bump Apply Handoff (F11 ← F4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn an F4 `DivergenceFinding` into a guarded, allow-listed, multi-repo `Proposal` the existing apply spine (fence/lease/journal → `nave pen` verbs → PR → reconcile) can land — closing the one gap between F4 (fleet dependency coherence) and F11 (apply mode).

**Architecture:** A new `dependency-bump` re-derivation source kind (`apply_rederive.py`) re-derives one finding fresh from F4 evidence at collect time, splits its diverging repos by package manager, and produces one `Proposal` per `(finding, manager)` — collect-once, rederive-many. Each proposal reuses `mutation_plan.build_proposal`'s existing guarantees via two additive extensions: whitelisted argv templating (`{package}`/`{version}` in `command_argv`, expanded from a new `Proposal.transform_params` field) and a second, tree-level drift guard (`Proposal.expected_tree_shas`) alongside the existing commit-level `expected_shas`. The driver fences and runs each manager-group proposal sequentially against one **shared** Nave pen (disjoint repo sets, one pen).

**Tech Stack:** Python 3.10+ (`lib/pulse/scripts/`), Rust (`~/git/discreteds/nave` — `nave_pen`, `nave_apply` crates), YAML config (`transformations.yaml.template`, `hiivmind-workspace/apply-authorization.yaml`).

**Spec:** `docs/superpowers/specs/2026-08-15-dependency-bump-handoff-design.md` (approved; 3 adversarial review rounds — GLM-5.2 via opencode, Gemini-3.1-pro via agy, Claude-Opus-4.6 via agy). Read it alongside this plan — this plan does not restate its rationale, only its execution.

## Global Constraints

- **No clone-write git in Pulse** — all mutation goes through Nave verbs (`nave pen ...`); Pulse orchestrates and reads only.
- **Fail closed everywhere** — every new validation path raises a typed error (`MutationPlanError`, `RederiveError`, `AuthorizationError`) on any ambiguity; there is no silent no-op or partial-success default.
- **No shell anywhere** — `subprocess.run(..., shell=False)` is unchanged; templating substitutes into a single argv element, never splits on whitespace, never reinterprets metacharacters.
- **v1 pins exact versions** (`==V` / `--save-exact`); range preservation and PEP 440 epochs are out of scope (spec § 7).
- **v1 restricts to `group == "main"` declarations** — a diverging repo whose declaration is `dev`/`optional` is dropped from selection with a per-repo `blocked` outcome, never silently promoted to main.
- **One proposal per (finding, manager)** — a finding spanning multiple managers (uv/poetry/npm/pnpm) becomes N independent proposals, never one multi-manager proposal.
- **Backward compatibility is mandatory** — every new field (`Proposal.transform_params`, `Proposal.expected_tree_shas`, `TransformationEntry.params`, `BranchRepoResult.observed_tree_sha`) is additive with a safe default; all four existing source kinds (plan-sync, generated-artifact, marketplace-sync, neutral) and all four existing transformation entries are unaffected.
- **Deterministic proposal id, target-independent** — `apply-bump-{ecosystem}-{package}-{manager}-{sha256(sorted selection)[:12]}`; a target-version change re-derives through the same id (cascading-bump semantics, intentional).
- Run all pulse-gh tests with `uv run pytest lib/pulse/scripts/tests/ -q` from the repo root (`~/git/hiivmind/hiivmind-pulse-gh`). Run all nave tests with `cargo test` from `~/git/discreteds/nave`.

---

## File Structure

| File | Repo | Responsibility |
|---|---|---|
| `crates/nave_pen/src/apply_ops.rs` | nave | `provision_one` gains a local, zero-API-cost tree-SHA computation |
| `crates/nave_apply/src/lib.rs` | nave | `BranchRepoResult` gains `observed_tree_sha: String` |
| `crates/nave_pen/tests/apply_ops.rs` | nave | Test coverage for the new field |
| `lib/pulse/scripts/nave_adapter.py` | pulse-gh | Wire-contract: `observed_tree_sha` becomes a required branch-result field |
| `lib/pulse/scripts/mutation_plan.py` | pulse-gh | `TransformationEntry.params`, templated `resolve_argv`, `_validate_param_value`, `Proposal.transform_params` + `Proposal.expected_tree_shas`, digest update |
| `lib/pulse/scripts/apply_phases.py` | pulse-gh | `exec_phase` passes `transform_params`; `provision_phase` gains the tree-drift `elif` |
| `templates/transformations.yaml.template` | pulse-gh | Four new `bump-*` transformation entries |
| `lib/pulse/scripts/apply_rederive.py` | pulse-gh | New `dependency-bump` source kind: collect-once/rederive-many |
| `lib/pulse/scripts/apply_reconcile.py` | pulse-gh | `resolve_intended_base` gains the `dependency-bump` branch |
| `lib/pulse/scripts/apply_driver.py` | pulse-gh | `--finding-ref` CLI wiring, shared-pen sequential orchestration |
| `~/git/hiivmind/hiivmind-workspace/apply-authorization.yaml` | hiivmind-workspace | Data: authorize the bump transformations for the live-proof repos |

Task order follows the dependency chain: nave (Task 1) → pulse-gh wire adapter (Task 2) → mutation_plan (Task 3, no dependencies on 1/2) → apply_phases (Task 4, needs 3) → transformations.yaml (Task 5, needs 3) → apply_rederive (Task 6, needs 3+5) → apply_reconcile (Task 7, needs 6) → apply_driver (Task 8, needs 4+6+7) → integration + live proof (Task 9, needs everything).

---

### Task 1: nave — `provision_one` reports `observed_tree_sha`

**Files:**
- Modify: `crates/nave_apply/src/lib.rs` (repo: `~/git/discreteds/nave`)
- Modify: `crates/nave_pen/src/apply_ops.rs`
- Modify: `crates/nave_pen/tests/apply_ops.rs`

**Interfaces:**
- Consumes: `BranchRepoResult` (existing struct, `#[derive(Debug, Clone, Serialize)]`, no `Deserialize` — safe to extend additively), `provision_one`'s existing `observed: String` (the commit SHA already resolved via `git rev-parse origin/{base_ref}`).
- Produces: `BranchRepoResult.observed_tree_sha: String` — the tree SHA of `observed`, computed via a local `git rev-parse {observed}^{tree}` call (zero extra GitHub API cost). Populated on every return path of `provision_one`, including early-return error paths (empty string, matching the existing `observed` field's convention).

- [ ] **Step 1: Read `provision_one`'s current full body to confirm anchor points**

Run: `sed -n '121,205p' crates/nave_pen/src/apply_ops.rs` — confirm the `mk` closure signature (`mk(state, observed: String, reason: Option<&str>)`) and every call site, since the tree-SHA computation must be threaded through all of them.

- [ ] **Step 2: Add `observed_tree_sha` to `BranchRepoResult`**

In `crates/nave_apply/src/lib.rs`, the struct (around line 202-212) becomes:

```rust
#[derive(Debug, Clone, Serialize)]
pub struct BranchRepoResult {
    pub repo: String,
    pub base_ref: String,
    pub expected_base_sha: String,
    pub observed_base_sha: String,
    pub observed_tree_sha: String,
    pub apply_ref: String,
    pub state: BranchState,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}
```

- [ ] **Step 3: Compute the tree SHA locally in `provision_one`**

In `crates/nave_pen/src/apply_ops.rs`, change the `mk` closure to also accept `observed_tree: String`, and thread an empty string through every early-return call site (mirroring how `observed` is already threaded as `String::new()` before it's resolved):

```rust
async fn provision_one(
    dir: &Path,
    req: &nave_apply::BranchRepoRequest,
    apply_ref: &str,
) -> nave_apply::BranchRepoResult {
    let mk = |state, observed: String, observed_tree: String, reason: Option<&str>| nave_apply::BranchRepoResult {
        repo: req.repo.clone(),
        base_ref: req.base_ref.clone(),
        expected_base_sha: req.expected_base_sha.clone(),
        observed_base_sha: observed,
        observed_tree_sha: observed_tree,
        apply_ref: apply_ref.to_string(),
        state,
        reason: reason.map(str::to_string),
    };
    if !dir.exists() {
        return mk(
            nave_apply::BranchState::MissingRef,
            String::new(),
            String::new(),
            Some("clone directory does not exist"),
        );
    }
    if let Err(e) = git_status(dir, &["fetch", "--depth=1", "origin", &req.base_ref]).await {
        return mk(
            nave_apply::BranchState::MissingRef,
            String::new(),
            String::new(),
            Some(&e.to_string()),
        );
    }
    let observed = match git_output(dir, &["rev-parse", &format!("origin/{}", req.base_ref)]).await
    {
        Ok(sha) => sha,
        Err(e) => {
            return mk(
                nave_apply::BranchState::MissingRef,
                String::new(),
                String::new(),
                Some(&e.to_string()),
            );
        }
    };
    if git_output(dir, &["cat-file", "-t", &observed])
        .await
        .ok()
        .as_deref()
        != Some("commit")
    {
        return mk(
            nave_apply::BranchState::NotACommit,
            observed,
            String::new(),
            Some("resolved object is not a commit"),
        );
    }
    // The tree SHA is resolved from the already-fetched, already-verified
    // commit object — a purely local `git rev-parse`, zero extra network
    // or GitHub-API cost. A failure here (should not happen for a verified
    // commit) is reported the same way a missing ref is: NotACommit with
    // an explicit reason, never a silent empty string passed downstream.
    let observed_tree = match git_output(dir, &["rev-parse", &format!("{observed}^{{tree}}")]).await
    {
        Ok(tree_sha) => tree_sha,
        Err(e) => {
            return mk(
                nave_apply::BranchState::NotACommit,
                observed,
                String::new(),
                Some(&format!("resolved commit has no tree: {e}")),
            );
        }
    };
    if observed != req.expected_base_sha {
        return mk(
            nave_apply::BranchState::StaleBase,
            observed,
            observed_tree,
            Some("observed base sha does not match expected"),
        );
    }
    if git_ok(
        dir,
        &[
            "rev-parse",
            "--verify",
            "--quiet",
            &format!("refs/heads/{apply_ref}"),
        ],
    )
    .await
    .unwrap_or(false)
    {
        return mk(
            nave_apply::BranchState::Exists,
            observed,
            observed_tree,
            Some("apply branch already exists"),
        );
    }
    if let Err(e) = git_status(dir, &["checkout", "-B", apply_ref, &observed]).await {
        return mk(
            nave_apply::BranchState::NotACommit,
            observed,
            observed_tree,
            Some(&e.to_string()),
        );
    }
    // ... existing final Ok branch: change its `mk(...)` call site to also
    // pass `observed_tree` in the new parameter slot, matching the
    // signature change above.
}
```

Note: `git rev-parse {observed}^{tree}` is a single local call. The commit has already been verified by the preceding `cat-file -t` check, so a failure here is reported as `NotACommit` with the git error; there is no silent empty string passed downstream.

Locate and update the final success-path `mk(...)` call (the branch after the successful `checkout -B`, at the end of the function body you read in Step 1) to also pass `observed_tree`.

- [ ] **Step 4: `cargo build -p nave_pen` to confirm the crate compiles**

Run: `cd ~/git/discreteds/nave && cargo build -p nave_pen`
Expected: clean build; any other `BranchRepoResult { ... }` construction site in the crate (check `provision_branch`'s `UnknownRepo` early-return, which the earlier read at line ~68-76 showed constructs a `BranchRepoResult` directly) also needs `observed_tree_sha: String::new()` added — the compiler will name every missing-field site.

- [ ] **Step 5: Write the failing Rust test**

In `crates/nave_pen/tests/apply_ops.rs`, add after `branch_provisions_off_verified_remote_base`:

```rust
#[tokio::test]
async fn branch_reports_observed_tree_sha_matching_local_git() {
    let fx = nave_test_support::init_pen_fixture("branch-tree", "acme", "docs", "develop").await;
    let res = provision_branch(
        fx.pen_root.path(),
        &fx.pen,
        &branch_req(&fx, "pulse/apply/p-tree"),
    )
    .await
    .unwrap();
    assert!(matches!(res.repos[0].state, nave_apply::BranchState::Ok));

    let dir = nave_pen::pen_repo_clone_dir(fx.pen_root.path(), "branch-tree", "acme", "docs");
    let expected_tree = git_output(&dir, &["rev-parse", &format!("{}^{{tree}}", fx.base_sha)]).await;
    assert_eq!(res.repos[0].observed_tree_sha, expected_tree);
    assert!(!res.repos[0].observed_tree_sha.is_empty());
}
```

- [ ] **Step 6: Run the test to verify it fails before Step 3's fix is complete, then passes after**

Run: `cd ~/git/discreteds/nave && cargo test -p nave_pen branch_reports_observed_tree_sha`
Expected: PASS (Step 3 already implements the field; this test is written after the implementation in this plan's ordering to keep TDD's red/green cycle honest — run it once against a version of the code with Step 3 reverted to see it fail with "no field `observed_tree_sha`", then reapply Step 3 and re-run to confirm PASS).

- [ ] **Step 7: Run the full nave workspace suite**

Run: `cd ~/git/discreteds/nave && cargo test`
Expected: all tests pass, including every existing `provision_branch`/`provision_one` test (they construct `BranchRepoResult` only through the public API, never a literal struct, so the new field doesn't break them).

- [ ] **Step 8: Commit**

```bash
cd ~/git/discreteds/nave
git add crates/nave_apply/src/lib.rs crates/nave_pen/src/apply_ops.rs crates/nave_pen/tests/apply_ops.rs
git commit -m "feat(apply): provision_one reports observed_tree_sha (local git, zero extra API cost)"
```

---

### Task 2: pulse-gh — wire `observed_tree_sha` through `nave_adapter.py`

**Files:**
- Modify: `lib/pulse/scripts/nave_adapter.py`
- Modify: `lib/pulse/scripts/tests/test_nave_adapter.py`
- Modify: `lib/pulse/scripts/tests/test_apply_ops.py`
- Modify: `lib/pulse/scripts/tests/fixtures/nave_apply/pen/branch.json`

**Interfaces:**
- Consumes: Task 1's `observed_tree_sha` field, always present on a `nave pen branch --json` response's `repos[]` entries once nave is upgraded.
- Produces: `_BRANCH_REQUIRED_FIELDS` gains `"observed_tree_sha"` — a `pen branch` response missing it now fails closed via `_validate_apply_result` (`"nave pen branch repo {repo!r} missing required field(s): observed_tree_sha"`), exactly like a missing `observed_base_sha` already does.

- [ ] **Step 1: Write the failing test — missing `observed_tree_sha` fails closed**

In `lib/pulse/scripts/tests/test_nave_adapter.py`, near the existing `del entry["observed_base_sha"]` test (around line 845), add:

```python
def test_pen_branch_rejects_result_missing_observed_tree_sha():
    entry = _branch_repo_result()
    del entry["observed_tree_sha"]
    payload = {"protocol_version": 1, "adapter_state": "ok", "repos": [entry]}
    runner = RequestFileRunner([_json_ok(payload)])

    result = nave_adapter.pen_branch(runner, "pen", "pulse/apply/p1", [
        {"repo": entry["repo"], "base_ref": entry["base_ref"], "expected_base_sha": entry["expected_base_sha"]},
    ])

    assert result["adapter_state"] == "error"
    assert "observed_tree_sha" in result["reason"]
    assert result["repos"] == []
```

(Match the exact fixture-construction calls the neighboring `test_pen_branch_rejects_result_missing_observed_base_sha`-style test already uses for `RequestFileRunner`/`_json_ok` — read that test's setup lines immediately before writing this one, since the exact request-list shape passed to `pen_branch` must mirror it.)

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py::test_pen_branch_rejects_result_missing_observed_tree_sha -v`
Expected: FAIL — `_branch_repo_result()` doesn't yet produce an `observed_tree_sha` key to delete (`KeyError`), or the assertion fails because the current code doesn't require the field.

- [ ] **Step 3: Add `observed_tree_sha` to `_branch_repo_result()` and `_BRANCH_REQUIRED_FIELDS`**

In `lib/pulse/scripts/tests/test_nave_adapter.py`, the `_branch_repo_result()` helper (around line 804-817) gains a new keyword and dict key:

```python
def _branch_repo_result(
    repo="acme/api",
    base_ref="refs/heads/main",
    expected_base_sha="a" * 40,
    observed_base_sha="a" * 40,
    observed_tree_sha="c" * 40,
    apply_ref="pulse/apply/p1",
    state="ok",
    **extra,
):
    return {
        "repo": repo,
        "base_ref": base_ref,
        "expected_base_sha": expected_base_sha,
        "observed_base_sha": observed_base_sha,
        "observed_tree_sha": observed_tree_sha,
        "apply_ref": apply_ref,
        "state": state,
        **extra,
    }
```

In `lib/pulse/scripts/nave_adapter.py`, `_BRANCH_REQUIRED_FIELDS` (around line 547-554) becomes:

```python
_BRANCH_REQUIRED_FIELDS = (
    "repo",
    "base_ref",
    "expected_base_sha",
    "observed_base_sha",
    "observed_tree_sha",
    "apply_ref",
    "state",
)
```

- [ ] **Step 4: Run the new test to confirm it passes**

Run: `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py::test_pen_branch_rejects_result_missing_observed_tree_sha -v`
Expected: PASS.

- [ ] **Step 5: Update every existing fixture that now fails the stricter check**

`_branch_repo_result()`'s new default (`observed_tree_sha="c" * 40`) already fixes every `test_nave_adapter.py` test that builds a full branch result via that helper. Two more fixtures remain, found by grepping the repo:

`lib/pulse/scripts/tests/test_apply_ops.py`, line 22 — add `observed_tree_sha`:

```python
response(repo, base_ref="refs/heads/main", expected_base_sha="abc", apply_ref=branch, observed_base_sha="abc", observed_tree_sha="tree-abc"),
```

`lib/pulse/scripts/tests/fixtures/nave_apply/pen/branch.json` — add the field to the single repo entry:

```json
{"protocol_version":1,"adapter_state":"ok","repos":[{"repo":"acme/widget","base_ref":"develop","expected_base_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","observed_base_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","observed_tree_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","apply_ref":"pulse/apply/p1","state":"ok"}]}
```

- [ ] **Step 6: Run the full pulse-gh suite to confirm no other fixture regressed**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass. (`RecordingApplyOps`/`Ops`-style fakes in `test_apply_acceptance.py`/`test_apply_phases.py`/`test_apply_driver.py` implement the `ApplyOps` protocol directly in Python and never go through `_validate_apply_result` — they are unaffected and need no changes.)

- [ ] **Step 7: Commit**

```bash
git add lib/pulse/scripts/nave_adapter.py lib/pulse/scripts/tests/test_nave_adapter.py lib/pulse/scripts/tests/test_apply_ops.py lib/pulse/scripts/tests/fixtures/nave_apply/pen/branch.json
git commit -m "feat(apply): require observed_tree_sha on pen branch results"
```

---

### Task 3: pulse-gh — templated argv + `_validate_param_value` (`mutation_plan.py`)

**Files:**
- Modify: `lib/pulse/scripts/mutation_plan.py`
- Modify: `lib/pulse/scripts/tests/test_mutation_plan.py`

**Interfaces:**
- Consumes: nothing new (self-contained module change).
- Produces:
  - `TransformationEntry.params: tuple[str, ...] = ()` — declared `{placeholder}` names an entry's `command_argv` may contain.
  - `resolve_argv(entry: TransformationEntry, params: dict[str, str] | None = None) -> tuple[str, ...]` — `None` (or omitted, all 5 existing callers) returns `entry.command_argv` verbatim; a `dict` expands declared placeholders, re-validating every substituted value.
  - `_validate_param_value(key: str, value: str) -> str` — module-level function; raises `MutationPlanError` on an invalid shape, returns `value` unchanged otherwise.
  - `Proposal.transform_params: dict[str, str] = field(default_factory=dict)` and `Proposal.expected_tree_shas: dict[str, str] | None = None` — both optional, defaulting to values that make every existing caller's behavior unchanged.
  - `build_proposal(..., transform_params: dict[str, str] | None = None, expected_tree_shas: dict[str, str] | None = None, ...)` — two new optional keyword parameters; validates `transform_params` against the registry entry's declared `params` when `registry` is supplied.
  - `proposal_digest` payload gains `transform_params` (canonicalized), so a target-version change changes the digest even though it doesn't change the proposal id.

- [ ] **Step 1: Write the failing tests for `_validate_param_value`**

In `lib/pulse/scripts/tests/test_mutation_plan.py`, add a new section after the `# --- proposal_digest ---` block:

```python
# --- transform_params: templated argv & param-aware validation --------------


def test_validate_param_value_accepts_bare_package_name():
    assert mutation_plan._validate_param_value("package", "requests") == "requests"


def test_validate_param_value_accepts_scoped_npm_package():
    assert mutation_plan._validate_param_value("package", "@acme/widget") == "@acme/widget"


def test_validate_param_value_accepts_version():
    assert mutation_plan._validate_param_value("version", "2.32.0") == "2.32.0"


def test_validate_param_value_rejects_leading_dash():
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid value"):
        mutation_plan._validate_param_value("version", "-rf")


def test_validate_param_value_rejects_pep440_epoch():
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid value"):
        mutation_plan._validate_param_value("version", "1!2.3.4")


def test_validate_param_value_rejects_equals_sign():
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid value"):
        mutation_plan._validate_param_value("version", "2.3.4=malicious")


def test_validate_param_value_rejects_whitespace():
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid value"):
        mutation_plan._validate_param_value("package", "requests malicious")


def test_validate_param_value_rejects_shell_metacharacters():
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid value"):
        mutation_plan._validate_param_value("version", "2.3.4;rm -rf /")
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k validate_param_value -v`
Expected: FAIL — `mutation_plan._validate_param_value` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement `_validate_param_value` and the placeholder-scanning helper**

In `lib/pulse/scripts/mutation_plan.py`, add near the top (after the existing `_only_keys` helper, before `_argv`):

```python
import re

_PACKAGE_PARAM_PATTERN = re.compile(
    r"^(@[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*|[A-Za-z0-9][A-Za-z0-9._-]*)$"
)
_VERSION_PARAM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]*$")
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_]+)\}")


def _validate_param_value(key: str, value: str) -> str:
    """Validate one templated argv substitution value.

    Param-aware: `package` and `version` have different legal shapes (a
    scoped npm package's normalized identity is `@scope/name`; one
    character class for both would reject every scoped package). Both
    patterns preserve the two security invariants strict argv relies on:
    the first character is alphanumeric (never a leading `-`, so a
    substituted value can never become a flag), and the body excludes
    every character with argv/shell meaning (`=`, whitespace,
    `;|&$\`"'<>()`) — `/` and `@` are inert in a single argv element. A
    PEP 440 epoch (`1!2.3.4`) is rejected: `!` is not in either class,
    v1 fail-closed.
    """
    if not isinstance(value, str):
        raise MutationPlanError(f"transform_params[{key!r}] must be a string")
    pattern = _PACKAGE_PARAM_PATTERN if key == "package" else _VERSION_PARAM_PATTERN
    if not pattern.match(value):
        raise MutationPlanError(f"transform_params[{key!r}] invalid value: {value!r}")
    return value


def _check_undeclared_placeholders(
    command_argv: tuple[str, ...], params: tuple[str, ...], entry_id: str
) -> None:
    declared = set(params)
    for index, element in enumerate(command_argv):
        for name in _PLACEHOLDER_PATTERN.findall(element):
            if name not in declared:
                raise MutationPlanError(
                    f"transformation {entry_id}.command_argv[{index}] has undeclared "
                    f"placeholder {{{name}}}: not in params"
                )
```

- [ ] **Step 4: Run to confirm all 8 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k validate_param_value -v`
Expected: PASS (8/8).

- [ ] **Step 5: Write the failing tests for `TransformationEntry.params` + registry loading**

Add:

```python
def registry_data_with_params():
    data = minimal_registry_data()
    data["transformations"]["bump-python-uv"] = {
        "id": "bump-python-uv",
        "command_argv": ["uv", "add", "{package}=={version}"],
        "applies_to": ["always"],
        "validation": {"kind": "none"},
        "allow_scheduled": False,
        "params": ["package", "version"],
    }
    return data


def test_loads_registry_entry_with_declared_params():
    registry = mutation_plan.load_registry(registry_data_with_params())
    entry = registry.get("bump-python-uv")
    assert entry.params == ("package", "version")
    assert entry.command_argv == ("uv", "add", "{package}=={version}")


def test_registry_defaults_params_to_empty_tuple_when_omitted():
    registry = mutation_plan.load_registry(minimal_registry_data())
    assert registry.get("format-python").params == ()


def test_registry_rejects_undeclared_placeholder_in_command_argv():
    data = registry_data_with_params()
    data["transformations"]["bump-python-uv"]["params"] = ["package"]  # omit "version"
    with pytest.raises(mutation_plan.MutationPlanError, match="undeclared placeholder"):
        mutation_plan.load_registry(data)


def test_registry_rejects_non_list_params():
    data = registry_data_with_params()
    data["transformations"]["bump-python-uv"]["params"] = "package"
    with pytest.raises(mutation_plan.MutationPlanError, match="must be a list"):
        mutation_plan.load_registry(data)
```

- [ ] **Step 6: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k "declared_params or undeclared_placeholder or non_list_params" -v`
Expected: FAIL — `TransformationEntry` has no `params` field.

- [ ] **Step 7: Add `params` to `TransformationEntry` and wire registry loading**

In `lib/pulse/scripts/mutation_plan.py`:

```python
@dataclass(frozen=True)
class TransformationEntry:
    """One registered repository transformation. `command_argv` is strict
    unless `params` declares placeholders — see `resolve_argv`."""

    id: str
    command_argv: tuple[str, ...]
    applies_to: tuple[str, ...]
    validation: ValidationSpec
    allow_scheduled: bool
    params: tuple[str, ...] = ()
```

In `_load_transformation`, extend the allowed-keys set and load `params` before the undeclared-placeholder check:

```python
def _load_transformation(raw: Any, entry_id: str) -> TransformationEntry:
    item = _mapping(raw, f"transformation {entry_id}")
    _only_keys(
        item,
        {"id", "command_argv", "applies_to", "validation", "allow_scheduled", "params"},
        f"transformation {entry_id}",
    )
    declared_id = _string(item.get("id"), f"transformation {entry_id}.id")
    if declared_id != entry_id:
        raise MutationPlanError(
            f"transformation {entry_id}.id must match its registry key: {declared_id}"
        )
    command_argv = _argv(item.get("command_argv"), f"transformation {entry_id}.command_argv")
    try:
        validate_command_argv(command_argv, entry_id)
    except ValueError as exc:
        raise MutationPlanError(str(exc)) from exc
    params_raw = item.get("params")
    params = (
        tuple(
            _string(p, f"transformation {entry_id}.params entry")
            for p in _list(params_raw, f"transformation {entry_id}.params")
        )
        if params_raw is not None
        else ()
    )
    _check_undeclared_placeholders(command_argv, params, entry_id)
    applies_to_raw = _list(item.get("applies_to"), f"transformation {entry_id}.applies_to")
    if not applies_to_raw:
        raise MutationPlanError(f"transformation {entry_id}.applies_to must be non-empty")
    applies_to = tuple(
        _applicability_predicate(predicate, entry_id) for predicate in applies_to_raw
    )
    validation = _load_validation(item.get("validation"), entry_id)
    allow_scheduled = item.get("allow_scheduled")
    if not isinstance(allow_scheduled, bool):
        raise MutationPlanError(
            f"transformation {entry_id}.allow_scheduled must be a boolean"
        )
    return TransformationEntry(
        id=entry_id,
        command_argv=command_argv,
        applies_to=applies_to,
        validation=validation,
        allow_scheduled=allow_scheduled,
        params=params,
    )
```

- [ ] **Step 8: Run to confirm all 4 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k "declared_params or undeclared_placeholder or non_list_params" -v`
Expected: PASS (4/4).

- [ ] **Step 9: Write the failing tests for templated `resolve_argv`**

Add:

```python
def test_resolve_argv_expands_declared_params():
    registry = mutation_plan.load_registry(registry_data_with_params())
    entry = registry.get("bump-python-uv")
    argv = mutation_plan.resolve_argv(entry, {"package": "requests", "version": "2.32.0"})
    assert argv == ("uv", "add", "requests==2.32.0")


def test_resolve_argv_none_params_returns_verbatim_argv_backward_compat():
    registry = mutation_plan.load_registry(minimal_registry_data())
    entry = registry.get("format-python")
    assert mutation_plan.resolve_argv(entry) == entry.command_argv
    assert mutation_plan.resolve_argv(entry, None) == entry.command_argv


def test_resolve_argv_rejects_missing_declared_param():
    registry = mutation_plan.load_registry(registry_data_with_params())
    entry = registry.get("bump-python-uv")
    with pytest.raises(mutation_plan.MutationPlanError, match="missing declared param"):
        mutation_plan.resolve_argv(entry, {"package": "requests"})


def test_resolve_argv_rejects_invalid_substituted_value():
    registry = mutation_plan.load_registry(registry_data_with_params())
    entry = registry.get("bump-python-uv")
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid value"):
        mutation_plan.resolve_argv(entry, {"package": "requests", "version": "-rf"})


def test_resolve_argv_scoped_npm_package_round_trips():
    data = registry_data_with_params()
    data["transformations"]["bump-npm"] = {
        "id": "bump-npm",
        "command_argv": ["npm", "install", "--save-exact", "{package}@{version}"],
        "applies_to": ["always"],
        "validation": {"kind": "none"},
        "allow_scheduled": False,
        "params": ["package", "version"],
    }
    registry = mutation_plan.load_registry(data)
    entry = registry.get("bump-npm")
    argv = mutation_plan.resolve_argv(entry, {"package": "@acme/widget", "version": "1.2.3"})
    assert argv == ("npm", "install", "--save-exact", "@acme/widget@1.2.3")
```

- [ ] **Step 10: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k resolve_argv -v`
Expected: `test_resolve_argv_returns_registered_argv_verbatim` and the two shell-metacharacter tests still PASS unchanged (verbatim path); the 5 new tests FAIL (`resolve_argv() takes 1 positional argument but 2 were given`).

- [ ] **Step 11: Implement templated `resolve_argv`**

Replace `resolve_argv` in `lib/pulse/scripts/mutation_plan.py`:

```python
def resolve_argv(
    entry: TransformationEntry, params: dict[str, str] | None = None
) -> tuple[str, ...]:
    """Return a registered transformation's argv, optionally with declared
    placeholders expanded from `params`.

    `params is None` (all callers before this change, and every entry with
    no declared `params`) returns `entry.command_argv` verbatim — byte-
    identical, no interpolation, matching the original strict-argv
    contract. A `dict` expands every `{key}` the registry already
    validated as declared at load time (re-checked here too, fail-closed
    defense in depth); every substituted value is re-validated with
    `_validate_param_value` immediately before insertion. The substitution
    still lands in a single argv element handed to
    `subprocess.run(..., shell=False)` — no shell, no splitting, no
    reinterpretation of any element boundary.
    """
    if params is None:
        return entry.command_argv
    missing = [key for key in entry.params if key not in params]
    if missing:
        raise MutationPlanError(
            f"resolve_argv: missing declared param(s) for {entry.id}: {', '.join(missing)}"
        )

    def _substitute(element: str) -> str:
        def _sub_one(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in entry.params:
                raise MutationPlanError(
                    f"resolve_argv: undeclared placeholder {{{key}}} in {entry.id}"
                )
            return _validate_param_value(key, params[key])

        return _PLACEHOLDER_PATTERN.sub(_sub_one, element)

    return tuple(_substitute(element) for element in entry.command_argv)
```

- [ ] **Step 12: Run to confirm all pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k resolve_argv -v`
Expected: PASS (8/8 — 3 existing + 5 new).

- [ ] **Step 13: Write the failing tests for `Proposal.transform_params` + `build_proposal`**

Add:

```python
def test_build_proposal_accepts_transform_params_with_registry_validation():
    registry = mutation_plan.load_registry(registry_data_with_params())
    proposal = mutation_plan.build_proposal(
        id="apply-bump-python-requests-uv-abc123",
        selection=["acme/api"],
        transformation="bump-python-uv",
        expected_shas={"acme/api": "a" * 40},
        actor=minimal_actor(),
        mutation_policy="allow-listed",
        bound_paths={"acme/api": ("pyproject.toml", "uv.lock")},
        transform_params={"package": "requests", "version": "2.32.0"},
        registry=registry,
    )
    assert proposal.transform_params == {"package": "requests", "version": "2.32.0"}


def test_build_proposal_defaults_transform_params_to_empty_dict():
    proposal = mutation_plan.build_proposal(
        id="p1", selection=["acme/api"], transformation="format-python",
        expected_shas={"acme/api": "abc"}, actor=minimal_actor(),
    )
    assert proposal.transform_params == {}


def test_build_proposal_rejects_unknown_transform_params_key():
    registry = mutation_plan.load_registry(registry_data_with_params())
    with pytest.raises(mutation_plan.MutationPlanError, match="unknown transform_params key"):
        mutation_plan.build_proposal(
            id="p1", selection=["acme/api"], transformation="bump-python-uv",
            expected_shas={"acme/api": "a" * 40}, actor=minimal_actor(),
            mutation_policy="allow-listed", bound_paths={"acme/api": ("pyproject.toml",)},
            transform_params={"package": "requests", "version": "2.32.0", "extra": "x"},
            registry=registry,
        )


def test_build_proposal_rejects_missing_declared_transform_params_key():
    registry = mutation_plan.load_registry(registry_data_with_params())
    with pytest.raises(mutation_plan.MutationPlanError, match="missing declared transform_params"):
        mutation_plan.build_proposal(
            id="p1", selection=["acme/api"], transformation="bump-python-uv",
            expected_shas={"acme/api": "a" * 40}, actor=minimal_actor(),
            mutation_policy="allow-listed", bound_paths={"acme/api": ("pyproject.toml",)},
            transform_params={"package": "requests"},
            registry=registry,
        )


def test_build_proposal_rejects_nonempty_transform_params_for_untemplated_entry():
    registry = mutation_plan.load_registry(minimal_registry_data())
    with pytest.raises(mutation_plan.MutationPlanError, match="transform_params must be empty"):
        mutation_plan.build_proposal(
            id="p1", selection=["acme/api"], transformation="format-python",
            expected_shas={"acme/api": "abc"}, actor=minimal_actor(),
            transform_params={"unexpected": "value"},
            registry=registry,
        )


def test_build_proposal_rejects_invalid_transform_params_value():
    registry = mutation_plan.load_registry(registry_data_with_params())
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid value"):
        mutation_plan.build_proposal(
            id="p1", selection=["acme/api"], transformation="bump-python-uv",
            expected_shas={"acme/api": "a" * 40}, actor=minimal_actor(),
            mutation_policy="allow-listed", bound_paths={"acme/api": ("pyproject.toml",)},
            transform_params={"package": "requests", "version": "-rf"},
            registry=registry,
        )
```

- [ ] **Step 14: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k transform_params -v`
Expected: FAIL — `build_proposal()` doesn't accept `transform_params`.

- [ ] **Step 15: Add `transform_params` and `expected_tree_shas` to `Proposal`, and validate in `build_proposal`**

In `lib/pulse/scripts/mutation_plan.py`:

```python
@dataclass(frozen=True)
class Proposal:
    """A validated repository-mutation proposal.

    `selection` is the list of `owner/name` repositories this proposal
    targets. `expected_shas` is the expected-base guard: the commit SHA
    each selected repo must currently be at before the orchestrator (F6
    Task 3) proceeds — a mismatch means the remote moved since the
    proposal was built and the run must block rather than mutate a stale
    base. `transform_params` templates `command_argv` placeholders
    (dependency-bump only; empty for every other source). `expected_tree_shas`
    is a second, independent drift guard on the *tree* SHA the proposal's
    target was computed from (dependency-bump only; `None` for every other
    source, which never populates or checks it).
    """

    id: str
    selection: tuple[str, ...]
    transformation: str
    expected_shas: dict[str, str]
    mutation_policy: str
    actor: Actor
    bound_paths: dict[str, tuple[str, ...]] = field(default_factory=dict)
    transform_params: dict[str, str] = field(default_factory=dict)
    expected_tree_shas: dict[str, str] | None = None
```

In `build_proposal`, add the two new parameters and validation. The signature becomes:

```python
def build_proposal(
    id: str,
    selection: list[str] | tuple[str, ...],
    transformation: str,
    expected_shas: dict[str, str],
    actor: dict[str, Any] | Actor,
    mutation_policy: str = "propose",
    bound_paths: dict[str, list[str] | tuple[str, ...]] | None = None,
    transform_params: dict[str, str] | None = None,
    expected_tree_shas: dict[str, str] | None = None,
    registry: TransformationRegistry | None = None,
) -> Proposal:
```

After the existing `normalized_bound_paths` block and before the `proposal = Proposal(...)` construction, add:

```python
    normalized_transform_params: dict[str, str] = {}
    if transform_params is not None:
        raw_params = _mapping(transform_params, "proposal.transform_params")
        if registry is not None:
            entry = registry.get(transformation_id)
            unknown_keys = set(raw_params) - set(entry.params)
            if unknown_keys:
                raise MutationPlanError(
                    f"unknown transform_params key: {sorted(unknown_keys)[0]}"
                )
            missing_keys = set(entry.params) - set(raw_params)
            if entry.params and missing_keys:
                raise MutationPlanError(
                    "missing declared transform_params key(s): "
                    f"{', '.join(sorted(missing_keys))}"
                )
            if not entry.params and raw_params:
                raise MutationPlanError(
                    f"proposal.transform_params must be empty for {transformation_id!r} "
                    "(no declared params)"
                )
            normalized_transform_params = {
                key: _validate_param_value(key, value) for key, value in raw_params.items()
            }
        else:
            normalized_transform_params = {
                _string(key, "proposal.transform_params key"): _string(
                    value, f"proposal.transform_params[{key}]"
                )
                for key, value in raw_params.items()
            }

    normalized_expected_tree_shas: dict[str, str] | None = None
    if expected_tree_shas is not None:
        tree_shas = _mapping(expected_tree_shas, "proposal.expected_tree_shas")
        missing_tree = set(repos) - set(tree_shas)
        if missing_tree:
            raise MutationPlanError(
                f"proposal.expected_tree_shas missing entry for: {sorted(missing_tree)[0]}"
            )
        extra_tree = set(tree_shas) - set(repos)
        if extra_tree:
            raise MutationPlanError(
                f"proposal.expected_tree_shas has entry outside selection: {sorted(extra_tree)[0]}"
            )
        normalized_expected_tree_shas = {
            repo: _string(tree_shas[repo], f"proposal.expected_tree_shas[{repo}]")
            for repo in repos
        }
```

Update the `Proposal(...)` construction to pass both:

```python
    proposal = Proposal(
        id=proposal_id,
        selection=repos,
        transformation=transformation_id,
        expected_shas=normalized_shas,
        mutation_policy=policy,
        actor=actor_block,
        bound_paths=normalized_bound_paths,
        transform_params=normalized_transform_params,
        expected_tree_shas=normalized_expected_tree_shas,
    )
```

- [ ] **Step 16: Run to confirm all 6 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -k transform_params -v`
Expected: PASS (6/6).

- [ ] **Step 17: Write the failing test for `proposal_digest` covering `transform_params`**

Add to the `_digest_proposal` overrides parametrization (find the existing `@pytest.mark.parametrize(...)` block feeding `test_proposal_digest_changes_when_any_covered_field_changes` — read its exact current parameter list first) a new case, and a standalone test:

```python
def test_proposal_digest_changes_when_transform_params_changes():
    # Same proposal id, different target version via templated argv:
    registry = mutation_plan.load_registry(registry_data_with_params())
    p1 = mutation_plan.build_proposal(
        id="apply-bump-python-requests-uv-abc123", selection=["acme/api"],
        transformation="bump-python-uv", expected_shas={"acme/api": "a" * 40},
        actor=minimal_actor(), mutation_policy="allow-listed",
        bound_paths={"acme/api": ("pyproject.toml",)},
        transform_params={"package": "requests", "version": "2.32.0"},
        registry=registry,
    )
    p2 = mutation_plan.build_proposal(
        id="apply-bump-python-requests-uv-abc123", selection=["acme/api"],
        transformation="bump-python-uv", expected_shas={"acme/api": "a" * 40},
        actor=minimal_actor(), mutation_policy="allow-listed",
        bound_paths={"acme/api": ("pyproject.toml",)},
        transform_params={"package": "requests", "version": "2.33.0"},
        registry=registry,
    )
    assert mutation_plan.proposal_digest(p1) != mutation_plan.proposal_digest(p2)
```

- [ ] **Step 18: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py::test_proposal_digest_changes_when_transform_params_changes -v`
Expected: FAIL — `proposal_digest` doesn't cover `transform_params` yet, so `p1`/`p2` digest identically.

- [ ] **Step 19: Add `transform_params` to `proposal_digest`'s payload**

In `lib/pulse/scripts/mutation_plan.py`, `proposal_digest`'s payload dict gains one key:

```python
    payload = {
        "id": proposal.id,
        "selection": list(proposal.selection),
        "transformation": proposal.transformation,
        "expected_shas": dict(proposal.expected_shas),
        "mutation_policy": proposal.mutation_policy,
        "bound_paths": {
            repo: list(paths) for repo, paths in proposal.bound_paths.items()
        },
        "transform_params": dict(sorted(proposal.transform_params.items())),
        "actor": {
            "gh_login": proposal.actor.gh_login,
            "machine": proposal.actor.machine,
            "mode": proposal.actor.mode,
        },
    }
```

(`expected_tree_shas` is deliberately **not** added to the digest payload — it is a drift guard the proposal is re-validated against at provision time, not proposal content the digest identifies; the existing `expected_shas` sets the precedent that base-SHA guards live outside the identity digest... re-check this decision against the existing `expected_shas` treatment: `expected_shas` **is** already in the digest payload above. For consistency, `expected_tree_shas` should be too — add it:)

```python
        "expected_tree_shas": dict(sorted((proposal.expected_tree_shas or {}).items())),
```

Add this line to the payload dict (after `"transform_params"`), so a tree-drift-guard change is also digest-visible, consistent with how `expected_shas` is already covered.

- [ ] **Step 20: Run to confirm pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py::test_proposal_digest_changes_when_transform_params_changes -v`
Expected: PASS.

- [ ] **Step 21: Run the full mutation_plan test file**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -v`
Expected: every test passes, including every pre-existing test (backward compatibility: `transform_params`/`expected_tree_shas` default to values that reproduce prior behavior exactly).

- [ ] **Step 22: Run the full pulse-gh suite**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass — `proposal_digest`'s new payload keys are additive per-proposal, so no test elsewhere that captures/compares a digest literal (rather than comparing two live-computed digests) should exist; if one does, it will show up here and must be updated to match the new payload shape rather than skipped.

- [ ] **Step 23: Commit**

```bash
git add lib/pulse/scripts/mutation_plan.py lib/pulse/scripts/tests/test_mutation_plan.py
git commit -m "feat(apply): whitelisted argv templating + tree-SHA drift guard on Proposal"
```

---

### Task 4: pulse-gh — `apply_phases.py`: templated exec + tree-drift provision check

**Files:**
- Modify: `lib/pulse/scripts/apply_phases.py`
- Modify: `lib/pulse/scripts/tests/test_apply_phases.py`

**Interfaces:**
- Consumes: Task 3's `resolve_argv(entry, params)`, `Proposal.transform_params`, `Proposal.expected_tree_shas`; Task 2's `observed_tree_sha` (present on every real provision result once nave is upgraded).
- Produces:
  - `exec_phase(runner, pen, entry, transform_params: dict[str, str] | None = None)` — new optional 4th parameter, defaulting to `None` (existing callers unaffected until Task 8 updates them).
  - `provision_phase` gains one more `elif`, checked **after** the existing `observed_base_sha` (`stale-base`) check, comparing `observed_tree_sha` against `proposal.expected_tree_shas`, gated on `proposal.expected_tree_shas is not None` — every non-dependency-bump proposal (where the field is `None`) is completely unaffected.

- [ ] **Step 1: Write the failing test for templated `exec_phase`**

In `lib/pulse/scripts/tests/test_apply_phases.py`, add near `test_exec_blocks_missing_tool_before_exec`:

```python
def entry_with_params():
    return mutation_plan.load_registry({"transformations": {"bump-python-uv": {
        "id": "bump-python-uv", "command_argv": ["uv", "add", "{package}=={version}"],
        "applies_to": ["always"], "validation": {"kind": "none"}, "allow_scheduled": False,
        "params": ["package", "version"],
    }}}).get("bump-python-uv")


def test_exec_passes_transform_params_to_resolve_argv(monkeypatch):
    captured = {}

    def fake_pen_exec(runner, pen_name, argv, **kwargs):
        captured["argv"] = argv
        return {"adapter_state": "ok"}

    monkeypatch.setattr(apply_phases.nave_adapter, "pen_exec", fake_pen_exec)
    pen = {"name": "pen", "repos": [{"repo": "acme/api"}]}
    result = apply_phases.exec_phase(
        None, pen, entry_with_params(), transform_params={"package": "requests", "version": "2.32.0"}
    )
    assert captured["argv"] == ["uv", "add", "requests==2.32.0"]
    assert result["acme/api"]["state"] == "ok"


def test_exec_none_transform_params_uses_verbatim_argv_backward_compat(monkeypatch):
    captured = {}

    def fake_pen_exec(runner, pen_name, argv, **kwargs):
        captured["argv"] = argv
        return {"adapter_state": "ok"}

    monkeypatch.setattr(apply_phases.nave_adapter, "pen_exec", fake_pen_exec)
    monkeypatch.setattr(apply_phases.executor_probe, "probe_required_tool", lambda *_: {"state": "ok"})
    pen = {"name": "pen", "repos": [{"repo": "acme/api"}]}
    apply_phases.exec_phase(None, pen, entry())
    assert captured["argv"] == ["ruff", "format", "."]
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_phases.py -k transform_params -v`
Expected: FAIL — `exec_phase()` doesn't accept a 4th positional/keyword argument.

- [ ] **Step 3: Implement**

In `lib/pulse/scripts/apply_phases.py`:

```python
def exec_phase(runner, pen, entry, transform_params=None) -> dict[str, dict]:
    argv = resolve_argv(entry, transform_params)
    probe = executor_probe.probe_required_tool(argv[0])
    selection = tuple(
        item.get("repo") or f"{item.get('owner')}/{item.get('name')}"
        for item in pen.get("repos", [])
    ) if isinstance(pen, dict) else ()
    if probe.get("state") != "ok":
        return {repo: {"state": "blocked", "reason": probe.get("reason", "required tool missing")} for repo in selection}
    pen_name = pen.get("name") if isinstance(pen, dict) else pen
    result = nave_adapter.pen_exec(runner, pen_name, list(argv), only=None, commit=False, push_changes=False, message=None)
    if result.get("adapter_state") == "error":
        reason = (result.get("stderr") or "").strip() or "pen exec failed"
        return {repo: {"state": "failed", "reason": reason} for repo in selection}
    return {repo: {"state": "ok"} for repo in selection}
```

(Only the signature and the first line changed — `resolve_argv(entry)` → `resolve_argv(entry, transform_params)`.)

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_phases.py -k transform_params -v`
Expected: PASS (2/2). Also re-run the pre-existing `test_exec_blocks_missing_tool_before_exec` to confirm it's unaffected: `uv run pytest lib/pulse/scripts/tests/test_apply_phases.py::test_exec_blocks_missing_tool_before_exec -v` → PASS.

- [ ] **Step 5: Write the failing tests for the tree-drift provision check**

Add near `test_provision_blocks_drift_and_echo_mismatch`:

```python
def proposal_with_tree_shas(**tree_shas):
    return mutation_plan.build_proposal(
        id="run-1", selection=list(REPOS), transformation="format-python",
        expected_shas={repo: "abc" for repo in REPOS},
        actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
        mutation_policy="allow-listed", bound_paths={repo: ("src/**",) for repo in REPOS},
        expected_tree_shas=tree_shas or {repo: "tree-abc" for repo in REPOS},
    )


def test_provision_blocks_stale_tree_when_commit_matches_but_tree_drifted():
    ops = Ops({
        "acme/api": provision_item("acme/api", observed_tree_sha="tree-DIFFERENT"),
        "acme/web": provision_item("acme/web", observed_tree_sha="tree-abc"),
    })
    result = apply_phases.provision_phase(
        None, None, ops, proposal_with_tree_shas(), "pulse/apply/run-1",
        {repo: "refs/heads/main" for repo in REPOS},
    )
    assert "stale-tree" in result["acme/api"]["reason"]
    assert result["acme/web"]["state"] == "ok"


def test_provision_reports_stale_base_not_stale_tree_when_both_drift():
    """Commit-level drift takes precedence in the reported reason — the
    operator sees the more actionable stale-base diagnosis first."""
    ops = Ops({
        "acme/api": provision_item("acme/api", observed_base_sha="old", observed_tree_sha="tree-DIFFERENT"),
        "acme/web": provision_item("acme/web", observed_tree_sha="tree-abc"),
    })
    result = apply_phases.provision_phase(
        None, None, ops, proposal_with_tree_shas(), "pulse/apply/run-1",
        {repo: "refs/heads/main" for repo in REPOS},
    )
    assert "stale-base" in result["acme/api"]["reason"]
    assert "stale-tree" not in result["acme/api"]["reason"]


def test_provision_ignores_tree_sha_when_expected_tree_shas_is_none():
    """Every non-dependency-bump proposal (expected_tree_shas=None) is
    unaffected even if the fake provision result's observed_tree_sha
    doesn't match anything — the elif is never reached."""
    ops = Ops({
        "acme/api": provision_item("acme/api", observed_tree_sha="whatever"),
        "acme/web": provision_item("acme/web", observed_tree_sha="anything"),
    })
    result = apply_phases.provision_phase(
        None, None, ops, proposal(), "pulse/apply/run-1",
        {repo: "refs/heads/main" for repo in REPOS},
    )
    assert result["acme/api"]["state"] == "ok"
    assert result["acme/web"]["state"] == "ok"
```

Update `provision_item`'s default to carry a matching `observed_tree_sha` so pre-existing tests (which use `expected_tree_shas=None` proposals and never exercise the new elif) stay green regardless:

```python
def provision_item(repo, **changes):
    item = {
        "state": "ok", "base_ref": "refs/heads/main", "expected_base_sha": "abc",
        "apply_ref": "pulse/apply/run-1", "observed_base_sha": "abc",
        "observed_tree_sha": "tree-abc",
    }
    item.update(changes)
    return item
```

- [ ] **Step 6: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_phases.py -k "stale_tree or ignores_tree_sha" -v`
Expected: FAIL — `provision_phase` has no tree-drift check yet, so `test_provision_blocks_stale_tree_when_commit_matches_but_tree_drifted` sees `state == "ok"` for `acme/api` instead of `blocked`.

- [ ] **Step 7: Implement the tree-drift `elif`**

In `lib/pulse/scripts/apply_phases.py`, `provision_phase`:

```python
def provision_phase(runner, pen, apply_ops, proposal, apply_branch, base_refs) -> dict[str, dict]:
    del runner, pen
    expected_shas = proposal.expected_shas
    expected_tree_shas = proposal.expected_tree_shas
    raw = _by_repo(apply_ops.provision_branch(apply_branch, expected_shas))
    outcomes = {}
    for repo in proposal.selection:
        item = raw.get(repo)
        reason = None
        if not isinstance(item, dict) or item.get("state") != "ok":
            reason = item.get("reason", "missing provision result") if isinstance(item, dict) else "missing provision result"
        elif item.get("expected_base_sha") != expected_shas.get(repo):
            reason = "provision echoed expected_base_sha mismatch"
        elif item.get("apply_ref") != apply_branch:
            reason = "provision echoed apply_ref mismatch"
        elif repo not in base_refs or not base_refs[repo]:
            reason = "provision missing expected base_ref for echo verification"
        elif item.get("base_ref") != base_refs[repo]:
            reason = "provision echoed base_ref mismatch"
        elif item.get("observed_base_sha") != expected_shas.get(repo):
            reason = "stale-base: observed base SHA drifted from expected base SHA"
        elif expected_tree_shas is not None and item.get("observed_tree_sha") != expected_tree_shas.get(repo):
            reason = "stale-tree: observed tree SHA drifted from evidence tree SHA"
        outcomes[repo] = ({"state": "blocked", "reason": reason} if reason else {"state": "ok", "observed_base_sha": item["observed_base_sha"]})
    return outcomes
```

(Only two lines added: `expected_tree_shas = proposal.expected_tree_shas`, and the new `elif` — placed after the existing `stale-base` `elif`, satisfying the ordering requirement.)

- [ ] **Step 8: Run to confirm all pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_phases.py -v`
Expected: every test in the file passes, including every pre-existing test (the new `elif` is unreachable when `expected_tree_shas is None`, which is every existing proposal fixture).

- [ ] **Step 9: Run the full pulse-gh suite**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add lib/pulse/scripts/apply_phases.py lib/pulse/scripts/tests/test_apply_phases.py
git commit -m "feat(apply): exec_phase templating + provision_phase tree-drift guard"
```

---

### Task 5: pulse-gh — bump transformation registry entries

**Files:**
- Modify: `templates/transformations.yaml.template`
- Modify: `lib/pulse/scripts/tests/test_mutation_plan.py`

**Interfaces:**
- Consumes: Task 3's `params:` registry key.
- Produces: four new transformation ids loadable via `mutation_plan.load_registry` — `bump-python-uv`, `bump-python-poetry`, `bump-npm`, `bump-pnpm` — each with `params: [package, version]`, `allow_scheduled: false` (a dependency bump is never unattended), `applies_to: [always]` (manager-eligibility is decided by `_collect_dependency_bump`'s manager-split, not by `applies_to`), `validation: {kind: none}`.

- [ ] **Step 1: Write the failing test — the real template file loads and contains the four entries**

In `lib/pulse/scripts/tests/test_mutation_plan.py`, add:

```python
def test_transformations_template_loads_bump_entries():
    template_path = Path(__file__).resolve().parents[4] / "templates" / "transformations.yaml.template"
    registry = mutation_plan.load_registry(template_path)
    for tid, argv in [
        ("bump-python-uv", ("uv", "add", "{package}=={version}")),
        ("bump-python-poetry", ("poetry", "add", "{package}=={version}")),
        ("bump-npm", ("npm", "install", "--save-exact", "{package}@{version}")),
        ("bump-pnpm", ("pnpm", "add", "--save-exact", "{package}@{version}")),
    ]:
        entry = registry.get(tid)
        assert entry.command_argv == argv
        assert entry.params == ("package", "version")
        assert entry.allow_scheduled is False
```

(Confirm the exact relative-path depth from `test_mutation_plan.py` to the repo root — `lib/pulse/scripts/tests/test_mutation_plan.py` is 4 levels below the repo root (`tests` → `scripts` → `pulse` → `lib`), so `parents[4]` (0-indexed: `tests`=0, `scripts`=1, `pulse`=2, `lib`=3, repo-root=4) is `Path(__file__).resolve().parents[4]`; verify this resolves to the actual repo root before running, e.g. via `python -c "from pathlib import Path; print(Path('lib/pulse/scripts/tests/test_mutation_plan.py').resolve().parents[4])"` from the repo root, and adjust the index if off by one. Add `from pathlib import Path` to the test file's imports if not already present.)

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py::test_transformations_template_loads_bump_entries -v`
Expected: FAIL — `unknown transformation: bump-python-uv`.

- [ ] **Step 3: Add the four entries to `templates/transformations.yaml.template`**

Append, after the existing `regenerate-docs-index` entry:

```yaml
  # F11 dependency-bump handoff: one entry per package manager the F4
  # DivergenceFinding -> Proposal handoff (apply_rederive.py's
  # dependency-bump source kind) can target. `{package}`/`{version}` are
  # whitelisted argv placeholders (declared via `params`), expanded by
  # `mutation_plan.resolve_argv` from `Proposal.transform_params` and
  # re-validated by `_validate_param_value` before substitution — never
  # shell-interpreted, never split, never reused for anything but these
  # two declared slots. Never allowed to run unattended: a dependency
  # bump always needs human review of the resulting lockfile diff before
  # it lands (mirrors refresh-node-lockfile's allow_scheduled: false).
  bump-python-uv:
    id: bump-python-uv
    command_argv:
      - uv
      - add
      - "{package}=={version}"
    applies_to:
      - always
    validation:
      kind: none
    allow_scheduled: false
    params:
      - package
      - version

  bump-python-poetry:
    id: bump-python-poetry
    command_argv:
      - poetry
      - add
      - "{package}=={version}"
    applies_to:
      - always
    validation:
      kind: none
    allow_scheduled: false
    params:
      - package
      - version

  bump-npm:
    id: bump-npm
    command_argv:
      - npm
      - install
      - --save-exact
      - "{package}@{version}"
    applies_to:
      - always
    validation:
      kind: none
    allow_scheduled: false
    params:
      - package
      - version

  bump-pnpm:
    id: bump-pnpm
    command_argv:
      - pnpm
      - add
      - --save-exact
      - "{package}@{version}"
    applies_to:
      - always
    validation:
      kind: none
    allow_scheduled: false
    params:
      - package
      - version
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py::test_transformations_template_loads_bump_entries -v`
Expected: PASS.

- [ ] **Step 5: Run the full pulse-gh suite**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass — confirms `load_registry` on the real, now-larger template file still validates cleanly against every other existing entry.

- [ ] **Step 6: Commit**

```bash
git add templates/transformations.yaml.template lib/pulse/scripts/tests/test_mutation_plan.py
git commit -m "feat(apply): register bump-python-uv/poetry, bump-npm/pnpm transformations"
```

---

### Task 6: pulse-gh — the `dependency-bump` source kind (`apply_rederive.py`)

This is the largest task — it re-derives one F4 finding into N per-manager proposals. Read `docs/superpowers/specs/2026-08-15-dependency-bump-handoff-design.md` § 4.4 alongside this task; the steps below are its concrete implementation.

**Files:**
- Modify: `lib/pulse/scripts/apply_rederive.py`
- Modify: `lib/pulse/scripts/tests/test_apply_rederive.py`

**Interfaces:**
- Consumes: Task 3's `Proposal.transform_params`/`expected_tree_shas`/`build_proposal(transform_params=, expected_tree_shas=)`; Task 5's `bump-python-uv`/`bump-python-poetry`/`bump-npm`/`bump-pnpm` transformation ids; `dependencies.{PackageRecord, DivergenceFinding, CoherenceGroup, compare}`; `dependency_policy.load_dependency_policy`; `dependency_pipeline.{materialize_dependency_evidence, evaluate_dependencies}`; `dependency_evidence.load_dependency_evidence`; `profile_dispatch.ConfigError`.
- Produces:
  - `SOURCE_KINDS` gains `"dependency-bump"`.
  - `DependencyBumpProviderInputs` dataclass — the single `ProviderInputs` variant this source produces (one per finding, not per proposal).
  - `bump_proposal_id(ecosystem, package, manager, selection) -> str`.
  - `bump_summary(finding_ref, group_repos, manager) -> dict` — mirrors `neutral_summary`'s "no propose phase" synthesis.
  - `_collect_dependency_bump(finding_ref, actor, io_seams) -> DependencyBumpProviderInputs`.
  - `rederive_dependency_bump(inputs: DependencyBumpProviderInputs) -> list[RederivedProposal]` — a **new top-level function**, not folded into the generic single-return `rederive()` dispatcher (the return type is plural, a structural break from every other source kind — the spec calls this out explicitly as the "one structural difference").
  - `MANAGER_TRANSFORM: dict[str, str]` — `{"uv": "bump-python-uv", "poetry": "bump-python-poetry", "npm": "bump-npm", "pnpm": "bump-pnpm"}`.

- [ ] **Step 1: Write the failing test for `bump_proposal_id`**

In `lib/pulse/scripts/tests/test_apply_rederive.py`, add a new section (find where `neutral_fleet_proposal_id`/`neutral_proposal_id` are tested first, to match the existing test style in this file, then add adjacent):

```python
# --- dependency-bump: bump_proposal_id ---------------------------------------


def test_bump_proposal_id_deterministic_over_identity():
    id1 = apply_rederive.bump_proposal_id("python", "requests", "uv", ("acme/api", "acme/web"))
    id2 = apply_rederive.bump_proposal_id("python", "requests", "uv", ("acme/web", "acme/api"))
    assert id1 == id2  # order-independent (selection is sorted before hashing)
    assert id1.startswith("apply-bump-python-requests-uv-")


def test_bump_proposal_id_distinct_from_neutral_fleet_id():
    bump_id = apply_rederive.bump_proposal_id("python", "requests", "uv", ("acme/api",))
    neutral_id = apply_rederive.neutral_fleet_proposal_id("format-python", ("acme/api",))
    assert bump_id != neutral_id


def test_bump_proposal_id_target_independent():
    """The id must not encode the target version — a target change
    re-derives through the same id (spec § 4.6 cascading-bump semantics)."""
    id_a = apply_rederive.bump_proposal_id("python", "requests", "uv", ("acme/api",))
    id_b = apply_rederive.bump_proposal_id("python", "requests", "uv", ("acme/api",))
    assert id_a == id_b


def test_bump_proposal_id_changes_with_membership():
    id_a = apply_rederive.bump_proposal_id("python", "requests", "uv", ("acme/api",))
    id_b = apply_rederive.bump_proposal_id("python", "requests", "uv", ("acme/api", "acme/web"))
    assert id_a != id_b
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k bump_proposal_id -v`
Expected: FAIL — `AttributeError: module has no attribute 'bump_proposal_id'`.

- [ ] **Step 3: Implement `bump_proposal_id` and `MANAGER_TRANSFORM`**

In `lib/pulse/scripts/apply_rederive.py`, add near `SOURCE_KINDS`:

```python
SOURCE_KINDS = ("plan-sync", "generated-artifact", "marketplace-sync", "neutral", "dependency-bump")

MANAGER_TRANSFORM: dict[str, str] = {
    "uv": "bump-python-uv",
    "poetry": "bump-python-poetry",
    "npm": "bump-npm",
    "pnpm": "bump-pnpm",
}
```

And, near `neutral_fleet_proposal_id`:

```python
def bump_proposal_id(
    ecosystem: str, package: str, manager: str, selection: tuple[str, ...]
) -> str:
    """Deterministic, target-independent proposal id for one (finding,
    manager) group: `apply-bump-{ecosystem}-{package}-{manager}-{sha256(sorted selection)[:12]}`.
    Distinct from every neutral/plan-sync/generated-artifact/marketplace-sync
    id space. A target-version change re-derives through the SAME id
    (cascading-bump semantics, spec § 4.6) — the target is never part of
    the id, only of `transform_params` (which the digest, not the id,
    makes visible)."""
    digest = hashlib.sha256(",".join(sorted(selection)).encode()).hexdigest()[:12]
    return f"apply-bump-{ecosystem}-{package}-{manager}-{digest}"
```

- [ ] **Step 4: Run to confirm all 4 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k bump_proposal_id -v`
Expected: PASS (4/4).

- [ ] **Step 5: Write the failing tests for `_collect_dependency_bump`**

Add fakes and tests. This module's `IoSeams` doesn't carry a Nave `runner` shaped for `dependency_pipeline.materialize_dependency_evidence` (which needs `nave_adapter.NaveRunner`-shaped `.run`) directly — `_collect_dependency_bump` calls `dependency_pipeline.materialize_dependency_evidence` and `dependencies.compare`, both pure/injectable via the existing `io_seams.runner`/`io_seams.gh_api` seams plus a new `io_seams` field for the coherence policy. Read `dependency_pipeline.materialize_dependency_evidence`'s signature (`(repos, *, runner)`) and `dependency_policy.load_dependency_policy`'s signature (`(path) -> DependencyPolicy`) before writing fakes — both are real, already-existing functions this task calls, not new ones.

```python
# --- dependency-bump: collect ------------------------------------------------

from lib.pulse.scripts import dependencies as deps_module
from lib.pulse.scripts.dependencies import CoherenceGroup, DivergenceFinding, PackageRecord


def _package_record(repo, name="requests", locked_version="2.28.0", manager="uv", **overrides):
    fields = dict(
        repo=repo, ecosystem="python", name=name, resolution="single",
        manifest_range=">=2.0", locked_version=locked_version,
        unresolved_reason=None, manager=manager,
        manifest_path="pyproject.toml", lock_path="uv.lock",
        tree_sha="tree-" + repo.replace("/", "-"), provenance=(),
    )
    fields.update(overrides)
    return PackageRecord(**fields)


def _coherence_group(**overrides):
    fields = dict(
        id="core-runtime", repos=("acme/api", "acme/web"),
        packages=("python:requests",), exclude_packages=(), policy="exact",
    )
    fields.update(overrides)
    return CoherenceGroup(**fields)


class FakeDependencyBumpIoSeams:
    """Fakes the collaborators _collect_dependency_bump needs: fresh
    PackageRecords per repo (bypassing real evidence materialization),
    the coherence policy, and per-repo default_branch/HEAD sha resolution
    via gh_api — the same seam neutral already uses."""

    def __init__(self, records_by_repo, groups, branches_by_repo, heads_by_repo):
        self.records_by_repo = records_by_repo
        self.groups = groups
        self.branches_by_repo = branches_by_repo
        self.heads_by_repo = heads_by_repo
        self.gh_api_calls = []

    def gh_api(self, endpoint):
        self.gh_api_calls.append(endpoint)
        parts = endpoint.split("/")
        owner, name = parts[1], parts[2]
        repo = f"{owner}/{name}"
        if endpoint.endswith(f"repos/{owner}/{name}"):
            return {"default_branch": self.branches_by_repo[repo]}
        # .../branches/{branch}
        return {"commit": {"sha": self.heads_by_repo[repo]}}


def test_collect_dependency_bump_resolves_finding_and_target():
    io = FakeDependencyBumpIoSeams(
        records_by_repo={
            "acme/api": [_package_record("acme/api", locked_version="2.28.0")],
            "acme/web": [_package_record("acme/web", locked_version="2.31.0")],
        },
        groups=(_coherence_group(),),
        branches_by_repo={"acme/api": "main", "acme/web": "main"},
        heads_by_repo={"acme/api": "a" * 40, "acme/web": "b" * 40},
    )
    inputs = apply_rederive._collect_dependency_bump(
        {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
        actor=mutation_plan.Actor("octocat", "laptop", "interactive"),
        io_seams=io,
        _fetch_records=lambda repos, io_seams: (
            [r for repo in repos for r in io.records_by_repo.get(repo, [])],
            {},
        ),
        _load_groups=lambda io_seams: io.groups,
    )
    assert inputs.finding.package == "requests"
    assert inputs.target == "2.31.0"
    assert inputs.selection == ("acme/api",)  # only the diverging repo
    assert inputs.head_shas == {"acme/api": "a" * 40}
    assert inputs.tree_shas == {"acme/api": "tree-acme-api"}


def test_collect_dependency_bump_rejects_unknown_finding_address():
    io = FakeDependencyBumpIoSeams(
        records_by_repo={"acme/api": [_package_record("acme/api")]},
        groups=(_coherence_group(),),
        branches_by_repo={"acme/api": "main"}, heads_by_repo={"acme/api": "a" * 40},
    )
    with pytest.raises(apply_rederive.RederiveError, match="no finding"):
        apply_rederive._collect_dependency_bump(
            {"group": "core-runtime", "ecosystem": "python", "package": "does-not-exist"},
            actor=mutation_plan.Actor("octocat", "laptop", "interactive"), io_seams=io,
            _fetch_records=lambda repos, io_seams: (io.records_by_repo["acme/api"], {}),
            _load_groups=lambda io_seams: io.groups,
        )


def test_collect_dependency_bump_rejects_unresolved_distance():
    io = FakeDependencyBumpIoSeams(
        records_by_repo={
            "acme/api": [_package_record("acme/api", resolution="multiple", locked_version=None)],
            "acme/web": [_package_record("acme/web", locked_version="2.31.0")],
        },
        groups=(_coherence_group(),),
        branches_by_repo={"acme/api": "main", "acme/web": "main"},
        heads_by_repo={"acme/api": "a" * 40, "acme/web": "b" * 40},
    )
    with pytest.raises(apply_rederive.RederiveError, match="unresolved"):
        apply_rederive._collect_dependency_bump(
            {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
            actor=mutation_plan.Actor("octocat", "laptop", "interactive"), io_seams=io,
            _fetch_records=lambda repos, io_seams: (
                [r for repo in repos for r in io.records_by_repo.get(repo, [])],
                {},
            ),
            _load_groups=lambda io_seams: io.groups,
        )


def test_collect_dependency_bump_drops_non_main_group_declaration():
    io = FakeDependencyBumpIoSeams(
        records_by_repo={
            "acme/api": [_package_record("acme/api", locked_version="2.28.0")],
            "acme/web": [_package_record("acme/web", locked_version="2.31.0")],
        },
        groups=(_coherence_group(),),
        branches_by_repo={"acme/api": "main", "acme/web": "main"},
        heads_by_repo={"acme/api": "a" * 40, "acme/web": "b" * 40},
    )
    inputs = apply_rederive._collect_dependency_bump(
        {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
        actor=mutation_plan.Actor("octocat", "laptop", "interactive"), io_seams=io,
        _fetch_records=lambda repos, io_seams: (
            [r for repo in repos for r in io.records_by_repo.get(repo, [])],
            {},
        ),
        _load_groups=lambda io_seams: io.groups,
        _declarations_by_repo={"acme/api": {"python": {"requests": "dev"}}, "acme/web": {"python": {"requests": "main"}}},
    )
    assert inputs.selection == ()
    assert inputs.blocked == {"acme/api": "non-main-group-package"}


def test_collect_dependency_bump_rejects_empty_selection_when_all_at_target():
    io = FakeDependencyBumpIoSeams(
        records_by_repo={
            "acme/api": [_package_record("acme/api", locked_version="2.31.0")],
            "acme/web": [_package_record("acme/web", locked_version="2.31.0")],
        },
        groups=(_coherence_group(),),
        branches_by_repo={"acme/api": "main", "acme/web": "main"},
        heads_by_repo={"acme/api": "a" * 40, "acme/web": "b" * 40},
    )
    with pytest.raises(apply_rederive.RederiveError, match="nothing to do"):
        apply_rederive._collect_dependency_bump(
            {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
            actor=mutation_plan.Actor("octocat", "laptop", "interactive"), io_seams=io,
            _fetch_records=lambda repos, io_seams: (
                [r for repo in repos for r in io.records_by_repo.get(repo, [])],
                {},
            ),
            _load_groups=lambda io_seams: io.groups,
        )


def test_collect_dependency_bump_drops_repo_missing_evidence_tree_sha():
    io = FakeDependencyBumpIoSeams(
        records_by_repo={
            "acme/api": [_package_record("acme/api", locked_version="2.28.0", tree_sha=None)],
            "acme/web": [_package_record("acme/web", locked_version="2.31.0")],
        },
        groups=(_coherence_group(),),
        branches_by_repo={"acme/api": "main", "acme/web": "main"},
        heads_by_repo={"acme/api": "a" * 40, "acme/web": "b" * 40},
    )
    inputs = apply_rederive._collect_dependency_bump(
        {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
        actor=mutation_plan.Actor("octocat", "laptop", "interactive"), io_seams=io,
        _fetch_records=lambda repos, io_seams: (
            [r for repo in repos for r in io.records_by_repo.get(repo, [])],
            {},
        ),
        _load_groups=lambda io_seams: io.groups,
    )
    assert inputs.selection == ()
    assert inputs.blocked == {"acme/api": "evidence-tree-sha-missing"}
```

(The exact keyword names `_fetch_records` (returns `(records, declarations_by_repo)`), `_load_groups`, and `_declarations_by_repo` are seams this step's implementation must expose as injectable — see Step 7's design; if the real implementation names them differently, update these test call sites to match, keeping the SAME test intent: fresh-records injection, coherence-group injection, and declaration-group injection are each independently fakeable without a real Nave/GitHub round-trip.)

- [ ] **Step 6: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k collect_dependency_bump -v`
Expected: FAIL — `_collect_dependency_bump` doesn't exist yet.

- [ ] **Step 7: Implement `DependencyBumpProviderInputs` and `_collect_dependency_bump`**

In `lib/pulse/scripts/apply_rederive.py`, add the imports (top of file, alongside the existing `from lib.pulse.scripts import (...)` block):

```python
from lib.pulse.scripts import dependencies as deps_module
from lib.pulse.scripts import dependency_pipeline
from lib.pulse.scripts import dependency_policy
from lib.pulse.scripts import dependency_evidence
from lib.pulse.scripts.profile_dispatch import ConfigError
```

Add the dataclass next to `NeutralProviderInputs`:

```python
@dataclass(frozen=True)
class DependencyBumpProviderInputs:
    """Fresh dependency-bump evidence for ONE finding — the one structural
    difference from every other source: `_collect` runs once per finding
    (not once per proposal), and `rederive_dependency_bump` fans this ONE
    input out into N per-manager proposals.

    `finding` is the freshly re-derived DivergenceFinding (never the
    caller-supplied finding_ref, which is only an address). `target` is
    the semantically-highest locked_version among the finding's versions.
    `selection` is every diverging, main-group-declared repo (dropped:
    already-at-target repos, and non-main-group declarations — see
    `blocked`). `records_by_repo` is `(repo, ecosystem, name) ->
    PackageRecord`, used to split `selection` by manager. `head_shas` is
    the FRESH per-repo commit SHA (branches/{base_ref} at collect-time,
    same convention as neutral — never pinned to evidence). `tree_shas`
    is the per-repo F4 evidence tree SHA (the finding-validity guard).
    `default_branches` is per-repo, threaded to `resolve_intended_base`.
    `blocked` names repos dropped from selection with their reason code
    (e.g. `non-main-group-package`), carried through so the driver can
    still report a per-repo blocked outcome instead of silently omitting
    them.
    """

    finding_ref: Mapping[str, Any]
    finding: deps_module.DivergenceFinding
    target: str
    selection: tuple[str, ...]
    records_by_repo: dict[tuple[str, str, str], deps_module.PackageRecord]
    head_shas: dict[str, str]
    tree_shas: dict[str, str]
    default_branches: dict[str, str]
    blocked: dict[str, str]
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None
```

Add `_collect_dependency_bump`:

```python
def _fetch_fresh_records(
    repos: tuple[str, ...], io_seams: IoSeams
) -> tuple[list[deps_module.PackageRecord], dict[str, dict[str, dict[str, str]]]]:
    """The REAL fresh-evidence path: materialize F4 evidence for exactly
    the finding's group repos (never the whole fleet), then run the same
    typed evaluation the healthcheck fleet.dependencies.coherence check
    uses. Returns both the fleet-comparison records and a mapping from
    repo -> ecosystem -> package name -> declared group, so the bump
    collect step can enforce main-group-only without a separate evidence
    round-trip. Not called `_collect_neutral`-style with a fake —
    production callers pass no override; tests inject `_fetch_records`
    directly."""
    if io_seams.runner is None:
        raise RederiveError("apply_rederive: dependency-bump requires io_seams.runner")
    try:
        document = dependency_pipeline.materialize_dependency_evidence(
            list(repos), runner=io_seams.runner
        )
    except ConfigError as exc:
        raise RederiveError(
            f"apply_rederive: dependency-bump evidence materialization failed: {exc}"
        ) from exc
    evidence_index = dependency_evidence.load_dependency_evidence(document)
    records: list[deps_module.PackageRecord] = []
    declarations_by_repo: dict[str, dict[str, dict[str, str]]] = {}
    for repo in repos:
        evidence = evidence_index.get(repo)
        for ecosystem in ("python", "node"):
            evaluation = dependency_pipeline.evaluate_dependencies(repo, ecosystem, evidence)
            records.extend(evaluation.records)
            package_namespace = evaluation.records[0].ecosystem if evaluation.records else ecosystem
            by_ecosystem = declarations_by_repo.setdefault(repo, {})
            by_name = by_ecosystem.setdefault(package_namespace, {})
            for decl in evaluation.declarations:
                # A package may appear in more than one group; "main" wins
                # over dev/optional because any main declaration makes the
                # package safe to bump as fleet runtime surface.
                if decl.name not in by_name or decl.group == "main":
                    by_name[decl.name] = decl.group
    return records, declarations_by_repo


def _load_coherence_groups(io_seams: IoSeams) -> tuple[deps_module.CoherenceGroup, ...]:
    if io_seams.workdir is None:
        raise RederiveError("apply_rederive: dependency-bump requires io_seams.workdir (dependencies.yaml root)")
    try:
        policy = dependency_policy.load_dependency_policy(
            str(Path(io_seams.workdir) / "dependencies.yaml")
        )
    except dependency_policy.DependencyPolicyError as exc:
        raise RederiveError(f"apply_rederive: could not load dependencies.yaml: {exc}") from exc
    return policy.groups


def _collect_dependency_bump(
    finding_ref: Mapping[str, Any],
    actor: Mapping[str, Any] | mutation_plan.Actor,
    io_seams: IoSeams,
    *,
    _fetch_records=_fetch_fresh_records,
    _load_groups=_load_coherence_groups,
    _declarations_by_repo: Mapping[str, Mapping[str, Mapping[str, str]]] | None = None,
) -> DependencyBumpProviderInputs:
    """Collect-once: re-derive the finding fresh, compute its target,
    resolve selection (diverging + main-group-only), and resolve fresh
    per-repo commit/tree/default-branch evidence. `_fetch_records` returns
    `(records, declarations_by_repo)` where declarations_by_repo is
    `repo -> ecosystem -> package -> group`; `_load_groups` loads coherence
    groups; `_declarations_by_repo` is an optional test-only override for
    the main-group join."""
    group_id = finding_ref.get("group")
    ecosystem = finding_ref.get("ecosystem")
    package = finding_ref.get("package")
    if not all(isinstance(v, str) and v for v in (group_id, ecosystem, package)):
        raise RederiveError(
            f"apply_rederive: finding_ref requires non-empty group/ecosystem/package, got {finding_ref!r}"
        )

    groups = _load_groups(io_seams)
    group = next((g for g in groups if g.id == group_id), None)
    if group is None:
        raise RederiveError(f"apply_rederive: no coherence group named {group_id!r}")

    records, fetched_declarations = _fetch_records(group.repos, io_seams)
    report = deps_module.compare(records, groups)
    matches = [
        f for f in (*report.findings, *report.unresolved)
        if f.group == group_id and f.ecosystem == ecosystem and f.package == package
    ]
    if not matches:
        raise RederiveError(
            f"apply_rederive: no finding for (group={group_id!r}, ecosystem={ecosystem!r}, package={package!r})"
        )
    finding = matches[0]
    if finding.distance == "unresolved":
        raise RederiveError(
            f"apply_rederive: finding (group={group_id!r}, ecosystem={ecosystem!r}, package={package!r}) "
            "is unresolved — refusing a partial bump"
        )

    target = max(
        (v for _, v in finding.versions if v is not None),
        key=lambda raw: deps_module._parse_version(ecosystem, raw),
    )
    diverging = tuple(sorted(repo for repo, v in finding.versions if v != target))
    if not diverging:
        raise RederiveError(
            f"apply_rederive: finding (group={group_id!r}, ecosystem={ecosystem!r}, package={package!r}) "
            "has nothing to do — every repo is already at the target"
        )

    records_by_repo = {(r.repo, r.ecosystem, r.name): r for r in records}
    declarations_by_repo = _declarations_by_repo if _declarations_by_repo is not None else fetched_declarations
    selection: list[str] = []
    blocked: dict[str, str] = {}
    for repo in diverging:
        declared_group = declarations_by_repo.get(repo, {}).get(ecosystem, {}).get(package, "main")
        if declared_group != "main":
            blocked[repo] = "non-main-group-package"
            continue
        selection.append(repo)
    selection = tuple(sorted(selection))
    if not selection:
        return DependencyBumpProviderInputs(
            finding_ref=finding_ref, finding=finding, target=target, selection=(),
            records_by_repo=records_by_repo, head_shas={}, tree_shas={},
            default_branches={}, blocked=blocked, actor=actor, registry=io_seams.registry,
        )

    if io_seams.gh_api is None:
        raise RederiveError("apply_rederive: dependency-bump requires io_seams.gh_api")
    head_shas: dict[str, str] = {}
    tree_shas: dict[str, str] = {}
    default_branches: dict[str, str] = {}
    resolved_selection: list[str] = []
    for repo in selection:
        record = records_by_repo.get((repo, ecosystem, package))
        if record is None or record.tree_sha is None:
            blocked[repo] = "evidence-tree-sha-missing"
            continue
        owner, name = repo.split("/", 1)
        try:
            meta = io_seams.gh_api(f"repos/{owner}/{name}")
            default_branch = meta["default_branch"] if isinstance(meta, Mapping) else None
            if not isinstance(default_branch, str) or not default_branch:
                continue
            branch_payload = io_seams.gh_api(f"repos/{owner}/{name}/branches/{default_branch}")
            head_sha = None
            if isinstance(branch_payload, Mapping):
                commit = branch_payload.get("commit")
                if isinstance(commit, Mapping) and isinstance(commit.get("sha"), str):
                    head_sha = commit["sha"] or None
        except Exception:
            continue
        if head_sha is None:
            continue
        head_shas[repo] = head_sha
        tree_shas[repo] = record.tree_sha
        default_branches[repo] = default_branch
        resolved_selection.append(repo)

    return DependencyBumpProviderInputs(
        finding_ref=finding_ref, finding=finding, target=target,
        selection=tuple(sorted(resolved_selection)), records_by_repo=records_by_repo,
        head_shas=head_shas, tree_shas=tree_shas, default_branches=default_branches,
        blocked=blocked, actor=actor, registry=io_seams.registry,
    )
```

- [ ] **Step 8: Run to confirm all 6 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k collect_dependency_bump -v`
Expected: PASS (6/6). If a test's exact seam-keyword name (`_fetch_records` returning `(records, declarations_by_repo)`, `_load_groups`, or `_declarations_by_repo`) doesn't line up with the implementation above, fix the test call site to match — the implementation's seam names are authoritative since they're what production code (Step 7) also uses.

- [ ] **Step 9: Write the failing tests for `rederive_dependency_bump`**

Add:

```python
# --- dependency-bump: rederive (collect-once, rederive-many) ----------------


def _bump_inputs(**overrides):
    fields = dict(
        finding_ref={"group": "core-runtime", "ecosystem": "python", "package": "requests"},
        finding=DivergenceFinding(
            group="core-runtime", ecosystem="python", package="requests",
            versions=(("acme/api", "2.28.0"), ("acme/web", "2.31.0")), distance="minor",
        ),
        target="2.31.0",
        selection=("acme/api",),
        records_by_repo={
            ("acme/api", "python", "requests"): _package_record("acme/api", manager="uv"),
        },
        head_shas={"acme/api": "a" * 40},
        tree_shas={"acme/api": "tree-acme-api"},
        default_branches={"acme/api": "main"},
        blocked={},
        actor=mutation_plan.Actor("octocat", "laptop", "interactive"),
        registry=None,
    )
    fields.update(overrides)
    return apply_rederive.DependencyBumpProviderInputs(**fields)


def test_rederive_dependency_bump_builds_one_proposal_per_manager():
    inputs = _bump_inputs(
        selection=("acme/api", "acme/other"),
        records_by_repo={
            ("acme/api", "python", "requests"): _package_record("acme/api", manager="uv"),
            ("acme/other", "python", "requests"): _package_record("acme/other", manager="poetry"),
        },
        head_shas={"acme/api": "a" * 40, "acme/other": "c" * 40},
        tree_shas={"acme/api": "tree-acme-api", "acme/other": "tree-acme-other"},
        default_branches={"acme/api": "main", "acme/other": "main"},
    )
    rederived = apply_rederive.rederive_dependency_bump(inputs)
    assert len(rederived) == 2
    by_transform = {rp.proposal.transformation: rp for rp in rederived}
    assert by_transform["bump-python-uv"].proposal.selection == ("acme/api",)
    assert by_transform["bump-python-poetry"].proposal.selection == ("acme/other",)
    for rp in rederived:
        assert rp.proposal.transform_params == {"package": "requests", "version": "2.31.0"}
        assert rp.proposal.mutation_policy == "allow-listed"
        assert rp.source_kind == "dependency-bump"


def test_rederive_dependency_bump_proposal_expected_shas_and_tree_shas():
    inputs = _bump_inputs()
    [rp] = apply_rederive.rederive_dependency_bump(inputs)
    assert rp.proposal.expected_shas == {"acme/api": "a" * 40}
    assert rp.proposal.expected_tree_shas == {"acme/api": "tree-acme-api"}


def test_rederive_dependency_bump_finalizer_record_carries_default_branches():
    inputs = _bump_inputs()
    [rp] = apply_rederive.rederive_dependency_bump(inputs)
    assert rp.finalizer_record == {"base_refs": {"acme/api": "main"}}


def test_rederive_dependency_bump_bound_paths_from_package_record():
    inputs = _bump_inputs()
    [rp] = apply_rederive.rederive_dependency_bump(inputs)
    assert rp.proposal.bound_paths == {"acme/api": ("pyproject.toml", "uv.lock")}


def test_rederive_dependency_bump_unmapped_manager_is_skipped_not_raised():
    inputs = _bump_inputs(
        records_by_repo={
            ("acme/api", "python", "requests"): _package_record("acme/api", manager="pdm"),
        },
    )
    rederived = apply_rederive.rederive_dependency_bump(inputs)
    assert rederived == []  # unmapped manager -> no proposal, never a crash


def test_rederive_dependency_bump_empty_selection_returns_empty_list():
    inputs = _bump_inputs(selection=(), head_shas={}, tree_shas={}, default_branches={})
    assert apply_rederive.rederive_dependency_bump(inputs) == []


def test_rederive_dependency_bump_unmapped_manager_does_not_block_mapped_manager():
    """One (finding, manager) group with no transform entry must not
    prevent another (finding, manager) group in the SAME finding from
    producing its proposal — 'a manager has no transform entry -> per-
    manager blocked; other managers proceed' (spec error table)."""
    inputs = _bump_inputs(
        selection=("acme/api", "acme/other"),
        records_by_repo={
            ("acme/api", "python", "requests"): _package_record("acme/api", manager="uv"),
            ("acme/other", "python", "requests"): _package_record("acme/other", manager="pdm"),
        },
        head_shas={"acme/api": "a" * 40, "acme/other": "c" * 40},
        tree_shas={"acme/api": "tree-acme-api", "acme/other": "tree-acme-other"},
        default_branches={"acme/api": "main", "acme/other": "main"},
    )
    rederived = apply_rederive.rederive_dependency_bump(inputs)
    assert len(rederived) == 1
    assert rederived[0].proposal.transformation == "bump-python-uv"
    assert rederived[0].proposal.selection == ("acme/api",)


def test_rederive_dependency_bump_wraps_invalid_transform_params_as_rederive_error():
    """A version string mutation_plan._validate_param_value would reject
    (here a PEP 440 epoch, unsupported in v1 per spec § 4.3/§ 7) must
    surface as RederiveError, not a raw mutation_plan.MutationPlanError —
    'transform_params key/value fails validation -> RederiveError
    (fail-closed)' (spec error table). Requires a real registry: build_proposal
    only runs _validate_param_value's param-aware regex check when a
    registry is supplied (registry=None skips straight to a generic
    non-empty-string check) — production's run_apply_dependency_bump
    always loads one before calling rederive_dependency_bump, precisely
    so this rejection happens at rederive time, not deep inside exec_phase."""
    registry = mutation_plan.load_registry({"transformations": {"bump-python-uv": {
        "id": "bump-python-uv", "command_argv": ["uv", "add", "{package}=={version}"],
        "applies_to": ["always"], "validation": {"kind": "none"}, "allow_scheduled": False,
        "params": ["package", "version"],
    }}})
    inputs = _bump_inputs(target="1!2.3.4", registry=registry)
    with pytest.raises(apply_rederive.RederiveError, match="dependency-bump build failed"):
        apply_rederive.rederive_dependency_bump(inputs)
```

- [ ] **Step 10: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k rederive_dependency_bump -v`
Expected: FAIL — `rederive_dependency_bump` doesn't exist yet.

- [ ] **Step 11: Implement `rederive_dependency_bump`**

```python
def rederive_dependency_bump(
    inputs: DependencyBumpProviderInputs,
) -> list[RederivedProposal]:
    """Rederive-many: split `inputs.selection` by manager, build one
    `Proposal` per (finding, manager) group. A repo whose manager has no
    entry in MANAGER_TRANSFORM is silently excluded from every proposal
    (never raised — the rest of the finding still proceeds; the driver is
    responsible for reporting the excluded repo as a per-manager
    `blocked` outcome using `inputs.blocked`/the manager gap, not this
    function, which only ever returns proposals it can actually build)."""
    ecosystem = inputs.finding.ecosystem
    package = inputs.finding.package
    by_manager: dict[str, list[str]] = {}
    for repo in inputs.selection:
        record = inputs.records_by_repo.get((repo, ecosystem, package))
        if record is None:
            continue
        transformation = MANAGER_TRANSFORM.get(record.manager)
        if transformation is None:
            continue
        by_manager.setdefault(transformation, []).append(repo)

    rederived: list[RederivedProposal] = []
    for transformation, group_repos in by_manager.items():
        group_repos = tuple(sorted(group_repos))
        proposal_id = bump_proposal_id(ecosystem, package, _manager_for(transformation), group_repos)
        try:
            proposal = mutation_plan.build_proposal(
                id=proposal_id,
                selection=list(group_repos),
                transformation=transformation,
                expected_shas={repo: inputs.head_shas[repo] for repo in group_repos},
                actor=inputs.actor,
                mutation_policy="allow-listed",
                bound_paths={
                    repo: tuple(
                        p for p in (
                            inputs.records_by_repo[(repo, ecosystem, package)].manifest_path,
                            inputs.records_by_repo[(repo, ecosystem, package)].lock_path,
                        ) if p is not None
                    )
                    for repo in group_repos
                },
                transform_params={"package": package, "version": inputs.target},
                expected_tree_shas={repo: inputs.tree_shas[repo] for repo in group_repos},
                registry=inputs.registry,
            )
        except mutation_plan.MutationPlanError as exc:
            raise RederiveError(f"apply_rederive: dependency-bump build failed: {exc}") from exc
        rederived.append(
            RederivedProposal(
                binding_id=proposal_id,
                proposal=proposal,
                source_kind="dependency-bump",
                finalizer_record={
                    "base_refs": {repo: inputs.default_branches[repo] for repo in group_repos},
                },
            )
        )
    return rederived


def _manager_for(transformation: str) -> str:
    for manager, tid in MANAGER_TRANSFORM.items():
        if tid == transformation:
            return manager
    raise RederiveError(f"apply_rederive: no manager maps to transformation {transformation!r}")
```

- [ ] **Step 12: Run to confirm all 8 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k rederive_dependency_bump -v`
Expected: PASS (8/8).

- [ ] **Step 13: Write `bump_summary`**

```python
def test_bump_summary_synthesizes_recorded_summary():
    summary = apply_rederive.bump_summary(
        {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
        selection=("acme/api",), manager="uv", target="2.31.0",
    )
    assert summary["binding"] == {"group": "core-runtime", "ecosystem": "python", "package": "requests"}
    assert summary["transformation"] == "bump-python-uv"
    assert summary["proposal_id"] == apply_rederive.bump_proposal_id(
        "python", "requests", "uv", ("acme/api",)
    )
    assert summary["target"] == "2.31.0"
```

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py::test_bump_summary_synthesizes_recorded_summary -v` → FAIL.

Implement, near `neutral_summary`:

```python
def bump_summary(
    finding_ref: Mapping[str, Any], *, selection: tuple[str, ...], manager: str, target: str
) -> dict[str, Any]:
    """Synthesize the `recorded_summary` for a dependency-bump apply (no
    propose phase — mirrors `neutral_summary`). Included for human review
    even though `target` is deliberately not part of the proposal id."""
    ecosystem = finding_ref["ecosystem"]
    package = finding_ref["package"]
    transformation = MANAGER_TRANSFORM[manager]
    return {
        "binding": dict(finding_ref),
        "transformation": transformation,
        "proposal_id": bump_proposal_id(ecosystem, package, manager, selection),
        "target": target,
    }
```

Run again → PASS.

- [ ] **Step 14: Write the failing test for `collect_inputs` dispatch**

```python
def test_collect_inputs_dispatches_dependency_bump(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        apply_rederive, "_collect_dependency_bump",
        lambda finding_ref, actor, io_seams: sentinel,
    )
    result = apply_rederive.collect_inputs(
        "dependency-bump", {"group": "g", "ecosystem": "python", "package": "requests"},
        {}, actor=mutation_plan.Actor("octocat", "laptop", "interactive"),
        io_seams=apply_rederive.IoSeams(),
    )
    assert result is sentinel
```

Run to confirm failure, then wire the dispatch branch into `collect_inputs`:

```python
    if source_kind == "dependency-bump":
        return _collect_dependency_bump(binding_ref, actor, io_seams)
    if source_kind == "plan-sync":
        return _collect_plan_sync(binding_ref, actor, io_seams)
    if source_kind == "generated-artifact":
        return _collect_generated(binding_ref, actor, io_seams)
    if source_kind == "neutral":
        return _collect_neutral(binding_ref, actor, io_seams)
    return _collect_marketplace(binding_ref, actor, io_seams)
```

Note: `collect_inputs`'s existing binding-identity fail-closed check (`recorded_binding = recorded_summary.get("binding"); if recorded_binding is not None and binding_id != recorded_binding: raise RederiveError(...)`) computes `binding_id` per source_kind BEFORE this dispatch. Add a `dependency-bump` branch there too:

```python
    if source_kind == "dependency-bump":
        binding_id = binding_ref  # the finding_ref triple itself, compared as a dict
    elif source_kind == "neutral":
        ...
```

(Read the exact surrounding `if/elif` structure at the top of `collect_inputs` before editing — the existing code is `if source_kind == "neutral": ... else: binding_id = binding_ref.get(...)`; insert the `dependency-bump` case as a new leading branch so `binding_id` compares the WHOLE finding_ref dict against `recorded_summary["binding"]`, which `bump_summary` already sets to `dict(finding_ref)`.)

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py::test_collect_inputs_dispatches_dependency_bump -v` → PASS.

- [ ] **Step 15: Run the full apply_rederive test file, then the full pulse-gh suite**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -v`
Expected: every test passes, including all pre-existing plan-sync/generated-artifact/marketplace-sync/neutral tests (dependency-bump is purely additive — `rederive()`'s dispatcher, deliberately, is NOT touched, since dependency-bump never goes through it — Task 8 calls `rederive_dependency_bump` directly).

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass.

- [ ] **Step 16: Commit**

```bash
git add lib/pulse/scripts/apply_rederive.py lib/pulse/scripts/tests/test_apply_rederive.py
git commit -m "feat(apply): dependency-bump source kind (collect-once, rederive-many)"
```

---

### Task 7: pulse-gh — `resolve_intended_base`'s `dependency-bump` branch

**Files:**
- Modify: `lib/pulse/scripts/apply_reconcile.py`
- Modify: `lib/pulse/scripts/tests/test_apply_reconcile.py`

**Interfaces:**
- Consumes: Task 6's `RederivedProposal.finalizer_record = {"base_refs": {repo: default_branch, ...}}` shape for `source_kind == "dependency-bump"`.
- Produces: `resolve_intended_base("dependency-bump", binding_ref, finalizer_record)` returns `finalizer_record["base_refs"]` (a `dict[repo, str]`) instead of raising `ValueError("unknown source_kind: dependency-bump")`.

- [ ] **Step 1: Write the failing tests**

In `lib/pulse/scripts/tests/test_apply_reconcile.py`, add near the existing `resolve_intended_base` tests (read one first to match the exact style/imports used):

```python
def test_resolve_intended_base_dependency_bump_returns_per_repo_map():
    result = apply_reconcile.resolve_intended_base(
        "dependency-bump", {}, {"base_refs": {"acme/api": "main", "acme/web": "develop"}},
    )
    assert result == {"acme/api": "main", "acme/web": "develop"}


def test_resolve_intended_base_dependency_bump_raises_without_finalizer_record():
    with pytest.raises(ValueError, match="dependency-bump"):
        apply_reconcile.resolve_intended_base("dependency-bump", {}, None)


def test_resolve_intended_base_dependency_bump_raises_on_empty_base_refs():
    with pytest.raises(ValueError, match="dependency-bump"):
        apply_reconcile.resolve_intended_base("dependency-bump", {}, {"base_refs": {}})
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -k dependency_bump -v`
Expected: FAIL — `ValueError: unknown source_kind: dependency-bump` (the first test's `resolve_intended_base` call raises unconditionally today).

- [ ] **Step 3: Implement the branch**

In `lib/pulse/scripts/apply_reconcile.py`, `resolve_intended_base`, add before the final `raise ValueError(f"unknown source_kind: {source_kind}")`:

```python
    if source_kind == "dependency-bump":
        base_refs = (finalizer_record or {}).get("base_refs")
        if not isinstance(base_refs, dict) or not base_refs:
            raise ValueError(
                "cannot resolve intended base for dependency-bump: no base_refs in finalizer_record"
            )
        return dict(base_refs)

```

- [ ] **Step 4: Run to confirm all 3 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -k dependency_bump -v`
Expected: PASS (3/3).

- [ ] **Step 5: Run the full pulse-gh suite**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add lib/pulse/scripts/apply_reconcile.py lib/pulse/scripts/tests/test_apply_reconcile.py
git commit -m "feat(apply): resolve_intended_base dependency-bump branch (per-repo base_refs)"
```

---

### Task 8: pulse-gh — driver: `--finding-ref`, shared-pen sequential orchestration (`apply_driver.py`)

**Files:**
- Modify: `lib/pulse/scripts/apply_driver.py`
- Modify: `lib/pulse/scripts/tests/test_apply_driver.py`

**Interfaces:**
- Consumes: Task 6's `apply_rederive.{collect_inputs, rederive_dependency_bump, bump_summary, DependencyBumpProviderInputs}`; Task 7's `resolve_intended_base("dependency-bump", ...)`.
- Produces:
  - `run_apply(..., inputs_override: apply_rederive.ProviderInputs | None = None, rederived_override: apply_rederive.RederivedProposal | None = None, pen_name: str | None = None)` — three new optional keyword-only params, all defaulting to `None` (existing 4-source-kind behavior byte-identical when omitted).
  - `_run_multi_repo(..., pen_name: str | None = None)` — one new optional param, threaded from `run_apply`.
  - `run_apply_dependency_bump(*, finding_ref, authorization_path, ledger_path, step_id, actor_id, runner, gh_api, gh_ops, result_path, workspace) -> dict` — the new top-level orchestrator: collect-once, rederive-many, one shared pen, sequential fenced runs (one journal per proposal id).
  - CLI `main()`: `--finding-ref` (mutually exclusive with `--binding-ref`, required exactly when `--source-kind dependency-bump`).

- [ ] **Step 1: Write the failing test for `run_apply`'s `inputs_override`/`rederived_override` bypass and templated argv threading**

In `lib/pulse/scripts/tests/test_apply_driver.py`, this file already defines `RecordingRunner`, `FakeGhOps`, `FakeOps`, `proposal(...)`, `setup_run(tmp_path, monkeypatch, ...)`, and `install_happy(monkeypatch, runner)` (read them in full before writing — `setup_run` returns `(kwargs, runner, ledger, result)`; `install_happy` stubs the pen lifecycle and returns a `FakeOps` instance). Reuse them; do not redefine.

Add:

```python
def test_run_apply_rederived_override_skips_collect_and_rederive_and_threads_transform_params(
    tmp_path, monkeypatch
):
    """When both inputs_override and rederived_override are supplied,
    run_apply must NOT call apply_rederive.collect_inputs/.rederive
    (collect-once/rederive-many callers already did that work), AND the
    proposal's transform_params must reach the real exec_phase ->
    resolve_argv -> nave_adapter.pen_exec call with placeholders actually
    substituted — the load-bearing correctness property of the whole
    dependency-bump feature. exec_phase is deliberately left UN-stubbed
    here (unlike install_happy's blanket stub) so resolve_argv genuinely
    runs; only its own collaborators (executor_probe, nave_adapter.pen_exec)
    are faked."""
    monkeypatch.setattr(
        apply_driver.apply_rederive, "collect_inputs",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("collect_inputs must not be called")),
    )
    monkeypatch.setattr(
        apply_driver.apply_rederive, "rederive",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("rederive must not be called")),
    )

    registry = mutation_plan.load_registry({"transformations": {"bump-python-uv": {
        "id": "bump-python-uv", "command_argv": ["uv", "add", "{package}=={version}"],
        "applies_to": ["always"], "validation": {"kind": "none"}, "allow_scheduled": False,
        "params": ["package", "version"],
    }}})
    prop = mutation_plan.build_proposal(
        id="apply-bump-python-requests-uv-abc123", selection=[REPO],
        transformation="bump-python-uv", expected_shas={REPO: "base"},
        actor={"gh_login": "octocat", "machine": "host", "mode": "interactive"},
        mutation_policy="allow-listed", bound_paths={REPO: ("pyproject.toml", "uv.lock")},
        transform_params={"package": "requests", "version": "2.32.0"},
        expected_tree_shas={REPO: "tree-abc"},
        registry=registry,
    )
    inputs = SimpleNamespace(registry=registry)
    rederived = apply_rederive.RederivedProposal(
        "apply-bump-python-requests-uv-abc123", prop, "dependency-bump",
        {"base_refs": {REPO: "main"}},
    )

    kwargs, runner, _, result = setup_run(tmp_path, monkeypatch, (REPO,))
    kwargs.update(
        source_kind="dependency-bump",
        binding_ref={"group": "core-runtime", "ecosystem": "python", "package": "requests"},
        recorded_summary={
            "binding": {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
            "transformation": "bump-python-uv",
            "proposal_id": "apply-bump-python-requests-uv-abc123",
            "target": "2.32.0",
        },
        inputs_override=inputs, rederived_override=rederived,
    )
    ops = FakeOps()
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_capabilities", lambda r: {"adapter_state": "ok", "protocol_version": 1})
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_create", lambda r, q, n: SimpleNamespace(state="ok", pen={"name": n, "repos": [{"repo": REPO}]}, stderr=""))
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_status", lambda r, n: {"repos": [{"owner": "acme", "repo": "widget", "clone_path": "/clone"}]})
    reader = SimpleNamespace(read_repo_head=lambda repo: "commit", read_repo_file=lambda *a: b"", read_repo_changed_paths=lambda *a: ())
    monkeypatch.setattr(apply_driver.pen_clone_reader, "make_pen_clone_reader", lambda *a, **k: reader)
    monkeypatch.setattr(apply_driver.apply_phases, "preflight_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_phases, "validate_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_ops, "make_apply_ops", lambda *a: ops)
    # exec_phase is deliberately LEFT REAL here (unlike install_happy) —
    # only its own collaborators are faked, so resolve_argv's templating
    # genuinely executes end to end.
    monkeypatch.setattr(
        apply_driver.apply_phases.executor_probe, "probe_required_tool",
        lambda tool: {"state": "ok", "tool": tool, "ecosystem": "python"},
    )
    captured_argv = {}
    monkeypatch.setattr(
        apply_driver.apply_phases.nave_adapter, "pen_exec",
        lambda runner, name, argv, **kw: captured_argv.update(argv=argv) or {"adapter_state": "ok"},
    )

    outcome = apply_driver.run_apply(**kwargs)

    assert captured_argv["argv"] == ["uv", "add", "requests==2.32.0"]
    assert outcome["state"] == "pr_opened"
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k rederived_override -v`
Expected: FAIL — `run_apply()` doesn't accept `inputs_override`/`rederived_override`.

- [ ] **Step 3: Implement the `inputs_override`/`rederived_override`/`pen_name` parameters on `run_apply`**

In `lib/pulse/scripts/apply_driver.py`, change `run_apply`'s signature and its collect/rederive block:

```python
def run_apply(*, source_kind, binding_ref, recorded_summary=None, authorization_path, ledger_path,
              step_id, actor_id, runner, gh_api=None, gh_ops, result_path, workspace,
              inputs_override=None, rederived_override=None, pen_name=None) -> dict:
    """Run one single-repository (or, via _run_multi_repo, multi-repo)
    apply; return apply-status or repo-mutation.

    `inputs_override`/`rederived_override`: when BOTH are supplied, the
    internal `collect_inputs`+`rederive` call is skipped entirely and
    these are used directly — the collect-once/rederive-many caller
    (`run_apply_dependency_bump`) already performed that work once for
    every proposal in a finding. `pen_name`: when supplied, pen
    acquisition also skips `nave_adapter.pen_create` (which is NOT
    idempotent — a second call with a colliding name silently creates
    `{name}-2`, defeating a shared pen) and builds the `pen` dict directly
    from `proposal.selection`, reusing the caller's already-created pen.
    Both parameters default to `None`; every existing caller (all four
    original source kinds) is unaffected."""
    proposal = None
    proposal_digest = None
    authorization_digest = None
    actor = _actor(actor_id)

    try:
        if inputs_override is not None and rederived_override is not None:
            inputs = inputs_override
            rederived = rederived_override
        else:
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
            rederived = apply_rederive.rederive(inputs)
        proposal = rederived.proposal
        proposal_digest = mutation_plan.proposal_digest(proposal)
        auth = apply_authorization.load_authorization(authorization_path, proposal.transformation)
        authorization_digest = apply_authorization.authorization_digest(auth)
        apply_authorization.authorize(rederived, auth, recorded_summary)
        if not proposal.selection:
            raise apply_rederive.RederiveError("apply proposal selection is empty")
        selection = proposal.selection
        entry = _entry(inputs, workspace, proposal.transformation)
        resolved_base = apply_reconcile.resolve_intended_base(
            rederived.source_kind, binding_ref, rederived.finalizer_record
        )
        if isinstance(resolved_base, str):
            base_refs = {repo: resolved_base for repo in selection}
        else:
            base_refs = resolved_base
        if rederived.finalizer_record:
            _persist_finalizer(result_path, rederived.finalizer_record)
    except (apply_rederive.RederiveError, apply_authorization.AuthorizationError,
            mutation_plan.MutationPlanError, ValueError) as exc:
        return _write_failure(
            result_path, state="blocked", reason=exc, actor=actor, workspace=workspace,
            proposal=proposal, recorded_summary=recorded_summary,
            proposal_digest=proposal_digest, authorization_digest=authorization_digest,
        )
```

(Everything from `resolve_run.snapshot_audit(...)` onward is UNCHANGED except the two pen-acquisition and dispatch call sites below.)

Change the `pen_name` local-variable line (originally `pen_name = f"pulse-apply-{proposal.id}"`) to:

```python
    effective_pen_name = pen_name or f"pulse-apply-{proposal.id}"
```

and every subsequent reference to the local `pen_name` in this function's single-repo body (the `nave_adapter.pen_create(...)`/`pen_status(runner, pen_name)`/`apply_ops.make_apply_ops(runner, pen_name, ...)` calls, and the `resume_transform` branch's `pen = {"name": pen_name, ...}`) to `effective_pen_name`.

Change the pen-acquisition block (originally `if resume_transform: pen = {...} else: journal.begin(...); handle = pen_create(...); ...`) to a three-way branch:

```python
            if resume_transform:
                pen = {"name": effective_pen_name, "repos": [{"repo": repo}]}
            elif pen_name is not None:
                pen = {"name": effective_pen_name, "repos": [{"repo": r} for r in proposal.selection]}
            else:
                journal.begin(repo, "pen_ready", token)
                handle = nave_adapter.pen_create(
                    runner, nave_adapter.PenQuery(terms=["repo:" + "|".join(proposal.selection)]), effective_pen_name
                )
                if handle.state != "ok":
                    return failure("failed", handle.stderr or "pen create failed")
                pen = handle.pen
```

**Critical:** `exec_phase` (Task 4) now accepts a `transform_params` argument that must be threaded through, or a dependency-bump proposal's `{package}`/`{version}` placeholders are never substituted (silently running the literal string `"{package}=={version}"`). This module already computes `entry.command_argv`-independent argv resolution via two call sites further down in this same single-repo body: the `resume_transform` branch's `outcomes = apply_phases.exec_phase(runner, pen, entry)`, and the `phases` tuple's `("transformed", lambda: apply_phases.exec_phase(runner, pen, entry))`. Change **both** to pass `proposal.transform_params`:

```python
            if resume_transform:
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                outcomes = apply_phases.exec_phase(runner, pen, entry, proposal.transform_params)
                ...
            phases = (("validated", lambda: apply_phases.validate_phase(entry, reader, proposal)),) if resume_transform else (
                ("transformed", lambda: apply_phases.exec_phase(runner, pen, entry, proposal.transform_params)),
                ("validated", lambda: apply_phases.validate_phase(entry, reader, proposal)),
            )
```

(Passing `proposal.transform_params` unconditionally is safe for every existing source kind too: it defaults to `{}` for all four, and `resolve_argv(entry, {})` — an empty-but-not-`None` dict — produces byte-identical output to `resolve_argv(entry, None)` for any entry with no declared `params`, which is every pre-existing transformation. Verified by Task 3's `test_resolve_argv_none_params_returns_verbatim_argv_backward_compat`-adjacent reasoning: an empty-dict substitution pass over argv containing no `{...}` placeholders is a no-op.)

Change the multi-repo dispatch call site to thread `pen_name` through:

```python
    if len(selection) > 1:
        return _run_multi_repo(
            ledger_path=ledger_path, step_id=step_id, actor_id=actor_id, token=token,
            runner=runner, gh_ops=gh_ops, result_path=result_path, workspace=workspace,
            proposal=proposal, selection=list(selection), base_refs=base_refs, entry=entry,
            recorded_summary=recorded_summary, proposal_digest=proposal_digest,
            authorization_digest=authorization_digest, actor=actor, nave_version=nave_version,
            pen_name=pen_name,
        )
```

- [ ] **Step 4: Thread `pen_name` through `_run_multi_repo`**

Change `_run_multi_repo`'s signature to accept `pen_name=None`, rename its internal computed name to `effective_pen_name = pen_name or f"pulse-apply-{proposal.id}"`, update every reference (`apply_ops.make_apply_ops(runner, pen_name, ...)` → `effective_pen_name`, `nave_adapter.pen_status(runner, pen_name)` → `effective_pen_name`), and wrap the pen-acquisition block:

```python
def _run_multi_repo(
    *,
    ledger_path, step_id, actor_id, token, runner, gh_ops, result_path, workspace,
    proposal, selection, base_refs, entry, recorded_summary, proposal_digest,
    authorization_digest, actor, nave_version, pen_name=None,
) -> dict:
    """Drive one proposal across N repos with per-repo independent outcomes."""
    apply_branch = f"pulse/apply/{proposal.id}"
    effective_pen_name = pen_name or f"pulse-apply-{proposal.id}"
    journal = Journal(Path(f"{result_path}.journal"))
    actor_doc = {"gh_login": actor.gh_login, "machine": actor.machine, "mode": actor.mode}
    # ... _repo_doc / _subset_proposal / _subset_pen / _write_fleet / _finish unchanged ...

    try:
        with ApplyLock(f"{ledger_path}.apply.lock"):
            resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
            if pen_name is not None:
                pen = {
                    "name": effective_pen_name,
                    "repos": [{"repo": r} for r in proposal.selection],
                }
            else:
                handle = nave_adapter.pen_create(
                    runner, nave_adapter.PenQuery(terms=["repo:" + "|".join(proposal.selection)]), effective_pen_name
                )
                if handle.state != "ok":
                    return _write_failure(
                        result_path, state="failed", reason=handle.stderr or "pen create failed",
                        actor=actor, workspace=workspace, proposal=proposal,
                        recorded_summary=recorded_summary, proposal_digest=proposal_digest,
                        authorization_digest=authorization_digest, nave_version=nave_version,
                    )
                pen = handle.pen
            status = nave_adapter.pen_status(runner, effective_pen_name)
            clone_paths = {
                f"{item['owner']}/{item['repo']}": item["clone_path"]
                for item in status.get("repos", [])
                if isinstance(item, dict) and item.get("owner") and item.get("repo") and item.get("clone_path")
            }
            # ... rest of the function body unchanged, except every remaining
            # bare `pen_name` reference (there is one more: `ops =
            # apply_ops.make_apply_ops(runner, pen_name, ...)`) becomes
            # `effective_pen_name`.
```

**Same `transform_params` threading applies here.** `_run_multi_repo`'s own exec-phase line — `executed = apply_phases.exec_phase(runner, sub_pen, entry)` — must become:

```python
            executed = apply_phases.exec_phase(runner, sub_pen, entry, proposal.transform_params)
```

- [ ] **Step 5: Run Step 1's test to confirm it passes**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k rederived_override -v`
Expected: PASS.

- [ ] **Step 6: Run the full driver test file to confirm zero regressions**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -v`
Expected: every pre-existing test passes unchanged — `inputs_override`/`rederived_override`/`pen_name` all default to values reproducing the exact prior code path.

- [ ] **Step 7: Write the failing tests for `run_apply_dependency_bump`**

```python
# --- run_apply_dependency_bump: collect-once, rederive-many, shared pen -----


class SharedPenRunner:
    """Records every `nave` CLI call; asserts `pen create` fires exactly
    once across the whole multi-proposal run."""

    def __init__(self, responses):
        self.calls = []
        self._responses = list(responses)

    def run(self, args):
        self.calls.append(list(args))
        return self._responses.pop(0)

    def pen_create_call_count(self):
        return sum(1 for c in self.calls if c[:2] == ["pen", "create"])


def test_run_apply_dependency_bump_creates_exactly_one_shared_pen(monkeypatch, tmp_path):
    """Two manager-group proposals for one finding must provision from a
    SINGLE nave pen create call, not one per proposal — nave's `pen
    create` silently suffixes a colliding name (`X-2`) rather than
    erroring, so calling it twice would silently create TWO pens and
    defeat the shared-pen requirement without any visible error."""
    finding_ref = {"group": "core-runtime", "ecosystem": "python", "package": "requests"}
    inputs = apply_rederive.DependencyBumpProviderInputs(
        finding_ref=finding_ref,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="core-runtime", ecosystem="python", package="requests",
            versions=(("acme/api", "2.28.0"), ("acme/other", "2.20.0")), distance="minor",
        ),
        target="2.31.0", selection=("acme/api", "acme/other"),
        records_by_repo={
            ("acme/api", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/api", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=2", locked_version="2.28.0", unresolved_reason=None,
                manager="uv", manifest_path="pyproject.toml", lock_path="uv.lock",
                tree_sha="tree-api", provenance=(),
            ),
            ("acme/other", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/other", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=2", locked_version="2.20.0", unresolved_reason=None,
                manager="poetry", manifest_path="pyproject.toml", lock_path="poetry.lock",
                tree_sha="tree-other", provenance=(),
            ),
        },
        head_shas={"acme/api": "a" * 40, "acme/other": "c" * 40},
        tree_shas={"acme/api": "tree-api", "acme/other": "tree-other"},
        default_branches={"acme/api": "main", "acme/other": "main"},
        blocked={}, actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: inputs)
    monkeypatch.setattr(
        apply_driver, "run_apply",
        lambda **kwargs: {"state": "pr_opened", "proposal_id": kwargs["rederived_override"].proposal.id},
    )
    pen_create_calls = []
    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_create",
        lambda runner, query, name: pen_create_calls.append((name, sorted(query.terms))) or SimpleNamespace(
            state="ok", pen={"name": name, "repos": []}, stderr=None,
        ),
    )
    result = apply_driver.run_apply_dependency_bump(
        finding_ref=finding_ref, authorization_path="/does/not/matter",
        ledger_path=str(tmp_path / "ledger.yaml"), step_id="step-1", actor_id="octocat@laptop",
        runner=SimpleNamespace(run=lambda args: None), gh_api=lambda ep: None,
        gh_ops=SimpleNamespace(), result_path=str(tmp_path / "result.yaml"),
        workspace=str(tmp_path),
    )
    assert len(pen_create_calls) == 1
    assert result["state"] in ("pr_opened", "applied", "partial")
    assert len(result["proposals"]) == 2


def test_run_apply_dependency_bump_rolls_up_worst_proposal_state(monkeypatch, tmp_path):
    finding_ref = {"group": "g", "ecosystem": "python", "package": "requests"}
    inputs = apply_rederive.DependencyBumpProviderInputs(
        finding_ref=finding_ref,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="g", ecosystem="python", package="requests",
            versions=(("acme/api", "1.0.0"), ("acme/other", "0.9.0")), distance="minor",
        ),
        target="1.0.0", selection=("acme/other",),
        records_by_repo={
            ("acme/other", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/other", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=0", locked_version="0.9.0", unresolved_reason=None,
                manager="uv", manifest_path="pyproject.toml", lock_path="uv.lock",
                tree_sha="tree-other", provenance=(),
            ),
        },
        head_shas={"acme/other": "c" * 40}, tree_shas={"acme/other": "tree-other"},
        default_branches={"acme/other": "main"}, blocked={},
        actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: inputs)
    monkeypatch.setattr(apply_driver, "run_apply", lambda **kwargs: {"state": "blocked"})
    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_create",
        lambda runner, query, name: SimpleNamespace(state="ok", pen={"name": name, "repos": []}, stderr=None),
    )
    result = apply_driver.run_apply_dependency_bump(
        finding_ref=finding_ref, authorization_path="/x", ledger_path=str(tmp_path / "l.yaml"),
        step_id="s", actor_id="octocat@laptop", runner=SimpleNamespace(run=lambda a: None),
        gh_api=lambda ep: None, gh_ops=SimpleNamespace(), result_path=str(tmp_path / "r.yaml"),
        workspace=str(tmp_path),
    )
    assert result["state"] == "failed"  # rollup_state: all-{failed,blocked} -> "failed"


def test_run_apply_dependency_bump_pen_create_failure_blocks_whole_run(monkeypatch, tmp_path):
    finding_ref = {"group": "g", "ecosystem": "python", "package": "requests"}
    inputs = apply_rederive.DependencyBumpProviderInputs(
        finding_ref=finding_ref,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="g", ecosystem="python", package="requests",
            versions=(("acme/api", "1.0.0"), ("acme/other", "0.9.0")), distance="minor",
        ),
        target="1.0.0", selection=("acme/other",),
        records_by_repo={
            ("acme/other", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/other", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=0", locked_version="0.9.0", unresolved_reason=None,
                manager="uv", manifest_path="pyproject.toml", lock_path="uv.lock",
                tree_sha="tree-other", provenance=(),
            ),
        },
        head_shas={"acme/other": "c" * 40}, tree_shas={"acme/other": "tree-other"},
        default_branches={"acme/other": "main"}, blocked={},
        actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: inputs)
    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_create",
        lambda runner, query, name: SimpleNamespace(state="error", pen=None, stderr="fleet cache empty"),
    )
    result = apply_driver.run_apply_dependency_bump(
        finding_ref=finding_ref, authorization_path="/x", ledger_path=str(tmp_path / "l.yaml"),
        step_id="s", actor_id="octocat@laptop", runner=SimpleNamespace(run=lambda a: None),
        gh_api=lambda ep: None, gh_ops=SimpleNamespace(), result_path=str(tmp_path / "r.yaml"),
        workspace=str(tmp_path),
    )
    assert result["state"] == "blocked"
    assert "pen create" in result["reason"] or "fleet cache empty" in result["reason"]
```

- [ ] **Step 8: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k run_apply_dependency_bump -v`
Expected: FAIL — `run_apply_dependency_bump` doesn't exist.

- [ ] **Step 9: Implement `run_apply_dependency_bump`**

Add to `lib/pulse/scripts/apply_driver.py`, after `_run_multi_repo`:

```python
def run_apply_dependency_bump(
    *, finding_ref, authorization_path, ledger_path, step_id, actor_id, runner,
    gh_api=None, gh_ops, result_path, workspace,
) -> dict:
    """Collect-once, rederive-many, one shared pen, sequential fenced runs.
    Fences and journals EACH manager-group proposal independently (its own
    step_id, its own result_path) — never one `run_apply` per finding,
    since that would collapse N proposals' independent journals into one.
    Provisions exactly ONE Nave pen up front, covering the union of every
    proposal's selection, because `nave pen create` is not idempotent: a
    second call with a colliding name silently creates `{name}-2` rather
    than erroring, which would silently defeat sharing without any visible
    failure.

    Unlike the 4 pre-existing source kinds (which pass `io_seams.registry
    =None` and defer registry loading to `_entry`, right before exec),
    dependency-bump loads its registry HERE, before rederive — spec § 5's
    error table requires `transform_params key/value fails validation ->
    RederiveError (fail-closed)`, i.e. rejected before the fence/lease/pen
    ever gets touched, not discovered deep inside `exec_phase`. Reuses
    `_entry`'s exact fallback: the workspace's configured registry if
    present, else the bundled template.
    """
    actor = _actor(actor_id)
    configured = Path(workspace) / ".hiivmind" / "github" / "transformations.yaml"
    template = Path(__file__).resolve().parents[3] / "templates" / "transformations.yaml.template"
    try:
        registry = mutation_plan.load_registry(configured if configured.exists() else template)
    except mutation_plan.MutationPlanError as exc:
        return _write_failure(
            result_path, state="blocked", reason=f"could not load transformation registry: {exc}",
            actor=actor, workspace=workspace,
        )
    io_seams = apply_rederive.IoSeams(runner=runner, gh_api=gh_api, registry=registry, workdir=workspace)
    try:
        inputs = apply_rederive.collect_inputs(
            "dependency-bump", finding_ref, {}, actor=actor, io_seams=io_seams,
        )
        rederived_list = apply_rederive.rederive_dependency_bump(inputs)
    except (apply_rederive.RederiveError, mutation_plan.MutationPlanError, ValueError) as exc:
        return _write_failure(
            result_path, state="blocked", reason=exc, actor=actor, workspace=workspace,
        )
    if not rederived_list:
        return _write_failure(
            result_path, state="blocked",
            reason="dependency-bump: no manager-mapped proposal could be built for this finding",
            actor=actor, workspace=workspace,
        )

    union_repos = sorted({repo for rp in rederived_list for repo in rp.proposal.selection})
    digest = hashlib.sha256(",".join(union_repos).encode()).hexdigest()[:12]
    shared_pen_name = f"pulse-apply-bump-{digest}"
    handle = nave_adapter.pen_create(
        runner, nave_adapter.PenQuery(terms=["repo:" + "|".join(union_repos)]), shared_pen_name
    )
    if handle.state != "ok":
        return _write_failure(
            result_path, state="blocked",
            reason=handle.stderr or "pen create failed", actor=actor, workspace=workspace,
        )

    results: dict[str, dict] = {}
    for rederived in rederived_list:
        manager = apply_rederive._manager_for(rederived.proposal.transformation)
        summary = apply_rederive.bump_summary(
            finding_ref, selection=rederived.proposal.selection, manager=manager,
            target=rederived.proposal.transform_params["version"],
        )
        results[rederived.proposal.id] = run_apply(
            source_kind="dependency-bump", binding_ref=finding_ref, recorded_summary=summary,
            authorization_path=authorization_path, ledger_path=ledger_path,
            step_id=f"{step_id}.{rederived.proposal.id}", actor_id=actor_id, runner=runner,
            gh_api=gh_api, gh_ops=gh_ops, result_path=f"{result_path}.{manager}",
            workspace=workspace, inputs_override=inputs, rederived_override=rederived,
            pen_name=shared_pen_name,
        )

    rollup = apply_reconcile.rollup_state(
        {pid: {"state": r.get("state")} for pid, r in results.items()}
    )
    return {"state": rollup, "proposals": results}
```

Add `import hashlib` to the top of `apply_driver.py` if not already imported (`bump_proposal_id`'s digest logic is already imported via `apply_rederive`, but this function's own `union_repos` digest needs it directly).

- [ ] **Step 10: Run to confirm all 3 pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k run_apply_dependency_bump -v`
Expected: PASS (3/3).

- [ ] **Step 11: Write the failing test for CLI `--finding-ref` wiring**

```python
def test_main_requires_finding_ref_for_dependency_bump_source_kind(capsys):
    with pytest.raises(SystemExit):
        apply_driver.main([
            "--source-kind", "dependency-bump", "--authorization", "/x", "--ledger", "/x",
            "--step", "s", "--actor", "octocat@laptop", "--result", "/x", "--workspace", "/x",
        ])
    assert "--finding-ref" in capsys.readouterr().err


def test_main_dispatches_to_run_apply_dependency_bump(monkeypatch, tmp_path, capsys):
    captured = {}
    monkeypatch.setattr(
        apply_driver, "run_apply_dependency_bump",
        lambda **kwargs: captured.update(kwargs) or {"state": "pr_opened", "proposals": {}},
    )
    apply_driver.main([
        "--source-kind", "dependency-bump",
        "--finding-ref", json.dumps({"group": "g", "ecosystem": "python", "package": "requests"}),
        "--authorization", "/x", "--ledger", "/x", "--step", "s", "--actor", "octocat@laptop",
        "--result", "/x", "--workspace", "/x",
    ])
    assert captured["finding_ref"] == {"group": "g", "ecosystem": "python", "package": "requests"}
    assert json.loads(capsys.readouterr().out)["state"] == "pr_opened"
```

- [ ] **Step 12: Run to confirm failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k finding_ref -v`
Expected: FAIL — `main()` has no `--finding-ref` argument yet.

- [ ] **Step 13: Wire the CLI**

In `lib/pulse/scripts/apply_driver.py`, `main()`:

```python
def main(argv=None):
    """CLI entry point: run one apply against the real Nave + gh binaries."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run one apply-mode proposal")
    parser.add_argument("--source-kind", required=True)
    parser.add_argument("--binding-ref", required=False, default=None, help="JSON object; required unless --source-kind dependency-bump")
    parser.add_argument("--finding-ref", required=False, default=None, help="JSON {group,ecosystem,package}; only for --source-kind dependency-bump")
    parser.add_argument("--recorded-summary", required=False, default=None,
                        help="JSON {binding, transformation, proposal_id}; omit for --source-kind neutral or dependency-bump")
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--actor", required=True, help="login@machine")
    parser.add_argument("--result", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--fixtures", default=None, help="optional PULSE_NAVE_FIXTURES root")
    args = parser.parse_args(argv)

    if args.source_kind == "dependency-bump":
        if not args.finding_ref:
            parser.error("--finding-ref is required when --source-kind is dependency-bump")
        if args.binding_ref:
            parser.error("--binding-ref is not used with --source-kind dependency-bump; use --finding-ref")
    else:
        if not args.binding_ref:
            parser.error("--binding-ref is required unless --source-kind is dependency-bump")
        if args.source_kind != "neutral" and not args.recorded_summary:
            parser.error("--recorded-summary is required unless --source-kind is neutral or dependency-bump")

    runner = nave_adapter.NaveRunner(fixtures=args.fixtures)
    if args.source_kind == "dependency-bump":
        result = run_apply_dependency_bump(
            finding_ref=json.loads(args.finding_ref),
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
    else:
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
    print(json.dumps(result))
```

- [ ] **Step 14: Run to confirm both tests pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k finding_ref -v`
Expected: PASS (2/2).

- [ ] **Step 15: Run the full apply_driver test file, then the full pulse-gh suite**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -v`
Expected: every test passes, including every pre-existing single-repo and multi-repo test (the new params on `run_apply`/`_run_multi_repo` all default to values that reproduce the exact prior behavior).

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass.

- [ ] **Step 16: Commit**

```bash
git add lib/pulse/scripts/apply_driver.py lib/pulse/scripts/tests/test_apply_driver.py
git commit -m "feat(apply): --finding-ref CLI + shared-pen sequential dependency-bump orchestration"
```

---

### Task 9: Integration test + live-proof runbook

**Files:**
- Create: `lib/pulse/scripts/tests/test_dependency_bump_acceptance.py`
- Modify (live proof only, not exercised by the automated suite): `~/git/hiivmind/hiivmind-workspace/apply-authorization.yaml`

**Interfaces:**
- Consumes: every interface produced by Tasks 1-8.
- Produces: an in-process, fake-seam acceptance test proving finding → N proposals → driver (collect-once, rederive-many, sequential fenced runs) → `pr_opened` end to end; a documented, executable live-proof procedure against 2 real repos.

- [ ] **Step 1: Write the integration test**

Create `lib/pulse/scripts/tests/test_dependency_bump_acceptance.py`. Model it closely on `test_apply_acceptance.py`'s existing `QueuedRunner`/`RecordingApplyOps` fakes (reuse those exact classes via `from lib.pulse.scripts.tests.test_apply_acceptance import QueuedRunner, RecordingApplyOps` if that module exposes them at module scope — confirm by reading its top-level names first; if they're not directly importable, copy their minimal shape locally rather than reaching into another test module's internals):

```python
"""Dependency-bump handoff acceptance test (F11 <- F4): one finding, two
manager groups, one shared pen, two independent fenced proposal runs."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from lib.pulse.scripts import apply_driver, apply_rederive, mutation_plan, nave_adapter


FINDING_REF = {"group": "core-runtime", "ecosystem": "python", "package": "requests"}


def _record(repo, manager, locked_version, manifest_path="pyproject.toml", lock_path=None):
    return apply_rederive.deps_module.PackageRecord(
        repo=repo, ecosystem="python", name="requests", resolution="single",
        manifest_range=">=2", locked_version=locked_version, unresolved_reason=None,
        manager=manager, manifest_path=manifest_path,
        lock_path=lock_path or {"uv": "uv.lock", "poetry": "poetry.lock"}[manager],
        tree_sha=f"tree-{repo.replace('/', '-')}", provenance=(),
    )


def _inputs():
    return apply_rederive.DependencyBumpProviderInputs(
        finding_ref=FINDING_REF,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="core-runtime", ecosystem="python", package="requests",
            versions=(("acme/uv-repo", "2.28.0"), ("acme/poetry-repo", "2.20.0"), ("acme/leader", "2.31.0")),
            distance="minor",
        ),
        target="2.31.0", selection=("acme/poetry-repo", "acme/uv-repo"),
        records_by_repo={
            ("acme/uv-repo", "python", "requests"): _record("acme/uv-repo", "uv", "2.28.0"),
            ("acme/poetry-repo", "python", "requests"): _record("acme/poetry-repo", "poetry", "2.20.0"),
        },
        head_shas={"acme/uv-repo": "a" * 40, "acme/poetry-repo": "b" * 40},
        tree_shas={"acme/uv-repo": "tree-acme-uv-repo", "acme/poetry-repo": "tree-acme-poetry-repo"},
        default_branches={"acme/uv-repo": "main", "acme/poetry-repo": "main"},
        blocked={}, actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )


def test_finding_to_two_manager_proposals_to_pr_opened(monkeypatch, tmp_path):
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: _inputs())

    pen_create_calls = []

    def fake_pen_create(runner, query, name):
        pen_create_calls.append(name)
        return SimpleNamespace(state="ok", pen={"name": name, "repos": [
            {"owner": "acme", "repo": "uv-repo", "clone_path": str(tmp_path / "uv-repo")},
            {"owner": "acme", "repo": "poetry-repo", "clone_path": str(tmp_path / "poetry-repo")},
        ]}, stderr=None)

    monkeypatch.setattr(apply_driver.nave_adapter, "pen_create", fake_pen_create)

    proposal_states = {}

    def fake_run_apply(**kwargs):
        rp = kwargs["rederived_override"]
        proposal_states[rp.proposal.id] = kwargs
        return {"state": "pr_opened", "proposal_id": rp.proposal.id}

    monkeypatch.setattr(apply_driver, "run_apply", fake_run_apply)

    result = apply_driver.run_apply_dependency_bump(
        finding_ref=FINDING_REF,
        authorization_path=str(tmp_path / "auth.yaml"),
        ledger_path=str(tmp_path / "ledger.yaml"),
        step_id="dep-bump-1",
        actor_id="octocat@laptop",
        runner=SimpleNamespace(run=lambda a: None),
        gh_api=lambda ep: None,
        gh_ops=SimpleNamespace(),
        result_path=str(tmp_path / "result.yaml"),
        workspace=str(tmp_path),
    )

    assert len(pen_create_calls) == 1, "exactly one shared pen across both manager groups"
    assert result["state"] == "pr_opened"
    assert len(result["proposals"]) == 2
    assert len(proposal_states) == 2
    for proposal_id, kwargs in proposal_states.items():
        rp = kwargs["rederived_override"]
        assert rp.proposal.transform_params == {"package": "requests", "version": "2.31.0"}
        assert kwargs["pen_name"] == pen_create_calls[0]
        assert kwargs["step_id"] == f"dep-bump-1.{proposal_id}"
        assert kwargs["result_path"].endswith((".uv", ".poetry"))
    transforms = {kwargs["rederived_override"].proposal.transformation for kwargs in proposal_states.values()}
    assert transforms == {"bump-python-uv", "bump-python-poetry"}


def test_finding_with_dev_group_declaration_blocks_that_repo_without_promoting(monkeypatch, tmp_path):
    inputs = apply_rederive._collect_dependency_bump(
        FINDING_REF, actor=mutation_plan.Actor("octocat", "laptop", "interactive"),
        io_seams=apply_rederive.IoSeams(),
        _fetch_records=lambda repos, io_seams: (
            [_record("acme/uv-repo", "uv", "2.28.0"), _record("acme/leader", "uv", "2.31.0")],
            {},
        ),
        _load_groups=lambda io_seams: (
            apply_rederive.deps_module.CoherenceGroup(
                id="core-runtime", repos=("acme/uv-repo", "acme/leader"),
                packages=("python:requests",), exclude_packages=(), policy="exact",
            ),
        ),
        _declarations_by_repo={"acme/uv-repo": {"python": {"requests": "dev"}}},
    )
    assert inputs.selection == ()
    assert inputs.blocked == {"acme/uv-repo": "non-main-group-package"}
    assert apply_rederive.rederive_dependency_bump(inputs) == []
```

- [ ] **Step 2: Run to confirm it fails for the right reason, then implement any gap it surfaces**

Run: `uv run pytest lib/pulse/scripts/tests/test_dependency_bump_acceptance.py -v`
Expected: this test exercises ONLY code already implemented in Tasks 1-8, so a failure here means either (a) a mismatch between this test's fixture-construction and an interface decided during Task 6/8 (fix the test to match the real interface), or (b) a genuine gap Task 6/8 missed (fix the implementation). Do not proceed to Step 3 until this passes for the right reason — read the failure's traceback fully before changing anything.

Expected once correct: PASS (2/2).

- [ ] **Step 3: Run the complete pulse-gh suite**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: all pass — this is the full-suite gate the spec's testing plan item 10 (integration) requires.

- [ ] **Step 4: Commit**

```bash
git add lib/pulse/scripts/tests/test_dependency_bump_acceptance.py
git commit -m "test(apply): dependency-bump end-to-end acceptance (finding -> 2 proposals -> pr_opened)"
```

- [ ] **Step 5: Live-proof runbook (spec § 6 testing plan item 11 — real 2-repo bump)**

This step is executed against the real fleet, not the automated suite — read and follow it at execution time rather than pre-authoring fixed repo names, since the correct pilot pair depends on the fleet's ACTUAL current dependency-coherence state at the time this plan runs.

1. **Identify a real live-proof pair.** Run the existing F4 fleet-coherence path (or `nave fleet list --json` plus a manual `dependency_pipeline.materialize_dependency_evidence` call) against 2-3 candidate repos sharing a `uv`-managed Python dependency with genuinely diverging locked versions, both declared in the `main` group. `hiivmind/hiivmind-corpus` and `hiivmind/agent-kernel` (already authorized for `format-python` in `apply-authorization.yaml`) are reasonable starting candidates — confirm their actual locked versions for a shared package before committing to them.
2. **Author `dependencies.yaml`** (in `hiivmind-workspace`, root-level, alongside `apply-authorization.yaml`) with one `coherence_groups` entry covering the chosen pair and the shared package glob, `policy: exact`. This file does not exist yet in production (`build_fleet_missing_policy_block` is the current no-op path) — creating it is this step's first real deliverable, and it is a **prerequisite** for `_load_coherence_groups` (Task 6 Step 7) to find anything.
3. **Authorize the bump transformations.** Add to `~/git/hiivmind/hiivmind-workspace/apply-authorization.yaml`, under `authorizations:`, one entry per transformation the live-proof will exercise (at minimum `bump-python-uv`, and `bump-python-poetry` if the pair spans managers), each with `mutation_policy: allow-listed`, `permitted_repos:` naming the chosen pair, and `bound_paths:` naming each repo's `pyproject.toml`/`uv.lock` (or `poetry.lock`), mirroring the existing `format-python` entry's shape exactly:

   ```yaml
     bump-python-uv:
       mutation_policy: allow-listed
       permitted_repos:
         - <chosen-repo-1>
         - <chosen-repo-2>
       bound_paths:
         <chosen-repo-1>:
           - pyproject.toml
           - uv.lock
         <chosen-repo-2>:
           - pyproject.toml
           - uv.lock
   ```

4. **Run** `python -m lib.pulse.scripts.apply_driver --source-kind dependency-bump --finding-ref '{"group":"<group-id>","ecosystem":"python","package":"<package>"}' --authorization <path-to-apply-authorization.yaml> --ledger <tmp>/ledger.yaml --step live-proof-1 --actor <you>@<machine> --result <tmp>/result.yaml --workspace <hiivmind-workspace-checkout-path>` against the real Nave binary (no `--fixtures`).
5. **Verify**: exactly one Nave pen was created (check `nave pen status --json` or the pen directory listing — no `-2`-suffixed sibling pen); two branches exist (`pulse/apply/apply-bump-python-<package>-uv-<hash>` and, if multi-manager, the `-poetry-<hash>` sibling); two PRs opened, each with the expected `{package}=={target}` diff in exactly its repo's manifest/lock; `result["state"] == "pr_opened"`.
6. **Merge** both PRs, then run `apply_reconcile.reconcile_apply` (or the existing `apply_reconcile.py` CLI) against each `result_path` to confirm both transition to `applied`.
7. **Clean up**: this is a REAL mutation against REAL repos — do not leave the live-proof's `dependencies.yaml`/`apply-authorization.yaml` entries in place if the chosen pair was only a proof vehicle and not a genuine ongoing coherence policy; ask the user whether to keep or revert them before finishing this step.

Do not mark this step done until the real PRs have been observed opened and merged — a green automated suite alone does not satisfy this step.

---

## Final verification (after Task 9)

- [ ] `uv run pytest lib/pulse/scripts/tests/ -q` — full pulse-gh suite green.
- [ ] `cargo test` in `~/git/discreteds/nave` — full nave workspace suite green.
- [ ] Live-proof runbook (Task 9 Step 5) executed against real repos: pen created once, two PRs opened, both merged, both reconciled to `applied`.
- [ ] Re-read `docs/superpowers/specs/2026-08-15-dependency-bump-handoff-design.md` § 5 (error handling table) and § 6 (testing plan) line by line, confirming every row has a corresponding test written in Tasks 1-9. If any row is uncovered, add the missing test before declaring this plan complete.

## Execution Handoff

The plan is saved. Execute with `superpowers:subagent-driven-development` (fresh subagent per task + two-stage review — recommended, given this plan spans two repositories and nine tasks with real cross-file dependencies) or `superpowers:executing-plans` (batch execution in this session with checkpoints).
