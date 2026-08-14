#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Apply-mode authorization policy (F11 Task 2).

`ApplyAuthorization` is the operator-approved scope a re-derived
`allow-listed` proposal must fall within before an apply run is permitted
to mutate anything: which transformation, which repositories, which
bound paths per repository. `authorize` is the fail-closed gate — it
never silently passes a mismatch (Global Constraints: "Fail closed ...
unauthorized proposal").

Two independent things are checked, both required:

1. **Recorded-summary identity** — the freshly re-derived proposal
   (`apply_rederive.RederivedProposal`) must be the SAME proposal the
   caller previously recorded (`binding`/`transformation`/
   `proposal_id` all match `recorded_summary` exactly). A mismatch means
   re-derivation produced a different proposal than what was reviewed —
   the world moved since the recorded summary was written, and this run
   must not proceed on it.
2. **Authorization scope** — the rederived proposal's transformation,
   mutation policy, repository selection, and bound paths must all fall
   within what `ApplyAuthorization` actually grants. This is the
   allow-listed apply's real gate: it is independent of whether the
   *content* changed, and is what makes `allow-listed` safe to run
   unattended.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from lib.pulse.scripts import mutation_plan
from lib.pulse.scripts.apply_rederive import RederivedProposal


class AuthorizationError(ValueError):
    """Raised when a rederived proposal fails to match its recorded
    summary, or falls outside its `ApplyAuthorization` scope."""


@dataclass(frozen=True)
class ApplyAuthorization:
    """The operator-approved scope for one transformation's allow-listed
    apply runs, loaded from a `apply-authorization.yaml`-shaped file."""

    transformation: str
    mutation_policy: str
    permitted_repos: tuple[str, ...]
    bound_paths: dict[str, tuple[str, ...]]


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorizationError(f"{label} must be a mapping")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AuthorizationError(f"{label} must be a list")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthorizationError(f"{label} must be a non-empty string")
    return value


def _only_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise AuthorizationError(f"unknown {label} key: {sorted(unknown)[0]}")


def load_authorization(path: str | Path, transformation: str) -> ApplyAuthorization:
    """Load the `ApplyAuthorization` scoped to one transformation id.

    `path` points at a YAML file shaped:

        authorizations:
          <transformation-id>:
            mutation_policy: allow-listed
            permitted_repos: [owner/repo, ...]
            bound_paths:
              owner/repo: [path/glob, ...]

    Fails closed (raises `AuthorizationError`) on a missing file,
    malformed YAML, an unknown transformation id, an invalid
    `mutation_policy`, empty `permitted_repos`, or a malformed shape —
    there is never an implicit "no authorization" pass-through.
    """
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text())
    except FileNotFoundError as exc:
        raise AuthorizationError(f"apply-authorization not found: {p}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AuthorizationError(f"could not load apply-authorization: {exc}") from exc

    root = _mapping(raw or {}, "apply-authorization")
    authorizations = _mapping(
        root.get("authorizations") or {}, "apply-authorization.authorizations"
    )
    label = f"apply-authorization.authorizations[{transformation}]"
    entry_raw = authorizations.get(transformation)
    if entry_raw is None:
        raise AuthorizationError(
            f"apply-authorization: no authorization recorded for transformation "
            f"{transformation!r}"
        )
    item = _mapping(entry_raw, label)
    _only_keys(
        item, {"mutation_policy", "permitted_repos", "bound_paths"}, label
    )

    mutation_policy = _string(item.get("mutation_policy"), f"{label}.mutation_policy")
    if mutation_policy not in mutation_plan.MUTATION_POLICIES:
        raise AuthorizationError(f"{label}.mutation_policy invalid: {mutation_policy}")

    permitted_repos_raw = _list(
        item.get("permitted_repos"), f"{label}.permitted_repos"
    )
    if not permitted_repos_raw:
        raise AuthorizationError(f"{label}.permitted_repos must be non-empty")
    permitted_repos = tuple(
        _string(repo, f"{label}.permitted_repos entry")
        for repo in permitted_repos_raw
    )

    bound_paths_raw = _mapping(item.get("bound_paths") or {}, f"{label}.bound_paths")
    bound_paths: dict[str, tuple[str, ...]] = {}
    for repo, paths in bound_paths_raw.items():
        repo_key = _string(repo, f"{label}.bound_paths key")
        path_list = _list(paths, f"{label}.bound_paths[{repo_key}]")
        bound_paths[repo_key] = tuple(
            _string(entry, f"{label}.bound_paths[{repo_key}] entry") for entry in path_list
        )

    return ApplyAuthorization(
        transformation=transformation,
        mutation_policy=mutation_policy,
        permitted_repos=permitted_repos,
        bound_paths=bound_paths,
    )


def authorization_digest(auth: ApplyAuthorization) -> str:
    """Deterministic, versioned digest identifying an authorization's
    granted scope (`"v1|"` domain-separated, mirrors
    `mutation_plan.proposal_digest`)."""
    payload = {
        "transformation": auth.transformation,
        "mutation_policy": auth.mutation_policy,
        "permitted_repos": list(auth.permitted_repos),
        "bound_paths": {
            repo: list(paths) for repo, paths in auth.bound_paths.items()
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "v1|" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def authorize(
    rederived: RederivedProposal,
    auth: ApplyAuthorization,
    recorded_summary: Mapping[str, Any],
) -> None:
    """Raise `AuthorizationError` unless `rederived` both (1) matches its
    `recorded_summary` identity (`{binding, transformation, proposal_id}`)
    exactly and (2) falls within `auth`'s granted scope. Never returns a
    value or silently passes a mismatch — the absence of an exception IS
    the authorization.
    """
    recorded_binding = recorded_summary.get("binding")
    if recorded_binding != rederived.binding_id:
        raise AuthorizationError(
            "apply_authorization: binding mismatch: recorded "
            f"{recorded_binding!r} != rederived {rederived.binding_id!r}"
        )
    recorded_transformation = recorded_summary.get("transformation")
    if recorded_transformation != rederived.proposal.transformation:
        raise AuthorizationError(
            "apply_authorization: transformation mismatch: recorded "
            f"{recorded_transformation!r} != rederived "
            f"{rederived.proposal.transformation!r}"
        )
    recorded_proposal_id = recorded_summary.get("proposal_id")
    if recorded_proposal_id != rederived.proposal.id:
        raise AuthorizationError(
            "apply_authorization: proposal_id mismatch: recorded "
            f"{recorded_proposal_id!r} != rederived {rederived.proposal.id!r}"
        )

    if rederived.proposal.transformation != auth.transformation:
        raise AuthorizationError(
            "apply_authorization: proposal transformation "
            f"{rederived.proposal.transformation!r} is not authorized "
            f"(authorization covers {auth.transformation!r})"
        )
    if rederived.proposal.mutation_policy != auth.mutation_policy:
        raise AuthorizationError(
            "apply_authorization: proposal mutation_policy "
            f"{rederived.proposal.mutation_policy!r} != authorized "
            f"{auth.mutation_policy!r}"
        )
    outside_repos = set(rederived.proposal.selection) - set(auth.permitted_repos)
    if outside_repos:
        raise AuthorizationError(
            "apply_authorization: proposal selection contains repo outside "
            f"permitted_repos: {sorted(outside_repos)[0]}"
        )
    for repo in rederived.proposal.selection:
        proposed = set(rederived.proposal.bound_paths.get(repo, ()))
        authorized = set(auth.bound_paths.get(repo, ()))
        outside = proposed - authorized
        if outside:
            raise AuthorizationError(
                f"apply_authorization: {repo} bound_paths outside authorization: "
                f"{sorted(outside)[0]}"
            )
