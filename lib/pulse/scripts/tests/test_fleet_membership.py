"""Tests for identity-safe GitHub fleet membership reconciliation."""

import json
import subprocess
import sys

import yaml

from lib.pulse.scripts.fleet_membership import reconcile_membership


SCRIPT = "lib/pulse/scripts/fleet_membership.py"
STABLE_FIELDS = {
    "name",
    "id",
    "full_name",
    "default_branch",
    "is_public",
    "archived",
    "fork",
    "mirror_url",
}


def live_repo(name, node_id, **overrides):
    repo = {
        "name": name.split("/", 1)[1],
        "node_id": node_id,
        "full_name": name,
        "default_branch": "main",
        "private": False,
        "archived": False,
        "fork": False,
        "mirror_url": None,
    }
    repo.update(overrides)
    return repo


def catalog_repo(name, node_id=None, **overrides):
    repo = {
        "name": name.split("/", 1)[1],
        "id": node_id,
        "full_name": name,
        "default_branch": "main",
        "is_public": True,
        "archived": False,
        "fork": False,
        "mirror_url": None,
    }
    repo.update(overrides)
    return repo


def reconcile(live, catalog, discovery=None):
    config = {"repositories": catalog}
    if discovery is not None:
        config["fleet_membership"] = {"discovery": discovery}
    return reconcile_membership(live, config)


def finding_kinds(result):
    return [finding["kind"] for finding in result["findings"]]


def test_new_repository_is_added_with_stable_facts_only():
    result = reconcile([live_repo("acme/new", "R_NEW")], [])

    assert finding_kinds(result) == ["repository-created"]
    assert result["catalog_patch"] == [catalog_repo("acme/new", "R_NEW")]
    assert set(result["catalog_patch"][0]) == STABLE_FIELDS
    assert "profiles" not in result["catalog_patch"][0]
    assert "scorecard" not in result["catalog_patch"][0]
    assert result["catalog_repos"] == []


def test_rename_matches_by_node_id_and_updates_name():
    result = reconcile(
        [live_repo("acme/new-name", "R_ONE")],
        [catalog_repo("acme/old-name", "R_ONE")],
    )

    assert finding_kinds(result) == ["repository-renamed"]
    assert result["findings"][0]["before"] == "acme/old-name"
    assert result["catalog_patch"][0]["full_name"] == "acme/new-name"


def test_archived_repository_remains_a_catalog_fact_by_default():
    result = reconcile(
        [live_repo("acme/old", "R_OLD", archived=True)],
        [catalog_repo("acme/old", "R_OLD")],
    )

    assert finding_kinds(result) == ["repository-archived"]
    assert result["catalog_patch"][0]["archived"] is True


def test_transfer_and_missing_catalog_entries_are_distinct():
    result = reconcile(
        [live_repo("other/moved", "R_MOVE")],
        [
            catalog_repo("acme/moved", "R_MOVE"),
            catalog_repo("acme/missing", "R_MISSING"),
        ],
    )

    assert finding_kinds(result) == ["repository-transferred", "repository-missing"]
    assert [repo["full_name"] for repo in result["catalog_patch"]] == ["other/moved"]


def test_forks_and_mirrors_are_excluded_by_default():
    result = reconcile(
        [
            live_repo("acme/fork", "R_FORK", fork=True),
            live_repo("acme/mirror", "R_MIRROR", mirror_url="ssh://mirror"),
        ],
        [],
    )

    assert result["org_repos"] == []
    assert result["catalog_patch"] == []
    assert finding_kinds(result) == ["repository-excluded", "repository-excluded"]


def test_discovery_policy_can_include_forks_and_exclude_archived():
    result = reconcile(
        [
            live_repo("acme/fork", "R_FORK", fork=True),
            live_repo("acme/old", "R_OLD", archived=True),
        ],
        [],
        {"include_forks": True, "include_archived": False},
    )

    assert [repo["full_name"] for repo in result["catalog_patch"]] == ["acme/fork"]
    assert finding_kinds(result) == ["repository-created", "repository-excluded"]


def test_idless_catalog_entry_is_backfilled_only_by_exact_full_name():
    result = reconcile(
        [live_repo("acme/legacy", "R_LEGACY")],
        [catalog_repo("acme/legacy", None)],
    )

    assert finding_kinds(result) == ["repository-identity-backfilled"]
    assert result["catalog_patch"][0]["id"] == "R_LEGACY"


def test_legacy_name_only_catalog_entry_uses_workspace_owner_for_safe_backfill():
    config = {
        "workspace": {"login": "acme"},
        "repositories": [{"name": "legacy"}],
    }

    result = reconcile_membership([live_repo("acme/legacy", "R_LEGACY")], config)

    assert finding_kinds(result) == ["repository-identity-backfilled"]
    assert result["catalog_patch"][0] == catalog_repo("acme/legacy", "R_LEGACY")


def test_cli_emits_deterministic_json(tmp_path):
    org_path = tmp_path / "org.json"
    config_path = tmp_path / "config.yaml"
    org_path.write_text(json.dumps([live_repo("acme/zeta", "R_Z")]))
    config_path.write_text(yaml.safe_dump({"repositories": []}))

    result = subprocess.run(
        [sys.executable, SCRIPT, "--org-repos", str(org_path), "--config", str(config_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["catalog_patch"][0]["full_name"] == "acme/zeta"


def test_cli_apply_catalog_updates_only_repository_facts(tmp_path):
    org_path = tmp_path / "org.json"
    config_path = tmp_path / "config.yaml"
    org_path.write_text(json.dumps([live_repo("acme/new", "R_NEW")]))
    config_path.write_text(yaml.safe_dump({
        "workspace": {"login": "acme"},
        "repositories": [],
        "milestones": {"keep": []},
    }))

    result = subprocess.run(
        [
            sys.executable,
            SCRIPT,
            "--org-repos",
            str(org_path),
            "--config",
            str(config_path),
            "--apply-catalog",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["catalog_updated"] is True
    assert output["catalog_repos"] == ["acme/new"]
    updated = yaml.safe_load(config_path.read_text())
    assert updated["repositories"] == [catalog_repo("acme/new", "R_NEW")]
    assert updated["milestones"] == {"keep": []}
