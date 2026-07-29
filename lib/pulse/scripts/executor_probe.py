"""Executor on PATH probe helper and command_argv safety linter."""

from __future__ import annotations

import shutil
import sysconfig
from typing import Any


KNOWN_CONSOLE_SCRIPTS = {
    "pulse-apply-doc-patch",
    "pulse-apply-marketplace-entry",
}

ECOSYSTEM_MAP = {
    "ruff": "python",
    "npm": "nodejs",
    "mkdocs": "docs",
    "nave": "nave",
    "pulse-apply-doc-patch": "plan-sync",
    "pulse-apply-marketplace-entry": "marketplace",
}


def validate_command_argv(command_argv: tuple[str, ...] | list[str], entry_id: str = "") -> None:
    """Scan every element of command_argv for repo-relative script paths.

    Every element must be resolvable on PATH or a bare argument/command.
    Repo-relative script paths (e.g. `lib/pulse/scripts/apply_doc_patch.py` or
    `foo/bar.py`) are rejected at any position.
    """
    prefix = f"transformation {entry_id}." if entry_id else ""
    for index, arg in enumerate(command_argv):
        if isinstance(arg, str) and arg.endswith(".py"):
            raise ValueError(
                f"{prefix}command_argv[{index}] is a repo-relative script path, not reachable on PATH: {arg!r}"
            )


def probe_required_tool(tool: str, ecosystem: str | None = None, path_env: str | None = None) -> dict[str, Any]:
    """Probe presence of a required executable tool on PATH before execution.

    If absent, returns a fail-closed `blocked`-shaped dictionary naming the
    missing tool and ecosystem.
    """
    resolved_ecosystem = ecosystem or ECOSYSTEM_MAP.get(tool, "unknown")
    found = shutil.which(tool, path=path_env)
    if not found and path_env is None and tool in KNOWN_CONSOLE_SCRIPTS:
        scripts_dir = sysconfig.get_path("scripts")
        if scripts_dir:
            found = shutil.which(tool, path=scripts_dir)

    if not found:
        return {
            "state": "blocked",
            "reason": f"required tool {tool!r} for ecosystem {resolved_ecosystem!r} is absent from PATH",
            "missing_tool": tool,
            "ecosystem": resolved_ecosystem,
        }
    return {
        "state": "ok",
        "tool": tool,
        "ecosystem": resolved_ecosystem,
    }
