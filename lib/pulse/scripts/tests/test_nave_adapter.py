"""Tests for the external Nave CLI adapter."""

import json
from pathlib import Path

from lib.pulse.scripts import nave_adapter


FIXTURES = Path("lib/pulse/scripts/tests/fixtures/nave")


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
