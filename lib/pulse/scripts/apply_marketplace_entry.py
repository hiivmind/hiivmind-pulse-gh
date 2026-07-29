#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ruamel.yaml>=0.18.0"]
# ///
"""Apply one guarded marketplace entry patch from a pen checkout.

The variable patch content lives in a well-known file rather than command
arguments.  This script only writes after the target's Git blob hash matches
the patch's recorded base, so a stale checkout cannot overwrite newer work.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
from typing import Any

from ruamel.yaml import YAML


_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


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


def apply_marketplace_patch_file(patch_file: Path, checkout: Path) -> None:
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
        original_text = original_bytes.decode()
    except UnicodeDecodeError as exc:
        raise ValueError(f"document is not UTF-8: {path}") from exc

    if "content" in patch:
        new_content = str(patch["content"])
    elif "entry_patch" in patch or "plugin_patch" in patch:
        entry_patch = patch.get("entry_patch") or patch.get("plugin_patch")
        if not isinstance(entry_patch, dict):
            raise ValueError("patch.entry_patch must be a mapping")

        # Handle JSON or YAML target document
        try:
            doc_data = json.loads(original_text)
        except json.JSONDecodeError:
            doc_data = yaml.load(original_text)

        plugin_name = entry_patch.get("name") or entry_patch.get("plugin_id")
        if not plugin_name:
            raise ValueError("entry_patch must contain 'name' or 'plugin_id'")

        if isinstance(doc_data, dict) and isinstance(doc_data.get("plugins"), list):
            found = False
            for plugin in doc_data["plugins"]:
                if isinstance(plugin, dict) and plugin.get("name") == plugin_name:
                    plugin.update({k: v for k, v in entry_patch.items() if k not in ("plugin_id",)})
                    found = True
                    break
            if not found:
                doc_data["plugins"].append({k: v for k, v in entry_patch.items() if k not in ("plugin_id",)})
        else:
            raise ValueError("target document structure does not match marketplace schema")

        if path.name.endswith(".json"):
            new_content = json.dumps(doc_data, indent=2) + "\n"
        else:
            stream = io.StringIO()
            yaml.dump(doc_data, stream)
            new_content = stream.getvalue()
    else:
        raise ValueError("patch must contain 'content' or 'entry_patch'")

    target.write_text(new_content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", default=".hiivmind/marketplace-entry-patch.yaml")
    args = parser.parse_args(argv)
    checkout = Path.cwd().resolve()
    try:
        apply_marketplace_patch_file(checkout / _relative_path(args.patch, "--patch"), checkout)
    except (OSError, UnicodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
