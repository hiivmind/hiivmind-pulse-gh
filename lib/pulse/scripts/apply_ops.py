"""Nave-backed operations used by the apply-mode driver phases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from lib.pulse.scripts import nave_adapter


class ApplyOps(Protocol):
    def provision_branch(self, branch: str, base_shas: dict[str, str]) -> dict[str, dict]: ...

    def commit_repos(
        self, message: str, bound_paths: dict[str, tuple[str, ...]]
    ) -> dict[str, dict]: ...

    def push_repos(self, branch: str) -> dict[str, dict]: ...

    def reset_repos(
        self, branch: str, expected_pushed_shas: dict[str, str | None]
    ) -> dict[str, dict]: ...


@dataclass
class _NaveApplyOps:
    runner: object
    pen_name: str
    bound_paths_by_repo: dict[str, tuple[str, ...]]
    base_refs: dict[str, str]
    _apply_branch: str | None = field(default=None, init=False)

    def provision_branch(self, branch: str, base_shas: dict[str, str]) -> dict[str, dict]:
        self._apply_branch = branch
        request = [
            {
                "repo": repo,
                "base_ref": self.base_refs[repo],
                "expected_base_sha": base_shas[repo],
            }
            for repo in self.bound_paths_by_repo
        ]
        return nave_adapter.pen_branch(self.runner, self.pen_name, branch, request)

    def commit_repos(
        self, message: str, bound_paths: dict[str, tuple[str, ...]]
    ) -> dict[str, dict]:
        if self._apply_branch is None:
            raise RuntimeError("provision_branch must run before commit_repos")
        request = [
            {"repo": repo, "paths": list(bound_paths[repo])}
            for repo in self.bound_paths_by_repo
        ]
        return nave_adapter.pen_commit(
            self.runner, self.pen_name, self._apply_branch, request, message
        )

    def push_repos(self, branch: str) -> dict[str, dict]:
        return nave_adapter.pen_push(
            self.runner,
            self.pen_name,
            branch,
            [{"repo": repo} for repo in self.bound_paths_by_repo],
        )

    def reset_repos(
        self, branch: str, expected_pushed_shas: dict[str, str | None]
    ) -> dict[str, dict]:
        request = [
            {"repo": repo, "expected_pushed_sha": expected_pushed_shas.get(repo)}
            for repo in self.bound_paths_by_repo
        ]
        return nave_adapter.pen_reset(self.runner, self.pen_name, branch, request)


def make_apply_ops(runner, pen_name, bound_paths_by_repo, base_refs) -> ApplyOps:
    return _NaveApplyOps(runner, pen_name, bound_paths_by_repo, base_refs)
