"""Pure claim-currency audit for the Claude Code plugin overlay.

This module is a strict one-way dependency: ``claude_plugin`` imports
``repo_claims``, never the reverse. It is pure (no filesystem, no
subprocess, no GitHub) and the deterministic helpers (``facts`` and
``check_claims``) accept no inferred input.

Three responsibilities:

* ``facts``  — derive the repository's current ground truth
  (``skill_paths``, ``command_names``, ``manifest``) from the evidence
  snapshot. Deterministic; trusts only ``files`` and ``file_contents``.

* ``check_claims`` — scan a ``CLAUDE.md`` body for textual path
  references and report which ones disagree with the current facts.
  Deterministic; every finding carries ``inferred=False``.

* ``validate_inferred_findings`` — the schema guard for candidate
  findings produced by an external (non-deterministic) inference step.
  Any violation raises :class:`InferenceValidationError`; on success the
  returned findings are marked ``inferred=True``.

The reasoning for the split: extracting claims from prose is genuinely
non-deterministic and belongs to a skill or model. Once those raw
candidate findings exist, this module is the only place that decides
whether they are well-formed enough to fold into the deterministic
audit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import re
from typing import Any


CLAIM_KINDS = frozenset(
    {"missing_claimed_skill", "stale_command", "unsupported_evidence"}
)


PLUGIN_MANIFEST_PATH = ".claude-plugin/plugin.json"
SKILL_PATH_PREFIX = "skills/"
SKILL_FILENAME = "SKILL.md"
COMMAND_PATH_PREFIX = "commands/"
COMMAND_FILENAME_SUFFIX = ".md"
HOOKS_PATH_PREFIX = "hooks/"


_SKILL_RE = re.compile(r"skills/([^/\s]+)/SKILL\.md")
_COMMAND_RE = re.compile(r"commands/([^/\s]+)\.md")
_HOOKS_RE = re.compile(r"hooks/([\w\-]+(?:\.[\w\-]+)*)")


UNSUPPORTED_EVIDENCE_DETAIL = (
    "hooks are a recognized Claude artifact class that facts() does not "
    "model — claim surfaced, not verified"
)


@dataclass(frozen=True)
class ClaimFinding:
    """A single claim-currency disagreement or surfaced reference.

    ``inferred`` distinguishes deterministic findings (extracted by
    :func:`check_claims` from the text) from inferred findings (produced
    by an external inference step and validated by
    :func:`validate_inferred_findings`). Downstream consumers treat
    inferred findings as advisory unless paired with deterministic
    evidence.
    """

    kind: str
    subject: str
    detail: str
    inferred: bool


@dataclass(frozen=True)
class RepoFacts:
    """Current ground truth about a repository, derived deterministically."""

    skill_paths: frozenset[str]
    command_names: frozenset[str]
    manifest: dict[str, Any]


class InferenceValidationError(ValueError):
    """Raised when an inferred-claim candidate fails schema validation."""


def _safe_files(evidence: Any) -> tuple[str, ...]:
    """Return ``evidence['files']`` as a tuple of ``str`` or ``()``.

    Mirrors the defensive shape checks used by
    :func:`lib.pulse.scripts.adapters.generic._files` so that an
    evidence payload with a malformed ``files`` field yields an empty
    fact set rather than a crash.
    """
    value = evidence.get("files") if isinstance(evidence, Mapping) else None
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return ()
    if not all(isinstance(path, str) for path in value):
        return ()
    return tuple(value)


def _safe_contents(evidence: Any) -> dict[str, str]:
    """Return ``evidence['file_contents']`` as ``{path: str}`` or ``{}``."""
    value = (
        evidence.get("file_contents") if isinstance(evidence, Mapping) else None
    )
    if not isinstance(value, Mapping):
        return {}
    return {path: text for path, text in value.items() if isinstance(text, str)}


def _is_skill_path(path: str) -> bool:
    if not path.startswith(SKILL_PATH_PREFIX):
        return False
    if not path.endswith("/" + SKILL_FILENAME):
        return False
    remainder = path[len(SKILL_PATH_PREFIX) : -len("/" + SKILL_FILENAME)]
    return bool(remainder) and "/" not in remainder


def _is_command_path(path: str) -> bool:
    if not path.startswith(COMMAND_PATH_PREFIX):
        return False
    if not path.endswith(COMMAND_FILENAME_SUFFIX):
        return False
    remainder = path[len(COMMAND_PATH_PREFIX) : -len(COMMAND_FILENAME_SUFFIX)]
    return bool(remainder) and "/" not in remainder


def facts(evidence: Any) -> RepoFacts:
    """Derive :class:`RepoFacts` from an evidence mapping.

    Pure and deterministic. Only ``evidence['files']`` and
    ``evidence['file_contents']`` are read. The plugin manifest is
    parsed defensively: any absence, invalid JSON, or non-mapping root
    collapses to ``{}``.
    """
    files = _safe_files(evidence)
    skill_paths = frozenset(path for path in files if _is_skill_path(path))
    command_names = frozenset(
        path[len(COMMAND_PATH_PREFIX) : -len(COMMAND_FILENAME_SUFFIX)]
        for path in files
        if _is_command_path(path)
    )
    contents = _safe_contents(evidence)
    raw_manifest = contents.get(PLUGIN_MANIFEST_PATH)
    manifest: dict[str, Any] = {}
    if isinstance(raw_manifest, str):
        try:
            parsed = json.loads(raw_manifest)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, Mapping):
            manifest = dict(parsed)
    return RepoFacts(
        skill_paths=skill_paths,
        command_names=command_names,
        manifest=manifest,
    )


def check_claims(
    claude_md_text: str, facts: RepoFacts
) -> list[ClaimFinding]:
    """Scan ``claude_md_text`` for path references and audit them.

    Every returned finding is deterministic and carries
    ``inferred=False``. Findings are deduplicated by ``(kind, subject)``
    and sorted by the same key so that the result is stable across
    runs.

    The supported references are:

    * ``skills/<seg>/SKILL.md`` — must exist in ``facts.skill_paths``,
      otherwise a ``missing_claimed_skill`` finding is produced.
    * ``commands/<name>.md`` — ``name`` must exist in
      ``facts.command_names``, otherwise a ``stale_command`` finding
      is produced.
    * ``hooks/<file>`` — a recognized Claude artifact class that
      :func:`facts` does not model. The reference is always surfaced
      as ``unsupported_evidence`` (never guessed at).
    """
    findings: dict[tuple[str, str], ClaimFinding] = {}

    for match in _SKILL_RE.finditer(claude_md_text):
        path = match.group(0)
        if path in facts.skill_paths:
            continue
        findings[("missing_claimed_skill", path)] = ClaimFinding(
            kind="missing_claimed_skill",
            subject=path,
            detail=f"CLAUDE.md references {path} but no such skill exists",
            inferred=False,
        )

    for match in _COMMAND_RE.finditer(claude_md_text):
        name = match.group(1)
        if name in facts.command_names:
            continue
        findings[("stale_command", name)] = ClaimFinding(
            kind="stale_command",
            subject=name,
            detail=(
                f"CLAUDE.md references commands/{name}.md but no such "
                "command exists"
            ),
            inferred=False,
        )

    for match in _HOOKS_RE.finditer(claude_md_text):
        path = match.group(0)
        findings[("unsupported_evidence", path)] = ClaimFinding(
            kind="unsupported_evidence",
            subject=path,
            detail=UNSUPPORTED_EVIDENCE_DETAIL,
            inferred=False,
        )

    return [findings[key] for key in sorted(findings)]


def validate_inferred_findings(raw: Any) -> list[ClaimFinding]:
    """Validate a raw list of inferred-claim candidates.

    The schema for each item is:

    * ``kind``   — must be in :data:`CLAIM_KINDS`.
    * ``subject`` — must be a non-empty ``str``.
    * ``detail`` — must be a ``str``.
    * ``inferred`` — if present, must be ``True`` (absent is allowed and
      coerced to ``True``).

    Any violation raises :class:`InferenceValidationError` naming the
    first offending item; the candidate list is never silently truncated
    or coerced. ``raw`` is accepted as any :class:`collections.abc.Sequence`
    so that callers passing the frozen :class:`CheckContext` evidence
    (where lists are normalised to tuples) still validate correctly —
    the schema is about the shape of the payload, not its concrete
    Python container type.
    """
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise InferenceValidationError(
            "inferred claims must be a list, got "
            f"{type(raw).__name__}"
        )

    validated: list[ClaimFinding] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise InferenceValidationError(
                f"inferred claim at index {index} is not a mapping"
            )
        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in CLAIM_KINDS:
            raise InferenceValidationError(
                f"inferred claim at index {index} has invalid kind: "
                f"{kind!r}"
            )
        subject = item.get("subject")
        if not isinstance(subject, str) or not subject:
            raise InferenceValidationError(
                f"inferred claim at index {index} has invalid subject: "
                f"{subject!r}"
            )
        detail = item.get("detail")
        if not isinstance(detail, str):
            raise InferenceValidationError(
                f"inferred claim at index {index} has invalid detail: "
                f"{detail!r}"
            )
        if "inferred" in item and item["inferred"] is not True:
            raise InferenceValidationError(
                f"inferred claim at index {index} has inferred != True"
            )
        validated.append(
            ClaimFinding(
                kind=kind,
                subject=subject,
                detail=detail,
                inferred=True,
            )
        )
    return validated


__all__ = [
    "CLAIM_KINDS",
    "ClaimFinding",
    "InferenceValidationError",
    "RepoFacts",
    "check_claims",
    "facts",
    "validate_inferred_findings",
]
