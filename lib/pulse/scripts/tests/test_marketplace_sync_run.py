"""Tests for the marketplace-sync CLI driver layer (marketplace_sync_run.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts import validate_result


# Helpers for setting up fake workspace roots
def create_test_workspace(
    tmp_path: Path,
    login: str = "acme-corp",
    bindings: list[dict] | None = None,
) -> Path:
    ws = tmp_path / "workspace"
    config_dir = ws / ".hiivmind" / "github"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_yaml = config_dir / "config.yaml"
    config_yaml.write_text(yaml.dump({"workspace": {"login": login}}))

    if bindings is None:
        bindings = [
            {
                "plugin_id": "acme-addon",
                "repo": "acme/acme-addon",
                "marketplace_repo": "acme/marketplace",
                "marketplace_file": ".claude-plugin/marketplace.json",
            }
        ]

    sync_yaml = config_dir / "marketplace-sync.yaml"
    sync_yaml.write_text(yaml.dump({"bindings": bindings}))

    return ws


def test_driver_missing_workspace_aborts_and_validates(tmp_path):
    from lib.pulse.scripts import marketplace_sync_run  # type: ignore

    non_existent = tmp_path / "non_existent_workspace"
    result_path = tmp_path / "result.yaml"

    rc = marketplace_sync_run.main_cli([
        "--workspace", str(non_existent),
        "--result", str(result_path),
    ])

    assert rc != 0
    assert result_path.exists()

    data = yaml.safe_load(result_path.read_text())
    errors = validate_result.validate(data, "marketplace-sync")
    assert errors == []
    assert len(data["errors"]) > 0
    assert "not a workspace root" in data["errors"][0]


def test_driver_unresolvable_repo_aborts_and_validates(tmp_path):
    from lib.pulse.scripts import marketplace_sync_run  # type: ignore

    ws = create_test_workspace(tmp_path)
    result_path = tmp_path / "result.yaml"

    rc = marketplace_sync_run.main_cli([
        "--workspace", str(ws),
        "--repo", "nonexistent-repo-name",
        "--result", str(result_path),
    ])

    assert rc != 0
    assert result_path.exists()

    data = yaml.safe_load(result_path.read_text())
    errors = validate_result.validate(data, "marketplace-sync")
    assert errors == []
    assert len(data["errors"]) > 0
    assert "unknown repo" in data["errors"][0]


def test_driver_valid_run_with_fake_runner(tmp_path):
    from lib.pulse.scripts import marketplace_sync_run  # type: ignore

    ws = create_test_workspace(tmp_path)
    result_path = tmp_path / "result.yaml"

    # Fake runner for gh commands
    def fake_runner(argv, cwd=None):
        cmd = " ".join(argv)
        if "contents" in cmd:
            # Marketplace doc
            doc_content = {
                "plugins": [
                    {"name": "acme-addon", "version": "1.0.0"}
                ]
            }
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(doc_content), stderr=""
            )
        elif "release list" in cmd:
            releases = [
                {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False}
            ]
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(releases), stderr=""
            )
        elif "commits/HEAD" in cmd:
            return subprocess.CompletedProcess(
                argv, 0, stdout="deadbeef9999", stderr=""
            )
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="command not found")

    rc = marketplace_sync_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="interactive",
        runner=fake_runner,
    )

    assert rc == 0
    assert result_path.exists()

    data = yaml.safe_load(result_path.read_text())
    errors = validate_result.validate(data, "marketplace-sync")
    assert errors == []
    assert data["bindings_scanned"] == 1
    assert data["drift"] == 1
    assert len(data["proposals"]) == 1
    assert data["proposals"][0]["binding"] == "acme-addon"
