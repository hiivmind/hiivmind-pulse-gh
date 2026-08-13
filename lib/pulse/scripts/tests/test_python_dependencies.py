"""Tests for the Python dependency-manager adapter (uv, Poetry, PDM, pip-tools, Conda)."""

from __future__ import annotations

from pathlib import Path

from lib.pulse.scripts.dependency_evidence import Artifact, RepoEvidence
from lib.pulse.scripts.adapters.python_dependencies import (
    detect_python,
    evaluate_python,
    parse_python,
)
from lib.pulse.scripts.check_adapters import CheckContext


FIXTURES = Path(__file__).parent / "fixtures" / "dependencies" / "python"


def _read(*parts: str) -> str:
    return (FIXTURES.joinpath(*parts)).read_text()


def _found(path: str, content: str, *, selector_id: str | None = None) -> Artifact:
    return Artifact(
        selector_id=selector_id or path,
        path=path,
        blob_sha="a" * 40,
        size_bytes=len(content.encode("utf-8")),
        state="found",
        encoding="utf-8",
        content=content,
        detail=None,
    )


def _absent(path: str, *, selector_id: str | None = None) -> Artifact:
    return Artifact(
        selector_id=selector_id or path,
        path=None,
        blob_sha=None,
        size_bytes=None,
        state="absent",
        encoding=None,
        content=None,
        detail=None,
    )


def _artifact(path: str, *, state: str, content: str | None = None, selector_id: str | None = None) -> Artifact:
    if state == "found":
        return _found(path, content or "", selector_id=selector_id)
    if state == "absent":
        return _absent(path, selector_id=selector_id)
    return Artifact(
        selector_id=selector_id or path,
        path=path,
        blob_sha=None,
        size_bytes=None,
        state=state,
        encoding=None,
        content=None,
        detail="materialize could not resolve this artifact",
    )


def _evidence(repo: str, artifacts: list[Artifact]) -> RepoEvidence:
    return RepoEvidence(
        repo=repo,
        ref_name="main",
        tree_sha="b" * 40,
        tree_complete=True,
        artifacts=tuple(artifacts),
    )


def _manager_evidence(manager: str) -> RepoEvidence:
    """Build evidence for a fixture directory named after the manager, with every
    other candidate manager file authoritatively absent."""
    directory = FIXTURES / manager
    all_names = {
        "pyproject.toml": "python.pyproject",
        "uv.lock": "python.uv_lock",
        "poetry.lock": "python.poetry_lock",
        "pdm.lock": "python.pdm_lock",
    }
    artifacts = []
    for name, selector_id in all_names.items():
        path = directory / name
        if path.exists():
            artifacts.append(_found(name, path.read_text(), selector_id=selector_id))
        else:
            artifacts.append(_absent(name, selector_id=selector_id))
    for pattern_dir_glob in ("requirements.in", "requirements.txt"):
        path = directory / pattern_dir_glob
        if path.exists():
            selector = "python.pip_tools_in" if pattern_dir_glob.endswith(".in") else "python.pip_tools_txt"
            artifacts.append(_found(pattern_dir_glob, path.read_text(), selector_id=selector))
    env_path = directory / "environment.yml"
    if env_path.exists():
        artifacts.append(_found("environment.yml", env_path.read_text(), selector_id="python.conda_env"))
    else:
        artifacts.append(_absent("environment.yml", selector_id="python.conda_env"))
    return _evidence(f"acme/{manager}", artifacts)


# --- capability=False -------------------------------------------------------


def test_capability_false_is_not_applicable():
    evidence = _evidence("acme/none", [])
    detection = detect_python("acme/none", evidence, capability=False)
    assert detection.state == "not_applicable"
    evaluation = parse_python("acme/none", evidence, capability=False)
    assert evaluation.local_status == "not_applicable"
    assert evaluation.records == ()
    assert evaluation.declarations == ()


# --- workspace detection -----------------------------------------------------


def test_uv_workspace_table_detected_is_unsupported():
    content = _read("uv_workspace", "pyproject.toml")
    evidence = _evidence("acme/mono", [_found("pyproject.toml", content, selector_id="python.pyproject")])
    detection = detect_python("acme/mono", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "workspace_repository"
    evaluation = parse_python("acme/mono", evidence, capability=True)
    assert evaluation.local_status == "unsupported"
    assert evaluation.local_reason_code == "workspace_repository"
    assert evaluation.records == ()
    assert evaluation.declarations == ()


def test_workspace_sentinel_unresolved_is_unknown():
    evidence = _evidence(
        "acme/mono",
        [_artifact("pyproject.toml", state="unresolved", selector_id="python.pyproject")],
    )
    detection = detect_python("acme/mono", evidence, capability=True)
    assert detection.state == "unknown"
    assert detection.reason_code == "workspace_sentinel_unresolved"
    evaluation = parse_python("acme/mono", evidence, capability=True)
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "workspace_sentinel_unresolved"


# --- no manager evidence / evidence gap --------------------------------------


def test_no_manager_evidence_when_tree_complete_and_nothing_found():
    evidence = _evidence(
        "acme/empty",
        [
            _absent("pyproject.toml", selector_id="python.pyproject"),
            _absent("uv.lock", selector_id="python.uv_lock"),
            _absent("poetry.lock", selector_id="python.poetry_lock"),
            _absent("pdm.lock", selector_id="python.pdm_lock"),
            _absent("environment.yml", selector_id="python.conda_env"),
        ],
    )
    evaluation = parse_python("acme/empty", evidence, capability=True)
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "no_manager_evidence"


def test_evidence_gap_when_lock_is_unresolved_for_an_identified_manager():
    evidence = _evidence(
        "acme/flaky",
        [
            _found("pyproject.toml", _read("uv", "pyproject.toml"), selector_id="python.pyproject"),
            _artifact("uv.lock", state="too_large", selector_id="python.uv_lock"),
            _absent("poetry.lock", selector_id="python.poetry_lock"),
            _absent("pdm.lock", selector_id="python.pdm_lock"),
            _absent("environment.yml", selector_id="python.conda_env"),
        ],
    )
    evaluation = parse_python("acme/flaky", evidence, capability=True)
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "evidence_gap"


# --- uv (PEP 621 + uv.lock) --------------------------------------------------


def test_uv_manager_all_ranges_satisfied_is_pass():
    evidence = _manager_evidence("uv")
    evaluation = parse_python("acme/uv", evidence, capability=True)
    assert evaluation.detection.manager == "uv"
    assert evaluation.local_status == "pass"
    names = {r.name for r in evaluation.records}
    assert {"requests", "click", "pytest", "ruff"} <= names
    for record in evaluation.records:
        assert record.resolution == "single"
        assert record.ecosystem == "python"
    assert evaluation.coverage_state == "complete"


def test_uv_manager_json_projection_covers_declarations_and_records():
    evidence = _manager_evidence("uv")
    evaluation = parse_python("acme/uv", evidence, capability=True)
    from lib.pulse.scripts.dependencies import project_evaluation

    projected = project_evaluation(evaluation)
    assert isinstance(projected["declarations"], list)
    assert isinstance(projected["records"], list)
    assert any(d["name"] == "requests" for d in projected["declarations"])
    click_record = next(r for r in projected["records"] if r["name"] == "click")
    assert click_record["locked_version"] == "8.1.3"
    assert click_record["provenance"]


def test_uv_missing_lock_is_fail_missing_lock():
    content = _read("uv", "pyproject.toml")
    evidence = _evidence(
        "acme/uv-nolock",
        [
            _found("pyproject.toml", content, selector_id="python.pyproject"),
            _absent("uv.lock", selector_id="python.uv_lock"),
            _absent("poetry.lock", selector_id="python.poetry_lock"),
            _absent("pdm.lock", selector_id="python.pdm_lock"),
            _absent("environment.yml", selector_id="python.conda_env"),
        ],
    )
    evaluation = parse_python("acme/uv-nolock", evidence, capability=True)
    assert evaluation.local_status == "fail"
    assert evaluation.local_reason_code == "missing_lock"


def test_malformed_pyproject_toml_is_fail_malformed_source():
    evidence = _evidence(
        "acme/broken",
        [
            _found("pyproject.toml", "not [ valid toml", selector_id="python.pyproject"),
            _found("uv.lock", _read("uv", "uv.lock"), selector_id="python.uv_lock"),
            _absent("poetry.lock", selector_id="python.poetry_lock"),
            _absent("pdm.lock", selector_id="python.pdm_lock"),
            _absent("environment.yml", selector_id="python.conda_env"),
        ],
    )
    evaluation = parse_python("acme/broken", evidence, capability=True)
    assert evaluation.local_status == "fail"
    assert evaluation.local_reason_code == "malformed_source"


def test_malformed_lock_is_fail_malformed_source():
    evidence = _evidence(
        "acme/broken-lock",
        [
            _found("pyproject.toml", _read("uv", "pyproject.toml"), selector_id="python.pyproject"),
            _found("uv.lock", "not [ valid toml", selector_id="python.uv_lock"),
            _absent("poetry.lock", selector_id="python.poetry_lock"),
            _absent("pdm.lock", selector_id="python.pdm_lock"),
            _absent("environment.yml", selector_id="python.conda_env"),
        ],
    )
    evaluation = parse_python("acme/broken-lock", evidence, capability=True)
    assert evaluation.local_status == "fail"
    assert evaluation.local_reason_code == "malformed_source"


def test_ambiguous_manager_when_two_locks_present():
    evidence = _evidence(
        "acme/ambiguous-manager",
        [
            _found("pyproject.toml", _read("uv", "pyproject.toml"), selector_id="python.pyproject"),
            _found("uv.lock", _read("uv", "uv.lock"), selector_id="python.uv_lock"),
            _found("poetry.lock", _read("poetry", "poetry.lock"), selector_id="python.poetry_lock"),
            _absent("pdm.lock", selector_id="python.pdm_lock"),
            _absent("environment.yml", selector_id="python.conda_env"),
        ],
    )
    detection = detect_python("acme/ambiguous-manager", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "ambiguous_manager"
    evaluation = parse_python("acme/ambiguous-manager", evidence, capability=True)
    assert evaluation.local_status == "unsupported"
    assert evaluation.local_reason_code == "ambiguous_manager"


# --- Poetry: every constraint-algorithm branch + range violation ------------


def test_poetry_manager_every_constraint_branch():
    evidence = _manager_evidence("poetry")
    evaluation = parse_python("acme/poetry", evidence, capability=True)
    assert evaluation.detection.manager == "poetry"

    records_by_name = {r.name: r for r in evaluation.records}
    findings_by_name = {f.name: f for f in evaluation.local_findings}

    # python interpreter constraint is never a package
    assert "python" not in records_by_name

    for satisfied_name in (
        "caret-full",
        "caret-minor-prefix-zero",
        "caret-patch-prefix-zeros",
        "caret-two-part",
        "caret-one-part",
        "caret-zero",
        "caret-all-zero",
        "tilde-full",
        "tilde-two-part",
        "tilde-one-part",
        "compound-range",
        "exact-version",
        "prefix-wildcard-two",
        "prefix-wildcard-three",
        "bare-wildcard",
        "union-range",
    ):
        assert records_by_name[satisfied_name].resolution == "single"
        assert findings_by_name[satisfied_name].status == "pass", satisfied_name

    # vcs-dep is a table-form (git) dependency: non_range_spec, still resolves
    vcs = records_by_name["vcs-dep"]
    assert vcs.resolution == "single"
    assert vcs.locked_version == "0.1.0"

    # shared-pkg: declared in both main (>=2.0,<3.0, satisfied by 2.5.0) and
    # dev (>=1.0,<2.0, violated by 2.5.0) — the package-level finding is fail.
    assert findings_by_name["shared-pkg"].status == "fail"
    assert findings_by_name["shared-pkg"].reason_code == "range_violation"
    assert evaluation.local_status == "fail"
    assert evaluation.local_reason_code == "range_violation"


def test_poetry_bare_wildcard_is_unconstrained_declaration():
    evidence = _manager_evidence("poetry")
    evaluation = parse_python("acme/poetry", evidence, capability=True)
    decl = next(d for d in evaluation.declarations if d.name == "bare-wildcard")
    assert decl.manifest_range == "*"
    assert decl.unresolved_reason is None


def test_poetry_vcs_dependency_is_non_range_spec():
    evidence = _manager_evidence("poetry")
    evaluation = parse_python("acme/poetry", evidence, capability=True)
    decl = next(d for d in evaluation.declarations if d.name == "vcs-dep")
    assert decl.manifest_range is None
    assert decl.unresolved_reason == "non_range_spec"


# --- PDM ----------------------------------------------------------------------


def test_pdm_manager_range_violation_is_fail():
    evidence = _manager_evidence("pdm")
    evaluation = parse_python("acme/pdm", evidence, capability=True)
    assert evaluation.detection.manager == "pdm"
    flask = next(f for f in evaluation.local_findings if f.name == "flask")
    assert flask.status == "fail"
    assert flask.reason_code == "range_violation"
    assert evaluation.local_status == "fail"


# --- pip-tools ------------------------------------------------------------------


def test_pip_tools_with_compiled_lock_is_pass():
    evidence = _manager_evidence("pip_tools")
    evaluation = parse_python("acme/pip_tools", evidence, capability=True)
    assert evaluation.detection.manager == "pip-tools"
    assert evaluation.local_status == "pass"
    click_record = next(r for r in evaluation.records if r.name == "click")
    assert click_record.locked_version == "8.1.3"


def test_pip_tools_lockless_is_warn_unresolved_lockless():
    evidence = _manager_evidence("pip_tools_lockless")
    evaluation = parse_python("acme/pip_tools_lockless", evidence, capability=True)
    assert evaluation.detection.manager == "pip-tools"
    assert evaluation.local_status == "warn"
    assert evaluation.local_reason_code == "unresolved_lockless"
    assert evaluation.records == ()
    assert evaluation.coverage_state == "incomplete"


# --- Conda (nested pip: only) ------------------------------------------------


def test_conda_nested_pip_only_is_pass():
    evidence = _manager_evidence("conda")
    evaluation = parse_python("acme/conda", evidence, capability=True)
    assert evaluation.detection.manager == "conda"
    assert evaluation.local_status == "pass"
    names = {r.name for r in evaluation.records}
    assert names == {"requests", "click"}
    assert evaluation.partial_unsupported == 0


def test_conda_mixed_native_and_pip_counts_partial_unsupported():
    evidence = _manager_evidence("conda_mixed")
    evaluation = parse_python("acme/conda_mixed", evidence, capability=True)
    assert evaluation.detection.manager == "conda"
    assert evaluation.local_status == "pass"
    names = {r.name for r in evaluation.records}
    assert names == {"requests"}
    # numpy=1.24.0 and scipy>=1.9 are native conda specs — not PackageRecords,
    # each counted as partial_unsupported, never silently dropped.
    assert evaluation.partial_unsupported == 2


# --- multi-resolution ambiguity -----------------------------------------------


def test_genuine_multi_resolution_is_unknown_multiple_resolutions():
    evidence = _manager_evidence("ambiguous_resolution")
    evaluation = parse_python("acme/ambiguous_resolution", evidence, capability=True)
    foo = next(r for r in evaluation.records if r.name == "foo")
    assert foo.resolution == "multiple"
    assert foo.unresolved_reason == "multiple_resolutions"
    assert foo.manifest_range is None
    assert foo.locked_version is None
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "multiple_resolutions"
    assert evaluation.coverage_state == "incomplete"


# --- evaluate_python (CheckBlock dispatch) ------------------------------------


def test_evaluate_python_projects_the_precomputed_evaluation():
    evidence = _manager_evidence("uv")
    evaluation = parse_python("acme/uv", evidence, capability=True)
    context = CheckContext(
        repo="acme/uv",
        evidence={"dependency_evaluations": {"python": evaluation}},
        check={"id": "python_manifest_lock_consistency", "adapter": "python.dependencies", "weight": 1},
        workspace=Path("."),
    )
    block = evaluate_python(context)
    assert block["status"] == "pass"
    assert block["data"]["records"]
    assert block["data"]["evidence"] == {"paths": [], "refs": []}


def test_evaluate_python_never_calls_parse_python_itself(monkeypatch):
    evidence = _manager_evidence("uv")
    evaluation = parse_python("acme/uv", evidence, capability=True)
    context = CheckContext(
        repo="acme/uv",
        evidence={"dependency_evaluations": {"python": evaluation}},
        check={"id": "python_manifest_lock_consistency", "adapter": "python.dependencies", "weight": 1},
        workspace=Path("."),
    )

    def _boom(*args, **kwargs):
        raise AssertionError("evaluate_python must not call parse_python")

    monkeypatch.setattr(
        "lib.pulse.scripts.adapters.python_dependencies.parse_python", _boom
    )
    block = evaluate_python(context)
    assert block["status"] == "pass"
