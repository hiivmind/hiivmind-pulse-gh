"""Contract checks for the headless impact-audit orchestration skill."""

from pathlib import Path


SKILL = Path("skills/gh-impact-audit-headless/SKILL.md")


def read_skill() -> str:
    return SKILL.read_text()


def test_phases_are_present_in_order():
    skill = read_skill()
    for phase in ("Phase 1: VALIDATE", "Phase 2: SNAPSHOT", "Phase 3: AUDIT",
                  "Phase 4: PROPOSE ISSUE/DISPATCH", "Phase 5: RECORD"):
        assert phase in skill
    normalized = " ".join(skill.split())
    order = [
        normalized.index("Phase 1: VALIDATE"),
        normalized.index("Phase 2: SNAPSHOT"),
        normalized.index("Phase 3: AUDIT"),
        normalized.index("Phase 4: PROPOSE ISSUE/DISPATCH"),
        normalized.index("Phase 5: RECORD"),
    ]
    assert order == sorted(order)


def test_dispatch_never_advances_markers():
    skill = read_skill()
    normalized = " ".join(skill.split())

    assert "markers_updated: 0" in normalized
    assert (
        "successful integration-workflow dispatch proposal, even if a human or "
        "automation later runs it, does not by itself advance any marker"
    ) in normalized
    assert (
        "this skill never writes `integration_tested_sha` markers "
        "(`impact.py::mark`) and never opens issues or dispatches workflows"
    ) in normalized
    assert "never calls `gh` and never invokes `impact.py mark`" in normalized


def test_result_kind_is_impact_and_validated():
    skill = read_skill()
    assert "kind: impact" in skill
    assert "validate_result.py" in skill
    assert '--kind impact' in skill


def test_missing_baseline_blocks_closed_language():
    skill = read_skill()
    normalized = " ".join(skill.split())
    assert (
        "an edge whose `integration_tested_sha` cannot be resolved on the remote "
        "is `state: unknown`, never `current`"
    ) in normalized
