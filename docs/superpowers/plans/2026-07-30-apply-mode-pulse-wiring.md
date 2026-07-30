# Apply-Mode Pulse-Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `hiivmind-pulse-gh` to land a re-derived, workspace-authorized `allow-listed` proposal end-to-end **through Nave verbs only** — no clone-write git in Pulse — for a neutral transformation, with a crash-resumable driver, a base-and-head-verified merge gate, and a PR-gated F8 base advance.

**Architecture:** Single-mutator (PR #141): Nave owns all clone writes; Pulse keeps orchestration, policy, and read-only verification. This plan is the **`hiivmind-pulse-gh` half** — thin adapters over new Nave verbs (contract pinned here in Task 1, consumer-side), an evolved `ApplyOps` data contract, a phase-journaled driver, and the F8 finalizer. The **Nave fork half** (implementing the verbs) is a separate plan that conforms to Task 1's contract. Workspace enrollment is a follow-up PR.

**Tech Stack:** Python 3.10+ PEP 723 scripts, PyYAML, pytest, `gh` CLI, `nave` CLI (new verbs), git (read-only in Pulse). No new library dependencies.

**Source spec:** `docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md`. Read it before starting.

## Global Constraints

- **No clone-write git in Pulse.** Every branch/commit/push/reset is a Nave verb call via `nave_adapter`. Read-only `git rev-parse`/`status` in `pen_clone_reader` is allowed and stays.
- **The `propose` path through `pen_orchestrator.execute()` is byte-for-byte unchanged.** Apply adds an `allow-listed` branch after the same gates; it never weakens a gate.
- **Every apply run writes a validated result on every exit** (including early `blocked`/`failed`/ABORT) and self-validates via `validate_result.py`; a non-zero validator exit is a bug. Pre-push exits write `repo-mutation`; `apply-status` is remote-lifecycle only.
- **Fail closed.** A missing reader, missing Nave verb, stale base, out-of-allowlist change, unauthorized proposal, or absent required tool is `blocked`/`failed`, never a silent success.
- **Values are built from the `Proposal` that gated execution plus observed facts — never reconstructed.**
- **Nave contract is versioned.** Every request/result carries `protocol_version: 1`; a capability handshake fails closed before any mutation against an incompatible Nave.
- `uv run pytest -q` and `git diff --check` pass before each task closes. Tests live under `lib/pulse/scripts/tests/`. Run one file with `uv run pytest lib/pulse/scripts/tests/test_x.py -q`.
- Commit subjects use Conventional Commits; end bodies with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` only when the executing workflow requires it (the controller commits).

---

### Task 1: Nave verb adapters + capability handshake + delete the raw-git trio

Pins the Nave CLI+JSON **contract** (consumer side) the fork plan implements, adds thin adapters (argv + strict `--json` decode with field/version validation), and deletes the raw-git trio.

**Files:**
- Modify: `lib/pulse/scripts/nave_adapter.py` — add `NAVE_APPLY_PROTOCOL = 1`, `pen_capabilities`, `pen_branch`, `pen_commit`, `pen_push`, `pen_reset`, extend `pen_status` decode to carry `clone_path`; **delete** `provision_apply_branch`, `commit_apply_clones`, `push_apply_clones` (`nave_adapter.py:500–616`)
- Modify: `lib/pulse/scripts/tests/test_nave_adapter.py` — delete the trio's tests (incl. the existing-branch case at `:724`); add verb-adapter + handshake tests
- Create: `lib/pulse/scripts/tests/fixtures/nave_apply/` — `--json` fixture files per verb (success, partial-failure, malformed, wrong-protocol)

**The pinned contract (protocol_version 1).** Every verb takes `--name <pen> --json` and, where per-repo input is needed, `--request <file.json>`. Every result is `{"protocol_version": 1, "adapter_state": "ok"|"error", "repos": [ {repo-result} ]}`. Per-repo result shapes:
- `pen capabilities --json` → `{"protocol_version": 1, "verbs": ["branch","commit","push","reset","status"]}`
- `pen branch --request <f>` (request: `[{repo, base_ref, expected_base_sha, apply_ref}]`) → repo `{repo, base_ref, expected_base_sha, observed_base_sha, apply_ref, state: "ok"|"failed", reason?}`
- `pen commit --request <f> --message <m>` (request: `[{repo, bound_paths: [...]}]`) → repo `{repo, local_commit_sha, state, reason?}`
- `pen push --branch <b>` → repo `{repo, remote, remote_ref, remote_sha, upstream, state, reason?}`
- `pen reset --branch <b> --request <f>` (request: `[{repo, expected_pushed_sha}]`) → repo `{repo, state, reason?}`
- `pen status --name <pen> --json` → repo `{repo, clone_path, working_tree, freshness, divergence}` (extends today's status with `clone_path`)

**Interfaces:**
- Produces (consumed by Tasks 3, 4, 8):
  - `pen_capabilities(runner) -> dict` — `{"protocol_version": int, "verbs": list[str], "adapter_state": str}`
  - `pen_branch(runner, name: str, request: list[dict]) -> dict` — `{"adapter_state","repos":[{repo,base_ref,expected_base_sha,observed_base_sha,apply_ref,state,reason?}]}`
  - `pen_commit(runner, name: str, request: list[dict], message: str) -> dict` — repos carry `local_commit_sha`
  - `pen_push(runner, name: str, branch: str) -> dict` — repos carry `remote_ref, remote_sha, upstream`
  - `pen_reset(runner, name: str, branch: str, request: list[dict]) -> dict`
  - `pen_status(runner, name)` — existing, now each repo dict includes `clone_path`
  - `NAVE_APPLY_PROTOCOL = 1`
- Consumes: the existing `NaveRunner`/`QueuedRunner` idiom and `_decode_json`/argv helpers already in `nave_adapter.py`.

- [ ] **Step 1: Write failing tests** for the adapters + handshake + strict decode.

```python
# test_nave_adapter.py (additions)
from lib.pulse.scripts import nave_adapter as na

def test_pen_capabilities_reports_protocol_and_verbs():
    runner = QueuedRunner([_json_ok({"protocol_version": 1, "verbs": ["branch","commit","push","reset","status"]})])
    caps = na.pen_capabilities(runner)
    assert caps["protocol_version"] == 1
    assert "branch" in caps["verbs"]

def test_pen_branch_returns_observed_base_per_repo():
    payload = {"protocol_version": 1, "adapter_state": "ok", "repos": [
        {"repo": "acme/docs", "base_ref": "develop", "expected_base_sha": "aaa",
         "observed_base_sha": "aaa", "apply_ref": "pulse/apply/p1", "state": "ok"}]}
    runner = QueuedRunner([_json_ok(payload)])
    res = na.pen_branch(runner, "pen1", [{"repo":"acme/docs","base_ref":"develop","expected_base_sha":"aaa","apply_ref":"pulse/apply/p1"}])
    r = res["repos"][0]
    assert r["observed_base_sha"] == "aaa" and r["state"] == "ok"

def test_pen_push_returns_remote_ref_and_sha():
    payload = {"protocol_version": 1, "adapter_state": "ok", "repos": [
        {"repo":"acme/docs","remote":"origin","remote_ref":"pulse/apply/p1","remote_sha":"bbb","upstream":"origin/pulse/apply/p1","state":"ok"}]}
    runner = QueuedRunner([_json_ok(payload)])
    res = na.pen_push(runner, "pen1", "pulse/apply/p1")
    assert res["repos"][0]["remote_sha"] == "bbb"

def test_wrong_protocol_version_is_error_not_silent():
    runner = QueuedRunner([_json_ok({"protocol_version": 99, "adapter_state": "ok", "repos": []})])
    res = na.pen_branch(runner, "pen1", [])
    assert res["adapter_state"] == "error"
    assert "protocol" in (res.get("reason","").lower())

def test_malformed_json_is_error():
    runner = QueuedRunner([_json_raw("not json")])
    res = na.pen_push(runner, "pen1", "b")
    assert res["adapter_state"] == "error"

def test_trio_is_deleted():
    assert not hasattr(na, "provision_apply_branch")
    assert not hasattr(na, "commit_apply_clones")
    assert not hasattr(na, "push_apply_clones")
```

(`_json_ok(obj)` / `_json_raw(s)` are small helpers producing the runner's recorded stdout — mirror the existing `QueuedRunner` fixture idiom in this test file.)

- [ ] **Step 2: Run tests, verify they fail** — `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py -q` → FAIL (attributes missing).

- [ ] **Step 3: Implement the adapters + strict decode.**

```python
# nave_adapter.py (additions near the other pen_* functions)
NAVE_APPLY_PROTOCOL = 1

def _apply_verb(runner, argv, *, expect_repos=True):
    """Run a JSON apply verb; enforce protocol_version and shape, fail closed."""
    raw = runner.run(argv)  # existing runner contract: returns decoded-or-raw per the idiom
    data = _decode_json(raw)  # existing helper
    if not isinstance(data, dict):
        return {"adapter_state": "error", "reason": "non-JSON or non-object result", "repos": []}
    if data.get("protocol_version") != NAVE_APPLY_PROTOCOL:
        return {"adapter_state": "error",
                "reason": f"protocol mismatch: got {data.get('protocol_version')!r}, need {NAVE_APPLY_PROTOCOL}",
                "repos": []}
    if expect_repos and not isinstance(data.get("repos"), list):
        return {"adapter_state": "error", "reason": "missing repos list", "repos": []}
    data.setdefault("adapter_state", "ok")
    return data

def pen_capabilities(runner):
    data = _apply_verb(runner, ["pen", "capabilities", "--json"], expect_repos=False)
    return {"protocol_version": data.get("protocol_version") if data.get("adapter_state") == "ok" else None,
            "verbs": data.get("verbs", []), "adapter_state": data.get("adapter_state", "error"),
            "reason": data.get("reason")}

def _write_request(request):  # returns a temp file path; caller cleans up (or use PULSE_NAVE_FIXTURES bypass)
    import json, tempfile
    fd, path = tempfile.mkstemp(suffix=".json"); 
    with os.fdopen(fd, "w") as fh: json.dump(request, fh)
    return path

def pen_branch(runner, name, request):
    path = _write_request(request)
    try:
        return _apply_verb(runner, ["pen", "branch", "--name", name, "--request", path, "--json"])
    finally:
        try: os.unlink(path)
        except OSError: pass

def pen_commit(runner, name, request, message):
    path = _write_request(request)
    try:
        return _apply_verb(runner, ["pen", "commit", "--name", name, "--request", path, "--message", message, "--json"])
    finally:
        try: os.unlink(path)
        except OSError: pass

def pen_push(runner, name, branch):
    return _apply_verb(runner, ["pen", "push", "--name", name, "--branch", branch, "--json"])

def pen_reset(runner, name, branch, request):
    path = _write_request(request)
    try:
        return _apply_verb(runner, ["pen", "reset", "--name", name, "--branch", branch, "--request", path, "--json"])
    finally:
        try: os.unlink(path)
        except OSError: pass
```

Extend `pen_status`'s per-repo decode to pass through `clone_path` (add it to whatever field list the existing decode builds). **Delete** `provision_apply_branch`, `commit_apply_clones`, `push_apply_clones` (`nave_adapter.py:500–616`).

- [ ] **Step 4: Run tests, verify pass** — `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py -q` → PASS.

- [ ] **Step 5: Commit** — `feat: nave apply-verb adapters + capability handshake; delete raw-git trio`.

---

### Task 2: Mandatory bound_paths, proposal re-derivation, and ApplyAuthorization

Allow-listed proposals must carry exact non-empty `bound_paths` (any validation kind); apply re-derives a fresh Proposal and authorizes it against a workspace policy; audit identity is enforced.

**Files:**
- Modify: `lib/pulse/scripts/mutation_plan.py` — `build_proposal` requires non-empty `bound_paths` covering `selection` exactly when `mutation_policy == "allow-listed"` (independent of validation kind); add `proposal_digest(proposal) -> str`
- Create: `lib/pulse/scripts/apply_rederive.py` — `rederive_proposal(binding_ref, recorded_summary, *, read_repo_head) -> Proposal`
- Create: `lib/pulse/scripts/apply_authorization.py` — `load_authorization(path) -> ApplyAuthorization`; `authorize(proposal, auth, recorded_summary) -> None|raises AuthorizationError`
- Create: `lib/pulse/scripts/tests/test_apply_authorization.py`, `test_apply_rederive.py`; modify `test_mutation_plan.py`

**Interfaces:**
- Consumes: `mutation_plan.Proposal`, `build_proposal` (`mutation_plan.py`), the F6–F9 `build_proposal` path for the binding's transformation.
- Produces (Tasks 3, 8):
  - `mutation_plan.proposal_digest(proposal: Proposal) -> str` (stable sha256 of the immutable fields)
  - `apply_rederive.rederive_proposal(...) -> Proposal` (mutation_policy `allow-listed`, fresh `expected_shas`, non-empty `bound_paths`)
  - `apply_authorization.ApplyAuthorization` (`{transformation: str, permitted_repos: frozenset[str], policy: str}`), `load_authorization(path)`, `authorize(proposal, auth, recorded_summary)` — raises `AuthorizationError` on transformation/selection/identity mismatch.

- [ ] **Step 1: Write failing tests.**

```python
# test_mutation_plan.py (additions)
import pytest
from lib.pulse.scripts import mutation_plan as mp

def test_allow_listed_requires_nonempty_bound_paths():
    with pytest.raises(ValueError, match="bound_paths"):
        mp.build_proposal(transformation="refresh-node-lockfile", selection=["acme/node"],
                          expected_shas={"acme/node": "aaa"}, mutation_policy="allow-listed",
                          bound_paths={})  # empty -> reject

def test_allow_listed_bound_paths_must_cover_selection_exactly():
    with pytest.raises(ValueError, match="selection"):
        mp.build_proposal(transformation="refresh-node-lockfile", selection=["acme/node"],
                          expected_shas={"acme/node": "aaa"}, mutation_policy="allow-listed",
                          bound_paths={"acme/other": ("package-lock.json",)})

def test_proposal_digest_is_stable():
    p = mp.build_proposal(transformation="refresh-node-lockfile", selection=["acme/node"],
                          expected_shas={"acme/node": "aaa"}, mutation_policy="allow-listed",
                          bound_paths={"acme/node": ("package-lock.json",)})
    assert mp.proposal_digest(p) == mp.proposal_digest(p)
```

```python
# test_apply_authorization.py
import pytest
from lib.pulse.scripts import apply_authorization as aa, mutation_plan as mp

def _prop():
    return mp.build_proposal(transformation="refresh-node-lockfile", selection=["acme/node"],
                             expected_shas={"acme/node":"aaa"}, mutation_policy="allow-listed",
                             bound_paths={"acme/node": ("package-lock.json",)})

SUMMARY = {"binding": "b1", "transformation": "refresh-node-lockfile", "proposal_id": "p1"}

def test_authorized_when_transformation_and_selection_covered():
    auth = aa.ApplyAuthorization(transformation="refresh-node-lockfile",
                                 permitted_repos=frozenset({"acme/node"}), policy="allow-listed")
    aa.authorize(_prop(), auth, SUMMARY)  # no raise

def test_rejects_selection_outside_permitted():
    auth = aa.ApplyAuthorization(transformation="refresh-node-lockfile",
                                 permitted_repos=frozenset({"acme/other"}), policy="allow-listed")
    with pytest.raises(aa.AuthorizationError, match="permitted"):
        aa.authorize(_prop(), auth, SUMMARY)

def test_rejects_transformation_mismatch():
    auth = aa.ApplyAuthorization(transformation="format-python",
                                 permitted_repos=frozenset({"acme/node"}), policy="allow-listed")
    with pytest.raises(aa.AuthorizationError, match="transformation"):
        aa.authorize(_prop(), auth, SUMMARY)
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.**

```python
# mutation_plan.py — inside build_proposal, after existing validation:
if mutation_policy == "allow-listed":
    if not bound_paths or any(not v for v in bound_paths.values()):
        raise ValueError("allow-listed proposals require non-empty bound_paths for every selected repo")
    if set(bound_paths) != set(selection):
        raise ValueError("bound_paths keys must cover selection exactly")

# mutation_plan.py — module level:
import hashlib, json
def proposal_digest(proposal) -> str:
    payload = {"transformation": proposal.transformation, "selection": list(proposal.selection),
               "expected_shas": dict(proposal.expected_shas),
               "bound_paths": {k: list(v) for k, v in proposal.bound_paths.items()},
               "mutation_policy": proposal.mutation_policy}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```

```python
# apply_authorization.py
from __future__ import annotations
from dataclasses import dataclass
import yaml
from pathlib import Path

class AuthorizationError(ValueError): ...

@dataclass(frozen=True)
class ApplyAuthorization:
    transformation: str
    permitted_repos: frozenset
    policy: str

def load_authorization(path, transformation: str) -> ApplyAuthorization:
    doc = yaml.safe_load(Path(path).read_text()) or {}
    entries = doc.get("apply_authorizations", [])
    for e in entries:
        if e.get("transformation") == transformation:
            return ApplyAuthorization(transformation=transformation,
                                      permitted_repos=frozenset(e.get("permitted_repos", [])),
                                      policy=e.get("policy", "allow-listed"))
    raise AuthorizationError(f"no apply authorization for transformation {transformation!r}")

def authorize(proposal, auth: ApplyAuthorization, recorded_summary: dict) -> None:
    if proposal.transformation != auth.transformation:
        raise AuthorizationError(f"transformation {proposal.transformation!r} != authorized {auth.transformation!r}")
    if recorded_summary.get("transformation") != proposal.transformation \
       or recorded_summary.get("proposal_id") != proposal.id:
        raise AuthorizationError("re-derived proposal identity does not match recorded summary")
    outside = set(proposal.selection) - auth.permitted_repos
    if outside:
        raise AuthorizationError(f"selection not permitted: {sorted(outside)}")
    if auth.policy != "allow-listed":
        raise AuthorizationError(f"policy {auth.policy!r} not landable in v1")
```

```python
# apply_rederive.py
from __future__ import annotations
from lib.pulse.scripts import mutation_plan as mp

def rederive_proposal(*, transformation, selection, bound_paths, read_repo_head) -> "mp.Proposal":
    """Mint a fresh allow-listed Proposal off CURRENT head SHAs (never reconstructed from a summary)."""
    expected_shas = {repo: read_repo_head(repo) for repo in selection}
    return mp.build_proposal(transformation=transformation, selection=list(selection),
                             expected_shas=expected_shas, mutation_policy="allow-listed",
                             bound_paths=bound_paths)
```

(If `build_proposal`'s real signature differs — e.g. it takes an entry or actor — match it; read `mutation_plan.py` and adapt keyword names. The behavior contract above is fixed; the exact kwargs are whatever `build_proposal` already exposes.)

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: mandatory bound_paths, proposal re-derivation, ApplyAuthorization`.

---

### Task 3: Evolve ApplyOps/PenRunResult; bind to Nave verbs; rewire execute() allow-listed flow

**Files:**
- Modify: `lib/pulse/scripts/pen_orchestrator.py` — extend `ApplyOps` protocol (`commit_repos(message, bound_paths)`, `push_repos(branch) -> per-repo SHA dict`, add `reset_repos(branch, expected_pushed_shas)`); add `PenRunResult.repo_landings`; rewire the allow-listed commit/push section to consume typed results
- Create: `lib/pulse/scripts/apply_ops.py` — `make_apply_ops(runner, pen_name, bound_paths_by_repo)` returning a production `ApplyOps` bound to the Task 1 verbs
- Modify: `lib/pulse/scripts/tests/test_pen_orchestrator.py` — update the `allow-listed` assertions; Modify: `test_apply_acceptance.py`'s `RecordingApplyOps` to the new protocol
- Create: `lib/pulse/scripts/tests/test_apply_ops.py`

**Interfaces:**
- Consumes: `nave_adapter.pen_branch/pen_commit/pen_push/pen_reset` (Task 1).
- Produces (Tasks 4, 8):
  - `ApplyOps.provision_branch(branch, base_shas) -> {repo: {state, reason?, observed_base_sha?}}`
  - `ApplyOps.commit_repos(message, bound_paths) -> {repo: {state, reason?, local_commit_sha?}}`
  - `ApplyOps.push_repos(branch) -> {repo: {state, reason?, local_commit_sha?, remote_ref?, remote_sha?, upstream?}}`
  - `ApplyOps.reset_repos(branch, expected_pushed_shas) -> {repo: {state, reason?}}`
  - `PenRunResult.repo_landings: dict[str, dict]` (per-repo phase + `local_commit_sha`/`remote_ref`/`remote_sha`), default `{}`
  - `apply_ops.make_apply_ops(runner, pen_name, bound_paths_by_repo, base_refs) -> ApplyOps` (`base_refs: dict[str,str]` maps repo → intended base branch, needed to build the `pen_branch` request)

- [ ] **Step 1: Write failing tests.**

```python
# test_apply_ops.py
from lib.pulse.scripts import apply_ops
# reuse QueuedRunner pattern to feed pen_push JSON; assert make_apply_ops surfaces SHAs

def test_push_repos_surfaces_remote_sha():
    runner = _runner_returning_push({"acme/node": {"remote_ref":"pulse/apply/p1","remote_sha":"bbb","local_commit_sha":"ccc"}})
    ops = apply_ops.make_apply_ops(runner, "pen1", {"acme/node": ("package-lock.json",)})
    res = ops.push_repos("pulse/apply/p1")
    assert res["acme/node"]["remote_sha"] == "bbb"

def test_commit_repos_passes_bound_paths():
    # RecordingRunner captures the request file content; assert bound_paths reached the verb
    ...
```

```python
# test_pen_orchestrator.py — update the existing allow-listed block:
def test_allow_listed_reaches_pushed_with_landings():
    result = execute(plan_allow_listed, runner, read_repo_head=head_ok,
                     read_repo_changed_paths=changed_bound, apply_ops=recording_ops)
    assert result.state == "pushed"
    assert result.repo_landings["acme/node"]["remote_sha"]  # populated from push

def test_provision_observed_base_mismatch_blocks_before_push():
    # apply_ops.provision_branch returns observed_base_sha != expected -> stale base, no push
    ops = _ops_provision_returning({"acme/node": {"state":"ok","observed_base_sha":"DRIFTED"}})
    result = execute(plan_allow_listed_expecting("aaa"), runner, read_repo_head=head_ok,
                     read_repo_changed_paths=changed_bound, apply_ops=ops)
    assert result.state == "blocked" and "stale" in result.reason.lower()
    assert not any(c[0] == "push_repos" for c in ops.calls)
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** Evolve the protocol + result, and rewire `execute()`'s landing section (`pen_orchestrator.py:641–…`):

```python
# pen_orchestrator.py — ApplyOps protocol
class ApplyOps(Protocol):
    def provision_branch(self, branch, base_shas): ...
    def commit_repos(self, message, bound_paths): ...
    def push_repos(self, branch): ...
    def reset_repos(self, branch, expected_pushed_shas): ...

# PenRunResult — add field (frozen dataclass): repo_landings: dict = field(default_factory=dict)

# In execute() allow-listed landing: pass proposal.bound_paths to commit_repos,
# collect push_repos per-repo {local_commit_sha, remote_ref, remote_sha} into repo_landings,
# and on any push/commit failure call apply_ops.reset_repos(apply_branch, {repo: landing["local_commit_sha"]})
# before returning "failed" (deterministic CAS cleanup — spec §6 v1 policy).

# In execute() allow-listed provision handling (Task 3 also hardens the existing block at
# pen_orchestrator.py:582): a per-repo provision result must be state=="ok" AND its
# observed_base_sha must equal the expected base SHA — the remote-base CAS (spec §3.1).
# A mismatch is a stale-base 'blocked' (recovery: re-derive off current HEAD), never a push.
```

```python
# apply_ops.py
from __future__ import annotations
from lib.pulse.scripts import nave_adapter as na

def _by_repo(result):
    return {r["repo"]: r for r in result.get("repos", [])}

class _NaveApplyOps:
    def __init__(self, runner, pen_name, bound_paths_by_repo):
        self._r, self._pen, self._bp = runner, pen_name, bound_paths_by_repo
    def provision_branch(self, branch, base_shas):
        req = [{"repo": repo, "base_ref": self._base_ref(repo), "expected_base_sha": sha, "apply_ref": branch}
               for repo, sha in base_shas.items()]
        return _by_repo(na.pen_branch(self._r, self._pen, req))
    def commit_repos(self, message, bound_paths):
        req = [{"repo": repo, "bound_paths": list(bound_paths[repo])} for repo in bound_paths]
        return _by_repo(na.pen_commit(self._r, self._pen, req, message))
    def push_repos(self, branch):
        return _by_repo(na.pen_push(self._r, self._pen, branch))
    def reset_repos(self, branch, expected_pushed_shas):
        req = [{"repo": repo, "expected_pushed_sha": sha} for repo, sha in expected_pushed_shas.items()]
        return _by_repo(na.pen_reset(self._r, self._pen, branch, req))
    def _base_ref(self, repo): return self._base_refs[repo]  # injected by make_apply_ops

def make_apply_ops(runner, pen_name, bound_paths_by_repo, base_refs):
    ops = _NaveApplyOps(runner, pen_name, bound_paths_by_repo); ops._base_refs = base_refs; return ops
```

- [ ] **Step 4: Run, verify pass** (`test_apply_ops.py`, `test_pen_orchestrator.py`).
- [ ] **Step 5: Commit** — `feat: evolve ApplyOps/PenRunResult; bind landing to Nave verbs`.

---

### Task 4: Identity-hardened clone reader (exact repo→path map)

**Files:**
- Modify: `lib/pulse/scripts/pen_clone_reader.py` — `make_pen_clone_reader` accepts `clone_paths: dict[str,str]` (exact map from `pen_status --json`), validates coverage/uniqueness/remote-identity/branch/HEAD; keep the three reader callables
- Modify: `lib/pulse/scripts/tests/test_pen_clone_reader.py`

**Interfaces:**
- Consumes: `nave_adapter.pen_status` per-repo `clone_path` (Task 1).
- Produces (Task 8): `make_pen_clone_reader(clone_paths: dict[str,str], selection, *, expected_branch=None, expected_remotes=None) -> PenCloneReaders` — raises `PenCloneReaderError` on missing coverage, duplicate paths, `.git` absence, wrong `origin`, or (when given) wrong branch/HEAD.

- [ ] **Step 1: Write failing tests.**

```python
def test_reader_requires_exact_selection_coverage(tmp_path):
    with pytest.raises(PenCloneReaderError, match="coverage"):
        make_pen_clone_reader({"acme/a": str(tmp_path)}, selection=["acme/a", "acme/b"])

def test_reader_rejects_duplicate_paths(tmp_path):
    with pytest.raises(PenCloneReaderError, match="unique"):
        make_pen_clone_reader({"acme/a": str(tmp_path), "acme/b": str(tmp_path)}, selection=["acme/a","acme/b"])

def test_reader_verifies_origin_when_expected(tmp_path):
    repo = _init_git_with_origin(tmp_path, "https://github.com/acme/a.git")
    r = make_pen_clone_reader({"acme/a": str(repo)}, ["acme/a"], expected_remotes={"acme/a":"acme/a"})
    assert r.read_repo_head("acme/a")  # ok
    with pytest.raises(PenCloneReaderError, match="origin"):
        make_pen_clone_reader({"acme/a": str(repo)}, ["acme/a"], expected_remotes={"acme/a":"acme/other"})
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** the new signature (map-based), coverage/uniqueness checks, and an `origin` check via `git -C <path> remote get-url origin` normalized to `owner/name`; keep the three closures (`read_repo_head`/`read_repo_file`/`read_repo_changed_paths`) as-is but keyed off the provided map.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: identity-hardened pen clone reader (exact repo->path map)`.

---

### Task 5: Result contract — apply-status base/head + audit fields; repo-mutation audit fields

**Files:**
- Modify: `lib/pulse/scripts/validate_result.py` — `apply-status` gains required `recorded_proposal_id`, `proposal_digest`, `authorization_digest`, and nullable `intended_base`, `observed_base`, `expected_head_sha`, `observed_head_sha`; add cross-field rule (`applied` requires `observed_base` and `observed_head_sha`); `repo-mutation` gains required audit fields
- Modify: `lib/pulse/scripts/tests/test_validate_result.py`
- Modify: `lib/patterns/headless-contract.md` — document the new fields

**Interfaces:**
- Produces (Tasks 6, 8): `apply-status` schema with `{intended_base, observed_base, expected_head_sha, observed_head_sha, recorded_proposal_id, proposal_digest, authorization_digest}`.

- [ ] **Step 1: Write failing tests.**

```python
def test_apply_status_requires_audit_fields():
    doc = _min_apply_status(state="pushed")  # without audit fields
    errs = validate_result.validate(doc, "apply-status")
    assert any("proposal_digest" in e for e in errs)

def test_applied_requires_observed_base_and_head():
    doc = _min_apply_status(state="applied", merged_sha="m", pr_url="u", pushed_sha="p",
                            recorded_proposal_id="p1", proposal_digest="d", authorization_digest="a")
    errs = validate_result.validate(doc, "apply-status")
    assert any("observed_base" in e for e in errs)
    assert any("observed_head_sha" in e for e in errs)
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** — in the `apply-status` branch (`validate_result.py:654`) add the `_require(..., str)` audit-field checks and `_require_nullable(..., str)` for the four base/head fields, plus:

```python
if state == "applied":
    for f in ("observed_base", "observed_head_sha"):
        if data.get(f) is None:
            _err(errors, f"{f} must not be null when state is applied")
```

Add the three audit `_require(..., str)` calls to the `repo-mutation` branch (`:579`) as well.

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: apply-status base/head + audit fields in result contract`.

---

### Task 6: Merge gate verifies base AND head; per-repo reconcile; lease fencing

**Files:**
- Modify: `lib/pulse/scripts/apply_reconcile.py` — `GhCliOps.view_pr` requests `baseRefName,headRefOid`; `reconcile_apply` writes `observed_base`/`observed_head_sha` and re-reads GitHub on resume (never fabricates from a prior `applied`); accept a per-repo step id
- Modify: `lib/pulse/scripts/resolve_run.py` — `evaluate_merge_detected_gate` requires `observed_base == intended_base` and `observed_head_sha == expected_head_sha`; add `renew_lease`/ownership check
- Modify: `lib/pulse/scripts/tests/test_apply_reconcile.py`, `test_resolve_run.py`

**Interfaces:**
- Consumes: Task 5 apply-status fields.
- Produces (Task 8): `evaluate_merge_detected_gate(result_path)` — satisfied only on `applied` + base match + head match; `resolve_run.renew_lease(path, step_id, by)` that raises `LeaseError` if fenced out.

- [ ] **Step 1: Write failing tests.**

```python
def test_merge_gate_rejects_wrong_base():
    p = _write_apply_status(state="applied", merged_sha="m", intended_base="develop",
                            observed_base="main", expected_head_sha="h", observed_head_sha="h", ...)
    satisfied, detail = resolve_run.evaluate_merge_detected_gate(p)
    assert not satisfied and "base" in detail

def test_merge_gate_rejects_head_mismatch():
    p = _write_apply_status(state="applied", merged_sha="m", intended_base="develop",
                            observed_base="develop", expected_head_sha="h", observed_head_sha="OTHER", ...)
    satisfied, _ = resolve_run.evaluate_merge_detected_gate(p)
    assert not satisfied

def test_renew_lease_fences_out_original():
    resolve_run.acquire_lease(led, "s1", "actorA")
    resolve_run.acquire_lease(led, "s1", "actorB", ttl_minutes=0)  # steal after expiry
    with pytest.raises(resolve_run.LeaseError):
        resolve_run.renew_lease(led, "s1", "actorA")
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement:**

```python
# resolve_run.evaluate_merge_detected_gate — after the existing state/merged_sha checks:
if data.get("observed_base") != data.get("intended_base"):
    return False, f"base mismatch: observed {data.get('observed_base')!r} != intended {data.get('intended_base')!r}"
if data.get("observed_head_sha") != data.get("expected_head_sha"):
    return False, "merged head does not match expected pushed sha"

# resolve_run.renew_lease
def renew_lease(file_path, step_id, by):
    doc = load(file_path); step = find_step(doc, step_id); lease = step.get("lease")
    if not lease or lease.get("leased_by") != by:
        raise LeaseError(f"lease no longer held by {by}")
    step["lease"]["leased_at"] = now_iso(); save(file_path, doc); return step["lease"]
```

In `apply_reconcile`: add `baseRefName,headRefOid` to the `--json` field list (`apply_reconcile.py:96`), populate `observed_base`/`observed_head_sha` in `write_apply_status`, drop the "fabricate from existing applied" shortcut (`:300`) so resume re-reads via `gh_ops.view_pr`.

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: base+head merge gate, lease fencing, resume re-reads GitHub`.

---

### Task 7: Phase journal (crash-resumable per-repo boundaries)

**Files:**
- Create: `lib/pulse/scripts/apply_journal.py` — `Journal` persisting `{proposal_id, repo, phase, local_commit_sha?, remote_ref?, remote_sha?, apply_ref, base_ref, expected_base_sha}` per repo under the run-ledger dir
- Create: `lib/pulse/scripts/tests/test_apply_journal.py`

**Interfaces:**
- Produces (Task 8): `Journal(path)` with `record(repo, phase, **evidence)`, `phase_of(repo) -> str|None`, `evidence(repo) -> dict`, `PHASES = ("leased","pen_ready","branch_provisioned","transformed","validated","committed","pushed","pr_opened")`. Journal writes are atomic (temp-file + rename) and append-authoritative (last phase per repo wins).

- [ ] **Step 1: Write failing tests.**

```python
def test_journal_records_and_reads_phase(tmp_path):
    j = apply_journal.Journal(tmp_path / "j.yaml")
    j.record("acme/node", "branch_provisioned", apply_ref="pulse/apply/p1")
    assert j.phase_of("acme/node") == "branch_provisioned"
    j.record("acme/node", "pushed", remote_sha="bbb")
    assert j.phase_of("acme/node") == "pushed"
    assert j.evidence("acme/node")["remote_sha"] == "bbb"

def test_journal_survives_reload(tmp_path):
    p = tmp_path / "j.yaml"
    apply_journal.Journal(p).record("acme/node", "committed", local_commit_sha="ccc")
    assert apply_journal.Journal(p).phase_of("acme/node") == "committed"
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `Journal` with atomic YAML persistence keyed by repo.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: per-repo apply phase journal`.

---

### Task 8: `apply_driver.py` — assemble the lease-first, journaled Path A run

**Files:**
- Create: `lib/pulse/scripts/apply_driver.py` — the `uv run` CLI + `run_apply(...)`
- Create: `lib/pulse/scripts/tests/test_apply_driver.py`

**Interfaces:**
- Consumes: Tasks 1–7 (`pen_capabilities`, `rederive_proposal`, `load_authorization`/`authorize`, `make_apply_ops`, `make_pen_clone_reader`, `pen_orchestrator.execute`, `apply_reconcile.open_apply_pr`, `Journal`, `acquire_lease`/`renew_lease`).
- Produces (Task 10 skill): `run_apply(*, binding_ref, recorded_summary, authorization_path, ledger_path, step_id, actor_id, runner, gh_ops, result_path, workspace) -> dict` and `main()`.

- [ ] **Step 1: Write failing tests** — the acceptance-style flow with fixtures (see Task 11 for the full matrix; here, unit-level):

```python
def test_capability_handshake_fails_closed_on_old_nave(...):
    runner = _runner_without_verbs()
    out = apply_driver.run_apply(..., runner=runner)
    assert out["state"] == "blocked" and "protocol" in out["reason"].lower()

def test_unauthorized_proposal_blocks_before_mutation(...):
    out = apply_driver.run_apply(..., authorization_path=auth_denying, runner=recording)
    assert out["state"] == "blocked"
    assert recording.mutations == []  # no pen_branch/commit/push happened

def test_lease_acquired_before_any_mutation(...):
    # a competing lease holder makes run_apply raise/lease-block before pen_branch
    ...
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `run_apply`:

```python
def run_apply(*, binding_ref, recorded_summary, authorization_path, ledger_path, step_id,
              actor_id, runner, gh_ops, result_path, workspace, clone_root_reader=None):
    # 1. capability handshake — fail closed
    caps = nave_adapter.pen_capabilities(runner)
    if caps.get("adapter_state") != "ok" or caps.get("protocol_version") != nave_adapter.NAVE_APPLY_PROTOCOL:
        return _blocked_repo_mutation(result_path, recorded_summary, "nave capability/protocol mismatch")
    # 2. lease BEFORE any mutation
    resolve_run.acquire_lease(ledger_path, step_id, actor_id)
    journal = apply_journal.Journal(_journal_path(ledger_path, recorded_summary["proposal_id"]))
    # 3. re-derive off current heads (read via clone reader once pen exists) + authorize
    #    (pen_status gives clone paths -> reader -> read_repo_head)
    #    resolve intended base branch per repo from binding metadata (never default main)
    # 4. execute() with make_apply_ops + reader; journal each phase transition
    # 5. on 'pushed': write durable apply-status(pushed) BEFORE PR; open_apply_pr(pushed_sha, intended_base)
    # 6. write repo-mutation on any pre-push exit; always validate the result before returning
    ...
```

Write the durable `pushed` apply-status (with `expected_head_sha` = the verb-reported `remote_sha`, `intended_base`) **before** `open_apply_pr`, so a crash between push and PR loses nothing. Record `recorded_proposal_id`/`proposal_digest`/`authorization_digest` in every result.

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: apply_driver — lease-first journaled Path A run`.

---

### Task 9: `apply_advance_base.py` — F8 doc-blob finalizer (PR-gated, dual-CAS) + wire into reconcile

**Files:**
- Create: `lib/pulse/scripts/apply_advance_base.py` — `make_f8_advance_base(finalizer_record, gh_contents_ops)` returning `advance_base(repo, merged_sha) -> {"state": "ok"|"blocked"|"failed", "reason"?}`
- Modify: `lib/pulse/scripts/apply_reconcile.py` — the `reconcile` CLI builds the F8 `advance_base` from a persisted finalizer record instead of `advance_base=None`
- Create: `lib/pulse/scripts/tests/test_apply_advance_base.py`

**Interfaces:**
- Consumes: an injected `gh_contents_ops` (get file @ ref → `{content, file_sha}`, put file with `file_sha` CAS on a bookkeeping branch + open PR).
- Produces: `advance_base(repo, merged_sha)` satisfying `reconcile_apply`'s callback contract (`apply_reconcile.py:349`, returns `{"state":"ok"}`).

- [ ] **Step 1: Write failing tests.**

```python
def test_advance_blocks_on_semantic_cas_mismatch(fake_contents):
    fake_contents.set(doc_path, base_ref, frontmatter_base_blob="OLD_DIFFERENT", file_sha="fs1")
    adv = apply_advance_base.make_f8_advance_base(
        {"repo":"acme/docs","base_ref":"develop","doc_path":"d.md","expected_prior_blob":"EXPECTED"}, fake_contents)
    assert adv("acme/docs", "merge_sha")["state"] == "blocked"

def test_advance_ok_and_idempotent(fake_contents):
    fake_contents.set(doc_path, base_ref, frontmatter_base_blob="EXPECTED", file_sha="fs1")
    adv = apply_advance_base.make_f8_advance_base(
        {"repo":"acme/docs","base_ref":"develop","doc_path":"d.md","expected_prior_blob":"EXPECTED"}, fake_contents)
    assert adv("acme/docs", "merge_sha")["state"] == "ok"
    assert adv("acme/docs", "merge_sha")["state"] == "ok"  # no-op second time
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement:**

```python
def make_f8_advance_base(record, gh_contents_ops):
    def advance_base(repo, merged_sha):
        desired = gh_contents_ops.get_blob(record["repo"], record["doc_path"], merged_sha)     # new content @ merge
        current = gh_contents_ops.get(record["repo"], record["doc_path"], record["base_ref"])  # {sync_base_blob, file_sha}
        if current is None:
            return {"state": "failed", "reason": "document not found on base"}
        if current["sync_base_blob"] == desired["blob"]:
            return {"state": "ok"}  # already advanced — idempotent
        if current["sync_base_blob"] != record["expected_prior_blob"]:
            return {"state": "blocked", "reason": "semantic base CAS mismatch (base drifted)"}
        # semantic CAS ok -> land the frontmatter advance PR-gated with Contents file-SHA CAS
        return gh_contents_ops.put_via_pr(record["repo"], record["doc_path"], base_ref=record["base_ref"],
                                          new_base_blob=desired["blob"], if_file_sha=current["file_sha"],
                                          branch=f"pulse/apply-base/{record['proposal_id']}")
    return advance_base
```

Wire the `reconcile` subcommand (`apply_reconcile.main`) to load the persisted finalizer record and pass `advance_base=make_f8_advance_base(record, GhContentsCliOps())`. *Pin whether the advance folds into the apply patch or a separate bookkeeping PR by reading `plan_sync.finalize` during implementation — the CAS + PR-gated contract above is fixed either way.*

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat: F8 doc-blob finalizer (PR-gated dual-CAS) wired into reconcile`.

---

### Task 10: `gh-apply` skill (interactive trigger)

**Files:**
- Create: `skills/gh-apply/SKILL.md` — phase-structured skill wrapping `apply_driver` (open PR) + `apply_reconcile reconcile` (detect merge → advance base), PR-gated, confirm-before-apply
- Modify: `commands/hiivmind-pulse-gh.md` — route "apply <proposal>" intent to `gh-apply`

**Interfaces:** Consumes `apply_driver.run_apply` / `apply_reconcile` CLIs.

- [ ] **Step 1:** Write the skill following the existing skill shape (CONTEXT → RESOLVE → EXECUTE → REPORT), with an explicit STOP/confirm before the first mutation and a "reconcile later" second phase. No new code paths — orchestration only.
- [ ] **Step 2:** Add an intent line to the gateway command.
- [ ] **Step 3: Commit** — `feat: gh-apply interactive trigger skill`.

---

### Task 11: Neutral acceptance matrix + neutrality/import-boundary guards

**Files:**
- Modify: `lib/pulse/scripts/tests/test_apply_acceptance.py` — drive the **real `apply_driver`** against Nave-verb `--json` fixtures + injected `gh_ops`; assert the full contract
- Modify: `lib/pulse/scripts/tests/test_apply_neutrality.py` — extend the structural guard to `apply_driver`/`apply_advance_base`; flip the import-boundary test from "trio unreachable" to "single apply driver is the sole flag-bearing caller"
- Create fixtures under `tests/fixtures/nave_apply/` as needed

**Interfaces:** Consumes all prior tasks.

- [ ] **Step 1: Write the neutral matrix** — one `refresh-node-lockfile` run driven through `apply_driver.run_apply`: re-derivation + authorization (unauthorized refused; summary-identity mismatch refused), capability handshake (absent verb → blocked before mutation), lease ordering + fencing (competing actor blocked pre-mutation), phase-journal crash/resume (inject a failure after `committed`; resume reaches `pushed` without re-provisioning), pushed-SHA correctness (result `expected_head_sha` == verb `remote_sha`, not base), base+head merge-gate (wrong-base and wrong-head merges rejected), F8 finalizer dual-CAS + idempotency, and cross-repo contract malformed/missing-field/duplicate-path/extra-repo/nonzero-with-JSON fixtures. Log any mocked boundary (real `gh` merge) as a known coverage note.
- [ ] **Step 2: Write the neutrality/import-boundary guards** — AST import check over `apply_driver`, `apply_advance_base`, `apply_ops` (no `profile_dispatch`/claude-plugin imports; no `profile:claude-plugin` predicate); assert `apply_driver` is the only module passing commit/push/branch flags.
- [ ] **Step 3: Run full suite + `git diff --check`** — `uv run pytest -q` all green.
- [ ] **Step 4: Commit** — `test: gate apply-mode neutral end-to-end through the real driver`.

---

### Task 12: Close the propose-only doc debt (spec §9)

The merged code already supports allow-listed landing, but the contracts still say "propose-only".

**Files:**
- Modify: `lib/pulse/scripts/pen_orchestrator.py:21` (module docstring "propose-only, unconditionally") and `:136` (`PenPlan.request_push` "always forbidden") — describe the allow-listed landing branch while stating the `propose` control flow is unchanged
- Modify: `lib/patterns/repository-mutations.md` — C1's *Implementation* line from `nave_adapter.provision_apply_branch(...)` to the Nave `pen branch` verb; note the invariant text (per-proposal branch off `expected_shas[repo]`, pushes never target a base branch) is unchanged
- Modify: `lib/pulse/scripts/tests/test_pen_orchestrator.py` — a doc-consistency assertion is optional; this task is prose

- [ ] **Step 1:** Update the two docstrings in `pen_orchestrator.py` to reflect allow-listed landing (do not alter code).
- [ ] **Step 2:** Update `repository-mutations.md` C1's Implementation line to the Nave verb; leave the invariant text intact.
- [ ] **Step 3: Run** `uv run pytest lib/pulse/scripts/tests/test_pen_orchestrator.py -q` (green — no behavior change) and **commit** — `docs: retire propose-only wording; point C1 at the nave branch verb`.

---

## Follow-ups (out of this plan)

- **Nave fork plan** (`discreteds/nave`): implement the § 3 verbs to the Task 1 contract + Rust tests + the post-exec repo-control invariants + the "output actually lands" integration proof. **Blocks execution integration** — Tasks 1/8/11 test against fixtures until the fork lands.
- **Workspace enrollment PR** (`hiivmind/hiivmind-workspace` → main): the `ApplyAuthorization` policy + a real neutral proposal source (a `refresh-node-lockfile` binding), gated on the installed engine.
- **Deferred (spec §6/§10):** F5-marker advance, F9/F2 Path B emitter wiring, scheduled auto-apply + `allow`, independent per-repo multi-repo PRs, submodules/LFS.
