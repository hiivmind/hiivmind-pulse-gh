#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ruamel.yaml>=0.18.0"]
# ///
"""Apply one guarded plan-document patch from a pen checkout.

The variable patch content lives in a well-known file rather than command
arguments.  This script only writes after the target's Git blob hash matches
the patch's recorded base, so a stale checkout cannot overwrite newer work.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Any

from ruamel.yaml import YAML


# The script is invoked by an absolute plugin path while its working directory
# is a pen checkout.  Keep the plugin root importable without depending on the
# checkout containing the Pulse package itself.
_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib.pulse.scripts.plan_sync import patch_document  # noqa: E402


def _blob_sha(content: bytes) -> str:
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


def _relative_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a safe relative path")
    return path


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def apply_patch_file(patch_file: Path, checkout: Path) -> None:
    yaml = YAML(typ="safe")
    try:
        patch = _mapping(yaml.load(patch_file.read_text()), "patch")
    except FileNotFoundError as exc:
        raise ValueError(f"patch file not found: {patch_file}") from exc

    path = _relative_path(patch.get("path"), "patch.path")
    output_paths = patch.get("output_paths")
    if not isinstance(output_paths, list) or not output_paths:
        raise ValueError("patch.output_paths must be a non-empty list")
    allowed_paths = {
        str(_relative_path(output_path, "patch.output_paths entry"))
        for output_path in output_paths
    }
    if str(path) not in allowed_paths:
        raise ValueError(f"document is outside the output allowlist: {path}")
    target = (checkout / path).resolve()
    try:
        target.relative_to(checkout.resolve())
    except ValueError as exc:
        raise ValueError("patch.path escapes the checkout") from exc
    if not target.is_file():
        raise ValueError(f"document not found: {path}")

    base_blob = patch.get("base_blob")
    if not isinstance(base_blob, str) or not base_blob:
        raise ValueError("patch.base_blob must be a non-empty string")
    original_bytes = target.read_bytes()
    if _blob_sha(original_bytes) != base_blob:
        raise ValueError(f"base blob mismatch for document: {path}")

    try:
        original = original_bytes.decode()
    except UnicodeDecodeError as exc:
        raise ValueError(f"document is not UTF-8: {path}") from exc
    doc_patch = _mapping(patch.get("doc_patch"), "patch.doc_patch")
    sync_patch = _mapping(patch.get("sync_patch"), "patch.sync_patch")
    target.write_text(patch_document(original, doc_patch, sync_patch))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", default=".hiivmind/plan-sync-patch.yaml")
    args = parser.parse_args(argv)
    checkout = Path.cwd().resolve()
    try:
        apply_patch_file(checkout / _relative_path(args.patch, "--patch"), checkout)
    except (OSError, UnicodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
