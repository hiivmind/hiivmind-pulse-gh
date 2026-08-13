"""Integration tests for F4's integrated two-pass dependency pipeline inside
evaluate_fleet: mixed-fleet dispatch, dismissal-immune fleet comparison, score
reconciliation, missing-policy handling, and collector/coverage reconciliation.
"""

from __future__ import annotations

import copy

import pytest
import yaml

from lib.pulse.scripts import dependency_pipeline as dp
from lib.pulse.scripts.dependencies import CoherenceGroup, DependencyPolicy, reconcile_coverage
from lib.pulse.scripts.dependency_evidence import Artifact, RepoEvidence
from lib.pulse.scripts.healthcheck_dispatch import evaluate_fleet


def _artifact(path, content, *, selector_id=None, state="found"):
    if state != "found":
        return Artifact(
            selector_id=selector_id or path or "?",
            path=None,
            blob_sha=None,
            size_bytes=None,
            state=state,
            encoding=None,
            content=None,
            detail=None,
        )
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


def _python_evidence(repo, *, locked_version="1.0.0", requests_range=">=1.0"):
    pyproject = f'[project]\nname="x"\ndependencies=["requests{requests_range}"]\n'
    lock = f'[[package]]\nname="requests"\nversion="{locked_version}"\n'
    return RepoEvidence(
        repo=repo,
        ref_name="main",
        tree_sha="c" * 40,
        tree_complete=True,
        artifacts=(
            _artifact("pyproject.toml", pyproject, selector_id="python.pyproject"),
            _artifact("uv.lock", lock, selector_id="python.uv_lock"),
        ),
    )


def _node_evidence(repo, *, locked_version="1.0.0"):
    package_json = '{"name":"x","version":"0.1.0","dependencies":{"lodash":"^1.0.0"}}'
    lock = (
        '{"lockfileVersion":3,"packages":{'
        '"":{"name":"x","version":"0.1.0"},'
        f'"node_modules/lodash":{{"version":"{locked_version}"}}'
        "}}"
    )
    return RepoEvidence(
        repo=repo,
        ref_name="main",
        tree_sha="d" * 40,
        tree_complete=True,
        artifacts=(
            _artifact("package.json", package_json, selector_id="node.package_json"),
            _artifact("package-lock.json", lock, selector_id="node.npm_lock"),
        ),
    )


def _write_profiles(path, *, with_fleet_check=True):
    checks_generic = [
        {"id": "documentation", "adapter": "generic.docs", "weight": 1},
    ]
    py_checks = list(checks_generic) + [
        {"id": "python_manifest_lock_consistency", "adapter": "python.dependencies", "weight": 1},
    ]
    node_checks = list(checks_generic) + [
        {"id": "node_manifest_lock_consistency", "adapter": "node.dependencies", "weight": 1},
    ]
    poly_checks = list(checks_generic) + [
        {"id": "python_manifest_lock_consistency", "adapter": "python.dependencies", "weight": 1},
        {"id": "node_manifest_lock_consistency", "adapter": "node.dependencies", "weight": 1},
    ]
    docs_checks = list(checks_generic)
    terraform_checks = list(checks_generic) + [
        {"id": "terraform-validate", "adapter": "terraform.validate", "weight": 1},
    ]
    if with_fleet_check:
        fleet_check = {
            "id": "fleet_dependency_coherence",
            "adapter": "fleet.dependencies.coherence",
            "weight": 1,
        }
        py_checks.append(fleet_check)
        node_checks.append(fleet_check)
        poly_checks.append(fleet_check)

    profiles = {
        "repository_profiles": {
            "acme/py-a": {"profiles": [], "scorecard": "py-v1"},
            "acme/py-b": {"profiles": [], "scorecard": "py-v1"},
            "acme/node-a": {"profiles": [], "scorecard": "node-v1"},
            "acme/poly": {"profiles": [], "scorecard": "poly-v1"},
            "acme/docs": {"profiles": [], "scorecard": "docs-v1"},
            "acme/terraform": {"profiles": [], "scorecard": "terraform-v1"},
        },
        "scorecards": {
            "generic-v1": {"checks": checks_generic},
            "py-v1": {"checks": py_checks},
            "node-v1": {"checks": node_checks},
            "poly-v1": {"checks": poly_checks},
            "docs-v1": {"checks": docs_checks},
            "terraform-v1": {"checks": terraform_checks},
        },
        "adapters": {
            "generic.docs": {"state": "available"},
            "python.dependencies": {"state": "available"},
            "node.dependencies": {"state": "available"},
            "fleet.dependencies.coherence": {"state": "available"},
            "terraform.validate": {
                "state": "unsupported",
                "reason": "not implemented",
            },
        },
    }
    path.write_text(yaml.safe_dump(profiles))
    return path


def _evidence_doc(repos):
    return {"repos": [{"repo": repo} for repo in repos]}


def _run(tmp_path, *, dependency_evidence=None, dependency_policy=None, dependency_collector=None,
          with_fleet_check=True, dismissals_path=None):
    return evaluate_fleet(
        evidence=_evidence_doc(
            ["acme/py-a", "acme/py-b", "acme/node-a", "acme/poly", "acme/docs", "acme/terraform"]
        ),
        profiles_path=_write_profiles(tmp_path / "profiles.yaml", with_fleet_check=with_fleet_check),
        workspace=tmp_path,
        dependency_evidence=dependency_evidence,
        dependency_policy=dependency_policy,
        dependency_collector=dependency_collector,
        dismissals_path=dismissals_path,
    )


# --- mixed fleet dispatch -----------------------------------------------------


def test_mixed_fleet_docs_and_terraform_never_get_dependency_checks(tmp_path):
    result = _run(tmp_path)
    by_repo = {r["repo"]: r for r in result["repos"]}
    assert "python_manifest_lock_consistency" not in by_repo["acme/docs"]["checks"]
    assert "node_manifest_lock_consistency" not in by_repo["acme/docs"]["checks"]
    assert "python_manifest_lock_consistency" not in by_repo["acme/terraform"]["checks"]
    assert "node_manifest_lock_consistency" not in by_repo["acme/terraform"]["checks"]


def test_polyglot_repo_selects_both_ecosystems_exactly_once(tmp_path, monkeypatch):
    calls = []
    real = dp.evaluate_dependencies

    def _counting(repo, ecosystem, evidence):
        calls.append((repo, ecosystem))
        return real(repo, ecosystem, evidence)

    monkeypatch.setattr(
        "lib.pulse.scripts.healthcheck_dispatch.evaluate_dependencies", _counting
    )
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a"),
        "acme/py-b": _python_evidence("acme/py-b"),
        "acme/node-a": _node_evidence("acme/node-a"),
        "acme/poly": _python_evidence("acme/poly"),
    }
    result = _run(tmp_path, dependency_evidence=dependency_evidence)
    assert sorted(calls) == [
        ("acme/node-a", "node"),
        ("acme/poly", "node"),
        ("acme/poly", "python"),
        ("acme/py-a", "python"),
        ("acme/py-b", "python"),
    ]
    by_repo = {r["repo"]: r for r in result["repos"]}
    poly = by_repo["acme/poly"]
    assert poly["checks"]["python_manifest_lock_consistency"]["status"] == "pass"
    assert poly["checks"]["node_manifest_lock_consistency"]["status"] == "unknown"  # no node evidence given -> evidence_gap


def test_evidence_none_and_repo_missing_from_evidence_both_yield_stable_evidence_gap(tmp_path, monkeypatch):
    calls = []
    real_parse_python = dp.parse_python

    def _counting(*args, **kwargs):
        calls.append(args)
        return real_parse_python(*args, **kwargs)

    monkeypatch.setattr("lib.pulse.scripts.dependency_pipeline.parse_python", _counting)

    # dependency_evidence mapping present but this repo has no entry
    dependency_evidence = {"acme/py-b": _python_evidence("acme/py-b")}
    result = _run(tmp_path, dependency_evidence=dependency_evidence)
    by_repo = {r["repo"]: r for r in result["repos"]}
    assert by_repo["acme/py-a"]["checks"]["python_manifest_lock_consistency"]["status"] == "unknown"
    assert all(call[0] != "acme/py-a" for call in calls)  # never called for py-a — evidence lookup returned None

    # dependency_evidence is None for the whole run
    result2 = _run(tmp_path, dependency_evidence=None)
    by_repo2 = {r["repo"]: r for r in result2["repos"]}
    assert by_repo2["acme/py-a"]["checks"]["python_manifest_lock_consistency"]["status"] == "unknown"


# --- dismissal-immune fleet comparison (regression) ---------------------------


def test_local_dismissal_never_starves_fleet_comparison_of_records(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a", locked_version="1.0.0"),
        "acme/py-b": _python_evidence("acme/py-b", locked_version="2.0.0"),
    }
    policy = DependencyPolicy(
        groups=(
            CoherenceGroup(
                id="g1",
                repos=("acme/py-a", "acme/py-b"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
        )
    )
    dismissals_path = tmp_path / "dismissals.yaml"
    dismissals_path.write_text(
        yaml.safe_dump(
            {
                "dismissals": {
                    "acme/py-a": {
                        "python_manifest_lock_consistency": {"reason": "known, tracked"}
                    }
                }
            }
        )
    )
    result = _run(
        tmp_path,
        dependency_evidence=dependency_evidence,
        dependency_policy=policy,
        dismissals_path=dismissals_path,
    )
    by_repo = {r["repo"]: r for r in result["repos"]}
    # the local check is dismissed...
    assert by_repo["acme/py-a"]["checks"]["python_manifest_lock_consistency"]["status"] == (
        "not_applicable"
    )
    # ...but the fleet comparison still sees acme/py-a's real 1.0.0 record and
    # reports the major divergence against acme/py-b's 2.0.0.
    fleet_block = by_repo["acme/py-b"]["checks"]["fleet_dependency_coherence"]
    assert fleet_block["status"] == "fail"
    findings = fleet_block["data"]["findings"]
    assert len(findings) == 1
    assert findings[0]["distance"] == "major"
    versions = dict(findings[0]["versions"])
    assert versions["acme/py-a"] == "1.0.0"
    assert versions["acme/py-b"] == "2.0.0"


def test_fleet_check_dismissal_survives_placeholder_replacement(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a", locked_version="1.0.0"),
        "acme/py-b": _python_evidence("acme/py-b", locked_version="2.0.0"),
    }
    policy = DependencyPolicy(
        groups=(
            CoherenceGroup(
                id="g1",
                repos=("acme/py-a", "acme/py-b"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
        )
    )
    dismissals_path = tmp_path / "dismissals.yaml"
    dismissals_path.write_text(
        yaml.safe_dump(
            {
                "dismissals": {
                    "acme/py-a": {
                        "fleet_dependency_coherence": {"reason": "accepted risk"}
                    }
                }
            }
        )
    )
    result = _run(
        tmp_path,
        dependency_evidence=dependency_evidence,
        dependency_policy=policy,
        dismissals_path=dismissals_path,
    )
    by_repo = {r["repo"]: r for r in result["repos"]}
    fleet_block = by_repo["acme/py-a"]["checks"]["fleet_dependency_coherence"]
    assert fleet_block["status"] == "not_applicable"
    assert fleet_block["detail"].startswith("Dismissed:")
    # the other repo, undismissed, still sees the real fail.
    other = by_repo["acme/py-b"]["checks"]["fleet_dependency_coherence"]
    assert other["status"] == "fail"


def test_score_after_fleet_pass_reflects_real_fleet_block_not_placeholder(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a", locked_version="1.0.0"),
        "acme/py-b": _python_evidence("acme/py-b", locked_version="2.0.0"),
    }
    policy = DependencyPolicy(
        groups=(
            CoherenceGroup(
                id="g1",
                repos=("acme/py-a", "acme/py-b"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
        )
    )
    result = _run(tmp_path, dependency_evidence=dependency_evidence, dependency_policy=policy)
    by_repo = {r["repo"]: r for r in result["repos"]}
    py_b = by_repo["acme/py-b"]
    # documentation earns "unknown" (no file evidence supplied) and is
    # excluded from `total`; fleet check earned 0 of its weight (status=fail)
    # but its weight must still count toward `total` — the placeholder's
    # "unknown" would have been excluded from `total` entirely (unknown is
    # not a scored status), so a stale score here would silently
    # under-report `total` instead of adding a 0-scoring `fail` to it.
    assert py_b["checks"]["documentation"]["status"] == "unknown"
    fleet_weight = py_b["checks"]["fleet_dependency_coherence"]["weight"]
    local_weight = py_b["checks"]["python_manifest_lock_consistency"]["weight"]
    assert py_b["total"] == pytest.approx(fleet_weight + local_weight)
    assert py_b["checks"]["fleet_dependency_coherence"]["status"] == "fail"
    assert py_b["score"] == pytest.approx(local_weight)  # fail contributes 0


# --- missing policy -------------------------------------------------------------


def test_missing_policy_produces_stable_block_and_run_error(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a"),
    }
    result = _run(tmp_path, dependency_evidence=dependency_evidence, dependency_policy=None)
    by_repo = {r["repo"]: r for r in result["repos"]}
    block = by_repo["acme/py-a"]["checks"]["fleet_dependency_coherence"]
    assert block["status"] == "unknown"
    assert block["detail"] == "dependencies.yaml missing"
    assert block["data"]["reason_code"] == "missing_policy"
    assert result.get("errors")


def test_no_repo_selects_fleet_check_produces_complete_collector_with_empty_report(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a"),
        "acme/py-b": _python_evidence("acme/py-b"),
    }
    policy = DependencyPolicy(
        groups=(
            CoherenceGroup(
                id="g1",
                repos=("acme/py-a", "acme/py-b"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
        )
    )
    collector: dict = {}
    _run(
        tmp_path,
        dependency_evidence=dependency_evidence,
        dependency_policy=policy,
        dependency_collector=collector,
        with_fleet_check=False,
    )
    assert collector["records"]
    assert collector["repository_evaluations"]
    assert collector["groups"] == policy.groups
    assert collector["report"].findings == ()
    assert collector["report"].unresolved == ()


# --- overlapping groups ---------------------------------------------------------


def test_overlapping_groups_group_memberships_only_the_comparable_group(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a", locked_version="1.0.0"),
        "acme/py-b": _python_evidence("acme/py-b", locked_version="1.0.0"),
    }
    policy = DependencyPolicy(
        groups=(
            CoherenceGroup(
                id="comparable",
                repos=("acme/py-a", "acme/py-b"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
            CoherenceGroup(
                id="solo",
                repos=("acme/py-a", "acme/node-a"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
        )
    )
    collector: dict = {}
    _run(
        tmp_path,
        dependency_evidence=dependency_evidence,
        dependency_policy=policy,
        dependency_collector=collector,
    )
    summaries = {s.repo: s for s in collector["repository_evaluations"] if s.ecosystem == "python"}
    assert summaries["acme/py-a"].group_memberships == ("comparable", "solo")
    assert summaries["acme/py-b"].group_memberships == ("comparable",)

    coverage = reconcile_coverage(collector["repository_evaluations"], collector["groups"])
    assert coverage.groups_with_insufficient_members == ("solo",)


# --- collector/coverage reconciliation identity + idempotence -----------------


def test_collector_and_durable_coverage_reconcile_identically(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a", locked_version="1.0.0"),
        "acme/py-b": _python_evidence("acme/py-b", locked_version="2.0.0"),
    }
    policy = DependencyPolicy(
        groups=(
            CoherenceGroup(
                id="g1",
                repos=("acme/py-a", "acme/py-b"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
        )
    )
    collector: dict = {}
    result = _run(
        tmp_path,
        dependency_evidence=dependency_evidence,
        dependency_policy=policy,
        dependency_collector=collector,
    )
    recomputed = reconcile_coverage(collector["repository_evaluations"], collector["groups"])
    assert result["coverage"]["dependencies"] == {
        "repositories_selected": recomputed.repositories_selected,
        "repositories_grouped": recomputed.repositories_grouped,
        "repositories_ungrouped": recomputed.repositories_ungrouped,
        "groups_with_insufficient_members": list(recomputed.groups_with_insufficient_members),
        "packages_matched": recomputed.packages_matched,
        "packages_unmatched": recomputed.packages_unmatched,
        "unsupported_by_adapter": dict(recomputed.unsupported_by_adapter),
    }


def test_evaluate_fleet_is_idempotent_across_repeated_calls(tmp_path):
    dependency_evidence = {
        "acme/py-a": _python_evidence("acme/py-a", locked_version="1.0.0"),
        "acme/py-b": _python_evidence("acme/py-b", locked_version="2.0.0"),
    }
    policy = DependencyPolicy(
        groups=(
            CoherenceGroup(
                id="g1",
                repos=("acme/py-a", "acme/py-b"),
                packages=("python:requests",),
                exclude_packages=(),
                policy="same-minor",
            ),
        )
    )
    result_a = _run(
        tmp_path, dependency_evidence=copy.deepcopy(dependency_evidence), dependency_policy=policy
    )
    result_b = _run(
        tmp_path, dependency_evidence=copy.deepcopy(dependency_evidence), dependency_policy=policy
    )
    assert result_a == result_b


# --- placeholder integrity guard -----------------------------------------------


def test_missing_placeholder_raises(tmp_path, monkeypatch):
    # Simulate a placeholder that never got built by making dispatch skip the
    # fleet check entirely for one repo while fleet_coherence_selected_repos
    # still reports it selected (an internal-consistency violation).
    monkeypatch.setattr(
        "lib.pulse.scripts.healthcheck_dispatch.fleet_coherence_selected_repos",
        lambda config: {"acme/py-a", "acme/does-not-exist"},
    )
    dependency_evidence = {"acme/py-a": _python_evidence("acme/py-a")}
    policy = DependencyPolicy(groups=())
    # acme/does-not-exist has no repo_dict at all — the loop just skips it
    # (no KeyError), but a repo present WITHOUT a real placeholder must raise.
    # Force that by disabling the fleet check in the scorecard while the
    # scan still (incorrectly) reports it selected for acme/py-a too.
    with pytest.raises(Exception):
        evaluate_fleet(
            evidence=_evidence_doc(["acme/py-a"]),
            profiles_path=_write_profiles(tmp_path / "profiles.yaml", with_fleet_check=False),
            workspace=tmp_path,
            dependency_evidence=dependency_evidence,
            dependency_policy=policy,
        )
