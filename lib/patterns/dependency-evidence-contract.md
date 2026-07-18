# Dependency evidence contract

Pulse's F4 dependency-evidence workflow consumes Nave's protocol-2
`materialize` command through a Pulse-owned, versioned contract. Unlike the
[Nave fleet evidence contract](nave-evidence-contract.md), this document is
**transient**: it carries raw file `content` fetched from repositories, so it
must never be committed, logged, echoed to a terminal, or folded into any
committed artifact (`deps-snapshot.json`, a healthcheck result, or any
`*-result.yaml`). F4 reads this document, derives a content-free dependency
snapshot from it, and deletes the document. Nothing downstream of F4 may
retain raw `content`.

Minimum Nave version: TBD (pinned in Pre-F4 Task 6)

## Storage

The normalized document lives under a run-specific temporary directory
created with mode `0700` (`lib/pulse/scripts/dependency_evidence.py:
secure_run_dir`), and the document itself is written with mode `0600`
(`write_evidence`). Only the current user can read either. The run directory
and its contents must be deleted once F4 has emitted its content-free
snapshot — do not leave `dependency-evidence.json` on disk across sessions.

## Version 1

```yaml
contract_version: 1
provider:
  name: nave
  version: 0.9.0    # string or null when unavailable
  protocol: 2       # must be 2; materialize requires protocol-2 capabilities
generated_at: "2026-07-18T10:00:00Z"
request_sha256: <64-char lowercase hex>   # sha256 of the canonical MaterializeRequest
repos:
  - repo: acme/api
    ref_name: main
    tree_sha: <40- or 64-char hex, or null>
    tree_complete: true
    artifacts:
      - selector_id: python.pyproject
        path: pyproject.toml
        blob_sha: <40- or 64-char hex, or null>
        size_bytes: 1234
        state: found       # found | absent | unresolved | too_large | binary | unsupported | error
        encoding: utf-8     # required (and must be utf-8) when state is found; null otherwise
        content: "..."      # required string when state is found; forbidden (null/absent) otherwise
        detail: ""
errors: []
```

Top-level keys are exact: `contract_version`, `provider`, `generated_at`,
`request_sha256`, `repos`, `errors` — no extras. Each repo entry has exactly
`repo`, `ref_name`, `tree_sha`, `tree_complete`, `artifacts`. Each artifact
entry has exactly `selector_id`, `path`, `blob_sha`, `size_bytes`, `state`,
`encoding`, `content`, `detail`.

`provider.protocol` must be `2`; a protocol-1 (or any other) value is a
contract violation, since `materialize` is a protocol-2-only capability (see
[Protocol 2](nave-evidence-contract.md#protocol-2)).

Repository names are unique across `repos` and match `owner/name`. Within a
repo, `selector_id` is unique, and non-null `path` values are unique.
`size_bytes` is always a finite non-negative integer. `blob_sha` and
`tree_sha` are hex strings (40- or 64-char) or null.

`content` is present (a string) if and only if `state == found`, and in that
case `encoding` must be `utf-8`. For every other state, `content` must be
absent or null — carrying content on a non-`found` artifact is a contract
violation, not just noise, because it would leak fetched file bytes into
evidence that outlives the F4 run.

## Request hashing

`request_sha256` is the SHA-256 hex digest of the `MaterializeRequest` JSON
serialized with sorted keys and no incidental whitespace
(`json.dumps(request, sort_keys=True, separators=(",", ":"))`). Two logically
identical requests — regardless of key order at any nesting level — hash
identically. This lets consumers correlate a normalized evidence document
with the exact selector set that produced it without re-serializing the
request.

## Deterministic ordering

`repos` is sorted by `repo`. Within a repo, `artifacts` is sorted by
`(path is None, path, selector_id)` — artifacts with a real path sort before
artifacts with a null path, mirroring the ordering Nave itself uses on the
wire.

## Validation

Run:

```text
uv run lib/pulse/scripts/validate_dependency_evidence.py FILE
```

Exit status is `0` for valid evidence, `1` for a parsed document that
violates the contract, and `2` for a missing or unparseable file. Validation
errors are plain strings on stderr, one per line, and **never** include an
artifact's `content` value — only structural facts (key names, states,
formats) are reported.
