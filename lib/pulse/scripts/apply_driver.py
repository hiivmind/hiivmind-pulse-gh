"""Journaled, fenced sequencer for one allow-listed repository apply."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from lib.pulse.scripts import (
    apply_authorization,
    apply_ops,
    apply_phases,
    apply_reconcile,
    apply_rederive,
    mutation_plan,
    nave_adapter,
    pen_clone_reader,
    resolve_run,
    validate_result,
)
from lib.pulse.scripts.apply_journal import Journal, RESET_AND_REEXEC_TRANSFORM
from lib.pulse.scripts.apply_lock import ApplyLock, ApplyLockError


def _actor(actor_id: str) -> mutation_plan.Actor:
    login, separator, machine = actor_id.partition("@")
    if not separator or not login or not machine:
        raise ValueError("actor_id must be login@machine")
    return mutation_plan.Actor(login, machine, "interactive")


def _default_gh_api(path: str):
    """Production `gh api` seam — parsed JSON, or None on any failure."""
    import json
    import subprocess

    res = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except ValueError:
        return None


def _expand_bound_globs(clone_dir: str, patterns: tuple[str, ...]) -> tuple[str, ...]:
    """Expand glob `bound_paths` to the concrete repo-relative paths they cover.

    Nave's commit gate is exact-path: a dirty path must literally appear in the
    request's `paths`. The proposal carries glob patterns (`src/**`); expanding
    them here (with the same fnmatch semantics as the paths_changed validator)
    yields the concrete allow-list the commit request needs. Tracked + untracked
    non-ignored files only — the same surface `git status --porcelain` reports
    dirty, so anything Nave can flag is either covered by a pattern or fails
    closed.
    """
    from fnmatch import fnmatchcase
    import subprocess

    root = Path(clone_dir)
    listed: set[str] = set()
    for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
        res = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True
        )
        if res.returncode == 0:
            listed.update(res.stdout.splitlines())
    matched = []
    for path in sorted(listed):
        if any(
            fnmatchcase(path, pattern) if "*" in pattern else path == pattern
            for pattern in patterns
        ):
            matched.append(path)
    return tuple(matched)


def _entry(inputs: apply_rederive.ProviderInputs, workspace: str, transformation: str):
    """Use the provider's registry, then the same workspace/template fallback as run callers."""
    registry = getattr(inputs, "registry", None)
    if registry is None:
        configured = Path(workspace) / ".hiivmind" / "github" / "transformations.yaml"
        template = Path(__file__).resolve().parents[3] / "templates" / "transformations.yaml.template"
        registry = mutation_plan.load_registry(configured if configured.exists() else template)
    entry = registry.get(transformation)
    if entry.id != transformation:
        raise ValueError("resolved transformation entry identity mismatch")
    return entry


def _write_failure(path, *, state, reason, actor, workspace, proposal=None,
                   recorded_summary=None, proposal_digest=None, authorization_digest=None,
                   nave_version=None, repo_outcomes=None):
    recorded_summary = recorded_summary or {}
    selection = list(proposal.selection) if proposal is not None else []
    proposal_id = proposal.id if proposal is not None else str(recorded_summary.get("proposal_id") or "unknown")
    transformation = proposal.transformation if proposal is not None else str(recorded_summary.get("transformation") or "unknown")
    pen_name = f"pulse-apply-{proposal_id}"
    doc = {
        "contract_version": 1,
        "kind": "repo-mutation",
        "workspace": workspace,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": {"gh_login": actor.gh_login, "machine": actor.machine, "mode": actor.mode},
        "state": state,
        "proposal_id": proposal_id,
        "recorded_proposal_id": recorded_summary.get("proposal_id"),
        "proposal_digest": proposal_digest,
        "authorization_digest": authorization_digest,
        "transformation": transformation,
        "pen_name": pen_name,
        "selection": selection,
        "nave_version": nave_version,
        "repo_outcomes": repo_outcomes or {repo: state for repo in selection},
        "reason": str(reason),
        "errors": [],
    }
    errors = validate_result.validate(doc, "repo-mutation")
    if errors:
        raise ValueError(f"invalid repo-mutation result: {'; '.join(errors)}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(doc, sort_keys=False))
    return doc


def _failed_outcomes(outcomes, fallback):
    return {
        repo: (item.get("state", fallback) if isinstance(item, dict) else fallback)
        for repo, item in outcomes.items()
    }


def _phase_reason(name, outcomes):
    details = [f"{repo}: {item.get('reason')}" for repo, item in outcomes.items()
               if isinstance(item, dict) and item.get("state") != "ok"]
    return f"{name} failed" + (f": {'; '.join(details)}" if details else "")


def _persist_finalizer(result_path, finalizer_record) -> None:
    """Durably write the F8 finalizer record beside the result file, so the
    reconcile step (a separate invocation) can load it via --finalizer-record."""
    path = Path(f"{result_path}.finalizer.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(finalizer_record, sort_keys=False))


def run_apply(*, source_kind, binding_ref, recorded_summary=None, authorization_path, ledger_path,
              step_id, actor_id, runner, gh_api=None, gh_ops, result_path, workspace) -> dict:
    """Run one single-repository apply; return apply-status or repo-mutation."""
    proposal = None
    proposal_digest = None
    authorization_digest = None
    actor = _actor(actor_id)

    try:
        if source_kind == "neutral":
            recorded_summary = apply_rederive.neutral_summary(binding_ref)
        elif not recorded_summary:
            raise apply_rederive.RederiveError(
                f"recorded_summary is required for source_kind={source_kind!r}"
            )
        inputs = apply_rederive.collect_inputs(
            source_kind, binding_ref, recorded_summary, actor=actor,
            io_seams=apply_rederive.IoSeams(runner=runner, gh_api=gh_api, registry=None),
        )
        rederived = apply_rederive.rederive(inputs)
        proposal = rederived.proposal
        proposal_digest = mutation_plan.proposal_digest(proposal)
        auth = apply_authorization.load_authorization(authorization_path, proposal.transformation)
        authorization_digest = apply_authorization.authorization_digest(auth)
        apply_authorization.authorize(rederived, auth, recorded_summary)
        if not proposal.selection:
            raise apply_rederive.RederiveError("apply proposal selection is empty")
        selection = proposal.selection
        entry = _entry(inputs, workspace, proposal.transformation)
        resolved_base = apply_reconcile.resolve_intended_base(
            rederived.source_kind, binding_ref, rederived.finalizer_record
        )
        if isinstance(resolved_base, str):
            base_refs = {repo: resolved_base for repo in selection}
        else:
            base_refs = resolved_base
        if rederived.finalizer_record:
            _persist_finalizer(result_path, rederived.finalizer_record)
    except (apply_rederive.RederiveError, apply_authorization.AuthorizationError,
            mutation_plan.MutationPlanError, ValueError) as exc:
        return _write_failure(
            result_path, state="blocked", reason=exc, actor=actor, workspace=workspace,
            proposal=proposal, recorded_summary=recorded_summary,
            proposal_digest=proposal_digest, authorization_digest=authorization_digest,
        )

    resolve_run.snapshot_audit(
        ledger_path, step_id, recorded_proposal_id=recorded_summary["proposal_id"],
        proposal_digest=proposal_digest, authorization_digest=authorization_digest,
        policy_version="v1",
    )
    capabilities = nave_adapter.pen_capabilities(runner)
    nave_version = str(capabilities.get("protocol_version")) if capabilities.get("protocol_version") is not None else None
    if capabilities.get("adapter_state") != "ok":
        return _write_failure(
            result_path, state="blocked", reason=capabilities.get("reason") or "capability handshake failed",
            actor=actor, workspace=workspace, proposal=proposal, recorded_summary=recorded_summary,
            proposal_digest=proposal_digest, authorization_digest=authorization_digest,
            nave_version=nave_version,
        )

    try:
        lease = resolve_run.acquire_lease(ledger_path, step_id, actor_id)
    except resolve_run.LeaseError as exc:
        return _write_failure(
            result_path, state="blocked", reason=exc, actor=actor, workspace=workspace,
            proposal=proposal, recorded_summary=recorded_summary,
            proposal_digest=proposal_digest, authorization_digest=authorization_digest,
            nave_version=nave_version,
        )
    token = lease["token"]
    apply_branch = f"pulse/apply/{proposal.id}"
    pen_name = f"pulse-apply-{proposal.id}"
    journal = Journal(Path(f"{result_path}.journal"))

    def failure(state, reason, outcomes=None):
        return _write_failure(
            result_path, state=state, reason=reason, actor=actor, workspace=workspace,
            proposal=proposal, recorded_summary=recorded_summary,
            proposal_digest=proposal_digest, authorization_digest=authorization_digest,
            nave_version=nave_version, repo_outcomes=outcomes,
        )

    def _finish_push(repo, remote_sha):
        """Durable pushed receipt + PR open for one repo — shared by the normal
        path and the pushed-boundary crash-resume path."""
        actor_doc = {"gh_login": actor.gh_login, "machine": actor.machine, "mode": actor.mode}
        pushed_result = apply_reconcile.write_apply_status(
            result_path,
            proposal_id=proposal.id,
            selection=list(selection),
            repos={
                repo: {
                    "branch": apply_branch,
                    "state": "pushed",
                    "intended_base": base_refs[repo],
                    "expected_head_sha": remote_sha,
                    "pushed_sha": remote_sha,
                    "pr_url": None,
                    "merged_sha": None,
                    "observed_base": None,
                    "observed_head_sha": None,
                    "reason": None,
                },
            },
            state="pushed",
            recorded_proposal_id=recorded_summary["proposal_id"],
            proposal_digest=proposal_digest,
            authorization_digest=authorization_digest,
            workspace=workspace,
            actor=actor_doc,
        )
        try:
            resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
            journal.begin(repo, "pr_opened", token)
            result = apply_reconcile.open_apply_pr(
                ledger_path=ledger_path, step_id=step_id, proposal_id=proposal.id,
                repo=repo, branch=apply_branch, base=base_refs[repo], pushed_sha=remote_sha,
                title=f"pulse-apply {proposal.id}", body=f"Automated apply for proposal {proposal.id}.",
                result_path=result_path, gh_ops=gh_ops,
                recorded_proposal_id=recorded_summary["proposal_id"],
                proposal_digest=proposal_digest, authorization_digest=authorization_digest,
                intended_base=base_refs[repo], expected_head_sha=remote_sha,
                selection=list(selection), token=token, actor_id=actor_id, workspace=workspace,
            )
            journal.complete(repo, "pr_opened", pr_url=result.get("repos", {}).get(repo, {}).get("pr_url"))
            return result
        except Exception:
            # The pushed receipt is the crash-recovery input. Never replace it
            # with a pre-push repo-mutation document when PR creation fails.
            return pushed_result
    repo = selection[0]

    if len(selection) > 1:
        return _run_multi_repo(
            ledger_path=ledger_path, step_id=step_id, actor_id=actor_id, token=token,
            runner=runner, gh_ops=gh_ops, result_path=result_path, workspace=workspace,
            proposal=proposal, selection=list(selection), base_refs=base_refs, entry=entry,
            recorded_summary=recorded_summary, proposal_digest=proposal_digest,
            authorization_digest=authorization_digest, actor=actor, nave_version=nave_version,
        )

    try:
        with ApplyLock(f"{ledger_path}.apply.lock"):
            resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
            previous = journal.state(repo)
            resume_transform = (
                previous["in_progress"] == "transformed"
                and journal.resume_action(repo) == RESET_AND_REEXEC_TRANSFORM
            )
            resume_pushed = (
                previous["in_progress"] == "pushed" or previous["phase"] == "pushed"
            )
            if previous["in_progress"] and not (resume_transform or resume_pushed):
                return failure(
                    "failed",
                    f"resume requires live remote reconciliation for in-progress "
                    f"{previous['in_progress']}; refusing blind reuse",
                )
            if previous["phase"] is not None and not (resume_transform or resume_pushed):
                if previous["phase"] == "pr_opened":
                    existing = apply_reconcile.load_apply_status(result_path)
                    if existing and existing.get("state") in {"pr_opened", "applied", "rejected"}:
                        return existing
                return failure(
                    "failed",
                    f"resume requires live evidence for completed {previous['phase']}; "
                    "refusing blind reuse",
                )
            if resume_pushed:
                remote_sha = previous["evidence"].get("remote_sha")
                if not remote_sha:
                    return failure("failed", "resume from pushed: missing remote_sha journal evidence")
                return _finish_push(repo, remote_sha)
            if resume_transform:
                pen = {"name": pen_name, "repos": [{"repo": repo}]}
            else:
                journal.begin(repo, "pen_ready", token)
                handle = nave_adapter.pen_create(
                    runner, nave_adapter.PenQuery(terms=list(proposal.selection)), pen_name
                )
                if handle.state != "ok":
                    return failure("failed", handle.stderr or "pen create failed")
                pen = handle.pen
            status = nave_adapter.pen_status(runner, pen_name)
            clone_paths = {
                f"{item['owner']}/{item['repo']}": item["clone_path"]
                for item in status.get("repos", [])
                if isinstance(item, dict) and item.get("owner") and item.get("repo") and item.get("clone_path")
            }
            try:
                pen_clone_reader.make_pen_clone_reader(clone_paths, proposal.selection)
            except Exception as exc:
                return failure("blocked", f"clone identity preflight failed: {exc}")
            if not resume_transform:
                outcomes = apply_phases.preflight_phase(runner, pen, proposal, clone_paths)
                if any(item.get("state") != "ok" for item in outcomes.values()):
                    return failure("blocked", _phase_reason("preflight", outcomes), _failed_outcomes(outcomes, "blocked"))
                journal.complete(repo, "pen_ready")

            ops = apply_ops.make_apply_ops(runner, pen_name, dict(proposal.bound_paths), base_refs)
            if resume_transform:
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                reset = ops.reset_repos(apply_branch, {repo: None})
                if reset.get(repo, {}).get("state") != "ok":
                    return failure("failed", f"resume reset failed: {reset.get(repo, {}).get('reason')}")
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                setattr(ops, "_apply_branch", apply_branch)
                base_sha = previous["evidence"].get("observed_base_sha")
                if base_sha != proposal.expected_shas[repo]:
                    return failure("failed", "resume provisioned-base evidence mismatch")
            else:
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                journal.begin(repo, "branch_provisioned", token, apply_branch=apply_branch,
                              expected_base_sha=proposal.expected_shas[repo], base_ref=base_refs[repo])
                outcomes = apply_phases.provision_phase(runner, pen, ops, proposal, apply_branch, base_refs)
                if any(item.get("state") != "ok" for item in outcomes.values()):
                    resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                    apply_phases.cleanup(ops, apply_branch, {repo: None})
                    return failure("blocked", _phase_reason("provision", outcomes), _failed_outcomes(outcomes, "blocked"))
                base_sha = outcomes[repo]["observed_base_sha"]
                journal.complete(repo, "branch_provisioned", observed_base_sha=base_sha)
            reader = pen_clone_reader.make_pen_clone_reader(
                clone_paths, proposal.selection, expected_branch=apply_branch,
                expected_heads={repo: base_sha}, expected_remotes={repo: repo},
            )

            if resume_transform:
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                outcomes = apply_phases.exec_phase(runner, pen, entry)
                if any(item.get("state") != "ok" for item in outcomes.values()):
                    resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                    apply_phases.cleanup(ops, apply_branch, {repo: None})
                    state = "blocked" if any(item.get("state") == "blocked" for item in outcomes.values()) else "failed"
                    return failure(state, _phase_reason("transformed", outcomes), _failed_outcomes(outcomes, state))
                journal.complete(repo, "transformed")
            phases = (("validated", lambda: apply_phases.validate_phase(entry, reader, proposal)),) if resume_transform else (
                ("transformed", lambda: apply_phases.exec_phase(runner, pen, entry)),
                ("validated", lambda: apply_phases.validate_phase(entry, reader, proposal)),
            )
            for phase, operation in phases:
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                journal.begin(repo, phase, token)
                outcomes = operation()
                if any(item.get("state") != "ok" for item in outcomes.values()):
                    resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                    apply_phases.cleanup(ops, apply_branch, {repo: None})
                    state = "blocked" if any(item.get("state") == "blocked" for item in outcomes.values()) else "failed"
                    return failure(state, _phase_reason(phase, outcomes), _failed_outcomes(outcomes, state))
                journal.complete(repo, phase)

            resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
            journal.begin(repo, "committed", token)
            bound_paths = {
                r: _expand_bound_globs(clone_paths[r], proposal.bound_paths.get(r, ()))
                for r in proposal.selection
            }
            outcomes = apply_phases.commit_phase(
                ops, proposal, f"pulse-apply {proposal.id} by {actor.gh_login}@{actor.machine}",
                bound_paths=bound_paths,
            )
            if outcomes[repo].get("state") != "ok":
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                apply_phases.cleanup(ops, apply_branch, {repo: None})
                return failure("failed", _phase_reason("commit", outcomes), _failed_outcomes(outcomes, "failed"))
            local_sha = outcomes[repo]["local_commit_sha"]
            journal.complete(repo, "committed", local_commit_sha=local_sha)

            resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
            journal.begin(repo, "pushed", token, local_commit_sha=local_sha)
            outcomes = apply_phases.push_phase(ops, reader, apply_branch, {repo: local_sha})
            if outcomes[repo].get("state") != "ok":
                resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
                apply_phases.cleanup(ops, apply_branch, {repo: None})
                return failure("failed", _phase_reason("push", outcomes), _failed_outcomes(outcomes, "failed"))
            remote_sha = outcomes[repo]["remote_sha"]
            journal.complete(repo, "pushed", remote_ref=outcomes[repo]["remote_ref"], remote_sha=remote_sha)
            return _finish_push(repo, remote_sha)
    except (resolve_run.LeaseError, ApplyLockError) as exc:
        return failure("blocked", f"fencing stopped apply: {exc}")
    except Exception as exc:
        return failure("failed", exc)

def _run_multi_repo(
    *,
    ledger_path,
    step_id,
    actor_id,
    token,
    runner,
    gh_ops,
    result_path,
    workspace,
    proposal,
    selection,
    base_refs,
    entry,
    recorded_summary,
    proposal_digest,
    authorization_digest,
    actor,
    nave_version,
) -> dict:
    """Drive one proposal across N repos with per-repo independent outcomes."""
    apply_branch = f"pulse/apply/{proposal.id}"
    pen_name = f"pulse-apply-{proposal.id}"
    journal = Journal(Path(f"{result_path}.journal"))
    actor_doc = {"gh_login": actor.gh_login, "machine": actor.machine, "mode": actor.mode}

    def _repo_doc(repo, state, reason=None, **fields):
        doc = {
            "branch": apply_branch,
            "state": state,
            "intended_base": base_refs.get(repo),
            "expected_head_sha": proposal.expected_shas.get(repo),
            "pushed_sha": None,
            "pr_url": None,
            "merged_sha": None,
            "observed_base": None,
            "observed_head_sha": None,
            "reason": reason,
        }
        doc.update(fields)
        return doc

    def _subset_proposal(repos):
        return mutation_plan.Proposal(
            id=proposal.id,
            selection=tuple(repos),
            transformation=proposal.transformation,
            expected_shas={r: proposal.expected_shas[r] for r in repos},
            mutation_policy=proposal.mutation_policy,
            actor=proposal.actor,
            bound_paths={r: proposal.bound_paths[r] for r in repos},
        )

    def _subset_pen(pen, repos):
        keep = {f"{item.get('owner')}/{item.get('repo')}" if item.get("owner") else item.get("repo")
                for item in pen.get("repos", [])}
        return {"name": pen.get("name"), "repos": [i for i in pen.get("repos", [])
                                                  if (i.get("repo") or f"{i.get('owner')}/{i.get('repo')}") in set(repos)]}

    def _write_fleet(repos_doc):
        return apply_reconcile.write_apply_status(
            result_path,
            proposal_id=proposal.id,
            selection=list(selection),
            repos=repos_doc,
            state=apply_reconcile.rollup_state(repos_doc),
            recorded_proposal_id=recorded_summary["proposal_id"],
            proposal_digest=proposal_digest,
            authorization_digest=authorization_digest,
            workspace=workspace,
            actor=actor_doc,
        )

    def _finish(repo, remote_sha):
        pushed = apply_reconcile.upsert_repo_status(
            result_path,
            proposal_id=proposal.id,
            selection=list(selection),
            repo=repo,
            repo_doc=_repo_doc(repo, "pushed", pushed_sha=remote_sha),
            recorded_proposal_id=recorded_summary["proposal_id"],
            proposal_digest=proposal_digest,
            authorization_digest=authorization_digest,
            workspace=workspace,
            actor=actor_doc,
        )
        try:
            resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
            journal.begin(repo, "pr_opened", token)
            result = apply_reconcile.open_apply_pr(
                ledger_path=ledger_path, step_id=step_id, proposal_id=proposal.id,
                repo=repo, branch=apply_branch, base=base_refs[repo], pushed_sha=remote_sha,
                title=f"pulse-apply {proposal.id}", body=f"Automated apply for proposal {proposal.id}.",
                result_path=result_path, gh_ops=gh_ops,
                recorded_proposal_id=recorded_summary["proposal_id"],
                proposal_digest=proposal_digest, authorization_digest=authorization_digest,
                intended_base=base_refs[repo], expected_head_sha=remote_sha,
                selection=list(selection), token=token, actor_id=actor_id, workspace=workspace,
            )
            journal.complete(repo, "pr_opened", pr_url=result.get("repos", {}).get(repo, {}).get("pr_url"))
            return result
        except Exception:
            return pushed

    try:
        with ApplyLock(f"{ledger_path}.apply.lock"):
            resolve_run.renew_lease(ledger_path, step_id, actor_id, token)
            handle = nave_adapter.pen_create(
                runner, nave_adapter.PenQuery(terms=list(proposal.selection)), pen_name
            )
            if handle.state != "ok":
                return _write_failure(
                    result_path, state="failed", reason=handle.stderr or "pen create failed",
                    actor=actor, workspace=workspace, proposal=proposal,
                    recorded_summary=recorded_summary, proposal_digest=proposal_digest,
                    authorization_digest=authorization_digest, nave_version=nave_version,
                )
            pen = handle.pen
            status = nave_adapter.pen_status(runner, pen_name)
            clone_paths = {
                f"{item['owner']}/{item['repo']}": item["clone_path"]
                for item in status.get("repos", [])
                if isinstance(item, dict) and item.get("owner") and item.get("repo") and item.get("clone_path")
            }
            try:
                pen_clone_reader.make_pen_clone_reader(clone_paths, proposal.selection)
            except Exception as exc:
                return _write_failure(
                    result_path, state="blocked", reason=f"clone identity preflight failed: {exc}",
                    actor=actor, workspace=workspace, proposal=proposal,
                    recorded_summary=recorded_summary, proposal_digest=proposal_digest,
                    authorization_digest=authorization_digest, nave_version=nave_version,
                )

            outcomes = {}
            preflight = apply_phases.preflight_phase(runner, pen, proposal, clone_paths)
            for repo in proposal.selection:
                o = preflight.get(repo, {})
                if o.get("state") != "ok":
                    outcomes[repo] = _repo_doc(repo, "blocked", o.get("reason") or "preflight failed")
            pending = [r for r in proposal.selection if r not in outcomes]
            if not pending:
                return _write_fleet(outcomes)

            ops = apply_ops.make_apply_ops(runner, pen_name, dict(proposal.bound_paths), base_refs)
            for repo in pending:
                journal.begin(repo, "branch_provisioned", token, apply_branch=apply_branch,
                              expected_base_sha=proposal.expected_shas[repo], base_ref=base_refs[repo])
            prov = apply_phases.provision_phase(runner, pen, ops, proposal, apply_branch, base_refs)
            base_shas = {}
            for repo in list(pending):
                o = prov.get(repo, {})
                if o.get("state") != "ok":
                    outcomes[repo] = _repo_doc(repo, "blocked", o.get("reason") or "provision failed")
                    pending.remove(repo)
                else:
                    base_shas[repo] = o["observed_base_sha"]
                    journal.complete(repo, "branch_provisioned", observed_base_sha=o["observed_base_sha"])
            if not pending:
                return _write_fleet(outcomes)

            reader = pen_clone_reader.make_pen_clone_reader(
                clone_paths, tuple(pending), expected_branch=apply_branch,
                expected_heads=base_shas, expected_remotes={r: r for r in pending},
            )
            for repo in pending:
                journal.begin(repo, "transformed", token)
            sub_pen = _subset_pen(pen, pending)
            executed = apply_phases.exec_phase(runner, sub_pen, entry)
            for repo in list(pending):
                o = executed.get(repo, {})
                if o.get("state") != "ok":
                    outcomes[repo] = _repo_doc(repo, o.get("state", "failed") if o.get("state") in ("blocked", "failed") else "failed", o.get("reason") or "transform failed")
                    pending.remove(repo)
                else:
                    journal.complete(repo, "transformed")
            if not pending:
                return _write_fleet(outcomes)

            for repo in pending:
                journal.begin(repo, "validated", token)
            validated = apply_phases.validate_phase(entry, reader, _subset_proposal(pending))
            for repo in list(pending):
                o = validated.get(repo, {})
                if o.get("state") != "ok":
                    outcomes[repo] = _repo_doc(repo, o.get("state", "failed") if o.get("state") in ("blocked", "failed") else "failed", o.get("reason") or "validate failed")
                    pending.remove(repo)
                else:
                    journal.complete(repo, "validated")
            if not pending:
                return _write_fleet(outcomes)

            for repo in pending:
                journal.begin(repo, "committed", token)
            bound_paths = {
                r: _expand_bound_globs(clone_paths[r], proposal.bound_paths.get(r, ()))
                for r in pending
            }
            committed = apply_phases.commit_phase(
                ops, _subset_proposal(pending),
                f"pulse-apply {proposal.id} by {actor.gh_login}@{actor.machine}",
                bound_paths=bound_paths,
            )
            local_shas = {}
            for repo in list(pending):
                o = committed.get(repo, {})
                if o.get("state") != "ok":
                    outcomes[repo] = _repo_doc(repo, "failed", o.get("reason") or "commit failed")
                    pending.remove(repo)
                else:
                    local_shas[repo] = o["local_commit_sha"]
                    journal.complete(repo, "committed", local_commit_sha=o["local_commit_sha"])
            if not pending:
                return _write_fleet(outcomes)

            for repo in pending:
                journal.begin(repo, "pushed", token, local_commit_sha=local_shas[repo])
            pushed = apply_phases.push_phase(ops, reader, apply_branch, local_shas)
            for repo in list(pending):
                o = pushed.get(repo, {})
                if o.get("state") != "ok":
                    outcomes[repo] = _repo_doc(repo, "failed", o.get("reason") or "push failed")
                    pending.remove(repo)
                else:
                    journal.complete(repo, "pushed", remote_ref=o["remote_ref"], remote_sha=o["remote_sha"])

            for repo in pending:
                final = _finish(repo, pushed[repo]["remote_sha"])
                outcomes[repo] = final.get("repos", {}).get(repo, _repo_doc(repo, "pr_opened", pushed_sha=pushed[repo]["remote_sha"]))
            return _write_fleet(outcomes)
    except (resolve_run.LeaseError, ApplyLockError) as exc:
        return _write_failure(
            result_path, state="blocked", reason=f"fencing stopped apply: {exc}",
            actor=actor, workspace=workspace, proposal=proposal,
            recorded_summary=recorded_summary, proposal_digest=proposal_digest,
            authorization_digest=authorization_digest, nave_version=nave_version,
        )
    except Exception as exc:
        return _write_failure(
            result_path, state="failed", reason=exc,
            actor=actor, workspace=workspace, proposal=proposal,
            recorded_summary=recorded_summary, proposal_digest=proposal_digest,
            authorization_digest=authorization_digest, nave_version=nave_version,
        )


def main(argv=None):
    """CLI entry point: run one apply against the real Nave + gh binaries."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run one apply-mode proposal")
    parser.add_argument("--source-kind", required=True)
    parser.add_argument("--binding-ref", required=True, help="JSON object")
    parser.add_argument("--recorded-summary", required=False, default=None,
                        help="JSON {binding, transformation, proposal_id}; omit for --source-kind neutral")
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--actor", required=True, help="login@machine")
    parser.add_argument("--result", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--fixtures", default=None, help="optional PULSE_NAVE_FIXTURES root")
    args = parser.parse_args(argv)

    if args.source_kind != "neutral" and not args.recorded_summary:
        parser.error("--recorded-summary is required unless --source-kind is neutral")

    runner = nave_adapter.NaveRunner(fixtures=args.fixtures)
    result = run_apply(
        source_kind=args.source_kind,
        binding_ref=json.loads(args.binding_ref),
        recorded_summary=json.loads(args.recorded_summary) if args.recorded_summary else None,
        authorization_path=args.authorization,
        ledger_path=args.ledger,
        step_id=args.step,
        actor_id=args.actor,
        runner=runner,
        gh_api=_default_gh_api,
        gh_ops=apply_reconcile.GhCliOps(),
        result_path=args.result,
        workspace=args.workspace,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
