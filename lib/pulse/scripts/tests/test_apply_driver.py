import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from lib.pulse.scripts import apply_driver, apply_rederive, mutation_plan, resolve_run


REPO = "acme/widget"


class RecordingRunner:
    def __init__(self):
        self.calls = []


class FakeGhOps:
    def __init__(self, result_path=None, fail=False):
        self.calls = []
        self.result_path = result_path
        self.fail = fail

    def create_or_get_pr(self, **kwargs):
        if self.result_path:
            self.calls.append(("status", yaml.safe_load(self.result_path.read_text())["state"]))
        self.calls.append(("create", kwargs))
        if self.fail:
            raise RuntimeError("PR unavailable")
        return {"url": "https://github.test/acme/widget/pull/1", "created": True}


class FakeOps:
    def __init__(self):
        self.calls = []

    def provision_branch(self, branch, shas):
        self.calls.append("branch")
        return {REPO: {"state": "ok", "base_ref": "main", "expected_base_sha": "base",
                       "observed_base_sha": "base", "apply_ref": branch}}

    def commit_repos(self, message, bounds):
        self.calls.append("commit")
        return {REPO: {"state": "ok", "local_commit_sha": "commit"}}

    def push_repos(self, branch):
        self.calls.append("push")
        return {REPO: {"state": "ok", "remote_ref": branch, "remote_sha": "commit",
                       "upstream": f"origin/{branch}"}}

    def reset_repos(self, branch, shas):
        self.calls.append("reset")
        return {REPO: {"state": "ok"}}


def proposal(selection=(REPO,), proposal_id="p1"):
    return mutation_plan.build_proposal(
        id=proposal_id, selection=list(selection), transformation="format-python",
        expected_shas={repo: "base" for repo in selection},
        actor={"gh_login": "octocat", "machine": "host", "mode": "interactive"},
        mutation_policy="allow-listed", bound_paths={repo: ("x.txt",) for repo in selection},
    )


def setup_run(tmp_path, monkeypatch, selection=(REPO,), authorize_error=None):
    prop = proposal(selection)
    registry = mutation_plan.load_registry({"transformations": {"format-python": {
        "id": "format-python", "command_argv": ["formatter"], "applies_to": ["always"],
        "validation": {"kind": "none"}, "allow_scheduled": True,
    }}})
    inputs = SimpleNamespace(registry=registry)
    rederived = apply_rederive.RederivedProposal("binding", prop, "generated-artifact", None)
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: inputs)
    monkeypatch.setattr(apply_driver.apply_rederive, "rederive", lambda value: rederived)
    monkeypatch.setattr(apply_driver.apply_authorization, "load_authorization", lambda *a: object())
    monkeypatch.setattr(apply_driver.apply_authorization, "authorization_digest", lambda a: "v1|" + "b" * 64)
    if authorize_error:
        monkeypatch.setattr(apply_driver.apply_authorization, "authorize", lambda *a: (_ for _ in ()).throw(authorize_error))
    else:
        monkeypatch.setattr(apply_driver.apply_authorization, "authorize", lambda *a: None)
    monkeypatch.setattr(apply_driver.apply_reconcile, "resolve_intended_base", lambda *a: "main")
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml.safe_dump({
        "ledger_version": 1, "run_id": "r", "workflow": "w", "status": "running",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "host"}, "params": {}, "repos": [REPO],
        "steps": [{"id": "step", "repo": REPO, "depends_on": [], "gate": None,
                   "status": "pending", "notes": []}],
    }, sort_keys=False))
    result = tmp_path / "result.yaml"
    runner = RecordingRunner()
    kwargs = dict(
        source_kind="generated-artifact", binding_ref={"id": "binding", "branch": "main"},
        recorded_summary={"binding": "binding", "transformation": "format-python", "proposal_id": "p1"},
        authorization_path=tmp_path / "auth.yaml", ledger_path=ledger, step_id="step",
        actor_id="octocat@host", runner=runner, gh_ops=FakeGhOps(), result_path=result,
        workspace=str(tmp_path),
    )
    return kwargs, runner, ledger, result


def install_happy(monkeypatch, runner):
    ops = FakeOps()
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_capabilities", lambda r: runner.calls.append(["pen", "capabilities"]) or {"adapter_state": "ok", "protocol_version": 1})
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_create", lambda r, q, n: runner.calls.append(["pen", "create"]) or SimpleNamespace(state="ok", pen={"name": n, "repos": [{"repo": REPO}]}, stderr=""))
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_status", lambda r, n: {"repos": [{"owner": "acme", "repo": "widget", "clone_path": "/clone"}]})
    reader = SimpleNamespace(read_repo_head=lambda repo: "commit", read_repo_file=lambda *a: b"", read_repo_changed_paths=lambda *a: ())
    monkeypatch.setattr(apply_driver.pen_clone_reader, "make_pen_clone_reader", lambda *a, **k: reader)
    monkeypatch.setattr(apply_driver.apply_phases, "preflight_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_phases, "exec_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_phases, "validate_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_ops, "make_apply_ops", lambda *a: ops)
    return ops


def test_unauthorized_blocks_before_pen_create(tmp_path, monkeypatch):
    from lib.pulse.scripts.apply_authorization import AuthorizationError
    kwargs, runner, _, _ = setup_run(tmp_path, monkeypatch, authorize_error=AuthorizationError("denied"))
    assert apply_driver.run_apply(**kwargs)["state"] == "blocked"
    assert not any(call[:2] == ["pen", "create"] for call in runner.calls)


def test_run_apply_multi_repo_one_repo_fails_others_continue(tmp_path, monkeypatch):
    from types import SimpleNamespace

    other = "acme/other"
    kwargs, runner, _, _ = setup_run(tmp_path, monkeypatch, (REPO, other))

    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_capabilities",
        lambda r: runner.calls.append(["pen", "capabilities"]) or {
            "adapter_state": "ok", "protocol_version": 1},
    )
    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_create",
        lambda r, q, n: runner.calls.append(["pen", "create"]) or SimpleNamespace(
            state="ok", pen={"name": n, "repos": [{"repo": REPO}, {"repo": other}]}, stderr=""),
    )
    monkeypatch.setattr(
        apply_driver.nave_adapter, "pen_status", lambda r, n: {
            "repos": [
                {"owner": "acme", "repo": "widget", "clone_path": "/clone/widget"},
                {"owner": "acme", "repo": "other", "clone_path": "/clone/other"},
            ]},
    )
    reader = SimpleNamespace(
        read_repo_head=lambda repo: "commit",
        read_repo_file=lambda *a: b"",
        read_repo_changed_paths=lambda *a: (),
    )
    monkeypatch.setattr(apply_driver.pen_clone_reader, "make_pen_clone_reader", lambda *a, **k: reader)
    monkeypatch.setattr(
        apply_driver.apply_phases, "preflight_phase",
        lambda *a: {REPO: {"state": "ok"}, other: {"state": "ok"}},
    )
    monkeypatch.setattr(
        apply_driver.apply_phases, "provision_phase",
        lambda *a: {REPO: {"state": "ok", "observed_base_sha": "base"},
                    other: {"state": "failed", "reason": "boom"}},
    )
    monkeypatch.setattr(apply_driver.apply_phases, "exec_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_phases, "validate_phase", lambda *a: {REPO: {"state": "ok"}})

    class MultiOps:
        def __init__(self):
            self.calls = []
        def commit_repos(self, message, bounds):
            self.calls.append("commit")
            return {REPO: {"state": "ok", "local_commit_sha": "commit"}}
        def push_repos(self, branch):
            self.calls.append("push")
            return {REPO: {"state": "ok", "remote_ref": branch, "remote_sha": "commit",
                           "upstream": f"origin/{branch}"}}

    monkeypatch.setattr(apply_driver.apply_ops, "make_apply_ops", lambda *a: MultiOps())

    result = apply_driver.run_apply(**kwargs)
    assert result["state"] == "pr_opened"
    assert result["repos"][other]["state"] == "blocked"
    assert "boom" in result["repos"][other]["reason"]
    assert result["repos"][REPO]["state"] == "pr_opened"


def test_summary_identity_mismatch_blocks_before_pen_create(tmp_path, monkeypatch):
    from lib.pulse.scripts.apply_authorization import AuthorizationError
    kwargs, runner, _, _ = setup_run(tmp_path, monkeypatch, authorize_error=AuthorizationError("proposal_id mismatch"))
    result = apply_driver.run_apply(**kwargs)
    assert "mismatch" in result["reason"] and not runner.calls


def test_handshake_failure_snapshots_audit_before_any_branch(tmp_path, monkeypatch):
    kwargs, runner, ledger, _ = setup_run(tmp_path, monkeypatch)
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_capabilities", lambda r: runner.calls.append(["pen", "capabilities"]) or {"adapter_state": "error", "reason": "old Nave"})
    result = apply_driver.run_apply(**kwargs)
    assert result["state"] == "blocked"
    assert "step" in yaml.safe_load(ledger.read_text())["state_snapshot"]
    assert not any(call[:2] == ["pen", "branch"] for call in runner.calls)


def test_lock_is_entered_before_pen_create(tmp_path, monkeypatch):
    kwargs, runner, _, _ = setup_run(tmp_path, monkeypatch)
    install_happy(monkeypatch, runner)
    events = []
    class Lock:
        def __init__(self, path): events.append("lock-init")
        def __enter__(self): events.append("lock-enter")
        def __exit__(self, *args): events.append("lock-exit")
    monkeypatch.setattr(apply_driver, "ApplyLock", Lock)
    original = apply_driver.nave_adapter.pen_create
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_create", lambda *a: events.append("pen-create") or original(*a))
    assert apply_driver.run_apply(**kwargs)["state"] == "pr_opened"
    assert events.index("lock-enter") < events.index("pen-create") < events.index("lock-exit")


def test_stolen_token_stops_before_next_nave_or_github_call(tmp_path, monkeypatch):
    kwargs, runner, _, _ = setup_run(tmp_path, monkeypatch)
    ops = install_happy(monkeypatch, runner)
    real = resolve_run.renew_lease
    count = 0
    def stolen(*args):
        nonlocal count
        count += 1
        if count == 3:
            raise resolve_run.LeaseError("lease token mismatch")
        return real(*args)
    monkeypatch.setattr(apply_driver.resolve_run, "renew_lease", stolen)
    result = apply_driver.run_apply(**kwargs)
    assert result["state"] == "blocked" and "fencing" in result["reason"]
    assert ops.calls == ["branch"]
    assert kwargs["gh_ops"].calls == []


def test_happy_path_persists_pushed_sha_before_opening_pr(tmp_path, monkeypatch):
    kwargs, runner, _, result_path = setup_run(tmp_path, monkeypatch)
    install_happy(monkeypatch, runner)
    gh = FakeGhOps(result_path)
    kwargs["gh_ops"] = gh
    result = apply_driver.run_apply(**kwargs)
    assert result["state"] == "pr_opened"
    assert result["repos"][REPO]["expected_head_sha"] == "commit" == result["repos"][REPO]["pushed_sha"]
    assert gh.calls[0] == ("status", "pushed")


def test_resume_transformed_reset_failure_fails_closed(tmp_path, monkeypatch):
    kwargs, runner, _, result_path = setup_run(tmp_path, monkeypatch)
    ops = install_happy(monkeypatch, runner)
    # Simulate a crash after transformed began: journal holds an in-progress
    # transformed boundary with the provisioned base evidence.
    apply_driver.Journal(Path(f"{result_path}.journal")).begin(
        REPO, "transformed", "token", observed_base_sha="base"
    )
    ops.reset_repos = lambda branch, shas: {REPO: {"state": "failed", "reason": "reset refused"}}

    result = apply_driver.run_apply(**kwargs)

    assert result["state"] == "failed"
    assert "reset failed" in result["reason"]
    assert "commit" not in ops.calls and "push" not in ops.calls


def test_resume_from_completed_push_reopens_pr_from_durable_evidence(tmp_path, monkeypatch):
    kwargs, runner, _, result_path = setup_run(tmp_path, monkeypatch)
    ops = install_happy(monkeypatch, runner)
    journal = apply_driver.Journal(Path(f"{result_path}.journal"))
    journal.begin(REPO, "pushed", "token", remote_sha="commit")
    journal.complete(REPO, "pushed", remote_ref="pulse/apply/p1", remote_sha="commit")

    result = apply_driver.run_apply(**kwargs)

    assert result["state"] == "pr_opened"
    assert result["repos"][REPO]["pushed_sha"] == "commit"
    assert "commit" not in ops.calls and "push" not in ops.calls


def test_run_apply_neutral_synthesizes_summary_and_threads_gh_api(tmp_path, monkeypatch):
    from lib.pulse.scripts.apply_authorization import AuthorizationError

    captured = {}

    def fake_collect(source_kind, binding_ref, recorded_summary, *, actor, io_seams):
        captured["recorded_summary"] = recorded_summary
        captured["gh_api"] = io_seams.gh_api
        return SimpleNamespace(registry=None)

    def fake_rederive(inputs):
        prop = mutation_plan.build_proposal(
            id="apply-format-python-hiivmind-agent-kernel",
            selection=["hiivmind/agent-kernel"], transformation="format-python",
            expected_shas={"hiivmind/agent-kernel": "e" * 40},
            actor={"gh_login": "octocat", "machine": "host", "mode": "interactive"},
            mutation_policy="allow-listed",
            bound_paths={"hiivmind/agent-kernel": ("src/**",)},
        )
        return apply_rederive.RederivedProposal("hiivmind/agent-kernel", prop, "neutral", None)

    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", fake_collect)
    monkeypatch.setattr(apply_driver.apply_rederive, "rederive", fake_rederive)
    monkeypatch.setattr(apply_driver.apply_authorization, "load_authorization", lambda *a: object())
    monkeypatch.setattr(apply_driver.apply_authorization, "authorization_digest", lambda a: "v1|" + "b" * 64)
    monkeypatch.setattr(apply_driver.apply_authorization, "authorize",
                        lambda *a: (_ for _ in ()).throw(AuthorizationError("stop")))

    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml.safe_dump({
        "ledger_version": 1, "run_id": "r", "workflow": "w", "status": "running",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "host"}, "params": {},
        "repos": ["hiivmind/agent-kernel"],
        "steps": [{"id": "step", "repo": "hiivmind/agent-kernel", "depends_on": [],
                   "gate": None, "status": "pending", "notes": []}],
    }, sort_keys=False))
    result = tmp_path / "result.yaml"
    fake_gh_api = lambda path: {"commit": {"sha": "e" * 40}}

    out = apply_driver.run_apply(
        source_kind="neutral",
        binding_ref={"repo": "hiivmind/agent-kernel", "transformation": "format-python",
                     "base_ref": "main", "bound_paths": ["src/**"]},
        recorded_summary=None,
        authorization_path=tmp_path / "auth.yaml", ledger_path=ledger, step_id="step",
        actor_id="octocat@host", runner=RecordingRunner(), gh_api=fake_gh_api,
        gh_ops=FakeGhOps(), result_path=result, workspace=str(tmp_path),
    )

    assert out["state"] == "blocked"
    assert captured["recorded_summary"] == {
        "binding": "hiivmind/agent-kernel",
        "transformation": "format-python",
        "proposal_id": "apply-format-python-hiivmind-agent-kernel",
        "selection": ["hiivmind/agent-kernel"],
    }
    assert captured["gh_api"] is fake_gh_api


def test_run_apply_rejects_missing_summary_for_non_neutral(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not collect")))
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml.safe_dump({
        "ledger_version": 1, "run_id": "r", "workflow": "w", "status": "running",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "actor": {"gh_login": "octocat", "machine": "host"}, "params": {},
        "repos": ["acme/widget"],
        "steps": [{"id": "step", "repo": "acme/widget", "depends_on": [],
                   "gate": None, "status": "pending", "notes": []}],
    }, sort_keys=False))
    result = tmp_path / "result.yaml"
    out = apply_driver.run_apply(
        source_kind="generated-artifact",
        binding_ref={"id": "binding", "branch": "main"},
        recorded_summary=None,
        authorization_path=tmp_path / "auth.yaml", ledger_path=ledger, step_id="step",
        actor_id="octocat@host", runner=RecordingRunner(), gh_ops=FakeGhOps(),
        result_path=result, workspace=str(tmp_path),
    )
    assert out["state"] == "blocked"
    assert "recorded_summary" in out["reason"]


def test_expand_bound_globs_matches_tracked_and_untracked(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "examples").mkdir()
    (tmp_path / "src").joinpath("a.py").write_text("x")
    (tmp_path / "src").joinpath("b.py").write_text("y")
    (tmp_path / "examples").joinpath("spinner.py").write_text("z")
    (tmp_path / "src").joinpath("ignored.txt").write_text("i")
    (tmp_path / ".gitignore").write_text("src/ignored.txt\n")
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "src", "examples", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "seed", "--no-verify"],
                   check=True, env={**__import__("os").environ,
                                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q", "src/ignored.txt"], check=False)
    (tmp_path / "src").joinpath("untracked.py").write_text("u")

    expanded = apply_driver._expand_bound_globs(
        str(tmp_path), ("src/**", "examples/**")
    )
    assert "src/a.py" in expanded
    assert "src/b.py" in expanded
    assert "src/untracked.py" in expanded
    assert "examples/spinner.py" in expanded
    assert not any("ignored" in p for p in expanded)


def test_run_apply_rederived_override_skips_collect_and_rederive_and_threads_transform_params(
    tmp_path, monkeypatch
):
    """When both inputs_override and rederived_override are supplied,
    run_apply must NOT call apply_rederive.collect_inputs/.rederive
    (collect-once/rederive-many callers already did that work), AND the
    proposal's transform_params must reach the real exec_phase ->
    resolve_argv -> nave_adapter.pen_exec call with placeholders actually
    substituted — the load-bearing correctness property of the whole
    dependency-bump feature. exec_phase is deliberately left UN-stubbed
    here (unlike install_happy's blanket stub) so resolve_argv genuinely
    runs; only its own collaborators (executor_probe, nave_adapter.pen_exec)
    are faked."""
    monkeypatch.setattr(
        apply_driver.apply_rederive, "collect_inputs",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("collect_inputs must not be called")),
    )
    monkeypatch.setattr(
        apply_driver.apply_rederive, "rederive",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("rederive must not be called")),
    )

    registry = mutation_plan.load_registry({"transformations": {"bump-python-uv": {
        "id": "bump-python-uv", "command_argv": ["uv", "add", "{package}=={version}"],
        "applies_to": ["always"], "validation": {"kind": "none"}, "allow_scheduled": False,
        "params": ["package", "version"],
    }}})
    prop = mutation_plan.build_proposal(
        id="apply-bump-python-requests-uv-abc123", selection=[REPO],
        transformation="bump-python-uv", expected_shas={REPO: "base"},
        actor={"gh_login": "octocat", "machine": "host", "mode": "interactive"},
        mutation_policy="allow-listed", bound_paths={REPO: ("pyproject.toml", "uv.lock")},
        transform_params={"package": "requests", "version": "2.32.0"},
        expected_tree_shas={REPO: "tree-abc"},
        registry=registry,
    )
    inputs = SimpleNamespace(registry=registry)
    rederived = apply_rederive.RederivedProposal(
        "apply-bump-python-requests-uv-abc123", prop, "dependency-bump",
        {"base_refs": {REPO: "main"}},
    )

    kwargs, runner, _, result = setup_run(tmp_path, monkeypatch, (REPO,))
    kwargs.update(
        source_kind="dependency-bump",
        binding_ref={"group": "core-runtime", "ecosystem": "python", "package": "requests"},
        recorded_summary={
            "binding": {"group": "core-runtime", "ecosystem": "python", "package": "requests"},
            "transformation": "bump-python-uv",
            "proposal_id": "apply-bump-python-requests-uv-abc123",
            "target": "2.32.0",
        },
        inputs_override=inputs, rederived_override=rederived,
    )
    ops = FakeOps()
    ops.provision_branch = lambda branch, shas: {
        REPO: {"state": "ok", "base_ref": "main", "expected_base_sha": "base",
               "observed_base_sha": "base", "apply_ref": branch, "observed_tree_sha": "tree-abc"},
    }
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_capabilities", lambda r: {"adapter_state": "ok", "protocol_version": 1})
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_create", lambda r, q, n: SimpleNamespace(state="ok", pen={"name": n, "repos": [{"repo": REPO}]}, stderr=""))
    monkeypatch.setattr(apply_driver.nave_adapter, "pen_status", lambda r, n: {"repos": [{"owner": "acme", "repo": "widget", "clone_path": "/clone"}]})
    reader = SimpleNamespace(read_repo_head=lambda repo: "commit", read_repo_file=lambda *a: b"", read_repo_changed_paths=lambda *a: ())
    monkeypatch.setattr(apply_driver.pen_clone_reader, "make_pen_clone_reader", lambda *a, **k: reader)
    monkeypatch.setattr(apply_driver.apply_phases, "preflight_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_phases, "validate_phase", lambda *a: {REPO: {"state": "ok"}})
    monkeypatch.setattr(apply_driver.apply_ops, "make_apply_ops", lambda *a: ops)
    # exec_phase is deliberately LEFT REAL here (unlike install_happy) —
    # only its own collaborators are faked, so resolve_argv's templating
    # genuinely executes end to end.
    monkeypatch.setattr(
        apply_driver.apply_phases.executor_probe, "probe_required_tool",
        lambda tool: {"state": "ok", "tool": tool, "ecosystem": "python"},
    )
    captured_argv = {}
    monkeypatch.setattr(
        apply_driver.apply_phases.nave_adapter, "pen_exec",
        lambda runner, name, argv, **kw: captured_argv.update(argv=argv) or {"adapter_state": "ok"},
    )

    outcome = apply_driver.run_apply(**kwargs)

    assert captured_argv["argv"] == ["uv", "add", "requests==2.32.0"]
    assert outcome["state"] == "pr_opened"


# --- run_apply_dependency_bump: collect-once, rederive-many, per-proposal pens ---


def test_run_apply_dependency_bump_calls_run_apply_once_per_manager_group(monkeypatch, tmp_path):
    """Two manager-group proposals for one finding must call `run_apply`
    once EACH, never once for the whole finding — each carries its own
    `rederived_override` (so its own pen, named `pulse-apply-{proposal.id}`
    by run_apply's existing unchanged logic — never shared; proposal ids
    already differ per manager, so there is no name collision to avoid by
    sharing). No `pen_name` kwarg is passed to `run_apply` at all: this
    task never introduces one."""
    finding_ref = {"group": "core-runtime", "ecosystem": "python", "package": "requests"}
    inputs = apply_rederive.DependencyBumpProviderInputs(
        finding_ref=finding_ref,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="core-runtime", ecosystem="python", package="requests",
            versions=(("acme/api", "2.28.0"), ("acme/other", "2.20.0")), distance="minor",
        ),
        target="2.31.0", selection=("acme/api", "acme/other"),
        records_by_repo={
            ("acme/api", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/api", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=2", locked_version="2.28.0", unresolved_reason=None,
                manager="uv", manifest_path="pyproject.toml", lock_path="uv.lock",
                tree_sha="tree-api", provenance=(),
            ),
            ("acme/other", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/other", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=2", locked_version="2.20.0", unresolved_reason=None,
                manager="poetry", manifest_path="pyproject.toml", lock_path="poetry.lock",
                tree_sha="tree-other", provenance=(),
            ),
        },
        head_shas={"acme/api": "a" * 40, "acme/other": "c" * 40},
        tree_shas={"acme/api": "tree-api", "acme/other": "tree-other"},
        default_branches={"acme/api": "main", "acme/other": "main"},
        blocked={}, actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: inputs)
    run_apply_calls = []

    def fake_run_apply(**kwargs):
        run_apply_calls.append(kwargs)
        return {"state": "pr_opened", "proposal_id": kwargs["rederived_override"].proposal.id}

    monkeypatch.setattr(apply_driver, "run_apply", fake_run_apply)
    result = apply_driver.run_apply_dependency_bump(
        finding_ref=finding_ref, authorization_path="/does/not/matter",
        ledger_path=str(tmp_path / "ledger.yaml"), step_id="step-1", actor_id="octocat@laptop",
        runner=SimpleNamespace(run=lambda args: None), gh_api=lambda ep: None,
        gh_ops=SimpleNamespace(), result_path=str(tmp_path / "result.yaml"),
        workspace=str(tmp_path),
    )
    assert len(run_apply_calls) == 2, "one run_apply call per manager-group proposal, never one per finding"
    proposal_ids = {kwargs["rederived_override"].proposal.id for kwargs in run_apply_calls}
    assert len(proposal_ids) == 2, "proposal ids (and therefore each run_apply call's own pen name) are distinct"
    for kwargs in run_apply_calls:
        assert "pen_name" not in kwargs
        assert kwargs["inputs_override"] is inputs
        pid = kwargs["rederived_override"].proposal.id
        assert kwargs["step_id"] == f"step-1.{pid}"
    assert result["state"] == "pr_opened"
    assert len(result["proposals"]) == 2


def test_run_apply_dependency_bump_rolls_up_worst_proposal_state(monkeypatch, tmp_path):
    finding_ref = {"group": "g", "ecosystem": "python", "package": "requests"}
    inputs = apply_rederive.DependencyBumpProviderInputs(
        finding_ref=finding_ref,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="g", ecosystem="python", package="requests",
            versions=(("acme/api", "1.0.0"), ("acme/other", "0.9.0")), distance="minor",
        ),
        target="1.0.0", selection=("acme/other",),
        records_by_repo={
            ("acme/other", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/other", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=0", locked_version="0.9.0", unresolved_reason=None,
                manager="uv", manifest_path="pyproject.toml", lock_path="uv.lock",
                tree_sha="tree-other", provenance=(),
            ),
        },
        head_shas={"acme/other": "c" * 40}, tree_shas={"acme/other": "tree-other"},
        default_branches={"acme/other": "main"}, blocked={},
        actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: inputs)
    monkeypatch.setattr(apply_driver, "run_apply", lambda **kwargs: {"state": "blocked"})
    result = apply_driver.run_apply_dependency_bump(
        finding_ref=finding_ref, authorization_path="/x", ledger_path=str(tmp_path / "l.yaml"),
        step_id="s", actor_id="octocat@laptop", runner=SimpleNamespace(run=lambda a: None),
        gh_api=lambda ep: None, gh_ops=SimpleNamespace(), result_path=str(tmp_path / "r.yaml"),
        workspace=str(tmp_path),
    )
    assert result["state"] == "failed"  # rollup_state: all-{failed,blocked} -> "failed"


def test_run_apply_dependency_bump_one_proposal_pen_failure_does_not_block_the_other(monkeypatch, tmp_path):
    """A pen-create (or any other) failure inside ONE manager group's
    run_apply call is now entirely internal to that call's own result —
    there is no shared pre-loop pen-create step left to fail the whole
    finding (spec § 4.7: pen creation is per-proposal, never shared).
    The other manager group's run_apply call is independent and must
    still be able to succeed; rollup_state's 'any pr_opened wins' rule
    surfaces the still-progressing proposal at the top level while
    `result['proposals']` keeps the failing one's own reason visible."""
    finding_ref = {"group": "core-runtime", "ecosystem": "python", "package": "requests"}
    inputs = apply_rederive.DependencyBumpProviderInputs(
        finding_ref=finding_ref,
        finding=apply_rederive.deps_module.DivergenceFinding(
            group="core-runtime", ecosystem="python", package="requests",
            versions=(("acme/api", "2.28.0"), ("acme/other", "2.20.0")), distance="minor",
        ),
        target="2.31.0", selection=("acme/api", "acme/other"),
        records_by_repo={
            ("acme/api", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/api", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=2", locked_version="2.28.0", unresolved_reason=None,
                manager="uv", manifest_path="pyproject.toml", lock_path="uv.lock",
                tree_sha="tree-api", provenance=(),
            ),
            ("acme/other", "python", "requests"): apply_rederive.deps_module.PackageRecord(
                repo="acme/other", ecosystem="python", name="requests", resolution="single",
                manifest_range=">=2", locked_version="2.20.0", unresolved_reason=None,
                manager="poetry", manifest_path="pyproject.toml", lock_path="poetry.lock",
                tree_sha="tree-other", provenance=(),
            ),
        },
        head_shas={"acme/api": "a" * 40, "acme/other": "c" * 40},
        tree_shas={"acme/api": "tree-api", "acme/other": "tree-other"},
        default_branches={"acme/api": "main", "acme/other": "main"},
        blocked={}, actor=mutation_plan.Actor("octocat", "laptop", "interactive"), registry=None,
    )
    monkeypatch.setattr(apply_driver.apply_rederive, "collect_inputs", lambda *a, **k: inputs)

    def fake_run_apply(**kwargs):
        manager = apply_rederive._manager_for(kwargs["rederived_override"].proposal.transformation)
        if manager == "poetry":
            return {"state": "blocked", "reason": "pen create failed: fleet cache empty"}
        return {"state": "pr_opened"}

    monkeypatch.setattr(apply_driver, "run_apply", fake_run_apply)
    result = apply_driver.run_apply_dependency_bump(
        finding_ref=finding_ref, authorization_path="/x", ledger_path=str(tmp_path / "l.yaml"),
        step_id="s", actor_id="octocat@laptop", runner=SimpleNamespace(run=lambda a: None),
        gh_api=lambda ep: None, gh_ops=SimpleNamespace(), result_path=str(tmp_path / "r.yaml"),
        workspace=str(tmp_path),
    )
    assert result["state"] == "pr_opened"  # the uv proposal still progressed
    states = {pid: r["state"] for pid, r in result["proposals"].items()}
    assert "blocked" in states.values() and "pr_opened" in states.values()
    blocked_reasons = [r["reason"] for r in result["proposals"].values() if r["state"] == "blocked"]
    assert blocked_reasons == ["pen create failed: fleet cache empty"]


# --- CLI: --finding-ref -------------------------------------------------------


def test_main_requires_finding_ref_for_dependency_bump_source_kind(capsys):
    with pytest.raises(SystemExit):
        apply_driver.main([
            "--source-kind", "dependency-bump", "--authorization", "/x", "--ledger", "/x",
            "--step", "s", "--actor", "octocat@laptop", "--result", "/x", "--workspace", "/x",
        ])
    assert "--finding-ref" in capsys.readouterr().err


def test_main_dispatches_to_run_apply_dependency_bump(monkeypatch, tmp_path, capsys):
    captured = {}
    monkeypatch.setattr(
        apply_driver, "run_apply_dependency_bump",
        lambda **kwargs: captured.update(kwargs) or {"state": "pr_opened", "proposals": {}},
    )
    apply_driver.main([
        "--source-kind", "dependency-bump",
        "--finding-ref", json.dumps({"group": "g", "ecosystem": "python", "package": "requests"}),
        "--authorization", "/x", "--ledger", "/x", "--step", "s", "--actor", "octocat@laptop",
        "--result", "/x", "--workspace", "/x",
    ])
    assert captured["finding_ref"] == {"group": "g", "ecosystem": "python", "package": "requests"}
    assert json.loads(capsys.readouterr().out)["state"] == "pr_opened"
