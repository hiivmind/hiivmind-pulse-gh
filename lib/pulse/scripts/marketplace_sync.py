#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Pure marketplace entry version drift decision + proposal builder.

This module is the marketplace-binding equivalent of the plan-sync merge
path (`lib.pulse.scripts.plan_sync`): it reads the marketplace document's
recorded version for a plugin and the plugin repo's release list, decides
whether the marketplace entry is current, and — for `drift` or
`missing_entry` outcomes — wraps that decision in an F6 `Proposal` via
`mutation_plan.build_proposal`. The proposal is expected-SHA-guard ready
(F6 Task 3 will block a stale base at execution time).

**Pure module**: no subprocess, no filesystem, no `gh` calls. The caller
(the headless skill `skills/gh-marketplace-sync-headless/SKILL.md`)
fetches the releases and the marketplace document bytes and passes the
parsed values in.

The marketplace document is the parsed JSON of `<marketplace_repo>/<marketplace_file>`
(see `.claude-plugin/marketplace.json` for the live format): a top-level
mapping with a `plugins` list whose entries carry `name`, `source`,
`description`, `version`, and `keywords`. The plugin identifier field is
`name` (NOT `id`); the recorded version for `plugin_id` is the `version`
of the `plugins[]` entry whose `name == plugin_id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lib.pulse.scripts.mutation_plan import (
    Proposal,
    TransformationRegistry,
    build_proposal,
)


# Outcome strings. Frozen literals — the headless skill and tests key on
# these. `in_sync` is a positive outcome (no proposal). The other four
# carry distinct semantics; see the README above for the decision rules.
OUTCOME_NOT_APPLICABLE = "not_applicable"
OUTCOME_UNKNOWN = "unknown"
OUTCOME_IN_SYNC = "in_sync"
OUTCOME_MISSING_ENTRY = "missing_entry"
OUTCOME_DRIFT = "drift"

# `build_marketplace_proposal` only accepts these two outcomes — every
# other outcome is a caller bug (a proposal for `in_sync` would be a
# no-op; for `not_applicable`/`unknown` there is nothing to propose).
_PROPOSABLE_OUTCOMES = frozenset({OUTCOME_DRIFT, OUTCOME_MISSING_ENTRY})


@dataclass(frozen=True)
class MarketplaceDrift:
    """Pure decision from comparing a binding to its marketplace entry.

    `outcome` is one of the `OUTCOME_*` constants. `current_version` /
    `target_version` are `None` for `not_applicable` / `unknown`. The
    proposal-building function only accepts `drift` or `missing_entry`.
    """

    outcome: str
    plugin_id: str
    marketplace_repo: str
    marketplace_file: str
    current_version: str | None
    target_version: str | None
    reason: str | None = None


def _newest_stable_tag(releases: Any) -> str | None:
    """Return the newest STABLE `tagName` from a `gh release list --json` payload.

    `gh release list --json` returns newest-first; the first entry whose
    `isPrerelease` is not truthy AND `isDraft` is not truthy is the
    newest STABLE release. Defensive:

    - A non-mapping entry (e.g. `None`, stray `str`) is skipped.
    - A release with `isPrerelease is True` is skipped (prerelease).
    - A release with `isDraft is True` is skipped (draft).
    - Missing/non-bool `isPrerelease`/`isDraft` are treated as not-excluded
      only when their value is explicitly `False`; any other value
      (`None`, missing, non-bool truthy) is treated as excluded
      (fail-closed against accidental misrelease).

    Returns `None` when no entry is a stable release.
    """
    if not isinstance(releases, list):
        return None
    for entry in releases:
        if not isinstance(entry, dict):
            continue
        tag = entry.get("tagName")
        if not isinstance(tag, str) or not tag:
            continue
        is_prerelease = entry.get("isPrerelease")
        is_draft = entry.get("isDraft")
        # Only an explicit `False` counts as "not excluded". `True`/missing
        # /`None`/non-bool is treated as "excluded" — fail-closed against
        # misrelease of a release that lacks the flags.
        if is_prerelease is not False or is_draft is not False:
            continue
        return tag
    return None


def _find_plugin_entry(marketplace_doc: Any, plugin_id: Any) -> tuple[str | None, bool]:
    """Find the `plugins[]` entry whose `name == plugin_id`.

    Returns `(recorded_version, found)`:
    - `found=True, version=<str>` when the entry exists with a non-empty
      string `version`.
    - `found=True, version=None` when the entry exists but has no usable
      version (non-string or empty). The doc is structurally valid and the
      entry is present, so `compare` classifies it as `drift` (with
      `current_version=None`) — an UPDATE of the existing entry, not an
      `missing_entry` add that would duplicate it.
    - `found=False, version=None` when no entry's `name` matches
      `plugin_id` (or the doc is structurally unparseable).
    """
    if not isinstance(marketplace_doc, dict):
        return None, False
    plugins = marketplace_doc.get("plugins")
    if not isinstance(plugins, list):
        return None, False
    for entry in plugins:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == plugin_id:
            version = entry.get("version")
            if isinstance(version, str) and version:
                return version, True
            return None, True
    return None, False


def _binding_fields(binding: dict[str, Any] | None) -> tuple[str, str, str]:
    """Extract the three fields every outcome carries, defensively."""
    if not isinstance(binding, dict):
        return "", "", ""
    return (
        str(binding.get("plugin_id") or ""),
        str(binding.get("marketplace_repo") or ""),
        str(binding.get("marketplace_file") or ""),
    )


def compare(
    binding: dict[str, Any] | None,
    releases: Any,
    marketplace_doc: Any,
) -> MarketplaceDrift:
    """Compare the recorded marketplace entry to the newest stable plugin release.

    Returns a `MarketplaceDrift` whose `outcome` is one of:
    - `not_applicable` when `binding is None` (no marketplace binding for
      this repo — global F9 v1 constraint).
    - `unknown` (fail-closed, no decision) when no stable release is
      found, OR the marketplace document is unparseable / not the
      expected mapping shape. `reason` names the gap.
    - `in_sync` when the recorded `plugins[]` entry's `version` equals
      the newest stable `tagName`.
    - `missing_entry` when `plugin_id` is absent from `plugins[]` —
      treated as drift with an add; `current_version=None`,
      `target_version=<tag>`.
    - `drift` when the recorded version is present but ≠ the newest
      stable `tagName`; `current_version=<recorded>`, `target_version=<tag>`.
    """
    if binding is None:
        return MarketplaceDrift(
            outcome=OUTCOME_NOT_APPLICABLE,
            plugin_id="",
            marketplace_repo="",
            marketplace_file="",
            current_version=None,
            target_version=None,
            reason="no binding configured",
        )

    plugin_id, marketplace_repo, marketplace_file = _binding_fields(binding)
    newest = _newest_stable_tag(releases)

    if newest is None:
        return MarketplaceDrift(
            outcome=OUTCOME_UNKNOWN,
            plugin_id=plugin_id,
            marketplace_repo=marketplace_repo,
            marketplace_file=marketplace_file,
            current_version=None,
            target_version=None,
            reason="no stable release found",
        )

    if not isinstance(marketplace_doc, dict):
        return MarketplaceDrift(
            outcome=OUTCOME_UNKNOWN,
            plugin_id=plugin_id,
            marketplace_repo=marketplace_repo,
            marketplace_file=marketplace_file,
            current_version=None,
            target_version=newest,
            reason="marketplace_doc is not a mapping",
        )
    plugins = marketplace_doc.get("plugins")
    if not isinstance(plugins, list):
        return MarketplaceDrift(
            outcome=OUTCOME_UNKNOWN,
            plugin_id=plugin_id,
            marketplace_repo=marketplace_repo,
            marketplace_file=marketplace_file,
            current_version=None,
            target_version=newest,
            reason="marketplace_doc.plugins is not a list",
        )

    recorded, found = _find_plugin_entry(marketplace_doc, plugin_id)
    if not found:
        return MarketplaceDrift(
            outcome=OUTCOME_MISSING_ENTRY,
            plugin_id=plugin_id,
            marketplace_repo=marketplace_repo,
            marketplace_file=marketplace_file,
            current_version=None,
            target_version=newest,
            reason=f"plugin_id {plugin_id!r} not in marketplace plugins[]",
        )
    if recorded == newest:
        return MarketplaceDrift(
            outcome=OUTCOME_IN_SYNC,
            plugin_id=plugin_id,
            marketplace_repo=marketplace_repo,
            marketplace_file=marketplace_file,
            current_version=recorded,
            target_version=newest,
            reason=None,
        )
    return MarketplaceDrift(
        outcome=OUTCOME_DRIFT,
        plugin_id=plugin_id,
        marketplace_repo=marketplace_repo,
        marketplace_file=marketplace_file,
        current_version=recorded,
        target_version=newest,
        reason=f"recorded version {recorded!r} != newest stable {newest!r}",
    )


def build_marketplace_proposal(
    drift: MarketplaceDrift,
    head_sha: str,
    actor: dict[str, Any],
    registry: TransformationRegistry | None = None,
) -> Proposal:
    """Wrap a `drift` or `missing_entry` decision in an F6 `Proposal`.

    The proposal selects the `marketplace_repo` (single selection) and
    carries `expected_shas={marketplace_repo: head_sha}` so the F6
    expected-SHA guard (see `pen_orchestrator.execute`) blocks a stale
    base at execution. `mutation_policy="propose"` — this orchestrator
    is propose-only, exactly like `plan-sync-doc-patch`.

    Raises `ValueError` when `drift.outcome` is not in
    `{OUTCOME_DRIFT, OUTCOME_MISSING_ENTRY}` — the caller (the headless
    skill) is expected to only invoke this for those two outcomes.
    """
    if drift.outcome not in _PROPOSABLE_OUTCOMES:
        raise ValueError(
            f"build_marketplace_proposal requires drift or missing_entry, "
            f"got outcome={drift.outcome!r}"
        )
    return build_proposal(
        id=f"marketplace-{drift.plugin_id}",
        selection=[drift.marketplace_repo],
        transformation="marketplace-entry-update",
        expected_shas={drift.marketplace_repo: head_sha},
        actor=actor,
        mutation_policy="propose",
        registry=registry,
    )
