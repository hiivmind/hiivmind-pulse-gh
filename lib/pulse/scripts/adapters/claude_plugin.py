"""Claude Code plugin healthcheck adapters.

These adapters extend the neutral scorecard surface with checks that only
make sense for repositories that follow the Claude Code plugin layout
(````.claude-plugin/plugin.json`` plus ````skills/*/SKILL.md````). The
content they read is sourced from an overlay-scoped ````file_contents`````
map on the evidence; the neutral snapshot never carries content, so the
adapters stay inert on repositories that have no overlay enabled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import dataclasses
import json
from typing import Any

import yaml

from lib.pulse.scripts import repo_claims
from lib.pulse.scripts.adapters import generic
from lib.pulse.scripts.check_adapters import CheckContext


F0_FILES_REF = generic.F0_FILES_REF

PLUGIN_MANIFEST_PATH = ".claude-plugin/plugin.json"
CLAUDE_CONTEXT_PATH = "CLAUDE.md"
SKILL_PATH_PREFIX = "skills/"
SKILL_FILENAME = "SKILL.md"


def _result(
    status: str,
    detail: str,
    *,
    paths: Sequence[str] = (),
    refs: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "status": status,
        "detail": detail,
        "data": {
            "evidence": {
                "paths": list(paths),
                "refs": list(refs),
            }
        },
    }


def _evidence_gap(
    detail: str,
    *,
    paths: Sequence[str] = (),
    refs: Sequence[str] = (F0_FILES_REF,),
) -> dict[str, Any]:
    return _result(
        "unknown", f"Evidence gap: {detail}", paths=paths, refs=refs
    )


def _files(context: CheckContext) -> tuple[str, ...] | None:
    return generic._files(context)


def _file_content(context: CheckContext, path: str) -> str | None:
    """Return the verbatim content of ``path`` from the overlay content map.

    Returns ``None`` when the map is missing, malformed, the path is
    absent, or the stored value is not a ``str`` — mirroring the
    defensive shape checks used by ``generic._files``.
    """
    contents = context.evidence.get("file_contents")
    if not isinstance(contents, Mapping):
        return None
    value = contents.get(path)
    if not isinstance(value, str):
        return None
    return value


def _is_skill_path(path: str) -> bool:
    if not path.startswith(SKILL_PATH_PREFIX):
        return False
    if not path.endswith("/" + SKILL_FILENAME):
        return False
    remainder = path[len(SKILL_PATH_PREFIX) : -len("/" + SKILL_FILENAME)]
    return bool(remainder) and "/" not in remainder


def _skill_paths(files: Sequence[str]) -> list[str]:
    return sorted(path for path in files if _is_skill_path(path))


def _parse_frontmatter(text: str) -> tuple[Mapping[str, Any] | None, str | None]:
    """Split a ``SKILL.md`` body into frontmatter mapping and remainder.

    Returns a tuple ``(frontmatter, error)``. ``error`` is ``None`` on
    success and a short diagnostic string on any malformation (the caller
    surfaces this as ``fail`` rather than letting an exception escape).
    """
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None, "missing opening fence"
    end_index = None
    for index in range(1, len(lines)):
        if lines[index] == "---":
            end_index = index
            break
    if end_index is None:
        return None, "missing closing fence"
    payload = "\n".join(lines[1:end_index])
    try:
        parsed = yaml.safe_load(payload)
    except yaml.YAMLError:
        return None, "frontmatter is not valid YAML"
    if not isinstance(parsed, Mapping):
        return None, "frontmatter is not a mapping"
    return parsed, None


def _has_nonempty_string(mapping: Mapping[str, Any], key: str) -> bool:
    value = mapping.get(key)
    return isinstance(value, str) and bool(value)


def plugin_manifest(context: CheckContext) -> dict[str, Any]:
    """Evaluate ``.claude-plugin/plugin.json`` presence and shape."""
    files = _files(context)
    if files is None:
        return _evidence_gap("contents unavailable")

    if PLUGIN_MANIFEST_PATH not in files:
        return _result(
            "fail",
            f"{PLUGIN_MANIFEST_PATH} not declared in repository",
            paths=(PLUGIN_MANIFEST_PATH,),
            refs=(F0_FILES_REF,),
        )

    content = _file_content(context, PLUGIN_MANIFEST_PATH)
    if content is None:
        return _evidence_gap(
            f"{PLUGIN_MANIFEST_PATH} content unavailable",
            paths=(PLUGIN_MANIFEST_PATH,),
        )

    try:
        manifest = json.loads(content)
    except json.JSONDecodeError:
        return _result(
            "fail",
            f"{PLUGIN_MANIFEST_PATH} is not valid JSON",
            paths=(PLUGIN_MANIFEST_PATH,),
            refs=(F0_FILES_REF,),
        )
    if not isinstance(manifest, Mapping):
        return _result(
            "fail",
            f"{PLUGIN_MANIFEST_PATH} root is not a mapping",
            paths=(PLUGIN_MANIFEST_PATH,),
            refs=(F0_FILES_REF,),
        )
    if not _has_nonempty_string(manifest, "name"):
        return _result(
            "fail",
            f"{PLUGIN_MANIFEST_PATH} missing non-empty string 'name'",
            paths=(PLUGIN_MANIFEST_PATH,),
            refs=(F0_FILES_REF,),
        )
    if not _has_nonempty_string(manifest, "version"):
        return _result(
            "fail",
            f"{PLUGIN_MANIFEST_PATH} missing non-empty string 'version'",
            paths=(PLUGIN_MANIFEST_PATH,),
            refs=(F0_FILES_REF,),
        )
    name = manifest["name"]
    version = manifest["version"]
    return _result(
        "pass",
        f"manifest declares {name} {version}",
        paths=(PLUGIN_MANIFEST_PATH,),
        refs=(F0_FILES_REF,),
    )


def skills(context: CheckContext) -> dict[str, Any]:
    """Evaluate every ``skills/*/SKILL.md`` against the frontmatter contract."""
    files = _files(context)
    if files is None:
        return _evidence_gap("contents unavailable")

    skill_paths = _skill_paths(files)
    if not skill_paths:
        return _result(
            "fail",
            "no skills/*/SKILL.md declared in repository",
            paths=(),
            refs=(F0_FILES_REF,),
        )

    for path in skill_paths:
        content = _file_content(context, path)
        if content is None:
            return _evidence_gap(
                f"{path} content unavailable",
                paths=(path,),
            )
        frontmatter, error = _parse_frontmatter(content)
        if error is not None:
            return _result(
                "fail",
                f"{path} has {error}",
                paths=(path,),
                refs=(F0_FILES_REF,),
            )
        if not _has_nonempty_string(frontmatter, "name"):
            return _result(
                "fail",
                f"{path} missing non-empty string 'name'",
                paths=(path,),
                refs=(F0_FILES_REF,),
            )
        if not _has_nonempty_string(frontmatter, "description"):
            return _result(
                "fail",
                f"{path} missing non-empty string 'description'",
                paths=(path,),
                refs=(F0_FILES_REF,),
            )

    return _result(
        "pass",
        f"{len(skill_paths)} skill(s) with valid frontmatter",
        paths=tuple(skill_paths),
        refs=(F0_FILES_REF,),
    )


def context(context: CheckContext) -> dict[str, Any]:  # noqa: A002
    """Audit ``CLAUDE.md`` for claim currency.

    The audit runs in four stages, each one early-returning on the
    smallest decisive signal:

    1. **Evidence gate** — without ``files`` or ``file_contents`` there
       is nothing to grade, so the adapter reports an evidence gap.
    2. **Inference-status gate** — only ``evidence['inference_status']
       == "ran"`` may yield ``pass``/``fail``. ``skipped``, ``failed``,
       or an absent status force ``unknown`` so a headless run that never
       extracts claims cannot silently pass over stale docs.
    3. **Inference payload guard** — when an external agent has supplied
       candidate findings under ``evidence['inferred_claims']``, they
       must pass :func:`repo_claims.validate_inferred_findings` or the
       whole audit downgrades to ``unknown`` (we never synthesize a
       pass/fail from malformed input).
    4. **Deterministic check** — the textual claims in ``CLAUDE.md`` are
       cross-referenced against :func:`repo_claims.facts` (the
       repository's current ground truth). Findings from the
       deterministic pass and the (validated) inferred pass are merged
       and graded together.
    """
    files = _files(context)
    if files is None:
        return _evidence_gap("contents unavailable")

    if CLAUDE_CONTEXT_PATH not in files:
        return _result(
            "fail",
            "CLAUDE.md absent",
            paths=(CLAUDE_CONTEXT_PATH,),
            refs=(F0_FILES_REF,),
        )

    text = _file_content(context, CLAUDE_CONTEXT_PATH)
    if text is None:
        return _evidence_gap(
            "CLAUDE.md content unavailable",
            paths=(CLAUDE_CONTEXT_PATH,),
        )

    # Inference-status gate: only a completed inference step may yield
    # pass/fail. Absent status is treated as skipped so a headless run that
    # never extracts claims cannot silently pass over stale docs.
    inference_status = context.evidence.get("inference_status")
    if inference_status != "ran":
        if inference_status in {"skipped", "failed"}:
            label = inference_status
        elif inference_status is None:
            label = "skipped"
        else:
            label = f"invalid ({inference_status!r})"
        return _result(
            "unknown",
            f"claude.context inference step {label}; "
            "only inference_status=ran may yield pass/fail",
            paths=(CLAUDE_CONTEXT_PATH,),
            refs=(F0_FILES_REF,),
        )

    raw_inferred = context.evidence.get("inferred_claims")
    if raw_inferred is not None:
        try:
            inferred = repo_claims.validate_inferred_findings(raw_inferred)
        except repo_claims.InferenceValidationError as exc:
            return _result(
                "unknown",
                f"inferred claim validation failed: {exc}",
                paths=(CLAUDE_CONTEXT_PATH,),
                refs=(F0_FILES_REF,),
            )
    else:
        inferred = []

    facts = repo_claims.facts(context.evidence)
    deterministic = repo_claims.check_claims(text, facts)
    # Dedupe across the two sources by (kind, subject); a deterministic finding
    # wins over an inferred one for the same claim (it carries direct evidence),
    # so one underlying problem is never double-counted in the grade or citation.
    by_key: dict[tuple[str, str], Any] = {}
    for finding in (*inferred, *deterministic):
        by_key[(finding.kind, finding.subject)] = finding
    merged = sorted(
        by_key.values(),
        key=lambda finding: (finding.kind, finding.subject),
    )

    stale_count = sum(
        1
        for finding in merged
        if finding.kind in {"missing_claimed_skill", "stale_command"}
    )
    unsupported_count = sum(
        1 for finding in merged if finding.kind == "unsupported_evidence"
    )

    if stale_count:
        detail = f"{stale_count} stale CLAUDE.md claim(s)"
        status = "fail"
    else:
        detail = "CLAUDE.md claims current"
        if unsupported_count:
            detail += f"; {unsupported_count} unsupported claim(s) surfaced"
        status = "pass"

    cited_paths = (CLAUDE_CONTEXT_PATH,) + tuple(
        sorted(
            finding.subject
            for finding in merged
            if "/" in finding.subject
        )
    )
    result = _result(
        status,
        detail,
        paths=cited_paths,
        refs=(F0_FILES_REF,),
    )
    result["data"]["claim_findings"] = [
        dataclasses.asdict(finding) for finding in merged
    ]
    return result
