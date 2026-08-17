#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Propose-only CLI driver for GitHub-bound Markdown plan synchronization audits.

Consumes CONFIG_DIR/plan-sync.yaml bindings, snapshots pushed documents and
GitHub issues via plan_sync_snapshot.collect, hands snapshot evidence to
plan_sync.build_result to produce a kind: plan-sync result file.
Self-validates using validate_result.py. Propose-only.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from lib.pulse.scripts import (
    mutation_plan,
    plan_sync,
    plan_sync_snapshot,
    validate_result,
)
from lib.pulse.scripts.overlay_content import default_gh_api

Collector = Callable[..., Any]


def _write_and_validate_result(result_path: Path, data: dict[str, Any]) -> int:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(yaml.dump(data, sort_keys=False))

    errors = validate_result.validate(data, "plan-sync")
    if errors:
        for err in errors:
            print(f"validation error: {err}", file=sys.stderr)
        return 1
    return 0


def _build_abort_result(
    workspace_name: str,
    actor: dict[str, Any],
    error_message: str,
) -> dict[str, Any]:
    return {
        "contract_version": 1,
        "kind": "plan-sync",
        "workspace": workspace_name,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "docs_scanned": 0,
        "in_sync": 0,
        "doc_patches": 0,
        "github_patches": 0,
        "conflicts": 0,
        "excluded": 0,
        "findings": [],
        "proposals": [],
        "proposed_actions": [],
        "errors": [error_message],
    }


def load_transformation_registry(workspace: Path) -> mutation_plan.TransformationRegistry:
    config_registry = workspace / ".hiivmind" / "github" / "transformations.yaml"
    if config_registry.exists():
        return mutation_plan.load_registry(config_registry)

    repo_root = Path(__file__).resolve().parents[3]
    template_registry = repo_root / "templates" / "transformations.yaml.template"
    if template_registry.exists():
        return mutation_plan.load_registry(template_registry)

    return mutation_plan.load_registry({
        "transformations": {
            "plan-sync-doc-patch": {
                "id": "plan-sync-doc-patch",
                "command_argv": [
                    "pulse-apply-doc-patch",
                    "--patch",
                    ".hiivmind/plan-sync-patch.yaml",
                ],
                "applies_to": ["always"],
                "validation": {"kind": "paths_changed"},
                "allow_scheduled": False,
            }
        }
    })


def run_driver(
    workspace: Path,
    repo_filter: str | None,
    result_path: Path | None,
    mode: str = "scheduled",
    collector: Collector | None = None,
) -> int:
    collect = collector or plan_sync_snapshot.collect
    config_dir = workspace / ".hiivmind" / "github"

    # Determine default result path
    if result_path is not None:
        target_result_path = result_path
    elif config_dir.exists():
        target_result_path = config_dir / "plan-sync-result.yaml"
    else:
        target_result_path = Path.cwd() / "plan-sync-result.yaml"

    actor = {
        "gh_login": "unknown",
        "machine": platform.node() or "local",
        "mode": mode,
    }

    # Validate workspace
    if not workspace.exists() or not (config_dir / "config.yaml").exists():
        err_msg = f"not a workspace root: {workspace}"
        abort_data = _build_abort_result("unknown", actor, err_msg)
        _write_and_validate_result(target_result_path, abort_data)
        return 1

    try:
        config_data = yaml.safe_load((config_dir / "config.yaml").read_text()) or {}
    except Exception:
        config_data = {}

    ws_cfg = config_data.get("workspace")
    if isinstance(ws_cfg, dict):
        login = str(ws_cfg.get("login") or "unknown")
    elif isinstance(ws_cfg, str):
        login = ws_cfg
    else:
        login = "unknown"

    actor["gh_login"] = login

    # Read bindings — missing plan-sync.yaml is a hard abort (skill Phase 1 step 5)
    sync_config_path = config_dir / "plan-sync.yaml"
    if not sync_config_path.exists():
        err_msg = f"plan-sync.yaml not found: {sync_config_path}"
        abort_data = _build_abort_result(login, actor, err_msg)
        _write_and_validate_result(target_result_path, abort_data)
        return 1

    bindings: list[dict[str, Any]] = []
    try:
        sync_data = yaml.safe_load(sync_config_path.read_text()) or {}
        if isinstance(sync_data, dict) and isinstance(sync_data.get("docs"), list):
            bindings = sync_data["docs"]
    except Exception:
        bindings = []

    # Filter bindings if --repo passed
    if repo_filter:
        matched = []
        for b in bindings:
            if not isinstance(b, dict):
                continue
            r = b.get("repo")
            bid = b.get("id")
            if r == repo_filter or (isinstance(r, str) and r.endswith("/" + repo_filter)) or bid == repo_filter:
                matched.append(b)
        if not matched:
            err_msg = f"unknown repo: {repo_filter}"
            abort_data = _build_abort_result(login, actor, err_msg)
            _write_and_validate_result(target_result_path, abort_data)
            return 1
        bindings = matched

    snapshot = collect(bindings, workdir=workspace, gh_api=default_gh_api)
    registry = load_transformation_registry(workspace)

    result_data = plan_sync.build_result(
        snapshot,
        workspace=login,
        run_at=datetime.now(timezone.utc).isoformat(),
        actor=actor,
        registry=registry,
        mode=mode,
    )

    val_code = _write_and_validate_result(target_result_path, result_data)
    if val_code != 0:
        return val_code

    print(
        f"plan-sync: docs={result_data['docs_scanned']} "
        f"in_sync={result_data['in_sync']} doc={result_data['doc_patches']} "
        f"github={result_data['github_patches']} conflicts={result_data['conflicts']} "
        f"excluded={result_data['excluded']}"
    )
    return 0


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--repo", default=None, help="Filter by document repo full or short name")
    parser.add_argument("--result", default=None, type=Path, help="Output result YAML path")
    parser.add_argument("--mode", choices=["scheduled", "interactive"], default="scheduled")

    args = parser.parse_args(argv)

    return run_driver(
        workspace=args.workspace,
        repo_filter=args.repo,
        result_path=args.result,
        mode=args.mode,
    )


if __name__ == "__main__":
    sys.exit(main_cli())
