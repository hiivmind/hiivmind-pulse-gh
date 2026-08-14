"""Tests for the durable write-ahead apply phase journal."""

import importlib

import pytest


MODULE = "lib.pulse.scripts.apply_journal"


def _module():
    return importlib.import_module(MODULE)


apply_journal_module = _module()


def test_begin_persists_intent_token_and_evidence_across_reload(tmp_path):
    apply_journal = _module()
    path = tmp_path / "apply-journal.yaml"

    apply_journal.Journal(path).begin(
        "octo/widgets",
        "leased",
        "fence-17",
        apply_id="apply-42",
        audit_id="audit-99",
    )

    assert apply_journal.Journal(path).state("octo/widgets") == {
        "phase": None,
        "in_progress": "leased",
        "evidence": {"apply_id": "apply-42", "audit_id": "audit-99"},
        "token": "fence-17",
    }


def test_complete_advances_phase_clears_intent_and_accumulates_evidence(tmp_path):
    apply_journal = _module()
    path = tmp_path / "apply-journal.yaml"
    journal = apply_journal.Journal(path)
    journal.begin("octo/widgets", "committed", "fence-18", branch="pulse/apply/42")

    journal.complete("octo/widgets", "committed", commit_sha="a" * 40)

    assert apply_journal.Journal(path).state("octo/widgets") == {
        "phase": "committed",
        "in_progress": None,
        "evidence": {
            "branch": "pulse/apply/42",
            "commit_sha": "a" * 40,
        },
        "token": "fence-18",
    }


@pytest.mark.parametrize("phase", ["pen_ready", "pr_opened"])
def test_boundary_intents_are_recorded_for_pen_ready_and_pr_opened(tmp_path, phase):
    apply_journal = _module()
    path = tmp_path / "apply-journal.yaml"

    apply_journal.Journal(path).begin("octo/widgets", phase, "fence-19")

    assert apply_journal.Journal(path).state("octo/widgets")["in_progress"] == phase


def test_resume_action_resets_and_reruns_only_an_interrupted_transform(tmp_path):
    apply_journal = _module()
    path = tmp_path / "apply-journal.yaml"
    journal = apply_journal.Journal(path)
    journal.begin("octo/widgets", "transformed", "fence-20")

    assert journal.resume_action("octo/widgets") == apply_journal.RESET_AND_REEXEC_TRANSFORM


@pytest.mark.parametrize(
    "phase",
    [None] + [p for p in apply_journal_module.PHASES if p != "transformed"],
)
def test_resume_action_verifies_remote_evidence_for_all_other_states(tmp_path, phase):
    apply_journal = _module()
    path = tmp_path / "apply-journal.yaml"
    journal = apply_journal.Journal(path)
    if phase is not None:
        journal.begin("octo/widgets", phase, "fence-21")

    assert journal.resume_action("octo/widgets") == apply_journal.VERIFY_REMOTE_EVIDENCE


def test_corrupt_journal_fails_closed(tmp_path):
    apply_journal = _module()
    path = tmp_path / "apply-journal.yaml"
    path.write_text("repos: [not a mapping")

    with pytest.raises(apply_journal.JournalError, match="could not load journal"):
        apply_journal.Journal(path)


@pytest.mark.parametrize(
    "contents",
    [
        "repos: [a, b]",
        (
            "repos:\n"
            "  octo/widgets:\n"
            "    phase: null\n"
            "    in_progress: null\n"
            "    evidence: {}\n"
        ),
        (
            "repos:\n"
            "  octo/widgets:\n"
            "    phase: not-a-real-phase\n"
            "    in_progress: null\n"
            "    evidence: {}\n"
            "    token: null\n"
        ),
    ],
    ids=["repos-is-a-list", "record-missing-token-key", "record-invalid-phase-enum"],
)
def test_schema_invalid_journal_fails_closed(tmp_path, contents):
    apply_journal = _module()
    path = tmp_path / "apply-journal.yaml"
    path.write_text(contents)

    with pytest.raises(apply_journal.JournalError, match="could not load journal"):
        apply_journal.Journal(path)
