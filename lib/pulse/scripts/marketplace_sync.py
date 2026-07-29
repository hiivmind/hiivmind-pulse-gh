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
from datetime import datetime, timezone
from typing import Any

from lib.pulse.scripts import mutation_plan
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


def build_result(
    bindings: list[dict[str, Any]],
    *,
    releases_by_repo: dict[str, Any],
    docs_by_repo: dict[str, Any],
    head_shas: dict[str, Any],
    actor: dict[str, Any] | mutation_plan.Actor,
    registry: TransformationRegistry | None = None,
    mode: str = "interactive",
    workspace: str | None = None,
    run_at: str | None = None,
) -> dict[str, Any]:
    """Pure envelope owner for marketplace-sync result.

    Translates each binding's compare drift into typed findings + counters,
    handles invalid_binding, fetch errors, and calls
    build_marketplace_proposal(..., registry=registry) so allow_scheduled
    gating fires in scheduled mode.
    Returns a kind: marketplace-sync envelope body. No I/O.
    """
    if isinstance(actor, mutation_plan.Actor):
        actor_dict = {
            "gh_login": actor.gh_login,
            "machine": actor.machine,
            "mode": mode,
        }
    elif isinstance(actor, dict):
        actor_dict = dict(actor)
        actor_dict["mode"] = mode
    else:
        actor_dict = {"gh_login": "unknown", "machine": "unknown", "mode": mode}

    ws = workspace if workspace is not None else actor_dict.get("gh_login", "unknown")
    ts = run_at if run_at is not None else datetime.now(timezone.utc).isoformat()

    bindings_scanned = 0
    in_sync_count = 0
    drift_count = 0
    missing_entry_count = 0
    unknown_count = 0
    not_applicable_count = 0

    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    proposed_actions: list[str] = []

    for b in bindings:
        if not isinstance(b, dict):
            findings.append({
                "kind": "invalid_binding",
                "repo": "",
                "severity": "medium",
                "detail": "binding element is not a mapping",
            })
            continue

        plugin_id = b.get("plugin_id")
        repo = b.get("repo")
        marketplace_repo = b.get("marketplace_repo")
        marketplace_file = b.get("marketplace_file")

        if not (
            isinstance(plugin_id, str) and plugin_id and
            isinstance(repo, str) and repo and
            isinstance(marketplace_repo, str) and marketplace_repo and
            isinstance(marketplace_file, str) and marketplace_file
        ):
            findings.append({
                "kind": "invalid_binding",
                "repo": str(repo or ""),
                "severity": "medium",
                "detail": f"malformed binding locator for plugin_id {plugin_id!r}",
            })
            continue

        bindings_scanned += 1

        releases = releases_by_repo.get(repo)
        if isinstance(releases, Exception) or (releases is None and repo in releases_by_repo):
            findings.append({
                "kind": "unreadable_release_list",
                "repo": repo,
                "severity": "medium",
                "detail": f"Could not fetch releases for {repo}",
            })
            releases = []

        doc_key = f"{marketplace_repo}/{marketplace_file}"
        doc = docs_by_repo.get(doc_key)
        if doc is None and doc_key not in docs_by_repo:
            doc = docs_by_repo.get(marketplace_repo)
            lookup_key = marketplace_repo if marketplace_repo in docs_by_repo else doc_key
        else:
            lookup_key = doc_key

        if isinstance(doc, Exception) or (doc is None and lookup_key in docs_by_repo):
            findings.append({
                "kind": "unreadable_marketplace_file",
                "repo": marketplace_repo,
                "severity": "medium",
                "detail": f"Could not fetch marketplace document for {marketplace_repo}",
            })
            doc = None

        drift = compare(b, releases, doc)

        if drift.outcome == OUTCOME_NOT_APPLICABLE:
            not_applicable_count += 1
        elif drift.outcome == OUTCOME_UNKNOWN:
            unknown_count += 1
            kind = "no_stable_release" if (drift.reason and "stable" in drift.reason) else "unknown_marketplace_doc"
            findings.append({
                "kind": kind,
                "repo": marketplace_repo,
                "severity": "medium",
                "detail": drift.reason or "unknown drift outcome",
            })
        elif drift.outcome == OUTCOME_IN_SYNC:
            in_sync_count += 1
        elif drift.outcome in _PROPOSABLE_OUTCOMES:
            if drift.outcome == OUTCOME_DRIFT:
                drift_count += 1
            else:
                missing_entry_count += 1

            head_sha = head_shas.get(marketplace_repo)
            if not isinstance(head_sha, str) or not head_sha:
                findings.append({
                    "kind": "unreadable_head",
                    "repo": marketplace_repo,
                    "severity": "high",
                    "detail": f"Could not resolve HEAD SHA for {marketplace_repo}",
                })
                continue

            try:
                prop = build_marketplace_proposal(drift, head_sha, actor_dict, registry=registry)
                proposals.append({
                    "binding": plugin_id,
                    "transformation": prop.transformation,
                    "proposal_id": prop.id,
                })
                proposed_actions.append(
                    f"propose marketplace entry update for {plugin_id} to {drift.target_version}"
                )
            except mutation_plan.MutationPlanError as exc:
                findings.append({
                    "kind": "gated_transformation",
                    "repo": marketplace_repo,
                    "severity": "medium",
                    "detail": str(exc),
                })
                proposed_actions.append(
                    f"propose marketplace entry update for {plugin_id} to {drift.target_version}"
                )

    return {
        "contract_version": 1,
        "kind": "marketplace-sync",
        "workspace": ws,
        "run_at": ts,
        "actor": actor_dict,
        "bindings_scanned": bindings_scanned,
        "in_sync": in_sync_count,
        "drift": drift_count,
        "missing_entry": missing_entry_count,
        "unknown": unknown_count,
        "not_applicable": not_applicable_count,
        "findings": findings,
        "proposals": proposals,
        "proposed_actions": proposed_actions,
        "errors": [],
    }
