"""Proves AdapterRegistry.evaluate's exception boundary never leaks the
caught exception's message on any channel — this is a general dispatch-
boundary fix, not dependency-specific; it protects every registered adapter's
error path, including the F4 dependency adapters."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from lib.pulse.scripts.check_adapters import AdapterRegistry, CheckContext


CANARY = "CANARY-SECRET-9f3c2b1a-do-not-leak-this-string"


def _context() -> CheckContext:
    return CheckContext(
        repo="testorg/widget",
        evidence={},
        check={"id": "docs", "adapter": "broken", "weight": 1},
        workspace=Path("/workspace"),
    )


def test_exception_message_never_appears_in_the_returned_check_block():
    registry = AdapterRegistry()

    def _boom(_context):
        raise RuntimeError(CANARY)

    registry.register("broken", _boom)
    out = registry.evaluate("broken", _context())

    assert out["status"] == "error"
    assert CANARY not in out["detail"]
    assert CANARY not in repr(out)
    assert CANARY not in str(out["data"])


def test_exception_message_never_reaches_stdout_or_stderr():
    registry = AdapterRegistry()

    def _boom(_context):
        raise RuntimeError(CANARY)

    registry.register("broken", _boom)

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    real_stdout, real_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = captured_stdout, captured_stderr
    try:
        registry.evaluate("broken", _context())
    finally:
        sys.stdout, sys.stderr = real_stdout, real_stderr

    assert CANARY not in captured_stdout.getvalue()
    assert CANARY not in captured_stderr.getvalue()  # no exemption for stderr


def test_exception_message_never_appears_regardless_of_exception_type():
    registry = AdapterRegistry()

    for exc_type in (ValueError, KeyError, TypeError, RuntimeError, Exception):

        def _boom(_context, _exc_type=exc_type):
            raise _exc_type(CANARY)

        registry.register("broken", _boom)
        out = registry.evaluate("broken", _context())
        assert CANARY not in out["detail"]
        assert out["status"] == "error"


def test_detail_is_a_fixed_content_free_template():
    registry = AdapterRegistry()
    registry.register("broken", lambda _c: 1 / 0)
    out = registry.evaluate("broken", _context())
    assert out["detail"] == "Adapter broken raised an internal error"
