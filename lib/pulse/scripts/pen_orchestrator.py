#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Drive a validated mutation `Proposal` through a Nave pen, safely.

The state machine: `planned -> created -> executed -> validated ->
proposed | blocked | failed` (F6 plan, verbatim). This module is pure
w.r.t. subprocess — every Nave interaction is a call into
`lib.pulse.scripts.nave_adapter`'s `pen_create`/`pen_status`/`pen_exec`/
`probe` functions, using the injectable `runner` `execute()` receives as
its second argument. This is the same `runner` idiom `nave_adapter.py`
and `test_nave_adapter.py` already establish (`NaveRunner`,
`RecordingRunner`, `QueuedRunner`) — tests never touch a real `nave`
binary or the network; `execute`'s second parameter is that runner
(named `nave_adapter` in the interface per the F6 plan, since together
with the statically-imported `nave_adapter` module it forms "the Nave
adapter").

This orchestrator is **propose-only, unconditionally**: it never emits
`--commit`/`--push-changes` to `pen exec` regardless of a proposal's
`mutation_policy`. Its terminal success state is always `proposed` — a
commit/push/PR action for something else to apply later, never performed
here. A proposal whose `mutation_policy` is not `propose`, or a `PenPlan`
that explicitly requests a push, is a **forbidden push** and blocks
before any Nave call. See `lib/patterns/repository-mutations.md` for the
full mutation-policy vocabulary; Task 4 (F6 plan) is where a policy other
than `propose` gets to actually authorize a later apply step.

## `validation.kind == "json_schema"`: injectable file reader

`mutation_plan.ValidationSpec` declares a `json_schema` kind that
validates a repo-relative output file's parsed content against an inline
JSON Schema. No Nave CLI surface exposes that content directly: `pen
show`/`pen status` (`nave_pen::storage::Pen` / `state::RepoState`) carry
no local clone path, and `pen exec`'s stdout/stderr are opaque by
contract (Task 1: "never parsed as data"). `nave materialize` fetches
committed content from the GitHub API, not a pen's local uncommitted
working tree, so it cannot stand in either. `pen_orchestrator` therefore
never reads a pen's working tree itself — instead `execute` accepts an
injectable `read_repo_file: Callable[[str, str], bytes] | None` seam
(repo `owner/name` + relative path -> bytes, raising `FileNotFoundError`
when absent). A caller that knows its pen root (e.g. a future `pen
cat`/`--json` adapter, or a caller with direct filesystem access to the
pen's clones) wires a reader in; Pulse never hardcodes Nave's internal
pen layout itself. With no reader supplied, `json_schema` validation
still fails closed (see `_validate` below) with a message explaining
*why* — the capability gap is real, but no longer unconditional.

## expected-SHA guard: injectable head reader

`Proposal.expected_shas` (`mutation_plan.py`) is the expected-base guard:
each selected repo's SHA at proposal-build time, which `execute` must
verify still matches before mutating anything (a stale base is never
silently mutated — see `lib/patterns/repository-mutations.md`). No Nave
CLI surface exposes a per-repo SHA either: `pen show`/`pen status`
(verified against `crates/nave_pen/src/state.rs` fixtures) carry
`working_tree`/`freshness`/`divergence`, never a hex SHA. So, exactly like
`read_repo_file` above, `execute` accepts a second injectable seam:
`read_repo_head: Callable[[str], str] | None` (repo `owner/name` -> current
HEAD SHA as hex, raising `FileNotFoundError`/`KeyError` when the repo is
unknown to the caller). A caller with direct filesystem/git access to the
pen's clones (or a future Nave surface that exposes this) wires a reader
in. With `expected_shas` non-empty and no reader supplied, verification
fails closed — blocked, not skipped — with a message naming the gap. This
check runs after pen creation and the freshness/cleanliness preflight
(a pen must exist, and have a resolvable HEAD, before it can be checked)
and strictly before `pen exec`.

## `validation.kind == "paths_changed"`: injectable changed-paths reader

`mutation_plan.ValidationSpec` declares a `paths_changed` kind that asserts
the set of changed paths in each repo matches exactly that repo's `bound_paths`
on the `Proposal`. `execute` accepts an injectable
`read_repo_changed_paths: Callable[[str], tuple[str, ...]] | None` seam (repo
`owner/name` -> repo-relative paths that changed in that repo's pen clone).
With no reader supplied and `kind == "paths_changed"`, validation fails closed
as `blocked` with a message explaining that a reader is required.

## NEEDS_CONTEXT: per-repo command-failure attribution

`nave_pen::ops::exec_pen` (verified against
`crates/nave_pen/src/ops.rs`) iterates a pen's repos and `bail!`s
immediately at the **first** repo whose command exits non-zero — it never
attempts the remaining repos, and its only externally visible signal is
one aggregate process exit code. There is no structured per-repo
success/failure record, and `pen_exec`'s stdout/stderr must never be
parsed for data (Task 1 contract) — so the exact failing repo cannot be
identified from the adapter surface without violating that contract. On
an exec failure this module therefore marks **every** selected repo's
outcome `"failed"` and fails the whole run, rather than fabricating a
false per-repo split by guessing from opaque text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, Callable

from lib.pulse.scripts import nave_adapter
from lib.pulse.scripts.mutation_plan import (
    Actor,
    Proposal,
    TransformationEntry,
    ValidationSpec,
    resolve_argv,
)


class PenOrchestratorError(ValueError):
    """Raised for a structurally invalid `PenPlan` — a caller/programmer
    bug (e.g. a mismatched resolved transformation), never a runtime
    gating outcome. Runtime gating outcomes are always reported via a
    `PenRunResult`, never raised."""


@dataclass(frozen=True)
class PenPlan:
    """Everything `execute` needs to drive one pen run.

    Bundles the validated `Proposal` (`mutation_plan.py`) with its
    already-resolved `TransformationEntry` — registry loading and lookup
    are the caller's job; `execute` never loads a registry itself, it
    only requires `entry.id == proposal.transformation` (checked, raises
    `PenOrchestratorError` otherwise). `pen_name`/`query` are the pen
    provisioning details only the orchestrator needs: the pen to
    create and the `PenQuery` used to seed it. `request_push` records an
    explicit caller ask to commit/push; since this orchestrator's
    terminal success state is always `proposed` (propose-only, never
    pushes — see module docstring), `request_push=True` is always a
    forbidden-push attempt and blocks before any Nave call.
    """

    proposal: Proposal
    entry: TransformationEntry
    pen_name: str
    query: nave_adapter.PenQuery
    request_push: bool = False


@dataclass(frozen=True)
class PenRunResult:
    """Terminal record of one orchestrator run — the attribution record.

    Carries actor, machine (inside `actor`), probed Nave version, pen
    name, selection, transformation (command) ID, and per-repo outcome —
    the F6 attribution requirement, built entirely from the `Proposal`
    that gated execution plus what the adapter actually observed; nothing
    here is inferred or reconstructed after the fact.

    `repo_outcomes` maps each selected `owner/name` to
    `"ok" | "failed" | "blocked"`. `reason` is set whenever `state` is
    `"blocked"` or `"failed"`.
    """

    state: str
    proposal_id: str
    transformation: str
    pen_name: str
    selection: tuple[str, ...]
    actor: Actor
    nave_version: str | None
    repo_outcomes: dict[str, str]
    reason: str | None = None


def _probe_version(runner) -> str | None:
    try:
        result = nave_adapter.probe(runner)
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    version = result.get("version")
    return version if isinstance(version, str) else None


def _result(plan: PenPlan, state: str, version: str | None, repo_outcomes: dict[str, str], reason: str | None) -> PenRunResult:
    return PenRunResult(
        state=state,
        proposal_id=plan.proposal.id,
        transformation=plan.proposal.transformation,
        pen_name=plan.pen_name,
        selection=plan.proposal.selection,
        actor=plan.proposal.actor,
        nave_version=version,
        repo_outcomes=repo_outcomes,
        reason=reason,
    )


_SCHEMA_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _schema_errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Minimal, pure structural check against a JSON Schema subset: `type`
    (object/array/string/number/integer/boolean/null), `required` (list of
    keys on objects), `properties` (recursive). No external `jsonschema`
    dependency — any schema keyword outside this subset is simply ignored."""
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None:
        checker = _SCHEMA_TYPE_CHECKS.get(expected_type)
        if checker is None or not checker(value):
            errors.append(f"{path}: expected type {expected_type!r}, got {type(value).__name__}")
            return errors
    required = schema.get("required")
    if required:
        if not isinstance(value, dict):
            errors.append(f"{path}: 'required' check needs an object, got {type(value).__name__}")
        else:
            errors.extend(
                f"{path}: missing required property {key!r}"
                for key in required
                if key not in value
            )
    properties = schema.get("properties")
    if properties and isinstance(value, dict):
        for key, subschema in properties.items():
            if key in value:
                errors.extend(_schema_errors(value[key], subschema, f"{path}.{key}"))
    return errors


def _validate_repo_output(spec: ValidationSpec, read_repo_file, repo: str) -> str | None:
    """Read and schema-check `spec.path` for one `repo` via the injected
    `read_repo_file` seam; return an error string or `None` on success."""
    try:
        raw = read_repo_file(repo, spec.path)
    except FileNotFoundError as exc:
        return f"{repo}: validation file {spec.path!r} not found: {exc}"
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return f"{repo}: validation file {spec.path!r} is not valid JSON: {exc}"
    errors = _schema_errors(data, spec.schema or {})
    if errors:
        return f"{repo}: schema validation failed for {spec.path!r}: {'; '.join(errors)}"
    return None


def _match_bound_path(pattern: str, path: str) -> bool:
    if "*" in pattern:
        return fnmatchcase(path, pattern)
    return path == pattern


def _validate_repo_paths_changed(
    bound_patterns: tuple[str, ...],
    read_repo_changed_paths: Callable[[str], tuple[str, ...]],
    repo: str,
) -> str | None:
    try:
        changed_raw = read_repo_changed_paths(repo)
    except Exception as exc:
        return f"{repo}: could not read changed paths: {exc}"

    changed = set(changed_raw)
    if not changed:
        return f"{repo}: no paths changed (expected changes in bound_paths)"

    unmatched = [
        p for p in sorted(changed) if not any(_match_bound_path(pat, p) for pat in bound_patterns)
    ]
    if unmatched:
        return f"{repo}: path changed outside bound_paths allowlist: {', '.join(unmatched)}"

    missing_exact = [
        pat for pat in bound_patterns if "*" not in pat and pat not in changed
    ]
    if missing_exact:
        return f"{repo}: bound_paths exact path did not change: {', '.join(sorted(missing_exact))}"

    return None


def _validate(
    spec: ValidationSpec,
    read_repo_file: Callable[[str, str], bytes] | None,
    read_repo_changed_paths: Callable[[str], tuple[str, ...]] | None,
    bound_paths: dict[str, tuple[str, ...]],
    selection: tuple[str, ...],
) -> tuple[dict[str, str], str, str] | None:
    """Run the post-exec check `spec` declares across `selection`; return
    `None` on success, or `(repo_outcomes, reason, state)` on failure. `kind ==
    "none"` always passes. `kind == "json_schema"` or `"paths_changed"` with no
    reader fails closed uniformly (see module docstring); with a reader, each repo
    is checked independently so failure is attributed per repo."""
    if spec.kind == "none":
        return None

    if spec.kind == "json_schema":
        if read_repo_file is None:
            reason = (
                f"validation kind 'json_schema' (path={spec.path!r}) requires a "
                "read_repo_file callable to read the pen's local output file "
                "content — none was provided to execute(); pen show/status "
                "carry no clone path, pen exec stdout/stderr are opaque by "
                "contract, and `materialize` fetches committed GitHub content, "
                "not a pen's local working tree, so pen_orchestrator cannot "
                "read repo files on its own"
            )
            return ({repo: "failed" for repo in selection}, reason, "failed")
        errors = {
            repo: error
            for repo in selection
            if (error := _validate_repo_output(spec, read_repo_file, repo)) is not None
        }
        if not errors:
            return None
        repo_outcomes = {repo: ("failed" if repo in errors else "ok") for repo in selection}
        reason = "; ".join(errors[repo] for repo in selection if repo in errors)
        return (repo_outcomes, reason, "failed")

    if spec.kind == "paths_changed":
        if read_repo_changed_paths is None:
            reason = (
                "validation kind 'paths_changed' requires a "
                "read_repo_changed_paths callable to read the pen's changed "
                "paths — none was provided to execute(); pen show/status "
                "carry no clone path, pen exec stdout/stderr are opaque by "
                "contract, and `materialize` fetches committed GitHub content, "
                "not a pen's local working tree, so pen_orchestrator cannot "
                "read repo changed paths on its own"
            )
            return ({repo: "blocked" for repo in selection}, reason, "blocked")
        errors = {
            repo: error
            for repo in selection
            if (
                error := _validate_repo_paths_changed(
                    bound_paths.get(repo, ()), read_repo_changed_paths, repo
                )
            )
            is not None
        }
        if not errors:
            return None
        repo_outcomes = {repo: ("failed" if repo in errors else "ok") for repo in selection}
        reason = "; ".join(errors[repo] for repo in selection if repo in errors)
        return (repo_outcomes, reason, "failed")

    return None


def execute(
    plan: PenPlan,
    nave_adapter_runner,
    *,
    read_repo_file: Callable[[str, str], bytes] | None = None,
    read_repo_head: Callable[[str], str] | None = None,
    read_repo_changed_paths: Callable[[str], tuple[str, ...]] | None = None,
) -> PenRunResult:
    """Drive `plan` through the pen state machine using `nave_adapter_runner`.

    `nave_adapter_runner` is the injectable runner (`NaveRunner` /
    `RecordingRunner` / `QueuedRunner` / `NaveRunner(fixtures=...)`) passed
    to the statically-imported `nave_adapter` module's functions — this
    function never imports or calls `subprocess` itself.

    `read_repo_file`, if supplied, is called as `read_repo_file(repo,
    relative_path) -> bytes` (raising `FileNotFoundError` when the path is
    absent) to satisfy `kind: json_schema` validation entries.

    `read_repo_head`, if supplied, is called as `read_repo_head(repo) ->
    str` (raising `FileNotFoundError` or `KeyError` when `repo` is unknown)
    to satisfy `proposal.expected_shas` verification — see the module
    docstring's "expected-SHA guard" section. These two callables are the
    only filesystem seams this module accepts.
    """
    proposal = plan.proposal
    entry = plan.entry
    if entry.id != proposal.transformation:
        raise PenOrchestratorError(
            f"plan.entry.id ({entry.id!r}) does not match "
            f"plan.proposal.transformation ({proposal.transformation!r})"
        )

    runner = nave_adapter_runner
    version = _probe_version(runner)
    selection = proposal.selection

    # --- forbidden push: checked before any Nave call --------------------
    if plan.request_push or proposal.mutation_policy != "propose":
        return _result(
            plan,
            "blocked",
            version,
            {repo: "blocked" for repo in selection},
            "push forbidden: pen_orchestrator is propose-only and never "
            f"commits or pushes; got mutation_policy={proposal.mutation_policy!r} "
            f"request_push={plan.request_push!r}",
        )

    # --- planned -> created ------------------------------------------------
    handle = nave_adapter.pen_create(runner, plan.query, plan.pen_name)
    if handle.state != "ok":
        return _result(
            plan,
            "failed",
            version,
            {repo: "failed" for repo in selection},
            f"pen create failed: {(handle.stderr or handle.stdout).strip()}",
        )

    pen_payload = handle.pen or {}
    pen_repos = {
        f"{repo.get('owner')}/{repo.get('name')}" for repo in pen_payload.get("repos", [])
    }
    if pen_repos != set(selection):
        return _result(
            plan,
            "blocked",
            version,
            {repo: "blocked" for repo in selection},
            f"pen {plan.pen_name!r} repos {sorted(pen_repos)} do not match "
            f"proposal selection {sorted(selection)}",
        )

    # --- created -> executed: preflight (stale/dirty block BEFORE run) ---
    preflight = nave_adapter.pen_status(runner, plan.pen_name)
    if preflight.get("adapter_state") == "error":
        return _result(
            plan,
            "failed",
            version,
            {repo: "failed" for repo in selection},
            f"pen status failed: {preflight.get('error')}",
        )
    preflight_by_repo = {
        f"{r.get('owner')}/{r.get('repo')}": r for r in preflight.get("repos", [])
    }
    reasons: list[str] = []
    for repo in selection:
        state = preflight_by_repo.get(repo)
        if state is None:
            reasons.append(f"{repo}: missing from pen status")
        elif state.get("working_tree") != "clean":
            # Fail closed on partial/malformed status entries too: anything
            # other than an explicit "clean" blocks, not just "dirty".
            reasons.append(
                f"{repo}: working tree not clean before run "
                f"(working_tree={state.get('working_tree')!r})"
            )
        # Freshness must be explicitly "fresh" and divergence explicitly
        # "up-to-date"; any other value — including a missing field on a
        # partial status entry — is staleness, fail closed.
        elif state.get("freshness") != "fresh" or state.get("divergence") != "up-to-date":
            reasons.append(
                f"{repo}: stale pen (freshness={state.get('freshness')}, "
                f"divergence={state.get('divergence')})"
            )
    if reasons:
        # Fail closed: a stale or dirty repo blocks the *whole* run, never
        # just itself — nothing gets executed anywhere.
        return _result(
            plan,
            "blocked",
            version,
            {repo: "blocked" for repo in selection},
            "; ".join(reasons),
        )

    # --- created -> executed: expected-SHA guard (stale-base block) ------
    # See module docstring "expected-SHA guard" section: Nave exposes no
    # per-repo SHA on its own, so verification requires an injected reader.
    # Runs after the pen exists and preflight passed, strictly before exec.
    # Fail closed on coverage, not just mismatch: `execute` cannot assume the
    # Proposal came through build_proposal, so a selected repo missing from
    # expected_shas (or an entirely empty dict) blocks rather than skipping
    # the guard — an unguarded repo is exactly the stale-base mutation this
    # gate exists to prevent.
    expected_shas = proposal.expected_shas
    if selection:
        if read_repo_head is None:
            return _result(
                plan,
                "blocked",
                version,
                {repo: "blocked" for repo in selection},
                "no read_repo_head callable was provided to execute(); "
                "expected-SHA "
                "verification requires reading each repo's current HEAD, "
                "and Nave's pen show/status JSON exposes no per-repo SHA "
                "to compare against",
            )
        sha_outcomes: dict[str, str] = {}
        sha_reasons: list[str] = []
        for repo in selection:
            expected = expected_shas.get(repo)
            if expected is None:
                sha_outcomes[repo] = "blocked"
                sha_reasons.append(
                    f"{repo}: selected but has no expected_shas entry; "
                    "an unguarded repo cannot be mutated"
                )
                continue
            try:
                actual = read_repo_head(repo)
            except (FileNotFoundError, KeyError) as exc:
                sha_outcomes[repo] = "blocked"
                sha_reasons.append(f"{repo}: could not read current HEAD: {exc}")
                continue
            if actual.strip().lower() != expected.strip().lower():
                sha_outcomes[repo] = "blocked"
                sha_reasons.append(
                    f"{repo}: expected SHA {expected!r} but current HEAD is {actual!r}"
                )
            else:
                sha_outcomes[repo] = "ok"
        if sha_reasons:
            return _result(
                plan,
                "blocked",
                version,
                sha_outcomes,
                "; ".join(sha_reasons),
            )

    # --- executed -----------------------------------------------------------
    argv = resolve_argv(entry)
    exec_result = nave_adapter.pen_exec(
        runner,
        plan.pen_name,
        list(argv),
        only=None,
        commit=False,
        push_changes=False,
        message=None,
    )
    if exec_result.get("adapter_state") == "error":
        # See module NEEDS_CONTEXT note: no per-repo attribution is
        # possible, so the whole run fails and every repo is "failed".
        return _result(
            plan,
            "failed",
            version,
            {repo: "failed" for repo in selection},
            f"pen exec failed: {(exec_result.get('stderr') or '').strip() or 'nonzero exit'}",
        )

    # --- validated -----------------------------------------------------------
    validation_failure = _validate(
        entry.validation,
        read_repo_file,
        read_repo_changed_paths,
        proposal.bound_paths,
        selection,
    )
    if validation_failure is not None:
        repo_outcomes, reason, state = validation_failure
        return _result(plan, state, version, repo_outcomes, reason)

    # --- proposed: terminal success, propose-only, never pushed -------------
    return _result(
        plan,
        "proposed",
        version,
        {repo: "ok" for repo in selection},
        None,
    )
