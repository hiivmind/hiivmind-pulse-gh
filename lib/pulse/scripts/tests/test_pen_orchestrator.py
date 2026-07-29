"""Tests for the pen mutation orchestrator state machine."""

import dataclasses

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


def make_proposal(selection=("acme/api", "acme/web"), mutation_policy="propose", bound_paths=None):
    return mutation_plan.build_proposal(
        id="run-1",
        selection=list(selection),
        transformation="format-python",
        expected_shas={repo: "deadbeef" for repo in selection},
        actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
        mutation_policy=mutation_policy,
        bound_paths=bound_paths,
    )


def make_plan(selection=("acme/api", "acme/web"), mutation_policy="propose", request_push=False, validation=None, bound_paths=None):
    proposal = make_proposal(selection=selection, mutation_policy=mutation_policy, bound_paths=bound_paths)
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


def matching_head(repo):
    """`read_repo_head` stub returning the SHA `make_proposal` bakes into
    every `expected_shas` entry ("deadbeef") — used by tests that must
    clear the expected-SHA guard to reach exec/validation."""
    return "deadbeef"


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


# --- expected-SHA guard (stale-base block) ---------------------------------


def _clean_preflight_sequence():
    return [
        *create_sequence(REPOS),
        pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
    ]


def test_expected_shas_with_no_reader_blocks_with_explicit_message():
    plan = make_plan()
    runner = QueuedRunner(_clean_preflight_sequence())

    result = pen_orchestrator.execute(plan, runner)

    assert result.state == "blocked"
    assert "read_repo_head" in result.reason
    assert "expected-SHA" in result.reason
    assert result.repo_outcomes == {repo: "blocked" for repo in SELECTION}
    # Exec must never be reached: only create (2 calls) + status (1 call).
    assert len(runner.calls) == 3
    assert not any("exec" in call for call in runner.calls)


def test_expected_shas_all_matching_proceeds_to_proposed():
    plan = make_plan()
    runner = QueuedRunner(
        [
            *_clean_preflight_sequence(),
            nave_adapter.Completed(0, "ran ok", ""),
            pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
        ]
    )

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

    assert result.state == "proposed"
    assert result.repo_outcomes == {repo: "ok" for repo in SELECTION}


def test_expected_shas_one_mismatch_blocks_before_exec_with_attribution():
    plan = make_plan()
    runner = QueuedRunner(_clean_preflight_sequence())

    def read_repo_head(repo):
        if repo == "acme/api":
            return "deadbeef"
        return "0000000"  # acme/web: does not match expected "deadbeef"

    result = pen_orchestrator.execute(plan, runner, read_repo_head=read_repo_head)

    assert result.state == "blocked"
    assert result.repo_outcomes == {"acme/api": "ok", "acme/web": "blocked"}
    assert "acme/web" in result.reason
    assert "deadbeef" in result.reason
    assert "acme/api" not in result.reason
    # Exec must never be reached: only create (2 calls) + status (1 call).
    assert len(runner.calls) == 3
    assert not any("exec" in call for call in runner.calls)


def test_expected_shas_reader_raising_for_a_repo_blocks_with_attribution():
    plan = make_plan()
    runner = QueuedRunner(_clean_preflight_sequence())

    def read_repo_head(repo):
        if repo == "acme/api":
            return "deadbeef"
        raise FileNotFoundError(f"no checkout for {repo}")

    result = pen_orchestrator.execute(plan, runner, read_repo_head=read_repo_head)

    assert result.state == "blocked"
    assert result.repo_outcomes == {"acme/api": "ok", "acme/web": "blocked"}
    assert "acme/web" in result.reason
    assert "no checkout" in result.reason
    assert len(runner.calls) == 3
    assert not any("exec" in call for call in runner.calls)


def test_expected_shas_missing_entry_for_selected_repo_blocks_before_exec():
    # A hand-built Proposal (bypassing build_proposal's coverage check) with
    # a selected repo absent from expected_shas must block, not skip the
    # guard for that repo — an unguarded repo is exactly the stale-base
    # mutation the guard exists to prevent.
    plan = make_plan()
    partial = dataclasses.replace(
        plan.proposal, expected_shas={"acme/api": "deadbeef"}
    )
    plan = dataclasses.replace(plan, proposal=partial)
    runner = QueuedRunner(_clean_preflight_sequence())

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

    assert result.state == "blocked"
    assert result.repo_outcomes == {"acme/api": "ok", "acme/web": "blocked"}
    assert "no expected_shas entry" in result.reason
    assert len(runner.calls) == 3
    assert not any("exec" in call for call in runner.calls)


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

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

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

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

    assert result.state == "failed"
    assert "json_schema" in result.reason
    assert "package-lock.json" in result.reason
    assert result.repo_outcomes == {repo: "failed" for repo in SELECTION}


# --- schema validation with an injected reader -----------------------------


def _json_schema_plan():
    return make_plan(
        validation={
            "kind": "json_schema",
            "path": "package-lock.json",
            "schema": {"type": "object", "required": ["lockfileVersion"]},
        }
    )


def _exec_ok_sequence():
    return [
        *create_sequence(REPOS),
        pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
        nave_adapter.Completed(0, "ran ok", ""),
        pen_status_completed([repo_state("acme", "api"), repo_state("acme", "web")]),
    ]


def test_json_schema_with_reader_and_valid_file_proceeds_to_proposed():
    plan = _json_schema_plan()
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_file(repo, path):
        assert path == "package-lock.json"
        return b'{"lockfileVersion": 3}'

    result = pen_orchestrator.execute(
        plan, runner, read_repo_file=read_repo_file, read_repo_head=matching_head
    )

    assert result.state == "proposed"
    assert result.reason is None
    assert result.repo_outcomes == {repo: "ok" for repo in SELECTION}


def test_json_schema_with_reader_and_invalid_file_fails_with_per_repo_attribution():
    plan = _json_schema_plan()
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_file(repo, path):
        if repo == "acme/api":
            return b'{"lockfileVersion": 3}'
        return b"{}"  # acme/web: missing required lockfileVersion

    result = pen_orchestrator.execute(
        plan, runner, read_repo_file=read_repo_file, read_repo_head=matching_head
    )

    assert result.state == "failed"
    assert result.repo_outcomes == {"acme/api": "ok", "acme/web": "failed"}
    assert "acme/web" in result.reason
    assert "lockfileVersion" in result.reason
    assert "acme/api" not in result.reason


def test_json_schema_with_reader_and_missing_file_fails():
    plan = _json_schema_plan()
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_file(repo, path):
        raise FileNotFoundError(f"{repo}:{path} not found")

    result = pen_orchestrator.execute(
        plan, runner, read_repo_file=read_repo_file, read_repo_head=matching_head
    )

    assert result.state == "failed"
    assert result.repo_outcomes == {repo: "failed" for repo in SELECTION}
    assert "not found" in result.reason


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

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

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

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

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


# --- paths_changed validation kind ----------------------------------------


def _paths_changed_plan(bound_paths=None):
    if bound_paths is None:
        bound_paths = {repo: ("docs/a.md",) for repo in SELECTION}
    return make_plan(
        validation={"kind": "paths_changed"},
        bound_paths=bound_paths,
    )


def test_paths_changed_without_reader_fails_closed_as_blocked():
    plan = _paths_changed_plan()
    runner = QueuedRunner(_exec_ok_sequence())

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

    assert result.state == "blocked"
    assert "paths_changed" in result.reason
    assert "read_repo_changed_paths" in result.reason
    assert result.repo_outcomes == {repo: "blocked" for repo in SELECTION}


def test_paths_changed_exact_and_glob_match_passes():
    bound_paths = {
        "acme/api": ("docs/a.md", ".generated/docs/**"),
        "acme/web": (".generated/docs/**",),
    }
    plan = _paths_changed_plan(bound_paths=bound_paths)
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_changed_paths(repo):
        if repo == "acme/api":
            return ("docs/a.md", ".generated/docs/sub/page.html")
        return (".generated/docs/index.html",)

    result = pen_orchestrator.execute(
        plan,
        runner,
        read_repo_head=matching_head,
        read_repo_changed_paths=read_repo_changed_paths,
    )

    assert result.state == "proposed"
    assert result.reason is None
    assert result.repo_outcomes == {repo: "ok" for repo in SELECTION}


def test_paths_changed_glob_matches_deep_subdirectories():
    # Explicitly prove .generated/docs/sub/page.html matches .generated/docs/**
    bound_paths = {repo: (".generated/docs/**",) for repo in SELECTION}
    plan = _paths_changed_plan(bound_paths=bound_paths)
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_changed_paths(repo):
        return (".generated/docs/sub/page.html",)

    result = pen_orchestrator.execute(
        plan,
        runner,
        read_repo_head=matching_head,
        read_repo_changed_paths=read_repo_changed_paths,
    )

    assert result.state == "proposed"
    assert result.repo_outcomes == {repo: "ok" for repo in SELECTION}


def test_paths_changed_fails_on_out_of_allowlist_change():
    bound_paths = {repo: ("docs/a.md",) for repo in SELECTION}
    plan = _paths_changed_plan(bound_paths=bound_paths)
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_changed_paths(repo):
        if repo == "acme/api":
            return ("docs/a.md", "src/secret.py")
        return ("docs/a.md",)

    result = pen_orchestrator.execute(
        plan,
        runner,
        read_repo_head=matching_head,
        read_repo_changed_paths=read_repo_changed_paths,
    )

    assert result.state == "failed"
    assert result.repo_outcomes == {"acme/api": "failed", "acme/web": "ok"}
    assert "acme/api" in result.reason
    assert "src/secret.py" in result.reason


def test_paths_changed_fails_on_missing_exact_path():
    bound_paths = {repo: ("docs/a.md", "docs/b.md") for repo in SELECTION}
    plan = _paths_changed_plan(bound_paths=bound_paths)
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_changed_paths(repo):
        if repo == "acme/api":
            return ("docs/a.md",)  # missing exact docs/b.md
        return ("docs/a.md", "docs/b.md")

    result = pen_orchestrator.execute(
        plan,
        runner,
        read_repo_head=matching_head,
        read_repo_changed_paths=read_repo_changed_paths,
    )

    assert result.state == "failed"
    assert result.repo_outcomes == {"acme/api": "failed", "acme/web": "ok"}
    assert "acme/api" in result.reason
    assert "docs/b.md" in result.reason


def test_paths_changed_fails_on_silent_noop():
    bound_paths = {repo: ("docs/**",) for repo in SELECTION}
    plan = _paths_changed_plan(bound_paths=bound_paths)
    runner = QueuedRunner(_exec_ok_sequence())

    def read_repo_changed_paths(repo):
        if repo == "acme/api":
            return ()  # silent no-op
        return ("docs/a.md",)

    result = pen_orchestrator.execute(
        plan,
        runner,
        read_repo_head=matching_head,
        read_repo_changed_paths=read_repo_changed_paths,
    )

    assert result.state == "failed"
    assert result.repo_outcomes == {"acme/api": "failed", "acme/web": "ok"}
    assert "acme/api" in result.reason
    assert "no paths changed" in result.reason or "no-op" in result.reason


def test_paths_changed_on_neutral_transformation_fixture():
    # Prove the guard on a neutral transformation entry (`regenerate-docs-index`)
    neutral_registry_data = {
        "transformations": {
            "regenerate-docs-index": {
                "id": "regenerate-docs-index",
                "command_argv": ["mkdocs", "build", "--site-dir", ".generated/docs"],
                "applies_to": ["evidence_path:mkdocs.yml"],
                "validation": {"kind": "paths_changed"},
                "allow_scheduled": True,
            }
        }
    }
    registry = mutation_plan.load_registry(neutral_registry_data)
    entry = registry.get("regenerate-docs-index")
    proposal = mutation_plan.build_proposal(
        id="run-neutral",
        selection=["acme/api"],
        transformation="regenerate-docs-index",
        expected_shas={"acme/api": "deadbeef"},
        actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
        bound_paths={"acme/api": [".generated/docs/**"]},
        registry=registry,
    )
    plan = pen_orchestrator.PenPlan(
        proposal=proposal,
        entry=entry,
        pen_name="nave/docs-gen",
        query=nave_adapter.PenQuery(),
    )
    runner = QueuedRunner(
        [
            *create_sequence([("acme", "api")]),
            pen_status_completed([repo_state("acme", "api")]),
            nave_adapter.Completed(0, "built docs", ""),
            pen_status_completed([repo_state("acme", "api")]),
        ]
    )

    def read_repo_changed_paths(repo):
        return (".generated/docs/index.html", ".generated/docs/search/search_index.json")

    result = pen_orchestrator.execute(
        plan,
        runner,
        read_repo_head=lambda repo: "deadbeef",
        read_repo_changed_paths=read_repo_changed_paths,
    )

    assert result.state == "proposed"
    assert result.repo_outcomes == {"acme/api": "ok"}

