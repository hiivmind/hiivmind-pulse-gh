#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Diff a live GitHub repository set against the workspace catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


STABLE_FIELDS = (
    "name",
    "id",
    "full_name",
    "default_branch",
    "is_public",
    "archived",
    "fork",
    "mirror_url",
)
DEFAULT_DISCOVERY = {
    "include_archived": True,
    "include_forks": False,
    "include_mirrors": False,
}


class MembershipError(ValueError):
    """Raised when membership inputs cannot be reconciled safely."""


def _repo_id(repo: dict[str, Any]) -> str | None:
    value = repo.get("node_id") or repo.get("id")
    return value if isinstance(value, str) and value else None


def _full_name(repo: dict[str, Any]) -> str:
    value = repo.get("full_name")
    if not isinstance(value, str) or "/" not in value:
        raise MembershipError("repository full_name must be owner/name")
    return value


def _stable_facts(repo: dict[str, Any]) -> dict[str, Any]:
    full_name = _full_name(repo)
    node_id = _repo_id(repo)
    if node_id is None:
        raise MembershipError(f"live repository has no node ID: {full_name}")
    visibility = repo.get("visibility")
    if visibility is not None:
        is_public = visibility == "public"
    else:
        is_public = not bool(repo.get("private", False))
    return {
        "name": full_name.split("/", 1)[1],
        "id": node_id,
        "full_name": full_name,
        "default_branch": repo.get("default_branch") or "main",
        "is_public": is_public,
        "archived": bool(repo.get("archived", False)),
        "fork": bool(repo.get("fork", False)),
        "mirror_url": repo.get("mirror_url"),
    }


def _finding(kind: str, repo: str, detail: str, **extra: Any) -> dict[str, Any]:
    finding = {
        "kind": kind,
        "repo": repo,
        "severity": "medium",
        "detail": detail,
    }
    finding.update(extra)
    return finding


def _discovery_policy(config: dict[str, Any]) -> dict[str, bool]:
    raw = ((config.get("fleet_membership") or {}).get("discovery") or {})
    if not isinstance(raw, dict):
        raise MembershipError("fleet_membership.discovery must be a mapping")
    unknown = set(raw) - set(DEFAULT_DISCOVERY)
    if unknown:
        raise MembershipError(f"unknown discovery policy: {sorted(unknown)[0]}")
    policy = dict(DEFAULT_DISCOVERY)
    for key, value in raw.items():
        if not isinstance(value, bool):
            raise MembershipError(f"discovery policy {key} must be boolean")
        policy[key] = value
    return policy


def _excluded_reason(repo: dict[str, Any], policy: dict[str, bool]) -> str | None:
    if repo.get("fork") and not policy["include_forks"]:
        return "fork excluded by discovery policy"
    if repo.get("mirror_url") and not policy["include_mirrors"]:
        return "mirror excluded by discovery policy"
    if repo.get("archived") and not policy["include_archived"]:
        return "archived repository excluded by discovery policy"
    return None


def _unique_index(
    repositories: list[dict[str, Any]],
    key_fn,
    label: str,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for repo in repositories:
        value = key_fn(repo)
        if value is None:
            continue
        if value in index:
            raise MembershipError(f"duplicate {label}: {value}")
        index[value] = repo
    return index


def reconcile_membership(
    org_repos: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic desired catalog and identity-aware findings."""
    if not isinstance(org_repos, list) or not all(isinstance(r, dict) for r in org_repos):
        raise MembershipError("org repositories must be a list of mappings")
    catalog = config.get("repositories", [])
    if not isinstance(catalog, list) or not all(isinstance(r, dict) for r in catalog):
        raise MembershipError("config repositories must be a list of mappings")

    policy = _discovery_policy(config)
    catalog_by_id = _unique_index(catalog, _repo_id, "catalog node ID")
    catalog_by_name = _unique_index(catalog, _full_name, "catalog full_name")
    _unique_index(org_repos, _repo_id, "live node ID")

    findings: list[dict[str, Any]] = []
    desired: list[dict[str, Any]] = []
    matched_catalog: set[int] = set()
    included_names: list[str] = []

    for live in sorted(org_repos, key=_full_name):
        full_name = _full_name(live)
        node_id = _repo_id(live)
        reason = _excluded_reason(live, policy)
        existing = catalog_by_id.get(node_id) if node_id else None
        if existing is None:
            existing = catalog_by_name.get(full_name)
        if reason is not None:
            if existing is not None:
                matched_catalog.add(id(existing))
            findings.append(_finding("repository-excluded", full_name, reason))
            continue

        facts = _stable_facts(live)
        included_names.append(full_name)
        desired.append(facts)
        existing_by_id = catalog_by_id.get(facts["id"])
        existing_by_name = catalog_by_name.get(full_name)

        if existing_by_id is not None:
            matched_catalog.add(id(existing_by_id))
            old_name = _full_name(existing_by_id)
            if old_name != full_name:
                old_owner = old_name.split("/", 1)[0]
                new_owner = full_name.split("/", 1)[0]
                kind = "repository-renamed" if old_owner == new_owner else "repository-transferred"
                findings.append(_finding(
                    kind,
                    full_name,
                    f"repository identity moved from {old_name} to {full_name}",
                    before=old_name,
                    after=full_name,
                ))
            if not bool(existing_by_id.get("archived", False)) and facts["archived"]:
                findings.append(_finding(
                    "repository-archived",
                    full_name,
                    "repository is now archived",
                ))
            continue

        if existing_by_name is not None and _repo_id(existing_by_name) is None:
            matched_catalog.add(id(existing_by_name))
            findings.append(_finding(
                "repository-identity-backfilled",
                full_name,
                f"catalog entry gained GitHub node ID {facts['id']}",
            ))
            continue

        findings.append(_finding(
            "repository-created",
            full_name,
            "repository is present in GitHub but absent from the catalog",
        ))

    for existing in sorted(catalog, key=_full_name):
        if id(existing) in matched_catalog:
            continue
        full_name = _full_name(existing)
        findings.append(_finding(
            "repository-missing",
            full_name,
            "catalog repository is absent from the live organization set",
        ))

    desired.sort(key=lambda repo: repo["full_name"])
    return {
        "findings": findings,
        "catalog_patch": desired,
        "org_repos": sorted(included_names),
        "catalog_repos": [repo["full_name"] for repo in desired],
    }


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise MembershipError(f"input not found: {path}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise MembershipError(f"could not load {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-repos", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = reconcile_membership(_load(args.org_repos), _load(args.config))
    except MembershipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
