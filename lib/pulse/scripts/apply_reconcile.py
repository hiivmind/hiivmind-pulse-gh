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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

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
        """Return {"state": "OPEN"|"MERGED"|"CLOSED"|"ERROR", "merged": bool, "merge_commit_sha": str|None, "url": str, "error"?: str}."""
        raise NotImplementedError

    def delete_remote_branch(self, repo: str, branch: str) -> dict:
        """Return {"state": "ok"|"failed", "reason": str|None}."""
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
            "state,mergedAt,mergeCommit,url",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return {
                "state": "ERROR",
                "merged": False,
                "merge_commit_sha": None,
                "url": "",
                "error": res.stderr.strip() or f"gh pr view exit code {res.returncode}",
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
        }

    def delete_remote_branch(self, repo: str, branch: str) -> dict:
        cmd = [
            self.gh_binary,
            "api",
            "-X",
            "DELETE",
            f"repos/{repo}/git/refs/heads/{branch}",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return {"state": "ok"}
        return {"state": "failed", "reason": res.stderr.strip()}


def load_apply_status(path: str | Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = yaml.safe_load(p.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


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
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
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
    actor_id: str = "octocat@mba-m4",
    workspace: str = "unknown",
) -> dict:
    resolve_run.acquire_lease(ledger_path, step_id, actor_id)

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
    observed_base: str | None = None,
    observed_head_sha: str | None = None,
    advance_base: Callable[[str, str], dict] | None = None,
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
    resolve_run.acquire_lease(ledger_path, step_id, actor_id)

    existing = load_apply_status(result_path)
    if existing:
        ex_state = existing.get("state")
        if ex_state == "applied":
            ledger_doc = resolve_run.load(ledger_path)
            step = resolve_run.find_step(ledger_doc, step_id)
            if step["status"] == "done":
                return existing
            # If step is NOT done, fall through to re-run advancement path below.
        elif ex_state == "rejected":
            ledger_doc = resolve_run.load(ledger_path)
            step = resolve_run.find_step(ledger_doc, step_id)
            if step["status"] != "failed":
                step["status"] = "failed"
                resolve_run.recompute_status(ledger_doc)
                resolve_run.save(ledger_path, ledger_doc)
            return existing

    if existing and existing.get("state") == "applied":
        pr_info = {
            "state": "MERGED",
            "merged": True,
            "merge_commit_sha": existing.get("merged_sha"),
            "url": existing.get("pr_url", ""),
        }
    else:
        pr_info = gh_ops.view_pr(repo=repo, branch=branch)

    actor_parts = actor_id.split("@", 1)
    login = actor_parts[0]
    machine = actor_parts[1] if len(actor_parts) > 1 else ""
    actor_doc = {"gh_login": login, "machine": machine, "mode": "interactive"}

    pushed_sha = existing.get("pushed_sha") if existing else None
    pr_url = pr_info.get("url") or (existing.get("pr_url") if existing else None)

    if pr_info.get("merged") and pr_info.get("merge_commit_sha"):
        merged_sha = pr_info["merge_commit_sha"]
        if not (existing and existing.get("state") == "applied"):
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
                pushed_sha=pushed_sha or "unknown",
                pr_url=pr_url or "",
                merged_sha=merged_sha,
                workspace=workspace,
                actor=actor_doc,
            )
        else:
            doc = existing

        satisfied, detail = resolve_run.evaluate_merge_detected_gate(str(result_path))
        if satisfied:
            if advance_base is None:
                ledger_doc = resolve_run.load(ledger_path)
                step = resolve_run.find_step(ledger_doc, step_id)
                resolve_run._apply_gate_result(step, True, detail)
                step["status"] = "done"
                step["notes"].append(
                    f"{resolve_run.now_iso()} Merge detected; base advance deferred to caller driver"
                )
                resolve_run.recompute_status(ledger_doc)
                resolve_run.save(ledger_path, ledger_doc)
            else:
                adv_res = advance_base(repo, merged_sha)
                ledger_doc = resolve_run.load(ledger_path)
                step = resolve_run.find_step(ledger_doc, step_id)
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
            pushed_sha=pushed_sha,
            pr_url=pr_url,
            reason=reason,
            workspace=workspace,
            actor=actor_doc,
        )

        gh_ops.delete_remote_branch(repo, branch)

        ledger_doc = resolve_run.load(ledger_path)
        step = resolve_run.find_step(ledger_doc, step_id)
        step["status"] = "failed"
        step["notes"].append(
            f"{resolve_run.now_iso()} {reason}; deleted branch {branch}"
        )
        resolve_run.recompute_status(ledger_doc)
        resolve_run.save(ledger_path, ledger_doc)

        return doc

    else:
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

        if existing:
            return existing
        else:
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
                pushed_sha=pushed_sha or "unknown",
                pr_url=pr_url or "",
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
    o.add_argument("--base", default="main")
    o.add_argument("--pushed-sha", required=True)
    o.add_argument("--title", required=True)
    o.add_argument("--body", default="")
    o.add_argument("--result", required=True)
    o.add_argument("--recorded-proposal-id", required=True)
    o.add_argument("--proposal-digest", required=True)
    o.add_argument("--authorization-digest", required=True)
    o.add_argument("--intended-base", required=True)
    o.add_argument("--expected-head-sha", required=True)
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
    r.add_argument("--observed-base", default=None)
    r.add_argument("--observed-head-sha", default=None)
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
            observed_base=args.observed_base,
            observed_head_sha=args.observed_head_sha,
            actor_id=args.actor,
            workspace=args.workspace,
        )
        print(json.dumps(doc))


if __name__ == "__main__":
    main()
