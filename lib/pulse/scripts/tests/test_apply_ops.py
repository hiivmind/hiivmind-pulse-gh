import json
from pathlib import Path

from lib.pulse.scripts import apply_ops, nave_adapter


class RecordingRunner:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def run(self, args):
        request = json.loads(Path(args[args.index("--request") + 1]).read_text())
        self.calls.append((list(args), request))
        return nave_adapter.Completed(0, json.dumps(self.responses.pop(0)), "")


def response(repo, state="ok", **fields):
    return {"protocol_version": 1, "adapter_state": "ok", "repos": [{"repo": repo, "state": state, **fields}]}


def test_make_apply_ops_builds_all_apply_verb_requests():
    repo, branch = "acme/api", "pulse/apply/run-1"
    runner = RecordingRunner([
        response(repo, base_ref="refs/heads/main", expected_base_sha="abc", apply_ref=branch, observed_base_sha="abc", observed_tree_sha="tree-abc"),
        response(repo, local_commit_sha="def"),
        response(repo, remote_ref=branch, remote_sha="def", upstream=f"origin/{branch}"),
        response(repo, local_reset=True, remote_deleted=False),
    ])
    ops = apply_ops.make_apply_ops(runner, "pen", {repo: ("src/**",)}, {repo: "refs/heads/main"})
    assert ops.provision_branch(branch, {repo: "abc"})["repos"][0]["state"] == "ok"
    assert ops.commit_repos("message", {repo: ("src/**",)})["repos"][0]["local_commit_sha"] == "def"
    assert ops.push_repos(branch)["repos"][0]["remote_sha"] == "def"
    assert ops.reset_repos(branch, {repo: None})["repos"][0]["state"] == "ok"
    assert runner.calls[0][1]["repos"] == [{"repo": repo, "base_ref": "refs/heads/main", "expected_base_sha": "abc"}]
    assert runner.calls[1][1]["repos"] == [{"repo": repo, "paths": ["src/**"]}]
    assert runner.calls[2][1]["repos"] == [{"repo": repo}]
    assert runner.calls[3][1]["repos"] == [{"repo": repo, "expected_pushed_sha": None}]
