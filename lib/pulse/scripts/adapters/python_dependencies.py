"""Parse Python dependency managers (uv, Poetry, PDM, pip-tools, Conda's nested
pip: section) from materialized dependency evidence into one typed
`DependencyRepoEvaluation` per (repo, "python") — exactly once, before any
dispatch or dismissal logic runs.

See lib/patterns/dependency-coherence.md and docs/superpowers/plans/
2026-07-13-f4-dependency-adapters.md for the full evidence-state lattice and
Poetry constraint-conversion algorithm this module implements exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from lib.pulse.scripts.check_adapters import CheckContext
from lib.pulse.scripts.dependencies import (
    ArtifactProvenance,
    DeclaredRequirement,
    DependencyRepoEvaluation,
    LocalFinding,
    PackageRecord,
    normalize_python_name,
    project_evaluation,
    reduce_local_status,
)
from lib.pulse.scripts.dependency_evidence import RepoEvidence


@dataclass(frozen=True)
class AdapterDetection:
    state: Literal["applicable", "not_applicable", "unsupported", "unknown", "error"]
    manager: str | None
    reason_code: str | None  # bounded enum-like string; never interpolates raw content
    source_files: tuple[str, ...]


_UNRESOLVED_ARTIFACT_STATES = {"unresolved", "too_large", "binary", "error"}

_LOCK_SELECTORS: dict[str, str] = {
    "uv": "uv.lock",
    "poetry": "poetry.lock",
    "pdm": "pdm.lock",
}


# --- workspace / capability detection ----------------------------------------


def _toml_loads(text: str) -> dict[str, Any] | None:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def _yaml_loads(text: str) -> Any | None:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _has_uv_workspace_table(data: dict[str, Any]) -> bool:
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return False
    uv = tool.get("uv")
    if not isinstance(uv, dict):
        return False
    return isinstance(uv.get("workspace"), dict)


def detect_python(
    repo: str, evidence: RepoEvidence, *, capability: bool
) -> AdapterDetection:
    if not capability:
        return AdapterDetection(
            state="not_applicable", manager=None, reason_code=None, source_files=()
        )

    pyproject = evidence.by_path("pyproject.toml")
    if pyproject is not None and pyproject.state == "found":
        data = _toml_loads(pyproject.content or "")
        if data is not None and _has_uv_workspace_table(data):
            return AdapterDetection(
                state="unsupported",
                manager=None,
                reason_code="workspace_repository",
                source_files=("pyproject.toml",),
            )
    elif pyproject is not None and pyproject.state in _UNRESOLVED_ARTIFACT_STATES:
        return AdapterDetection(
            state="unknown",
            manager=None,
            reason_code="workspace_sentinel_unresolved",
            source_files=("pyproject.toml",),
        )

    manager, source_files, ambiguous = _identify_manager(evidence)
    if ambiguous:
        return AdapterDetection(
            state="unsupported",
            manager=None,
            reason_code="ambiguous_manager",
            source_files=source_files,
        )
    if manager is None:
        # Distinguish a genuine evidence gap (a candidate file's state couldn't
        # be resolved) from true absence (no manager evidence at all).
        if _has_unresolved_candidate(evidence):
            return AdapterDetection(
                state="unknown", manager=None, reason_code="evidence_gap", source_files=()
            )
        return AdapterDetection(
            state="unknown", manager=None, reason_code="no_manager_evidence", source_files=()
        )
    return AdapterDetection(
        state="applicable", manager=manager, reason_code=None, source_files=source_files
    )


def _has_unresolved_candidate(evidence: RepoEvidence) -> bool:
    candidate_paths = {
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
        "pdm.lock",
        "environment.yml",
    }
    for artifact in evidence.artifacts:
        if artifact.path in candidate_paths and artifact.state in _UNRESOLVED_ARTIFACT_STATES:
            return True
        if artifact.selector_id in ("python.pip_tools_in", "python.pip_tools_txt"):
            if artifact.state in _UNRESOLVED_ARTIFACT_STATES:
                return True
    return False


def _manifest_declared_manager(evidence: RepoEvidence) -> str | None:
    """The manager implied by pyproject.toml's own tool sections — identifiable
    even when the manager's lock is absent (the "missing_lock" row needs this).
    None when pyproject.toml is absent/unparseable/declares neither a
    recognized [tool.*] manager section nor a PEP 621 [project] table."""
    pyproject = evidence.by_path("pyproject.toml")
    if pyproject is None or pyproject.state != "found":
        return None
    data = _toml_loads(pyproject.content or "")
    if data is None:
        return None
    tool = data.get("tool")
    tool = tool if isinstance(tool, dict) else {}
    if isinstance(tool.get("poetry"), dict):
        return "poetry"
    if isinstance(tool.get("pdm"), dict):
        return "pdm"
    if isinstance(data.get("project"), dict):
        return "uv"  # Global Constraints: v1 pairs PEP 621 with uv.lock
    return None


def _identify_manager(
    evidence: RepoEvidence,
) -> tuple[str | None, tuple[str, ...], bool]:
    """Returns (manager, source_files, ambiguous). manager is None when no
    recognized manager is present; ambiguous is True when more than one
    recognized-but-conflicting manager's lock is present."""
    found_locks = [
        manager
        for manager, filename in _LOCK_SELECTORS.items()
        if (artifact := evidence.by_path(filename)) is not None and artifact.state == "found"
    ]
    if len(found_locks) > 1:
        files = tuple(sorted(_LOCK_SELECTORS[m] for m in found_locks))
        return None, files, True

    manifest_manager = _manifest_declared_manager(evidence)
    if manifest_manager is not None:
        return manifest_manager, ("pyproject.toml", _LOCK_SELECTORS[manifest_manager]), False
    if len(found_locks) == 1:
        manager = found_locks[0]
        return manager, ("pyproject.toml", _LOCK_SELECTORS[manager]), False

    in_files = evidence.by_selector("python.pip_tools_in")
    txt_files = evidence.by_selector("python.pip_tools_txt")
    in_found = tuple(a.path for a in in_files if a.state == "found" and a.path)
    txt_found = tuple(a.path for a in txt_files if a.state == "found" and a.path)
    if in_found or txt_found:
        return "pip-tools", tuple(sorted(in_found + txt_found)), False

    env = evidence.by_path("environment.yml")
    if env is not None and env.state == "found":
        return "conda", ("environment.yml",), False

    return None, (), False


# --- PEP 508-ish requirement string parsing ----------------------------------

_REQ_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\s*\[[^\]]*\])?"
    r"\s*(?P<rest>.*)$"
)


def _parse_requirement_string(raw: str) -> tuple[str | None, str | None, str | None]:
    """Returns (name, manifest_range, unresolved_reason) for one PEP 508-ish
    requirement line/string. name is None only for unparseable garbage."""
    raw = raw.strip()
    if not raw:
        return None, None, None
    if ";" in raw:
        raw = raw.split(";", 1)[0].strip()
    match = _REQ_RE.match(raw)
    if not match:
        return None, None, None
    name = match.group("name")
    rest = match.group("rest").strip()
    if not rest:
        return name, None, None
    if rest.startswith("@") or rest.startswith("(") or "://" in rest:
        return name, None, "non_range_spec"
    try:
        SpecifierSet(rest)
    except InvalidSpecifier:
        return name, None, "non_range_spec"
    return name, rest, None


# --- Poetry constraint conversion --------------------------------------------

_PEP440_OPS = ("~=", "==", ">=", "<=", "!=", ">", "<")
_EXACT_VERSION_RE = re.compile(r"\d+(\.\d+)*")
_WILDCARD_RE = re.compile(r"\d+(\.\d+)*\.\*")


def _split_int_components(version: str) -> list[int] | None:
    try:
        return [int(part) for part in version.split(".")]
    except ValueError:
        return None


def _convert_caret(version: str) -> str | None:
    parts = _split_int_components(version)
    if not parts:
        return None
    lower_parts = parts + [0] * (3 - len(parts)) if len(parts) < 3 else parts
    lower = ".".join(str(p) for p in lower_parts)
    idx = next((i for i, p in enumerate(parts) if p != 0), None)
    upper_parts = list(parts)
    if idx is None:
        upper_parts[-1] += 1
    else:
        upper_parts = upper_parts[: idx + 1]
        upper_parts[idx] += 1
    upper = ".".join(str(p) for p in upper_parts)
    return f">={lower},<{upper}"


def _convert_tilde(version: str) -> str | None:
    parts = _split_int_components(version)
    if not parts:
        return None
    if len(parts) == 1:
        return _convert_caret(version)
    lower_parts = parts + [0] * (3 - len(parts)) if len(parts) < 3 else parts
    lower = ".".join(str(p) for p in lower_parts)
    upper_parts = list(parts[:2])
    upper_parts[1] += 1
    upper = ".".join(str(p) for p in upper_parts)
    return f">={lower},<{upper}"


def _poetry_convert_single(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    if raw == "*":
        return ""
    if "," in raw:
        branches = [p.strip() for p in raw.split(",")]
        converted = []
        for branch in branches:
            result = _poetry_convert_single(branch)
            if result is None:
                return None
            converted.append(result)
        return ",".join(c for c in converted if c)
    for op in _PEP440_OPS:
        if raw.startswith(op):
            return raw
    if raw.startswith("^"):
        return _convert_caret(raw[1:])
    if raw.startswith("~"):
        return _convert_tilde(raw[1:])
    if _WILDCARD_RE.fullmatch(raw):
        return f"=={raw}"
    if _EXACT_VERSION_RE.fullmatch(raw):
        return f"=={raw}"
    return None


def convert_poetry_constraint(raw: str) -> tuple[str, ...] | None:
    """Convert a full Poetry version constraint into a tuple of PEP 440
    SpecifierSet-string branches (OR'd together — a version satisfies the
    declaration if it satisfies ANY branch). Returns None (non_range_spec) if
    the constraint syntax is unrecognized."""
    raw = raw.strip()
    if not raw:
        return None
    branches = re.split(r"\s*\|\|?\s*", raw)
    converted: list[str] = []
    for branch in branches:
        result = _poetry_convert_single(branch)
        if result is None:
            return None
        converted.append(result)
    return tuple(converted)


def _satisfies_poetry_branches(branches: tuple[str, ...], locked_version: str) -> bool:
    for branch in branches:
        try:
            if SpecifierSet(branch).contains(locked_version, prereleases=True):
                return True
        except InvalidSpecifier:
            continue
    return False


# --- lock parsing (shared TOML [[package]] shape: uv/poetry/pdm) ------------


def _collect_lock_versions(data: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for pkg in data.get("package", []) or []:
        if not isinstance(pkg, dict):
            continue
        name = pkg.get("name")
        version = pkg.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            continue
        result.setdefault(normalize_python_name(name), []).append(version)
    return result


def _build_records_from_lock(
    repo: str,
    manifest_path: str,
    lock_path: str,
    manifest_blob_sha: str | None,
    lock_blob_sha: str | None,
    manager: str,
    tree_sha: str | None,
    lock_versions: dict[str, list[str]],
    manifest_ranges: dict[str, str | None],
) -> tuple[PackageRecord, ...]:
    records: list[PackageRecord] = []
    provenance = (
        ArtifactProvenance(role="manifest", path=manifest_path, blob_sha=manifest_blob_sha),
        ArtifactProvenance(role="lock", path=lock_path, blob_sha=lock_blob_sha),
    )
    for name, versions in sorted(lock_versions.items()):
        unique_versions = sorted(set(versions))
        manifest_range = manifest_ranges.get(name)
        if len(unique_versions) > 1:
            records.append(
                PackageRecord(
                    repo=repo,
                    ecosystem="python",
                    name=name,
                    resolution="multiple",
                    manifest_range=None,
                    locked_version=None,
                    unresolved_reason="multiple_resolutions",
                    manager=manager,
                    manifest_path=None,
                    lock_path=None,
                    tree_sha=tree_sha,
                    provenance=provenance,
                )
            )
            continue
        try:
            Version(unique_versions[0])
        except InvalidVersion:
            records.append(
                PackageRecord(
                    repo=repo,
                    ecosystem="python",
                    name=name,
                    resolution="single",
                    manifest_range=None,
                    locked_version=None,
                    unresolved_reason="unparseable_version",
                    manager=manager,
                    manifest_path=None,
                    lock_path=None,
                    tree_sha=tree_sha,
                    provenance=provenance,
                )
            )
            continue
        records.append(
            PackageRecord(
                repo=repo,
                ecosystem="python",
                name=name,
                resolution="single",
                manifest_range=manifest_range,
                locked_version=unique_versions[0],
                unresolved_reason=None,
                manager=manager,
                manifest_path=manifest_path,
                lock_path=lock_path,
                tree_sha=tree_sha,
                provenance=provenance,
            )
        )
    return tuple(records)


# --- per-manager declaration extraction --------------------------------------


def _pep621_declarations(data: dict[str, Any], manifest_path: str) -> list[DeclaredRequirement]:
    declarations: list[DeclaredRequirement] = []
    project = data.get("project")
    if isinstance(project, dict):
        for raw in project.get("dependencies", []) or []:
            if not isinstance(raw, str):
                continue
            name, manifest_range, reason = _parse_requirement_string(raw)
            if name is None:
                continue
            declarations.append(
                DeclaredRequirement(
                    name=normalize_python_name(name),
                    manifest_path=manifest_path,
                    manifest_range=manifest_range,
                    unresolved_reason=reason,
                    group="main",
                )
            )
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for reqs in optional.values():
                for raw in reqs or []:
                    if not isinstance(raw, str):
                        continue
                    name, manifest_range, reason = _parse_requirement_string(raw)
                    if name is None:
                        continue
                    declarations.append(
                        DeclaredRequirement(
                            name=normalize_python_name(name),
                            manifest_path=manifest_path,
                            manifest_range=manifest_range,
                            unresolved_reason=reason,
                            group="optional",
                        )
                    )
    dependency_groups = data.get("dependency-groups")
    if isinstance(dependency_groups, dict):
        for reqs in dependency_groups.values():
            for raw in reqs or []:
                if not isinstance(raw, str):
                    continue
                name, manifest_range, reason = _parse_requirement_string(raw)
                if name is None:
                    continue
                declarations.append(
                    DeclaredRequirement(
                        name=normalize_python_name(name),
                        manifest_path=manifest_path,
                        manifest_range=manifest_range,
                        unresolved_reason=reason,
                        group="dev",
                    )
                )
    tool = data.get("tool")
    if isinstance(tool, dict):
        pdm = tool.get("pdm")
        if isinstance(pdm, dict):
            dev_deps = pdm.get("dev-dependencies")
            if isinstance(dev_deps, dict):
                for reqs in dev_deps.values():
                    for raw in reqs or []:
                        if not isinstance(raw, str):
                            continue
                        name, manifest_range, reason = _parse_requirement_string(raw)
                        if name is None:
                            continue
                        declarations.append(
                            DeclaredRequirement(
                                name=normalize_python_name(name),
                                manifest_path=manifest_path,
                                manifest_range=manifest_range,
                                unresolved_reason=reason,
                                group="dev",
                            )
                        )
    return declarations


def _poetry_dependency_value_to_range(value: Any) -> tuple[str | None, str | None]:
    """Returns (manifest_range_for_projection, unresolved_reason)."""
    if isinstance(value, str):
        branches = convert_poetry_constraint(value)
        if branches is None:
            return None, "non_range_spec"
        return value, None
    # table-form dependency (git/path/url/etc.) — never a version range.
    return None, "non_range_spec"


def _poetry_declarations(data: dict[str, Any], manifest_path: str) -> list[DeclaredRequirement]:
    declarations: list[DeclaredRequirement] = []
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return declarations
    poetry = tool.get("poetry")
    if not isinstance(poetry, dict):
        return declarations

    def _collect(table: Any, group: Literal["main", "dev", "optional"]) -> None:
        if not isinstance(table, dict):
            return
        for name, value in table.items():
            if name == "python":
                continue
            manifest_range, reason = _poetry_dependency_value_to_range(value)
            declarations.append(
                DeclaredRequirement(
                    name=normalize_python_name(name),
                    manifest_path=manifest_path,
                    manifest_range=manifest_range,
                    unresolved_reason=reason,
                    group=group,
                )
            )

    _collect(poetry.get("dependencies"), "main")
    group_table = poetry.get("group")
    if isinstance(group_table, dict):
        for group_data in group_table.values():
            if isinstance(group_data, dict):
                _collect(group_data.get("dependencies"), "dev")

    return declarations


def _pip_tools_in_declarations(text: str, manifest_path: str) -> list[DeclaredRequirement]:
    declarations: list[DeclaredRequirement] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        name, manifest_range, reason = _parse_requirement_string(stripped)
        if name is None:
            continue
        declarations.append(
            DeclaredRequirement(
                name=normalize_python_name(name),
                manifest_path=manifest_path,
                manifest_range=manifest_range,
                unresolved_reason=reason,
                group="main",
            )
        )
    return declarations


_PIP_COMPILED_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;#]+)")


def _pip_tools_txt_pins(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in text.splitlines():
        match = _PIP_COMPILED_RE.match(line)
        if not match:
            continue
        name, version = match.group(1), match.group(2)
        pins[normalize_python_name(name)] = version
    return pins


# --- per-manager parsing ------------------------------------------------------


def _range_local_findings(
    declarations: list[DeclaredRequirement],
    records: tuple[PackageRecord, ...],
    *,
    is_poetry: bool = False,
) -> list[LocalFinding]:
    """One LocalFinding per package with at least one declaration, fail if ANY
    range-checkable declaration is violated; unknown/non_range_spec when the
    package resolved but every one of its declarations is non-range-spec —
    never silently dropped. Poetry constraints are converted fresh per
    declaration (never cached by package name — a package declared twice
    with two different constraints must check each against its own range)."""
    records_by_name = {r.name: r for r in records}
    declarations_by_name: dict[str, list[DeclaredRequirement]] = {}
    for d in declarations:
        declarations_by_name.setdefault(d.name, []).append(d)

    findings: list[LocalFinding] = []
    for name, decls in sorted(declarations_by_name.items()):
        record = records_by_name.get(name)
        if record is None or record.resolution != "single" or record.locked_version is None:
            continue  # nothing resolved to check against — no independent verdict here
        violated = False
        checked_any = False
        for decl in decls:
            if decl.unresolved_reason is not None or decl.manifest_range is None:
                continue
            if is_poetry:
                branches = convert_poetry_constraint(decl.manifest_range)
                if branches is None:
                    continue
                checked_any = True
                if not _satisfies_poetry_branches(branches, record.locked_version):
                    violated = True
                    break
            else:
                try:
                    ok = SpecifierSet(decl.manifest_range).contains(
                        record.locked_version, prereleases=True
                    )
                except InvalidSpecifier:
                    continue
                checked_any = True
                if not ok:
                    violated = True
                    break
        if not checked_any:
            findings.append(
                LocalFinding(name=name, status="unknown", reason_code="non_range_spec")
            )
            continue
        findings.append(
            LocalFinding(
                name=name,
                status="fail" if violated else "pass",
                reason_code="range_violation" if violated else "satisfied",
            )
        )
    return findings


def _finalize(
    repo: str,
    ecosystem: Literal["python"],
    detection: AdapterDetection,
    declarations: list[DeclaredRequirement],
    records: tuple[PackageRecord, ...],
    local_findings: list[LocalFinding],
    *,
    partial_unsupported: int = 0,
    force_status: tuple[str, str | None] | None = None,
) -> DependencyRepoEvaluation:
    has_multiple_resolutions = any(r.resolution == "multiple" for r in records)
    has_unparseable_version = any(r.unresolved_reason == "unparseable_version" for r in records)
    has_unresolved_record = has_multiple_resolutions or has_unparseable_version
    if force_status is not None:
        status, reason = force_status
    else:
        status, reason = reduce_local_status(local_findings)
        if status == "pass" and has_unresolved_record:
            status = "unknown"
            reason = (
                "multiple_resolutions" if has_multiple_resolutions else "unparseable_version"
            )
    coverage_state = "incomplete" if (has_unresolved_record or force_status is not None) else "complete"
    return DependencyRepoEvaluation(
        repo=repo,
        ecosystem=ecosystem,
        detection=detection,
        declarations=tuple(declarations),
        records=records,
        local_findings=tuple(local_findings),
        local_status=status,
        local_reason_code=reason,
        coverage_state=coverage_state,
        partial_unsupported=partial_unsupported,
    )


def _evidence_gap_evaluation(repo: str, reason_code: str) -> DependencyRepoEvaluation:
    return DependencyRepoEvaluation(
        repo=repo,
        ecosystem="python",
        detection=AdapterDetection(
            state="unknown", manager=None, reason_code=reason_code, source_files=()
        ),
        declarations=(),
        records=(),
        local_findings=(),
        local_status="unknown",
        local_reason_code=reason_code,
        coverage_state="incomplete",
        partial_unsupported=0,
    )


def _not_applicable_evaluation(repo: str) -> DependencyRepoEvaluation:
    return DependencyRepoEvaluation(
        repo=repo,
        ecosystem="python",
        detection=AdapterDetection(
            state="not_applicable", manager=None, reason_code=None, source_files=()
        ),
        declarations=(),
        records=(),
        local_findings=(),
        local_status="not_applicable",
        local_reason_code=None,
        coverage_state="complete",
        partial_unsupported=0,
    )


def _unsupported_evaluation(
    repo: str, reason_code: str, source_files: tuple[str, ...]
) -> DependencyRepoEvaluation:
    return DependencyRepoEvaluation(
        repo=repo,
        ecosystem="python",
        detection=AdapterDetection(
            state="unsupported", manager=None, reason_code=reason_code, source_files=source_files
        ),
        declarations=(),
        records=(),
        local_findings=(),
        local_status="unsupported",
        local_reason_code=reason_code,
        coverage_state="complete",
        partial_unsupported=0,
    )


def _parse_uv_pdm(
    repo: str, evidence: RepoEvidence, manager: str, lock_filename: str
) -> DependencyRepoEvaluation:
    pyproject = evidence.by_path("pyproject.toml")
    lock = evidence.by_path(lock_filename)
    detection = AdapterDetection(
        state="applicable",
        manager=manager,
        reason_code=None,
        source_files=("pyproject.toml", lock_filename),
    )
    if pyproject is None or pyproject.state != "found":
        return _evidence_gap_evaluation(repo, "evidence_gap")
    if lock is None or lock.state == "absent":
        data = _toml_loads(pyproject.content or "")
        declarations = _pep621_declarations(data, "pyproject.toml") if data is not None else []
        return _finalize(
            repo,
            "python",
            detection,
            declarations,
            (),
            [],
            force_status=("fail", "missing_lock"),
        )
    if lock.state in _UNRESOLVED_ARTIFACT_STATES:
        return _evidence_gap_evaluation(repo, "evidence_gap")

    manifest_data = _toml_loads(pyproject.content or "")
    lock_data = _toml_loads(lock.content or "")
    if manifest_data is None or lock_data is None:
        return _finalize(
            repo, "python", detection, [], (), [], force_status=("fail", "malformed_source")
        )

    declarations = _pep621_declarations(manifest_data, "pyproject.toml")
    manifest_ranges = {d.name: d.manifest_range for d in declarations if d.unresolved_reason is None}
    lock_versions = _collect_lock_versions(lock_data)
    records = _build_records_from_lock(
        repo,
        "pyproject.toml",
        lock_filename,
        pyproject.blob_sha,
        lock.blob_sha,
        manager,
        evidence.tree_sha,
        lock_versions,
        manifest_ranges,
    )
    findings = _range_local_findings(declarations, records)
    return _finalize(repo, "python", detection, declarations, records, findings)


def _parse_poetry(repo: str, evidence: RepoEvidence) -> DependencyRepoEvaluation:
    pyproject = evidence.by_path("pyproject.toml")
    lock = evidence.by_path("poetry.lock")
    detection = AdapterDetection(
        state="applicable",
        manager="poetry",
        reason_code=None,
        source_files=("pyproject.toml", "poetry.lock"),
    )
    if pyproject is None or pyproject.state != "found":
        return _evidence_gap_evaluation(repo, "evidence_gap")
    if lock is None or lock.state == "absent":
        data = _toml_loads(pyproject.content or "")
        declarations = _poetry_declarations(data, "pyproject.toml") if data is not None else []
        return _finalize(
            repo, "python", detection, declarations, (), [], force_status=("fail", "missing_lock")
        )
    if lock.state in _UNRESOLVED_ARTIFACT_STATES:
        return _evidence_gap_evaluation(repo, "evidence_gap")

    manifest_data = _toml_loads(pyproject.content or "")
    lock_data = _toml_loads(lock.content or "")
    if manifest_data is None or lock_data is None:
        return _finalize(
            repo, "python", detection, [], (), [], force_status=("fail", "malformed_source")
        )

    declarations = _poetry_declarations(manifest_data, "pyproject.toml")
    manifest_ranges = {d.name: d.manifest_range for d in declarations if d.unresolved_reason is None}
    lock_versions = _collect_lock_versions(lock_data)
    records = _build_records_from_lock(
        repo,
        "pyproject.toml",
        "poetry.lock",
        pyproject.blob_sha,
        lock.blob_sha,
        "poetry",
        evidence.tree_sha,
        lock_versions,
        manifest_ranges,
    )
    findings = _range_local_findings(declarations, records, is_poetry=True)
    return _finalize(repo, "python", detection, declarations, records, findings)


def _parse_pip_tools(repo: str, evidence: RepoEvidence) -> DependencyRepoEvaluation:
    in_artifacts = [a for a in evidence.by_selector("python.pip_tools_in") if a.state == "found"]
    txt_artifacts = [a for a in evidence.by_selector("python.pip_tools_txt") if a.state == "found"]

    declarations: list[DeclaredRequirement] = []
    for artifact in in_artifacts:
        declarations.extend(_pip_tools_in_declarations(artifact.content or "", artifact.path))

    # Accumulate EVERY (version, contributing artifact) pair per name across
    # every requirements*.txt artifact — never last-file-wins, so two
    # compiled files pinning different versions of the same package surface
    # as a genuine resolution="multiple", not a silently overwritten pin.
    pins_by_name: dict[str, list[tuple[str, Any]]] = {}
    for artifact in txt_artifacts:
        for name, version in _pip_tools_txt_pins(artifact.content or "").items():
            pins_by_name.setdefault(name, []).append((version, artifact))

    source_files = tuple(
        sorted([a.path for a in in_artifacts] + [a.path for a in txt_artifacts])
    )
    detection = AdapterDetection(
        state="applicable", manager="pip-tools", reason_code=None, source_files=source_files
    )

    if not txt_artifacts:
        # Lockless: a compiled requirements.txt never showed up — no locked
        # version can be proven for anything declared in the .in file(s).
        return _finalize(
            repo,
            "python",
            detection,
            declarations,
            (),
            [],
            force_status=("warn", "unresolved_lockless"),
        )

    manifest_path = in_artifacts[0].path if in_artifacts else txt_artifacts[0].path
    manifest_ranges = {d.name: d.manifest_range for d in declarations if d.unresolved_reason is None}
    if not in_artifacts:
        # A frozen requirements.txt with no source .in: each pin is its own
        # trivially-satisfied declaration (the first resolved version stands
        # in for the declaration text when a name is pinned differently by
        # more than one compiled file).
        for name, entries in sorted(pins_by_name.items()):
            version = sorted({v for v, _artifact in entries})[0]
            declarations.append(
                DeclaredRequirement(
                    name=name,
                    manifest_path=txt_artifacts[0].path,
                    manifest_range=f"=={version}",
                    unresolved_reason=None,
                    group="main",
                )
            )
        manifest_ranges = {d.name: d.manifest_range for d in declarations}

    manifest_provenance = tuple(
        ArtifactProvenance(role="manifest", path=a.path, blob_sha=a.blob_sha)
        for a in sorted(in_artifacts, key=lambda a: a.path)
    ) or (ArtifactProvenance(role="manifest", path=manifest_path, blob_sha=None),)

    records: list[PackageRecord] = []
    for name, entries in sorted(pins_by_name.items()):
        unique_versions = sorted({v for v, _artifact in entries})
        contributing = sorted({a.path: a for _v, a in entries}.values(), key=lambda a: a.path)
        lock_provenance = tuple(
            ArtifactProvenance(role="lock", path=a.path, blob_sha=a.blob_sha) for a in contributing
        )
        provenance = tuple(
            sorted(manifest_provenance + lock_provenance, key=lambda p: (p.role, p.path))
        )
        if len(unique_versions) > 1:
            records.append(
                PackageRecord(
                    repo=repo,
                    ecosystem="python",
                    name=name,
                    resolution="multiple",
                    manifest_range=None,
                    locked_version=None,
                    unresolved_reason="multiple_resolutions",
                    manager="pip-tools",
                    manifest_path=None,
                    lock_path=None,
                    tree_sha=evidence.tree_sha,
                    provenance=provenance,
                )
            )
            continue
        try:
            Version(unique_versions[0])
        except InvalidVersion:
            records.append(
                PackageRecord(
                    repo=repo,
                    ecosystem="python",
                    name=name,
                    resolution="single",
                    manifest_range=None,
                    locked_version=None,
                    unresolved_reason="unparseable_version",
                    manager="pip-tools",
                    manifest_path=None,
                    lock_path=None,
                    tree_sha=evidence.tree_sha,
                    provenance=provenance,
                )
            )
            continue
        records.append(
            PackageRecord(
                repo=repo,
                ecosystem="python",
                name=name,
                resolution="single",
                manifest_range=manifest_ranges.get(name),
                locked_version=unique_versions[0],
                unresolved_reason=None,
                manager="pip-tools",
                manifest_path=manifest_path,
                lock_path=contributing[0].path,
                tree_sha=evidence.tree_sha,
                provenance=provenance,
            )
        )
    findings = _range_local_findings(declarations, tuple(records))
    return _finalize(repo, "python", detection, declarations, tuple(records), findings)


_CONDA_EXACT_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")


def _parse_conda(repo: str, evidence: RepoEvidence) -> DependencyRepoEvaluation:
    env = evidence.by_path("environment.yml")
    detection = AdapterDetection(
        state="applicable", manager="conda", reason_code=None, source_files=("environment.yml",)
    )
    if env is None or env.state != "found":
        return _evidence_gap_evaluation(repo, "evidence_gap")

    data = _yaml_loads(env.content or "")
    if not isinstance(data, dict):
        return _finalize(
            repo, "python", detection, [], (), [], force_status=("fail", "malformed_source")
        )

    declarations: list[DeclaredRequirement] = []
    records: list[PackageRecord] = []
    partial_unsupported = 0

    for entry in data.get("dependencies", []) or []:
        if isinstance(entry, str):
            # native Conda channel/build-qualified spec — never force-mapped
            # into the python namespace. The interpreter pin itself ("python"
            # or "python=3.10") is not a package dependency.
            bare_name = re.split(r"[=<>!~ ]", entry.strip(), maxsplit=1)[0]
            if bare_name != "python":
                partial_unsupported += 1
            continue
        if isinstance(entry, dict) and "pip" in entry:
            for raw in entry.get("pip") or []:
                if not isinstance(raw, str):
                    continue
                match = _CONDA_EXACT_PIN_RE.match(raw.strip())
                if match:
                    name, version = normalize_python_name(match.group(1)), match.group(2)
                    declarations.append(
                        DeclaredRequirement(
                            name=name,
                            manifest_path="environment.yml",
                            manifest_range=f"=={version}",
                            unresolved_reason=None,
                            group="main",
                        )
                    )
                    records.append(
                        PackageRecord(
                            repo=repo,
                            ecosystem="python",
                            name=name,
                            resolution="single",
                            manifest_range=f"=={version}",
                            locked_version=version,
                            unresolved_reason=None,
                            manager="conda",
                            manifest_path="environment.yml",
                            lock_path=None,
                            tree_sha=evidence.tree_sha,
                            provenance=(
                                ArtifactProvenance(
                                    role="manifest", path="environment.yml", blob_sha=env.blob_sha
                                ),
                            ),
                        )
                    )
                    continue
                name, manifest_range, reason = _parse_requirement_string(raw)
                if name is None:
                    continue
                declarations.append(
                    DeclaredRequirement(
                        name=normalize_python_name(name),
                        manifest_path="environment.yml",
                        manifest_range=manifest_range,
                        unresolved_reason=reason,
                        group="main",
                    )
                )

    findings = _range_local_findings(declarations, tuple(records))
    return _finalize(
        repo,
        "python",
        detection,
        declarations,
        tuple(records),
        findings,
        partial_unsupported=partial_unsupported,
    )


# --- public entry points -------------------------------------------------------


def parse_python(
    repo: str, evidence: RepoEvidence, *, capability: bool
) -> DependencyRepoEvaluation:
    if not capability:
        return _not_applicable_evaluation(repo)

    pyproject = evidence.by_path("pyproject.toml")
    if pyproject is not None and pyproject.state == "found":
        data = _toml_loads(pyproject.content or "")
        if data is not None and _has_uv_workspace_table(data):
            return _unsupported_evaluation(repo, "workspace_repository", ("pyproject.toml",))
    elif pyproject is not None and pyproject.state in _UNRESOLVED_ARTIFACT_STATES:
        return _evidence_gap_evaluation(repo, "workspace_sentinel_unresolved")

    manager, source_files, ambiguous = _identify_manager(evidence)
    if ambiguous:
        return _unsupported_evaluation(repo, "ambiguous_manager", source_files)
    if manager is None:
        if _has_unresolved_candidate(evidence):
            return _evidence_gap_evaluation(repo, "evidence_gap")
        return _evidence_gap_evaluation(repo, "no_manager_evidence")

    if manager in ("uv", "pdm"):
        return _parse_uv_pdm(repo, evidence, manager, _LOCK_SELECTORS[manager])
    if manager == "poetry":
        return _parse_poetry(repo, evidence)
    if manager == "pip-tools":
        return _parse_pip_tools(repo, evidence)
    if manager == "conda":
        return _parse_conda(repo, evidence)
    raise AssertionError(f"unreachable manager: {manager!r}")  # pragma: no cover


def evaluate_python(context: CheckContext) -> dict[str, Any]:
    evaluation = context.evidence["dependency_evaluations"]["python"]
    projected = project_evaluation(evaluation)
    detail = f"{evaluation.local_status}"
    if evaluation.local_reason_code:
        detail = f"{evaluation.local_status}: {evaluation.local_reason_code}"
    return {
        "status": evaluation.local_status,
        "detail": detail,
        "data": {
            **projected,
            "coverage_state": evaluation.coverage_state,
            "partial_unsupported": evaluation.partial_unsupported,
            "evidence": {"paths": [], "refs": []},
        },
    }
