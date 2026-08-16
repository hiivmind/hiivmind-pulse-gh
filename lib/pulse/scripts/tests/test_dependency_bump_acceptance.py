"""Dependency-bump handoff acceptance test (F11 <- F4): one finding, two
manager groups, two independent fenced proposal runs (each its own pen)."""

from __future__ import annotations

from types import SimpleNamespace

from lib.pulse.scripts import apply_driver, apply_rederive, mutation_plan


FINDING_REF = {"group": "core-runtime", "ecosystem": "python", "package": "requests"}


def _record(repo, manager, locked_version, manifest_path="pyproject.toml", lock_path=None):
    return apply_rederive.deps_module.PackageRecord(
        repo=repo, ecosystem="python", name="requests", resolution="single",
        manifest_range=">=2", locked_version=locked_version, unresolved_reason=None,
        manager=manager, manifest_path=manifest_path,
        lock_path=lock_path or {"uv": "uv.lock", "poetry": "poetry.lock"}[manager],
        tree_sha=f"tree-{repo.replace('/', '-')}", provenance=(),
    )


def _inputs():
    return apply_rederive.DependencyBumpProviderInputs(
        finding_ref=FINDING_REF,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="core-runtime", ecosystem="python", package="requests",
            versions=(("acme/uv-repo", "2.28.0"), ("acme/poetry-repo", "2.20.0"), ("acme/leader", "2.31.0")),
            distance="minor",
        ),
        target="2.31.0", selection=("acme/poetry-repo", "acme/uv-repo"),
        records_by_repo={
            ("acme/uv-repo", "python", "requests"): _record("acme/uv-repo", "uv", "2.28.0"),
            ("acme/poetry-repo", "python", "requests"): _record("acme/poetry-repo", "poetry", "2.20.0"),
        },
        head_shas={"acme/uv-repo": "a" * 40, "acme/poetry-repo": "b" * 40},
        tree_shas={"acme/uv-repo": "tree-acme-uv-repo", "acme/poetry-repo": "tree-acme-poetry-repo"},
        default_branches={"acme/uv-repo": "main", "acme/poetry-repo": "main"},
        blocked={}, actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )


def test_finding_to_two_manager_proposals_to_pr_opened(monkeypatch, tmp_path):
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: _inputs())

    proposal_states = {}

    def fake_run_apply(**kwargs):
        rp = kwargs["rederived_override"]
        proposal_states[rp.proposal.id] = kwargs
        return {"state": "pr_opened", "proposal_id": rp.proposal.id}

    monkeypatch.setattr(apply_driver, "run_apply", fake_run_apply)

    result = apply_driver.run_apply_dependency_bump(
        finding_ref=FINDING_REF,
        authorization_path=str(tmp_path / "auth.yaml"),
        ledger_path=str(tmp_path / "ledger.yaml"),
        step_id="dep-bump-1",
        actor_id="octocat@laptop",
        runner=SimpleNamespace(run=lambda a: None),
        gh_api=lambda ep: None,
        gh_ops=SimpleNamespace(),
        result_path=str(tmp_path / "result.yaml"),
        workspace=str(tmp_path),
    )

    assert result["state"] == "pr_opened"
    assert len(result["proposals"]) == 2
    assert len(proposal_states) == 2
    for proposal_id, kwargs in proposal_states.items():
        rp = kwargs["rederived_override"]
        assert rp.proposal.transform_params == {"package": "requests", "version": "2.31.0"}
        assert "pen_name" not in kwargs, "each proposal must own its own pen — never shared"
        assert kwargs["step_id"] == f"dep-bump-1.{proposal_id}"
        assert kwargs["result_path"].endswith((".uv", ".poetry"))
    transforms = {kwargs["rederived_override"].proposal.transformation for kwargs in proposal_states.values()}
    assert transforms == {"bump-python-uv", "bump-python-poetry"}


def test_finding_with_dev_group_declaration_blocks_that_repo_without_promoting(monkeypatch, tmp_path):
    inputs = apply_rederive._collect_dependency_bump(
        FINDING_REF, actor=mutation_plan.Actor("octocat", "laptop", "interactive"),
        io_seams=apply_rederive.IoSeams(),
        _fetch_records=lambda repos, io_seams: (
            [_record("acme/uv-repo", "uv", "2.28.0"), _record("acme/leader", "uv", "2.31.0")],
            {},
        ),
        _load_groups=lambda io_seams: (
            apply_rederive.deps_module.CoherenceGroup(
                id="core-runtime", repos=("acme/uv-repo", "acme/leader"),
                packages=("python:requests",), exclude_packages=(), policy="exact",
            ),
        ),
        _declarations_by_repo={"acme/uv-repo": {"python": {"requests": "dev"}}},
    )
    assert inputs.selection == ()
    assert inputs.blocked == {"acme/uv-repo": "non-main-group-package"}
    assert apply_rederive.rederive_dependency_bump(inputs) == []
