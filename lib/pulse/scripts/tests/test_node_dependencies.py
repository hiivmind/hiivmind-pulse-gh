"""Tests for the Node dependency-manager adapter (npm, pnpm, Yarn v1)."""

from __future__ import annotations

from pathlib import Path

from lib.pulse.scripts.dependency_evidence import Artifact, RepoEvidence
from lib.pulse.scripts.adapters.node_dependencies import (
    detect_node,
    evaluate_node,
    parse_node,
)
from lib.pulse.scripts.check_adapters import CheckContext


FIXTURES = Path(__file__).parent / "fixtures" / "dependencies" / "node"


def _read(*parts: str) -> str:
    return (FIXTURES.joinpath(*parts)).read_text()


def _found(path: str, content: str, *, selector_id: str | None = None) -> Artifact:
    return Artifact(
        selector_id=selector_id or path,
        path=path,
        blob_sha="a" * 40,
        size_bytes=len(content.encode("utf-8")),
        state="found",
        encoding="utf-8",
        content=content,
        detail=None,
    )


def _absent(path: str, *, selector_id: str | None = None) -> Artifact:
    return Artifact(
        selector_id=selector_id or path,
        path=None,
        blob_sha=None,
        size_bytes=None,
        state="absent",
        encoding=None,
        content=None,
        detail=None,
    )


def _artifact(path: str, *, state: str, selector_id: str | None = None) -> Artifact:
    if state == "found":
        raise ValueError("use _found for the found state")
    if state == "absent":
        return _absent(path, selector_id=selector_id)
    return Artifact(
        selector_id=selector_id or path,
        path=path,
        blob_sha=None,
        size_bytes=None,
        state=state,
        encoding=None,
        content=None,
        detail="materialize could not resolve this artifact",
    )


def _evidence(repo: str, artifacts: list[Artifact]) -> RepoEvidence:
    return RepoEvidence(
        repo=repo, ref_name="main", tree_sha="b" * 40, tree_complete=True, artifacts=tuple(artifacts)
    )


_CANDIDATE_SELECTORS = {
    "package.json": "node.package_json",
    "package-lock.json": "node.npm_lock",
    "pnpm-lock.yaml": "node.pnpm_lock",
    "pnpm-workspace.yaml": "node.pnpm_workspace_yaml",
    "yarn.lock": "node.yarn_lock",
}


def _manager_evidence(fixture_dir: str, *, repo: str | None = None) -> RepoEvidence:
    directory = FIXTURES / fixture_dir
    artifacts = []
    for name, selector_id in _CANDIDATE_SELECTORS.items():
        path = directory / name
        if path.exists():
            artifacts.append(_found(name, path.read_text(), selector_id=selector_id))
        else:
            artifacts.append(_absent(name, selector_id=selector_id))
    return _evidence(repo or f"acme/{fixture_dir}", artifacts)


# --- capability=False ---------------------------------------------------------


def test_capability_false_is_not_applicable():
    evidence = _evidence("acme/none", [])
    detection = detect_node("acme/none", evidence, capability=False)
    assert detection.state == "not_applicable"
    evaluation = parse_node("acme/none", evidence, capability=False)
    assert evaluation.local_status == "not_applicable"
    assert evaluation.records == ()


# --- workspace detection -------------------------------------------------------


def test_workspaces_key_in_package_json_is_unsupported():
    evidence = _manager_evidence("workspaces_key")
    detection = detect_node("acme/mono", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "workspace_repository"
    evaluation = parse_node("acme/mono", evidence, capability=True)
    assert evaluation.local_status == "unsupported"
    assert evaluation.local_reason_code == "workspace_repository"
    assert evaluation.records == ()


def test_pnpm_workspace_yaml_found_is_unsupported():
    evidence = _manager_evidence("pnpm_workspace_found")
    detection = detect_node("acme/mono", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "workspace_repository"
    evaluation = parse_node("acme/mono", evidence, capability=True)
    assert evaluation.local_status == "unsupported"
    assert evaluation.local_reason_code == "workspace_repository"


def test_pnpm_workspace_yaml_unresolved_is_workspace_sentinel_unresolved():
    evidence = _evidence(
        "acme/mono",
        [
            _found("package.json", _read("pnpm", "package.json"), selector_id="node.package_json"),
            _absent("package-lock.json", selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _artifact("pnpm-workspace.yaml", state="too_large", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    detection = detect_node("acme/mono", evidence, capability=True)
    assert detection.state == "unknown"
    assert detection.reason_code == "workspace_sentinel_unresolved"
    evaluation = parse_node("acme/mono", evidence, capability=True)
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "workspace_sentinel_unresolved"


def test_empty_workspaces_array_still_declares_a_workspace():
    # Any "workspaces" key at all is a declaration — an empty array is not
    # evidence of "no workspace" and must not fall through to normal parsing.
    evidence = _evidence(
        "acme/mono-empty",
        [
            _found(
                "package.json",
                '{"name":"acme-mono","version":"0.1.0","workspaces":[]}',
                selector_id="node.package_json",
            ),
            _absent("package-lock.json", selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    detection = detect_node("acme/mono-empty", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "workspace_repository"


def test_empty_workspaces_packages_object_still_declares_a_workspace():
    evidence = _evidence(
        "acme/mono-empty-obj",
        [
            _found(
                "package.json",
                '{"name":"acme-mono","version":"0.1.0","workspaces":{"packages":[]}}',
                selector_id="node.package_json",
            ),
            _absent("package-lock.json", selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    detection = detect_node("acme/mono-empty-obj", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "workspace_repository"


# --- no manager evidence / evidence gap ---------------------------------------


def test_no_manager_evidence_when_nothing_found():
    evidence = _evidence(
        "acme/empty",
        [_absent(name, selector_id=sel) for name, sel in _CANDIDATE_SELECTORS.items()],
    )
    evaluation = parse_node("acme/empty", evidence, capability=True)
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "no_manager_evidence"


def test_evidence_gap_when_lock_is_unresolved_for_identified_manager():
    evidence = _evidence(
        "acme/flaky",
        [
            _found("package.json", _read("npm", "package.json"), selector_id="node.package_json"),
            _artifact("package-lock.json", state="too_large", selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/flaky", evidence, capability=True)
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "evidence_gap"


# --- npm -----------------------------------------------------------------------


def test_npm_manager_all_ranges_satisfied_is_pass():
    evidence = _manager_evidence("npm")
    evaluation = parse_node("acme/npm", evidence, capability=True)
    assert evaluation.detection.manager == "npm"
    assert evaluation.local_status == "pass"
    names = {r.name for r in evaluation.records}
    assert {"lodash", "@acme/widgets", "jest", "fsevents", "glob"} <= names
    for record in evaluation.records:
        assert record.ecosystem == "npm"
        assert record.resolution == "single"


def test_npm_declaration_groups_runtime_dev_optional():
    evidence = _manager_evidence("npm")
    evaluation = parse_node("acme/npm", evidence, capability=True)
    groups = {d.name: d.group for d in evaluation.declarations}
    assert groups["lodash"] == "main"
    assert groups["jest"] == "dev"
    assert groups["fsevents"] == "optional"


def test_npm_scoped_package_normalization():
    evidence = _manager_evidence("npm")
    evaluation = parse_node("acme/npm", evidence, capability=True)
    widgets = next(r for r in evaluation.records if r.name == "@acme/widgets")
    assert widgets.locked_version == "1.2.5"
    assert widgets.ecosystem == "npm"


def test_npm_missing_lock_is_fail_missing_lock():
    evidence = _evidence(
        "acme/npm-nolock",
        [
            _found("package.json", _read("npm", "package.json"), selector_id="node.package_json"),
            _absent("package-lock.json", selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/npm-nolock", evidence, capability=True)
    assert evaluation.detection.manager == "npm"
    assert evaluation.local_status == "fail"
    assert evaluation.local_reason_code == "missing_lock"


def test_npm_range_violation_is_fail():
    evidence = _evidence(
        "acme/npm-violation",
        [
            _found("package.json", _read("npm", "package.json"), selector_id="node.package_json"),
            _found(
                "package-lock.json",
                _read("npm", "package-lock.json").replace('"version": "4.17.21"', '"version": "5.0.0"'),
                selector_id="node.npm_lock",
            ),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/npm-violation", evidence, capability=True)
    lodash = next(f for f in evaluation.local_findings if f.name == "lodash")
    assert lodash.status == "fail"
    assert lodash.reason_code == "range_violation"
    assert evaluation.local_status == "fail"


def test_malformed_package_lock_is_fail_malformed_source():
    evidence = _evidence(
        "acme/broken-lock",
        [
            _found("package.json", _read("npm", "package.json"), selector_id="node.package_json"),
            _found("package-lock.json", "{not valid json", selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/broken-lock", evidence, capability=True)
    assert evaluation.local_status == "fail"
    assert evaluation.local_reason_code == "malformed_source"


def test_conflicting_locks_is_ambiguous_manager():
    evidence = _evidence(
        "acme/ambiguous",
        [
            _found("package.json", _read("npm", "package.json"), selector_id="node.package_json"),
            _found("package-lock.json", _read("npm", "package-lock.json"), selector_id="node.npm_lock"),
            _found("pnpm-lock.yaml", _read("pnpm", "pnpm-lock.yaml"), selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    detection = detect_node("acme/ambiguous", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "ambiguous_manager"
    evaluation = parse_node("acme/ambiguous", evidence, capability=True)
    assert evaluation.local_status == "unsupported"
    assert evaluation.local_reason_code == "ambiguous_manager"


# --- pnpm ------------------------------------------------------------------------


def test_pnpm_manager_pass():
    evidence = _manager_evidence("pnpm")
    evaluation = parse_node("acme/pnpm", evidence, capability=True)
    assert evaluation.detection.manager == "pnpm"
    assert evaluation.local_status == "pass"
    express = next(r for r in evaluation.records if r.name == "express")
    assert express.locked_version == "4.18.2"
    ts = next(r for r in evaluation.records if r.name == "typescript")
    assert ts.locked_version == "5.1.6"


# --- Yarn v1 -----------------------------------------------------------------------


def test_yarn1_manager_pass():
    evidence = _manager_evidence("yarn1")
    evaluation = parse_node("acme/yarn1", evidence, capability=True)
    assert evaluation.detection.manager == "yarn1"
    assert evaluation.local_status == "pass"
    chalk = next(r for r in evaluation.records if r.name == "chalk")
    assert chalk.locked_version == "4.1.2"
    # ansi-styles is a transitive dep in the lock, not declared in package.json —
    # it still becomes a PackageRecord (fleet-comparison input), just earns no
    # LocalFinding since there is no DeclaredRequirement to check it against.
    assert any(r.name == "ansi-styles" for r in evaluation.records)


def test_yarn_modern_lockfile_is_unsupported_manager():
    evidence = _manager_evidence("yarn_modern")
    detection = detect_node("acme/yarn-modern", evidence, capability=True)
    assert detection.state == "unsupported"
    assert detection.reason_code == "unsupported_manager"
    evaluation = parse_node("acme/yarn-modern", evidence, capability=True)
    assert evaluation.local_status == "unsupported"
    assert evaluation.local_reason_code == "unsupported_manager"


# --- non-range forms -----------------------------------------------------------


def test_non_range_npm_forms_are_non_range_spec():
    package_json = (
        '{"name":"acme-mixed","version":"0.1.0","dependencies":{'
        '"wildcard-dep":"*",'
        '"workspace-dep":"workspace:*",'
        '"git-dep":"git+https://example.com/acme/gitdep.git",'
        '"alias-dep":"npm:other-pkg@^1.0.0"'
        "}}"
    )
    lock = (
        '{"lockfileVersion":3,"packages":{'
        '"":{"name":"acme-mixed","version":"0.1.0"},'
        '"node_modules/wildcard-dep":{"version":"9.9.9"},'
        '"node_modules/workspace-dep":{"version":"1.0.0"},'
        '"node_modules/git-dep":{"version":"0.0.1"},'
        '"node_modules/alias-dep":{"version":"1.5.0"}'
        "}}"
    )
    evidence = _evidence(
        "acme/mixed",
        [
            _found("package.json", package_json, selector_id="node.package_json"),
            _found("package-lock.json", lock, selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/mixed", evidence, capability=True)
    reasons = {d.name: d.unresolved_reason for d in evaluation.declarations}
    assert reasons["wildcard-dep"] == "non_range_spec"
    assert reasons["workspace-dep"] == "non_range_spec"
    assert reasons["git-dep"] == "non_range_spec"
    assert reasons["alias-dep"] == "non_range_spec"
    # every record still resolves — a non-range declared spec never blocks
    # fleet comparison of the locked_version — but the LOCAL check can't
    # confirm compliance with an unconstrained/non-range declaration, so it
    # is explicit unknown coverage debt, never a guessed pass.
    for name in ("wildcard-dep", "workspace-dep", "git-dep", "alias-dep"):
        record = next(r for r in evaluation.records if r.name == name)
        assert record.resolution == "single"
        finding = next(f for f in evaluation.local_findings if f.name == name)
        assert finding.status == "unknown"
        assert finding.reason_code == "non_range_spec"
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "non_range_spec"


# --- genuinely ambiguous resolution --------------------------------------------


def test_genuine_multi_resolution_is_unknown_multiple_resolutions():
    package_json = '{"name":"acme-split","version":"0.1.0","dependencies":{"foo":"^1.0.0"}}'
    lock = (
        '{"lockfileVersion":3,"packages":{'
        '"":{"name":"acme-split","version":"0.1.0"},'
        '"node_modules/foo":{"version":"1.2.0"},'
        '"node_modules/react-native/node_modules/foo":{"version":"1.5.0"}'
        "}}"
    )
    evidence = _evidence(
        "acme/split",
        [
            _found("package.json", package_json, selector_id="node.package_json"),
            _found("package-lock.json", lock, selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/split", evidence, capability=True)
    foo = next(r for r in evaluation.records if r.name == "foo")
    assert foo.resolution == "multiple"
    assert foo.unresolved_reason == "multiple_resolutions"
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "multiple_resolutions"



def test_unparseable_npm_locked_version_never_crashes_and_is_typed():
    package_json = '{"name":"acme-garbage","version":"0.1.0","dependencies":{"lodash":"^1.0.0"}}'
    lock = (
        '{"lockfileVersion":3,"packages":{'
        '"":{"name":"acme-garbage","version":"0.1.0"},'
        '"node_modules/lodash":{"version":"not-a-real-semver!!"}'
        "}}"
    )
    evidence = _evidence(
        "acme/garbage-version",
        [
            _found("package.json", package_json, selector_id="node.package_json"),
            _found("package-lock.json", lock, selector_id="node.npm_lock"),
            _absent("pnpm-lock.yaml", selector_id="node.pnpm_lock"),
            _absent("pnpm-workspace.yaml", selector_id="node.pnpm_workspace_yaml"),
            _absent("yarn.lock", selector_id="node.yarn_lock"),
        ],
    )
    evaluation = parse_node("acme/garbage-version", evidence, capability=True)
    record = next(r for r in evaluation.records if r.name == "lodash")
    assert record.resolution == "single"
    assert record.locked_version is None
    assert record.unresolved_reason == "unparseable_version"
    assert evaluation.local_status == "unknown"
    assert evaluation.local_reason_code == "unparseable_version"
    assert evaluation.coverage_state == "incomplete"

    from lib.pulse.scripts.dependencies import CoherenceGroup, compare

    group = CoherenceGroup(
        id="g1",
        repos=("acme/garbage-version",),
        packages=("npm:lodash",),
        exclude_packages=(),
        policy="same-minor",
    )
    report = compare(evaluation.records, [group])
    assert report.findings == ()
    assert len(report.unresolved) == 1

# --- evaluate_node (CheckBlock dispatch) ----------------------------------------


def test_evaluate_node_projects_the_precomputed_evaluation():
    evidence = _manager_evidence("npm")
    evaluation = parse_node("acme/npm", evidence, capability=True)
    context = CheckContext(
        repo="acme/npm",
        evidence={"dependency_evaluations": {"node": evaluation}},
        check={"id": "node_manifest_lock_consistency", "adapter": "node.dependencies", "weight": 1},
        workspace=Path("."),
    )
    block = evaluate_node(context)
    assert block["status"] == "pass"
    assert block["data"]["records"]
    assert block["data"]["evidence"] == {"paths": [], "refs": []}
