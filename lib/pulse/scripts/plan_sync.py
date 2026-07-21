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
from typing import Any

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
