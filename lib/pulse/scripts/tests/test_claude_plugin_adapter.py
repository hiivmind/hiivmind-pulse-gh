"""Behavioral tests for the Claude Code plugin healthcheck adapters."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts.adapters import register_claude_adapters
from lib.pulse.scripts.check_adapters import AdapterRegistry, CheckContext
from lib.pulse.scripts.profile_dispatch import (
    dispatch,
    load_profiles,
    resolve_scorecard,
)


FIXTURES = Path(__file__).parent / "fixtures" / "overlays" / "claude-plugin"
TEMPLATE = Path("templates/profiles.yaml.template")


def _load_evidence(name: str) -> dict:
    return yaml.safe_load((FIXTURES / f"{name}.yaml").read_text())


def _make_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    register_claude_adapters(registry)
    return registry


def _context(adapter: str, evidence: dict) -> CheckContext:
    return CheckContext(
        repo=evidence.get("repo", "test/plugin"),
        evidence=evidence,
        check={"id": adapter.rsplit(".", 1)[-1], "weight": 1},
        workspace=Path("/workspace/that/must/not/be/read"),
    )


def _evaluate(adapter: str, evidence: dict) -> dict:
    return _make_registry().evaluate(adapter, _context(adapter, evidence))


def test_valid_plugin_manifest_passes_and_cites_manifest_path():
    out = _evaluate("claude.plugin_manifest", _load_evidence("valid-plugin"))

    assert out["status"] == "pass"
    assert out["data"]["evidence"]["paths"] == [".claude-plugin/plugin.json"]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_valid_skills_pass_and_cite_sorted_skill_paths():
    out = _evaluate("claude.skills", _load_evidence("valid-plugin"))

    assert out["status"] == "pass"
    assert out["data"]["evidence"]["paths"] == [
        "skills/audit/SKILL.md",
        "skills/example/SKILL.md",
    ]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_valid_claude_context_passes_and_cites_context_file():
    out = _evaluate("claude.context", _load_evidence("valid-plugin"))

    assert out["status"] == "pass"
    assert out["data"]["evidence"]["paths"] == ["CLAUDE.md"]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_missing_manifest_fails_citing_the_layout_required_path():
    out = _evaluate("claude.plugin_manifest", _load_evidence("missing-manifest"))

    assert out["status"] == "fail"
    assert out["data"]["evidence"]["paths"] == [".claude-plugin/plugin.json"]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_malformed_manifest_fails_citing_the_manifest():
    out = _evaluate("claude.plugin_manifest", _load_evidence("malformed-manifest"))

    assert out["status"] == "fail"
    assert out["data"]["evidence"]["paths"] == [".claude-plugin/plugin.json"]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_content_unavailable_manifest_is_unknown_evidence_gap():
    out = _evaluate(
        "claude.plugin_manifest", _load_evidence("content-unavailable")
    )

    assert out["status"] == "unknown"
    assert "evidence gap" in out["detail"].lower()
    assert out["data"]["evidence"]["paths"] == [".claude-plugin/plugin.json"]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_malformed_skill_frontmatter_fails_citing_the_offending_file():
    out = _evaluate("claude.skills", _load_evidence("malformed-skill-frontmatter"))

    assert out["status"] == "fail"
    assert out["data"]["evidence"]["paths"] == ["skills/broken/SKILL.md"]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_no_skills_fails_with_no_path_to_cite():
    out = _evaluate("claude.skills", _load_evidence("no-skills"))

    assert out["status"] == "fail"
    assert out["data"]["evidence"]["paths"] == []
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_missing_claude_md_fails_citing_the_context_file():
    out = _evaluate("claude.context", _load_evidence("missing-claude-md"))

    assert out["status"] == "fail"
    assert out["data"]["evidence"]["paths"] == ["CLAUDE.md"]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_template_loads_and_claude_plugin_v1_resolves_to_inherited_plus_new_checks():
    config = load_profiles(TEMPLATE)

    resolved = resolve_scorecard(config, "claude-plugin-v1")
    check_ids = [check.id for check in resolved]

    assert check_ids == [
        "documentation",
        "ci",
        "plugin-manifest",
        "plugin-skills",
        "claude-context",
    ]
    for check in resolved:
        assert check.weight == 1
    for check in resolved[-3:]:
        assert check.applicability == "profile:claude-plugin"
    assert config.adapters["claude.plugin_manifest"].state == "available"
    assert config.adapters["claude.skills"].state == "available"
    assert config.adapters["claude.context"].state == "available"


def test_plain_python_repo_dispatch_invokes_no_claude_adapter():
    config = load_profiles(FIXTURES / "plain-python-profiles.yaml")
    evidence = {
        "repos": [
            {
                "repo": "acme/python-lib",
                "files": ["pyproject.toml", "README.md"],
                "capabilities": ["ci", "python"],
                "structural_signals": [],
            }
        ]
    }

    plan = dispatch("acme/python-lib", evidence, config)

    invocable_claude = [
        check
        for check in plan.checks.values()
        if check.state is None and check.adapter.startswith("claude.")
    ]
    assert invocable_claude == []
    assert {check.adapter for check in plan.checks.values() if check.state is None} == {
        "generic.docs",
        "github.actions",
    }


def test_unregistered_claude_adapters_are_unsupported_when_dispatched():
    registry = AdapterRegistry()
    context = CheckContext(
        repo="acme/plugin",
        evidence=_load_evidence("valid-plugin"),
        check={"id": "plugin_manifest", "weight": 1},
        workspace=Path("/workspace/that/must/not/be/read"),
    )

    out = registry.evaluate("claude.plugin_manifest", context)

    assert out["status"] == "unsupported"
    assert "no adapter registered" in out["detail"].lower()


# --- claim-currency audit (Task 3) ---------------------------------------


def test_stale_claim_fails_and_attach_claim_findings():
    out = _evaluate("claude.context", _load_evidence("stale-claim"))

    assert out["status"] == "fail"
    assert "2 stale CLAUDE.md claim(s)" in out["detail"]

    findings = out["data"]["claim_findings"]
    assert {f["kind"] for f in findings} == {
        "missing_claimed_skill",
        "stale_command",
    }
    assert out["data"]["evidence"]["paths"] == [
        "CLAUDE.md",
        "skills/ghost/SKILL.md",
    ]
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_stale_claim_reports_correct_subjects_sorted():
    out = _evaluate("claude.context", _load_evidence("stale-claim"))

    findings = out["data"]["claim_findings"]
    assert findings == sorted(findings, key=lambda f: (f["kind"], f["subject"]))

    by_kind = {f["kind"]: f for f in findings}
    assert by_kind["missing_claimed_skill"]["subject"] == "skills/ghost/SKILL.md"
    assert by_kind["stale_command"]["subject"] == "deprecated"
    assert by_kind["missing_claimed_skill"]["inferred"] is False
    assert by_kind["stale_command"]["inferred"] is False


def test_unsupported_claim_passes_and_surfaces_hooks_finding():
    out = _evaluate("claude.context", _load_evidence("unsupported-claim"))

    assert out["status"] == "pass"
    assert "CLAUDE.md claims current" in out["detail"]
    assert "1 unsupported claim(s) surfaced" in out["detail"]

    findings = out["data"]["claim_findings"]
    assert len(findings) == 1
    assert findings[0]["kind"] == "unsupported_evidence"
    assert findings[0]["subject"] == "hooks/heartbeat.sh"
    assert findings[0]["inferred"] is False
    assert out["data"]["evidence"]["paths"] == ["CLAUDE.md", "hooks/heartbeat.sh"]


def test_inference_invalid_payload_yields_unknown_status():
    out = _evaluate("claude.context", _load_evidence("inference-invalid"))

    assert out["status"] == "unknown"
    assert "inferred claim validation failed" in out["detail"].lower()
    assert out["data"]["evidence"]["paths"] == ["CLAUDE.md"]


def test_inference_valid_payload_folds_into_findings_with_inferred_flag():
    out = _evaluate("claude.context", _load_evidence("inference-valid"))

    assert out["status"] == "fail"
    assert "1 stale CLAUDE.md claim(s)" in out["detail"]

    findings = out["data"]["claim_findings"]
    assert len(findings) == 1
    assert findings[0]["kind"] == "missing_claimed_skill"
    assert findings[0]["subject"] == "skills/inferred-only/SKILL.md"
    assert findings[0]["inferred"] is True
    assert out["data"]["evidence"]["paths"] == [
        "CLAUDE.md",
        "skills/inferred-only/SKILL.md",
    ]


def test_valid_plugin_context_still_passes_with_no_claim_findings():
    out = _evaluate("claude.context", _load_evidence("valid-plugin"))

    assert out["status"] == "pass"
    assert out["data"]["evidence"]["paths"] == ["CLAUDE.md"]
    assert out["data"]["claim_findings"] == []


# --- inference_status gate (F10 Task 4) ------------------------------------


def test_absent_inference_status_grades_context_unknown():
    evidence = _load_evidence("valid-plugin")
    evidence.pop("inference_status", None)

    out = _evaluate("claude.context", evidence)

    assert out["status"] == "unknown"
    assert "inference" in out["detail"].lower() or "skipped" in out["detail"].lower()


@pytest.mark.parametrize("status", ["skipped", "failed"])
def test_non_ran_inference_status_grades_context_unknown(status):
    evidence = _load_evidence("valid-plugin")
    evidence["inference_status"] = status

    out = _evaluate("claude.context", evidence)

    assert out["status"] == "unknown"
    assert status in out["detail"].lower()


def test_inference_status_ran_still_allows_pass():
    evidence = _load_evidence("valid-plugin")
    evidence["inference_status"] = "ran"

    out = _evaluate("claude.context", evidence)

    assert out["status"] == "pass"
