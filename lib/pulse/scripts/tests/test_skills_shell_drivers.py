"""Enrollment lint for skills/headless-driver-map.yaml.

Regression gate: every on-disk skills/*-headless skill must be enrolled as
either a self-validating result-driver or an explicit exempt entry. A new
headless skill that is neither FAILS this suite (no prose scan required —
enrollment is by directory existence).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
MAP_PATH = REPO_ROOT / "skills" / "headless-driver-map.yaml"
SKILLS_DIR = REPO_ROOT / "skills"


def _load_map() -> dict:
    assert MAP_PATH.is_file(), f"missing enrollment map: {MAP_PATH}"
    data = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "headless-driver-map.yaml must be a mapping"
    drivers = data.get("drivers") or {}
    exempt = data.get("exempt") or {}
    assert isinstance(drivers, dict), "drivers must be a mapping"
    assert isinstance(exempt, dict), "exempt must be a mapping"
    return {"drivers": drivers, "exempt": exempt}


def _on_disk_headless_skills() -> set[str]:
    return {
        path.name
        for path in SKILLS_DIR.glob("*-headless")
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def _argparse_flags(script_path: Path) -> set[str]:
    """Collect option strings from argparse add_argument calls via AST."""
    tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_add = (
            isinstance(func, ast.Attribute) and func.attr == "add_argument"
        ) or (isinstance(func, ast.Name) and func.id == "add_argument")
        if not is_add:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value.startswith("-"):
                    flags.add(arg.value)
    return flags


def _source_invokes_validator_kind(script_path: Path, kind: str) -> bool:
    """True when the driver source passes ``kind`` into a validate call."""
    src = script_path.read_text(encoding="utf-8")
    # Direct string literal used as the kind argument.
    if f'"{kind}"' not in src and f"'{kind}'" not in src:
        return False
    tree = ast.parse(src, filename=str(script_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        if name not in {"validate", "validate_result"}:
            continue
        for arg in list(node.args) + [
            kw.value for kw in node.keywords if kw.arg in {None, "kind"}
        ]:
            if isinstance(arg, ast.Constant) and arg.value == kind:
                return True
        for kw in node.keywords:
            if kw.arg == "kind" and isinstance(kw.value, ast.Constant):
                if kw.value.value == kind:
                    return True
    # Also accept validate_result.validate(data, "kind") even if attr name
    # check above already covered it; fall back to regex for multi-line.
    pattern = re.compile(
        rf"validate_result\.validate\s*\([^)]*['\"]{re.escape(kind)}['\"]",
        re.DOTALL,
    )
    return bool(pattern.search(src))


def _source_writes_result_on_abort(script_path: Path) -> bool:
    """Self-validating drivers write + validate an abort envelope."""
    src = script_path.read_text(encoding="utf-8")
    has_abort_builder = "_build_abort_result" in src or "abort" in src.lower()
    has_write = (
        "_write_and_validate_result" in src
        or "write_text" in src
        or "yaml.dump" in src
    )
    has_errors = '"errors"' in src or "'errors'" in src
    return has_abort_builder and has_write and has_errors


def _has_abort_test_for_script(script_name: str) -> bool:
    """Reference existing per-driver ABORT tests in the suite."""
    tests_dir = Path(__file__).resolve().parent
    stem = Path(script_name).stem  # marketplace_sync_run
    candidates = list(tests_dir.glob(f"test_{stem}*.py")) + list(
        tests_dir.glob(f"test_*{stem}*.py")
    )
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        if re.search(r"abort", text, re.IGNORECASE) and re.search(
            r"validat", text, re.IGNORECASE
        ):
            return True
    return False


def test_map_coverage_equals_on_disk_headless_skills():
    data = _load_map()
    mapped = set(data["drivers"]) | set(data["exempt"])
    on_disk = _on_disk_headless_skills()
    missing = on_disk - mapped
    extra = mapped - on_disk
    assert missing == set(), (
        f"headless skills not enrolled in headless-driver-map.yaml: {sorted(missing)}"
    )
    assert extra == set(), (
        f"map entries with no on-disk skills/*-headless: {sorted(extra)}"
    )
    overlap = set(data["drivers"]) & set(data["exempt"])
    assert overlap == set(), (
        f"skills enrolled under both drivers and exempt: {sorted(overlap)}"
    )


def test_exempt_entries_have_nonempty_reason():
    data = _load_map()
    for skill, reason in data["exempt"].items():
        assert isinstance(reason, str) and reason.strip(), (
            f"exempt entry for {skill} must be a non-empty one-line reason"
        )


def test_each_driver_script_exists_and_exposes_cli_flags():
    data = _load_map()
    for skill, entry in data["drivers"].items():
        assert isinstance(entry, dict), f"{skill}: driver entry must be a mapping"
        script_rel = entry.get("script")
        assert isinstance(script_rel, str) and script_rel, (
            f"{skill}: missing script path"
        )
        script_path = REPO_ROOT / script_rel
        assert script_path.is_file(), f"{skill}: script missing: {script_path}"

        command = entry.get("command")
        assert isinstance(command, str) and "uv run" in command, (
            f"{skill}: command must document a uv run invocation"
        )
        assert script_rel in command or Path(script_rel).name in command, (
            f"{skill}: command must reference {script_rel}"
        )

        declared = entry.get("cli_flags")
        assert isinstance(declared, list) and declared, (
            f"{skill}: cli_flags must list the documented argparse flags"
        )
        available = _argparse_flags(script_path)
        missing_flags = set(declared) - available
        assert missing_flags == set(), (
            f"{skill}: argparse in {script_rel} missing flags {sorted(missing_flags)}; "
            f"found {sorted(available)}"
        )


def test_each_driver_writes_result_on_abort():
    data = _load_map()
    for skill, entry in data["drivers"].items():
        script_path = REPO_ROOT / entry["script"]
        by_source = _source_writes_result_on_abort(script_path)
        by_test = _has_abort_test_for_script(entry["script"])
        assert by_source or by_test, (
            f"{skill}: driver {entry['script']} must write a validated result on "
            f"ABORT (source abort-write pattern or an existing ABORT test)"
        )


def test_each_driver_invokes_declared_validator_kind():
    data = _load_map()
    for skill, entry in data["drivers"].items():
        kind = entry.get("validator_kind")
        assert isinstance(kind, str) and kind, (
            f"{skill}: missing validator_kind"
        )
        script_path = REPO_ROOT / entry["script"]
        assert _source_invokes_validator_kind(script_path, kind), (
            f"{skill}: {entry['script']} must call validate with kind {kind!r}"
        )
