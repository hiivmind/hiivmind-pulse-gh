#!/usr/bin/env python3
"""PR-gated F8 plan-sync document-blob finalization."""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping

from lib.pulse.scripts import plan_sync


def _git_blob_sha(content: str) -> str:
    payload = content.encode("utf-8")
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _failed(operation: str, result: Mapping) -> dict:
    reason = result.get("reason") or f"{operation} failed"
    return {"state": "failed", "reason": str(reason)}


def _base_blob(content: str) -> str | None:
    document = plan_sync.parse_document(content)
    binding = document.binding
    if not isinstance(binding, Mapping):
        return None
    base = binding.get("base")
    blob = base.get("blob") if isinstance(base, Mapping) else None
    return str(blob) if blob is not None else None


def make_f8_advance_base(finalizer_record, contents_ops, gh_ops) -> Callable[[str, str], dict]:
    """Build an idempotent finalizer for one recorded plan-sync proposal."""
    record = dict(finalizer_record)

    def advance_base(repo: str, merged_sha: str) -> dict:
        if repo != record.get("repo"):
            return {
                "state": "blocked",
                "reason": f"finalizer repo {record.get('repo')!r} does not match {repo!r}",
            }

        path = record["doc_path"]
        base_ref = record["base_ref"]
        proposal_id = record["proposal_id"]
        branch = f"pulse/advance-base/{proposal_id}"

        desired = contents_ops.get_file(repo, path, merged_sha)
        if desired.get("state") != "ok":
            return _failed("read merged document", desired)
        desired_content = desired["content"]
        desired_blob = _git_blob_sha(desired_content)

        current = contents_ops.get_file(repo, path, base_ref)
        if current.get("state") != "ok":
            return _failed("read base document", current)
        current_content = current["content"]
        try:
            current_blob = _base_blob(current_content)
        except (TypeError, ValueError) as exc:
            return {"state": "failed", "reason": f"parse base document failed: {exc}"}

        pr = gh_ops.view_pr(repo, branch)
        if current_blob == desired_blob:
            return {"state": "ok"}

        expected_prior = record.get("expected_prior_blob")
        if current_blob != expected_prior:
            return {
                "state": "blocked",
                "reason": (
                    "semantic CAS mismatch: expected prior blob "
                    f"{expected_prior!r}, observed {current_blob!r}"
                ),
            }

        if pr.get("merged"):
            return {
                "state": "blocked-on-gate",
                "reason": "bookkeeping PR merged but desired base blob is not yet observed",
            }
        if pr.get("state") == "OPEN":
            return {"state": "blocked-on-gate"}

        try:
            patched = plan_sync.patch_document(
                current_content,
                doc_patch={},
                sync_patch={"base": {"blob": desired_blob}},
            )
        except (TypeError, ValueError) as exc:
            return {"state": "failed", "reason": f"patch base document failed: {exc}"}

        created = contents_ops.create_branch(repo, branch, base_ref)
        if created.get("state") != "ok":
            return _failed("create bookkeeping branch", created)

        message = f"Advance plan-sync base for {proposal_id}"
        put = contents_ops.put_file(
            repo,
            path,
            patched,
            file_sha=current["file_sha"],
            branch=branch,
            message=message,
        )
        if put.get("state") != "ok":
            return _failed("write bookkeeping document", put)

        opened = contents_ops.open_pr(
            repo,
            branch,
            base_ref,
            message,
            (
                "Advance the plan-sync base blob after proposal "
                f"{proposal_id} merged. Binding: {record.get('binding_id')}."
            ),
        )
        if opened.get("state") == "failed" or not opened.get("url"):
            return _failed("open bookkeeping PR", opened)
        return {"state": "blocked-on-gate"}

    return advance_base
