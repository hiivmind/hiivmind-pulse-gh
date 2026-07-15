"""Contract checks for the headless fleet membership skill and workflow."""

from pathlib import Path

import yaml


SKILL = Path("skills/gh-fleet-membership-headless/SKILL.md")
WORKFLOW = Path("templates/workflows/fleet-watch.yaml")


def read_skill():
    text = SKILL.read_text()
    _, frontmatter, body = text.split("---", 2)
    return yaml.safe_load(frontmatter), body


def test_skill_declares_explicit_headless_interface_and_phases():
    frontmatter, body = read_skill()

    assert frontmatter["name"] == "gh-fleet-membership-headless"
    for input_name in ("workspace_path", "apply_catalog", "mode"):
        assert input_name in frontmatter["inputs"]
    for phase in ("FETCH", "DIFF", "LOAD F0 EVIDENCE", "PROPOSE PROFILES", "APPLY CATALOG", "WRITE + VALIDATE"):
        assert phase in body
    for script in ("fleet_membership.py", "profile_proposals.py", "validate_result.py"):
        assert script in body


def test_skill_separates_registration_from_profile_onboarding():
    _, body = read_skill()
    normalized = " ".join(body.lower().split())

    assert "stable repository facts only" in normalized
    assert "never seeds labels, milestones, scheduler" in normalized
    assert "asks_recorded" in body
    assert "apply_catalog" in body


def test_fleet_watch_is_an_org_signature_trigger():
    workflow = yaml.safe_load(WORKFLOW.read_text())

    assert workflow["trigger"] == {
        "type": "session_poll",
        "source": "org_repos",
        "condition": "state_changed",
    }
    assert workflow["headless"]["enabled"] is True
    assert workflow["headless"]["on_mutation"] == "propose"
