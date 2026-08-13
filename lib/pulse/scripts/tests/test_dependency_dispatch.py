"""Tests for the committed python-v1/nodejs-v1 scorecard templates and dispatch
across the full ecosystem matrix: Python, Node, polyglot, docs, Terraform,
unclassified, and unsupported-ecosystem repositories.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from lib.pulse.scripts.dependency_pipeline import dependency_selected_repos
from lib.pulse.scripts.profile_dispatch import dispatch, load_profiles, resolve_scorecard


TEMPLATE = Path("templates/profiles.yaml.template")


def test_template_loads_cleanly():
    config = load_profiles(TEMPLATE)
    assert "python-v1" in config.scorecards
    assert "nodejs-v1" in config.scorecards


def test_python_v1_resolves_dependency_and_fleet_checks():
    config = load_profiles(TEMPLATE)
    checks = {c.id: c for c in resolve_scorecard(config, "python-v1")}
    assert checks["python_manifest_lock_consistency"].adapter == "python.dependencies"
    assert checks["fleet_dependency_coherence"].adapter == "fleet.dependencies.coherence"
    assert "node_manifest_lock_consistency" not in checks


def test_nodejs_v1_resolves_dependency_and_fleet_checks():
    config = load_profiles(TEMPLATE)
    checks = {c.id: c for c in resolve_scorecard(config, "nodejs-v1")}
    assert checks["node_manifest_lock_consistency"].adapter == "node.dependencies"
    assert checks["fleet_dependency_coherence"].adapter == "fleet.dependencies.coherence"
    assert "python_manifest_lock_consistency" not in checks


def _write(tmp_path, profiles: dict) -> Path:
    path = tmp_path / "profiles.yaml"
    path.write_text(yaml.safe_dump(profiles))
    return path


def _base_profiles():
    template = yaml.safe_load(TEMPLATE.read_text())
    # A polyglot scorecard for repos selecting both ecosystem checks.
    template["scorecards"]["polyglot-v1"] = {
        "extends": "generic-v1",
        "checks": [
            {
                "id": "python_manifest_lock_consistency",
                "adapter": "python.dependencies",
                "applicability": "profile:python",
                "weight": 2,
            },
            {
                "id": "node_manifest_lock_consistency",
                "adapter": "node.dependencies",
                "applicability": "profile:nodejs",
                "weight": 2,
            },
            {
                "id": "fleet_dependency_coherence",
                "adapter": "fleet.dependencies.coherence",
                "applicability": "always",
                "weight": 1,
            },
        ],
    }
    template["scorecards"]["terraform-v1"] = {
        "extends": "generic-v1",
        "checks": [
            {
                "id": "terraform-validate",
                "adapter": "terraform.validate",
                "applicability": "always",
                "weight": 1,
            }
        ],
    }
    template["scorecards"]["rust-v1"] = {
        "extends": "generic-v1",
        "checks": [
            {
                "id": "rust-dependency-consistency",
                "adapter": "rust.dependencies",
                "applicability": "always",
                "weight": 1,
            }
        ],
    }
    template["adapters"]["terraform.validate"] = {
        "state": "unsupported",
        "reason": "not implemented",
    }
    template["adapters"]["rust.dependencies"] = {
        "state": "unsupported",
        "reason": "Rust ecosystem is out of F4 v1 scope",
    }
    return template


def test_scorecard_selecting_both_check_ids_loads_and_resolves_both():
    template = _base_profiles()
    template["repository_profiles"] = {
        "acme/poly": {"profiles": ["python", "nodejs"], "scorecard": "polyglot-v1"}
    }
    config = load_profiles_from_dict(template)
    checks = {c.id: c for c in resolve_scorecard(config, "polyglot-v1")}
    assert set(checks) >= {
        "python_manifest_lock_consistency",
        "node_manifest_lock_consistency",
        "fleet_dependency_coherence",
    }


def load_profiles_from_dict(data, tmp_path=None):
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        yaml.safe_dump(data, handle)
        path = handle.name
    return load_profiles(path)


def test_dispatch_matrix_python_node_polyglot_docs_terraform_unclassified_unsupported():
    template = _base_profiles()
    template["repository_profiles"] = {
        "acme/py": {"profiles": ["python"], "scorecard": "python-v1"},
        "acme/node": {"profiles": ["nodejs"], "scorecard": "nodejs-v1"},
        "acme/poly": {"profiles": ["python", "nodejs"], "scorecard": "polyglot-v1"},
        "acme/docs": {"profiles": ["documentation"], "scorecard": "generic-v1"},
        "acme/terraform": {"profiles": ["terraform"], "scorecard": "terraform-v1"},
        "acme/unclassified": {"profiles": [], "scorecard": "generic-v1"},
        "acme/rust": {"profiles": ["rust"], "scorecard": "rust-v1"},
    }
    config = load_profiles_from_dict(template)

    selected = dependency_selected_repos(config)
    assert selected["acme/py"] == frozenset({"python"})
    assert selected["acme/node"] == frozenset({"node"})
    assert selected["acme/poly"] == frozenset({"python", "node"})
    assert "acme/docs" not in selected
    assert "acme/terraform" not in selected
    assert "acme/unclassified" not in selected
    assert "acme/rust" not in selected

    # Rust selects a genuinely unsupported ecosystem adapter — dispatch still
    # resolves cleanly, producing visible coverage debt, not a crash.
    plan = dispatch("acme/rust", {"repos": [{"repo": "acme/rust"}]}, config)
    assert plan.checks["rust-dependency-consistency"].state == "unsupported"

    # Python repo's fleet check is applicable (always) even without a profile match.
    plan_py = dispatch("acme/py", {"repos": [{"repo": "acme/py"}]}, config)
    assert plan_py.checks["fleet_dependency_coherence"].state is None  # dispatched, not precomputed
