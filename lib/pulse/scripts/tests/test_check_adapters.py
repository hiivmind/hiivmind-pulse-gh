"""Tests for the healthcheck adapter registry boundary."""

from dataclasses import FrozenInstanceError
from pathlib import Path

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
    assert out["status"] == "unsupported"
    assert out["adapter"] == "rust.lockfiles"


def test_adapter_exception_is_error():
    registry = AdapterRegistry()
    registry.register("broken", lambda _: 1 / 0)
    assert registry.evaluate("broken", context())["status"] == "error"


def test_context_is_immutable():
    ctx = context()

    with pytest.raises(FrozenInstanceError):
        ctx.repo = "testorg/other"  # type: ignore[misc]


def test_valid_adapter_output_is_normalized():
    registry = AdapterRegistry()
    registry.register(
        "generic.docs",
        lambda ctx: {
            "status": "pass",
            "detail": f"Documentation found in {ctx.repo}",
            "data": {"path": "README.md"},
        },
    )

    assert registry.evaluate("generic.docs", context()) == {
        "adapter": "generic.docs",
        "status": "pass",
        "detail": "Documentation found in testorg/widget",
        "data": {"path": "README.md"},
    }


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
    assert out["status"] == "error"
    assert "invalid output" in out["detail"]
    assert out["data"] == {}
