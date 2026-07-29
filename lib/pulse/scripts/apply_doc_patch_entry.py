#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ruamel.yaml>=0.18.0"]
# ///
"""Console entry point for pulse-apply-doc-patch.

Wraps lib.pulse.scripts.apply_doc_patch so the applier can be installed on PATH
and executed regardless of the target checkout directory.
"""
from __future__ import annotations

from pathlib import Path
import sys

# Ensure plugin root is in sys.path when invoked directly or via entry point
_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib.pulse.scripts.apply_doc_patch import main as _apply_doc_patch_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return _apply_doc_patch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
