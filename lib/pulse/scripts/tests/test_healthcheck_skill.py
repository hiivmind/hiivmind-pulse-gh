"""Contract checks for the headless healthcheck orchestration skill."""

from pathlib import Path


SKILL = Path("skills/gh-healthcheck-headless/SKILL.md")


def read_skill() -> str:
    return SKILL.read_text()


def test_result_path_has_current_directory_fallback_before_workspace_validation():
    skill = read_skill()
    normalized = " ".join(skill.split())

    fallback = (
        "explicit `result_path`; otherwise the workspace default when "
        "`workspace_path` is non-empty and usable; otherwise "
        "`./healthcheck-result.yaml` in the current directory"
    )
    assert fallback in normalized
    assert normalized.index(fallback) < normalized.index(
        "Missing `workspace_path` → ABORT"
    )


def test_repo_filter_pairs_evidence_and_profile_scope():
    skill = read_skill()
    normalized = " ".join(skill.split())

    assert (
        "`PREPARED_EVIDENCE` must be a temporary copy whose `repos` list contains "
        "exactly the selected authoritative repositories' available F0 entries, in "
        "lexical order"
    ) in normalized
    assert (
        "`PREPARED_PROFILES` must contain exactly the selected "
        "`repository_profiles`"
    ) in normalized
    assert "Enrich only that same selected repository set" in normalized
    assert (
        "A selected authoritative repository with no F0 entry remains absent from "
        "`PREPARED_EVIDENCE`"
    ) in normalized
    assert "evaluates it from its profile as an evidence gap" in normalized
