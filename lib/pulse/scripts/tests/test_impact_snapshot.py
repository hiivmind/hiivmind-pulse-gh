"""Tests for impact_snapshot.py — remote evidence collector for the F5
impact audit. Every git invocation goes through a fake runner; no real git
process, no network (see nave_adapter's RecordingRunner idiom in
test_nave_adapter.py)."""
from __future__ import annotations

from dataclasses import dataclass, field

from lib.pulse.scripts import impact_snapshot as snap


@dataclass
class Completed:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Fake `runner(argv, cwd) -> Completed` seam. Responses keyed by exact
    argv tuple; unmatched calls fail loudly so tests catch drift."""

    def __init__(self, responses: dict[tuple, Completed] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[tuple, str | None]] = []

    def __call__(self, argv, cwd=None):
        key = tuple(argv)
        self.calls.append((key, str(cwd) if cwd is not None else None))
        return self.responses.get(key, Completed(1, "", f"no fixture for {argv}"))


def relationships(depends_on, dependent="dependent-repo"):
    return {
        "repo_dependencies": {
            dependent: {
                "depends_on": depends_on,
                "depended_by": [],
                "relationship_type": "test",
            }
        }
    }


def edge(**overrides):
    e = {
        "repo": "upstream-repo",
        "watch_paths": ["lib/foo.py"],
        "watch_branch": "develop",
        "integration_tested_sha": "abc1234",
        "tested_at": "2026-07-01T10:00:00Z",
    }
    e.update(overrides)
    return e


def ls_remote_ok(sha="head999"):
    return Completed(0, f"{sha}\trefs/heads/develop\n", "")


def init_ok():
    return Completed(0, "", "")


def fetch_ok():
    return Completed(0, "", "")


def rev_parse_ok(sha="head999"):
    return Completed(0, f"{sha}\n", "")


def diff_ok(paths):
    return Completed(0, "\n".join(paths) + ("\n" if paths else ""), "")


# --- no watched edges ---

def test_no_object_edges_returns_empty_snapshot():
    rel = relationships([])
    runner = RecordingRunner()

    result = snap.collect(rel, runner=runner)

    assert result == {}
    assert runner.calls == []


def test_legacy_string_edges_are_skipped():
    rel = relationships(["upstream-repo"])
    runner = RecordingRunner()

    result = snap.collect(rel, runner=runner)

    assert result == {}
    assert runner.calls == []


# --- happy path ---

def test_happy_path_produces_exact_snapshot_shape(tmp_path):
    rel = relationships([edge()])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "abc1234"): fetch_ok(),
        ("git", "diff", "--name-only", "abc1234", "head999"): diff_ok(
            ["lib/foo.py", "lib/bar.py"]
        ),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    assert result == {
        "upstream-repo": {
            "develop": {
                "head": "head999",
                "changed_files_by_base": {
                    "abc1234": ["lib/bar.py", "lib/foo.py"],  # sorted
                },
                "base_missing": [],
            }
        }
    }


def test_diff_command_runs_in_the_bare_repo_dir(tmp_path):
    rel = relationships([edge()])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "abc1234"): fetch_ok(),
        ("git", "diff", "--name-only", "abc1234", "head999"): diff_ok(["lib/foo.py"]),
    })

    snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    diff_call = [c for c in runner.calls
                if c[0] == ("git", "diff", "--name-only", "abc1234", "head999")][0]
    assert diff_call[1] == str(repo_dir)


# --- base_missing ---

def test_unresolvable_tested_sha_is_recorded_in_base_missing(tmp_path):
    rel = relationships([edge(integration_tested_sha="deadbee1")])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "deadbee1"):
            Completed(128, "", "fatal: could not find remote ref deadbee1"),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap["head"] == "head999"
    assert branch_snap["changed_files_by_base"] == {}
    assert branch_snap["base_missing"] == ["deadbee1"]


def test_malformed_tested_sha_never_invokes_git(tmp_path):
    """A tested_sha that doesn't look like a git SHA (hex, 7-40 chars) is
    never passed to git — it's recorded as missing without a fetch/diff
    round trip, per the hardened argv-validation rule."""
    rel = relationships([edge(integration_tested_sha="ghost-sha")])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("head999"),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap["head"] == "head999"
    assert branch_snap["changed_files_by_base"] == {}
    assert branch_snap["base_missing"] == ["ghost-sha"]
    base_fetch_calls = [c for c in runner.calls if c[0][1] == "fetch" and "ghost-sha" in c[0]]
    assert base_fetch_calls == []
    diff_calls = [c for c in runner.calls if c[0][1] == "diff"]
    assert diff_calls == []


def test_invalid_branch_name_is_never_passed_to_git(tmp_path):
    """A watch_branch starting with '-' could be parsed as a git option if
    passed as a bare positional; it must never reach ls-remote/fetch."""
    rel = relationships([edge(watch_branch="-evil-branch")])
    repo_dir = tmp_path / "work" / "upstream-repo_-evil-branch"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["-evil-branch"]
    assert branch_snap["head"] is None
    assert branch_snap["changed_files_by_base"] == {}
    assert branch_snap["base_missing"] == ["abc1234"]
    ls_remote_calls = [c for c in runner.calls if c[0][1] == "ls-remote"]
    fetch_calls = [c for c in runner.calls if c[0][1] == "fetch"]
    assert ls_remote_calls == []
    assert fetch_calls == []


def test_unresolvable_head_marks_all_tested_shas_missing_and_head_none(tmp_path):
    rel = relationships([edge(integration_tested_sha="abc1234")])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"):
            Completed(128, "", "fatal: repository not found"),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap["head"] is None
    assert branch_snap["changed_files_by_base"] == {}
    assert branch_snap["base_missing"] == ["abc1234"]
    # never fetched branch tip or a base once head resolution failed
    fetch_calls = [c for c in runner.calls if c[0][1] == "fetch"]
    assert fetch_calls == []


def test_branch_fetch_failure_marks_tested_shas_missing_but_keeps_head(tmp_path):
    rel = relationships([edge(integration_tested_sha="abc1234")])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"):
            Completed(128, "", "fatal: could not fetch branch"),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap["head"] == "head999"
    assert branch_snap["changed_files_by_base"] == {}
    assert branch_snap["base_missing"] == ["abc1234"]


def test_fetch_head_resolution_failure_keeps_previous_head_hint(tmp_path):
    """If the branch fetch succeeds but `git rev-parse FETCH_HEAD` cannot be
    resolved, fall back to the pre-fetch head hint rather than crashing or
    fabricating a head."""
    rel = relationships([edge(integration_tested_sha="abc1234")])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): Completed(128, "", "fatal: ambiguous argument"),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap["head"] == "head999"
    assert branch_snap["changed_files_by_base"] == {}
    assert branch_snap["base_missing"] == ["abc1234"]


# --- multiple tested_shas on the same edge ---

def test_multiple_dependents_watching_same_branch_union_their_tested_shas(tmp_path):
    rel = {
        "repo_dependencies": {
            "dependent-a": {
                "depends_on": [edge(integration_tested_sha="abc1234")],
                "depended_by": [], "relationship_type": "test",
            },
            "dependent-b": {
                "depends_on": [edge(integration_tested_sha="bcd2234")],
                "depended_by": [], "relationship_type": "test",
            },
        }
    }
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "abc1234"): fetch_ok(),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "bcd2234"): fetch_ok(),
        ("git", "diff", "--name-only", "abc1234", "head999"): diff_ok(["a.py"]),
        ("git", "diff", "--name-only", "bcd2234", "head999"): diff_ok(["b.py"]),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap["changed_files_by_base"] == {
        "abc1234": ["a.py"],
        "bcd2234": ["b.py"],
    }
    assert branch_snap["base_missing"] == []


def test_edge_without_tested_sha_still_resolves_head_with_no_bases(tmp_path):
    rel = relationships([edge(integration_tested_sha=None)])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "ls-remote", "--", url, "refs/heads/develop"): ls_remote_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("head999"),
    })

    result = snap.collect(rel, workdir=tmp_path / "work", runner=runner)

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap == {"head": "head999", "changed_files_by_base": {},
                           "base_missing": []}


# --- known_heads short-circuit ---

def test_known_heads_skips_ls_remote_but_diff_is_still_computed_by_git(tmp_path):
    rel = relationships([edge()])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("head999"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "abc1234"): fetch_ok(),
        ("git", "diff", "--name-only", "abc1234", "head999"): diff_ok(["lib/foo.py"]),
    })

    result = snap.collect(
        rel, workdir=tmp_path / "work", runner=runner,
        known_heads={"upstream-repo": {"develop": "head999"}},
    )

    assert result["upstream-repo"]["develop"]["head"] == "head999"
    assert result["upstream-repo"]["develop"]["changed_files_by_base"] == {
        "abc1234": ["lib/foo.py"],
    }
    ls_remote_calls = [c for c in runner.calls if c[0][1] == "ls-remote"]
    assert ls_remote_calls == []
    # the diff still runs through git — known_heads never supplies path evidence
    diff_calls = [c for c in runner.calls if c[0][1] == "diff"]
    assert len(diff_calls) == 1


def test_stale_known_head_is_not_used_as_diff_endpoint(tmp_path):
    """A cached known_head that has fallen behind the remote's true current
    tip must never become the diff endpoint — that would under-report
    staleness (fail open). The collector always resolves the actual fetched
    head via `git rev-parse FETCH_HEAD` and diffs against THAT, regardless
    of what known_heads supplied."""
    rel = relationships([edge()])
    repo_dir = tmp_path / "work" / "upstream-repo_develop"
    url = "https://github.com/upstream-repo.git"
    runner = RecordingRunner({
        ("git", "init", "--bare", "-q", str(repo_dir)): init_ok(),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "develop"): fetch_ok(),
        ("git", "rev-parse", "FETCH_HEAD"): rev_parse_ok("newerhead000"),
        ("git", "fetch", "--filter=blob:none", "-q", "--", url, "abc1234"): fetch_ok(),
        ("git", "diff", "--name-only", "abc1234", "newerhead000"): diff_ok(["lib/foo.py"]),
    })

    result = snap.collect(
        rel, workdir=tmp_path / "work", runner=runner,
        known_heads={"upstream-repo": {"develop": "stalehead999"}},
    )

    branch_snap = result["upstream-repo"]["develop"]
    assert branch_snap["head"] == "newerhead000"
    assert branch_snap["changed_files_by_base"] == {"abc1234": ["lib/foo.py"]}

    diff_calls = [c for c in runner.calls if c[0][1] == "diff"]
    assert diff_calls[0][0] == ("git", "diff", "--name-only", "abc1234", "newerhead000")
    # the stale known_head must never appear as a diff endpoint
    stale_diff_calls = [c for c in diff_calls if "stalehead999" in c[0]]
    assert stale_diff_calls == []
    ls_remote_calls = [c for c in runner.calls if c[0][1] == "ls-remote"]
    assert ls_remote_calls == []


# --- --known-heads loader: accepts YAML or JSON ---

def test_load_known_heads_parses_yaml(tmp_path):
    path = tmp_path / "known-heads.yaml"
    path.write_text(
        "upstream-repo:\n"
        "  develop: head999\n"
        "  main: head888\n"
    )

    result = snap._load_known_heads(path)

    assert result == {"upstream-repo": {"develop": "head999", "main": "head888"}}


def test_load_known_heads_parses_json(tmp_path):
    import json as jsonlib
    path = tmp_path / "known-heads.json"
    path.write_text(jsonlib.dumps({"upstream-repo": {"develop": "head999"}}))

    result = snap._load_known_heads(path)

    assert result == {"upstream-repo": {"develop": "head999"}}


def test_load_known_heads_empty_file_returns_empty_dict(tmp_path):
    path = tmp_path / "known-heads.yaml"
    path.write_text("")

    result = snap._load_known_heads(path)

    assert result == {}


# --- workdir cleanup default ---

def test_default_workdir_is_a_cleaned_up_temp_dir():
    rel = relationships([edge()])
    captured = {}

    def runner(argv, cwd=None):
        if "init" in argv:
            captured["init_target"] = argv[-1]
        if "ls-remote" in argv:
            return Completed(0, "head999\trefs/heads/develop\n", "")
        if "rev-parse" in argv:
            return Completed(0, "head999\n", "")
        return Completed(0, "", "")

    result = snap.collect(rel, runner=runner)

    assert result["upstream-repo"]["develop"]["head"] == "head999"
    # temp dir used for git init must not survive the call
    from pathlib import Path
    assert "init_target" in captured
    assert not Path(captured["init_target"]).exists()
