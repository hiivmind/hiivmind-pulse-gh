"""AST import-boundary gate for the three F10 propose-only drivers.

Enforcement is DIRECT: parse each named driver's own module AST and reject
apply-mode imports / pen_orchestrator.execute calls on that module's surface.
A pure library that transitively touches apply code is fine — the boundary is
the driver's own Import / ImportFrom / Call nodes.

Do NOT glob ``*_run.py``: ``resolve_run.py`` is the pre-existing F5 run-ledger
driver and is out of scope for this F10 constraint.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]

# Explicit F10 propose drivers only (Task 7 brief — name them, do not glob).
F10_PROPOSE_DRIVERS = (
    "marketplace_sync_run.py",
    "plan_sync_run.py",
    "generated_artifact_run.py",
)

# Apply-mode modules / names that F10 drivers must never import.
FORBIDDEN_MODULES = frozenset(
    {
        "object_apply",
        "apply_reconcile",
        "pen_clone_reader",
        "apply_doc_patch",
        "apply_doc_patch_entry",
        "apply_marketplace_entry",
    }
)
FORBIDDEN_NAVE_NAMES = frozenset(
    {
        "provision_apply_branch",
        "commit_apply_clones",
        "push_apply_clones",
    }
)

APPLY_MUTATION_VERBS = frozenset({"pen_branch", "pen_commit", "pen_push", "pen_reset"})
ALLOWED_MUTATION_CALLERS = frozenset({"apply_ops.py", "apply_phases.py", "nave_adapter.py"})


def _module_basename(name: str) -> str:
    """Last segment of a dotted module path (handles lib.pulse.scripts.X)."""
    return name.rsplit(".", 1)[-1]


def _collect_import_violations(tree: ast.AST) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = _module_basename(alias.name)
                if base in FORBIDDEN_MODULES or base == "pen_orchestrator":
                    violations.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            base = _module_basename(module) if module else ""
            if base in FORBIDDEN_MODULES or base == "pen_orchestrator":
                violations.append(f"from {module} import ...")
                continue
            if base == "nave_adapter" or module.endswith("nave_adapter"):
                for alias in node.names:
                    if alias.name in FORBIDDEN_NAVE_NAMES or alias.name == "*":
                        violations.append(
                            f"from {module} import {alias.name}"
                        )
    return violations


def _call_name(node: ast.AST) -> str | None:
    """Best-effort dotted name for a Call's function."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    return None


def _collect_execute_violations(tree: ast.AST) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name is None:
            continue
        # pen_orchestrator.execute(...) or execute imported from pen_orchestrator
        if name == "pen_orchestrator.execute" or name.endswith(
            ".pen_orchestrator.execute"
        ):
            violations.append(name)
        # bare execute only if the module imported pen_orchestrator.execute
        # (covered by import check) — still flag pen_orchestrator.execute form.
    return violations


@pytest.mark.parametrize("filename", F10_PROPOSE_DRIVERS)
def test_f10_propose_driver_has_no_apply_mode_imports(filename: str):
    path = SCRIPTS / filename
    assert path.is_file(), f"missing F10 propose driver: {path}"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = _collect_import_violations(tree)
    assert violations == [], (
        f"{filename} imports apply-mode surface(s): {violations}"
    )


@pytest.mark.parametrize("filename", F10_PROPOSE_DRIVERS)
def test_f10_propose_driver_never_calls_pen_orchestrator_execute(filename: str):
    path = SCRIPTS / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = _collect_execute_violations(tree)
    assert violations == [], (
        f"{filename} calls pen_orchestrator.execute: {violations}"
    )


def test_f10_propose_driver_set_is_exactly_the_three_named_modules():
    """Guard against silently expanding or shrinking the boundary set."""
    assert set(F10_PROPOSE_DRIVERS) == {
        "marketplace_sync_run.py",
        "plan_sync_run.py",
        "generated_artifact_run.py",
    }
    for name in F10_PROPOSE_DRIVERS:
        assert (SCRIPTS / name).is_file()


def test_only_apply_adapters_call_nave_mutation_verbs():
    """No orchestrator or alternate driver may bypass the apply adapters."""
    violations: list[str] = []
    observed_callers: set[str] = set()
    for path in sorted(SCRIPTS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name and name.rsplit(".", 1)[-1] in APPLY_MUTATION_VERBS:
                observed_callers.add(path.name)
                if path.name not in ALLOWED_MUTATION_CALLERS:
                    violations.append(f"{path.name}:{node.lineno}:{name}")

    assert violations == [], f"non-adapter Nave mutation callers: {violations}"
    assert observed_callers <= ALLOWED_MUTATION_CALLERS
    assert "apply_ops.py" in observed_callers
