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

    out = evaluate("generic.documentation", evidence)

    assert out["status"] == "warn"
    assert out["detail"] == "README exists but no CONTRIBUTING.md and no docs/"
    assert out["data"]["evidence"] == {
        "paths": ["README.md"],
        "refs": ["f0:files"],
    }


def test_documentation_cites_the_observed_nested_docs_path():
    evidence = load_json(FIXTURES / "documentation-only" / "evidence.json")
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
    evidence["github"]["rulesets"] = [{"enforcement": "active"}]

    out = evaluate("github.branch_protection", evidence)

    assert out["status"] == "pass"
    assert out["detail"] == "Active ruleset on default branch"
    assert out["data"]["evidence"] == {
        "paths": [],
        "refs": ["github:repo", "github:protection", "github:rulesets"],
    }


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
