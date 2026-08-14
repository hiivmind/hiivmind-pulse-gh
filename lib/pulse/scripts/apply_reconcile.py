#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Resumable reconcile loop turning a pushed branch into a landed change (F11 Task 6).

Open PR -> detect merge -> advance base.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from lib.pulse.scripts import resolve_run  # noqa: E402
from lib.pulse.scripts import validate_result  # noqa: E402


class GhOps:
    """Interface for GitHub CLI operations (injected for testing)."""

    def create_or_get_pr(
        self, repo: str, branch: str, base: str, title: str, body: str
    ) -> dict:
        """Return {"url": str, "created": bool}."""
        raise NotImplementedError

    def view_pr(self, repo: str, branch: str) -> dict:
        """Return state, merged, merge_commit_sha, url, observed base/head, and error."""
        raise NotImplementedError

    def delete_remote_branch(
        self, repo: str, branch: str, expected_sha: str
    ) -> dict:
        """CAS-delete a remote branch, returning state and an optional reason."""
        raise NotImplementedError


class GhCliOps(GhOps):
    """Production implementation of GhOps calling `gh` CLI."""

    def __init__(self, gh_binary: str = "gh") -> None:
        self.gh_binary = gh_binary

    def create_or_get_pr(
        self, repo: str, branch: str, base: str, title: str, body: str
    ) -> dict:
        existing = self.view_pr(repo, branch)
        if existing.get("url") and existing.get("state") == "OPEN":
            return {"url": existing["url"], "created": False}

        cmd = [
            self.gh_binary,
            "pr",
            "create",
            "-R",
            repo,
            "--head",
            branch,
            "--base",
            base,
            "--title",
            title,
            "--body",
            body,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            url = res.stdout.strip()
            return {"url": url, "created": True}

        existing = self.view_pr(repo, branch)
        if existing.get("url"):
            return {"url": existing["url"], "created": False}
        raise RuntimeError(
            f"gh pr create failed for {repo} {branch}: {res.stderr.strip()}"
        )

    def view_pr(self, repo: str, branch: str) -> dict:
        cmd = [
            self.gh_binary,
            "pr",
            "view",
            branch,
            "-R",
            repo,
            "--json",
            "state,mergedAt,mergeCommit,url,baseRefName,headRefOid",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return {
                "state": "ERROR",
                "merged": False,
                "merge_commit_sha": None,
                "url": "",
                "error": res.stderr.strip() or f"gh pr view exit code {res.returncode}",
                "observed_base": None,
                "observed_head_sha": None,
            }
        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError as exc:
            return {
                "state": "ERROR",
                "merged": False,
                "merge_commit_sha": None,
                "url": "",
                "error": f"unparseable JSON from gh pr view: {exc.msg}",
                "observed_base": None,
                "observed_head_sha": None,
            }
        state = data.get("state", "CLOSED").upper()
        merged_at = data.get("mergedAt")
        merge_commit = data.get("mergeCommit")
        merge_commit_sha = (
            merge_commit.get("oid")
            if isinstance(merge_commit, dict)
            else (merge_commit if isinstance(merge_commit, str) else None)
        )
        merged = bool(merged_at) or state == "MERGED"
        return {
            "state": "MERGED" if merged else state,
            "merged": merged,
            "merge_commit_sha": merge_commit_sha if merged else None,
            "url": data.get("url", ""),
            "observed_base": data.get("baseRefName"),
            "observed_head_sha": data.get("headRefOid"),
        }

    def delete_remote_branch(
        self, repo: str, branch: str, expected_sha: str
    ) -> dict:
        if not expected_sha:
            return {
                "state": "failed",
                "reason": "missing expected ref sha, refusing to delete",
            }

        endpoint = f"repos/{repo}/git/refs/heads/{branch}"
        observed = subprocess.run(
            [self.gh_binary, "api", endpoint],
            capture_output=True,
            text=True,
            check=False,
        )
        if observed.returncode != 0:
            error = observed.stderr.strip() or observed.stdout.strip()
            if "404" in error or "not found" in error.lower():
                return {"state": "ok"}
            return {
                "state": "failed",
                "reason": error or "could not read remote branch ref",
            }

        try:
            current_sha = json.loads(observed.stdout)["object"]["sha"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            return {
                "state": "failed",
                "reason": f"could not parse remote branch ref SHA: {exc}",
            }

        if current_sha != expected_sha:
            return {
                "state": "failed",
                "reason": "ref sha changed since observation, refusing to delete",
            }

        cmd = [
            self.gh_binary,
            "api",
            "-X",
            "DELETE",
            endpoint,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return {"state": "ok"}
        return {"state": "failed", "reason": res.stderr.strip()}


def resolve_intended_base(
    source_kind: str,
    binding_ref: Mapping[str, Any],
    finalizer_record: Mapping[str, Any] | None = None,
) -> str:
    if source_kind == "plan-sync":
        if finalizer_record and finalizer_record.get("base_ref"):
            return finalizer_record["base_ref"]
        if binding_ref.get("base_ref"):
            return binding_ref["base_ref"]
        raise ValueError("cannot resolve intended base for plan-sync: no base_ref")

    if source_kind == "marketplace-sync":
        if finalizer_record and finalizer_record.get("base_ref"):
            return finalizer_record["base_ref"]
        raise ValueError(
            "cannot resolve intended base for marketplace-sync: no base_ref"
        )

    if source_kind == "generated-artifact":
        if binding_ref.get("branch"):
            return binding_ref["branch"]
        raise ValueError(
            "cannot resolve intended base for generated-artifact: no branch"
        )

    raise ValueError(f"unknown source_kind: {source_kind}")


class ApplyStatusError(ValueError):
    """Raised when apply-status state cannot be safely read or persisted."""


def load_apply_status(path: str | Path) -> dict | None:
    p = Path(path)
    try:
        text = p.read_text()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise ApplyStatusError(f"could not load apply status {p}: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ApplyStatusError(f"could not load apply status {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ApplyStatusError(
            f"could not load apply status {p}: expected a mapping"
        )
    return data


def _atomic_write_yaml(path: str | Path, doc: Mapping[str, Any]) -> None:
    p = Path(path)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=p.parent,
            prefix=f".{p.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            yaml.safe_dump(doc, handle, sort_keys=False, allow_unicode=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, p)
        # Rename succeeded: nothing left to clean up on a later failure.
        temporary_name = None
        dir_fd = os.open(str(p.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as exc:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except OSError:
                pass
        raise ApplyStatusError(f"could not write apply status {p}: {exc}") from exc


def write_apply_status(
    path: str | Path,
    *,
    proposal_id: str,
    repo: str,
    branch: str,
    state: str,
    recorded_proposal_id: str,
    proposal_digest: str,
    authorization_digest: str,
    intended_base: str,
    expected_head_sha: str,
    observed_base: str | None = None,
    observed_head_sha: str | None = None,
    pushed_sha: str | None = None,
    pr_url: str | None = None,
    merged_sha: str | None = None,
    reason: str | None = None,
    workspace: str = "unknown",
    actor: dict | None = None,
    errors: list[str] | None = None,
) -> dict:
    if actor is None:
        actor = {"gh_login": "unknown", "machine": "unknown", "mode": "interactive"}
    doc = {
        "contract_version": 1,
        "kind": "apply-status",
        "workspace": workspace,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": actor,
        "errors": errors or [],
        "proposal_id": proposal_id,
        "recorded_proposal_id": recorded_proposal_id,
        "proposal_digest": proposal_digest,
        "authorization_digest": authorization_digest,
        "selection": [repo],
        "branch": branch,
        "state": state,
        "pushed_sha": pushed_sha,
        "pr_url": pr_url,
        "merged_sha": merged_sha,
        "reason": reason,
        "intended_base": intended_base,
        "expected_head_sha": expected_head_sha,
        "observed_base": observed_base,
        "observed_head_sha": observed_head_sha,
    }
    validation_errors = validate_result.validate(doc, "apply-status")
    if validation_errors:
        raise ValueError(
            f"Invalid apply-status document: {'; '.join(validation_errors)}"
        )

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_yaml(p, doc)
    return doc


def open_apply_pr(
    *,
    ledger_path: str | Path,
    step_id: str,
    proposal_id: str,
    repo: str,
    branch: str,
    base: str,
    pushed_sha: str,
    title: str,
    body: str,
    result_path: str | Path,
    gh_ops: GhOps,
    recorded_proposal_id: str,
    proposal_digest: str,
    authorization_digest: str,
    intended_base: str,
    expected_head_sha: str,
    token: str | None = None,
    actor_id: str = "octocat@mba-m4",
    workspace: str = "unknown",
) -> dict:
    if base != intended_base:
        raise ValueError(
            f"open_apply_pr: base {base!r} != intended_base {intended_base!r} "
            "- the PR's actual base must match the audited intended base"
        )
    if token is not None:
        resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
    else:
        resolve_run.acquire_lease(ledger_path, step_id, actor_id)
    resolve_run.snapshot_audit(
        ledger_path,
        step_id,
        recorded_proposal_id=recorded_proposal_id,
        proposal_digest=proposal_digest,
        authorization_digest=authorization_digest,
    )

    existing = load_apply_status(result_path)
    if existing and existing.get("state") in {"pr_opened", "applied", "rejected"}:
        return existing

    pr_info = gh_ops.create_or_get_pr(
        repo=repo, branch=branch, base=base, title=title, body=body
    )
    pr_url = pr_info["url"]

    actor_parts = actor_id.split("@", 1)
    login = actor_parts[0]
    machine = actor_parts[1] if len(actor_parts) > 1 else ""
    actor_doc = {"gh_login": login, "machine": machine, "mode": "interactive"}

    doc = write_apply_status(
        result_path,
        proposal_id=proposal_id,
        repo=repo,
        branch=branch,
        state="pr_opened",
        recorded_proposal_id=recorded_proposal_id,
        proposal_digest=proposal_digest,
        authorization_digest=authorization_digest,
        intended_base=intended_base,
        expected_head_sha=expected_head_sha,
        pushed_sha=pushed_sha,
        pr_url=pr_url,
        workspace=workspace,
        actor=actor_doc,
    )

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, step_id)
    step["status"] = "blocked-on-gate"
    step["notes"].append(f"{resolve_run.now_iso()} PR opened: {pr_url}")
    resolve_run.recompute_status(ledger_doc)
    resolve_run.save(ledger_path, ledger_doc)

    return doc


def _branch_cleanup_note(branch: str, result: dict) -> str:
    if result.get("state") == "ok":
        return f"deleted branch {branch}"
    reason = result.get("reason") or "unknown cleanup error"
    if "sha changed" in reason or "refusing to delete" in reason:
        return f"refused: sha mismatch for branch {branch}: {reason}"
    return f"branch cleanup failed for {branch}: {reason}"


def reconcile_apply(
    *,
    ledger_path: str | Path,
    step_id: str,
    proposal_id: str,
    repo: str,
    branch: str,
    result_path: str | Path,
    gh_ops: GhOps,
    recorded_proposal_id: str,
    proposal_digest: str,
    authorization_digest: str,
    intended_base: str,
    expected_head_sha: str,
    advance_base: Callable[[str, str], dict] | None = None,
    token: str | None = None,
    actor_id: str = "octocat@mba-m4",
    workspace: str = "unknown",
) -> dict:
    """Reconcile a pushed apply branch against remote PR state and advance base off merged SHA.

    Note on bare CLI vs Python API: When advance_base is None (e.g. bare CLI execution
    via main()), base advancement is deferred to the caller driver, and reconcile_apply
    marks the step done once merge is detected. When advance_base is provided, base
    advancement must be idempotent, and the step is marked done ONLY after advance_base
    returns {"state": "ok"}.
    """
    if token is not None:
        resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
    else:
        resolve_run.acquire_lease(ledger_path, step_id, actor_id)
    resolve_run.snapshot_audit(
        ledger_path,
        step_id,
        recorded_proposal_id=recorded_proposal_id,
        proposal_digest=proposal_digest,
        authorization_digest=authorization_digest,
    )

    existing = load_apply_status(result_path)
    if existing and existing.get("state") == "rejected":
        ledger_doc = resolve_run.load(ledger_path)
        step = resolve_run.find_step(ledger_doc, step_id)
        if step["status"] == "failed":
            return existing

    pr_info = gh_ops.view_pr(repo=repo, branch=branch)

    actor_parts = actor_id.split("@", 1)
    login = actor_parts[0]
    machine = actor_parts[1] if len(actor_parts) > 1 else ""
    actor_doc = {"gh_login": login, "machine": machine, "mode": "interactive"}

    pushed_sha = (
        existing.get("pushed_sha")
        if existing and existing.get("pushed_sha")
        else expected_head_sha
    )
    pr_url = pr_info.get("url") or (existing.get("pr_url") if existing else None)

    if pr_info.get("merged") and pr_info.get("merge_commit_sha"):
        merged_sha = pr_info["merge_commit_sha"]
        observed_base = pr_info.get("observed_base")
        observed_head_sha = pr_info.get("observed_head_sha")
        if observed_base != intended_base or observed_head_sha != expected_head_sha:
            reason = (
                "merged PR base/head mismatch: "
                f"observed_base={observed_base} (want {intended_base}), "
                f"observed_head_sha={observed_head_sha} (want {expected_head_sha})"
            )
            doc = write_apply_status(
                result_path,
                proposal_id=proposal_id,
                repo=repo,
                branch=branch,
                state="rejected",
                recorded_proposal_id=recorded_proposal_id,
                proposal_digest=proposal_digest,
                authorization_digest=authorization_digest,
                intended_base=intended_base,
                expected_head_sha=expected_head_sha,
                observed_base=observed_base,
                observed_head_sha=observed_head_sha,
                pushed_sha=pushed_sha,
                pr_url=pr_url or "",
                merged_sha=merged_sha,
                reason=reason,
                workspace=workspace,
                actor=actor_doc,
            )
            cleanup_result = gh_ops.delete_remote_branch(
                repo, branch, observed_head_sha
            )

            ledger_doc = resolve_run.load(ledger_path)
            step = resolve_run.find_step(ledger_doc, step_id)
            step["status"] = "failed"
            step["notes"].append(
                f"{resolve_run.now_iso()} {reason}; "
                f"{_branch_cleanup_note(branch, cleanup_result)}"
            )
            resolve_run.recompute_status(ledger_doc)
            resolve_run.save(ledger_path, ledger_doc)
            return doc

        doc = write_apply_status(
            result_path,
            proposal_id=proposal_id,
            repo=repo,
            branch=branch,
            state="applied",
            recorded_proposal_id=recorded_proposal_id,
            proposal_digest=proposal_digest,
            authorization_digest=authorization_digest,
            intended_base=intended_base,
            expected_head_sha=expected_head_sha,
            observed_base=observed_base,
            observed_head_sha=observed_head_sha,
            pushed_sha=pushed_sha,
            pr_url=pr_url or "",
            merged_sha=merged_sha,
            workspace=workspace,
            actor=actor_doc,
        )

        satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
        if not satisfied:
            doc = write_apply_status(
                result_path,
                proposal_id=proposal_id,
                repo=repo,
                branch=branch,
                state="rejected",
                recorded_proposal_id=recorded_proposal_id,
                proposal_digest=proposal_digest,
                authorization_digest=authorization_digest,
                intended_base=intended_base,
                expected_head_sha=expected_head_sha,
                observed_base=observed_base,
                observed_head_sha=observed_head_sha,
                pushed_sha=pushed_sha,
                pr_url=pr_url or "",
                merged_sha=merged_sha,
                reason=detail,
                workspace=workspace,
                actor=actor_doc,
            )
            ledger_doc = resolve_run.load(ledger_path)
            step = resolve_run.find_step(ledger_doc, step_id)
            resolve_run._apply_gate_result(step, False, detail)
            step["status"] = "failed"
            resolve_run.recompute_status(ledger_doc)
            resolve_run.save(ledger_path, ledger_doc)
            return doc

        ledger_doc = resolve_run.load(ledger_path)
        step = resolve_run.find_step(ledger_doc, step_id)
        if step["status"] == "done":
            return doc

        if advance_base is None:
            resolve_run._apply_gate_result(step, True, detail)
            step["status"] = "done"
            step["notes"].append(
                f"{resolve_run.now_iso()} Merge detected; base advance deferred to caller driver"
            )
            resolve_run.recompute_status(ledger_doc)
            resolve_run.save(ledger_path, ledger_doc)
        else:
            adv_res = advance_base(repo, merged_sha)
            if isinstance(adv_res, dict) and adv_res.get("state") == "ok":
                resolve_run._apply_gate_result(step, True, detail)
                step["status"] = "done"
                resolve_run.recompute_status(ledger_doc)
                resolve_run.save(ledger_path, ledger_doc)
            else:
                reason = (
                    adv_res.get("reason", "unknown error")
                    if isinstance(adv_res, dict)
                    else "unknown error"
                )
                step["status"] = "blocked-on-gate"
                step["notes"].append(
                    f"{resolve_run.now_iso()} base advance failed: {reason}"
                )
                resolve_run.recompute_status(ledger_doc)
                resolve_run.save(ledger_path, ledger_doc)

        return doc

    elif pr_info.get("state") == "CLOSED" and not pr_info.get("merged"):
        reason = "PR closed without merging"
        doc = write_apply_status(
            result_path,
            proposal_id=proposal_id,
            repo=repo,
            branch=branch,
            state="rejected",
            recorded_proposal_id=recorded_proposal_id,
            proposal_digest=proposal_digest,
            authorization_digest=authorization_digest,
            intended_base=intended_base,
            expected_head_sha=expected_head_sha,
            observed_base=pr_info.get("observed_base"),
            observed_head_sha=pr_info.get("observed_head_sha"),
            pushed_sha=pushed_sha,
            pr_url=pr_url,
            reason=reason,
            workspace=workspace,
            actor=actor_doc,
        )

        cleanup_expected_sha = pr_info.get("observed_head_sha") or pushed_sha
        cleanup_result = gh_ops.delete_remote_branch(
            repo, branch, cleanup_expected_sha
        )

        ledger_doc = resolve_run.load(ledger_path)
        step = resolve_run.find_step(ledger_doc, step_id)
        step["status"] = "failed"
        step["notes"].append(
            f"{resolve_run.now_iso()} {reason}; "
            f"{_branch_cleanup_note(branch, cleanup_result)}"
        )
        resolve_run.recompute_status(ledger_doc)
        resolve_run.save(ledger_path, ledger_doc)

        return doc

    if pr_info.get("state") == "ERROR" and existing:
        ledger_doc = resolve_run.load(ledger_path)
        step = resolve_run.find_step(ledger_doc, step_id)
        if step["status"] not in resolve_run.TERMINAL:
            step["status"] = "blocked-on-gate"
        err_detail = pr_info.get("error", "unknown gh error")
        step["notes"].append(
            f"{resolve_run.now_iso()} gh view_pr error: {err_detail}"
        )
        resolve_run.recompute_status(ledger_doc)
        resolve_run.save(ledger_path, ledger_doc)
        return existing

    if existing and existing.get("state") in {"pr_opened", "applied"}:
        return existing

    ledger_doc = resolve_run.load(ledger_path)
    step = resolve_run.find_step(ledger_doc, step_id)
    step["status"] = "blocked-on-gate"
    if pr_info.get("state") == "ERROR":
        err_detail = pr_info.get("error", "unknown gh error")
        step["notes"].append(
            f"{resolve_run.now_iso()} gh view_pr error: {err_detail}"
        )
    resolve_run.recompute_status(ledger_doc)
    resolve_run.save(ledger_path, ledger_doc)

    if pr_info.get("state") == "ERROR":
        err_detail = pr_info.get("error", "unknown gh error")
        raise ApplyStatusError(
            f"cannot determine PR state for {repo} {branch}: {err_detail}"
        )
    if not pr_url:
        raise ApplyStatusError(
            f"cannot determine PR state for {repo} {branch}: no PR URL"
        )

    return write_apply_status(
        result_path,
        proposal_id=proposal_id,
        repo=repo,
        branch=branch,
        state="pr_opened",
        recorded_proposal_id=recorded_proposal_id,
        proposal_digest=proposal_digest,
        authorization_digest=authorization_digest,
        intended_base=intended_base,
        expected_head_sha=expected_head_sha,
        pushed_sha=pushed_sha,
        pr_url=pr_url,
        workspace=workspace,
        actor=actor_doc,
    )


def main():
    parser = argparse.ArgumentParser(description="Apply reconcile operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open-pr")
    o.add_argument("--ledger", required=True)
    o.add_argument("--step", required=True)
    o.add_argument("--proposal-id", required=True)
    o.add_argument("--repo", required=True)
    o.add_argument("--branch", required=True)
    o.add_argument("--base", required=True)
    o.add_argument("--pushed-sha", required=True)
    o.add_argument("--title", required=True)
    o.add_argument("--body", default="")
    o.add_argument("--result", required=True)
    o.add_argument("--recorded-proposal-id", required=True)
    o.add_argument("--proposal-digest", required=True)
    o.add_argument("--authorization-digest", required=True)
    o.add_argument("--intended-base", required=True)
    o.add_argument("--expected-head-sha", required=True)
    o.add_argument("--token")
    o.add_argument("--actor", default="unknown@unknown")
    o.add_argument("--workspace", default="unknown")

    r = sub.add_parser("reconcile")
    r.add_argument("--ledger", required=True)
    r.add_argument("--step", required=True)
    r.add_argument("--proposal-id", required=True)
    r.add_argument("--repo", required=True)
    r.add_argument("--branch", required=True)
    r.add_argument("--result", required=True)
    r.add_argument("--recorded-proposal-id", required=True)
    r.add_argument("--proposal-digest", required=True)
    r.add_argument("--authorization-digest", required=True)
    r.add_argument("--intended-base", required=True)
    r.add_argument("--expected-head-sha", required=True)
    r.add_argument("--token")
    r.add_argument("--actor", default="unknown@unknown")
    r.add_argument("--workspace", default="unknown")

    args = parser.parse_args()
    gh_ops = GhCliOps()

    if args.cmd == "open-pr":
        doc = open_apply_pr(
            ledger_path=args.ledger,
            step_id=args.step,
            proposal_id=args.proposal_id,
            repo=args.repo,
            branch=args.branch,
            base=args.base,
            pushed_sha=args.pushed_sha,
            title=args.title,
            body=args.body,
            result_path=args.result,
            gh_ops=gh_ops,
            recorded_proposal_id=args.recorded_proposal_id,
            proposal_digest=args.proposal_digest,
            authorization_digest=args.authorization_digest,
            intended_base=args.intended_base,
            expected_head_sha=args.expected_head_sha,
            token=args.token,
            actor_id=args.actor,
            workspace=args.workspace,
        )
        print(json.dumps(doc))

    elif args.cmd == "reconcile":
        doc = reconcile_apply(
            ledger_path=args.ledger,
            step_id=args.step,
            proposal_id=args.proposal_id,
            repo=args.repo,
            branch=args.branch,
            result_path=args.result,
            gh_ops=gh_ops,
            recorded_proposal_id=args.recorded_proposal_id,
            proposal_digest=args.proposal_digest,
            authorization_digest=args.authorization_digest,
            intended_base=args.intended_base,
            expected_head_sha=args.expected_head_sha,
            token=args.token,
            actor_id=args.actor,
            workspace=args.workspace,
        )
        print(json.dumps(doc))


if __name__ == "__main__":
    main()
