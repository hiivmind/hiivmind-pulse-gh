"""Fail-closed, per-repository phases sequenced by the apply-mode driver."""

from __future__ import annotations

from lib.pulse.scripts import executor_probe, nave_adapter
from lib.pulse.scripts.mutation_plan import resolve_argv
from lib.pulse.scripts.pen_orchestrator import _validate


def _by_repo(result) -> dict[str, dict]:
    if not isinstance(result, dict):
        return {}
    repos = result.get("repos")
    if isinstance(repos, list):
        return {item.get("repo"): item for item in repos if isinstance(item, dict) and item.get("repo")}
    return result


def preflight_phase(runner, pen, proposal, clone_paths) -> dict[str, dict]:
    selection = proposal.selection
    pen_name = pen.get("name") if isinstance(pen, dict) else pen
    pen_repos = None
    if isinstance(pen, dict):
        pen_repos = {
            item.get("repo") or f"{item.get('owner')}/{item.get('name')}"
            for item in pen.get("repos", [])
        }
    status = nave_adapter.pen_status(runner, pen_name)
    status_repos = status.get("repos", []) if isinstance(status, dict) else []
    status_by_repo = {
        item.get("repo") if "/" in str(item.get("repo", "")) else f"{item.get('owner')}/{item.get('repo')}": item
        for item in status_repos
        if isinstance(item, dict)
    }
    exact = set(status_by_repo) == set(selection) and (pen_repos is None or pen_repos == set(selection))
    outcomes: dict[str, dict] = {}
    for repo in selection:
        reasons = []
        state = status_by_repo.get(repo)
        if not exact:
            reasons.append("pen selection/status repos do not exactly match proposal selection")
        if repo not in clone_paths:
            reasons.append("missing clone_path")
        if state is None:
            reasons.append("missing from pen status")
        else:
            if state.get("working_tree") != "clean":
                reasons.append(f"working tree not clean (working_tree={state.get('working_tree')!r})")
            if state.get("freshness") != "fresh" or state.get("divergence") != "up-to-date":
                reasons.append(
                    f"stale pen (freshness={state.get('freshness')!r}, divergence={state.get('divergence')!r})"
                )
        outcomes[repo] = {"state": "blocked", "reason": "; ".join(reasons)} if reasons else {"state": "ok"}
    return outcomes


def provision_phase(runner, pen, apply_ops, proposal, apply_branch, base_refs) -> dict[str, dict]:
    del runner, pen
    expected_shas = proposal.expected_shas
    raw = _by_repo(apply_ops.provision_branch(apply_branch, expected_shas))
    outcomes = {}
    for repo in proposal.selection:
        item = raw.get(repo)
        reason = None
        if not isinstance(item, dict) or item.get("state") != "ok":
            reason = item.get("reason", "missing provision result") if isinstance(item, dict) else "missing provision result"
        elif item.get("expected_base_sha") != expected_shas.get(repo):
            reason = "provision echoed expected_base_sha mismatch"
        elif item.get("apply_ref") != apply_branch:
            reason = "provision echoed apply_ref mismatch"
        elif base_refs and item.get("base_ref") != base_refs.get(repo):
            reason = "provision echoed base_ref mismatch"
        elif not item.get("base_ref"):
            reason = "provision missing echoed base_ref"
        elif item.get("observed_base_sha") != expected_shas.get(repo):
            reason = "stale-base: observed base SHA drifted from expected base SHA"
        outcomes[repo] = ({"state": "blocked", "reason": reason} if reason else {"state": "ok", "observed_base_sha": item["observed_base_sha"]})
    return outcomes


def exec_phase(runner, pen, entry) -> dict[str, dict]:
    argv = resolve_argv(entry)
    probe = executor_probe.probe_required_tool(argv[0])
    selection = tuple(
        item.get("repo") or f"{item.get('owner')}/{item.get('name')}"
        for item in pen.get("repos", [])
    ) if isinstance(pen, dict) else ()
    if probe.get("state") != "ok":
        return {repo: {"state": "blocked", "reason": probe.get("reason", "required tool missing")} for repo in selection}
    pen_name = pen.get("name") if isinstance(pen, dict) else pen
    result = nave_adapter.pen_exec(runner, pen_name, list(argv), only=None, commit=False, push_changes=False, message=None)
    if result.get("adapter_state") == "error":
        reason = (result.get("stderr") or "").strip() or "pen exec failed"
        return {repo: {"state": "failed", "reason": reason} for repo in selection}
    return {repo: {"state": "ok"} for repo in selection}


def validate_phase(entry, reader, proposal) -> dict[str, dict]:
    failure = _validate(
        entry.validation,
        reader.read_repo_file,
        reader.read_repo_changed_paths,
        proposal.bound_paths,
        proposal.selection,
    )
    if failure is None:
        return {repo: {"state": "ok"} for repo in proposal.selection}
    repo_outcomes, reason, state = failure
    return {
        repo: ({"state": repo_outcomes[repo], "reason": reason} if repo_outcomes[repo] != "ok" else {"state": "ok"})
        for repo in proposal.selection
    }


def commit_phase(apply_ops, proposal, message) -> dict[str, dict]:
    raw = _by_repo(apply_ops.commit_repos(message, proposal.bound_paths))
    outcomes = {}
    for repo in proposal.selection:
        item = raw.get(repo)
        if not isinstance(item, dict) or item.get("state") != "ok" or not item.get("local_commit_sha"):
            reason = item.get("reason", "commit failed or missing local_commit_sha") if isinstance(item, dict) else "missing commit result"
            outcomes[repo] = {"state": "failed", "reason": reason}
        else:
            outcomes[repo] = {"state": "ok", "local_commit_sha": item["local_commit_sha"]}
    return outcomes


def push_phase(apply_ops, reader, apply_branch, expected_local_shas) -> dict[str, dict]:
    outcomes = {}
    eligible = True
    for repo, expected in expected_local_shas.items():
        try:
            actual = reader.read_repo_head(repo)
        except Exception as exc:
            actual = None
            outcomes[repo] = {"state": "failed", "reason": f"could not read local HEAD: {exc}"}
            eligible = False
        if actual is not None and actual != expected:
            outcomes[repo] = {"state": "failed", "reason": f"local HEAD {actual!r} does not match commit SHA {expected!r}"}
            eligible = False
    if not eligible:
        for repo in expected_local_shas:
            outcomes.setdefault(repo, {"state": "failed", "reason": "push blocked by another repo's invalid local HEAD"})
        return outcomes
    raw = _by_repo(apply_ops.push_repos(apply_branch))
    for repo, expected in expected_local_shas.items():
        item = raw.get(repo)
        reason = None
        if not isinstance(item, dict) or item.get("state") != "ok":
            reason = item.get("reason", "missing push result") if isinstance(item, dict) else "missing push result"
        elif item.get("remote_sha") != expected:
            reason = "remote_sha does not match local_commit_sha"
        elif item.get("remote_ref") != apply_branch:
            reason = "remote_ref does not match apply branch"
        if reason:
            outcomes[repo] = {"state": "failed", "reason": reason}
        else:
            outcomes[repo] = {"state": "ok", **{key: item.get(key) for key in ("remote_ref", "remote_sha", "upstream")}}
    return outcomes


def cleanup(apply_ops, apply_branch, pushed_shas) -> None:
    apply_ops.reset_repos(apply_branch, pushed_shas)
