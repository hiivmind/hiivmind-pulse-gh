"""Round-trip and reconciliation tests for plan-document synchronization."""

import json
from pathlib import Path

import pytest

from lib.pulse.scripts import mutation_plan, nave_adapter, pen_orchestrator, plan_sync
from lib.pulse.scripts.plan_sync import parse_document, patch_document


DOCUMENT = """---\n# Keep this frontmatter comment.\nowner: docs-team\ncustom: # Unknown keys must survive sync patches.\n  review: required\nsync:\n  issue: {repo: acme/widgets, number: 42}\n  base:\n    blob: deadbeef\n    title: Original title\n---\n# Original title\n\nThis body must remain exactly as written.  \n"""


def test_parse_document_preserves_frontmatter_comments_unknown_keys_and_body_bytes():
    document = parse_document(DOCUMENT)

    assert document.frontmatter["owner"] == "docs-team"
    assert document.frontmatter["custom"]["review"] == "required"
    assert document.binding is document.frontmatter["sync"]
    assert document.title == "Original title"
    assert document.body == "# Original title\n\nThis body must remain exactly as written.  \n"


def test_parse_document_allows_unbound_documents():
    source = "---\nowner: docs-team\n---\n# Standalone plan\n\nNo sync block.\n"

    document = parse_document(source)

    assert document.frontmatter["owner"] == "docs-team"
    assert document.binding is None
    assert document.title == "Standalone plan"
    assert document.body == "# Standalone plan\n\nNo sync block.\n"


def test_noop_patch_returns_byte_identical_document():
    assert patch_document(DOCUMENT, {}, {}) == DOCUMENT


def test_sync_base_patch_preserves_frontmatter_comments_unknown_keys_and_body_bytes():
    patched = patch_document(DOCUMENT, {}, {"blob": "cafebabe"})

    assert patched == DOCUMENT.replace("blob: deadbeef", "blob: cafebabe")


def test_patch_preserves_crlf_line_endings_and_untouched_body_bytes():
    document = DOCUMENT.replace("\n", "\r\n")

    patched = patch_document(document, {}, {"blob": "cafebabe"})

    assert patched == document.replace("blob: deadbeef", "blob: cafebabe")
    assert "\n" not in patched.replace("\r\n", "")


def test_retitle_changes_only_the_first_h1_line():
    document = "# Old title\n\n# Later H1 stays\n"

    patched = patch_document(document, {"title": "New title"}, {})

    assert patched == "# New title\n\n# Later H1 stays\n"


def test_body_patch_uses_the_replacement_verbatim():
    replacement = "# Replacement\r\n\r\nBody with CRLF.\r\n"

    patched = patch_document(DOCUMENT, {"body": replacement}, {})

    assert patched == DOCUMENT[:DOCUMENT.index("# Original title")] + replacement


FIELD_VALUES = {
    "title": ("Base title", "Document title", "GitHub title"),
    "state": ("open", "closed", "in progress"),
    "assignees": (["ada"], ["zoe", "ada", "zoe"], ["bea"]),
    "milestone": ("M1", "M2", "M3"),
    "body": ("Base body\n", "Document body\n", "GitHub body\n"),
}


@pytest.mark.parametrize("field", FIELD_VALUES)
@pytest.mark.parametrize(
    ("scenario", "doc_source", "github_source", "policy", "expected"),
    [
        ("neither", "base", "base", None, ("noop", None)),
        (
            "document only",
            "doc",
            "base",
            None,
            ("apply_to_github", "doc"),
        ),
        (
            "github only",
            "base",
            "github",
            None,
            ("apply_to_doc", "github"),
        ),
        ("both agree", "doc", "doc", None, ("agree", "doc")),
        ("conflict", "doc", "github", None, ("conflict", None)),
        (
            "prefer document",
            "doc",
            "github",
            "prefer-doc",
            ("apply_to_github", "doc"),
        ),
        (
            "prefer github",
            "doc",
            "github",
            "prefer-github",
            ("apply_to_doc", "github"),
        ),
    ],
)
def test_merge_field_full_three_way_matrix(
    field, scenario, doc_source, github_source, policy, expected
):
    base, document_change, github_change = FIELD_VALUES[field]
    values = {"base": base, "doc": document_change, "github": github_change}
    expected_decision, expected_value_source = expected
    expected_value = values[expected_value_source] if expected_value_source else None
    if field == "assignees" and expected_value is not None:
        expected_value = sorted(set(expected_value))

    assert callable(getattr(plan_sync, "merge_field", None))

    decision = plan_sync.merge_field(
        field, base, values[doc_source], values[github_source], policy=policy
    )

    assert decision == plan_sync.FieldDecision(expected_decision, expected_value)


def test_merge_field_normalizes_assignee_order_and_duplicates_before_comparison():
    assert callable(getattr(plan_sync, "merge_field", None))

    decision = plan_sync.merge_field(
        "assignees",
        ["ada"],
        ["zoe", "ada", "zoe"],
        ["ada"],
    )

    assert decision == plan_sync.FieldDecision("apply_to_github", ["ada", "zoe"])


def test_compute_treats_missing_and_null_milestones_as_the_same_value():
    assert callable(getattr(plan_sync, "compute", None))

    plan = plan_sync.compute(
        {field: base for field, (base, _, _) in FIELD_VALUES.items() if field != "milestone"},
        {
            field: base
            for field, (base, _, _) in FIELD_VALUES.items()
            if field != "milestone"
        }
        | {"milestone": None},
        {"base": {field: base for field, (base, _, _) in FIELD_VALUES.items()}},
        FIELD_VALUES["body"][0],
    )

    assert plan == plan_sync.ReconciliationPlan({}, {}, {"milestone": None}, ())
    assert plan.conflicted is False


def test_compute_keeps_non_conflicting_field_applies_when_another_field_conflicts():
    base = {field: values[0] for field, values in FIELD_VALUES.items()}
    assert callable(getattr(plan_sync, "compute", None))

    plan = plan_sync.compute(
        base | {"title": "Document title", "assignees": ["zoe", "ada", "zoe"]},
        base | {"title": "GitHub title"},
        {"base": base},
        base["body"],
    )

    assert plan.doc_patch == {}
    assert plan.github_patch == {"assignees": ["ada", "zoe"]}
    assert plan.base_patch == {"assignees": ["ada", "zoe"]}
    assert plan.conflicts == ("title",)
    assert plan.conflicted is True


def _pen_show(repo):
    owner, name = repo.split("/", 1)
    return nave_adapter.Completed(
        0,
        json.dumps(
            {
                "name": "nave/plan-sync",
                "created_at": "2026-07-21T00:00:00Z",
                "branch": "nave/plan-sync",
                "filter": {"terms": []},
                "repos": [
                    {
                        "owner": owner,
                        "name": name,
                        "default_branch": "main",
                        "clone_url": "x",
                        "synced_at": "2026-07-21T00:00:00Z",
                    }
                ],
                "ops": [],
            }
        ),
        "",
    )


def _clean_pen_status(repo):
    owner, name = repo.split("/", 1)
    return nave_adapter.Completed(
        0,
        json.dumps(
            [
                {
                    "owner": owner,
                    "repo": name,
                    "working_tree": "clean",
                    "freshness": "fresh",
                    "run_state": "not-run",
                    "divergence": "up-to-date",
                    "ahead": 0,
                    "behind": 0,
                }
            ]
        ),
        "",
    )


class _QueuedRunner:
    def __init__(self, results):
        self.calls = []
        self.results = list(results)

    def run(self, args):
        self.calls.append(args)
        return self.results.pop(0)


def _binding():
    return {
        "id": "widget-plan",
        "repo": "acme/docs",
        "branch": "main",
        "path": "plans/widget.md",
        "sync": {"issue": {"repo": "acme/widgets", "number": 42}},
    }


def _snapshot():
    return {"repo": "acme/docs", "head": "head-at-snapshot", "blob": "blob-at-snapshot"}


def _actor():
    return {"gh_login": "octocat", "machine": "test-mac", "mode": "interactive"}


def test_build_apply_plans_keeps_document_and_github_proposals_separate_and_propose_only():
    reconciliation = plan_sync.ReconciliationPlan(
        {"state": "closed"},
        {"title": "Document title"},
        {"state": "closed", "title": "Document title"},
        (),
    )

    plans = plan_sync.build_apply_plans(reconciliation, _binding(), _snapshot(), _actor())

    assert isinstance(plans.repo_mutation, mutation_plan.Proposal)
    assert plans.repo_mutation.selection == ("acme/docs",)
    assert plans.repo_mutation.expected_shas == {"acme/docs": "head-at-snapshot"}
    assert plans.repo_mutation.transformation == "plan-sync-doc-patch"
    assert plans.repo_mutation.mutation_policy == "propose"
    assert plans.doc_patch == {
        "path": "plans/widget.md",
        "base_blob": "blob-at-snapshot",
        "doc_patch": {"state": "closed"},
        "sync_patch": {},
        "output_paths": ["plans/widget.md"],
    }
    assert plans.github_mutation == {
        "repo": "acme/widgets",
        "number": 42,
        "patch": {"title": "Document title"},
        "mutation_policy": "propose",
        "proposed_actions": [
            "propose GitHub issue patch for acme/widgets#42: {\"title\": \"Document title\"}"
        ],
    }


def test_expected_blob_mismatch_blocks_the_separate_document_proposal_before_exec(monkeypatch):
    reconciliation = plan_sync.ReconciliationPlan(
        {"title": "Current GitHub title"}, {}, {"title": "Current GitHub title"}, ()
    )
    plans = plan_sync.build_apply_plans(reconciliation, _binding(), _snapshot(), _actor())
    registry = mutation_plan.load_registry(Path("templates/transformations.yaml.template"))
    entry = registry.get(plans.repo_mutation.transformation)
    pen_plan = pen_orchestrator.PenPlan(
        proposal=plans.repo_mutation,
        entry=entry,
        pen_name="nave/plan-sync",
        query=nave_adapter.PenQuery(terms=["repo:acme/docs"]),
    )
    runner = _QueuedRunner(
        [
            nave_adapter.Completed(0, "created\n", ""),
            _pen_show("acme/docs"),
            _clean_pen_status("acme/docs"),
        ]
    )
    monkeypatch.setattr(
        pen_orchestrator.nave_adapter,
        "probe",
        lambda _runner: {"available": True, "version": "0.0.9", "protocol": 1},
    )

    result = pen_orchestrator.execute(
        pen_plan, runner, read_repo_head=lambda _repo: "different-current-blob"
    )

    assert result.state == "blocked"
    assert result.repo_outcomes == {"acme/docs": "blocked"}
    assert result.reason is not None
    assert "acme/docs" in result.reason
    assert not any("exec" in call for call in runner.calls)


@pytest.mark.parametrize(
    ("doc_applied", "github_applied", "expected_base"),
    [
        (True, False, {"state": "closed"}),
        (False, True, {"title": "Document title"}),
    ],
)
def test_finalize_advances_only_the_confirmed_side_and_reports_partial_application(
    doc_applied, github_applied, expected_base
):
    reconciliation = plan_sync.ReconciliationPlan(
        {"state": "closed"},
        {"title": "Document title"},
        {"state": "closed", "title": "Document title"},
        (),
    )

    decision = plan_sync.finalize(reconciliation, doc_applied, github_applied)

    assert decision.base_patch == expected_base
    assert [finding.kind for finding in decision.findings] == ["partial_application"]


def test_finalize_one_sided_reconciliation_is_not_a_partial_application():
    # Only the document changed; there is no GitHub patch. Applying the single
    # side is a COMPLETE reconciliation, not a partial one — no finding.
    reconciliation = plan_sync.ReconciliationPlan(
        {"state": "closed"},
        {},
        {"state": "closed"},
        (),
    )

    decision = plan_sync.finalize(reconciliation, doc_applied=True, github_applied=False)

    assert decision.base_patch == {"state": "closed"}
    assert decision.findings == ()
