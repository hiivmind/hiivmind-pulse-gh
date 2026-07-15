"""Tests for the healthcheck adapter registry boundary."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from lib.pulse.scripts.check_adapters import AdapterRegistry, CheckContext


def context() -> CheckContext:
    return CheckContext(
        repo="testorg/widget",
        evidence={"paths": ["README.md"]},
        check={"id": "docs", "weight": 1},
        workspace=Path("/workspace"),
    )


def test_missing_adapter_is_unsupported():
    out = AdapterRegistry().evaluate("rust.lockfiles", context())
    assert out == {
        "check_id": "docs",
        "adapter": "rust.lockfiles",
        "weight": 1.0,
        "status": "unsupported",
        "detail": "No adapter registered: rust.lockfiles",
        "data": {"evidence": {"paths": [], "refs": []}},
    }


def test_adapter_exception_is_error():
    registry = AdapterRegistry()
    registry.register("broken", lambda _: 1 / 0)
    out = registry.evaluate("broken", context())
    assert out["check_id"] == "docs"
    assert out["weight"] == 1.0
    assert out["status"] == "error"
    assert out["data"] == {"evidence": {"paths": [], "refs": []}}


def test_context_is_immutable():
    ctx = context()

    with pytest.raises(FrozenInstanceError):
        ctx.repo = "testorg/other"  # type: ignore[misc]


def test_context_defensively_freezes_nested_mutable_values():
    evidence = {
        "nested": [{"paths": ["README.md"]}],
        "labels": {"docs", "public"},
    }
    check = {"id": "docs", "weight": 1, "options": {"strict": [True]}}

    ctx = CheckContext("testorg/widget", evidence, check, Path("/workspace"))
    evidence["nested"][0]["paths"].append("CHANGED.md")
    evidence["labels"].add("changed")
    check["options"]["strict"].append(False)

    assert ctx.evidence["nested"][0]["paths"] == ("README.md",)
    assert ctx.evidence["labels"] == frozenset({"docs", "public"})
    assert ctx.check["options"]["strict"] == (True,)
    with pytest.raises(TypeError):
        ctx.evidence["new"] = "value"


def test_valid_adapter_output_is_normalized():
    registry = AdapterRegistry()
    registry.register(
        "generic.docs",
        lambda ctx: {
            "status": "pass",
            "detail": f"Documentation found in {ctx.repo}",
            "data": {
                "path": "README.md",
                "evidence": {
                    "paths": ("README.md",),
                    "refs": ("github:README.md",),
                },
            },
        },
    )

    assert registry.evaluate("generic.docs", context()) == {
        "check_id": "docs",
        "adapter": "generic.docs",
        "weight": 1.0,
        "status": "pass",
        "detail": "Documentation found in testorg/widget",
        "data": {
            "path": "README.md",
            "evidence": {
                "paths": ["README.md"],
                "refs": ["github:README.md"],
            },
        },
    }


def test_accepts_mapping_output_and_normalizes_it_to_dict():
    registry = AdapterRegistry()
    registry.register(
        "generic.docs",
        lambda _: MappingProxyType(
            {
                "status": "pass",
                "detail": "Documentation found",
                "data": MappingProxyType(
                    {
                        "evidence": MappingProxyType(
                            {"paths": ("README.md",), "refs": ()}
                        )
                    }
                ),
            }
        ),
    )

    out = registry.evaluate("generic.docs", context())

    assert type(out) is dict
    assert type(out["data"]) is dict
    assert type(out["data"]["evidence"]) is dict
    assert out["data"]["evidence"] == {"paths": ["README.md"], "refs": []}


def test_uses_planned_check_metadata():
    from lib.pulse.scripts.profile_dispatch import CheckDefinition, PlannedCheck

    planned = PlannedCheck(CheckDefinition("ci", "github.actions", 2.5), None)
    ctx = CheckContext("testorg/widget", {}, planned, Path("/workspace"))
    registry = AdapterRegistry()
    registry.register(
        "github.actions",
        lambda _: {
            "status": "pass",
            "detail": "Actions configured",
            "data": {"evidence": {"paths": [".github/workflows/ci.yml"], "refs": []}},
        },
    )

    out = registry.evaluate("github.actions", ctx)

    assert out["check_id"] == "ci"
    assert out["weight"] == 2.5


@pytest.mark.parametrize(
    "check",
    [
        {"id": "", "weight": 1},
        {"id": "docs", "weight": -1},
        {"id": "docs", "weight": True},
        {"id": "docs", "weight": "1"},
    ],
)
def test_rejects_invalid_check_metadata(check):
    with pytest.raises((TypeError, ValueError)):
        CheckContext("testorg/widget", {}, check, Path("/workspace"))


@pytest.mark.parametrize(
    "evidence",
    [
        None,
        {},
        {"paths": [], "refs": [], "extra": []},
        {"paths": "README.md", "refs": []},
        {"paths": [], "refs": [42]},
    ],
)
def test_invalid_evidence_citation_output_is_error(evidence):
    registry = AdapterRegistry()
    registry.register(
        "invalid",
        lambda _: {
            "status": "pass",
            "detail": "invalid citations",
            "data": {"evidence": evidence} if evidence is not None else {},
        },
    )

    out = registry.evaluate("invalid", context())

    assert out["status"] == "error"
    assert "invalid output" in out["detail"]
    assert out["data"] == {"evidence": {"paths": [], "refs": []}}


@pytest.mark.parametrize(
    "output",
    [
        None,
        {"status": "passing", "detail": "bad state", "data": {}},
        {"status": "pass", "detail": 42, "data": {}},
        {"status": "pass", "detail": "bad data", "data": []},
    ],
)
def test_invalid_adapter_output_is_error(output):
    registry = AdapterRegistry()
    registry.register("invalid", lambda _: output)

    out = registry.evaluate("invalid", context())

    assert out["adapter"] == "invalid"
    assert out["check_id"] == "docs"
    assert out["weight"] == 1.0
    assert out["status"] == "error"
    assert "invalid output" in out["detail"]
    assert out["data"] == {"evidence": {"paths": [], "refs": []}}
