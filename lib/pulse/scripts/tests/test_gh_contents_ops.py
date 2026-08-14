"""Command-contract tests for GitHub Contents API operations."""

import base64
import json

from lib.pulse.scripts.gh_contents_ops import GhContentsCliOps


class Result:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_get_file_decodes_content_and_returns_contents_sha():
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        payload = base64.b64encode(b"# Plan\n").decode("ascii")
        return Result(json.dumps({"content": payload, "sha": "file-sha-1"}))

    result = GhContentsCliOps(run=run).get_file(
        "acme/plans", "plans/one.md", "merged-sha"
    )

    assert result == {"state": "ok", "content": "# Plan\n", "file_sha": "file-sha-1"}
    assert calls == [
        (
            [
                "gh",
                "api",
                "repos/acme/plans/contents/plans/one.md?ref=merged-sha",
            ],
            {"capture_output": True, "text": True, "check": False},
        )
    ]


def test_create_branch_reads_base_tip_then_posts_ref():
    calls = []
    responses = iter(
        [Result(json.dumps({"object": {"sha": "base-tip"}})), Result("{}")]
    )

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return next(responses)

    result = GhContentsCliOps(run=run).create_branch(
        "acme/plans", "pulse/advance-base/p-1", "develop"
    )

    assert result == {"state": "ok"}
    assert calls[0][0] == [
        "gh",
        "api",
        "repos/acme/plans/git/refs/heads/develop",
    ]
    assert calls[1][0] == [
        "gh",
        "api",
        "-X",
        "POST",
        "repos/acme/plans/git/refs",
        "-f",
        "ref=refs/heads/pulse/advance-base/p-1",
        "-f",
        "sha=base-tip",
    ]


def test_put_file_supplies_file_sha_cas_and_base64_content():
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Result("{}")

    result = GhContentsCliOps(run=run).put_file(
        "acme/plans",
        "plans/one.md",
        "updated\n",
        "current-file-sha",
        "pulse/advance-base/p-1",
        "Advance plan-sync base for p-1",
    )

    assert result == {"state": "ok"}
    assert calls[0][0] == [
        "gh",
        "api",
        "-X",
        "PUT",
        "repos/acme/plans/contents/plans/one.md",
        "-f",
        "branch=pulse/advance-base/p-1",
        "-f",
        "message=Advance plan-sync base for p-1",
        "-f",
        "sha=current-file-sha",
        "-f",
        f"content={base64.b64encode(b'updated\n').decode('ascii')}",
    ]


def test_open_pr_returns_url_and_uses_bookkeeping_branch():
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Result("https://github.com/acme/plans/pull/42\n")

    result = GhContentsCliOps(run=run).open_pr(
        "acme/plans",
        "pulse/advance-base/p-1",
        "develop",
        "Advance plan-sync base",
        "Bookkeeping update",
    )

    assert result == {"url": "https://github.com/acme/plans/pull/42"}
    assert calls[0][0] == [
        "gh",
        "pr",
        "create",
        "-R",
        "acme/plans",
        "--head",
        "pulse/advance-base/p-1",
        "--base",
        "develop",
        "--title",
        "Advance plan-sync base",
        "--body",
        "Bookkeeping update",
    ]


def test_view_pr_reports_merged_and_unmerged_states():
    calls = []
    responses = iter(
        [
            Result(
                json.dumps(
                    {
                        "state": "MERGED",
                        "mergedAt": "2026-08-14T00:00:00Z",
                        "mergeCommit": {"oid": "merge-42"},
                    }
                )
            ),
            Result(
                json.dumps(
                    {"state": "OPEN", "mergedAt": None, "mergeCommit": None}
                )
            ),
        ]
    )

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return next(responses)

    ops = GhContentsCliOps(run=run)
    merged = ops.view_pr("acme/plans", "pulse/advance-base/p-1")
    unmerged = ops.view_pr("acme/plans", "pulse/advance-base/p-1")

    assert merged == {
        "state": "MERGED",
        "merged": True,
        "merge_commit_sha": "merge-42",
    }
    assert unmerged == {
        "state": "OPEN",
        "merged": False,
        "merge_commit_sha": None,
    }
    assert calls[0][0] == [
        "gh",
        "pr",
        "view",
        "pulse/advance-base/p-1",
        "-R",
        "acme/plans",
        "--json",
        "state,mergedAt,mergeCommit",
    ]


def test_get_file_tolerates_newline_wrapped_base64():
    raw = b"# Plan\nbody line\n"
    encoded = base64.b64encode(raw).decode("ascii")
    wrapped = "\n".join(encoded[i : i + 60] for i in range(0, len(encoded), 60))

    def run(cmd, **kwargs):
        return Result(json.dumps({"content": wrapped, "sha": "file-sha-wrapped"}))

    result = GhContentsCliOps(run=run).get_file("acme/plans", "p.md", "ref")

    assert result == {
        "state": "ok",
        "content": "# Plan\nbody line\n",
        "file_sha": "file-sha-wrapped",
    }
