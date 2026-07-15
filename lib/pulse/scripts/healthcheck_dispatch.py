#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Evaluate a heterogeneous F0 fleet through authoritative scorecards."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from lib.pulse.scripts.adapters import register_universal_adapters
from lib.pulse.scripts.check_adapters import AdapterRegistry, CheckContext
from lib.pulse.scripts.evaluate_checks import score_checks
from lib.pulse.scripts.profile_dispatch import (
    ConfigError,
    PlannedCheck,
    dispatch,
    load_profiles,
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


def _json_native(value: Any) -> Any:
    """Recursively copy YAML-loaded metadata into JSON-native values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_native(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ConfigError(
        f"dismissal metadata contains unsupported type: {type(value).__name__}"
    )


def _apply_dismissals(
    repo: str,
    checks: dict[str, dict[str, Any]],
    dismissals: Mapping[str, Any],
    as_of: date,
) -> None:
    for check_id, (dismissal, scope) in _repo_dismissals(
        repo, dismissals
    ).items():
        if check_id not in checks:
            continue
        review_after = _review_after_date(
            dismissal.get("review_after"), scope=scope, check_id=check_id
        )
        if review_after is not None and as_of >= review_after:
            continue
        reason = dismissal.get("reason", "")
        checks[check_id] = {
            **checks[check_id],
            "status": "not_applicable",
            "detail": f"Dismissed: {reason}",
            "data": {
                "dismissed": True,
                "dismissal": _json_native(dismissal),
                "evidence": {
                    "paths": [],
                    "refs": [f"dismissals:{scope}:{check_id}"],
                },
            },
        }


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

    _apply_dismissals(repo, checks, dismissals, as_of)
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


def evaluate_fleet(
    *,
    evidence: Mapping[str, Any],
    profiles_path: str | Path,
    workspace: str | Path,
    dismissals_path: str | Path | None = None,
    as_of: str | date | datetime | None = None,
) -> dict[str, Any]:
    """Dispatch and evaluate profiled repositories from one F0 fleet snapshot."""
    if not isinstance(evidence, Mapping):
        raise ConfigError("evidence must be a mapping")
    evidence_by_repo = _evidence_repositories(evidence)
    config = load_profiles(profiles_path)
    dismissals = _load_dismissals(dismissals_path)
    as_of_date = _parse_as_of(as_of)
    registry = AdapterRegistry()
    register_universal_adapters(registry)
    workspace_path = Path(workspace)

    profiled = sorted(config.repositories)
    unprofiled = sorted(set(evidence_by_repo) - set(config.repositories))
    repos = [
        _repo_result(
            repo,
            evidence_by_repo.get(repo, {"repo": repo}),
            config,
            registry,
            workspace_path,
            dismissals,
            as_of_date,
        )
        for repo in profiled
    ]

    scorecard_repo_counts = Counter()
    scorecard_percentages: dict[str, list[float]] = defaultdict(list)
    unsupported = Counter()
    checks_total = 0
    checks_supported = 0
    for repo in repos:
        scorecard = repo["scorecard"]
        scorecard_repo_counts[scorecard] += 1
        total = repo["total"]
        if total:
            percent = repo["score"] / total * 100
            scorecard_percentages[scorecard].append(percent)
        for check in repo["checks"].values():
            checks_total += 1
            if check["status"] == "unsupported":
                unsupported[check["adapter"]] += 1
            else:
                checks_supported += 1

    by_scorecard = {
        scorecard: {
            "repos": repos_count,
            "repos_scored": len(scorecard_percentages[scorecard]),
            "average_percent": (
                round(
                    sum(scorecard_percentages[scorecard])
                    / len(scorecard_percentages[scorecard]),
                    2,
                )
                if scorecard_percentages[scorecard]
                else None
            ),
        }
        for scorecard, repos_count in sorted(scorecard_repo_counts.items())
    }
    return {
        "repos": repos,
        "aggregate": {"by_scorecard": by_scorecard},
        "coverage": {
            "checks_total": checks_total,
            "checks_supported": checks_supported,
            "unsupported_by_adapter": dict(sorted(unsupported.items())),
            "unprofiled_repos": unprofiled,
        },
    }


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
    args = parser.parse_args(argv)

    try:
        result = evaluate_fleet(
            evidence=_load_evidence(Path(args.evidence)),
            profiles_path=args.profiles,
            workspace=args.workspace,
            dismissals_path=args.dismissals,
            as_of=args.as_of,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
