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

## NEEDS_CONTEXT: `validation.kind == "json_schema"` cannot be checked

`mutation_plan.ValidationSpec` declares a `json_schema` kind that is
supposed to validate a repo-relative output file's parsed content against
an inline JSON Schema. No Nave CLI surface exposes that content:
`pen show`/`pen status` (`nave_pen::storage::Pen` / `state::RepoState`)
carry no local clone path, and `pen exec`'s stdout/stderr are opaque by
contract (Task 1: "never parsed as data"). `nave materialize` fetches
committed content from the GitHub API, not a pen's local uncommitted
working tree, so it cannot stand in either. Every transformation entry
whose `validation.kind == "json_schema"` therefore fails closed today —
see `_validate` below — until a future Nave/adapter capability exposes
pen repo file content (e.g. a `pen cat`/`--json` command). This is a real
capability gap, not a design choice this module can route around.

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

from dataclasses import dataclass

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


# Any divergence other than "up-to-date" means the pen's local branch has
# moved relative to its remote counterpart in some way the orchestrator
# did not itself cause yet (it hasn't run anything at this point) — treat
# all of them as staleness pre-flight, fail closed.
_STALE_DIVERGENCE = {"ahead", "behind", "diverged", "unknown"}


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


def _is_stale(state: dict) -> bool:
    return state.get("freshness") == "stale" or state.get("divergence") in _STALE_DIVERGENCE


def _validate(spec: ValidationSpec) -> str | None:
    """Run the post-exec check `spec` declares; return an error string or
    `None` on success. See the module-level NEEDS_CONTEXT note: `none` is
    the only kind currently checkable — `json_schema` fails closed."""
    if spec.kind == "none":
        return None
    return (
        f"validation kind 'json_schema' (path={spec.path!r}) cannot be "
        "checked: no Nave adapter capability exposes a pen repo's local "
        "file content (pen show/status carry no clone path, pen exec "
        "stdout/stderr are opaque by contract, and `materialize` fetches "
        "committed GitHub content, not a pen's local working tree) — see "
        "the NEEDS_CONTEXT note in pen_orchestrator.py / task-3-report.md"
    )


def execute(plan: PenPlan, nave_adapter_runner) -> PenRunResult:
    """Drive `plan` through the pen state machine using `nave_adapter_runner`.

    `nave_adapter_runner` is the injectable runner (`NaveRunner` /
    `RecordingRunner` / `QueuedRunner` / `NaveRunner(fixtures=...)`) passed
    to the statically-imported `nave_adapter` module's functions — this
    function never imports or calls `subprocess` itself.
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
    if pen_payload.get("adapter_state") == "error":
        return _result(
            plan,
            "failed",
            version,
            {repo: "failed" for repo in selection},
            f"pen show after create failed: {pen_payload.get('error')}",
        )
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
        elif state.get("working_tree") == "dirty":
            reasons.append(f"{repo}: dirty working tree before run")
        elif _is_stale(state):
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
    validation_error = _validate(entry.validation)
    if validation_error is not None:
        return _result(
            plan,
            "failed",
            version,
            {repo: "failed" for repo in selection},
            validation_error,
        )

    # --- proposed: terminal success, propose-only, never pushed -------------
    return _result(
        plan,
        "proposed",
        version,
        {repo: "ok" for repo in selection},
        None,
    )
