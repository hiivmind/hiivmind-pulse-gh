"""Pure registry boundary for dispatched healthcheck adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict


CHECK_STATUSES = {
    "pass",
    "warn",
    "fail",
    "unknown",
    "not_applicable",
    "unsupported",
    "error",
}


class CheckBlock(TypedDict):
    """Normalized output shared by every registered adapter."""

    adapter: str
    status: str
    detail: str
    data: dict[str, Any]


@dataclass(frozen=True)
class CheckContext:
    """Read-only inputs supplied to one adapter evaluation."""

    repo: str
    evidence: Any
    check: Any
    workspace: Path


Adapter = Callable[[CheckContext], object]


class AdapterRegistry:
    """Register healthcheck adapters and normalize their output."""

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, name: str, fn: Adapter) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("adapter name must be a non-empty string")
        if not callable(fn):
            raise TypeError("adapter must be callable")
        self._adapters[name] = fn

    def evaluate(self, name: str, context: CheckContext) -> CheckBlock:
        adapter = self._adapters.get(name)
        if adapter is None:
            return self._boundary_block(
                name,
                "unsupported",
                f"No adapter registered: {name}",
            )

        try:
            output = adapter(context)
            return self._normalize(name, output)
        except Exception as exc:
            return self._boundary_block(name, "error", f"Adapter {name} failed: {exc}")

    @classmethod
    def _normalize(cls, name: str, output: object) -> CheckBlock:
        if not isinstance(output, Mapping):
            raise ValueError("invalid output: expected a mapping")

        status = output.get("status")
        detail = output.get("detail")
        data = output.get("data")
        if status not in CHECK_STATUSES:
            raise ValueError(f"invalid output status: {status}")
        if not isinstance(detail, str):
            raise ValueError("invalid output detail: expected a string")
        if not isinstance(data, dict):
            raise ValueError("invalid output data: expected a mapping")

        return {
            "adapter": name,
            "status": status,
            "detail": detail,
            "data": dict(data),
        }

    @staticmethod
    def _boundary_block(name: str, status: str, detail: str) -> CheckBlock:
        return {
            "adapter": name,
            "status": status,
            "detail": detail,
            "data": {},
        }
