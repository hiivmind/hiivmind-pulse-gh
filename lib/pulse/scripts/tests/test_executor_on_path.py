"""Tests for Task 1 (B1): Executor on PATH & command_argv safety checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from lib.pulse.scripts import mutation_plan
from lib.pulse.scripts import executor_probe
from lib.pulse.scripts import apply_doc_patch_entry
from lib.pulse.scripts import apply_marketplace_entry


TEMPLATE_PATH = Path("templates/transformations.yaml.template").resolve()


def _blob(text: str) -> str:
    data = text.encode()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def test_registry_command_argv_has_no_repo_relative_script_paths():
    registry = mutation_plan.load_registry(TEMPLATE_PATH)
    doc_entry = registry.get("plan-sync-doc-patch")
    assert doc_entry.command_argv[0] == "pulse-apply-doc-patch"

    mkt_entry = registry.get("marketplace-entry-update")
    assert mkt_entry.command_argv[0] == "pulse-apply-marketplace-entry"

    for entry_id, entry in registry.transformations.items():
        executor_probe.validate_command_argv(entry.command_argv, entry_id)


def test_argv_linter_rejects_synthetic_repo_relative_script_path():
    synthetic_data = {
        "transformations": {
            "bad-transformation": {
                "id": "bad-transformation",
                "command_argv": ["uv", "run", "foo/bar.py"],
                "applies_to": ["always"],
                "validation": {"kind": "none"},
                "allow_scheduled": False,
            }
        }
    }
    with pytest.raises(mutation_plan.MutationPlanError, match=r"repo-relative script path"):
        mutation_plan.load_registry(synthetic_data)


def test_probe_required_tool_returns_blocked_when_tool_absent(tmp_path):
    # Fake empty PATH
    fake_path = str(tmp_path)
    result = executor_probe.probe_required_tool("npm", ecosystem="nodejs", path_env=fake_path)
    assert result["state"] == "blocked"
    assert "npm" in result["reason"]
    assert "nodejs" in result["reason"]


def test_probe_required_tool_honors_explicit_path_env(tmp_path):
    fake_path = str(tmp_path)
    # Even for a known console script, an explicit path_env must not fall back to sysconfig scripts
    result = executor_probe.probe_required_tool("pulse-apply-doc-patch", path_env=fake_path)
    assert result["state"] == "blocked"


def test_apply_doc_patch_entry_applies_change_and_rejects_path_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    doc_content = "---\nsync:\n  base:\n    blob: old\n---\n# Old title\n"
    target = tmp_path / "plans" / "widget.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc_content)

    patch_path = tmp_path / ".hiivmind" / "plan-sync-patch.yaml"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_content = (
        "path: plans/widget.md\n"
        f"base_blob: {_blob(doc_content)}\n"
        "doc_patch: {title: 'New title'}\n"
        "sync_patch: {blob: 'new'}\n"
        "output_paths: [plans/widget.md]\n"
    )
    patch_path.write_text(patch_content)

    ret = apply_doc_patch_entry.main(["--patch", ".hiivmind/plan-sync-patch.yaml"])
    assert ret == 0
    assert "New title" in target.read_text()

    # Path escape test
    patch_escape = (
        "path: ../escaping.md\n"
        f"base_blob: {_blob(doc_content)}\n"
        "doc_patch: {}\n"
        "sync_patch: {}\n"
        "output_paths: ['plans/widget.md']\n"
    )
    patch_path.write_text(patch_escape)
    ret_escape = apply_doc_patch_entry.main(["--patch", ".hiivmind/plan-sync-patch.yaml"])
    assert ret_escape != 0


def test_apply_marketplace_entry_applies_change_and_rejects_path_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mkt_doc = {
        "plugins": [
            {"name": "hiivmind-pulse-gh", "version": "0.1.0"}
        ]
    }
    target = tmp_path / "marketplace.json"
    doc_text = json.dumps(mkt_doc, indent=2) + "\n"
    target.write_text(doc_text)

    patch_path = tmp_path / ".hiivmind" / "marketplace-entry-patch.yaml"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_content = (
        "path: marketplace.json\n"
        f"base_blob: {_blob(doc_text)}\n"
        "entry_patch: {name: 'hiivmind-pulse-gh', version: '0.2.0'}\n"
        "output_paths: [marketplace.json]\n"
    )
    patch_path.write_text(patch_content)

    ret = apply_marketplace_entry.main(["--patch", ".hiivmind/marketplace-entry-patch.yaml"])
    assert ret == 0
    updated = json.loads(target.read_text())
    assert updated["plugins"][0]["version"] == "0.2.0"

    # Base blob mismatch test
    patch_path.write_text(patch_content)  # target now has 0.2.0 text, so old base_blob will mismatch
    ret_mismatch = apply_marketplace_entry.main(["--patch", ".hiivmind/marketplace-entry-patch.yaml"])
    assert ret_mismatch != 0

    # Path escape test
    patch_escape = (
        "path: ../escaping.json\n"
        "base_blob: deadbeef\n"
        "entry_patch: {name: 'hiivmind-pulse-gh', version: '0.2.0'}\n"
        "output_paths: ['marketplace.json']\n"
    )
    patch_path.write_text(patch_escape)
    ret_escape = apply_marketplace_entry.main(["--patch", ".hiivmind/marketplace-entry-patch.yaml"])
    assert ret_escape != 0


def test_apply_marketplace_entry_with_raw_content_replacement(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "marketplace.json"
    initial = '{"plugins": []}\n'
    target.write_text(initial)

    patch_path = tmp_path / ".hiivmind" / "marketplace-entry-patch.yaml"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    new_text = '{"plugins": [{"name": "new-plugin", "version": "1.0.0"}]}\n'
    patch_content = (
        "path: marketplace.json\n"
        f"base_blob: {_blob(initial)}\n"
        f"content: '{new_text.strip()}'\n"
        "output_paths: [marketplace.json]\n"
    )
    patch_path.write_text(patch_content)

    ret = apply_marketplace_entry.main(["--patch", ".hiivmind/marketplace-entry-patch.yaml"])
    assert ret == 0
    assert target.read_text() == new_text.strip()
