"""Tests for building and serializing the deps-snapshot.json envelope."""

from __future__ import annotations

from lib.pulse.scripts import dependency_snapshot as ds
from lib.pulse.scripts.dependencies import (
    ArtifactProvenance,
    CoherenceGroup,
    DivergenceFinding,
    DivergenceReport,
    PackageRecord,
    RepositoryEvaluationSummary,
)


def _record(repo, name, *, ecosystem="python", locked_version="1.0.0"):
    return PackageRecord(
        repo=repo,
        ecosystem=ecosystem,
        name=name,
        resolution="single",
        manifest_range=">=1.0",
        locked_version=locked_version,
        unresolved_reason=None,
        manager="uv",
        manifest_path="pyproject.toml",
        lock_path="uv.lock",
        tree_sha="a" * 40,
        provenance=(
            ArtifactProvenance(role="manifest", path="pyproject.toml", blob_sha="b" * 40),
            ArtifactProvenance(role="lock", path="uv.lock", blob_sha="c" * 40),
        ),
    )


def _group():
    return CoherenceGroup(
        id="core-runtime",
        repos=("acme/api", "acme/worker"),
        packages=("python:requests",),
        exclude_packages=("python:typing-extensions",),
        policy="same-minor",
    )


def _summary(repo, *, group_memberships=("core-runtime",)):
    return RepositoryEvaluationSummary(
        repo=repo,
        ecosystem="python",
        adapter="python.dependencies",
        status="pass",
        reason_code=None,
        total_packages=1,
        matched_packages=1,
        partial_unsupported=0,
        group_memberships=group_memberships,
    )


def _collector():
    finding = DivergenceFinding(
        group="core-runtime",
        ecosystem="python",
        package="requests",
        versions=(("acme/api", "2.32.0"), ("acme/worker", "2.30.0")),
        distance="minor",
    )
    return {
        "records": (
            _record("acme/api", "requests", locked_version="2.32.0"),
            _record("acme/worker", "requests", locked_version="2.30.0"),
        ),
        "groups": (_group(),),
        "report": DivergenceReport(findings=(finding,), unresolved=()),
        "repository_evaluations": (_summary("acme/worker"), _summary("acme/api")),
    }


def test_build_document_reconciles_coverage_from_collector():
    document = ds.build_document(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        collector=_collector(),
        errors=(),
    )
    assert document.snapshot.coverage.repositories_selected == 2
    assert document.snapshot.coverage.repositories_grouped == 2
    assert document.snapshot.coverage.groups_with_insufficient_members == ()


def test_build_document_sorts_records_and_summaries():
    document = ds.build_document(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        collector=_collector(),
        errors=(),
    )
    assert [r.repo for r in document.snapshot.records] == ["acme/api", "acme/worker"]
    assert [s.repo for s in document.snapshot.repository_evaluations] == [
        "acme/api",
        "acme/worker",
    ]


def test_serialize_produces_the_exact_wire_shape():
    document = ds.build_document(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        collector=_collector(),
        errors=(),
    )
    wire = ds.serialize(document)
    assert set(wire) == {
        "contract_version",
        "generated_at",
        "request_sha256",
        "records",
        "groups",
        "findings",
        "unresolved",
        "repository_evaluations",
        "coverage",
        "errors",
    }
    assert wire["contract_version"] == 1
    assert wire["request_sha256"] == "f" * 64

    # groups is a MAPPING keyed by group id, matching the policy file's shape.
    assert wire["groups"] == {
        "core-runtime": {
            "policy": "same-minor",
            "repos": ["acme/api", "acme/worker"],
            "packages": ["python:requests"],
            "exclude_packages": ["python:typing-extensions"],
        }
    }

    record = wire["records"][0]
    assert record["repo"] == "acme/api"
    assert record["provenance"] == [
        {"role": "manifest", "path": "pyproject.toml", "blob_sha": "b" * 40},
        {"role": "lock", "path": "uv.lock", "blob_sha": "c" * 40},
    ]

    assert wire["findings"] == [
        {
            "group": "core-runtime",
            "ecosystem": "python",
            "package": "requests",
            "versions": [["acme/api", "2.32.0"], ["acme/worker", "2.30.0"]],
            "distance": "minor",
        }
    ]
    assert wire["unresolved"] == []

    summary = wire["repository_evaluations"][0]
    assert summary["repo"] == "acme/api"
    assert summary["group_memberships"] == ["core-runtime"]

    assert wire["coverage"]["repositories_selected"] == 2
    assert wire["errors"] == []


def test_serialize_findings_and_unresolved_sorted_by_group_ecosystem_package():
    collector = _collector()
    extra_finding = DivergenceFinding(
        group="core-runtime",
        ecosystem="python",
        package="alpha",
        versions=(("acme/api", "1.0.0"), ("acme/worker", "2.0.0")),
        distance="major",
    )
    collector["report"] = DivergenceReport(
        findings=(collector["report"].findings[0], extra_finding), unresolved=()
    )
    document = ds.build_document(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        collector=collector,
        errors=(),
    )
    wire = ds.serialize(document)
    assert [f["package"] for f in wire["findings"]] == ["alpha", "requests"]


def test_errors_propagate_into_the_serialized_envelope():
    document = ds.build_document(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        collector=_collector(),
        errors=("dependencies.yaml missing: fleet_dependency_coherence unresolved",),
    )
    wire = ds.serialize(document)
    assert wire["errors"] == [
        "dependencies.yaml missing: fleet_dependency_coherence unresolved"
    ]
