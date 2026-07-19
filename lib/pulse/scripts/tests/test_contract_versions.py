"""Tests for contract_versions.py — pure contract-version extraction/evaluation."""
from __future__ import annotations

import json

import pytest

from lib.pulse.scripts.contract_versions import (
    ContractState,
    evaluate,
    extract,
    validate_parser_spec,
)


# --- parser spec validation ---


def test_regex_with_exactly_one_capture_group_is_valid():
    validate_parser_spec({"kind": "regex", "pattern": r"version = \"(\d+\.\d+)\""})


def test_regex_with_zero_capture_groups_rejected_at_load():
    with pytest.raises(ValueError, match="exactly one capture group"):
        validate_parser_spec({"kind": "regex", "pattern": r"version = \"\d+\.\d+\""})


def test_regex_with_two_capture_groups_rejected_at_load():
    with pytest.raises(ValueError, match="exactly one capture group"):
        validate_parser_spec({"kind": "regex", "pattern": r"(version) = \"(\d+\.\d+)\""})


def test_toml_parser_spec_is_valid():
    validate_parser_spec({"kind": "toml", "key": "project.version"})


def test_json_parser_spec_is_valid():
    validate_parser_spec({"kind": "json", "pointer": "/version"})


def test_yaml_parser_spec_is_valid():
    validate_parser_spec({"kind": "yaml", "key": "version"})


# --- regex extraction ---


def test_regex_extracts_capture_group():
    spec = {"kind": "regex", "pattern": r"version = \"(\d+\.\d+\.\d+)\""}
    content = b'\n# comment\nversion = "1.2.3"\n'
    assert extract(spec, content) == "1.2.3"


def test_regex_no_match_returns_none():
    spec = {"kind": "regex", "pattern": r"version = \"(\d+\.\d+\.\d+)\""}
    assert extract(spec, b"no version here") is None


def test_regex_bad_bytes_returns_none():
    spec = {"kind": "regex", "pattern": r"version = \"(\d+\.\d+\.\d+)\""}
    assert extract(spec, b"\xff\xfe") is None


# --- toml extraction ---


def test_toml_extracts_dotted_key():
    spec = {"kind": "toml", "key": "project.version"}
    content = b'[project]\nname = "example"\nversion = "2.0.0"\n'
    assert extract(spec, content) == "2.0.0"


def test_toml_missing_key_returns_none():
    spec = {"kind": "toml", "key": "project.version"}
    assert extract(spec, b'[project]\nname = "example"\n') is None


def test_toml_bad_bytes_returns_none():
    spec = {"kind": "toml", "key": "project.version"}
    assert extract(spec, b"\xff\xfe not valid utf8") is None


# --- json pointer extraction ---


def test_json_pointer_extracts_top_level_value():
    spec = {"kind": "json", "pointer": "/version"}
    content = json.dumps({"version": "3.1.4"}).encode()
    assert extract(spec, content) == "3.1.4"


def test_json_pointer_extracts_nested_value():
    spec = {"kind": "json", "pointer": "/deps/foo"}
    content = json.dumps({"deps": {"foo": "1.0.0"}}).encode()
    assert extract(spec, content) == "1.0.0"


def test_json_pointer_missing_returns_none():
    spec = {"kind": "json", "pointer": "/missing"}
    content = json.dumps({"version": "1.0.0"}).encode()
    assert extract(spec, content) is None


def test_json_pointer_bad_bytes_returns_none():
    spec = {"kind": "json", "pointer": "/version"}
    assert extract(spec, b"{not json") is None


# --- yaml extraction ---


def test_yaml_extracts_dotted_key():
    spec = {"kind": "yaml", "key": "version"}
    content = b'version: "4.5.6"\n'
    assert extract(spec, content) == "4.5.6"


def test_yaml_extracts_nested_dotted_key():
    spec = {"kind": "yaml", "key": "project.version"}
    content = b'project:\n  version: "7.8.9"\n'
    assert extract(spec, content) == "7.8.9"


def test_yaml_missing_key_returns_none():
    spec = {"kind": "yaml", "key": "project.version"}
    content = b'other:\n  value: 1\n'
    assert extract(spec, content) is None


def test_yaml_bad_bytes_returns_none():
    spec = {"kind": "yaml", "key": "version"}
    assert extract(spec, b"\xff\xfe") is None


# --- evaluate() ---


def fake_reader(files: dict) -> callable:
    def read(repo: str, path: str) -> bytes:
        return files[(repo, path)]
    return read


def test_evaluate_pep440_compatible():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {
                "path": "pyproject.toml",
                "parser": {"kind": "toml", "key": "project.version"},
            },
                "consumer": {
                    "path": "requirements.txt",
                    "parser": {"kind": "regex", "pattern": r"upstream(>=[^\s]+)"},
                },
            "version_scheme": "pep440",
        },
    }
    files = {
        ("upstream", "pyproject.toml"): b'[project]\nversion = "1.5.0"\n',
        ("upstream", "requirements.txt"): b"upstream>=1.0,<2.0\n",
    }
    result = evaluate(edge, fake_reader(files))
    assert result == ContractState("compatible", "1.5.0", ">=1.0,<2.0")


def test_evaluate_pep440_gap():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {
                "path": "version.json",
                "parser": {"kind": "json", "pointer": "/version"},
            },
            "consumer": {
                "path": "consumer.yaml",
                "parser": {"kind": "yaml", "key": "requires"},
            },
            "version_scheme": "pep440",
        },
    }
    files = {
        ("upstream", "version.json"): b'{"version": "2.0.0"}',
        ("upstream", "consumer.yaml"): b"requires: \">=1.0,<2.0\"\n",
    }
    result = evaluate(edge, fake_reader(files))
    assert result == ContractState("gap", "2.0.0", ">=1.0,<2.0")


def test_evaluate_pep440_bare_version_equal():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {
                "path": "version.txt",
                "parser": {"kind": "regex", "pattern": r"version:\s*(\S+)"},
            },
            "consumer": {
                "path": "pin.txt",
                "parser": {"kind": "regex", "pattern": r"version:\s*(\S+)"},
            },
            "version_scheme": "pep440",
        },
    }
    files = {
        ("upstream", "version.txt"): b"version: 1.2.3",
        ("upstream", "pin.txt"): b"version: 1.2.3",
    }
    result = evaluate(edge, fake_reader(files))
    assert result == ContractState("compatible", "1.2.3", "1.2.3")


def test_evaluate_pep440_bare_version_gap():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "v.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "p.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "version_scheme": "pep440",
        },
    }
    files = {
        ("upstream", "v.txt"): b"1.2.3",
        ("upstream", "p.txt"): b"1.2.4",
    }
    result = evaluate(edge, fake_reader(files))
    assert result == ContractState("gap", "1.2.3", "1.2.4")


def test_evaluate_no_scheme_string_equality_compatible():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "a.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "b.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
        },
    }
    files = {
        ("upstream", "a.txt"): b"abc123",
        ("upstream", "b.txt"): b"abc123",
    }
    result = evaluate(edge, fake_reader(files))
    assert result == ContractState("compatible", "abc123", "abc123")


def test_evaluate_no_scheme_string_equality_gap():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "a.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "b.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
        },
    }
    files = {
        ("upstream", "a.txt"): b"abc123",
        ("upstream", "b.txt"): b"def456",
    }
    result = evaluate(edge, fake_reader(files))
    assert result == ContractState("gap", "abc123", "def456")


def test_evaluate_non_pep440_scheme_uses_string_equality():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "a.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "b.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "version_scheme": "semver",
        },
    }
    files = {
        ("upstream", "a.txt"): b"abc123",
        ("upstream", "b.txt"): b"abc123",
    }
    result = evaluate(edge, fake_reader(files))
    assert result == ContractState("compatible", "abc123", "abc123")


def test_evaluate_unknown_when_producer_missing():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "missing.toml", "parser": {"kind": "toml", "key": "version"}},
            "consumer": {"path": "b.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
        },
    }
    files = {
        ("upstream", "b.txt"): b"1.2.3",
    }
    result = evaluate(edge, fake_reader(files))
    assert result.state == "unknown"
    assert result.producer_version is None
    assert result.consumer_requirement == "1.2.3"


def test_evaluate_unknown_when_consumer_missing():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "a.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "missing.yaml", "parser": {"kind": "yaml", "key": "version"}},
        },
    }
    files = {
        ("upstream", "a.txt"): b"1.2.3",
    }
    result = evaluate(edge, fake_reader(files))
    assert result.state == "unknown"
    assert result.producer_version == "1.2.3"
    assert result.consumer_requirement is None


def test_evaluate_unknown_when_reader_raises():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "a.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "b.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
        },
    }

    def read(_repo: str, _path: str) -> bytes:
        raise FileNotFoundError("nope")

    result = evaluate(edge, read)
    assert result.state == "unknown"
    assert result.producer_version is None
    assert result.consumer_requirement is None


def test_evaluate_unknown_on_invalid_pep440_version():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "a.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "b.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "version_scheme": "pep440",
        },
    }
    files = {
        ("upstream", "a.txt"): b"not-a-version",
        ("upstream", "b.txt"): b">=1.0",
    }
    result = evaluate(edge, fake_reader(files))
    assert result.state == "unknown"


def test_evaluate_unknown_on_invalid_pep440_specifier():
    edge = {
        "repo": "upstream",
        "contract": {
            "producer": {"path": "a.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "consumer": {"path": "b.txt", "parser": {"kind": "regex", "pattern": r"(\S+)"}},
            "version_scheme": "pep440",
        },
    }
    files = {
        ("upstream", "a.txt"): b"1.2.3",
        ("upstream", "b.txt"): b"not-a-specifier",
    }
    result = evaluate(edge, fake_reader(files))
    assert result.state == "unknown"
