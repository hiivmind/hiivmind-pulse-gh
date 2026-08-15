# Multi-Repo Apply (v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the apply pipeline from one repository per run to one proposal spanning N repositories, with per-repo independent outcomes and a fleet-level rollup, plus a nave fleet-query command for selector-based bindings.

**Architecture:** The mutation spine (Proposal, authorize, journal, all six apply phases, nave pen) is already multi-repo. This plan removes the four files' scalar assumptions: `apply_rederive.py` (fleet expansion + multi-repo proposal), `apply_reconcile.py` (multi-repo apply-status + per-repo reconcile), `apply_driver.py` (per-repo iteration), `resolve_run.py` (step `repos`), plus `validate_result.py` (schema) and one new nave subcommand.

**Tech Stack:** Python 3.10+ (pulse-gh), pytest, PyYAML; Rust (nave), clap, serde.

## Global Constraints

- Deterministic transforms only — crash-resume relies on reset + re-exec producing identical output. No network-dependent or nondeterministic steps in the transform itself.
- Nave owns fleet discovery — pulse-gh never enumerates repos itself; selector resolution shells out to `nave fleet list --json`.
- Fleet proposal id: `apply-{transformation}-{owner}-{sha256(sorted_repos)[:12]}`. Single-repo bindings keep the existing `apply-{transformation}-{owner}-{name}` (backward compatible).
- Per-repo independent failure: a repo failing at provision/transform/commit/push is recorded in its own outcome; the run continues.
- Backward compatibility: a v1 single-repo apply-status file (no `repos` map) must still load and reconcile.
- No new Python runtime dependencies (use existing `yaml`, `hashlib`, `json`).
- pulse-gh tests: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k <pattern> -v` (targeted) and `uv run pytest lib/pulse/scripts/tests/ -q` (suite). nave tests: `cargo test -p nave --test fleet`.
- Commits use conventional prefixes (`feat:`, `fix:`, `test:`); never `--no-verify` on pulse-gh (no husky there); nave has a husky pre-commit hook that may need `--no-verify` if `echo-comment` is absent.

---

### Task 1: nave `fleet list --json` subcommand

**Files:**
- Create: `crates/nave/src/commands/fleet.rs`
- Modify: `crates/nave/src/commands/mod.rs` (register `pub(crate) mod fleet;`)
- Modify: `crates/nave/src/main.rs` (add `Fleet(commands::fleet::FleetArgs)` to the `Command` enum and the match arm)
- Test: `crates/nave/tests/fleet.rs`

**Interfaces:**
- Consumes: `nave_config::{NaveConfig, cache_root, load_default}`, `nave_config::cache::read_repo_meta` (`read_repo_meta(cache_root: &Path, owner: &str, repo: &str) -> Result<Option<RepoMeta>>`), `RepoMeta` (`owner`, `name`, `default_branch`, `clone_url`, `tree_sha`, `pushed_at`).
- Produces: `nave fleet list --json` → stdout is a JSON array `[{"owner": String, "name": String, "default_branch": String}]`, sorted by `(owner, name)`. Exit 0 on success; non-zero + a stderr message when the fleet cache is missing/empty.

**Behavior:** Read `~/.cache/nave/fleet/<owner>/<repo>/meta.toml` for every repo (two-level directory walk like `prune_stale_repos` in `crates/nave_scan/src/lib.rs`), collect `{owner, name, default_branch}`, sort, print as JSON. No GitHub API access.

- [ ] **Step 1: Write the failing test**

Create `crates/nave/tests/fleet.rs`:

```rust
//! End-to-end coverage for `nave fleet list --json` against a seeded fleet cache.

use std::io::Read;

fn temp_dir(tag: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "nave-fleet-{tag}-{}-{:?}",
        std::process::id(),
        std::thread::current().id()
    ));
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

fn write_config(home: &std::path::Path, cache_root: &std::path::Path) {
    let cfg_dir = home.join(".config");
    std::fs::create_dir_all(&cfg_dir).unwrap();
    let toml = format!(
        "[github]\nuse_gh_cli = false\nusername = \"acme\"\n[cache]\nroot = \"{}\"\n",
        cache_root.display()
    );
    std::fs::write(cfg_dir.join("nave.toml"), toml).unwrap();
}

fn seed_repo(cache: &std::path::Path, owner: &str, name: &str, default_branch: &str) {
    let dir = cache.join("fleet").join(owner).join(name);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(
        dir.join("meta.toml"),
        format!(
            "owner = \"{owner}\"\nname = \"{name}\"\ndefault_branch = \"{default_branch}\"\n\
             clone_url = \"https://example.invalid/{owner}/{name}.git\"\n"
        ),
    )
    .unwrap();
}

#[test]
fn fleet_list_emits_sorted_json() {
    let home = temp_dir("list");
    let cache = temp_dir("cache");
    // Seed out of order to prove sorting.
    seed_repo(&cache, "acme", "zeta", "main");
    seed_repo(&cache, "acme", "alpha", "develop");
    write_config(&home, &cache);

    let output = std::process::Command::new(env!("CARGO_BIN_EXE_nave"))
        .args(["fleet", "list", "--json"])
        .env("HOME", &home)
        .output()
        .expect("failed to execute nave");

    let _ = std::fs::remove_dir_all(&home);
    let _ = std::fs::remove_dir_all(&cache);

    assert!(
        output.status.success(),
        "fleet list failed; stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = serde_json::from_str(stdout.trim()).unwrap();
    assert_eq!(
        parsed,
        serde_json::json!([
            {"owner": "acme", "name": "alpha", "default_branch": "develop"},
            {"owner": "acme", "name": "zeta", "default_branch": "main"},
        ])
    );
}
```

Add `serde_json` as a dev-dependency of the `nave` crate if not already present (check `crates/nave/Cargo.toml`; the smoke test does not use it).

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test -p nave --test fleet`
Expected: FAIL — `error: unexpected argument 'fleet' found` (the subcommand does not exist yet).

- [ ] **Step 3: Implement the command**

Create `crates/nave/src/commands/fleet.rs`:

```rust
use anyhow::{Context, Result};
use clap::Args;
use serde::Serialize;

use nave_config::{NaveConfig, cache_root, load_default};

#[derive(Args, Debug)]
pub(crate) struct FleetArgs {
    /// Emit a JSON array of {owner, name, default_branch}, sorted.
    #[arg(long)]
    pub json: bool,
}

#[derive(Serialize)]
struct FleetRepo {
    owner: String,
    name: String,
    default_branch: String,
}

pub(crate) fn run(args: FleetArgs) -> Result<()> {
    let cfg: NaveConfig = load_default()?;
    let root = match cfg.cache.root.clone() {
        Some(r) => r,
        None => cache_root()?,
    };
    let fleet_root = root.join("fleet");
    if !fleet_root.exists() {
        anyhow::bail!(
            "no fleet cache at {} — run `nave scan` first",
            fleet_root.display()
        );
    }

    let mut repos: Vec<FleetRepo> = Vec::new();
    for owner_entry in std::fs::read_dir(&fleet_root)
        .with_context(|| format!("reading fleet cache {}", fleet_root.display()))?
    {
        let owner_entry = owner_entry?;
        if !owner_entry.file_type()?.is_dir() {
            continue;
        }
        let owner = owner_entry.file_name().to_string_lossy().into_owned();
        for repo_entry in std::fs::read_dir(owner_entry.path())? {
            let repo_entry = repo_entry?;
            if !repo_entry.file_type()?.is_dir() {
                continue;
            }
            let name = repo_entry.file_name().to_string_lossy().into_owned();
            let meta = nave_config::cache::read_repo_meta(&root, &owner, &name)?;
            if let Some(meta) = meta {
                repos.push(FleetRepo {
                    owner: meta.owner,
                    name: meta.name,
                    default_branch: meta.default_branch,
                });
            }
        }
    }
    repos.sort_by(|a, b| (a.owner.as_str(), a.name.as_str()).cmp(&(b.owner.as_str(), b.name.as_str())));
    if repos.is_empty() {
        anyhow::bail!("fleet cache is empty — run `nave scan` first");
    }

    if args.json {
        println!("{}", serde_json::to_string(&repos)?);
    } else {
        for r in &repos {
            println!("{}/{} ({})", r.owner, r.name, r.default_branch);
        }
    }
    Ok(())
}
```

`serde_json` and `serde` are already dependencies of the `nave` crate (the search command emits JSON); confirm `serde::Serialize` is available (it is, via `serde`).

- [ ] **Step 4: Register the subcommand**

In `crates/nave/src/commands/mod.rs`, add `pub(crate) mod fleet;` alongside the other `pub(crate) mod` lines. In `crates/nave/src/main.rs`, add `Fleet(commands::fleet::FleetArgs)` to the `Command` enum and the arm `Command::Fleet(args) => commands::fleet::run(args).await,` in the match. `run` is synchronous (`Result<()>`); if the match arms are `.await`-ed uniformly, wrap with `async` or call without await — match the existing pattern (most commands are `async fn run(...) -> Result<()>`). If `run` must be async to fit the match, declare `pub(crate) async fn run(args: FleetArgs) -> Result<()>`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cargo test -p nave --test fleet`
Expected: PASS (1 test).

- [ ] **Step 6: Full nave suite**

Run: `cargo test -p nave` (or `cargo test` for the workspace)
Expected: all pass (158 existing + 1 new).

- [ ] **Step 7: Commit**

```bash
git add crates/nave/src/commands/fleet.rs crates/nave/src/commands/mod.rs crates/nave/src/main.rs crates/nave/tests/fleet.rs
git commit -m "feat(fleet): add 'nave fleet list --json' fleet-cache query"
```

---

### Task 2: pulse-gh binding validation + fleet expansion (`apply_rederive.py`)

**Files:**
- Modify: `lib/pulse/scripts/apply_rederive.py`
- Test: `lib/pulse/scripts/tests/test_apply_rederive.py`

**Interfaces:**
- Consumes: `IoSeams.runner` (`(argv: list[str], cwd) -> CompletedProcess-like`, already injected), `IoSeams.gh_api` (`(endpoint) -> parsed JSON`), `mutation_plan.build_proposal`, `RederivedProposal`.
- Produces (new/changed):
  - `NeutralProviderInputs` gains `selection: tuple[str, ...]` and `head_shas: dict[str, str]` (replacing the single `head_sha: str | None`).
  - `_validate_neutral_binding(binding) -> tuple[str, tuple[str, ...]]` — returns `(transformation, selection)` after validating exactly one of `repo` or (`repos`/`repo_selector`); for a single-repo binding, `selection` is the one-element tuple.
  - `_resolve_neutral_repos(binding, runner) -> tuple[str, ...]` — returns the de-duplicated, sorted repo set (explicit `repos` ∪ selector results).
  - `_collect_neutral(binding_ref, actor, io_seams) -> NeutralProviderInputs` — fetches per-repo HEAD into `head_shas`.

**Behavior:** A binding is single-repo (`repo: "owner/name"`) or fleet (`repos: [...]` and/or `repo_selector: {term: ...}`). Explicit repos and selector results union, de-duplicate, sort. Each resolved repo's live HEAD is fetched via `gh_api(repos/{owner}/{name}/branches/{base})`. A repo whose HEAD fetch fails is dropped from `selection` and recorded as a per-repo blocked outcome (see Task 5 for where outcomes live; in collect, a dropped repo is surfaced by its absence from `head_shas`/`selection`).

- [ ] **Step 1: Write the failing tests**

Append to `lib/pulse/scripts/tests/test_apply_rederive.py`:

```python
def test_neutral_fleet_expands_explicit_repos_with_live_heads(registry):
    from lib.pulse.scripts import apply_rederive as r

    binding = {
        "repos": ["hiivmind/a", "hiivmind/b"],
        "transformation": "format-python",
        "base_ref": "main",
        "bound_paths": ["src/**"],
    }

    def gh_api(endpoint):
        # endpoint == "repos/{owner}/{name}/branches/{base}"
        parts = endpoint.split("/")
        name = parts[1]
        return {"commit": {"sha": {"a": "sha-a", "b": "sha-b"}[name]}}

    inputs = r._collect_neutral(
        binding, {"gh_login": "x", "machine": "m", "mode": "interactive"},
        r.IoSeams(runner=None, gh_api=gh_api),
    )
    assert inputs.selection == ("hiivmind/a", "hiivmind/b")
    assert inputs.head_shas == {"hiivmind/a": "sha-a", "hiivmind/b": "sha-b"}


def test_neutral_fleet_selector_unions_and_dedups(registry):
    from lib.pulse.scripts import apply_rederive as r

    binding = {
        "repos": ["hiivmind/a", "hiivmind/b"],
        "repo_selector": {"term": "pyproject:true"},
        "transformation": "format-python",
        "bound_paths": ["src/**"],
    }

    class Completed:
        def __init__(self, stdout):
            self.stdout = stdout
            self.returncode = 0

    def runner(argv, cwd):
        assert argv[:3] == ["nave", "fleet", "list"]
        return Completed(
            '[{"owner":"hiivmind","name":"b","default_branch":"main"},'
            '{"owner":"hiivmind","name":"c","default_branch":"main"}]'
        )

    def gh_api(endpoint):
        return {"commit": {"sha": "sha"}}

    inputs = r._collect_neutral(
        binding, {"gh_login": "x", "machine": "m", "mode": "interactive"},
        r.IoSeams(runner=runner, gh_api=gh_api),
    )
    # explicit [a, b] union selector [b, c] == [a, b, c], sorted
    assert inputs.selection == ("hiivmind/a", "hiivmind/b", "hiivmind/c")


def test_neutral_fleet_empty_selector_raises(registry):
    from lib.pulse.scripts import apply_rederive as r
    from lib.pulse.scripts import apply_reconcile  # noqa: F401  (imports settle)

    binding = {
        "repo_selector": {"term": "nope:true"},
        "transformation": "format-python",
        "bound_paths": ["src/**"],
    }

    class Completed:
        stdout = "[]"
        returncode = 0

    def runner(argv, cwd):
        return Completed()

    with pytest.raises(r.RederiveError):
        r._collect_neutral(
            binding, {"gh_login": "x", "machine": "m", "mode": "interactive"},
            r.IoSeams(runner=runner, gh_api=lambda e: {"commit": {"sha": "sha"}}),
        )
```

Confirm the `registry` fixture name by checking the top of `test_apply_rederive.py`; if existing tests use a different fixture (e.g. `transformation_registry`), match it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k "fleet" -v`
Expected: FAIL — `TypeError`/`AttributeError` (no `_resolve_neutral_repos`; `NeutralProviderInputs` has no `selection`/`head_shas`).

- [ ] **Step 3: Implement fleet validation + resolution**

In `apply_rederive.py`, replace `NeutralProviderInputs` (lines 129-137) and `_validate_neutral_binding` (lines 165-182), and add `_resolve_neutral_repos`:

```python
@dataclass(frozen=True)
class NeutralProviderInputs:
    """Fresh neutral evidence: `binding` is the caller-supplied `binding_ref`
    (validated); `selection` is the resolved, sorted repo set; `head_shas` maps
    each selected repo to the live HEAD of its `base_ref` branch."""

    binding: Mapping[str, Any]
    selection: tuple[str, ...]
    head_shas: dict[str, str]
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None


def _repo_name(value: Any) -> str:
    if not isinstance(value, str) or not value or value.count("/") != 1:
        raise RederiveError(
            f"apply_rederive: repo must be 'owner/name', got {value!r}"
        )
    return value


def _validate_neutral_binding(
    binding: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    """Validate a neutral binding; return (transformation, resolved_selection).

    A binding is exactly one of single-repo (`repo`) or fleet
    (`repos` and/or `repo_selector`). Raises `RederiveError` (never
    KeyError/ValueError) on any malformed shape.
    """
    transformation = binding.get("transformation")
    if not isinstance(transformation, str) or not transformation:
        raise RederiveError(
            "apply_rederive: neutral binding requires a non-empty transformation, "
            f"got {transformation!r}"
        )
    has_repo = binding.get("repo") is not None
    has_repos = binding.get("repos") is not None
    has_selector = binding.get("repo_selector") is not None
    if has_repo and (has_repos or has_selector):
        raise RederiveError(
            "apply_rederive: neutral binding must be either single-repo (`repo`) "
            "or fleet (`repos`/`repo_selector`), not both"
        )
    if not (has_repo or has_repos or has_selector):
        raise RederiveError(
            "apply_rederive: neutral binding requires `repo` or `repos`/`repo_selector`"
        )
    if has_repo:
        return transformation, (_repo_name(binding.get("repo")),)
    repos = binding.get("repos") or []
    if not isinstance(repos, list) or any(
        not isinstance(r, str) or not r for r in repos
    ):
        raise RederiveError(
            f"apply_rederive: neutral binding `repos` must be a list of 'owner/name', got {repos!r}"
        )
    selection = tuple(_repo_name(r) for r in repos)
    if len(set(selection)) != len(selection):
        raise RederiveError("apply_rederive: neutral binding `repos` has duplicates")
    return transformation, selection


def _resolve_neutral_repos(
    binding: Mapping[str, Any], runner: Callable[..., Any] | None
) -> tuple[str, ...]:
    """Union explicit `repos` with `repo_selector` results (via `nave fleet
    list --json`), de-duplicated and sorted."""
    _, selection = _validate_neutral_binding(binding)
    selector = binding.get("repo_selector")
    if selector is not None:
        if runner is None:
            raise RederiveError(
                "apply_rederive: neutral repo_selector requires io_seams.runner"
            )
        if not isinstance(selector, Mapping) or not isinstance(
            selector.get("term"), str
        ):
            raise RederiveError(
                f"apply_rederive: repo_selector must be {{term: str}}, got {selector!r}"
            )
        proc = runner(["nave", "fleet", "list", "--json"], cwd=None)
        if getattr(proc, "returncode", 0) != 0:
            raise RederiveError(
                "apply_rederive: selector resolution failed (nave fleet list): "
                f"{getattr(proc, 'stderr', '') or getattr(proc, 'stdout', '')}"
            )
        raw = getattr(proc, "stdout", "")
        try:
            entries = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise RederiveError(
                f"apply_rederive: selector resolution returned invalid JSON: {exc}"
            ) from exc
        if not isinstance(entries, list) or any(
            not isinstance(e, Mapping) or not isinstance(e.get("owner"), str)
            or not isinstance(e.get("name"), str) for e in entries
        ):
            raise RederiveError(
                "apply_rederive: selector resolution returned a malformed fleet list"
            )
        selection = selection + tuple(
            f"{e['owner']}/{e['name']}" for e in entries
        )
    selection = tuple(sorted(set(selection)))
    if not selection:
        raise RederiveError(
            "apply_rederive: neutral binding resolved to an empty selection"
        )
    return selection
```

Add `import json` to the top of `apply_rederive.py` if not already imported.

- [ ] **Step 4: Rewrite `_collect_neutral`**

Replace `_collect_neutral` (lines 340-373) with:

```python
def _collect_neutral(
    binding_ref: Mapping[str, Any],
    actor: Mapping[str, Any] | mutation_plan.Actor,
    io_seams: IoSeams,
) -> NeutralProviderInputs:
    transformation, _ = _validate_neutral_binding(binding_ref)
    selection = _resolve_neutral_repos(binding_ref, io_seams.runner)
    base_ref = binding_ref.get("base_ref")
    if not isinstance(base_ref, str) or not base_ref:
        raise RederiveError(
            f"apply_rederive: neutral binding requires a non-empty base_ref, got {base_ref!r}"
        )
    if io_seams.gh_api is None:
        raise RederiveError("apply_rederive: neutral requires io_seams.gh_api")
    head_shas: dict[str, str] = {}
    for repo in selection:
        owner, name = repo.split("/", 1)
        try:
            payload = io_seams.gh_api(f"repos/{owner}/{name}/branches/{base_ref}")
        except Exception as exc:
            # Per-repo collect failure: drop the repo; the driver records it as
            # a blocked outcome. Never abort the whole fleet.
            continue
        head_sha = None
        if isinstance(payload, Mapping):
            commit = payload.get("commit")
            if isinstance(commit, Mapping) and isinstance(commit.get("sha"), str):
                head_sha = commit["sha"] or None
        if head_sha is not None:
            head_shas[repo] = head_sha
    if not head_shas:
        raise RederiveError(
            "apply_rederive: neutral could not resolve HEAD for any selected repo"
        )
    return NeutralProviderInputs(
        binding=binding_ref,
        selection=tuple(repo for repo in selection if repo in head_shas),
        head_shas=head_shas,
        actor=actor,
        registry=io_seams.registry,
    )
```

Note: `transformation` is returned by `_validate_neutral_binding` but re-read from `binding_ref["transformation"]` in the re-derive; keep the local for the empty-selection guard's clarity or drop it — use `_ = _validate_neutral_binding(binding_ref)` if unused to satisfy lint.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k "fleet or neutral" -v`
Expected: PASS (new fleet tests + existing neutral tests still green — the existing single-repo neutral tests use `binding={"repo": ...}` and must still pass through the single-repo branch).

- [ ] **Step 6: Commit**

```bash
git add lib/pulse/scripts/apply_rederive.py lib/pulse/scripts/tests/test_apply_rederive.py
git commit -m "feat(apply): neutral fleet expansion (explicit repos + nave selector)"
```

---

### Task 3: pulse-gh multi-repo re-derive (`apply_rederive.py`)

**Files:**
- Modify: `lib/pulse/scripts/apply_rederive.py`
- Test: `lib/pulse/scripts/tests/test_apply_rederive.py`

**Interfaces:**
- Consumes: Task 2's `NeutralProviderInputs` (`selection`, `head_shas`), `_validate_neutral_binding`, `_resolve_neutral_repos`.
- Produces:
  - `neutral_proposal_id(binding) -> str` — single-repo: `apply-{t}-{owner}-{name}`; fleet: `apply-{t}-{owner}-{sha256(sorted repos joined by ',')[:12]}`.
  - `neutral_summary(binding) -> dict` — adds `"selection": list[str]` alongside `binding`, `transformation`, `proposal_id`.
  - `_rederive_neutral(inputs) -> RederivedProposal` — builds the multi-repo proposal.

- [ ] **Step 1: Write the failing tests**

```python
def test_neutral_fleet_proposal_id_is_deterministic_over_sorted_set(registry):
    from lib.pulse.scripts import apply_rederive as r
    import hashlib

    binding = {
        "repos": ["hiivmind/b", "hiivmind/a"],
        "transformation": "format-python",
        "bound_paths": ["src/**"],
    }
    id1 = r.neutral_proposal_id(binding)
    binding2 = dict(binding, repos=["hiivmind/a", "hiivmind/b"])
    id2 = r.neutral_proposal_id(binding2)
    assert id1 == id2
    assert id1.startswith("apply-format-python-hiivmind-")
    assert len(id1.split("-")[-1]) == 12
    # single-repo id is unchanged
    single = {"repo": "hiivmind/agent-kernel", "transformation": "format-python"}
    assert r.neutral_proposal_id(single) == "apply-format-python-hiivmind-agent-kernel"


def test_neutral_fleet_rederive_builds_multi_repo_proposal(registry):
    from lib.pulse.scripts import apply_rederive as r

    binding = {
        "repos": ["hiivmind/a", "hiivmind/b"],
        "transformation": "format-python",
        "bound_paths": ["src/**"],
    }
    inputs = r.NeutralProviderInputs(
        binding=binding,
        selection=("hiivmind/a", "hiivmind/b"),
        head_shas={"hiivmind/a": "sha-a", "hiivmind/b": "sha-b"},
        actor={"gh_login": "x", "machine": "m", "mode": "interactive"},
        registry=registry,
    )
    rederived = r._rederive_neutral(inputs)
    assert rederived.proposal.selection == ("hiivmind/a", "hiivmind/b")
    assert rederived.proposal.expected_shas == {
        "hiivmind/a": "sha-a",
        "hiivmind/b": "sha-b",
    }
    assert rederived.proposal.bound_paths == {
        "hiivmind/a": ("src/**",),
        "hiivmind/b": ("src/**",),
    }
    assert rederived.source_kind == "neutral"
    assert rederived.finalizer_record is None
    assert rederived.binding_id == rederived.proposal.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -k "fleet" -v`
Expected: FAIL — fleet id is `apply-format-python-hiivmind-a` (old formula uses `name`); `_rederive_neutral` returns a single-repo selection.

- [ ] **Step 3: Implement `neutral_fleet_proposal_id` + `neutral_proposal_id` + `neutral_summary`**

Replace `neutral_proposal_id` and `neutral_summary` (lines 185-203) and add `neutral_fleet_proposal_id`:

```python
def neutral_fleet_proposal_id(transformation: str, selection: tuple[str, ...]) -> str:
    """Fleet-scoped deterministic id: `apply-{t}-{owner}-{sha256(sorted repos)[:12]}`."""
    owner = selection[0].split("/", 1)[0]
    digest = hashlib.sha256(",".join(sorted(selection)).encode()).hexdigest()[:12]
    return f"apply-{transformation}-{owner}-{digest}"


def neutral_proposal_id(binding: Mapping[str, Any]) -> str:
    """Deterministic neutral proposal id. Single source of the id.

    Single-repo (`repo`): `apply-{t}-{owner}-{name}` (stable, backward
    compatible). Explicit-repos fleet: `neutral_fleet_proposal_id` over the
    sorted set. A selector-only binding has no fixed id before resolution —
    the driver resolves it and uses `neutral_fleet_proposal_id`.
    """
    transformation = binding.get("transformation")
    if not isinstance(transformation, str) or not transformation:
        raise RederiveError(
            "apply_rederive: neutral binding requires a non-empty transformation"
        )
    if binding.get("repo") is not None:
        owner, name = _repo_name(binding["repo"]).split("/", 1)
        return f"apply-{transformation}-{owner}-{name}"
    repos = binding.get("repos")
    if isinstance(repos, list) and repos:
        selection = tuple(sorted({_repo_name(r) for r in repos}))
        return neutral_fleet_proposal_id(transformation, selection)
    raise RederiveError(
        "apply_rederive: selector-only binding has no fixed proposal id before resolution"
    )


def neutral_summary(binding: Mapping[str, Any]) -> dict[str, Any]:
    """Synthesize the `recorded_summary` for a neutral apply (no propose phase)."""
    proposal_id = neutral_proposal_id(binding)
    if binding.get("repo") is not None:
        selection = [binding["repo"]]
    else:
        selection = sorted({_repo_name(r) for r in (binding.get("repos") or [])})
    return {
        "binding": binding.get("repo") or proposal_id,
        "transformation": binding["transformation"],
        "proposal_id": proposal_id,
        "selection": selection,
    }
```

Add `import hashlib` to the top of `apply_rederive.py`.

`_repo_name` is the Task 2 helper (validates `owner/name`). For a selector-only binding,
`neutral_proposal_id`/`neutral_summary` raise — the driver (Task 5 Step 3) resolves the selector
first and synthesizes the summary from the resolved selection via `neutral_fleet_proposal_id`.

- [ ] **Step 4: Implement `_rederive_neutral`**

Replace `_rederive_neutral` (lines 518-546) with:

```python
def _rederive_neutral(inputs: NeutralProviderInputs) -> RederivedProposal:
    binding = inputs.binding
    transformation = binding.get("transformation")
    if transformation not in NEUTRAL_TRANSFORMATIONS:
        raise RederiveError(
            f"apply_rederive: transformation {transformation!r} is not a neutral transformation"
        )
    selection = inputs.selection
    if not selection or any(sha is None for sha in inputs.head_shas.values()):
        raise RederiveError("apply_rederive: neutral requires a resolved HEAD per repo")
    if len(selection) == 1 and binding.get("repo") == selection[0]:
        proposal_id = neutral_proposal_id(binding)
    else:
        proposal_id = neutral_fleet_proposal_id(transformation, selection)
    bound_paths = binding.get("bound_paths")
    try:
        proposal = mutation_plan.build_proposal(
            id=proposal_id,
            selection=list(selection),
            transformation=transformation,
            expected_shas=dict(inputs.head_shas),
            actor=inputs.actor,
            mutation_policy="allow-listed",
            bound_paths={repo: bound_paths for repo in selection},
            registry=inputs.registry,
        )
    except mutation_plan.MutationPlanError as exc:
        raise RederiveError(f"apply_rederive: neutral build failed: {exc}") from exc
    return RederivedProposal(
        binding_id=proposal_id,
        proposal=proposal,
        source_kind="neutral",
        finalizer_record=None,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_rederive.py -v`
Expected: PASS (new fleet tests + all existing neutral tests — the existing single-repo id `apply-format-python-hiivmind-agent-kernel` is preserved).

- [ ] **Step 6: Commit**

```bash
git add lib/pulse/scripts/apply_rederive.py lib/pulse/scripts/tests/test_apply_rederive.py
git commit -m "feat(apply): neutral multi-repo re-derive + deterministic fleet id"
```

---

### Task 4: pulse-gh multi-repo apply-status + per-repo base resolution (`apply_reconcile.py`, `validate_result.py`)

**Files:**
- Modify: `lib/pulse/scripts/apply_reconcile.py`
- Modify: `lib/pulse/scripts/validate_result.py`
- Test: `lib/pulse/scripts/tests/test_apply_reconcile.py`

**Interfaces:**
- Consumes: `validate_result.validate(data, "apply-status")`.
- Produces:
  - `resolve_intended_base(source_kind, binding_ref, finalizer_record=None) -> str | dict[str, str]` — neutral returns `dict[repo, base_ref]` (single-repo binding → a one-key dict).
  - `write_apply_status(path, *, proposal_id, selection, repos, state, ...) -> dict` — `repos: dict[repo, dict]` of per-repo `{branch, state, intended_base, expected_head_sha, pushed_sha, pr_url, merged_sha, observed_base, observed_head_sha, reason}`; `state` is the rollup.
  - `rollup_state(repos: dict[str, dict]) -> str` — § 6.2 precedence function.
  - `load_apply_status(path) -> dict | None` — normalizes a v1 scalar doc to a one-element `repos` map in memory.
  - `upsert_repo_status(path, *, proposal_id, selection, repo, repo_doc) -> dict` — load-modify-write one repo's entry, recompute rollup.

- [ ] **Step 1: Write the failing tests**

```python
def test_rollup_state_precedence():
    from lib.pulse.scripts.apply_reconcile import rollup_state

    def repo(state):
        return {"state": state, "branch": "b", "intended_base": "main",
                "expected_head_sha": "s", "pushed_sha": "s", "pr_url": None,
                "merged_sha": None, "observed_base": None, "observed_head_sha": None,
                "reason": None}

    assert rollup_state({"a": repo("pr_opened"), "b": repo("applied")}) == "pr_opened"
    assert rollup_state({"a": repo("applied"), "b": repo("applied")}) == "applied"
    assert rollup_state({"a": repo("rejected"), "b": repo("rejected")}) == "rejected"
    assert rollup_state({"a": repo("failed"), "b": repo("blocked")}) == "failed"
    assert rollup_state({"a": repo("applied"), "b": repo("failed")}) == "partial"


def test_write_and_load_multi_repo_status_round_trip(tmp_path):
    from lib.pulse.scripts import apply_reconcile as rc

    repos = {
        "hiivmind/a": {"branch": "pulse/apply/x", "state": "pr_opened",
                       "intended_base": "main", "expected_head_sha": "sha-a",
                       "pushed_sha": "sha-a", "pr_url": "https://x/a/1",
                       "merged_sha": None, "observed_base": None,
                       "observed_head_sha": None, "reason": None},
        "hiivmind/b": {"branch": "pulse/apply/x", "state": "applied",
                       "intended_base": "main", "expected_head_sha": "sha-b",
                       "pushed_sha": "sha-b", "pr_url": "https://x/b/1",
                       "merged_sha": "merge-b", "observed_base": "main",
                       "observed_head_sha": "sha-b", "reason": None},
    }
    path = tmp_path / "result.yaml"
    rc.write_apply_status(
        path, proposal_id="pid", selection=["hiivmind/a", "hiivmind/b"],
        repos=repos, state=rc.rollup_state(repos),
        recorded_proposal_id="pid", proposal_digest="d1",
        authorization_digest="d2", workspace="w",
        actor={"gh_login": "x", "machine": "m", "mode": "interactive"},
    )
    loaded = rc.load_apply_status(path)
    assert loaded["repos"] == repos
    assert loaded["selection"] == ["hiivmind/a", "hiivmind/b"]
    assert loaded["state"] == "pr_opened"


def test_load_normalizes_v1_single_repo(tmp_path):
    from lib.pulse.scripts import apply_reconcile as rc
    import yaml

    v1 = {
        "contract_version": 1, "kind": "apply-status", "state": "pr_opened",
        "proposal_id": "pid", "recorded_proposal_id": "pid",
        "proposal_digest": "d1", "authorization_digest": "d2",
        "selection": ["hiivmind/a"], "branch": "pulse/apply/x",
        "pushed_sha": "sha", "pr_url": "https://x/a/1", "merged_sha": None,
        "reason": None, "intended_base": "main", "expected_head_sha": "sha",
        "observed_base": None, "observed_head_sha": None,
    }
    path = tmp_path / "result.yaml"
    path.write_text(yaml.safe_dump(v1))
    loaded = rc.load_apply_status(path)
    assert loaded["selection"] == ["hiivmind/a"]
    assert loaded["repos"]["hiivmind/a"]["branch"] == "pulse/apply/x"
```

Check `test_apply_reconcile.py` for its existing fixtures (e.g. a `GhOps` fake) and match the import style.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -k "rollup or multi_repo or normalizes" -v`
Expected: FAIL — `ImportError: cannot import name 'rollup_state'`; `write_apply_status` lacks `repos`/`selection` params.

- [ ] **Step 3: Implement `rollup_state` + `resolve_intended_base` neutral branch**

In `apply_reconcile.py`, add after `load_apply_status`:

```python
def rollup_state(repos: Mapping[str, Mapping[str, Any]]) -> str:
    """Fleet rollup (§ 6.2), total over every combination, first match wins."""
    states = [r.get("state") for r in repos.values()]
    if any(s in {"pr_opened", "pushed"} for s in states):
        return "pr_opened"
    if all(s == "applied" for s in states):
        return "applied"
    if all(s == "rejected" for s in states):
        return "rejected"
    if all(s in {"failed", "blocked"} for s in states):
        return "failed"
    return "partial"
```

Change `resolve_intended_base`'s neutral branch (lines 237-241) to return a per-repo dict:

```python
    if source_kind == "neutral":
        if binding_ref.get("repo") is not None:
            repo = binding_ref["repo"]
            base = binding_ref.get("base_ref")
            if not isinstance(base, str) or not base:
                raise ValueError("cannot resolve intended base for neutral: no base_ref")
            return {repo: base}
        repos = binding_ref.get("repos") or []
        base = binding_ref.get("base_ref")
        if not isinstance(base, str) or not base:
            raise ValueError("cannot resolve intended base for neutral: no base_ref")
        if not isinstance(repos, list) or not repos:
            raise ValueError("cannot resolve intended base for neutral: no repos")
        return {repo: base for repo in repos}
```

Note: the return type widens from `str` to `str | dict[str, str]`. Existing single-repo callers (driver `base_refs = {repo: resolve_intended_base(...)}`) must be updated in Task 5 — but the current driver passes a single-repo neutral binding, so `resolve_intended_base` returns a one-key dict. Update the docstring's return annotation and the driver's use in Task 5; until then the driver may break. To keep the suite green within this task, update the driver's call site minimally (Task 5 does the full rewrite): change `base_refs = {repo: apply_reconcile.resolve_intended_base(...)}` to handle the dict return. Coordinate: this task's Step 6 commit must leave the suite green — if the driver change is substantial, do the minimal one-line fix here and the full rewrite in Task 5.

- [ ] **Step 4: Implement multi-repo `write_apply_status` + `load_apply_status` normalization + `upsert_repo_status`**

Rewrite `write_apply_status` (lines 308-364) to the multi-repo shape:

```python
def write_apply_status(
    path: str | Path,
    *,
    proposal_id: str,
    selection: list[str],
    repos: Mapping[str, Mapping[str, Any]],
    state: str,
    recorded_proposal_id: str,
    proposal_digest: str,
    authorization_digest: str,
    reason: str | None = None,
    workspace: str = "unknown",
    actor: dict | None = None,
    errors: list[str] | None = None,
) -> dict:
    if actor is None:
        actor = {"gh_login": "unknown", "machine": "unknown", "mode": "interactive"}
    doc = {
        "contract_version": 1,
        "kind": "apply-status",
        "workspace": workspace,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": actor,
        "errors": errors or [],
        "proposal_id": proposal_id,
        "recorded_proposal_id": recorded_proposal_id,
        "proposal_digest": proposal_digest,
        "authorization_digest": authorization_digest,
        "selection": list(selection),
        "repos": {repo: dict(entry) for repo, entry in repos.items()},
        "state": state,
        "reason": reason,
    }
    validation_errors = validate_result.validate(doc, "apply-status")
    if validation_errors:
        raise ValueError(
            f"Invalid apply-status document: {'; '.join(validation_errors)}"
        )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_yaml(p, doc)
    return doc
```

Add `upsert_repo_status` (used by `open_apply_pr` in Task 5 and `reconcile_apply` in Task 6):

```python
def upsert_repo_status(
    path: str | Path,
    *,
    proposal_id: str,
    selection: list[str],
    repo: str,
    repo_doc: Mapping[str, Any],
    recorded_proposal_id: str,
    proposal_digest: str,
    authorization_digest: str,
    workspace: str = "unknown",
    actor: dict | None = None,
) -> dict:
    """Load-modify-write one repo's entry; recompute the rollup."""
    existing = load_apply_status(path) or {}
    repos = dict(existing.get("repos") or {})
    repos[repo] = dict(repo_doc)
    return write_apply_status(
        path,
        proposal_id=proposal_id,
        selection=selection,
        repos=repos,
        state=rollup_state(repos),
        recorded_proposal_id=recorded_proposal_id,
        proposal_digest=proposal_digest,
        authorization_digest=authorization_digest,
        workspace=workspace,
        actor=actor,
        errors=list(existing.get("errors") or []),
    )
```

Update `load_apply_status` (lines 250-273) to normalize v1 → multi-repo after validation:

```python
    data = data  # already validated as a mapping
    if "repos" not in data and data.get("selection"):
        repo = data["selection"][0]
        data = dict(data)
        data["repos"] = {
            repo: {
                "branch": data.get("branch"),
                "state": data.get("state"),
                "intended_base": data.get("intended_base"),
                "expected_head_sha": data.get("expected_head_sha"),
                "pushed_sha": data.get("pushed_sha"),
                "pr_url": data.get("pr_url"),
                "merged_sha": data.get("merged_sha"),
                "observed_base": data.get("observed_base"),
                "observed_head_sha": data.get("observed_head_sha"),
                "reason": data.get("reason"),
            }
        }
    return data
```

(Insert this normalization between the schema validation and `return data`.)

`open_apply_pr` (lines 367-444) currently calls `write_apply_status` with the scalar signature, which
now raises `TypeError`. Replace that call with `upsert_repo_status(...)` so it load-modify-writes the
single repo's `pr_opened` entry and recomputes the rollup; its return doc becomes the multi-repo shape.
Update `test_open_apply_pr_creates_and_reuses_pr` (in `test_apply_reconcile.py`) accordingly:
`doc["pushed_sha"]` → `doc["repos"]["testorg/repo1"]["pushed_sha"]`, `doc["pr_url"]` →
`doc["repos"]["testorg/repo1"]["pr_url"]`; `doc["state"]` stays `"pr_opened"`.

- [ ] **Step 5: Extend the `apply-status` validator**

In `validate_result.py` `elif kind == "apply-status":` (lines 707-751), keep the scalar fields optional (for v1 back-compat via `_require_nullable`) and add multi-repo validation:

```python
    elif kind == "apply-status":
        state = _require_enum(data, "state", APPLY_STATUS_STATES, errors)
        _require(data, "proposal_id", str, errors)
        _require(data, "recorded_proposal_id", str, errors)
        _require(data, "proposal_digest", str, errors)
        _require(data, "authorization_digest", str, errors)
        _validate_string_list(data, "selection", errors)
        if "repos" in data:
            repos = data.get("repos")
            if not isinstance(repos, dict) or not repos:
                _err(errors, "repos must be a non-empty mapping")
            else:
                seen = set()
                for repo, entry in repos.items():
                    if not isinstance(repo, str) or "/" not in repo:
                        _err(errors, f"repos key {repo!r} must be owner/name")
                    if repo in seen:
                        _err(errors, f"duplicate repo key {repo}")
                    seen.add(repo)
                    if not isinstance(entry, dict):
                        _err(errors, f"repos[{repo}] must be a mapping")
                        continue
                    _require(entry, "branch", str, errors, ctx=f"repos[{repo}].")
                    _require_enum(entry, "state", APPLY_STATUS_STATES, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "pushed_sha", str, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "pr_url", str, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "merged_sha", str, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "reason", str, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "intended_base", str, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "expected_head_sha", str, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "observed_base", str, errors, ctx=f"repos[{repo}].")
                    _require_nullable(entry, "observed_head_sha", str, errors, ctx=f"repos[{repo}].")
                    if entry.get("state") == "applied" and entry.get("merged_sha") is None:
                        _err(errors, f"repos[{repo}].merged_sha must not be null when state is applied")
            # fleet invariants
            selection = data.get("selection") or []
            if set(repos) != set(selection):
                _err(errors, "repos keys must match selection")
        else:
            # v1 scalar shape (legacy): keep the existing scalar checks unchanged.
            _require(data, "branch", str, errors)
            _require_nullable(data, "pushed_sha", str, errors)
            # ... (retain the existing scalar block verbatim)
```

Check `_require`/`_require_enum`/`_require_nullable`/`_validate_string_list` signatures in `validate_result.py` for the `ctx=` parameter (they accept a positional `ctx` string prefix); if `ctx` is not supported, inline the prefix into the field name string instead.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -v`
Expected: PASS (new multi-repo tests + existing reconcile tests still green — existing tests that call `write_apply_status` with the old scalar signature must be updated to the new signature in this task; list them with `grep -rn "write_apply_status" lib/pulse/scripts/tests/` and update each call site to pass `selection`/`repos`/`state`).

- [ ] **Step 7: Full pulse-gh suite green**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: PASS (1522 + new tests; fix any call-site fallout from the `write_apply_status` signature change and the `resolve_intended_base` dict return).

- [ ] **Step 8: Commit**

```bash
git add lib/pulse/scripts/apply_reconcile.py lib/pulse/scripts/validate_result.py lib/pulse/scripts/tests/test_apply_reconcile.py lib/pulse/scripts/apply_driver.py
git commit -m "feat(apply): multi-repo apply-status + rollup + per-repo base resolution"
```

---

### Task 5: pulse-gh driver per-repo iteration (`apply_driver.py`, `resolve_run.py`)

**Files:**
- Modify: `lib/pulse/scripts/apply_driver.py`
- Modify: `lib/pulse/scripts/resolve_run.py` (step `repos`)
- Test: `lib/pulse/scripts/tests/test_apply_driver.py`

**Interfaces:**
- Consumes: Task 3's `_rederive_neutral` (multi-repo proposal), Task 4's `resolve_intended_base` (dict return), `write_apply_status`/`open_apply_pr`/`upsert_repo_status`.
- Produces: `run_apply(...)` returns an apply-status document with a multi-repo `repos` map and rollup `state`.

**Behavior:** Delete the `len(selection) > 1` guard. `base_refs` is now the dict from `resolve_intended_base`. Iterate repos through the phases (already per-repo); on a repo's phase failure, record that repo's outcome as `failed`/`blocked` and continue. `_finish_push`/`open_apply_pr` are per repo. The ledger step records `repos: [...]`.

- [ ] **Step 1: Write the failing test**

Delete the existing `test_multi_repo_blocks_before_pen_create` (it asserts the old blocking behavior — now wrong) and add:

```python
def test_run_apply_multi_repo_one_repo_fails_others_continue(tmp_path, monkeypatch):
    from types import SimpleNamespace

    other = "acme/other"
    kwargs, runner, _, result_path = setup_run(tmp_path, monkeypatch, (REPO, other))

    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_capabilities",
        lambda r: runner.calls.append(["pen", "capabilities"]) or {
            "adapter_state": "ok", "protocol_version": 1},
    )
    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_create",
        lambda r, q, n: runner.calls.append(["pen", "create"]) or SimpleNamespace(
            state="ok", pen={"name": n, "repos": [{"repo": REPO}, {"repo": other}]}, stderr=""),
    )
    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_status", lambda r, n: {
            "repos": [
                {"owner": "acme", "repo": "widget", "clone_path": "/clone/widget"},
                {"owner": "acme", "repo": "other", "clone_path": "/clone/other"},
            ]},
    )
    reader = SimpleNamespace(
        read_repo_head=lambda repo: "commit",
        read_repo_file=lambda *a: b"",
        read_repo_changed_paths=lambda *a: (),
    )
    monkeypatch.setattr(apply_driver.pen_clone_reader, "make_pen_clone_reader", lambda *a, **k: reader)
    monkeypatch.setattr(
        apply_driver.apply_phases, "preflight_phase",
        lambda *a: {REPO: {"state": "ok"}, other: {"state": "ok"}},
    )
    monkeypatch.setattr(
        apply_driver.apply_phases, "provision_phase",
        lambda *a: {REPO: {"state": "ok", "observed_base_sha": "base"},
                    other: {"state": "failed", "reason": "boom"}},
    )
    monkeypatch.setattr(apply_driver.apply_phases, "exec_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_phases, "validate_phase", lambda *a: {REPO: {"state": "ok"}})

    class MultiOps:
        def __init__(self):
            self.calls = []
        def commit_repos(self, message, bounds):
            self.calls.append("commit")
            return {REPO: {"state": "ok", "local_commit_sha": "commit"}}
        def push_repos(self, branch):
            self.calls.append("push")
            return {REPO: {"state": "ok", "remote_ref": branch, "remote_sha": "commit",
                           "upstream": f"origin/{branch}"}}

    monkeypatch.setattr(apply_driver.apply_ops, "make_apply_ops", lambda *a: MultiOps())

    result = apply_driver.run_apply(**kwargs)
    assert result["state"] == "pr_opened"
    assert result["repos"][other]["state"] == "blocked"
    assert "boom" in result["repos"][other]["reason"]
    assert result["repos"][REPO]["state"] == "pr_opened"
```

Note: `setup_run` monkeypatches `resolve_intended_base` to return the string `"main"`; the rewritten driver broadcasts a string base across all repos (`isinstance(resolved_base, str)` guard), so this harness remains valid. The new test asserts the observable contract (per-repo states + rollup), leaving the driver's internal `pending`-list mechanics to Step 4.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -k multi_repo -v`
Expected: FAIL — the driver raises `RederiveError("multi-repo apply is v2")`.

- [ ] **Step 3: Remove the guard + thread per-repo base refs**

In `run_apply` (lines 150-207):
- Delete lines 175-176 (`if len(proposal.selection) > 1: raise ...`).
- Replace `repo = proposal.selection[0]` (line 179) with `selection = proposal.selection`.
- Replace the `base_refs = {repo: apply_reconcile.resolve_intended_base(...)}` (lines 181-183) with:

```python
        resolved_base = apply_reconcile.resolve_intended_base(
            rederived.source_kind, binding_ref, rederived.finalizer_record
        )
        if isinstance(resolved_base, str):
            base_refs = {repo: resolved_base for repo in proposal.selection}
        else:
            base_refs = resolved_base
```

- Every subsequent `repo` scalar reference in the fenced body (lines 209-397) becomes a loop over `proposal.selection`. The phases already return per-repo dicts; the driver interprets them. For each repo that fails a phase, call `journal` per repo (already keyed) and accumulate a `repo_outcomes` dict. `_finish_push` becomes a per-repo function taking `(repo, remote_sha)`.

- [ ] **Step 4: Rewrite the fenced body as a per-repo loop**

The fenced block (lines 262-397) is restructured so each phase is driven once, its per-repo outcome dict is interpreted, and failed repos are recorded and excluded from subsequent phases. Concretely, keep the pen creation + preflight as-is (they return per-repo dicts already), then for the provision/exec/validate/commit/push sequence, track `pending = list(selection)` and `outcomes: dict[repo, dict]`; after each phase, remove repos whose outcome is not `ok` and record them. `_finish_push(repo, remote_sha)` calls `open_apply_pr` for that repo. After the loop, write the multi-repo status via `write_apply_status(..., selection=list(selection), repos=outcomes, state=rollup_state(outcomes), ...)`.

Because this is the largest change, structure it as: (a) a helper `_repo_outcome(state, **fields)`; (b) `failure()` now takes `repo_outcomes` and writes the multi-repo doc; (c) the happy path accumulates per-repo outcomes and calls `_finish_push` per repo.

- [ ] **Step 5: Ledger step `repos` (`resolve_run.py`)**

In `cmd_create` (lines 129-146), change the step dict to write `"repos": [r for r in (s.get("repos") or s.get("repo") or "").split(",") if r]` instead of the scalar `"repo"` field, keeping a `"repo": s.get("repo", "")` legacy field for backward compat if any consumer reads it. Keep the run-level `repos` (lines 163) unchanged. Add a test in `test_apply_driver.py` (or a `resolve_run` test) asserting a created step has `repos == ["hiivmind/a", "hiivmind/b"]`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_driver.py -v`
Expected: PASS (multi-repo driver test + existing driver tests green).

- [ ] **Step 7: Full pulse-gh suite green**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add lib/pulse/scripts/apply_driver.py lib/pulse/scripts/resolve_run.py lib/pulse/scripts/tests/test_apply_driver.py
git commit -m "feat(apply): per-repo driver iteration + ledger step repos"
```

---

### Task 6: pulse-gh per-repo reconcile loop (`apply_reconcile.py`)

**Files:**
- Modify: `lib/pulse/scripts/apply_reconcile.py`
- Test: `lib/pulse/scripts/tests/test_apply_reconcile.py`

**Interfaces:**
- Consumes: Task 4's `load_apply_status` (multi-repo doc), `upsert_repo_status`, `rollup_state`.
- Produces: `reconcile_apply(...)` reconciles every repo in the result's `repos` map in one pass and recomputes the rollup. It keeps its existing scalar parameters for one repo (backward compat) but the CLI (`main`) iterates the `repos` map.

- [ ] **Step 1: Write the failing test**

```python
def test_reconcile_repos_iterates_and_rolls_up(tmp_path):
    ledger_path = create_test_ledger(tmp_path, step_id="reconcile-repo1")
    result_path = tmp_path / "apply-status.yaml"
    gh_ops = FakeGhOps()

    repos = {
        "testorg/repo1": {"branch": "pulse/apply/p", "state": "pr_opened",
                          "intended_base": "main", "expected_head_sha": "sha1",
                          "pushed_sha": "sha1", "pr_url": "https://x/1",
                          "merged_sha": None, "observed_base": None,
                          "observed_head_sha": None, "reason": None},
        "testorg/repo2": {"branch": "pulse/apply/p", "state": "pr_opened",
                          "intended_base": "main", "expected_head_sha": "sha2",
                          "pushed_sha": "sha2", "pr_url": "https://x/2",
                          "merged_sha": None, "observed_base": None,
                          "observed_head_sha": None, "reason": None},
    }
    apply_reconcile.write_apply_status(
        result_path, proposal_id="prop-101",
        selection=["testorg/repo1", "testorg/repo2"], repos=repos,
        state="pr_opened", recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST, authorization_digest=AUTHORIZATION_DIGEST,
        workspace="testorg",
        actor={"gh_login": "octocat", "machine": "mba-m4", "mode": "interactive"},
    )
    # repo1 merged; repo2 still open.
    gh_ops.prs[("testorg/repo1", "pulse/apply/p")] = {
        "url": "https://x/1", "state": "MERGED", "merged": True,
        "merge_commit_sha": "merge1", "base": "main", "head_ref": "sha1",
    }
    gh_ops.prs[("testorg/repo2", "pulse/apply/p")] = {
        "url": "https://x/2", "state": "OPEN", "merged": False,
        "merge_commit_sha": None, "base": "main", "head_ref": "sha2",
    }

    doc = apply_reconcile.reconcile_repos(
        ledger_path=ledger_path, step_id="reconcile-repo1", result_path=result_path,
        gh_ops=gh_ops, recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST, authorization_digest=AUTHORIZATION_DIGEST,
        actor_id="octocat@mba-m4", workspace="testorg",
    )
    assert doc["repos"]["testorg/repo1"]["state"] == "applied"
    assert doc["repos"]["testorg/repo1"]["merged_sha"] == "merge1"
    assert doc["repos"]["testorg/repo2"]["state"] == "pr_opened"
    assert doc["state"] == "pr_opened"
```

`FakeGhOps.view_pr` already returns `observed_base`/`observed_head_sha` from the seeded PR's
`base`/`head_ref`, so repo1 (base `main` == intended, head `sha1` == expected) passes the merge gate
and reaches `applied`, while repo2 stays `pr_opened`; the rollup is `pr_opened`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -k iterates -v`
Expected: FAIL — `reconcile_apply` reads scalar `existing["pushed_sha"]` (now absent in the multi-repo doc) and does not iterate.

- [ ] **Step 3: Add a `reconcile_repos` loop**

Add a new function next to `reconcile_apply` that drives the existing single-repo merge check per repo:

```python
def reconcile_repos(
    *,
    ledger_path: str | Path,
    step_id: str,
    result_path: str | Path,
    gh_ops: GhOps,
    recorded_proposal_id: str,
    proposal_digest: str,
    authorization_digest: str,
    actor_id: str = "octocat@mba-m4",
    workspace: str = "unknown",
) -> dict:
    """Reconcile every repo in the result's `repos` map in one pass."""
    existing = load_apply_status(result_path)
    if existing is None or "repos" not in existing:
        raise ApplyStatusError(
            "reconcile_repos requires a multi-repo apply-status document"
        )
    proposal_id = existing["proposal_id"]
    selection = existing["selection"]
    for repo, entry in list(existing["repos"].items()):
        if entry.get("state") in {"applied", "rejected"}:
            continue
        updated = _reconcile_one_repo(
            ledger_path=ledger_path, step_id=step_id, result_path=result_path,
            proposal_id=proposal_id, selection=selection, repo=repo, entry=entry,
            gh_ops=gh_ops, recorded_proposal_id=recorded_proposal_id,
            proposal_digest=proposal_digest, authorization_digest=authorization_digest,
            actor_id=actor_id, workspace=workspace,
        )
        if updated:
            existing = updated
    return existing
```

Factor the merge-check body of `reconcile_apply` (lines 502-737: `view_pr` → merged/not-merged → `write_apply_status` per repo) into `_reconcile_one_repo(...)`, which uses `upsert_repo_status` to write the single repo's updated entry. `_reconcile_one_repo` returns the full updated doc (or `None` if the repo was already terminal). The existing `reconcile_apply` keeps its scalar signature for backward compatibility and delegates to `_reconcile_one_repo` for a one-element selection.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest lib/pulse/scripts/tests/test_apply_reconcile.py -v`
Expected: PASS (new test + existing reconcile tests green).

- [ ] **Step 5: Full pulse-gh suite green**

Run: `uv run pytest lib/pulse/scripts/tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/pulse/scripts/apply_reconcile.py lib/pulse/scripts/tests/test_apply_reconcile.py
git commit -m "feat(apply): per-repo reconcile loop with fleet rollup"
```

---

## Final verification (after Task 6)

- [ ] `uv run pytest lib/pulse/scripts/tests/ -q` — full pulse-gh suite green.
- [ ] `cargo test` in `~/git/discreteds/nave` — nave suite green (158 + 1 fleet test).
- [ ] Live proof (manual, after merge): seed `apply-neutral.yaml` with a 2-repo `format-python` fleet binding, run the driver against two real hiivmind repos, confirm two PRs → merge one → `partial` → merge both → `applied`. Then re-run with a `repo_selector` binding after `nave scan`.

## Execution Handoff

The plan is saved. Execute with superpowers:subagent-driven-development (fresh subagent per task + review between tasks) or superpowers:executing-plans (batch with checkpoints).
