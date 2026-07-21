"""Black-box tests for the guarded plan-document patch script."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys

import yaml


SCRIPT = Path("lib/pulse/scripts/apply_doc_patch.py").resolve()


def _blob(text: str) -> str:
    data = text.encode()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _write_patch(repo: Path, patch: dict) -> None:
    patch_path = repo / ".hiivmind" / "plan-sync-patch.yaml"
    patch_path.parent.mkdir()
    patch_path.write_text(yaml.safe_dump(patch, sort_keys=False))


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--patch", ".hiivmind/plan-sync-patch.yaml"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def test_apply_doc_patch_exits_zero_and_updates_the_bound_document(tmp_path):
    document = "---\nsync:\n  base:\n    blob: old\n---\n# Old title\n"
    target = tmp_path / "plans" / "widget.md"
    target.parent.mkdir()
    target.write_text(document)
    _write_patch(
        tmp_path,
        {
            "path": "plans/widget.md",
            "base_blob": _blob(document),
            "doc_patch": {"title": "New title"},
            "sync_patch": {"blob": "new"},
            "output_paths": ["plans/widget.md"],
        },
    )

    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert target.read_text() == document.replace("blob: old", "blob: new").replace(
        "# Old title", "# New title"
    )


def test_apply_doc_patch_exits_nonzero_when_the_bound_document_is_missing(tmp_path):
    _write_patch(
        tmp_path,
        {
            "path": "plans/missing.md",
            "base_blob": "deadbeef",
            "doc_patch": {},
            "sync_patch": {},
            "output_paths": ["plans/missing.md"],
        },
    )

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "not found" in result.stderr


def test_apply_doc_patch_exits_nonzero_when_the_document_blob_no_longer_matches(tmp_path):
    target = tmp_path / "plans" / "widget.md"
    target.parent.mkdir()
    target.write_text("# Current title\n")
    _write_patch(
        tmp_path,
        {
            "path": "plans/widget.md",
            "base_blob": _blob("# Previous title\n"),
            "doc_patch": {"title": "New title"},
            "sync_patch": {},
            "output_paths": ["plans/widget.md"],
        },
    )

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "base blob mismatch" in result.stderr


def test_apply_doc_patch_rejects_a_document_outside_its_bound_output_allowlist(tmp_path):
    document = "# Old title\n"
    target = tmp_path / "plans" / "widget.md"
    target.parent.mkdir()
    target.write_text(document)
    _write_patch(
        tmp_path,
        {
            "path": "plans/widget.md",
            "base_blob": _blob(document),
            "doc_patch": {"title": "New title"},
            "sync_patch": {},
            "output_paths": ["plans/other.md"],
        },
    )

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "outside the output allowlist" in result.stderr
    assert target.read_text() == document
