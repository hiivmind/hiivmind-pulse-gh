#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0", "packaging>=23.0", "tomli>=2.0; python_version<'3.11'"]
# ///
"""Pure contract-version extraction and comparison for dependency edges.

An edge may declare a `contract:` block that names a producer version file
(in the upstream repo) and a consumer requirement file (also in the upstream
repo), plus a parser for each and an optional version scheme.

Parser specs (v1):
  - {kind: regex, pattern} — pattern must contain EXACTLY ONE capture group;
    the extracted value is the first match's first group.
  - {kind: toml, key} — dotted key path into a TOML document, e.g.
    `project.version`.
  - {kind: json, pointer} — RFC 6901 JSON pointer, e.g. `/version` or
    `/deps/foo`.
  - {kind: yaml, key} — dotted key path into a YAML document.

Any failure to read, parse, or locate the requested value returns `None` from
`extract()` and ultimately produces `state: unknown` from `evaluate()` — the
module never guesses.

Version comparison:
  - `version_scheme: pep440` — parse the producer value with
    `packaging.version.Version` and the consumer value with
    `packaging.specifiers.SpecifierSet`. If the consumer value parses as a
    specifier set, compatibility is `Version(producer) in SpecifierSet(consumer)`;
    if it is a bare version, compatibility is an exact equality comparison of
    the two parsed versions. Any `InvalidVersion` or `InvalidSpecifier` results
    in `unknown`.
  - No `version_scheme` (or any non-pep440 scheme) — compatibility is plain
    string equality of the two extracted values.

The module is pure: it performs no network or disk I/O directly. The caller
injects a `read_file(repo, path) -> bytes` reader.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


# --------------------------------------------------------------------------
# Parser spec validation
# --------------------------------------------------------------------------

def validate_parser_spec(parser_spec: dict) -> None:
    """Validate a parser spec at load time.

    Raises ValueError with a clear message if the spec is malformed.
    """
    kind = parser_spec.get("kind")
    if kind == "regex":
        pattern = parser_spec.get("pattern", "")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern: {exc}") from None
        if compiled.groups != 1:
            raise ValueError(
                f"regex parser pattern must have exactly one capture group, "
                f"got {compiled.groups}: {pattern!r}"
            )
    elif kind in ("toml", "yaml", "json"):
        key_name = "key" if kind in ("toml", "yaml") else "pointer"
        if key_name not in parser_spec:
            raise ValueError(f"{kind} parser spec must include a '{key_name}'")
    else:
        raise ValueError(f"unsupported parser kind: {kind!r}")


# --------------------------------------------------------------------------
# Value extraction
# --------------------------------------------------------------------------

def extract(parser_spec: dict, content_bytes: bytes) -> str | None:
    """Extract a string value from `content_bytes` according to
    `parser_spec`. Returns None on any failure."""
    try:
        validate_parser_spec(parser_spec)
    except ValueError:
        return None

    kind = parser_spec["kind"]
    if kind == "regex":
        return _extract_regex(parser_spec, content_bytes)
    if kind == "toml":
        return _extract_toml(parser_spec, content_bytes)
    if kind == "json":
        return _extract_json(parser_spec, content_bytes)
    if kind == "yaml":
        return _extract_yaml(parser_spec, content_bytes)
    return None


def _extract_regex(parser_spec: dict, content_bytes: bytes) -> str | None:
    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    compiled = re.compile(parser_spec["pattern"])
    match = compiled.search(text)
    if not match:
        return None
    return match.group(1)


def _extract_toml(parser_spec: dict, content_bytes: bytes) -> str | None:
    try:
        text = content_bytes.decode("utf-8")
        data = tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return _get_dotted(data, parser_spec["key"])


def _extract_yaml(parser_spec: dict, content_bytes: bytes) -> str | None:
    try:
        text = content_bytes.decode("utf-8")
        data = yaml.safe_load(text)
    except (UnicodeDecodeError, yaml.YAMLError):
        return None
    return _get_dotted(data, parser_spec["key"])


def _extract_json(parser_spec: dict, content_bytes: bytes) -> str | None:
    try:
        text = content_bytes.decode("utf-8")
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _resolve_json_pointer(data, parser_spec["pointer"])


def _get_dotted(data, key_path: str) -> str | None:
    if data is None:
        return None
    current = data
    for part in key_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, str):
        return current
    if current is None:
        return None
    return str(current)


def _resolve_json_pointer(data, pointer: str) -> str | None:
    """Resolve a simple RFC 6901 JSON pointer (no escaped characters)."""
    if pointer == "" or pointer == "/":
        return None
    parts = pointer.lstrip("/").split("/")
    current = data
    for part in parts:
        if part == "":
            return None
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError):
                return None
        else:
            return None
    if isinstance(current, str):
        return current
    if current is None:
        return None
    return str(current)


# --------------------------------------------------------------------------
# Contract evaluation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ContractState:
    state: str  # compatible | gap | unknown
    producer_version: str | None
    consumer_requirement: str | None


def evaluate(edge: dict, read_file) -> ContractState:
    """Evaluate the contract declared on a `depends_on` object edge.

    `read_file(repo, path) -> bytes` is an injectable reader. Any I/O or
    parse failure, or an unsupported version scheme, returns `unknown`.
    """
    contract = edge.get("contract") or {}
    if not contract:
        return ContractState("unknown", None, None)

    upstream = edge.get("repo")
    producer_spec = contract.get("producer") or {}
    consumer_spec = contract.get("consumer") or {}
    version_scheme = contract.get("version_scheme")

    producer_version = _read_and_extract(upstream, producer_spec, read_file)
    consumer_requirement = _read_and_extract(upstream, consumer_spec, read_file)

    if producer_version is None or consumer_requirement is None:
        return ContractState("unknown", producer_version, consumer_requirement)

    if version_scheme == "pep440":
        return _evaluate_pep440(producer_version, consumer_requirement)

    return ContractState(
        "compatible" if producer_version == consumer_requirement else "gap",
        producer_version,
        consumer_requirement,
    )


def _read_and_extract(repo: str, spec: dict, read_file) -> str | None:
    if not spec:
        return None
    path = spec.get("path")
    parser_spec = spec.get("parser")
    if not path or not parser_spec:
        return None
    try:
        content = read_file(repo, path)
    except Exception:
        return None
    if content is None:
        return None
    return extract(parser_spec, content)


def _evaluate_pep440(producer_version: str, consumer_requirement: str) -> ContractState:
    try:
        producer = Version(producer_version)
    except InvalidVersion:
        return ContractState("unknown", producer_version, consumer_requirement)

    try:
        spec = SpecifierSet(consumer_requirement)
        compatible = producer in spec
    except InvalidSpecifier:
        try:
            consumer = Version(consumer_requirement)
            compatible = producer == consumer
        except InvalidVersion:
            return ContractState("unknown", producer_version, consumer_requirement)

    return ContractState(
        "compatible" if compatible else "gap",
        producer_version,
        consumer_requirement,
    )
