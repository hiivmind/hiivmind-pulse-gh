#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0", "packaging>=24.0", "semantic-version>=2.10", "tomli>=2.0; python_version<'3.11'"]
# ///
"""Evaluate a heterogeneous F0 fleet through authoritative scorecards."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from lib.pulse.scripts.adapters import register_universal_adapters
from lib.pulse.scripts.check_adapters import AdapterRegistry, CheckContext
from lib.pulse.scripts.dependencies import (
    DependencyPolicy,
    DependencyRepoEvaluation,
    DivergenceReport,
    RepositoryEvaluationSummary,
    compare,
    reconcile_coverage,
)
from lib.pulse.scripts.dependency_evidence import RepoEvidence
from lib.pulse.scripts.dependency_pipeline import (
    FLEET_COHERENCE_CHECK_ID,
    build_fleet_coherence_block,
    build_fleet_missing_policy_block,
    build_repository_evaluation_summary,
    dependency_coverage_to_dict,
    dependency_selected_repos,
    evaluate_dependencies,
    fleet_coherence_selected_repos,
)
from lib.pulse.scripts.evaluate_checks import (
    aggregate_by_scorecard,
    fleet_coverage,
    score_checks,
)
from lib.pulse.scripts.profile_dispatch import (
    ConfigError,
    PlannedCheck,
    ProfileConfig,
    dispatch,
    load_profiles,
    resolve_scorecard,
)


def _evidence_repositories(evidence: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    repos = evidence.get("repos")
    if not isinstance(repos, list):
        raise ConfigError("evidence repos must be a list")

    indexed: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(repos):
        if not isinstance(entry, dict):
            raise ConfigError(f"evidence repos[{index}] must be a mapping")
        repo = entry.get("repo")
        if not isinstance(repo, str) or not repo.strip():
            raise ConfigError(f"evidence repos[{index}].repo must be a non-empty string")
        if repo in indexed:
            raise ConfigError(f"duplicate evidence for repository: {repo}")
        indexed[repo] = entry
    return indexed


def _planned_block(planned: PlannedCheck) -> dict[str, Any]:
    """Materialize a precomputed dispatch state without adapter evaluation."""
    if planned.state is None:
        raise ValueError("planned block requires a precomputed state")
    return {
        "check_id": planned.check_id,
        "adapter": planned.adapter,
        "weight": planned.weight,
        "status": planned.state,
        "detail": planned.reason or "",
        "data": {"evidence": {"paths": [], "refs": []}},
    }


def _load_dismissals(path: str | Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    dismissal_path = Path(path)
    try:
        loaded = yaml.safe_load(dismissal_path.read_text()) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"dismissals not found: {dismissal_path}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"could not load dismissals: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ConfigError("dismissals document must be a mapping")
    dismissals = loaded.get("dismissals", {})
    if not isinstance(dismissals, Mapping):
        raise ConfigError("dismissals must be a mapping")
    return dismissals


def _repo_dismissals(
    repo: str, dismissals: Mapping[str, Any]
) -> dict[str, tuple[dict[str, Any], str]]:
    matched: dict[str, tuple[dict[str, Any], str]] = {}
    for scope in (repo, repo.rsplit("/", 1)[-1]):
        entries = dismissals.get(scope, {})
        if not isinstance(entries, Mapping):
            raise ConfigError(f"dismissals.{scope} must be a mapping")
        for check_id, dismissal in entries.items():
            if not isinstance(check_id, str):
                raise ConfigError(f"dismissals.{scope} keys must be strings")
            if dismissal is None:
                dismissal = {}
            if not isinstance(dismissal, Mapping):
                raise ConfigError(
                    f"dismissals.{scope}.{check_id} must be a mapping"
                )
            matched[check_id] = (dict(dismissal), scope)
    return matched


def _parse_as_of(value: str | date | datetime | None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ConfigError("as-of must be an ISO date or ISO datetime")
    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ConfigError(
                "as-of must be an ISO date or ISO datetime"
            ) from exc


def _review_after_date(value: Any, *, scope: str, check_id: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        raise ConfigError(
            f"dismissals.{scope}.{check_id}.review_after must be an ISO date or null"
        )
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ConfigError(
            f"dismissals.{scope}.{check_id}.review_after must be an ISO date or null"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(
            f"dismissals.{scope}.{check_id}.review_after must be an ISO date or null"
        ) from exc


def _json_native(value: Any, *, path: str = "dismissal metadata") -> Any:
    """Recursively copy YAML-loaded metadata into JSON-native values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _json_native(item, path=f"{path}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _json_native(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, float) and not math.isfinite(value):
        raise ConfigError(
            f"dismissal metadata at {path} must contain finite numbers"
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ConfigError(
        f"dismissal metadata at {path} contains unsupported type: "
        f"{type(value).__name__}"
    )


def _apply_single_dismissal(
    checks: dict[str, dict[str, Any]],
    check_id: str,
    dismissal: dict[str, Any],
    scope: str,
    as_of: date,
) -> None:
    """Apply one check's dismissal in place, if not yet due for review."""
    if check_id not in checks:
        return
    review_after = _review_after_date(
        dismissal.get("review_after"), scope=scope, check_id=check_id
    )
    if review_after is not None and as_of >= review_after:
        return
    reason = dismissal.get("reason", "")
    checks[check_id] = {
        **checks[check_id],
        "status": "not_applicable",
        "detail": f"Dismissed: {reason}",
        "data": {
            "dismissed": True,
            "dismissal": _json_native(
                dismissal, path=f"dismissals.{scope}.{check_id}"
            ),
            "evidence": {
                "paths": [],
                "refs": [f"dismissals:{scope}:{check_id}"],
            },
        },
    }


def _apply_dismissals(
    repo: str,
    checks: dict[str, dict[str, Any]],
    dismissals: Mapping[str, Any],
    as_of: date,
    *,
    skip_check_ids: frozenset[str] = frozenset(),
) -> None:
    for check_id, (dismissal, scope) in _repo_dismissals(
        repo, dismissals
    ).items():
        if check_id in skip_check_ids:
            continue
        _apply_single_dismissal(checks, check_id, dismissal, scope, as_of)


def _repo_result(
    repo: str,
    evidence: dict[str, Any],
    config: Any,
    registry: AdapterRegistry,
    workspace: Path,
    dismissals: Mapping[str, Any],
    as_of: date,
) -> dict[str, Any]:
    plan = dispatch(repo, {"repos": [evidence]}, config)
    checks: dict[str, dict[str, Any]] = {}
    for check_id in sorted(plan.checks):
        planned = plan.checks[check_id]
        if planned.state is not None:
            block = _planned_block(planned)
        else:
            context = CheckContext(
                repo=repo,
                evidence=evidence,
                check=planned,
                workspace=workspace,
            )
            block = registry.evaluate(planned.adapter, context)
        checks[check_id] = block

    _apply_dismissals(
        repo, checks, dismissals, as_of, skip_check_ids=frozenset({FLEET_COHERENCE_CHECK_ID})
    )
    summary = score_checks(checks)
    return {
        "repo": repo,
        "scorecard": plan.scorecard,
        "score": summary.score,
        "total": summary.total,
        "grade": summary.grade,
        "coverage_supported": summary.coverage_supported,
        "coverage_total": summary.coverage_total,
        "checks": checks,
    }


# Claude adapters that register_claude_adapters provides and that consume the
# overlay file_contents channel. Transitional names (e.g. claude.plugin-structure)
# do not trigger registration or content attachment.
_CLAUDE_OVERLAY_ADAPTERS = frozenset(
    {
        "claude.plugin_manifest",
        "claude.skills",
        "claude.context",
    }
)


def _scorecard_has_claude_adapter(
    config: ProfileConfig, scorecard_id: str
) -> bool:
    """True when the resolved scorecard names a content-consuming claude adapter.

    Only adapters registered by ``register_claude_adapters`` count. Transitional
    names such as ``claude.plugin-structure`` do not opt a repo into the overlay
    content channel or trigger registration on their own.
    """
    return any(
        check.adapter in _CLAUDE_OVERLAY_ADAPTERS
        for check in resolve_scorecard(config, scorecard_id)
    )


def _overlay_opted_in_repos(config: ProfileConfig) -> set[str]:
    return {
        repo
        for repo, profile in config.repositories.items()
        if _scorecard_has_claude_adapter(config, profile.scorecard)
    }


def _attach_overlay_content(
    repo: str,
    evidence: dict[str, Any],
    gh_api: Any,
) -> dict[str, Any]:
    """Return a shallow-copied evidence entry with file_contents attached.

    Pre-attached ``file_contents`` (fixture/skill) is preserved. The caller's
    original mapping is never mutated.
    """
    entry = dict(evidence)
    if "file_contents" in entry:
        return entry
    # Lazy import: neutral fleets never reach this path.
    from lib.pulse.scripts import overlay_content

    files = entry.get("files")
    if not isinstance(files, list):
        files = []
    branch = overlay_content.default_branch_from_evidence(entry)
    entry["file_contents"] = overlay_content.collect(
        repo,
        files=files,
        gh_api=gh_api,
        default_branch=branch,
    )
    return entry


def evaluate_fleet(
    *,
    evidence: Mapping[str, Any],
    profiles_path: str | Path,
    workspace: str | Path,
    dismissals_path: str | Path | None = None,
    as_of: str | date | datetime | None = None,
    gh_api: Any | None = None,
    dependency_evidence: Mapping[str, RepoEvidence] | None = None,
    dependency_policy: DependencyPolicy | None = None,
    dependency_collector: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch and evaluate profiled repositories from one F0 fleet snapshot.

    When any profiled repo's resolved scorecard contains a ``claude.*`` overlay
    adapter, the Claude adapters are registered (lazy import). Overlay content
    is collected and attached **only** to those opted-in repo entries, and only
    when ``gh_api`` is provided and ``file_contents`` is not already present.
    Neutral repos never gain ``file_contents``.

    ``dependency_collector``, if provided, is populated (as a side effect,
    before returning) with keys "records", "groups", "report", and
    "repository_evaluations" — the exact typed objects this call used
    internally to build the durable ``coverage["dependencies"]``. This is an
    ADDITIVE, purely-optional out-param: every existing caller passing
    ``dependency_collector=None`` (the default) sees zero behavior change.
    """
    if not isinstance(evidence, Mapping):
        raise ConfigError("evidence must be a mapping")
    evidence_by_repo = _evidence_repositories(evidence)
    config = load_profiles(profiles_path)
    dismissals = _load_dismissals(dismissals_path)
    as_of_date = _parse_as_of(as_of)
    registry = AdapterRegistry()
    register_universal_adapters(registry)

    overlay_repos = _overlay_opted_in_repos(config)
    if overlay_repos:
        # Lazy: importing register_claude_adapters does not load claude_plugin;
        # calling it does. Neutral fleets never enter this branch.
        from lib.pulse.scripts.adapters import register_claude_adapters

        register_claude_adapters(registry)

    workspace_path = Path(workspace)

    groups = dependency_policy.groups if dependency_policy is not None else ()

    # --- Step 1: pre-dispatch dependency evaluation, exactly once per
    # (repo, ecosystem), before any per-repo dispatch or dismissal logic. ---
    dependency_evaluations_by_repo: dict[str, dict[str, DependencyRepoEvaluation]] = {}
    all_evaluations: list[DependencyRepoEvaluation] = []
    all_summaries: list[RepositoryEvaluationSummary] = []
    for repo, ecosystems in dependency_selected_repos(config).items():
        for ecosystem in sorted(ecosystems):
            repo_evidence = (
                dependency_evidence.get(repo) if dependency_evidence is not None else None
            )
            evaluation = evaluate_dependencies(repo, ecosystem, repo_evidence)
            dependency_evaluations_by_repo.setdefault(repo, {})[ecosystem] = evaluation
            all_evaluations.append(evaluation)
            all_summaries.append(build_repository_evaluation_summary(evaluation, groups))

    profiled = sorted(config.repositories)
    unprofiled = sorted(set(evidence_by_repo) - set(config.repositories))
    fleet_repos = fleet_coherence_selected_repos(config)
    repos = []
    for repo in profiled:
        entry = evidence_by_repo.get(repo, {"repo": repo})
        if repo in overlay_repos and gh_api is not None:
            entry = _attach_overlay_content(repo, entry, gh_api)
        elif repo in overlay_repos:
            # Shallow copy so pre-attached fixture content is usable without
            # sharing mutable state with the caller.
            entry = dict(entry)
        else:
            entry = dict(entry)
        entry["dependency_evaluations"] = dependency_evaluations_by_repo.get(repo, {})
        repos.append(
            _repo_result(
                repo,
                entry,
                config,
                registry,
                workspace_path,
                dismissals,
                as_of_date,
            )
        )

    # --- Steps 3-4: the fleet pass — one compare() call for the whole run,
    # replacing every selected repo's placeholder in place, then rescoring. ---
    errors: list[str] = []
    report = DivergenceReport(findings=(), unresolved=())
    if fleet_repos:
        if dependency_policy is None:
            errors.append("dependencies.yaml missing: fleet_dependency_coherence unresolved")
        else:
            records = tuple(
                record for evaluation in all_evaluations for record in evaluation.records
            )
            report = compare(records, groups)

    repos_by_name = {repo_dict["repo"]: repo_dict for repo_dict in repos}
    for repo in fleet_repos:
        repo_dict = repos_by_name.get(repo)
        if repo_dict is None:
            continue
        checks = repo_dict["checks"]
        placeholder = checks.get(FLEET_COHERENCE_CHECK_ID)
        if placeholder is None or placeholder.get("adapter") != "fleet.dependencies.coherence":
            raise ConfigError(
                f"{repo}: missing or mismatched fleet_dependency_coherence placeholder"
            )
        weight = placeholder["weight"]
        if dependency_policy is None:
            block = build_fleet_missing_policy_block(weight)
        else:
            block = build_fleet_coherence_block(repo, weight, report, groups)
        checks[FLEET_COHERENCE_CHECK_ID] = block

        dismissal_entry = _repo_dismissals(repo, dismissals).get(FLEET_COHERENCE_CHECK_ID)
        if dismissal_entry is not None:
            dismissal, scope = dismissal_entry
            _apply_single_dismissal(
                checks, FLEET_COHERENCE_CHECK_ID, dismissal, scope, as_of_date
            )

        summary = score_checks(checks)
        repo_dict["score"] = summary.score
        repo_dict["total"] = summary.total
        repo_dict["grade"] = summary.grade
        repo_dict["coverage_supported"] = summary.coverage_supported
        repo_dict["coverage_total"] = summary.coverage_total

    by_scorecard = aggregate_by_scorecard(repos)
    coverage = fleet_coverage(repos)

    dependency_coverage = reconcile_coverage(all_summaries, groups)
    if dependency_collector is not None:
        dependency_collector["records"] = tuple(
            record for evaluation in all_evaluations for record in evaluation.records
        )
        dependency_collector["groups"] = groups
        dependency_collector["report"] = report
        dependency_collector["repository_evaluations"] = tuple(all_summaries)

    result = {
        "repos": repos,
        "aggregate": {"by_scorecard": by_scorecard},
        "coverage": {
            **coverage,
            "unprofiled_repos": unprofiled,
            "dependencies": dependency_coverage_to_dict(dependency_coverage),
        },
    }
    if errors:
        result["errors"] = errors
    return result


def _load_evidence(path: Path) -> Mapping[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"evidence not found: {path}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"could not load evidence: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ConfigError("evidence must be a mapping")
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--dismissals")
    parser.add_argument("--as-of")
    parser.add_argument(
        "--fetch-overlay-content",
        action="store_true",
        help=(
            "Collect overlay file_contents via gh api for repos whose scorecard "
            "opts into claude.* adapters. Pre-attached file_contents are kept. "
            "Default off so offline/fixture runs stay network-free; the skill "
            "attaches content (or passes this flag) for live overlay audits."
        ),
    )
    args = parser.parse_args(argv)

    try:
        gh_api = None
        if args.fetch_overlay_content:
            from lib.pulse.scripts.overlay_content import default_gh_api

            gh_api = default_gh_api
        result = evaluate_fleet(
            evidence=_load_evidence(Path(args.evidence)),
            profiles_path=args.profiles,
            workspace=args.workspace,
            dismissals_path=args.dismissals,
            as_of=args.as_of,
            gh_api=gh_api,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        rendered = json.dumps(result, indent=2, allow_nan=False)
    except ValueError as exc:
        print(f"error: result is not strict JSON: {exc}", file=sys.stderr)
        return 1
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
