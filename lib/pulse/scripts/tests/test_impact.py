"""Tests for impact.py — pure path-scoped integration-currency audit."""
from __future__ import annotations

import yaml

from lib.pulse.scripts.impact import audit, mark


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
