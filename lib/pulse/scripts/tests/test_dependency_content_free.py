"""Injects a canary string into malformed manifest content and a forced
parser-exception path, proving it appears in none of: the local CheckBlock,
the serialized deps-snapshot.json, or the fleet dependency_collector — across
every real F4 boundary (adapters, evaluate_dependencies, the snapshot
builder). Complements, never substitutes for, the schema validators."""

from __future__ import annotations

from lib.pulse.scripts import dependency_pipeline as dp
from lib.pulse.scripts import dependency_snapshot as ds
from lib.pulse.scripts.adapters.node_dependencies import evaluate_node, parse_node
from lib.pulse.scripts.adapters.python_dependencies import evaluate_python, parse_python
from lib.pulse.scripts.check_adapters import CheckContext
from lib.pulse.scripts.dependency_evidence import Artifact, RepoEvidence
from pathlib import Path


CANARY = "CANARY-LEAKED-CONTENT-4b7e1c-should-never-surface"


def _found(path, content, selector_id=None):
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


def _absent(path, selector_id=None):
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


def _evidence(repo, artifacts):
    return RepoEvidence(repo=repo, ref_name="main", tree_sha="b" * 40, tree_complete=True, artifacts=tuple(artifacts))


def test_malformed_python_manifest_canary_never_surfaces():
    content = f"not [ valid toml -- {CANARY}"
    evidence = _evidence(
        "acme/broken",
        [
            _found("pyproject.toml", content, selector_id="python.pyproject"),
            _found("uv.lock", '[[package]]\nname="x"\nversion="1.0.0"\n', selector_id="python.uv_lock"),
            _absent("poetry.lock", selector_id="python.poetry_lock"),
            _absent("pdm.lock", selector_id="python.pdm_lock"),
            _absent("environment.yml", selector_id="python.conda_env"),
        ],
    )
    evaluation = parse_python("acme/broken", evidence, capability=True)
    assert CANARY not in repr(evaluation)
    assert CANARY not in str(evaluation.local_reason_code)

    context = CheckContext(
        repo="acme/broken",
        evidence={"dependency_evaluations": {"python": evaluation}},
        check={"id": "python_manifest_lock_consistency", "adapter": "python.dependencies", "weight": 1},
        workspace=Path("."),
    )
    block = evaluate_python(context)
    assert CANARY not in block["detail"]
    assert CANARY not in repr(block["data"])


def test_malformed_node_manifest_canary_never_surfaces():
    content = f'{{"not valid json {CANARY}'
    evidence = _evidence(
        "acme/broken-node",
        [
            _found("package.json", content, selector_id="node.package_json"),
            _found("package-lock.json", '{"lockfileVersion":3,"packages":{}}', selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/broken-node", evidence, capability=True)
    assert CANARY not in repr(evaluation)

    context = CheckContext(
        repo="acme/broken-node",
        evidence={"dependency_evaluations": {"node": evaluation}},
        check={"id": "node_manifest_lock_consistency", "adapter": "node.dependencies", "weight": 1},
        workspace=Path("."),
    )
    block = evaluate_node(context)
    assert CANARY not in block["detail"]
    assert CANARY not in repr(block["data"])


def test_forced_parser_exception_canary_never_surfaces(monkeypatch):
    def _boom(repo, evidence, *, capability):
        raise RuntimeError(f"internal failure containing {CANARY}")

    monkeypatch.setattr(dp, "parse_python", _boom)
    evidence = _evidence(
        "acme/exploding",
        [
            _found("pyproject.toml", "[project]\nname='x'\n", selector_id="python.pyproject"),
            _found("uv.lock", "", selector_id="python.uv_lock"),
        ],
    )
    evaluation = dp.evaluate_dependencies("acme/exploding", "python", evidence)
    assert evaluation.local_status == "error"
    assert CANARY not in repr(evaluation)
    assert CANARY not in str(evaluation.local_reason_code)
    assert evaluation.local_reason_code == "internal_parser_error"

    context = CheckContext(
        repo="acme/exploding",
        evidence={"dependency_evaluations": {"python": evaluation}},
        check={"id": "python_manifest_lock_consistency", "adapter": "python.dependencies", "weight": 1},
        workspace=Path("."),
    )
    block = evaluate_python(context)
    assert CANARY not in block["detail"]
    assert CANARY not in repr(block["data"])


def test_canary_never_surfaces_end_to_end_from_forced_exception_to_snapshot(
    monkeypatch, tmp_path
):
    """A parser exception carrying the canary, forced deep inside evaluate_fleet's
    per-repo pass, must never resurface in the collector evaluate_fleet
    populates or in the snapshot dependency_snapshot.serialize() emits from
    that same collector."""
    import yaml

    from lib.pulse.scripts.healthcheck_dispatch import evaluate_fleet

    def _boom(repo, evidence, *, capability):
        raise RuntimeError(f"internal failure containing {CANARY}")

    monkeypatch.setattr(dp, "parse_python", _boom)

    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text(
        yaml.safe_dump(
            {
                "repository_profiles": {"acme/api": {"profiles": [], "scorecard": "py-v1"}},
                "scorecards": {
                    "py-v1": {
                        "checks": [
                            {
                                "id": "python_manifest_lock_consistency",
                                "adapter": "python.dependencies",
                                "weight": 1,
                            }
                        ]
                    }
                },
                "adapters": {"python.dependencies": {"state": "available"}},
            }
        )
    )
    evidence = _evidence(
        "acme/api",
        [
            _found("pyproject.toml", "[project]\nname='x'\n", selector_id="python.pyproject"),
            _found("uv.lock", "", selector_id="python.uv_lock"),
        ],
    )
    collector: dict = {}
    result = evaluate_fleet(
        evidence={"repos": [{"repo": "acme/api"}]},
        profiles_path=profiles_path,
        workspace=tmp_path,
        dependency_evidence={"acme/api": evidence},
        dependency_collector=collector,
    )
    assert CANARY not in repr(result)
    assert CANARY not in repr(collector)

    document = ds.build_document(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        collector=collector,
        errors=(),
    )
    wire = ds.serialize(document)
    assert CANARY not in repr(wire)
