"""Structural neutrality guard for apply-mode modules (F11 Task 8).

Guarantees that apply-mode modules carry NO plugin/overlay knowledge:
1. AST / Import-Graph Guard (PRIMARY): Ensures pen_orchestrator, apply_reconcile,
   object_apply, pen_clone_reader, and nave_adapter import NO plugin/overlay modules
   or overlay registration functions (top-level or inside functions).
2. Predicate Evaluation Guard: Asserts no `profile:claude-plugin` predicate logic
   is evaluated in the apply code paths.
3. Secondary Whitelisted Lexical Heuristic: A string-grep scanner with an explicit
   whitelist for legitimate prose references.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

APPLY_MODULE_PATHS = (
    "lib/pulse/scripts/pen_orchestrator.py",
    "lib/pulse/scripts/apply_reconcile.py",
    "lib/pulse/scripts/object_apply.py",
    "lib/pulse/scripts/pen_clone_reader.py",
    "lib/pulse/scripts/nave_adapter.py",
)

FORBIDDEN_OVERLAY_MODULES_AND_SYMBOLS = (
    "profile_dispatch",
    "lib.pulse.scripts.profile_dispatch",
    "claude_plugin",
    "lib.pulse.scripts.adapters.claude_plugin",
    "register_claude_adapters",
    "marketplace_sync",
    "lib.pulse.scripts.marketplace_sync",
    "repo_claims",
    "lib.pulse.scripts.repo_claims",
    "apply_marketplace_entry",
    "lib.pulse.scripts.apply_marketplace_entry",
    "apply_doc_patch",
    "lib.pulse.scripts.apply_doc_patch",
    "corpus_generator_overlay",
    "skills_path_resolver",
)


def _collect_all_ast_imports(source: str) -> set[str]:
    """Parse source and return all imported names anywhere in the AST (top-level or inside functions)."""
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module = node.module or ""
            if module:
                imported.add(module)
            for alias in node.names:
                imported.add(f"{module}.{alias.name}" if module else alias.name)
    return imported


@pytest.mark.parametrize("module_path", APPLY_MODULE_PATHS)
def test_apply_module_imports_no_overlay_modules_structural_ast(module_path: str) -> None:
    """PRIMARY AST GUARD: Assert apply module imports zero plugin/overlay modules or functions."""
    full_path = REPO_ROOT / module_path
    assert full_path.exists(), f"module file not found: {module_path}"
    source = full_path.read_text()
    imported = _collect_all_ast_imports(source)

    forbidden_hits: list[str] = []
    for imp in imported:
        for forbidden in FORBIDDEN_OVERLAY_MODULES_AND_SYMBOLS:
            if imp == forbidden or imp.startswith(forbidden + ".") or imp.endswith("." + forbidden):
                forbidden_hits.append(imp)

    assert forbidden_hits == [], (
        f"Apply module {module_path} imports plugin/overlay symbol(s): {forbidden_hits}. "
        "Apply-mode modules must be strictly neutral and carry no plugin/overlay imports."
    )


@pytest.mark.parametrize("module_path", APPLY_MODULE_PATHS)
def test_apply_module_evaluates_no_claude_plugin_predicates_ast(module_path: str) -> None:
    """AST PREDICATE GUARD: Assert apply module code path evaluates no profile:claude-plugin predicates."""
    full_path = REPO_ROOT / module_path
    source = full_path.read_text()
    tree = ast.parse(source)

    claude_pred_hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if "profile:claude-plugin" in val:
                claude_pred_hits.append(val)

    assert claude_pred_hits == [], (
        f"Apply module {module_path} hardcodes or evaluates `profile:claude-plugin` predicate logic: "
        f"{claude_pred_hits}. Neutral apply paths must evaluate no overlay-specific predicates."
    )


@pytest.mark.parametrize("module_path", APPLY_MODULE_PATHS)
def test_apply_module_secondary_whitelisted_lexical_heuristic(module_path: str) -> None:
    """SECONDARY HEURISTIC: Lexical scan with whitelist for legitimate prose cross-references."""
    full_path = REPO_ROOT / module_path
    source = full_path.read_text()

    flag_patterns = [
        re.compile(r"\bclaude_plugin\b"),
        re.compile(r"\bregister_claude_adapters\b"),
        re.compile(r"\bprofile:claude-plugin\b"),
        re.compile(r"\bcorpus_generator_overlay\b"),
    ]

    whitelist_patterns = [
        r"#.*F6 plan",
        r"#.*F11 plan",
        r'""".*F6 plan',
    ]

    lines = source.splitlines()
    unwhitelisted_hits: list[tuple[int, str]] = []

    for idx, line in enumerate(lines, 1):
        if any(re.search(pat, line) for pat in whitelist_patterns):
            continue
        for pat in flag_patterns:
            if pat.search(line):
                unwhitelisted_hits.append((idx, line.strip()))

    assert unwhitelisted_hits == [], (
        f"Secondary lexical scan found unwhitelisted overlay references in {module_path}: "
        f"{unwhitelisted_hits}"
    )
