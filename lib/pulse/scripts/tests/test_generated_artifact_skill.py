"""Contract checks for the headless generated-artifact orchestration skill."""

from pathlib import Path


SKILL = Path("skills/gh-generated-artifact-headless/SKILL.md")
WORKFLOW = Path("templates/workflows/generated-artifact-audit.yaml")
GENERATED_ARTIFACTS = Path("lib/pulse/scripts/generated_artifacts.py")
GENERATOR_DISPATCH = Path("lib/pulse/scripts/generator_dispatch.py")


def read_skill() -> str:
    return SKILL.read_text()


def read_workflow() -> str:
    return WORKFLOW.read_text()


def test_neutrality_forbidden_strings_absent():
    for path in (GENERATED_ARTIFACTS, GENERATOR_DISPATCH, SKILL, WORKFLOW):
        content = path.read_text().lower()
        for forbidden in ("claude", "corpus", "plugin manifest", "skill.md"):
            assert forbidden not in content, f"{forbidden!r} found in {path}"


def test_phases_are_present_in_order():
    skill = read_skill()
    for phase in ("Phase 1: VALIDATE", "Phase 2: SNAPSHOT", "Phase 3: AUDIT",
                  "Phase 4: CONFLICT/PROPOSE", "Phase 5: RECORD"):
        assert phase in skill
    normalized = " ".join(skill.split())
    order = [
        normalized.index("Phase 1: VALIDATE"),
        normalized.index("Phase 2: SNAPSHOT"),
        normalized.index("Phase 3: AUDIT"),
        normalized.index("Phase 4: CONFLICT/PROPOSE"),
        normalized.index("Phase 5: RECORD"),
    ]
    assert order == sorted(order)


def test_result_kind_is_generated_artifact_and_validated():
    skill = read_skill()
    assert "kind: generated-artifact" in skill
    assert "validate_result.py" in skill
    assert '--kind generated-artifact' in skill


def test_scheduled_gating_blocks_non_scheduled_transformations():
    skill = read_skill()
    normalized = " ".join(skill.split())
    assert (
        "Under mode: scheduled, a generator whose transformation has "
        "allow_scheduled: false MUST NOT be dispatched"
    ) in normalized
    assert (
        "Only allow_scheduled: true transformations may be dispatched unattended"
    ) in normalized
