"""F10 end-to-end acceptance matrix: trigger → driver → validated result.

Composes the REAL public entry points (run_driver / evaluate_fleet) with
injected seams so the suite stays network-free. Covers the three F10
propose drivers plus the overlay healthcheck path, including one
scheduled-gated case per propose driver proving allow_scheduled: false
yields a proposed-action / gated finding and no runnable proposal.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from lib.pulse.scripts import (
    generated_artifact_run,
    marketplace_sync_run,
    plan_sync_run,
    validate_result,
)
from lib.pulse.scripts.healthcheck_dispatch import evaluate_fleet
from lib.pulse.scripts.tests.test_generated_artifacts import binding as ga_binding
from lib.pulse.scripts.tests.test_generated_artifacts import snapshot_for
from lib.pulse.scripts.tests.test_healthcheck_dispatch import (
    _overlay_mixed_profiles,
    _valid_plugin_contents,
)
from lib.pulse.scripts.tests.test_plan_sync_acceptance import (
    BASE,
    _binding as plan_binding,
    _snapshot as plan_snapshot,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_REGISTRY = REPO_ROOT / "templates" / "transformations.yaml.template"
RUN_AT = "2026-07-21T12:00:00Z"


# ---------------------------------------------------------------------------
# Marketplace-sync
# ---------------------------------------------------------------------------


def _marketplace_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "mkt-ws"
    config_dir = ws / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        yaml.dump({"workspace": {"login": "acme-corp"}})
    )
    (config_dir / "marketplace-sync.yaml").write_text(
        yaml.dump(
            {
                "bindings": [
                    {
                        "plugin_id": "acme-addon",
                        "repo": "acme/acme-addon",
                        "marketplace_repo": "acme/marketplace",
                        "marketplace_file": ".claude-plugin/marketplace.json",
                    }
                ]
            }
        )
    )
    (config_dir / "transformations.yaml").write_text(TEMPLATE_REGISTRY.read_text())
    return ws


def _marketplace_drift_runner(argv, cwd=None):
    """Hermetic gh seam: marketplace pins 1.0.0, newest stable is 2.0.0."""
    cmd = " ".join(str(a) for a in argv)
    if "contents" in cmd:
        doc = {"plugins": [{"name": "acme-addon", "version": "1.0.0"}]}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(doc), stderr="")
    if "release list" in cmd:
        releases = [
            {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False}
        ]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(releases), stderr=""
        )
    if "commits/HEAD" in cmd:
        return subprocess.CompletedProcess(argv, 0, stdout="deadbeef9999", stderr="")
    return subprocess.CompletedProcess(argv, 1, stdout="", stderr="unexpected")


def test_marketplace_sync_interactive_trigger_to_validated_result(tmp_path):
    ws = _marketplace_workspace(tmp_path)
    result_path = tmp_path / "marketplace-sync-result.yaml"

    rc = marketplace_sync_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="interactive",
        runner=_marketplace_drift_runner,
    )

    assert rc == 0
    data = yaml.safe_load(result_path.read_text())
    assert validate_result.validate(data, "marketplace-sync") == []
    assert data["kind"] == "marketplace-sync"
    assert data["bindings_scanned"] == 1
    assert data["drift"] == 1
    assert len(data["proposals"]) == 1
    assert data["proposals"][0]["binding"] == "acme-addon"
    assert data["proposals"][0]["transformation"] == "marketplace-entry-update"


def test_marketplace_sync_scheduled_gates_allow_scheduled_false(tmp_path):
    ws = _marketplace_workspace(tmp_path)
    result_path = tmp_path / "marketplace-sync-scheduled.yaml"

    rc = marketplace_sync_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="scheduled",
        runner=_marketplace_drift_runner,
    )

    assert rc == 0
    data = yaml.safe_load(result_path.read_text())
    assert validate_result.validate(data, "marketplace-sync") == []
    assert data["bindings_scanned"] == 1
    assert data["drift"] == 1
    assert data["proposals"] == [], "scheduled must emit no runnable proposals"
    assert any(f.get("kind") == "gated_transformation" for f in data["findings"])
    assert data["proposed_actions"], "gated path must record a proposed_action"


# ---------------------------------------------------------------------------
# Plan-sync
# ---------------------------------------------------------------------------


def _plan_sync_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "plan-ws"
    config_dir = ws / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        yaml.dump({"workspace": {"login": "acme"}})
    )
    (config_dir / "plan-sync.yaml").write_text(
        yaml.dump({"docs": [plan_binding()]})
    )
    (config_dir / "transformations.yaml").write_text(TEMPLATE_REGISTRY.read_text())
    return ws


def test_plan_sync_interactive_trigger_to_validated_result(tmp_path):
    ws = _plan_sync_workspace(tmp_path)
    result_path = tmp_path / "plan-sync-result.yaml"
    # GitHub closed while document still open → doc_patch proposal.
    mock_snap = plan_snapshot(BASE, tmp_path, github_values=BASE | {"state": "closed"})

    def mock_collect(bindings, workdir=None, runner=None, gh_api=None):
        return mock_snap

    rc = plan_sync_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="interactive",
        collector=mock_collect,
    )

    assert rc == 0
    data = yaml.safe_load(result_path.read_text())
    assert validate_result.validate(data, "plan-sync") == []
    assert data["kind"] == "plan-sync"
    assert data["docs_scanned"] == 1
    assert data["doc_patches"] == 1
    assert len(data["proposals"]) == 1
    assert data["proposals"][0]["transformation"] == "plan-sync-doc-patch"


def test_plan_sync_scheduled_gates_allow_scheduled_false(tmp_path):
    ws = _plan_sync_workspace(tmp_path)
    result_path = tmp_path / "plan-sync-scheduled.yaml"
    mock_snap = plan_snapshot(BASE, tmp_path, github_values=BASE | {"state": "closed"})

    def mock_collect(bindings, workdir=None, runner=None, gh_api=None):
        return mock_snap

    rc = plan_sync_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="scheduled",
        collector=mock_collect,
    )

    assert rc == 0
    data = yaml.safe_load(result_path.read_text())
    assert validate_result.validate(data, "plan-sync") == []
    assert data["doc_patches"] == 0
    assert data["proposals"] == [], "scheduled must emit no runnable proposals"
    gated = [f for f in data["findings"] if f.get("kind") == "gated_transformation"]
    assert len(gated) == 1
    assert data.get("proposed_actions") is not None


# ---------------------------------------------------------------------------
# Generated-artifact
# ---------------------------------------------------------------------------


def _generated_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "gen-ws"
    config_dir = ws / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        yaml.dump({"workspace": {"login": "acme"}})
    )
    (config_dir / "generated.yaml").write_text(
        yaml.dump({"bindings": [ga_binding()]}, sort_keys=False)
    )
    (config_dir / "generators.yaml").write_text(
        yaml.dump(
            {
                "generators": {
                    "readme-from-template": {
                        "id": "readme-from-template",
                        "applies_to": ["always"],
                        "transformation": "regenerate-from-template",
                        "source_paths": ["templates/repo-readme.md"],
                        "output_paths": ["README.md", "docs/**/*.md"],
                        "validation": {"kind": "none"},
                    }
                }
            }
        )
    )
    (config_dir / "transformations.yaml").write_text(TEMPLATE_REGISTRY.read_text())
    return ws


def _drift_snapshot():
    snap = snapshot_for(trees={"templates/repo-readme.md": "tree2222"})
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"
    return snap


def test_generated_artifact_interactive_trigger_to_validated_result(tmp_path):
    ws = _generated_workspace(tmp_path)
    result_path = tmp_path / "generated-artifact-result.yaml"
    snap = _drift_snapshot()

    rc = generated_artifact_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="interactive",
        collector=lambda *a, **k: snap,
    )

    assert rc == 0
    data = yaml.safe_load(result_path.read_text())
    assert validate_result.validate(data, "generated-artifact") == []
    assert data["kind"] == "generated-artifact"
    assert data["bindings_audited"] == 1
    assert data["states"]["widget-readme"] == "template-drift"
    assert len(data["proposals"]) == 1
    assert data["proposals"][0]["transformation"] == "regenerate-from-template"


def test_generated_artifact_scheduled_gates_allow_scheduled_false(tmp_path):
    ws = _generated_workspace(tmp_path)
    result_path = tmp_path / "generated-artifact-scheduled.yaml"
    snap = _drift_snapshot()

    rc = generated_artifact_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="scheduled",
        collector=lambda *a, **k: snap,
    )

    assert rc == 0
    data = yaml.safe_load(result_path.read_text())
    assert validate_result.validate(data, "generated-artifact") == []
    assert data["states"]["widget-readme"] == "template-drift"
    assert data["proposals"] == [], "scheduled must emit no runnable proposals"
    gated = [f for f in data["findings"] if f.get("kind") == "gated_transformation"]
    assert len(gated) == 1
    assert data["proposed_actions"], "gated path must record a proposed_action"


# ---------------------------------------------------------------------------
# Overlay healthcheck (evaluate_fleet → skill-style envelope → validate)
# ---------------------------------------------------------------------------


def test_overlay_healthcheck_trigger_to_validated_result(tmp_path):
    """Fixture-driven overlay path: real evaluate_fleet → validated envelope.

    Mirrors the skill's wrap step around healthcheck_dispatch output so the
    acceptance matrix proves trigger → dispatch → validated healthcheck
    result without network (file_contents pre-attached; no --fetch-overlay-content).
    """
    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text(yaml.safe_dump(_overlay_mixed_profiles()))
    contents = _valid_plugin_contents()
    evidence = {
        "repos": [
            {
                "repo": "acme/plugin",
                "files": list(contents) + ["README.md"],
                "files_complete": True,
                "capabilities": ["python", "claude-plugin"],
                "structural_signals": [],
                "file_contents": contents,
                "inference_status": "ran",
                "inferred_claims": [],
            },
            {
                "repo": "acme/docs",
                "files": ["README.md", "docs/index.md"],
                "files_complete": True,
                "capabilities": ["documentation"],
                "structural_signals": [],
            },
            {
                "repo": "acme/python-lib",
                "files": ["README.md"],
                "files_complete": True,
                "capabilities": ["python"],
                "structural_signals": [],
            },
        ]
    }

    dispatch = evaluate_fleet(
        evidence=evidence,
        profiles_path=profiles_path,
        workspace=tmp_path,
    )

    # Skill Phase 4 wrap — copy dispatch fields, no arithmetic.
    envelope = {
        "contract_version": 1,
        "kind": "healthcheck",
        "workspace": "acme",
        "run_at": RUN_AT,
        "actor": {
            "gh_login": "octocat",
            "machine": "acceptance",
            "mode": "scheduled",
        },
        "repos": dispatch["repos"],
        "aggregate": dispatch["aggregate"],
        "coverage": dispatch["coverage"],
        "errors": [],
    }

    result_path = tmp_path / "healthcheck-result.yaml"
    result_path.write_text(yaml.dump(envelope, sort_keys=False))
    data = yaml.safe_load(result_path.read_text())
    assert validate_result.validate(data, "healthcheck") == []

    plugin = next(r for r in data["repos"] if r["repo"] == "acme/plugin")
    for check_id in ("plugin-manifest", "plugin-skills", "claude-context"):
        status = plugin["checks"][check_id]["status"]
        assert status != "unsupported", (
            f"{check_id} must resolve via overlay adapters, got "
            f"{plugin['checks'][check_id]}"
        )
        assert status in {"pass", "fail", "unknown"}
    assert plugin["checks"]["plugin-manifest"]["status"] == "pass"
    assert plugin["checks"]["plugin-skills"]["status"] == "pass"
    assert plugin["checks"]["claude-context"]["status"] == "pass"
    assert "claude-plugin-v1" in data["aggregate"]["by_scorecard"]
    assert data["aggregate"]["by_scorecard"]["claude-plugin-v1"]["repos"] == 1
