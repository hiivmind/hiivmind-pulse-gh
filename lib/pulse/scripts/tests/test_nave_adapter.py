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
    assert output["contract_version"] == 1
