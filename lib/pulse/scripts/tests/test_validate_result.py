"""Tests for validate_result.py — pulse headless result contract validation."""
import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts.evaluate_checks import (
    aggregate_by_scorecard,
    fleet_coverage,
    score_checks,
)

SCRIPT = "lib/pulse/scripts/validate_result.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures")
KINDS = [
    "status", "healthcheck", "refresh", "workflow-run", "fleet-membership",
    "impact", "repo-mutation",
]


def run_validator(path, kind):
    return subprocess.run(
        [sys.executable, SCRIPT, str(path), "--kind", kind],
        capture_output=True, text=True,
    )


def reconcile_healthcheck_summaries(doc):
    for repo in doc["repos"]:
        summary = score_checks(repo["checks"])
        repo.update(
            score=summary.score,
            total=summary.total,
            grade=summary.grade,
            coverage_supported=summary.coverage_supported,
            coverage_total=summary.coverage_total,
        )
    doc["aggregate"]["by_scorecard"] = aggregate_by_scorecard(doc["repos"])
    doc["coverage"].update(fleet_coverage(doc["repos"]))


@pytest.mark.parametrize("kind", KINDS)
def test_valid_fixture_passes(kind):
    r = run_validator(FIXTURES / f"{kind}-valid.yaml", kind)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("kind", KINDS)
def test_invalid_fixture_fails_with_errors(kind):
    r = run_validator(FIXTURES / f"{kind}-invalid.yaml", kind)
    assert r.returncode == 1
    assert r.stderr.strip(), "expected one error per line on stderr"


def test_kind_mismatch(tmp_path):
    r = run_validator(FIXTURES / "status-valid.yaml", "refresh")
    assert r.returncode == 1
    assert "kind mismatch" in r.stderr


def test_missing_actor_reported():
    r = run_validator(FIXTURES / "status-invalid.yaml", "status")
    assert "actor" in r.stderr


def test_missing_file_exit_2(tmp_path):
    r = run_validator(tmp_path / "nope.yaml", "status")
    assert r.returncode == 2


def test_unparseable_yaml_exit_2(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("kind: [unclosed")
    r = run_validator(bad, "status")
    assert r.returncode == 2


@pytest.mark.parametrize(
    "status",
    ["pass", "warn", "fail", "unknown", "not_applicable", "unsupported", "error"],
)
def test_healthcheck_accepts_exact_profile_states(tmp_path, status):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["repos"][0]["checks"]["branch_protection"]["status"] = status
    reconcile_healthcheck_summaries(doc)
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 0, result.stderr


def test_healthcheck_rejects_legacy_dismissed_state(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["repos"][0]["checks"]["branch_protection"]["status"] = "dismissed"
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "status invalid: dismissed" in result.stderr


def test_healthcheck_requires_scorecard_coverage_and_check_identity(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    repo = doc["repos"][0]
    repo.pop("scorecard", None)
    repo.pop("coverage_supported", None)
    repo.pop("coverage_total", None)
    for check in repo["checks"].values():
        check.pop("check_id", None)
        check.pop("adapter", None)
        check.pop("weight", None)
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "scorecard" in result.stderr
    assert "coverage_supported" in result.stderr
    assert "check_id" in result.stderr
    assert "adapter" in result.stderr
    assert "weight" in result.stderr


def test_healthcheck_requires_fleet_coverage(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc.pop("coverage")
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "missing required key: coverage" in result.stderr


def test_healthcheck_rejects_duplicate_repository_identity(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["repos"].append(copy.deepcopy(doc["repos"][0]))
    reconcile_healthcheck_summaries(doc)
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "duplicate repository identity: testorg/widget" in result.stderr


@pytest.mark.parametrize(
    ("container", "key"),
    [
        ("top", "score"),
        ("top", "total"),
        ("top", "grade"),
        ("top", "aggregate_score"),
        ("top", "aggregate_total"),
        ("top", "aggregate_grade"),
        ("aggregate", "score"),
        ("aggregate", "total"),
        ("aggregate", "grade"),
        ("aggregate", "aggregate_score"),
        ("aggregate", "aggregate_total"),
        ("aggregate", "aggregate_grade"),
    ],
)
def test_healthcheck_rejects_mixed_fleet_grade_keys(tmp_path, container, key):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    target = doc if container == "top" else doc["aggregate"]
    target[key] = 100
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert f"forbidden mixed fleet grade key: {container}.{key}" in result.stderr


def test_healthcheck_allows_unrelated_common_contract_fields(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["metadata"] = {"scheduler": "nightly"}
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 0, result.stderr


def test_healthcheck_governance_template_uses_only_new_last_run_fields():
    template = yaml.safe_load(Path("templates/healthcheck.yaml.template").read_text())

    assert template["last_run"] == {
        "run_at": None,
        "by_scorecard": {},
        "coverage": {
            "checks_total": 0,
            "checks_supported": 0,
            "unsupported_by_adapter": {},
            "unprofiled_repos": [],
        },
    }


def test_healthcheck_requires_scorecard_aggregate_fields(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    entry = doc["aggregate"]["by_scorecard"]["github-governance-v1"]
    entry.pop("repos")
    entry.pop("repos_scored")
    entry.pop("average_percent")
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "aggregate.by_scorecard.github-governance-v1.repos" in result.stderr
    assert "aggregate.by_scorecard.github-governance-v1.repos_scored" in result.stderr
    assert "aggregate.by_scorecard.github-governance-v1.average_percent" in result.stderr


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("coverage", "checks_total"), True),
        (("coverage", "checks_supported"), -1),
        (("coverage", "unsupported_by_adapter", "generic.docs"), 1.5),
        (
            (
                "aggregate",
                "by_scorecard",
                "github-governance-v1",
                "average_percent",
            ),
            "100",
        ),
    ],
)
def test_healthcheck_rejects_invalid_fleet_summary_types(tmp_path, path, value):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result_path = tmp_path / "healthcheck.yaml"
    result_path.write_text(yaml.safe_dump(doc))

    result = run_validator(result_path, "healthcheck")

    assert result.returncode == 1


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("repos", 0, "coverage_total"), True),
        (("repos", 0, "checks", "branch_protection", "weight"), -1),
    ],
)
def test_healthcheck_rejects_invalid_numeric_metadata(tmp_path, path, value):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result_path = tmp_path / "healthcheck.yaml"
    result_path.write_text(yaml.safe_dump(doc))

    result = run_validator(result_path, "healthcheck")

    assert result.returncode == 1
    assert "non-negative number" in result.stderr


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("repos", 0, "score"), float("nan")),
        (("repos", 0, "total"), float("inf")),
        (("repos", 0, "coverage_supported"), float("-inf")),
        (("repos", 0, "coverage_total"), float("nan")),
        (("repos", 0, "checks", "branch_protection", "weight"), float("inf")),
        (
            (
                "aggregate",
                "by_scorecard",
                "github-governance-v1",
                "average_percent",
            ),
            float("nan"),
        ),
    ],
)
def test_healthcheck_rejects_nonfinite_numbers(tmp_path, path, value):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result_path = tmp_path / "healthcheck.yaml"
    result_path.write_text(yaml.safe_dump(doc))

    result = run_validator(result_path, "healthcheck")

    assert result.returncode == 1
    assert "finite" in result.stderr


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda doc: doc["repos"][0].update(score=4), "score must not exceed total"),
        (
            lambda doc: doc["repos"][0].update(coverage_supported=4),
            "coverage_supported must not exceed coverage_total",
        ),
        (
            lambda doc: doc["coverage"].update(checks_supported=4),
            "checks_supported must not exceed checks_total",
        ),
        (
            lambda doc: doc["aggregate"]["by_scorecard"][
                "github-governance-v1"
            ].update(repos_scored=2),
            "repos_scored must not exceed repos",
        ),
        (
            lambda doc: doc["aggregate"]["by_scorecard"][
                "github-governance-v1"
            ].update(average_percent=100.1),
            "average_percent must be between 0 and 100",
        ),
        (
            lambda doc: doc["aggregate"]["by_scorecard"][
                "github-governance-v1"
            ].update(average_percent=-0.1),
            "average_percent must be between 0 and 100",
        ),
    ],
)
def test_healthcheck_rejects_cross_field_numeric_invariant(tmp_path, mutate, message):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    mutate(doc)
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert message in result.stderr


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        (None, "missing required key"),
        ([], "expected mapping"),
        ({"paths": "README.md", "refs": []}, "paths"),
        ({"paths": [], "refs": [42]}, "refs[0]"),
    ],
)
def test_healthcheck_requires_typed_check_evidence_citations(
    tmp_path, evidence, message
):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    data = doc["repos"][0]["checks"]["branch_protection"]["data"]
    if evidence is None:
        data.pop("evidence")
    else:
        data["evidence"] = evidence
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert message in result.stderr


def test_healthcheck_rejects_extra_check_evidence_citation_key(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    evidence = doc["repos"][0]["checks"]["branch_protection"]["data"][
        "evidence"
    ]
    evidence["urls"] = ["https://example.test/forged"]
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "data.evidence keys must be exactly paths, refs" in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", 0),
        ("total", 0),
        ("grade", "A"),
        ("coverage_supported", 0),
        ("coverage_total", 0),
    ],
)
def test_healthcheck_rejects_repo_summary_not_derived_from_checks(
    tmp_path, field, value
):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["repos"][0][field] = value
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert f"repos[0].{field} does not match checks" in result.stderr


def test_healthcheck_rejects_forged_zero_over_zero_grade_a(tmp_path):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["repos"][0].update(score=0, total=0, grade="A")
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "repos[0].grade does not match checks" in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [("repos", 2), ("repos_scored", 0), ("average_percent", 49.99)],
)
def test_healthcheck_rejects_scorecard_aggregate_not_derived_from_repos(
    tmp_path, field, value
):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["aggregate"]["by_scorecard"]["github-governance-v1"][field] = value
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert (
        f"aggregate.by_scorecard.github-governance-v1.{field} "
        "does not match repos"
    ) in result.stderr


@pytest.mark.parametrize("group", ["missing", "extra"])
def test_healthcheck_rejects_missing_or_extra_scorecard_group(tmp_path, group):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    groups = doc["aggregate"]["by_scorecard"]
    if group == "missing":
        groups.pop("github-governance-v1")
    else:
        groups["forged-v1"] = {
            "repos": 0,
            "repos_scored": 0,
            "average_percent": None,
        }
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert f"{group} aggregate.by_scorecard group" in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [("checks_total", 4), ("checks_supported", 2)],
)
def test_healthcheck_rejects_fleet_counts_not_derived_from_checks(
    tmp_path, field, value
):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["coverage"][field] = value
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert f"coverage.{field} does not match repo checks" in result.stderr


def test_healthcheck_rejects_unsupported_adapter_mapping_not_derived_from_checks(
    tmp_path,
):
    doc = yaml.safe_load((FIXTURES / "healthcheck-valid.yaml").read_text())
    doc["coverage"]["unsupported_by_adapter"] = {"generic.docs": 1}
    path = tmp_path / "healthcheck.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "healthcheck")

    assert result.returncode == 1
    assert "coverage.unsupported_by_adapter does not match repo checks" in result.stderr


def test_membership_explanation_requires_inferred_marker(tmp_path):
    doc = yaml.safe_load((FIXTURES / "fleet-membership-valid.yaml").read_text())
    doc["profile_proposals"][0]["explanation"] = "Inferred explanation"
    path = tmp_path / "fleet-membership.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "fleet-membership")

    assert result.returncode == 1
    assert "inferred: true" in result.stderr


def test_impact_rejects_invalid_edge_state(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    doc["edges"][0]["state"] = "broken"
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 1
    assert "state invalid: broken" in result.stderr


@pytest.mark.parametrize("state", ["current", "stale", "unknown"])
def test_impact_accepts_exact_edge_states(tmp_path, state):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    doc["edges"][0]["state"] = state
    doc["edges_stale"] = sum(1 for e in doc["edges"] if e["state"] == "stale")
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 0, result.stderr


def test_impact_rejects_edges_checked_not_derived_from_edges(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    doc["edges_checked"] = 5
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 1
    assert "edges_checked does not match edges" in result.stderr


def test_impact_rejects_edges_stale_not_derived_from_edges(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    doc["edges_stale"] = 0
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 1
    assert "edges_stale does not match edges" in result.stderr


def test_impact_rejects_negative_markers_updated(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    doc["markers_updated"] = -1
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 1
    assert "markers_updated must be a non-negative integer" in result.stderr


def test_impact_rejects_duplicate_edge_identity(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    dup = copy.deepcopy(doc["edges"][0])
    doc["edges"].append(dup)
    doc["edges_checked"] = len(doc["edges"])
    doc["edges_stale"] = sum(1 for e in doc["edges"] if e["state"] == "stale")
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 1
    assert "duplicate edge identity" in result.stderr


def test_impact_requires_edge_fields(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    edge = doc["edges"][0]
    edge.pop("dependent")
    edge.pop("upstream")
    edge.pop("watch_branch")
    edge.pop("changed_paths")
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 1
    assert "edges[0].dependent" in result.stderr
    assert "edges[0].upstream" in result.stderr
    assert "edges[0].watch_branch" in result.stderr
    assert "edges[0].changed_paths" in result.stderr


def test_impact_edge_tested_sha_and_remote_head_are_nullable(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    doc["edges"][0]["state"] = "unknown"
    doc["edges"][0]["tested_sha"] = None
    doc["edges"][0]["remote_head"] = None
    doc["edges_stale"] = sum(1 for e in doc["edges"] if e["state"] == "stale")
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 0, result.stderr


def test_repo_mutation_rejects_invalid_state(tmp_path):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    doc["state"] = "created"
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 1
    assert "state invalid: created" in result.stderr


@pytest.mark.parametrize("state", ["proposed", "blocked", "failed"])
def test_repo_mutation_accepts_exact_states(tmp_path, state):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    doc["state"] = state
    if state != "proposed":
        doc["reason"] = f"{state} for a reason"
        doc["repo_outcomes"] = {repo: state for repo in doc["selection"]}
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("state", ["blocked", "failed"])
def test_repo_mutation_requires_reason_when_blocked_or_failed(tmp_path, state):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    doc["state"] = state
    doc["reason"] = None
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 1
    assert "reason must not be null when state is blocked or failed" in result.stderr


def test_repo_mutation_allows_null_reason_when_proposed(tmp_path):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    assert doc["state"] == "proposed"
    assert doc["reason"] is None
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 0, result.stderr


def test_repo_mutation_rejects_invalid_repo_outcome_value(tmp_path):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    doc["repo_outcomes"]["testorg/core"] = "exploded"
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 1
    assert "repo_outcomes.testorg/core invalid: exploded" in result.stderr


@pytest.mark.parametrize(
    "field",
    [
        "state", "proposal_id", "transformation", "pen_name", "selection",
        "nave_version", "repo_outcomes", "reason",
    ],
)
def test_repo_mutation_requires_field(tmp_path, field):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    doc.pop(field)
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 1
    assert f"missing required key: {field}" in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", 1),
        ("proposal_id", 1),
        ("transformation", 1),
        ("pen_name", 1),
        ("selection", "not-a-list"),
        ("nave_version", 1),
        ("repo_outcomes", "not-a-mapping"),
        ("reason", 1),
    ],
)
def test_repo_mutation_rejects_wrong_type(tmp_path, field, value):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    doc[field] = value
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 1


def test_repo_mutation_selection_entries_must_be_strings(tmp_path):
    doc = yaml.safe_load((FIXTURES / "repo-mutation-valid.yaml").read_text())
    doc["selection"] = ["testorg/widget", 42]
    path = tmp_path / "repo-mutation.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "repo-mutation")

    assert result.returncode == 1
    assert "selection[1] is not a string" in result.stderr


def test_impact_legacy_string_edge_surfaces_as_unconfigured_finding(tmp_path):
    doc = yaml.safe_load((FIXTURES / "impact-valid.yaml").read_text())
    doc["findings"].append(
        {
            "kind": "unconfigured_edge",
            "repo": "testorg/widget",
            "severity": "low",
            "detail": "legacy string dependency carries no watch metadata",
        }
    )
    path = tmp_path / "impact.yaml"
    path.write_text(yaml.safe_dump(doc))

    result = run_validator(path, "impact")

    assert result.returncode == 0, result.stderr
