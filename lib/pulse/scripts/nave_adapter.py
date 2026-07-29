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
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


BASELINE_CAPABILITIES = {
    "scan",
    "pull",
    "search_json",
    "build_json",
    "check_json",
    "pen",
}
PROTOCOL_2_CAPABILITIES = BASELINE_CAPABILITIES | {"materialize_json"}


@dataclass(frozen=True)
class Completed:
    """Process result independent of subprocess' concrete result type."""

    returncode: int
    stdout: str
    stderr: str
    state: str = "ok"


@dataclass(frozen=True)
class LifecycleResult:
    """Exit-status-only result for Nave lifecycle commands."""

    state: str
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class PenQuery:
    """Fleet-filter query used to seed `nave pen create`.

    Mirrors `nave_pen::CreateOptions` (minus `name`, which is a required,
    separately-controlled argument on `pen_create` — see the F6 design
    decision to never let Nave derive a pen name we'd have to parse back out
    of opaque human text).
    """

    terms: Sequence[str] = ()
    match_preds: Sequence[str] = ()
    ignore_case: bool = False


@dataclass(frozen=True)
class PenHandle:
    """Normalized result of `pen_create`: exit status plus a resolved pen.

    `pen` is the normalized `pen show --json` payload (or the typed adapter
    error from that call) — never a parse of create's human-readable stdout.
    """

    name: str
    state: str
    returncode: int
    stdout: str
    stderr: str
    pen: dict | None


def _fixture_output_path(root: Path, args: Sequence[str]) -> Path:
    if list(args) == ["--version"]:
        return root / "probe" / "version.txt"
    if list(args) == ["--help"]:
        return root / "probe" / "help.txt"
    if args and args[-1] == "--help":
        command = "-".join(args[:-1])
        return root / "probe" / f"{command}-help.txt"
    if len(args) >= 2 and args[0] == "pen":
        # Every `pen` subcommand shares args[0]; disambiguate by action
        # (args[1]) into its own directory instead of colliding on
        # `pen.json`/`pen.txt`.
        action = args[1]
        if "--json" in args:
            return root / "pen" / f"{action}.json"
        return root / "pen" / f"{action}.txt"
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

    if _listed(help_text, "materialize"):
        has_request, request_error = _help_has(runner, ["materialize"], "--request")
        if request_error:
            errors.append(request_error)
        has_json, json_error = _help_has(runner, ["materialize"], "--json")
        if json_error:
            errors.append(json_error)
        if has_request and has_json:
            capabilities.add("materialize_json")

    if PROTOCOL_2_CAPABILITIES <= capabilities:
        protocol = 2
    elif BASELINE_CAPABILITIES <= capabilities:
        protocol = 1
    else:
        protocol = None
    return {
        "available": True,
        "state": "available" if protocol is not None and not errors else "degraded",
        "version": version,
        "protocol": protocol,
        "capabilities": sorted(capabilities),
        "errors": errors,
    }


def _lifecycle_result(completed: Completed) -> LifecycleResult:
    return LifecycleResult(
        state="success" if completed.returncode == 0 else "error",
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def scan(
    runner: NaveRunner,
    user: str | None = None,
    no_interaction: bool = False,
    prune: bool = False,
) -> LifecycleResult:
    """Refresh Nave's fleet inventory without assuming machine output."""
    args = ["scan"]
    if user is not None:
        args.extend(["--user", user])
    if no_interaction:
        args.append("--no-interaction")
    if prune:
        args.append("--prune")
    return _lifecycle_result(runner.run(args))


def pull(runner: NaveRunner) -> LifecycleResult:
    """Refresh Nave checkouts using exit status as the only protocol."""
    return _lifecycle_result(runner.run(["pull"]))


def _decode_json(command: str, completed: Completed) -> dict:
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "adapter_state": "error",
            "command": command,
            "returncode": completed.returncode,
            "error": f"invalid JSON from nave {command}: {exc.msg}",
            "stderr": completed.stderr,
        }
    if not isinstance(parsed, dict):
        return {
            "adapter_state": "error",
            "command": command,
            "returncode": completed.returncode,
            "error": f"invalid JSON from nave {command}: root is not an object",
            "stderr": completed.stderr,
        }
    return parsed


def search(
    runner: NaveRunner,
    terms: Sequence[str],
    matches: Sequence[str] = (),
) -> dict:
    """Run structural fleet search and require Nave's JSON protocol."""
    args = ["search", "--json", *terms]
    for predicate in matches:
        args.extend(["--match", predicate])
    return _decode_json("search", runner.run(args))


def build(
    runner: NaveRunner,
    file_filter: str | None,
    where: Sequence[str] = (),
    matches: Sequence[str] = (),
) -> dict:
    """Build structural fleet groups using Nave's JSON protocol."""
    args = ["build", "--json"]
    if file_filter is not None:
        args.extend(["--filter", file_filter])
    for term in where:
        args.extend(["--where", term])
    for predicate in matches:
        args.extend(["--match", predicate])
    return _decode_json("build", runner.run(args))


def check(runner: NaveRunner) -> dict:
    """Run round-trip validation and decode JSON even when checks fail."""
    return _decode_json("check", runner.run(["check", "--json"]))


def materialize(runner: NaveRunner, request: str) -> dict:
    """Materialize requested content using Nave's protocol-2 JSON contract."""
    args = ["materialize", "--request", request, "--json"]
    return _decode_json("materialize", runner.run(args))


def _decode_json_list(command: str, completed: Completed) -> dict:
    """Decode a JSON-array-rooted command, normalized into `{"repos": [...]}`.

    `pen status --json` serializes `Vec<RepoState>` — an array root, unlike
    every other adapter command's object root — so it needs its own decoder
    rather than reusing `_decode_json`.
    """
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "adapter_state": "error",
            "command": command,
            "returncode": completed.returncode,
            "error": f"invalid JSON from nave {command}: {exc.msg}",
            "stderr": completed.stderr,
        }
    if not isinstance(parsed, list):
        return {
            "adapter_state": "error",
            "command": command,
            "returncode": completed.returncode,
            "error": f"invalid JSON from nave {command}: root is not an array",
            "stderr": completed.stderr,
        }
    return {"repos": parsed}


def pen_show(
    runner: NaveRunner,
    name: str = "",
    filter_regex: str | None = None,
) -> dict:
    """Show a pen's normalized definition (`nave_pen::Pen` serialization)."""
    args = ["pen", "show"]
    if name:
        args.append(name)
    if filter_regex is not None:
        args.extend(["--filter", filter_regex])
    args.append("--json")
    return _decode_json("pen show", runner.run(args))


def pen_status(runner: NaveRunner, name: str) -> dict:
    """Per-repo pen state (`Vec<nave_pen::RepoState>`), normalized to a dict."""
    args = ["pen", "status", name, "--json"]
    return _decode_json_list("pen status", runner.run(args))


def pen_create(runner: NaveRunner, query: PenQuery, name: str) -> PenHandle:
    """Create a pen, then resolve it via `pen show --json`.

    `pen create` has no `--json` flag; its stdout is opaque text and is
    NEVER parsed for data — only its exit code is used. The caller must
    supply `name` explicitly (rather than letting Nave derive one from the
    first term) precisely so this function never needs to scrape a name back
    out of that opaque text to find the pen to show.
    """
    args = ["pen", "create", "--name", name]
    if query.ignore_case:
        args.append("--ignore-case")
    for predicate in query.match_preds:
        args.extend(["--match", predicate])
    args.extend(query.terms)

    create_result = runner.run(args)
    if create_result.returncode != 0:
        return PenHandle(
            name=name,
            state="error",
            returncode=create_result.returncode,
            stdout=create_result.stdout,
            stderr=create_result.stderr,
            pen=None,
        )

    show_result = pen_show(runner, name=name)
    state = "error" if show_result.get("adapter_state") == "error" else "ok"
    return PenHandle(
        name=name,
        state=state,
        returncode=create_result.returncode,
        stdout=create_result.stdout,
        stderr=create_result.stderr,
        pen=show_result,
    )


def pen_exec(
    runner: NaveRunner,
    name: str,
    command: Sequence[str],
    only: str | None = None,
    commit: bool = False,
    push_changes: bool = False,
    message: str | None = None,
) -> dict:
    """Run a command in each pen repo, then verify via `pen status --json`.

    `pen exec` has no `--json` flag; its stdout/stderr are opaque and are
    recorded as-is for the caller's report, never parsed. `--push-changes`
    (which implies `--commit` on the real CLI) and `--commit` are NEVER
    emitted unless the caller explicitly requests them — this keeps the
    default mutation policy propose-only (create/run locally, no push).
    `command` is passed as an argv list after `--`, never a shell string.
    """
    if not command:
        raise ValueError("pen_exec requires a non-empty command argv")

    args = ["pen", "exec", name]
    if only is not None:
        args.extend(["--only", only])
    if push_changes:
        args.append("--push-changes")
    elif commit:
        args.append("--commit")
    if message is not None:
        args.extend(["-m", message])
    args.append("--")
    args.extend(command)

    exec_result = runner.run(args)
    status = pen_status(runner, name)
    return {
        "adapter_state": "ok" if exec_result.returncode == 0 else "error",
        "command": "pen exec",
        "returncode": exec_result.returncode,
        "stdout": exec_result.stdout,
        "stderr": exec_result.stderr,
        "status": status,
    }


def provision_apply_branch(
    clone_paths: dict[str, str | Path],
    branch: str,
    base_shas: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Provision a per-proposal branch off the guarded base SHA in each repo clone.

    Operates directly on local repository clones via `git checkout -b <branch> <base_sha>`.
    This is a git operation on local clones, not a Nave CLI subcommand.

    Returns a dict mapping repo identifier (`owner/name`) to a result dict:
      `{"state": "ok"}` or `{"state": "failed", "reason": "..."}`.
    """
    results: dict[str, dict[str, str]] = {}
    for repo, clone_path in clone_paths.items():
        base_sha = base_shas.get(repo)
        if not base_sha:
            results[repo] = {
                "state": "failed",
                "reason": f"missing base SHA for repo {repo}",
            }
            continue

        res = subprocess.run(
            ["git", "-C", str(clone_path), "checkout", "-b", branch, base_sha],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            results[repo] = {"state": "ok"}
        else:
            reason = res.stderr.strip() or res.stdout.strip() or "git checkout -b failed"
            results[repo] = {"state": "failed", "reason": reason}

    return results


def commit_apply_clones(
    clone_paths: dict[str, str | Path],
    message: str,
) -> dict[str, dict[str, str]]:
    """Commit uncommitted changes in each repo clone with the attributed message.

    Operates directly on local repository clones via `git -C <clone> add -A` then
    `git -C <clone> commit -m <message>`. A repo with nothing to commit fails.

    Returns a dict mapping repo identifier (`owner/name`) to a result dict:
      `{"state": "ok"}` or `{"state": "failed", "reason": "..."}`.
    """
    results: dict[str, dict[str, str]] = {}
    for repo, clone_path in clone_paths.items():
        add_res = subprocess.run(
            ["git", "-C", str(clone_path), "add", "-A"],
            capture_output=True,
            text=True,
            check=False,
        )
        if add_res.returncode != 0:
            reason = add_res.stderr.strip() or add_res.stdout.strip() or "git add failed"
            results[repo] = {"state": "failed", "reason": reason}
            continue

        status_res = subprocess.run(
            ["git", "-C", str(clone_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if status_res.returncode == 0 and not status_res.stdout.strip():
            results[repo] = {
                "state": "failed",
                "reason": f"nothing to commit in {repo}",
            }
            continue

        res = subprocess.run(
            ["git", "-C", str(clone_path), "commit", "-m", message],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            results[repo] = {"state": "ok"}
        else:
            reason = res.stderr.strip() or res.stdout.strip() or "git commit failed"
            results[repo] = {"state": "failed", "reason": reason}

    return results


def push_apply_clones(
    clone_paths: dict[str, str | Path],
    branch: str,
) -> dict[str, dict[str, str]]:
    """Push each clone's apply branch to origin.

    Operates directly on local repository clones via `git -C <clone> push origin <branch>`.

    Returns a dict mapping repo identifier (`owner/name`) to a result dict:
      `{"state": "ok"}` or `{"state": "failed", "reason": "..."}`.
    """
    results: dict[str, dict[str, str]] = {}
    for repo, clone_path in clone_paths.items():
        res = subprocess.run(
            ["git", "-C", str(clone_path), "push", "origin", branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            results[repo] = {"state": "ok"}
        else:
            reason = res.stderr.strip() or res.stdout.strip() or "git push failed"
            results[repo] = {"state": "failed", "reason": reason}

    return results



def _materialize_summary(report: dict) -> dict:
    """Build a content-free per-repo, per-state artifact summary.

    Never includes artifact `content` (or `blob_sha`/`detail`) — only counts,
    so the CLI can report success without echoing decoded file bytes.
    """
    repos_summary = []
    for repo in report.get("repos", []):
        counts: dict[str, int] = {}
        for artifact in repo.get("artifacts", []):
            state = artifact.get("state", "unknown")
            counts[state] = counts.get(state, 0) + 1
        repos_summary.append(
            {
                "repo": repo.get("repo"),
                "artifacts_by_state": dict(sorted(counts.items())),
            }
        )
    repos_summary.sort(key=lambda entry: (entry["repo"] or ""))
    return {
        "repos": repos_summary,
        "protocol_note": "content omitted from CLI output; see materialize() for in-process access",
    }


def _runner_from_args(args: argparse.Namespace) -> NaveRunner:
    fixtures = os.environ.get("PULSE_NAVE_FIXTURES")
    return NaveRunner(binary=args.binary, fixtures=fixtures, timeout=args.timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_runner_options(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--binary", default="nave")
        command_parser.add_argument("--timeout", type=int, default=120)

    probe_parser = subparsers.add_parser("probe")
    add_runner_options(probe_parser)
    scan_parser = subparsers.add_parser("scan")
    add_runner_options(scan_parser)
    scan_parser.add_argument("--user")
    scan_parser.add_argument("--no-interaction", action="store_true")
    scan_parser.add_argument("--prune", action="store_true")
    pull_parser = subparsers.add_parser("pull")
    add_runner_options(pull_parser)
    search_parser = subparsers.add_parser("search")
    add_runner_options(search_parser)
    search_parser.add_argument("--term", action="append", default=[])
    search_parser.add_argument("--match", dest="matches", action="append", default=[])
    build_parser = subparsers.add_parser("build")
    add_runner_options(build_parser)
    build_parser.add_argument("--filter")
    build_parser.add_argument("--where", action="append", default=[])
    build_parser.add_argument("--match", dest="matches", action="append", default=[])
    check_parser = subparsers.add_parser("check")
    add_runner_options(check_parser)
    materialize_parser = subparsers.add_parser("materialize")
    add_runner_options(materialize_parser)
    materialize_parser.add_argument("--request", required=True)
    pen_show_parser = subparsers.add_parser("pen-show")
    add_runner_options(pen_show_parser)
    pen_show_parser.add_argument("--name", default="")
    pen_show_parser.add_argument("--filter")
    pen_status_parser = subparsers.add_parser("pen-status")
    add_runner_options(pen_status_parser)
    pen_status_parser.add_argument("--name", required=True)
    pen_create_parser = subparsers.add_parser("pen-create")
    add_runner_options(pen_create_parser)
    pen_create_parser.add_argument("--name", required=True)
    pen_create_parser.add_argument("--ignore-case", action="store_true")
    pen_create_parser.add_argument("--match", dest="matches", action="append", default=[])
    pen_create_parser.add_argument("--term", action="append", default=[])
    pen_exec_parser = subparsers.add_parser("pen-exec")
    add_runner_options(pen_exec_parser)
    pen_exec_parser.add_argument("--name", required=True)
    pen_exec_parser.add_argument("--only")
    pen_exec_parser.add_argument("--commit", action="store_true")
    pen_exec_parser.add_argument("--push-changes", action="store_true")
    pen_exec_parser.add_argument("--message", "-m")
    pen_exec_parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    runner = _runner_from_args(args)
    if args.command == "probe":
        print(json.dumps(probe(runner), indent=2, sort_keys=True))
        return 0
    if args.command == "scan":
        result = scan(
            runner,
            user=args.user,
            no_interaction=args.no_interaction,
            prune=args.prune,
        )
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return result.returncode
    if args.command == "pull":
        result = pull(runner)
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return result.returncode
    if args.command == "search":
        if not args.term and not args.matches:
            print("search requires --term or --match", file=sys.stderr)
            return 2
        result = search(runner, args.term, args.matches)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "build":
        result = build(runner, args.filter, args.where, args.matches)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "check":
        result = check(runner)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "materialize":
        result = materialize(runner, args.request)
        if result.get("adapter_state") == "error":
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1
        print(json.dumps(_materialize_summary(result), indent=2, sort_keys=True))
        return 0
    if args.command == "pen-show":
        result = pen_show(runner, name=args.name, filter_regex=args.filter)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "pen-status":
        result = pen_status(runner, args.name)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "pen-create":
        query = PenQuery(
            terms=args.term, match_preds=args.matches, ignore_case=args.ignore_case
        )
        handle = pen_create(runner, query, args.name)
        print(json.dumps(asdict(handle), indent=2, sort_keys=True))
        return 1 if handle.state == "error" else 0
    if args.command == "pen-exec":
        cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
        if not cmd:
            print("pen-exec requires a command after --", file=sys.stderr)
            return 2
        result = pen_exec(
            runner,
            args.name,
            cmd,
            only=args.only,
            commit=args.commit,
            push_changes=args.push_changes,
            message=args.message,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
