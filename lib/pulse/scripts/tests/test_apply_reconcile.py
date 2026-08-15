"""Tests for apply_reconcile.py — resumable PR open, merge detection, and base advance (F11 Task 6)."""

import json
import pytest
import yaml

from lib.pulse.scripts import apply_reconcile
from lib.pulse.scripts import resolve_run
from lib.pulse.scripts import validate_result

PROPOSAL_DIGEST = "v1|" + "a" * 64
AUTHORIZATION_DIGEST = "v1|" + "b" * 64


class FakeGhOps(apply_reconcile.GhOps):

    def __init__(self):
        self.prs = {}
        self.remote_refs = {}
        self.deleted_branches = []
        self.delete_calls = []
        self.create_calls = 0
        self.view_calls = []

    def create_or_get_pr(
        self, repo: str, branch: str, base: str, title: str, body: str
    ) -> dict:
        key = (repo, branch)
        if key in self.prs and self.prs[key]["state"] == "OPEN":
            return {"url": self.prs[key]["url"], "created": False}
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

    def view_pr(self, repo: str, branch: str) -> dict:
        self.view_calls.append((repo, branch))
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
        if pr.get("state") == "ERROR":
            return {
                "state": "ERROR",
                "merged": False,
                "merge_commit_sha": None,
                "url": "",
                "error": pr.get("error", "simulated gh view_pr execution failure"),
                "observed_base": pr.get("base"),
                "observed_head_sha": pr.get("head_ref"),
            }
        return {
            "state": pr["state"],
            "merged": pr["merged"],
            "merge_commit_sha": pr["merge_commit_sha"],
            "url": pr["url"],
            "observed_base": pr.get("base"),
            "observed_head_sha": pr.get("head_ref"),
        }

    def delete_remote_branch(
        self, repo: str, branch: str, expected_sha: str
    ) -> dict:
        self.delete_calls.append((repo, branch, expected_sha))
        if not expected_sha:
            return {
                "state": "failed",
                "reason": "missing expected ref sha, refusing to delete",
            }
        key = (repo, branch)
        if key not in self.remote_refs:
            return {"state": "ok"}
        if self.remote_refs[key] != expected_sha:
            return {
                "state": "failed",
                "reason": "ref sha changed since observation, refusing to delete",
            }
        del self.remote_refs[key]
        self.deleted_branches.append((repo, branch))
        return {"state": "ok"}


def test_gh_cli_view_pr_returns_remote_base_and_head(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "state": "MERGED",
                        "mergedAt": "2026-07-30T00:00:00Z",
                        "mergeCommit": {"oid": "merged_sha_999"},
                        "url": "https://github.com/testorg/repo1/pull/1",
                        "baseRefName": "develop",
                        "headRefOid": "pushed_sha_111",
                    }
                ),
                "stderr": "",
            },
        )()

    monkeypatch.setattr(apply_reconcile.subprocess, "run", fake_run)

    doc = apply_reconcile.GhCliOps().view_pr(
        "testorg/repo1", "pulse/apply/prop-101"
    )

    json_fields = calls[0][0][calls[0][0].index("--json") + 1]
    assert json_fields == (
        "state,mergedAt,mergeCommit,url,baseRefName,headRefOid"
    )
    assert doc["observed_base"] == "develop"
    assert doc["observed_head_sha"] == "pushed_sha_111"


def test_gh_cli_delete_remote_branch_deletes_only_matching_ref(monkeypatch):
    calls = []
    responses = iter(
        [
            type(
                "Result",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps({"object": {"sha": "observed_sha"}}),
                    "stderr": "",
                },
            )(),
            type(
                "Result",
                (),
                {"returncode": 0, "stdout": "", "stderr": ""},
            )(),
        ]
    )

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return next(responses)

    monkeypatch.setattr(apply_reconcile.subprocess, "run", fake_run)

    result = apply_reconcile.GhCliOps().delete_remote_branch(
        "testorg/repo1", "pulse/apply/prop-101", "observed_sha"
    )

    endpoint = "repos/testorg/repo1/git/refs/heads/pulse/apply/prop-101"
    assert result == {"state": "ok"}
    assert calls[0][0] == ["gh", "api", endpoint]
    assert calls[1][0] == ["gh", "api", "-X", "DELETE", endpoint]


def test_gh_cli_delete_remote_branch_refuses_changed_ref(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"object": {"sha": "replacement_sha"}}),
                "stderr": "",
            },
        )()

    monkeypatch.setattr(apply_reconcile.subprocess, "run", fake_run)

    result = apply_reconcile.GhCliOps().delete_remote_branch(
        "testorg/repo1", "pulse/apply/prop-101", "observed_sha"
    )

    assert result == {
        "state": "failed",
        "reason": "ref sha changed since observation, refusing to delete",
    }
    assert len(calls) == 1


def test_gh_cli_delete_remote_branch_treats_missing_ref_as_success(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return type(
            "Result",
            (),
            {"returncode": 1, "stdout": "", "stderr": "gh: Not Found (HTTP 404)"},
        )()

    monkeypatch.setattr(apply_reconcile.subprocess, "run", fake_run)

    result = apply_reconcile.GhCliOps().delete_remote_branch(
        "testorg/repo1", "pulse/apply/prop-101", "observed_sha"
    )

    assert result == {"state": "ok"}
    assert len(calls) == 1


def create_test_ledger(tmp_path, step_id="reconcile-repo1"):
    steps = json.dumps([
        {
            "id": step_id,
            "repo": "testorg/repo1",
            "gate": "merge_detected",
            "has_workflow": True,
        }
    ])
    r = resolve_run.cmd_create(
        type(
            "Args",
            (),
            {
                "runs_dir": str(tmp_path),
                "workflow": "apply-reconcile",
                "run_id": "2026-07-29-octocat-120000",
                "actor_login": "octocat",
                "actor_machine": "mba-m4",
                "mode": "interactive",
                "params": "{}",
                "repos": "testorg/repo1",
                "steps": steps,
                "local": True,
            },
        )()
    )
    return tmp_path / "local" / "apply-reconcile-2026-07-29-octocat-120000.yaml"


def test_open_apply_pr_creates_and_reuses_pr(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    doc = apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "pr_opened"
    assert doc["repos"]["testorg/repo1"]["pushed_sha"] == "pushed_sha_111"
    assert doc["repos"]["testorg/repo1"]["pr_url"] == "https://github.com/testorg/repo1/pull/1"
    assert validate_result.validate(doc, "apply-status") == []
    assert gh_ops.create_calls == 1

    doc2 = apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc2["repos"]["testorg/repo1"]["pr_url"] == doc["repos"]["testorg/repo1"]["pr_url"]
    assert gh_ops.create_calls == 1

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "blocked-on-gate"


def test_open_apply_pr_rejects_mismatched_actual_and_audited_base(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    gh_ops = FakeGhOps()

    with pytest.raises(
        ValueError,
        match="the PR's actual base must match the audited intended base",
    ):
        apply_reconcile.open_apply_pr(
            ledger_path=ledger_path,
            step_id="reconcile-repo1",
            proposal_id="prop-101",
            repo="testorg/repo1",
            branch="pulse/apply/prop-101",
            base="develop",
            pushed_sha="pushed_sha_111",
            title="Apply proposal prop-101",
            body="Automated apply PR",
            result_path=tmp_path / "apply-status-repo1.yaml",
            gh_ops=gh_ops,
            recorded_proposal_id="prop-101",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_111",
            actor_id="octocat@mba-m4",
            workspace="testorg",
        )

    assert gh_ops.create_calls == 0


def test_open_apply_pr_uses_token_and_does_not_reacquire(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()
    lease = resolve_run.acquire_lease(
        ledger_path, "reconcile-repo1", "octocat@mba-m4"
    )

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        token=lease["token"],
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["lease"]["token"] == lease["token"]
    assert gh_ops.create_calls == 1


def test_snapshot_audit_writes_ledger_state_snapshot(tmp_path):
    ledger_path = create_test_ledger(tmp_path)

    resolve_run.snapshot_audit(
        ledger_path,
        "reconcile-repo1",
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
    )

    ledger_doc = resolve_run.load(ledger_path)
    snapshot = ledger_doc["state_snapshot"]["reconcile-repo1"]
    assert snapshot["recorded_proposal_id"] == "prop-101"
    assert snapshot["proposal_digest"] == PROPOSAL_DIGEST
    assert snapshot["authorization_digest"] == AUTHORIZATION_DIGEST
    assert snapshot["policy_version"] == "v1"
    assert snapshot["run_at"]
    assert snapshot["actor"] == ledger_doc["actor"]


def test_reconcile_open_pr_withholds_base(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    advance_calls = []

    def advance_fake(r, s):
        advance_calls.append((r, s))
        return {"state": "ok"}

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=advance_fake,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "pr_opened"
    assert advance_calls == []

    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "blocked-on-gate"


def test_reconcile_gh_error_withholds_and_does_not_delete_branch(tmp_path):
    """Critical fix: transient gh view_pr error must NOT trigger branch deletion or terminal failure."""
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    # Simulate network outage / rate limit failure on gh view_pr
    gh_ops.prs[("testorg/repo1", "pulse/apply/prop-101")] = {
        "state": "ERROR",
        "error": "rate limit exceeded",
    }

    advance_calls = []

    def advance_fake(r, s):
        advance_calls.append((r, s))
        return {"state": "ok"}

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=advance_fake,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    # Step must WITHHOLD: status remains blocked-on-gate, branch NOT deleted, run NOT failed
    assert doc["state"] == "pr_opened"
    assert gh_ops.deleted_branches == []
    assert advance_calls == []

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "blocked-on-gate"
    assert ledger_doc["status"] == "blocked-on-gate"
    assert any("rate limit" in note for note in step["notes"])


def test_reconcile_gh_error_without_status_fails_closed(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()
    gh_ops.prs[("testorg/repo1", "pulse/apply/prop-101")] = {
        "state": "ERROR",
        "error": "rate limit exceeded",
    }

    with pytest.raises(ValueError, match="cannot determine PR state"):
        apply_reconcile.reconcile_apply(
            ledger_path=ledger_path,
            step_id="reconcile-repo1",
            proposal_id="prop-101",
            repo="testorg/repo1",
            branch="pulse/apply/prop-101",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-101",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_111",
            actor_id="octocat@mba-m4",
            workspace="testorg",
        )

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert not result_path.exists()
    assert step["status"] == "blocked-on-gate"
    assert any("rate limit exceeded" in note for note in step["notes"])


def test_reconcile_merged_pr_advances_base_off_merged_sha(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key]["state"] = "MERGED"
    gh_ops.prs[key]["merged"] = True
    gh_ops.prs[key]["merge_commit_sha"] = "merged_commit_sha_999"
    gh_ops.prs[key]["head_ref"] = "pushed_sha_111"

    advance_calls = []

    def advance_fake(r, s):
        advance_calls.append((r, s))
        return {"state": "ok"}

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=advance_fake,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "applied"
    assert doc["repos"]["testorg/repo1"]["merged_sha"] == "merged_commit_sha_999"
    assert doc["repos"]["testorg/repo1"]["observed_base"] == "main"
    assert doc["repos"]["testorg/repo1"]["observed_head_sha"] == "pushed_sha_111"
    assert validate_result.validate(doc, "apply-status") == []

    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is True
    assert "merged_commit_sha_999" in detail

    assert advance_calls == [("testorg/repo1", "merged_commit_sha_999")]

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "done"


def test_reconcile_merged_pr_wrong_base_rejects(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )
    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key]["state"] = "MERGED"
    gh_ops.prs[key]["merged"] = True
    gh_ops.prs[key]["merge_commit_sha"] = "merged_commit_sha_999"
    gh_ops.prs[key]["base"] = "develop"
    gh_ops.prs[key]["head_ref"] = "pushed_sha_111"
    gh_ops.remote_refs[key] = "pushed_sha_111"
    advance_calls = []

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert doc["state"] == "rejected"
    assert "observed_base=develop" in doc["repos"]["testorg/repo1"]["reason"]
    assert gh_ops.deleted_branches == [("testorg/repo1", "pulse/apply/prop-101")]
    assert gh_ops.delete_calls == [
        ("testorg/repo1", "pulse/apply/prop-101", "pushed_sha_111")
    ]
    assert step["status"] == "failed"
    assert any("deleted branch pulse/apply/prop-101" in note for note in step["notes"])
    assert advance_calls == []


def test_reconcile_merged_pr_wrong_head_rejects(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )
    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key]["state"] = "MERGED"
    gh_ops.prs[key]["merged"] = True
    gh_ops.prs[key]["merge_commit_sha"] = "merged_commit_sha_999"
    gh_ops.prs[key]["head_ref"] = "other_sha"
    gh_ops.remote_refs[key] = "replacement_sha"
    advance_calls = []

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert doc["state"] == "rejected"
    assert "observed_head_sha=other_sha" in doc["repos"]["testorg/repo1"]["reason"]
    assert gh_ops.delete_calls == [
        ("testorg/repo1", "pulse/apply/prop-101", "other_sha")
    ]
    assert gh_ops.deleted_branches == []
    assert step["status"] == "failed"
    assert any("refused: sha mismatch" in note for note in step["notes"])
    assert not any("deleted branch" in note for note in step["notes"])
    assert advance_calls == []


def test_reconcile_merge_gate_failure_rejects(tmp_path, monkeypatch):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )
    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key]["state"] = "MERGED"
    gh_ops.prs[key]["merged"] = True
    gh_ops.prs[key]["merge_commit_sha"] = "merged_commit_sha_999"
    gh_ops.prs[key]["head_ref"] = "pushed_sha_111"
    monkeypatch.setattr(
        resolve_run,
        "evaluate_merge_detected_gate",
        lambda path, repo=None: (False, "simulated merge gate failure"),
    )
    advance_calls = []

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert doc["state"] == "rejected"
    assert doc["repos"]["testorg/repo1"]["reason"] == "simulated merge gate failure"
    assert step["status"] == "failed"
    assert advance_calls == []


def test_reconcile_applied_crash_recovery(tmp_path):
    """Important 1 fix: crash after writing applied status but before advance_base finishes resume execution."""
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    # Pre-write an applied status file, but ledger step is still blocked-on-gate (simulating a crash)
    apply_reconcile.write_apply_status(
        result_path,
        proposal_id="prop-101",
        selection=["testorg/repo1"],
        repos={
            "testorg/repo1": {
                "branch": "pulse/apply/prop-101",
                "state": "applied",
                "intended_base": "main",
                "expected_head_sha": "pushed_sha_111",
                "observed_base": "main",
                "observed_head_sha": "pushed_sha_111",
                "pushed_sha": "pushed_sha_111",
                "pr_url": "https://github.com/testorg/repo1/pull/1",
                "merged_sha": "merged_commit_sha_777",
                "reason": None,
            },
        },
        state="applied",
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        workspace="testorg",
    )

    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key] = {
        "url": "https://github.com/testorg/repo1/pull/1",
        "state": "MERGED",
        "merged": True,
        "merge_commit_sha": "merged_commit_sha_777",
        "base": "main",
        "head_ref": "pushed_sha_111",
    }

    advance_calls = []

    def advance_fake(r, s):
        advance_calls.append((r, s))
        return {"state": "ok"}

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=advance_fake,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "applied"
    assert advance_calls == [("testorg/repo1", "merged_commit_sha_777")]
    assert gh_ops.view_calls == [("testorg/repo1", "pulse/apply/prop-101")]

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "done"


def test_reconcile_advance_base_failure_keeps_step_blocked(tmp_path):
    """Important 2 fix: advance_base failure must NOT mark step done."""
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key]["state"] = "MERGED"
    gh_ops.prs[key]["merged"] = True
    gh_ops.prs[key]["merge_commit_sha"] = "merged_commit_sha_999"
    gh_ops.prs[key]["head_ref"] = "pushed_sha_111"

    def failing_advance(r, s):
        return {"state": "failed", "reason": "git push rejected"}

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=failing_advance,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "applied"
    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "blocked-on-gate"
    assert any("git push rejected" in note for note in step["notes"])


def test_reconcile_closed_unmerged_pr_rejects_and_deletes_branch(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key]["state"] = "CLOSED"
    gh_ops.prs[key]["merged"] = False
    gh_ops.remote_refs[key] = "pushed_sha_111"

    advance_calls = []

    def advance_fake(r, s):
        advance_calls.append((r, s))
        return {"state": "ok"}

    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=advance_fake,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "rejected"
    assert doc["repos"]["testorg/repo1"]["reason"] is not None
    assert validate_result.validate(doc, "apply-status") == []
    assert advance_calls == []
    assert gh_ops.deleted_branches == [("testorg/repo1", "pulse/apply/prop-101")]
    assert gh_ops.delete_calls == [
        ("testorg/repo1", "pulse/apply/prop-101", "pushed_sha_111")
    ]

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "failed"
    assert ledger_doc["status"] == "failed"


def test_reconcile_applied_step_is_idempotent_noop(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    key = ("testorg/repo1", "pulse/apply/prop-101")
    gh_ops.prs[key]["state"] = "MERGED"
    gh_ops.prs[key]["merged"] = True
    gh_ops.prs[key]["merge_commit_sha"] = "merged_commit_sha_999"
    gh_ops.prs[key]["head_ref"] = "pushed_sha_111"

    advance_calls = []

    def advance_fake(r, s):
        advance_calls.append((r, s))
        return {"state": "ok"}

    apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=advance_fake,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )
    assert len(advance_calls) == 1

    doc2 = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        advance_base=advance_fake,
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )
    assert doc2["state"] == "applied"
    assert len(advance_calls) == 1  # Idempotent: no duplicate advance!
    assert gh_ops.view_calls == [
        ("testorg/repo1", "pulse/apply/prop-101"),
        ("testorg/repo1", "pulse/apply/prop-101"),
    ]


def test_lease_concurrency_blocks_second_actor(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    gh_ops = FakeGhOps()

    apply_reconcile.open_apply_pr(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        base="main",
        pushed_sha="pushed_sha_111",
        title="Apply proposal prop-101",
        body="Automated apply PR",
        result_path=result_path,
        gh_ops=gh_ops,
        recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
        intended_base="main",
        expected_head_sha="pushed_sha_111",
        actor_id="actor1@machine1",
        workspace="testorg",
    )

    with pytest.raises(resolve_run.LeaseError):
        apply_reconcile.reconcile_apply(
            ledger_path=ledger_path,
            step_id="reconcile-repo1",
            proposal_id="prop-101",
            repo="testorg/repo1",
            branch="pulse/apply/prop-101",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-101",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_111",
            advance_base=lambda repo, sha: {"state": "ok"},
            actor_id="actor2@machine2",
            workspace="testorg",
        )


def test_resolve_intended_base_plan_sync_prefers_finalizer_record():
    assert apply_reconcile.resolve_intended_base(
        "plan-sync",
        {"base_ref": "binding-base"},
        {"base_ref": "finalizer-base"},
    ) == "finalizer-base"
    assert apply_reconcile.resolve_intended_base(
        "plan-sync", {"base_ref": "binding-base"}
    ) == "binding-base"


def test_resolve_intended_base_generated_artifact_uses_branch():
    assert apply_reconcile.resolve_intended_base(
        "generated-artifact",
        {"branch": "release"},
    ) == "release"


def test_resolve_intended_base_marketplace_sync_uses_finalizer_record():
    assert apply_reconcile.resolve_intended_base(
        "marketplace-sync", {}, {"base_ref": "develop"}
    ) == "develop"


@pytest.mark.parametrize(
    "source_kind",
    ["plan-sync", "generated-artifact", "marketplace-sync"],
)
def test_resolve_intended_base_rejects_missing_base(source_kind):
    with pytest.raises(ValueError, match="cannot resolve intended base"):
        apply_reconcile.resolve_intended_base(source_kind, {})


def test_resolve_intended_base_rejects_unknown_source_kind():
    with pytest.raises(ValueError):
        apply_reconcile.resolve_intended_base("unknown", {"base": "main"})


@pytest.mark.parametrize("contents", ["state: [\n", "- not\n- a mapping\n"])
def test_load_apply_status_rejects_corrupt_or_non_mapping(tmp_path, contents):
    result_path = tmp_path / "apply-status.yaml"
    result_path.write_text(contents)

    with pytest.raises(ValueError, match="could not load apply status"):
        apply_reconcile.load_apply_status(result_path)


def test_load_apply_status_rejects_valid_mapping_missing_required_fields(tmp_path):
    """A valid-YAML, valid-dict document that is still schema-invalid (e.g.
    truncated mid-write, or hand-edited) must fail closed the same as
    malformed YAML - `isinstance(dict)` alone is not enough evidence to
    trust a status document."""
    result_path = tmp_path / "apply-status.yaml"
    result_path.write_text(yaml.safe_dump({"state": "applied"}))

    with pytest.raises(ValueError, match="could not load apply status"):
        apply_reconcile.load_apply_status(result_path)


def test_open_apply_pr_fails_closed_on_schema_invalid_existing_status(tmp_path):
    """open_apply_pr must not treat a schema-invalid existing status as
    proof a PR already exists and skip creating one."""
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    result_path.write_text(yaml.safe_dump({"state": "applied"}))
    gh_ops = FakeGhOps()

    with pytest.raises(ValueError, match="could not load apply status"):
        apply_reconcile.open_apply_pr(
            ledger_path=ledger_path,
            step_id="reconcile-repo1",
            proposal_id="prop-101",
            repo="testorg/repo1",
            branch="pulse/apply/prop-101",
            base="main",
            pushed_sha="pushed_sha_111",
            title="Apply proposal prop-101",
            body="Automated apply PR",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-101",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_111",
            actor_id="octocat@mba-m4",
            workspace="testorg",
        )

    assert gh_ops.create_calls == 0


def test_reconcile_corrupt_status_fails_closed_before_remote_view(tmp_path):
    ledger_path = create_test_ledger(tmp_path)
    result_path = tmp_path / "apply-status-repo1.yaml"
    result_path.write_text("state: [\n")
    gh_ops = FakeGhOps()

    with pytest.raises(ValueError, match="could not load apply status"):
        apply_reconcile.reconcile_apply(
            ledger_path=ledger_path,
            step_id="reconcile-repo1",
            proposal_id="prop-101",
            repo="testorg/repo1",
            branch="pulse/apply/prop-101",
            result_path=result_path,
            gh_ops=gh_ops,
            recorded_proposal_id="prop-101",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
            intended_base="main",
            expected_head_sha="pushed_sha_111",
            actor_id="octocat@mba-m4",
            workspace="testorg",
        )

    assert gh_ops.view_calls == []
    assert result_path.read_text() == "state: [\n"


def test_atomic_apply_status_write_fsyncs_file_and_directory(tmp_path, monkeypatch):
    result_path = tmp_path / "apply-status.yaml"
    fsync_calls = []
    replace_calls = []
    real_replace = apply_reconcile.os.replace

    def record_fsync(fd):
        fsync_calls.append(fd)

    def record_replace(source, destination):
        replace_calls.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(apply_reconcile.os, "fsync", record_fsync)
    monkeypatch.setattr(apply_reconcile.os, "replace", record_replace)

    apply_reconcile._atomic_write_yaml(result_path, {"state": "ok"})

    assert yaml.safe_load(result_path.read_text()) == {"state": "ok"}
    assert len(fsync_calls) == 2
    assert replace_calls and replace_calls[0][1] == result_path
    assert not list(tmp_path.glob(f".{result_path.name}.*.tmp"))


def test_atomic_apply_status_write_preserves_existing_file_on_replace_error(
    tmp_path, monkeypatch
):
    result_path = tmp_path / "apply-status.yaml"
    result_path.write_text("state: old\n")

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(apply_reconcile.os, "replace", fail_replace)

    with pytest.raises(ValueError, match="could not write apply status"):
        apply_reconcile._atomic_write_yaml(result_path, {"state": "new"})

    assert result_path.read_text() == "state: old\n"
    assert not list(tmp_path.glob(f".{result_path.name}.*.tmp"))


def test_merge_detected_gate_evaluator_fail_closed(tmp_path):
    result_path = tmp_path / "apply-status.yaml"

    def write(state, **entry_fields):
        entry = {
            "branch": "b1",
            "state": state,
            "intended_base": "main",
            "expected_head_sha": "sha1",
            "pushed_sha": "sha1",
            "pr_url": "https://pr1",
            "merged_sha": None,
            "observed_base": None,
            "observed_head_sha": None,
            "reason": None,
        }
        entry.update(entry_fields)
        apply_reconcile.write_apply_status(
            result_path,
            proposal_id="p1",
            selection=["acme/r1"],
            repos={"acme/r1": entry},
            state=state,
            recorded_proposal_id="p1",
            proposal_digest=PROPOSAL_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
        )

    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False

    write("pr_opened")
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False

    write("rejected", reason="closed")
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False

    write("applied", observed_base="main", observed_head_sha="sha1",
          merged_sha="sha_merged_456")
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is True
    assert "sha_merged_456" in detail

    write("applied", observed_base="develop", observed_head_sha="sha1",
          merged_sha="sha_merged_456")
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False
    assert "observed_base" in detail

    write("applied", observed_base="main", observed_head_sha="other_sha",
          merged_sha="sha_merged_456")
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False
    assert "observed_head_sha" in detail


def test_resolve_intended_base_neutral_uses_binding_base_ref():
    assert apply_reconcile.resolve_intended_base(
        "neutral", {"repo": "hiivmind/a", "base_ref": "main"}, None
    ) == {"hiivmind/a": "main"}
    assert apply_reconcile.resolve_intended_base(
        "neutral",
        {"repos": ["hiivmind/a", "hiivmind/b"], "base_ref": "main"},
        None,
    ) == {"hiivmind/a": "main", "hiivmind/b": "main"}


def test_resolve_intended_base_neutral_rejects_missing_base_ref():
    with pytest.raises(ValueError, match="cannot resolve intended base for neutral"):
        apply_reconcile.resolve_intended_base("neutral", {"repo": "hiivmind/a"}, None)
    with pytest.raises(ValueError, match="cannot resolve intended base for neutral"):
        apply_reconcile.resolve_intended_base("neutral", {"repos": ["hiivmind/a"]}, None)


def test_rollup_state_precedence():
    def repo(state):
        return {"state": state, "branch": "b", "intended_base": "main",
                "expected_head_sha": "s", "pushed_sha": "s", "pr_url": None,
                "merged_sha": None, "observed_base": None, "observed_head_sha": None,
                "reason": None}

    assert apply_reconcile.rollup_state({"a": repo("pr_opened"), "b": repo("applied")}) == "pr_opened"
    assert apply_reconcile.rollup_state({"a": repo("applied"), "b": repo("applied")}) == "applied"
    assert apply_reconcile.rollup_state({"a": repo("rejected"), "b": repo("rejected")}) == "rejected"
    assert apply_reconcile.rollup_state({"a": repo("failed"), "b": repo("blocked")}) == "failed"
    assert apply_reconcile.rollup_state({"a": repo("applied"), "b": repo("failed")}) == "partial"


def test_write_and_load_multi_repo_status_round_trip(tmp_path):
    repos = {
        "hiivmind/a": {"branch": "pulse/apply/x", "state": "pr_opened",
                       "intended_base": "main", "expected_head_sha": "sha-a",
                       "pushed_sha": "sha-a", "pr_url": "https://x/a/1",
                       "merged_sha": None, "observed_base": None,
                       "observed_head_sha": None, "reason": None},
        "hiivmind/b": {"branch": "pulse/apply/x", "state": "applied",
                       "intended_base": "main", "expected_head_sha": "sha-b",
                       "pushed_sha": "sha-b", "pr_url": "https://x/b/1",
                       "merged_sha": "merge-b", "observed_base": "main",
                       "observed_head_sha": "sha-b", "reason": None},
    }
    path = tmp_path / "result.yaml"
    apply_reconcile.write_apply_status(
        path, proposal_id="pid", selection=["hiivmind/a", "hiivmind/b"],
        repos=repos, state=apply_reconcile.rollup_state(repos),
        recorded_proposal_id="pid", proposal_digest="d1",
        authorization_digest="d2", workspace="w",
        actor={"gh_login": "x", "machine": "m", "mode": "interactive"},
    )
    loaded = apply_reconcile.load_apply_status(path)
    assert loaded["repos"] == repos
    assert loaded["selection"] == ["hiivmind/a", "hiivmind/b"]
    assert loaded["state"] == "pr_opened"


def test_load_normalizes_v1_single_repo(tmp_path):
    v1 = {
        "contract_version": 1, "kind": "apply-status", "state": "pr_opened",
        "workspace": "w", "run_at": "2026-01-01T00:00:00Z",
        "actor": {"gh_login": "x", "machine": "m", "mode": "interactive"},
        "errors": [],
        "proposal_id": "pid", "recorded_proposal_id": "pid",
        "proposal_digest": "d1", "authorization_digest": "d2",
        "selection": ["hiivmind/a"], "branch": "pulse/apply/x",
        "pushed_sha": "sha", "pr_url": "https://x/a/1", "merged_sha": None,
        "reason": None, "intended_base": "main", "expected_head_sha": "sha",
        "observed_base": None, "observed_head_sha": None,
    }
    path = tmp_path / "result.yaml"
    path.write_text(yaml.safe_dump(v1))
    loaded = apply_reconcile.load_apply_status(path)
    assert loaded["selection"] == ["hiivmind/a"]
    assert loaded["repos"]["hiivmind/a"]["branch"] == "pulse/apply/x"


def test_reconcile_repos_iterates_and_rolls_up(tmp_path):
    ledger_path = create_test_ledger(tmp_path, step_id="reconcile-repo1")
    result_path = tmp_path / "apply-status.yaml"
    gh_ops = FakeGhOps()

    repos = {
        "testorg/repo1": {"branch": "pulse/apply/p", "state": "pr_opened",
                          "intended_base": "main", "expected_head_sha": "sha1",
                          "pushed_sha": "sha1", "pr_url": "https://x/1",
                          "merged_sha": None, "observed_base": None,
                          "observed_head_sha": None, "reason": None},
        "testorg/repo2": {"branch": "pulse/apply/p", "state": "pr_opened",
                          "intended_base": "main", "expected_head_sha": "sha2",
                          "pushed_sha": "sha2", "pr_url": "https://x/2",
                          "merged_sha": None, "observed_base": None,
                          "observed_head_sha": None, "reason": None},
    }
    apply_reconcile.write_apply_status(
        result_path, proposal_id="prop-101",
        selection=["testorg/repo1", "testorg/repo2"], repos=repos,
        state="pr_opened", recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST, authorization_digest=AUTHORIZATION_DIGEST,
        workspace="testorg",
        actor={"gh_login": "octocat", "machine": "mba-m4", "mode": "interactive"},
    )
    # repo1 merged; repo2 still open.
    gh_ops.prs[("testorg/repo1", "pulse/apply/p")] = {
        "url": "https://x/1", "state": "MERGED", "merged": True,
        "merge_commit_sha": "merge1", "base": "main", "head_ref": "sha1",
    }
    gh_ops.prs[("testorg/repo2", "pulse/apply/p")] = {
        "url": "https://x/2", "state": "OPEN", "merged": False,
        "merge_commit_sha": None, "base": "main", "head_ref": "sha2",
    }

    doc = apply_reconcile.reconcile_repos(
        ledger_path=ledger_path, step_id="reconcile-repo1", result_path=result_path,
        gh_ops=gh_ops, recorded_proposal_id="prop-101",
        proposal_digest=PROPOSAL_DIGEST, authorization_digest=AUTHORIZATION_DIGEST,
        actor_id="octocat@mba-m4", workspace="testorg",
    )
    assert doc["repos"]["testorg/repo1"]["state"] == "applied"
    assert doc["repos"]["testorg/repo1"]["merged_sha"] == "merge1"
    assert doc["repos"]["testorg/repo2"]["state"] == "pr_opened"
    assert doc["state"] == "pr_opened"
    # Fleet terminal: the step is done only when every repo is applied.
    step = resolve_run.find_step(resolve_run.load(ledger_path), "reconcile-repo1")
    assert step["status"] == "blocked-on-gate"
