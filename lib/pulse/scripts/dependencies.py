"""Typed dependency-evaluation objects, fleet comparison, and coverage reconciliation.

`PackageRecord` is the collapsed, fleet-comparison-ready record for one
`(repo, ecosystem, name)` identity. `DependencyRepoEvaluation` is the ONE object
produced per `(repo, ecosystem)` by the Task 2/3 adapters, exactly once, before any
dispatch or dismissal logic runs — every other output (public `CheckBlock`, the
fleet comparator's input, the durable healthcheck coverage, and the transient
snapshot) projects from it.

Two distinct ecosystem literals exist for two distinct domains — never conflated:
  - Adapter-selection ecosystem, `Literal["python", "node"]` — which dependency
    adapter a scorecard selected for a repo. Used by `DependencyRepoEvaluation.ecosystem`
    and `RepositoryEvaluationSummary.ecosystem`.
  - Package namespace ecosystem, `Literal["python", "npm"]` — which packaging
    ecosystem a `PackageRecord` belongs to. Used by `PackageRecord.ecosystem`,
    `DivergenceFinding.ecosystem`, and the `"ecosystem:name"` glob-matching string.

See lib/patterns/dependency-coherence.md for the full contract.
"""

from __future__ import annotations

import fnmatch
import re
import string
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Literal

from packaging.version import Version as PyVersion
from semantic_version import Version as SemVersion


# --- typed evaluation objects -------------------------------------------------


@dataclass(frozen=True)
class ArtifactProvenance:
    role: Literal["manifest", "lock"]
    path: str  # repo-relative
    blob_sha: str | None


@dataclass(frozen=True)
class PackageRecord:
    """The collapsed, fleet-comparison-ready record for one (repo, ecosystem, name).

    Always exactly one per identity. `ecosystem` here is the PACKAGE NAMESPACE
    literal (python|npm), never the adapter-selection literal (python|node).
    """

    repo: str
    ecosystem: Literal["python", "npm"]
    name: str  # normalized identity component
    resolution: Literal["single", "multiple"]
    manifest_range: str | None  # None unless resolution == "single" and parseable
    locked_version: str | None  # None unless resolution == "single" and parseable
    unresolved_reason: (
        Literal["multiple_resolutions", "unparseable_version", "non_range_spec"] | None
    )
    manager: str
    manifest_path: str | None  # repo-relative declaring file; None if resolution == "multiple"
    lock_path: str | None  # repo-relative resolving file; None if lockless or "multiple"
    tree_sha: str | None  # from RepoEvidence, for F11 provenance
    provenance: tuple[ArtifactProvenance, ...]  # every contributing artifact, sorted


@dataclass(frozen=True)
class DeclaredRequirement:
    """One declaration of a package within one repo.

    A single PackageRecord's resolved version may be checked against several of
    these.
    """

    name: str  # normalized identity component
    manifest_path: str
    manifest_range: str | None  # None if unresolved_reason == "non_range_spec"
    unresolved_reason: Literal["non_range_spec"] | None
    group: Literal["main", "dev", "optional"]


@dataclass(frozen=True)
class LocalFinding:
    """The per-package local-check outcome — the reduction input for CheckBlock.status."""

    name: str
    status: Literal["pass", "fail", "warn", "unknown"]
    reason_code: str


@dataclass(frozen=True)
class DependencyRepoEvaluation:
    """The ONE object produced per (repo, ecosystem), exactly once, before any
    dispatch or dismissal logic runs. Every other output projects from this
    object. Never re-parsed; never reconstructed from a public, possibly-dismissed
    CheckBlock.
    """

    repo: str
    ecosystem: Literal["python", "node"]  # adapter-selection ecosystem
    detection: Any  # an AdapterDetection instance (Task 2/3 adapters); Any here
    # avoids a circular import — dependencies.py must not import adapters/*.
    declarations: tuple[DeclaredRequirement, ...]
    records: tuple[PackageRecord, ...]  # fleet-comparison input; one per normalized name
    local_findings: tuple[LocalFinding, ...]
    local_status: Literal[
        "pass", "warn", "fail", "unknown", "not_applicable", "unsupported", "error"
    ]
    local_reason_code: str | None
    coverage_state: Literal["complete", "incomplete"]
    partial_unsupported: int


@dataclass(frozen=True)
class CoherenceGroup:
    id: str
    repos: tuple[str, ...]
    packages: tuple[str, ...]  # ecosystem-qualified globs, e.g. "npm:@acme/*"
    exclude_packages: tuple[str, ...]
    policy: Literal["exact", "same-major", "same-minor"]


@dataclass(frozen=True)
class DependencyPolicy:
    groups: tuple[CoherenceGroup, ...]


@dataclass(frozen=True)
class DivergenceFinding:
    group: str
    ecosystem: Literal["python", "npm"]  # package namespace literal
    package: str
    versions: tuple[tuple[str, str | None], ...]  # (repo, locked_version|None)
    distance: Literal["major", "minor", "patch", "unresolved"]  # coarsest pairwise


@dataclass(frozen=True)
class DivergenceReport:
    findings: tuple[DivergenceFinding, ...]
    unresolved: tuple[DivergenceFinding, ...]


@dataclass(frozen=True)
class RepositoryEvaluationSummary:
    """The per-selected-(repo,ecosystem) reconciliation input the snapshot validator
    needs. `reconcile_coverage` below derives every `DependencyCoverage` counter
    entirely from instances of this shape plus the policy's `CoherenceGroup`s.
    """

    repo: str
    ecosystem: Literal["python", "node"]  # adapter-selection ecosystem
    adapter: Literal["python.dependencies", "node.dependencies"]
    status: Literal[
        "pass", "warn", "fail", "unknown", "not_applicable", "unsupported", "error"
    ]
    reason_code: str | None
    total_packages: int  # len(evaluation.records) — any resolution, any local_status
    matched_packages: int  # subset that is resolution=="single" + parseable AND
    # comparable (repo is a member of >= 1 CoherenceGroup whose glob matches it)
    partial_unsupported: int
    group_memberships: tuple[str, ...]  # CoherenceGroup ids with COMPARABLE membership


@dataclass(frozen=True)
class DependencyCoverage:
    repositories_selected: int
    repositories_grouped: int
    repositories_ungrouped: int
    groups_with_insufficient_members: tuple[str, ...]  # group ids with < 2 comparable repos
    packages_matched: int
    packages_unmatched: int
    unsupported_by_adapter: Mapping[str, int]


@dataclass(frozen=True)
class DependencySnapshot:
    records: tuple[PackageRecord, ...]
    groups: tuple[CoherenceGroup, ...]
    report: DivergenceReport
    coverage: DependencyCoverage
    repository_evaluations: tuple[RepositoryEvaluationSummary, ...]


@dataclass(frozen=True)
class DependencySnapshotDocument:
    """The versioned envelope wrapping DependencySnapshot for the wire format
    (deps-snapshot.json). Distinct from DependencySnapshot itself.
    """

    contract_version: int
    generated_at: str
    request_sha256: str
    snapshot: DependencySnapshot
    errors: tuple[str, ...]


# --- normalization -------------------------------------------------------------


def normalize_python_name(name: str) -> str:
    """PEP 503 normalization: lowercase, runs of -_. collapsed to a single '-'."""
    return re.sub(r"[-_.]+", "-", name).lower()


def normalize_npm_name(name: str) -> str:
    """Lowercase npm normalization, preserving the '@scope/' structure verbatim."""
    return name.lower()


def package_identity(ecosystem: Literal["python", "npm"], name: str) -> str:
    """The normalized "ecosystem:name" string globs match against."""
    return f"{ecosystem}:{name}"


# --- glob grammar (packages / exclude_packages) --------------------------------
#
# glob        = python_glob | npm_glob
# python_glob = "python:" py_segment
# npm_glob    = "npm:" (npm_scoped | npm_plain)
# npm_scoped  = "@" plain_atom+ "/" plain_atom+
# npm_plain   = plain_atom+
# py_segment  = plain_atom+
# plain_atom  = literal | star | question | bracket
# literal     = letter | digit | "-" | "_" | "."
# star        = "*"
# question    = "?"
# bracket     = "[" ["!"] rangeitem+ "]"
# rangeitem   = letter | digit | letter "-" letter | digit "-" digit
# letter      = "a".."z" | "A".."Z"          (ASCII only; no Unicode letters in v1)
# digit       = "0".."9"
#
# `/` and `@` are not members of `literal`/`plain_atom` — they appear only in the
# fixed `npm_scoped` production, at the fixed positions shown.

_LITERAL_CHARS = frozenset(string.ascii_letters + string.digits + "-_.")


def _is_ascii_letter(ch: str) -> bool:
    return ch.isascii() and ch.isalpha()


def _is_valid_bracket_body(body: str) -> bool:
    if body.startswith("!"):
        body = body[1:]
    if not body:
        return False
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        is_letter = _is_ascii_letter(c)
        is_digit = c.isdigit()
        if not (is_letter or is_digit):
            return False
        if i + 2 < n and body[i + 1] == "-":
            c2 = body[i + 2]
            if is_digit and c2.isdigit():
                i += 3
                continue
            if is_letter and _is_ascii_letter(c2):
                i += 3
                continue
            return False
        i += 1
    return True


def _is_valid_atom_run(segment: str) -> bool:
    """Validate one `plain_atom+` run — a py_segment, or one npm scope/name half."""
    if not segment:
        return False
    i, n = 0, len(segment)
    while i < n:
        c = segment[i]
        if c in _LITERAL_CHARS or c in "*?":
            i += 1
            continue
        if c == "[":
            close = segment.find("]", i + 1)
            if close == -1:
                return False
            if not _is_valid_bracket_body(segment[i + 1 : close]):
                return False
            i = close + 1
            continue
        return False
    return True


def is_valid_package_glob(glob: str) -> bool:
    """Validate one `packages`/`exclude_packages` glob against the grammar above."""
    if glob.startswith("python:"):
        return _is_valid_atom_run(glob[len("python:") :])
    if glob.startswith("npm:"):
        rest = glob[len("npm:") :]
        if rest.startswith("@"):
            body = rest[1:]
            if "/" not in body:
                return False
            slash = body.find("/")
            scope, name = body[:slash], body[slash + 1 :]
            if "/" in name:
                return False
            return _is_valid_atom_run(scope) and _is_valid_atom_run(name)
        if "/" in rest or "@" in rest:
            return False
        return _is_valid_atom_run(rest)
    return False


def matches_glob(identity: str, glob: str) -> bool:
    """Case-sensitive glob match — fnmatch.fnmatchcase, never the platform-normalizing
    fnmatch.fnmatch, since matching must stay case-sensitive post-normalization."""
    return fnmatch.fnmatchcase(identity, glob)


# --- version distance ------------------------------------------------------------

_TIER_RANK = {"patch": 0, "minor": 1, "major": 2}


def _python_pairwise_distance(a: PyVersion, b: PyVersion) -> str | None:
    if a.epoch != b.epoch:
        return "major"
    n = max(3, len(a.release), len(b.release))
    ra = tuple(a.release) + (0,) * (n - len(a.release))
    rb = tuple(b.release) + (0,) * (n - len(b.release))
    if ra[0] != rb[0]:
        return "major"
    if ra[1] != rb[1]:
        return "minor"
    if a == b:
        return None
    return "patch"


def _npm_pairwise_distance(a: SemVersion, b: SemVersion) -> str | None:
    if a.major != b.major:
        return "major"
    if a.minor != b.minor:
        return "minor"
    if a.patch != b.patch:
        return "patch"
    if a == b:
        return None
    # prerelease/build metadata-only difference at equal (major, minor, patch)
    return "patch"


def _parse_version(ecosystem: str, raw: str) -> PyVersion | SemVersion:
    if ecosystem == "python":
        return PyVersion(raw)
    return SemVersion(raw)


def _pairwise_distance(ecosystem: str, a: object, b: object) -> str | None:
    if ecosystem == "python":
        return _python_pairwise_distance(a, b)  # type: ignore[arg-type]
    return _npm_pairwise_distance(a, b)  # type: ignore[arg-type]


def _reduce_distance(distances: Iterable[str | None]) -> str | None:
    """The coarsest tier across every pairwise comparison; None if every pair
    was equal (no divergence)."""
    real = [d for d in distances if d is not None]
    if not real:
        return None
    return max(real, key=lambda d: _TIER_RANK[d])


# --- fleet comparison --------------------------------------------------------


def _is_eligible_for_distance(record: PackageRecord) -> bool:
    """A record participates in fleet distance comparison only when it resolved
    to a single, parseable locked_version. `unresolved_reason == "non_range_spec"`
    describes the *manifest_range*, not the locked_version, and does not disqualify
    a record here.
    """
    return (
        record.resolution == "single"
        and record.locked_version is not None
        and record.unresolved_reason != "unparseable_version"
    )


def compare(
    records: Iterable[PackageRecord],
    groups: Iterable[CoherenceGroup],
) -> DivergenceReport:
    """Detect fleet-wide version divergence for every package inside every
    committed coherence group. Cross-repo divergence is evaluated only among a
    group's own member repos; a package identity matched by multiple groups
    produces one independent finding per group (never merged or ranked).
    """
    findings: list[DivergenceFinding] = []
    unresolved: list[DivergenceFinding] = []

    for group in groups:
        member_repos = set(group.repos)
        buckets: dict[tuple[str, str], list[PackageRecord]] = {}
        for record in records:
            if record.repo not in member_repos:
                continue
            identity = package_identity(record.ecosystem, record.name)
            if not any(matches_glob(identity, g) for g in group.packages):
                continue
            if any(matches_glob(identity, g) for g in group.exclude_packages):
                continue
            buckets.setdefault((record.ecosystem, record.name), []).append(record)

        for (ecosystem, name), members in buckets.items():
            members = sorted(members, key=lambda m: m.repo)
            resolved = [m for m in members if _is_eligible_for_distance(m)]

            if len(resolved) != len(members):
                # At least one member is a genuine resolution ambiguity or an
                # unparseable locked_version — this is coverage debt, never a
                # guessed comparison, and it is never silently dropped.
                versions = tuple(
                    (m.repo, m.locked_version if _is_eligible_for_distance(m) else None)
                    for m in members
                )
                unresolved.append(
                    DivergenceFinding(
                        group=group.id,
                        ecosystem=ecosystem,
                        package=name,
                        versions=versions,
                        distance="unresolved",
                    )
                )
                continue

            if len(resolved) < 2:
                continue  # nothing to compare against

            parsed = [(m.repo, _parse_version(ecosystem, m.locked_version)) for m in resolved]
            distances = [
                _pairwise_distance(ecosystem, a[1], b[1])
                for a, b in combinations(parsed, 2)
            ]
            reduced = _reduce_distance(distances)
            if reduced is None:
                continue  # identical across every member — no divergence

            versions = tuple((m.repo, m.locked_version) for m in resolved)
            findings.append(
                DivergenceFinding(
                    group=group.id,
                    ecosystem=ecosystem,
                    package=name,
                    versions=versions,
                    distance=reduced,
                )
            )

    findings.sort(key=lambda f: (f.group, f.ecosystem, f.package))
    unresolved.sort(key=lambda f: (f.group, f.ecosystem, f.package))
    return DivergenceReport(findings=tuple(findings), unresolved=tuple(unresolved))


# --- coverage reconciliation --------------------------------------------------


def reconcile_coverage(
    evaluations: Iterable[RepositoryEvaluationSummary],
    groups: Iterable[CoherenceGroup],
) -> DependencyCoverage:
    """The single source of truth for every DependencyCoverage counter, derived
    entirely from RepositoryEvaluationSummary + CoherenceGroup — both the durable
    healthcheck coverage and the transient snapshot call this over the same
    collected inputs, so the two can never silently diverge.
    """
    evaluations = list(evaluations)
    groups = list(groups)

    repos_selected = {e.repo for e in evaluations}
    repos_grouped = {e.repo for e in evaluations if e.group_memberships}
    repos_ungrouped = repos_selected - repos_grouped

    insufficient: list[str] = []
    for group in groups:
        comparable = {
            e.repo
            for e in evaluations
            if group.id in e.group_memberships and e.repo in group.repos
        }
        if len(comparable) < 2:
            insufficient.append(group.id)

    packages_matched = sum(e.matched_packages for e in evaluations)
    packages_unmatched = sum(e.total_packages - e.matched_packages for e in evaluations)

    unsupported_by_adapter: dict[str, int] = {}
    for e in evaluations:
        count = (1 if e.status == "unsupported" else 0) + e.partial_unsupported
        if count:
            unsupported_by_adapter[e.adapter] = unsupported_by_adapter.get(e.adapter, 0) + count

    return DependencyCoverage(
        repositories_selected=len(repos_selected),
        repositories_grouped=len(repos_grouped),
        repositories_ungrouped=len(repos_ungrouped),
        groups_with_insufficient_members=tuple(sorted(insufficient)),
        packages_matched=packages_matched,
        packages_unmatched=packages_unmatched,
        unsupported_by_adapter=dict(sorted(unsupported_by_adapter.items())),
    )
