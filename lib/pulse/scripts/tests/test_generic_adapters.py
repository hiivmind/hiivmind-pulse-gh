"""Behavioral tests for universal GitHub healthcheck adapters."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from lib.pulse.scripts.adapters import register_universal_adapters
from lib.pulse.scripts.adapters import generic
from lib.pulse.scripts.check_adapters import AdapterRegistry, CheckContext


FIXTURES = Path(__file__).parent / "fixtures" / "checks"


def load_json(path: Path):
    return json.loads(path.read_text())


def evidence_from_legacy(name: str) -> dict:
    fixture = FIXTURES / name
    root = load_json(fixture / "root-contents.json")
    github = load_json(fixture / "github-contents.json")
    files = [entry["name"] for entry in root]
    files.extend(f".github/{entry['name']}" for entry in github)
    workflows = load_json(fixture / "workflows.json")
    if workflows["total_count"]:
        files.append(".github/workflows/ci.yml")
    governance = {
        "repo": load_json(fixture / "repo.json"),
        "protection": (
            load_json(fixture / "protection.json")
            if (fixture / "protection.json").exists()
            else None
        ),
        "rulesets": [],
    }
    return {
        "repo": f"testorg/{name}",
        "remote_sha": f"{name}-sha",
        "files": files,
        "files_complete": True,
        "structural_signals": [],
        "validation": {"state": "unknown", "errors": []},
        "github": governance,
    }


def context(adapter: str, evidence: dict) -> CheckContext:
    return CheckContext(
        repo=evidence.get("repo", "testorg/missing"),
        evidence=evidence,
        check={"id": adapter.rsplit(".", 1)[-1], "weight": 1},
        workspace=Path("/workspace/that/must/not/be/read"),
    )


def evaluate(adapter: str, evidence: dict) -> dict:
    registry = AdapterRegistry()
    register_universal_adapters(registry)
    return registry.evaluate(adapter, context(adapter, evidence))


@pytest.mark.parametrize(
    ("adapter", "status", "detail"),
    [
        ("generic.ci", "pass", "1 workflow(s) configured"),
        (
            "generic.documentation",
            "pass",
            "README ✓, docs/ or CONTRIBUTING ✓",
        ),
        ("generic.license", "pass", "MIT"),
        (
            "github.branch_protection",
            "pass",
            "Protected (1 required review(s), enforce_admins)",
        ),
        ("github.security_policy", "pass", "SECURITY.md present"),
    ],
)
def test_good_fixture_passes(adapter, status, detail):
    out = evaluate(adapter, evidence_from_legacy("good"))

    assert (out["status"], out["detail"]) == (status, detail)
    assert out["data"]["evidence"]["paths"] or out["data"]["evidence"]["refs"]


@pytest.mark.parametrize(
    "adapter",
    [
        "generic.ci",
        "generic.documentation",
        "generic.license",
        "github.branch_protection",
        "github.security_policy",
    ],
)
def test_bare_fixture_fails(adapter):
    assert evaluate(adapter, evidence_from_legacy("bare"))["status"] == "fail"


def test_documentation_only_fixture_warns():
    evidence = load_json(FIXTURES / "documentation-only" / "evidence.json")
    evidence["files_complete"] = True

    out = evaluate("generic.documentation", evidence)

    assert out["status"] == "warn"
    assert out["detail"] == "README exists but no CONTRIBUTING.md and no docs/"
    assert out["data"]["evidence"] == {
        "paths": ["README.md"],
        "refs": ["f0:files"],
    }


def test_documentation_cites_the_observed_nested_docs_path():
    evidence = load_json(FIXTURES / "documentation-only" / "evidence.json")
    evidence["files_complete"] = True
    evidence["files"].append("docs/index.md")

    out = evaluate("generic.documentation", evidence)

    assert out["status"] == "pass"
    assert out["data"]["evidence"]["paths"] == ["README.md", "docs/index.md"]


def test_incomplete_protection_warns():
    evidence = evidence_from_legacy("good")
    evidence["github"]["protection"] = {
        "enforce_admins": {"enabled": False},
        "required_pull_request_reviews": {
            "required_approving_review_count": 1
        },
    }

    out = evaluate("github.branch_protection", evidence)

    assert out["status"] == "warn"
    assert out["detail"] == (
        "Protection exists but enforce_admins: false, required reviews: 1"
    )


@pytest.mark.parametrize(
    "adapter",
    [
        "generic.ci",
        "generic.documentation",
        "generic.license",
        "github.branch_protection",
        "github.security_policy",
    ],
)
def test_missing_evidence_is_unknown(adapter):
    assert evaluate(adapter, {"repo": "testorg/missing"})["status"] == "unknown"


def test_active_ruleset_passes_without_legacy_protection():
    evidence = evidence_from_legacy("bare")
    evidence["github"]["repo"]["default_branch"] = "main"
    evidence["github"]["rulesets"] = [
        {
            "enforcement": "active",
            "target": "branch",
            "conditions": {
                "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
            },
        }
    ]

    out = evaluate("github.branch_protection", evidence)

    assert out["status"] == "pass"
    assert out["detail"] == "Active ruleset on default branch"
    assert out["data"]["evidence"] == {
        "paths": [],
        "refs": ["github:repo", "github:protection", "github:rulesets"],
    }


def test_active_list_summary_without_targeting_is_unknown():
    evidence = evidence_from_legacy("bare")
    evidence["github"]["repo"]["default_branch"] = "main"
    evidence["github"]["rulesets"] = [
        {
            "id": 17,
            "name": "release tags",
            "enforcement": "active",
            "target": "tag",
        }
    ]

    out = evaluate("github.branch_protection", evidence)

    assert out["status"] == "unknown"
    assert out["detail"] == "active ruleset targeting unavailable"


def test_hydrated_matching_ruleset_passes():
    evidence = evidence_from_legacy("bare")
    evidence["github"]["repo"]["default_branch"] = "main"
    evidence["github"]["rulesets"] = [
        {
            "id": 17,
            "name": "default protection",
            "enforcement": "active",
            "target": "branch",
            "conditions": {
                "ref_name": {
                    "include": ["~DEFAULT_BRANCH"],
                    "exclude": [],
                }
            },
        }
    ]

    assert evaluate("github.branch_protection", evidence)["status"] == "pass"


def test_hydrated_match_outweighs_another_incomplete_active_ruleset():
    evidence = _ruleset_evidence(
        {
            "id": 17,
            "enforcement": "active",
            "target": "branch",
            "conditions": {
                "ref_name": {
                    "include": ["~DEFAULT_BRANCH"],
                    "exclude": [],
                }
            },
        }
    )
    evidence["github"]["rulesets"].append(
        {"id": 23, "enforcement": "active"}
    )

    assert evaluate("github.branch_protection", evidence)["status"] == "pass"


@pytest.mark.parametrize(
    "adapter",
    [
        "generic.ci",
        "generic.documentation",
        "generic.license",
        "github.security_policy",
    ],
)
def test_observational_file_absence_is_unknown_with_evidence_gap(adapter):
    evidence = {
        "repo": "testorg/partial",
        "files": ["pyproject.toml"],
        "files_complete": False,
    }

    out = evaluate(adapter, evidence)

    assert out["status"] == "unknown"
    assert "evidence gap" in out["detail"].lower()
    assert out["data"]["evidence"]["refs"] == ["f0:files"]


def test_observed_readme_without_complete_file_list_is_unknown():
    out = evaluate(
        "generic.documentation",
        {"repo": "testorg/partial", "files": ["README.md"]},
    )

    assert out["status"] == "unknown"
    assert out["data"]["evidence"]["paths"] == ["README.md"]


def test_authoritative_null_github_license_is_fail_even_with_incomplete_files():
    out = evaluate(
        "generic.license",
        {
            "repo": "testorg/unlicensed",
            "files": ["pyproject.toml"],
            "files_complete": False,
            "github": {"repo": {"license": None}},
        },
    )

    assert out["status"] == "fail"
    assert out["data"]["evidence"]["refs"] == ["github:repo"]


def test_unrecognized_github_license_metadata_does_not_prove_presence():
    out = evaluate(
        "generic.license",
        {
            "repo": "testorg/custom-license",
            "files": ["pyproject.toml"],
            "files_complete": False,
            "github": {
                "repo": {
                    "license": {
                        "key": "other",
                        "name": "Other",
                        "spdx_id": "NOASSERTION",
                    }
                }
            },
        },
    )

    assert out["status"] == "unknown"


def _ruleset_evidence(ruleset, *, default_branch="main"):
    evidence = evidence_from_legacy("bare")
    evidence["github"]["repo"]["default_branch"] = default_branch
    evidence["github"]["rulesets"] = [ruleset]
    return evidence


def test_hydrated_tag_only_ruleset_with_explicit_null_protection_fails():
    evidence = _ruleset_evidence(
        {
            "id": 23,
            "name": "release tags",
            "enforcement": "active",
            "target": "tag",
            "conditions": {
                "ref_name": {"include": ["~ALL"], "exclude": []}
            },
        }
    )
    assert evidence["github"]["protection"] is None

    out = evaluate(
        "github.branch_protection",
        evidence,
    )

    assert out["status"] == "fail"


def test_ruleset_matching_explicit_default_branch_passes():
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {
                "enforcement": "active",
                "target": "branch",
                "conditions": {
                    "ref_name": {
                        "include": ["refs/heads/main"],
                        "exclude": [],
                    }
                },
            }
        ),
    )

    assert out["status"] == "pass"


@pytest.mark.parametrize(
    "pattern",
    ["refs/heads/ma*", "refs/heads/m??n", "refs/heads/**"],
)
def test_ruleset_matching_default_branch_glob_passes(pattern):
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {
                "enforcement": "active",
                "target": "branch",
                "conditions": {
                    "ref_name": {"include": [pattern], "exclude": []}
                },
            }
        ),
    )

    assert out["status"] == "pass"


@pytest.mark.parametrize(
    ("pattern", "expected_status"),
    [
        ("refs/heads/*", "fail"),
        ("refs/heads/**", "pass"),
    ],
)
def test_ruleset_wildcards_are_slash_aware_for_nested_branch_names(
    pattern, expected_status
):
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {
                "enforcement": "active",
                "target": "branch",
                "conditions": {
                    "ref_name": {"include": [pattern], "exclude": []}
                },
            },
            default_branch="release/v1",
        ),
    )

    assert out["status"] == expected_status


def test_ruleset_excluding_default_branch_does_not_pass():
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {
                "enforcement": "active",
                "target": "branch",
                "conditions": {
                    "ref_name": {
                        "include": ["~ALL"],
                        "exclude": ["~DEFAULT_BRANCH"],
                    }
                },
            }
        ),
    )

    assert out["status"] == "fail"


def test_ruleset_matching_exclusion_glob_overrides_all_include():
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {
                "enforcement": "active",
                "target": "branch",
                "conditions": {
                    "ref_name": {
                        "include": ["~ALL"],
                        "exclude": ["refs/heads/ma*"],
                    }
                },
            }
        ),
    )

    assert out["status"] == "fail"


@pytest.mark.parametrize(
    ("pattern", "expected_status"),
    [
        ("refs/heads/*", "pass"),
        ("refs/heads/**", "fail"),
    ],
)
def test_ruleset_exclusion_wildcards_are_slash_aware(
    pattern, expected_status
):
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {
                "enforcement": "active",
                "target": "branch",
                "conditions": {
                    "ref_name": {"include": ["~ALL"], "exclude": [pattern]}
                },
            },
            default_branch="release/v1",
        ),
    )

    assert out["status"] == expected_status


@pytest.mark.parametrize(
    "ref_name",
    [
        {"include": ["~FUTURE_TOKEN"], "exclude": []},
        {"include": ["~ALL"], "exclude": ["~FUTURE_TOKEN"]},
        {"include": ["refs/heads/[main"], "exclude": []},
        {"include": ["refs/heads/[mr]ain"], "exclude": []},
        {"include": ["~ALL"], "exclude": "refs/heads/release"},
    ],
)
def test_active_branch_ruleset_with_unknown_targeting_is_unknown(ref_name):
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {
                "enforcement": "active",
                "target": "branch",
                "conditions": {"ref_name": ref_name},
            }
        ),
    )

    assert out["status"] == "unknown"


def test_active_branch_ruleset_with_incomplete_conditions_is_unknown():
    out = evaluate(
        "github.branch_protection",
        _ruleset_evidence(
            {"enforcement": "active", "target": "branch"}
        ),
    )

    assert out["status"] == "unknown"


def test_archived_repository_uses_the_same_universal_checks():
    evidence = load_json(FIXTURES / "archived" / "evidence.json")

    assert evaluate("generic.ci", evidence)["status"] == "pass"
    assert evaluate("generic.license", evidence)["status"] == "pass"
    assert evaluate("github.security_policy", evidence)["status"] == "pass"
    assert evaluate("github.branch_protection", evidence)["status"] == "fail"


def test_compatibility_aliases_use_the_canonical_implementations():
    registry = AdapterRegistry()
    register_universal_adapters(registry)

    assert registry._adapters["generic.docs"] is generic.documentation
    assert registry._adapters["github.actions"] is generic.ci


def test_adapter_source_is_universal_and_data_only():
    source = inspect.getsource(generic)
    forbidden = tuple(
        bytes.fromhex(encoded).decode()
        for encoded in (
            "434c415544452e6d64",
            "2e636c617564652d706c7567696e",
            "736b696c6c732f",
        )
    )

    assert all(value not in source for value in forbidden)
    assert ".workspace" not in source
