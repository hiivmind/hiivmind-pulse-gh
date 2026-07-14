"""Contract checks for the headless fleet evidence orchestration skill."""

from pathlib import Path

import yaml


SKILL = Path("skills/gh-fleet-evidence-headless/SKILL.md")


def read_skill():
    text = SKILL.read_text()
    _, frontmatter, body = text.split("---", 2)
    return yaml.safe_load(frontmatter), body


def test_skill_declares_headless_inputs_and_output_contract():
    frontmatter, body = read_skill()

    assert frontmatter["name"] == "gh-fleet-evidence-headless"
    assert set(frontmatter) == {"name", "description"}
    for input_name in ("workspace_path", "nave_binary", "mode"):
        assert f"`{input_name}`" in body
    assert ".hiivmind/github/fleet-evidence.yaml" in body
    assert "Zero prompts" in body


def test_skill_runs_all_evidence_phases_through_adapter_and_validator():
    _, body = read_skill()

    for phase in ("PROBE", "SCAN", "PULL", "ANALYZE", "NORMALIZE", "VALIDATE"):
        assert f"Phase" in body and phase in body
    assert "nave_adapter.py" in body
    assert "evidence_snapshot.py" in body
    assert "validate_evidence.py" in body
    assert "PULSE_NAVE_FIXTURES" in body


def test_missing_nave_is_valid_evidence_not_repo_failure():
    _, body = read_skill()

    assert "capability_status" in body
    assert "state: unavailable" in body
    assert "return success" in body.lower()
    assert "repos: []" in body


def test_skill_preserves_projection_and_mutation_boundaries():
    _, body = read_skill()
    prose = " ".join(body.lower().split())

    assert "not authoritative fleet membership" in prose
    assert "not observed" in prose
    assert "Do not mutate repositories" in body
    assert "Do not mutate GitHub" in body
