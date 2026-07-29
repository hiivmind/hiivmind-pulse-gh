"""Fold of an inner headless-sibling result into workflow-run accumulators.

Guards the F10 layer-4 defect: a scheduled `INVOKE skill X-headless` workflow
must surface the sibling's proposals in its `workflow-run-result.yaml`, or the
maintenance PR body shows nothing. Covers the pure fold, the anti-duplication
contract (proposals[] is NOT re-rendered), the CLI, and a round-trip proving the
folded surface satisfies the workflow-run schema.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts import subresult_fold, validate_result
from lib.pulse.scripts.subresult_fold import SubresultFoldError, fold_subresult

SCRIPT = Path(subresult_fold.__file__)


def _marketplace_result():
    """A realistic marketplace-sync envelope: one proposal + one gated action."""
    return {
        "contract_version": 1,
        "kind": "marketplace-sync",
        "workspace": "hiivmind",
        "run_at": "2026-07-30T12:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "host", "mode": "scheduled"},
        "bindings_scanned": 2,
        "in_sync": 0,
        "drift": 2,
        "missing_entry": 0,
        "unknown": 0,
        "not_applicable": 0,
        "findings": [
            {"kind": "gated_transformation", "repo": "hiivmind/mp", "severity": "medium",
             "detail": "allow_scheduled: false"},
        ],
        "proposals": [
            {"binding": "plug-a", "transformation": "marketplace-entry-update",
             "proposal_id": "mp-1"},
        ],
        "proposed_actions": [
            "propose marketplace entry update for plug-a to 2.0.0",
            "propose marketplace entry update for plug-b to 3.0.0",
        ],
        "errors": [],
    }


# --------------------------------------------------------------------------- #
# Pure fold
# --------------------------------------------------------------------------- #

def test_fold_passes_findings_and_actions_and_asks_through():
    inner = _marketplace_result()
    inner["asks_recorded"] = ["Q1: which release channel?"]
    folded = fold_subresult(inner)
    assert folded["findings"] == inner["findings"]
    assert folded["proposed_actions"] == inner["proposed_actions"]
    assert folded["asks_recorded"] == ["Q1: which release channel?"]


def test_fold_does_not_re_render_proposals_no_duplication():
    """The load-bearing design assertion: proposals[] is the F11 re-derivation
    channel and is NOT projected — proposed_actions keeps the driver's own lines
    verbatim, so a proposal never appears twice."""
    inner = _marketplace_result()
    folded = fold_subresult(inner)
    # Two driver-authored action lines in, exactly two out — proposals[] (len 1)
    # contributed nothing extra.
    assert folded["proposed_actions"] == inner["proposed_actions"]
    assert len(folded["proposed_actions"]) == 2


def test_fold_missing_fields_default_to_empty_lists():
    folded = fold_subresult({"kind": "plan-sync"})
    assert folded == {"findings": [], "proposed_actions": [], "asks_recorded": []}


def test_fold_null_field_treated_as_empty():
    folded = fold_subresult({"kind": "plan-sync", "proposed_actions": None})
    assert folded["proposed_actions"] == []


def test_fold_findings_are_copied_not_aliased():
    inner = _marketplace_result()
    folded = fold_subresult(inner)
    folded["findings"][0]["severity"] = "high"
    assert inner["findings"][0]["severity"] == "medium"


def test_fold_rejects_non_mapping():
    with pytest.raises(SubresultFoldError):
        fold_subresult(["not", "a", "mapping"])


def test_fold_rejects_non_list_field():
    with pytest.raises(SubresultFoldError):
        fold_subresult({"kind": "plan-sync", "findings": "oops"})


def test_fold_rejects_malformed_finding_element():
    # A non-mapping in findings must raise here (recorded as a fold error), not
    # pass through and fail the outer workflow-run schema validation later.
    with pytest.raises(SubresultFoldError):
        fold_subresult({"kind": "plan-sync", "findings": ["oops"]})


def test_fold_rejects_non_string_action_element():
    with pytest.raises(SubresultFoldError):
        fold_subresult({"kind": "plan-sync", "proposed_actions": [{"not": "a string"}]})


def test_fold_rejects_non_string_ask_element():
    with pytest.raises(SubresultFoldError):
        fold_subresult({"kind": "plan-sync", "asks_recorded": [123]})


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _run_cli(path: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True, text=True,
    )


def test_cli_prints_folded_json(tmp_path):
    inner = tmp_path / "marketplace-sync-result.yaml"
    inner.write_text(yaml.safe_dump(_marketplace_result()), encoding="utf-8")
    proc = _run_cli(inner)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["proposed_actions"] == _marketplace_result()["proposed_actions"]
    assert out["findings"][0]["kind"] == "gated_transformation"
    assert out["asks_recorded"] == []


def test_cli_missing_file_exit_2(tmp_path):
    proc = _run_cli(tmp_path / "nope.yaml")
    assert proc.returncode == 2


def test_cli_non_foldable_exit_3(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    proc = _run_cli(bad)
    assert proc.returncode == 3


def test_cli_invalid_utf8_exit_2(tmp_path):
    # Invalid UTF-8 bytes must map to the documented "unparseable" exit 2, not an
    # uncaught UnicodeDecodeError traceback (exit 1).
    bad = tmp_path / "bad-bytes.yaml"
    bad.write_bytes(b"\xff\xfe not utf-8")
    proc = _run_cli(bad)
    assert proc.returncode == 2


def test_cli_malformed_finding_exit_3(tmp_path):
    inner = tmp_path / "marketplace-sync-result.yaml"
    payload = _marketplace_result()
    payload["findings"] = ["not-a-mapping"]
    inner.write_text(yaml.safe_dump(payload), encoding="utf-8")
    proc = _run_cli(inner)
    assert proc.returncode == 3


# --------------------------------------------------------------------------- #
# Round-trip: folded surface satisfies the workflow-run schema
# --------------------------------------------------------------------------- #

def _workflow_run_envelope(folded, *, workflow):
    return {
        "contract_version": 1,
        "kind": "workflow-run",
        "workspace": "hiivmind",
        "run_at": "2026-07-30T12:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "host", "mode": "scheduled"},
        "workflow": workflow,
        "repos": [],
        "run_id": "2026-07-30-octocat-120000",
        "outcome": "success",
        "findings": list(folded["findings"]),
        "proposed_actions": list(folded["proposed_actions"]),
        "asks_recorded": list(folded["asks_recorded"]),
        "errors": [],
    }


@pytest.mark.parametrize("kind", ["marketplace-sync", "plan-sync", "generated-artifact"])
def test_folded_surface_builds_a_valid_workflow_run(kind):
    inner = _marketplace_result()
    inner["kind"] = kind  # fold is generic over kind; the surface fields are identical
    folded = fold_subresult(inner)
    envelope = _workflow_run_envelope(folded, workflow=kind)
    assert validate_result.validate(envelope, "workflow-run") == []
    # The sibling's proposals reach the PR-body projection surface.
    assert envelope["proposed_actions"], "folded workflow-run must carry sibling actions"
    assert any(f["kind"] == "gated_transformation" for f in envelope["findings"])
