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

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from lib.pulse.scripts.executor_probe import validate_command_argv


ACTOR_MODES = {"interactive", "scheduled"}
MUTATION_POLICIES = {"propose", "allow-listed", "allow"}
VALIDATION_KINDS = {"none", "json_schema", "paths_changed"}


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
    """One registered repository transformation. `command_argv` is strict
    unless `params` declares placeholders — see `resolve_argv`."""

    id: str
    command_argv: tuple[str, ...]
    applies_to: tuple[str, ...]
    validation: ValidationSpec
    allow_scheduled: bool
    params: tuple[str, ...] = ()


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


_PACKAGE_PARAM_PATTERN = re.compile(
    r"^(@[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*|[A-Za-z0-9][A-Za-z0-9._-]*)$"
)
_VERSION_PARAM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]*$")
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_]+)\}")


def _validate_param_value(key: str, value: str) -> str:
    """Validate one templated argv substitution value.

    Param-aware: `package` and `version` have different legal shapes (a
    scoped npm package's normalized identity is `@scope/name`; one
    character class for both would reject every scoped package). Both
    patterns preserve the two security invariants strict argv relies on:
    the first character is alphanumeric (never a leading `-`, so a
    substituted value can never become a flag), and the body excludes
    every character with argv/shell meaning (`=`, whitespace, and the
    shell metacharacters `;`, `|`, `&`, `$`, backtick, quotes, `<`, `>`,
    `(`, `)`) — `/` and `@` are inert in a single argv element. A
    PEP 440 epoch (`1!2.3.4`) is rejected: `!` is not in either class,
    v1 fail-closed.
    """
    if not isinstance(value, str):
        raise MutationPlanError(f"transform_params[{key!r}] must be a string")
    pattern = _PACKAGE_PARAM_PATTERN if key == "package" else _VERSION_PARAM_PATTERN
    if not pattern.match(value):
        raise MutationPlanError(f"transform_params[{key!r}] invalid value: {value!r}")
    return value


def _check_undeclared_placeholders(
    command_argv: tuple[str, ...], params: tuple[str, ...], entry_id: str
) -> None:
    """Fail-closed check for entries that opt into templating (`params`
    non-empty): every `{name}` in `command_argv` must be a declared param.

    Entries that never declare `params` (the overwhelming majority — every
    pre-dependency-bump transformation) skip this check entirely: their
    `command_argv` may contain literal `{...}` text (e.g. shell brace
    syntax) that is never templated and must survive `resolve_argv`
    byte-identical, exactly as before this feature existed.
    """
    if not params:
        return
    declared = set(params)
    for index, element in enumerate(command_argv):
        for name in _PLACEHOLDER_PATTERN.findall(element):
            if name not in declared:
                raise MutationPlanError(
                    f"transformation {entry_id}.command_argv[{index}] has undeclared "
                    f"placeholder {{{name}}}: not in params"
                )


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
    if kind in ("none", "paths_changed"):
        if "path" in item or "schema" in item:
            raise MutationPlanError(
                f"transformation {entry_id}.validation: kind '{kind}' takes no path/schema"
            )
        return ValidationSpec(kind=kind)
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
        {"id", "command_argv", "applies_to", "validation", "allow_scheduled", "params"},
        f"transformation {entry_id}",
    )
    declared_id = _string(item.get("id"), f"transformation {entry_id}.id")
    if declared_id != entry_id:
        raise MutationPlanError(
            f"transformation {entry_id}.id must match its registry key: {declared_id}"
        )
    command_argv = _argv(item.get("command_argv"), f"transformation {entry_id}.command_argv")
    try:
        validate_command_argv(command_argv, entry_id)
    except ValueError as exc:
        raise MutationPlanError(str(exc)) from exc
    params_raw = item.get("params")
    params = (
        tuple(
            _string(p, f"transformation {entry_id}.params entry")
            for p in _list(params_raw, f"transformation {entry_id}.params")
        )
        if params_raw is not None
        else ()
    )
    _check_undeclared_placeholders(command_argv, params, entry_id)
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
        params=params,
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


def resolve_argv(
    entry: TransformationEntry, params: dict[str, str] | None = None
) -> tuple[str, ...]:
    """Return a registered transformation's argv, optionally with declared
    placeholders expanded from `params`.

    `params is None` (all callers before this change, and every entry with
    no declared `params`) returns `entry.command_argv` verbatim — byte-
    identical, no interpolation, matching the original strict-argv
    contract. A `dict` expands every `{key}` the registry already
    validated as declared at load time (re-checked here too, fail-closed
    defense in depth); every substituted value is re-validated with
    `_validate_param_value` immediately before insertion. The substitution
    still lands in a single argv element handed to
    `subprocess.run(..., shell=False)` — no shell, no splitting, no
    reinterpretation of any element boundary.
    """
    if params is None:
        return entry.command_argv
    missing = [key for key in entry.params if key not in params]
    if missing:
        raise MutationPlanError(
            f"resolve_argv: missing declared param(s) for {entry.id}: {', '.join(missing)}"
        )

    def _substitute(element: str) -> str:
        def _sub_one(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in entry.params:
                raise MutationPlanError(
                    f"resolve_argv: undeclared placeholder {{{key}}} in {entry.id}"
                )
            return _validate_param_value(key, params[key])

        return _PLACEHOLDER_PATTERN.sub(_sub_one, element)

    return tuple(_substitute(element) for element in entry.command_argv)


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
    targets. `expected_shas` is the expected-base guard: the commit SHA
    each selected repo must currently be at before the orchestrator (F6
    Task 3) proceeds — a mismatch means the remote moved since the
    proposal was built and the run must block rather than mutate a stale
    base. `transform_params` templates `command_argv` placeholders
    (dependency-bump only; empty for every other source). `expected_tree_shas`
    is a second, independent drift guard on the *tree* SHA the proposal's
    target was computed from (dependency-bump only; `None` for every other
    source, which never populates or checks it).
    """

    id: str
    selection: tuple[str, ...]
    transformation: str
    expected_shas: dict[str, str]
    mutation_policy: str
    actor: Actor
    bound_paths: dict[str, tuple[str, ...]] = field(default_factory=dict)
    transform_params: dict[str, str] = field(default_factory=dict)
    expected_tree_shas: dict[str, str] | None = None


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
    bound_paths: dict[str, list[str] | tuple[str, ...]] | None = None,
    transform_params: dict[str, str] | None = None,
    expected_tree_shas: dict[str, str] | None = None,
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

    normalized_bound_paths: dict[str, tuple[str, ...]] = {}
    if bound_paths is not None:
        b_map = _mapping(bound_paths, "proposal.bound_paths")
        for repo, paths in b_map.items():
            repo_key = _repo_name(repo, "proposal.bound_paths key")
            if repo_key not in repos:
                raise MutationPlanError(
                    f"proposal.bound_paths has entry outside selection: {repo_key}"
                )
            path_list = _list(list(paths), f"proposal.bound_paths[{repo_key}]")
            normalized_bound_paths[repo_key] = tuple(
                _string(p, f"proposal.bound_paths[{repo_key}] entry") for p in path_list
            )

    if policy == "allow-listed":
        if not normalized_bound_paths:
            raise MutationPlanError(
                "proposal.bound_paths must be non-empty when mutation_policy is allow-listed"
            )
        missing_bounds = set(repos) - set(normalized_bound_paths)
        if missing_bounds:
            raise MutationPlanError(
                f"proposal.bound_paths missing entry for: {sorted(missing_bounds)[0]}"
            )
        empty_bounds = [
            repo for repo, paths in normalized_bound_paths.items() if not paths
        ]
        if empty_bounds:
            raise MutationPlanError(
                "proposal.bound_paths must be non-empty for: "
                f"{sorted(empty_bounds)[0]}"
            )

    normalized_transform_params: dict[str, str] = {}
    if transform_params is not None:
        raw_params = _mapping(transform_params, "proposal.transform_params")
        if registry is not None:
            entry = registry.get(transformation_id)
            if not entry.params and raw_params:
                raise MutationPlanError(
                    f"proposal.transform_params must be empty for {transformation_id!r} "
                    "(no declared params)"
                )
            unknown_keys = set(raw_params) - set(entry.params)
            if unknown_keys:
                raise MutationPlanError(
                    f"unknown transform_params key: {sorted(unknown_keys)[0]}"
                )
            missing_keys = set(entry.params) - set(raw_params)
            if entry.params and missing_keys:
                raise MutationPlanError(
                    "missing declared transform_params key(s): "
                    f"{', '.join(sorted(missing_keys))}"
                )
            normalized_transform_params = {
                key: _validate_param_value(key, value) for key, value in raw_params.items()
            }
        else:
            normalized_transform_params = {
                _string(key, "proposal.transform_params key"): _string(
                    value, f"proposal.transform_params[{key}]"
                )
                for key, value in raw_params.items()
            }

    normalized_expected_tree_shas: dict[str, str] | None = None
    if expected_tree_shas is not None:
        tree_shas = _mapping(expected_tree_shas, "proposal.expected_tree_shas")
        missing_tree = set(repos) - set(tree_shas)
        if missing_tree:
            raise MutationPlanError(
                f"proposal.expected_tree_shas missing entry for: {sorted(missing_tree)[0]}"
            )
        extra_tree = set(tree_shas) - set(repos)
        if extra_tree:
            raise MutationPlanError(
                f"proposal.expected_tree_shas has entry outside selection: {sorted(extra_tree)[0]}"
            )
        normalized_expected_tree_shas = {
            repo: _string(tree_shas[repo], f"proposal.expected_tree_shas[{repo}]")
            for repo in repos
        }

    proposal = Proposal(
        id=proposal_id,
        selection=repos,
        transformation=transformation_id,
        expected_shas=normalized_shas,
        mutation_policy=policy,
        actor=actor_block,
        bound_paths=normalized_bound_paths,
        transform_params=normalized_transform_params,
        expected_tree_shas=normalized_expected_tree_shas,
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
    if entry.validation.kind == "paths_changed":
        missing = set(proposal.selection) - set(proposal.bound_paths)
        if missing:
            raise MutationPlanError(
                f"proposal.bound_paths missing entry for: {sorted(missing)[0]}"
            )
        extra = set(proposal.bound_paths) - set(proposal.selection)
        if extra:
            raise MutationPlanError(
                f"proposal.bound_paths has entry outside selection: {sorted(extra)[0]}"
            )


def proposal_digest(proposal: Proposal) -> str:
    """Deterministic, versioned digest identifying a proposal's content.

    `"v1|"` domain-separates this digest space from any future version.
    The payload spans every field that defines what the proposal actually
    authorizes — transformation, selection, expected bases, bound paths,
    mutation policy, id, actor — so a change to any of them changes the
    digest. Key order and tuple-vs-list are normalized (`sort_keys=True`,
    lists) so equal proposals always produce the same digest.
    """
    payload = {
        "id": proposal.id,
        "selection": list(proposal.selection),
        "transformation": proposal.transformation,
        "expected_shas": dict(proposal.expected_shas),
        "bound_paths": {
            repo: list(paths) for repo, paths in proposal.bound_paths.items()
        },
        "transform_params": dict(sorted(proposal.transform_params.items())),
        "expected_tree_shas": dict(sorted((proposal.expected_tree_shas or {}).items())),
        "actor": {
            "gh_login": proposal.actor.gh_login,
            "machine": proposal.actor.machine,
            "mode": proposal.actor.mode,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "v1|" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
