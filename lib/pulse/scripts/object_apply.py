#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Precondition-guarded, idempotent Path B GitHub object writes under on_mutation policy (F11 Task 7).

Independence Notice (B4):
-------------------------
Path B (GitHub-object apply) is completely independent of Path A (doc-pen apply).
``object_apply`` knows nothing about pens, branches, or PRs. A Path A doc-pen push
failure does not block an object write, and vice-versa.

Emitter Integration Points:
---------------------------
1. F8 Issue Field Patch (Concrete Demonstrator):
   Use ``apply_issue_field_patch(issue_repo, issue_number, field, target_value, expected_value, ...)``
   or construct ``ObjectWrite(verb="update-field", target=f"{issue_repo}#{issue_number}", payload=..., precondition=Precondition(target=f"{issue_repo}#{issue_number}", field=field, expected=expected_value))``.

2. F5 Marker Advancement (Documented Integration Point):
   To advance a dependency marker on GitHub under Path B:
   - Construct ``Precondition(target=f"{repo}:{marker_id}", field="sha", expected=current_marker_sha)``.
   - Construct ``ObjectWrite(verb="marker-advance", target=f"{repo}:{marker_id}", payload={"marker": marker_id, "sha": target_marker_sha}, precondition=precondition)``.
   - Call ``apply_object_write(write, policy=policy, mutation_allowlist=mutation_allowlist, gh_ops=gh_ops)``.

3. F9 Marketplace Entry Update (Documented Integration Point):
   To land a marketplace version patch on GitHub under Path B:
   - Construct ``Precondition(target=f"{marketplace_repo}:{file_path}", field="version", expected=current_version)``.
   - Construct ``ObjectWrite(verb="marketplace-entry", target=f"{marketplace_repo}:{file_path}", payload={"plugin_id": plugin_id, "version": new_version}, precondition=precondition)``.
   - Call ``apply_object_write(write, policy=policy, mutation_allowlist=mutation_allowlist, gh_ops=gh_ops)``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


BLOCKED_VERBS: set[str] = {
    "remove-all-members",
}


@dataclass(frozen=True)
class Precondition:
    """Descriptor naming an object's expected current state (Path B expected_shas equivalent)."""

    target: str
    field: str
    expected: Any


@dataclass(frozen=True)
class ObjectWrite:
    """Descriptor for a typed GitHub object write operation."""

    verb: str
    target: str
    payload: dict[str, Any]
    precondition: Precondition
    desired: Any = None


class GhExecutionError(Exception):
    """Raised when a gh CLI operation fails or produces unparseable output."""

    pass


OPERATIONAL_ERRORS = (
    GhExecutionError,
    subprocess.SubprocessError,
    OSError,
    json.JSONDecodeError,
)


class ObjectGhOps:
    """Interface for GitHub object CLI operations (injected for testing)."""

    def get_state(self, precondition: Precondition) -> Any:
        """Return current live state for precondition checking.

        Raises GhExecutionError on gh execution or parsing failure.
        """
        raise NotImplementedError

    def apply_write(self, write: ObjectWrite) -> dict[str, Any]:
        """Execute the object write against GitHub API / CLI.

        Returns result dict e.g. {"state": "applied", "detail": ...}.
        Raises GhExecutionError on execution failure.
        """
        raise NotImplementedError


def build_gh_api_post_args(
    target: str, payload: dict[str, Any], gh_binary: str = "gh"
) -> list[str]:
    """Construct `gh api -X POST` command args with `-f key=value` flags."""
    cmd = [gh_binary, "api", "-X", "POST", target]
    for k, v in payload.items():
        cmd.extend(["-f", f"{k}={v}"])
    return cmd


class ObjectGhCliOps(ObjectGhOps):
    """Production implementation of ObjectGhOps shelling `gh` CLI."""

    def __init__(self, gh_binary: str = "gh") -> None:
        self.gh_binary = gh_binary

    def get_state(self, precondition: Precondition) -> Any:
        target = precondition.target
        if "#" in target:
            repo, num = target.split("#", 1)
            cmd = [
                self.gh_binary,
                "issue",
                "view",
                num,
                "-R",
                repo,
                "--json",
                precondition.field,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                raise GhExecutionError(
                    f"gh issue view exit code {res.returncode}: {res.stderr.strip()}"
                )
            try:
                data = json.loads(res.stdout)
                return data.get(precondition.field)
            except Exception as exc:
                raise GhExecutionError(f"Failed to parse gh issue view JSON: {exc}")

        cmd = [self.gh_binary, "api", target]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise GhExecutionError(
                f"gh api exit code {res.returncode}: {res.stderr.strip()}"
            )
        try:
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                return data.get(precondition.field)
            return data
        except Exception as exc:
            raise GhExecutionError(f"Failed to parse gh api response: {exc}")

    def apply_write(self, write: ObjectWrite) -> dict[str, Any]:
        if write.verb in {"update-field", "issue-patch"} and "#" in write.target:
            repo, num = write.target.split("#", 1)
            field = write.payload.get("field") or write.precondition.field
            val = write.desired if write.desired is not None else write.payload.get("value")
            cmd = [
                self.gh_binary,
                "issue",
                "edit",
                num,
                "-R",
                repo,
                f"--{field}",
                str(val),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                raise GhExecutionError(
                    f"gh issue edit exit code {res.returncode}: {res.stderr.strip()}"
                )
            return {
                "state": "applied",
                "target": write.target,
                "field": field,
                "value": val,
            }

        cmd = build_gh_api_post_args(write.target, write.payload, self.gh_binary)
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise GhExecutionError(
                f"gh api write exit code {res.returncode}: {res.stderr.strip()}"
            )
        return {"state": "applied", "target": write.target}


def is_verb_blocked(verb: str) -> bool:
    v = verb.lower().strip()
    return v in BLOCKED_VERBS or any(
        b in v for b in ("delete", "transfer", "archive")
    )


def apply_object_write(
    write: ObjectWrite,
    *,
    policy: str,
    mutation_allowlist: Sequence[str] | set[str] | None = None,
    gh_ops: ObjectGhOps,
) -> dict[str, Any]:
    """Execute a guarded, idempotent Path-B GitHub object write under on_mutation policy."""
    # 1. Unconditional Blocklist Check
    if is_verb_blocked(write.verb):
        return {
            "state": "blocked",
            "reason": f"blocked: operation '{write.verb}' is in operation blocklist",
        }

    # 2. Policy: propose
    if policy == "propose":
        return {"state": "proposed", "action": f"{write.verb} {write.target}"}

    # 3. Policy: allow (reserved / blocked in v1)
    if policy == "allow":
        return {"state": "blocked", "reason": "allow is reserved and blocked in v1"}

    # 4. Policy: allow-listed
    if policy == "allow-listed":
        allowlist = set(mutation_allowlist or ())
        if write.verb not in allowlist:
            return {"state": "proposed", "action": f"{write.verb} {write.target}"}

        # Verb is in allowlist -> check precondition live state
        try:
            current_state = gh_ops.get_state(write.precondition)
        except OPERATIONAL_ERRORS as exc:
            return {
                "state": "blocked",
                "reason": f"precondition unconfirmable: {exc}",
            }

        # Determine desired end state
        desired = write.desired
        if desired is None:
            if write.precondition.field in write.payload:
                desired = write.payload[write.precondition.field]
            elif "value" in write.payload:
                desired = write.payload["value"]
            elif "patch" in write.payload and isinstance(write.payload["patch"], dict):
                desired = write.payload["patch"].get(write.precondition.field)

        # Idempotency check: if object is already in desired end state -> no-op
        if desired is not None and current_state == desired:
            return {"state": "applied", "noop": True}

        # Precondition check: must match expected state
        if current_state != write.precondition.expected:
            return {
                "state": "blocked",
                "reason": (
                    f"precondition mismatch: expected {write.precondition.expected!r}, "
                    f"got {current_state!r}"
                ),
            }

        # Apply write
        try:
            res = gh_ops.apply_write(write)
            if isinstance(res, dict):
                result = dict(res)
                result.setdefault("state", "applied")
                result["noop"] = False
                return result
            return {"state": "applied", "noop": False, "result": res}
        except OPERATIONAL_ERRORS as exc:
            return {"state": "failed", "reason": str(exc)}

    return {"state": "blocked", "reason": f"unrecognized policy: {policy}"}


def apply_issue_field_patch(
    *,
    issue_repo: str,
    issue_number: int,
    field: str,
    target_value: Any,
    expected_value: Any,
    policy: str,
    mutation_allowlist: Sequence[str] | set[str] | None = None,
    gh_ops: ObjectGhOps,
) -> dict[str, Any]:
    """Demonstrator wiring for F8 issue/milestone field patch under Path B."""
    target = f"{issue_repo}#{issue_number}"
    precondition = Precondition(target=target, field=field, expected=expected_value)
    write = ObjectWrite(
        verb="update-field",
        target=target,
        payload={
            "repo": issue_repo,
            "number": issue_number,
            "field": field,
            "value": target_value,
        },
        precondition=precondition,
        desired=target_value,
    )
    return apply_object_write(
        write,
        policy=policy,
        mutation_allowlist=mutation_allowlist,
        gh_ops=gh_ops,
    )
