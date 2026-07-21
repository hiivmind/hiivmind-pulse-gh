#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Validate a headless result file against the pulse result contract.

Usage: validate_result.py <result.yaml> --kind status|healthcheck|refresh|workflow-run|fleet-membership|impact|repo-mutation

See lib/patterns/headless-contract.md for the schemas.

Exit codes:
  0 - valid
  1 - invalid (errors on stderr, one per line)
  2 - file missing or unparseable
"""
import argparse
from math import isclose, isfinite
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from lib.pulse.scripts.evaluate_checks import (
    aggregate_by_scorecard,
    fleet_coverage,
    score_checks,
)

SUPPORTED_VERSIONS = {1}
ACTOR_MODES = {"interactive", "scheduled"}
CHECK_STATUSES = {
    "pass", "warn", "fail", "unknown", "not_applicable", "unsupported", "error",
}
GRADES = {"A", "B", "C", "D", "F"}
REFRESH_SECTION_STATUSES = {"refreshed", "skipped", "failed"}
OUTCOMES = {"success", "failure", "skipped-cooldown", "aborted"}
SEVERITIES = {"low", "medium", "high"}
EDGE_STATES = {"current", "stale", "unknown"}
REPO_MUTATION_STATES = {"proposed", "blocked", "failed"}
REPO_OUTCOME_STATES = {"ok", "failed", "blocked"}
GENERATED_ARTIFACT_STATES = {
    "current",
    "template-drift",
    "local-customization",
    "conflict",
    "error",
}


def _err(errors, msg):
    errors.append(msg)


def _require(data, key, types, errors, ctx=""):
    label = f"{ctx}{key}"
    if key not in data:
        _err(errors, f"missing required key: {label}")
        return None
    if not isinstance(data[key], types):
        _err(errors, f"wrong type for {label}: expected {types}, got {type(data[key]).__name__}")
        return None
    return data[key]


def _require_nullable(data, key, types, errors, ctx=""):
    """Key must be present; value may be of `types` or None."""
    label = f"{ctx}{key}"
    if key not in data:
        _err(errors, f"missing required key: {label}")
        return
    if data[key] is not None and not isinstance(data[key], types):
        _err(errors, f"wrong type for {label}: expected {types} or null, got {type(data[key]).__name__}")


def _require_enum(data, key, allowed, errors, ctx=""):
    val = _require(data, key, str, errors, ctx=ctx)
    if val is not None and val not in allowed:
        _err(errors, f"{ctx}{key} invalid: {val}")
    return val


def _require_nonnegative_number(data, key, errors, ctx=""):
    label = f"{ctx}{key}"
    value = _require(data, key, (int, float), errors, ctx=ctx)
    if value is not None and (
        isinstance(value, bool) or not isfinite(value) or value < 0
    ):
        qualifier = "finite non-negative" if not isinstance(value, bool) else "non-negative"
        _err(errors, f"{label} must be a {qualifier} number")
        return None
    return value


def _require_nonnegative_integer(data, key, errors, ctx=""):
    label = f"{ctx}{key}"
    value = _require(data, key, int, errors, ctx=ctx)
    if value is not None and (isinstance(value, bool) or value < 0):
        _err(errors, f"{label} must be a non-negative integer")
        return None
    return value


def _require_nullable_number(data, key, errors, ctx=""):
    label = f"{ctx}{key}"
    if key not in data:
        _err(errors, f"missing required key: {label}")
        return None
    value = data[key]
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, (int, float))
    ):
        _err(errors, f"wrong type for {label}: expected number or null")
        return None
    if value is not None and not isfinite(value):
        _err(errors, f"{label} must be finite")
        return None
    return value


def _require_actor(data, errors):
    actor = _require(data, "actor", dict, errors)
    if actor is None:
        return
    _require(actor, "gh_login", str, errors, ctx="actor.")
    _require(actor, "machine", str, errors, ctx="actor.")
    _require_enum(actor, "mode", ACTOR_MODES, errors, ctx="actor.")


def _validate_grade_block(block, errors, ctx):
    _require_nonnegative_number(block, "score", errors, ctx=ctx)
    _require_nonnegative_number(block, "total", errors, ctx=ctx)
    _require_enum(block, "grade", GRADES, errors, ctx=ctx)


def _validate_string_list(data, key, errors, ctx=""):
    values = _require(data, key, list, errors, ctx=ctx)
    for index, value in enumerate(values or []):
        if not isinstance(value, str):
            _err(errors, f"{ctx}{key}[{index}] is not a string")
    return values


def _validate_findings(data, errors):
    findings = _require(data, "findings", list, errors)
    for index, finding in enumerate(findings or []):
        if not isinstance(finding, dict):
            _err(errors, f"findings[{index}] is not a mapping")
            continue
        ctx = f"findings[{index}]."
        _require(finding, "kind", str, errors, ctx=ctx)
        _require(finding, "repo", str, errors, ctx=ctx)
        _require_enum(finding, "severity", SEVERITIES, errors, ctx=ctx)
        if "inferred" in finding and not isinstance(finding["inferred"], bool):
            _err(errors, f"wrong type for {ctx}inferred: expected bool")
        if "ref" in finding and not isinstance(finding["ref"], dict):
            _err(errors, f"wrong type for {ctx}ref: expected mapping")
    return findings


def _same_number(actual, expected) -> bool:
    return (
        not isinstance(actual, bool)
        and isinstance(actual, (int, float))
        and isfinite(actual)
        and isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9)
    )


def _reconcile_repo_summary(repo, checks, errors, ctx):
    try:
        expected = score_checks(checks)
    except (AttributeError, TypeError, ValueError):
        return None
    for field in ("score", "total", "coverage_supported", "coverage_total"):
        if not _same_number(repo.get(field), getattr(expected, field)):
            _err(errors, f"{ctx}{field} does not match checks")
    if repo.get("grade") != expected.grade:
        _err(errors, f"{ctx}grade does not match checks")
    return {
        **repo,
        "score": expected.score,
        "total": expected.total,
        "grade": expected.grade,
        "coverage_supported": expected.coverage_supported,
        "coverage_total": expected.coverage_total,
        "checks": checks,
    }


def _reconcile_mapping(actual, expected, errors, *, ctx, source):
    if not isinstance(actual, dict):
        return
    for key, expected_value in expected.items():
        if key not in actual:
            continue
        actual_value = actual[key]
        matches = (
            _same_number(actual_value, expected_value)
            if isinstance(expected_value, float)
            else actual_value == expected_value
        )
        if not matches:
            _err(errors, f"{ctx}{key} does not match {source}")


def validate(data, kind: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["result is not a mapping"]

    version = _require(data, "contract_version", int, errors)
    if version is not None and version not in SUPPORTED_VERSIONS:
        _err(errors, f"unsupported contract_version: {version}")

    got_kind = _require(data, "kind", str, errors)
    if got_kind is not None and got_kind != kind:
        _err(errors, f"kind mismatch: expected {kind}, got {got_kind}")

    _require(data, "workspace", str, errors)
    _require(data, "run_at", str, errors)
    _require_actor(data, errors)
    _require(data, "errors", list, errors)

    if kind == "status":
        sections = _require(data, "sections", list, errors)
        for i, s in enumerate(sections or []):
            if not isinstance(s, dict):
                _err(errors, f"sections[{i}] is not a mapping")
                continue
            ctx = f"sections[{i}]."
            _require(s, "id", str, errors, ctx=ctx)
            _require(s, "stale", bool, errors, ctx=ctx)
            _require_nullable(s, "last_checked", str, errors, ctx=ctx)
        _require_nullable(data, "rate_limit_remaining", int, errors)
        _require(data, "refresh_needed", bool, errors)

    elif kind == "healthcheck":
        forbidden_grade_keys = {
            "score",
            "total",
            "grade",
            "aggregate_score",
            "aggregate_total",
            "aggregate_grade",
        }
        for key in sorted(forbidden_grade_keys & data.keys()):
            _err(errors, f"forbidden mixed fleet grade key: top.{key}")
        repos = _require(data, "repos", list, errors)
        reconciled_repos = []
        seen_repos: set[str] = set()
        for i, r in enumerate(repos or []):
            if not isinstance(r, dict):
                _err(errors, f"repos[{i}] is not a mapping")
                continue
            ctx = f"repos[{i}]."
            repo_identity = _require(r, "repo", str, errors, ctx=ctx)
            if repo_identity in seen_repos:
                _err(errors, f"duplicate repository identity: {repo_identity}")
            elif repo_identity is not None:
                seen_repos.add(repo_identity)
            _require(r, "scorecard", str, errors, ctx=ctx)
            score = _require_nonnegative_number(r, "score", errors, ctx=ctx)
            total = _require_nonnegative_number(r, "total", errors, ctx=ctx)
            _require_enum(r, "grade", GRADES, errors, ctx=ctx)
            coverage_supported = _require_nonnegative_number(
                r, "coverage_supported", errors, ctx=ctx
            )
            coverage_total = _require_nonnegative_number(
                r, "coverage_total", errors, ctx=ctx
            )
            if score is not None and total is not None and score > total:
                _err(errors, f"{ctx}score must not exceed total")
            if (
                coverage_supported is not None
                and coverage_total is not None
                and coverage_supported > coverage_total
            ):
                _err(
                    errors,
                    f"{ctx}coverage_supported must not exceed coverage_total",
                )
            checks = _require(r, "checks", dict, errors, ctx=ctx)
            for cid, c in (checks or {}).items():
                cctx = f"{ctx}checks.{cid}."
                if not isinstance(c, dict):
                    _err(errors, f"{ctx}checks.{cid} is not a mapping")
                    continue
                check_id = _require(c, "check_id", str, errors, ctx=cctx)
                if check_id is not None and check_id != cid:
                    _err(errors, f"{cctx}check_id mismatch: expected {cid}, got {check_id}")
                _require(c, "adapter", str, errors, ctx=cctx)
                _require_nonnegative_number(c, "weight", errors, ctx=cctx)
                _require_enum(c, "status", CHECK_STATUSES, errors, ctx=cctx)
                _require(c, "detail", str, errors, ctx=cctx)
                check_data = _require(c, "data", dict, errors, ctx=cctx)
                if check_data is not None:
                    if "evidence" not in check_data:
                        _err(errors, f"missing required key: {cctx}data.evidence")
                    elif not isinstance(check_data["evidence"], dict):
                        _err(errors, f"{cctx}data.evidence: expected mapping")
                    else:
                        evidence = check_data["evidence"]
                        if set(evidence) != {"paths", "refs"}:
                            _err(
                                errors,
                                f"{cctx}data.evidence keys must be exactly paths, refs",
                            )
                        _validate_string_list(
                            evidence, "paths", errors, ctx=f"{cctx}data.evidence."
                        )
                        _validate_string_list(
                            evidence, "refs", errors, ctx=f"{cctx}data.evidence."
                        )
                if "profile" in c and not isinstance(c["profile"], str):
                    _err(errors, f"wrong type for {cctx}profile: expected str")
                if "inferred" in c and not isinstance(c["inferred"], bool):
                    _err(errors, f"wrong type for {cctx}inferred: expected bool")
            if isinstance(checks, dict):
                reconciled = _reconcile_repo_summary(r, checks, errors, ctx)
                if reconciled is not None and isinstance(r.get("scorecard"), str):
                    reconciled_repos.append(reconciled)
        agg = _require(data, "aggregate", dict, errors)
        if agg is not None:
            for key in sorted(forbidden_grade_keys & agg.keys()):
                _err(errors, f"forbidden mixed fleet grade key: aggregate.{key}")
            by_scorecard = _require(
                agg, "by_scorecard", dict, errors, ctx="aggregate."
            )
            for scorecard, entry in (by_scorecard or {}).items():
                ctx = f"aggregate.by_scorecard.{scorecard}."
                if not isinstance(scorecard, str):
                    _err(errors, "aggregate.by_scorecard keys must be strings")
                if not isinstance(entry, dict):
                    _err(errors, f"{ctx[:-1]} is not a mapping")
                    continue
                repo_count = _require_nonnegative_integer(
                    entry, "repos", errors, ctx=ctx
                )
                repos_scored = _require_nonnegative_integer(
                    entry, "repos_scored", errors, ctx=ctx
                )
                average_percent = _require_nullable_number(
                    entry, "average_percent", errors, ctx=ctx
                )
                if (
                    repo_count is not None
                    and repos_scored is not None
                    and repos_scored > repo_count
                ):
                    _err(errors, f"{ctx}repos_scored must not exceed repos")
                if average_percent is not None and not 0 <= average_percent <= 100:
                    _err(errors, f"{ctx}average_percent must be between 0 and 100")
            if isinstance(by_scorecard, dict) and len(reconciled_repos) == len(
                repos or []
            ):
                expected_groups = aggregate_by_scorecard(reconciled_repos)
                actual_groups = set(by_scorecard)
                for scorecard in sorted(
                    set(expected_groups) - actual_groups, key=str
                ):
                    _err(errors, f"missing aggregate.by_scorecard group: {scorecard}")
                for scorecard in sorted(
                    actual_groups - set(expected_groups), key=str
                ):
                    _err(errors, f"extra aggregate.by_scorecard group: {scorecard}")
                for scorecard in sorted(
                    actual_groups & set(expected_groups), key=str
                ):
                    _reconcile_mapping(
                        by_scorecard[scorecard],
                        expected_groups[scorecard],
                        errors,
                        ctx=f"aggregate.by_scorecard.{scorecard}.",
                        source="repos",
                    )
        coverage = _require(data, "coverage", dict, errors)
        if coverage is not None:
            checks_total = _require_nonnegative_integer(
                coverage, "checks_total", errors, ctx="coverage."
            )
            checks_supported = _require_nonnegative_integer(
                coverage, "checks_supported", errors, ctx="coverage."
            )
            if (
                checks_total is not None
                and checks_supported is not None
                and checks_supported > checks_total
            ):
                _err(
                    errors,
                    "coverage.checks_supported must not exceed checks_total",
                )
            unsupported = _require(
                coverage,
                "unsupported_by_adapter",
                dict,
                errors,
                ctx="coverage.",
            )
            for adapter, count in (unsupported or {}).items():
                if not isinstance(adapter, str):
                    _err(errors, "coverage.unsupported_by_adapter keys must be strings")
                if (
                    isinstance(count, bool)
                    or not isinstance(count, int)
                    or count < 0
                ):
                    _err(
                        errors,
                        "coverage.unsupported_by_adapter."
                        f"{adapter} must be a non-negative integer",
                    )
            _validate_string_list(
                coverage, "unprofiled_repos", errors, ctx="coverage."
            )
            if len(reconciled_repos) == len(repos or []):
                expected_coverage = fleet_coverage(reconciled_repos)
                _reconcile_mapping(
                    coverage,
                    expected_coverage,
                    errors,
                    ctx="coverage.",
                    source="repo checks",
                )

    elif kind == "refresh":
        sections = _require(data, "sections", list, errors)
        for i, s in enumerate(sections or []):
            if not isinstance(s, dict):
                _err(errors, f"sections[{i}] is not a mapping")
                continue
            ctx = f"sections[{i}]."
            _require(s, "id", str, errors, ctx=ctx)
            _require_enum(s, "status", REFRESH_SECTION_STATUSES, errors, ctx=ctx)
        _require(data, "config_updated", bool, errors)

    elif kind == "workflow-run":
        _require(data, "workflow", str, errors)
        repos = _require(data, "repos", list, errors)
        for i, r in enumerate(repos or []):
            if not isinstance(r, str):
                _err(errors, f"repos[{i}] is not a string")
        _require(data, "run_id", str, errors)
        _require_enum(data, "outcome", OUTCOMES, errors)
        _validate_findings(data, errors)
        _require(data, "proposed_actions", list, errors)
        _require(data, "asks_recorded", list, errors)

    elif kind == "fleet-membership":
        _validate_string_list(data, "org_repos", errors)
        _validate_string_list(data, "catalog_repos", errors)
        _require(data, "catalog_updated", bool, errors)
        proposals = _require(data, "profile_proposals", list, errors)
        for index, proposal in enumerate(proposals or []):
            if not isinstance(proposal, dict):
                _err(errors, f"profile_proposals[{index}] is not a mapping")
                continue
            ctx = f"profile_proposals[{index}]."
            _require(proposal, "repo", str, errors, ctx=ctx)
            _require(proposal, "evidence", dict, errors, ctx=ctx)
            candidates = _require(proposal, "candidates", list, errors, ctx=ctx)
            for candidate_index, candidate in enumerate(candidates or []):
                cctx = f"{ctx}candidates[{candidate_index}]."
                if not isinstance(candidate, dict):
                    _err(errors, f"{cctx[:-1]} is not a mapping")
                    continue
                _require(candidate, "profile", str, errors, ctx=cctx)
                confidence = _require_nonnegative_number(
                    candidate, "confidence", errors, ctx=cctx
                )
                if confidence is not None and confidence > 1:
                    _err(errors, f"{cctx}confidence must be at most 1")
                _validate_string_list(candidate, "evidence", errors, ctx=cctx)
                _validate_string_list(candidate, "rule_ids", errors, ctx=cctx)
            if "explanation" in proposal and not isinstance(proposal["explanation"], str):
                _err(errors, f"wrong type for {ctx}explanation: expected str")
            if "explanation" in proposal and proposal.get("inferred") is not True:
                _err(errors, f"{ctx}explanation requires inferred: true")
            if "inferred" in proposal and not isinstance(proposal["inferred"], bool):
                _err(errors, f"wrong type for {ctx}inferred: expected bool")
        _validate_findings(data, errors)
        _require(data, "proposed_actions", list, errors)
        _require(data, "asks_recorded", list, errors)

    elif kind == "impact":
        edges = _require(data, "edges", list, errors)
        seen_edges: set[tuple] = set()
        stale_count = 0
        for i, e in enumerate(edges or []):
            if not isinstance(e, dict):
                _err(errors, f"edges[{i}] is not a mapping")
                continue
            ctx = f"edges[{i}]."
            dependent = _require(e, "dependent", str, errors, ctx=ctx)
            upstream = _require(e, "upstream", str, errors, ctx=ctx)
            watch_branch = _require(e, "watch_branch", str, errors, ctx=ctx)
            state = _require_enum(e, "state", EDGE_STATES, errors, ctx=ctx)
            _require_nullable(e, "tested_sha", str, errors, ctx=ctx)
            _require_nullable(e, "remote_head", str, errors, ctx=ctx)
            _validate_string_list(e, "changed_paths", errors, ctx=ctx)
            if state == "stale":
                stale_count += 1
            if None not in (dependent, upstream, watch_branch):
                identity = (dependent, upstream, watch_branch)
                if identity in seen_edges:
                    _err(
                        errors,
                        f"duplicate edge identity: {dependent} <- {upstream} "
                        f"({watch_branch})",
                    )
                else:
                    seen_edges.add(identity)
        edges_checked = _require_nonnegative_integer(data, "edges_checked", errors)
        if edges_checked is not None and edges_checked != len(edges or []):
            _err(errors, "edges_checked does not match edges")
        edges_stale = _require_nonnegative_integer(data, "edges_stale", errors)
        if edges_stale is not None and edges_stale != stale_count:
            _err(errors, "edges_stale does not match edges")
        _require_nonnegative_integer(data, "markers_updated", errors)
        _validate_findings(data, errors)
        _require(data, "proposed_actions", list, errors)
        _require(data, "asks_recorded", list, errors)

    elif kind == "repo-mutation":
        state = _require_enum(data, "state", REPO_MUTATION_STATES, errors)
        _require(data, "proposal_id", str, errors)
        _require(data, "transformation", str, errors)
        _require(data, "pen_name", str, errors)
        _validate_string_list(data, "selection", errors)
        _require_nullable(data, "nave_version", str, errors)
        repo_outcomes = _require(data, "repo_outcomes", dict, errors)
        for repo, outcome in (repo_outcomes or {}).items():
            if not isinstance(repo, str):
                _err(errors, "repo_outcomes keys must be strings")
            if outcome not in REPO_OUTCOME_STATES:
                _err(errors, f"repo_outcomes.{repo} invalid: {outcome}")
        _require_nullable(data, "reason", str, errors)
        if state in {"blocked", "failed"} and data.get("reason") is None:
            _err(errors, "reason must not be null when state is blocked or failed")

    elif kind == "generated-artifact":
        _require_nonnegative_integer(data, "bindings_audited", errors)
        states = _require(data, "states", dict, errors)
        for binding_id, state in (states or {}).items():
            if not isinstance(binding_id, str):
                _err(errors, "states keys must be strings")
            if state not in GENERATED_ARTIFACT_STATES:
                _err(errors, f"states.{binding_id} invalid: {state}")
        _validate_findings(data, errors)
        proposals = _require(data, "proposals", list, errors)
        for index, proposal in enumerate(proposals or []):
            if not isinstance(proposal, dict):
                _err(errors, f"proposals[{index}] is not a mapping")
                continue
            ctx = f"proposals[{index}]."
            _require(proposal, "binding", str, errors, ctx=ctx)
            _require(proposal, "transformation", str, errors, ctx=ctx)
            _require(proposal, "proposal_id", str, errors, ctx=ctx)
        _require(data, "proposed_actions", list, errors)

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate a headless result file")
    parser.add_argument("file", help="Path to result YAML file")
    parser.add_argument("--kind", required=True,
                        choices=["status", "healthcheck", "refresh", "workflow-run",
                                 "fleet-membership", "impact", "repo-mutation",
                                 "generated-artifact"])
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    import yaml
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        print(f"error: unparseable YAML: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate(data, args.kind)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
