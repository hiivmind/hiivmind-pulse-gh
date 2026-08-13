#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0", "packaging>=24.0", "semantic-version>=2.10"]
# ///
"""Materialize dependency evidence and dispatch it into typed evaluations.

This is the sanitized boundary around parser invocation for F4: every
selected `(repo, ecosystem)` is parsed exactly once, before any per-repo
dismissal logic runs, through `evaluate_dependencies` — never through an
unchecked `Mapping.get` fed directly into a parser.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Literal

from lib.pulse.scripts import dependency_evidence as de
from lib.pulse.scripts import nave_adapter
from lib.pulse.scripts import validate_dependency_evidence as vde
from lib.pulse.scripts.adapters.node_dependencies import parse_node
from lib.pulse.scripts.adapters.python_dependencies import AdapterDetection, parse_python
from lib.pulse.scripts.check_adapters import CheckContext
from lib.pulse.scripts.dependencies import (
    CoherenceGroup,
    DependencyCoverage,
    DependencyRepoEvaluation,
    DivergenceFinding,
    DivergenceReport,
    RepositoryEvaluationSummary,
    matches_glob,
    package_identity,
)
from lib.pulse.scripts.dependency_evidence import RepoEvidence
from lib.pulse.scripts.profile_dispatch import ConfigError, ProfileConfig, resolve_scorecard


DEPENDENCY_SELECTORS: tuple[dict, ...] = (
    # static, ecosystem-wide selectors covering every v1-supported manager
    # file/glob — not derived per-repo; feature detection happens from
    # materialize's per-artifact state (found/absent/unresolved/...), never
    # from a repo-name or pre-scan heuristic.
    {"id": "python.pyproject", "pattern": "pyproject.toml"},
    {"id": "python.uv_lock", "pattern": "uv.lock"},
    {"id": "python.poetry_lock", "pattern": "poetry.lock"},
    {"id": "python.pdm_lock", "pattern": "pdm.lock"},
    {"id": "python.pip_tools_in", "pattern": "requirements*.in"},
    {"id": "python.pip_tools_txt", "pattern": "requirements*.txt"},
    {"id": "python.conda_env", "pattern": "environment.yml"},
    {"id": "node.package_json", "pattern": "package.json"},
    {"id": "node.npm_lock", "pattern": "package-lock.json"},
    {"id": "node.pnpm_lock", "pattern": "pnpm-lock.yaml"},
    {"id": "node.pnpm_workspace_yaml", "pattern": "pnpm-workspace.yaml"},
    {"id": "node.yarn_lock", "pattern": "yarn.lock"},
)


_ADAPTER_TO_ECOSYSTEM: dict[str, Literal["python", "node"]] = {
    "python.dependencies": "python",
    "node.dependencies": "node",
}

FLEET_COHERENCE_CHECK_ID = "fleet_dependency_coherence"


def dependency_selected_repos(
    config: ProfileConfig,
) -> dict[str, frozenset[Literal["python", "node"]]]:
    """repo -> the set of dependency ADAPTER-SELECTION ecosystems its resolved
    scorecard selects. A scorecard may legally select both — resolve_scorecard
    enforces no mutual exclusivity across DIFFERENT check ids, so this returns
    a set, never a single ecosystem string. Mirrors
    healthcheck_dispatch._overlay_opted_in_repos's scan of resolve_scorecard,
    generalized to preserve every selected ecosystem."""
    result: dict[str, frozenset[Literal["python", "node"]]] = {}
    for repo, profile in config.repositories.items():
        ecosystems = {
            _ADAPTER_TO_ECOSYSTEM[check.adapter]
            for check in resolve_scorecard(config, profile.scorecard)
            if check.adapter in _ADAPTER_TO_ECOSYSTEM
        }
        if ecosystems:
            result[repo] = frozenset(ecosystems)
    return result


def fleet_coherence_selected_repos(config: ProfileConfig) -> set[str]:
    """Repos whose resolved scorecard selects the fleet_dependency_coherence
    check id — regardless of whether its applicability predicate will
    actually be satisfied for that repo (that is decided at dispatch time)."""
    return {
        repo
        for repo, profile in config.repositories.items()
        if any(
            check.id == FLEET_COHERENCE_CHECK_ID
            for check in resolve_scorecard(config, profile.scorecard)
        )
    }


def materialize_dependency_evidence(
    repos: Sequence[str], *, runner: nave_adapter.NaveRunner
) -> dict:
    """build_request -> nave_adapter.materialize -> normalize -> validate
    (raise on any violation) -> return the validated normalized document.
    Never returns an unvalidated document to the caller."""
    request = de.build_request(list(repos), list(DEPENDENCY_SELECTORS))
    digest = de.request_sha256(request)
    raw = nave_adapter.materialize(runner, json.dumps(request, sort_keys=True))
    if raw.get("adapter_state") == "error":
        raise ConfigError(f"dependency-evidence materialize failed: {raw.get('error')}")
    probed = nave_adapter.probe(runner)
    provider = {"name": "nave", "version": probed.get("version"), "protocol": 2}
    generated_at = datetime.now(timezone.utc).isoformat()
    document = de.normalize(raw, provider, generated_at, digest)
    errors = vde.validate(document)
    if errors:
        raise ConfigError(
            "dependency evidence failed validation: " + "; ".join(errors)
        )
    return document


def _synthetic_evaluation(
    repo: str,
    ecosystem: Literal["python", "node"],
    *,
    state: Literal["unknown", "error"],
    reason_code: str,
    local_status: Literal["unknown", "error"],
    coverage_state: Literal["complete", "incomplete"],
) -> DependencyRepoEvaluation:
    return DependencyRepoEvaluation(
        repo=repo,
        ecosystem=ecosystem,
        detection=AdapterDetection(
            state=state, manager=None, reason_code=reason_code, source_files=()
        ),
        declarations=(),
        records=(),
        local_findings=(),
        local_status=local_status,
        local_reason_code=reason_code,
        coverage_state=coverage_state,
        partial_unsupported=0,
    )


def evaluate_dependencies(
    repo: str,
    ecosystem: Literal["python", "node"],
    evidence: RepoEvidence | None,
) -> DependencyRepoEvaluation:
    """The one typed pre-dispatch entry point, and the sanitized boundary
    around parser invocation. `capability` is always True here — the caller
    only invokes this for repos `dependency_selected_repos` already selected.
    """
    if evidence is None:
        return _synthetic_evaluation(
            repo,
            ecosystem,
            state="unknown",
            reason_code="evidence_gap",
            local_status="unknown",
            coverage_state="incomplete",
        )
    try:
        if ecosystem == "python":
            return parse_python(repo, evidence, capability=True)
        return parse_node(repo, evidence, capability=True)
    except Exception:  # noqa: BLE001 - sanitized boundary, never re-raises
        return _synthetic_evaluation(
            repo,
            ecosystem,
            state="error",
            reason_code="internal_parser_error",
            local_status="error",
            coverage_state="complete",
        )


# --- placeholder adapter (registered as "fleet.dependencies.coherence") -------


def evaluate_fleet_dependency_coherence_placeholder(context: CheckContext) -> dict:
    """Every repo selecting fleet_dependency_coherence gets this complete,
    normalized placeholder during the per-repo pass; evaluate_fleet's
    post-loop fleet pass always replaces it (with either a real comparison
    block or the missing_policy block) before dismissals/scoring finalize."""
    return {
        "status": "unknown",
        "detail": "pending fleet pass",
        "data": {"evidence": {"paths": [], "refs": []}, "coverage_state": "pending_fleet_pass"},
    }


# --- per-(repo, ecosystem) summary, built unconditionally during the loop -----


def build_repository_evaluation_summary(
    evaluation: DependencyRepoEvaluation,
    groups: tuple[CoherenceGroup, ...],
) -> RepositoryEvaluationSummary:
    adapter = "python.dependencies" if evaluation.ecosystem == "python" else "node.dependencies"
    matched = 0
    memberships: set[str] = set()
    for record in evaluation.records:
        if record.resolution != "single" or record.locked_version is None:
            continue
        identity = package_identity(record.ecosystem, record.name)
        record_matched = False
        for group in groups:
            if evaluation.repo not in group.repos:
                continue
            if not any(matches_glob(identity, g) for g in group.packages):
                continue
            if any(matches_glob(identity, g) for g in group.exclude_packages):
                continue
            record_matched = True
            memberships.add(group.id)
        if record_matched:
            matched += 1
    return RepositoryEvaluationSummary(
        repo=evaluation.repo,
        ecosystem=evaluation.ecosystem,
        adapter=adapter,
        status=evaluation.local_status,
        reason_code=evaluation.local_reason_code,
        total_packages=len(evaluation.records),
        matched_packages=matched,
        partial_unsupported=evaluation.partial_unsupported,
        group_memberships=tuple(sorted(memberships)),
    )


# --- fleet CheckBlock construction (post-loop, single compare() call) ---------


def divergence_finding_to_dict(finding: DivergenceFinding) -> dict:
    return {
        "group": finding.group,
        "ecosystem": finding.ecosystem,
        "package": finding.package,
        "versions": [[repo, version] for repo, version in finding.versions],
        "distance": finding.distance,
    }


def _policy_allows(policy: str, distance: str) -> bool:
    if distance == "major":
        return False
    if policy == "exact":
        return False
    if policy == "same-minor":
        return distance == "patch"
    if policy == "same-major":
        return distance in ("minor", "patch")
    return False


def _finding_severity(
    finding: DivergenceFinding, groups_by_id: dict[str, CoherenceGroup]
) -> Literal["pass", "warn", "fail", "unknown"]:
    if finding.distance == "unresolved":
        return "unknown"
    group = groups_by_id.get(finding.group)
    if group is not None and _policy_allows(group.policy, finding.distance):
        return "pass"
    return "fail" if finding.distance == "major" else "warn"


def build_fleet_missing_policy_block(weight: float) -> dict:
    return {
        "check_id": FLEET_COHERENCE_CHECK_ID,
        "adapter": "fleet.dependencies.coherence",
        "weight": weight,
        "status": "unknown",
        "detail": "dependencies.yaml missing",
        "data": {"evidence": {"paths": [], "refs": []}, "reason_code": "missing_policy"},
    }


def build_fleet_coherence_block(
    repo: str,
    weight: float,
    report: DivergenceReport,
    groups: tuple[CoherenceGroup, ...],
) -> dict:
    in_any_group = any(repo in group.repos for group in groups)
    if not in_any_group:
        return {
            "check_id": FLEET_COHERENCE_CHECK_ID,
            "adapter": "fleet.dependencies.coherence",
            "weight": weight,
            "status": "not_applicable",
            "detail": "repository is not a member of any coherence group",
            "data": {
                "evidence": {"paths": [], "refs": []},
                "reason_code": "ungrouped",
                "findings": [],
                "unresolved": [],
            },
        }

    groups_by_id = {group.id: group for group in groups}
    relevant_findings = [f for f in report.findings if any(r == repo for r, _ in f.versions)]
    relevant_unresolved = [f for f in report.unresolved if any(r == repo for r, _ in f.versions)]

    severities = [_finding_severity(f, groups_by_id) for f in relevant_findings]
    severities.extend("unknown" for _ in relevant_unresolved)
    status: Literal["pass", "warn", "fail", "unknown"] = "pass"
    for candidate in ("fail", "unknown", "warn"):
        if candidate in severities:
            status = candidate
            break

    count = len(relevant_findings) + len(relevant_unresolved)
    detail = "no divergence" if count == 0 else f"{count} divergence finding(s), worst={status}"
    return {
        "check_id": FLEET_COHERENCE_CHECK_ID,
        "adapter": "fleet.dependencies.coherence",
        "weight": weight,
        "status": status,
        "detail": detail,
        "data": {
            "evidence": {"paths": [], "refs": []},
            "findings": [divergence_finding_to_dict(f) for f in relevant_findings],
            "unresolved": [divergence_finding_to_dict(f) for f in relevant_unresolved],
        },
    }


def dependency_coverage_to_dict(coverage: DependencyCoverage) -> dict:
    """JSON-safe projection of DependencyCoverage for coverage["dependencies"]."""
    return {
        "repositories_selected": coverage.repositories_selected,
        "repositories_grouped": coverage.repositories_grouped,
        "repositories_ungrouped": coverage.repositories_ungrouped,
        "groups_with_insufficient_members": list(coverage.groups_with_insufficient_members),
        "packages_matched": coverage.packages_matched,
        "packages_unmatched": coverage.packages_unmatched,
        "unsupported_by_adapter": dict(coverage.unsupported_by_adapter),
    }
