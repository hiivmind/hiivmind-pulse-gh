# Backlog: extract `lib/pulse` as a standalone Python package

**Date:** 2026-08-17
**Status:** Open, no spec
**Severity:** Architectural — structural coupling, not a bug
**Found in:** user request, directly following the F8 Projects-v2 backlog capture;
subsumes and concretizes `2026-07-13-fleet-scope-audit.md` finding **F7**
**Scope:** `lib/pulse/scripts/` (53 modules + `tests/` + `adapters/`), root `pyproject.toml`,
every skill's `{PLUGIN_ROOT}`-relative script invocation, `hooks/heartbeat.sh`

## Problem

`lib/pulse/scripts/` is a real Python library — 53 modules covering fleet
evidence, dependency-coherence, apply-mode (single/multi-repo/dependency-bump),
plan-sync, healthcheck, impact-audit, marketplace-sync, generated-artifact —
with its own test suite (1590+ tests). It is **not distributable or reusable
outside this exact repo checkout**:

- **Root `pyproject.toml` names it dev tooling, not a library.**
  `name = "hiivmind-pulse-gh-dev"`, `version = "0.0.0"`, description literally
  reads *"Dev/test environment for hiivmind-pulse-gh plugin scripts"*. Only 2
  of 53 scripts have a `[project.scripts]` entry point
  (`pulse-apply-doc-patch`, `pulse-apply-marketplace-entry`); the rest have no
  installed entry point at all.
- **Invocation is absolute-path, plugin-root-relative — every skill.**
  Every headless and interactive `SKILL.md` invokes scripts as
  `uv run "{PLUGIN_ROOT}/lib/pulse/scripts/<name>.py"`, where `{PLUGIN_ROOT}`
  is defined as "the directory containing `plugin.json`" — a Claude-plugin
  distribution concept, not a Python packaging one. `hooks/heartbeat.sh`
  does the same: `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-...}"` then
  `exec uv run "$PLUGIN_ROOT/lib/pulse/scripts/poll.py"`.
- **Cross-module imports are absolute-from-repo-root, not package-relative.**
  Modules import siblings as `from lib.pulse.scripts import apply_authorization`
  / `from lib.pulse.scripts.apply_journal import Journal` etc. — this only
  resolves because `pytest.ini_options.pythonpath = ["."]` puts the repo root
  on `sys.path` for tests, and because scripts are always run from within a
  checkout of *this* repo in production. There is no installed `lib.pulse`
  distribution with real package metadata.
- **PEP 723 self-containment solves a different problem.** Each script
  declares its own inline `# dependencies = [...]` header so `uv run <file>.py`
  works without a shared venv — genuinely useful for isolated, dependency-free
  execution — but it is a script-portability mechanism, not a
  package-distribution mechanism. It doesn't make the modules `import`-able
  from another project; it makes `uv run` able to invoke *this specific file
  path* without a preinstalled environment.

## Why this is the same problem as audit finding F7

`docs/superpowers/audits/2026-07-13-fleet-scope-audit.md` **F7** (Medium)
already named half of this:

> A fleet-management skill may run from a plugin, a standalone CLI, CI, a
> scheduler, or another automation host. Requiring a plugin root and
> `plugin.json` makes the manager unusable outside Claude plugin distribution
> and confuses the control plane with the managed repositories.
> **Required correction:** Define a neutral runtime root and workspace root.

F7's recommended fix — "a neutral runtime root, not `{PLUGIN_ROOT}`" — cannot
be implemented in Python *without* extracting `lib/pulse` to its own
installable package. As long as the scripts live inside the Claude-plugin
repo and are invoked via `{PLUGIN_ROOT}`-relative file paths, "neutral runtime
root" has no meaning to distinguish from "the plugin's install directory" —
there is nothing else to resolve against. Decoupling the runtime from the
plugin host **is** package extraction; they aren't two projects, they're one.

## Existing precedent in this codebase: Nave

This is not a novel move for this program. `nave` (the fleet-evidence/apply
engine's Rust core) already made exactly this transition: it lives in its own
repo (`discreteds/nave`), builds to a standalone release binary
(`cargo build --release -p nave`), is installed independently
(`~/.local/bin/nave`), and `hiivmind-pulse-gh` consumes it as an external CLI
subprocess (`apply_driver.py`, `nave_adapter.py`) — no vendored source, no
plugin-root-relative path coupling. `lib/pulse` extraction is the same move
for the Python side: own repo, own package, own version, own release
artifact, consumed by the plugin rather than living inside it.

## What extraction would require (real scope, not exhaustive by design)

- **A new repo + real distributable package** (e.g. `hiivmind-pulse`) with
  actual `[project.dependencies]`, a build backend, and semantic versioning —
  replacing the `hiivmind-pulse-gh-dev` / `0.0.0` placeholder.
- **A console-entry-point (or single-dispatcher-CLI) surface for every script
  currently invoked by file path** — 51 of 53 have none today.
- **Every `SKILL.md`'s `{PLUGIN_ROOT}/lib/pulse/scripts/<name>.py` invocation
  rewritten** to an installed-command form (e.g. `uvx hiivmind-pulse <verb>`
  or `pulse-<name>`), and `hooks/heartbeat.sh` likewise.
- **A decision on the PEP-723-per-script mechanism's fate**: keep it (so the
  package remains `uv run`-invokable standalone, dependency-free, in addition
  to being pip/uv-installable), drop it in favor of the package's own
  `[project.dependencies]`, or keep both deliberately for different consumers
  (a "run without installing" story vs. an "import as a library" story) —
  this is a genuine design fork, not a detail.
- **The test suite (1590+ tests, `lib/pulse/scripts/tests/`) moves with the
  modules** — splitting what stays plugin-side (skills, `SKILL.md`,
  `templates/`, `lib/patterns/`, `lib/references/`) from what becomes
  library-side (`lib/pulse/scripts/`, `lib/pulse/scripts/adapters/`, their
  tests) is the core of the cut line.
- **A release/versioning and CI story for the new repo** — build, test,
  publish (PyPI or git-installable), and a compatibility policy for
  `hiivmind-pulse-gh` pinning a version of it, mirroring how nave is pinned
  and rebuilt today.
- **`hiivmind-pulse-gh` becomes a thin consumer**: skills + templates +
  patterns + a declared dependency on the extracted package, not a repo that
  vendors 53 implementation modules alongside its plugin surface.

## Evidence

- `pyproject.toml` (root) — `name = "hiivmind-pulse-gh-dev"`, `version = "0.0.0"`,
  dev-tooling description; only 2 `[project.scripts]` entries against 53 modules.
- `skills/*/SKILL.md` (23+ skills) — every headless/interactive skill defines
  `{PLUGIN_ROOT}` = "directory containing `plugin.json`" and invokes scripts as
  `uv run "{PLUGIN_ROOT}/lib/pulse/scripts/<name>.py"`.
- `hooks/heartbeat.sh:50,52` — `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-...}"` then
  `exec uv run "$PLUGIN_ROOT/lib/pulse/scripts/poll.py" ... --plugin-root "$PLUGIN_ROOT"`.
- `lib/pulse/scripts/apply_driver.py` (and others) — `from lib.pulse.scripts
  import (...)` absolute-from-repo-root imports, `# noqa: E402` markers
  confirming the path-hack pattern.
- `docs/superpowers/audits/2026-07-13-fleet-scope-audit.md` § F7 — the prior,
  narrower framing of the same underlying coupling.
- `~/git/discreteds/nave` (this workspace) — the working precedent: an
  extracted, independently released, subprocess-consumed engine already
  proven for the Rust half of this program.

## Notes

Not framed as "do we need this" — capturing full real scope per this
program's backlog convention (see `2026-08-13-f4-deferred-scope.md` /
`2026-07-29-apply-mode-v2-deferrals.md`'s "Trigger to build" pattern). This is
design-first, not implementation-first: the PEP-723-vs-installed-package fork
above needs settling before any code moves, and it changes the shape of every
skill in this repo, so it should get its own `brainstorming` → spec pass
rather than being folded into an unrelated change.
