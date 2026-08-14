#!/usr/bin/env python3
"""GitHub CLI adapter for PR-gated Contents API document updates."""
from __future__ import annotations

import base64
import json
import subprocess
from typing import Callable


class GhContentsCliOps:
    """Run the narrow GitHub operations needed by the F8 finalizer."""

    def __init__(
        self,
        gh_binary: str = "gh",
        run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self.gh_binary = gh_binary
        self.run = run

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return self.run(cmd, capture_output=True, text=True, check=False)

    @staticmethod
    def _failure(result: subprocess.CompletedProcess, operation: str) -> dict:
        reason = result.stderr.strip() or result.stdout.strip()
        return {
            "state": "failed",
            "reason": reason or f"{operation} failed with exit code {result.returncode}",
        }

    def get_file(self, repo: str, path: str, ref: str) -> dict:
        result = self._run(
            [self.gh_binary, "api", f"repos/{repo}/contents/{path}?ref={ref}"]
        )
        if result.returncode != 0:
            return self._failure(result, "get file")
        try:
            data = json.loads(result.stdout)
            content = base64.b64decode(data["content"], validate=True).decode("utf-8")
            file_sha = data["sha"]
        except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {"state": "failed", "reason": f"invalid get-file response: {exc}"}
        return {"state": "ok", "content": content, "file_sha": file_sha}

    def create_branch(self, repo: str, branch: str, base: str) -> dict:
        base_result = self._run(
            [self.gh_binary, "api", f"repos/{repo}/git/refs/heads/{base}"]
        )
        if base_result.returncode != 0:
            return self._failure(base_result, "read base ref")
        try:
            base_sha = json.loads(base_result.stdout)["object"]["sha"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            return {"state": "failed", "reason": f"invalid base-ref response: {exc}"}

        result = self._run(
            [
                self.gh_binary,
                "api",
                "-X",
                "POST",
                f"repos/{repo}/git/refs",
                "-f",
                f"ref=refs/heads/{branch}",
                "-f",
                f"sha={base_sha}",
            ]
        )
        if result.returncode != 0:
            return self._failure(result, "create branch")
        return {"state": "ok"}

    def put_file(
        self,
        repo: str,
        path: str,
        content: str,
        file_sha: str,
        branch: str,
        message: str,
    ) -> dict:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        result = self._run(
            [
                self.gh_binary,
                "api",
                "-X",
                "PUT",
                f"repos/{repo}/contents/{path}",
                "-f",
                f"branch={branch}",
                "-f",
                f"message={message}",
                "-f",
                f"sha={file_sha}",
                "-f",
                f"content={encoded}",
            ]
        )
        if result.returncode != 0:
            return self._failure(result, "put file")
        return {"state": "ok"}

    def open_pr(
        self, repo: str, branch: str, base: str, title: str, body: str
    ) -> dict:
        result = self._run(
            [
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
        )
        if result.returncode != 0:
            return self._failure(result, "open PR")
        return {"url": result.stdout.strip()}

    def view_pr(self, repo: str, branch: str) -> dict:
        result = self._run(
            [
                self.gh_binary,
                "pr",
                "view",
                branch,
                "-R",
                repo,
                "--json",
                "state,mergedAt,mergeCommit",
            ]
        )
        if result.returncode != 0:
            failed = self._failure(result, "view PR")
            return {
                **failed,
                "merged": False,
                "merge_commit_sha": None,
            }
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return {
                "state": "failed",
                "reason": f"invalid PR response: {exc}",
                "merged": False,
                "merge_commit_sha": None,
            }
        state = str(data.get("state", "CLOSED")).upper()
        merged = bool(data.get("mergedAt")) or state == "MERGED"
        merge_commit = data.get("mergeCommit")
        merge_sha = (
            merge_commit.get("oid")
            if isinstance(merge_commit, dict)
            else merge_commit if isinstance(merge_commit, str) else None
        )
        return {
            "state": "MERGED" if merged else state,
            "merged": merged,
            "merge_commit_sha": merge_sha if merged else None,
        }
