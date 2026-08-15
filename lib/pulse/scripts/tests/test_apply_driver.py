from pathlib import Path
from types import SimpleNamespace
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
