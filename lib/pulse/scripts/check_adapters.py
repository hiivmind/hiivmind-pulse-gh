"""Pure registry boundary for dispatched healthcheck adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from types import MappingProxyType
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


class EvidenceCitations(TypedDict):
    """Normalized citations supporting an adapter result."""

    paths: list[str]
    refs: list[str]


class CheckBlock(TypedDict):
    """Normalized output shared by every registered adapter."""

    check_id: str
    adapter: str
    weight: float
    status: str
    detail: str
    data: dict[str, Any]


def _freeze(value: Any) -> Any:
    """Defensively copy mutable containers into deeply immutable equivalents."""
    if isinstance(value, Mapping):
        return MappingProxyType({_freeze(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def _check_metadata(check: Any) -> tuple[str, float]:
    if isinstance(check, Mapping):
        check_id = check.get("check_id", check.get("id"))
        weight = check.get("weight")
    else:
        check_id = getattr(check, "check_id", None)
        weight = getattr(check, "weight", None)

    if not isinstance(check_id, str) or not check_id:
        raise ValueError("check id must be a non-empty string")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise TypeError("check weight must be numeric")
    normalized_weight = float(weight)
    if not isfinite(normalized_weight) or normalized_weight < 0:
        raise ValueError("check weight must be finite and nonnegative")
    return check_id, normalized_weight


@dataclass(frozen=True)
class CheckContext:
    """Read-only inputs supplied to one adapter evaluation."""

    repo: str
    evidence: Any
    check: Any
    workspace: Path

    def __post_init__(self) -> None:
        _check_metadata(self.check)
        object.__setattr__(self, "evidence", _freeze(self.evidence))
        object.__setattr__(self, "check", _freeze(self.check))

    @property
    def check_id(self) -> str:
        return _check_metadata(self.check)[0]

    @property
    def weight(self) -> float:
        return _check_metadata(self.check)[1]


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
                context,
                "unsupported",
                f"No adapter registered: {name}",
            )

        try:
            output = adapter(context)
            return self._normalize(name, context, output)
        except Exception as exc:
            return self._boundary_block(
                name, context, "error", f"Adapter {name} failed: {exc}"
            )

    @classmethod
    def _normalize(
        cls, name: str, context: CheckContext, output: object
    ) -> CheckBlock:
        if not isinstance(output, Mapping):
            raise ValueError("invalid output: expected a mapping")

        status = output.get("status")
        detail = output.get("detail")
        data = output.get("data")
        if status not in CHECK_STATUSES:
            raise ValueError(f"invalid output status: {status}")
        if not isinstance(detail, str):
            raise ValueError("invalid output detail: expected a string")
        if not isinstance(data, Mapping):
            raise ValueError("invalid output data: expected a mapping")

        normalized_data = dict(data)
        normalized_data["evidence"] = cls._normalize_evidence(data.get("evidence"))

        return {
            "check_id": context.check_id,
            "adapter": name,
            "weight": context.weight,
            "status": status,
            "detail": detail,
            "data": normalized_data,
        }

    @staticmethod
    def _normalize_evidence(value: object) -> EvidenceCitations:
        if not isinstance(value, Mapping):
            raise ValueError("invalid output data.evidence: expected a mapping")
        if set(value) != {"paths", "refs"}:
            raise ValueError("invalid output data.evidence: expected paths and refs")

        normalized: EvidenceCitations = {"paths": [], "refs": []}
        for key in ("paths", "refs"):
            items = value[key]
            if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
                raise ValueError(
                    f"invalid output data.evidence.{key}: expected a sequence"
                )
            if not all(isinstance(item, str) for item in items):
                raise ValueError(
                    f"invalid output data.evidence.{key}: expected strings"
                )
            normalized[key] = list(items)
        return normalized

    @staticmethod
    def _boundary_block(
        name: str, context: CheckContext, status: str, detail: str
    ) -> CheckBlock:
        return {
            "check_id": context.check_id,
            "adapter": name,
            "weight": context.weight,
            "status": status,
            "detail": detail,
            "data": {"evidence": {"paths": [], "refs": []}},
        }
