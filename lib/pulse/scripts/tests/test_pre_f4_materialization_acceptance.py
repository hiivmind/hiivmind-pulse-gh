"""Cross-repository acceptance gate for Pre-F4 dependency-evidence materialization.

Proves the whole pipeline end-to-end via the offline fixture runner (no
network, no real Nave process):

1. Nave protocol v1 still builds F0 structural evidence (materialize did not
   regress the existing evidence path).
2. Nave protocol v2 materializes an exact manifest artifact AND a selector
   that fans out to multiple globbed lock artifacts, and both survive
   normalization with content, correct selector_ids, and deterministic
   ordering.
3. A truncated tree (`tree_complete: false`) with no selector match leaves
   the artifact `state` as `unresolved`, never `absent` — absence is only
   authoritative over a complete tree.
4. The normalized v2 document validates cleanly against the dependency
   evidence contract.

Also asserts no Pulse production script reads Nave's cache/checkout
internals directly — Pulse must consume only the CLI JSON contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.pulse.scripts import dependency_evidence as de
from lib.pulse.scripts import evidence_snapshot
from lib.pulse.scripts import nave_adapter
from lib.pulse.scripts import validate_dependency_evidence as vde
from lib.pulse.scripts import validate_evidence


FIXTURES_V1 = Path("lib/pulse/scripts/tests/fixtures/nave")
GENERATED_AT = "2026-07-18T12:00:00Z"


def _v1_provider() -> dict:
    return {
        "available": True,
        "state": "available",
        "version": "0.0.8",
        "protocol": 1,
        "capabilities": ["scan", "pull", "search_json", "build_json", "check_json", "pen"],
        "errors": [],
    }


# --- 1. Protocol v1 still builds F0 evidence -------------------------------


def test_protocol_v1_still_builds_f0_evidence():
    runner = nave_adapter.NaveRunner(fixtures=FIXTURES_V1)

    probed = nave_adapter.probe(runner)
    assert probed["available"] is True
    assert probed["protocol"] == 1
    assert "materialize_json" not in probed["capabilities"]

    search = nave_adapter.search(runner, ["anything"])
    build = nave_adapter.build(runner, None)
    check = nave_adapter.check(runner)

    doc = evidence_snapshot.normalize(search, build, check, probed, GENERATED_AT)

    assert validate_evidence.validate(doc) == []
    assert doc["repos"]
    assert any(r["repo"] == "acme/api" for r in doc["repos"])


# --- 2/3/4. Protocol v2 materialization fixtures ----------------------------


def _write_v2_probe_dir(base: Path) -> Path:
    probe_dir = base / "probe"
    probe_dir.mkdir()
    (probe_dir / "version.txt").write_text("nave 0.9.0\n")
    (probe_dir / "help.txt").write_text(
        "Commands:\n"
        "  scan\n"
        "  pull\n"
        "  search\n"
        "  build\n"
        "  check\n"
        "  pen\n"
        "  materialize\n"
    )
    for command in ("search", "build", "check"):
        (probe_dir / f"{command}-help.txt").write_text("Options:\n  --json\n")
    (probe_dir / "pen-help.txt").write_text("Commands:\n  list\n  show\n  status\n")
    for action in ("list", "show", "status"):
        (probe_dir / f"pen-{action}-help.txt").write_text("Options:\n  --json\n")
    (probe_dir / "materialize-help.txt").write_text(
        "Options:\n  --request <PATH>\n  --json\n"
    )
    return probe_dir


def _write_v2_materialize_fixture(base: Path) -> None:
    """A repo with an exact manifest, a globbed multi-lock selector, and a
    truncated-tree repo whose selector matches nothing."""
    report = {
        "contract_version": 1,
        "repos": [
            {
                "repo": "acme/api",
                "ref_name": "main",
                "tree_sha": "a" * 40,
                "tree_complete": True,
                "artifacts": [
                    {
                        "selector_id": "python.pyproject",
                        "path": "pyproject.toml",
                        "blob_sha": "b" * 40,
                        "size_bytes": 128,
                        "state": "found",
                        "encoding": "utf-8",
                        "content": "[project]\nname = \"api\"\n",
                        "detail": None,
                    },
                    {
                        "selector_id": "python.lockfiles",
                        "path": "uv.lock",
                        "blob_sha": "c" * 40,
                        "size_bytes": 256,
                        "state": "found",
                        "encoding": "utf-8",
                        "content": "version = 1\n",
                        "detail": None,
                    },
                    {
                        "selector_id": "python.lockfiles",
                        "path": "requirements.lock",
                        "blob_sha": "d" * 40,
                        "size_bytes": 64,
                        "state": "found",
                        "encoding": "utf-8",
                        "content": "requests==2.32.0\n",
                        "detail": None,
                    },
                ],
            },
            {
                "repo": "acme/partial",
                "ref_name": "main",
                "tree_sha": None,
                "tree_complete": False,
                "artifacts": [
                    {
                        "selector_id": "python.lockfiles",
                        "path": None,
                        "blob_sha": None,
                        "size_bytes": None,
                        "state": "unresolved",
                        "encoding": None,
                        "content": None,
                        "detail": "tree scan was truncated before this selector could be resolved",
                    },
                ],
            },
        ],
        "errors": [],
    }
    (base / "materialize.json").write_text(json.dumps(report))


def _v2_provider(version: str) -> dict:
    return {"name": "nave", "version": version, "protocol": 2}


def test_protocol_v2_materializes_exact_manifest_and_globbed_locks(tmp_path):
    _write_v2_probe_dir(tmp_path)
    _write_v2_materialize_fixture(tmp_path)
    runner = nave_adapter.NaveRunner(fixtures=tmp_path)

    probed = nave_adapter.probe(runner)
    assert probed["protocol"] == 2
    assert "materialize_json" in probed["capabilities"]

    request = de.build_request(
        ["acme/api", "acme/partial"],
        [
            {"id": "python.pyproject", "pattern": "pyproject.toml"},
            {"id": "python.lockfiles", "pattern": "*.lock"},
        ],
    )
    digest = de.request_sha256(request)
    raw = nave_adapter.materialize(runner, json.dumps(request))
    assert raw.get("adapter_state") != "error"

    doc = de.normalize(raw, _v2_provider(probed["version"]), GENERATED_AT, digest)

    api = next(r for r in doc["repos"] if r["repo"] == "acme/api")
    manifest = next(a for a in api["artifacts"] if a["selector_id"] == "python.pyproject")
    assert manifest["path"] == "pyproject.toml"
    assert manifest["state"] == "found"
    assert manifest["content"] == "[project]\nname = \"api\"\n"
    assert manifest["encoding"] == "utf-8"

    locks = [a for a in api["artifacts"] if a["selector_id"] == "python.lockfiles"]
    assert len(locks) == 2
    assert {lock["path"] for lock in locks} == {"uv.lock", "requirements.lock"}
    assert all(lock["state"] == "found" for lock in locks)
    assert all(lock["content"] is not None for lock in locks)
    # Deterministic ordering: sorted by (path is None, path, selector_id).
    assert [lock["path"] for lock in locks] == ["requirements.lock", "uv.lock"]


def test_truncated_tree_absence_remains_unresolved(tmp_path):
    _write_v2_probe_dir(tmp_path)
    _write_v2_materialize_fixture(tmp_path)
    runner = nave_adapter.NaveRunner(fixtures=tmp_path)
    probed = nave_adapter.probe(runner)

    request = de.build_request(
        ["acme/api", "acme/partial"],
        [{"id": "python.lockfiles", "pattern": "*.lock"}],
    )
    digest = de.request_sha256(request)
    raw = nave_adapter.materialize(runner, json.dumps(request))
    doc = de.normalize(raw, _v2_provider(probed["version"]), GENERATED_AT, digest)

    partial = next(r for r in doc["repos"] if r["repo"] == "acme/partial")
    assert partial["tree_complete"] is False
    assert len(partial["artifacts"]) == 1
    artifact = partial["artifacts"][0]
    assert artifact["state"] == "unresolved"
    assert artifact["state"] != "absent"
    assert artifact["content"] is None
    assert artifact["path"] is None


def test_protocol_v2_normalized_document_validates(tmp_path):
    _write_v2_probe_dir(tmp_path)
    _write_v2_materialize_fixture(tmp_path)
    runner = nave_adapter.NaveRunner(fixtures=tmp_path)
    probed = nave_adapter.probe(runner)
    assert probed["protocol"] == 2

    request = de.build_request(
        ["acme/api", "acme/partial"],
        [
            {"id": "python.pyproject", "pattern": "pyproject.toml"},
            {"id": "python.lockfiles", "pattern": "*.lock"},
        ],
    )
    digest = de.request_sha256(request)
    raw = nave_adapter.materialize(runner, json.dumps(request))
    doc = de.normalize(raw, _v2_provider(probed["version"]), GENERATED_AT, digest)

    assert doc["provider"]["protocol"] == 2
    assert vde.validate(doc) == []


# --- Source scan: no Nave cache/checkout internals in production code ------


FORBIDDEN_SUBSTRINGS = [
    "~/.cache/nave",
    ".cache/nave",
    "tracked.toml",
    "/nave/checkouts",
]


def test_no_pulse_production_code_references_nave_cache_or_checkout_internals():
    """Pulse must consume only Nave's CLI JSON contract, never its cache
    layout or tracked-config file. Scans lib/pulse/scripts/*.py excluding the
    tests/ subtree."""
    scripts_root = Path("lib/pulse/scripts")
    production_files = sorted(
        p
        for p in scripts_root.glob("*.py")
        if p.is_file()
    )
    assert production_files, "expected to find production scripts to scan"

    violations = []
    for path in production_files:
        text = path.read_text()
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in text:
                violations.append(f"{path}: contains forbidden substring {needle!r}")

    assert violations == [], "\n".join(violations)
