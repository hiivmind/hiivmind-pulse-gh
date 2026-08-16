from types import SimpleNamespace

from lib.pulse.scripts import apply_phases, mutation_plan


REPOS = ("acme/api", "acme/web")


def proposal():
    return mutation_plan.build_proposal(
        id="run-1", selection=list(REPOS), transformation="format-python",
        expected_shas={repo: "abc" for repo in REPOS},
        actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
        mutation_policy="allow-listed", bound_paths={repo: ("src/**",) for repo in REPOS},
    )


def entry():
    return mutation_plan.load_registry({"transformations": {"format-python": {
        "id": "format-python", "command_argv": ["ruff", "format", "."],
        "applies_to": ["always"], "validation": {"kind": "none"}, "allow_scheduled": True,
    }}}).get("format-python")


def status(repo="web", **changes):
    item = {"owner": "acme", "repo": repo, "working_tree": "clean", "freshness": "fresh", "divergence": "up-to-date"}
    item.update(changes)
    return item


def test_preflight_blocks_dirty_stale_mismatch_and_missing_clone(monkeypatch):
    monkeypatch.setattr(apply_phases.nave_adapter, "pen_status", lambda *_: {"repos": [status("api", working_tree="dirty"), status(freshness="stale", divergence="behind")]})
    result = apply_phases.preflight_phase(None, {"name": "p", "repos": [{"repo": "acme/api"}]}, proposal(), {"acme/api": "/tmp/a"})
    assert all(item["state"] == "blocked" for item in result.values())
    assert "missing clone_path" in result["acme/web"]["reason"]


def test_exec_blocks_missing_tool_before_exec(monkeypatch):
    monkeypatch.setattr(apply_phases.executor_probe, "probe_required_tool", lambda *_: {"state": "blocked", "reason": "required tool 'ruff' for ecosystem 'python' is absent"})
    monkeypatch.setattr(apply_phases.nave_adapter, "pen_exec", lambda *_args, **_kw: (_ for _ in ()).throw(AssertionError("called")))
    result = apply_phases.exec_phase(None, {"name": "p", "repos": [{"repo": repo} for repo in REPOS]}, entry())
    assert all(item["state"] == "blocked" for item in result.values())


def entry_with_params():
    return mutation_plan.load_registry({"transformations": {"bump-python-uv": {
        "id": "bump-python-uv", "command_argv": ["uv", "add", "{package}=={version}"],
        "applies_to": ["always"], "validation": {"kind": "none"}, "allow_scheduled": False,
        "params": ["package", "version"],
    }}}).get("bump-python-uv")


def test_exec_passes_transform_params_to_resolve_argv(monkeypatch):
    captured = {}

    def fake_pen_exec(runner, pen_name, argv, **kwargs):
        captured["argv"] = argv
        return {"adapter_state": "ok"}

    monkeypatch.setattr(apply_phases.nave_adapter, "pen_exec", fake_pen_exec)
    monkeypatch.setattr(apply_phases.executor_probe, "probe_required_tool", lambda *_: {"state": "ok"})
    pen = {"name": "pen", "repos": [{"repo": "acme/api"}]}
    result = apply_phases.exec_phase(
        None, pen, entry_with_params(), transform_params={"package": "requests", "version": "2.32.0"}
    )
    assert captured["argv"] == ["uv", "add", "requests==2.32.0"]
    assert result["acme/api"]["state"] == "ok"


def test_exec_none_transform_params_uses_verbatim_argv_backward_compat(monkeypatch):
    captured = {}

    def fake_pen_exec(runner, pen_name, argv, **kwargs):
        captured["argv"] = argv
        return {"adapter_state": "ok"}

    monkeypatch.setattr(apply_phases.nave_adapter, "pen_exec", fake_pen_exec)
    monkeypatch.setattr(apply_phases.executor_probe, "probe_required_tool", lambda *_: {"state": "ok"})
    pen = {"name": "pen", "repos": [{"repo": "acme/api"}]}
    apply_phases.exec_phase(None, pen, entry())
    assert captured["argv"] == ["ruff", "format", "."]


class Ops:
    def __init__(self, result): self.result, self.calls = result, []
    def provision_branch(self, branch, bases): self.calls.append((branch, bases)); return self.result
    def commit_repos(self, message, bound_paths): self.calls.append((message, bound_paths)); return self.result
    def push_repos(self, branch): self.calls.append(branch); return self.result
    def reset_repos(self, branch, shas): self.calls.append((branch, shas)); return {}


def test_commit_phase_passes_expanded_bound_paths():
    ops = Ops({"acme/api": {"state": "ok", "local_commit_sha": "c1"}, "acme/web": {"state": "ok", "local_commit_sha": "c2"}})
    result = apply_phases.commit_phase(
        ops, proposal(), "msg",
        bound_paths={"acme/api": ("src/a.py", "src/b.py"), "acme/web": ("src/c.py",)},
    )
    assert result["acme/api"]["state"] == "ok"
    message, passed = ops.calls[0]
    assert message == "msg"
    assert passed == {"acme/api": ("src/a.py", "src/b.py"), "acme/web": ("src/c.py",)}


def test_commit_phase_defaults_to_proposal_bound_paths():
    ops = Ops({"acme/api": {"state": "ok", "local_commit_sha": "c1"}, "acme/web": {"state": "ok", "local_commit_sha": "c2"}})
    apply_phases.commit_phase(ops, proposal(), "msg")
    message, passed = ops.calls[0]
    assert passed == proposal().bound_paths


def provision_item(repo, **changes):
    item = {
        "state": "ok", "base_ref": "refs/heads/main", "expected_base_sha": "abc",
        "apply_ref": "pulse/apply/run-1", "observed_base_sha": "abc",
        "observed_tree_sha": "tree-abc",
    }
    item.update(changes)
    return item


def test_provision_blocks_drift_and_echo_mismatch():
    ops = Ops({"acme/api": provision_item("acme/api", observed_base_sha="old"), "acme/web": provision_item("acme/web", apply_ref="wrong")})
    result = apply_phases.provision_phase(None, None, ops, proposal(), "pulse/apply/run-1", {repo: "refs/heads/main" for repo in REPOS})
    assert "stale-base" in result["acme/api"]["reason"]
    assert "apply_ref" in result["acme/web"]["reason"]


def proposal_with_tree_shas(**tree_shas):
    return mutation_plan.build_proposal(
        id="run-1", selection=list(REPOS), transformation="format-python",
        expected_shas={repo: "abc" for repo in REPOS},
        actor={"gh_login": "octocat", "machine": "laptop", "mode": "interactive"},
        mutation_policy="allow-listed", bound_paths={repo: ("src/**",) for repo in REPOS},
        expected_tree_shas=tree_shas or {repo: "tree-abc" for repo in REPOS},
    )


def test_provision_blocks_stale_tree_when_commit_matches_but_tree_drifted():
    ops = Ops({
        "acme/api": provision_item("acme/api", observed_tree_sha="tree-DIFFERENT"),
        "acme/web": provision_item("acme/web", observed_tree_sha="tree-abc"),
    })
    result = apply_phases.provision_phase(
        None, None, ops, proposal_with_tree_shas(), "pulse/apply/run-1",
        {repo: "refs/heads/main" for repo in REPOS},
    )
    assert "stale-tree" in result["acme/api"]["reason"]
    assert result["acme/web"]["state"] == "ok"


def test_provision_reports_stale_base_not_stale_tree_when_both_drift():
    """Commit-level drift takes precedence in the reported reason — the
    operator sees the more actionable stale-base diagnosis first."""
    ops = Ops({
        "acme/api": provision_item("acme/api", observed_base_sha="old", observed_tree_sha="tree-DIFFERENT"),
        "acme/web": provision_item("acme/web", observed_tree_sha="tree-abc"),
    })
    result = apply_phases.provision_phase(
        None, None, ops, proposal_with_tree_shas(), "pulse/apply/run-1",
        {repo: "refs/heads/main" for repo in REPOS},
    )
    assert "stale-base" in result["acme/api"]["reason"]
    assert "stale-tree" not in result["acme/api"]["reason"]


def test_provision_ignores_tree_sha_when_expected_tree_shas_is_none():
    """Every non-dependency-bump proposal (expected_tree_shas=None) is
    unaffected even if the fake provision result's observed_tree_sha
    doesn't match anything — the elif is never reached."""
    ops = Ops({
        "acme/api": provision_item("acme/api", observed_tree_sha="whatever"),
        "acme/web": provision_item("acme/web", observed_tree_sha="anything"),
    })
    result = apply_phases.provision_phase(
        None, None, ops, proposal(), "pulse/apply/run-1",
        {repo: "refs/heads/main" for repo in REPOS},
    )
    assert result["acme/api"]["state"] == "ok"
    assert result["acme/web"]["state"] == "ok"


def test_push_checks_head_before_push_and_validates_remote_evidence():
    ops = Ops({})
    reader = SimpleNamespace(read_repo_head=lambda _repo: "wrong")
    result = apply_phases.push_phase(ops, reader, "pulse/apply/run-1", {"acme/api": "abc"})
    assert result["acme/api"]["state"] == "failed" and ops.calls == []

    ops = Ops({"acme/api": {"state": "ok", "remote_sha": "wrong", "remote_ref": "wrong"}})
    reader = SimpleNamespace(read_repo_head=lambda _repo: "abc")
    result = apply_phases.push_phase(ops, reader, "pulse/apply/run-1", {"acme/api": "abc"})
    assert result["acme/api"]["state"] == "failed"


def test_cleanup_passes_confirmed_and_local_only_shas():
    ops = Ops({})
    apply_phases.cleanup(ops, "pulse/apply/run-1", {"acme/api": "abc", "acme/web": None})
    assert ops.calls == [("pulse/apply/run-1", {"acme/api": "abc", "acme/web": None})]


def test_preflight_blocks_on_empty_clone_path_value(monkeypatch):
    monkeypatch.setattr(apply_phases.nave_adapter, "pen_status", lambda *_: {"repos": [status("api"), status("web")]})
    result = apply_phases.preflight_phase(
        None,
        {"name": "p", "repos": [{"owner": "acme", "name": "api"}, {"owner": "acme", "name": "web"}]},
        proposal(),
        {"acme/api": None, "acme/web": ""},
    )
    assert "missing clone_path" in result["acme/api"]["reason"]
    assert "missing clone_path" in result["acme/web"]["reason"]


def test_provision_blocks_when_expected_base_ref_missing():
    ops = Ops({"acme/api": provision_item("acme/api"), "acme/web": provision_item("acme/web")})
    result = apply_phases.provision_phase(
        None, None, ops, proposal(), "pulse/apply/run-1", {"acme/api": "refs/heads/main"}
    )
    assert result["acme/api"]["state"] == "ok"
    assert result["acme/web"]["state"] == "blocked"
    assert "base_ref" in result["acme/web"]["reason"]
