"""Tests for dependency_pipeline: selector catalog, selection scan, and the
sanitized pre-dispatch evaluation boundary."""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

from lib.pulse.scripts import dependency_pipeline as dp
from lib.pulse.scripts.dependency_evidence import Artifact, RepoEvidence
from lib.pulse.scripts.profile_dispatch import (
    AdapterDefinition,
    CheckDefinition,
    ProfileConfig,
    RepositoryProfile,
    Scorecard,
)


def _config(scorecards: dict[str, Scorecard], repositories: dict[str, RepositoryProfile]) -> ProfileConfig:
    adapters = {
        "python.dependencies": AdapterDefinition(id="python.dependencies", state="available"),
        "node.dependencies": AdapterDefinition(id="node.dependencies", state="available"),
        "fleet.dependencies.coherence": AdapterDefinition(
            id="fleet.dependencies.coherence", state="available"
        ),
        "generic.docs": AdapterDefinition(id="generic.docs", state="available"),
    }
    return ProfileConfig(
        repositories=repositories, scorecards=scorecards, adapters=adapters, proposal_rules={}
    )


def _check(id_, adapter, weight=1.0):
    return CheckDefinition(id=id_, adapter=adapter, weight=weight)


# --- DEPENDENCY_SELECTORS ------------------------------------------------------


def test_dependency_selectors_cover_every_v1_supported_manager_file():
    ids = {s["id"] for s in dp.DEPENDENCY_SELECTORS}
    assert ids == {
        "python.pyproject",
        "python.uv_lock",
        "python.poetry_lock",
        "python.pdm_lock",
        "python.pip_tools_in",
        "python.pip_tools_txt",
        "python.conda_env",
        "node.package_json",
        "node.npm_lock",
        "node.pnpm_lock",
        "node.pnpm_workspace_yaml",
        "node.yarn_lock",
    }


# --- dependency_selected_repos --------------------------------------------------


def test_dependency_selected_repos_single_ecosystem():
    scorecards = {
        "py-v1": Scorecard(
            id="py-v1",
            checks=(_check("python_manifest_lock_consistency", "python.dependencies"),),
        )
    }
    repos = {"acme/api": RepositoryProfile(profiles=(), scorecard="py-v1")}
    config = _config(scorecards, repos)
    selected = dp.dependency_selected_repos(config)
    assert selected == {"acme/api": frozenset({"python"})}


def test_dependency_selected_repos_polyglot_selects_both():
    scorecards = {
        "poly-v1": Scorecard(
            id="poly-v1",
            checks=(
                _check("python_manifest_lock_consistency", "python.dependencies"),
                _check("node_manifest_lock_consistency", "node.dependencies"),
            ),
        )
    }
    repos = {"acme/full": RepositoryProfile(profiles=(), scorecard="poly-v1")}
    config = _config(scorecards, repos)
    selected = dp.dependency_selected_repos(config)
    assert selected == {"acme/full": frozenset({"python", "node"})}


def test_dependency_selected_repos_excludes_unrelated_repos():
    scorecards = {
        "docs-v1": Scorecard(id="docs-v1", checks=(_check("documentation", "generic.docs"),)),
        "py-v1": Scorecard(
            id="py-v1",
            checks=(_check("python_manifest_lock_consistency", "python.dependencies"),),
        ),
    }
    repos = {
        "acme/docs": RepositoryProfile(profiles=(), scorecard="docs-v1"),
        "acme/api": RepositoryProfile(profiles=(), scorecard="py-v1"),
    }
    config = _config(scorecards, repos)
    selected = dp.dependency_selected_repos(config)
    assert "acme/docs" not in selected
    assert selected == {"acme/api": frozenset({"python"})}


# --- fleet_coherence_selected_repos ---------------------------------------------


def test_fleet_coherence_selected_repos():
    scorecards = {
        "fleet-v1": Scorecard(
            id="fleet-v1",
            checks=(
                _check("python_manifest_lock_consistency", "python.dependencies"),
                _check("fleet_dependency_coherence", "fleet.dependencies.coherence"),
            ),
        ),
        "py-only-v1": Scorecard(
            id="py-only-v1",
            checks=(_check("python_manifest_lock_consistency", "python.dependencies"),),
        ),
    }
    repos = {
        "acme/grouped": RepositoryProfile(profiles=(), scorecard="fleet-v1"),
        "acme/ungrouped": RepositoryProfile(profiles=(), scorecard="py-only-v1"),
    }
    config = _config(scorecards, repos)
    assert dp.fleet_coherence_selected_repos(config) == {"acme/grouped"}


# --- evaluate_dependencies (sanitized pre-dispatch boundary) -------------------


def _evidence() -> RepoEvidence:
    return RepoEvidence(
        repo="acme/api",
        ref_name="main",
        tree_sha="a" * 40,
        tree_complete=True,
        artifacts=(
            Artifact(
                selector_id="python.pyproject",
                path="pyproject.toml",
                blob_sha="b" * 40,
                size_bytes=10,
                state="found",
                encoding="utf-8",
                content='[project]\nname="x"\ndependencies=["requests>=1.0"]\n',
                detail=None,
            ),
            Artifact(
                selector_id="python.uv_lock",
                path="uv.lock",
                blob_sha="c" * 40,
                size_bytes=10,
                state="found",
                encoding="utf-8",
                content='[[package]]\nname="requests"\nversion="2.0.0"\n',
                detail=None,
            ),
        ),
    )


def test_evaluate_dependencies_none_evidence_is_stable_evidence_gap_without_parsing():
    evaluation = dp.evaluate_dependencies("acme/api", "python", None)
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "evidence_gap"
    assert evaluation.detection.state == "unknown"
    assert evaluation.records == ()


def test_evaluate_dependencies_calls_the_real_parser_on_success():
    evaluation = dp.evaluate_dependencies("acme/api", "python", _evidence())
    assert evaluation.local_status == "pass"
    assert any(r.name == "requests" for r in evaluation.records)


def test_evaluate_dependencies_sanitizes_an_internal_parser_exception(monkeypatch):
    def _boom(repo, evidence, *, capability):
        raise RuntimeError("leaked secret content should never appear anywhere")

    monkeypatch.setattr(dp, "parse_python", _boom)
    evaluation = dp.evaluate_dependencies("acme/api", "python", _evidence())
    assert evaluation.local_status == "error"
    assert evaluation.local_reason_code == "internal_parser_error"
    assert evaluation.detection.state == "error"
    assert "leaked secret" not in str(evaluation)
    assert evaluation.coverage_state == "complete"


# --- materialize CLI entry point (main()) --------------------------------------


_MATERIALIZE_FIXTURES = Path(__file__).parent / "fixtures" / "nave" / "dependency_pipeline_cli"


def test_main_writes_content_free_path_and_secure_file(tmp_path, monkeypatch, capsys):
    # Route secure_run_dir() into tmp_path so the test cleans up after itself.
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    exit_code = dp.main(["--repos", "acme/api", "--nave-fixtures", str(_MATERIALIZE_FIXTURES)])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    written_path = Path(out)
    assert written_path.exists()
    # stdout is ONLY the path — never the materialized content.
    assert "pyproject.toml" not in out
    assert "[project]" not in out

    document = json.loads(written_path.read_text())
    assert document["repos"][0]["repo"] == "acme/api"
    assert document["repos"][0]["artifacts"][0]["content"] == '[project]\nname="x"\n'
    assert stat.S_IMODE(written_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(written_path.parent.stat().st_mode) == 0o700


def test_main_rejects_empty_repos_list():
    assert dp.main(["--repos", ""]) == 2


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed on PATH")
def test_isolated_uv_run_materialize_cli_never_prints_raw_content():
    """The exact production `uv run` invocation, not an in-process import —
    proves the PEP 723 header is sufficient standalone AND that nothing but
    the file path ever reaches stdout."""
    script = Path("lib/pulse/scripts/dependency_pipeline.py")
    completed = subprocess.run(
        [
            "uv", "run", "--no-project", str(script),
            "--repos", "acme/api",
            "--nave-fixtures", str(_MATERIALIZE_FIXTURES),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    out = completed.stdout.strip()
    assert "[project]" not in out
    assert "pyproject.toml" not in out
    written_path = Path(out)
    assert written_path.exists()
    document = json.loads(written_path.read_text())
    assert document["repos"][0]["repo"] == "acme/api"
    written_path.unlink()
    written_path.parent.rmdir()
