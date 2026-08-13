#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Strictly load the committed fleet dependency-coherence policy (dependencies.yaml).

See lib/patterns/dependency-coherence.md for the schema. Unlike a plain
`yaml.safe_load`, this loader detects duplicate mapping keys at every nesting
level (default PyYAML silently keeps the last key and would hide a duplicate
`coherence_groups` entry or a duplicate group). Because that detection only
works on the raw YAML text — a document already parsed with a normal loader
has already lost the duplicate-key information — every entry point here
accepts YAML text, never a pre-parsed dict.
"""

from __future__ import annotations

from typing import Any

import yaml

from lib.pulse.scripts.dependencies import CoherenceGroup, DependencyPolicy, is_valid_package_glob


SUPPORTED_VERSIONS = {1}
POLICIES = {"exact", "same-major", "same-minor"}
TOP_LEVEL_KEYS = {"contract_version", "coherence_groups"}
GROUP_KEYS = {"repos", "packages", "exclude_packages", "policy"}


class DependencyPolicyError(ValueError):
    """Raised when a committed dependencies.yaml document violates its schema."""


class _DuplicateKeyLoader(yaml.SafeLoader):
    """A SafeLoader that raises on duplicate mapping keys instead of last-key-wins."""


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.Node, deep: bool = False) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DependencyPolicyError(f"duplicate key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DependencyPolicyError(f"{label} must be a mapping")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DependencyPolicyError(f"{label} must be a list")
    return value


def _only_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise DependencyPolicyError(f"unknown {label} key: {sorted(unknown)[0]}")
    missing = allowed - set(data)
    if missing:
        raise DependencyPolicyError(f"missing required {label} key: {sorted(missing)[0]}")


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    items = _list(value, label)
    result: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item:
            raise DependencyPolicyError(f"{label} entries must be non-empty strings")
        if item in result:
            raise DependencyPolicyError(f"{label} has duplicate entry: {item}")
        result.append(item)
    return tuple(result)


def _load_group(group_id: str, raw: Any) -> CoherenceGroup:
    data = _mapping(raw, f"coherence_groups.{group_id}")
    allowed = GROUP_KEYS
    required = {"repos", "packages", "policy"}
    unknown = set(data) - allowed
    if unknown:
        raise DependencyPolicyError(
            f"unknown coherence_groups.{group_id} key: {sorted(unknown)[0]}"
        )
    missing = required - set(data)
    if missing:
        raise DependencyPolicyError(
            f"missing required coherence_groups.{group_id} key: {sorted(missing)[0]}"
        )

    repos = _string_list(data["repos"], f"coherence_groups.{group_id}.repos")
    if not repos:
        raise DependencyPolicyError(f"coherence_groups.{group_id}.repos must be non-empty")

    packages = _string_list(data["packages"], f"coherence_groups.{group_id}.packages")
    if not packages:
        raise DependencyPolicyError(f"coherence_groups.{group_id}.packages must be non-empty")
    for glob in packages:
        if not is_valid_package_glob(glob):
            raise DependencyPolicyError(
                f"coherence_groups.{group_id}.packages has an invalid glob: {glob!r}"
            )

    exclude_packages = _string_list(
        data.get("exclude_packages", []), f"coherence_groups.{group_id}.exclude_packages"
    )
    for glob in exclude_packages:
        if not is_valid_package_glob(glob):
            raise DependencyPolicyError(
                f"coherence_groups.{group_id}.exclude_packages has an invalid glob: {glob!r}"
            )

    policy = data["policy"]
    if policy not in POLICIES:
        raise DependencyPolicyError(
            f"coherence_groups.{group_id}.policy invalid: {policy!r}"
        )

    return CoherenceGroup(
        id=group_id,
        repos=repos,
        packages=packages,
        exclude_packages=exclude_packages,
        policy=policy,
    )


def parse_dependency_policy(text: str) -> DependencyPolicy:
    """Strictly parse committed dependencies.yaml text into a DependencyPolicy."""
    try:
        raw = yaml.load(text, Loader=_DuplicateKeyLoader)
    except DependencyPolicyError:
        raise
    except yaml.YAMLError as exc:
        raise DependencyPolicyError(f"invalid YAML: {exc}") from exc

    document = _mapping(raw, "dependencies.yaml")
    _only_keys(document, TOP_LEVEL_KEYS, "dependencies.yaml")

    version = document["contract_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version not in SUPPORTED_VERSIONS:
        raise DependencyPolicyError(f"unsupported contract_version: {version!r}")

    groups_raw = _mapping(document["coherence_groups"], "coherence_groups")
    groups: list[CoherenceGroup] = []
    for group_id, group_data in groups_raw.items():
        if not isinstance(group_id, str) or not group_id:
            raise DependencyPolicyError("coherence_groups keys must be non-empty strings")
        groups.append(_load_group(group_id, group_data))

    return DependencyPolicy(groups=tuple(groups))


def load_dependency_policy(path: str) -> DependencyPolicy:
    """Read and strictly parse a committed dependencies.yaml file."""
    with open(path, encoding="utf-8") as handle:
        return parse_dependency_policy(handle.read())
