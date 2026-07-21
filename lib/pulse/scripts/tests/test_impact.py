"""Tests for impact.py — pure path-scoped integration-currency audit."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts.impact import audit, apply_proposals, mark, propose_marks


SPLIT_REPO_OVERLAY = Path("templates/relationships/split-repo-tests.yaml")


def relationships(depends_on):
    return {
        "repo_dependencies": {
            "dependent-repo": {
                "depends_on": depends_on,
                "depended_by": [],
                "relationship_type": "test",
            }
        }
    }


def edge(**overrides):
    e = {
        "repo": "upstream-repo",
        "watch_paths": ["lib/foo.py"],
        "watch_branch": "develop",
        "integration_tested_sha": "base111",
        "tested_at": "2026-07-01T10:00:00Z",
    }
    e.update(overrides)
    return e


def snapshot_for(head="head999", changed_files_by_base=None, base_missing=None,
                  repo="upstream-repo", branch="develop"):
    return {
        repo: {
            branch: {
                "head": head,
                "changed_files_by_base": changed_files_by_base or {},
                "base_missing": base_missing or [],
            }
        }
    }


# --- audit(): watched vs unwatched changes ---

def test_watched_path_change_marks_edge_stale():
    rel = relationships([edge(watch_paths=["lib/foo.py"])])
    snap = snapshot_for(changed_files_by_base={"base111": ["lib/foo.py"]})

    report = audit(rel, snap)

    assert len(report.edges) == 1
    result = report.edges[0]
    assert result.dependent == "dependent-repo"
    assert result.upstream == "upstream-repo"
    assert result.state == "stale"
    assert result.changed_paths == ["lib/foo.py"]
    assert result.tested_sha == "base111"
    assert result.remote_head == "head999"


def test_unwatched_path_change_leaves_edge_current():
    rel = relationships([edge(watch_paths=["lib/foo.py"])])
    snap = snapshot_for(changed_files_by_base={"base111": ["docs/readme.md"]})

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "current"
    assert result.changed_paths == []


def test_no_changes_leaves_edge_current():
    rel = relationships([edge(watch_paths=["lib/foo.py"])])
    snap = snapshot_for(changed_files_by_base={"base111": []})

    report = audit(rel, snap)

    assert report.edges[0].state == "current"
    assert report.edges_stale == 0


# --- audit(): ** glob semantics ---

def test_double_star_watches_entire_tree():
    rel = relationships([edge(watch_paths=["**"])])
    snap = snapshot_for(changed_files_by_base={"base111": ["any/deeply/nested/file.txt"]})

    report = audit(rel, snap)

    assert report.edges[0].state == "stale"
    assert report.edges[0].changed_paths == ["any/deeply/nested/file.txt"]


def test_nested_double_star_glob_matches_across_directories():
    rel = relationships([edge(watch_paths=["lib/**/*.py"])])
    snap = snapshot_for(changed_files_by_base={
        "base111": ["lib/a/b/c.py", "lib/top.py", "other/x.py"],
    })

    report = audit(rel, snap)

    assert report.edges[0].state == "stale"
    # lib/top.py: ** matches zero segments too, so it also hits.
    assert report.edges[0].changed_paths == ["lib/a/b/c.py", "lib/top.py"]


def test_single_star_does_not_cross_directory_boundary():
    rel = relationships([edge(watch_paths=["lib/*.py"])])
    snap = snapshot_for(changed_files_by_base={
        "base111": ["lib/a/nested.py", "lib/top.py"],
    })

    report = audit(rel, snap)

    assert report.edges[0].state == "stale"
    assert report.edges[0].changed_paths == ["lib/top.py"]


# --- audit(): missing / unreachable baseline blocks closed ---

def test_missing_integration_tested_sha_is_unknown():
    rel = relationships([edge(integration_tested_sha=None)])
    snap = snapshot_for(changed_files_by_base={})

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "unknown"
    assert result.tested_sha is None
    assert result.changed_paths == []


def test_unreachable_base_sha_is_unknown():
    rel = relationships([edge(integration_tested_sha="gone123")])
    snap = snapshot_for(base_missing=["gone123"])

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "unknown"
    assert result.tested_sha == "gone123"
    assert result.remote_head == "head999"


def test_base_absent_entirely_from_snapshot_is_unknown():
    rel = relationships([edge(integration_tested_sha="untouched999")])
    snap = snapshot_for(changed_files_by_base={"other_base": ["lib/foo.py"]})

    report = audit(rel, snap)

    assert report.edges[0].state == "unknown"


def test_repo_absent_from_snapshot_is_unknown():
    rel = relationships([edge()])
    snap = {}

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "unknown"
    assert result.remote_head is None
    assert result.tested_sha == "base111"


def test_branch_absent_from_snapshot_is_unknown():
    rel = relationships([edge(watch_branch="develop")])
    snap = {"upstream-repo": {"main": {"head": "x", "changed_files_by_base": {}, "base_missing": []}}}

    report = audit(rel, snap)

    assert report.edges[0].state == "unknown"


def test_unknown_never_reported_as_current_even_with_no_watch_hits():
    # Regression guard: missing baseline must not silently pass as current
    # just because there's no path evidence to point to.
    rel = relationships([edge(integration_tested_sha=None, watch_paths=["**"])])
    snap = snapshot_for(changed_files_by_base={})

    report = audit(rel, snap)

    assert report.edges[0].state != "current"
    assert report.edges[0].state == "unknown"


# --- audit(): deterministic file evidence ---

def test_changed_paths_are_sorted_and_deduplicated():
    rel = relationships([edge(watch_paths=["lib/**", "lib/foo.py"])])
    snap = snapshot_for(changed_files_by_base={
        "base111": ["lib/foo.py", "lib/zzz.py", "lib/foo.py", "lib/aaa.py"],
    })

    report = audit(rel, snap)

    assert report.edges[0].changed_paths == ["lib/aaa.py", "lib/foo.py", "lib/zzz.py"]


# --- audit(): empty/missing watch_paths fails closed ---

def test_empty_watch_paths_list_is_unknown_with_finding():
    rel = relationships([edge(watch_paths=[])])
    snap = snapshot_for(changed_files_by_base={"base111": ["lib/foo.py"]})

    report = audit(rel, snap)

    assert len(report.edges) == 1
    result = report.edges[0]
    assert result.state == "unknown"
    assert result.changed_paths == []

    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.kind == "empty_watch_paths"
    assert finding.repo == "dependent-repo"
    assert finding.severity == "low"
    assert finding.inferred is False


def test_missing_watch_paths_key_is_unknown_with_finding():
    edge_config = edge()
    del edge_config["watch_paths"]
    rel = relationships([edge_config])
    snap = snapshot_for(changed_files_by_base={"base111": ["lib/foo.py"]})

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "unknown"
    assert result.changed_paths == []
    assert len(report.findings) == 1
    assert report.findings[0].kind == "empty_watch_paths"


def test_empty_watch_paths_never_reported_as_current_even_with_no_changes():
    # Regression guard mirroring the missing-baseline case: an edge that can
    # never be marked stale (no watch_paths to hit) must not default to
    # current just because there's nothing to point to.
    rel = relationships([edge(watch_paths=[])])
    snap = snapshot_for(changed_files_by_base={})

    report = audit(rel, snap)

    assert report.edges[0].state != "current"
    assert report.edges[0].state == "unknown"


# --- audit(): legacy string edges ---

def test_legacy_string_edge_produces_unconfigured_edge_finding():
    rel = relationships(["upstream-repo"])
    snap = snapshot_for()

    report = audit(rel, snap)

    assert report.edges == []
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.kind == "unconfigured_edge"
    assert finding.repo == "dependent-repo"
    assert finding.severity == "low"
    assert finding.inferred is False


def test_mixed_legacy_and_object_edges():
    rel = relationships(["legacy-upstream", edge()])
    snap = snapshot_for(changed_files_by_base={"base111": ["lib/foo.py"]})

    report = audit(rel, snap)

    assert len(report.edges) == 1
    assert len(report.findings) == 1
    assert report.findings[0].kind == "unconfigured_edge"


# --- ImpactReport aggregate counters ---

def test_report_counts_reconcile_with_edges():
    rel = relationships([
        edge(repo="upstream-a", watch_branch="develop",
             integration_tested_sha="base111"),
    ])
    snap = snapshot_for(repo="upstream-a", changed_files_by_base={"base111": ["lib/foo.py"]})

    report = audit(rel, snap)

    assert report.edges_checked == len(report.edges) == 1
    assert report.edges_stale == 1


def test_empty_relationships_produce_empty_report():
    report = audit({"repo_dependencies": {}}, {})

    assert report.edges == []
    assert report.findings == []
    assert report.edges_checked == 0
    assert report.edges_stale == 0


# --- audit(): contract-version composition ---

def contract(**overrides):
    c = {
        "producer": {
            "path": "producer.txt",
            "parser": {"kind": "regex", "pattern": r"version:\s*(\S+)"},
        },
        "consumer": {
            "path": "consumer.txt",
            "parser": {"kind": "regex", "pattern": r"requires:\s*(\S+)"},
        },
        "version_scheme": "pep440",
    }
    c.update(overrides)
    return c


def fake_contract_reader(files):
    def read(repo, path):
        return files[(repo, path)]
    return read


def test_contract_state_set_when_reader_supplied():
    rel = relationships([edge(contract=contract())])
    snap = snapshot_for(changed_files_by_base={"base111": []})
    files = {
        ("upstream-repo", "producer.txt"): b"version: 1.5.0",
        ("upstream-repo", "consumer.txt"): b"requires: >=1.0,<2.0",
    }
    report = audit(rel, snap, contract_reader=fake_contract_reader(files))

    result = report.edges[0]
    assert result.state == "current"
    assert result.contract_state == "compatible"
    assert report.findings == []


def test_contract_state_set_to_gap_when_versions_diverge():
    rel = relationships([edge(contract=contract())])
    snap = snapshot_for(changed_files_by_base={"base111": []})
    files = {
        ("upstream-repo", "producer.txt"): b"version: 2.5.0",
        ("upstream-repo", "consumer.txt"): b"requires: >=1.0,<2.0",
    }
    report = audit(rel, snap, contract_reader=fake_contract_reader(files))

    assert report.edges[0].contract_state == "gap"


def test_stale_edge_with_contract_gap_emits_one_finding():
    rel = relationships([edge(watch_paths=["lib/foo.py"], contract=contract())])
    snap = snapshot_for(changed_files_by_base={"base111": ["lib/foo.py"]})
    files = {
        ("upstream-repo", "producer.txt"): b"version: 2.5.0",
        ("upstream-repo", "consumer.txt"): b"requires: >=1.0,<2.0",
    }
    report = audit(rel, snap, contract_reader=fake_contract_reader(files))

    result = report.edges[0]
    assert result.state == "stale"
    assert result.contract_state == "gap"
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.kind == "stale_with_contract_gap"
    assert finding.repo == "dependent-repo"
    assert finding.severity == "high"
    assert "path stale" in finding.detail.lower()
    assert "contract gap" in finding.detail.lower()


def test_contract_block_without_reader_is_unknown_and_finding():
    rel = relationships([edge(contract=contract())])
    snap = snapshot_for(changed_files_by_base={"base111": []})

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "current"
    assert result.contract_state == "unknown"
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.kind == "unevaluated_contract"
    assert finding.repo == "dependent-repo"
    assert finding.severity == "low"


def test_empty_watch_paths_and_contract_no_reader_emits_both_findings():
    rel = relationships([edge(watch_paths=[], contract=contract())])
    snap = snapshot_for(changed_files_by_base={"base111": []})

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "unknown"
    assert result.contract_state == "unknown"

    kinds = [f.kind for f in report.findings]
    assert "empty_watch_paths" in kinds
    assert "unevaluated_contract" in kinds
    assert len(report.findings) == 2


def test_non_contract_edges_unchanged():
    rel = relationships([edge()])
    snap = snapshot_for(changed_files_by_base={"base111": []})

    report = audit(rel, snap)

    result = report.edges[0]
    assert result.state == "current"
    assert result.contract_state is None
    assert report.findings == []


# --- mark(): expected-base guarded, idempotent, atomic marker patch ---

def make_relationships_file(tmp_path, depends_on):
    path = tmp_path / "relationships.yaml"
    path.write_text(yaml.safe_dump(relationships(depends_on), sort_keys=False))
    return path


def test_mark_updates_when_current_matches_expected(tmp_path):
    path = make_relationships_file(tmp_path, [edge(integration_tested_sha="base111")])

    result = mark(path, "dependent-repo", "upstream-repo",
                   expected_sha="base111", new_sha="base222",
                   tested_at="2026-07-19T00:00:00Z")

    assert result.status == "updated"
    assert result.previous_sha == "base111"
    assert result.new_sha == "base222"

    on_disk = yaml.safe_load(path.read_text())
    written_edge = on_disk["repo_dependencies"]["dependent-repo"]["depends_on"][0]
    assert written_edge["integration_tested_sha"] == "base222"
    assert written_edge["tested_at"] == "2026-07-19T00:00:00Z"


def test_mark_repeat_call_is_idempotent_after_update(tmp_path):
    path = make_relationships_file(tmp_path, [edge(integration_tested_sha="base111")])
    args = dict(dependent="dependent-repo", upstream="upstream-repo",
                expected_sha="base111", new_sha="base222",
                tested_at="2026-07-19T00:00:00Z")

    first = mark(path, **args)
    second = mark(path, **args)

    assert first.status == "updated"
    assert second.status == "noop"

    on_disk = yaml.safe_load(path.read_text())
    written_edge = on_disk["repo_dependencies"]["dependent-repo"]["depends_on"][0]
    assert written_edge["integration_tested_sha"] == "base222"


def test_mark_conflict_on_mismatched_expected_base_does_not_write(tmp_path):
    path = make_relationships_file(tmp_path, [edge(integration_tested_sha="base111")])
    before = path.read_text()

    result = mark(path, "dependent-repo", "upstream-repo",
                   expected_sha="wrong-base", new_sha="base222",
                   tested_at="2026-07-19T00:00:00Z")

    assert result.status == "conflict"
    assert result.previous_sha == "base111"
    assert path.read_text() == before


def test_mark_not_found_for_unknown_edge(tmp_path):
    path = make_relationships_file(tmp_path, [edge(repo="some-other-upstream")])
    before = path.read_text()

    result = mark(path, "dependent-repo", "upstream-repo",
                   expected_sha="base111", new_sha="base222",
                   tested_at="2026-07-19T00:00:00Z")

    assert result.status == "not_found"
    assert path.read_text() == before


def test_mark_not_found_for_legacy_string_edge(tmp_path):
    path = make_relationships_file(tmp_path, ["upstream-repo"])
    before = path.read_text()

    result = mark(path, "dependent-repo", "upstream-repo",
                   expected_sha="base111", new_sha="base222",
                   tested_at="2026-07-19T00:00:00Z")

    assert result.status == "not_found"
    assert path.read_text() == before


# --- propose_marks(): workflow-run evidence -> exact mark proposal ---

def run_evidence(**overrides):
    e = {
        "workflow": "ci.yml",
        "repo": "upstream-repo",
        "outcome": "success",
        "head_sha": "head999",
        "tested_at": "2026-07-19T00:00:00Z",
    }
    e.update(overrides)
    return e


def test_propose_marks_only_configured_successful_workflow_proposes():
    rel = relationships([edge(integration_workflow="ci.yml",
                               integration_tested_sha="base111")])

    proposals = propose_marks(rel, [run_evidence()])

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.dependent == "dependent-repo"
    assert proposal.upstream == "upstream-repo"
    assert proposal.expected_sha == "base111"
    assert proposal.new_sha == "head999"
    assert proposal.tested_at == "2026-07-19T00:00:00Z"


def test_propose_marks_failed_run_produces_nothing():
    rel = relationships([edge(integration_workflow="ci.yml",
                               integration_tested_sha="base111")])

    proposals = propose_marks(rel, [run_evidence(outcome="failure")])

    assert proposals == []


def test_propose_marks_in_progress_run_produces_nothing():
    rel = relationships([edge(integration_workflow="ci.yml",
                               integration_tested_sha="base111")])

    proposals = propose_marks(rel, [run_evidence(outcome="aborted")])

    assert proposals == []


def test_propose_marks_unrelated_workflow_produces_nothing():
    rel = relationships([edge(integration_workflow="ci.yml",
                               integration_tested_sha="base111")])

    proposals = propose_marks(rel, [run_evidence(workflow="other-workflow.yml")])

    assert proposals == []


def test_propose_marks_unrelated_repo_produces_nothing():
    rel = relationships([edge(integration_workflow="ci.yml",
                               integration_tested_sha="base111")])

    proposals = propose_marks(rel, [run_evidence(repo="some-other-repo")])

    assert proposals == []


def test_propose_marks_edge_without_configured_workflow_produces_nothing():
    rel = relationships([edge(integration_tested_sha="base111")])  # no integration_workflow

    proposals = propose_marks(rel, [run_evidence()])

    assert proposals == []


def test_propose_marks_legacy_string_edge_produces_nothing():
    rel = relationships(["upstream-repo"])

    proposals = propose_marks(rel, [run_evidence()])

    assert proposals == []


def test_propose_marks_dispatch_alone_never_advances_markers():
    # skipped-cooldown means the workflow never actually ran this pass —
    # dispatch/skip is not evidence of validation.
    rel = relationships([edge(integration_workflow="ci.yml",
                               integration_tested_sha="base111")])

    proposals = propose_marks(rel, [run_evidence(outcome="skipped-cooldown")])

    assert proposals == []


def test_apply_proposals_writes_marks(tmp_path):
    path = make_relationships_file(
        tmp_path, [edge(integration_workflow="ci.yml", integration_tested_sha="base111")])
    rel = yaml.safe_load(path.read_text())

    proposals = propose_marks(rel, [run_evidence()])
    results = apply_proposals(path, proposals)

    assert len(results) == 1
    assert results[0].status == "updated"
    assert results[0].new_sha == "head999"

    on_disk = yaml.safe_load(path.read_text())
    written_edge = on_disk["repo_dependencies"]["dependent-repo"]["depends_on"][0]
    assert written_edge["integration_tested_sha"] == "head999"


def test_apply_proposals_idempotent_on_repeat_application(tmp_path):
    path = make_relationships_file(
        tmp_path, [edge(integration_workflow="ci.yml", integration_tested_sha="base111")])
    rel = yaml.safe_load(path.read_text())
    proposals = propose_marks(rel, [run_evidence()])

    first = apply_proposals(path, proposals)
    second = apply_proposals(path, proposals)

    assert first[0].status == "updated"
    assert second[0].status == "noop"

    on_disk = yaml.safe_load(path.read_text())
    written_edge = on_disk["repo_dependencies"]["dependent-repo"]["depends_on"][0]
    assert written_edge["integration_tested_sha"] == "head999"


def test_apply_proposals_expected_base_conflict_passes_through(tmp_path):
    path = make_relationships_file(
        tmp_path, [edge(integration_workflow="ci.yml", integration_tested_sha="base111")])
    rel = yaml.safe_load(path.read_text())
    # Build the proposal from a stale in-memory view (expected_sha base111),
    # then have the on-disk marker move to something else before applying —
    # the expected-base guard must surface a conflict, not silently overwrite.
    proposals = propose_marks(rel, [run_evidence()])

    mark(path, "dependent-repo", "upstream-repo",
         expected_sha="base111", new_sha="unexpected-sha",
         tested_at="2026-07-18T00:00:00Z")

    results = apply_proposals(path, proposals)

    assert results[0].status == "conflict"
    assert results[0].previous_sha == "unexpected-sha"

    on_disk = yaml.safe_load(path.read_text())
    written_edge = on_disk["repo_dependencies"]["dependent-repo"]["depends_on"][0]
    assert written_edge["integration_tested_sha"] == "unexpected-sha"


def test_mark_preserves_other_edges_and_sections(tmp_path):
    other_edge = edge(repo="other-upstream", integration_tested_sha="untouched")
    path = make_relationships_file(
        tmp_path, [edge(integration_tested_sha="base111"), other_edge])

    mark(path, "dependent-repo", "upstream-repo",
         expected_sha="base111", new_sha="base222",
         tested_at="2026-07-19T00:00:00Z")

    on_disk = yaml.safe_load(path.read_text())
    edges = on_disk["repo_dependencies"]["dependent-repo"]["depends_on"]
    other = next(e for e in edges if e["repo"] == "other-upstream")
    assert other["integration_tested_sha"] == "untouched"


# --- Split-repo binding (configuration over existing F5 machinery) ---

@pytest.fixture
def split_repo_overlay():
    return yaml.safe_load(SPLIT_REPO_OVERLAY.read_text())


def test_split_repo_full_tree_edge_goes_stale_on_any_change(split_repo_overlay):
    base_sha = "0000000000000000000000000000000000000000"
    snap = {
        "hiivmind-pulse-gh": {
            "develop": {
                "head": "head999",
                "changed_files_by_base": {
                    base_sha: [
                        "lib/pulse/scripts/impact.py",
                        "docs/readme.md",
                    ],
                },
                "base_missing": [],
            }
        }
    }

    report = audit(split_repo_overlay, snap)

    assert len(report.edges) == 1
    result = report.edges[0]
    assert result.dependent == "hiivmind-pulse-gh-tests"
    assert result.upstream == "hiivmind-pulse-gh"
    assert result.watch_branch == "develop"
    assert result.state == "stale"
    assert result.tested_sha == base_sha
    assert result.remote_head == "head999"
    # Full-tree "**" watch matches arbitrary paths in any part of the tree.
    assert "lib/pulse/scripts/impact.py" in result.changed_paths
    assert "docs/readme.md" in result.changed_paths


def test_split_repo_successful_workflow_advances_marker(split_repo_overlay, tmp_path):
    base_sha = "0000000000000000000000000000000000000000"
    new_sha = "abc1234def5678abc1234def5678abc1234def56"
    tested_at = "2026-07-20T12:00:00Z"

    proposals = propose_marks(split_repo_overlay, [
        run_evidence(
            workflow="ci.yml",
            repo="hiivmind-pulse-gh",
            outcome="success",
            head_sha=new_sha,
            tested_at=tested_at,
        )
    ])

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.dependent == "hiivmind-pulse-gh-tests"
    assert proposal.upstream == "hiivmind-pulse-gh"
    assert proposal.expected_sha == base_sha
    assert proposal.new_sha == new_sha
    assert proposal.tested_at == tested_at

    path = tmp_path / "relationships.yaml"
    path.write_text(yaml.safe_dump(split_repo_overlay, sort_keys=False))
    results = apply_proposals(path, proposals)

    assert len(results) == 1
    assert results[0].status == "updated"
    assert results[0].new_sha == new_sha

    on_disk = yaml.safe_load(path.read_text())
    written_edge = on_disk["repo_dependencies"]["hiivmind-pulse-gh-tests"]["depends_on"][0]
    assert written_edge["integration_tested_sha"] == new_sha
    assert written_edge["tested_at"] == tested_at
