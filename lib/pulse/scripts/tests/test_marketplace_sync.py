"""Tests for the marketplace entry version drift decision + proposal builder.

Pure module (`lib.pulse.scripts.marketplace_sync`) is the unit under test.
The single integration test reuses the `test_pen_orchestrator` harness
idiom (re-implemented locally to keep the test file self-contained, the
same pattern `test_plan_sync.py` already uses) to prove the marketplace
proposal is guard-compatible end to end — the expected-SHA guard blocks
the run when the marketplace repo's HEAD has moved past the proposal's
recorded `expected_shas`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.pulse.scripts import (
    marketplace_sync,
    mutation_plan,
    nave_adapter,
    pen_orchestrator,
)


# Stub nave_adapter.probe: it issues several `--help`/`--version` calls of
# its own (see nave_adapter.probe docstring) — noise unrelated to what this
# test's QueuedRunner sequence is checking. Mirrors the autouse fixture
# `test_pen_orchestrator.py` uses; the test that exercises the guard
# already has a queue sized for the *post-probe* pen state machine.
@pytest.fixture(autouse=True)
def _stub_probe(monkeypatch):
    def fake_probe(_runner):
        return {"available": True, "version": "0.0.8", "protocol": 1}

    monkeypatch.setattr(pen_orchestrator.nave_adapter, "probe", fake_probe)


# Paths -----------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[4]  # tests/ -> scripts/ -> pulse/ -> lib/ -> repo root
TEMPLATE_PATH = REPO_ROOT / "templates" / "transformations.yaml.template"


# Fixtures --------------------------------------------------------------


PLUGIN_ID = "hiivmind-pulse-gh"
PLUGIN_REPO = "hiivmind/hiivmind-pulse-gh"
MARKETPLACE_REPO = "hiivmind/claude-marketplace"
MARKETPLACE_FILE = ".claude-plugin/marketplace.json"
ACTOR = {"gh_login": "octocat", "machine": "laptop", "mode": "interactive"}


def binding(
    plugin_id: str = PLUGIN_ID,
    marketplace_repo: str = MARKETPLACE_REPO,
    marketplace_file: str = MARKETPLACE_FILE,
):
    return {
        "plugin_id": plugin_id,
        "repo": PLUGIN_REPO,
        "marketplace_repo": marketplace_repo,
        "marketplace_file": marketplace_file,
    }


def marketplace_doc(plugin_id: str, version):
    return {
        "name": "hiivmind",
        "owner": {"name": "Discrete Data Systems"},
        "repository": "https://github.com/hiivmind/hiivmind",
        "metadata": {"version": "1.0.0"},
        "plugins": [
            {
                "name": plugin_id,
                "source": "./",
                "description": "...",
                "version": version,
                "keywords": ["github"],
            }
        ],
    }


# --- compare(): release-selection / exclusion logic ---------------------


def test_compare_drift_when_recorded_version_is_older_than_newest_stable():
    b = binding()
    releases = [
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False},
        {"tagName": "v1.5.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "drift"
    assert drift.plugin_id == PLUGIN_ID
    assert drift.marketplace_repo == MARKETPLACE_REPO
    assert drift.marketplace_file == MARKETPLACE_FILE
    assert drift.current_version == "1.5.0"
    assert drift.target_version == "v2.0.0"


def test_compare_excludes_prerelease_and_draft_releases():
    """A newer prerelease/draft present but the newest STABLE is older → excluded correctly."""
    b = binding()
    releases = [
        {"tagName": "v3.0.0-rc.1", "isPrerelease": True, "isDraft": False},
        {"tagName": "v2.5.0-rc.2", "isPrerelease": True, "isDraft": False},
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False},
        {"tagName": "v1.5.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "drift"
    assert drift.current_version == "1.5.0"
    assert drift.target_version == "v2.0.0"


def test_compare_excludes_draft_only_release_when_no_stable_present():
    b = binding()
    releases = [
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": True},
        {"tagName": "v1.5.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "drift"
    assert drift.target_version == "v1.5.0"


def test_compare_skips_non_mapping_release_entries():
    """A non-mapping entry (e.g. None, str) is silently skipped, not a failure."""
    b = binding()
    releases = [
        None,
        "garbage",
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False},
        {"tagName": "v1.5.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.target_version == "v2.0.0"


def test_compare_treats_missing_or_non_bool_flags_as_excluded_defensively():
    """Defensive: a missing/non-bool `isPrerelease`/`isDraft` is treated as
    excluded. Only an explicit `False` lets a release through as a stable
    candidate. A release whose flags are `None` (the most common "unknown"
    shape) must NOT silently become the newest stable release."""
    b = binding()
    releases = [
        # isPrerelease=None — treated as excluded (defensive against
        # misrelease of a release that lacks the flag).
        {"tagName": "v2.0.0", "isPrerelease": None, "isDraft": False},
        {"tagName": "v1.5.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "v1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "in_sync"
    assert drift.target_version == "v1.5.0"


def test_compare_treats_non_bool_truthy_flags_as_excluded():
    """Defensive: a non-bool truthy value (e.g. the string "true") is also
    treated as excluded — only the literal `False` is "not excluded"."""
    b = binding()
    releases = [
        {"tagName": "v2.0.0", "isPrerelease": "true", "isDraft": False},
        {"tagName": "v1.5.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "v1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.target_version == "v1.5.0"


# --- compare(): not_applicable / missing_entry / unknown / in_sync ------


def test_compare_binding_none_returns_not_applicable():
    drift = marketplace_sync.compare(None, [], {})

    assert drift.outcome == "not_applicable"
    assert drift.current_version is None
    assert drift.target_version is None


def test_compare_missing_entry_when_plugin_id_not_in_plugins():
    b = binding(plugin_id="not-registered")
    releases = [
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "missing_entry"
    assert drift.current_version is None
    assert drift.target_version == "v2.0.0"


def test_compare_unknown_when_no_stable_release_present():
    b = binding()
    releases = [
        {"tagName": "v3.0.0-rc.1", "isPrerelease": True, "isDraft": False},
        {"tagName": "v2.5.0-rc.1", "isPrerelease": True, "isDraft": True},
    ]
    doc = marketplace_doc(PLUGIN_ID, "1.5.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "unknown"
    assert drift.current_version is None
    assert drift.target_version is None
    assert drift.reason is not None
    assert "stable" in drift.reason


def test_compare_unknown_when_marketplace_doc_is_not_a_mapping():
    b = binding()
    releases = [
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False},
    ]

    drift = marketplace_sync.compare(b, releases, [])

    assert drift.outcome == "unknown"
    assert drift.current_version is None
    # The newest stable tag is still observed (the doc is the unparseable side).
    assert drift.target_version == "v2.0.0"
    assert drift.reason is not None


def test_compare_unknown_when_marketplace_doc_plugins_not_a_list():
    b = binding()
    releases = [
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = {"name": "hiivmind", "plugins": "not a list"}

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "unknown"
    assert drift.reason is not None


def test_compare_in_sync_when_recorded_equals_newest_stable():
    b = binding()
    releases = [
        {"tagName": "v2.0.0", "isPrerelease": False, "isDraft": False},
        {"tagName": "v1.5.0", "isPrerelease": False, "isDraft": False},
    ]
    doc = marketplace_doc(PLUGIN_ID, "v2.0.0")

    drift = marketplace_sync.compare(b, releases, doc)

    assert drift.outcome == "in_sync"
    assert drift.current_version == "v2.0.0"
    assert drift.target_version == "v2.0.0"


# --- build_marketplace_proposal ----------------------------------------


def _drift_drift():
    return marketplace_sync.MarketplaceDrift(
        outcome="drift",
        plugin_id=PLUGIN_ID,
        marketplace_repo=MARKETPLACE_REPO,
        marketplace_file=MARKETPLACE_FILE,
        current_version="1.5.0",
        target_version="v2.0.0",
    )


def _drift_missing():
    return marketplace_sync.MarketplaceDrift(
        outcome="missing_entry",
        plugin_id=PLUGIN_ID,
        marketplace_repo=MARKETPLACE_REPO,
        marketplace_file=MARKETPLACE_FILE,
        current_version=None,
        target_version="v2.0.0",
    )


def test_build_marketplace_proposal_for_drift_outcome_builds_expected_sha_guarded_proposal():
    drift = _drift_drift()
    head_sha = "deadbeef0001"

    proposal = marketplace_sync.build_marketplace_proposal(drift, head_sha, ACTOR)

    assert proposal.id == f"marketplace-{PLUGIN_ID}"
    assert proposal.selection == (MARKETPLACE_REPO,)
    assert proposal.transformation == "marketplace-entry-update"
    assert proposal.expected_shas == {MARKETPLACE_REPO: head_sha}
    assert proposal.mutation_policy == "propose"
    assert proposal.actor.gh_login == "octocat"
    assert proposal.actor.mode == "interactive"


def test_build_marketplace_proposal_for_missing_entry_outcome_builds_proposal():
    proposal = marketplace_sync.build_marketplace_proposal(
        _drift_missing(), "cafef00d", ACTOR
    )

    assert proposal.selection == (MARKETPLACE_REPO,)
    assert proposal.transformation == "marketplace-entry-update"
    assert proposal.expected_shas == {MARKETPLACE_REPO: "cafef00d"}


def test_build_marketplace_proposal_raises_for_in_sync_outcome():
    drift = marketplace_sync.MarketplaceDrift(
        outcome="in_sync",
        plugin_id=PLUGIN_ID,
        marketplace_repo=MARKETPLACE_REPO,
        marketplace_file=MARKETPLACE_FILE,
        current_version="v2.0.0",
        target_version="v2.0.0",
    )
    with pytest.raises(ValueError, match="drift or missing_entry"):
        marketplace_sync.build_marketplace_proposal(drift, "deadbeef", ACTOR)


def test_build_marketplace_proposal_raises_for_not_applicable_outcome():
    drift = marketplace_sync.MarketplaceDrift(
        outcome="not_applicable",
        plugin_id=PLUGIN_ID,
        marketplace_repo=MARKETPLACE_REPO,
        marketplace_file=MARKETPLACE_FILE,
        current_version=None,
        target_version=None,
    )
    with pytest.raises(ValueError):
        marketplace_sync.build_marketplace_proposal(drift, "deadbeef", ACTOR)


def test_build_marketplace_proposal_raises_for_unknown_outcome():
    drift = marketplace_sync.MarketplaceDrift(
        outcome="unknown",
        plugin_id=PLUGIN_ID,
        marketplace_repo=MARKETPLACE_REPO,
        marketplace_file=MARKETPLACE_FILE,
        current_version=None,
        target_version=None,
    )
    with pytest.raises(ValueError):
        marketplace_sync.build_marketplace_proposal(drift, "deadbeef", ACTOR)


# --- registry gate: transformation loads + scheduled-mode rejection -----


def test_registry_loads_marketplace_entry_update_from_template():
    registry = mutation_plan.load_registry(TEMPLATE_PATH)

    entry = registry.get("marketplace-entry-update")

    assert entry.id == "marketplace-entry-update"
    assert entry.allow_scheduled is False
    assert entry.validation.kind == "none"
    # Profile-gating mirrors plan-sync-doc-patch's `always`/`profile:claude-plugin`
    # contract. marketplace-entry-update is profile:claude-plugin per the brief.
    assert "profile:claude-plugin" in entry.applies_to


def test_build_marketplace_proposal_with_registry_succeeds_for_interactive_actor():
    registry = mutation_plan.load_registry(TEMPLATE_PATH)

    proposal = marketplace_sync.build_marketplace_proposal(
        _drift_drift(), "deadbeef", ACTOR, registry=registry
    )

    assert proposal.transformation == "marketplace-entry-update"


def test_build_marketplace_proposal_with_registry_rejects_scheduled_actor():
    registry = mutation_plan.load_registry(TEMPLATE_PATH)
    scheduled_actor = dict(ACTOR, mode="scheduled")

    with pytest.raises(
        mutation_plan.MutationPlanError, match="not allowed in scheduled mode"
    ):
        marketplace_sync.build_marketplace_proposal(
            _drift_drift(), "deadbeef", scheduled_actor, registry=registry
        )


def test_validate_proposal_rejects_scheduled_for_marketplace_entry_update():
    """A scheduled actor's proposal built without a registry must still be rejected
    by `validate_proposal` against the loaded registry."""
    registry = mutation_plan.load_registry(TEMPLATE_PATH)
    scheduled_actor = dict(ACTOR, mode="scheduled")

    proposal = marketplace_sync.build_marketplace_proposal(
        _drift_drift(), "deadbeef", scheduled_actor
    )

    with pytest.raises(
        mutation_plan.MutationPlanError, match="not allowed in scheduled mode"
    ):
        mutation_plan.validate_proposal(proposal, registry)


# --- one guard integration test ----------------------------------------


class _QueuedRunner:
    """Mirror of `test_pen_orchestrator.QueuedRunner`: returns a distinct
    Completed per call, in order."""

    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def run(self, args):
        self.calls.append(list(args))
        return self._results.pop(0)


def _pen_show_completed(repos):
    payload = {
        "name": "nave/marketplace-audit",
        "created_at": "2026-07-22T00:00:00Z",
        "branch": "nave/marketplace-audit",
        "filter": {"terms": []},
        "repos": [
            {
                "owner": o,
                "name": n,
                "default_branch": "main",
                "clone_url": "x",
                "synced_at": "2026-07-22T00:00:00Z",
            }
            for o, n in repos
        ],
        "ops": [],
    }
    return nave_adapter.Completed(0, json.dumps(payload), "")


def _pen_status_completed(entries):
    return nave_adapter.Completed(0, json.dumps(entries), "")


def _repo_state(owner, name, **overrides):
    state = {
        "owner": owner,
        "repo": name,
        "working_tree": "clean",
        "freshness": "fresh",
        "run_state": "not-run",
        "divergence": "up-to-date",
        "ahead": 0,
        "behind": 0,
    }
    state.update(overrides)
    return state


def _marketplace_repos():
    return [(MARKETPLACE_REPO.split("/")[0], MARKETPLACE_REPO.split("/")[1])]


def test_marketplace_drift_proposal_is_blocked_by_stale_head_sha():
    """End-to-end guard integration: a marketplace drift proposal whose
    `expected_shas` no longer matches the marketplace repo's current HEAD
    is blocked before any exec by the F6 expected-SHA guard."""
    import json as _json  # noqa: F401  # used by helper functions

    from lib.pulse.scripts.pen_orchestrator import nave_adapter as _na

    registry = mutation_plan.load_registry(TEMPLATE_PATH)

    drift = marketplace_sync.MarketplaceDrift(
        outcome="drift",
        plugin_id=PLUGIN_ID,
        marketplace_repo=MARKETPLACE_REPO,
        marketplace_file=MARKETPLACE_FILE,
        current_version="1.5.0",
        target_version="v2.0.0",
    )
    head_sha_at_proposal = "expected_sha_xxx"
    proposal = marketplace_sync.build_marketplace_proposal(
        drift, head_sha_at_proposal, ACTOR, registry=registry
    )
    entry = registry.get("marketplace-entry-update")

    plan = pen_orchestrator.PenPlan(
        proposal=proposal,
        entry=entry,
        pen_name="nave/marketplace-audit",
        query=nave_adapter.PenQuery(terms=[]),
    )

    repos = _marketplace_repos()
    runner = _QueuedRunner(
        [
            nave_adapter.Completed(0, "created\n", ""),
            _pen_show_completed(repos),
            _pen_status_completed([_repo_state(*repos[0])]),
        ]
    )

    def read_repo_head(_repo):
        # Marketplace repo's HEAD has moved past the proposal's recorded SHA.
        return "different_current_sha_yyy"

    result = pen_orchestrator.execute(plan, runner, read_repo_head=read_repo_head)

    assert result.state == "blocked"
    assert result.repo_outcomes == {MARKETPLACE_REPO: "blocked"}
    assert "expected SHA" in result.reason
    # Exec must never be reached: only create (2 calls) + status (1 call).
    assert len(runner.calls) == 3
    assert not any("exec" in call for call in runner.calls)
