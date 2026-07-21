"""Offline acceptance coverage for the F8 plan synchronization contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from lib.pulse.scripts import (
    mutation_plan,
    nave_adapter,
    pen_orchestrator,
    plan_sync,
    plan_sync_snapshot,
    validate_result,
)


SKILL = Path("skills/gh-plan-sync-headless/SKILL.md")
WORKFLOW = Path("templates/workflows/plan-sync.yaml")
HEAD = "a" * 40
BASE_BLOB = "b" * 40
CURRENT_BLOB = "c" * 40
REPO = "acme/docs"
ISSUE_REPO = "acme/widgets"
PATH = "plans/release.md"
ACTOR = {"gh_login": "octocat", "machine": "acceptance-mba", "mode": "scheduled"}
BASE = {
    "title": "Release plan",
    "state": "open",
    "assignees": ["ada"],
    "milestone": None,
    "body": "# Release plan\n\nBase body.\n",
}


@dataclass
class Completed:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class SnapshotRunner:
    """Hermetic remote-document fixture; no subprocesses or network."""

    def __init__(
        self,
        document: str,
        *,
        blob: str = CURRENT_BLOB,
        base_document: str = BASE["body"],
        rename: str | None = None,
    ):
        self.document = document
        self.blob = blob
        self.base_document = base_document
        self.rename = rename
        self.calls = []

    def __call__(self, argv, cwd=None):
        self.calls.append(tuple(argv))
        if tuple(argv) == ("git", "rev-parse", "--is-inside-work-tree"):
            return Completed(1)
        if argv[:3] == ["git", "init", "--bare"] or argv[:2] == ["git", "fetch"]:
            return Completed()
        if tuple(argv) == ("git", "rev-parse", "FETCH_HEAD"):
            return Completed(0, f"{HEAD}\n")
        if tuple(argv) == ("git", "rev-parse", f"FETCH_HEAD:{PATH}"):
            return Completed(0, f"{self.blob}\n") if self.rename is None else Completed(128, "", "missing")
        if tuple(argv[:3]) == ("git", "cat-file", "blob"):
            return Completed(0, self.document if argv[-1] == self.blob else self.base_document)
        if tuple(argv[:3]) == ("git", "log", "FETCH_HEAD") and self.rename:
            return Completed(0, f"{HEAD}\nR100\t{PATH}\t{self.rename}\n")
        return Completed(1, "", f"unexpected: {argv}")


def _binding(base_blob: str = BASE_BLOB):
    return {
        "id": "release-plan",
        "repo": REPO,
        "branch": "main",
        "path": PATH,
        "sync": {
            "issue": {"repo": ISSUE_REPO, "number": 42},
            "base": {key: value for key, value in BASE.items() if key != "body"} | {"blob": base_blob},
        },
    }


def _document(values: dict, *, sync_base: dict = BASE, sync_blob: str = BASE_BLOB) -> str:
    return (
        "---\n"
        f"state: {values['state']}\n"
        f"assignees: [{', '.join(values['assignees'])}]\n"
        f"milestone: {values['milestone'] if values['milestone'] is not None else ''}\n"
        "sync:\n"
        "  issue: {repo: acme/widgets, number: 42}\n"
        f"  base: {{blob: {sync_blob}, title: {sync_base['title']}, state: {sync_base['state']}, "
        f"assignees: [{', '.join(sync_base['assignees'])}], "
        f"milestone: {sync_base['milestone'] if sync_base['milestone'] is not None else 'null'}}}\n"
        "---\n"
        f"# {values['title']}\n\n"
        f"{values['body'].split('\n\n', 1)[1]}"
    )


def _github(values: dict):
    def api(endpoint):
        if endpoint == "/repos/acme/widgets/issues/42":
            return {
                "title": values["title"], "body": values["body"], "state": values["state"],
                "assignees": [{"login": name} for name in values["assignees"]],
                "milestone": None if values["milestone"] is None else {"title": values["milestone"]},
            }
        if endpoint == "/repos/acme/widgets/milestones?state=all&per_page=100":
            return []
        raise AssertionError(endpoint)
    return api


def _snapshot(
    values: dict,
    tmp_path,
    *,
    blob: str = CURRENT_BLOB,
    github_values: dict | None = None,
    sync_base: dict = BASE,
    sync_blob: str = BASE_BLOB,
    base_document: str = BASE["body"],
):
    return plan_sync_snapshot.collect(
        [_binding()],
        workdir=tmp_path,
        runner=SnapshotRunner(
            _document(values, sync_base=sync_base, sync_blob=sync_blob),
            blob=blob,
            base_document=base_document,
        ),
        gh_api=_github(github_values or values),
    )


def _collect(values: dict, tmp_path, *, blob: str = CURRENT_BLOB, github_values: dict | None = None):
    return _snapshot(values, tmp_path, blob=blob, github_values=github_values).documents[0]


def _result(snapshot):
    return plan_sync.build_result(
        snapshot,
        workspace="acme",
        run_at="2026-07-21T00:00:00Z",
        actor=ACTOR,
    )


@pytest.mark.parametrize(
    ("doc_values", "github_values", "expected"),
    [
        (BASE, BASE, {"in_sync": 1}),
        (BASE | {"title": "Document title"}, BASE, {"github_patches": 1}),
        (BASE, BASE | {"state": "closed"}, {"doc_patches": 1}),
        (BASE | {"title": "Document title"}, BASE | {"title": "GitHub title"}, {"conflicts": 1}),
        (BASE | {"title": "Shared title"}, BASE | {"title": "Shared title"}, {"doc_patches": 1}),
    ],
    ids=("noop", "document-to-github", "github-to-document", "conflict", "agree"),
)
def test_merge_outcomes_land_in_their_result_buckets(tmp_path, doc_values, github_values, expected):
    result = _result(_snapshot(doc_values, tmp_path, github_values=github_values))

    assert {key: result[key] for key in expected} == expected
    assert "proposals" in result
    assert "proposed_actions" in result


def test_rename_and_local_ahead_are_excluded_from_reconciliation(tmp_path):
    renamed = plan_sync_snapshot.collect(
        [_binding()], workdir=tmp_path,
        runner=SnapshotRunner(_document(BASE), rename="plans/renamed-release.md"), gh_api=_github(BASE),
    )
    assert renamed.documents[0].state == "excluded"
    assert _result(renamed)["excluded"] == 1

    class LocalAheadRunner(SnapshotRunner):
        def __call__(self, argv, cwd=None):
            if tuple(argv) == ("git", "rev-parse", "--is-inside-work-tree"):
                return Completed(0, "true\n")
            if tuple(argv) == ("git", "status", "--porcelain", "--", PATH):
                return Completed()
            if tuple(argv) == ("git", "rev-list", "--count", f"{HEAD}..HEAD"):
                return Completed(0, "1\n")
            return super().__call__(argv, cwd)

    ahead = plan_sync_snapshot.collect(
        [_binding()], workdir=tmp_path, runner=LocalAheadRunner(_document(BASE)), gh_api=_github(BASE)
    )
    assert ahead.documents[0].state == "excluded"
    assert _result(ahead)["excluded"] == 1


def _pen_show():
    return nave_adapter.Completed(0, json.dumps({
        "name": "nave/plan-sync", "created_at": "2026-07-21T00:00:00Z", "branch": "nave/plan-sync",
        "filter": {"terms": []}, "repos": [{"owner": "acme", "name": "docs", "default_branch": "main", "clone_url": "x", "synced_at": "2026-07-21T00:00:00Z"}], "ops": [],
    }), "")


def test_remote_base_advance_blocks_document_proposal_before_pen_execution(tmp_path, monkeypatch):
    document = _collect(BASE, tmp_path)
    changed = plan_sync.ReconciliationPlan({"title": "GitHub title"}, {}, {"title": "GitHub title"}, ())
    proposal = plan_sync.build_apply_plans(changed, document.binding, document, ACTOR).repo_mutation
    registry = mutation_plan.load_registry(Path("templates/transformations.yaml.template"))
    pen_plan = pen_orchestrator.PenPlan(proposal, registry.get(proposal.transformation), "nave/plan-sync", nave_adapter.PenQuery(terms=["repo:acme/docs"]))

    class QueuedRunner:
        def __init__(self):
            self.calls, self.results = [], [nave_adapter.Completed(0, "created\n", ""), _pen_show(), nave_adapter.Completed(0, json.dumps([{"owner": "acme", "repo": "docs", "working_tree": "clean", "freshness": "fresh", "run_state": "not-run", "divergence": "up-to-date", "ahead": 0, "behind": 0}]), "")]
        def run(self, args):
            self.calls.append(args)
            return self.results.pop(0)

    monkeypatch.setattr(pen_orchestrator.nave_adapter, "probe", lambda _runner: {"available": True, "version": "0.0.9", "protocol": 1})
    runner = QueuedRunner()
    result = pen_orchestrator.execute(pen_plan, runner, read_repo_head=lambda _repo: "remote-advanced")

    assert result.state == "blocked"
    assert result.repo_outcomes == {REPO: "blocked"}
    assert not any("exec" in call for call in runner.calls)


def test_repeat_after_full_sync_is_a_noop_with_identical_counts(tmp_path):
    first = _collect(BASE | {"title": "Updated title"}, tmp_path)
    reconciliation = plan_sync.compute(
        first.document, first.github, first.binding["sync"], first.base_body,
        document_blob=first.blob,
    )
    finalized = plan_sync.finalize(reconciliation, doc_applied=True, github_applied=True)
    assert finalized.base_patch == {"title": "Updated title", "blob": CURRENT_BLOB}

    synced_values = BASE | {
        "title": "Updated title",
        "body": "# Updated title\n\nBase body.\n",
    }
    new_blob = "d" * 40
    kwargs = {
        "blob": new_blob,
        "sync_base": synced_values,
        "sync_blob": CURRENT_BLOB,
        "base_document": synced_values["body"],
    }
    document = _snapshot(synced_values, tmp_path, **kwargs)
    repeated = _snapshot(synced_values, tmp_path, **kwargs)

    expected = {"docs_scanned": 1, "in_sync": 1, "doc_patches": 0,
                "github_patches": 0, "conflicts": 0, "excluded": 0}
    assert {key: _result(document)[key] for key in expected} == expected
    assert {key: _result(repeated)[key] for key in expected} == expected


def test_real_result_builder_round_trips_through_plan_sync_validator(tmp_path):
    result = _result(_snapshot(BASE, tmp_path, github_values=BASE | {"state": "closed"}))
    result_path = tmp_path / "plan-sync-result.yaml"
    result_path.write_text(yaml.safe_dump(result, sort_keys=False))

    validated = subprocess.run(
        [sys.executable, str(Path(validate_result.__file__)), str(result_path), "--kind", "plan-sync"],
        capture_output=True,
        text=True,
    )

    assert validated.returncode == 0, validated.stderr
    assert result["proposals"] == [{
        "binding": "release-plan",
        "transformation": "plan-sync-doc-patch",
        "proposal_id": "plan-sync-doc-release-plan",
    }]
    assert result["proposed_actions"]


def test_github_evidence_error_is_counted_as_excluded(tmp_path):
    snapshot = plan_sync_snapshot.collect(
        [_binding()],
        workdir=tmp_path,
        runner=SnapshotRunner(_document(BASE)),
        gh_api=lambda _endpoint: None,
    )

    result = _result(snapshot)

    assert result["docs_scanned"] == 1
    assert result["excluded"] == 1
    assert result["in_sync"] == 0
    assert [finding["kind"] for finding in result["findings"]] == ["snapshot_error"]


def test_headless_skill_is_neutral_and_declares_ordered_propose_only_phases():
    for path in (plan_sync.__file__, plan_sync_snapshot.__file__, validate_result.__file__, SKILL, WORKFLOW):
        content = Path(path).read_text().lower()
        for forbidden in ("claude", "corpus", "plugin manifest", "skill.md"):
            assert forbidden not in content, f"{forbidden!r} found in {path}"

    skill = SKILL.read_text()
    normalized = " ".join(skill.split())
    phases = ("Phase 1: DISCOVER", "Phase 2: SNAPSHOT", "Phase 3: COMPUTE", "Phase 4: APPLY_GITHUB", "Phase 5: APPLY_DOC", "Phase 6: FINALIZE", "Phase 7: RECORD")
    assert [normalized.index(phase) for phase in phases] == sorted(normalized.index(phase) for phase in phases)
    assert "mutation_policy: propose" in skill
    assert "--kind plan-sync" in skill
