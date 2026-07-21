"""Tests for pushed-document and GitHub snapshot collection (F8 Task 4)."""
from __future__ import annotations

from dataclasses import dataclass

from lib.pulse.scripts import plan_sync_snapshot as snap


@dataclass
class Completed:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Hermetic git seam keyed by exact argv, including argv guard checks."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def __call__(self, argv, cwd=None):
        self.calls.append((tuple(argv), str(cwd) if cwd is not None else None))
        return self.responses.get(tuple(argv), Completed(1, "", f"unexpected: {argv}"))


REPO = "acme/docs"
BRANCH = "main"
PATH = "plans/release.md"
URL = "https://github.com/acme/docs.git"
HEAD = "a" * 40
BASE_BLOB = "b" * 40
CHANGED_BLOB = "c" * 40


def binding(**overrides):
    value = {
        "repo": REPO,
        "branch": BRANCH,
        "path": PATH,
        "sync": {
            "issue": {"repo": "acme/widgets", "number": 42},
            "base": {
                "blob": BASE_BLOB,
                "title": "Release plan",
                "state": "open",
                "assignees": ["ada"],
                "milestone": None,
            },
        },
    }
    value.update(overrides)
    return value


def base_git_responses(repo_dir, blob=CHANGED_BLOB):
    return {
        ("git", "init", "--bare", "-q", "--", str(repo_dir)): Completed(),
        ("git", "fetch", "--filter=blob:none", "-q", "--", URL, BRANCH): Completed(),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(0, f"{HEAD}\n"),
        ("git", "rev-parse", f"FETCH_HEAD:{PATH}"): Completed(0, f"{blob}\n"),
    }


def test_same_blob_on_unrelated_commit_short_circuits_as_in_sync(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    runner = RecordingRunner(base_git_responses(repo_dir, BASE_BLOB))
    gh_calls = []

    snapshot = snap.collect(
        [binding()], workdir=tmp_path, runner=runner,
        gh_api=lambda path: gh_calls.append(path),
    )

    document = snapshot.documents[0]
    assert document.state == "in_sync"
    assert document.head == HEAD
    assert document.blob == BASE_BLOB
    assert document.github is None
    assert snapshot.findings == ()
    assert gh_calls == []
    assert not any(call[0][1:3] == ("cat-file", "blob") for call in runner.calls)


def test_changed_blob_loads_pushed_document_and_body_base(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir)
    responses.update({
        ("git", "cat-file", "blob", CHANGED_BLOB): Completed(
            0, "---\nsync:\n  base:\n    blob: base\n---\n# Updated release\n\nChanged body.\n"
        ),
        ("git", "cat-file", "blob", BASE_BLOB): Completed(0, "# Release plan\n\nBase body.\n"),
    })

    snapshot = snap.collect([binding()], workdir=tmp_path, runner=RecordingRunner(responses))

    document = snapshot.documents[0]
    assert document.state == "changed"
    assert document.document.title == "Updated release"
    assert document.base_body == "# Release plan\n\nBase body.\n"


def test_base_body_strips_frontmatter_from_the_base_blob(tmp_path):
    # The base blob is a full bound document (frontmatter + body). base_body must
    # be the BODY only, so it compares like-for-like against the current doc's
    # frontmatter-stripped body in compute(); otherwise every bound doc's body
    # reads as changed.
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir)
    responses.update({
        ("git", "cat-file", "blob", CHANGED_BLOB): Completed(
            0, "---\nsync:\n  base:\n    blob: base\n---\n# Release plan\n\nShared body.\n"
        ),
        ("git", "cat-file", "blob", BASE_BLOB): Completed(
            0,
            "---\nsync:\n  issue: {repo: acme/widgets, number: 42}\n---\n"
            "# Release plan\n\nShared body.\n",
        ),
    })

    snapshot = snap.collect([binding()], workdir=tmp_path, runner=RecordingRunner(responses))

    document = snapshot.documents[0]
    assert document.base_body == "# Release plan\n\nShared body.\n"
    assert "sync:" not in document.base_body


def test_git_init_uses_option_separator_for_the_repo_dir(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    runner = RecordingRunner(base_git_responses(repo_dir, BASE_BLOB))

    snap.collect([binding()], workdir=tmp_path, runner=runner,
                 gh_api=lambda path: None)

    init_calls = [call[0] for call in runner.calls if call[0][:2] == ("git", "init")]
    assert init_calls == [("git", "init", "--bare", "-q", "--", str(repo_dir))]


def test_missing_head_path_reports_rename_without_silently_following_it(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir)
    responses[("git", "rev-parse", f"FETCH_HEAD:{PATH}")] = Completed(128, "", "missing")
    responses[("git", "log", "--follow", "--format=%H", "--name-only", "--", PATH)] = Completed(
        0, f"{HEAD}\nplans/renamed-release.md\n{BASE_BLOB}\n{PATH}\n"
    )

    snapshot = snap.collect([binding()], workdir=tmp_path, runner=RecordingRunner(responses))

    document = snapshot.documents[0]
    assert document.state == "excluded"
    assert document.blob is None
    assert snapshot.findings[0].kind == "rename_detected"
    assert snapshot.findings[0].new_path == "plans/renamed-release.md"


def test_dirty_or_local_ahead_checkout_is_excluded_and_nudged(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    checkout = tmp_path / "checkout"
    responses = base_git_responses(repo_dir)
    responses.update({
        ("git", "rev-parse", "--is-inside-work-tree"): Completed(0, "true\n"),
        ("git", "status", "--porcelain", "--", PATH): Completed(0, " M plans/release.md\n"),
    })
    runner = RecordingRunner(responses)

    snapshot = snap.collect([binding()], workdir=checkout, runner=runner)

    assert snapshot.documents[0].state == "excluded"
    assert snapshot.findings[0].kind == "dirty_doc"
    assert not any(call[0][1] == "fetch" for call in runner.calls)


def test_local_ahead_checkout_is_excluded_and_nudged_without_reading_it(tmp_path):
    checkout = tmp_path / "checkout"
    class LocalAheadRunner(RecordingRunner):
        def __call__(self, argv, cwd=None):
            self.calls.append((tuple(argv), str(cwd) if cwd is not None else None))
            if argv[1] in {"init", "fetch"}:
                return Completed()
            if tuple(argv) == ("git", "rev-parse", "FETCH_HEAD"):
                return Completed(0, f"{HEAD}\n")
            return self.responses.get(tuple(argv), Completed(1, "", f"unexpected: {argv}"))

    runner = LocalAheadRunner({
        ("git", "rev-parse", "--is-inside-work-tree"): Completed(0, "true\n"),
        ("git", "status", "--porcelain", "--", PATH): Completed(),
        ("git", "rev-list", "--count", f"{HEAD}..HEAD"): Completed(0, "2\n"),
    })

    snapshot = snap.collect([binding()], workdir=checkout, runner=runner)

    assert snapshot.documents[0].state == "excluded"
    assert snapshot.findings[0].kind == "local_ahead"
    assert not any(call[0][1] == "cat-file" for call in runner.calls)


def test_github_snapshot_normalizes_assignees_and_missing_milestone(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir)
    responses.update({
        ("git", "cat-file", "blob", CHANGED_BLOB): Completed(0, "# Updated release\n"),
        ("git", "cat-file", "blob", BASE_BLOB): Completed(0, "# Release plan\n"),
    })
    calls = []

    def gh_api(path):
        calls.append(path)
        if path == "/repos/acme/widgets/issues/42":
            return {
                "title": "GitHub title", "body": "GitHub body\n", "state": "open",
                "assignees": [{"login": "zoe"}, {"login": "ada"}, {"login": "zoe"}],
                "milestone": None,
            }
        if path == "/repos/acme/widgets/milestones?state=all&per_page=100":
            return [{"title": "M2"}, {"title": "M1"}]
        raise AssertionError(path)

    snapshot = snap.collect([binding()], workdir=tmp_path, runner=RecordingRunner(responses), gh_api=gh_api)

    assert snapshot.documents[0].github == {
        "title": "GitHub title", "body": "GitHub body\n", "state": "open",
        "assignees": ["ada", "zoe"], "milestone": None,
    }
    assert snapshot.documents[0].milestones == ("M1", "M2")
    assert calls == [
        "/repos/acme/widgets/issues/42",
        "/repos/acme/widgets/milestones?state=all&per_page=100",
    ]
