#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0", "packaging>=24.0", "semantic-version>=2.10"]
# ///
"""Strictly validate a serialized deps-snapshot.json document.

Mirrors validate_dependency_evidence.py's pattern exactly: exact top-level/
nested keys, hex-string checks, enum checks, uniqueness/disjointness
invariants, deterministic ordering, and a `coverage` field recomputed via
`reconcile_coverage` and compared field-for-field against the serialized
block — a mismatch is a contract violation, not a warning.

This is a standalone versioned-artifact validator for the transient, gitignored
`deps-snapshot.json` — it is not a `validate_result.py` `kind`. The healthcheck
result's own `coverage.dependencies` field is validated inside
`validate_result.py`'s `kind == "healthcheck"` branch instead, since that
field is part of the durable result.

Usage: validate_dependency_snapshot.py FILE

Exit codes:
  0 - valid
  1 - parsed but invalid
  2 - missing or unparseable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from lib.pulse.scripts.dependencies import (
    CoherenceGroup,
    RepositoryEvaluationSummary,
    reconcile_coverage,
)


SUPPORTED_VERSIONS = {1}
CHECK_STATUSES = {
    "pass",
    "warn",
    "fail",
    "unknown",
    "not_applicable",
    "unsupported",
    "error",
}
PACKAGE_ECOSYSTEMS = {"python", "npm"}
ADAPTER_ECOSYSTEMS = {"python", "node"}
RESOLUTIONS = {"single", "multiple"}
RECORD_UNRESOLVED_REASONS = {"multiple_resolutions", "unparseable_version", "non_range_spec"}
POLICIES = {"exact", "same-major", "same-minor"}
ROLES = {"manifest", "lock"}
DISTANCES = {"major", "minor", "patch"}
ADAPTERS = {"python.dependencies", "node.dependencies"}

TOP_LEVEL_KEYS = {
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
RECORD_KEYS = {
    "repo",
    "ecosystem",
    "name",
    "resolution",
    "manifest_range",
    "locked_version",
    "unresolved_reason",
    "manager",
    "manifest_path",
    "lock_path",
    "tree_sha",
    "provenance",
}
PROVENANCE_KEYS = {"role", "path", "blob_sha"}
GROUP_KEYS = {"policy", "repos", "packages", "exclude_packages"}
FINDING_KEYS = {"group", "ecosystem", "package", "versions", "distance"}
SUMMARY_KEYS = {
    "repo",
    "ecosystem",
    "adapter",
    "status",
    "reason_code",
    "total_packages",
    "matched_packages",
    "partial_unsupported",
    "group_memberships",
}
COVERAGE_KEYS = {
    "repositories_selected",
    "repositories_grouped",
    "repositories_ungrouped",
    "groups_with_insufficient_members",
    "packages_matched",
    "packages_unmatched",
    "unsupported_by_adapter",
}

HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
REPO_NAME_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


def _type_name(types: type | tuple[type, ...]) -> str:
    if isinstance(types, tuple):
        return " or ".join(t.__name__ for t in types)
    return types.__name__


def require(data: dict[str, Any], key: str, types, errors: list[str], ctx: str = "") -> Any:
    label = f"{ctx}{key}"
    if key not in data:
        errors.append(f"missing required key: {label}")
        return None
    value = data[key]
    if not isinstance(value, types) or (
        isinstance(value, bool) and (types is int or (isinstance(types, tuple) and int in types))
    ):
        errors.append(f"wrong type for {label}: expected {_type_name(types)}, got {type(value).__name__}")
        return None
    return value


def require_nullable(data: dict[str, Any], key: str, types, errors: list[str], ctx: str = "") -> Any:
    if key not in data:
        errors.append(f"missing required key: {ctx}{key}")
        return None
    if data[key] is None:
        return None
    return require(data, key, types, errors, ctx)


def require_enum(data: dict[str, Any], key: str, allowed: set[str], errors: list[str], ctx: str = "") -> str | None:
    value = require(data, key, str, errors, ctx)
    if value is not None and value not in allowed:
        errors.append(f"{ctx}{key} invalid: {value}")
    return value


def require_nullable_enum(
    data: dict[str, Any], key: str, allowed: set[str], errors: list[str], ctx: str = ""
) -> str | None:
    value = require_nullable(data, key, str, errors, ctx)
    if value is not None and value not in allowed:
        errors.append(f"{ctx}{key} invalid: {value}")
    return value


def _require_exact_keys(data: dict[str, Any], allowed: set[str], errors: list[str], ctx: str) -> None:
    extra = sorted(set(data.keys()) - allowed)
    for key in extra:
        errors.append(f"unknown key: {ctx}{key}")
    for key in sorted(allowed - set(data.keys())):
        errors.append(f"missing required key: {ctx}{key}")


def _require_hex_or_null(data: dict[str, Any], key: str, errors: list[str], ctx: str) -> None:
    if key not in data:
        errors.append(f"missing required key: {ctx}{key}")
        return
    value = data[key]
    if value is not None and (not isinstance(value, str) or not (HEX40_RE.match(value) or HEX64_RE.match(value))):
        errors.append(f"{ctx}{key} must be a 40- or 64-char hex string or null")


def _validate_provenance(entry: Any, errors: list[str], ctx: str) -> None:
    if not isinstance(entry, dict):
        errors.append(f"{ctx[:-1]} is not a mapping")
        return
    _require_exact_keys(entry, PROVENANCE_KEYS, errors, ctx)
    require_enum(entry, "role", ROLES, errors, ctx)
    require(entry, "path", str, errors, ctx)
    _require_hex_or_null(entry, "blob_sha", errors, ctx)


def _validate_record(entry: Any, errors: list[str], ctx: str) -> tuple[str, str, str] | None:
    if not isinstance(entry, dict):
        errors.append(f"{ctx[:-1]} is not a mapping")
        return None
    _require_exact_keys(entry, RECORD_KEYS, errors, ctx)
    repo = require(entry, "repo", str, errors, ctx)
    if repo is not None and not REPO_NAME_RE.match(repo):
        errors.append(f"{ctx}repo must match owner/name: {repo}")
    ecosystem = require_enum(entry, "ecosystem", PACKAGE_ECOSYSTEMS, errors, ctx)
    name = require(entry, "name", str, errors, ctx)
    resolution = require_enum(entry, "resolution", RESOLUTIONS, errors, ctx)
    require_nullable(entry, "manifest_range", str, errors, ctx)
    require_nullable(entry, "locked_version", str, errors, ctx)
    unresolved_reason = require_nullable_enum(
        entry, "unresolved_reason", RECORD_UNRESOLVED_REASONS, errors, ctx
    )
    require(entry, "manager", str, errors, ctx)
    require_nullable(entry, "manifest_path", str, errors, ctx)
    require_nullable(entry, "lock_path", str, errors, ctx)
    _require_hex_or_null(entry, "tree_sha", errors, ctx)

    if resolution == "multiple":
        if entry.get("manifest_range") is not None or entry.get("locked_version") is not None:
            errors.append(f"{ctx}resolution=multiple requires null manifest_range/locked_version")
        if unresolved_reason != "multiple_resolutions":
            errors.append(f"{ctx}resolution=multiple requires unresolved_reason=multiple_resolutions")

    provenance = require(entry, "provenance", list, errors, ctx)
    for index, item in enumerate(provenance or []):
        _validate_provenance(item, errors, f"{ctx}provenance[{index}].")

    if repo is not None and ecosystem is not None and name is not None:
        return repo, ecosystem, name
    return None


def _validate_group(group_id: Any, entry: Any, errors: list[str], ctx: str) -> None:
    if not isinstance(group_id, str) or not group_id:
        errors.append(f"{ctx[:-1]} key must be a non-empty string")
    if not isinstance(entry, dict):
        errors.append(f"{ctx[:-1]} is not a mapping")
        return
    _require_exact_keys(entry, GROUP_KEYS, errors, ctx)
    require_enum(entry, "policy", POLICIES, errors, ctx)
    require(entry, "repos", list, errors, ctx)
    require(entry, "packages", list, errors, ctx)
    require(entry, "exclude_packages", list, errors, ctx)


def _validate_finding(entry: Any, errors: list[str], ctx: str, *, allowed_distances: set[str]) -> tuple[str, str, str] | None:
    if not isinstance(entry, dict):
        errors.append(f"{ctx[:-1]} is not a mapping")
        return None
    _require_exact_keys(entry, FINDING_KEYS, errors, ctx)
    group = require(entry, "group", str, errors, ctx)
    ecosystem = require_enum(entry, "ecosystem", PACKAGE_ECOSYSTEMS, errors, ctx)
    package = require(entry, "package", str, errors, ctx)
    require_enum(entry, "distance", allowed_distances, errors, ctx)
    versions = require(entry, "versions", list, errors, ctx)
    for index, pair in enumerate(versions or []):
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
            errors.append(f"{ctx}versions[{index}] must be [repo, version|null]")
            continue
        if pair[1] is not None and not isinstance(pair[1], str):
            errors.append(f"{ctx}versions[{index}][1] must be a string or null")
    if group is not None and ecosystem is not None and package is not None:
        return group, ecosystem, package
    return None


def _validate_summary(entry: Any, errors: list[str], ctx: str) -> RepositoryEvaluationSummary | None:
    if not isinstance(entry, dict):
        errors.append(f"{ctx[:-1]} is not a mapping")
        return None
    _require_exact_keys(entry, SUMMARY_KEYS, errors, ctx)
    repo = require(entry, "repo", str, errors, ctx)
    ecosystem = require_enum(entry, "ecosystem", ADAPTER_ECOSYSTEMS, errors, ctx)
    adapter = require_enum(entry, "adapter", ADAPTERS, errors, ctx)
    status = require_enum(entry, "status", CHECK_STATUSES, errors, ctx)
    reason_code = require_nullable(entry, "reason_code", str, errors, ctx)
    total = require(entry, "total_packages", int, errors, ctx)
    matched = require(entry, "matched_packages", int, errors, ctx)
    partial = require(entry, "partial_unsupported", int, errors, ctx)
    memberships = require(entry, "group_memberships", list, errors, ctx)
    if (
        repo is None
        or ecosystem is None
        or adapter is None
        or status is None
        or total is None
        or matched is None
        or partial is None
        or memberships is None
    ):
        return None
    if not all(isinstance(m, str) for m in memberships):
        errors.append(f"{ctx}group_memberships must be a list of strings")
        return None
    return RepositoryEvaluationSummary(
        repo=repo,
        ecosystem=ecosystem,
        adapter=adapter,
        status=status,
        reason_code=reason_code,
        total_packages=total,
        matched_packages=matched,
        partial_unsupported=partial,
        group_memberships=tuple(memberships),
    )


def validate(data: Any) -> list[str]:
    """Return all contract violations in a parsed deps-snapshot.json document."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["dependency snapshot is not a mapping"]

    _require_exact_keys(data, TOP_LEVEL_KEYS, errors, "")

    version = require(data, "contract_version", int, errors)
    if version is not None and version not in SUPPORTED_VERSIONS:
        errors.append(f"unsupported contract_version: {version}")

    generated_at = require(data, "generated_at", str, errors)
    if generated_at is not None and not generated_at:
        errors.append("generated_at must not be empty")

    request_hash = require(data, "request_sha256", str, errors)
    if request_hash is not None and not HEX64_RE.match(request_hash):
        errors.append("request_sha256 must be a 64-char lowercase hex string")

    records = require(data, "records", list, errors)
    seen_identities: set[tuple[str, str, str]] = set()
    prior_key: tuple[str, str, str] | None = None
    for index, entry in enumerate(records or []):
        identity = _validate_record(entry, errors, f"records[{index}].")
        if identity is not None:
            if identity in seen_identities:
                errors.append(f"records[{index}]: duplicate (repo, ecosystem, name): {identity}")
            seen_identities.add(identity)
            if prior_key is not None and identity < prior_key:
                errors.append("records must be sorted by (repo, ecosystem, name)")
            prior_key = identity

    groups_raw = require(data, "groups", dict, errors)
    known_group_ids: set[str] = set()
    parsed_groups: list[CoherenceGroup] = []
    if groups_raw is not None:
        for group_id, entry in groups_raw.items():
            _validate_group(group_id, entry, errors, f"groups.{group_id}.")
            if isinstance(group_id, str) and isinstance(entry, dict):
                known_group_ids.add(group_id)
                if all(k in entry for k in GROUP_KEYS) and isinstance(entry.get("repos"), list):
                    parsed_groups.append(
                        CoherenceGroup(
                            id=group_id,
                            repos=tuple(entry.get("repos", [])),
                            packages=tuple(entry.get("packages", [])),
                            exclude_packages=tuple(entry.get("exclude_packages", [])),
                            policy=entry.get("policy"),
                        )
                    )

    findings = require(data, "findings", list, errors)
    finding_identities: set[tuple[str, str, str]] = set()
    prior_key = None
    for index, entry in enumerate(findings or []):
        identity = _validate_finding(entry, errors, f"findings[{index}].", allowed_distances=DISTANCES)
        if identity is not None:
            if identity[0] not in known_group_ids:
                errors.append(f"findings[{index}]: group not in groups: {identity[0]}")
            finding_identities.add(identity)
            if prior_key is not None and identity < prior_key:
                errors.append("findings must be sorted by (group, ecosystem, package)")
            prior_key = identity

    unresolved = require(data, "unresolved", list, errors)
    unresolved_identities: set[tuple[str, str, str]] = set()
    prior_key = None
    for index, entry in enumerate(unresolved or []):
        identity = _validate_finding(
            entry, errors, f"unresolved[{index}].", allowed_distances={"unresolved"}
        )
        if identity is not None:
            if identity[0] not in known_group_ids:
                errors.append(f"unresolved[{index}]: group not in groups: {identity[0]}")
            unresolved_identities.add(identity)
            if prior_key is not None and identity < prior_key:
                errors.append("unresolved must be sorted by (group, ecosystem, package)")
            prior_key = identity

    overlap = finding_identities & unresolved_identities
    if overlap:
        errors.append(f"findings/unresolved are not disjoint: {sorted(overlap)}")

    summaries_raw = require(data, "repository_evaluations", list, errors)
    parsed_summaries: list[RepositoryEvaluationSummary] = []
    prior_pair: tuple[str, str] | None = None
    for index, entry in enumerate(summaries_raw or []):
        summary = _validate_summary(entry, errors, f"repository_evaluations[{index}].")
        if summary is not None:
            parsed_summaries.append(summary)
            pair = (summary.repo, summary.ecosystem)
            if prior_pair is not None and pair < prior_pair:
                errors.append("repository_evaluations must be sorted by (repo, ecosystem)")
            prior_pair = pair
            for membership in summary.group_memberships:
                if membership not in known_group_ids:
                    errors.append(
                        f"repository_evaluations[{index}]: group_memberships references "
                        f"unknown group: {membership}"
                    )

    coverage = require(data, "coverage", dict, errors)
    if coverage is not None:
        _require_exact_keys(coverage, COVERAGE_KEYS, errors, "coverage.")
        if not errors_have_coverage_type_issues(coverage):
            recomputed = reconcile_coverage(parsed_summaries, parsed_groups)
            expected = {
                "repositories_selected": recomputed.repositories_selected,
                "repositories_grouped": recomputed.repositories_grouped,
                "repositories_ungrouped": recomputed.repositories_ungrouped,
                "groups_with_insufficient_members": list(
                    recomputed.groups_with_insufficient_members
                ),
                "packages_matched": recomputed.packages_matched,
                "packages_unmatched": recomputed.packages_unmatched,
                "unsupported_by_adapter": dict(recomputed.unsupported_by_adapter),
            }
            if coverage != expected:
                errors.append(
                    "coverage does not match reconcile_coverage(repository_evaluations, groups): "
                    f"got {coverage!r}, expected {expected!r}"
                )

    error_list = require(data, "errors", list, errors)
    if error_list is not None:
        for index, value in enumerate(error_list):
            if not isinstance(value, str):
                errors.append(f"errors[{index}] is not a string")

    return errors


def errors_have_coverage_type_issues(coverage: dict[str, Any]) -> bool:
    """True when `coverage`'s own key set is malformed enough that a
    reconciliation comparison would be meaningless (already reported above)."""
    return set(coverage.keys()) != COVERAGE_KEYS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"could not read {path}: {exc}", file=sys.stderr)
        return 2
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"could not parse {path}: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
