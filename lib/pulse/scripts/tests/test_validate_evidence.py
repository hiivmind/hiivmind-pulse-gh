"""Tests for the normalized fleet evidence contract validator."""

import subprocess
import sys

import pytest
import yaml


SCRIPT = "lib/pulse/scripts/validate_evidence.py"


def valid_evidence():
    return {
        "contract_version": 1,
        "provider": {"name": "nave", "version": "0.4.0", "protocol": 1},
        "generated_at": "2026-07-13T10:00:00Z",
        "capability_status": {
            "state": "available",
            "capabilities": ["search_json"],
        },
        "repos": [
            {
                "repo": "acme/api",
                "remote_sha": "abc",
                "files": [],
                "structural_signals": [],
                "validation": {"state": "valid", "errors": []},
            }
        ],
        "errors": [],
    }


def run_validator(path):
    return subprocess.run(
        [sys.executable, SCRIPT, str(path)],
        capture_output=True,
        text=True,
    )


def write_evidence(tmp_path, doc):
    path = tmp_path / "evidence.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def test_valid_evidence(tmp_path):
    result = run_validator(write_evidence(tmp_path, valid_evidence()))
    assert result.returncode == 0, result.stderr


def test_accepts_optional_repo_completeness_and_capabilities(tmp_path):
    doc = valid_evidence()
    doc["repos"][0].update(
        {"files_complete": False, "capabilities": ["ci", "python"]}
    )

    result = run_validator(write_evidence(tmp_path, doc))

    assert result.returncode == 0, result.stderr


def test_legacy_absence_of_repo_completeness_and_capabilities_is_valid(tmp_path):
    result = run_validator(write_evidence(tmp_path, valid_evidence()))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("files_complete", "false", "files_complete"),
        ("capabilities", "ci", "capabilities"),
        ("capabilities", ["python", "ci"], "must be sorted"),
        ("capabilities", ["ci", "ci"], "contains duplicates"),
    ],
)
def test_rejects_invalid_optional_repo_evidence_fields(
    tmp_path, field, value, message
):
    doc = valid_evidence()
    doc["repos"][0][field] = value

    result = run_validator(write_evidence(tmp_path, doc))

    assert result.returncode == 1
    assert message in result.stderr


def test_rejects_unknown_capability_state(tmp_path):
    doc = valid_evidence()
    doc["capability_status"]["state"] = "missing-ish"
    result = run_validator(write_evidence(tmp_path, doc))
    assert result.returncode == 1
    assert "capability_status.state invalid" in result.stderr


def test_rejects_duplicate_repo_names(tmp_path):
    doc = valid_evidence()
    doc["repos"].append(dict(doc["repos"][0]))
    result = run_validator(write_evidence(tmp_path, doc))
    assert result.returncode == 1
    assert "duplicate repo: acme/api" in result.stderr


def test_requires_timestamp_to_remain_a_string(tmp_path):
    path = tmp_path / "evidence.yaml"
    path.write_text(yaml.safe_dump(valid_evidence()).replace(
        "generated_at: '2026-07-13T10:00:00Z'",
        "generated_at: 2026-07-13",
    ))
    result = run_validator(path)
    assert result.returncode == 1
    assert "generated_at" in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("files", {}),
        ("structural_signals", {}),
        ("validation", []),
    ],
)
def test_rejects_wrong_repo_field_types(tmp_path, field, value):
    doc = valid_evidence()
    doc["repos"][0][field] = value
    result = run_validator(write_evidence(tmp_path, doc))
    assert result.returncode == 1
    assert field in result.stderr


def test_missing_file_exits_two(tmp_path):
    assert run_validator(tmp_path / "missing.yaml").returncode == 2


def test_unparseable_yaml_exits_two(tmp_path):
    path = tmp_path / "evidence.yaml"
    path.write_text("repos: [unclosed")
    assert run_validator(path).returncode == 2
