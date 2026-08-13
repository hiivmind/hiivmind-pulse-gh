#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ruamel.yaml>=0.18.0"]
# ///
"""Lossless parsing and patching for GitHub-bound Markdown plans."""
from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
import json
import re
from typing import Any, Mapping

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from lib.pulse.scripts import mutation_plan
from lib.pulse.scripts.mutation_plan import Proposal, build_proposal


_YAML = YAML(typ="rt")
_YAML.preserve_quotes = True
_FRONTMATTER = re.compile(
    r"\A(?P<opening>---(?P<line_ending>\r?\n))"
    r"(?P<content>.*?)"
    r"(?P<closing>^---(?:\r?\n|\Z))",
    re.DOTALL | re.MULTILINE,
)
_H1 = re.compile(r"^# (?P<title>[^\r\n]*)(?=\r?$)", re.MULTILINE)


@dataclass(frozen=True)
class BoundDocument:
    """A Markdown document and its optional ``sync:`` frontmatter block."""

    frontmatter: Any | None
    body: str
    title: str | None
    binding: Any | None


@dataclass(frozen=True)
class FieldDecision:
    """The selected outcome for reconciling one synchronized field."""

    decision: str
    value: Any | None


@dataclass(frozen=True)
class ReconciliationPlan:
    """Pure patches and conflicts resulting from a three-way reconciliation."""

    doc_patch: dict[str, Any]
    github_patch: dict[str, Any]
    base_patch: dict[str, Any]
    conflicts: tuple[str, ...]
    doc_base_patch: dict[str, Any] = field(default_factory=dict)
    requires_final_blob: bool = False

    @property
    def conflicted(self) -> bool:
        """Whether any field requires manual reconciliation."""
        return bool(self.conflicts)


@dataclass(frozen=True)
class ApplyPlans:
    """Independent, propose-only plans for one reconciliation.

    ``repo_mutation`` is an F6 proposal for the document checkout.  Its
    companion ``doc_patch`` is the caller-owned content for the well-known
    pen-checkout patch file; it is deliberately data, never command argv.
    ``github_mutation`` is a Pulse proposed action, not an API invocation.

    When the document-side transformation is gated (e.g. ``allow_scheduled:
    false`` in scheduled mode), ``repo_mutation`` and ``doc_patch`` are
    suppressed and ``gated_transformation`` carries the gate detail while
    ``github_mutation`` is still built through the normal validated path.
    """

    repo_mutation: Proposal | None
    github_mutation: dict[str, Any] | None
    doc_patch: dict[str, Any] | None
    gated_transformation: str | None = None


@dataclass(frozen=True)
class FinalizeFinding:
    """A typed finalization finding suitable for a plan-sync result."""

    kind: str
    severity: str
    detail: str


@dataclass(frozen=True)
class FinalizeDecision:
    """The bases safe to persist after the two independent apply paths."""

    base_patch: dict[str, Any]
    findings: tuple[FinalizeFinding, ...]


_SYNC_FIELDS = ("title", "state", "assignees", "milestone", "body")
_GITHUB_ONLY_FIELDS = {"state", "assignees", "milestone"}


def _normalise(field: str, value: Any) -> Any:
    if field == "assignees":
        return sorted(set(value or ()))
    return value


def merge_field(
    field: str,
    base: Any,
    doc: Any,
    github: Any,
    policy: str | None = None,
) -> FieldDecision:
    """Determine a pure three-way merge outcome for a single plan field."""
    base_value = _normalise(field, base)
    doc_value = _normalise(field, doc)
    github_value = _normalise(field, github)
    doc_changed = doc_value != base_value
    github_changed = github_value != base_value

    if not doc_changed and not github_changed:
        return FieldDecision("noop", None)
    if doc_changed and not github_changed:
        return FieldDecision("apply_to_github", doc_value)
    if github_changed and not doc_changed:
        return FieldDecision("apply_to_doc", github_value)
    if doc_value == github_value:
        return FieldDecision("agree", doc_value)
    if policy == "prefer-doc":
        return FieldDecision("apply_to_github", doc_value)
    if policy == "prefer-github":
        return FieldDecision("apply_to_doc", github_value)
    return FieldDecision("conflict", None)


def _field_value(source: Mapping[str, Any] | BoundDocument, field: str) -> Any:
    if isinstance(source, BoundDocument):
        if field == "title":
            return source.title
        if field == "body":
            return source.body
        if isinstance(source.frontmatter, Mapping):
            return source.frontmatter.get(field)
        return None
    return source.get(field)


def compute(
    doc: Mapping[str, Any] | BoundDocument,
    github: Mapping[str, Any],
    binding: Mapping[str, Any],
    base_body: Any,
    document_blob: str | None = None,
) -> ReconciliationPlan:
    """Reconcile V1 plan fields into independent document, GitHub, and base patches."""
    base = binding.get("base", {})
    policies = binding.get("policy", {})
    doc_patch: dict[str, Any] = {}
    github_patch: dict[str, Any] = {}
    base_patch: dict[str, Any] = {}
    doc_base_patch: dict[str, Any] = {}
    conflicts: list[str] = []
    requires_final_blob = False

    for field in _SYNC_FIELDS:
        base_value = base_body if field == "body" else base.get(field)
        policy = policies.get(field) if isinstance(policies, Mapping) else None
        # V1 has no document representation for these GitHub-only scalars.
        # Their document-side value is therefore the recorded base; a GitHub
        # delta advances sync.base rather than inventing a body/frontmatter key.
        doc_value = (
            base_value
            if isinstance(doc, BoundDocument) and field in _GITHUB_ONLY_FIELDS
            else _field_value(doc, field)
        )
        outcome = merge_field(
            field,
            base_value,
            doc_value,
            github.get(field),
            policy,
        )
        if outcome.decision == "conflict":
            conflicts.append(field)
        elif outcome.decision == "apply_to_doc":
            if field in _GITHUB_ONLY_FIELDS:
                base_patch[field] = outcome.value
                doc_base_patch[field] = outcome.value
            else:
                doc_patch[field] = outcome.value
                if field == "body":
                    requires_final_blob = True
                else:
                    base_patch[field] = outcome.value
                    doc_base_patch[field] = outcome.value
        elif outcome.decision == "apply_to_github":
            github_patch[field] = outcome.value
            if field == "body":
                if document_blob:
                    base_patch["blob"] = document_blob
            else:
                base_patch[field] = outcome.value
        elif outcome.decision == "agree":
            if field == "body":
                if document_blob:
                    base_patch["blob"] = document_blob
                    doc_base_patch["blob"] = document_blob
            else:
                base_patch[field] = outcome.value
                if isinstance(doc, BoundDocument):
                    doc_base_patch[field] = outcome.value

    return ReconciliationPlan(
        doc_patch,
        github_patch,
        base_patch,
        tuple(conflicts),
        doc_base_patch,
        requires_final_blob,
    )


def _snapshot_value(snapshot: Any, name: str) -> Any:
    if isinstance(snapshot, Mapping):
        return snapshot.get(name)
    return getattr(snapshot, name, None)


def _sync_binding(binding: Mapping[str, Any]) -> Mapping[str, Any]:
    sync = binding.get("sync")
    return sync if isinstance(sync, Mapping) else binding


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def build_apply_plans(
    reconciliation: ReconciliationPlan,
    binding: Mapping[str, Any],
    snapshot: Any,
    actor: Mapping[str, Any] | Any,
    registry: mutation_plan.TransformationRegistry | None = None,
    mutation_policy: str = "propose",
    bound_paths: dict[str, list[str]] | None = None,
) -> ApplyPlans:
    """Build separate propose-only document and GitHub patch proposals.

    This function has no side effects.  The caller writes ``doc_patch`` to
    ``.hiivmind/plan-sync-patch.yaml`` in the pen checkout only when it is
    ready to execute the already-proposed F6 document path.  GitHub receives
    a parallel proposed action and is never folded into that proposal.

    ``mutation_policy``/``bound_paths`` thread into the document-side
    `build_proposal` call; the GitHub-side proposal dict is unaffected
    (GitHub patches remain propose-only, applied separately). Defaults
    preserve existing callers byte-for-byte: `mutation_policy="propose"`
    and, when `bound_paths` is omitted, the existing `{repo: [path]}`.
    """
    repo = _required_string(binding.get("repo"), "binding.repo")
    path = _required_string(binding.get("path"), "binding.path")
    binding_id = _required_string(binding.get("id"), "binding.id")
    snapshot_repo = _snapshot_value(snapshot, "repo")
    if snapshot_repo is not None and snapshot_repo != repo:
        raise ValueError("snapshot.repo must match binding.repo")

    repo_mutation: Proposal | None = None
    doc_patch: dict[str, Any] | None = None
    gated_transformation: str | None = None
    if reconciliation.doc_patch or reconciliation.doc_base_patch:
        head = _required_string(_snapshot_value(snapshot, "head"), "snapshot.head")
        blob = _required_string(_snapshot_value(snapshot, "blob"), "snapshot.blob")
        try:
            repo_mutation = build_proposal(
                id=f"plan-sync-doc-{binding_id}",
                selection=[repo],
                transformation="plan-sync-doc-patch",
                expected_shas={repo: head},
                actor=actor,
                mutation_policy=mutation_policy,
                bound_paths=bound_paths if bound_paths is not None else {repo: [path]},
                registry=registry,
            )
            doc_patch = {
                "path": path,
                "base_blob": blob,
                "doc_patch": dict(reconciliation.doc_patch),
                "sync_patch": (
                    {"base": dict(reconciliation.doc_base_patch)}
                    if reconciliation.doc_base_patch
                    else {}
                ),
                "output_paths": [path],
            }
        except mutation_plan.MutationPlanError as exc:
            # Gate only the document component; GitHub mutation still builds
            # through the validated path below.
            gated_transformation = str(exc)
            repo_mutation = None
            doc_patch = None

    github_mutation: dict[str, Any] | None = None
    if reconciliation.github_patch:
        issue = _sync_binding(binding).get("issue")
        if not isinstance(issue, Mapping):
            raise ValueError("binding.sync.issue must be a mapping")
        issue_repo = _required_string(issue.get("repo"), "binding.sync.issue.repo")
        issue_number = issue.get("number")
        if isinstance(issue_number, bool) or not isinstance(issue_number, int) or issue_number <= 0:
            raise ValueError("binding.sync.issue.number must be a positive integer")
        patch = dict(reconciliation.github_patch)
        github_mutation = {
            "repo": issue_repo,
            "number": issue_number,
            "patch": patch,
            "mutation_policy": "propose",
            "proposed_actions": [
                f"propose GitHub issue patch for {issue_repo}#{issue_number}: "
                f"{json.dumps(patch, sort_keys=True)}"
            ],
        }

    return ApplyPlans(repo_mutation, github_mutation, doc_patch, gated_transformation)


def finalize(
    reconciliation: ReconciliationPlan,
    doc_applied: bool,
    github_applied: bool,
    confirmed_document_blob: str | None = None,
) -> FinalizeDecision:
    """Advance bases only where the corresponding two-way value is confirmed."""
    base_patch: dict[str, Any] = {}
    for field, value in reconciliation.base_patch.items():
        if (
            field in reconciliation.doc_patch
            or field in reconciliation.doc_base_patch
        ) and not doc_applied:
            continue
        if field == "blob" and "body" in reconciliation.github_patch and not github_applied:
            continue
        if field in reconciliation.github_patch and not github_applied:
            continue
        base_patch[field] = value
    if reconciliation.requires_final_blob and doc_applied and confirmed_document_blob:
        base_patch["blob"] = confirmed_document_blob

    findings: tuple[FinalizeFinding, ...] = ()
    # Only a genuine partial application is notable: both sides had a patch to
    # apply and exactly one succeeded. A one-sided reconciliation (only the doc
    # or only GitHub changed) is a complete application, not a partial one.
    both_had_work = bool(
        reconciliation.doc_patch or reconciliation.doc_base_patch
    ) and bool(reconciliation.github_patch)
    if both_had_work and doc_applied != github_applied:
        findings = (
            FinalizeFinding(
                "partial_application",
                "medium",
                "document and GitHub proposals must be finalized independently",
            ),
        )
    return FinalizeDecision(base_patch, findings)


def _finding_dict(finding: Any, *, repo: str | None = None) -> dict[str, Any]:
    result = {
        "kind": getattr(finding, "kind"),
        "repo": getattr(finding, "repo", None) or repo or "",
        "severity": getattr(finding, "severity"),
    }
    for key in ("detail", "path", "new_path"):
        value = getattr(finding, key, None)
        if value is not None:
            result[key] = value
    result["inferred"] = False
    return result


def build_result(
    snapshot: Any,
    *,
    workspace: str,
    run_at: str,
    actor: Mapping[str, Any],
    registry: mutation_plan.TransformationRegistry | None = None,
    mode: str = "interactive",
) -> dict[str, Any]:
    """Build the production plan-sync result from collected evidence.

    The builder composes the public merge and proposal paths used by the
    headless workflow.  It is deliberately propose-only and performs no I/O.
    """
    actor_dict = dict(actor)
    actor_dict["mode"] = mode

    result: dict[str, Any] = {
        "contract_version": 1,
        "kind": "plan-sync",
        "workspace": workspace,
        "run_at": run_at,
        "actor": actor_dict,
        "docs_scanned": 0,
        "in_sync": 0,
        "doc_patches": 0,
        "github_patches": 0,
        "conflicts": 0,
        "excluded": 0,
        "findings": [_finding_dict(f) for f in getattr(snapshot, "findings", ())],
        "proposals": [],
        "proposed_actions": [],
        "errors": [],
    }

    for document in getattr(snapshot, "documents", ()):
        result["docs_scanned"] += 1
        if document.state in {"excluded", "error"}:
            result["excluded"] += 1
            continue
        if document.state == "in_sync":
            result["in_sync"] += 1
            continue
        if not document.document or not document.github or document.base_body is None:
            result["excluded"] += 1
            continue

        reconciliation = compute(
            document.document,
            document.github,
            document.document.binding,
            document.base_body,
            document_blob=document.blob,
        )
        if reconciliation.conflicted:
            result["conflicts"] += 1
            for conflict in reconciliation.conflicts:
                result["findings"].append({
                    "kind": "base_conflict",
                    "repo": document.repo,
                    "severity": "high",
                    "detail": f"{conflict} changed differently in the document and GitHub",
                    "inferred": False,
                })
            continue

        plans = build_apply_plans(
            reconciliation, document.binding, document, actor_dict, registry=registry
        )
        # Per-document gate signal from build_apply_plans — never query the
        # cumulative result["findings"] list (that leaks across documents).
        document_gated = plans.gated_transformation is not None
        if document_gated:
            result["findings"].append({
                "kind": "gated_transformation",
                "repo": document.repo,
                "severity": "medium",
                "detail": plans.gated_transformation,
                "inferred": False,
            })
            # Emit a proposed_actions line for the withheld doc patch so the
            # scheduler PR-body projection surfaces it — parity with the gated
            # paths in marketplace_sync.build_result / generated_artifacts (a
            # gated transformation records the intended action without a
            # proposal id, since build_apply_plans withheld the proposal).
            result["proposed_actions"].append(
                f"propose document patch for {document.path} at {document.head}"
            )

        if plans.repo_mutation is not None:
            result["doc_patches"] += 1
            result["proposals"].append({
                "binding": document.binding["id"],
                "transformation": plans.repo_mutation.transformation,
                "proposal_id": plans.repo_mutation.id,
            })
            result["proposed_actions"].append(
                f"propose document patch {plans.repo_mutation.id} for "
                f"{document.path} at {document.head}"
            )
        if plans.github_mutation is not None:
            result["github_patches"] += 1
            result["proposed_actions"].extend(
                plans.github_mutation.get("proposed_actions", [])
            )
        if plans.repo_mutation is None and plans.github_mutation is None:
            # Gated docs are not in-sync; the flag is per-document only.
            if not document_gated:
                result["in_sync"] += 1

        # Propose-only: neither path is confirmed, so no base is persisted.
        final = finalize(reconciliation, doc_applied=False, github_applied=False)
        result["findings"].extend(
            _finding_dict(finding, repo=document.repo) for finding in final.findings
        )

    return result


def _split_frontmatter(text: str) -> tuple[re.Match[str] | None, str]:
    match = _FRONTMATTER.match(text)
    return match, text[match.end():] if match else text


def _title_from(body: str) -> str | None:
    match = _H1.search(body)
    return match.group("title") if match else None


def parse_document(text: str) -> BoundDocument:
    """Parse frontmatter without normalizing the Markdown body."""
    match, body = _split_frontmatter(text)
    if match is None:
        return BoundDocument(None, body, _title_from(body), None)

    frontmatter = _YAML.load(match.group("content"))
    binding = frontmatter.get("sync") if isinstance(frontmatter, dict) else None
    return BoundDocument(frontmatter, body, _title_from(body), binding)


def _replace_title(body: str, title: str) -> str:
    match = _H1.search(body)
    if match is None:
        raise ValueError("document has no H1 title to patch")
    start, end = match.span("title")
    return body[:start] + title + body[end:]


def _dump_frontmatter(frontmatter: Any, line_ending: str) -> str:
    output = StringIO()
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.line_break = line_ending
    yaml.dump(frontmatter, output)
    # ruamel's comment attachment can otherwise yield ``\r\r\n`` for an
    # inline-commented mapping when serializing a CRLF source document.
    return output.getvalue().replace("\r\r\n", "\r\n")


def _apply_base_patch(binding: Any, sync_patch: dict) -> None:
    if not isinstance(binding, dict):
        raise ValueError("document has no sync binding to patch")

    base_patch = sync_patch.get("base", sync_patch)
    if not isinstance(base_patch, dict):
        raise TypeError("sync patch must be a mapping of base fields")

    base = binding.get("base")
    if base is None:
        base = CommentedMap()
        binding["base"] = base
    if not isinstance(base, dict):
        raise TypeError("sync.base must be a mapping")
    base.update(base_patch)


def patch_document(text: str, doc_patch: dict, sync_patch: dict) -> str:
    """Apply document and ``sync.base`` updates while preserving untouched text."""
    if not doc_patch and not sync_patch:
        return text

    match, original_body = _split_frontmatter(text)
    document = parse_document(text)
    body = doc_patch.get("body", original_body)
    if "title" in doc_patch:
        body = _replace_title(body, doc_patch["title"])

    if not sync_patch:
        return text[:match.end()] + body if match else body

    if match is None:
        raise ValueError("document has no frontmatter to patch")
    _apply_base_patch(document.binding, sync_patch)
    frontmatter = _dump_frontmatter(document.frontmatter, match.group("line_ending"))
    return match.group("opening") + frontmatter + match.group("closing") + body
