"""Tests for generated_artifacts.py — generated-artifact binding audit engine."""
from __future__ import annotations

from dataclasses import dataclass

import yaml

from lib.pulse.scripts import generated_artifacts as ga
from lib.pulse.scripts.impact import Finding


@dataclass
class Completed:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Fake `runner(argv, cwd) -> Completed` seam."""

    def __init__(self, responses: dict[tuple, Completed] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[tuple, str | None]] = []

    def __call__(self, argv, cwd=None):
        key = tuple(argv)
        self.calls.append((key, str(cwd) if cwd is not None else None))
        return self.responses.get(key, Completed(1, "", f"no fixture for {argv}"))


def binding(**overrides):
    b = {
        "id": "widget-readme",
        "source": "hiivmind/template-repo",
        "branch": "main",
        "template_path": "templates/repo-readme.md",
        "template_tree": "tree1111",
        "generator": "readme-from-template",
        "files": [{"path": "README.md", "blob": "blob1111"}],
        "generated_at": "2026-07-10T09:15:00Z",
    }
    b.update(overrides)
    return b


def manifest(bindings_list):
    return {"bindings": bindings_list}


def snapshot_for(source="hiivmind/template-repo", branch="main", head="head999",
                 trees=None, blobs=None):
    return {
        source: {
            branch: {
                "head": head,
                "trees": trees or {"templates/repo-readme.md": "tree1111"},
                "blobs": blobs or {"README.md": "blob1111"},
            }
        }
    }


# --- backfill() ---

def test_backfill_resolves_tree_and_blobs_from_snapshot():
    snap = snapshot_for(
        trees={"templates/repo-readme.md": "tree2222"},
        blobs={"README.md": "blob2222"},
    )
    inp = binding()
    del inp["template_tree"]
    inp["files"] = [{"path": "README.md"}]

    entry = ga.backfill(inp, snap)

    assert entry.id == "widget-readme"
    assert entry.source == "hiivmind/template-repo"
    assert entry.branch == "main"
    assert entry.template_path == "templates/repo-readme.md"
    assert entry.template_tree == "tree2222"
    assert entry.files == [ga.GeneratedFile("README.md", "blob2222")]


def test_backfill_missing_repo_in_snapshot_fails_closed():
    inp = binding()
    del inp["template_tree"]
    inp["files"] = [{"path": "README.md"}]

    try:
        ga.backfill(inp, {})
    except ValueError as exc:
        assert "hiivmind/template-repo" in str(exc)
        assert "main" in str(exc)
    else:
        raise AssertionError("backfill must raise when repo/branch is missing")


def test_backfill_missing_branch_in_snapshot_fails_closed():
    inp = binding()
    del inp["template_tree"]
    inp["files"] = [{"path": "README.md"}]
    snap = {"hiivmind/template-repo": {"develop": {}}}

    try:
        ga.backfill(inp, snap)
    except ValueError as exc:
        assert "hiivmind/template-repo" in str(exc)
        assert "main" in str(exc)
    else:
        raise AssertionError("backfill must raise when repo/branch is missing")


# --- audit(): classification ---

def test_audit_current_tree_same_blobs_same():
    report = ga.audit(manifest([binding()]), snapshot_for())

    assert len(report.bindings) == 1
    result = report.bindings[0]
    assert result.id == "widget-readme"
    assert result.state == "current"
    assert result.stored_tree == "tree1111"
    assert result.snapshot_tree == "tree1111"
    assert result.files[0].state == "current"
    assert result.files[0].stored_blob == "blob1111"
    assert result.files[0].snapshot_blob == "blob1111"
    assert result.proposal is None


def test_audit_current_produces_zero_findings():
    report = ga.audit(manifest([binding()]), snapshot_for())

    assert report.findings == []
    assert report.bindings_checked == 1
    assert report.bindings_drift == 0


def test_audit_template_drift_tree_changed_blobs_same():
    snap = snapshot_for(trees={"templates/repo-readme.md": "tree2222"})
    report = ga.audit(manifest([binding()]), snap)

    result = report.bindings[0]
    assert result.state == "template-drift"
    assert result.snapshot_tree == "tree2222"
    assert result.files[0].state == "current"
    assert report.findings == []
    assert result.proposal is not None
    assert result.proposal.binding_id == "widget-readme"
    assert result.proposal.expected_tree == "tree1111"
    assert result.proposal.new_tree == "tree2222"
    assert result.proposal.files == [ga.GeneratedFile("README.md", "blob1111")]


def test_audit_local_customization_tree_same_blob_changed():
    snap = snapshot_for(blobs={"README.md": "blob2222"})
    report = ga.audit(manifest([binding()]), snap)

    result = report.bindings[0]
    assert result.state == "local-customization"
    assert result.files[0].state == "changed"
    assert result.files[0].snapshot_blob == "blob2222"
    assert result.proposal is None
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.kind == "local_customization"
    assert finding.repo == "hiivmind/template-repo"
    assert finding.severity == "medium"


def test_audit_conflict_tree_changed_blob_changed():
    snap = snapshot_for(
        trees={"templates/repo-readme.md": "tree2222"},
        blobs={"README.md": "blob2222"},
    )
    report = ga.audit(manifest([binding()]), snap)

    result = report.bindings[0]
    assert result.state == "conflict"
    assert result.files[0].state == "changed"
    assert result.proposal is None
    assert len(report.findings) == 1
    assert report.findings[0].kind == "conflict"
    assert report.findings[0].severity == "high"


def test_audit_missing_output_error():
    snap = snapshot_for(blobs={"README.md": ga.ABSENT})
    report = ga.audit(manifest([binding()]), snap)

    result = report.bindings[0]
    assert result.state == "error"
    assert result.files[0].state == "missing"
    assert result.files[0].snapshot_blob == ga.ABSENT
    assert result.proposal is None
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.kind == "missing_output"
    assert finding.severity == "high"
    assert "README.md" in (finding.detail or "")


def test_audit_snapshot_gap_error():
    report = ga.audit(manifest([binding()]), {})

    result = report.bindings[0]
    assert result.state == "error"
    assert result.snapshot_tree is None
    assert result.proposal is None
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.kind == "snapshot_gap"
    assert finding.severity == "high"
    assert "hiivmind/template-repo" in (finding.detail or "")
    assert "main" in (finding.detail or "")


def test_audit_multiple_files_one_missing_one_changed():
    b = binding(files=[
        {"path": "README.md", "blob": "blob1111"},
        {"path": "LICENSE", "blob": "blob2222"},
    ])
    snap = snapshot_for(blobs={
        "README.md": "blob1111",
        "LICENSE": "blob3333",
    })
    report = ga.audit(manifest([b]), snap)

    result = report.bindings[0]
    assert result.state == "local-customization"
    assert len(result.files) == 2
    assert result.files[0].state == "current"
    assert result.files[1].state == "changed"


def test_audit_empty_manifest():
    report = ga.audit(manifest([]), {})

    assert report.bindings == []
    assert report.findings == []
    assert report.bindings_checked == 0


# --- advance() ---

def make_manifest_file(tmp_path, bindings_list):
    path = tmp_path / "generated.yaml"
    path.write_text(yaml.safe_dump(manifest(bindings_list), sort_keys=False))
    return path


def test_advance_updates_when_expected_matches(tmp_path):
    path = make_manifest_file(tmp_path, [binding()])
    new_files = [{"path": "README.md", "blob": "blob2222"}]

    result = ga.advance(
        path,
        binding_id="widget-readme",
        expected_tree="tree1111",
        new_tree="tree2222",
        files=new_files,
        generated_at="2026-07-19T00:00:00Z",
    )

    assert result.status == "updated"
    assert result.previous_tree == "tree1111"
    assert result.new_tree == "tree2222"

    on_disk = yaml.safe_load(path.read_text())
    b = on_disk["bindings"][0]
    assert b["template_tree"] == "tree2222"
    assert b["files"] == new_files
    assert b["generated_at"] == "2026-07-19T00:00:00Z"


def test_advance_conflict_when_expected_mismatches(tmp_path):
    path = make_manifest_file(tmp_path, [binding()])
    before = path.read_text()

    result = ga.advance(
        path,
        binding_id="widget-readme",
        expected_tree="wrong-tree",
        new_tree="tree2222",
        files=[{"path": "README.md", "blob": "blob2222"}],
        generated_at="2026-07-19T00:00:00Z",
    )

    assert result.status == "conflict"
    assert result.previous_tree == "tree1111"
    assert path.read_text() == before


def test_advance_idempotent_repeat_is_noop(tmp_path):
    path = make_manifest_file(tmp_path, [binding()])
    args = dict(
        binding_id="widget-readme",
        expected_tree="tree1111",
        new_tree="tree2222",
        files=[{"path": "README.md", "blob": "blob2222"}],
        generated_at="2026-07-19T00:00:00Z",
    )

    first = ga.advance(path, **args)
    second = ga.advance(path, **args)

    assert first.status == "updated"
    assert second.status == "noop"
    assert second.previous_tree == "tree2222"

    on_disk = yaml.safe_load(path.read_text())
    assert on_disk["bindings"][0]["template_tree"] == "tree2222"


def test_advance_not_found_for_unknown_binding(tmp_path):
    path = make_manifest_file(tmp_path, [binding()])
    before = path.read_text()

    result = ga.advance(
        path,
        binding_id="unknown-binding",
        expected_tree="tree1111",
        new_tree="tree2222",
        files=[{"path": "README.md", "blob": "blob2222"}],
        generated_at="2026-07-19T00:00:00Z",
    )

    assert result.status == "not_found"
    assert path.read_text() == before


def test_advance_preserves_other_bindings(tmp_path):
    other = binding(id="other-binding", template_tree="tree9999")
    path = make_manifest_file(tmp_path, [binding(), other])

    ga.advance(
        path,
        binding_id="widget-readme",
        expected_tree="tree1111",
        new_tree="tree2222",
        files=[{"path": "README.md", "blob": "blob2222"}],
        generated_at="2026-07-19T00:00:00Z",
    )

    on_disk = yaml.safe_load(path.read_text())
    bindings = on_disk["bindings"]
    assert bindings[0]["template_tree"] == "tree2222"
    assert bindings[1]["template_tree"] == "tree9999"


# --- collect() ---

def test_collect_happy_path(tmp_path):
    b = binding()
    repo_dir = tmp_path / "work" / "hiivmind_template-repo_main"
    url = "https://github.com/hiivmind/template-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): Completed(0, "", ""),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "main"): Completed(0, "", ""),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(0, "head999\n", ""),
        ("git", "rev-parse", "FETCH_HEAD:templates/repo-readme.md"): Completed(0, "tree1111\n", ""),
        ("git", "rev-parse", "FETCH_HEAD:README.md"): Completed(0, "blob1111\n", ""),
    })

    result = ga.collect(manifest([b]), workdir=tmp_path / "work", runner=runner)

    assert result == {
        "hiivmind/template-repo": {
            "main": {
                "head": "head999",
                "trees": {"templates/repo-readme.md": "tree1111"},
                "blobs": {"README.md": "blob1111"},
            }
        }
    }


def test_collect_missing_path_records_absent(tmp_path):
    b = binding()
    repo_dir = tmp_path / "work" / "hiivmind_template-repo_main"
    url = "https://github.com/hiivmind/template-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): Completed(0, "", ""),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "main"): Completed(0, "", ""),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(0, "head999\n", ""),
        ("git", "rev-parse", "FETCH_HEAD:templates/repo-readme.md"): Completed(0, "tree1111\n", ""),
        ("git", "rev-parse", "FETCH_HEAD:README.md"): Completed(128, "", "fatal: Not a valid object name"),
    })

    result = ga.collect(manifest([b]), workdir=tmp_path / "work", runner=runner)

    assert result["hiivmind/template-repo"]["main"]["blobs"]["README.md"] == ga.ABSENT


def test_collect_fetch_failure_records_head_none(tmp_path):
    b = binding()
    repo_dir = tmp_path / "work" / "hiivmind_template-repo_main"
    url = "https://github.com/hiivmind/template-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): Completed(0, "", ""),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "main"): Completed(128, "", "fatal"),
    })

    result = ga.collect(manifest([b]), workdir=tmp_path / "work", runner=runner)

    branch_snap = result["hiivmind/template-repo"]["main"]
    assert branch_snap["head"] is None
    assert branch_snap["trees"] == {}
    assert branch_snap["blobs"] == {}


def test_collect_groups_bindings_by_repo_branch_single_fetch(tmp_path):
    b1 = binding(id="widget-readme")
    b2 = binding(id="widget-ci", files=[{"path": ".github/workflows/ci.yml", "blob": "blob2222"}])
    repo_dir = tmp_path / "work" / "hiivmind_template-repo_main"
    url = "https://github.com/hiivmind/template-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): Completed(0, "", ""),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "main"): Completed(0, "", ""),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(0, "head999\n", ""),
        ("git", "rev-parse", "FETCH_HEAD:templates/repo-readme.md"): Completed(0, "tree1111\n", ""),
        ("git", "rev-parse", "FETCH_HEAD:README.md"): Completed(0, "blob1111\n", ""),
        ("git", "rev-parse", "FETCH_HEAD:.github/workflows/ci.yml"): Completed(0, "blob2222\n", ""),
    })

    ga.collect(manifest([b1, b2]), workdir=tmp_path / "work", runner=runner)

    fetch_calls = [c for c in runner.calls if c[0][1] == "fetch"]
    assert len(fetch_calls) == 1


def test_collect_invalid_branch_never_invokes_fetch():
    b = binding(branch="-evil")
    runner = RecordingRunner()

    result = ga.collect(manifest([b]), runner=runner)

    branch_snap = result["hiivmind/template-repo"]["-evil"]
    assert branch_snap["head"] is None
    assert branch_snap["trees"] == {}
    assert branch_snap["blobs"] == {}
    fetch_calls = [c for c in runner.calls if c[0][1] == "fetch"]
    assert fetch_calls == []


def test_collect_empty_manifest():
    runner = RecordingRunner()
    result = ga.collect(manifest([]), runner=runner)

    assert result == {}
    assert runner.calls == []
