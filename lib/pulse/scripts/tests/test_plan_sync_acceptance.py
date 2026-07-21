"""Offline acceptance coverage for the F8 plan synchronization contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

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

    def __init__(self, document: str, *, blob: str = CURRENT_BLOB, rename: str | None = None):
        self.document = document
        self.blob = blob
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
            return Completed(0, self.document if argv[-1] == CURRENT_BLOB else BASE["body"])
        if tuple(argv[:3]) == ("git", "log", "--follow") and self.rename:
            return Completed(0, f"{HEAD}\n{self.rename}\n{BASE_BLOB}\n{PATH}\n")
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


def _document(values: dict) -> str:
    return (
        "---\n"
        f"state: {values['state']}\n"
        f"assignees: [{', '.join(values['assignees'])}]\n"
        f"milestone: {values['milestone'] if values['milestone'] is not None else ''}\n"
        "sync:\n"
        "  issue: {repo: acme/widgets, number: 42}\n"
        f"  base: {{blob: {BASE_BLOB}, title: Release plan, state: open, assignees: [ada], milestone: null}}\n"
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


def _collect(values: dict, tmp_path, *, blob: str = CURRENT_BLOB, github_values: dict | None = None):
    snapshot = plan_sync_snapshot.collect(
        [_binding()], workdir=tmp_path, runner=SnapshotRunner(_document(values), blob=blob),
        gh_api=_github(github_values or values),
    )
    return snapshot.documents[0]


def _counts(document, reconciliation):
    """The result buckets used by the headless orchestration document."""
    result = {"docs_scanned": 1, "in_sync": 0, "doc_patches": 0,
              "github_patches": 0, "conflicts": 0, "excluded": 0}
    if document.state == "in_sync":
        result["in_sync"] = 1
    elif document.state == "excluded":
        result["excluded"] = 1
    elif reconciliation.conflicted:
        result["conflicts"] = 1
    elif reconciliation.doc_patch or reconciliation.github_patch:
        result["doc_patches"] = int(bool(reconciliation.doc_patch))
        result["github_patches"] = int(bool(reconciliation.github_patch))
    else:
        result["in_sync"] = 1
    return result


@pytest.mark.parametrize(
    ("doc_values", "github_values", "expected"),
    [
        (BASE, BASE, {"in_sync": 1}),
        (BASE | {"state": "closed"}, BASE, {"github_patches": 1}),
        (BASE, BASE | {"state": "closed"}, {"doc_patches": 1}),
        (BASE | {"state": "closed"}, BASE | {"state": "in progress"}, {"conflicts": 1}),
        (BASE | {"state": "closed"}, BASE | {"state": "closed"}, {"in_sync": 1}),
    ],
    ids=("noop", "document-to-github", "github-to-document", "conflict", "agree"),
)
def test_merge_outcomes_land_in_their_result_buckets(tmp_path, doc_values, github_values, expected):
    document = _collect(doc_values, tmp_path, github_values=github_values)
    reconciliation = plan_sync.compute(document.document, document.github, document.binding["sync"], document.base_body)
    plans = plan_sync.build_apply_plans(reconciliation, document.binding, document, ACTOR)
    plan_sync.finalize(reconciliation, doc_applied=False, github_applied=False)

    counts = _counts(document, reconciliation)

    assert {key: counts[key] for key in expected} == expected
    assert (plans.doc_patch is not None) == bool(reconciliation.doc_patch)
    assert (plans.github_mutation is not None) == bool(reconciliation.github_patch)


def test_rename_and_local_ahead_are_excluded_from_reconciliation(tmp_path):
    renamed = plan_sync_snapshot.collect(
        [_binding()], workdir=tmp_path,
        runner=SnapshotRunner(_document(BASE), rename="plans/renamed-release.md"), gh_api=_github(BASE),
    ).documents[0]
    assert renamed.state == "excluded"
    assert _counts(renamed, plan_sync.ReconciliationPlan({}, {}, {}, ()))["excluded"] == 1

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
    ).documents[0]
    assert ahead.state == "excluded"
    assert _counts(ahead, plan_sync.ReconciliationPlan({}, {}, {}, ()))["excluded"] == 1


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
    first = _collect(BASE | {"state": "closed"}, tmp_path)
    reconciliation = plan_sync.compute(first.document, first.github, first.binding["sync"], first.base_body)
    finalized = plan_sync.finalize(reconciliation, doc_applied=True, github_applied=True)
    assert finalized.base_patch == {"state": "closed"}

    synced_base = BASE | finalized.base_patch
    document = _collect(synced_base, tmp_path, blob=BASE_BLOB)
    repeated = _collect(synced_base, tmp_path, blob=BASE_BLOB)
    noop = plan_sync.ReconciliationPlan({}, {}, {}, ())

    assert _counts(document, noop) == _counts(repeated, noop) == {
        "docs_scanned": 1, "in_sync": 1, "doc_patches": 0, "github_patches": 0, "conflicts": 0, "excluded": 0,
    }


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
