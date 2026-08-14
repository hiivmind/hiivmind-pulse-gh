"""Tests for the PR-gated F8 document-blob finalizer."""

import hashlib
import json

from lib.pulse.scripts.apply_advance_base import make_f8_advance_base
from lib.pulse.scripts import apply_reconcile
from lib.pulse.scripts import plan_sync


PRIOR = "1" * 40
DESIRED_CONTENT = "---\nsync:\n  base:\n    blob: old\n---\n# Updated plan\n\nNew body.\n"
DESIRED_BLOB = hashlib.sha1(
    f"blob {len(DESIRED_CONTENT.encode())}\0".encode() + DESIRED_CONTENT.encode(),
    usedforsecurity=False,
).hexdigest()


def document(blob, body="# Plan\n\nBody.\n"):
    return f"---\nsync:\n  base:\n    blob: {blob}\n---\n{body}"


class FakeContentsOps:
    def __init__(self, current_content):
        self.current_content = current_content
        self.created = []
        self.puts = []
        self.opened = []

    def get_file(self, repo, path, ref):
        if ref == "merged-sha":
            return {
                "state": "ok",
                "content": DESIRED_CONTENT,
                "file_sha": "merged-file-sha",
            }
        return {
            "state": "ok",
            "content": self.current_content,
            "file_sha": "current-file-sha",
        }

    def create_branch(self, repo, branch, base):
        self.created.append((repo, branch, base))
        return {"state": "ok"}

    def put_file(self, repo, path, content, file_sha, branch, message):
        self.puts.append((repo, path, content, file_sha, branch, message))
        return {"state": "ok"}

    def open_pr(self, repo, branch, base, title, body):
        self.opened.append((repo, branch, base, title, body))
        return {"url": "https://github.com/acme/plans/pull/42"}


class FakeGhOps:
    def __init__(self, merged=False):
        self.merged = merged
        self.views = []

    def view_pr(self, repo, branch):
        self.views.append((repo, branch))
        return {
            "state": "MERGED" if self.merged else "CLOSED",
            "merged": self.merged,
            "merge_commit_sha": "bookkeeping-merge" if self.merged else None,
        }


def record():
    return {
        "repo": "acme/plans",
        "base_ref": "develop",
        "doc_path": "plans/one.md",
        "expected_prior_blob": PRIOR,
        "proposal_id": "p-1",
        "binding_id": "binding-1",
    }


def test_semantic_cas_mismatch_blocks_without_mutation():
    contents = FakeContentsOps(document("2" * 40))

    result = make_f8_advance_base(record(), contents, FakeGhOps())(
        "acme/plans", "merged-sha"
    )

    assert result["state"] == "blocked"
    assert "expected prior blob" in result["reason"]
    assert not contents.created
    assert not contents.puts
    assert not contents.opened


def test_already_advanced_is_ok_without_pr():
    contents = FakeContentsOps(document(DESIRED_BLOB))

    result = make_f8_advance_base(record(), contents, FakeGhOps())(
        "acme/plans", "merged-sha"
    )

    assert result == {"state": "ok"}
    assert not contents.created
    assert not contents.puts
    assert not contents.opened


def test_first_pass_patches_blob_opens_pr_and_blocks_on_gate():
    contents = FakeContentsOps(document(PRIOR))

    result = make_f8_advance_base(record(), contents, FakeGhOps())(
        "acme/plans", "merged-sha"
    )

    assert result == {"state": "blocked-on-gate"}
    assert contents.created == [
        ("acme/plans", "pulse/advance-base/p-1", "develop")
    ]
    assert len(contents.puts) == 1
    parsed = plan_sync.parse_document(contents.puts[0][2])
    assert parsed.binding["base"]["blob"] == DESIRED_BLOB
    assert contents.puts[0][3] == "current-file-sha"
    assert len(contents.opened) == 1


def test_merged_pr_is_ok_only_after_base_observes_desired_blob():
    contents = FakeContentsOps(document(DESIRED_BLOB))
    gh_ops = FakeGhOps(merged=True)

    result = make_f8_advance_base(record(), contents, gh_ops)(
        "acme/plans", "merged-sha"
    )

    assert result == {"state": "ok"}
    assert gh_ops.views == [("acme/plans", "pulse/advance-base/p-1")]
    assert not contents.opened


def test_frontmatter_patch_preserves_multiline_body_and_only_changes_base_blob():
    body = "# Plan title\n\nParagraph one.\n\n- alpha\n- beta  \n\n```yaml\nkey: value\n```\n"
    original = (
        "---\n"
        "owner: team-a\n"
        "sync:\n"
        "  issue:\n"
        "    repo: acme/issues\n"
        "    number: 7\n"
        f"  base:\n    blob: {PRIOR}\n"
        "---\n"
        + body
    )
    contents = FakeContentsOps(original)

    result = make_f8_advance_base(record(), contents, FakeGhOps())(
        "acme/plans", "merged-sha"
    )

    assert result == {"state": "blocked-on-gate"}
    patched = contents.puts[0][2]
    before = plan_sync.parse_document(original)
    after = plan_sync.parse_document(patched)
    assert after.body == before.body == body
    assert after.frontmatter["owner"] == "team-a"
    assert after.binding["issue"] == before.binding["issue"]
    assert str(before.binding["base"]["blob"]) == PRIOR
    assert after.binding["base"]["blob"] == DESIRED_BLOB


def test_reconcile_cli_loads_finalizer_record_and_wires_advance_base(
    tmp_path, monkeypatch, capsys
):
    record_path = tmp_path / "finalizer.json"
    record_path.write_text(json.dumps(record()), encoding="utf-8")
    captured = {}

    class ContentsSentinel:
        pass

    gh_sentinel = object()
    contents_sentinel = ContentsSentinel()

    monkeypatch.setattr(apply_reconcile, "GhCliOps", lambda: gh_sentinel)
    monkeypatch.setattr(apply_reconcile, "GhContentsCliOps", lambda: contents_sentinel)

    def fake_make(loaded_record, contents_ops, gh_ops):
        captured["factory"] = (loaded_record, contents_ops, gh_ops)
        return lambda repo, merged_sha: {"state": "ok"}

    def fake_reconcile_apply(**kwargs):
        captured["advance_base"] = kwargs["advance_base"]
        return {"state": "waiting"}

    monkeypatch.setattr(apply_reconcile, "make_f8_advance_base", fake_make)
    monkeypatch.setattr(apply_reconcile, "reconcile_apply", fake_reconcile_apply)
    monkeypatch.setattr(
        "sys.argv",
        [
            "apply_reconcile.py",
            "reconcile",
            "--ledger",
            "ledger.yaml",
            "--step",
            "step-1",
            "--proposal-id",
            "p-1",
            "--repo",
            "acme/plans",
            "--branch",
            "pulse/apply/p-1",
            "--result",
            "result.yaml",
            "--recorded-proposal-id",
            "p-1",
            "--proposal-digest",
            "v1|" + "a" * 64,
            "--authorization-digest",
            "v1|" + "b" * 64,
            "--intended-base",
            "develop",
            "--expected-head-sha",
            "pushed-sha",
            "--finalizer-record",
            str(record_path),
        ],
    )

    apply_reconcile.main()

    assert captured["factory"] == (record(), contents_sentinel, gh_sentinel)
    assert callable(captured["advance_base"])
    assert json.loads(capsys.readouterr().out) == {"state": "waiting"}
