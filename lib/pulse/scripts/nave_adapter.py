#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Run Nave as an external CLI and expose a stable Pulse adapter surface."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


CURRENT_PROTOCOL = 1
CURRENT_CAPABILITIES = {
    "scan",
    "pull",
    "search_json",
    "build_json",
    "check_json",
    "pen",
}


@dataclass(frozen=True)
class Completed:
    """Process result independent of subprocess' concrete result type."""

    returncode: int
    stdout: str
    stderr: str
    state: str = "ok"


def _fixture_output_path(root: Path, args: Sequence[str]) -> Path:
    if list(args) == ["--version"]:
        return root / "probe" / "version.txt"
    if list(args) == ["--help"]:
        return root / "probe" / "help.txt"
    if args and args[-1] == "--help":
        command = "-".join(args[:-1])
        return root / "probe" / f"{command}-help.txt"
    if args and "--json" in args:
        return root / f"{args[0]}.json"
    if args:
        return root / f"{args[0]}.txt"
    return root / "empty.txt"


def load_fixture(root: Path, args: Sequence[str]) -> Completed:
    """Load stdout plus optional sibling .stderr and .exit fixture records."""
    output_path = _fixture_output_path(root, args)
    stderr_path = output_path.with_suffix(".stderr")
    exit_path = output_path.with_suffix(".exit")
    if not output_path.exists() and not exit_path.exists():
        return Completed(
            2,
            "",
            f"fixture not found for command: {' '.join(args)}",
            "error",
        )
    try:
        stdout = output_path.read_text() if output_path.exists() else ""
        stderr = stderr_path.read_text() if stderr_path.exists() else ""
        returncode = int(exit_path.read_text().strip()) if exit_path.exists() else 0
    except (OSError, UnicodeError, ValueError) as exc:
        return Completed(2, "", f"invalid fixture record: {exc}", "error")
    return Completed(
        returncode,
        stdout,
        stderr,
        "ok" if returncode == 0 else "error",
    )


class NaveRunner:
    """Safe subprocess boundary with an offline fixture replacement."""

    def __init__(
        self,
        binary: str = "nave",
        fixtures: str | Path | None = None,
        timeout: int = 120,
    ) -> None:
        self.binary = binary
        self.fixtures = Path(fixtures) if fixtures is not None else None
        self.timeout = timeout

    def run(self, args: list[str]) -> Completed:
        if self.fixtures is not None:
            return load_fixture(self.fixtures, args)
        try:
            process = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
        except FileNotFoundError:
            return Completed(
                127,
                "",
                f"binary not found: {self.binary}",
                "unavailable",
            )
        except subprocess.TimeoutExpired:
            return Completed(
                124,
                "",
                f"timeout after {self.timeout}s",
                "error",
            )
        except OSError as exc:
            return Completed(126, "", f"could not execute {self.binary}: {exc}", "error")
        return Completed(
            process.returncode,
            process.stdout,
            process.stderr,
            "ok" if process.returncode == 0 else "error",
        )


def _listed(help_text: str, command: str) -> bool:
    return bool(re.search(rf"^\s{{0,8}}{re.escape(command)}(?:\s|$)", help_text, re.MULTILINE))


def _help_has(runner: NaveRunner, args: list[str], option: str) -> tuple[bool, str | None]:
    result = runner.run([*args, "--help"])
    if result.returncode != 0:
        return False, result.stderr.strip() or f"could not probe {' '.join(args)}"
    return option in result.stdout, None


def probe(runner: NaveRunner) -> dict:
    """Probe the installed CLI without relying on Nave implementation internals."""
    version_result = runner.run(["--version"])
    if version_result.returncode == 127 or version_result.state == "unavailable":
        return {
            "available": False,
            "state": "unavailable",
            "version": None,
            "protocol": None,
            "capabilities": [],
            "errors": [version_result.stderr.strip()],
        }

    errors: list[str] = []
    if version_result.returncode != 0:
        errors.append(version_result.stderr.strip() or "nave --version failed")
    version_match = re.search(r"\bnave\s+([^\s]+)", version_result.stdout)
    version = version_match.group(1) if version_match else None
    if version is None:
        errors.append("could not parse nave version")

    help_result = runner.run(["--help"])
    if help_result.returncode != 0:
        errors.append(help_result.stderr.strip() or "nave --help failed")
    help_text = help_result.stdout if help_result.returncode == 0 else ""
    capabilities: set[str] = set()

    for command in ("scan", "pull"):
        if _listed(help_text, command):
            capabilities.add(command)

    for command in ("search", "build", "check"):
        if not _listed(help_text, command):
            continue
        has_json, error = _help_has(runner, [command], "--json")
        if error:
            errors.append(error)
        if has_json:
            capabilities.add(f"{command}_json")

    if _listed(help_text, "pen"):
        pen_help = runner.run(["pen", "--help"])
        if pen_help.returncode != 0:
            errors.append(pen_help.stderr.strip() or "could not probe pen")
        else:
            pen_json = True
            for action in ("list", "show", "status"):
                if not _listed(pen_help.stdout, action):
                    pen_json = False
                    break
                has_json, error = _help_has(runner, ["pen", action], "--json")
                if error:
                    errors.append(error)
                pen_json = pen_json and has_json
            if pen_json:
                capabilities.add("pen")

    protocol = CURRENT_PROTOCOL if CURRENT_CAPABILITIES <= capabilities else None
    return {
        "available": True,
        "state": "available" if protocol is not None and not errors else "degraded",
        "version": version,
        "protocol": protocol,
        "capabilities": sorted(capabilities),
        "errors": errors,
    }


def _runner_from_args(args: argparse.Namespace) -> NaveRunner:
    fixtures = os.environ.get("PULSE_NAVE_FIXTURES")
    return NaveRunner(binary=args.binary, fixtures=fixtures, timeout=args.timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--binary", default="nave")
    probe_parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)

    if args.command == "probe":
        print(json.dumps(probe(_runner_from_args(args)), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
