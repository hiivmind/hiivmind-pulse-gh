"""Tests for the mutation proposal shape and transformation registry."""

import pytest

from lib.pulse.scripts import mutation_plan


def minimal_registry_data():
    return {
        "transformations": {
            "format-python": {
                "id": "format-python",
                "command_argv": ["ruff", "format", "."],
                "applies_to": ["profile:python"],
                "validation": {"kind": "none"},
                "allow_scheduled": True,
            },
            "interactive-only": {
                "id": "interactive-only",
                "command_argv": ["make", "risky"],
                "applies_to": ["always"],
                "validation": {"kind": "none"},
                "allow_scheduled": False,
            },
        }
    }


def minimal_actor(mode="interactive"):
    return {"gh_login": "octocat", "machine": "laptop", "mode": mode}


# --- registry loading -----------------------------------------------------


def test_loads_valid_registry():
    registry = mutation_plan.load_registry(minimal_registry_data())

    entry = registry.get("format-python")
    assert entry.command_argv == ("ruff", "format", ".")
    assert entry.applies_to == ("profile:python",)
    assert entry.allow_scheduled is True
    assert entry.validation.kind == "none"


def test_loads_registry_from_yaml_file(tmp_path):
    import yaml

    path = tmp_path / "transformations.yaml"
    path.write_text(yaml.safe_dump(minimal_registry_data(), sort_keys=False))

    registry = mutation_plan.load_registry(path)

    assert set(registry.transformations) == {"format-python", "interactive-only"}


def test_missing_registry_file_raises():
    with pytest.raises(mutation_plan.MutationPlanError, match="not found"):
        mutation_plan.load_registry("/nonexistent/transformations.yaml")


def test_registry_rejects_non_mapping_root():
    with pytest.raises(mutation_plan.MutationPlanError, match="path or a mapping"):
        mutation_plan.load_registry([])


def test_registry_rejects_non_mapping_root_from_yaml_file(tmp_path):
    path = tmp_path / "transformations.yaml"
    path.write_text("- not\n- a\n- mapping\n")
    with pytest.raises(mutation_plan.MutationPlanError, match="must be a mapping"):
        mutation_plan.load_registry(path)


def test_registry_rejects_unknown_top_level_key():
    data = minimal_registry_data()
    data["extra"] = {}
    with pytest.raises(mutation_plan.MutationPlanError, match="unknown registry key"):
        mutation_plan.load_registry(data)


def test_registry_entry_id_must_match_key():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["id"] = "something-else"
    with pytest.raises(mutation_plan.MutationPlanError, match="must match its registry key"):
        mutation_plan.load_registry(data)


def test_registry_rejects_empty_command_argv():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["command_argv"] = []
    with pytest.raises(mutation_plan.MutationPlanError, match="non-empty list"):
        mutation_plan.load_registry(data)


def test_registry_rejects_nested_argv_element():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["command_argv"] = ["ruff", ["format"]]
    with pytest.raises(mutation_plan.MutationPlanError, match=r"command_argv\[1\] must be a string"):
        mutation_plan.load_registry(data)


def test_registry_rejects_boolean_argv_element():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["command_argv"] = ["ruff", True]
    with pytest.raises(mutation_plan.MutationPlanError, match=r"command_argv\[1\] must be a string"):
        mutation_plan.load_registry(data)


def test_registry_rejects_empty_applies_to():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["applies_to"] = []
    with pytest.raises(mutation_plan.MutationPlanError, match="applies_to must be non-empty"):
        mutation_plan.load_registry(data)


def test_registry_rejects_invalid_applies_to_predicate():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["applies_to"] = ["nonsense"]
    with pytest.raises(mutation_plan.MutationPlanError, match="invalid predicate"):
        mutation_plan.load_registry(data)


def test_registry_accepts_capability_and_evidence_path_predicates():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["applies_to"] = [
        "capability:ci",
        "evidence_path:**/*.py",
    ]
    registry = mutation_plan.load_registry(data)
    assert registry.get("format-python").applies_to == (
        "capability:ci",
        "evidence_path:**/*.py",
    )


def test_registry_rejects_non_boolean_allow_scheduled():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["allow_scheduled"] = "yes"
    with pytest.raises(mutation_plan.MutationPlanError, match="allow_scheduled must be a boolean"):
        mutation_plan.load_registry(data)


def test_registry_rejects_unknown_validation_kind():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["validation"] = {"kind": "vibes"}
    with pytest.raises(mutation_plan.MutationPlanError, match="validation.kind invalid"):
        mutation_plan.load_registry(data)


def test_registry_json_schema_validation_requires_path_and_schema():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["validation"] = {"kind": "json_schema"}
    with pytest.raises(mutation_plan.MutationPlanError, match="validation.path"):
        mutation_plan.load_registry(data)


def test_registry_json_schema_validation_loads_path_and_schema():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["validation"] = {
        "kind": "json_schema",
        "path": "package.json",
        "schema": {"type": "object"},
    }
    registry = mutation_plan.load_registry(data)
    validation = registry.get("format-python").validation
    assert validation.kind == "json_schema"
    assert validation.path == "package.json"
    assert validation.schema == {"type": "object"}


def test_registry_get_unknown_transformation_raises():
    registry = mutation_plan.load_registry(minimal_registry_data())
    with pytest.raises(mutation_plan.MutationPlanError, match="unknown transformation"):
        registry.get("does-not-exist")


# --- applicability ----------------------------------------------------


def test_transformation_applies_matches_profile_predicate():
    registry = mutation_plan.load_registry(minimal_registry_data())
    entry = registry.get("format-python")

    assert mutation_plan.transformation_applies(entry, profiles=("python",)) is True
    assert mutation_plan.transformation_applies(entry, profiles=("nodejs",)) is False


def test_transformation_applies_always_matches_regardless_of_evidence():
    registry = mutation_plan.load_registry(minimal_registry_data())
    entry = registry.get("interactive-only")

    assert mutation_plan.transformation_applies(entry) is True


def test_transformation_applies_matches_capability_and_evidence_path():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["applies_to"] = [
        "capability:ci",
        "evidence_path:**/*.py",
    ]
    entry = mutation_plan.load_registry(data).get("format-python")

    assert mutation_plan.transformation_applies(entry, capabilities=("ci",)) is True
    assert (
        mutation_plan.transformation_applies(entry, evidence_paths=("src/app.py",)) is True
    )
    assert mutation_plan.transformation_applies(entry, evidence_paths=("README.md",)) is False


# --- argv resolution: shell metacharacters stay literal --------------------


def test_resolve_argv_returns_registered_argv_verbatim():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["command_argv"] = [
        "sh",
        "-c",
        "$(rm -rf /)",
    ]
    entry = mutation_plan.load_registry(data).get("format-python")

    argv = mutation_plan.resolve_argv(entry)

    # The dangerous-looking element is passed through as an opaque literal
    # string — it is never interpreted, expanded, or substituted.
    assert argv == ("sh", "-c", "$(rm -rf /)")


@pytest.mark.parametrize(
    "dangerous",
    [
        "$(rm -rf /)",
        "; rm -rf /",
        "`rm -rf /`",
        "$HOME && rm -rf /",
        "a; b | c",
    ],
)
def test_resolve_argv_treats_shell_metacharacters_as_literal_data(dangerous):
    data = minimal_registry_data()
    data["transformations"]["format-python"]["command_argv"] = ["echo", dangerous]
    entry = mutation_plan.load_registry(data).get("format-python")

    argv = mutation_plan.resolve_argv(entry)

    assert argv[-1] == dangerous


def test_resolve_argv_never_templates_proposal_data():
    """No proposal field ever flows into the argv — it is registry-only."""
    data = minimal_registry_data()
    data["transformations"]["format-python"]["command_argv"] = ["ruff", "format", "{repo}"]
    entry = mutation_plan.load_registry(data).get("format-python")

    argv = mutation_plan.resolve_argv(entry)

    # The literal placeholder text survives untouched - never substituted.
    assert argv == ("ruff", "format", "{repo}")


# --- proposal construction and validation ---------------------------------


def test_build_proposal_constructs_valid_proposal():
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api", "acme/web"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123", "acme/web": "def456"},
        actor=minimal_actor(),
    )

    assert proposal.id == "run-1"
    assert proposal.selection == ("acme/api", "acme/web")
    assert proposal.mutation_policy == "propose"
    assert proposal.actor.gh_login == "octocat"
    assert proposal.actor.mode == "interactive"


def test_build_proposal_defaults_mutation_policy_to_propose():
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(),
    )
    assert proposal.mutation_policy == "propose"


@pytest.mark.parametrize("policy", ["propose", "allow-listed", "allow"])
def test_build_proposal_accepts_all_mutation_policy_values(policy):
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(),
        mutation_policy=policy,
    )
    assert proposal.mutation_policy == policy


def test_build_proposal_rejects_invalid_mutation_policy():
    with pytest.raises(mutation_plan.MutationPlanError, match="mutation_policy invalid"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api"],
            transformation="format-python",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(),
            mutation_policy="yolo",
        )


def test_build_proposal_rejects_empty_selection():
    with pytest.raises(mutation_plan.MutationPlanError, match="selection must be non-empty"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=[],
            transformation="format-python",
            expected_shas={},
            actor=minimal_actor(),
        )


def test_build_proposal_rejects_malformed_repo_name():
    with pytest.raises(mutation_plan.MutationPlanError, match="must be owner/name"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["not-owner-slash-name"],
            transformation="format-python",
            expected_shas={"not-owner-slash-name": "abc123"},
            actor=minimal_actor(),
        )


def test_build_proposal_rejects_duplicate_selection_entries():
    with pytest.raises(mutation_plan.MutationPlanError, match="duplicate"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api", "acme/api"],
            transformation="format-python",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(),
        )


def test_build_proposal_rejects_missing_expected_sha_for_selected_repo():
    with pytest.raises(mutation_plan.MutationPlanError, match="expected_shas missing entry"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api", "acme/web"],
            transformation="format-python",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(),
        )


def test_build_proposal_rejects_expected_sha_outside_selection():
    with pytest.raises(mutation_plan.MutationPlanError, match="entry outside selection"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api"],
            transformation="format-python",
            expected_shas={"acme/api": "abc123", "acme/other": "zzz"},
            actor=minimal_actor(),
        )


def test_build_proposal_rejects_invalid_actor_mode():
    with pytest.raises(mutation_plan.MutationPlanError, match="actor.mode invalid"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api"],
            transformation="format-python",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(mode="whenever"),
        )


def test_build_proposal_accepts_actor_dataclass_directly():
    actor = mutation_plan.Actor(gh_login="octocat", machine="laptop", mode="interactive")
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=actor,
    )
    assert proposal.actor is actor


# --- registry-backed validation: unknown transformation, scheduled gating -


def test_build_proposal_with_registry_rejects_unknown_transformation():
    registry = mutation_plan.load_registry(minimal_registry_data())
    with pytest.raises(mutation_plan.MutationPlanError, match="unknown transformation"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api"],
            transformation="does-not-exist",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(),
            registry=registry,
        )


def test_validate_proposal_rejects_unknown_transformation():
    registry = mutation_plan.load_registry(minimal_registry_data())
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(),
    )
    # Mutate to reference an unregistered transformation post-construction.
    forged = mutation_plan.Proposal(
        id=proposal.id,
        selection=proposal.selection,
        transformation="does-not-exist",
        expected_shas=proposal.expected_shas,
        mutation_policy=proposal.mutation_policy,
        actor=proposal.actor,
    )
    with pytest.raises(mutation_plan.MutationPlanError, match="unknown transformation"):
        mutation_plan.validate_proposal(forged, registry)


def test_scheduled_actor_allowed_for_allow_scheduled_transformation():
    registry = mutation_plan.load_registry(minimal_registry_data())
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(mode="scheduled"),
        registry=registry,
    )
    assert proposal.actor.mode == "scheduled"


def test_scheduled_actor_disallowed_for_non_scheduled_transformation():
    registry = mutation_plan.load_registry(minimal_registry_data())
    with pytest.raises(mutation_plan.MutationPlanError, match="not allowed in scheduled mode"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api"],
            transformation="interactive-only",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(mode="scheduled"),
            registry=registry,
        )


def test_interactive_actor_allowed_for_non_scheduled_transformation():
    registry = mutation_plan.load_registry(minimal_registry_data())
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="interactive-only",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(mode="interactive"),
        registry=registry,
    )
    assert proposal.transformation == "interactive-only"


# --- bound_paths & paths_changed validation -------------------------------


def test_registry_paths_changed_validation_loads_kind():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["validation"] = {"kind": "paths_changed"}
    registry = mutation_plan.load_registry(data)
    validation = registry.get("format-python").validation
    assert validation.kind == "paths_changed"
    assert validation.path is None
    assert validation.schema is None


def test_registry_paths_changed_validation_rejects_extra_fields():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["validation"] = {
        "kind": "paths_changed",
        "path": "some/path",
    }
    with pytest.raises(mutation_plan.MutationPlanError, match="takes no path/schema"):
        mutation_plan.load_registry(data)


def test_build_proposal_accepts_and_normalizes_bound_paths():
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(),
        bound_paths={"acme/api": ["docs/a.md", ".generated/docs/**"]},
    )
    assert proposal.bound_paths == {"acme/api": ("docs/a.md", ".generated/docs/**")}


def test_build_proposal_rejects_bound_paths_key_outside_selection():
    with pytest.raises(mutation_plan.MutationPlanError, match="entry outside selection"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api"],
            transformation="format-python",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(),
            bound_paths={"acme/api": ["docs/a.md"], "acme/other": ["x"]},
        )


def test_validate_proposal_enforces_bound_paths_covers_selection_for_paths_changed():
    data = minimal_registry_data()
    data["transformations"]["format-python"]["validation"] = {"kind": "paths_changed"}
    registry = mutation_plan.load_registry(data)

    # Missing bound_paths entry for selected repo acme/api
    with pytest.raises(mutation_plan.MutationPlanError, match="missing entry for"):
        mutation_plan.build_proposal(
            id="run-1",
            selection=["acme/api"],
            transformation="format-python",
            expected_shas={"acme/api": "abc123"},
            actor=minimal_actor(),
            registry=registry,
        )

    # Valid when bound_paths covers selection
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(),
        bound_paths={"acme/api": ["docs/a.md"]},
        registry=registry,
    )
    assert proposal.bound_paths == {"acme/api": ("docs/a.md",)}


def test_validate_proposal_allows_absent_bound_paths_for_none_kind():
    data = minimal_registry_data()
    registry = mutation_plan.load_registry(data)
    proposal = mutation_plan.build_proposal(
        id="run-1",
        selection=["acme/api"],
        transformation="format-python",
        expected_shas={"acme/api": "abc123"},
        actor=minimal_actor(),
        registry=registry,
    )
    assert proposal.bound_paths == {}

