"""Tests for the typed per-repo dependency-evidence loader."""

from __future__ import annotations

import pytest

from lib.pulse.scripts import dependency_evidence as de


def _artifact(
    *,
    selector_id="python.pyproject",
    path="pyproject.toml",
    blob_sha="a" * 40,
    size_bytes=12,
    state="found",
    encoding="utf-8",
    content="[project]\n",
    detail=None,
):
    return {
        "selector_id": selector_id,
        "path": path,
        "blob_sha": blob_sha,
        "size_bytes": size_bytes,
        "state": state,
        "encoding": encoding,
        "content": content,
        "detail": detail,
    }


def _document(repos):
    return {
        "contract_version": 1,
        "provider": {"name": "nave", "version": "0.9.0", "protocol": 2},
        "generated_at": "2026-07-18T10:00:00Z",
        "request_sha256": "f" * 64,
        "repos": repos,
        "errors": [],
    }


# --- load_dependency_evidence -----------------------------------------------


def test_load_indexes_by_repo():
    document = _document(
        [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": "b" * 40,
                "tree_complete": True,
                "artifacts": [_artifact()],
            },
            {
                "repo": "acme/web",
                "ref_name": "main",
                "tree_sha": "c" * 40,
                "tree_complete": True,
                "artifacts": [_artifact(selector_id="node.package_json", path="package.json")],
            },
        ]
    )
    index = de.load_dependency_evidence(document)
    assert set(index) == {"acme/api", "acme/web"}
    assert index["acme/api"].repo == "acme/api"
    assert index["acme/api"].tree_sha == "b" * 40
    assert index["acme/api"].tree_complete is True


def test_repo_evidence_by_selector_fans_out_multiple_artifacts():
    document = _document(
        [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": False,
                "artifacts": [
                    _artifact(selector_id="python.lock_glob", path="requirements.txt"),
                    _artifact(selector_id="python.lock_glob", path="requirements-dev.txt"),
                    _artifact(selector_id="python.pyproject", path="pyproject.toml"),
                ],
            }
        ]
    )
    index = de.load_dependency_evidence(document)
    matches = index["acme/api"].by_selector("python.lock_glob")
    assert {a.path for a in matches} == {"requirements.txt", "requirements-dev.txt"}
    assert all(a.selector_id == "python.lock_glob" for a in matches)


def test_repo_evidence_by_path_lookup():
    document = _document(
        [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": True,
                "artifacts": [_artifact(path="pyproject.toml")],
            }
        ]
    )
    index = de.load_dependency_evidence(document)
    artifact = index["acme/api"].by_path("pyproject.toml")
    assert artifact is not None
    assert artifact.path == "pyproject.toml"
    assert artifact.content == "[project]\n"


def test_repo_evidence_by_path_returns_none_when_absent():
    document = _document(
        [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": True,
                "artifacts": [_artifact(path="pyproject.toml")],
            }
        ]
    )
    index = de.load_dependency_evidence(document)
    assert index["acme/api"].by_path("poetry.lock") is None


def test_repo_evidence_by_path_with_multiple_null_path_artifacts():
    document = _document(
        [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": True,
                "artifacts": [
                    _artifact(path=None, state="absent", content=None, encoding=None),
                    _artifact(path=None, selector_id="python.lock_glob", state="absent", content=None, encoding=None),
                    _artifact(path="pyproject.toml"),
                ],
            }
        ]
    )
    index = de.load_dependency_evidence(document)
    evidence = index["acme/api"]
    assert evidence.by_path("pyproject.toml") is not None
    assert evidence.by_selector("python.lock_glob")[0].path is None
    null_path_artifacts = [a for a in evidence.artifacts if a.path is None]
    assert len(null_path_artifacts) == 2


def test_load_raises_on_malformed_document_missing_repo_key():
    document = _document(
        [
            {
                # missing "repo" key entirely — must raise, never silently skip.
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": True,
                "artifacts": [],
            }
        ]
    )
    with pytest.raises(KeyError):
        de.load_dependency_evidence(document)


def test_load_raises_on_malformed_artifact_missing_state():
    document = _document(
        [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": True,
                "artifacts": [
                    {
                        "selector_id": "python.pyproject",
                        "path": "pyproject.toml",
                        "blob_sha": None,
                        "size_bytes": 1,
                        # missing "state"
                        "encoding": "utf-8",
                        "content": "x",
                        "detail": None,
                    }
                ],
            }
        ]
    )
    with pytest.raises(KeyError):
        de.load_dependency_evidence(document)


def test_load_raises_rather_than_producing_partial_index():
    document = _document(
        [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": True,
                "artifacts": [_artifact()],
            },
            {
                # second repo is malformed — the whole call must raise, not
                # return a partial index containing only acme/api.
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": True,
                "artifacts": [],
            },
        ]
    )
    with pytest.raises(KeyError):
        de.load_dependency_evidence(document)
