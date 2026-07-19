#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Typed repository-mutation proposals and the transformation registry.

Pure module: no subprocess calls, no filesystem writes, no Nave interaction.
`lib/pulse/scripts/pen_orchestrator.py` (F6 Task 3) resolves a validated
`Proposal`'s `transformation` into exact argv via `resolve_argv` and drives
`nave_adapter.pen_exec` with it. See `lib/patterns/repository-mutations.md`
for the normative contract this module implements.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml


ACTOR_MODES = {"interactive", "scheduled"}
MUTATION_POLICIES = {"propose", "allow-listed", "allow"}
VALIDATION_KINDS = {"none", "json_schema"}


class MutationPlanError(ValueError):
    """Raised when registry metadata or a mutation proposal violates its contract."""


# --- registry -----------------------------------------------------------


@dataclass(frozen=True)
class ValidationSpec:
    """Post-execution validation a transformation's result must satisfy."""

    kind: str
    path: str | None = None
    schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class TransformationEntry:
    """One registered, strict-argv repository transformation."""

    id: str
    command_argv: tuple[str, ...]
    applies_to: tuple[str, ...]
    validation: ValidationSpec
    allow_scheduled: bool


@dataclass(frozen=True)
class TransformationRegistry:
    """Loaded, cross-validated `transformations.yaml` content."""

    transformations: dict[str, TransformationEntry]

    def get(self, transformation_id: str) -> TransformationEntry:
        entry = self.transformations.get(transformation_id)
        if entry is None:
            raise MutationPlanError(f"unknown transformation: {transformation_id}")
        return entry


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MutationPlanError(f"{label} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise MutationPlanError(f"{label} keys must be strings")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise MutationPlanError(f"{label} must be a list")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MutationPlanError(f"{label} must be a non-empty string")
    return value


def _only_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise MutationPlanError(f"unknown {label} key: {sorted(unknown)[0]}")


def _argv(value: Any, label: str) -> tuple[str, ...]:
    """Strict argv: a non-empty list of plain strings, no nested structures.

    Shell metacharacters inside an element (e.g. `$(rm -rf /)`, `; rm -rf /`,
    `| cat`) are never interpreted — they are opaque literal bytes handed to
    `subprocess.run(..., shell=False)` (see `nave_adapter.NaveRunner.run`).
    There is no templating or command substitution of any kind: an argv
    element is exactly the string committed in the registry, always.
    """
    items = _list(value, label)
    if not items:
        raise MutationPlanError(f"{label} must be a non-empty list")
    for index, item in enumerate(items):
        if isinstance(item, bool) or not isinstance(item, str):
            raise MutationPlanError(f"{label}[{index}] must be a string")
    return tuple(items)


def _load_validation(raw: Any, entry_id: str) -> ValidationSpec:
    item = _mapping(raw, f"transformation {entry_id}.validation")
    _only_keys(item, {"kind", "path", "schema"}, f"transformation {entry_id}.validation")
    kind = _string(item.get("kind"), f"transformation {entry_id}.validation.kind")
    if kind not in VALIDATION_KINDS:
        raise MutationPlanError(
            f"transformation {entry_id}.validation.kind invalid: {kind}"
        )
    if kind == "none":
        if "path" in item or "schema" in item:
            raise MutationPlanError(
                f"transformation {entry_id}.validation: kind 'none' takes no path/schema"
            )
        return ValidationSpec(kind="none")
    # kind == "json_schema"
    path = _string(item.get("path"), f"transformation {entry_id}.validation.path")
    schema = _mapping(item.get("schema"), f"transformation {entry_id}.validation.schema")
    return ValidationSpec(kind="json_schema", path=path, schema=schema)


def _applicability_predicate(predicate: str, entry_id: str) -> str:
    """Validate one `applies_to` predicate against the profile-dispatch grammar.

    Reuses `lib/pulse/scripts/profile_dispatch.py`'s applicability vocabulary
    verbatim (`always`, `profile:<id>`, `capability:<id>`,
    `evidence_path:<glob>`) so a transformation's repository eligibility is
    expressed the same way a scorecard check's applicability is.
    """
    predicate = _string(predicate, f"transformation {entry_id}.applies_to entry")
    if predicate == "always":
        return predicate
    if ":" not in predicate:
        raise MutationPlanError(
            f"transformation {entry_id}.applies_to invalid predicate: {predicate}"
        )
    kind, value = predicate.split(":", 1)
    if kind not in {"profile", "capability", "evidence_path"} or not value:
        raise MutationPlanError(
            f"transformation {entry_id}.applies_to invalid predicate: {predicate}"
        )
    return predicate


def _load_transformation(raw: Any, entry_id: str) -> TransformationEntry:
    item = _mapping(raw, f"transformation {entry_id}")
    _only_keys(
        item,
        {"id", "command_argv", "applies_to", "validation", "allow_scheduled"},
        f"transformation {entry_id}",
    )
    declared_id = _string(item.get("id"), f"transformation {entry_id}.id")
    if declared_id != entry_id:
        raise MutationPlanError(
            f"transformation {entry_id}.id must match its registry key: {declared_id}"
        )
    command_argv = _argv(item.get("command_argv"), f"transformation {entry_id}.command_argv")
    applies_to_raw = _list(item.get("applies_to"), f"transformation {entry_id}.applies_to")
    if not applies_to_raw:
        raise MutationPlanError(f"transformation {entry_id}.applies_to must be non-empty")
    applies_to = tuple(
        _applicability_predicate(predicate, entry_id) for predicate in applies_to_raw
    )
    validation = _load_validation(item.get("validation"), entry_id)
    allow_scheduled = item.get("allow_scheduled")
    if not isinstance(allow_scheduled, bool):
        raise MutationPlanError(
            f"transformation {entry_id}.allow_scheduled must be a boolean"
        )
    return TransformationEntry(
        id=entry_id,
        command_argv=command_argv,
        applies_to=applies_to,
        validation=validation,
        allow_scheduled=allow_scheduled,
    )


def load_registry(source: str | Path | dict[str, Any]) -> TransformationRegistry:
    """Load and cross-validate `transformations.yaml` content.

    `source` is either a path to a YAML file or an already-parsed mapping
    (tests and in-process callers may pass a dict directly).
    """
    if isinstance(source, dict):
        data = source
    elif isinstance(source, (str, Path)):
        path = Path(source)
        try:
            data = yaml.safe_load(path.read_text())
        except FileNotFoundError as exc:
            raise MutationPlanError(f"registry not found: {path}") from exc
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise MutationPlanError(f"could not load registry: {exc}") from exc
    else:
        raise MutationPlanError("registry source must be a path or a mapping")

    root = _mapping(data, "registry")
    _only_keys(root, {"transformations"}, "registry")
    if "transformations" not in root:
        raise MutationPlanError("missing required key: transformations")
    raw_transformations = _mapping(root["transformations"], "registry.transformations")

    transformations = {
        transformation_id: _load_transformation(value, transformation_id)
        for transformation_id, value in raw_transformations.items()
    }
    return TransformationRegistry(transformations)


def resolve_argv(entry: TransformationEntry) -> tuple[str, ...]:
    """Return a registered transformation's exact argv, verbatim.

    No templating, no interpolation of proposal fields, no shell
    interpretation of any element — the returned tuple is byte-identical to
    `entry.command_argv`.
    """
    return entry.command_argv


def transformation_applies(
    entry: TransformationEntry,
    profiles: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    evidence_paths: tuple[str, ...] = (),
) -> bool:
    """Evaluate `applies_to` (OR semantics) against one repository's evidence.

    Mirrors `profile_dispatch._is_applicable`'s predicate grammar so a
    transformation's eligibility reads the same way a scorecard check's
    applicability does.
    """
    for predicate in entry.applies_to:
        if predicate == "always":
            return True
        kind, value = predicate.split(":", 1)
        if kind == "profile" and value in profiles:
            return True
        if kind == "capability" and value in capabilities:
            return True
        if kind == "evidence_path" and any(
            fnmatchcase(path, value) for path in evidence_paths
        ):
            return True
    return False


# --- proposal -------------------------------------------------------------


@dataclass(frozen=True)
class Actor:
    """Attribution block — identical shape to the headless result contract's
    `actor:` (see `lib/patterns/headless-contract.md`)."""

    gh_login: str
    machine: str
    mode: str


@dataclass(frozen=True)
class Proposal:
    """A validated repository-mutation proposal.

    `selection` is the list of `owner/name` repositories this proposal
    targets. `expected_shas` is the expected-base guard: the SHA each
    selected repo must currently be at before the orchestrator (F6 Task 3)
    proceeds — a mismatch means the remote moved since the proposal was
    built and the run must block rather than mutate a stale base.
    """

    id: str
    selection: tuple[str, ...]
    transformation: str
    expected_shas: dict[str, str]
    mutation_policy: str
    actor: Actor


def _repo_name(value: Any, label: str) -> str:
    name = _string(value, label)
    parts = name.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise MutationPlanError(f"{label} must be owner/name: {name}")
    return name


def _load_actor(raw: Any) -> Actor:
    item = _mapping(raw, "proposal.actor")
    _only_keys(item, {"gh_login", "machine", "mode"}, "proposal.actor")
    gh_login = _string(item.get("gh_login"), "proposal.actor.gh_login")
    machine = _string(item.get("machine"), "proposal.actor.machine")
    mode = _string(item.get("mode"), "proposal.actor.mode")
    if mode not in ACTOR_MODES:
        raise MutationPlanError(f"proposal.actor.mode invalid: {mode}")
    return Actor(gh_login=gh_login, machine=machine, mode=mode)


def build_proposal(
    id: str,
    selection: list[str] | tuple[str, ...],
    transformation: str,
    expected_shas: dict[str, str],
    actor: dict[str, Any] | Actor,
    mutation_policy: str = "propose",
    registry: TransformationRegistry | None = None,
) -> Proposal:
    """Construct and validate a `Proposal`.

    Raises `MutationPlanError` for any contract violation — see
    `lib/patterns/repository-mutations.md` § Gating rules. When `registry`
    is supplied, the proposal is also checked against it (unknown
    transformation id, scheduled/`allow_scheduled` gating); omit it only for
    shape-only construction in tests that check registry gating separately.
    """
    proposal_id = _string(id, "proposal.id")
    selection_list = _list(list(selection), "proposal.selection")
    if not selection_list:
        raise MutationPlanError("proposal.selection must be non-empty")
    repos = tuple(_repo_name(repo, "proposal.selection entry") for repo in selection_list)
    if len(set(repos)) != len(repos):
        raise MutationPlanError("proposal.selection must not contain duplicate repos")

    transformation_id = _string(transformation, "proposal.transformation")

    shas = _mapping(expected_shas, "proposal.expected_shas")
    missing = set(repos) - set(shas)
    if missing:
        raise MutationPlanError(
            f"proposal.expected_shas missing entry for: {sorted(missing)[0]}"
        )
    extra = set(shas) - set(repos)
    if extra:
        raise MutationPlanError(
            f"proposal.expected_shas has entry outside selection: {sorted(extra)[0]}"
        )
    normalized_shas = {
        repo: _string(shas[repo], f"proposal.expected_shas[{repo}]") for repo in repos
    }

    policy = _string(mutation_policy, "proposal.mutation_policy")
    if policy not in MUTATION_POLICIES:
        raise MutationPlanError(f"proposal.mutation_policy invalid: {policy}")

    actor_block = actor if isinstance(actor, Actor) else _load_actor(actor)

    proposal = Proposal(
        id=proposal_id,
        selection=repos,
        transformation=transformation_id,
        expected_shas=normalized_shas,
        mutation_policy=policy,
        actor=actor_block,
    )

    if registry is not None:
        validate_proposal(proposal, registry)
    return proposal


def validate_proposal(proposal: Proposal, registry: TransformationRegistry) -> None:
    """Validate a `Proposal` against a loaded registry.

    Raises `MutationPlanError` when the transformation is unknown, or when
    the proposal's actor runs in `scheduled` mode against a transformation
    that does not set `allow_scheduled: true` (see the F6 global constraint:
    "automatic mode permits only registered transformation IDs").
    """
    entry = registry.get(proposal.transformation)
    if proposal.actor.mode == "scheduled" and not entry.allow_scheduled:
        raise MutationPlanError(
            f"transformation not allowed in scheduled mode: {proposal.transformation}"
        )
