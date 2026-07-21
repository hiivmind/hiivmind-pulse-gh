"""Contract checks for the corpus-overlay generator configuration.

The F9 v1 dogfood generator entry `hiivmind.corpus-navigate-skill` is the one
configured overlay under the F7 generic engine. These tests load the shipped
templates, prove they cross-validate, and exercise the generic engine
end-to-end on the corpus overlay — without touching any overlay-specific
engine code.
"""

from __future__ import annotations

import pytest

from lib.pulse.scripts import (
    generated_artifacts,
    generator_dispatch,
    mutation_plan,
)


GENERATORS_TEMPLATE = "templates/generators.yaml.template"
TRANSFORMATIONS_TEMPLATE = "templates/transformations.yaml.template"

CORPUS_ID = "hiivmind.corpus-navigate-skill"
CORPUS_TRANSFORMATION = "regenerate-corpus-navigate-skill"
CORPUS_TEMPLATE_PATH = "templates/corpus/navigate-skill.md.tmpl"
CORPUS_OUTPUT_PATH = "skills/hiivmind-corpus-navigate/SKILL.md"
SOURCE = "hiivmind/hiivmind-pulse-gh"
BRANCH = "main"


@pytest.fixture(scope="module")
def registry_and_generators():
    """Load the shipped registry + generators together; fail-closed on either."""
    registry = mutation_plan.load_registry(TRANSFORMATIONS_TEMPLATE)
    generators = generator_dispatch.load_generators(GENERATORS_TEMPLATE, registry)
    return registry, generators


def _binding(**overrides):
    base = {
        "id": "corpus-navigate-skill",
        "source": SOURCE,
        "branch": BRANCH,
        "template_path": CORPUS_TEMPLATE_PATH,
        "template_tree": "tree-A",
        "generator": CORPUS_ID,
        "files": [{"path": CORPUS_OUTPUT_PATH, "blob": "blob-A"}],
        "generated_at": "2026-07-22T10:00:00Z",
    }
    base.update(overrides)
    return base


def _actor():
    return {"gh_login": "octocat", "machine": "laptop", "mode": "interactive"}


# 1. Templates load & cross-validate ----------------------------------------


def test_templates_load_and_cross_validate(registry_and_generators):
    _, generators = registry_and_generators

    assert CORPUS_ID in generators
    gen = generators[CORPUS_ID]
    assert gen.transformation == CORPUS_TRANSFORMATION
    assert gen.applies_to == ("profile:claude-plugin",)
    assert gen.output_paths == (CORPUS_OUTPUT_PATH,)
    assert gen.source_paths == (CORPUS_TEMPLATE_PATH,)
    assert gen.validation.kind == "none"


# 2. audit → template-drift → proposal --------------------------------------


def test_audit_classifies_template_drift_and_returns_proposal(
    registry_and_generators,
):
    _, _ = registry_and_generators
    manifest = {"bindings": [_binding()]}

    snapshot = {
        SOURCE: {
            BRANCH: {
                "head": "headsha",
                "trees": {CORPUS_TEMPLATE_PATH: "tree-B"},
                "blobs": {CORPUS_OUTPUT_PATH: "blob-A"},
            }
        }
    }

    report = generated_artifacts.audit(manifest, snapshot)

    assert len(report.bindings) == 1
    result = report.bindings[0]
    assert result.state == "template-drift"
    assert result.proposal is not None
    assert result.proposal.new_tree == "tree-B"
    assert result.proposal.expected_tree == "tree-A"
    assert report.findings == []


# 3. audit → local-customization → no proposal ------------------------------


def test_audit_classifies_local_customization_without_proposal(
    registry_and_generators,
):
    _, _ = registry_and_generators
    manifest = {"bindings": [_binding()]}

    snapshot = {
        SOURCE: {
            BRANCH: {
                "head": "headsha",
                "trees": {CORPUS_TEMPLATE_PATH: "tree-A"},
                "blobs": {CORPUS_OUTPUT_PATH: "blob-B"},
            }
        }
    }

    report = generated_artifacts.audit(manifest, snapshot)

    assert len(report.bindings) == 1
    result = report.bindings[0]
    assert result.state == "local-customization"
    assert result.proposal is None
    assert any(f.kind == "local_customization" for f in report.findings)


# 4. dispatch builds a valid F6 proposal ------------------------------------


def test_dispatch_builds_valid_proposal_for_corpus_overlay(
    registry_and_generators,
):
    _, generators = registry_and_generators
    gen = generators[CORPUS_ID]

    binding = {
        "id": "corpus-navigate-skill",
        "source": SOURCE,
        "branch": BRANCH,
        "files": [{"path": CORPUS_OUTPUT_PATH}],
    }
    snapshot = {SOURCE: {BRANCH: {"head": "headsha"}}}

    proposal = generator_dispatch.dispatch(gen, binding, snapshot, _actor())

    assert isinstance(proposal, mutation_plan.Proposal)
    assert proposal.id == f"generate-{CORPUS_ID}-corpus-navigate-skill"
    assert proposal.selection == (SOURCE,)
    assert proposal.expected_shas == {SOURCE: "headsha"}
    assert proposal.transformation == CORPUS_TRANSFORMATION
    assert proposal.mutation_policy == "propose"
    assert proposal.actor.gh_login == "octocat"


# 5. output-allowlist enforcement -------------------------------------------


def test_dispatch_rejects_binding_file_outside_allowlist(registry_and_generators):
    _, generators = registry_and_generators
    gen = generators[CORPUS_ID]

    binding = {
        "id": "corpus-navigate-skill",
        "source": SOURCE,
        "branch": BRANCH,
        "files": [{"path": "README.md"}],
    }
    snapshot = {SOURCE: {BRANCH: {"head": "headsha"}}}

    with pytest.raises(mutation_plan.MutationPlanError) as exc:
        generator_dispatch.dispatch(gen, binding, snapshot, _actor())

    assert "README.md" in str(exc.value)
    assert "allowlist" in str(exc.value).lower() or "output_paths" in str(exc.value)


# 6. scheduled-actor gate (parity with the marketplace overlay) --------------


def test_corpus_transformation_rejects_scheduled_actor(registry_and_generators):
    """The corpus transformation is allow_scheduled: false, so a proposal built
    for a scheduled actor must be rejected by validate_proposal — parity with
    marketplace-entry-update. (generator_dispatch.dispatch does not itself gate
    on the registry; the scheduled gate lives in validate_proposal, enforced by
    pen_orchestrator at execution.)"""
    registry, generators = registry_and_generators
    gen = generators[CORPUS_ID]

    binding = {
        "id": "corpus-navigate-skill",
        "source": SOURCE,
        "branch": BRANCH,
        "files": [{"path": CORPUS_OUTPUT_PATH}],
    }
    snapshot = {SOURCE: {BRANCH: {"head": "headsha"}}}
    scheduled_actor = {"gh_login": "bot", "machine": "ci", "mode": "scheduled"}

    proposal = generator_dispatch.dispatch(gen, binding, snapshot, scheduled_actor)

    with pytest.raises(mutation_plan.MutationPlanError):
        mutation_plan.validate_proposal(proposal, registry)
