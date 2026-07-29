#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Propose-only CLI driver for generated-artifact binding audits.

Consumes CONFIG_DIR/generated.yaml bindings, snapshots remote template tree
and output blob SHAs via generated_artifacts.collect, and hands evidence to
generated_artifacts.build_result to produce a kind: generated-artifact
result file. Self-validates using validate_result.py. Propose-only.
"""

from __future__ import annotations

import argparse
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from lib.pulse.scripts import (
    generated_artifacts,
    generator_dispatch,
    mutation_plan,
    validate_result,
)

Collector = Callable[..., Any]


def _write_and_validate_result(result_path: Path, data: dict[str, Any]) -> int:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(yaml.dump(data, sort_keys=False))

    errors = validate_result.validate(data, "generated-artifact")
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
        "kind": "generated-artifact",
        "workspace": workspace_name,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "bindings_audited": 0,
        "states": {},
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
            "regenerate-from-template": {
                "id": "regenerate-from-template",
                "command_argv": ["nave", "generate", "--from-template"],
                "applies_to": ["always"],
                "validation": {"kind": "none"},
                "allow_scheduled": False,
            }
        }
    })


def load_generators(
    workspace: Path,
    registry: mutation_plan.TransformationRegistry,
) -> dict[str, generator_dispatch.Generator]:
    config_gens = workspace / ".hiivmind" / "github" / "generators.yaml"
    if config_gens.exists():
        return generator_dispatch.load_generators(config_gens, registry)

    repo_root = Path(__file__).resolve().parents[3]
    template_gens = repo_root / "templates" / "generators.yaml.template"
    if template_gens.exists():
        return generator_dispatch.load_generators(template_gens, registry)

    return {}


def run_driver(
    workspace: Path,
    repo_filter: str | None,
    result_path: Path | None,
    mode: str = "scheduled",
    collector: Collector | None = None,
) -> int:
    collect = collector or generated_artifacts.collect
    config_dir = workspace / ".hiivmind" / "github"

    if result_path is not None:
        target_result_path = result_path
    elif config_dir.exists():
        target_result_path = config_dir / "generated-artifact-result.yaml"
    else:
        target_result_path = Path.cwd() / "generated-artifact-result.yaml"

    actor = {
        "gh_login": "unknown",
        "machine": platform.node() or "local",
        "mode": mode,
    }

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

    manifest_path = config_dir / "generated.yaml"
    if not manifest_path.exists():
        err_msg = f"generated.yaml not found: {manifest_path}"
        abort_data = _build_abort_result(login, actor, err_msg)
        _write_and_validate_result(target_result_path, abort_data)
        return 1

    try:
        manifest_data = yaml.safe_load(manifest_path.read_text()) or {}
    except Exception as exc:
        err_msg = f"could not load generated.yaml: {exc}"
        abort_data = _build_abort_result(login, actor, err_msg)
        _write_and_validate_result(target_result_path, abort_data)
        return 1

    if not isinstance(manifest_data, dict):
        manifest_data = {"bindings": []}

    bindings: list[dict[str, Any]] = []
    raw_bindings = manifest_data.get("bindings")
    if isinstance(raw_bindings, list):
        bindings = [b for b in raw_bindings if isinstance(b, dict)]

    if repo_filter:
        matched: list[dict[str, Any]] = []
        for b in bindings:
            source = b.get("source")
            bid = b.get("id")
            if (
                source == repo_filter
                or (isinstance(source, str) and source.endswith("/" + repo_filter))
                or bid == repo_filter
            ):
                matched.append(b)
        if not matched:
            err_msg = f"unknown repo: {repo_filter}"
            abort_data = _build_abort_result(login, actor, err_msg)
            _write_and_validate_result(target_result_path, abort_data)
            return 1
        bindings = matched

    prepared_manifest = dict(manifest_data)
    prepared_manifest["bindings"] = bindings

    snapshot = collect(prepared_manifest, workdir=workspace)
    registry = load_transformation_registry(workspace)
    generators = load_generators(workspace, registry)

    result_data = generated_artifacts.build_result(
        prepared_manifest,
        snapshot,
        generators=generators,
        registry=registry,
        actor=actor,
        mode=mode,
    )
    # Authoritative workspace login from config, not actor default.
    result_data["workspace"] = login

    val_code = _write_and_validate_result(target_result_path, result_data)
    if val_code != 0:
        return val_code

    drift = sum(1 for s in (result_data.get("states") or {}).values() if s == "template-drift")
    print(
        f"generated-artifact-audit: bindings={result_data['bindings_audited']} "
        f"drift={drift} proposals={len(result_data.get('proposals') or [])}"
    )
    # Non-zero when the library recorded structural errors (malformed manifest).
    if result_data.get("errors"):
        return 1
    return 0


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--repo",
        default=None,
        help="Filter by binding source full/short name or binding id",
    )
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
