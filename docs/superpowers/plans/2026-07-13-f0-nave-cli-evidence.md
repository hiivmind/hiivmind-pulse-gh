# F0: Nave CLI Evidence Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-testable external Nave CLI adapter that produces stable Pulse-owned fleet evidence without assuming repository language or type.

**Architecture:** `nave_adapter.py` probes the installed binary, runs lifecycle commands, consumes JSON only from commands that currently support it, and normalizes output into versioned evidence documents. Nave's cache remains a local projection; Pulse workflows consume only the normalized contract. Missing or incompatible Nave produces typed capability status rather than repository failures.

**Tech Stack:** Python 3.10+ PEP 723, PyYAML, pytest, subprocess, `nave` CLI.

## Global Constraints

- Do not import Nave Rust/Python internals or parse its human-readable tables.
- Current Nave JSON commands: `search --json`, `build --json`, `check --json`, and pen list/show/status reports. `scan` and `pull` are exit-status lifecycle commands.
- All subprocess calls use argument arrays, `shell=False`, captured output, and a finite timeout.
- `PULSE_NAVE_FIXTURES` replaces subprocess execution with fixture JSON/exit records.
- Normalized evidence `contract_version` starts at **1** and is Pulse-owned.
- Missing Nave is `unavailable`; unsupported commands/protocols are `unsupported`.
- No repository or GitHub mutation is permitted in this phase.

---

### Task 1: Define and validate normalized Nave evidence

**Files:**
- Create: `lib/patterns/nave-evidence-contract.md`
- Create: `lib/pulse/scripts/validate_evidence.py`
- Create: `lib/pulse/scripts/tests/test_validate_evidence.py`

**Interfaces:**
- Produces CLI: `uv run lib/pulse/scripts/validate_evidence.py FILE`.
- Evidence root: `{contract_version, provider, generated_at, capability_status, repos, errors}`.
- Repo entry: `{repo, remote_sha, files, structural_signals, validation}`.

- [ ] **Step 1: Write the failing validator tests**

```python
def valid_evidence():
    return {
        "contract_version": 1,
        "provider": {"name": "nave", "version": "0.4.0", "protocol": 1},
        "generated_at": "2026-07-13T10:00:00Z",
        "capability_status": {"state": "available", "capabilities": ["search"]},
        "repos": [{"repo": "acme/api", "remote_sha": "abc",
                   "files": [], "structural_signals": [],
                   "validation": {"state": "valid", "errors": []}}],
        "errors": [],
    }

def test_valid_evidence(tmp_path):
    path = tmp_path / "evidence.yaml"
    path.write_text(yaml.safe_dump(valid_evidence()))
    assert run(path).returncode == 0

def test_rejects_unknown_capability_state(tmp_path):
    doc = valid_evidence()
    doc["capability_status"]["state"] = "missing-ish"
    path = tmp_path / "evidence.yaml"
    path.write_text(yaml.safe_dump(doc))
    assert run(path).returncode == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest lib/pulse/scripts/tests/test_validate_evidence.py -v`
Expected: FAIL because `validate_evidence.py` does not exist.

- [ ] **Step 3: Implement the validator**

```python
CAPABILITY_STATES = {"available", "degraded", "unavailable", "unsupported"}
VALIDATION_STATES = {"valid", "invalid", "unknown", "unsupported", "error"}

def require(data, key, typ, errors, ctx=""):
    if key not in data:
        errors.append(f"missing required key: {ctx}{key}")
        return None
    if not isinstance(data[key], typ):
        errors.append(f"wrong type for {ctx}{key}: expected {typ.__name__}")
        return None
    return data[key]
```

Validate every root and repo field, reject duplicate repo names, require quoted-string timestamps, and return exit 0 valid, 1 invalid, 2 missing/unparseable.

- [ ] **Step 4: Run focused and full tests**

Run: `uv run pytest lib/pulse/scripts/tests/test_validate_evidence.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/patterns/nave-evidence-contract.md lib/pulse/scripts/validate_evidence.py lib/pulse/scripts/tests/test_validate_evidence.py
git commit -m "feat: define normalized fleet evidence contract"
```

---

### Task 2: Implement Nave probing and safe command execution

**Files:**
- Create: `lib/pulse/scripts/nave_adapter.py`
- Create: `lib/pulse/scripts/tests/test_nave_adapter.py`
- Create: `lib/pulse/scripts/tests/fixtures/nave/probe/version.txt`
- Create: `lib/pulse/scripts/tests/fixtures/nave/probe/help.txt`

**Interfaces:**
- `NaveRunner(binary="nave", fixtures=None, timeout=120).run(args) -> Completed`.
- `probe(runner) -> {available, version, protocol, capabilities, errors}`.
- CLI: `nave_adapter.py probe [--binary PATH]` prints JSON.

- [ ] **Step 1: Write failing probe tests**

```python
def test_probe_detects_current_capabilities(fixture_runner):
    out = nave_adapter.probe(fixture_runner)
    assert out["available"] is True
    assert out["protocol"] == 1
    assert {"scan", "pull", "search_json", "build_json", "check_json", "pen"} <= set(out["capabilities"])

def test_probe_missing_binary_is_unavailable():
    out = nave_adapter.probe(nave_adapter.NaveRunner(binary="definitely-no-nave"))
    assert out["available"] is False
    assert out["state"] == "unavailable"
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py -v`
Expected: FAIL because module is absent.

- [ ] **Step 3: Implement runner and capability probe**

```python
@dataclass
class Completed:
    returncode: int
    stdout: str
    stderr: str

class NaveRunner:
    def run(self, args: list[str]) -> Completed:
        if self.fixtures:
            return load_fixture(self.fixtures, args)
        try:
            p = subprocess.run([self.binary, *args], capture_output=True,
                               text=True, timeout=self.timeout, shell=False)
            return Completed(p.returncode, p.stdout, p.stderr)
        except FileNotFoundError:
            return Completed(127, "", f"binary not found: {self.binary}")
        except subprocess.TimeoutExpired:
            return Completed(124, "", f"timeout after {self.timeout}s")
```

Probe help text for command presence and command-specific `--help` for `--json`; do not infer JSON support merely from the command name.

- [ ] **Step 4: Verify green and commit**

Run: `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py -v`
Expected: all PASS.

```bash
git add lib/pulse/scripts/nave_adapter.py lib/pulse/scripts/tests/test_nave_adapter.py lib/pulse/scripts/tests/fixtures/nave
git commit -m "feat: probe Nave CLI capabilities safely"
```

---

### Task 3: Add lifecycle and JSON analysis commands

**Files:**
- Modify: `lib/pulse/scripts/nave_adapter.py`
- Modify: `lib/pulse/scripts/tests/test_nave_adapter.py`
- Create: `lib/pulse/scripts/tests/fixtures/nave/search.json`
- Create: `lib/pulse/scripts/tests/fixtures/nave/build.json`
- Create: `lib/pulse/scripts/tests/fixtures/nave/check.json`

**Interfaces:**
- `scan(runner, user=None, prune=False) -> LifecycleResult`.
- `pull(runner) -> LifecycleResult`.
- `search(runner, terms, matches=()) -> dict`.
- `build(runner, file_filter, where=(), matches=()) -> dict`.
- `check(runner) -> dict`.

- [ ] **Step 1: Add failing command-construction tests**

```python
def test_scan_never_adds_nonexistent_json_flag(recording_runner):
    nave_adapter.scan(recording_runner, user="acme", prune=True)
    assert recording_runner.calls == [["scan", "--user", "acme", "--prune"]]

def test_search_requires_json(recording_runner):
    nave_adapter.search(recording_runner, ["workflow:pytest"])
    assert recording_runner.calls == [["search", "--json", "workflow:pytest"]]
```

- [ ] **Step 2: Verify red**, then implement exact argument-array builders and strict JSON decoding. A zero exit with invalid JSON becomes adapter state `error`; non-zero lifecycle commands preserve stderr without attempting to parse tables.

- [ ] **Step 3: Run tests**

Run: `uv run pytest lib/pulse/scripts/tests/test_nave_adapter.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit** with `feat: invoke Nave fleet analysis commands`.

---

### Task 4: Normalize Nave output into FleetEvidenceSnapshot

**Files:**
- Create: `lib/pulse/scripts/evidence_snapshot.py`
- Create: `lib/pulse/scripts/tests/test_evidence_snapshot.py`
- Modify: `lib/patterns/nave-evidence-contract.md`

**Interfaces:**
- CLI: `evidence_snapshot.py --search FILE --build FILE --check FILE --provider FILE`.
- `normalize(search, build, check, provider, generated_at) -> dict`.
- Output validates with Task 1.

- [ ] **Step 1: Write failing normalization tests** for mixed repositories: Python, Node, documentation-only, Terraform, and a malformed config. Assert deterministic repo ordering and no inferred profile labels.
- [ ] **Step 2: Verify red** with focused pytest.
- [ ] **Step 3: Implement normalization**. Structural signals may be factual (`has_pyproject`, `has_package_json`, `has_workflows`) but must not emit authoritative `profiles`.
- [ ] **Step 4: Validate output**

Run: `uv run pytest lib/pulse/scripts/tests/test_evidence_snapshot.py -v`
Expected: all PASS.

Run: `uv run lib/pulse/scripts/validate_evidence.py lib/pulse/scripts/tests/fixtures/nave/evidence-valid.yaml`
Expected: exit 0.

- [ ] **Step 5: Commit** with `feat: normalize Nave fleet evidence`.

---

### Task 5: Add the headless evidence skill

**Files:**
- Create: `skills/gh-fleet-evidence-headless/SKILL.md`
- Modify: `templates/workspace-gitignore.template`
- Modify: `README.md`
- Modify: `SKILL.md`

**Interfaces:**
- Inputs: `workspace_path`, optional `nave_binary`, `mode`.
- Output: `{workspace}/.hiivmind/github/fleet-evidence.yaml`.

- [ ] **Step 1: Write the skill** with phases PROBE → SCAN → PULL → ANALYZE → NORMALIZE → VALIDATE. If probe fails, write a valid degraded evidence file and return success with capability warning.
- [ ] **Step 2: Add ignore entries** for local evidence/cache result files; never ignore authoritative workspace profiles.
- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests PASS.

- [ ] **Step 4: Commit** with `feat: add Nave-backed fleet evidence skill`.

---

### Task 6: Upstream protocol follow-up

**Files:**
- Create: `docs/backlogs/2026-07-13-nave-json-lifecycle-protocol.md`

**Interfaces:**
- Consumes: observed Nave CLI capabilities from Tasks 2–3.
- Produces: an upstream-facing protocol proposal; no runtime interface changes in Pulse.

- [ ] **Step 1: Record a focused upstream proposal** for `nave capabilities --json`, `nave scan --json`, and `nave pull --json`, including example schemas and the guarantee that human output remains unchanged.
- [ ] **Step 2: Record the current integration behavior**: Pulse relies only on exit status for scan/pull and therefore cannot report per-repository lifecycle outcomes until Nave adds machine output.
- [ ] **Step 3: Commit** with `docs: propose Nave lifecycle JSON protocol`.
