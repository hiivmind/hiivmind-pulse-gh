#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Re-derivation provider registry (F11 Task 2, plan-review F1).

Re-derivation must invoke the REAL, source-specific proposal builders — a
generic function cannot reproduce plan-sync (F8), generated-artifact (F7),
or marketplace-sync (F9) decisions. This module collects FRESH
source-of-truth evidence for one binding via typed provider input
contexts, then hands it to the real builder
(`plan_sync.build_apply_plans`, `generator_dispatch.dispatch`,
`marketplace_sync.build_marketplace_proposal`) with
`mutation_policy="allow-listed"` so the re-derived `Proposal` carries the
mandatory `bound_paths` allow-listed apply requires
(`mutation_plan.build_proposal`).

Re-derivation always reads FRESH SOURCE STATE — never a pen, never
`read_repo_head` alone: each source's `collect_inputs` branch fetches its
own snapshot straight from git/GitHub through the injected `IoSeams`,
mirroring the seam-injection style already used across this codebase
(`plan_sync_snapshot.collect`'s `runner`/`gh_api`, `generated_artifacts
.collect`'s `runner`, `marketplace_sync_run.fetch_remote_evidence`'s
`runner`) rather than a pen-backed reader.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from lib.pulse.scripts import (
    generated_artifacts,
    generator_dispatch,
    marketplace_sync,
    marketplace_sync_run,
    mutation_plan,
    plan_sync,
    plan_sync_snapshot,
)

SOURCE_KINDS = ("plan-sync", "generated-artifact", "marketplace-sync")


class RederiveError(ValueError):
    """Raised when a source's fresh evidence cannot produce a proposal."""


@dataclass(frozen=True)
class IoSeams:
    """Injected I/O collaborators `collect_inputs` uses to gather fresh
    source-of-truth evidence. Each `collect_inputs` branch reads only the
    fields its source needs; the rest may be left at their default.

    - `runner`: shaped like `plan_sync_snapshot.Runner` /
      `generated_artifacts.Runner` / `marketplace_sync_run.Runner` —
      `(argv: list[str], cwd: str | Path | None) -> CompletedProcess-like`.
      Used by all three sources (git fetch/rev-parse for plan-sync and
      generated-artifact, `gh` CLI calls for marketplace-sync).
    - `gh_api`: shaped like `plan_sync_snapshot.GhApi` —
      `(endpoint: str) -> Any` (parsed JSON). Used only by plan-sync, for
      the bound GitHub issue's fresh state.
    - `workdir`: optional local-checkout hint threaded straight through to
      `plan_sync_snapshot.collect`/`generated_artifacts.collect`.
    - `generators`: pre-loaded `{generator_id: Generator}` registry (not
      I/O — a config artifact loaded once by the caller, exactly like
      `generated_artifact_run.load_generators`). Used only by
      generated-artifact to resolve the binding's `generator` id.
    - `registry`: the loaded `TransformationRegistry`, threaded into every
      source's real builder so `allow_scheduled`/gating checks fire.
    """

    runner: Callable[..., Any] | None = None
    gh_api: Callable[[str], Any] | None = None
    workdir: str | Path | None = None
    generators: Mapping[str, generator_dispatch.Generator] | None = None
    registry: mutation_plan.TransformationRegistry | None = None


@dataclass(frozen=True)
class PlanSyncProviderInputs:
    """Fresh plan-sync evidence: `binding` is the PARSED binding built by
    `plan_sync_snapshot.collect` from the pushed document (never the stale
    caller-supplied `binding_ref`)."""

    binding: Mapping[str, Any]
    document_snapshot: plan_sync_snapshot.DocumentSnapshot
    github_snapshot: Mapping[str, Any] | None
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None


@dataclass(frozen=True)
class GeneratedProviderInputs:
    """Fresh generated-artifact evidence: `snapshot` is the nested
    `{source: {branch: {head, trees, blobs}}}` shape
    `generated_artifacts.collect`/`generator_dispatch.dispatch` share."""

    generator: generator_dispatch.Generator
    binding: Mapping[str, Any]
    snapshot: dict[str, Any]
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None


@dataclass(frozen=True)
class MarketplaceProviderInputs:
    """Fresh marketplace-sync evidence: `drift` is the pure decision from
    `marketplace_sync.compare` against a freshly fetched release list and
    marketplace document; `head_sha` is the marketplace repo's current
    HEAD."""

    binding: Mapping[str, Any]
    drift: marketplace_sync.MarketplaceDrift
    head_sha: str | None
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None


ProviderInputs = PlanSyncProviderInputs | GeneratedProviderInputs | MarketplaceProviderInputs


@dataclass(frozen=True)
class RederivedProposal:
    """The output of one re-derivation: a real, source-specific `Proposal`
    plus enough context to authorize and (for plan-sync) finalize it.

    `binding_id` is carried here because `Proposal` itself has no binding
    field. `finalizer_record` is only populated for `plan-sync` (the F8
    finalize step needs it); the other two sources leave it `None`.
    """

    binding_id: str
    proposal: mutation_plan.Proposal
    source_kind: str
    finalizer_record: dict[str, Any] | None


def collect_inputs(
    source_kind: str,
    binding_ref: Mapping[str, Any],
    recorded_summary: Mapping[str, Any],
    *,
    io_seams: IoSeams,
) -> ProviderInputs:
    """Gather FRESH source-of-truth evidence for one binding, no pen.

    `recorded_summary` is the previously recorded proposal's summary
    (`binding_id`, `transformation`, `proposal_id`, `actor`) — the same
    shape `authorize` later re-validates against. Before doing any I/O,
    this fails closed when `binding_ref`'s id disagrees with
    `recorded_summary["binding_id"]`: collecting evidence for the wrong
    binding would waste a network round trip on a re-derivation that can
    never authorize. `recorded_summary["actor"]` supplies the actor block
    every provider-input context carries.
    """
    if source_kind not in SOURCE_KINDS:
        raise RederiveError(f"apply_rederive: unknown source_kind: {source_kind!r}")

    binding_id = binding_ref.get("id")
    recorded_binding_id = recorded_summary.get("binding_id")
    if recorded_binding_id is not None and binding_id != recorded_binding_id:
        raise RederiveError(
            "apply_rederive: binding_ref id "
            f"{binding_id!r} does not match recorded_summary binding_id "
            f"{recorded_binding_id!r}"
        )
    actor = recorded_summary.get("actor")
    if actor is None:
        raise RederiveError("apply_rederive: recorded_summary.actor is required")

    if source_kind == "plan-sync":
        return _collect_plan_sync(binding_ref, actor, io_seams)
    if source_kind == "generated-artifact":
        return _collect_generated(binding_ref, actor, io_seams)
    return _collect_marketplace(binding_ref, actor, io_seams)


def _collect_plan_sync(
    binding_ref: Mapping[str, Any],
    actor: Mapping[str, Any] | mutation_plan.Actor,
    io_seams: IoSeams,
) -> PlanSyncProviderInputs:
    if io_seams.runner is None:
        raise RederiveError("apply_rederive: plan-sync requires io_seams.runner")
    snap = plan_sync_snapshot.collect(
        [dict(binding_ref)],
        workdir=io_seams.workdir,
        runner=io_seams.runner,
        gh_api=io_seams.gh_api,
    )
    if not snap.documents:
        raise RederiveError(
            "apply_rederive: plan-sync collected no document for binding "
            f"{binding_ref.get('id')!r}"
        )
    document_snapshot = snap.documents[0]
    return PlanSyncProviderInputs(
        binding=document_snapshot.binding,
        document_snapshot=document_snapshot,
        github_snapshot=document_snapshot.github,
        actor=actor,
        registry=io_seams.registry,
    )


def _collect_generated(
    binding_ref: Mapping[str, Any],
    actor: Mapping[str, Any] | mutation_plan.Actor,
    io_seams: IoSeams,
) -> GeneratedProviderInputs:
    if io_seams.generators is None:
        raise RederiveError(
            "apply_rederive: generated-artifact requires io_seams.generators"
        )
    generator_id = binding_ref.get("generator")
    generator = (
        io_seams.generators.get(generator_id) if isinstance(generator_id, str) else None
    )
    if generator is None:
        raise RederiveError(
            f"apply_rederive: generator {generator_id!r} not found for binding "
            f"{binding_ref.get('id')!r}"
        )
    manifest = {"bindings": [dict(binding_ref)]}
    snapshot = generated_artifacts.collect(
        manifest, workdir=io_seams.workdir, runner=io_seams.runner
    )
    return GeneratedProviderInputs(
        generator=generator,
        binding=binding_ref,
        snapshot=snapshot,
        actor=actor,
        registry=io_seams.registry,
    )


def _collect_marketplace(
    binding_ref: Mapping[str, Any],
    actor: Mapping[str, Any] | mutation_plan.Actor,
    io_seams: IoSeams,
) -> MarketplaceProviderInputs:
    if io_seams.runner is None:
        raise RederiveError("apply_rederive: marketplace-sync requires io_seams.runner")
    releases_by_repo, docs_by_repo, head_shas = marketplace_sync_run.fetch_remote_evidence(
        [dict(binding_ref)], io_seams.runner
    )
    plugin_repo = binding_ref.get("repo")
    marketplace_repo = binding_ref.get("marketplace_repo")
    marketplace_file = binding_ref.get("marketplace_file")
    releases = releases_by_repo.get(plugin_repo)
    doc = docs_by_repo.get(f"{marketplace_repo}/{marketplace_file}")
    drift = marketplace_sync.compare(dict(binding_ref), releases, doc)
    head_sha = head_shas.get(marketplace_repo)
    return MarketplaceProviderInputs(
        binding=binding_ref,
        drift=drift,
        head_sha=head_sha,
        actor=actor,
        registry=io_seams.registry,
    )


def rederive(inputs: ProviderInputs) -> RederivedProposal:
    """Call the REAL source-specific proposal builder, allow-listed.

    Never reconstructs a proposal from `recorded_summary` or from stale
    values — everything here comes from `inputs`, which `collect_inputs`
    built from fresh evidence. Raises `RederiveError` when the fresh
    evidence cannot produce a proposal (e.g. an in-sync plan-sync
    document, or a `mutation_plan.MutationPlanError` from the real
    builder — bound_paths coverage, out-of-allowlist output path, or
    unknown/gated transformation).
    """
    if isinstance(inputs, PlanSyncProviderInputs):
        return _rederive_plan_sync(inputs)
    if isinstance(inputs, GeneratedProviderInputs):
        return _rederive_generated(inputs)
    if isinstance(inputs, MarketplaceProviderInputs):
        return _rederive_marketplace(inputs)
    raise RederiveError(f"apply_rederive: unsupported provider inputs: {type(inputs)!r}")


def _rederive_plan_sync(inputs: PlanSyncProviderInputs) -> RederivedProposal:
    snapshot = inputs.document_snapshot
    document = snapshot.document
    if document is None:
        raise RederiveError(
            "apply_rederive: plan-sync snapshot has no parsed document "
            f"(state={snapshot.state!r})"
        )
    sync_binding = document.binding
    if not isinstance(sync_binding, Mapping):
        raise RederiveError(
            "apply_rederive: plan-sync snapshot document has no sync binding"
        )

    reconciliation = plan_sync.compute(
        document,
        inputs.github_snapshot or {},
        sync_binding,
        snapshot.base_body,
        document_blob=snapshot.blob,
    )
    try:
        apply_plans = plan_sync.build_apply_plans(
            reconciliation,
            inputs.binding,
            snapshot,
            inputs.actor,
            inputs.registry,
            mutation_policy="allow-listed",
            bound_paths={snapshot.repo: [snapshot.path]},
        )
    except mutation_plan.MutationPlanError as exc:
        raise RederiveError(f"apply_rederive: plan-sync build failed: {exc}") from exc
    if apply_plans.repo_mutation is None:
        reason = apply_plans.gated_transformation or "no repository mutation proposal was produced"
        raise RederiveError(f"apply_rederive: plan-sync produced no repo proposal: {reason}")

    proposal = apply_plans.repo_mutation
    base = sync_binding.get("base")
    expected_prior_blob = base.get("blob") if isinstance(base, Mapping) else None
    binding_id = inputs.binding.get("id") if isinstance(inputs.binding, Mapping) else None
    finalizer_record = {
        "repo": snapshot.repo,
        "base_ref": snapshot.branch,
        "doc_path": snapshot.path,
        "expected_prior_blob": expected_prior_blob,
        "proposal_id": proposal.id,
        "binding_id": binding_id,
    }
    return RederivedProposal(
        binding_id=str(binding_id),
        proposal=proposal,
        source_kind="plan-sync",
        finalizer_record=finalizer_record,
    )


def _rederive_generated(inputs: GeneratedProviderInputs) -> RederivedProposal:
    binding = inputs.binding
    source = binding.get("source") if isinstance(binding, Mapping) else None
    files = binding.get("files") if isinstance(binding, Mapping) else None
    bound = tuple(
        f.get("path")
        for f in (files or [])
        if isinstance(f, Mapping) and isinstance(f.get("path"), str)
    )
    bound_paths = {source: list(bound)} if isinstance(source, str) else None
    try:
        proposal = generator_dispatch.dispatch(
            inputs.generator,
            dict(binding),
            inputs.snapshot,
            inputs.actor,
            mutation_policy="allow-listed",
            bound_paths=bound_paths,
            registry=inputs.registry,
        )
    except mutation_plan.MutationPlanError as exc:
        raise RederiveError(f"apply_rederive: generated-artifact dispatch failed: {exc}") from exc
    binding_id = binding.get("id") if isinstance(binding, Mapping) else None
    return RederivedProposal(
        binding_id=str(binding_id),
        proposal=proposal,
        source_kind="generated-artifact",
        finalizer_record=None,
    )


def _rederive_marketplace(inputs: MarketplaceProviderInputs) -> RederivedProposal:
    proposable = (marketplace_sync.OUTCOME_DRIFT, marketplace_sync.OUTCOME_MISSING_ENTRY)
    if inputs.drift.outcome not in proposable:
        raise RederiveError(
            "apply_rederive: marketplace-sync drift is not proposable: "
            f"outcome={inputs.drift.outcome!r}"
        )
    if not isinstance(inputs.head_sha, str) or not inputs.head_sha:
        raise RederiveError("apply_rederive: marketplace-sync requires a resolved head_sha")
    try:
        proposal = marketplace_sync.build_marketplace_proposal(
            inputs.drift,
            inputs.head_sha,
            inputs.actor,
            registry=inputs.registry,
            mutation_policy="allow-listed",
            bound_paths={inputs.drift.marketplace_repo: [inputs.drift.marketplace_file]},
        )
    except mutation_plan.MutationPlanError as exc:
        raise RederiveError(f"apply_rederive: marketplace-sync build failed: {exc}") from exc
    binding = inputs.binding if isinstance(inputs.binding, Mapping) else {}
    binding_id = binding.get("id") or inputs.drift.plugin_id
    return RederivedProposal(
        binding_id=str(binding_id),
        proposal=proposal,
        source_kind="marketplace-sync",
        finalizer_record=None,
    )
