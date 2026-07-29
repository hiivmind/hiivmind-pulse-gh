"""Tests for object_apply.py — precondition-guarded, idempotent Path B GitHub object writes (F11 Task 7)."""

import pytest

from lib.pulse.scripts import object_apply


class FakeObjectGhOps(object_apply.ObjectGhOps):

    def __init__(self, initial_state: dict[str, dict[str, object]] | None = None) -> None:
        # store state as {target: {field: value}}
        self.state: dict[str, dict[str, object]] = initial_state or {}
        self.writes: list[object_apply.ObjectWrite] = []
        self.fail_get_state: bool = False
        self.fail_apply_write: bool = False

    def get_state(self, precondition: object_apply.Precondition) -> object:
        if self.fail_get_state:
            raise object_apply.GhExecutionError("simulated gh api execution failure")
        target_state = self.state.get(precondition.target, {})
        if precondition.field not in target_state:
            raise object_apply.GhExecutionError(
                f"field {precondition.field} not found for {precondition.target}"
            )
        return target_state[precondition.field]

    def apply_write(self, write: object_apply.ObjectWrite) -> dict[str, object]:
        if self.fail_apply_write:
            raise object_apply.GhExecutionError("simulated gh write failure")
        self.writes.append(write)
        target = write.target
        if target not in self.state:
            self.state[target] = {}

        field = write.payload.get("field") or write.precondition.field
        val = write.desired if write.desired is not None else write.payload.get("value")
        self.state[target][field] = val
        return {"state": "applied", "target": target, "field": field, "value": val}


def test_allow_listed_success_and_idempotent_repeat():
    gh_ops = FakeObjectGhOps({"org/repo#1": {"state": "open"}})
    precondition = object_apply.Precondition(
        target="org/repo#1", field="state", expected="open"
    )
    write = object_apply.ObjectWrite(
        verb="update-field",
        target="org/repo#1",
        payload={"field": "state", "value": "closed"},
        precondition=precondition,
        desired="closed",
    )

    # 1. First execution applies write
    res1 = object_apply.apply_object_write(
        write,
        policy="allow-listed",
        mutation_allowlist=["update-field"],
        gh_ops=gh_ops,
    )
    assert res1["state"] == "applied"
    assert res1.get("noop") is False
    assert len(gh_ops.writes) == 1
    assert gh_ops.state["org/repo#1"]["state"] == "closed"

    # 2. Repeat execution is idempotent no-op (no new write)
    res2 = object_apply.apply_object_write(
        write,
        policy="allow-listed",
        mutation_allowlist=["update-field"],
        gh_ops=gh_ops,
    )
    assert res2["state"] == "applied"
    assert res2.get("noop") is True
    assert len(gh_ops.writes) == 1


def test_precondition_mismatch_blocks():
    gh_ops = FakeObjectGhOps({"org/repo#1": {"state": "in_progress"}})
    precondition = object_apply.Precondition(
        target="org/repo#1", field="state", expected="open"
    )
    write = object_apply.ObjectWrite(
        verb="update-field",
        target="org/repo#1",
        payload={"field": "state", "value": "closed"},
        precondition=precondition,
        desired="closed",
    )

    res = object_apply.apply_object_write(
        write,
        policy="allow-listed",
        mutation_allowlist=["update-field"],
        gh_ops=gh_ops,
    )
    assert res["state"] == "blocked"
    assert "precondition mismatch" in res["reason"]
    assert len(gh_ops.writes) == 0


def test_verb_not_in_allowlist_proposed():
    gh_ops = FakeObjectGhOps({"org/repo#1": {"state": "open"}})
    precondition = object_apply.Precondition(
        target="org/repo#1", field="state", expected="open"
    )
    write = object_apply.ObjectWrite(
        verb="update-field",
        target="org/repo#1",
        payload={"field": "state", "value": "closed"},
        precondition=precondition,
        desired="closed",
    )

    res = object_apply.apply_object_write(
        write,
        policy="allow-listed",
        mutation_allowlist=["label", "comment"],
        gh_ops=gh_ops,
    )
    assert res["state"] == "proposed"
    assert res["action"] == "update-field org/repo#1"
    assert len(gh_ops.writes) == 0


def test_blocklisted_verb_blocked_unconditionally():
    gh_ops = FakeObjectGhOps({"org/repo": {"name": "repo"}})
    precondition = object_apply.Precondition(
        target="org/repo", field="name", expected="repo"
    )
    write = object_apply.ObjectWrite(
        verb="delete",
        target="org/repo",
        payload={},
        precondition=precondition,
    )

    for pol in ("allow-listed", "allow", "propose"):
        res = object_apply.apply_object_write(
            write,
            policy=pol,
            mutation_allowlist=["delete"],
            gh_ops=gh_ops,
        )
        assert res["state"] == "blocked"
        assert "operation blocklist" in res["reason"]
    assert len(gh_ops.writes) == 0


def test_allow_policy_blocked_in_v1():
    gh_ops = FakeObjectGhOps({"org/repo#1": {"state": "open"}})
    precondition = object_apply.Precondition(
        target="org/repo#1", field="state", expected="open"
    )
    write = object_apply.ObjectWrite(
        verb="update-field",
        target="org/repo#1",
        payload={"field": "state", "value": "closed"},
        precondition=precondition,
    )

    res = object_apply.apply_object_write(
        write,
        policy="allow",
        gh_ops=gh_ops,
    )
    assert res["state"] == "blocked"
    assert "allow is reserved and blocked in v1" in res["reason"]
    assert len(gh_ops.writes) == 0


def test_propose_policy_returns_proposed():
    gh_ops = FakeObjectGhOps({"org/repo#1": {"state": "open"}})
    precondition = object_apply.Precondition(
        target="org/repo#1", field="state", expected="open"
    )
    write = object_apply.ObjectWrite(
        verb="update-field",
        target="org/repo#1",
        payload={"field": "state", "value": "closed"},
        precondition=precondition,
    )

    res = object_apply.apply_object_write(
        write,
        policy="propose",
        gh_ops=gh_ops,
    )
    assert res["state"] == "proposed"
    assert res["action"] == "update-field org/repo#1"
    assert len(gh_ops.writes) == 0


def test_gh_execution_error_during_get_state_fails_safe():
    gh_ops = FakeObjectGhOps({"org/repo#1": {"state": "open"}})
    gh_ops.fail_get_state = True
    precondition = object_apply.Precondition(
        target="org/repo#1", field="state", expected="open"
    )
    write = object_apply.ObjectWrite(
        verb="update-field",
        target="org/repo#1",
        payload={"field": "state", "value": "closed"},
        precondition=precondition,
    )

    res = object_apply.apply_object_write(
        write,
        policy="allow-listed",
        mutation_allowlist=["update-field"],
        gh_ops=gh_ops,
    )
    assert res["state"] == "blocked"
    assert "precondition unconfirmable" in res["reason"]
    assert len(gh_ops.writes) == 0


def test_f8_demonstrator_apply_issue_field_patch():
    gh_ops = FakeObjectGhOps({"myorg/myrepo#42": {"milestone": "v1.0"}})

    res = object_apply.apply_issue_field_patch(
        issue_repo="myorg/myrepo",
        issue_number=42,
        field="milestone",
        target_value="v2.0",
        expected_value="v1.0",
        policy="allow-listed",
        mutation_allowlist=["update-field"],
        gh_ops=gh_ops,
    )

    assert res["state"] == "applied"
    assert res.get("noop") is False
    assert gh_ops.state["myorg/myrepo#42"]["milestone"] == "v2.0"
