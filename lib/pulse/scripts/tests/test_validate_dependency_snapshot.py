"""Tests for the strict deps-snapshot.json validator, including the
coverage-vs-reconcile_coverage reconciliation check on overlapping groups."""

from __future__ import annotations


from lib.pulse.scripts import dependency_snapshot as ds
from lib.pulse.scripts import validate_dependency_snapshot as vds
from lib.pulse.scripts.dependencies import (
    ArtifactProvenance,
    CoherenceGroup,
    DivergenceFinding,
    DivergenceReport,
    PackageRecord,
    RepositoryEvaluationSummary,
)


def _record(repo, name, *, locked_version="1.0.0"):
    return PackageRecord(
        repo=repo,
        ecosystem="python",
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


def _summary(repo, *, group_memberships=(), total=1, matched=1):
    return RepositoryEvaluationSummary(
        repo=repo,
        ecosystem="python",
        adapter="python.dependencies",
        status="pass",
        reason_code=None,
        total_packages=total,
        matched_packages=matched,
        partial_unsupported=0,
        group_memberships=group_memberships,
    )


def _valid_wire():
    finding = DivergenceFinding(
        group="well-covered",
        ecosystem="python",
        package="requests",
        versions=(("acme/api", "2.32.0"), ("acme/worker", "2.30.0")),
        distance="minor",
    )
    groups = (
        CoherenceGroup(
            id="well-covered",
            repos=("acme/api", "acme/worker"),
            packages=("python:requests",),
            exclude_packages=(),
            policy="same-minor",
        ),
        CoherenceGroup(
            id="under-covered",
            repos=("acme/api", "acme/solo"),
            packages=("python:requests",),
            exclude_packages=(),
            policy="same-minor",
        ),
    )
    collector = {
        "records": (
            _record("acme/api", "requests", locked_version="2.32.0"),
            _record("acme/worker", "requests", locked_version="2.30.0"),
            _record("acme/solo", "flask", locked_version="1.0.0"),
        ),
        "groups": groups,
        "report": DivergenceReport(findings=(finding,), unresolved=()),
        "repository_evaluations": (
            _summary("acme/api", group_memberships=("under-covered", "well-covered")),
            _summary("acme/worker", group_memberships=("well-covered",)),
            _summary("acme/solo", total=1, matched=0),
        ),
    }
    document = ds.build_document(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        collector=collector,
        errors=(),
    )
    return ds.serialize(document)


def test_valid_document_has_no_errors():
    assert vds.validate(_valid_wire()) == []


def test_coverage_reconciles_including_overlapping_groups_and_unmatched():
    wire = _valid_wire()
    assert wire["coverage"]["groups_with_insufficient_members"] == ["under-covered"]
    assert wire["coverage"]["packages_unmatched"] == 1  # acme/solo's flask


def test_tampered_coverage_is_rejected():
    wire = _valid_wire()
    wire["coverage"]["packages_matched"] = 999
    errors = vds.validate(wire)
    assert any("reconcile_coverage" in e for e in errors)


def test_duplicate_repo_ecosystem_name_record_rejected():
    wire = _valid_wire()
    wire["records"].append(dict(wire["records"][0]))
    errors = vds.validate(wire)
    assert any("duplicate" in e for e in errors)


def test_out_of_order_records_rejected():
    wire = _valid_wire()
    wire["records"] = list(reversed(wire["records"]))
    errors = vds.validate(wire)
    assert any("sorted" in e for e in errors)


def test_finding_referencing_unknown_group_rejected():
    wire = _valid_wire()
    wire["findings"][0]["group"] = "does-not-exist"
    errors = vds.validate(wire)
    assert any("group not in groups" in e for e in errors)


def test_findings_and_unresolved_must_be_disjoint():
    wire = _valid_wire()
    wire["unresolved"] = [dict(wire["findings"][0], distance="unresolved")]
    errors = vds.validate(wire)
    assert any("disjoint" in e for e in errors)


def test_invalid_ecosystem_literal_rejected():
    wire = _valid_wire()
    wire["records"][0]["ecosystem"] = "node"  # package-namespace literal must be python|npm
    errors = vds.validate(wire)
    assert any("ecosystem invalid" in e for e in errors)


def test_repository_evaluation_ecosystem_rejects_package_namespace_literal():
    wire = _valid_wire()
    wire["repository_evaluations"][0]["ecosystem"] = "npm"  # must be python|node here
    errors = vds.validate(wire)
    assert any("ecosystem invalid" in e for e in errors)


def test_malformed_tree_sha_rejected():
    wire = _valid_wire()
    wire["records"][0]["tree_sha"] = "not-hex"
    errors = vds.validate(wire)
    assert any("tree_sha" in e for e in errors)


def test_multiple_resolution_requires_null_range_and_version():
    wire = _valid_wire()
    wire["records"][0]["resolution"] = "multiple"
    wire["records"][0]["unresolved_reason"] = "multiple_resolutions"
    # locked_version/manifest_range still populated — contract violation.
    errors = vds.validate(wire)
    assert any("resolution=multiple requires null" in e for e in errors)


def test_unknown_top_level_key_rejected():
    wire = _valid_wire()
    wire["extra"] = True
    errors = vds.validate(wire)
    assert any("unknown key: extra" in e for e in errors)


def test_negative_repository_evaluation_counter_rejected():
    wire = _valid_wire()
    wire["repository_evaluations"][0]["total_packages"] = -1
    errors = vds.validate(wire)
    assert any("total_packages must be a non-negative integer" in e for e in errors)


def test_matched_exceeding_total_packages_rejected():
    wire = _valid_wire()
    wire["repository_evaluations"][0]["total_packages"] = 1
    wire["repository_evaluations"][0]["matched_packages"] = 2
    errors = vds.validate(wire)
    assert any("matched_packages must not exceed total_packages" in e for e in errors)


def test_non_string_group_list_member_rejected():
    wire = _valid_wire()
    wire["groups"]["well-covered"]["packages"] = [123]
    errors = vds.validate(wire)
    assert any("packages must be a list of non-empty strings" in e for e in errors)


def test_empty_group_repos_rejected():
    wire = _valid_wire()
    wire["groups"]["well-covered"]["repos"] = []
    errors = vds.validate(wire)
    assert any("repos must be non-empty" in e for e in errors)


def test_duplicate_repository_evaluation_pair_rejected():
    wire = _valid_wire()
    wire["repository_evaluations"].append(dict(wire["repository_evaluations"][0]))
    errors = vds.validate(wire)
    assert any("duplicate (repo, ecosystem)" in e for e in errors)


def test_unsorted_group_memberships_rejected():
    wire = _valid_wire()
    wire["repository_evaluations"][0]["group_memberships"] = ["z-group", "a-group"]
    errors = vds.validate(wire)
    assert any("group_memberships must be sorted" in e for e in errors)


def test_duplicate_group_memberships_rejected():
    wire = _valid_wire()
    wire["repository_evaluations"][0]["group_memberships"] = ["well-covered", "well-covered"]
    errors = vds.validate(wire)
    assert any("group_memberships must not contain duplicates" in e for e in errors)


def test_missing_file_exits_2(tmp_path):
    assert vds.main([str(tmp_path / "missing.json")]) == 2


def test_valid_file_exits_0(tmp_path):
    import json

    path = tmp_path / "deps-snapshot.json"
    path.write_text(json.dumps(_valid_wire()))
    assert vds.main([str(path)]) == 0


def test_invalid_file_exits_1(tmp_path, capsys):
    import json

    wire = _valid_wire()
    wire["coverage"]["packages_matched"] = 999
    path = tmp_path / "deps-snapshot.json"
    path.write_text(json.dumps(wire))
    assert vds.main([str(path)]) == 1
    captured = capsys.readouterr()
    assert "reconcile_coverage" in captured.err
