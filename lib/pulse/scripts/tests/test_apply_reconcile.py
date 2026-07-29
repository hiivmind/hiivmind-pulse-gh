"""Tests for apply_reconcile.py — resumable PR open, merge detection, and base advance (F11 Task 6)."""

import json
import pytest
import yaml

from lib.pulse.scripts import apply_reconcile
from lib.pulse.scripts import resolve_run
from lib.pulse.scripts import validate_result


class FakeGhOps(apply_reconcile.GhOps):

    def __init__(self):
        self.prs = {}
        self.deleted_branches = []
        self.create_calls = 0

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
            "title": title,
            "body": body,
        }
        return {"url": url, "created": True}

    def view_pr(self, repo: str, branch: str) -> dict:
        key = (repo, branch)
        if key not in self.prs:
            return {
                "state": "CLOSED",
                "merged": False,
                "merge_commit_sha": None,
                "url": "",
            }
        pr = self.prs[key]
        return {
            "state": pr["state"],
            "merged": pr["merged"],
            "merge_commit_sha": pr["merge_commit_sha"],
            "url": pr["url"],
        }

    def delete_remote_branch(self, repo: str, branch: str) -> dict:
        self.deleted_branches.append((repo, branch))
        return {"state": "ok"}


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
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "pr_opened"
    assert doc["pushed_sha"] == "pushed_sha_111"
    assert doc["pr_url"] == "https://github.com/testorg/repo1/pull/1"
    assert validate_result.validate(doc, "apply-status") == []
    assert gh_ops.create_calls == 1

    # Second pass reuses PR without creating duplicate
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
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc2["pr_url"] == doc["pr_url"]
    assert gh_ops.create_calls == 1

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "blocked-on-gate"


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
        actor_id="octocat@mba-m4",
        workspace="testorg",
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
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
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
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    # Mark PR merged in fake
    gh_ops.prs[("testorg/repo1", "pulse/apply/prop-101")] = {
        "url": "https://github.com/testorg/repo1/pull/1",
        "state": "MERGED",
        "merged": True,
        "merge_commit_sha": "merged_commit_sha_999",
        "base": "main",
        "title": "Apply proposal prop-101",
        "body": "Automated apply PR",
    }

    advance_calls = []
    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "applied"
    assert doc["merged_sha"] == "merged_commit_sha_999"
    assert validate_result.validate(doc, "apply-status") == []

    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is True
    assert "merged_commit_sha_999" in detail

    assert advance_calls == [("testorg/repo1", "merged_commit_sha_999")]

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, "reconcile-repo1")
    assert step["status"] == "done"


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
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    # Mark PR closed unmerged
    gh_ops.prs[("testorg/repo1", "pulse/apply/prop-101")]["state"] = "CLOSED"
    gh_ops.prs[("testorg/repo1", "pulse/apply/prop-101")]["merged"] = False

    advance_calls = []
    doc = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    assert doc["state"] == "rejected"
    assert doc["reason"] is not None
    assert validate_result.validate(doc, "apply-status") == []
    assert advance_calls == []
    assert gh_ops.deleted_branches == [("testorg/repo1", "pulse/apply/prop-101")]

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
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )

    gh_ops.prs[("testorg/repo1", "pulse/apply/prop-101")] = {
        "url": "https://github.com/testorg/repo1/pull/1",
        "state": "MERGED",
        "merged": True,
        "merge_commit_sha": "merged_commit_sha_999",
        "base": "main",
        "title": "Apply proposal prop-101",
        "body": "Automated apply PR",
    }

    advance_calls = []
    apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )
    assert len(advance_calls) == 1

    # Re-run on already applied step
    doc2 = apply_reconcile.reconcile_apply(
        ledger_path=ledger_path,
        step_id="reconcile-repo1",
        proposal_id="prop-101",
        repo="testorg/repo1",
        branch="pulse/apply/prop-101",
        result_path=result_path,
        gh_ops=gh_ops,
        advance_base=lambda repo, sha: advance_calls.append((repo, sha)),
        actor_id="octocat@mba-m4",
        workspace="testorg",
    )
    assert doc2["state"] == "applied"
    assert len(advance_calls) == 1  # No duplicate advance!


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
            advance_base=lambda repo, sha: None,
            actor_id="actor2@machine2",
            workspace="testorg",
        )


def test_merge_detected_gate_evaluator_fail_closed(tmp_path):
    result_path = tmp_path / "apply-status.yaml"

    # Missing file
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False

    # State pr_opened
    apply_reconcile.write_apply_status(
        result_path,
        proposal_id="p1",
        repo="r1",
        branch="b1",
        state="pr_opened",
        pushed_sha="sha1",
        pr_url="https://pr1",
    )
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False

    # State rejected
    apply_reconcile.write_apply_status(
        result_path,
        proposal_id="p1",
        repo="r1",
        branch="b1",
        state="rejected",
        reason="closed",
    )
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is False

    # State applied with merged_sha
    apply_reconcile.write_apply_status(
        result_path,
        proposal_id="p1",
        repo="r1",
        branch="b1",
        state="applied",
        pushed_sha="sha1",
        pr_url="https://pr1",
        merged_sha="sha_merged_456",
    )
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
    assert satisfied is True
    assert "sha_merged_456" in detail
