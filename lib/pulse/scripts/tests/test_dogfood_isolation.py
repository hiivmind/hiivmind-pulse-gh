"""Isolation proof: the neutral fleet path is provably overlay-independent.

Two guarantees, per the F9 plan (Task 5):

(a) No neutral engine module imports a dogfood-overlay module at module load
    time — importing the neutral path never pulls an overlay into the process.
    Verified by walking each neutral module's module-level import statements
    with `ast` (lazy imports inside functions are intentionally allowed: they
    execute only when an overlay is explicitly enabled).

(b) The neutral acceptance tests pass with the overlay fixture directories
    absent — proving no neutral test depends on an overlay fixture. Verified by
    copying the package into a tmp tree minus `tests/fixtures/overlays/` and
    running the neutral acceptance suite there.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]

# Neutral engine modules: the fleet path that must never know an overlay exists.
# `adapters/__init__.py` is included deliberately — it is the shared registration
# surface, and importing it (to get `register_universal_adapters`) must NOT drag
# in the overlay adapters. Its `register_claude_adapters` entry point may import
# the overlay LAZILY (inside the function body), which this module-level scan
# does not see.
NEUTRAL_MODULES = (
    "lib/pulse/scripts/profile_dispatch.py",
    "lib/pulse/scripts/check_adapters.py",
    "lib/pulse/scripts/adapters/generic.py",
    "lib/pulse/scripts/adapters/__init__.py",
    "lib/pulse/scripts/evaluate_checks.py",
    "lib/pulse/scripts/generated_artifacts.py",
    "lib/pulse/scripts/generator_dispatch.py",
)

# The dogfood-overlay modules introduced by F9. None of the neutral modules
# above may import any of these at module level.
OVERLAY_MODULES = (
    "lib.pulse.scripts.adapters.claude_plugin",
    "lib.pulse.scripts.marketplace_sync",
    "lib.pulse.scripts.repo_claims",
)

# Neutral acceptance tests that must pass with overlay fixtures absent. Each of
# these builds its own fixtures inline or reads only neutral fixture dirs
# (fixtures/profiles, fixtures/checks) — never fixtures/overlays.
NEUTRAL_ACCEPTANCE_TESTS = (
    "lib/pulse/scripts/tests/test_profile_acceptance.py",
    "lib/pulse/scripts/tests/test_fleet_healthcheck_acceptance.py",
    "lib/pulse/scripts/tests/test_generic_adapters.py",
    "lib/pulse/scripts/tests/test_healthcheck_dispatch.py",
)


def _module_level_imports(source: str) -> set[str]:
    """Return the dotted names imported at MODULE LEVEL by `source`.

    Only statements in the module body are inspected; imports nested inside
    functions/classes (lazy imports) are excluded on purpose. For an
    ``ImportFrom`` both the source module and each ``module.name`` are recorded
    so `from a.b import c` surfaces as both ``a.b`` and ``a.b.c``.
    """
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import — not used for overlays here
                continue
            module = node.module or ""
            if module:
                names.add(module)
            for alias in node.names:
                names.add(f"{module}.{alias.name}" if module else alias.name)
    return names


def _imports_any_overlay(imported: set[str]) -> list[str]:
    hits: list[str] = []
    for name in imported:
        for overlay in OVERLAY_MODULES:
            if name == overlay or name.startswith(overlay + "."):
                hits.append(name)
    return hits


@pytest.mark.parametrize("module_path", NEUTRAL_MODULES)
def test_neutral_module_does_not_import_overlay_at_module_level(module_path):
    source = (REPO_ROOT / module_path).read_text()
    imported = _module_level_imports(source)
    leaked = _imports_any_overlay(imported)
    assert leaked == [], (
        f"{module_path} imports overlay module(s) at module level: {leaked}. "
        "Neutral modules must stay overlay-independent; move the import into a "
        "lazily-invoked function if it is truly needed."
    )


def test_neutral_acceptance_passes_without_overlay_fixtures(tmp_path):
    # Copy the package into an isolated tree, then delete the overlay fixtures.
    dst = tmp_path / "tree"
    shutil.copytree(
        REPO_ROOT / "lib",
        dst / "lib",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    overlays = dst / "lib/pulse/scripts/tests/fixtures/overlays"
    assert overlays.is_dir(), "overlay fixtures must exist before removal"
    shutil.rmtree(overlays)

    env = {**os.environ, "PYTHONPATH": str(dst)}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *NEUTRAL_ACCEPTANCE_TESTS, "-q"],
        cwd=dst,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "neutral acceptance suite failed with overlay fixtures absent:\n"
        + result.stdout
        + result.stderr
    )
