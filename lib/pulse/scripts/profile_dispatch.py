#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Load authoritative repository profiles and dispatch scorecard checks."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from math import isfinite
from pathlib import Path
from typing import Any

import yaml


ADAPTER_STATES = {"available", "unsupported"}


class ConfigError(ValueError):
    """Raised when committed profile metadata violates its schema."""


@dataclass(frozen=True)
class RepositoryProfile:
    profiles: tuple[str, ...]
    scorecard: str


@dataclass(frozen=True)
class CheckDefinition:
    id: str
    adapter: str
    weight: float
    applicability: str = "always"
    replace: bool = False


@dataclass(frozen=True)
class Scorecard:
    id: str
    checks: tuple[CheckDefinition, ...]
    extends: str | None = None


@dataclass(frozen=True)
class AdapterDefinition:
    id: str
    state: str
    reason: str | None = None


@dataclass(frozen=True)
class ProposalRule:
    id: str
    profile: str
    confidence: float
    priority: int
    any_paths: tuple[str, ...] = ()
    all_paths: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    structural_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileConfig:
    repositories: dict[str, RepositoryProfile]
    scorecards: dict[str, Scorecard]
    adapters: dict[str, AdapterDefinition]
    proposal_rules: dict[str, ProposalRule]


@dataclass(frozen=True)
class PlannedCheck:
    definition: CheckDefinition
    state: str | None
    reason: str | None = None

    @property
    def check_id(self) -> str:
        return self.definition.id

    @property
    def adapter(self) -> str:
        return self.definition.adapter

    @property
    def weight(self) -> float:
        return self.definition.weight


@dataclass(frozen=True)
class DispatchPlan:
    repo: str
    profiles: tuple[str, ...]
    scorecard: str
    checks: dict[str, PlannedCheck]


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise ConfigError(f"{label} keys must be strings")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"{label} must be a list")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string")
    return value


def _only_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ConfigError(f"unknown {label} key: {sorted(unknown)[0]}")


def _load_adapters(raw: dict[str, Any]) -> dict[str, AdapterDefinition]:
    adapters: dict[str, AdapterDefinition] = {}
    for adapter_id, value in raw.items():
        adapter_id = _string(adapter_id, "adapter id")
        item = _mapping(value, f"adapter {adapter_id}")
        _only_keys(item, {"state", "reason"}, "adapter")
        state = _string(item.get("state"), f"adapter {adapter_id}.state")
        if state not in ADAPTER_STATES:
            raise ConfigError(f"invalid adapter state: {state}")
        reason = item.get("reason")
        if reason is not None:
            reason = _string(reason, f"adapter {adapter_id}.reason")
        if state == "unsupported" and reason is None:
            raise ConfigError(f"unsupported adapter requires reason: {adapter_id}")
        adapters[adapter_id] = AdapterDefinition(adapter_id, state, reason)
    return adapters


def _load_check(raw: Any, scorecard_id: str) -> CheckDefinition:
    item = _mapping(raw, f"scorecard {scorecard_id} check")
    _only_keys(
        item,
        {"id", "adapter", "weight", "applicability", "replace"},
        "check",
    )
    check_id = _string(item.get("id"), f"scorecard {scorecard_id} check id")
    adapter = _string(item.get("adapter"), f"check {check_id}.adapter")
    weight = item.get("weight")
    if (
        isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or not isfinite(weight)
        or weight < 0
    ):
        raise ConfigError(
            f"check {check_id}.weight must be a finite non-negative number"
        )
    applicability = item.get("applicability", "always")
    applicability = _string(applicability, f"check {check_id}.applicability")
    replace = item.get("replace", False)
    if not isinstance(replace, bool):
        raise ConfigError(f"check {check_id}.replace must be a boolean")
    return CheckDefinition(check_id, adapter, float(weight), applicability, replace)


def _load_scorecards(raw: dict[str, Any]) -> dict[str, Scorecard]:
    scorecards: dict[str, Scorecard] = {}
    for scorecard_id, value in raw.items():
        scorecard_id = _string(scorecard_id, "scorecard id")
        item = _mapping(value, f"scorecard {scorecard_id}")
        _only_keys(item, {"extends", "checks"}, "scorecard")
        extends = item.get("extends")
        if extends is not None:
            extends = _string(extends, f"scorecard {scorecard_id}.extends")
        checks = tuple(
            _load_check(check, scorecard_id)
            for check in _list(item.get("checks"), f"scorecard {scorecard_id}.checks")
        )
        seen: set[str] = set()
        for check in checks:
            if check.id in seen:
                raise ConfigError(f"duplicate check in scorecard {scorecard_id}: {check.id}")
            seen.add(check.id)
        scorecards[scorecard_id] = Scorecard(scorecard_id, checks, extends)
    return scorecards


def _load_repositories(raw: dict[str, Any]) -> dict[str, RepositoryProfile]:
    repositories: dict[str, RepositoryProfile] = {}
    for repo, value in raw.items():
        repo = _string(repo, "repository name")
        item = _mapping(value, f"repository profile {repo}")
        _only_keys(item, {"profiles", "scorecard"}, "repository profile")
        profiles = tuple(
            _string(profile, f"repository {repo} profile")
            for profile in _list(item.get("profiles"), f"repository {repo}.profiles")
        )
        seen: set[str] = set()
        for profile in profiles:
            if profile in seen:
                raise ConfigError(f"duplicate profile: {profile}")
            seen.add(profile)
        scorecard = _string(item.get("scorecard"), f"repository {repo}.scorecard")
        repositories[repo] = RepositoryProfile(profiles, scorecard)
    return repositories


def _optional_strings(item: dict[str, Any], key: str, label: str) -> tuple[str, ...]:
    values = item.get(key, [])
    return tuple(
        _string(value, f"{label}.{key}")
        for value in _list(values, f"{label}.{key}")
    )


def _load_proposal_rules(raw: dict[str, Any]) -> dict[str, ProposalRule]:
    rules: dict[str, ProposalRule] = {}
    selector_keys = {"any_paths", "all_paths", "capabilities", "structural_signals"}
    for rule_id, value in raw.items():
        rule_id = _string(rule_id, "proposal rule id")
        item = _mapping(value, f"proposal rule {rule_id}")
        _only_keys(
            item,
            {"profile", "confidence", "priority", *selector_keys},
            "proposal rule",
        )
        profile = _string(item.get("profile"), f"proposal rule {rule_id}.profile")
        confidence = item.get("confidence")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise ConfigError(
                f"proposal rule {rule_id}.confidence must be between 0 and 1"
            )
        priority = item.get("priority", 100)
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:
            raise ConfigError(
                f"proposal rule {rule_id}.priority must be a non-negative integer"
            )
        selectors = {
            key: _optional_strings(item, key, f"proposal rule {rule_id}")
            for key in selector_keys
        }
        if not any(selectors.values()):
            raise ConfigError(f"proposal rule {rule_id} requires an evidence selector")
        rules[rule_id] = ProposalRule(
            rule_id,
            profile,
            float(confidence),
            priority,
            selectors["any_paths"],
            selectors["all_paths"],
            selectors["capabilities"],
            selectors["structural_signals"],
        )
    return rules


def load_profiles(path: str | Path) -> ProfileConfig:
    """Load and cross-validate committed profile metadata."""
    source = Path(path)
    try:
        data = yaml.safe_load(source.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"profile config not found: {source}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"could not load profile config: {exc}") from exc
    root = _mapping(data, "profile config")
    required = {"repository_profiles", "scorecards", "adapters"}
    _only_keys(root, required | {"proposal_rules"}, "profile config")
    missing = required - set(root)
    if missing:
        raise ConfigError(f"missing profile config key: {sorted(missing)[0]}")

    adapters = _load_adapters(_mapping(root["adapters"], "adapters"))
    scorecards = _load_scorecards(_mapping(root["scorecards"], "scorecards"))
    repositories = _load_repositories(
        _mapping(root["repository_profiles"], "repository_profiles")
    )
    proposal_rules = _load_proposal_rules(
        _mapping(root.get("proposal_rules", {}), "proposal_rules")
    )

    for scorecard in scorecards.values():
        if scorecard.extends is not None and scorecard.extends not in scorecards:
            raise ConfigError(f"unknown scorecard: {scorecard.extends}")
        for check in scorecard.checks:
            if check.adapter not in adapters:
                raise ConfigError(f"unknown adapter: {check.adapter}")
    for repository in repositories.values():
        if repository.scorecard not in scorecards:
            raise ConfigError(f"unknown scorecard: {repository.scorecard}")
    return ProfileConfig(repositories, scorecards, adapters, proposal_rules)


def resolve_scorecard(
    config: ProfileConfig,
    scorecard_id: str,
    _stack: tuple[str, ...] = (),
) -> tuple[CheckDefinition, ...]:
    """Resolve inheritance with explicit, deterministic check replacement."""
    if scorecard_id not in config.scorecards:
        raise ConfigError(f"unknown scorecard: {scorecard_id}")
    if scorecard_id in _stack:
        cycle = " -> ".join((*_stack, scorecard_id))
        raise ConfigError(f"scorecard inheritance cycle: {cycle}")

    scorecard = config.scorecards[scorecard_id]
    resolved = list(
        resolve_scorecard(config, scorecard.extends, (*_stack, scorecard_id))
        if scorecard.extends is not None
        else ()
    )
    positions = {check.id: index for index, check in enumerate(resolved)}
    for check in scorecard.checks:
        if check.id in positions:
            if not check.replace:
                raise ConfigError(
                    f"duplicate check {check.id} requires replace: true"
                )
            resolved[positions[check.id]] = check
            continue
        if check.replace:
            raise ConfigError(
                f"check {check.id} sets replace but is not inherited"
            )
        positions[check.id] = len(resolved)
        resolved.append(check)
    return tuple(resolved)


def _repo_evidence(snapshot: dict[str, Any], repo: str) -> dict[str, Any]:
    if snapshot.get("repo") == repo:
        return snapshot
    repos = snapshot.get("repos", [])
    if not isinstance(repos, list):
        raise ConfigError("evidence repos must be a list")
    matches = [entry for entry in repos if isinstance(entry, dict) and entry.get("repo") == repo]
    if len(matches) > 1:
        raise ConfigError(f"duplicate evidence for repository: {repo}")
    return matches[0] if matches else {}


def _string_set(evidence: dict[str, Any], key: str) -> set[str]:
    values = evidence.get(key, [])
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ConfigError(f"repository evidence {key} must be a list of strings")
    return set(values)


def _is_applicable(
    predicate: str,
    repository: RepositoryProfile,
    evidence: dict[str, Any],
) -> bool:
    if predicate == "always":
        return True
    if ":" not in predicate:
        raise ConfigError(f"unsupported applicability: {predicate}")
    kind, value = predicate.split(":", 1)
    if not value:
        raise ConfigError(f"unsupported applicability: {predicate}")
    if kind == "profile":
        return value in repository.profiles
    if kind == "capability":
        return value in _string_set(evidence, "capabilities")
    if kind == "evidence_path":
        return any(fnmatchcase(path, value) for path in _string_set(evidence, "files"))
    raise ConfigError(f"unsupported applicability: {predicate}")


def dispatch(repo: str, evidence: dict[str, Any], config: ProfileConfig) -> DispatchPlan:
    """Resolve one repository's authoritative scorecard into an execution plan."""
    if repo not in config.repositories:
        raise ConfigError(f"repository has no authoritative profile: {repo}")
    repository = config.repositories[repo]
    repo_evidence = _repo_evidence(evidence, repo)
    checks: dict[str, PlannedCheck] = {}
    for check in resolve_scorecard(config, repository.scorecard):
        if not _is_applicable(check.applicability, repository, repo_evidence):
            planned = PlannedCheck(
                check,
                "not_applicable",
                f"predicate not satisfied: {check.applicability}",
            )
        else:
            adapter = config.adapters[check.adapter]
            if adapter.state == "unsupported":
                planned = PlannedCheck(check, "unsupported", adapter.reason)
            else:
                planned = PlannedCheck(check, None)
        checks[check.id] = planned
    return DispatchPlan(repo, repository.profiles, repository.scorecard, checks)
