"""Tests for building/normalizing/securing temporary dependency evidence."""

from __future__ import annotations

import json
import stat
from pathlib import Path

from lib.pulse.scripts import dependency_evidence as de


GENERATED_AT = "2026-07-18T10:00:00Z"


def provider():
    return {"name": "nave", "version": "0.9.0", "protocol": 2}


def selectors():
    return [
        {"id": "python.pyproject", "pattern": "pyproject.toml"},
        {"id": "node.package_json", "pattern": "package.json", "max_bytes": 65536},
    ]


def raw_result():
    return {
        "contract_version": 1,
        "repos": [
            {
                "repo": "acme/web",
                "ref_name": "main",
                "tree_sha": "b" * 40,
                "tree_complete": True,
                "artifacts": [
                    {
                        "selector_id": "node.package_json",
                        "path": "package.json",
                        "blob_sha": "c" * 40,
                        "size_bytes": 512,
                        "state": "found",
                        "encoding": "utf-8",
                        "content": '{"name": "web"}',
                        "detail": "",
                    },
                    {
                        "selector_id": "python.pyproject",
                        "path": None,
                        "blob_sha": None,
                        "size_bytes": 0,
                        "state": "absent",
                        "encoding": None,
                        "content": None,
                        "detail": "",
                    },
                ],
            },
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": "a" * 40,
                "tree_complete": True,
                "artifacts": [
                    {
                        "selector_id": "python.pyproject",
                        "path": "pyproject.toml",
                        "blob_sha": "d" * 40,
                        "size_bytes": 1234,
                        "state": "found",
                        "encoding": "utf-8",
                        "content": "[project]\nname = \"api\"\n",
                        "detail": "",
                    },
                ],
            },
        ],
    }


# --- build_request ---------------------------------------------------------


def test_build_request_shape():
    request = de.build_request(["acme/api", "acme/web"], selectors())

    assert request == {
        "contract_version": 1,
        "repos": [
            {"repo": "acme/api", "selectors": selectors()},
            {"repo": "acme/web", "selectors": selectors()},
        ],
    }


def test_build_request_with_no_repos_has_empty_repo_list():
    request = de.build_request([], selectors())
    assert request["repos"] == []


# --- request_sha256 ---------------------------------------------------------


def test_request_sha256_is_deterministic_across_key_order_permutations():
    request_a = {
        "contract_version": 1,
        "repos": [{"repo": "acme/api", "selectors": [{"id": "x", "pattern": "y"}]}],
    }
    # Same logical content, different key order at every level.
    request_b = {
        "repos": [{"selectors": [{"pattern": "y", "id": "x"}], "repo": "acme/api"}],
        "contract_version": 1,
    }

    assert de.request_sha256(request_a) == de.request_sha256(request_b)


def test_request_sha256_changes_when_content_changes():
    request_a = de.build_request(["acme/api"], selectors())
    request_b = de.build_request(["acme/other"], selectors())

    assert de.request_sha256(request_a) != de.request_sha256(request_b)


def test_request_sha256_is_64_char_lowercase_hex():
    digest = de.request_sha256(de.build_request(["acme/api"], selectors()))
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)  # raises if not hex


# --- normalize ---------------------------------------------------------


def test_normalize_produces_exact_top_level_shape():
    raw = raw_result()
    doc = de.normalize(raw, provider(), GENERATED_AT, "f" * 64)

    assert set(doc.keys()) == {
        "contract_version",
        "provider",
        "generated_at",
        "request_sha256",
        "repos",
        "errors",
    }
    assert doc["contract_version"] == 1
    assert doc["provider"] == {"name": "nave", "version": "0.9.0", "protocol": 2}
    assert doc["generated_at"] == GENERATED_AT
    assert doc["request_sha256"] == "f" * 64
    assert doc["errors"] == []


def test_normalize_sorts_repos_by_repo_name():
    doc = de.normalize(raw_result(), provider(), GENERATED_AT, "f" * 64)
    assert [r["repo"] for r in doc["repos"]] == ["acme/api", "acme/web"]


def test_normalize_repo_has_exact_keys():
    doc = de.normalize(raw_result(), provider(), GENERATED_AT, "f" * 64)
    repo = doc["repos"][0]
    assert set(repo.keys()) == {
        "repo",
        "ref_name",
        "tree_sha",
        "tree_complete",
        "artifacts",
    }


def test_normalize_artifact_has_exact_keys():
    doc = de.normalize(raw_result(), provider(), GENERATED_AT, "f" * 64)
    artifact = doc["repos"][0]["artifacts"][0]
    assert set(artifact.keys()) == {
        "selector_id",
        "path",
        "blob_sha",
        "size_bytes",
        "state",
        "encoding",
        "content",
        "detail",
    }


def test_normalize_sorts_artifacts_by_path_none_then_path_then_selector_id():
    doc = de.normalize(raw_result(), provider(), GENERATED_AT, "f" * 64)
    web = next(r for r in doc["repos"] if r["repo"] == "acme/web")
    # Sort key is (path is None, path, selector_id): False < True, so the
    # artifact with a real path (found) sorts before the null-path (absent) one.
    assert [a["selector_id"] for a in web["artifacts"]] == [
        "node.package_json",
        "python.pyproject",
    ]


def test_normalize_every_state_passes_through():
    states = [
        "found",
        "absent",
        "unresolved",
        "too_large",
        "binary",
        "unsupported",
        "error",
    ]
    raw = {
        "contract_version": 1,
        "repos": [
            {
                "repo": "acme/multi",
                "ref_name": "main",
                "tree_sha": "e" * 40,
                "tree_complete": True,
                "artifacts": [
                    {
                        "selector_id": f"sel.{state}",
                        "path": f"path/{state}.txt" if state != "absent" else None,
                        "blob_sha": None,
                        "size_bytes": 0,
                        "state": state,
                        "encoding": None,
                        "content": None,
                        "detail": "",
                    }
                    for state in states
                ],
            }
        ],
    }
    doc = de.normalize(raw, provider(), GENERATED_AT, "f" * 64)
    seen_states = {a["state"] for a in doc["repos"][0]["artifacts"]}
    assert seen_states == set(states)


def test_normalize_carries_errors_from_raw():
    raw = raw_result()
    raw["errors"] = ["repo acme/gone: unresolved ref"]
    doc = de.normalize(raw, provider(), GENERATED_AT, "f" * 64)
    assert doc["errors"] == ["repo acme/gone: unresolved ref"]


def test_normalize_defaults_errors_to_empty_list_when_absent():
    doc = de.normalize(raw_result(), provider(), GENERATED_AT, "f" * 64)
    assert doc["errors"] == []


def test_normalize_is_deterministic_regardless_of_raw_repo_order():
    raw = raw_result()
    reordered = dict(raw)
    reordered["repos"] = list(reversed(raw["repos"]))

    doc_a = de.normalize(raw, provider(), GENERATED_AT, "f" * 64)
    doc_b = de.normalize(reordered, provider(), GENERATED_AT, "f" * 64)

    assert doc_a == doc_b


# --- secure write helpers ---------------------------------------------------


def test_secure_run_dir_has_mode_0700():
    run_dir = de.secure_run_dir()
    mode = stat.S_IMODE(run_dir.stat().st_mode)
    assert mode == 0o700


def test_write_evidence_file_has_mode_0600():
    run_dir = de.secure_run_dir()
    doc = de.normalize(raw_result(), provider(), GENERATED_AT, "f" * 64)

    path = de.write_evidence(run_dir, "dependency-evidence.json", doc)

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
    assert json.loads(path.read_text()) == doc


def test_write_evidence_refuses_to_overwrite_existing_file():
    run_dir = de.secure_run_dir()
    doc = de.normalize(raw_result(), provider(), GENERATED_AT, "f" * 64)

    de.write_evidence(run_dir, "dependency-evidence.json", doc)

    import pytest

    with pytest.raises(FileExistsError):
        de.write_evidence(run_dir, "dependency-evidence.json", doc)
