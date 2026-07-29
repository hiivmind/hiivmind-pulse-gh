#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Propose-only CLI driver for marketplace entry version drift audits.

Consumes CONFIG_DIR/marketplace-sync.yaml bindings, fetches remote evidence
(marketplace doc, release list, HEAD SHA) via a gh runner seam, and hands
evidence to marketplace_sync.build_result to produce a kind: marketplace-sync
result file. Self-validates using validate_result.py. Propose-only.
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

from lib.pulse.scripts import marketplace_sync, mutation_plan, validate_result

Runner = Callable[..., "subprocess.CompletedProcess[str] | object"]


def default_runner(argv: list[str], cwd: str | Path | None = None):
    """Real process runner for gh calls. Injected seam for tests."""
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _failed(result: Any) -> bool:
    return getattr(result, "returncode", 1) != 0


def _stdout(result: Any) -> str:
    return getattr(result, "stdout", "") or ""


def _write_and_validate_result(result_path: Path, data: dict[str, Any]) -> int:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(yaml.dump(data, sort_keys=False))

    errors = validate_result.validate(data, "marketplace-sync")
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
        "kind": "marketplace-sync",
        "workspace": workspace_name,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "bindings_scanned": 0,
        "in_sync": 0,
        "drift": 0,
        "missing_entry": 0,
        "unknown": 0,
        "not_applicable": 0,
        "findings": [],
        "proposals": [],
        "proposed_actions": [],
        "errors": [error_message],
    }


def fetch_remote_evidence(
    bindings: list[dict[str, Any]],
    runner: Runner,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    releases_by_repo: dict[str, Any] = {}
    docs_by_repo: dict[str, Any] = {}
    head_shas: dict[str, Any] = {}

    for b in bindings:
        repo = b.get("repo")
        marketplace_repo = b.get("marketplace_repo")
        marketplace_file = b.get("marketplace_file")

        if isinstance(repo, str) and repo and repo not in releases_by_repo:
            rel_res = runner([
                "gh", "release", "list",
                "--json", "tagName,isPrerelease,isDraft",
                "--limit", "100",
                "--repo", repo,
            ], None)
            if not _failed(rel_res):
                try:
                    releases_by_repo[repo] = json.loads(_stdout(rel_res))
                except Exception:
                    releases_by_repo[repo] = None
            else:
                releases_by_repo[repo] = None

        if (
            isinstance(marketplace_repo, str) and marketplace_repo and
            isinstance(marketplace_file, str) and marketplace_file and
            marketplace_repo not in docs_by_repo
        ):
            doc_res = runner([
                "gh", "api", f"repos/{marketplace_repo}/contents/{marketplace_file}",
            ], None)
            if not _failed(doc_res):
                try:
                    raw_out = _stdout(doc_res).strip()
                    parsed = json.loads(raw_out)
                    if isinstance(parsed, dict) and "content" in parsed:
                        import base64
                        decoded = base64.b64decode(parsed["content"]).decode("utf-8")
                        docs_by_repo[marketplace_repo] = json.loads(decoded)
                    elif isinstance(parsed, dict) and "plugins" in parsed:
                        docs_by_repo[marketplace_repo] = parsed
                    else:
                        docs_by_repo[marketplace_repo] = None
                except Exception:
                    docs_by_repo[marketplace_repo] = None
            else:
                docs_by_repo[marketplace_repo] = None

        if (
            isinstance(marketplace_repo, str) and marketplace_repo and
            marketplace_repo not in head_shas
        ):
            sha_res = runner([
                "gh", "api", f"repos/{marketplace_repo}/commits/HEAD", "--jq", ".sha",
            ], None)
            if not _failed(sha_res):
                sha_str = _stdout(sha_res).strip()
                head_shas[marketplace_repo] = sha_str if sha_str else None
            else:
                head_shas[marketplace_repo] = None

    return releases_by_repo, docs_by_repo, head_shas


def load_transformation_registry(workspace: Path) -> mutation_plan.TransformationRegistry:
    config_registry = workspace / ".hiivmind" / "github" / "transformations.yaml"
    if config_registry.exists():
        return mutation_plan.load_registry(config_registry)

    repo_root = Path(__file__).resolve().parents[3]
    template_registry = repo_root / "templates" / "transformations.yaml.template"
    if template_registry.exists():
        return mutation_plan.load_registry(template_registry)

    # Fallback minimal registry
    return mutation_plan.load_registry({
        "transformations": {
            "marketplace-entry-update": {
                "id": "marketplace-entry-update",
                "command_argv": ["python3", "-m", "lib.pulse.scripts.marketplace_sync"],
                "applies_to": ["always"],
                "validation": {"kind": "none"},
                "allow_scheduled": False,
            }
        }
    })


def run_driver(
    workspace: Path,
    repo_filter: str | None,
    result_path: Path | None,
    mode: str = "scheduled",
    runner: Runner | None = None,
) -> int:
    run = runner or default_runner
    config_dir = workspace / ".hiivmind" / "github"

    # Determine default result path
    if result_path is not None:
        target_result_path = result_path
    elif config_dir.exists():
        target_result_path = config_dir / "marketplace-sync-result.yaml"
    else:
        target_result_path = Path.cwd() / "marketplace-sync-result.yaml"

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

    # Read bindings
    sync_config_path = config_dir / "marketplace-sync.yaml"
    bindings: list[dict[str, Any]] = []
    if sync_config_path.exists():
        try:
            sync_data = yaml.safe_load(sync_config_path.read_text()) or {}
            if isinstance(sync_data, dict) and isinstance(sync_data.get("bindings"), list):
                bindings = sync_data["bindings"]
        except Exception:
            bindings = []

    # Filter bindings if --repo passed
    if repo_filter:
        matched = []
        for b in bindings:
            if not isinstance(b, dict):
                continue
            r = b.get("repo")
            pid = b.get("plugin_id")
            if r == repo_filter or (isinstance(r, str) and r.endswith("/" + repo_filter)) or pid == repo_filter:
                matched.append(b)
        if not matched:
            err_msg = f"unknown repo: {repo_filter}"
            abort_data = _build_abort_result(login, actor, err_msg)
            _write_and_validate_result(target_result_path, abort_data)
            return 1
        bindings = matched

    releases_by_repo, docs_by_repo, head_shas = fetch_remote_evidence(bindings, run)
    registry = load_transformation_registry(workspace)

    result_data = marketplace_sync.build_result(
        bindings,
        releases_by_repo=releases_by_repo,
        docs_by_repo=docs_by_repo,
        head_shas=head_shas,
        actor=actor,
        registry=registry,
        mode=mode,
        workspace=login,
    )

    val_code = _write_and_validate_result(target_result_path, result_data)
    if val_code != 0:
        return val_code

    print(
        f"marketplace-sync: bindings={result_data['bindings_scanned']} "
        f"in_sync={result_data['in_sync']} drift={result_data['drift']} "
        f"missing={result_data['missing_entry']} unknown={result_data['unknown']} "
        f"not_applicable={result_data['not_applicable']}"
    )
    return 0


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--repo", default=None, help="Filter by plugin repo full or short name")
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
