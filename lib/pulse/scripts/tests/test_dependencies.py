"""Tests for PackageRecord/CoherenceGroup comparison and coverage reconciliation."""

from __future__ import annotations

from lib.pulse.scripts.dependencies import (
    ArtifactProvenance,
    CoherenceGroup,
    DependencySnapshot,
    DependencySnapshotDocument,
    DivergenceFinding,
    DivergenceReport,
    PackageRecord,
    RepositoryEvaluationSummary,
    compare,
    reconcile_coverage,
)


def _record(
    repo,
    name,
    *,
    ecosystem="python",
    resolution="single",
    manifest_range="^1.0.0",
    locked_version="1.0.0",
    unresolved_reason=None,
    manager="uv",
    manifest_path="pyproject.toml",
    lock_path="uv.lock",
    tree_sha=None,
    provenance=(),
):
    return PackageRecord(
        repo=repo,
        ecosystem=ecosystem,
        name=name,
        resolution=resolution,
        manifest_range=manifest_range,
        locked_version=locked_version,
        unresolved_reason=unresolved_reason,
        manager=manager,
        manifest_path=manifest_path,
        lock_path=lock_path,
        tree_sha=tree_sha,
        provenance=provenance,
    )


def _group(id_, repos, packages, *, exclude_packages=(), policy="same-minor"):
    return CoherenceGroup(
        id=id_,
        repos=tuple(repos),
        packages=tuple(packages),
        exclude_packages=tuple(exclude_packages),
        policy=policy,
    )


# --- exact / major / minor / patch pairwise divergence -----------------------


def test_python_major_divergence():
    records = [
        _record("acme/api", "requests", locked_version="1.0.0"),
        _record("acme/worker", "requests", locked_version="2.0.0"),
    ]
    group = _group("g1", ["acme/api", "acme/worker"], ["python:requests"])
    report = compare(records, [group])
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.group == "g1"
    assert finding.ecosystem == "python"
    assert finding.package == "requests"
    assert finding.distance == "major"
    assert dict(finding.versions) == {"acme/api": "1.0.0", "acme/worker": "2.0.0"}
    assert report.unresolved == ()


def test_python_minor_divergence():
    records = [
        _record("acme/api", "requests", locked_version="1.2.0"),
        _record("acme/worker", "requests", locked_version="1.3.0"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    assert report.findings[0].distance == "minor"


def test_python_patch_divergence_from_pre_dev_local_identifier():
    records = [
        _record("acme/api", "requests", locked_version="2"),
        _record("acme/worker", "requests", locked_version="2.dev1"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    # Regression case: both release tuples are (2,) — equal length — but the
    # full versions differ via the .dev1 suffix. Must resolve to "patch", not
    # crash on release[1] and not silently report no divergence.
    assert len(report.findings) == 1
    assert report.findings[0].distance == "patch"


def test_python_epoch_difference_is_always_major():
    records = [
        _record("acme/api", "requests", locked_version="1!1.0.0"),
        _record("acme/worker", "requests", locked_version="1.0.0"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    assert report.findings[0].distance == "major"


def test_python_equal_versions_produce_no_finding():
    records = [
        _record("acme/api", "requests", locked_version="1.0.0"),
        _record("acme/worker", "requests", locked_version="1.0.0"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    assert report.findings == ()
    assert report.unresolved == ()


def test_npm_patch_divergence():
    records = [
        _record("acme/api", "@acme/widgets", ecosystem="npm", locked_version="1.2.3"),
        _record("acme/worker", "@acme/widgets", ecosystem="npm", locked_version="1.2.4"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["npm:@acme/*"])])
    assert report.findings[0].distance == "patch"


def test_npm_minor_divergence():
    records = [
        _record("acme/api", "@acme/widgets", ecosystem="npm", locked_version="1.2.3"),
        _record("acme/worker", "@acme/widgets", ecosystem="npm", locked_version="1.3.0"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["npm:@acme/*"])])
    assert report.findings[0].distance == "minor"


def test_npm_major_divergence():
    records = [
        _record("acme/api", "@acme/widgets", ecosystem="npm", locked_version="1.2.3"),
        _record("acme/worker", "@acme/widgets", ecosystem="npm", locked_version="2.0.0"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["npm:@acme/*"])])
    assert report.findings[0].distance == "major"


def test_npm_prerelease_only_difference_is_patch():
    records = [
        _record("acme/api", "@acme/widgets", ecosystem="npm", locked_version="1.2.3"),
        _record("acme/worker", "@acme/widgets", ecosystem="npm", locked_version="1.2.3-beta.1"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["npm:@acme/*"])])
    assert report.findings[0].distance == "patch"


# --- group-level coarsest-pairwise-distance reduction (3+ members) ----------


def test_three_member_group_reduces_to_coarsest_pairwise_distance():
    records = [
        _record("acme/api", "requests", locked_version="1.2.0"),
        _record("acme/worker", "requests", locked_version="1.3.0"),
        _record("acme/edge", "requests", locked_version="2.0.0"),
    ]
    group = _group("g1", ["acme/api", "acme/worker", "acme/edge"], ["python:requests"])
    report = compare(records, [group])
    assert len(report.findings) == 1
    assert report.findings[0].distance == "major"
    assert dict(report.findings[0].versions) == {
        "acme/api": "1.2.0",
        "acme/worker": "1.3.0",
        "acme/edge": "2.0.0",
    }


# --- unresolved / non-range specs -------------------------------------------


def test_multiple_resolution_record_is_unresolved_not_dropped():
    records = [
        _record("acme/api", "requests", locked_version="1.0.0"),
        _record(
            "acme/worker",
            "requests",
            resolution="multiple",
            manifest_range=None,
            locked_version=None,
            unresolved_reason="multiple_resolutions",
            lock_path=None,
        ),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    assert report.findings == ()
    assert len(report.unresolved) == 1
    finding = report.unresolved[0]
    assert finding.distance == "unresolved"
    assert dict(finding.versions) == {"acme/api": "1.0.0", "acme/worker": None}


def test_unparseable_locked_version_is_unresolved():
    records = [
        _record("acme/api", "requests", locked_version="1.0.0"),
        _record(
            "acme/worker",
            "requests",
            locked_version="not-a-version",
            unresolved_reason="unparseable_version",
        ),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    assert report.findings == ()
    assert len(report.unresolved) == 1
    assert dict(report.unresolved[0].versions) == {"acme/api": "1.0.0", "acme/worker": None}


def test_non_range_spec_record_is_still_eligible_for_distance_comparison():
    # unresolved_reason="non_range_spec" describes the *manifest_range*, not the
    # locked_version — a resolution="single" record with a parseable
    # locked_version participates in fleet distance comparison normally.
    records = [
        _record(
            "acme/api",
            "requests",
            manifest_range=None,
            unresolved_reason="non_range_spec",
            locked_version="1.0.0",
        ),
        _record("acme/worker", "requests", locked_version="2.0.0"),
    ]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    assert report.unresolved == ()
    assert len(report.findings) == 1
    assert report.findings[0].distance == "major"


def test_single_member_bucket_produces_no_finding():
    records = [_record("acme/api", "requests", locked_version="1.0.0")]
    report = compare(records, [_group("g1", ["acme/api", "acme/worker"], ["python:requests"])])
    assert report.findings == ()
    assert report.unresolved == ()


def test_compare_accepts_a_one_shot_iterator_of_records_across_multiple_groups():
    # records is documented as Iterable[PackageRecord] — a generator (consumed
    # once) must still produce findings for every group, not just the first.
    def _records():
        yield _record("acme/api", "requests", locked_version="1.0.0")
        yield _record("acme/worker", "requests", locked_version="2.0.0")

    groups = [
        _group("g1", ["acme/api", "acme/worker"], ["python:requests"]),
        _group("g2", ["acme/api", "acme/worker"], ["python:requests"]),
    ]
    report = compare(_records(), groups)
    assert {f.group for f in report.findings} == {"g1", "g2"}


# --- ecosystem / group scoping ------------------------------------------------


def test_cross_ecosystem_same_name_packages_are_never_compared():
    records = [
        _record("acme/api", "requests", ecosystem="python", locked_version="1.0.0"),
        _record("acme/worker", "requests", ecosystem="npm", locked_version="2.0.0"),
    ]
    group = _group(
        "g1", ["acme/api", "acme/worker"], ["python:requests", "npm:requests"]
    )
    report = compare(records, [group])
    assert report.findings == ()
    assert report.unresolved == ()


def test_repos_outside_the_group_are_excluded():
    records = [
        _record("acme/api", "requests", locked_version="1.0.0"),
        _record("acme/worker", "requests", locked_version="1.0.0"),
        _record("acme/outsider", "requests", locked_version="9.0.0"),
    ]
    group = _group("g1", ["acme/api", "acme/worker"], ["python:requests"])
    report = compare(records, [group])
    assert report.findings == ()
    assert report.unresolved == ()


def test_exclude_always_wins_over_include():
    records = [
        _record("acme/api", "typing-extensions", locked_version="1.0.0"),
        _record("acme/worker", "typing-extensions", locked_version="2.0.0"),
    ]
    group = _group(
        "g1",
        ["acme/api", "acme/worker"],
        ["python:*"],
        exclude_packages=["python:typing-extensions"],
    )
    report = compare(records, [group])
    assert report.findings == ()
    assert report.unresolved == ()


def test_overlapping_groups_with_different_policies_produce_independent_findings():
    records = [
        _record("acme/api", "requests", locked_version="1.0.0"),
        _record("acme/worker", "requests", locked_version="1.1.0"),
    ]
    groups = [
        _group("strict", ["acme/api", "acme/worker"], ["python:requests"], policy="exact"),
        _group("loose", ["acme/api", "acme/worker"], ["python:requests"], policy="same-major"),
    ]
    report = compare(records, groups)
    assert len(report.findings) == 2
    ids = {f.group for f in report.findings}
    assert ids == {"strict", "loose"}
    assert all(f.distance == "minor" for f in report.findings)


def test_finding_identity_is_group_ecosystem_package_and_deterministically_ordered():
    records = [
        _record("acme/api", "zeta", locked_version="1.0.0"),
        _record("acme/worker", "zeta", locked_version="2.0.0"),
        _record("acme/api", "alpha", locked_version="1.0.0"),
        _record("acme/worker", "alpha", locked_version="2.0.0"),
    ]
    group = _group("g1", ["acme/api", "acme/worker"], ["python:zeta", "python:alpha"])
    report = compare(records, [group])
    assert [f.package for f in report.findings] == ["alpha", "zeta"]


# --- reconcile_coverage -------------------------------------------------------


def _summary(
    repo,
    *,
    ecosystem="python",
    adapter="python.dependencies",
    status="pass",
    reason_code=None,
    total_packages=0,
    matched_packages=0,
    partial_unsupported=0,
    group_memberships=(),
):
    return RepositoryEvaluationSummary(
        repo=repo,
        ecosystem=ecosystem,
        adapter=adapter,
        status=status,
        reason_code=reason_code,
        total_packages=total_packages,
        matched_packages=matched_packages,
        partial_unsupported=partial_unsupported,
        group_memberships=tuple(group_memberships),
    )


def test_reconcile_coverage_counts_distinct_repos_once_for_polyglot_repo():
    evaluations = [
        _summary("acme/api", ecosystem="python", adapter="python.dependencies"),
        _summary("acme/api", ecosystem="node", adapter="node.dependencies"),
    ]
    coverage = reconcile_coverage(evaluations, [])
    assert coverage.repositories_selected == 1


def test_reconcile_coverage_handles_repo_contributing_zero_records():
    evaluations = [
        _summary("acme/api", status="unsupported", total_packages=0, matched_packages=0)
    ]
    coverage = reconcile_coverage(evaluations, [])
    assert coverage.repositories_selected == 1
    assert coverage.repositories_grouped == 0
    assert coverage.repositories_ungrouped == 1
    assert coverage.packages_matched == 0
    assert coverage.packages_unmatched == 0
    assert coverage.unsupported_by_adapter["python.dependencies"] == 1


def test_reconcile_coverage_overlapping_groups_only_flags_insufficient_one():
    groups = [
        _group("well-covered", ["acme/api", "acme/worker"], ["python:*"]),
        _group("under-covered", ["acme/api", "acme/other"], ["python:*"]),
    ]
    evaluations = [
        _summary(
            "acme/api",
            total_packages=2,
            matched_packages=2,
            group_memberships=("well-covered", "under-covered"),
        ),
        _summary(
            "acme/worker",
            total_packages=2,
            matched_packages=2,
            group_memberships=("well-covered",),
        ),
        # acme/other selects the ecosystem but has no comparable record in
        # under-covered — its evaluation carries no membership for it.
        _summary("acme/other", total_packages=1, matched_packages=0),
    ]
    coverage = reconcile_coverage(evaluations, groups)
    assert coverage.groups_with_insufficient_members == ("under-covered",)
    assert coverage.repositories_grouped == 2
    assert coverage.repositories_ungrouped == 1
    assert coverage.packages_matched == 4
    assert coverage.packages_unmatched == 1


def test_reconcile_coverage_partial_unsupported_alongside_pass_status():
    evaluations = [
        _summary(
            "acme/api",
            status="pass",
            total_packages=5,
            matched_packages=3,
            partial_unsupported=2,
        )
    ]
    coverage = reconcile_coverage(evaluations, [])
    assert coverage.unsupported_by_adapter["python.dependencies"] == 2
    assert coverage.packages_matched == 3
    assert coverage.packages_unmatched == 2


# --- dataclass shape / field round-trip --------------------------------------


def test_package_record_provenance_preserves_role_path_blob_sha():
    provenance = (
        ArtifactProvenance(role="manifest", path="pyproject.toml", blob_sha="a" * 40),
        ArtifactProvenance(role="lock", path="uv.lock", blob_sha="b" * 40),
    )
    record = _record("acme/api", "requests", provenance=provenance)
    assert record.provenance == provenance
    assert record.provenance[0].role == "manifest"
    assert record.provenance[0].path == "pyproject.toml"
    assert record.provenance[0].blob_sha == "a" * 40
    assert record.provenance[1].role == "lock"


def test_coherence_group_every_field_round_trips_through_snapshot_document():
    group = _group(
        "core-runtime",
        ["acme/api", "acme/worker"],
        ["python:requests", "npm:@acme/*"],
        exclude_packages=["python:typing-extensions"],
        policy="same-minor",
    )
    record = _record("acme/api", "requests")
    finding = DivergenceFinding(
        group="core-runtime",
        ecosystem="python",
        package="requests",
        versions=(("acme/api", "1.0.0"), ("acme/worker", "2.0.0")),
        distance="major",
    )
    report = DivergenceReport(findings=(finding,), unresolved=())
    summary = _summary("acme/api", total_packages=1, matched_packages=1)
    coverage = reconcile_coverage([summary], [group])
    snapshot = DependencySnapshot(
        records=(record,),
        groups=(group,),
        report=report,
        coverage=coverage,
        repository_evaluations=(summary,),
    )
    document = DependencySnapshotDocument(
        contract_version=1,
        generated_at="2026-07-18T10:00:00Z",
        request_sha256="f" * 64,
        snapshot=snapshot,
        errors=(),
    )
    round_tripped = document.snapshot.groups[0]
    assert round_tripped.id == group.id
    assert round_tripped.repos == group.repos
    assert round_tripped.packages == group.packages
    assert round_tripped.exclude_packages == group.exclude_packages
    assert round_tripped.policy == group.policy
    assert document.snapshot.report.findings[0].distance == "major"
