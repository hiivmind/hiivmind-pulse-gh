"""End-to-end acceptance for F4: materialized dependency evidence -> the
integrated two-pass evaluate_fleet pipeline -> the content-free deps-snapshot
envelope -> both validators — driven through the real CLI, including an
isolated `uv run` invocation proving the PEP 723 headers' declared runtime
dependencies are actually sufficient standalone (not only inside the pytest
dev environment).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


SCRIPT = Path("lib/pulse/scripts/healthcheck_dispatch.py")
SNAPSHOT_VALIDATOR = Path("lib/pulse/scripts/validate_dependency_snapshot.py")
RESULT_VALIDATOR = Path("lib/pulse/scripts/validate_result.py")

UV_AVAILABLE = shutil.which("uv") is not None


def _artifact(path, content, *, selector_id=None, state="found"):
    if state == "found":
        return {
            "selector_id": selector_id or path,
            "path": path,
            "blob_sha": "a" * 40,
            "size_bytes": len(content.encode("utf-8")),
            "state": "found",
            "encoding": "utf-8",
            "content": content,
            "detail": None,
        }
    return {
        "selector_id": selector_id or path,
        "path": None,
        "blob_sha": None,
        "size_bytes": None,
        "state": state,
        "encoding": None,
        "content": None,
        "detail": None,
    }


def _dependency_evidence_document():
    py_pyproject = (
        '[project]\nname="api"\ndependencies=["requests>=1.0,<3.0"]\n'
    )
    py_lock_a = '[[package]]\nname="requests"\nversion="1.0.0"\n'
    py_lock_b = '[[package]]\nname="requests"\nversion="2.0.0"\n'
    node_package_json = '{"name":"web","version":"0.1.0","dependencies":{"lodash":"^1.0.0"}}'
    node_lock = (
        '{"lockfileVersion":3,"packages":{'
        '"":{"name":"web","version":"0.1.0"},'
        '"node_modules/lodash":{"version":"1.0.0"}'
        "}}"
    )
    return {
        "contract_version": 1,
        "provider": {"name": "nave", "version": "test", "protocol": 2},
        "generated_at": "2026-07-18T10:00:00Z",
        "request_sha256": "f" * 64,
        "repos": [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": "b" * 40,
                "tree_complete": True,
                "artifacts": [
                    _artifact("pyproject.toml", py_pyproject, selector_id="python.pyproject"),
                    _artifact("uv.lock", py_lock_a, selector_id="python.uv_lock"),
                    _artifact("poetry.lock", "", selector_id="python.poetry_lock", state="absent"),
                    _artifact("pdm.lock", "", selector_id="python.pdm_lock", state="absent"),
                    _artifact(
                        "environment.yml", "", selector_id="python.conda_env", state="absent"
                    ),
                ],
            },
            {
                "repo": "acme/worker",
                "ref_name": "main",
                "tree_sha": "c" * 40,
                "tree_complete": True,
                "artifacts": [
                    _artifact("pyproject.toml", py_pyproject, selector_id="python.pyproject"),
                    _artifact("uv.lock", py_lock_b, selector_id="python.uv_lock"),
                    _artifact("poetry.lock", "", selector_id="python.poetry_lock", state="absent"),
                    _artifact("pdm.lock", "", selector_id="python.pdm_lock", state="absent"),
                    _artifact(
                        "environment.yml", "", selector_id="python.conda_env", state="absent"
                    ),
                ],
            },
            {
                "repo": "acme/web",
                "ref_name": "main",
                "tree_sha": "d" * 40,
                "tree_complete": True,
                "artifacts": [
                    _artifact("package.json", node_package_json, selector_id="node.package_json"),
                    _artifact("package-lock.json", node_lock, selector_id="node.npm_lock"),
                    _artifact("pnpm-lock.yaml", "", selector_id="node.pnpm_lock", state="absent"),
                    _artifact(
                        "pnpm-workspace.yaml",
                        "",
                        selector_id="node.pnpm_workspace_yaml",
                        state="absent",
                    ),
                    _artifact("yarn.lock", "", selector_id="node.yarn_lock", state="absent"),
                ],
            },
        ],
        "errors": [],
    }


def _profiles_document():
    return {
        "repository_profiles": {
            "acme/api": {"profiles": ["python"], "scorecard": "py-v1"},
            "acme/worker": {"profiles": ["python"], "scorecard": "py-v1"},
            "acme/web": {"profiles": ["nodejs"], "scorecard": "node-v1"},
        },
        "scorecards": {
            "py-v1": {
                "checks": [
                    {
                        "id": "python_manifest_lock_consistency",
                        "adapter": "python.dependencies",
                        "weight": 1,
                    },
                    {
                        "id": "fleet_dependency_coherence",
                        "adapter": "fleet.dependencies.coherence",
                        "weight": 1,
                    },
                ]
            },
            "node-v1": {
                "checks": [
                    {
                        "id": "node_manifest_lock_consistency",
                        "adapter": "node.dependencies",
                        "weight": 1,
                    },
                    {
                        "id": "fleet_dependency_coherence",
                        "adapter": "fleet.dependencies.coherence",
                        "weight": 1,
                    },
                ]
            },
        },
        "adapters": {
            "python.dependencies": {"state": "available"},
            "node.dependencies": {"state": "available"},
            "fleet.dependencies.coherence": {"state": "available"},
        },
    }


def _dependencies_policy_document():
    return {
        "contract_version": 1,
        "coherence_groups": {
            "core-runtime": {
                "repos": ["acme/api", "acme/worker"],
                "packages": ["python:requests"],
                "policy": "same-minor",
            }
        },
    }


def _write_fixtures(tmp_path: Path) -> dict[str, Path]:
    evidence_path = tmp_path / "evidence.yaml"
    evidence_path.write_text(yaml.safe_dump({"repos": [{"repo": r} for r in ("acme/api", "acme/worker", "acme/web")]}))

    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text(yaml.safe_dump(_profiles_document()))

    dependency_evidence_path = tmp_path / "dependency-evidence.json"
    dependency_evidence_path.write_text(json.dumps(_dependency_evidence_document()))

    dependency_policy_path = tmp_path / "dependencies.yaml"
    dependency_policy_path.write_text(yaml.safe_dump(_dependencies_policy_document()))

    return {
        "evidence": evidence_path,
        "profiles": profiles_path,
        "dependency_evidence": dependency_evidence_path,
        "dependency_policy": dependency_policy_path,
    }


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_full_pipeline_via_cli_produces_valid_result_and_snapshot(tmp_path):
    paths = _write_fixtures(tmp_path)
    snapshot_path = tmp_path / "deps-snapshot.json"

    completed = _run_cli(
        "--evidence", str(paths["evidence"]),
        "--profiles", str(paths["profiles"]),
        "--workspace", str(tmp_path / "does-not-exist"),
        "--dependency-evidence", str(paths["dependency_evidence"]),
        "--dependency-policy", str(paths["dependency_policy"]),
        "--dependency-snapshot-out", str(snapshot_path),
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)

    by_repo = {r["repo"]: r for r in result["repos"]}
    fleet_block = by_repo["acme/worker"]["checks"]["fleet_dependency_coherence"]
    assert fleet_block["status"] == "fail"
    assert fleet_block["data"]["findings"][0]["distance"] == "major"

    assert result["coverage"]["dependencies"]["repositories_selected"] == 3
    assert result["coverage"]["dependencies"]["repositories_grouped"] == 2
    assert result["coverage"]["dependencies"]["repositories_ungrouped"] == 1  # acme/web, no group

    assert snapshot_path.exists()
    snapshot = json.loads(snapshot_path.read_text())
    assert snapshot["coverage"] == result["coverage"]["dependencies"]
    assert len(snapshot["findings"]) == 1
    assert snapshot["findings"][0]["package"] == "requests"

    # validate both artifacts with their real, standalone CLI validators.
    validated_snapshot = subprocess.run(
        [sys.executable, str(SNAPSHOT_VALIDATOR), str(snapshot_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert validated_snapshot.returncode == 0, validated_snapshot.stderr

    healthcheck_result_path = tmp_path / "healthcheck-result.yaml"
    healthcheck_result_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": 1,
                "kind": "healthcheck",
                "workspace": "acme",
                "run_at": "2026-07-18T10:00:00Z",
                "actor": {"gh_login": "unknown", "machine": "test", "mode": "scheduled"},
                "repos": result["repos"],
                "aggregate": result["aggregate"],
                "coverage": result["coverage"],
                "errors": [],
            }
        )
    )
    validated_result = subprocess.run(
        [sys.executable, str(RESULT_VALIDATOR), str(healthcheck_result_path), "--kind", "healthcheck"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert validated_result.returncode == 0, validated_result.stderr


@pytest.mark.skipif(not UV_AVAILABLE, reason="uv is not installed on PATH")
def test_isolated_uv_run_invocation_proves_pep723_dependencies_are_sufficient(tmp_path):
    """The exact production `uv run` invocation, not an in-process pytest
    import — proves the PEP 723 header actually carries every runtime
    dependency the new dependency-coherence code paths need, standalone,
    outside the pytest dev environment's own dependency group."""
    paths = _write_fixtures(tmp_path)
    snapshot_path = tmp_path / "deps-snapshot.json"

    completed = subprocess.run(
        [
            "uv", "run", "--no-project", str(SCRIPT),
            "--evidence", str(paths["evidence"]),
            "--profiles", str(paths["profiles"]),
            "--workspace", str(tmp_path / "does-not-exist"),
            "--dependency-evidence", str(paths["dependency_evidence"]),
            "--dependency-policy", str(paths["dependency_policy"]),
            "--dependency-snapshot-out", str(snapshot_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    by_repo = {r["repo"]: r for r in result["repos"]}
    assert by_repo["acme/worker"]["checks"]["fleet_dependency_coherence"]["status"] == "fail"
    assert snapshot_path.exists()

    validated = subprocess.run(
        ["uv", "run", "--no-project", str(SNAPSHOT_VALIDATOR), str(snapshot_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert validated.returncode == 0, validated.stderr
