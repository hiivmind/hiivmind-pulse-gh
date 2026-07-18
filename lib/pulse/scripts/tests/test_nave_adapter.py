"""Tests for the external Nave CLI adapter."""

import json
from pathlib import Path

from lib.pulse.scripts import nave_adapter


FIXTURES = Path("lib/pulse/scripts/tests/fixtures/nave")


class RecordingRunner:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or nave_adapter.Completed(0, "{}", "")

    def run(self, args):
        self.calls.append(args)
        return self.result


class QueuedRunner:
    """Fake runner that returns a distinct Completed per call, in order."""

    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def run(self, args):
        self.calls.append(args)
        return self._results.pop(0)


def test_probe_detects_current_capabilities():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES)
    result = nave_adapter.probe(runner)

    assert result["available"] is True
    assert result["version"] == "0.0.8"
    assert result["protocol"] == 1
    assert {
        "scan",
        "pull",
        "search_json",
        "build_json",
        "check_json",
        "pen",
    } <= set(result["capabilities"])


def test_probe_missing_binary_is_unavailable():
    result = nave_adapter.probe(
        nave_adapter.NaveRunner(binary="definitely-no-nave")
    )

    assert result["available"] is False
    assert result["state"] == "unavailable"
    assert result["protocol"] is None


def test_probe_does_not_infer_json_from_command_name(tmp_path):
    probe_dir = tmp_path / "probe"
    probe_dir.mkdir()
    (probe_dir / "version.txt").write_text("nave 0.0.8\n")
    (probe_dir / "help.txt").write_text("Commands:\n  search\n")
    (probe_dir / "search-help.txt").write_text("Usage: nave search [TERMS]...\n")

    result = nave_adapter.probe(nave_adapter.NaveRunner(fixtures=tmp_path))

    assert "search_json" not in result["capabilities"]
    assert result["state"] == "degraded"


def test_fixture_mode_can_be_selected_by_environment(monkeypatch, capsys):
    monkeypatch.setenv("PULSE_NAVE_FIXTURES", str(FIXTURES))

    assert nave_adapter.main(["probe"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["available"] is True


def test_probe_cli_accepts_binary_after_subcommand(monkeypatch, capsys):
    monkeypatch.setenv("PULSE_NAVE_FIXTURES", str(FIXTURES))

    assert nave_adapter.main(["probe", "--binary", "/opt/nave"]) == 0
    assert json.loads(capsys.readouterr().out)["available"] is True


def test_runner_timeout_is_typed(monkeypatch):
    def timeout(*args, **kwargs):
        raise nave_adapter.subprocess.TimeoutExpired(args[0], 3)

    monkeypatch.setattr(nave_adapter.subprocess, "run", timeout)
    result = nave_adapter.NaveRunner(timeout=3).run(["--version"])

    assert result.returncode == 124
    assert result.state == "error"
    assert "timeout after 3s" in result.stderr


def test_scan_never_adds_nonexistent_json_flag():
    runner = RecordingRunner()

    result = nave_adapter.scan(
        runner, user="acme", no_interaction=True, prune=True
    )

    assert runner.calls == [
        ["scan", "--user", "acme", "--no-interaction", "--prune"]
    ]
    assert result.state == "success"


def test_pull_is_lifecycle_only():
    runner = RecordingRunner(nave_adapter.Completed(1, "human table", "failed"))

    result = nave_adapter.pull(runner)

    assert runner.calls == [["pull"]]
    assert result.state == "error"
    assert result.stderr == "failed"


def test_search_requires_json():
    runner = RecordingRunner()

    nave_adapter.search(runner, ["workflow:pytest"])

    assert runner.calls == [["search", "--json", "workflow:pytest"]]


def test_analysis_commands_build_exact_argument_arrays():
    runner = RecordingRunner()

    nave_adapter.search(runner, ["pytest"], matches=["tool.pytest"])
    nave_adapter.build(
        runner,
        "pyproject.toml",
        where=["pytest"],
        matches=["tool.pytest"],
    )
    nave_adapter.check(runner)

    assert runner.calls == [
        ["search", "--json", "pytest", "--match", "tool.pytest"],
        [
            "build",
            "--json",
            "--filter",
            "pyproject.toml",
            "--where",
            "pytest",
            "--match",
            "tool.pytest",
        ],
        ["check", "--json"],
    ]


def test_fixture_analysis_commands_decode_json():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES)

    assert nave_adapter.search(runner, ["anything"])["repos"][0]["repo"] == "api"
    assert nave_adapter.build(runner, None)["groups"][0]["pattern"] == "pyproject.toml"
    assert nave_adapter.check(runner)["totals"]["ok"] == 3


def test_invalid_json_becomes_typed_adapter_error():
    runner = RecordingRunner(nave_adapter.Completed(0, "not json", ""))

    result = nave_adapter.search(runner, ["anything"])

    assert result["adapter_state"] == "error"
    assert result["returncode"] == 0
    assert "invalid JSON" in result["error"]


def test_cli_exposes_fixture_backed_lifecycle_and_analysis(monkeypatch, capsys):
    monkeypatch.setenv("PULSE_NAVE_FIXTURES", str(FIXTURES))

    assert nave_adapter.main(
        ["scan", "--user", "acme", "--no-interaction", "--prune"]
    ) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "success"
    assert nave_adapter.main(["pull"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "success"
    assert nave_adapter.main(["search", "--term", "anything"]) == 0
    assert json.loads(capsys.readouterr().out)["repos"][0]["repo"] == "api"
    assert nave_adapter.main(["build", "--filter", "pyproject.toml"]) == 0
    assert json.loads(capsys.readouterr().out)["groups"]
    assert nave_adapter.main(["check"]) == 0
    assert json.loads(capsys.readouterr().out)["totals"]["ok"] == 3


def _write_v1_probe_dir(base):
    probe_dir = base / "probe"
    probe_dir.mkdir()
    (probe_dir / "version.txt").write_text("nave 0.0.8\n")
    (probe_dir / "help.txt").write_text(
        "Commands:\n"
        "  scan\n"
        "  pull\n"
        "  search\n"
        "  build\n"
        "  check\n"
        "  pen\n"
    )
    for command in ("search", "build", "check"):
        (probe_dir / f"{command}-help.txt").write_text("Options:\n  --json\n")
    (probe_dir / "pen-help.txt").write_text("Commands:\n  list\n  show\n  status\n")
    for action in ("list", "show", "status"):
        (probe_dir / f"pen-{action}-help.txt").write_text("Options:\n  --json\n")
    return probe_dir


def test_v1_fixture_without_materialize_stays_protocol_one(tmp_path):
    _write_v1_probe_dir(tmp_path)

    result = nave_adapter.probe(nave_adapter.NaveRunner(fixtures=tmp_path))

    assert result["available"] is True
    assert result["protocol"] == 1
    assert "materialize_json" not in result["capabilities"]


def test_v2_fixture_with_materialize_is_protocol_two(tmp_path):
    probe_dir = _write_v1_probe_dir(tmp_path)
    help_path = probe_dir / "help.txt"
    help_path.write_text(help_path.read_text() + "  materialize\n")
    (probe_dir / "materialize-help.txt").write_text(
        "Options:\n  --request <PATH>\n  --json\n"
    )

    result = nave_adapter.probe(nave_adapter.NaveRunner(fixtures=tmp_path))

    assert result["protocol"] == 2
    assert "materialize_json" in result["capabilities"]


def test_materialize_listed_without_json_stays_protocol_one(tmp_path):
    probe_dir = _write_v1_probe_dir(tmp_path)
    help_path = probe_dir / "help.txt"
    help_path.write_text(help_path.read_text() + "  materialize\n")
    (probe_dir / "materialize-help.txt").write_text("Options:\n  --request <PATH>\n")

    result = nave_adapter.probe(nave_adapter.NaveRunner(fixtures=tmp_path))

    assert result["protocol"] == 1
    assert "materialize_json" not in result["capabilities"]


def test_materialize_requires_request_flag_argument():
    runner = RecordingRunner()

    nave_adapter.materialize(runner, "/tmp/request.json")

    assert runner.calls == [
        ["materialize", "--request", "/tmp/request.json", "--json"]
    ]


def test_fixture_materialize_decodes_json():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES)

    result = nave_adapter.materialize(runner, "anything")

    assert result["contract_version"] == 1
    assert result["repos"][0]["artifacts"][0]["state"] == "found"


def test_materialize_invalid_json_becomes_typed_adapter_error():
    runner = RecordingRunner(nave_adapter.Completed(0, "not json", ""))

    result = nave_adapter.materialize(runner, "anything")

    assert result["adapter_state"] == "error"
    assert result["returncode"] == 0
    assert "invalid JSON" in result["error"]


def test_materialize_timeout_is_typed_adapter_error():
    runner = RecordingRunner(
        nave_adapter.Completed(124, "", "timeout after 3s", "error")
    )

    result = nave_adapter.materialize(runner, "anything")

    assert result["adapter_state"] == "error"
    assert result["returncode"] == 124


def test_materialize_nonzero_exit_becomes_typed_adapter_error():
    runner = RecordingRunner(
        nave_adapter.Completed(1, "not json either", "boom", "error")
    )

    result = nave_adapter.materialize(runner, "anything")

    assert result["adapter_state"] == "error"
    assert result["returncode"] == 1
    assert result["stderr"] == "boom"


def test_cli_materialize_subcommand_uses_request_flag(monkeypatch, capsys):
    monkeypatch.setenv("PULSE_NAVE_FIXTURES", str(FIXTURES))

    assert nave_adapter.main(["materialize", "--request", "anything"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["repos"][0]["repo"] == "acme/api"
    assert output["repos"][0]["artifacts_by_state"] == {"found": 1}


def test_cli_materialize_subcommand_does_not_leak_content(monkeypatch, capsys):
    monkeypatch.setenv("PULSE_NAVE_FIXTURES", str(FIXTURES))

    exit_code = nave_adapter.main(["materialize", "--request", "anything"])
    raw_stdout = capsys.readouterr().out

    assert exit_code == 0
    # The fixture's found artifact contains this pyproject snippet in its
    # decoded `content` field; it must never reach CLI stdout.
    assert "[tool.pytest.ini_options]" not in raw_stdout

    output = json.loads(raw_stdout)
    assert "content" not in output["repos"][0]["artifacts_by_state"]
    for repo in output["repos"]:
        assert "artifacts" not in repo
    assert output["repos"][0]["artifacts_by_state"]["found"] >= 1


# --- pen lifecycle ---

PEN_FIXTURES = FIXTURES / "pen"


def test_pen_show_builds_exact_command_with_name():
    runner = RecordingRunner(nave_adapter.Completed(0, "{}", ""))

    nave_adapter.pen_show(runner, name="nave/api-audit")

    assert runner.calls == [["pen", "show", "nave/api-audit", "--json"]]


def test_pen_show_builds_exact_command_with_filter_only():
    runner = RecordingRunner(nave_adapter.Completed(0, "{}", ""))

    nave_adapter.pen_show(runner, filter_regex="api.*")

    assert runner.calls == [["pen", "show", "--filter", "api.*", "--json"]]


def test_pen_status_builds_exact_command_and_normalizes_array_root():
    status_json = json.dumps(
        [
            {
                "owner": "acme",
                "repo": "api",
                "working_tree": "clean",
                "freshness": "fresh",
                "run_state": "not-run",
                "divergence": "up-to-date",
                "ahead": 0,
                "behind": 0,
            }
        ]
    )
    runner = RecordingRunner(nave_adapter.Completed(0, status_json, ""))

    result = nave_adapter.pen_status(runner, "nave/api-audit")

    assert runner.calls == [["pen", "status", "nave/api-audit", "--json"]]
    assert result == {
        "repos": [
            {
                "owner": "acme",
                "repo": "api",
                "working_tree": "clean",
                "freshness": "fresh",
                "run_state": "not-run",
                "divergence": "up-to-date",
                "ahead": 0,
                "behind": 0,
            }
        ]
    }


def test_pen_status_invalid_json_becomes_typed_adapter_error():
    runner = RecordingRunner(nave_adapter.Completed(0, "not json", ""))

    result = nave_adapter.pen_status(runner, "nave/api-audit")

    assert result["adapter_state"] == "error"
    assert "invalid JSON" in result["error"]


def test_pen_status_non_array_root_becomes_typed_adapter_error():
    runner = RecordingRunner(nave_adapter.Completed(0, "{}", ""))

    result = nave_adapter.pen_status(runner, "nave/api-audit")

    assert result["adapter_state"] == "error"
    assert "not an array" in result["error"]


def test_pen_create_builds_exact_command_then_calls_show():
    show_json = json.dumps({"name": "nave/api-audit", "branch": "nave/api-audit"})
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "nave/api-audit\n  acme/api\n", ""),
            nave_adapter.Completed(0, show_json, ""),
        ]
    )
    query = nave_adapter.PenQuery(
        terms=["workflow:pytest"], match_preds=["tool.pytest"], ignore_case=True
    )

    handle = nave_adapter.pen_create(runner, query, "nave/api-audit")

    assert runner.calls == [
        [
            "pen",
            "create",
            "--name",
            "nave/api-audit",
            "--ignore-case",
            "--match",
            "tool.pytest",
            "workflow:pytest",
        ],
        ["pen", "show", "nave/api-audit", "--json"],
    ]
    assert handle.name == "nave/api-audit"
    assert handle.state == "ok"
    assert handle.pen == {"name": "nave/api-audit", "branch": "nave/api-audit"}


def test_pen_create_never_parses_human_text_as_data():
    # The create command's stdout is deliberately gibberish/opaque; only the
    # exit code and the subsequent `pen show --json` call may inform state.
    show_json = json.dumps({"name": "nave/api-audit"})
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "not structured at all !!!", ""),
            nave_adapter.Completed(0, show_json, ""),
        ]
    )

    handle = nave_adapter.pen_create(runner, nave_adapter.PenQuery(), "nave/api-audit")

    assert handle.state == "ok"
    assert handle.pen == {"name": "nave/api-audit"}


def test_pen_create_nonzero_exit_skips_show_call():
    runner = QueuedRunner([nave_adapter.Completed(1, "", "boom")])

    handle = nave_adapter.pen_create(runner, nave_adapter.PenQuery(), "nave/api-audit")

    assert runner.calls == [
        ["pen", "create", "--name", "nave/api-audit"],
    ]
    assert handle.state == "error"
    assert handle.returncode == 1
    assert handle.stderr == "boom"
    assert handle.pen is None


def test_pen_exec_default_never_passes_push_or_commit_flags():
    status_json = "[]"
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "ok", ""),
            nave_adapter.Completed(0, status_json, ""),
        ]
    )

    result = nave_adapter.pen_exec(runner, "nave/api-audit", ["echo", "hi"])

    exec_call = runner.calls[0]
    assert "--push-changes" not in exec_call
    assert "--commit" not in exec_call
    assert exec_call == ["pen", "exec", "nave/api-audit", "--", "echo", "hi"]
    assert result["adapter_state"] == "ok"
    assert result["status"] == {"repos": []}


def test_pen_exec_explicit_commit_adds_only_commit_flag():
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "ok", ""),
            nave_adapter.Completed(0, "[]", ""),
        ]
    )

    nave_adapter.pen_exec(
        runner, "nave/api-audit", ["echo", "hi"], commit=True, message="update"
    )

    exec_call = runner.calls[0]
    assert "--commit" in exec_call
    assert "--push-changes" not in exec_call
    assert exec_call == [
        "pen",
        "exec",
        "nave/api-audit",
        "--commit",
        "-m",
        "update",
        "--",
        "echo",
        "hi",
    ]


def test_pen_exec_explicit_push_changes_adds_only_push_flag():
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "ok", ""),
            nave_adapter.Completed(0, "[]", ""),
        ]
    )

    nave_adapter.pen_exec(
        runner, "nave/api-audit", ["echo", "hi"], commit=True, push_changes=True
    )

    exec_call = runner.calls[0]
    # --push-changes already implies --commit on the real CLI; the adapter
    # must not also emit a redundant --commit flag.
    assert exec_call.count("--push-changes") == 1
    assert "--commit" not in exec_call


def test_pen_exec_supports_only_repo_filter():
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "ok", ""),
            nave_adapter.Completed(0, "[]", ""),
        ]
    )

    nave_adapter.pen_exec(runner, "nave/api-audit", ["echo", "hi"], only="acme/api")

    assert runner.calls[0] == [
        "pen",
        "exec",
        "nave/api-audit",
        "--only",
        "acme/api",
        "--",
        "echo",
        "hi",
    ]


def test_pen_exec_command_is_argv_not_shell_string():
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "ok", ""),
            nave_adapter.Completed(0, "[]", ""),
        ]
    )

    nave_adapter.pen_exec(runner, "nave/api-audit", ["git", "grep", "-l", "TODO"])

    exec_call = runner.calls[0]
    tail = exec_call[exec_call.index("--") + 1 :]
    assert tail == ["git", "grep", "-l", "TODO"]


def test_pen_exec_rejects_empty_command():
    runner = QueuedRunner([])

    try:
        nave_adapter.pen_exec(runner, "nave/api-audit", [])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty command")
    assert runner.calls == []


def test_pen_exec_calls_status_after_exec_for_verification():
    status_json = json.dumps(
        [
            {
                "owner": "acme",
                "repo": "api",
                "working_tree": "dirty",
                "freshness": "fresh",
                "run_state": "run-local",
                "divergence": "up-to-date",
                "ahead": 0,
                "behind": 0,
            }
        ]
    )
    runner = QueuedRunner(
        [
            nave_adapter.Completed(0, "did the thing", ""),
            nave_adapter.Completed(0, status_json, ""),
        ]
    )

    result = nave_adapter.pen_exec(runner, "nave/api-audit", ["make", "fmt"])

    assert runner.calls[1] == ["pen", "status", "nave/api-audit", "--json"]
    assert result["stdout"] == "did the thing"
    assert result["status"]["repos"][0]["run_state"] == "run-local"


def test_pen_exec_nonzero_exit_still_records_status_and_marks_error():
    runner = QueuedRunner(
        [
            nave_adapter.Completed(1, "", "command failed"),
            nave_adapter.Completed(0, "[]", ""),
        ]
    )

    result = nave_adapter.pen_exec(runner, "nave/api-audit", ["false"])

    assert result["adapter_state"] == "error"
    assert result["returncode"] == 1
    assert result["stderr"] == "command failed"
    assert result["status"] == {"repos": []}


def test_fixture_pen_show_decodes_faithful_json():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES)

    result = nave_adapter.pen_show(runner, name="nave/api-audit")

    assert result["name"] == "nave/api-audit"
    assert result["repos"][0]["owner"] == "acme"
    assert "content" not in result


def test_fixture_pen_status_decodes_faithful_json():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES)

    result = nave_adapter.pen_status(runner, "nave/api-audit")

    assert result["repos"][0]["owner"] == "acme"
    assert result["repos"][0]["working_tree"] in {"clean", "dirty", "missing"}


def test_fixture_pen_create_builds_handle_from_show():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES)

    handle = nave_adapter.pen_create(
        runner, nave_adapter.PenQuery(terms=["workflow:pytest"]), "nave/api-audit"
    )

    assert handle.state == "ok"
    assert handle.pen["name"] == "nave/api-audit"


def test_fixture_pen_exec_is_opaque_and_reports_status():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES)

    result = nave_adapter.pen_exec(runner, "nave/api-audit", ["make", "fmt"])

    assert result["adapter_state"] == "ok"
    assert result["status"]["repos"]


def test_cli_pen_show_and_status_use_fixtures(monkeypatch, capsys):
    monkeypatch.setenv("PULSE_NAVE_FIXTURES", str(FIXTURES))

    assert nave_adapter.main(["pen-show", "--name", "nave/api-audit"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "nave/api-audit"

    assert nave_adapter.main(["pen-status", "--name", "nave/api-audit"]) == 0
    assert json.loads(capsys.readouterr().out)["repos"][0]["owner"] == "acme"
