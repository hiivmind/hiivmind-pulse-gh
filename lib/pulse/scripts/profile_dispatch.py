#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Load authoritative repository profiles and dispatch scorecard checks."""

from __future__ import annotations

from dataclasses import dataclass
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
class ProfileConfig:
    repositories: dict[str, RepositoryProfile]
    scorecards: dict[str, Scorecard]
    adapters: dict[str, AdapterDefinition]


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
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
        raise ConfigError(f"check {check_id}.weight must be a non-negative number")
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
    _only_keys(root, required, "profile config")
    missing = required - set(root)
    if missing:
        raise ConfigError(f"missing profile config key: {sorted(missing)[0]}")

    adapters = _load_adapters(_mapping(root["adapters"], "adapters"))
    scorecards = _load_scorecards(_mapping(root["scorecards"], "scorecards"))
    repositories = _load_repositories(
        _mapping(root["repository_profiles"], "repository_profiles")
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
    return ProfileConfig(repositories, scorecards, adapters)
