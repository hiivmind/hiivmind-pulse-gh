#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Generate non-authoritative profile candidates from normalized evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml

try:
    from .profile_dispatch import ConfigError, ProfileConfig, ProposalRule, load_profiles
except ImportError:  # direct script execution
    from profile_dispatch import ConfigError, ProfileConfig, ProposalRule, load_profiles


class ProposalError(ValueError):
    """Raised when evidence or repository selection is malformed."""


class ProposalConflict(ProposalError):
    """Raised when authoritative profile metadata changed since review."""


def _strings(data: dict[str, Any], key: str) -> list[str]:
    values = data.get(key, [])
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ProposalError(f"repository evidence {key} must be a list of strings")
    return values


def _path_matches(pattern: str, paths: list[str]) -> list[str]:
    return sorted(path for path in paths if fnmatchcase(path, pattern))


def _match_rule(rule: ProposalRule, evidence: dict[str, Any]) -> list[str] | None:
    paths = _strings(evidence, "files")
    capabilities = set(_strings(evidence, "capabilities"))
    signals = set(_strings(evidence, "structural_signals"))
    observed: set[str] = set()

    if rule.any_paths:
        any_matches = {
            path
            for pattern in rule.any_paths
            for path in _path_matches(pattern, paths)
        }
        if not any_matches:
            return None
        observed.update(any_matches)
    for pattern in rule.all_paths:
        matches = _path_matches(pattern, paths)
        if not matches:
            return None
        observed.update(matches)
    if not set(rule.capabilities).issubset(capabilities):
        return None
    observed.update(f"capability:{value}" for value in rule.capabilities)
    if not set(rule.structural_signals).issubset(signals):
        return None
    observed.update(f"signal:{value}" for value in rule.structural_signals)
    return sorted(observed)


def _evidence_by_repo(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict):
        raise ProposalError("evidence snapshot must be a mapping")
    repos = snapshot.get("repos", [])
    if not isinstance(repos, list):
        raise ProposalError("evidence repos must be a list")
    result: dict[str, dict[str, Any]] = {}
    for entry in repos:
        if not isinstance(entry, dict) or not isinstance(entry.get("repo"), str):
            raise ProposalError("evidence repository must be a mapping with repo")
        repo = entry["repo"]
        if repo in result:
            raise ProposalError(f"duplicate evidence repository: {repo}")
        result[repo] = entry
    return result


def _candidate_list(
    evidence: dict[str, Any],
    rules: dict[str, ProposalRule],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered_rules = sorted(rules.values(), key=lambda rule: (rule.priority, rule.id))
    for rule in ordered_rules:
        observed = _match_rule(rule, evidence)
        if observed is None:
            continue
        candidate = merged.setdefault(
            rule.profile,
            {
                "profile": rule.profile,
                "confidence": rule.confidence,
                "evidence": [],
                "rule_ids": [],
                "_priority": rule.priority,
            },
        )
        candidate["confidence"] = max(candidate["confidence"], rule.confidence)
        candidate["evidence"] = sorted(set(candidate["evidence"]) | set(observed))
        candidate["rule_ids"].append(rule.id)
        candidate["_priority"] = min(candidate["_priority"], rule.priority)
    candidates = sorted(merged.values(), key=lambda item: (item["_priority"], item["profile"]))
    for candidate in candidates:
        del candidate["_priority"]
    return candidates


def generate_profile_proposals(
    snapshot: dict[str, Any],
    config: ProfileConfig,
    repos: list[str],
    explanations: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Compute ordered candidates; explanations can annotate but never classify."""
    if not isinstance(repos, list) or not all(isinstance(repo, str) for repo in repos):
        raise ProposalError("repositories must be a list of strings")
    if explanations is not None and (
        not isinstance(explanations, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in explanations.items())
    ):
        raise ProposalError("explanations must map repository names to strings")
    by_repo = _evidence_by_repo(snapshot)
    proposals: list[dict[str, Any]] = []
    for repo in sorted(set(repos)):
        evidence = by_repo.get(repo, {"repo": repo, "files": [], "capabilities": [], "structural_signals": []})
        candidates = _candidate_list(evidence, config.proposal_rules)
        authoritative = config.repositories.get(repo)
        if authoritative is not None and {
            candidate["profile"] for candidate in candidates
        }.issubset(set(authoritative.profiles)):
            continue
        proposal = {
            "repo": repo,
            "candidates": candidates,
            "evidence": {
                "files": sorted(set(_strings(evidence, "files"))),
                "capabilities": sorted(set(_strings(evidence, "capabilities"))),
                "structural_signals": sorted(
                    set(_strings(evidence, "structural_signals"))
                ),
            },
        }
        if explanations and repo in explanations:
            proposal["explanation"] = explanations[repo]
            proposal["inferred"] = True
        proposals.append(proposal)
    return proposals


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise ProposalError(f"input not found: {path}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProposalError(f"could not load {path}: {exc}") from exc


def _selected_repos(data: Any) -> list[str]:
    if isinstance(data, dict):
        data = data.get("org_repos")
    if not isinstance(data, list) or not all(isinstance(repo, str) for repo in data):
        raise ProposalError("repos input must be a list or contain org_repos")
    return data


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except OSError:
                pass
        raise ProposalError(f"could not write profile metadata: {exc}") from exc


def confirm_profiles(
    path: str | Path,
    repo: str,
    expected_scorecard: str | None,
    profiles: list[str],
    scorecard: str,
) -> dict[str, Any]:
    """Compare-and-swap one authoritative repository profile assignment."""
    source = Path(path)
    config = load_profiles(source)
    raw = _load(source)
    if not isinstance(raw, dict):
        raise ProposalError("profile metadata root must be a mapping")
    if not isinstance(repo, str) or "/" not in repo:
        raise ProposalError("repo must be owner/name")
    if not profiles or not all(isinstance(profile, str) and profile.strip() for profile in profiles):
        raise ProposalError("profiles-list must contain non-empty profile IDs")
    if len(set(profiles)) != len(profiles):
        raise ProposalError("profiles-list contains duplicate profile IDs")
    if scorecard not in config.scorecards:
        raise ProposalError(f"unknown scorecard: {scorecard}")

    repositories = raw["repository_profiles"]
    current = repositories.get(repo)
    target = {"profiles": list(profiles), "scorecard": scorecard}
    if current == target:
        return {"changed": False, "repo": repo, **target}

    current_scorecard = current.get("scorecard") if isinstance(current, dict) else None
    if current_scorecard != expected_scorecard:
        expected = expected_scorecard if expected_scorecard is not None else "absent"
        actual = current_scorecard if current_scorecard is not None else "absent"
        raise ProposalConflict(
            f"expected scorecard {expected} for {repo}, found {actual}"
        )

    updated = dict(raw)
    updated_repositories = dict(repositories)
    updated_repositories[repo] = target
    updated["repository_profiles"] = updated_repositories
    _atomic_write(source, updated)
    return {"changed": True, "repo": repo, **target}


def _generate_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--repos", required=True, type=Path)
    parser.add_argument("--explanations", type=Path)
    args = parser.parse_args(argv)
    explanations = _load(args.explanations) if args.explanations else None
    proposals = generate_profile_proposals(
        _load(args.evidence),
        load_profiles(args.profiles),
        _selected_repos(_load(args.repos)),
        explanations,
    )
    print(json.dumps({"profile_proposals": proposals}, indent=2, sort_keys=True))
    return 0


def _confirm_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--expected-scorecard", required=True)
    parser.add_argument("--profiles-list", required=True)
    parser.add_argument("--scorecard", required=True)
    args = parser.parse_args(argv)
    profiles = [profile.strip() for profile in args.profiles_list.split(",")]
    expected = None if args.expected_scorecard == "absent" else args.expected_scorecard
    result = confirm_profiles(
        args.profiles,
        args.repo,
        expected,
        profiles,
        args.scorecard,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments[:1] == ["confirm"]:
            return _confirm_main(arguments[1:])
        return _generate_main(arguments)
    except (ConfigError, ProposalError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
