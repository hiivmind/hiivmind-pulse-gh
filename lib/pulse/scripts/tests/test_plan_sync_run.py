"""Tests for plan_sync_run CLI driver and build_result gating extension."""

import json
from pathlib import Path
import subprocess
import sys
import pytest
import yaml

from lib.pulse.scripts import mutation_plan, plan_sync, plan_sync_run, validate_result
from lib.pulse.scripts.tests.test_plan_sync_acceptance import (
    ACTOR,
    BASE,
    CURRENT_BLOB,
    PATH,
    REPO,
    SnapshotRunner,
    _binding,
    _document,
    _github,
    _snapshot,
)


def load_test_registry():
    repo_root = Path(__file__).resolve().parents[4]
    return mutation_plan.load_registry(repo_root / "templates" / "transformations.yaml.template")


def test_build_result_scheduled_mode_gates_doc_patch_to_finding():
    # Setup document change from GitHub (requires doc_patch for sync.base) or GitHub change requiring doc_patch
    # In test acceptance, BASE with GitHub state: closed causes doc_patches: 1
    snap = _snapshot(BASE, Path("/tmp"), github_values=BASE | {"state": "closed"})
    registry = load_test_registry()

    # In interactive mode, doc-patch proposal is generated
    res_interactive = plan_sync.build_result(
        snap,
        workspace="acme",
        run_at="2026-07-21T00:00:00Z",
        actor={"gh_login": "octocat", "machine": "test-mac", "mode": "interactive"},
        registry=registry,
        mode="interactive",
    )
    assert res_interactive["doc_patches"] == 1
    assert len(res_interactive["proposals"]) == 1
    assert res_interactive["proposals"][0]["transformation"] == "plan-sync-doc-patch"

    # In scheduled mode, doc-patch is gated to finding (plan-sync-doc-patch has allow_scheduled: false)
    res_scheduled = plan_sync.build_result(
        snap,
        workspace="acme",
        run_at="2026-07-21T00:00:00Z",
        actor={"gh_login": "octocat", "machine": "test-mac", "mode": "scheduled"},
        registry=registry,
        mode="scheduled",
    )
    assert res_scheduled["doc_patches"] == 0
    assert len(res_scheduled["proposals"]) == 0
    gated_findings = [f for f in res_scheduled["findings"] if f["kind"] == "gated_transformation"]
    assert len(gated_findings) == 1
    assert gated_findings[0]["repo"] == REPO


def test_plan_sync_run_cli_end_to_end(tmp_path):
    # Setup mock workspace
    config_dir = tmp_path / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("workspace:\n  login: acme\n")
    (config_dir / "plan-sync.yaml").write_text(yaml.dump({"docs": [_binding()]}))

    mock_snap = _snapshot(BASE, tmp_path, github_values=BASE | {"state": "closed"})

    def mock_collect(bindings, workdir=None, runner=None, gh_api=None):
        return mock_snap

    result_path = tmp_path / "result.yaml"
    ret = plan_sync_run.run_driver(
        workspace=tmp_path,
        repo_filter=None,
        result_path=result_path,
        mode="interactive",
        collector=mock_collect,
    )

    assert ret == 0
    assert result_path.exists()
    data = yaml.safe_load(result_path.read_text())
    assert data["kind"] == "plan-sync"
    assert data["workspace"] == "acme"
    assert data["doc_patches"] == 1
    assert validate_result.validate(data, "plan-sync") == []


def test_plan_sync_run_cli_abort_on_invalid_workspace(tmp_path):
    result_path = tmp_path / "result.yaml"
    ret = plan_sync_run.run_driver(
        workspace=tmp_path / "nonexistent",
        repo_filter=None,
        result_path=result_path,
        mode="scheduled",
    )

    assert ret == 1
    assert result_path.exists()
    data = yaml.safe_load(result_path.read_text())
    assert data["kind"] == "plan-sync"
    assert len(data["errors"]) > 0
    assert validate_result.validate(data, "plan-sync") == []
