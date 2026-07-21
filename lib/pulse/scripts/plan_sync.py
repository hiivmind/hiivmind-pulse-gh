#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ruamel.yaml>=0.18.0"]
# ///
"""Lossless parsing and patching for GitHub-bound Markdown plans."""
from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import re
from typing import Any, Mapping

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


_YAML = YAML(typ="rt")
_YAML.preserve_quotes = True
_FRONTMATTER = re.compile(
    r"\A(?P<opening>---(?P<line_ending>\r?\n))"
    r"(?P<content>.*?)"
    r"(?P<closing>^---(?:\r?\n|\Z))",
    re.DOTALL | re.MULTILINE,
)
_H1 = re.compile(r"^# (?P<title>[^\r\n]*)(?=\r?$)", re.MULTILINE)


@dataclass(frozen=True)
class BoundDocument:
    """A Markdown document and its optional ``sync:`` frontmatter block."""

    frontmatter: Any | None
    body: str
    title: str | None
    binding: Any | None


@dataclass(frozen=True)
class FieldDecision:
    """The selected outcome for reconciling one synchronized field."""

    decision: str
    value: Any | None


@dataclass(frozen=True)
class ReconciliationPlan:
    """Pure patches and conflicts resulting from a three-way reconciliation."""

    doc_patch: dict[str, Any]
    github_patch: dict[str, Any]
    base_patch: dict[str, Any]
    conflicts: tuple[str, ...]

    @property
    def conflicted(self) -> bool:
        """Whether any field requires manual reconciliation."""
        return bool(self.conflicts)


_SYNC_FIELDS = ("title", "state", "assignees", "milestone", "body")


def _normalise(field: str, value: Any) -> Any:
    if field == "assignees":
        return sorted(set(value or ()))
    return value


def merge_field(
    field: str,
    base: Any,
    doc: Any,
    github: Any,
    policy: str | None = None,
) -> FieldDecision:
    """Determine a pure three-way merge outcome for a single plan field."""
    base_value = _normalise(field, base)
    doc_value = _normalise(field, doc)
    github_value = _normalise(field, github)
    doc_changed = doc_value != base_value
    github_changed = github_value != base_value

    if not doc_changed and not github_changed:
        return FieldDecision("noop", None)
    if doc_changed and not github_changed:
        return FieldDecision("apply_to_github", doc_value)
    if github_changed and not doc_changed:
        return FieldDecision("apply_to_doc", github_value)
    if doc_value == github_value:
        return FieldDecision("agree", doc_value)
    if policy == "prefer-doc":
        return FieldDecision("apply_to_github", doc_value)
    if policy == "prefer-github":
        return FieldDecision("apply_to_doc", github_value)
    return FieldDecision("conflict", None)


def _field_value(source: Mapping[str, Any] | BoundDocument, field: str) -> Any:
    if isinstance(source, BoundDocument):
        if field == "title":
            return source.title
        if field == "body":
            return source.body
        if isinstance(source.frontmatter, Mapping):
            return source.frontmatter.get(field)
        return None
    return source.get(field)


def compute(
    doc: Mapping[str, Any] | BoundDocument,
    github: Mapping[str, Any],
    binding: Mapping[str, Any],
    base_body: Any,
) -> ReconciliationPlan:
    """Reconcile V1 plan fields into independent document, GitHub, and base patches."""
    base = binding.get("base", {})
    policies = binding.get("policy", {})
    doc_patch: dict[str, Any] = {}
    github_patch: dict[str, Any] = {}
    base_patch: dict[str, Any] = {}
    conflicts: list[str] = []

    for field in _SYNC_FIELDS:
        base_value = base_body if field == "body" else base.get(field)
        policy = policies.get(field) if isinstance(policies, Mapping) else None
        outcome = merge_field(
            field,
            base_value,
            _field_value(doc, field),
            github.get(field),
            policy,
        )
        if outcome.decision == "conflict":
            conflicts.append(field)
        elif outcome.decision == "apply_to_doc":
            doc_patch[field] = outcome.value
            base_patch[field] = outcome.value
        elif outcome.decision == "apply_to_github":
            github_patch[field] = outcome.value
            base_patch[field] = outcome.value
        elif outcome.decision == "agree":
            base_patch[field] = outcome.value

    return ReconciliationPlan(doc_patch, github_patch, base_patch, tuple(conflicts))


def _split_frontmatter(text: str) -> tuple[re.Match[str] | None, str]:
    match = _FRONTMATTER.match(text)
    return match, text[match.end():] if match else text


def _title_from(body: str) -> str | None:
    match = _H1.search(body)
    return match.group("title") if match else None


def parse_document(text: str) -> BoundDocument:
    """Parse frontmatter without normalizing the Markdown body."""
    match, body = _split_frontmatter(text)
    if match is None:
        return BoundDocument(None, body, _title_from(body), None)

    frontmatter = _YAML.load(match.group("content"))
    binding = frontmatter.get("sync") if isinstance(frontmatter, dict) else None
    return BoundDocument(frontmatter, body, _title_from(body), binding)


def _replace_title(body: str, title: str) -> str:
    match = _H1.search(body)
    if match is None:
        raise ValueError("document has no H1 title to patch")
    start, end = match.span("title")
    return body[:start] + title + body[end:]


def _dump_frontmatter(frontmatter: Any, line_ending: str) -> str:
    output = StringIO()
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.line_break = line_ending
    yaml.dump(frontmatter, output)
    # ruamel's comment attachment can otherwise yield ``\r\r\n`` for an
    # inline-commented mapping when serializing a CRLF source document.
    return output.getvalue().replace("\r\r\n", "\r\n")


def _apply_base_patch(binding: Any, sync_patch: dict) -> None:
    if not isinstance(binding, dict):
        raise ValueError("document has no sync binding to patch")

    base_patch = sync_patch.get("base", sync_patch)
    if not isinstance(base_patch, dict):
        raise TypeError("sync patch must be a mapping of base fields")

    base = binding.get("base")
    if base is None:
        base = CommentedMap()
        binding["base"] = base
    if not isinstance(base, dict):
        raise TypeError("sync.base must be a mapping")
    base.update(base_patch)


def patch_document(text: str, doc_patch: dict, sync_patch: dict) -> str:
    """Apply document and ``sync.base`` updates while preserving untouched text."""
    if not doc_patch and not sync_patch:
        return text

    match, original_body = _split_frontmatter(text)
    document = parse_document(text)
    body = doc_patch.get("body", original_body)
    if "title" in doc_patch:
        body = _replace_title(body, doc_patch["title"])

    if not sync_patch:
        return text[:match.end()] + body if match else body

    if match is None:
        raise ValueError("document has no frontmatter to patch")
    _apply_base_patch(document.binding, sync_patch)
    frontmatter = _dump_frontmatter(document.frontmatter, match.group("line_ending"))
    return match.group("opening") + frontmatter + match.group("closing") + body
