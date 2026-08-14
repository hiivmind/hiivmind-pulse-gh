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
    "lib/pulse/scripts/apply_driver.py",
    "lib/pulse/scripts/apply_advance_base.py",
    "lib/pulse/scripts/apply_phases.py",
    "lib/pulse/scripts/apply_ops.py",
    "lib/pulse/scripts/gh_contents_ops.py",
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
    """Parse source and return all imported names anywhere in the AST (top-level, inside functions, absolute and relative)."""
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                imported.add(module)
            for alias in node.names:
                alias_name = alias.name
                imported.add(alias_name)
                if module:
                    imported.add(f"{module}.{alias_name}")
    return imported


def _scan_line_for_unwhitelisted_overlay_tokens(
    line: str, in_docstring: bool
) -> tuple[bool, bool]:
    """Inspect line for forbidden overlay tokens.

    Returns (is_flagged, new_in_docstring_state). Whitelists apply ONLY to pure
    comment lines (# ...) or docstring prose — code before inline comments is
    never exempted by a comment whitelist.
    """
    flag_patterns = [
        re.compile(r"\bprofile_dispatch\b"),
        re.compile(r"\bclaude_plugin\b"),
        re.compile(r"\bregister_claude_adapters\b"),
        re.compile(r"\bprofile:claude-plugin\b"),
        re.compile(r"\bcorpus_generator_overlay\b"),
    ]

    whitelist_patterns = [
        r"#.*F6 plan",
        r"#.*F11 plan",
        r'""".*F6 plan',
        r"'''.*F6 plan",
    ]

    stripped = line.strip()

    num_triple_double = line.count('"""')
    num_triple_single = line.count("'''")
    docstring_toggle = (num_triple_double % 2 == 1) or (num_triple_single % 2 == 1)

    current_is_docstring = in_docstring or stripped.startswith('"""') or stripped.startswith("'''")
    new_in_docstring = in_docstring ^ docstring_toggle

    # Case 1: Pure comment line or inside docstring
    if current_is_docstring or stripped.startswith("#"):
        if any(re.search(pat, line) for pat in whitelist_patterns):
            return False, new_in_docstring
        for pat in flag_patterns:
            if pat.search(line):
                return True, new_in_docstring
        return False, new_in_docstring

    # Case 2: Code line (possibly with an inline comment after #)
    parts = line.split("#", 1)
    code_part = parts[0]
    comment_part = f"# {parts[1]}" if len(parts) > 1 else ""

    # Code before # is NEVER whitelisted by an inline comment
    for pat in flag_patterns:
        if pat.search(code_part):
            return True, new_in_docstring

    if comment_part:
        if not any(re.search(pat, comment_part) for pat in whitelist_patterns):
            for pat in flag_patterns:
                if pat.search(comment_part):
                    return True, new_in_docstring

    return False, new_in_docstring


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
            if (
                imp == forbidden
                or imp.startswith(forbidden + ".")
                or imp.endswith("." + forbidden)
                or f".{forbidden}." in f".{imp}."
            ):
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

    lines = source.splitlines()
    unwhitelisted_hits: list[tuple[int, str]] = []
    in_docstring = False

    for idx, line in enumerate(lines, 1):
        flagged, in_docstring = _scan_line_for_unwhitelisted_overlay_tokens(line, in_docstring)
        if flagged:
            unwhitelisted_hits.append((idx, line.strip()))

    assert unwhitelisted_hits == [], (
        f"Secondary lexical scan found unwhitelisted overlay references in {module_path}: "
        f"{unwhitelisted_hits}"
    )


def test_relative_import_detection_in_ast_guard() -> None:
    """Unit test for Important 1: Proves relative imports of forbidden overlay modules are caught."""
    synthetic_sources = [
        "from .profile_dispatch import foo",
        "from . import profile_dispatch",
        "from ..adapters.claude_plugin import bar",
        "from .marketplace_sync import sync",
    ]
    for src in synthetic_sources:
        imported = _collect_all_ast_imports(src)
        hits = []
        for imp in imported:
            for forbidden in FORBIDDEN_OVERLAY_MODULES_AND_SYMBOLS:
                if (
                    imp == forbidden
                    or imp.startswith(forbidden + ".")
                    or imp.endswith("." + forbidden)
                    or f".{forbidden}." in f".{imp}."
                ):
                    hits.append(imp)
        assert hits != [], f"Relative import not detected as forbidden in source: {src}"


def test_inline_comment_not_whitelisted_in_secondary_scan() -> None:
    """Unit test for Important 2: Proves inline comments do NOT whitelist code on the same line."""
    synthetic_line = "import profile_dispatch  # F6 plan"
    flagged, _ = _scan_line_for_unwhitelisted_overlay_tokens(synthetic_line, in_docstring=False)
    assert flagged is True, "Inline comment must NOT whitelist forbidden code before #"
