"""Tests for the pure claim-currency helper in :mod:`lib.pulse.scripts.repo_claims`.

The module is pure: it does not read the filesystem, run subprocesses, or
import :mod:`claude_plugin` (one-way dependency). ``facts`` and
``check_claims`` are deterministic and trust no inferred input. Inference
is the caller's job; ``validate_inferred_findings`` is the schema guard.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from lib.pulse.scripts import repo_claims
from lib.pulse.scripts.repo_claims import (
    CLAIM_KINDS,
    ClaimFinding,
    InferenceValidationError,
    RepoFacts,
    check_claims,
    facts,
    validate_inferred_findings,
)


def _evidence(
    files: list[str] | None = None,
    file_contents: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if files is not None:
        evidence["files"] = files
    if file_contents is not None:
        evidence["file_contents"] = dict(file_contents)
    return evidence


# --- facts() --------------------------------------------------------------


def test_facts_extracts_skill_paths():
    evidence = _evidence(
        files=[
            "skills/example/SKILL.md",
            "skills/audit/SKILL.md",
            "README.md",
            "CLAUDE.md",
        ]
    )

    result = facts(evidence)

    assert result.skill_paths == frozenset(
        {"skills/example/SKILL.md", "skills/audit/SKILL.md"}
    )


def test_facts_skill_paths_ignores_nested_or_non_skill_files():
    evidence = _evidence(
        files=[
            "skills/example/SKILL.md",
            "skills/team/sub/SKILL.md",
            "skills/README.md",
            "skills/SKILL.md",
            "skills",
        ]
    )

    result = facts(evidence)

    assert result.skill_paths == frozenset({"skills/example/SKILL.md"})


def test_facts_command_names_includes_only_md_files():
    evidence = _evidence(
        files=[
            "commands/gh.md",
            "commands/intent-mapping.yaml",
            "commands/pulse.md",
        ]
    )

    result = facts(evidence)

    assert result.command_names == frozenset({"gh", "pulse"})


def test_facts_command_names_ignores_nested_paths():
    evidence = _evidence(
        files=[
            "commands/gh.md",
            "commands/nested/extra.md",
        ]
    )

    result = facts(evidence)

    assert result.command_names == frozenset({"gh"})


def test_facts_parses_plugin_manifest_mapping():
    evidence = _evidence(
        files=[".claude-plugin/plugin.json"],
        file_contents={
            ".claude-plugin/plugin.json": (
                '{"name": "example-plugin", "version": "1.2.3"}'
            )
        },
    )

    result = facts(evidence)

    assert result.manifest == {
        "name": "example-plugin",
        "version": "1.2.3",
    }


def test_facts_manifest_is_empty_mapping_when_absent():
    result = facts(_evidence(files=["CLAUDE.md"]))

    assert result.manifest == {}


def test_facts_manifest_is_empty_mapping_when_invalid_json():
    evidence = _evidence(
        files=[".claude-plugin/plugin.json"],
        file_contents={".claude-plugin/plugin.json": "{not valid json"},
    )

    result = facts(evidence)

    assert result.manifest == {}


def test_facts_manifest_is_empty_mapping_when_root_is_not_mapping():
    evidence = _evidence(
        files=[".claude-plugin/plugin.json"],
        file_contents={".claude-plugin/plugin.json": "[1, 2, 3]"},
    )

    result = facts(evidence)

    assert result.manifest == {}


def test_facts_defensive_on_non_list_files():
    result = facts({"files": "not a list"})

    assert result == RepoFacts(
        skill_paths=frozenset(),
        command_names=frozenset(),
        manifest={},
    )


def test_facts_defensive_on_files_with_non_string_entries():
    result = facts({"files": ["CLAUDE.md", 42]})

    assert result.skill_paths == frozenset()
    assert result.command_names == frozenset()


def test_facts_facts_returns_frozensets_and_immutable_manifest_dict():
    result = facts(_evidence(files=["skills/example/SKILL.md", "commands/gh.md"]))

    assert isinstance(result.skill_paths, frozenset)
    assert isinstance(result.command_names, frozenset)
    assert isinstance(result.manifest, dict)


# --- check_claims() -------------------------------------------------------


def test_check_claims_flags_missing_claimed_skill():
    claude_md = "See skills/ghost/SKILL.md for the audit procedure."
    current = RepoFacts(
        skill_paths=frozenset({"skills/example/SKILL.md"}),
        command_names=frozenset(),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "missing_claimed_skill"
    assert finding.subject == "skills/ghost/SKILL.md"
    assert finding.inferred is False


def test_check_claims_flags_stale_command():
    claude_md = "Run `commands/deprecated.md` to refresh the scorecard."
    current = RepoFacts(
        skill_paths=frozenset(),
        command_names=frozenset({"gh"}),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "stale_command"
    assert finding.subject == "deprecated"
    assert finding.inferred is False


def test_check_claims_always_flags_hooks_reference_as_unsupported_evidence():
    claude_md = "The heartbeat lives at hooks/heartbeat.sh."
    current = RepoFacts(
        skill_paths=frozenset(),
        command_names=frozenset(),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "unsupported_evidence"
    assert finding.subject == "hooks/heartbeat.sh"
    assert finding.inferred is False
    assert "surfaced" in finding.detail


def test_check_claims_surfaces_hooks_even_when_facts_are_full():
    claude_md = "Audit via skills/audit/SKILL.md; heartbeat via hooks/heartbeat.sh."
    current = RepoFacts(
        skill_paths=frozenset({"skills/audit/SKILL.md"}),
        command_names=frozenset({"gh"}),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    assert [f.kind for f in findings] == ["unsupported_evidence"]


def test_check_claims_returns_empty_when_every_reference_resolves():
    claude_md = (
        "Use skills/audit/SKILL.md and run commands/gh.md. "
        "No hooks here."
    )
    current = RepoFacts(
        skill_paths=frozenset({"skills/audit/SKILL.md"}),
        command_names=frozenset({"gh"}),
        manifest={},
    )

    assert check_claims(claude_md, current) == []


def test_check_claims_all_deterministic_findings_carry_inferred_false():
    claude_md = (
        "Use skills/ghost/SKILL.md. "
        "Run commands/deprecated.md. "
        "Heartbeat at hooks/heartbeat.sh."
    )
    current = RepoFacts(
        skill_paths=frozenset(),
        command_names=frozenset(),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    assert findings
    for finding in findings:
        assert finding.inferred is False


def test_check_claims_dedupes_repeated_subjects():
    claude_md = (
        "First see skills/ghost/SKILL.md; later skills/ghost/SKILL.md again."
    )
    current = RepoFacts(
        skill_paths=frozenset(),
        command_names=frozenset(),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    assert len(findings) == 1
    assert findings[0].subject == "skills/ghost/SKILL.md"


def test_check_claims_sort_order_is_deterministic():
    claude_md = (
        "skills/zebra/SKILL.md "
        "commands/zzz.md "
        "skills/alpha/SKILL.md "
        "hooks/zzz.sh "
    )
    current = RepoFacts(
        skill_paths=frozenset(),
        command_names=frozenset(),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    keys = [(f.kind, f.subject) for f in findings]
    assert keys == sorted(keys)
    assert keys == [
        ("missing_claimed_skill", "skills/alpha/SKILL.md"),
        ("missing_claimed_skill", "skills/zebra/SKILL.md"),
        ("stale_command", "zzz"),
        ("unsupported_evidence", "hooks/zzz.sh"),
    ]


def test_check_claims_recognizes_references_inside_backticks_and_links():
    claude_md = (
        "- [audit skill](skills/ghost/SKILL.md)\n"
        "- `commands/legacy.md`\n"
        "- hooks/heartbeat.sh\n"
    )
    current = RepoFacts(
        skill_paths=frozenset(),
        command_names=frozenset(),
        manifest={},
    )

    findings = check_claims(claude_md, current)

    kinds = {f.kind for f in findings}
    subjects = {f.subject for f in findings}
    assert kinds == {"missing_claimed_skill", "stale_command", "unsupported_evidence"}
    assert "skills/ghost/SKILL.md" in subjects
    assert "legacy" in subjects
    assert "hooks/heartbeat.sh" in subjects


# --- validate_inferred_findings() ----------------------------------------


def test_validate_inferred_findings_accepts_well_formed_list():
    raw = [
        {
            "kind": "missing_claimed_skill",
            "subject": "skills/inferred/SKILL.md",
            "detail": "the agent inferred this from prose",
        },
        {
            "kind": "stale_command",
            "subject": "old",
            "detail": "removed last quarter",
            "inferred": True,
        },
    ]

    findings = validate_inferred_findings(raw)

    assert len(findings) == 2
    assert all(isinstance(f, ClaimFinding) for f in findings)
    assert all(f.inferred is True for f in findings)
    assert {f.kind for f in findings} == {"missing_claimed_skill", "stale_command"}


def test_validate_inferred_findings_coerces_absent_inferred_to_true():
    raw = [
        {
            "kind": "missing_claimed_skill",
            "subject": "skills/x/SKILL.md",
            "detail": "d",
        }
    ]

    findings = validate_inferred_findings(raw)

    assert findings[0].inferred is True


def test_validate_inferred_findings_rejects_non_list():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings({"kind": "missing_claimed_skill"})


def test_validate_inferred_findings_rejects_non_mapping_item():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings(
            [
                {
                    "kind": "missing_claimed_skill",
                    "subject": "skills/x/SKILL.md",
                    "detail": "ok",
                },
                "not a mapping",
            ]
        )


def test_validate_inferred_findings_rejects_bad_kind():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings(
            [
                {
                    "kind": "not_a_kind",
                    "subject": "skills/x/SKILL.md",
                    "detail": "d",
                }
            ]
        )


def test_validate_inferred_findings_rejects_missing_kind():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings(
            [
                {
                    "subject": "skills/x/SKILL.md",
                    "detail": "d",
                }
            ]
        )


def test_validate_inferred_findings_rejects_empty_subject():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings(
            [
                {
                    "kind": "missing_claimed_skill",
                    "subject": "",
                    "detail": "d",
                }
            ]
        )


def test_validate_inferred_findings_rejects_non_string_subject():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings(
            [
                {
                    "kind": "missing_claimed_skill",
                    "subject": 42,
                    "detail": "d",
                }
            ]
        )


def test_validate_inferred_findings_rejects_non_string_detail():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings(
            [
                {
                    "kind": "missing_claimed_skill",
                    "subject": "skills/x/SKILL.md",
                    "detail": 42,
                }
            ]
        )


def test_validate_inferred_findings_rejects_inferred_false():
    with pytest.raises(InferenceValidationError):
        validate_inferred_findings(
            [
                {
                    "kind": "missing_claimed_skill",
                    "subject": "skills/x/SKILL.md",
                    "detail": "d",
                    "inferred": False,
                }
            ]
        )


def test_validate_inferred_findings_accepts_empty_list():
    assert validate_inferred_findings([]) == []


def test_validate_inferred_findings_claim_kinds_contains_required_keys():
    assert CLAIM_KINDS == frozenset(
        {"missing_claimed_skill", "stale_command", "unsupported_evidence"}
    )


def test_module_does_not_import_claude_plugin():
    """One-way dependency: repo_claims never imports claude_plugin."""
    import sys

    module = sys.modules[repo_claims.__name__]
    for name in sys.modules:
        if name.endswith("claude_plugin"):
            assert module is not sys.modules[name]
