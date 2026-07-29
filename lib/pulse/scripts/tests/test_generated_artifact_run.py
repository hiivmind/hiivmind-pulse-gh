"""Tests for generated_artifact_run CLI driver and build_result composition."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lib.pulse.scripts import (
    generated_artifacts as ga,
    generator_dispatch,
    mutation_plan,
    validate_result,
)
from lib.pulse.scripts.tests.test_generated_artifacts import binding, manifest, snapshot_for

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_REGISTRY = REPO_ROOT / "templates" / "transformations.yaml.template"


def load_test_registry():
    return mutation_plan.load_registry(TEMPLATE_REGISTRY)


def load_test_generators(registry=None):
    registry = registry or load_test_registry()
    return generator_dispatch.load_generators(
        {
            "readme-from-template": {
                "id": "readme-from-template",
                "applies_to": ["always"],
                "transformation": "regenerate-from-template",
                "source_paths": ["templates/repo-readme.md"],
                "output_paths": ["README.md", "docs/**/*.md"],
                "validation": {"kind": "none"},
            }
        },
        registry,
    )


ACTOR = {"gh_login": "octocat", "machine": "test-mac", "mode": "interactive"}


# --- validate_manifest / build_result unit tests --------------------------------


def test_validate_manifest_accepts_well_formed():
    errors = ga.validate_manifest(manifest([binding()]))
    assert errors == []


def test_validate_manifest_rejects_missing_required_keys():
    bad = binding()
    del bad["template_tree"]
    errors = ga.validate_manifest(manifest([bad]))
    assert errors
    assert any("template_tree" in e for e in errors)


def test_validate_manifest_rejects_empty_files():
    errors = ga.validate_manifest(manifest([binding(files=[])]))
    assert errors
    assert any("files" in e.lower() for e in errors)


def test_validate_manifest_rejects_duplicate_file_paths():
    errors = ga.validate_manifest(
        manifest([
            binding(files=[
                {"path": "README.md", "blob": "b1"},
                {"path": "README.md", "blob": "b2"},
            ])
        ])
    )
    assert errors
    assert any("duplicate" in e.lower() for e in errors)


def test_validate_manifest_rejects_empty_path():
    errors = ga.validate_manifest(
        manifest([binding(files=[{"path": "", "blob": "b1"}])])
    )
    assert errors


def test_build_result_malformed_manifest_returns_validated_abort():
    registry = load_test_registry()
    generators = load_test_generators(registry)
    bad = binding()
    del bad["id"]

    res = ga.build_result(
        manifest([bad]),
        snapshot_for(),
        generators=generators,
        registry=registry,
        actor=ACTOR,
        mode="interactive",
    )

    assert res["kind"] == "generated-artifact"
    assert res["bindings_audited"] == 0
    assert res["states"] == {}
    assert res["proposals"] == []
    assert res["errors"]
    assert validate_result.validate(res, "generated-artifact") == []


def test_build_result_current_produces_no_proposal():
    registry = load_test_registry()
    generators = load_test_generators(registry)

    res = ga.build_result(
        manifest([binding()]),
        snapshot_for(),
        generators=generators,
        registry=registry,
        actor=ACTOR,
        mode="interactive",
    )

    assert res["bindings_audited"] == 1
    assert res["states"]["widget-readme"] == "current"
    assert res["proposals"] == []
    assert res["findings"] == []
    assert validate_result.validate(res, "generated-artifact") == []


def test_build_result_template_drift_interactive_proposal_summary_and_expected_shas():
    registry = load_test_registry()
    generators = load_test_generators(registry)
    gen = generators["readme-from-template"]
    b = binding()
    snap = snapshot_for(
        trees={"templates/repo-readme.md": "tree2222"},
        blobs={"README.md": "blob1111"},
    )
    # Snapshot must carry head for dispatch expected_shas
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"

    # Ephemeral full Proposal carries expected_shas (would pass execute guard)
    full = generator_dispatch.dispatch(
        gen, b, snap, dict(ACTOR, mode="interactive"), registry=registry
    )
    assert full.expected_shas == {"hiivmind/template-repo": "head999"}
    assert full.mutation_policy == "propose"

    res = ga.build_result(
        manifest([b]),
        snap,
        generators=generators,
        registry=registry,
        actor=ACTOR,
        mode="interactive",
    )

    assert res["states"]["widget-readme"] == "template-drift"
    assert len(res["proposals"]) == 1
    summary = res["proposals"][0]
    assert summary == {
        "binding": "widget-readme",
        "transformation": "regenerate-from-template",
        "proposal_id": "generate-readme-from-template-widget-readme",
    }
    assert "expected_shas" not in summary
    assert "selection" not in summary
    assert validate_result.validate(res, "generated-artifact") == []


def test_build_result_scheduled_gates_allow_scheduled_false():
    registry = load_test_registry()
    generators = load_test_generators(registry)
    b = binding()
    snap = snapshot_for(trees={"templates/repo-readme.md": "tree2222"})
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"
    scheduled_actor = dict(ACTOR, mode="scheduled")

    res = ga.build_result(
        manifest([b]),
        snap,
        generators=generators,
        registry=registry,
        actor=scheduled_actor,
        mode="scheduled",
    )

    assert res["states"]["widget-readme"] == "template-drift"
    assert res["proposals"] == []
    gated = [f for f in res["findings"] if f["kind"] == "gated_transformation"]
    assert len(gated) == 1
    assert "scheduled" in gated[0]["detail"].lower() or "allow_scheduled" in gated[0]["detail"].lower() or "not allowed" in gated[0]["detail"].lower()
    assert res["proposed_actions"]
    assert validate_result.validate(res, "generated-artifact") == []


def test_build_result_out_of_allowlist_becomes_finding_no_proposal():
    registry = load_test_registry()
    generators = load_test_generators(registry)
    # File path outside generator output_paths allowlist
    b = binding(files=[{"path": ".github/workflows/ci.yml", "blob": "blob1111"}])
    snap = snapshot_for(
        trees={"templates/repo-readme.md": "tree2222"},
        blobs={".github/workflows/ci.yml": "blob1111"},
    )
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"

    res = ga.build_result(
        manifest([b]),
        snap,
        generators=generators,
        registry=registry,
        actor=ACTOR,
        mode="interactive",
    )

    assert res["states"]["widget-readme"] == "template-drift"
    assert res["proposals"] == []
    assert any(
        f["kind"] in {"allowlist_violation", "dispatch_error"}
        or "allowlist" in (f.get("detail") or "").lower()
        or "output_paths" in (f.get("detail") or "").lower()
        for f in res["findings"]
    )
    assert validate_result.validate(res, "generated-artifact") == []


def test_build_result_local_customization_finding_no_proposal():
    registry = load_test_registry()
    generators = load_test_generators(registry)
    snap = snapshot_for(blobs={"README.md": "blob2222"})
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"

    res = ga.build_result(
        manifest([binding()]),
        snap,
        generators=generators,
        registry=registry,
        actor=ACTOR,
        mode="interactive",
    )

    assert res["states"]["widget-readme"] == "local-customization"
    assert res["proposals"] == []
    assert any(f["kind"] == "local_customization" for f in res["findings"])


def test_build_result_conflict_finding_no_proposal():
    registry = load_test_registry()
    generators = load_test_generators(registry)
    snap = snapshot_for(
        trees={"templates/repo-readme.md": "tree2222"},
        blobs={"README.md": "blob2222"},
    )
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"

    res = ga.build_result(
        manifest([binding()]),
        snap,
        generators=generators,
        registry=registry,
        actor=ACTOR,
        mode="interactive",
    )

    assert res["states"]["widget-readme"] == "conflict"
    assert res["proposals"] == []
    assert any(f["kind"] == "conflict" for f in res["findings"])


def test_build_result_error_state_copies_audit_finding():
    registry = load_test_registry()
    generators = load_test_generators(registry)
    snap = snapshot_for(blobs={"README.md": ga.ABSENT})
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"

    res = ga.build_result(
        manifest([binding()]),
        snap,
        generators=generators,
        registry=registry,
        actor=ACTOR,
        mode="interactive",
    )

    assert res["states"]["widget-readme"] == "error"
    assert res["proposals"] == []
    assert any(f["kind"] == "missing_output" for f in res["findings"])


# --- driver CLI ----------------------------------------------------------------


def create_test_workspace(
    tmp_path: Path,
    login: str = "acme",
    bindings: list[dict] | None = None,
) -> Path:
    ws = tmp_path / "workspace"
    config_dir = ws / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(yaml.dump({"workspace": {"login": login}}))
    if bindings is None:
        bindings = [binding()]
    (config_dir / "generated.yaml").write_text(
        yaml.dump({"bindings": bindings}, sort_keys=False)
    )
    # Local generators registry so driver does not need the corpus overlay generator
    (config_dir / "generators.yaml").write_text(
        yaml.dump({
            "generators": {
                "readme-from-template": {
                    "id": "readme-from-template",
                    "applies_to": ["always"],
                    "transformation": "regenerate-from-template",
                    "source_paths": ["templates/repo-readme.md"],
                    "output_paths": ["README.md", "docs/**/*.md"],
                    "validation": {"kind": "none"},
                }
            }
        })
    )
    (config_dir / "transformations.yaml").write_text(
        TEMPLATE_REGISTRY.read_text()
    )
    return ws


def test_driver_missing_workspace_aborts_and_validates(tmp_path):
    from lib.pulse.scripts import generated_artifact_run

    result_path = tmp_path / "result.yaml"
    rc = generated_artifact_run.run_driver(
        workspace=tmp_path / "nonexistent",
        repo_filter=None,
        result_path=result_path,
        mode="scheduled",
    )

    assert rc != 0
    assert result_path.exists()
    data = yaml.safe_load(result_path.read_text())
    assert data["kind"] == "generated-artifact"
    assert data["errors"]
    assert validate_result.validate(data, "generated-artifact") == []


def test_driver_missing_generated_yaml_aborts(tmp_path):
    from lib.pulse.scripts import generated_artifact_run

    ws = tmp_path / "workspace"
    config_dir = ws / ".hiivmind" / "github"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("workspace:\n  login: acme\n")

    result_path = tmp_path / "result.yaml"
    rc = generated_artifact_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="scheduled",
    )

    assert rc != 0
    data = yaml.safe_load(result_path.read_text())
    assert "generated.yaml not found" in data["errors"][0]
    assert validate_result.validate(data, "generated-artifact") == []


def test_driver_unknown_repo_aborts(tmp_path):
    from lib.pulse.scripts import generated_artifact_run

    ws = create_test_workspace(tmp_path)
    result_path = tmp_path / "result.yaml"
    rc = generated_artifact_run.run_driver(
        workspace=ws,
        repo_filter="nonexistent-repo",
        result_path=result_path,
        mode="scheduled",
        collector=lambda *a, **k: {},
    )

    assert rc != 0
    data = yaml.safe_load(result_path.read_text())
    assert "unknown repo" in data["errors"][0]
    assert validate_result.validate(data, "generated-artifact") == []


def test_driver_end_to_end_interactive_with_fake_collect(tmp_path):
    from lib.pulse.scripts import generated_artifact_run

    ws = create_test_workspace(tmp_path)
    result_path = tmp_path / "result.yaml"
    snap = snapshot_for(trees={"templates/repo-readme.md": "tree2222"})
    snap["hiivmind/template-repo"]["main"]["head"] = "head999"

    def fake_collect(m, workdir=None, runner=None):
        return snap

    rc = generated_artifact_run.run_driver(
        workspace=ws,
        repo_filter=None,
        result_path=result_path,
        mode="interactive",
        collector=fake_collect,
    )

    assert rc == 0
    data = yaml.safe_load(result_path.read_text())
    assert data["kind"] == "generated-artifact"
    assert data["workspace"] == "acme"
    assert data["bindings_audited"] == 1
    assert data["states"]["widget-readme"] == "template-drift"
    assert len(data["proposals"]) == 1
    assert validate_result.validate(data, "generated-artifact") == []
