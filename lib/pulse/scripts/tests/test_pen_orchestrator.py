"""Tests for the pen mutation orchestrator state machine."""

import pytest

from lib.pulse.scripts import mutation_plan, nave_adapter, pen_orchestrator


@pytest.fixture(autouse=True)
def _stub_probe(monkeypatch):
    """`nave_adapter.probe` issues several `--help`/`--version` calls of its
    own (version, help, `pen --help`, per-action `--help` probes) — noise
    unrelated to what any given test's `QueuedRunner` sequence is checking.
    Stub it to a fixed, cheap response by default; the one test that cares
    about the probed version overrides this with its own monkeypatch."""

    def fake_probe(_runner):
        return {"available": True, "version": "0.0.8", "protocol": 1}

    monkeypatch.setattr(pen_orchestrator.nave_adapter, "probe", fake_probe)


class QueuedRunner:
    """Fake runner that returns a distinct Completed per call, in order.

    Mirrors the `QueuedRunner` idiom `test_nave_adapter.py` already
    establishes for multi-call sequences.
    """

    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def run(self, args):
        self.calls.append(args)
        return self._results.pop(0)


class NoCallRunner:
    """Fake runner that fails the test if `.run` is ever invoked — used to
    prove a gate short-circuits before any Nave interaction."""

    def run(self, args):  # pragma: no cover - should never be called
        raise AssertionError(f"runner.run() called unexpectedly with {args}")


def registry_data(validation=None):
    return {
        "transformations": {
            "format-python": {
                "id": "format-python",
                "command_argv": ["ruff", "format", "."],
                "applies_to": ["always"],
                "validation": validation or {"kind": "none"},
                "allow_scheduled": True,
            }
        }
    }


def make_entry(validation=None):
    registry = mutation_plan.load_registry(registry_data(validation))
    return registry.get("format-python")


def make_proposal(selection=("acme/api", "acme/web"), mutation_policy="propose"):
    return mutation_plan.build_proposal(
        id="run-1",
        selection=list(selection),
        transformation="format-python",
        expected_shas={repo: "deadbeef" for repo in selection},
        actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
        mutation_policy=mutation_policy,
    )


def make_plan(selection=("acme/api", "acme/web"), mutation_policy="propose", request_push=False, validation=None):
    proposal = make_proposal(selection=selection, mutation_policy=mutation_policy)
    entry = make_entry(validation=validation)
    return pen_orchestrator.PenPlan(
        proposal=proposal,
        entry=entry,
        pen_name="nave/api-audit",
        query=nave_adapter.PenQuery(terms=["workflow:pytest"]),
        request_push=request_push,
    )


def pen_show_completed(repos):
    import json

    payload = {
        "name": "nave/api-audit",
        "created_at": "2026-07-15T10:00:00Z",
        "branch": "nave/api-audit",
        "filter": {"terms": []},
        "repos": [{"owner": o, "name": n, "default_branch": "main", "clone_url": "x", "synced_at": "2026-07-15T10:00:00Z"} for o, n in repos],
        "ops": [],
    }
    return nave_adapter.Completed(0, json.dumps(payload), "")


def pen_status_completed(entries):
    import json

    return nave_adapter.Completed(0, json.dumps(entries), "")


def repo_state(owner, repo, working_tree="clean", freshness="fresh", run_state="not-run", divergence="up-to-date", ahead=0, behind=0):
    return {
        "owner": owner,
        "repo": repo,
        "working_tree": working_tree,
        "freshness": freshness,
        "run_state": run_state,
        "divergence": divergence,
        "ahead": ahead,
        "behind": behind,
    }


def create_sequence(repos, extra=()):
    """Build the Completed queue for pen_create's two calls (create, show)."""
    return [
        nave_adapter.Completed(0, "created\n", ""),
        pen_show_completed(repos),
        *extra,
    ]


REPOS = [("acme", "api"), ("acme", "web")]
SELECTION = ("acme/api", "acme/web")


# --- forbidden push -----------------------------------------------------


def test_forbidden_push_via_explicit_request_blocks_before_any_nave_call():
    plan = make_plan(request_push=True)

    result = pen_orchestrator.execute(plan, NoCallRunner())

    assert result.state == "blocked"
    assert "forbidden" in result.reason
    assert result.repo_outcomes == {repo: "blocked" for repo in SELECTION}


def test_forbidden_push_via_non_propose_policy_blocks_before_any_nave_call():
    plan = make_plan(mutation_policy="allow")

    result = pen_orchestrator.execute(plan, NoCallRunner())

    assert result.state == "blocked"
    assert "forbidden" in result.reason


# --- stale pen ------------------------------------------------------------


def test_stale_pen_blocks_before_exec():
    plan = make_plan()
    runner = QueuedRunner(
        [
            *create_sequence(REPOS),
            pen_status_completed(
                [
                    repo_state("acme", "api"),
                    repo_state("acme", "web", freshness="stale", divergence="behind", behind=2),
                ]
            ),
        ]
    )

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "blocked"
    assert "stale" in result.reason
    assert result.repo_outcomes == {repo: "blocked" for repo in SELECTION}
    # Exec must never be reached: only create (2 calls) + status (1 call).
    assert len(runner.calls) == 3
    assert runner.calls[-1] == ["pen", "status", "nave/api-audit", "--json"]


# --- dirty before run -------------------------------------------------------


def test_dirty_working_tree_before_run_blocks_before_exec():
    plan = make_plan()
    runner = QueuedRunner(
        [
            *create_sequence(REPOS),
            pen_status_completed(
                [
                    repo_state("acme", "api", working_tree="dirty"),
                    repo_state("acme", "web"),
                ]
            ),
        ]
    )

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "blocked"
    assert "dirty" in result.reason
    assert result.repo_outcomes == {repo: "blocked" for repo in SELECTION}
    assert len(runner.calls) == 3


# --- command failure in one repo -------------------------------------------


def test_command_failure_fails_whole_run_and_marks_every_repo_failed():
    plan = make_plan()
    runner = QueuedRunner(
        [
            *create_sequence(REPOS),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
            nave_adapter.Completed(1, "", "exec failed in acme/web"),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
        ]
    )

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "failed"
    assert "exec failed" in result.reason
    assert result.repo_outcomes == {repo: "failed" for repo in SELECTION}
    exec_call = runner.calls[3]
    assert exec_call == [
        "pen",
        "exec",
        "nave/api-audit",
        "--",
        "ruff",
        "format",
        ".",
    ]
    assert "--push-changes" not in exec_call
    assert "--commit" not in exec_call


# --- schema validation (NEEDS_CONTEXT: fails closed, no read capability) --


def test_json_schema_validation_fails_closed_after_successful_exec():
    plan = make_plan(
        validation={
            "kind": "json_schema",
            "path": "package-lock.json",
            "schema": {"type": "object", "required": ["lockfileVersion"]},
        }
    )
    runner = QueuedRunner(
        [
            *create_sequence(REPOS),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
            nave_adapter.Completed(0, "ran ok", ""),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
        ]
    )

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "failed"
    assert "json_schema" in result.reason
    assert "package-lock.json" in result.reason
    assert result.repo_outcomes == {repo: "failed" for repo in SELECTION}


# --- propose-only success --------------------------------------------------


def test_propose_only_success_never_passes_push_or_commit_flags():
    plan = make_plan()
    runner = QueuedRunner(
        [
            *create_sequence(REPOS),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
            nave_adapter.Completed(0, "ran ok", ""),
            pen_status_completed(
                [
                    repo_state("acme", "api", working_tree="dirty"),
                    repo_state("acme", "web", working_tree="dirty"),
                ]
            ),
        ]
    )

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "proposed"
    assert result.reason is None
    assert result.repo_outcomes == {repo: "ok" for repo in SELECTION}
    assert result.pen_name == "nave/api-audit"
    assert result.proposal_id == "run-1"
    assert result.transformation == "format-python"
    assert result.selection == SELECTION
    assert result.actor.gh_login == "octocat"
    assert result.actor.machine == "laptop"
    exec_call = runner.calls[3]
    assert "--push-changes" not in exec_call
    assert "--commit" not in exec_call


def test_propose_only_success_records_probed_nave_version(monkeypatch):
    plan = make_plan()
    runner = QueuedRunner(
        [
            *create_sequence(REPOS),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
            nave_adapter.Completed(0, "ran ok", ""),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
        ]
    )

    def fake_probe(_runner):
        return {"available": True, "version": "0.0.9"}

    monkeypatch.setattr(pen_orchestrator.nave_adapter, "probe", fake_probe)

    result = pen_orchestrator.execute(plan, runner)

    assert result.nave_version == "0.0.9"
    assert result.state == "proposed"


# --- structural / safety-net checks not in the required matrix but real --


def test_entry_proposal_mismatch_raises_programmer_error():
    proposal = make_proposal()
    other_entry = mutation_plan.load_registry(
        {
            "transformations": {
                "other": {
                    "id": "other",
                    "command_argv": ["true"],
                    "applies_to": ["always"],
                    "validation": {"kind": "none"},
                    "allow_scheduled": True,
                }
            }
        }
    ).get("other")
    plan = pen_orchestrator.PenPlan(
        proposal=proposal,
        entry=other_entry,
        pen_name="nave/api-audit",
        query=nave_adapter.PenQuery(),
    )

    with pytest.raises(pen_orchestrator.PenOrchestratorError):
        pen_orchestrator.execute(plan, NoCallRunner())


def test_pen_create_failure_fails_the_run():
    plan = make_plan()
    runner = QueuedRunner([nave_adapter.Completed(1, "", "create failed")])

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "failed"
    assert "create failed" in result.reason
    assert result.repo_outcomes == {repo: "failed" for repo in SELECTION}


def test_pen_selection_mismatch_blocks_the_run():
    plan = make_plan()
    runner = QueuedRunner(create_sequence([("acme", "api")]))  # missing acme/web

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "blocked"
    assert "does not match" in result.reason or "do not match" in result.reason
    assert result.repo_outcomes == {repo: "blocked" for repo in SELECTION}
