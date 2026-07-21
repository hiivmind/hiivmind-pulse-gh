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
