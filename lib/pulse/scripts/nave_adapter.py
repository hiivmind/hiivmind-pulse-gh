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
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence


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


# --- apply verbs -----------------------------------------------------------
#
# `nave pen {capabilities,branch,commit,push,reset}` — the sole git-mutation
# path for apply-mode landings (F11 consolidation note: no clone-write git
# in Pulse). Contract source of truth: `crates/nave_apply/src/lib.rs` in
# `discreteds/nave`, transcribed for cross-repo convenience in
# `docs/superpowers/specs/2026-08-13-apply-verb-contract-handoff.md` (that
# repo, PR #2) — read it before changing anything below.

NAVE_APPLY_PROTOCOL = 1
APPLY_VERBS = ("branch", "commit", "push", "reset")

# Per-repo `state` values are closed sets, kebab-case on the wire. An
# unrecognized value is a validation error, never silently accepted.
_BRANCH_STATES = frozenset(
    {
        "ok",
        "stale-base",
        "exists",
        "missing-ref",
        "not-a-commit",
        "unknown-repo",
        "evidence-unavailable",
    }
)
_COMMIT_STATES = frozenset(
    {
        "ok",
        "nothing-to-commit",
        "dirty-outside-bounds",
        "invariant-violated",
        "missing-clone",
        "no-apply-state",
        "unknown-repo",
    }
)
_PUSH_STATES = frozenset(
    {"ok", "missing-branch", "diverged", "push-rejected", "no-apply-state", "unknown-repo"}
)
_RESET_STATES = frozenset(
    {"ok", "remote-cas-mismatch", "missing-branch", "unknown-repo", "evidence-mismatch"}
)

# Fields every `*RepoResult` variant serializes unconditionally (matches the
# Rust structs' non-`Option` fields); anything else (`reason`,
# `local_commit_sha`, ...) is present only when the verb has it to report.
_BRANCH_REQUIRED_FIELDS = (
    "repo",
    "base_ref",
    "expected_base_sha",
    "observed_base_sha",
    "observed_tree_sha",
    "apply_ref",
    "state",
)
_COMMIT_REQUIRED_FIELDS = ("repo", "state")
_PUSH_REQUIRED_FIELDS = ("repo", "state")
_RESET_REQUIRED_FIELDS = ("repo", "local_reset", "remote_deleted", "state")


def _validate_apply_result(
    data: dict,
    *,
    command: str,
    request_repos: Sequence[str],
    required_fields: Sequence[str],
    valid_states: frozenset[str],
    request_by_repo: Mapping[str, Mapping[str, object]] | None = None,
    per_repo_echo_from_request: Sequence[str] = (),
    per_repo_echo_uniform: Mapping[str, object] | None = None,
) -> dict:
    """Enforce the versioned apply-verb wire contract; never invent success.

    Checks, in order: JSON is an object; `protocol_version` matches; a
    `_decode_json` transport-layer error (bad JSON / non-dict root) passes
    through unchanged; `adapter_state` is present and one of `{"ok",
    "error"}` (an `"error"` envelope's `reason` is already top-level and is
    returned as-is); on `"ok"`, `repos` is a list with exact coverage
    against `request_repos` (no missing, no extra, no duplicate repo), every
    entry carries `required_fields` and a `state` in `valid_states`, and any
    echoed field — either per-repo (`per_repo_echo_from_request`, checked
    against the matching request entry) or envelope-uniform
    (`per_repo_echo_uniform`, e.g. `pen branch`'s single `apply_ref` across
    every repo) — matches what was requested. Any failure returns a typed
    `adapter_state: "error"` envelope with an empty `repos` and a `reason`
    naming exactly what was wrong.
    """

    def fail(reason: str) -> dict:
        return {
            "protocol_version": data.get("protocol_version") if isinstance(data, dict) else None,
            "adapter_state": "error",
            "reason": reason,
            "repos": [],
        }

    if not isinstance(data, dict):
        return fail(f"invalid JSON from nave {command}: root is not an object")
    if "command" in data and "returncode" in data and "error" in data:
        return data  # `_decode_json` transport-layer error; already typed.

    protocol_version = data.get("protocol_version")
    if protocol_version != NAVE_APPLY_PROTOCOL:
        return fail(
            f"unsupported protocol_version {protocol_version!r} from nave {command} "
            f"(expected {NAVE_APPLY_PROTOCOL})"
        )

    adapter_state = data.get("adapter_state")
    if adapter_state is None:
        return fail(f"adapter_state missing from nave {command} output")
    if adapter_state not in ("ok", "error"):
        return fail(f"unrecognized adapter_state {adapter_state!r} from nave {command}")
    if adapter_state == "error":
        return data

    repos = data.get("repos")
    if not isinstance(repos, list):
        return fail(f"nave {command} reported adapter_state=ok with a non-list repos field")

    seen: dict[str, int] = {}
    for entry in repos:
        if not isinstance(entry, dict) or "repo" not in entry:
            return fail(f"nave {command} repo entry missing 'repo' field")
        seen[entry["repo"]] = seen.get(entry["repo"], 0) + 1

    duplicates = sorted(repo for repo, count in seen.items() if count > 1)
    if duplicates:
        return fail(f"nave {command} reported duplicate repo(s): {', '.join(duplicates)}")

    requested = set(request_repos)
    reported = set(seen)
    missing = sorted(requested - reported)
    extra = sorted(reported - requested)
    if missing:
        return fail(f"nave {command} omitted requested repo(s): {', '.join(missing)}")
    if extra:
        return fail(f"nave {command} reported unrequested repo(s): {', '.join(extra)}")

    for entry in repos:
        repo = entry["repo"]
        missing_fields = [f for f in required_fields if f not in entry]
        if missing_fields:
            return fail(
                f"nave {command} repo {repo!r} missing required field(s): {', '.join(missing_fields)}"
            )
        state = entry.get("state")
        if state not in valid_states:
            return fail(f"nave {command} repo {repo!r} reported unrecognized state {state!r}")
        if request_by_repo is not None:
            requested_entry = request_by_repo.get(repo, {})
            for field in per_repo_echo_from_request:
                if field in requested_entry and entry.get(field) != requested_entry[field]:
                    return fail(
                        f"nave {command} repo {repo!r} echoed {field}={entry.get(field)!r}, "
                        f"requested {requested_entry[field]!r}"
                    )
        if per_repo_echo_uniform:
            for field, expected in per_repo_echo_uniform.items():
                if entry.get(field) != expected:
                    return fail(
                        f"nave {command} repo {repo!r} echoed {field}={entry.get(field)!r}, "
                        f"requested {expected!r}"
                    )

    return data


def _run_apply_verb(
    runner: NaveRunner,
    argv_prefix: Sequence[str],
    envelope: dict,
    *,
    extra_args: Sequence[str] = (),
    command: str,
) -> dict:
    """Write a versioned request envelope to a temp file, run the verb, decode JSON.

    `--request` always names a file path — the wire body is never passed as
    an inline shell argument (mirrors the existing `nave materialize
    --request` convention). The temp directory is removed once the process
    returns; callers needing the request body itself must capture it inside
    a fake runner's `run()` before this returns.
    """
    with tempfile.TemporaryDirectory(prefix="pulse-nave-apply-") as tmp_dir:
        request_path = Path(tmp_dir) / "request.json"
        request_path.write_text(json.dumps(envelope))
        args = [*argv_prefix, "--request", str(request_path), *extra_args, "--json"]
        return _decode_json(command, runner.run(args))


def pen_capabilities(runner: NaveRunner) -> dict:
    """Probe the apply-verb protocol version and supported verbs.

    Run before any apply-mode mutation. Fails closed if the command doesn't
    exist at all (a stale/pre-apply-verb Nave binary has no `pen
    capabilities` subcommand — `clap`'s "unrecognized subcommand" nonzero
    exit *is* the fail-closed signal), if `protocol_version` doesn't match
    `NAVE_APPLY_PROTOCOL`, or if `verbs` isn't a superset of `APPLY_VERBS`.
    """
    decoded = _decode_json("pen capabilities", runner.run(["pen", "capabilities", "--json"]))
    if decoded.get("adapter_state") != "ok":
        return {
            "protocol_version": decoded.get("protocol_version"),
            "verbs": [],
            "adapter_state": "error",
            "reason": decoded.get("reason") or decoded.get("error") or "nave pen capabilities failed",
        }
    protocol_version = decoded.get("protocol_version")
    verbs = decoded.get("verbs")
    if protocol_version != NAVE_APPLY_PROTOCOL:
        return {
            "protocol_version": protocol_version,
            "verbs": verbs if isinstance(verbs, list) else [],
            "adapter_state": "error",
            "reason": f"unsupported protocol_version {protocol_version!r} (expected {NAVE_APPLY_PROTOCOL})",
        }
    if not isinstance(verbs, list) or not set(APPLY_VERBS) <= set(verbs):
        missing = sorted(set(APPLY_VERBS) - set(verbs or []))
        return {
            "protocol_version": protocol_version,
            "verbs": verbs if isinstance(verbs, list) else [],
            "adapter_state": "error",
            "reason": f"nave pen capabilities missing required verb(s): {', '.join(missing)}",
        }
    return {"protocol_version": protocol_version, "verbs": verbs, "adapter_state": "ok", "reason": None}


def pen_branch(
    runner: NaveRunner,
    name: str,
    apply_ref: str,
    request: Sequence[dict],
) -> dict:
    """Provision the apply branch across a request's repos off a verified remote base.

    `request`: `[{"repo": str, "base_ref": str, "expected_base_sha": str}, ...]`.
    `apply_ref` is a single envelope-level field — one branch provisioning
    call names one apply branch across every repo in the request, never a
    per-repo field.
    """
    request_repos = [entry["repo"] for entry in request]
    request_by_repo = {entry["repo"]: entry for entry in request}
    envelope = {"protocol_version": NAVE_APPLY_PROTOCOL, "apply_ref": apply_ref, "repos": list(request)}
    decoded = _run_apply_verb(runner, ["pen", "branch", name], envelope, command="pen branch")
    return _validate_apply_result(
        decoded,
        command="pen branch",
        request_repos=request_repos,
        required_fields=_BRANCH_REQUIRED_FIELDS,
        valid_states=_BRANCH_STATES,
        request_by_repo=request_by_repo,
        per_repo_echo_from_request=("base_ref", "expected_base_sha"),
        per_repo_echo_uniform={"apply_ref": apply_ref},
    )


def pen_commit(
    runner: NaveRunner,
    name: str,
    branch: str,
    request: Sequence[dict],
    message: str,
) -> dict:
    """Bounded-stage and commit dirty apply-branch paths, with post-exec invariant checks.

    `request`: `[{"repo": str, "paths": [str, ...]}, ...]`. `branch` is a
    positional, not part of the request body. Neither `expected_base_sha`
    (Nave checks the committed branch against its own server-side sidecar
    written by `pen branch`) nor `message` (the separate `-m` flag) belongs
    in the request body.
    """
    request_repos = [entry["repo"] for entry in request]
    envelope = {"protocol_version": NAVE_APPLY_PROTOCOL, "repos": list(request)}
    decoded = _run_apply_verb(
        runner, ["pen", "commit", name, branch], envelope, extra_args=["-m", message], command="pen commit"
    )
    return _validate_apply_result(
        decoded,
        command="pen commit",
        request_repos=request_repos,
        required_fields=_COMMIT_REQUIRED_FIELDS,
        valid_states=_COMMIT_STATES,
    )


def pen_push(
    runner: NaveRunner,
    name: str,
    branch: str,
    request: Sequence[dict],
) -> dict:
    """Push the apply branch's committed local tip, verifying evidence before reporting ok.

    `request`: `[{"repo": str}, ...]` — carries the expected repo set so
    coverage is enforced against the request, never inferred from the
    response.
    """
    request_repos = [entry["repo"] for entry in request]
    envelope = {"protocol_version": NAVE_APPLY_PROTOCOL, "repos": list(request)}
    decoded = _run_apply_verb(runner, ["pen", "push", name, branch], envelope, command="pen push")
    return _validate_apply_result(
        decoded,
        command="pen push",
        request_repos=request_repos,
        required_fields=_PUSH_REQUIRED_FIELDS,
        valid_states=_PUSH_STATES,
    )


def pen_reset(
    runner: NaveRunner,
    name: str,
    branch: str,
    request: Sequence[dict],
) -> dict:
    """Discard a partial apply attempt: CAS-guarded local + remote branch cleanup.

    `request`: `[{"repo": str, "expected_pushed_sha": str | None}, ...]`;
    `expected_pushed_sha` is `None` for a repo that was never pushed.
    """
    request_repos = [entry["repo"] for entry in request]
    envelope = {"protocol_version": NAVE_APPLY_PROTOCOL, "repos": list(request)}
    decoded = _run_apply_verb(runner, ["pen", "reset", name, branch], envelope, command="pen reset")
    return _validate_apply_result(
        decoded,
        command="pen reset",
        request_repos=request_repos,
        required_fields=_RESET_REQUIRED_FIELDS,
        valid_states=_RESET_STATES,
    )


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


def _load_apply_request(path: str) -> list[dict]:
    """Read a CLI-supplied apply-verb request file: a JSON array of per-repo objects.

    Mirrors each `pen_*` function's own `request` parameter shape — the CLI
    reads this file and passes the parsed list straight through; the
    envelope wrapper (`protocol_version`, `apply_ref`/branch) is built by
    the adapter function itself, never by the caller.
    """
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        raise ValueError(f"apply-verb request file {path} must contain a JSON array of repo objects")
    return data


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
    pen_capabilities_parser = subparsers.add_parser("pen-capabilities")
    add_runner_options(pen_capabilities_parser)
    pen_branch_parser = subparsers.add_parser("pen-branch")
    add_runner_options(pen_branch_parser)
    pen_branch_parser.add_argument("--name", required=True)
    pen_branch_parser.add_argument("--apply-ref", required=True)
    pen_branch_parser.add_argument(
        "--request", required=True, help="JSON file: [{repo, base_ref, expected_base_sha}, ...]"
    )
    pen_commit_parser = subparsers.add_parser("pen-commit")
    add_runner_options(pen_commit_parser)
    pen_commit_parser.add_argument("--name", required=True)
    pen_commit_parser.add_argument("--branch", required=True)
    pen_commit_parser.add_argument("--request", required=True, help="JSON file: [{repo, paths}, ...]")
    pen_commit_parser.add_argument("--message", "-m", required=True)
    pen_push_parser = subparsers.add_parser("pen-push")
    add_runner_options(pen_push_parser)
    pen_push_parser.add_argument("--name", required=True)
    pen_push_parser.add_argument("--branch", required=True)
    pen_push_parser.add_argument("--request", required=True, help="JSON file: [{repo}, ...]")
    pen_reset_parser = subparsers.add_parser("pen-reset")
    add_runner_options(pen_reset_parser)
    pen_reset_parser.add_argument("--name", required=True)
    pen_reset_parser.add_argument("--branch", required=True)
    pen_reset_parser.add_argument(
        "--request", required=True, help="JSON file: [{repo, expected_pushed_sha}, ...]"
    )
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
    if args.command == "pen-capabilities":
        result = pen_capabilities(runner)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "pen-branch":
        result = pen_branch(runner, args.name, args.apply_ref, _load_apply_request(args.request))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "pen-commit":
        result = pen_commit(
            runner, args.name, args.branch, _load_apply_request(args.request), args.message
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "pen-push":
        result = pen_push(runner, args.name, args.branch, _load_apply_request(args.request))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    if args.command == "pen-reset":
        result = pen_reset(runner, args.name, args.branch, _load_apply_request(args.request))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("adapter_state") == "error" else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
