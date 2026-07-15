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


def _repo_result(
    repo: str,
    evidence: dict[str, Any],
    config: Any,
    registry: AdapterRegistry,
    workspace: Path,
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
) -> dict[str, Any]:
    """Dispatch and evaluate profiled repositories from one F0 fleet snapshot."""
    if not isinstance(evidence, Mapping):
        raise ConfigError("evidence must be a mapping")
    evidence_by_repo = _evidence_repositories(evidence)
    config = load_profiles(profiles_path)
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
        )
        for repo in profiled
    ]

    scorecard_percentages: dict[str, list[float]] = defaultdict(list)
    unsupported = Counter()
    checks_total = 0
    checks_supported = 0
    for repo in repos:
        total = repo["total"]
        percent = repo["score"] / total * 100 if total else 0.0
        scorecard_percentages[repo["scorecard"]].append(percent)
        for check in repo["checks"].values():
            checks_total += 1
            if check["status"] == "unsupported":
                unsupported[check["adapter"]] += 1
            else:
                checks_supported += 1

    by_scorecard = {
        scorecard: {
            "repos": len(percentages),
            "average_percent": round(sum(percentages) / len(percentages), 2),
        }
        for scorecard, percentages in sorted(scorecard_percentages.items())
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
    args = parser.parse_args(argv)

    try:
        result = evaluate_fleet(
            evidence=_load_evidence(Path(args.evidence)),
            profiles_path=args.profiles,
            workspace=args.workspace,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
