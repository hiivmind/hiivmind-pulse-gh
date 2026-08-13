"""Parse Node dependency managers (npm, pnpm, Yarn v1) from materialized
dependency evidence into one typed `DependencyRepoEvaluation` per
(repo, "node") — exactly once, before any dispatch or dismissal logic runs.

Mirrors lib/pulse/scripts/adapters/python_dependencies.py's evidence-state
lattice, range-check semantics, and precedence-ordered status reduction.
`PackageRecord.ecosystem` is always the package-namespace literal "npm" here,
regardless of which manager (npm/pnpm/yarn1) resolved it — see the Global
Constraints literal-domain note in lib/patterns/dependency-coherence.md.
"""

from __future__ import annotations

import json
from typing import Any

import yaml
from semantic_version import NpmSpec
from semantic_version import Version as SemVersion

from lib.pulse.scripts.adapters.python_dependencies import AdapterDetection
from lib.pulse.scripts.check_adapters import CheckContext
from lib.pulse.scripts.dependencies import (
    ArtifactProvenance,
    DeclaredRequirement,
    DependencyRepoEvaluation,
    LocalFinding,
    PackageRecord,
    normalize_npm_name,
    project_evaluation,
    reduce_local_status,
)
from lib.pulse.scripts.dependency_evidence import RepoEvidence


_UNRESOLVED_ARTIFACT_STATES = {"unresolved", "too_large", "binary", "error"}

_LOCK_FILES: dict[str, str] = {
    "npm": "package-lock.json",
    "pnpm": "pnpm-lock.yaml",
    "yarn1": "yarn.lock",
}


# --- JSON/YAML loading --------------------------------------------------------


def _json_loads(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _yaml_loads(text: str) -> Any | None:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _has_workspaces_key(package_json: dict[str, Any]) -> bool:
    value = package_json.get("workspaces")
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value.get("packages"))
    return False


# --- workspace / manager detection --------------------------------------------


def _found_locks(evidence: RepoEvidence) -> list[str]:
    return [
        manager
        for manager, filename in _LOCK_FILES.items()
        if (artifact := evidence.by_path(filename)) is not None and artifact.state == "found"
    ]


def _is_yarn_v1_lockfile(text: str) -> bool:
    return "yarn lockfile v1" in text


def _has_unresolved_candidate(evidence: RepoEvidence) -> bool:
    candidate_paths = set(_LOCK_FILES.values()) | {"package.json"}
    for artifact in evidence.artifacts:
        if artifact.path in candidate_paths and artifact.state in _UNRESOLVED_ARTIFACT_STATES:
            return True
    return False


def detect_node(repo: str, evidence: RepoEvidence, *, capability: bool) -> AdapterDetection:
    if not capability:
        return AdapterDetection(
            state="not_applicable", manager=None, reason_code=None, source_files=()
        )

    workspace_yaml = evidence.by_path("pnpm-workspace.yaml")
    if workspace_yaml is not None and workspace_yaml.state in _UNRESOLVED_ARTIFACT_STATES:
        return AdapterDetection(
            state="unknown",
            manager=None,
            reason_code="workspace_sentinel_unresolved",
            source_files=("pnpm-workspace.yaml",),
        )
    if workspace_yaml is not None and workspace_yaml.state == "found":
        return AdapterDetection(
            state="unsupported",
            manager=None,
            reason_code="workspace_repository",
            source_files=("pnpm-workspace.yaml",),
        )

    package_json = evidence.by_path("package.json")
    if package_json is not None and package_json.state == "found":
        data = _json_loads(package_json.content or "")
        if isinstance(data, dict) and _has_workspaces_key(data):
            return AdapterDetection(
                state="unsupported",
                manager=None,
                reason_code="workspace_repository",
                source_files=("package.json",),
            )

    manager, source_files, ambiguous, unsupported_yarn = _identify_manager(evidence)
    if ambiguous:
        return AdapterDetection(
            state="unsupported",
            manager=None,
            reason_code="ambiguous_manager",
            source_files=source_files,
        )
    if unsupported_yarn:
        return AdapterDetection(
            state="unsupported",
            manager=None,
            reason_code="unsupported_manager",
            source_files=source_files,
        )
    if manager is None:
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


def _identify_manager(
    evidence: RepoEvidence,
) -> tuple[str | None, tuple[str, ...], bool, bool]:
    """Returns (manager, source_files, ambiguous, unsupported_yarn)."""
    found = _found_locks(evidence)
    if len(found) > 1:
        return None, tuple(sorted(_LOCK_FILES[m] for m in found)), True, False
    if len(found) == 1:
        manager = found[0]
        if manager == "yarn1":
            artifact = evidence.by_path("yarn.lock")
            if not _is_yarn_v1_lockfile(artifact.content or ""):
                return None, ("yarn.lock",), False, True
        return manager, ("package.json", _LOCK_FILES[manager]), False, False

    package_json = evidence.by_path("package.json")
    if package_json is not None and package_json.state == "found":
        # No lock at all — npm is the universal fallback every Node project
        # can generate a lock for.
        return "npm", ("package.json", "package-lock.json"), False, False

    return None, (), False, False


# --- npm range classification --------------------------------------------------

_NON_RANGE_PREFIXES = ("workspace:", "npm:", "git+", "git://", "file:")


def _classify_npm_range(raw: str) -> tuple[str | None, str | None]:
    raw = raw.strip()
    if not raw:
        return None, None
    if raw == "*" or raw.startswith(_NON_RANGE_PREFIXES) or "://" in raw:
        return None, "non_range_spec"
    if raw.endswith(".tgz") or raw.endswith(".tar.gz"):
        return None, "non_range_spec"
    try:
        NpmSpec(raw)
    except ValueError:
        return None, "non_range_spec"
    return raw, None


def _package_json_declarations(
    data: dict[str, Any], manifest_path: str
) -> list[DeclaredRequirement]:
    declarations: list[DeclaredRequirement] = []
    group_keys: tuple[tuple[str, str], ...] = (
        ("dependencies", "main"),
        ("devDependencies", "dev"),
        ("optionalDependencies", "optional"),
    )
    for key, group in group_keys:
        table = data.get(key)
        if not isinstance(table, dict):
            continue
        for name, raw in table.items():
            if not isinstance(name, str) or not isinstance(raw, str):
                continue
            manifest_range, reason = _classify_npm_range(raw)
            declarations.append(
                DeclaredRequirement(
                    name=normalize_npm_name(name),
                    manifest_path=manifest_path,
                    manifest_range=manifest_range,
                    unresolved_reason=reason,
                    group=group,
                )
            )
    return declarations


# --- lock parsing ---------------------------------------------------------------


def _collect_npm_lock_versions(data: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    packages = data.get("packages")
    if isinstance(packages, dict):
        for key, entry in packages.items():
            if not isinstance(entry, dict) or "node_modules/" not in key:
                continue
            version = entry.get("version")
            if not isinstance(version, str):
                continue
            name = key.rsplit("node_modules/", 1)[-1]
            result.setdefault(normalize_npm_name(name), []).append(version)
        return result

    # legacy v1 shape: top-level "dependencies" mapping name -> {version, ...}
    legacy = data.get("dependencies")
    if isinstance(legacy, dict):
        for name, entry in legacy.items():
            if not isinstance(entry, dict):
                continue
            version = entry.get("version")
            if isinstance(version, str):
                result.setdefault(normalize_npm_name(name), []).append(version)
    return result


def _collect_pnpm_lock_versions(data: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    packages = data.get("packages")
    if not isinstance(packages, dict):
        return result
    for key in packages:
        if not isinstance(key, str):
            continue
        rest = key[1:] if key.startswith("/") else key
        # strip a trailing peer-dependency suffix like "(react@18.0.0)"
        paren = rest.find("(")
        if paren != -1:
            rest = rest[:paren]
        if "@" not in rest:
            continue
        name, version = rest.rsplit("@", 1)
        if not name or not version:
            continue
        result.setdefault(normalize_npm_name(name), []).append(version)
    return result


def _collect_yarn1_lock_versions(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    header: list[str] | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            if not line.rstrip().endswith(":"):
                header = None
                continue
            specs = [s.strip().strip('"') for s in line.rstrip()[:-1].split(",")]
            names = set()
            for spec in specs:
                if "@" not in spec:
                    continue
                name = spec.rsplit("@", 1)[0]
                names.add(name)
            header = sorted(names)
            continue
        stripped = line.strip()
        if header and stripped.startswith("version "):
            version = stripped[len("version ") :].strip().strip('"')
            for name in header:
                result.setdefault(normalize_npm_name(name), []).append(version)
            header = None
    return result


def _build_npm_records(
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
        if len(unique_versions) > 1:
            records.append(
                PackageRecord(
                    repo=repo,
                    ecosystem="npm",
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
        records.append(
            PackageRecord(
                repo=repo,
                ecosystem="npm",
                name=name,
                resolution="single",
                manifest_range=manifest_ranges.get(name),
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


def _range_local_findings(
    declarations: list[DeclaredRequirement], records: tuple[PackageRecord, ...]
) -> list[LocalFinding]:
    records_by_name = {r.name: r for r in records}
    declarations_by_name: dict[str, list[DeclaredRequirement]] = {}
    for d in declarations:
        declarations_by_name.setdefault(d.name, []).append(d)

    findings: list[LocalFinding] = []
    for name, decls in sorted(declarations_by_name.items()):
        record = records_by_name.get(name)
        if record is None or record.resolution != "single" or record.locked_version is None:
            continue
        violated = False
        checked_any = False
        for decl in decls:
            if decl.unresolved_reason is not None or decl.manifest_range is None:
                continue
            checked_any = True
            try:
                ok = NpmSpec(decl.manifest_range).match(SemVersion(record.locked_version))
            except ValueError:
                continue
            if not ok:
                violated = True
                break
        if not checked_any:
            continue
        findings.append(
            LocalFinding(
                name=name,
                status="fail" if violated else "pass",
                reason_code="range_violation" if violated else "satisfied",
            )
        )
    return findings


# --- reduction / evaluation shells --------------------------------------------


def _finalize(
    repo: str,
    detection: AdapterDetection,
    declarations: list[DeclaredRequirement],
    records: tuple[PackageRecord, ...],
    local_findings: list[LocalFinding],
    *,
    force_status: tuple[str, str | None] | None = None,
) -> DependencyRepoEvaluation:
    has_multiple = any(r.resolution == "multiple" for r in records)
    if force_status is not None:
        status, reason = force_status
    else:
        status, reason = reduce_local_status(local_findings)
        if status == "pass" and has_multiple:
            status, reason = "unknown", "multiple_resolutions"
    coverage_state = "incomplete" if (has_multiple or force_status is not None) else "complete"
    return DependencyRepoEvaluation(
        repo=repo,
        ecosystem="node",
        detection=detection,
        declarations=tuple(declarations),
        records=records,
        local_findings=tuple(local_findings),
        local_status=status,
        local_reason_code=reason,
        coverage_state=coverage_state,
        partial_unsupported=0,
    )


def _terminal_evaluation(
    repo: str, detection: AdapterDetection, status: str, reason_code: str | None
) -> DependencyRepoEvaluation:
    return DependencyRepoEvaluation(
        repo=repo,
        ecosystem="node",
        detection=detection,
        declarations=(),
        records=(),
        local_findings=(),
        local_status=status,
        local_reason_code=reason_code,
        coverage_state="complete" if status in ("not_applicable", "unsupported") else "incomplete",
        partial_unsupported=0,
    )


def _parse_manager(repo: str, evidence: RepoEvidence, manager: str) -> DependencyRepoEvaluation:
    lock_filename = _LOCK_FILES[manager]
    package_json = evidence.by_path("package.json")
    lock = evidence.by_path(lock_filename)
    detection = AdapterDetection(
        state="applicable",
        manager=manager,
        reason_code=None,
        source_files=("package.json", lock_filename),
    )
    if package_json is None or package_json.state != "found":
        return _terminal_evaluation(repo, detection, "unknown", "evidence_gap")

    manifest_data = _json_loads(package_json.content or "")
    if manifest_data is None:
        return _finalize(
            repo, detection, [], (), [], force_status=("fail", "malformed_source")
        )
    declarations = _package_json_declarations(manifest_data, "package.json")

    if lock is None or lock.state == "absent":
        return _finalize(
            repo, detection, declarations, (), [], force_status=("fail", "missing_lock")
        )
    if lock.state in _UNRESOLVED_ARTIFACT_STATES:
        return _terminal_evaluation(repo, detection, "unknown", "evidence_gap")

    if manager == "npm":
        lock_data = _json_loads(lock.content or "")
        if lock_data is None:
            return _finalize(
                repo, detection, [], (), [], force_status=("fail", "malformed_source")
            )
        lock_versions = _collect_npm_lock_versions(lock_data)
    elif manager == "pnpm":
        lock_data = _yaml_loads(lock.content or "")
        if not isinstance(lock_data, dict):
            return _finalize(
                repo, detection, [], (), [], force_status=("fail", "malformed_source")
            )
        lock_versions = _collect_pnpm_lock_versions(lock_data)
    else:  # yarn1
        lock_versions = _collect_yarn1_lock_versions(lock.content or "")

    manifest_ranges = {
        d.name: d.manifest_range for d in declarations if d.unresolved_reason is None
    }
    records = _build_npm_records(
        repo,
        "package.json",
        lock_filename,
        package_json.blob_sha,
        lock.blob_sha,
        manager,
        evidence.tree_sha,
        lock_versions,
        manifest_ranges,
    )
    findings = _range_local_findings(declarations, records)
    return _finalize(repo, detection, declarations, records, findings)


# --- public entry points -------------------------------------------------------


def parse_node(repo: str, evidence: RepoEvidence, *, capability: bool) -> DependencyRepoEvaluation:
    if not capability:
        return _terminal_evaluation(
            repo,
            AdapterDetection(state="not_applicable", manager=None, reason_code=None, source_files=()),
            "not_applicable",
            None,
        )

    workspace_yaml = evidence.by_path("pnpm-workspace.yaml")
    if workspace_yaml is not None and workspace_yaml.state in _UNRESOLVED_ARTIFACT_STATES:
        detection = AdapterDetection(
            state="unknown",
            manager=None,
            reason_code="workspace_sentinel_unresolved",
            source_files=("pnpm-workspace.yaml",),
        )
        return _terminal_evaluation(repo, detection, "unknown", "workspace_sentinel_unresolved")
    if workspace_yaml is not None and workspace_yaml.state == "found":
        detection = AdapterDetection(
            state="unsupported",
            manager=None,
            reason_code="workspace_repository",
            source_files=("pnpm-workspace.yaml",),
        )
        return _terminal_evaluation(repo, detection, "unsupported", "workspace_repository")

    package_json = evidence.by_path("package.json")
    if package_json is not None and package_json.state == "found":
        data = _json_loads(package_json.content or "")
        if isinstance(data, dict) and _has_workspaces_key(data):
            detection = AdapterDetection(
                state="unsupported",
                manager=None,
                reason_code="workspace_repository",
                source_files=("package.json",),
            )
            return _terminal_evaluation(repo, detection, "unsupported", "workspace_repository")

    manager, source_files, ambiguous, unsupported_yarn = _identify_manager(evidence)
    if ambiguous:
        detection = AdapterDetection(
            state="unsupported", manager=None, reason_code="ambiguous_manager", source_files=source_files
        )
        return _terminal_evaluation(repo, detection, "unsupported", "ambiguous_manager")
    if unsupported_yarn:
        detection = AdapterDetection(
            state="unsupported",
            manager=None,
            reason_code="unsupported_manager",
            source_files=source_files,
        )
        return _terminal_evaluation(repo, detection, "unsupported", "unsupported_manager")
    if manager is None:
        if _has_unresolved_candidate(evidence):
            detection = AdapterDetection(
                state="unknown", manager=None, reason_code="evidence_gap", source_files=()
            )
            return _terminal_evaluation(repo, detection, "unknown", "evidence_gap")
        detection = AdapterDetection(
            state="unknown", manager=None, reason_code="no_manager_evidence", source_files=()
        )
        return _terminal_evaluation(repo, detection, "unknown", "no_manager_evidence")

    return _parse_manager(repo, evidence, manager)


def evaluate_node(context: CheckContext) -> dict[str, Any]:
    evaluation = context.evidence["dependency_evaluations"]["node"]
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
