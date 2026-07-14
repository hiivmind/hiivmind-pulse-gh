# Nave machine-readable lifecycle protocol proposal

**Status:** upstream proposal

**Observed Nave source:** local checkout of `lmmx/nave`, package version `0.0.8`

**Consumer:** hiivmind-pulse-gh external CLI adapter

## Problem

Nave already exposes useful JSON for structural analysis:

- `search --json`
- `build --json`
- `check --json`
- `pen list --json`, `pen show --json`, and `pen status --json`

The fleet lifecycle remains human-only. `scan` and `pull` expose process status
and logs but no stable per-repository result. Consumers must probe help text for
capabilities, rely only on lifecycle exit codes, and cannot report which
repositories were discovered, excluded, refreshed, skipped, or failed.

Coverage is also opaque. Nave indexes only repositories matching configured
`scan.tracked_paths`; its current defaults cover Python, Rust, pre-commit,
Dependabot, and GitHub Actions paths, not arbitrary Node, documentation-only, or
Terraform repositories. A consumer therefore cannot safely interpret an absent
repository without knowing the effective tracked paths and exclusion policy.

## Compatibility goals

1. Keep existing human output and exit behavior unchanged unless `--json` is
   explicitly supplied.
2. Version machine contracts independently from the Nave package version.
3. Emit one JSON document to stdout; keep diagnostics on stderr.
4. Report partial per-repository failures in the document and retain a non-zero
   exit when the command did not fully succeed.
5. Never require consumers to read Nave cache internals.

## 1. `nave capabilities --json`

Provide one cheap, side-effect-free negotiation endpoint:

```json
{
  "protocol_version": 1,
  "nave_version": "0.0.8",
  "commands": {
    "scan": {"json": true, "schema_version": 1},
    "pull": {"json": true, "schema_version": 1},
    "search": {"json": true, "schema_version": 1},
    "build": {"json": true, "schema_version": 1},
    "check": {"json": true, "schema_version": 1},
    "pen": {"json_reports": ["list", "show", "status"]}
  },
  "effective_config": {
    "github": {
      "repo_type": "owner",
      "private_repositories": false
    },
    "scan": {
      "tracked_paths": [
        "pyproject.toml",
        "Cargo.toml",
        ".github/workflows/*.yml"
      ],
      "case_insensitive": true,
      "exclude_forks": true
    }
  }
}
```

The effective configuration is essential evidence scope, not incidental
configuration. If exposing another section later becomes sensitive, keep this
allowlisted projection rather than returning the full config.

## 2. `nave scan --json`

Suggested schema:

```json
{
  "schema_version": 1,
  "user": "acme",
  "mode": "full",
  "auth_mode": "gh-cli",
  "started_at": "2026-07-13T10:00:00Z",
  "completed_at": "2026-07-13T10:00:03Z",
  "summary": {
    "repos_seen": 42,
    "repos_indexed": 30,
    "tracked_files": 118,
    "excluded": 12,
    "pruned": 2,
    "failed": 1
  },
  "repos": [
    {
      "repo": "acme/api",
      "state": "indexed",
      "remote_sha": "abc123",
      "tracked_files": ["pyproject.toml", ".github/workflows/ci.yml"],
      "matched_patterns": ["pyproject.toml", ".github/workflows/*.yml"],
      "errors": []
    },
    {
      "repo": "acme/docs",
      "state": "excluded",
      "remote_sha": "def456",
      "tracked_files": [],
      "matched_patterns": [],
      "exclusion_reason": "no_tracked_paths",
      "errors": []
    }
  ],
  "errors": [
    {"repo": "acme/legacy", "code": "tree_fetch_failed", "message": "..."}
  ]
}
```

Recommended repository states are `indexed | excluded | pruned | error`.
Recommended exclusion codes include `archived`, `fork`, `no_tracked_paths`, and
`visibility_unsupported`. Stable codes let consumers reason without parsing
messages.

## 3. `nave pull --json`

Suggested schema:

```json
{
  "schema_version": 1,
  "started_at": "2026-07-13T10:00:04Z",
  "completed_at": "2026-07-13T10:00:08Z",
  "summary": {
    "cloned": 3,
    "updated": 20,
    "recloned": 1,
    "skipped": 6,
    "failed": 1,
    "sha_mismatches": 0
  },
  "repos": [
    {
      "repo": "acme/api",
      "state": "updated",
      "requested_sha": "abc123",
      "checkout_sha": "abc123",
      "tracked_files": ["pyproject.toml"],
      "errors": []
    }
  ],
  "errors": [
    {"repo": "acme/legacy", "code": "clone_failed", "message": "..."}
  ]
}
```

Recommended repository states mirror Nave's existing internal actions:
`cloned | updated | recloned | skipped | error`.

## Exit and output guarantees

- `0`: command completed with no repository errors.
- non-zero: invocation or one-or-more repository operations failed; when JSON
  mode initialized successfully, stdout still contains the complete report.
- stdout contains JSON only in `--json` mode.
- stderr may contain logs and diagnostics but is never part of the schema.
- timestamps are RFC 3339 strings in UTC.
- additions within a schema version are backward-compatible; removals,
  renames, or semantic changes increment `schema_version`.

## Current Pulse integration behavior

Until this protocol exists, Pulse:

- probes command-specific help for JSON flags;
- uses only exit status for `scan` and `pull`;
- cannot expose per-repository lifecycle outcomes;
- consumes JSON only from `search`, `build`, `check`, and supported pen reports;
- normalizes Nave output behind its own versioned evidence contract;
- treats the evidence repository list as a partial structural projection, never
  authoritative fleet membership;
- represents missing or incompatible Nave as capability state rather than
  repository failure.

Once `capabilities --json` is available, Pulse can stop parsing help text. Once
scan/pull reports are available, it can populate `remote_sha`, expose lifecycle
coverage, and distinguish excluded repositories from unobserved fleet members
without reading Nave's cache.
