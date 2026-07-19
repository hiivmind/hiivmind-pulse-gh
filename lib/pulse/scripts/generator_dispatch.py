#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Generator adapter dispatch (F7 Task 3).

Turns a drifted generated-artifact binding into an F6 Nave mutation `Proposal`.
Generators are registered adapters: each one names a registered transformation
(the only source of argv), declares which repositories it applies to, and
maintains an output-path allowlist that guards where generated files may be
written.

Pure module: no subprocess calls, no filesystem writes, no Nave interaction.
See `lib/patterns/repository-mutations.md` for the mutation contract and
`templates/generators.yaml.template` for the committed registry shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lib.pulse.scripts import impact, mutation_plan, profile_dispatch
from lib.pulse.scripts.mutation_plan import (
    MutationPlanError,
    TransformationRegistry,
    ValidationSpec,
    _load_validation,
    build_proposal,
)
from lib.pulse.scripts.profile_dispatch import RepositoryProfile, _is_applicable


@dataclass(frozen=True)
class Generator:
    """One registered generator adapter.

    `applies_to` uses the same predicate grammar as scorecard checks and
    transformations (`always`, `profile:<id>`, `capability:<id>`,
    `evidence_path:<glob>`). `output_paths` is an allowlist: every file a
    binding asks this generator to produce must match at least one glob.
    """

    id: str
    applies_to: tuple[str, ...]
    transformation: str
    source_paths: tuple[str, ...]
    output_paths: tuple[str, ...]
    validation: ValidationSpec


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


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


def _applicability_predicate(predicate: str, generator_id: str) -> str:
    """Validate one `applies_to` predicate against the profile_dispatch grammar.

    Reuses `profile_dispatch._is_applicable` on a deliberately empty profile
    and evidence set: any syntactically valid predicate either matches
    immediately (`always`) or returns `False` without raising. Invalid
    predicates raise `ConfigError`, which we translate into a load-time
    `MutationPlanError`.
    """
    predicate = _string(predicate, f"generator {generator_id}.applies_to entry")
    try:
        _is_applicable(
            predicate,
            RepositoryProfile(profiles=(), scorecard=""),
            {},
        )
    except profile_dispatch.ConfigError as exc:
        raise MutationPlanError(
            f"generator {generator_id}.applies_to invalid predicate: {predicate}"
        ) from exc
    return predicate


def _load_generator(
    raw: Any,
    generator_id: str,
    registry: TransformationRegistry,
) -> Generator:
    item = _mapping(raw, f"generator {generator_id}")
    # `command`/`command_argv` are not valid generator fields, but we allow
    # them here so we can reject them with an explicit, helpful message that
    # points callers at the transformation registry.
    _only_keys(
        item,
        {
            "id",
            "applies_to",
            "transformation",
            "source_paths",
            "output_paths",
            "validation",
            "command",
            "command_argv",
        },
        f"generator {generator_id}",
    )

    declared_id = _string(item.get("id"), f"generator {generator_id}.id")
    if declared_id != generator_id:
        raise MutationPlanError(
            f"generator {generator_id}.id must match its registry key: {declared_id}"
        )

    applies_to_raw = _list(item.get("applies_to"), f"generator {generator_id}.applies_to")
    if not applies_to_raw:
        raise MutationPlanError(
            f"generator {generator_id}.applies_to must be non-empty"
        )
    applies_to = tuple(
        _applicability_predicate(predicate, generator_id) for predicate in applies_to_raw
    )

    transformation_id = _string(
        item.get("transformation"), f"generator {generator_id}.transformation"
    )
    # Fail closed on an unknown transformation id. The registry lookup also
    # gives us the entry later callers (e.g. pen_orchestrator) need.
    registry.get(transformation_id)

    # Generators never carry their own command line; the transformation
    # registry is the only source of argv.
    for forbidden in ("command", "command_argv"):
        if forbidden in item:
            raise MutationPlanError(
                f"generator {generator_id} must not declare a '{forbidden}' key; "
                "the transformation registry is the only argv source"
            )

    source_paths = tuple(
        _string(path, f"generator {generator_id}.source_paths[{index}]")
        for index, path in enumerate(
            _list(item.get("source_paths"), f"generator {generator_id}.source_paths")
        )
    )
    if not source_paths:
        raise MutationPlanError(
            f"generator {generator_id}.source_paths must be non-empty"
        )

    output_paths = tuple(
        _string(path, f"generator {generator_id}.output_paths[{index}]")
        for index, path in enumerate(
            _list(item.get("output_paths"), f"generator {generator_id}.output_paths")
        )
    )
    if not output_paths:
        raise MutationPlanError(
            f"generator {generator_id}.output_paths must be non-empty"
        )

    validation = _load_validation(item.get("validation"), generator_id)

    return Generator(
        id=generator_id,
        applies_to=applies_to,
        transformation=transformation_id,
        source_paths=source_paths,
        output_paths=output_paths,
        validation=validation,
    )


def load_generators(
    data: dict[str, Any] | str | Path,
    registry: TransformationRegistry,
) -> dict[str, Generator]:
    """Load and cross-validate a generator registry.

    `data` is either a path to a YAML file or an already-parsed mapping.
    A top-level `generators:` key is accepted and unwrapped, so the same
    file shape `templates/generators.yaml.template` uses loads directly.

    Fail-closed errors:
      - unknown `transformation` id
      - empty `output_paths` (or `source_paths`)
      - presence of a `command` or `command_argv` key
      - invalid `applies_to` predicate grammar
    """
    if isinstance(data, dict):
        root = data
    elif isinstance(data, (str, Path)):
        path = Path(data)
        try:
            root = yaml.safe_load(path.read_text())
        except FileNotFoundError as exc:
            raise MutationPlanError(f"generators not found: {path}") from exc
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise MutationPlanError(f"could not load generators: {exc}") from exc
    else:
        raise MutationPlanError("generators source must be a path or a mapping")

    root = _mapping(root, "generators")
    if "generators" in root and isinstance(root["generators"], dict):
        root = _mapping(root["generators"], "generators.generators")

    return {
        generator_id: _load_generator(raw, generator_id, registry)
        for generator_id, raw in root.items()
    }


# ---------------------------------------------------------------------------
# Output-path allowlist matching
# ---------------------------------------------------------------------------


def path_matches_allowlist(path: str, output_paths: tuple[str, ...]) -> bool:
    """Return True when `path` matches at least one `output_paths` glob.

    Uses `impact._glob_to_regex` so the allowlist semantics exactly match the
    watch-path semantics used elsewhere in Pulse (`*` never crosses `/`,
    `**` does).
    """
    return any(impact._glob_to_regex(pattern).match(path) for pattern in output_paths)


# ---------------------------------------------------------------------------
# Applicability
# ---------------------------------------------------------------------------


def generator_applies(
    generator: Generator,
    repository: RepositoryProfile,
    evidence: dict[str, Any],
) -> bool:
    """Return True if any of the generator's `applies_to` predicates match.

    This is the pure, side-effect-free gate the caller checks before invoking
    `dispatch`. It reuses `profile_dispatch._is_applicable` verbatim.
    """
    for predicate in generator.applies_to:
        if _is_applicable(predicate, repository, evidence):
            return True
    return False


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def dispatch(
    generator: Generator,
    binding: dict[str, Any],
    snapshot: dict[str, Any],
    actor: dict[str, Any] | mutation_plan.Actor,
    mutation_policy: str = "propose",
) -> mutation_plan.Proposal:
    """Turn a drifted binding into a validated Nave mutation `Proposal`.

    `selection` is exactly `[binding["source"]]` and `expected_shas` maps
    that repo to `snapshot[binding["source"]][binding["branch"]]["head"]`.
    Every path in `binding["files"]` must match at least one of the
    generator's `output_paths` globs; any path outside the allowlist raises
    `MutationPlanError` without producing a proposal.
    """
    source = _string(binding.get("source"), "binding.source")
    branch = _string(binding.get("branch"), "binding.branch")
    binding_id = _string(binding.get("id"), "binding.id")

    repo_snap = snapshot.get(source)
    if repo_snap is None:
        raise MutationPlanError(
            f"dispatch: source repo {source!r} not found in snapshot"
        )
    branch_snap = repo_snap.get(branch)
    if branch_snap is None:
        raise MutationPlanError(
            f"dispatch: branch {branch!r} not found for {source!r} in snapshot"
        )
    head = branch_snap.get("head")
    if not isinstance(head, str) or not head.strip():
        raise MutationPlanError(
            f"dispatch: no head resolved for {source!r} {branch!r}"
        )

    files = binding.get("files") or []
    files = _list(list(files), "binding.files")
    for index, file_entry in enumerate(files):
        file_item = _mapping(file_entry, f"binding.files[{index}]")
        path = _string(file_item.get("path"), f"binding.files[{index}].path")
        if not path_matches_allowlist(path, generator.output_paths):
            raise MutationPlanError(
                f"dispatch: binding file {path!r} is outside generator "
                f"{generator.id!r} output_paths allowlist"
            )

    proposal_id = f"generate-{generator.id}-{binding_id}"
    return build_proposal(
        id=proposal_id,
        selection=[source],
        transformation=generator.transformation,
        expected_shas={source: head},
        actor=actor,
        mutation_policy=mutation_policy,
    )
