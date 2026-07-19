"""Tests for generator adapter dispatch.

Task 3 registers GENERATOR adapters and routes a drifted generated-artifact
binding into an F6 Nave mutation `Proposal`.
"""

from __future__ import annotations

import json

import pytest

from lib.pulse.scripts import generator_dispatch, mutation_plan, nave_adapter, pen_orchestrator
from lib.pulse.scripts.profile_dispatch import RepositoryProfile


@pytest.fixture
def registry():
    return mutation_plan.load_registry(
        {
            "transformations": {
                "regenerate-from-template": {
                    "id": "regenerate-from-template",
                    "command_argv": ["nave", "generate", "--from-template"],
                    "applies_to": ["always"],
                    "validation": {"kind": "none"},
                    "allow_scheduled": False,
                }
            }
        }
    )


@pytest.fixture
def generator_data():
    return {
        "id": "readme-from-template",
        "applies_to": ["always"],
        "transformation": "regenerate-from-template",
        "source_paths": ["templates/repo-readme.md"],
        "output_paths": ["README.md", "docs/**/*.md"],
        "validation": {"kind": "none"},
    }


@pytest.fixture
def binding():
    return {
        "id": "widget-readme",
        "source": "hiivmind/template-repo",
        "branch": "main",
        "files": [{"path": "README.md"}],
    }


@pytest.fixture
def snapshot():
    return {
        "hiivmind/template-repo": {
            "main": {"head": "abc1234"},
        }
    }


@pytest.fixture
def actor():
    return {"gh_login": "octocat", "machine": "laptop", "mode": "interactive"}


# --- helpers copied/condensed from test_pen_orchestrator.py ------------------


class QueuedRunner:
    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def run(self, args):
        self.calls.append(args)
        return self._results.pop(0)


def _repo_state(owner, repo, working_tree="clean", freshness="fresh", divergence="up-to-date"):
    return {
        "owner": owner,
        "repo": repo,
        "working_tree": working_tree,
        "freshness": freshness,
        "divergence": divergence,
    }


def _pen_show_completed(repo_tuple):
    owner, repo = repo_tuple
    payload = {
        "name": "nave/widget-readme",
        "created_at": "2026-07-15T10:00:00Z",
        "branch": "nave/widget-readme",
        "filter": {"terms": []},
        "repos": [
            {
                "owner": owner,
                "name": repo,
                "default_branch": "main",
                "clone_url": "x",
                "synced_at": "2026-07-15T10:00:00Z",
            }
        ],
        "ops": [],
    }
    return nave_adapter.Completed(0, json.dumps(payload), "")


def _clean_preflight_sequence(repo_tuple):
    return [
        nave_adapter.Completed(0, "created\n", ""),
        _pen_show_completed(repo_tuple),
        nave_adapter.Completed(
            0,
            json.dumps([_repo_state(repo_tuple[0], repo_tuple[1])]),
            "",
        ),
    ]


# --- load_generators ---------------------------------------------------------


def test_load_generators_returns_generator_objects(registry, generator_data):
    generators = generator_dispatch.load_generators(
        {"readme-from-template": generator_data}, registry
    )

    assert set(generators) == {"readme-from-template"}
    gen = generators["readme-from-template"]
    assert isinstance(gen, generator_dispatch.Generator)
    assert gen.id == "readme-from-template"
    assert gen.transformation == "regenerate-from-template"
    assert gen.output_paths == ("README.md", "docs/**/*.md")
    assert gen.validation.kind == "none"


def test_load_generators_unknown_transformation_raises(registry):
    data = {
        "bad": {
            "id": "bad",
            "applies_to": ["always"],
            "transformation": "not-a-real-transformation",
            "source_paths": ["x"],
            "output_paths": ["x"],
            "validation": {"kind": "none"},
        }
    }

    with pytest.raises(mutation_plan.MutationPlanError) as exc:
        generator_dispatch.load_generators(data, registry)

    assert "not-a-real-transformation" in str(exc.value)


@pytest.mark.parametrize("bad_key", ["command", "command_argv"])
def test_load_generators_rejects_shell_string_command(registry, generator_data, bad_key):
    generator_data[bad_key] = "echo pwned" if bad_key == "command" else ["echo", "pwned"]

    with pytest.raises(mutation_plan.MutationPlanError) as exc:
        generator_dispatch.load_generators(
            {"readme-from-template": generator_data}, registry
        )

    assert bad_key in str(exc.value)
    assert "registry" in str(exc.value).lower()


def test_load_generators_empty_output_paths_raises(registry):
    data = {
        "empty": {
            "id": "empty",
            "applies_to": ["always"],
            "transformation": "regenerate-from-template",
            "source_paths": ["x"],
            "output_paths": [],
            "validation": {"kind": "none"},
        }
    }

    with pytest.raises(mutation_plan.MutationPlanError) as exc:
        generator_dispatch.load_generators(data, registry)

    assert "output_paths" in str(exc.value)


# --- dispatch ----------------------------------------------------------------


def test_dispatch_explicit_selection_happy_path(
    registry, generator_data, binding, snapshot, actor
):
    gen = generator_dispatch.load_generators(
        {"readme-from-template": generator_data}, registry
    )["readme-from-template"]

    proposal = generator_dispatch.dispatch(gen, binding, snapshot, actor)

    assert isinstance(proposal, mutation_plan.Proposal)
    assert proposal.id == "generate-readme-from-template-widget-readme"
    assert proposal.selection == ("hiivmind/template-repo",)
    assert proposal.expected_shas == {"hiivmind/template-repo": "abc1234"}
    assert proposal.transformation == "regenerate-from-template"
    assert proposal.mutation_policy == "propose"
    assert proposal.actor.gh_login == "octocat"


def test_dispatch_rejects_binding_file_outside_allowlist(
    registry, generator_data, binding, snapshot, actor
):
    binding["files"].append({"path": ".github/workflows/ci.yml"})
    gen = generator_dispatch.load_generators(
        {"readme-from-template": generator_data}, registry
    )["readme-from-template"]

    with pytest.raises(mutation_plan.MutationPlanError) as exc:
        generator_dispatch.dispatch(gen, binding, snapshot, actor)

    assert ".github/workflows/ci.yml" in str(exc.value)
    assert "allowlist" in str(exc.value).lower() or "output_paths" in str(exc.value)


@pytest.mark.parametrize(
    "missing_snapshot",
    [
        {},
        {"hiivmind/template-repo": {}},
        {"hiivmind/template-repo": {"main": {"head": None}}},
    ],
)
def test_dispatch_fails_closed_when_snapshot_head_missing(
    registry, generator_data, binding, actor, missing_snapshot
):
    gen = generator_dispatch.load_generators(
        {"readme-from-template": generator_data}, registry
    )["readme-from-template"]

    with pytest.raises(mutation_plan.MutationPlanError) as exc:
        generator_dispatch.dispatch(gen, binding, missing_snapshot, actor)

    assert "hiivmind/template-repo" in str(exc.value)


# --- generator_applies -------------------------------------------------------


def test_generator_applies_profile_mismatch_returns_false(registry, generator_data):
    generator_data["applies_to"] = ["profile:python"]
    gen = generator_dispatch.load_generators(
        {"readme-from-template": generator_data}, registry
    )["readme-from-template"]

    repository = RepositoryProfile(profiles=("nodejs",), scorecard="default")

    assert generator_dispatch.generator_applies(gen, repository, {}) is False


def test_generator_applies_profile_match_returns_true(registry, generator_data):
    generator_data["applies_to"] = ["profile:python"]
    gen = generator_dispatch.load_generators(
        {"readme-from-template": generator_data}, registry
    )["readme-from-template"]

    repository = RepositoryProfile(profiles=("python",), scorecard="default")

    assert generator_dispatch.generator_applies(gen, repository, {}) is True


# --- round-trip through pen_orchestrator.execute ------------------------------


def test_dispatched_proposal_passes_pen_orchestrator_expected_sha_guard(
    registry, generator_data, binding, snapshot, actor, monkeypatch
):
    gen = generator_dispatch.load_generators(
        {"readme-from-template": generator_data}, registry
    )["readme-from-template"]
    proposal = generator_dispatch.dispatch(gen, binding, snapshot, actor)
    entry = registry.get("regenerate-from-template")

    plan = pen_orchestrator.PenPlan(
        proposal=proposal,
        entry=entry,
        pen_name="nave/widget-readme",
        query=nave_adapter.PenQuery(terms=["owner:hiivmind/template-repo"]),
    )

    def fake_probe(_runner):
        return {"available": True, "version": "0.0.8", "protocol": 1}

    monkeypatch.setattr(pen_orchestrator.nave_adapter, "probe", fake_probe)

    repo_tuple = ("hiivmind", "template-repo")
    runner = QueuedRunner(
        [
            *_clean_preflight_sequence(repo_tuple),
            nave_adapter.Completed(0, "ran ok", ""),
            nave_adapter.Completed(
                0,
                json.dumps([_repo_state(repo_tuple[0], repo_tuple[1])]),
                "",
            ),
        ]
    )

    def matching_head(repo):
        assert repo == "hiivmind/template-repo"
        return "abc1234"

    result = pen_orchestrator.execute(plan, runner, read_repo_head=matching_head)

    assert result.state == "proposed"
    assert result.proposal_id == "generate-readme-from-template-widget-readme"
    assert result.repo_outcomes == {"hiivmind/template-repo": "ok"}
