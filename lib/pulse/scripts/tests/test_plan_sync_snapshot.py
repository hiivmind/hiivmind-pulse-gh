"""Tests for pushed-document and GitHub snapshot collection (F8 Task 4)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

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
        response = self.responses.get(tuple(argv))
        if response is None and argv[:5] == ["git", "init", "--bare", "-q", "--"]:
            response = next(
                (value for key, value in self.responses.items() if key[:5] == tuple(argv[:5])),
                None,
            )
        return response or Completed(1, "", f"unexpected: {argv}")


REPO = "acme/docs"
BRANCH = "main"
PATH = "plans/release.md"
URL = "https://github.com/acme/docs.git"
HEAD = "a" * 40
BASE_BLOB = "b" * 40
CHANGED_BLOB = "c" * 40


def binding(**overrides):
    value = {
        "id": "release-plan",
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
        ("git", "fetch", "--filter=blob:none", "-q", "--", URL, f"refs/heads/{BRANCH}"): Completed(),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(0, f"{HEAD}\n"),
        ("git", "rev-parse", f"FETCH_HEAD:{PATH}"): Completed(0, f"{blob}\n"),
    }


def test_same_blob_on_unrelated_commit_is_in_sync_only_after_github_snapshot(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir, BASE_BLOB)
    responses[("git", "cat-file", "blob", BASE_BLOB)] = Completed(
        0,
        "---\nsync:\n"
        "  issue: {repo: acme/widgets, number: 42}\n"
        f"  base: {{blob: {BASE_BLOB}, title: Release plan, state: open, assignees: [ada], milestone: null}}\n"
        "---\n# Release plan\n\nBase body.\n",
    )
    runner = RecordingRunner(responses)
    gh_calls = []

    def gh_api(path):
        gh_calls.append(path)
        if path.endswith("/issues/42"):
            return {
                "title": "Release plan", "body": "# Release plan\n\nBase body.\n",
                "state": "open", "assignees": [{"login": "ada"}], "milestone": None,
            }
        return []

    snapshot = snap.collect(
        [binding()], workdir=tmp_path, runner=runner,
        gh_api=gh_api,
    )

    document = snapshot.documents[0]
    assert document.state == "in_sync"
    assert document.head == HEAD
    assert document.blob == BASE_BLOB
    assert document.github is not None
    assert snapshot.findings == ()
    assert gh_calls == [
        "/repos/acme/widgets/issues/42",
        "/repos/acme/widgets/milestones?state=all&per_page=100",
    ]


def test_changed_blob_loads_pushed_document_and_body_base(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir)
    responses.update({
        ("git", "cat-file", "blob", CHANGED_BLOB): Completed(
            0,
            "---\nsync:\n"
            "  issue: {repo: acme/widgets, number: 42}\n"
            f"  base: {{blob: {BASE_BLOB}, title: Release plan, state: open, assignees: [ada], milestone: null}}\n"
            "---\n# Updated release\n\nChanged body.\n",
        ),
        ("git", "cat-file", "blob", BASE_BLOB): Completed(0, "# Release plan\n\nBase body.\n"),
    })

    snapshot = snap.collect(
        [binding()], workdir=tmp_path, runner=RecordingRunner(responses),
        gh_api=lambda path: ({
            "title": "Release plan", "body": "# Release plan\n\nBase body.\n",
            "state": "open", "assignees": [{"login": "ada"}], "milestone": None,
        } if "/issues/" in path else []),
    )

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
            0,
            "---\nsync:\n"
            "  issue: {repo: acme/widgets, number: 42}\n"
            f"  base: {{blob: {BASE_BLOB}, title: Release plan, state: open, assignees: [ada], milestone: null}}\n"
            "---\n# Release plan\n\nShared body.\n",
        ),
        ("git", "cat-file", "blob", BASE_BLOB): Completed(
            0,
            "---\nsync:\n  issue: {repo: acme/widgets, number: 42}\n---\n"
            "# Release plan\n\nShared body.\n",
        ),
    })

    snapshot = snap.collect(
        [binding()], workdir=tmp_path, runner=RecordingRunner(responses),
        gh_api=lambda path: ({
            "title": "Release plan", "body": "# Release plan\n\nShared body.\n",
            "state": "open", "assignees": [{"login": "ada"}], "milestone": None,
        } if "/issues/" in path else []),
    )

    document = snapshot.documents[0]
    assert document.base_body == "# Release plan\n\nShared body.\n"
    assert "sync:" not in document.base_body


def test_git_init_uses_option_separator_for_the_repo_dir(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    runner = RecordingRunner(base_git_responses(repo_dir, BASE_BLOB))

    snap.collect([binding()], workdir=tmp_path, runner=runner,
                 gh_api=lambda path: None)

    init_calls = [call[0] for call in runner.calls if call[0][:2] == ("git", "init")]
    assert len(init_calls) == 1
    assert init_calls[0][:5] == ("git", "init", "--bare", "-q", "--")
    assert tmp_path not in Path(init_calls[0][-1]).parents


def test_missing_head_path_reports_rename_without_silently_following_it(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir)
    responses[("git", "rev-parse", f"FETCH_HEAD:{PATH}")] = Completed(128, "", "missing")
    responses[("git", "log", "FETCH_HEAD", "--format=%H", "--name-status", "--find-renames", "--diff-filter=R")] = Completed(
        0, f"{HEAD}\nR100\t{PATH}\tplans/renamed-release.md\n"
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
        ("git", "cat-file", "blob", CHANGED_BLOB): Completed(
            0,
            "---\nsync:\n"
            "  issue: {repo: acme/widgets, number: 42}\n"
            f"  base: {{blob: {BASE_BLOB}, title: Release plan, state: open, assignees: [ada], milestone: null}}\n"
            "---\n# Updated release\n",
        ),
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


def test_pushed_frontmatter_overrides_stale_config_sync_binding(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    pushed_base = "d" * 40
    responses = base_git_responses(repo_dir)
    responses.update({
        ("git", "cat-file", "blob", CHANGED_BLOB): Completed(
            0,
            "---\n"
            "sync:\n"
            "  issue: {repo: acme/widgets, number: 99}\n"
            "  policy: {title: prefer-github}\n"
            f"  base: {{blob: {pushed_base}, title: Pushed base, state: open, assignees: [], milestone: null}}\n"
            "---\n# Pushed title\n",
        ),
        ("git", "cat-file", "blob", pushed_base): Completed(0, "# Pushed base\n"),
    })
    calls = []

    def gh_api(path):
        calls.append(path)
        if path == "/repos/acme/widgets/issues/99":
            return {"title": "Issue 99", "body": "# Pushed base\n", "state": "open"}
        if path == "/repos/acme/widgets/milestones?state=all&per_page=100":
            return []
        raise AssertionError(path)

    snapshot = snap.collect(
        [binding()], workdir=tmp_path, runner=RecordingRunner(responses), gh_api=gh_api
    )

    document = snapshot.documents[0]
    assert document.binding["sync"]["issue"]["number"] == 99
    assert document.binding["sync"]["policy"] == {"title": "prefer-github"}
    assert document.binding["sync"]["base"]["blob"] == pushed_base
    assert document.base_body == "# Pushed base\n"
    assert calls[0] == "/repos/acme/widgets/issues/99"


def test_unchanged_document_still_detects_github_only_state_change(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    document_text = (
        "---\nsync:\n"
        "  issue: {repo: acme/widgets, number: 42}\n"
        f"  base: {{blob: {BASE_BLOB}, title: Release plan, state: open, assignees: [ada], milestone: null}}\n"
        "---\n# Release plan\n\nBase body.\n"
    )
    responses = base_git_responses(repo_dir, BASE_BLOB)
    responses[("git", "cat-file", "blob", BASE_BLOB)] = Completed(0, document_text)

    def gh_api(path):
        if path.endswith("/issues/42"):
            return {
                "title": "Release plan", "body": "# Release plan\n\nBase body.\n",
                "state": "closed", "assignees": [{"login": "ada"}], "milestone": None,
            }
        return []

    snapshot = snap.collect(
        [binding()], workdir=tmp_path, runner=RecordingRunner(responses), gh_api=gh_api
    )

    document = snapshot.documents[0]
    assert document.state == "changed"
    assert document.github["state"] == "closed"


def test_missing_github_evidence_is_an_explicit_error_and_finding(tmp_path):
    repo_dir = tmp_path / "acme_docs_main"
    responses = base_git_responses(repo_dir)
    responses.update({
        ("git", "cat-file", "blob", CHANGED_BLOB): Completed(
            0,
            "---\nsync:\n"
            "  issue: {repo: acme/widgets, number: 42}\n"
            f"  base: {{blob: {BASE_BLOB}, title: Release plan, state: open, assignees: [], milestone: null}}\n"
            "---\n# Release plan\n",
        ),
        ("git", "cat-file", "blob", BASE_BLOB): Completed(0, "# Release plan\n"),
    })

    snapshot = snap.collect(
        [binding()], workdir=tmp_path, runner=RecordingRunner(responses), gh_api=lambda _path: None
    )

    assert snapshot.documents[0].state == "error"
    assert snapshot.findings[0].kind == "snapshot_error"
    assert "GitHub" in snapshot.findings[0].detail


def test_non_repo_workspace_is_never_used_as_a_persistent_bare_fetch_directory(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class TempRunner(RecordingRunner):
        def __call__(self, argv, cwd=None):
            self.calls.append((tuple(argv), str(cwd) if cwd is not None else None))
            if argv[1] in {"init", "fetch"}:
                return Completed()
            if tuple(argv) == ("git", "rev-parse", "FETCH_HEAD"):
                return Completed(0, f"{HEAD}\n")
            if tuple(argv) == ("git", "rev-parse", f"FETCH_HEAD:{PATH}"):
                return Completed(128, "", "missing")
            if argv[1] == "log":
                return Completed(1)
            return Completed(1)

    runner = TempRunner()
    snap.collect([binding()], workdir=workspace, runner=runner)

    init_target = Path(next(call[0][-1] for call in runner.calls if call[0][1] == "init"))
    assert workspace not in init_target.parents
    assert list(workspace.iterdir()) == []


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_rename_detection_uses_fetch_head_in_a_real_bare_repository(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-q", "-b", "main")
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Test User")
    (source / "plans").mkdir()
    (source / "plans" / "old.md").write_text("old\n")
    _git(source, "add", "plans/old.md")
    _git(source, "commit", "-q", "-m", "add plan")
    _git(source, "mv", "plans/old.md", "plans/new.md")
    _git(source, "commit", "-q", "-m", "rename plan")

    bare = tmp_path / "snapshot.git"
    _git(tmp_path, "init", "--bare", "-q", str(bare))
    _git(bare, "fetch", "-q", str(source), "refs/heads/main")

    assert snap._rename_target(snap.default_runner, bare, "plans/old.md") == "plans/new.md"


def test_branch_refspec_destination_is_rejected_and_valid_fetch_is_explicit(tmp_path):
    bad = binding(branch="main:refs/heads/injected")
    bad_runner = RecordingRunner()

    snapshot = snap.collect([bad], workdir=tmp_path, runner=bad_runner)

    assert snapshot.documents[0].state == "error"
    assert not any(call[0][1] == "fetch" for call in bad_runner.calls)

    class FetchRunner(RecordingRunner):
        def __call__(self, argv, cwd=None):
            self.calls.append((tuple(argv), str(cwd) if cwd is not None else None))
            if argv[1] in {"init", "fetch"}:
                return Completed()
            if tuple(argv) == ("git", "rev-parse", "FETCH_HEAD"):
                return Completed(1)
            return Completed(1)

    good_runner = FetchRunner()
    snap.collect([binding()], workdir=tmp_path, runner=good_runner)
    fetch = next(call[0] for call in good_runner.calls if call[0][1] == "fetch")
    assert fetch[-1] == "refs/heads/main"


def test_missing_locator_id_is_a_fail_closed_error_not_a_crash(tmp_path):
    """An id-less binding must bucket as error, never reach fetch or crash RECORD.

    build_apply_plans/build_result hard-require binding.id; without in-collect
    enforcement an id-less binding would raise deep in RECORD and leave no
    result file. collect must reject it as a clean error-state document.
    """
    bad = binding()
    del bad["id"]
    runner = RecordingRunner()

    snapshot = snap.collect([bad], workdir=tmp_path, runner=runner)

    assert snapshot.documents[0].state == "error"
    assert snapshot.findings[0].kind == "snapshot_error"
    assert not any(call[0][1] == "fetch" for call in runner.calls)
