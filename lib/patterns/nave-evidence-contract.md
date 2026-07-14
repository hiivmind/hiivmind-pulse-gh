# Nave fleet evidence contract

Pulse consumes Nave through a Pulse-owned, versioned evidence contract. Nave
remains responsible for its local fleet projection; Pulse workflows do not
consume Nave cache files or human-readable command output directly.

The canonical workspace artifact is YAML at
`.hiivmind/github/fleet-evidence.yaml`. JSON is an equivalent wire encoding of
the same data model.

## Version 1

```yaml
contract_version: 1
provider:
  name: nave
  version: 0.4.0       # string or null when unavailable
  protocol: 1          # integer or null when unavailable
generated_at: "2026-07-13T10:00:00Z"
capability_status:
  state: available     # available | degraded | unavailable | unsupported
  capabilities:
    - search_json
repos:
  - repo: acme/api
    remote_sha: abc123 # string or null when unknown
    files:
      - pyproject.toml
    structural_signals:
      - has_pyproject
    validation:
      state: valid     # valid | invalid | unknown | unsupported | error
      errors: []
errors: []
```

All collection-level `errors` entries are strings. Repository names must be
unique. File paths and structural signals are sorted string lists in produced
snapshots, although the validator accepts any order. Structural signals record
facts only; they never assign authoritative repository profiles.

The version 1 normalizer may emit these factual signals:

| Signal | Evidence |
|---|---|
| `has_pyproject` | root `pyproject.toml` |
| `has_package_json` | root `package.json` |
| `has_documentation` | a README or path under `docs/` |
| `has_terraform` | a `.tf` file |
| `has_workflows` | a path under `.github/workflows/` |
| `has_claude_context` | root `CLAUDE.md` |
| `has_claude_plugin_manifest` | `.claude-plugin/plugin.json` |
| `has_skill` | a file named `SKILL.md` |

These are observations, not classifications. Profile selection is owned by
reviewed workspace metadata in the profile-dispatch layer.

The repository list is also observational. Nave indexes only repositories that
match its configured tracked paths, and its defaults do not cover every language
or repository type. Absence therefore means "not observed by this projection";
it is never authoritative fleet-membership evidence.

## Capability semantics

- `available`: all capabilities needed for the requested evidence run exist.
- `degraded`: useful evidence was produced, but one or more requested
  capabilities or lifecycle details were unavailable.
- `unavailable`: Nave could not be executed. This does not make repositories
  unhealthy.
- `unsupported`: Nave executed but its protocol is incompatible with this
  adapter.

For `unavailable` and `unsupported`, `provider.version` and
`provider.protocol` may be null and `repos` may be empty. This ensures tooling
absence is represented as evidence capability state, not as a false repository
failure.

## Validation

Run:

```text
uv run lib/pulse/scripts/validate_evidence.py FILE
```

Exit status is `0` for valid evidence, `1` for a parsed document that violates
the contract, and `2` for a missing or unparseable file.
