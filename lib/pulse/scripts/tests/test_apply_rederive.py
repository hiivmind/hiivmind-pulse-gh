"""Tests for the re-derivation provider registry (F11 Task 2).

`apply_rederive.collect_inputs` gathers FRESH source-of-truth evidence for
one binding (never a pen, never `read_repo_head` alone) via typed
provider input contexts; `rederive` hands that evidence to the REAL,
source-specific proposal builder with `mutation_policy="allow-listed"`.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json as jsonlib
from pathlib import Path

import pytest

from lib.pulse.scripts import (
    apply_rederive,
    generator_dispatch,
    marketplace_sync,
    marketplace_sync_run,
    mutation_plan,
    plan_sync_snapshot,
)

ACTOR = {"gh_login": "octocat", "machine": "laptop", "mode": "interactive"}


@dataclass
class Completed:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Hermetic argv-keyed fake runner, shared shape across all three
    sources' seams (`(argv, cwd) -> CompletedProcess-like`).

    `plan_sync_snapshot.collect`/`generated_artifacts.collect` always fetch
    into a freshly minted temp bare-fetch directory (never `workdir`
    itself), so the `git init` call's `repo_dir` argv element is
    unpredictable. Every other call (fetch/rev-parse/cat-file) uses that
    directory only as `cwd`, not as an argv value, so only `git init`
    needs a path-independent fallback.
    """

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def __call__(self, argv, cwd=None):
        self.calls.append((tuple(argv), str(cwd) if cwd is not None else None))
        key = tuple(argv)
        response = self.responses.get(key)
        if response is None and len(key) >= 2 and key[0] == "git" and key[1] == "init":
            response = next(
                (
                    value for other, value in self.responses.items()
                    if len(other) >= 2 and other[0] == "git" and other[1] == "init"
                ),
                None,
            )
        return response or Completed(1, "", f"unexpected: {argv}")


# --- plan-sync fixtures -----------------------------------------------------

PLAN_REPO = "acme/docs"
PLAN_BRANCH = "main"
PLAN_PATH = "plans/release.md"
PLAN_URL = "https://github.com/acme/docs.git"
PLAN_HEAD = "a" * 40
PLAN_BASE_BLOB = "b" * 40
PLAN_CHANGED_BLOB = "c" * 40


def plan_binding(**overrides):
    value = {
        "id": "release-plan",
        "repo": PLAN_REPO,
        "branch": PLAN_BRANCH,
        "path": PLAN_PATH,
        "sync": {
            "issue": {"repo": "acme/widgets", "number": 42},
            "base": {
                "blob": PLAN_BASE_BLOB,
                "title": "Release plan",
                "state": "open",
                "assignees": ["ada"],
                "milestone": None,
            },
        },
    }
    value.update(overrides)
    return value


def _plan_git_responses(repo_dir, blob=PLAN_CHANGED_BLOB):
    return {
        ("git", "init", "--bare", "-q", "--", str(repo_dir)): Completed(),
        ("git", "fetch", "--filter=blob:none", "-q", "--", PLAN_URL, f"refs/heads/{PLAN_BRANCH}"): Completed(),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(0, f"{PLAN_HEAD}\n"),
        ("git", "rev-parse", f"FETCH_HEAD:{PLAN_PATH}"): Completed(0, f"{blob}\n"),
    }


def _plan_gh_api(path):
    if path.endswith("/issues/42"):
        return {
            "title": "Release plan v2",
            "body": "GitHub body changed.",
            "state": "open",
            "assignees": [{"login": "ada"}],
            "milestone": None,
        }
    return []


def _plan_registry():
    return mutation_plan.load_registry({
        "transformations": {
            "plan-sync-doc-patch": {
                "id": "plan-sync-doc-patch",
                "command_argv": [
                    "pulse-apply-doc-patch", "--patch", ".hiivmind/plan-sync-patch.yaml",
                ],
                "applies_to": ["always"],
                "validation": {"kind": "paths_changed"},
                "allow_scheduled": False,
            }
        }
    })


def _plan_runner(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = _plan_git_responses(repo_dir)
    responses.update({
        ("git", "cat-file", "blob", PLAN_CHANGED_BLOB): Completed(
            0,
            "---\nsync:\n"
            "  issue: {repo: acme/widgets, number: 42}\n"
            f"  base: {{blob: {PLAN_BASE_BLOB}, title: Release plan, state: open, "
            "assignees: [ada], milestone: null}\n"
            "---\n# Release plan\n\nBase body.\n",
        ),
        ("git", "cat-file", "blob", PLAN_BASE_BLOB): Completed(
            0, "# Release plan\n\nBase body.\n"
        ),
    })
    return RecordingRunner(responses)


def _plan_recorded_summary(binding_id="release-plan"):
    return {"binding_id": binding_id, "transformation": None, "proposal_id": None, "actor": ACTOR}


# --- plan-sync: collect_inputs -----------------------------------------------


def test_collect_inputs_plan_sync_returns_fresh_document_snapshot(tmp_path):
    runner = _plan_runner(tmp_path)
    io_seams = apply_rederive.IoSeams(
        runner=runner, gh_api=_plan_gh_api, workdir=tmp_path, registry=_plan_registry(),
    )

    inputs = apply_rederive.collect_inputs(
        "plan-sync", plan_binding(), _plan_recorded_summary(), io_seams=io_seams,
    )

    assert isinstance(inputs, apply_rederive.PlanSyncProviderInputs)
    assert inputs.document_snapshot.state == "changed"
    assert inputs.document_snapshot.repo == PLAN_REPO
    assert inputs.document_snapshot.blob == PLAN_CHANGED_BLOB
    assert inputs.github_snapshot == inputs.document_snapshot.github
    assert inputs.binding["id"] == "release-plan"
    # Real git evidence was fetched — this never came from a pen. (The
    # fetch runs in an isolated, randomly named bare-fetch tempdir, so only
    # the argv — not `cwd` — is asserted.)
    fetch_argvs = [call[0] for call in runner.calls]
    assert (
        "git", "fetch", "--filter=blob:none", "-q", "--", PLAN_URL, f"refs/heads/{PLAN_BRANCH}",
    ) in fetch_argvs


def test_collect_inputs_rejects_binding_id_mismatch_before_any_io(tmp_path):
    runner = _plan_runner(tmp_path)
    io_seams = apply_rederive.IoSeams(runner=runner, gh_api=_plan_gh_api, workdir=tmp_path)

    with pytest.raises(apply_rederive.RederiveError, match="binding_id"):
        apply_rederive.collect_inputs(
            "plan-sync",
            plan_binding(),
            _plan_recorded_summary(binding_id="some-other-binding"),
            io_seams=io_seams,
        )

    # Fail-closed before any I/O: no git call was ever issued.
    assert runner.calls == []


def test_collect_inputs_rejects_unknown_source_kind():
    with pytest.raises(apply_rederive.RederiveError, match="source_kind"):
        apply_rederive.collect_inputs(
            "unknown-source", plan_binding(), _plan_recorded_summary(), io_seams=apply_rederive.IoSeams(),
        )


# --- plan-sync: rederive ------------------------------------------------------


def test_rederive_plan_sync_calls_real_build_apply_plans_allow_listed(tmp_path):
    runner = _plan_runner(tmp_path)
    io_seams = apply_rederive.IoSeams(
        runner=runner, gh_api=_plan_gh_api, workdir=tmp_path, registry=_plan_registry(),
    )
    inputs = apply_rederive.collect_inputs(
        "plan-sync", plan_binding(), _plan_recorded_summary(), io_seams=io_seams,
    )

    rederived = apply_rederive.rederive(inputs)

    assert isinstance(rederived, apply_rederive.RederivedProposal)
    assert rederived.source_kind == "plan-sync"
    assert rederived.binding_id == "release-plan"
    assert isinstance(rederived.proposal, mutation_plan.Proposal)
    assert rederived.proposal.transformation == "plan-sync-doc-patch"
    assert rederived.proposal.mutation_policy == "allow-listed"
    assert rederived.proposal.selection == (PLAN_REPO,)
    assert rederived.proposal.bound_paths == {PLAN_REPO: (PLAN_PATH,)}
    # F8 finalizer_record built directly from the fresh DocumentSnapshot +
    # parsed binding — never from stale recorded_summary fields.
    assert rederived.finalizer_record == {
        "repo": PLAN_REPO,
        "base_ref": PLAN_BRANCH,
        "doc_path": PLAN_PATH,
        "expected_prior_blob": PLAN_BASE_BLOB,
        "proposal_id": rederived.proposal.id,
        "binding_id": "release-plan",
    }


def test_rederive_plan_sync_raises_when_document_is_in_sync(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = _plan_git_responses(repo_dir, blob=PLAN_BASE_BLOB)
    responses[("git", "cat-file", "blob", PLAN_BASE_BLOB)] = Completed(
        0,
        "---\nsync:\n"
        "  issue: {repo: acme/widgets, number: 42}\n"
        f"  base: {{blob: {PLAN_BASE_BLOB}, title: Release plan, state: open, "
        "assignees: [ada], milestone: null}\n"
        "---\n# Release plan\n\nBase body.\n",
    )
    runner = RecordingRunner(responses)

    def gh_api_in_sync(path):
        if path.endswith("/issues/42"):
            return {
                "title": "Release plan", "body": "# Release plan\n\nBase body.\n",
                "state": "open", "assignees": [{"login": "ada"}], "milestone": None,
            }
        return []

    io_seams = apply_rederive.IoSeams(
        runner=runner, gh_api=gh_api_in_sync, workdir=tmp_path, registry=_plan_registry(),
    )
    inputs = apply_rederive.collect_inputs(
        "plan-sync", plan_binding(), _plan_recorded_summary(), io_seams=io_seams,
    )

    with pytest.raises(apply_rederive.RederiveError, match="no repo proposal|in_sync"):
        apply_rederive.rederive(inputs)


# --- generated-artifact fixtures ---------------------------------------------

GEN_SOURCE = "hiivmind/template-repo"
GEN_BRANCH = "main"
GEN_URL = "https://github.com/hiivmind/template-repo.git"


def gen_registry():
    return mutation_plan.load_registry({
        "transformations": {
            "regenerate-from-template": {
                "id": "regenerate-from-template",
                "command_argv": ["nave", "generate", "--from-template"],
                "applies_to": ["always"],
                "validation": {"kind": "none"},
                "allow_scheduled": False,
            }
        }
    })


def gen_generators(registry):
    return generator_dispatch.load_generators(
        {
            "readme-from-template": {
                "id": "readme-from-template",
                "applies_to": ["always"],
                "transformation": "regenerate-from-template",
                "source_paths": ["templates/repo-readme.md"],
                "output_paths": ["README.md", "docs/**/*.md"],
                "validation": {"kind": "none"},
            }
        },
        registry,
    )


def gen_binding(**overrides):
    value = {
        "id": "widget-readme",
        "source": GEN_SOURCE,
        "branch": GEN_BRANCH,
        "generator": "readme-from-template",
        "files": [{"path": "README.md"}],
    }
    value.update(overrides)
    return value


def _gen_recorded_summary(binding_id="widget-readme"):
    return {"binding_id": binding_id, "transformation": None, "proposal_id": None, "actor": ACTOR}


def _gen_runner(tmp_path):
    repo_dir = tmp_path / "hiivmind_template-repo_main"
    responses = {
        ("git", "init", "--bare", "-q", str(repo_dir)): Completed(),
        ("git", "fetch", "--filter=blob:none", "-q", "--", GEN_URL, GEN_BRANCH): Completed(),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(0, "head999\n"),
        ("git", "rev-parse", "FETCH_HEAD:README.md"): Completed(0, "blob1111\n"),
    }
    return RecordingRunner(responses)


def test_collect_inputs_generated_artifact_resolves_generator_and_snapshot(tmp_path):
    registry = gen_registry()
    generators = gen_generators(registry)
    runner = _gen_runner(tmp_path)
    io_seams = apply_rederive.IoSeams(
        runner=runner, workdir=tmp_path, generators=generators, registry=registry,
    )

    inputs = apply_rederive.collect_inputs(
        "generated-artifact", gen_binding(), _gen_recorded_summary(), io_seams=io_seams,
    )

    assert isinstance(inputs, apply_rederive.GeneratedProviderInputs)
    assert inputs.generator.id == "readme-from-template"
    assert inputs.snapshot == {GEN_SOURCE: {GEN_BRANCH: {"head": "head999", "trees": {}, "blobs": {"README.md": "blob1111"}}}}


def test_collect_inputs_generated_artifact_unknown_generator_fails_closed(tmp_path):
    registry = gen_registry()
    generators = gen_generators(registry)
    io_seams = apply_rederive.IoSeams(
        runner=_gen_runner(tmp_path), workdir=tmp_path, generators=generators, registry=registry,
    )

    with pytest.raises(apply_rederive.RederiveError, match="generator"):
        apply_rederive.collect_inputs(
            "generated-artifact",
            gen_binding(generator="does-not-exist"),
            _gen_recorded_summary(),
            io_seams=io_seams,
        )


def test_rederive_generated_artifact_calls_real_dispatch_allow_listed(tmp_path):
    registry = gen_registry()
    generators = gen_generators(registry)
    io_seams = apply_rederive.IoSeams(
        runner=_gen_runner(tmp_path), workdir=tmp_path, generators=generators, registry=registry,
    )
    inputs = apply_rederive.collect_inputs(
        "generated-artifact", gen_binding(), _gen_recorded_summary(), io_seams=io_seams,
    )

    rederived = apply_rederive.rederive(inputs)

    assert rederived.source_kind == "generated-artifact"
    assert rederived.binding_id == "widget-readme"
    assert rederived.finalizer_record is None
    assert rederived.proposal.transformation == "regenerate-from-template"
    assert rederived.proposal.mutation_policy == "allow-listed"
    assert rederived.proposal.selection == (GEN_SOURCE,)
    assert rederived.proposal.expected_shas == {GEN_SOURCE: "head999"}
    assert rederived.proposal.bound_paths == {GEN_SOURCE: ("README.md",)}


def test_rederive_generated_artifact_raises_for_out_of_allowlist_file(tmp_path):
    """An empty `files: []` binding still produces a valid (if pointless)
    proposal — `bound_paths={source: ()}` still covers the selected repo
    exactly, so the mandatory allow-listed bounds check is satisfied. The
    real fail-closed case is a binding file outside the generator's
    `output_paths` allowlist, which `generator_dispatch.dispatch` itself
    rejects; `rederive` wraps that `MutationPlanError` as `RederiveError`.
    """
    registry = gen_registry()
    generators = gen_generators(registry)
    io_seams = apply_rederive.IoSeams(
        runner=_gen_runner(tmp_path), workdir=tmp_path, generators=generators, registry=registry,
    )
    inputs = apply_rederive.collect_inputs(
        "generated-artifact",
        gen_binding(files=[{"path": "not-allowed.txt"}]),
        _gen_recorded_summary(),
        io_seams=io_seams,
    )

    with pytest.raises(apply_rederive.RederiveError, match="allowlist"):
        apply_rederive.rederive(inputs)


# --- marketplace-sync fixtures ------------------------------------------------

PLUGIN_ID = "hiivmind-pulse-gh"
PLUGIN_REPO = "hiivmind/hiivmind-pulse-gh"
MARKETPLACE_REPO = "hiivmind/claude-marketplace"
MARKETPLACE_FILE = ".claude-plugin/marketplace.json"


def mkt_binding(**overrides):
    value = {
        "id": "hiivmind-pulse-gh-marketplace",
        "plugin_id": PLUGIN_ID,
        "repo": PLUGIN_REPO,
        "marketplace_repo": MARKETPLACE_REPO,
        "marketplace_file": MARKETPLACE_FILE,
    }
    value.update(overrides)
    return value


def mkt_doc(plugin_id, version):
    return {
        "name": "hiivmind",
        "owner": {"name": "Discrete Data Systems"},
        "repository": "https://github.com/hiivmind/hiivmind",
        "metadata": {"version": "1.0.0"},
        "plugins": [
            {
                "name": plugin_id, "source": "./", "description": "...",
                "version": version, "keywords": ["github"],
            }
        ],
    }


def mkt_registry():
    return mutation_plan.load_registry({
        "transformations": {
            "marketplace-entry-update": {
                "id": "marketplace-entry-update",
                "command_argv": [
                    "pulse-apply-marketplace-entry", "--patch",
                    ".hiivmind/marketplace-entry-patch.yaml",
                ],
                "applies_to": ["profile:claude-plugin"],
                "validation": {"kind": "none"},
                "allow_scheduled": False,
            }
        }
    })


def _mkt_recorded_summary(binding_id="hiivmind-pulse-gh-marketplace"):
    return {"binding_id": binding_id, "transformation": None, "proposal_id": None, "actor": ACTOR}


def _mkt_runner(current_version="v1.0.0", next_version="v2.0.0", head_sha="deadbeefcafe"):
    releases = [{"tagName": next_version, "isPrerelease": False, "isDraft": False}]
    doc_bytes = jsonlib.dumps(mkt_doc(PLUGIN_ID, current_version)).encode()
    doc_b64 = base64.b64encode(doc_bytes).decode()
    responses = {
        (
            "gh", "release", "list", "--json", "tagName,isPrerelease,isDraft",
            "--limit", "100", "--repo", PLUGIN_REPO,
        ): Completed(0, jsonlib.dumps(releases), ""),
        (
            "gh", "api", f"repos/{MARKETPLACE_REPO}/contents/{MARKETPLACE_FILE}",
        ): Completed(0, jsonlib.dumps({"content": doc_b64}), ""),
        (
            "gh", "api", f"repos/{MARKETPLACE_REPO}/commits/HEAD", "--jq", ".sha",
        ): Completed(0, f"{head_sha}\n", ""),
    }
    return RecordingRunner(responses)


def test_collect_inputs_marketplace_sync_computes_fresh_drift_and_head_sha():
    runner = _mkt_runner()
    io_seams = apply_rederive.IoSeams(runner=runner, registry=mkt_registry())

    inputs = apply_rederive.collect_inputs(
        "marketplace-sync", mkt_binding(), _mkt_recorded_summary(), io_seams=io_seams,
    )

    assert isinstance(inputs, apply_rederive.MarketplaceProviderInputs)
    assert inputs.drift.outcome == marketplace_sync.OUTCOME_DRIFT
    assert inputs.drift.current_version == "v1.0.0"
    assert inputs.drift.target_version == "v2.0.0"
    assert inputs.head_sha == "deadbeefcafe"


def test_rederive_marketplace_sync_calls_real_build_marketplace_proposal_allow_listed():
    io_seams = apply_rederive.IoSeams(runner=_mkt_runner(), registry=mkt_registry())
    inputs = apply_rederive.collect_inputs(
        "marketplace-sync", mkt_binding(), _mkt_recorded_summary(), io_seams=io_seams,
    )

    rederived = apply_rederive.rederive(inputs)

    assert rederived.source_kind == "marketplace-sync"
    assert rederived.binding_id == "hiivmind-pulse-gh-marketplace"
    assert rederived.finalizer_record is None
    assert rederived.proposal.transformation == "marketplace-entry-update"
    assert rederived.proposal.mutation_policy == "allow-listed"
    assert rederived.proposal.selection == (MARKETPLACE_REPO,)
    assert rederived.proposal.expected_shas == {MARKETPLACE_REPO: "deadbeefcafe"}
    assert rederived.proposal.bound_paths == {MARKETPLACE_REPO: (MARKETPLACE_FILE,)}


def test_rederive_marketplace_sync_raises_when_head_sha_unresolved():
    runner = _mkt_runner()
    # Force an unresolved head SHA by removing the commits/HEAD response.
    del runner.responses[("gh", "api", f"repos/{MARKETPLACE_REPO}/commits/HEAD", "--jq", ".sha")]
    io_seams = apply_rederive.IoSeams(runner=runner, registry=mkt_registry())
    inputs = apply_rederive.collect_inputs(
        "marketplace-sync", mkt_binding(), _mkt_recorded_summary(), io_seams=io_seams,
    )

    assert inputs.head_sha is None
    with pytest.raises(apply_rederive.RederiveError, match="head_sha"):
        apply_rederive.rederive(inputs)


def test_rederive_marketplace_sync_raises_for_in_sync_drift():
    runner = _mkt_runner(current_version="v2.0.0", next_version="v2.0.0")
    io_seams = apply_rederive.IoSeams(runner=runner, registry=mkt_registry())
    inputs = apply_rederive.collect_inputs(
        "marketplace-sync", mkt_binding(), _mkt_recorded_summary(), io_seams=io_seams,
    )

    with pytest.raises(apply_rederive.RederiveError, match="not proposable"):
        apply_rederive.rederive(inputs)


def test_rederive_unsupported_inputs_type_raises():
    with pytest.raises(apply_rederive.RederiveError):
        apply_rederive.rederive(object())
