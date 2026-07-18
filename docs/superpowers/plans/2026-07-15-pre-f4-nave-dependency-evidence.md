# Pre-F4: Nave Dependency Evidence Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded, versioned Nave CLI capability that materializes adapter-declared repository files so Pulse dependency adapters can parse authoritative manifest and lock contents without reading Nave cache internals or duplicating GitHub retrieval.

**Architecture:** Nave protocol v2 adds `materialize --request FILE --json`. It resolves requested exact paths and globs against a repository's default-branch Git tree, fetches matched blobs, and reports authoritative absence only when the tree is complete. Pulse feature-detects this capability, normalizes the response into a temporary dependency-evidence contract, validates it, and keeps raw contents out of durable workspace state.

**Tech Stack:** Rust 2024 / Rust 1.95, Clap, Reqwest, Serde, Base64, Python 3.10+, PyYAML, pytest.

## Repository roots

- `nave:` means the root of the `discreteds/nave` fork checkout. The existing `/private/tmp/nave` checkout tracks `lmmx/nave` and is upstream reference material only; do not create feature branches or PRs against it.
- `pulse:` means the root of `hiivmind/hiivmind-pulse-gh`.
- Nave and Pulse changes use separate branches and PRs. Nave changes target `discreteds/nave`, with `lmmx/nave` retained as the upstream remote for comparison and future synchronization. Merge and release the fork first; then pin the released minimum capability in Pulse.

## Global Constraints

- Pulse never reads `~/.cache/nave`, Nave checkout directories, `tracked.toml`, or any other Nave implementation path.
- Materialization is read-only. It never creates a pen, edits a checkout, or mutates a repository.
- Requests contain explicit repository names and path selectors. Nave never infers an ecosystem or repository profile.
- Default limit is `4_194_304` bytes per file. The request may lower but never raise this materialization-contract-v1 limit.
- A request is at most `1_048_576` bytes, `500` repositories, and `256` selectors per repository. A report is at most `20_000` found artifacts and `268_435_456` decoded content bytes; exceeding a report limit produces typed `too_large`/`unresolved` outcomes rather than partial unmarked success.
- Only UTF-8 text is emitted as `content`. Binary, oversized, unavailable, and malformed files are typed outcomes without content.
- `absent` is authoritative only when the recursive tree response is not truncated. No match in a truncated tree is `unresolved`.
- Raw contents pass only through Nave/Pulse process memory, Nave's JSON stdout contract, and a mode-`0700` run-specific temporary directory with mode-`0600` files for the duration of F4. The Pulse wrapper must not echo or log Nave stdout. Contents are never committed, placed in `deps-snapshot.json`, or embedded in a healthcheck result.
- Nave protocol v1 remains valid for F0 structural evidence. Only dependency materialization requires protocol v2 plus `materialize_json`.
- Private-repository parity remains capability-scoped: authentication or visibility failure is `unsupported`/`error`, never false absence.

---

### Task 1: Define Nave materialization request and result types

**Files:**
- Modify: `nave:Cargo.toml`
- Create: `nave:crates/nave_materialize/Cargo.toml`
- Create: `nave:crates/nave_materialize/src/lib.rs`
- Create: `nave:crates/nave_materialize/tests/contract.rs`

**Interfaces:**

```rust
pub const CONTRACT_VERSION: u32 = 1;
pub const MAX_FILE_BYTES: u64 = 4_194_304;

pub struct MaterializeRequest {
    pub contract_version: u32,
    pub repos: Vec<RepoRequest>,
}

pub struct RepoRequest {
    pub repo: String,                 // exact owner/name
    pub selectors: Vec<Selector>,
}

pub struct Selector {
    pub id: String,                   // stable caller-owned identity
    pub pattern: String,              // repo-root exact path or glob
    pub max_bytes: Option<u64>,       // <= MAX_FILE_BYTES
}

pub enum ArtifactState {
    Found, Absent, Unresolved, TooLarge, Binary, Unsupported, Error,
}
```

The serialized result is deterministic: repositories, selectors, and matched paths are lexically sorted. Selector patterns use Nave's existing `globset` semantics over repo-root paths. Each artifact includes `selector_id`, `path` (nullable for no match), `blob_sha`, `size_bytes`, `state`, `encoding`, `content`, and `detail`. The repo block includes `repo`, `ref_name`, `tree_sha`, `tree_complete`, and `artifacts`.

- [ ] **Step 1: Write failing contract tests** for valid exact/glob requests, duplicate selector IDs, traversal (`../x`), absolute paths, limits above `MAX_FILE_BYTES`, unknown keys, and deterministic serialization.
- [ ] **Step 2: Run `cargo test -p nave_materialize --test contract`** and verify compilation fails because the crate/types do not exist.
- [ ] **Step 3: Implement strict Serde types and `validate_request`.** Reject empty repos/selectors, duplicate repos/selector IDs, non-`owner/name` identities, path traversal, absolute paths, and raised size limits.
- [ ] **Step 4: Run `cargo test -p nave_materialize --test contract`** and verify all contract tests pass.
- [ ] **Step 5: Commit** with `feat: define Nave materialization contract`.

---

### Task 2: Materialize Git tree selections and bounded blobs

**Files:**
- Modify: `nave:Cargo.toml`
- Modify: `nave:crates/nave_github/Cargo.toml`
- Modify: `nave:crates/nave_github/src/models.rs`
- Modify: `nave:crates/nave_github/src/client.rs`
- Modify: `nave:crates/nave_materialize/Cargo.toml`
- Modify: `nave:crates/nave_materialize/src/lib.rs`
- Create: `nave:crates/nave_materialize/tests/materialize.rs`

**Interfaces:**

```rust
pub trait MaterializeSource {
    async fn repository(&self, owner: &str, repo: &str) -> Result<Repo>;
    async fn tree(&self, owner: &str, repo: &str, ref_name: &str) -> Result<TreeResponse>;
    async fn blob(&self, owner: &str, repo: &str, sha: &str) -> Result<BlobResponse>;
}

pub async fn materialize<S: MaterializeSource>(
    source: &S,
    request: MaterializeRequest,
) -> MaterializeReport;
```

`BlobResponse` models GitHub's Git Blob API (`sha`, `size`, `encoding`, `content`). Base64 is decoded only after checking the declared size; decoded bytes must also remain within the selector limit.

- [ ] **Step 1: Write fake-source tests** for exact match, glob fan-out, authoritative absence, truncated-tree unresolved, missing repository, 403/rate-limit error, oversized declared/decoded blobs, invalid Base64, non-UTF-8 bytes, and stable lexical ordering.
- [ ] **Step 2: Run `cargo test -p nave_materialize --test materialize`** and verify RED.
- [ ] **Step 3: Add `GithubClient::get_repo` and `GithubClient::get_blob`; implement the generic source and materializer.** Never fetch a blob for a non-blob tree entry or an already oversized entry.
- [ ] **Step 4: Run `cargo test -p nave_materialize` and `cargo test -p nave_github`** and verify GREEN.
- [ ] **Step 5: Commit** with `feat: materialize bounded repository evidence`.

---

### Task 3: Expose `nave materialize --request FILE --json`

**Files:**
- Modify: `nave:crates/nave/Cargo.toml`
- Modify: `nave:crates/nave/src/commands.rs`
- Create: `nave:crates/nave/src/commands/materialize.rs`
- Modify: `nave:crates/nave/src/main.rs`
- Modify: `nave:crates/nave/tests/smoke.rs`
- Modify: `nave:README.md`

**Interfaces:**

```text
nave materialize --request request.json --json
```

JSON is the only machine contract. Without `--json`, print a summary containing counts and states but never file contents. Exit `0` when a valid report is produced, including typed per-file failures; exit non-zero only when the request cannot be parsed/validated or the command cannot initialize.

- [ ] **Step 1: Add failing CLI tests** asserting the subcommand appears in help, JSON output validates, human output omits `content`, and invalid requests exit non-zero without echoing request contents.
- [ ] **Step 2: Run `cargo test -p nave --test smoke`** and verify RED.
- [ ] **Step 3: Wire the command through `detect_auth`, `GithubClient`, and `nave_materialize::materialize`.** Enforce the exact request/report limits from Global Constraints, read the request with a size-bounded file read, and never accept request JSON from a shell argument.
- [ ] **Step 4: Run `cargo fmt --check`, `cargo clippy --workspace --all-targets -- -D warnings`, and `cargo test --workspace`.**
- [ ] **Step 5: Commit** with `feat: add materialize CLI command`.

---

### Task 4: Negotiate Nave protocol v2 in Pulse

**Files:**
- Modify: `pulse:lib/pulse/scripts/nave_adapter.py`
- Modify: `pulse:lib/pulse/scripts/tests/test_nave_adapter.py`
- Create: `pulse:lib/pulse/scripts/tests/fixtures/nave/probe/materialize-help.txt`
- Create: `pulse:lib/pulse/scripts/tests/fixtures/nave/materialize.json`
- Modify: `pulse:lib/patterns/nave-evidence-contract.md`

**Interfaces:**

```python
BASELINE_CAPABILITIES = {...existing v1 capabilities...}
PROTOCOL_2_CAPABILITIES = BASELINE_CAPABILITIES | {"materialize_json"}

def materialize(runner: NaveRunner, request: str) -> dict: ...
```

Probe returns protocol `2` only when `materialize --help` advertises both `--request` and `--json`; otherwise a valid v1 installation remains protocol `1`. The adapter invokes arguments as a list and never parses human output.

- [ ] **Step 1: Add failing probe/adapter tests** for v1 compatibility, v2 detection, missing `--json`, invalid JSON, timeout, and non-zero typed errors.
- [ ] **Step 2: Run `uv run pytest -q lib/pulse/scripts/tests/test_nave_adapter.py`** and verify RED.
- [ ] **Step 3: Implement feature negotiation and the `materialize` adapter subcommand.** Do not make `materialize_json` a baseline F0 requirement.
- [ ] **Step 4: Run the focused tests and `uv run pytest -q`.**
- [ ] **Step 5: Commit** with `feat: negotiate Nave materialization protocol`.

---

### Task 5: Normalize and validate temporary dependency evidence

**Files:**
- Create: `pulse:lib/pulse/scripts/dependency_evidence.py`
- Create: `pulse:lib/pulse/scripts/validate_dependency_evidence.py`
- Create: `pulse:lib/pulse/scripts/tests/test_dependency_evidence.py`
- Create: `pulse:lib/pulse/scripts/tests/test_validate_dependency_evidence.py`
- Create: `pulse:lib/pulse/scripts/tests/fixtures/dependency-evidence-valid.json`
- Create: `pulse:lib/patterns/dependency-evidence-contract.md`
- Modify: `pulse:templates/workspace-gitignore.template`

**Interfaces:**

```python
def build_request(repos: list[str], selectors: list[dict]) -> dict: ...
def normalize(raw: dict, provider: dict, generated_at: str) -> dict: ...
```

Normalized contract:

```yaml
contract_version: 1
provider: {name: nave, version: <str|null>, protocol: 2}
generated_at: <ISO-8601>
request_sha256: <hex>
repos:
  - repo: acme/api
    ref_name: main
    tree_sha: <sha|null>
    tree_complete: true
    artifacts:
      - selector_id: python.pyproject
        path: pyproject.toml
        blob_sha: <sha>
        size_bytes: 1234
        state: found
        encoding: utf-8
        content: "..."
        detail: ""
errors: []
```

- [ ] **Step 1: Add failing normalizer/validator tests** covering every state, unique repository/selector/path identity, exact keys, SHA formats, required content only for `found`, forbidden content otherwise, finite size metadata, deterministic ordering, and protocol mismatch.
- [ ] **Step 2: Run both focused test files** and verify RED.
- [ ] **Step 3: Implement deterministic request hashing, normalization, and strict validation.** Create temporary directories/files with modes `0700`/`0600`. Validation errors never include file contents.
- [ ] **Step 4: Add `dependency-evidence.json` to the workspace transient ignore template.** Document that the file should normally live under a run-specific temporary directory and be deleted after F4 emits the content-free snapshot.
- [ ] **Step 5: Run focused/full tests and commit** with `feat: validate temporary dependency evidence`.

---

### Task 6: Gate F4 with cross-repository acceptance

**Files:**
- Create: `pulse:lib/pulse/scripts/tests/test_pre_f4_materialization_acceptance.py`
- Modify: `pulse:docs/superpowers/plans/2026-07-13-fleet-program-roadmap.md`

- [ ] **Step 1: Add an acceptance test** using the Pulse Nave fixture runner: protocol v1 still builds F0 evidence, protocol v2 materializes an exact manifest and globbed locks, truncated-tree absence remains unresolved, and the normalized dependency evidence validates.
- [ ] **Step 2: Assert no Pulse production code references Nave cache/checkouts** with a targeted source scan.
- [ ] **Step 3: Run `uv run pytest -q`, `git diff --check`, and the Nave workspace checks from Task 3.**
- [ ] **Step 4: Release Nave with the new protocol capability and record the minimum released version in `lib/patterns/dependency-evidence-contract.md`.** Do not begin F4 against an unreleased local-only CLI.
- [ ] **Step 5: Commit** with `test: gate F4 dependency materialization`.

## Pre-F4 completion gate

- Nave protocol v1 remains usable for F0.
- Nave protocol v2 provides `materialize_json` through a released CLI.
- Pulse consumes only the CLI JSON contract, not Nave cache paths.
- Found contents are blob-addressed and bounded; missing paths are authoritative only for complete trees.
- Raw content is transient and content-free artifacts are the only F4 durable/reportable outputs.
- Both repositories have clean full test, lint, and diff checks.
