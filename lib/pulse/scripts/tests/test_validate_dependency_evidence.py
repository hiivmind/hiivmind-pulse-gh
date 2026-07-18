"""Tests for the strict dependency-evidence contract validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from lib.pulse.scripts import validate_dependency_evidence as vde


FIXTURE = Path(__file__).parent / "fixtures" / "dependency-evidence-valid.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_valid_fixture_passes():
    assert vde.validate(load_fixture()) == []


def test_every_state_is_accepted_when_content_rules_are_respected():
    doc = load_fixture()
    states_present = {
        a["state"] for r in doc["repos"] for a in r["artifacts"]
    }
    assert states_present == {
        "found",
        "absent",
        "too_large",
        "binary",
        "unresolved",
        "unsupported",
        "error",
    }
    assert vde.validate(doc) == []


def test_duplicate_repo_rejected():
    doc = load_fixture()
    dup = copy.deepcopy(doc["repos"][0])
    doc["repos"].append(dup)
    errors = vde.validate(doc)
    assert any("duplicate repo" in e for e in errors)


def test_duplicate_selector_id_within_repo_rejected():
    doc = load_fixture()
    artifact = copy.deepcopy(doc["repos"][0]["artifacts"][0])
    doc["repos"][0]["artifacts"].append(artifact)
    errors = vde.validate(doc)
    assert any("duplicate selector_id" in e for e in errors)


def test_duplicate_path_within_repo_rejected():
    doc = load_fixture()
    artifact = copy.deepcopy(doc["repos"][0]["artifacts"][0])
    artifact["selector_id"] = "python.other_selector"
    doc["repos"][0]["artifacts"].append(artifact)
    errors = vde.validate(doc)
    assert any("duplicate path" in e for e in errors)


def test_missing_key_rejected():
    doc = load_fixture()
    del doc["request_sha256"]
    errors = vde.validate(doc)
    assert any("request_sha256" in e for e in errors)


def test_extra_repo_key_rejected():
    doc = load_fixture()
    doc["repos"][0]["unexpected_key"] = "nope"
    errors = vde.validate(doc)
    assert any("unexpected_key" in e for e in errors)


def test_extra_artifact_key_rejected():
    doc = load_fixture()
    doc["repos"][0]["artifacts"][0]["unexpected_key"] = "nope"
    errors = vde.validate(doc)
    assert any("unexpected_key" in e for e in errors)


def test_missing_artifact_key_rejected():
    doc = load_fixture()
    del doc["repos"][0]["artifacts"][0]["detail"]
    errors = vde.validate(doc)
    assert any("detail" in e for e in errors)


def test_bad_tree_sha_format_rejected():
    doc = load_fixture()
    doc["repos"][0]["tree_sha"] = "not-a-sha"
    errors = vde.validate(doc)
    assert any("tree_sha" in e for e in errors)


def test_tree_sha_null_is_allowed():
    doc = load_fixture()
    doc["repos"][0]["tree_sha"] = None
    assert vde.validate(doc) == []


def test_bad_blob_sha_format_rejected():
    doc = load_fixture()
    doc["repos"][0]["artifacts"][0]["blob_sha"] = "xyz"
    errors = vde.validate(doc)
    assert any("blob_sha" in e for e in errors)


def test_content_present_on_non_found_state_rejected():
    doc = load_fixture()
    # too_large artifact must not carry content.
    too_large = next(
        a
        for r in doc["repos"]
        for a in r["artifacts"]
        if a["state"] == "too_large"
    )
    too_large["content"] = "leaked content should not be here"
    errors = vde.validate(doc)
    assert any("content" in e for e in errors)


def test_content_missing_on_found_state_rejected():
    doc = load_fixture()
    found = next(
        a for r in doc["repos"] for a in r["artifacts"] if a["state"] == "found"
    )
    found["content"] = None
    errors = vde.validate(doc)
    assert any("content" in e for e in errors)


def test_encoding_must_be_utf8_when_found():
    doc = load_fixture()
    found = next(
        a for r in doc["repos"] for a in r["artifacts"] if a["state"] == "found"
    )
    found["encoding"] = "latin-1"
    errors = vde.validate(doc)
    assert any("encoding" in e for e in errors)


def test_non_finite_size_rejected():
    doc = load_fixture()
    doc["repos"][0]["artifacts"][0]["size_bytes"] = float("nan")
    errors = vde.validate(doc)
    assert any("size_bytes" in e for e in errors)


def test_negative_size_rejected():
    doc = load_fixture()
    doc["repos"][0]["artifacts"][0]["size_bytes"] = -1
    errors = vde.validate(doc)
    assert any("size_bytes" in e for e in errors)


def test_protocol_mismatch_rejected():
    doc = load_fixture()
    doc["provider"]["protocol"] = 1
    errors = vde.validate(doc)
    assert any("protocol" in e for e in errors)


def test_bad_state_rejected():
    doc = load_fixture()
    doc["repos"][0]["artifacts"][0]["state"] = "bogus"
    errors = vde.validate(doc)
    assert any("state" in e for e in errors)


def test_unsupported_contract_version_rejected():
    doc = load_fixture()
    doc["contract_version"] = 2
    errors = vde.validate(doc)
    assert any("contract_version" in e for e in errors)


def test_bad_repo_name_format_rejected():
    doc = load_fixture()
    doc["repos"][0]["repo"] = "not-owner-slash-name"
    errors = vde.validate(doc)
    assert any("repo" in e for e in errors)


def test_error_message_for_bad_found_artifact_does_not_leak_content():
    doc = load_fixture()
    secret_content = "TOTALLY-SECRET-DEPENDENCY-FILE-CONTENTS-1234"
    found = next(
        a for r in doc["repos"] for a in r["artifacts"] if a["state"] == "found"
    )
    found["content"] = secret_content
    found["encoding"] = "latin-1"  # trigger an error against this artifact

    errors = vde.validate(doc)

    assert any("encoding" in e for e in errors)
    joined = "\n".join(errors)
    assert secret_content not in joined


def test_cli_exit_codes(tmp_path):
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(FIXTURE.read_text())
    assert vde.main([str(valid_path)]) == 0

    doc = load_fixture()
    doc["contract_version"] = 99
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(doc))
    assert vde.main([str(invalid_path)]) == 1

    missing_path = tmp_path / "missing.json"
    assert vde.main([str(missing_path)]) == 2
