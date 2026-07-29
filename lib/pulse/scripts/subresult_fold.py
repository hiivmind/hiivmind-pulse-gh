#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Fold an inner headless-sibling result envelope into workflow-run accumulators.

When a v2 workflow's pseudocode does ``INVOKE skill X-headless`` (see
``lib/patterns/workflow-execution.md`` § Headless Execution), the executor runs
the sibling driver, which writes its OWN ``{kind}-result.yaml`` (e.g.
``marketplace-sync-result.yaml``). That file is gitignored and overwritten per
run, and the maintenance PR body is the ONLY delivery channel for a scheduled
run's proposals. So the executor MUST fold the sibling's surfaced items into the
``workflow-run-result.yaml`` it emits — otherwise a scheduled F6–F9 run reports
zero proposals even when the sibling proposed many.

This module is that fold: deterministic and unit-tested, so the projection is a
concrete callable rather than a prose instruction that silently no-ops (the
exact failure mode that hid the gap until F10 was dogfooded).

**Contract — pass-through of the human-facing surface, not re-derivation.**
Every F10 driver already emits one ``proposed_actions`` string per proposal AND
per withheld/gated action; its ``proposals[]`` list is the *separate* machine
re-derivation channel (``{binding, transformation, proposal_id}``) consumed by
apply-mode (F11), and the ``workflow-run`` kind has no ``proposals`` field. So
the fold carries the inner ``findings``, ``proposed_actions``, and
``asks_recorded`` through verbatim and deliberately does NOT render
``proposals[]`` into ``proposed_actions`` — doing so would duplicate every line.

The fold is generic over any inner headless envelope: it takes ``findings`` /
``proposed_actions`` / ``asks_recorded`` when present (kinds that currently carry
them include marketplace-sync, plan-sync, generated-artifact, impact, and
fleet-membership) and contributes nothing for an envelope that lacks them. It is
never the caller's job to know which kinds surface what.

Usage: subresult_fold.py <inner-result.yaml>
       → prints JSON {"findings": [...], "proposed_actions": [...], "asks_recorded": [...]}
         on stdout; the executor extends its workflow-run accumulators with each list.

Exit codes: 0 ok (JSON on stdout), 2 file missing/unparseable, 3 not foldable.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

FOLDED_FIELDS = ("findings", "proposed_actions", "asks_recorded")


class SubresultFoldError(ValueError):
    """Raised when an inner result envelope cannot be folded into a workflow-run."""


def fold_subresult(inner: Any) -> dict[str, list]:
    """Return the ``findings`` / ``proposed_actions`` / ``asks_recorded`` to merge
    into a workflow-run result, given an inner headless result envelope.

    Each folded field is optional on the input (an envelope that omits it
    contributes an empty list), but when present it MUST be a list — a scalar or
    mapping there signals a malformed sibling result and raises rather than
    silently dropping data. ``findings`` mappings are shallow-copied so the
    caller can mutate its accumulator without aliasing the parsed input.
    """
    if not isinstance(inner, Mapping):
        raise SubresultFoldError("inner result must be a mapping")

    kind = inner.get("kind", "<unknown>")
    folded: dict[str, list] = {}
    for field in FOLDED_FIELDS:
        value = inner.get(field, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            raise SubresultFoldError(
                f"{kind} result field {field!r} must be a list, got {type(value).__name__}"
            )
        # Validate element shapes at this trust boundary — the sibling file is a
        # separate, gitignored artifact. A malformed element must raise here (→
        # recorded as a fold error) rather than pass through and blow up the
        # OUTER workflow-run schema validation, which reads as a skill bug.
        if field == "findings":
            for i, item in enumerate(value):
                if not isinstance(item, Mapping):
                    raise SubresultFoldError(
                        f"{kind} result findings[{i}] must be a mapping, "
                        f"got {type(item).__name__}"
                    )
            folded[field] = [dict(item) for item in value]
        else:
            for i, item in enumerate(value):
                if not isinstance(item, str):
                    raise SubresultFoldError(
                        f"{kind} result {field}[{i}] must be a string, "
                        f"got {type(item).__name__}"
                    )
            folded[field] = list(value)
    return folded


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("result", help="path to an inner {kind}-result.yaml to fold")
    args = ap.parse_args(argv)

    path = Path(args.result)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    try:
        inner = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        print(f"error: could not read {path}: {exc}", file=sys.stderr)
        return 2

    try:
        folded = fold_subresult(inner)
    except SubresultFoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    json.dump(folded, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
