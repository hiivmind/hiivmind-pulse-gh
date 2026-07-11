#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Compute per-section staleness from a freshness.yaml file.

Timestamps are the authority: any stored `stale:` flag is ignored and staleness
is recomputed as (now - last_checked) > threshold_hours, with null last_checked
always stale. Output is the `sections` + `refresh_needed` payload of the
`status` result kind (lib/patterns/headless-contract.md).

Usage: freshness_status.py --freshness <freshness.yaml> [--now <ISO 8601 UTC>]

Exit codes: 0 ok (JSON on stdout), 2 file missing or unparseable.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_THRESHOLD_HOURS = 168


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freshness", required=True)
    ap.add_argument("--now", default="")
    args = ap.parse_args()

    path = Path(args.freshness)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    import yaml
    try:
        doc = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        print(f"error: unparseable YAML: {e}", file=sys.stderr)
        return 2

    now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
    default_threshold = (doc.get("defaults") or {}).get(
        "threshold_hours", DEFAULT_THRESHOLD_HOURS)

    sections = []
    for sid, s in (doc.get("sections") or {}).items():
        if not isinstance(s, dict):
            continue
        last = s.get("last_checked")
        threshold = s.get("threshold_hours", default_threshold)
        # pyyaml parses unquoted ISO timestamps to datetime; normalize to str + UTC
        if isinstance(last, datetime):
            checked = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
            last = checked.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if last is None:
            stale = True
        else:
            try:
                age_hours = (now - parse_ts(str(last))).total_seconds() / 3600
                stale = age_hours > threshold
            except ValueError:
                stale = True
        sections.append({"id": sid, "stale": stale, "last_checked": last})

    print(json.dumps({"sections": sections,
                      "refresh_needed": any(s["stale"] for s in sections)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
