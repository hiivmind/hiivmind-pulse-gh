"""Tests for apply-mode authorization policy (F11 Task 2).

`ApplyAuthorization` is the operator-approved scope an `allow-listed`
re-derived proposal must fall within. `authorize` fails closed on any
recorded-summary identity mismatch (binding/transformation/proposal_id)
or authorization-scope violation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.pulse.scripts import apply_authorization, apply_rederive, mutation_plan

ACTOR = {"gh_login": "octocat", "machine": "laptop", "mode": "interactive"}


def _proposal(
    id="prop-1",
    selection=("acme/docs",),
    transformation="plan-sync-doc-patch",
    bound_paths=None,
):
    return mutation_plan.build_proposal(
        id=id,
        selection=list(selection),
        transformation=transformation,
        expected_shas={repo: "a" * 40 for repo in selection},
        actor=ACTOR,
        mutation_policy="allow-listed",
        bound_paths=bound_paths or {repo: ["plans/release.md"] for repo in selection},
    )


def _rederived(binding_id="release-plan", **proposal_overrides):
    return apply_rederive.RederivedProposal(
        binding_id=binding_id,
        proposal=_proposal(**proposal_overrides),
        source_kind="plan-sync",
        finalizer_record=None,
    )


def _auth(
    transformation="plan-sync-doc-patch",
    mutation_policy="allow-listed",
    permitted_repos=("acme/docs",),
    bound_paths=None,
):
    return apply_authorization.ApplyAuthorization(
        transformation=transformation,
        mutation_policy=mutation_policy,
        permitted_repos=tuple(permitted_repos),
        bound_paths=bound_paths
        or {repo: ("plans/release.md",) for repo in permitted_repos},
    )


def _recorded_summary(rederived, **overrides):
    summary = {
        "binding": rederived.binding_id,
        "transformation": rederived.proposal.transformation,
        "proposal_id": rederived.proposal.id,
    }
    summary.update(overrides)
    return summary


# --- load_authorization -------------------------------------------------


def test_load_authorization_reads_matching_transformation_entry(tmp_path):
    path = tmp_path / "apply-authorization.yaml"
    path.write_text(
        "authorizations:\n"
        "  plan-sync-doc-patch:\n"
        "    mutation_policy: allow-listed\n"
        "    permitted_repos: [acme/docs]\n"
        "    bound_paths:\n"
        "      acme/docs: [plans/release.md]\n"
    )

    auth = apply_authorization.load_authorization(path, "plan-sync-doc-patch")

    assert auth.transformation == "plan-sync-doc-patch"
    assert auth.mutation_policy == "allow-listed"
    assert auth.permitted_repos == ("acme/docs",)
    assert auth.bound_paths == {"acme/docs": ("plans/release.md",)}


def test_load_authorization_raises_for_missing_file(tmp_path):
    with pytest.raises(apply_authorization.AuthorizationError, match="not found"):
        apply_authorization.load_authorization(tmp_path / "missing.yaml", "plan-sync-doc-patch")


def test_load_authorization_raises_for_unknown_transformation(tmp_path):
    path = tmp_path / "apply-authorization.yaml"
    path.write_text(
        "authorizations:\n"
        "  plan-sync-doc-patch:\n"
        "    mutation_policy: allow-listed\n"
        "    permitted_repos: [acme/docs]\n"
        "    bound_paths: {acme/docs: [plans/release.md]}\n"
    )

    with pytest.raises(apply_authorization.AuthorizationError, match="no authorization recorded"):
        apply_authorization.load_authorization(path, "marketplace-entry-update")


def test_load_authorization_rejects_invalid_mutation_policy(tmp_path):
    path = tmp_path / "apply-authorization.yaml"
    path.write_text(
        "authorizations:\n"
        "  plan-sync-doc-patch:\n"
        "    mutation_policy: yolo\n"
        "    permitted_repos: [acme/docs]\n"
        "    bound_paths: {acme/docs: [plans/release.md]}\n"
    )

    with pytest.raises(apply_authorization.AuthorizationError, match="mutation_policy invalid"):
        apply_authorization.load_authorization(path, "plan-sync-doc-patch")


def test_load_authorization_rejects_empty_permitted_repos(tmp_path):
    path = tmp_path / "apply-authorization.yaml"
    path.write_text(
        "authorizations:\n"
        "  plan-sync-doc-patch:\n"
        "    mutation_policy: allow-listed\n"
        "    permitted_repos: []\n"
        "    bound_paths: {}\n"
    )

    with pytest.raises(
        apply_authorization.AuthorizationError,
        match="permitted_repos must be non-empty",
    ):
        apply_authorization.load_authorization(path, "plan-sync-doc-patch")


# --- authorization_digest -------------------------------------------------


def test_authorization_digest_is_versioned_and_deterministic():
    auth = _auth()
    digest_a = apply_authorization.authorization_digest(auth)
    digest_b = apply_authorization.authorization_digest(_auth())

    assert digest_a == digest_b
    assert digest_a.startswith("v1|")


def test_authorization_digest_changes_when_scope_changes():
    digest_a = apply_authorization.authorization_digest(_auth())
    digest_b = apply_authorization.authorization_digest(
        _auth(permitted_repos=("acme/other",))
    )

    assert digest_a != digest_b


# --- authorize: happy path -------------------------------------------------


def test_authorize_accepts_matching_rederived_proposal():
    rederived = _rederived()
    recorded_summary = _recorded_summary(rederived)

    apply_authorization.authorize(rederived, _auth(), recorded_summary)  # does not raise


def test_authorize_accepts_selection_strict_subset_of_permitted_repos():
    rederived = _rederived(
        selection=("acme/a",),
        bound_paths={"acme/a": ["plans/release.md"]},
    )
    recorded_summary = _recorded_summary(rederived)
    auth = _auth(
        permitted_repos=("acme/a", "acme/b"),
        bound_paths={
            "acme/a": ("plans/release.md",),
            "acme/b": ("plans/release.md",),
        },
    )

    apply_authorization.authorize(rederived, auth, recorded_summary)  # does not raise


# --- authorize: recorded-summary identity mismatches -----------------------


def test_authorize_refuses_binding_mismatch():
    rederived = _rederived(binding_id="release-plan")
    recorded_summary = _recorded_summary(rederived, binding="a-different-binding")

    with pytest.raises(apply_authorization.AuthorizationError, match="binding mismatch"):
        apply_authorization.authorize(rederived, _auth(), recorded_summary)


def test_authorize_refuses_transformation_mismatch():
    rederived = _rederived()
    recorded_summary = _recorded_summary(rederived, transformation="marketplace-entry-update")

    with pytest.raises(apply_authorization.AuthorizationError, match="transformation mismatch"):
        apply_authorization.authorize(rederived, _auth(), recorded_summary)


def test_authorize_refuses_proposal_id_mismatch():
    rederived = _rederived()
    recorded_summary = _recorded_summary(rederived, proposal_id="prop-stale")

    with pytest.raises(apply_authorization.AuthorizationError, match="proposal_id mismatch"):
        apply_authorization.authorize(rederived, _auth(), recorded_summary)


# --- authorize: authorization-scope violations ------------------------------


def test_authorize_refuses_selection_outside_authorization():
    rederived = _rederived(selection=("acme/docs", "acme/widgets"), bound_paths={
        "acme/docs": ["plans/release.md"], "acme/widgets": ["plans/release.md"],
    })
    recorded_summary = _recorded_summary(rederived)
    auth = _auth(
        permitted_repos=("acme/docs",)
    )  # authorization only covers one repo

    with pytest.raises(apply_authorization.AuthorizationError, match="selection"):
        apply_authorization.authorize(rederived, auth, recorded_summary)


def test_authorize_refuses_mutation_policy_mismatch():
    rederived = _rederived()
    recorded_summary = _recorded_summary(rederived)
    auth = _auth(mutation_policy="propose")

    with pytest.raises(apply_authorization.AuthorizationError, match="mutation_policy"):
        apply_authorization.authorize(rederived, auth, recorded_summary)


def test_authorize_refuses_bound_path_outside_authorization():
    rederived = _rederived(bound_paths={"acme/docs": ["plans/release.md", "plans/extra.md"]})
    recorded_summary = _recorded_summary(rederived)
    auth = _auth(bound_paths={"acme/docs": ("plans/release.md",)})

    with pytest.raises(apply_authorization.AuthorizationError, match="bound_paths outside authorization"):
        apply_authorization.authorize(rederived, auth, recorded_summary)


def test_authorize_refuses_transformation_outside_authorization_scope():
    rederived = _rederived(transformation="marketplace-entry-update", bound_paths={
        "acme/docs": ["plans/release.md"],
    })
    recorded_summary = _recorded_summary(rederived)
    auth = _auth(transformation="plan-sync-doc-patch")  # authorization covers a different transformation

    with pytest.raises(apply_authorization.AuthorizationError, match="not authorized"):
        apply_authorization.authorize(rederived, auth, recorded_summary)
