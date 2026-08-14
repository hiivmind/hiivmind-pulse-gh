"""Neutral end-to-end acceptance suite and overlay dogfood suite (F11 Task 8 capstone).

Composes real public entry points across F11 Tasks 1-7:
- `pen_orchestrator.execute` (allow-listed apply landing)
- `apply_reconcile.open_apply_pr` and `reconcile_apply` (PR open -> merge detect -> base advance)
- `resolve_run.evaluate_merge_detected_gate` (gate evaluation)
- `object_apply.apply_object_write` (Path B GitHub object writes)

All tests run without network access, injecting explicit fake seams for CLI/remote calls.
Known coverage boundaries are explicitly documented in test docstrings and assertions.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from lib.pulse.scripts import (
    apply_reconcile,
    mutation_plan,
    nave_adapter,
    object_apply,
    pen_orchestrator,
    resolve_run,
    validate_result,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "neutral_repos"

PROPOSAL_DIGEST = "v1|" + "a" * 64
AUTHORIZATION_DIGEST = "v1|" + "b" * 64


# --- Fakes & Test Helpers --------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_probe(monkeypatch):
    """Stub nave_adapter.probe to fixed available response avoiding extra CLI probe calls."""
    monkeypatch.setattr(
        pen_orchestrator.nave_adapter,
        "probe",
        lambda _runner: {"available": True, "version": "0.0.8", "protocol": 1},
    )


class QueuedRunner:
    """Fake Nave runner returning pre-queued Completed instances.

    KNOWN COVERAGE BOUNDARY: Nave CLI (`pen create`, `pen status`, `pen exec`)
    execution is stubbed here. Status: not_applicable in unit test suite.
    """

    def __init__(self, results: list[nave_adapter.Completed]) -> None:
        self.calls: list[list[str]] = []
        self._results = list(results)

    def run(self, args: list[str]) -> nave_adapter.Completed:
        self.calls.append(args)
        return self._results.pop(0)


class RecordingApplyOps:
    """Fake apply_ops recording branch provisioning, commit, and push operations.

    KNOWN COVERAGE BOUNDARY: Pen clone git branch creation, committing, and remote
    pushing are recorded in-memory. Status: not_applicable in unit test suite.
    """

    def __init__(
        self,
        prov_results: dict[str, dict[str, str]] | None = None,
        commit_results: dict[str, dict[str, str]] | None = None,
        push_results: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.prov_results = prov_results
        self.commit_results = commit_results
        self.push_results = push_results

    def provision_branch(self, branch: str, base_shas: dict[str, str]) -> dict[str, dict[str, str]]:
        self.calls.append(("provision_branch", branch, base_shas))
        if self.prov_results is not None:
            return self.prov_results
        return {repo: {"state": "ok"} for repo in base_shas}

    def commit_repos(self, message: str) -> dict[str, dict[str, str]]:
        self.calls.append(("commit_repos", message))
        if self.commit_results is not None:
            return self.commit_results
        return {"acme/docs-repo": {"state": "ok"}, "acme/node-repo": {"state": "ok"}, "acme/plugin-repo": {"state": "ok"}}

    def push_repos(self, branch: str) -> dict[str, dict[str, str]]:
        self.calls.append(("push_repos", branch))
        if self.push_results is not None:
            return self.push_results
        return {"acme/docs-repo": {"state": "ok"}, "acme/node-repo": {"state": "ok"}, "acme/plugin-repo": {"state": "ok"}}


class FakeGhOps(apply_reconcile.GhOps):
    """Fake GitHub CLI operations for PR management and reconciliation.

    KNOWN COVERAGE BOUNDARY: GitHub PR creation, viewing, and branch deletion
    via `gh` CLI are stubbed in-memory. Status: not_applicable in unit test suite.
    """

    def __init__(self) -> None:
        self.prs: dict[tuple[str, str], dict[str, object]] = {}
        self.deleted_branches: list[tuple[str, str]] = []
        self.create_calls = 0

    def create_or_get_pr(
        self, repo: str, branch: str, base: str, title: str, body: str
    ) -> dict[str, object]:
        key = (repo, branch)
        if key in self.prs and self.prs[key]["state"] == "OPEN":
            return {"url": str(self.prs[key]["url"]), "created": False}
        self.create_calls += 1
        url = f"https://github.com/{repo}/pull/{self.create_calls}"
        self.prs[key] = {
            "url": url,
            "state": "OPEN",
            "merged": False,
            "merge_commit_sha": None,
            "base": base,
            "head_ref": None,
            "title": title,
            "body": body,
        }
        return {"url": url, "created": True}

    def view_pr(self, repo: str, branch: str) -> dict[str, object]:
        key = (repo, branch)
        if key not in self.prs:
            return {
                "state": "CLOSED",
                "merged": False,
                "merge_commit_sha": None,
                "url": "",
                "observed_base": None,
                "observed_head_sha": None,
            }
        pr = self.prs[key]
        return {
            "state": pr["state"],
            "merged": pr["merged"],
            "merge_commit_sha": pr["merge_commit_sha"],
            "url": pr["url"],
            "observed_base": pr.get("base"),
            "observed_head_sha": pr.get("head_ref"),
        }

    def delete_remote_branch(self, repo: str, branch: str) -> dict[str, object]:
        self.deleted_branches.append((repo, branch))
        return {"state": "ok"}


class FakeObjectGhOps(object_apply.ObjectGhOps):
    """Fake GitHub object API operations for Path B writes.

    KNOWN COVERAGE BOUNDARY: GitHub GraphQL/REST object writes are stubbed in-memory.
    Status: not_applicable in unit test suite.
    """

    def __init__(self, initial_state: dict[str, dict[str, object]] | None = None) -> None:
        self.state: dict[str, dict[str, object]] = initial_state or {}
        self.writes: list[object_apply.ObjectWrite] = []

    def get_state(self, precondition: object_apply.Precondition) -> object:
        target_state = self.state.get(precondition.target, {})
        if precondition.field not in target_state:
            raise object_apply.GhExecutionError(
                f"field {precondition.field} not found for {precondition.target}"
            )
        return target_state[precondition.field]

    def apply_write(self, write: object_apply.ObjectWrite) -> dict[str, object]:
        self.writes.append(write)
        target = write.target
        if target not in self.state:
            self.state[target] = {}

        field = write.payload.get("field") or write.precondition.field
        val = write.desired if write.desired is not None else write.payload.get("value")
        self.state[target][field] = val
        return {"state": "applied", "target": target, "field": field, "value": val}


def _pen_show_completed(repos: list[tuple[str, str]]) -> nave_adapter.Completed:
    payload = {
        "name": "nave/acceptance",
        "created_at": "2026-07-29T10:00:00Z",
        "branch": "nave/acceptance",
        "filter": {"terms": []},
        "repos": [
            {
                "owner": o,
                "name": n,
                "default_branch": "main",
                "clone_url": "x",
                "synced_at": "2026-07-29T10:00:00Z",
            }
            for o, n in repos
        ],
        "ops": [],
    }
    return nave_adapter.Completed(0, json.dumps(payload), "")


def _pen_status_completed(entries: list[dict[str, object]]) -> nave_adapter.Completed:
    return nave_adapter.Completed(0, json.dumps(entries), "")


def _exec_ok_sequence(repos: list[tuple[str, str]]) -> list[nave_adapter.Completed]:
    status_entries = [
        {
            "owner": o,
            "repo": n,
            "working_tree": "clean",
            "freshness": "fresh",
            "run_state": "not-run",
            "divergence": "up-to-date",
            "ahead": 0,
            "behind": 0,
        }
        for o, n in repos
    ]
    return [
        nave_adapter.Completed(0, "created\n", ""),
        _pen_show_completed(repos),
        _pen_status_completed(status_entries),
        _pen_status_completed(status_entries),
        nave_adapter.Completed(0, "exec ok\n", ""),
    ]


def _create_test_ledger(tmp_path: Path, run_id: str, step_id: str, repo: str) -> Path:
    steps = json.dumps([
        {
            "id": step_id,
            "repo": repo,
            "gate": "merge_detected",
            "has_workflow": True,
        }
    ])
    resolve_run.cmd_create(
        type(
            "Args",
            (),
            {
                "runs_dir": str(tmp_path),
                "workflow": "apply-reconcile",
                "run_id": run_id,
                "actor_login": "octocat",
                "actor_machine": "laptop",
                "mode": "interactive",
                "params": "{}",
                "repos": repo,
                "steps": steps,
                "local": True,
            },
        )()
    )
    return tmp_path / "local" / f"apply-reconcile-{run_id}.yaml"


# --- Neutral Acceptance Suite -----------------------------------------------

class TestNeutralApplyAcceptanceSuite:
    """Suite 1: Fixture-driven NEUTRAL end-to-end acceptance tests.

    Tests non-plugin transformations (`regenerate-docs-index`, `refresh-node-lockfile`)
    through the full lifecycle:
    propose -> allow-listed apply -> branch -> push -> PR -> merge-detect -> base-advance.
    """

    def test_docs_index_neutral_lifecycle_success(self, tmp_path: Path) -> None:
        """Full lifecycle for neutral transformation `regenerate-docs-index`."""
        # 1. Proposal setup for neutral transformation
        proposal = mutation_plan.build_proposal(
            id="prop-docs-100",
            selection=["acme/docs-repo"],
            transformation="regenerate-docs-index",
            expected_shas={"acme/docs-repo": "pushed_sha_base_100"},
            actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
            mutation_policy="allow-listed",
            bound_paths={"acme/docs-repo": [".generated/docs/**"]},
        )
        registry = mutation_plan.load_registry({
            "transformations": {
                "regenerate-docs-index": {
                    "id": "regenerate-docs-index",
                    "command_argv": ["mkdocs", "build", "--site-dir", ".generated/docs"],
                    "applies_to": ["evidence_path:mkdocs.yml"],
                    "validation": {"kind": "paths_changed"},
                    "allow_scheduled": True,
                }
            }
        })
        plan = pen_orchestrator.PenPlan(
            proposal=proposal,
            entry=registry.get("regenerate-docs-index"),
            pen_name="nave/acceptance",
            query=nave_adapter.PenQuery(terms=[]),
        )

        runner = QueuedRunner(_exec_ok_sequence([("acme", "docs-repo")]))
        apply_ops = RecordingApplyOps()

        def read_repo_head(repo: str) -> str:
            return "pushed_sha_base_100"

        def read_repo_changed_paths(repo: str) -> tuple[str, ...]:
            return (".generated/docs/index.html",)

        # 2. Execute allow-listed apply
        exec_res = pen_orchestrator.execute(
            plan,
            runner,
            read_repo_head=read_repo_head,
            read_repo_changed_paths=read_repo_changed_paths,
            apply_ops=apply_ops,
        )

        # Assert: reaches state "pushed" and push targeted pulse/apply/{id}, NEVER main/base
        assert exec_res.state == "pushed"
        assert exec_res.repo_outcomes == {"acme/docs-repo": "ok"}

        assert len(apply_ops.calls) == 3
        prov_call, commit_call, push_call = apply_ops.calls
        assert prov_call == (
            "provision_branch",
            "pulse/apply/prop-docs-100",
            {"acme/docs-repo": "pushed_sha_base_100"},
        )
        assert push_call == ("push_repos", "pulse/apply/prop-docs-100")
        assert "main" not in push_call[1]
        assert "master" not in push_call[1]

        # 3. PR Open phase
        ledger_path = _create_test_ledger(tmp_path, "run-docs-100", "step-docs", "acme/docs-repo")
        result_path = tmp_path / "apply-status-docs.yaml"
        gh_ops = FakeGhOps()

        doc_pr = apply_reconcile.open_apply_pr(
            ledger_path=ledger_path,
            step_id="step-docs",
            proposal_id="prop-docs-100",
            repo="acme/docs-repo",
            branch="pulse/apply/prop-docs-100",
            base="main",
            pushed_sha="pushed_sha_base_100",
            title="Apply regenerate-docs-index prop-docs-100",
            body="Automated neutral apply PR",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-docs-100",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_base_100",
            actor_id="octocat@laptop",
            workspace="acme",
        )

        assert doc_pr["state"] == "pr_opened"
        assert doc_pr["pushed_sha"] == "pushed_sha_base_100"
        assert validate_result.validate(doc_pr, "apply-status") == []

        # Gate check before merge: merge-detected gate is NOT satisfied
        satisfied_before, _ = resolve_run.evaluate_merge_detected_gate(str(result_path))
        assert satisfied_before is False

        # Injected base advancement stub
        advance_calls: list[tuple[str, str]] = []

        def advance_base_fake(repo: str, merged_sha: str) -> dict[str, str]:
            advance_calls.append((repo, merged_sha))
            return {"state": "ok"}

        # First reconcile pass while PR is OPEN: base does NOT advance
        doc_reconcile_open = apply_reconcile.reconcile_apply(
            ledger_path=ledger_path,
            step_id="step-docs",
            proposal_id="prop-docs-100",
            repo="acme/docs-repo",
            branch="pulse/apply/prop-docs-100",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-docs-100",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_base_100",
            advance_base=advance_base_fake,
            actor_id="octocat@laptop",
            workspace="acme",
        )
        assert doc_reconcile_open["state"] == "pr_opened"
        assert advance_calls == [], "Base advancement must NOT occur while PR is OPEN"

        # 4. Simulate PR MERGED in GitHub
        gh_ops.prs[("acme/docs-repo", "pulse/apply/prop-docs-100")]["state"] = "MERGED"
        gh_ops.prs[("acme/docs-repo", "pulse/apply/prop-docs-100")]["merged"] = True
        gh_ops.prs[("acme/docs-repo", "pulse/apply/prop-docs-100")]["merge_commit_sha"] = "merged_sha_docs_999"
        gh_ops.prs[("acme/docs-repo", "pulse/apply/prop-docs-100")]["head_ref"] = "pushed_sha_base_100"

        doc_reconcile_merged = apply_reconcile.reconcile_apply(
            ledger_path=ledger_path,
            step_id="step-docs",
            proposal_id="prop-docs-100",
            repo="acme/docs-repo",
            branch="pulse/apply/prop-docs-100",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-docs-100",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_base_100",
            advance_base=advance_base_fake,
            actor_id="octocat@laptop",
            workspace="acme",
        )

        # Assert: state is "applied", validates schema, merged SHA is set
        assert doc_reconcile_merged["state"] == "applied"
        assert doc_reconcile_merged["merged_sha"] == "merged_sha_docs_999"
        assert validate_result.validate(doc_reconcile_merged, "apply-status") == []

        # Gate check after merge: gate IS satisfied
        satisfied_after, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
        assert satisfied_after is True
        assert "merged_sha_docs_999" in detail

        # Assert: base advancement happened ONLY on detected merge with MERGED sha (never pushed sha)
        assert advance_calls == [("acme/docs-repo", "merged_sha_docs_999")]
        assert advance_calls[0][1] != "pushed_sha_base_100"

    def test_neutral_bound_path_guard_fires_on_violation(self) -> None:
        """Bound-path guard (I7) fires on neutral transformation when changed paths violate bound_paths."""
        proposal = mutation_plan.build_proposal(
            id="prop-docs-101",
            selection=["acme/docs-repo"],
            transformation="regenerate-docs-index",
            expected_shas={"acme/docs-repo": "deadbeef"},
            actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
            mutation_policy="allow-listed",
            bound_paths={"acme/docs-repo": [".generated/docs/**"]},
        )
        registry = mutation_plan.load_registry({
            "transformations": {
                "regenerate-docs-index": {
                    "id": "regenerate-docs-index",
                    "command_argv": ["mkdocs", "build"],
                    "applies_to": ["always"],
                    "validation": {"kind": "paths_changed"},
                    "allow_scheduled": True,
                }
            }
        })
        plan = pen_orchestrator.PenPlan(
            proposal=proposal,
            entry=registry.get("regenerate-docs-index"),
            pen_name="nave/acceptance",
            query=nave_adapter.PenQuery(terms=[]),
        )

        runner = QueuedRunner(_exec_ok_sequence([("acme", "docs-repo")]))
        apply_ops = RecordingApplyOps()

        def read_repo_head(repo: str) -> str:
            return "deadbeef"

        # Violating path outside .generated/docs/**
        def read_repo_changed_paths_violating(repo: str) -> tuple[str, ...]:
            return (".generated/docs/index.html", "src/unauthorized_code.py")

        exec_res = pen_orchestrator.execute(
            plan,
            runner,
            read_repo_head=read_repo_head,
            read_repo_changed_paths=read_repo_changed_paths_violating,
            apply_ops=apply_ops,
        )

        # Assert: fails closed with blocked or failed (NOT pushed)
        assert exec_res.state in ("blocked", "failed")
        assert exec_res.state != "pushed"
        assert "bound_paths" in (exec_res.reason or "") or "out-of-bounds" in (exec_res.reason or "") or "validation" in (exec_res.reason or "")

        # Assert: no push was executed
        assert not any(call[0] == "push_repos" for call in apply_ops.calls)

    def test_node_lockfile_neutral_lifecycle_success(self, tmp_path: Path) -> None:
        """Full lifecycle for neutral transformation `refresh-node-lockfile` with json_schema validation."""
        node_fixture_lockfile = (FIXTURES_DIR / "node_repo" / "package-lock.json").read_bytes()

        proposal = mutation_plan.build_proposal(
            id="prop-node-200",
            selection=["acme/node-repo"],
            transformation="refresh-node-lockfile",
            expected_shas={"acme/node-repo": "sha_node_base_200"},
            actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
            mutation_policy="allow-listed",
            bound_paths={"acme/node-repo": ["package-lock.json"]},
        )
        registry = mutation_plan.load_registry({
            "transformations": {
                "refresh-node-lockfile": {
                    "id": "refresh-node-lockfile",
                    "command_argv": ["npm", "install", "--package-lock-only"],
                    "applies_to": ["profile:nodejs"],
                    "validation": {
                        "kind": "json_schema",
                        "path": "package-lock.json",
                        "schema": {"type": "object", "required": ["lockfileVersion"]},
                    },
                    "allow_scheduled": False,
                }
            }
        })
        plan = pen_orchestrator.PenPlan(
            proposal=proposal,
            entry=registry.get("refresh-node-lockfile"),
            pen_name="nave/acceptance",
            query=nave_adapter.PenQuery(terms=[]),
        )

        runner = QueuedRunner(_exec_ok_sequence([("acme", "node-repo")]))
        apply_ops = RecordingApplyOps()

        def read_repo_head(repo: str) -> str:
            return "sha_node_base_200"

        def read_repo_file(repo: str, path: str) -> bytes:
            if repo == "acme/node-repo" and path == "package-lock.json":
                return node_fixture_lockfile
            raise FileNotFoundError(f"not found: {path}")

        exec_res = pen_orchestrator.execute(
            plan,
            runner,
            read_repo_head=read_repo_head,
            read_repo_file=read_repo_file,
            apply_ops=apply_ops,
        )

        assert exec_res.state == "pushed"
        assert [c[0] for c in apply_ops.calls] == ["provision_branch", "commit_repos", "push_repos"]

        # Reconcile PR & Merge
        ledger_path = _create_test_ledger(tmp_path, "run-node-200", "step-node", "acme/node-repo")
        result_path = tmp_path / "apply-status-node.yaml"
        gh_ops = FakeGhOps()

        apply_reconcile.open_apply_pr(
            ledger_path=ledger_path,
            step_id="step-node",
            proposal_id="prop-node-200",
            repo="acme/node-repo",
            branch="pulse/apply/prop-node-200",
            base="main",
            pushed_sha="sha_node_base_200",
            title="Apply refresh-node-lockfile prop-node-200",
            body="Automated node lockfile PR",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-node-200",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="sha_node_base_200",
            actor_id="octocat@laptop",
            workspace="acme",
        )

        gh_ops.prs[("acme/node-repo", "pulse/apply/prop-node-200")]["state"] = "MERGED"
        gh_ops.prs[("acme/node-repo", "pulse/apply/prop-node-200")]["merged"] = True
        gh_ops.prs[("acme/node-repo", "pulse/apply/prop-node-200")]["merge_commit_sha"] = "merged_sha_node_888"
        gh_ops.prs[("acme/node-repo", "pulse/apply/prop-node-200")]["head_ref"] = "sha_node_base_200"

        advance_calls: list[tuple[str, str]] = []

        def advance_base_fake(repo: str, merged_sha: str) -> dict[str, str]:
            advance_calls.append((repo, merged_sha))
            return {"state": "ok"}

        doc_final = apply_reconcile.reconcile_apply(
            ledger_path=ledger_path,
            step_id="step-node",
            proposal_id="prop-node-200",
            repo="acme/node-repo",
            branch="pulse/apply/prop-node-200",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-node-200",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="sha_node_base_200",
            advance_base=advance_base_fake,
            actor_id="octocat@laptop",
            workspace="acme",
        )

        assert doc_final["state"] == "applied"
        assert doc_final["merged_sha"] == "merged_sha_node_888"
        assert validate_result.validate(doc_final, "apply-status") == []
        assert advance_calls == [("acme/node-repo", "merged_sha_node_888")]


# --- Overlay Dogfood Suite --------------------------------------------------

class TestOverlayApplySuite:
    """Suite 2: Overlay dogfood transformations (`marketplace-entry-update`, Path B writes).

    Demonstrates that overlay transformations land through the EXACT SAME neutral
    machinery (`pen_orchestrator.execute`, `apply_reconcile`, `object_apply.apply_object_write`),
    maintaining strict two-suite discipline.
    """

    def test_overlay_marketplace_entry_update_path_a_lifecycle(self, tmp_path: Path) -> None:
        """Path A overlay transformation `marketplace-entry-update` lands via neutral apply machinery."""
        proposal = mutation_plan.build_proposal(
            id="prop-mkt-300",
            selection=["acme/plugin-repo"],
            transformation="marketplace-entry-update",
            expected_shas={"acme/plugin-repo": "sha_plugin_base_300"},
            actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
            mutation_policy="allow-listed",
            bound_paths={"acme/plugin-repo": [".hiivmind/marketplace-entry-patch.yaml"]},
        )
        registry = mutation_plan.load_registry({
            "transformations": {
                "marketplace-entry-update": {
                    "id": "marketplace-entry-update",
                    "command_argv": ["pulse-apply-marketplace-entry", "--patch", ".hiivmind/marketplace-entry-patch.yaml"],
                    "applies_to": ["profile:claude-plugin"],
                    "validation": {"kind": "none"},
                    "allow_scheduled": False,
                }
            }
        })
        plan = pen_orchestrator.PenPlan(
            proposal=proposal,
            entry=registry.get("marketplace-entry-update"),
            pen_name="nave/acceptance",
            query=nave_adapter.PenQuery(terms=[]),
        )

        runner = QueuedRunner(_exec_ok_sequence([("acme", "plugin-repo")]))
        apply_ops = RecordingApplyOps()

        def read_repo_head(repo: str) -> str:
            return "sha_plugin_base_300"

        exec_res = pen_orchestrator.execute(
            plan,
            runner,
            read_repo_head=read_repo_head,
            apply_ops=apply_ops,
        )

        assert exec_res.state == "pushed"
        assert apply_ops.calls[2] == ("push_repos", "pulse/apply/prop-mkt-300")

        # PR & Reconcile through same neutral machinery
        ledger_path = _create_test_ledger(tmp_path, "run-mkt-300", "step-mkt", "acme/plugin-repo")
        result_path = tmp_path / "apply-status-mkt.yaml"
        gh_ops = FakeGhOps()

        apply_reconcile.open_apply_pr(
            ledger_path=ledger_path,
            step_id="step-mkt",
            proposal_id="prop-mkt-300",
            repo="acme/plugin-repo",
            branch="pulse/apply/prop-mkt-300",
            base="main",
            pushed_sha="sha_plugin_base_300",
            title="Apply marketplace-entry-update prop-mkt-300",
            body="Automated marketplace entry PR",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-mkt-300",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="sha_plugin_base_300",
            actor_id="octocat@laptop",
            workspace="acme",
        )

        gh_ops.prs[("acme/plugin-repo", "pulse/apply/prop-mkt-300")]["state"] = "MERGED"
        gh_ops.prs[("acme/plugin-repo", "pulse/apply/prop-mkt-300")]["merged"] = True
        gh_ops.prs[("acme/plugin-repo", "pulse/apply/prop-mkt-300")]["merge_commit_sha"] = "merged_sha_mkt_777"
        gh_ops.prs[("acme/plugin-repo", "pulse/apply/prop-mkt-300")]["head_ref"] = "sha_plugin_base_300"

        advance_calls: list[tuple[str, str]] = []

        def advance_base_fake(repo: str, merged_sha: str) -> dict[str, str]:
            advance_calls.append((repo, merged_sha))
            return {"state": "ok"}

        doc_final = apply_reconcile.reconcile_apply(
            ledger_path=ledger_path,
            step_id="step-mkt",
            proposal_id="prop-mkt-300",
            repo="acme/plugin-repo",
            branch="pulse/apply/prop-mkt-300",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-mkt-300",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="sha_plugin_base_300",
            advance_base=advance_base_fake,
            actor_id="octocat@laptop",
            workspace="acme",
        )

        assert doc_final["state"] == "applied"
        assert doc_final["merged_sha"] == "merged_sha_mkt_777"
        assert validate_result.validate(doc_final, "apply-status") == []
        assert advance_calls == [("acme/plugin-repo", "merged_sha_mkt_777")]

    def test_overlay_marketplace_entry_path_b_object_write(self) -> None:
        """Path B object write for marketplace entry lands through neutral object_apply."""
        gh_ops = FakeObjectGhOps({"acme/plugin-repo#mkt": {"status": "pending"}})
        precondition = object_apply.Precondition(
            target="acme/plugin-repo#mkt", field="status", expected="pending"
        )
        write = object_apply.ObjectWrite(
            verb="update-field",
            target="acme/plugin-repo#mkt",
            payload={"field": "status", "value": "active"},
            precondition=precondition,
            desired="active",
        )

        # First execution applies write
        res1 = object_apply.apply_object_write(
            write,
            policy="allow-listed",
            mutation_allowlist=["update-field"],
            gh_ops=gh_ops,
        )
        assert res1["state"] == "applied"
        assert res1.get("noop") is False
        assert len(gh_ops.writes) == 1
        assert gh_ops.state["acme/plugin-repo#mkt"]["status"] == "active"

        # Repeat execution is idempotent no-op
        res2 = object_apply.apply_object_write(
            write,
            policy="allow-listed",
            mutation_allowlist=["update-field"],
            gh_ops=gh_ops,
        )
        assert res2["state"] == "applied"
        assert res2.get("noop") is True
        assert len(gh_ops.writes) == 1
