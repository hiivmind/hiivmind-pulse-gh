"""Tests for the strict dependencies.yaml (coherence policy) loader."""

from __future__ import annotations

import pytest

from lib.pulse.scripts.dependency_policy import (
    DependencyPolicyError,
    parse_dependency_policy,
)


VALID_DOC = """
contract_version: 1
coherence_groups:
  core-runtime:
    repos: [acme/api, acme/worker]
    packages: ["python:requests", "npm:@acme/*"]
    exclude_packages: ["python:typing-extensions"]
    policy: same-minor
"""


def test_malformed_yaml_error_never_echoes_source_content():
    # PyYAML embeds the offending source line in its own exception message —
    # the policy loader must never let that content reach the raised error.
    canary = "CANARY-SECRET-do-not-leak-42"
    doc = f"contract_version: 1\ncoherence_groups: {{{canary}: [unbalanced\n"
    with pytest.raises(DependencyPolicyError) as excinfo:
        parse_dependency_policy(doc)
    assert canary not in str(excinfo.value)


def test_valid_document_parses_into_dependency_policy():
    policy = parse_dependency_policy(VALID_DOC)
    assert len(policy.groups) == 1
    group = policy.groups[0]
    assert group.id == "core-runtime"
    assert group.repos == ("acme/api", "acme/worker")
    assert group.packages == ("python:requests", "npm:@acme/*")
    assert group.exclude_packages == ("python:typing-extensions",)
    assert group.policy == "same-minor"


def test_exclude_packages_defaults_to_empty_tuple():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:requests"]
    policy: exact
"""
    policy = parse_dependency_policy(doc)
    assert policy.groups[0].exclude_packages == ()


def test_empty_coherence_groups_is_valid_empty_policy():
    doc = "contract_version: 1\ncoherence_groups: {}\n"
    policy = parse_dependency_policy(doc)
    assert policy.groups == ()


# --- duplicate keys ------------------------------------------------------


def test_duplicate_coherence_group_key_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:requests"]
    policy: exact
  g1:
    repos: [acme/other, acme/worker]
    packages: ["python:flask"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_duplicate_repo_within_one_group_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/api]
    packages: ["python:requests"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


# --- unqualified / malformed packages --------------------------------------


def test_unqualified_package_without_ecosystem_prefix_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["requests"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_python_glob_with_scoped_npm_syntax_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:@foo/bar"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_npm_glob_with_at_sign_outside_scoped_form_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["npm:foo@bar"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_npm_glob_with_slash_outside_scoped_form_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["npm:foo/bar/baz"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_empty_segment_glob_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_unbalanced_bracket_glob_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:type[ing"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_out_of_grammar_character_glob_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:requests!"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_accepted_glob_examples_parse_cleanly():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["npm:@acme/*", "python:requests", "python:type[i]ng*"]
    policy: exact
"""
    policy = parse_dependency_policy(doc)
    assert policy.groups[0].packages == (
        "npm:@acme/*",
        "python:requests",
        "python:type[i]ng*",
    )


def test_bracket_range_rejects_non_ascii_digit():
    # str.isdigit() accepts Unicode digits (e.g. Devanagari "३"); the grammar's
    # digit terminal is strictly ASCII "0".."9".
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:foo[\u09693-5]"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


# --- unknown keys / policies -------------------------------------------------


def test_unknown_top_level_key_rejected():
    doc = """
contract_version: 1
coherence_groups: {}
extra_key: true
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_unknown_group_key_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:requests"]
    policy: exact
    surprise: true
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_unknown_policy_value_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: ["python:requests"]
    policy: whatever
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_unsupported_contract_version_rejected():
    doc = """
contract_version: 2
coherence_groups: {}
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


# --- empty groups ------------------------------------------------------------


def test_group_with_empty_repos_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: []
    packages: ["python:requests"]
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)


def test_group_with_empty_packages_rejected():
    doc = """
contract_version: 1
coherence_groups:
  g1:
    repos: [acme/api, acme/worker]
    packages: []
    policy: exact
"""
    with pytest.raises(DependencyPolicyError):
        parse_dependency_policy(doc)
