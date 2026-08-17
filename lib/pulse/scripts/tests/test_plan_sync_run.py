"""Tests for plan_sync_run CLI driver and build_result gating extension."""

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts import mutation_plan, plan_sync, plan_sync_run, plan_sync_snapshot, validate_result
from lib.pulse.scripts.tests.test_plan_sync_acceptance import (
    BASE,
    REPO,
    _binding,
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


def test_gated_document_does_not_leak_into_later_in_sync_counting(tmp_path):
    """Per-document gate signal must not poison later documents' in_sync count.

    Forces the second document through the late apply-plans path (state
    'changed' with a noop reconciliation) so the cumulative-findings leak
    would have wrongly excluded it from in_sync under the old global check.
    """
    registry = load_test_registry()
    gated_snap = _snapshot(BASE, tmp_path, github_values=BASE | {"state": "closed"})
    in_sync_snap = _snapshot(BASE, tmp_path / "b", github_values=BASE)

    # Second doc is genuinely in-sync content-wise; force late path by state.
    later = replace(in_sync_snap.documents[0], state="changed")
    combined = plan_sync_snapshot.SyncSnapshot(
        (gated_snap.documents[0], later),
        gated_snap.findings + in_sync_snap.findings,
    )

    res = plan_sync.build_result(
        combined,
        workspace="acme",
        run_at="2026-07-21T00:00:00Z",
        actor={"gh_login": "octocat", "machine": "test-mac", "mode": "scheduled"},
        registry=registry,
        mode="scheduled",
    )

    assert res["docs_scanned"] == 2
    assert res["doc_patches"] == 0
    gated_findings = [f for f in res["findings"] if f["kind"] == "gated_transformation"]
    assert len(gated_findings) == 1
    # The later noop document must still count as in_sync despite prior gate.
    assert res["in_sync"] == 1


def test_build_apply_plans_gates_doc_but_keeps_validated_github_mutation():
    """Gating lives in build_apply_plans; github_mutation still uses validated path."""
    registry = load_test_registry()
    reconciliation = plan_sync.ReconciliationPlan(
        {"state": "closed"},
        {"title": "Document title"},
        {"state": "closed", "title": "Document title"},
        (),
        {"state": "closed"},
    )
    binding = {
        "id": "widget-plan",
        "repo": "acme/docs",
        "branch": "main",
        "path": "plans/widget.md",
        "sync": {"issue": {"repo": "acme/widgets", "number": 42}},
    }
    snapshot = {"repo": "acme/docs", "head": "head-at-snapshot", "blob": "blob-at-snapshot"}
    actor = {"gh_login": "octocat", "machine": "test-mac", "mode": "scheduled"}

    plans = plan_sync.build_apply_plans(
        reconciliation, binding, snapshot, actor, registry=registry
    )

    assert plans.repo_mutation is None
    assert plans.doc_patch is None
    assert plans.gated_transformation is not None
    assert "not allowed in scheduled mode" in plans.gated_transformation
    assert plans.github_mutation is not None
    assert plans.github_mutation["repo"] == "acme/widgets"
    assert plans.github_mutation["number"] == 42
    assert plans.github_mutation["patch"] == {"title": "Document title"}


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


def test_plan_sync_run_cli_abort_on_missing_plan_sync_yaml(tmp_path):
    config_dir = tmp_path / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("workspace:\n  login: acme\n")
    # deliberately no plan-sync.yaml

    result_path = tmp_path / "result.yaml"
    ret = plan_sync_run.run_driver(
        workspace=tmp_path,
        repo_filter=None,
        result_path=result_path,
        mode="scheduled",
    )

    assert ret == 1
    assert result_path.exists()
    data = yaml.safe_load(result_path.read_text())
    assert data["kind"] == "plan-sync"
    assert data["workspace"] == "acme"
    assert len(data["errors"]) == 1
    assert "plan-sync.yaml not found" in data["errors"][0]
    assert str(config_dir / "plan-sync.yaml") in data["errors"][0]
    assert validate_result.validate(data, "plan-sync") == []


def test_plan_sync_run_wires_real_gh_api_into_real_collector(tmp_path, monkeypatch):
    """Regression: run_driver's real (non-injected) collector call must wire a
    real gh_api seam. plan_sync_snapshot.collect() defaults gh_api to None,
    and _github_snapshot() unconditionally fails every GitHub read with
    "GitHub API reader is unavailable" when gh_api is None — so an unwired
    driver can never fetch real issue evidence, regardless of how correct the
    binding config is. Bindings themselves are irrelevant here: an empty
    docs[] list still exercises the real collect() call and its gh_api kwarg.
    """
    config_dir = tmp_path / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(yaml.dump({"workspace": {"login": "acme"}}))
    (config_dir / "plan-sync.yaml").write_text(yaml.dump({"docs": []}))

    captured = {}

    def fake_collect(bindings, workdir=None, runner=None, gh_api=None):
        captured["gh_api"] = gh_api
        return plan_sync_snapshot.SyncSnapshot((), ())

    monkeypatch.setattr(plan_sync_snapshot, "collect", fake_collect)

    ret = plan_sync_run.run_driver(
        workspace=tmp_path, repo_filter=None, result_path=tmp_path / "result.yaml",
    )

    assert ret == 0
    assert captured["gh_api"] is not None
    assert callable(captured["gh_api"])
