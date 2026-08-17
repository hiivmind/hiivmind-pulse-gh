> **ARCHIVED 2026-08-17.** Implementation complete — kept for historical
> reference only. See
> `docs/superpowers/archive/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
> §8.9 for original phase tracking.
>
> ---

# P1 — Result Contract + Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the machine-readable result contract (`contract_version: 1`, kinds `status`, `healthcheck`, `refresh`, `workflow-run`) and its validator — the foundation every headless skill (P3) and orchestrator (P5) consumes.

**Architecture:** Port the corpus headless-contract pattern (`hiivmind-corpus/lib/corpus/patterns/headless-contract.md` + `validate_result.py`) with pulse-specific kinds and one structural addition: a required `actor:` block on every kind (spec I4 — M:M humans/profiles/machines). This is the repo's first Python: corpus conventions copied exactly (PEP 723 self-contained scripts, `uv run`, root `pyproject.toml` for dev/test only, pytest via subprocess).

**Tech Stack:** Python ≥3.10 (PEP 723 + pyyaml), uv, pytest, Markdown patterns.

**Spec:** `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` — Part 5.1, §P1 (P1.1–P1.3). Also folds in the P7.1 *interim* CLAUDE.md staleness fix the spec says to do "immediately after P0".

## Global Constraints

- **Reusable-first:** no `hiivmind` hardcoding; schemas use `workspace: <login>` for any org/user.
- **Contract version:** `contract_version: 1` (int). Additive optional fields never bump it; renamed/removed/retyped fields do.
- **Required on ALL kinds** (spec I4): `contract_version`, `kind`, `workspace`, `run_at`, `actor: {gh_login, machine, mode: interactive|scheduled}`, `errors: []`.
- **Result files are per-machine transients:** `{workspace_root}/.hiivmind/github/{kind}-result.yaml`, covered by the `*-result.yaml` line in `templates/workspace-gitignore.template` (landed in P0). Skills must still verify coverage before writing (corpus rule).
- **Exit codes** (corpus convention): 0 valid, 1 invalid (errors on stderr, one per line), 2 file missing/unparseable.
- **D4:** the validator takes explicit paths; it never discovers a workspace.
- Commit after every task. Version bump to `4.5.0` happens once, in Task 4.

---

### Task 1: `lib/patterns/headless-contract.md`

**Files:**
- Create: `lib/patterns/headless-contract.md`

**Interfaces:**
- Produces: the four kind schemas below — Task 2's fixtures and Task 3's validator implement them field-for-field. P3 skills and the P5 scheduler consume this document as the single source of truth.

- [ ] **Step 1: Write the pattern document**

Write `lib/patterns/headless-contract.md` with exactly this content:

````markdown
# Pattern: Headless Result Contract

Headless skills communicate with orchestrators through **result files written
to disk**, not by prose parsing. A printed `---headless-result` block is
retained for human-readable logs only — orchestrators MUST read the file.

## File locations

| Kind | File | Default path |
|------|------|--------------|
| status | status-result.yaml | `{workspace_root}/.hiivmind/github/status-result.yaml` |
| healthcheck | healthcheck-result.yaml | `{workspace_root}/.hiivmind/github/healthcheck-result.yaml` |
| refresh | refresh-result.yaml | `{workspace_root}/.hiivmind/github/refresh-result.yaml` |
| workflow-run | workflow-run-result.yaml | `{workspace_root}/.hiivmind/github/workflow-run-result.yaml` |

Result files are per-machine transient run artifacts (never authority — see
`workspace-detection.md` § Multi-machine topology). The workspace repo's
`.gitignore` covers them via `*-result.yaml`; skills MUST verify that line
exists before writing (append if missing). Orchestrators treat a file as
consumed after parsing; a subsequent run overwrites it.

## Versioning

`contract_version` is a required integer. Current version: **1**. Consumers
MUST reject versions they don't support (`validate_result.py` does). Additive
optional fields do not bump the version; renamed/removed/retyped fields do.
New kinds are backward-compatible: consumers reject only unknown versions,
not kinds they were not asked to validate.

## Common required fields (all kinds)

```yaml
contract_version: 1                   # int, required
kind: status | healthcheck | refresh | workflow-run
workspace: <login>                    # str, required — org/user login
run_at: <ISO 8601 timestamp>          # str, required
actor:                                # required on ALL kinds (I4)
  gh_login: <gh auth identity>        # str, required
  machine: <hostname or alias>        # str, required
  mode: interactive | scheduled       # required enum
errors: [<str>, ...]                  # list, required (may be empty)
```

The `actor:` block exists because the team is M:M across humans, GitHub
profiles, and machines: identity-sensitive logic resolves against the
*recorded* actor, never against whatever profile the reading machine holds.

## Validation

    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py status-result.yaml --kind status
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py healthcheck-result.yaml --kind healthcheck
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py refresh-result.yaml --kind refresh
    uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py workflow-run-result.yaml --kind workflow-run

Orchestrators validate before consuming and treat exit 1/2 as a failed run
(report, do not commit). Exit codes: 0 valid, 1 invalid (errors on stderr),
2 file missing/unparseable.

Skills write the file **even on partial failure or early abort**: a missing
result file is indistinguishable from a crashed run.

## Schemas

### status-result.yaml (written by gh-status-headless, P3.1)

```yaml
contract_version: 1
kind: status
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
sections:                             # list, required (may be empty)
  - id: <freshness section id>        # str, required (workspace, projects, ...)
    stale: <bool>                     # required
    last_checked: <ISO 8601 or null>  # required key, nullable
rate_limit_remaining: <int or null>   # required key, nullable
refresh_needed: <bool>                # required — any section stale
errors: []
```

### healthcheck-result.yaml (written by gh-healthcheck-headless, P3.2)

Per-check shape mirrors the committed `healthcheck.yaml` so the transient
result and the governance record stay structurally aligned.

```yaml
contract_version: 1
kind: healthcheck
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
repos:                                # list, required (may be empty)
  - repo: <owner/name>                # str, required
    score: <number>                   # int or float, required
    total: <int>                      # required — checks counted (excl. unknown/dismissed)
    grade: A | B | C | D | F          # required enum
    checks:                           # dict, required: check_id -> result
      <check_id>:
        status: pass | warn | fail | unknown | dismissed   # required enum
        detail: <str>                 # required
        data: {}                      # dict, required (may be empty)
        inferred: <bool>              # optional — true when LLM judgment produced it
aggregate:                            # dict, required
  score: <number>
  total: <int>
  grade: A | B | C | D | F
errors: []
```

### refresh-result.yaml (written by gh-refresh-headless, P3.3)

```yaml
contract_version: 1
kind: refresh
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
sections:                             # list, required (may be empty)
  - id: <freshness section id>        # str, required
    status: refreshed | skipped | failed   # required enum
config_updated: <bool>                # required — any catalog changed on disk
errors: []
```

### workflow-run-result.yaml (written by the executor in headless mode, P4.3)

```yaml
contract_version: 1
kind: workflow-run
workspace: <login>
run_at: <ISO 8601>
actor: { gh_login: <str>, machine: <str>, mode: <enum> }
workflow: <workflow name>             # str, required
repos: [<owner/name>, ...]            # list of str, required (may be empty)
run_id: <{date}-{gh_login}-{n}>       # str, required — actor-embedded, collision-free
outcome: success | failure | skipped-cooldown | aborted    # required enum
findings:                             # list, required (may be empty) — typed data, not prose
  - kind: <str>                       # required, e.g. ci-failure
    repo: <owner/name>                # str, required
    severity: low | medium | high     # required enum
    detail: <str>                     # optional human-readable
    ref: { type: <str>, id: <any>, url: <str> }   # optional locator
    classification: <str>             # optional INFER output
    inferred: <bool>                  # optional — LLM judgment flagged as such
proposed_actions: [<str>, ...]        # list, required — mutations a headless run declined
asks_recorded: [<str>, ...]           # list, required — ASKs that had no user
errors: []
```

`inferred: true`, `proposed_actions`, and `asks_recorded` are the items
needing human judgment — orchestrators surface them under a "Needs attention"
heading (P5.4) instead of burying them in logs.

## Related patterns

- `workspace-detection.md` — workspace root, multi-machine topology, D4
- `hiivmind-corpus/lib/corpus/patterns/headless-contract.md` — the ported original
````

- [ ] **Step 2: Commit**

```bash
git add lib/patterns/headless-contract.md
git commit -m "docs(patterns): headless result contract v1 (status, healthcheck, refresh, workflow-run)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Python scaffolding, fixtures, failing tests (P1.2 scaffold + P1.3)

**Files:**
- Create: `pyproject.toml`
- Create: `lib/pulse/scripts/tests/fixtures/{status,healthcheck,refresh,workflow-run}-{valid,invalid}.yaml` (8 files)
- Create: `lib/pulse/scripts/tests/test_validate_result.py`
- Create: `lib/pulse/scripts/tests/__init__.py` (empty), `lib/pulse/scripts/tests/fixtures/` dir

**Interfaces:**
- Consumes: schemas from Task 1.
- Produces: `pyproject.toml` at repo root (P2 reuses it — its `testpaths` covers all of `lib/pulse/scripts/tests`); fixture naming convention `{kind}-{valid|invalid}.yaml`.

- [ ] **Step 1: Write `pyproject.toml`** (corpus conventions, trimmed to what pulse needs)

```toml
[project]
name = "hiivmind-pulse-gh-dev"
version = "0.0.0"
description = "Dev/test environment for hiivmind-pulse-gh plugin scripts (the scripts themselves are PEP 723 self-contained)"
requires-python = ">=3.10"
dependencies = []

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pyyaml>=6.0",
]

[tool.pytest.ini_options]
testpaths = ["lib/pulse/scripts/tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Write the eight fixtures**

`lib/pulse/scripts/tests/fixtures/status-valid.yaml`:

```yaml
contract_version: 1
kind: status
workspace: testorg
run_at: "2026-07-10T09:00:00Z"
actor:
  gh_login: octocat
  machine: mba-m4
  mode: scheduled
sections:
  - id: workspace
    stale: false
    last_checked: "2026-07-10T08:00:00Z"
  - id: projects
    stale: true
    last_checked: null
rate_limit_remaining: 4980
refresh_needed: true
errors: []
```

`lib/pulse/scripts/tests/fixtures/status-invalid.yaml` (missing `actor`, bad `refresh_needed` type, section missing `stale`):

```yaml
contract_version: 1
kind: status
workspace: testorg
run_at: "2026-07-10T09:00:00Z"
sections:
  - id: workspace
    last_checked: null
rate_limit_remaining: 4980
refresh_needed: "yes"
errors: []
```

`lib/pulse/scripts/tests/fixtures/healthcheck-valid.yaml`:

```yaml
contract_version: 1
kind: healthcheck
workspace: testorg
run_at: "2026-07-10T09:05:00Z"
actor:
  gh_login: octocat
  machine: mba-m4
  mode: interactive
repos:
  - repo: testorg/widget
    score: 7.5
    total: 9
    grade: B
    checks:
      branch_protection:
        status: warn
        detail: "main: 1 required review, enforce_admins: no"
        data: {}
      releases:
        status: fail
        detail: "No releases or tags"
        data: {}
      issue_triage:
        status: pass
        detail: "Bug: bug, Priority: P1"
        data: {}
        inferred: false
aggregate:
  score: 7.5
  total: 9
  grade: B
errors: []
```

`lib/pulse/scripts/tests/fixtures/healthcheck-invalid.yaml` (bad check status enum, missing aggregate, check missing `data`):

```yaml
contract_version: 1
kind: healthcheck
workspace: testorg
run_at: "2026-07-10T09:05:00Z"
actor:
  gh_login: octocat
  machine: mba-m4
  mode: interactive
repos:
  - repo: testorg/widget
    score: 7
    total: 9
    grade: B
    checks:
      branch_protection:
        status: passed
        detail: "ok"
errors: []
```

`lib/pulse/scripts/tests/fixtures/refresh-valid.yaml`:

```yaml
contract_version: 1
kind: refresh
workspace: testorg
run_at: "2026-07-10T09:10:00Z"
actor:
  gh_login: octocat
  machine: nuc-lab
  mode: scheduled
sections:
  - id: projects
    status: refreshed
  - id: teams
    status: skipped
config_updated: true
errors: []
```

`lib/pulse/scripts/tests/fixtures/refresh-invalid.yaml` (bad section status, `config_updated` missing, unsupported version):

```yaml
contract_version: 2
kind: refresh
workspace: testorg
run_at: "2026-07-10T09:10:00Z"
actor:
  gh_login: octocat
  machine: nuc-lab
  mode: scheduled
sections:
  - id: projects
    status: done
errors: []
```

`lib/pulse/scripts/tests/fixtures/workflow-run-valid.yaml`:

```yaml
contract_version: 1
kind: workflow-run
workspace: testorg
run_at: "2026-07-10T09:15:00Z"
actor:
  gh_login: octocat
  machine: mba-m4
  mode: scheduled
workflow: ci-monitor
repos: [testorg/widget]
run_id: 2026-07-10-octocat-1
outcome: success
findings:
  - kind: ci-failure
    repo: testorg/widget
    severity: high
    detail: "run 12345 failed on main"
    ref: { type: run, id: 12345, url: "https://github.com/testorg/widget/actions/runs/12345" }
    classification: flaky
    inferred: true
proposed_actions: ["rerun workflow 12345"]
asks_recorded: []
errors: []
```

`lib/pulse/scripts/tests/fixtures/workflow-run-invalid.yaml` (kind mismatch fodder is covered in tests; this one has bad outcome, finding missing severity, `proposed_actions` wrong type):

```yaml
contract_version: 1
kind: workflow-run
workspace: testorg
run_at: "2026-07-10T09:15:00Z"
actor:
  gh_login: octocat
  machine: mba-m4
  mode: scheduled
workflow: ci-monitor
repos: [testorg/widget]
run_id: 2026-07-10-octocat-1
outcome: partial
findings:
  - kind: ci-failure
    repo: testorg/widget
proposed_actions: "rerun"
asks_recorded: []
errors: []
```

- [ ] **Step 3: Write the failing tests**

`lib/pulse/scripts/tests/test_validate_result.py`:

```python
"""Tests for validate_result.py — pulse headless result contract validation."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = "lib/pulse/scripts/validate_result.py"
FIXTURES = Path("lib/pulse/scripts/tests/fixtures")
KINDS = ["status", "healthcheck", "refresh", "workflow-run"]


def run_validator(path, kind):
    return subprocess.run(
        [sys.executable, SCRIPT, str(path), "--kind", kind],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_valid_fixture_passes(kind):
    r = run_validator(FIXTURES / f"{kind}-valid.yaml", kind)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("kind", KINDS)
def test_invalid_fixture_fails_with_errors(kind):
    r = run_validator(FIXTURES / f"{kind}-invalid.yaml", kind)
    assert r.returncode == 1
    assert r.stderr.strip(), "expected one error per line on stderr"


def test_kind_mismatch(tmp_path):
    r = run_validator(FIXTURES / "status-valid.yaml", "refresh")
    assert r.returncode == 1
    assert "kind mismatch" in r.stderr


def test_missing_actor_reported():
    r = run_validator(FIXTURES / "status-invalid.yaml", "status")
    assert "actor" in r.stderr


def test_missing_file_exit_2(tmp_path):
    r = run_validator(tmp_path / "nope.yaml", "status")
    assert r.returncode == 2


def test_unparseable_yaml_exit_2(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("kind: [unclosed")
    r = run_validator(bad, "status")
    assert r.returncode == 2
```

Also create the empty `lib/pulse/scripts/tests/__init__.py`.

- [ ] **Step 4: Run tests to verify they fail for the right reason**

```bash
uv sync
uv run pytest lib/pulse/scripts/tests/test_validate_result.py -v
```

Expected: all tests FAIL/ERROR because `lib/pulse/scripts/validate_result.py` does not exist yet (exit code 2 from Python "No such file", not assertion passes).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml lib/pulse/scripts/tests/
git commit -m "test(pulse): scaffolding, contract fixtures, failing validator tests

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `validate_result.py` (P1.2)

**Files:**
- Create: `lib/pulse/scripts/validate_result.py`

**Interfaces:**
- Consumes: Task 1 schemas, Task 2 fixtures/tests.
- Produces: `uv run {PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py <file> --kind <k>` → exit 0/1/2. P3 skills and P5 orchestrators call exactly this.

- [ ] **Step 1: Write the validator**

`lib/pulse/scripts/validate_result.py`:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Validate a headless result file against the pulse result contract.

Usage: validate_result.py <result.yaml> --kind status|healthcheck|refresh|workflow-run

See lib/patterns/headless-contract.md for the schemas.

Exit codes:
  0 - valid
  1 - invalid (errors on stderr, one per line)
  2 - file missing or unparseable
"""
import argparse
import sys
from pathlib import Path

SUPPORTED_VERSIONS = {1}
ACTOR_MODES = {"interactive", "scheduled"}
CHECK_STATUSES = {"pass", "warn", "fail", "unknown", "dismissed"}
GRADES = {"A", "B", "C", "D", "F"}
REFRESH_SECTION_STATUSES = {"refreshed", "skipped", "failed"}
OUTCOMES = {"success", "failure", "skipped-cooldown", "aborted"}
SEVERITIES = {"low", "medium", "high"}


def _err(errors, msg):
    errors.append(msg)


def _require(data, key, types, errors, ctx=""):
    label = f"{ctx}{key}"
    if key not in data:
        _err(errors, f"missing required key: {label}")
        return None
    if not isinstance(data[key], types):
        _err(errors, f"wrong type for {label}: expected {types}, got {type(data[key]).__name__}")
        return None
    return data[key]


def _require_nullable(data, key, types, errors, ctx=""):
    """Key must be present; value may be of `types` or None."""
    label = f"{ctx}{key}"
    if key not in data:
        _err(errors, f"missing required key: {label}")
        return
    if data[key] is not None and not isinstance(data[key], types):
        _err(errors, f"wrong type for {label}: expected {types} or null, got {type(data[key]).__name__}")


def _require_enum(data, key, allowed, errors, ctx=""):
    val = _require(data, key, str, errors, ctx=ctx)
    if val is not None and val not in allowed:
        _err(errors, f"{ctx}{key} invalid: {val}")
    return val


def _require_actor(data, errors):
    actor = _require(data, "actor", dict, errors)
    if actor is None:
        return
    _require(actor, "gh_login", str, errors, ctx="actor.")
    _require(actor, "machine", str, errors, ctx="actor.")
    _require_enum(actor, "mode", ACTOR_MODES, errors, ctx="actor.")


def _validate_grade_block(block, errors, ctx):
    _require(block, "score", (int, float), errors, ctx=ctx)
    _require(block, "total", int, errors, ctx=ctx)
    _require_enum(block, "grade", GRADES, errors, ctx=ctx)


def validate(data, kind: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["result is not a mapping"]

    version = _require(data, "contract_version", int, errors)
    if version is not None and version not in SUPPORTED_VERSIONS:
        _err(errors, f"unsupported contract_version: {version}")

    got_kind = _require(data, "kind", str, errors)
    if got_kind is not None and got_kind != kind:
        _err(errors, f"kind mismatch: expected {kind}, got {got_kind}")

    _require(data, "workspace", str, errors)
    _require(data, "run_at", str, errors)
    _require_actor(data, errors)
    _require(data, "errors", list, errors)

    if kind == "status":
        sections = _require(data, "sections", list, errors)
        for i, s in enumerate(sections or []):
            if not isinstance(s, dict):
                _err(errors, f"sections[{i}] is not a mapping")
                continue
            ctx = f"sections[{i}]."
            _require(s, "id", str, errors, ctx=ctx)
            _require(s, "stale", bool, errors, ctx=ctx)
            _require_nullable(s, "last_checked", str, errors, ctx=ctx)
        _require_nullable(data, "rate_limit_remaining", int, errors)
        _require(data, "refresh_needed", bool, errors)

    elif kind == "healthcheck":
        repos = _require(data, "repos", list, errors)
        for i, r in enumerate(repos or []):
            if not isinstance(r, dict):
                _err(errors, f"repos[{i}] is not a mapping")
                continue
            ctx = f"repos[{i}]."
            _require(r, "repo", str, errors, ctx=ctx)
            _require(r, "score", (int, float), errors, ctx=ctx)
            _require(r, "total", int, errors, ctx=ctx)
            _require_enum(r, "grade", GRADES, errors, ctx=ctx)
            checks = _require(r, "checks", dict, errors, ctx=ctx)
            for cid, c in (checks or {}).items():
                cctx = f"{ctx}checks.{cid}."
                if not isinstance(c, dict):
                    _err(errors, f"{ctx}checks.{cid} is not a mapping")
                    continue
                _require_enum(c, "status", CHECK_STATUSES, errors, ctx=cctx)
                _require(c, "detail", str, errors, ctx=cctx)
                _require(c, "data", dict, errors, ctx=cctx)
                if "inferred" in c and not isinstance(c["inferred"], bool):
                    _err(errors, f"wrong type for {cctx}inferred: expected bool")
        agg = _require(data, "aggregate", dict, errors)
        if agg is not None:
            _validate_grade_block(agg, errors, ctx="aggregate.")

    elif kind == "refresh":
        sections = _require(data, "sections", list, errors)
        for i, s in enumerate(sections or []):
            if not isinstance(s, dict):
                _err(errors, f"sections[{i}] is not a mapping")
                continue
            ctx = f"sections[{i}]."
            _require(s, "id", str, errors, ctx=ctx)
            _require_enum(s, "status", REFRESH_SECTION_STATUSES, errors, ctx=ctx)
        _require(data, "config_updated", bool, errors)

    elif kind == "workflow-run":
        _require(data, "workflow", str, errors)
        repos = _require(data, "repos", list, errors)
        for i, r in enumerate(repos or []):
            if not isinstance(r, str):
                _err(errors, f"repos[{i}] is not a string")
        _require(data, "run_id", str, errors)
        _require_enum(data, "outcome", OUTCOMES, errors)
        findings = _require(data, "findings", list, errors)
        for i, f in enumerate(findings or []):
            if not isinstance(f, dict):
                _err(errors, f"findings[{i}] is not a mapping")
                continue
            ctx = f"findings[{i}]."
            _require(f, "kind", str, errors, ctx=ctx)
            _require(f, "repo", str, errors, ctx=ctx)
            _require_enum(f, "severity", SEVERITIES, errors, ctx=ctx)
            if "inferred" in f and not isinstance(f["inferred"], bool):
                _err(errors, f"wrong type for {ctx}inferred: expected bool")
            if "ref" in f and not isinstance(f["ref"], dict):
                _err(errors, f"wrong type for {ctx}ref: expected mapping")
        _require(data, "proposed_actions", list, errors)
        _require(data, "asks_recorded", list, errors)

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate a headless result file")
    parser.add_argument("file", help="Path to result YAML file")
    parser.add_argument("--kind", required=True,
                        choices=["status", "healthcheck", "refresh", "workflow-run"])
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    import yaml
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        print(f"error: unparseable YAML: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate(data, args.kind)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the test suite to verify it passes**

```bash
uv run pytest lib/pulse/scripts/tests/test_validate_result.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 3: Verify the P1 exit criterion directly (uv run against all eight fixtures)**

```bash
for k in status healthcheck refresh workflow-run; do
  uv run lib/pulse/scripts/validate_result.py "lib/pulse/scripts/tests/fixtures/${k}-valid.yaml" --kind "$k" \
    && echo "PASS $k valid"
  uv run lib/pulse/scripts/validate_result.py "lib/pulse/scripts/tests/fixtures/${k}-invalid.yaml" --kind "$k" 2>/dev/null \
    || echo "PASS $k invalid rejected ($?)"
done
```

Expected: eight `PASS ...` lines (invalid ones report exit code 1).

- [ ] **Step 4: Commit**

```bash
git add lib/pulse/scripts/validate_result.py
git commit -m "feat(pulse): validate_result.py for headless contract v1

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: CLAUDE.md interim alignment (P7.1 stale fix) + spec close-out

**Files:**
- Modify: `CLAUDE.md` (Skills table, config-location claims, file structure)
- Modify: `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` (§P1 checkboxes, §8.9 table, P7.1 note)
- Modify: `.claude-plugin/plugin.json` (version)

This is the *interim* fix the spec flags as misleading today — the full P7.1 rewrite still happens after P6.

- [ ] **Step 1: Fix the Skills table in CLAUDE.md**

Replace the `## Skills` table rows:

```markdown
| Skill | Purpose | Structure |
|-------|---------|-----------|
| `gh-init` | First-time workspace setup | 6 phases (~150 lines) |
| `gh-refresh` | Sync config with GitHub | 6 phases (~200 lines) |
| `gh-operations` | Execute GitHub operations | 5 phases (~270 lines) |
| `gh-healthcheck` | Repository governance audit | 5 phases (~270 lines) |
```

with:

```markdown
| Skill | Purpose |
|-------|---------|
| `gh-init` | First-time workspace setup (workspace-root placement, workspace repo init) |
| `gh-refresh` | Sync config with GitHub |
| `gh-operations` | Execute GitHub operations |
| `gh-healthcheck` | Repository governance audit |
| `gh-heartbeat` | Present/execute heartbeat-triggered workflows |
| `gh-workflows` | Manage and run workflow definitions |
| `gh-discover` | Discover workspace resources |
```

- [ ] **Step 2: Fix the config-location claims**

In CLAUDE.md, replace the line:

```markdown
**Rule of thumb:** If the repo has a `.hiivmind/github/config.yaml`, route ALL GitHub operations through this plugin.
```

with:

```markdown
**Rule of thumb:** If a workspace root resolves above cwd (a `.hiivmind/github/config.yaml` with a top-level `workspace:` section, at any parent depth — see `lib/patterns/workspace-detection.md`), route ALL GitHub operations through this plugin.
```

And replace the `### Team Config` heading line:

```markdown
### Team Config: `.hiivmind/github/config.yaml`

Shared across team, committed to git:
```

with:

```markdown
### Team Config: `{workspace_root}/.hiivmind/github/config.yaml`

The workspace root is typically the parent folder of an org's repo clones;
`.hiivmind/github/` there is its own small git repo shared by the team
(remote `{login}-workspace`). Per-machine transients are gitignored:
```

Also in the "When to Bypass the Plugin" list, change item 1 from
`1. Workspace is NOT initialized (no \`.hiivmind/github/config.yaml\`)` to
`1. Workspace is NOT initialized (no workspace root resolvable above cwd)`.

- [ ] **Step 3: Add hooks + Python scripts to the File Structure block**

In CLAUDE.md's `## File Structure` code block, after the `commands/` entry add:

```
├── hooks/
│   └── heartbeat.sh                      # SessionStart poll (workspace-root walk-up)
```

and inside `lib/` add:

```
│   ├── pulse/
│   │   └── scripts/                      # Deterministic Python (PEP 723, uv run)
│   │       └── validate_result.py        # Headless result contract validator
```

and under `skills/` list all seven skills (gh-init, gh-refresh, gh-operations, gh-healthcheck, gh-heartbeat, gh-workflows, gh-discover).

- [ ] **Step 4: Spec close-out**

In the spec:
1. Tick P1.1, P1.2, P1.3 checkboxes to `- [x]`.
2. §8.9 table: P1 row → `✅ done` with date 2026-07-10.
3. In P7.1's line, change `(Do the stale-skills fix immediately after P0 — it misleads today.)` to `(Stale-skills interim fix landed with P1; full rewrite after P6.)`

- [ ] **Step 5: Bump plugin version**

In `.claude-plugin/plugin.json`: `"version": "4.4.0"` → `"version": "4.5.0"`.

- [ ] **Step 6: Verify and commit**

```bash
uv run pytest -q                      # full suite still green
grep -c "gh-heartbeat" CLAUDE.md      # expect >= 1
git add CLAUDE.md docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md .claude-plugin/plugin.json
git commit -m "docs: interim CLAUDE.md alignment; mark P1 complete; bump to 4.5.0

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Deliverable → Task map (spec coverage)

| Spec deliverable | Task |
|------------------|------|
| P1.1 headless-contract.md (4 kinds, actor block, gitignore/consumption rules) | Task 1 |
| P1.2 validate_result.py + pyproject/tests scaffolding | Tasks 2 (scaffold) + 3 (implement) |
| P1.3 valid+invalid fixture per kind, used by tests | Task 2 |
| Exit criteria (uv run passes/fails correctly on all eight fixtures) | Task 3 Step 3 |
| P7.1 interim stale-CLAUDE.md fix ("immediately after P0") | Task 4 |
