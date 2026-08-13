#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0", "packaging>=24.0", "semantic-version>=2.10"]
# ///
"""Build and serialize the versioned, content-free dependency snapshot
(deps-snapshot.json) from evaluate_fleet's own dependency_collector output.

Never reconstructs state from public, possibly-dismissed CheckBlocks — the
collector carries the exact typed objects evaluate_fleet used internally to
build the durable healthcheck's coverage.dependencies field, so this snapshot
and that field are guaranteed to reconcile identically.
"""

from __future__ import annotations

from typing import Any

from lib.pulse.scripts.dependencies import (
    CoherenceGroup,
    DependencySnapshot,
    DependencySnapshotDocument,
    PackageRecord,
    RepositoryEvaluationSummary,
    reconcile_coverage,
)
from lib.pulse.scripts.dependency_pipeline import (
    dependency_coverage_to_dict,
    divergence_finding_to_dict,
)


def build_document(
    *,
    contract_version: int,
    generated_at: str,
    request_sha256: str,
    collector: dict[str, Any],
    errors: tuple[str, ...],
) -> DependencySnapshotDocument:
    """Assemble the envelope from evaluate_fleet's collector output.

    Calls the same shared `reconcile_coverage` Task 4 called for the durable
    `coverage.dependencies` field, over the same collected inputs — this is
    the driver-level glue that keeps the durable result and the transient
    snapshot from silently diverging.
    """
    groups: tuple[CoherenceGroup, ...] = tuple(collector["groups"])
    repository_evaluations: tuple[RepositoryEvaluationSummary, ...] = tuple(
        sorted(collector["repository_evaluations"], key=lambda s: (s.repo, s.ecosystem))
    )
    records: tuple[PackageRecord, ...] = tuple(
        sorted(collector["records"], key=lambda r: (r.repo, r.ecosystem, r.name))
    )
    coverage = reconcile_coverage(repository_evaluations, groups)

    snapshot = DependencySnapshot(
        records=records,
        groups=groups,
        report=collector["report"],
        coverage=coverage,
        repository_evaluations=repository_evaluations,
    )
    return DependencySnapshotDocument(
        contract_version=contract_version,
        generated_at=generated_at,
        request_sha256=request_sha256,
        snapshot=snapshot,
        errors=tuple(errors),
    )


def _record_to_dict(record: PackageRecord) -> dict[str, Any]:
    return {
        "repo": record.repo,
        "ecosystem": record.ecosystem,
        "name": record.name,
        "resolution": record.resolution,
        "manifest_range": record.manifest_range,
        "locked_version": record.locked_version,
        "unresolved_reason": record.unresolved_reason,
        "manager": record.manager,
        "manifest_path": record.manifest_path,
        "lock_path": record.lock_path,
        "tree_sha": record.tree_sha,
        "provenance": [
            {"role": p.role, "path": p.path, "blob_sha": p.blob_sha} for p in record.provenance
        ],
    }


def _group_to_dict(group: CoherenceGroup) -> dict[str, Any]:
    return {
        "policy": group.policy,
        "repos": list(group.repos),
        "packages": list(group.packages),
        "exclude_packages": list(group.exclude_packages),
    }


def _summary_to_dict(summary: RepositoryEvaluationSummary) -> dict[str, Any]:
    return {
        "repo": summary.repo,
        "ecosystem": summary.ecosystem,
        "adapter": summary.adapter,
        "status": summary.status,
        "reason_code": summary.reason_code,
        "total_packages": summary.total_packages,
        "matched_packages": summary.matched_packages,
        "partial_unsupported": summary.partial_unsupported,
        "group_memberships": list(summary.group_memberships),
    }


def serialize(document: DependencySnapshotDocument) -> dict[str, Any]:
    """Deterministic dict matching the deps-snapshot.json wire schema
    field-for-field with DependencySnapshotDocument and every nested
    dataclass."""
    snapshot = document.snapshot
    findings = sorted(
        snapshot.report.findings, key=lambda f: (f.group, f.ecosystem, f.package)
    )
    unresolved = sorted(
        snapshot.report.unresolved, key=lambda f: (f.group, f.ecosystem, f.package)
    )
    return {
        "contract_version": document.contract_version,
        "generated_at": document.generated_at,
        "request_sha256": document.request_sha256,
        "records": [_record_to_dict(r) for r in snapshot.records],
        "groups": {group.id: _group_to_dict(group) for group in snapshot.groups},
        "findings": [divergence_finding_to_dict(f) for f in findings],
        "unresolved": [divergence_finding_to_dict(f) for f in unresolved],
        "repository_evaluations": [
            _summary_to_dict(s) for s in snapshot.repository_evaluations
        ],
        "coverage": dependency_coverage_to_dict(snapshot.coverage),
        "errors": list(document.errors),
    }
