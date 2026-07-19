"""End-to-end acceptance gate for the F6 Nave pen mutation stack.

Proves the whole pipeline end-to-end via the offline fixture-driven fake
runner (no network, no real `nave` binary): `mutation_plan.load_registry`
loads the REAL `templates/transformations.yaml.template` registry (not a
hand-built dataclass), `mutation_plan.build_proposal`/`validate_proposal`
gate a `Proposal` against it, and `pen_orchestrator.execute` drives that
proposal through the pen state machine using the injectable
`read_repo_head`/`read_repo_file` seams `pen_orchestrator.py` (F6 Task 3)
defines.

1. A two-repo pen where one repo changes and one no-ops drives a full
   propose-only run to state "proposed": no push command is ever issued,
   the resulting `PenRunResult` converts to a `repo-mutation` result that
   passes `validate_result.validate`, attribution is exact, and running
   `execute()` again with the same inputs is idempotent (equal results, no
   additional command beyond the same expected second-run set).
2. A stale remote SHA (an `expected_shas` mismatch surfaced via
   `read_repo_head`) blocks the run before `pen exec` is ever invoked, with
   per-repo attribution naming which repo is stale.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.pulse.scripts import mutation_plan, nave_adapter, pen_orchestrator, validate_result


@pytest.fixture(autouse=True)
def _stub_probe(monkeypatch):
    """`nave_adapter.probe` issues its own `--version`/`--help` calls,
    noise unrelated to the scripted `QueuedRunner` sequences below — same
    stub `test_pen_orchestrator.py` uses."""

    def fake_probe(_runner):
        return {"available": True, "version": "0.0.9", "protocol": 1}

    monkeypatch.setattr(pen_orchestrator.nave_adapter, "probe", fake_probe)


REGISTRY_PATH = Path("templates/transformations.yaml.template")
TRANSFORMATION_ID = "format-python"  # command_argv: ruff format .; validation: none
REPOS = [("acme", "api"), ("acme", "web")]
SELECTION = ("acme/api", "acme/web")
PEN_NAME = "nave/acceptance"
WORKSPACE = "acme"
RUN_AT = "2026-07-19T09:00:00Z"
EXPECTED_SHAS = {"acme/api": "deadbeef00", "acme/web": "cafef00d00"}


class QueuedRunner:
    """Fake runner returning a distinct `Completed` per call, in order —
    the same idiom `test_nave_adapter.py`/`test_pen_orchestrator.py`
    already establish for scripted multi-call sequences. No subprocess,
    no network, no real `nave` binary."""

    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def run(self, args):
        self.calls.append(args)
        return self._results.pop(0)


def _pen_show_completed(repos):
    payload = {
        "name": PEN_NAME,
        "created_at": "2026-07-19T08:00:00Z",
        "branch": PEN_NAME,
        "filter": {"terms": []},
        "repos": [
            {
                "owner": owner,
                "name": name,
                "default_branch": "main",
                "clone_url": "x",
                "synced_at": "2026-07-19T08:00:00Z",
            }
            for owner, name in repos
        ],
        "ops": [],
    }
    return nave_adapter.Completed(0, json.dumps(payload), "")


def _pen_status_completed(entries):
    return nave_adapter.Completed(0, json.dumps(entries), "")


def _repo_state(owner, repo, working_tree="clean", freshness="fresh", divergence="up-to-date"):
    return {
        "owner": owner,
        "repo": repo,
        "working_tree": working_tree,
        "freshness": freshness,
        "run_state": "not-run",
        "divergence": divergence,
        "ahead": 0,
        "behind": 0,
    }


def _create_sequence(repos):
    """`pen_create`'s two calls: `pen create`, then `pen show --json`."""
    return [
        nave_adapter.Completed(0, "created\n", ""),
        _pen_show_completed(repos),
    ]


def _clean_preflight_status():
    return _pen_status_completed([_repo_state("acme", "api"), _repo_state("acme", "web")])


def _full_success_sequence():
    """create -> preflight status (clean) -> exec (ok) -> post-exec status,
    where `acme/api` ends dirty (the transformation changed it) and
    `acme/web` ends clean (a no-op for that repo) — the "one repo changes,
    one no-ops" scenario. Both still resolve to a single aggregate "ok"
    exec outcome: `nave_pen::ops::exec_pen` has no per-repo success signal
    (see `pen_orchestrator.py`'s NEEDS_CONTEXT docstring section), so a
    per-repo diff is visible only in post-exec `working_tree`, never in
    `repo_outcomes`."""
    return [
        *_create_sequence(REPOS),
        _clean_preflight_status(),
        nave_adapter.Completed(0, "reformatted acme/api\nacme/web: no changes\n", ""),
        _pen_status_completed(
            [
                _repo_state("acme", "api", working_tree="dirty"),
                _repo_state("acme", "web", working_tree="clean"),
            ]
        ),
    ]


def matching_head(repo: str) -> str:
    return EXPECTED_SHAS[repo]


def load_transformation():
    """Load the REAL registry from `templates/transformations.yaml.template`
    via the public `mutation_plan.load_registry` API — not a hand-built
    `TransformationEntry` — so this test exercises the same registry file a
    real deployment ships."""
    registry = mutation_plan.load_registry(REGISTRY_PATH)
    return registry, registry.get(TRANSFORMATION_ID)


def build_plan(*, selection=SELECTION, expected_shas=None):
    registry, entry = load_transformation()
    proposal = mutation_plan.build_proposal(
        id="acceptance-run-1",
        selection=list(selection),
        transformation=TRANSFORMATION_ID,
        expected_shas=expected_shas if expected_shas is not None else dict(EXPECTED_SHAS),
        actor={"gh_login": "octocat", "machine": "acceptance-mba", "mode": "interactive"},
        mutation_policy="propose",
        registry=registry,
    )
    plan = pen_orchestrator.PenPlan(
        proposal=proposal,
        entry=entry,
        pen_name=PEN_NAME,
        query=nave_adapter.PenQuery(terms=["workflow:pytest"]),
    )
    return plan


def to_repo_mutation_result(result: pen_orchestrator.PenRunResult) -> dict:
    """Build a `repo-mutation` result document from a `PenRunResult` plus
    the envelope fields `lib/patterns/headless-contract.md` requires on
    every kind — exactly what a headless caller writing
    `repo-mutation-result.yaml` would assemble."""
    return {
        "contract_version": 1,
        "kind": "repo-mutation",
        "workspace": WORKSPACE,
        "run_at": RUN_AT,
        "actor": {
            "gh_login": result.actor.gh_login,
            "machine": result.actor.machine,
            "mode": result.actor.mode,
        },
        "state": result.state,
        "proposal_id": result.proposal_id,
        "transformation": result.transformation,
        "pen_name": result.pen_name,
        "selection": list(result.selection),
        "nave_version": result.nave_version,
        "repo_outcomes": dict(result.repo_outcomes),
        "reason": result.reason,
        "errors": [],
    }


def _assert_no_push_or_commit(calls):
    for call in calls:
        assert "--push-changes" not in call, call
        assert "--commit" not in call, call


# --- 1. two-repo pen, one changes / one no-ops, propose-only, idempotent ---


def test_two_repo_pen_propose_only_no_push_valid_and_attributed():
    plan = build_plan()
    runner = QueuedRunner(_full_success_sequence())

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

    # (a) no push: every command argv issued to the runner is inspected.
    assert runner.calls  # sanity: the fixture sequence was actually consumed
    _assert_no_push_or_commit(runner.calls)

    # terminal state
    assert result.state == "proposed"
    assert result.reason is None

    # (b) the result converts to a repo-mutation document that validates.
    document = to_repo_mutation_result(result)
    assert validate_result.validate(document, "repo-mutation") == []

    # (c) exact attribution.
    assert result.actor.gh_login == "octocat"
    assert result.actor.machine == "acceptance-mba"
    assert result.actor.mode == "interactive"
    assert result.pen_name == PEN_NAME
    assert result.transformation == TRANSFORMATION_ID
    assert result.selection == SELECTION
    assert result.repo_outcomes == {"acme/api": "ok", "acme/web": "ok"}


def test_two_repo_pen_propose_only_repeat_is_idempotent():
    plan = build_plan()

    runner_1 = QueuedRunner(_full_success_sequence())
    result_1 = pen_orchestrator.execute(plan, runner_1, read_repo_head=matching_head)

    runner_2 = QueuedRunner(_full_success_sequence())
    result_2 = pen_orchestrator.execute(plan, runner_2, read_repo_head=matching_head)

    # Equal PenRunResults for equal inputs.
    assert result_1 == result_2
    assert result_1.state == "proposed"

    # No additional mutating commands beyond the expected second-run set:
    # the second run issues the identical shape of calls as the first
    # (create, show, preflight status, exec, post-exec status) — never more
    # — and neither run ever pushes or commits.
    assert runner_2.calls == runner_1.calls
    _assert_no_push_or_commit(runner_1.calls)
    _assert_no_push_or_commit(runner_2.calls)


# --- 2. stale remote SHA blocks before exec ---------------------------------


def test_stale_remote_sha_blocks_before_exec_with_attribution():
    plan = build_plan()
    runner = QueuedRunner(
        [
            *_create_sequence(REPOS),
            _clean_preflight_status(),
        ]
    )

    def read_repo_head(repo: str) -> str:
        if repo == "acme/api":
            return EXPECTED_SHAS[repo]
        return "0000000000"  # acme/web: remote moved since the proposal was built

    result = pen_orchestrator.execute(plan, runner, read_repo_head=read_repo_head)

    assert result.state == "blocked"
    assert result.reason is not None
    assert "acme/web" in result.reason
    assert "acme/api" not in result.reason

    # pen exec must never be invoked once a stale SHA is detected.
    assert not any("exec" in call for call in runner.calls)
    _assert_no_push_or_commit(runner.calls)

    # per-repo attribution: the stale repo is blocked, the fresh one is ok.
    assert result.repo_outcomes == {"acme/api": "ok", "acme/web": "blocked"}

    # The result still converts to a valid (blocked) repo-mutation document.
    document = to_repo_mutation_result(result)
    assert validate_result.validate(document, "repo-mutation") == []
