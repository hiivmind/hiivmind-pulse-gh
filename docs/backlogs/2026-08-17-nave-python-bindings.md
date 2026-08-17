# Backlog: expose Nave's Rust internals to Python (native bindings)

**Date:** 2026-08-17
**Status:** Open, no spec
**Severity:** Architectural — enables the FastAPI/agent-native service layer,
not a bug
**Found in:** user follow-up on the cross-language action boundary raised in
`2026-08-17-agent-native-fleet-ui.md`
**Scope:** `discreteds/nave` (Rust workspace: `crates/nave*`, `pyproject.toml`,
`python/nave/`) — a `nave`-repo item, not a `hiivmind-pulse-gh` change

## Problem

If `lib/pulse` grows a FastAPI service that calls its own Python functions
in-process (see the SDK amendment in
`2026-08-17-lib-pulse-package-extraction.md`), that service still has to
reach Nave for every fleet-evidence, pen, and apply operation — and today
that path is **always** a subprocess: `nave <verb> --json`, parse stdout.
That's the same subprocess/serialization boundary the SDK amendment exists
to remove for the Python side, just recreated at the Python↔Rust edge
instead of the Node↔Python edge.

**Nave already ships a Python package — but it wraps the binary, not the
library.** `discreteds/nave`'s root `pyproject.toml` is already a working
`maturin` build:

```toml
[build-system]
requires = ["maturin>=1.9.3,<2.0"]
build-backend = "maturin"

[tool.maturin]
bindings = "bin"
manifest-path = "crates/nave/Cargo.toml"
module-name = "nave"
python-source = "python"
```

`bindings = "bin"` is maturin's *binary-wrapping* mode: it compiles the
`nave` CLI crate and bundles the executable into a wheel, and
`python/nave/{__init__.py,__main__.py,_find_nave.py}` is a thin shim that
locates and execs that bundled binary. `pip install nave` today gives you a
`nave` command — still invoked as a subprocess, still communicating over
stdout JSON. There is **no `pyo3` dependency anywhere in the workspace** and
no `bindings = "pyo3"` target — confirmed by grep; the only `pyo3`/`maturin`
strings in the Rust source are nave's own **test fixtures**, because nave's
job includes parsing and rewriting *other* repos' `pyproject.toml` files
that happen to use PyO3 bindings (`nave_rewrite::apply` test data) — that is
nave modeling a capability of repos it manages, not a capability of itself.

## What native bindings would add

Rust functions callable **in-process** from Python — no subprocess spawn, no
JSON stdout parsing, and (with `pyo3-asyncio` or an explicit
`tokio::runtime::Runtime::block_on` bridge) real error propagation instead of
exit-code/stderr sniffing. This is a second `maturin` binding target
alongside (not necessarily replacing) the existing `bindings = "bin"` wheel —
maturin supports both `bin` and `pyo3` binding modes, they aren't mutually
exclusive as a project's overall distribution strategy, though a single
`[tool.maturin]` table picks one at a time (a genuine open question below).

**The Rust side is already shaped for this.** The workspace already
separates a CLI-only binary crate (`crates/nave`, `src/main.rs`, no
`lib.rs`) from real library crates with public APIs:
`nave_pen::{create_pen, exec_pen, rewrite_pen, ...}`,
`nave_apply` (`BranchRepoRequest`/`BranchResult`, `CommitRepoRequest`, etc. —
already `pub struct`/`pub fn`, already `serde`-derived for the existing JSON
CLI contract), `nave_scan`, `nave_search`, `nave_config`. A `pyo3` binding
crate would wrap **these existing library crates' public functions**, not
require carving new library boundaries out of CLI-only code — the same
situation the SDK amendment found on the Python side.

## Real open questions (design fork, not detail)

- **Async bridging.** `nave_pen` (and presumably other crates) depend on
  `tokio`. PyO3 bindings need an explicit strategy for calling `async fn`
  Rust from Python: block on a runtime per-call (`Runtime::block_on`, simple
  but blocks the GIL-released thread for the call's duration), integrate
  `pyo3-asyncio` for a real async Python API, or restrict the bound surface
  to Nave's synchronous entry points only. This changes the shape of the
  Python API a FastAPI handler would await.
- **Which functions get bound.** Not "all of nave" — the FastAPI service's
  actual call sites (evidence scan, pen create/exec, apply branch/commit/push,
  reconcile inputs) should drive an initial bound surface, not a blanket
  wrap of every public Rust item.
- **`bin` vs `pyo3` maturin coexistence.** One `pyproject.toml`'s
  `[tool.maturin]` table selects one `bindings` mode. Shipping both a CLI
  wheel (today's `pip install nave` → `nave` on PATH) and a native-extension
  wheel (`import nave_native`, or similar) likely means either two build
  targets/publish artifacts from one workspace, or a deliberate choice to
  fold the CLI into a thin wrapper over the same compiled extension instead
  of a second `bin` crate — a real Rust/Python packaging design decision.
- **Error/JSON contract parity.** The CLI's current JSON-on-stdout contract
  (`nave_pen`'s `serde`-derived result types) is the de facto stable
  interface `apply_driver.py`/`nave_adapter.py` already depend on. Native
  bindings should return the same typed shapes (via `pyo3`'s struct/dict
  conversion) rather than a divergent second contract — needs an explicit
  compatibility statement once designed.
- **Versioning/compatibility.** `nave`'s Python package version (`0.0.8`)
  already exists as one artifact; a `pyo3`-bound extension is effectively a
  second, ABI-sensitive artifact (tied to a specific Python/Rust build) that
  needs its own release discipline alongside the existing binary wheel and
  the `cargo build --release` path this program already pins
  (`~/.local/bin/nave`).

## Why this belongs in `nave`, not `hiivmind-pulse-gh`

Everything above is Rust-workspace and Rust-packaging scope in
`discreteds/nave`. `hiivmind-pulse-gh`'s only stake is being a consumer: once
bindings exist, `apply_driver.py`/`nave_adapter.py`'s subprocess calls become
candidates for replacement by direct `import nave_native` calls inside the
same SDK/FastAPI layer `2026-08-17-lib-pulse-package-extraction.md` is
building. That migration is this repo's follow-on work, not this item's.

## Evidence

- `~/git/discreteds/nave/pyproject.toml` — `[build-system] requires =
  ["maturin"]`, `[tool.maturin] bindings = "bin"`, `module-name = "nave"`,
  `python-source = "python"`.
- `~/git/discreteds/nave/python/nave/{__init__.py,__main__.py,_find_nave.py}`
  — the existing binary-locating shim confirming `bin` mode, not native
  bindings.
- `~/git/discreteds/nave/Cargo.toml` (workspace) — `crates/nave` (binary,
  `src/main.rs` only, no `lib.rs`) vs. library crates (`nave_pen`,
  `nave_apply`, `nave_scan`, etc.) with real `pub use`/`pub fn`/`pub struct`
  surfaces — confirmed via `crates/nave_pen/src/lib.rs`'s `pub use` block and
  `crates/nave_apply/src/lib.rs`'s public request/result types.
- Grep confirms no `pyo3` crate dependency anywhere in the workspace; every
  `pyo3`/`maturin` string hit is nave's own test fixture data for rewriting
  *other* repos' `pyproject.toml` files (`nave_config::match_pred`,
  `nave_rewrite::apply` test cases).
- `crates/nave_pen/Cargo.toml` — `tokio` dependency, confirming the async
  bridging question is real, not hypothetical.
- `docs/backlogs/2026-08-17-lib-pulse-package-extraction.md` (Amendment
  2026-08-17) — the Python-side SDK requirement this item is the Rust-side
  counterpart to.
- `docs/backlogs/2026-08-17-agent-native-fleet-ui.md` — where the
  cross-language action boundary was first raised.

## Notes

Design-first, `nave`-repo scope. Should get its own brainstorm/spec pass in
`discreteds/nave`, sequenced alongside (not necessarily after) the
`lib/pulse` SDK work — the two are the same architectural move (in-process
callable library instead of subprocess CLI) applied to each language, and a
FastAPI service's design should account for both from the start rather than
bolting Rust bindings on after the Python SDK ships.
