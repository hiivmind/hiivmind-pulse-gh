---
name: gh-fleet-evidence-headless
description: >
  Use when a scheduler, profile detector, or fleet workflow needs a zero-prompt structural
  evidence snapshot from the external Nave CLI, including when Nave may be missing or only a
  cached analysis should run. Trigger phrases: "fleet evidence", "Nave evidence", "scan fleet
  structure", "headless repository evidence".
---

# Headless Fleet Evidence

Produce profile-neutral structural evidence through the Pulse-owned Nave
adapter. Zero prompts: use explicit inputs and always write a validator-compatible
evidence file when `workspace_path` is usable.

## Interface

Inputs:

- `workspace_path` (required): absolute workspace root containing
  `.hiivmind/github/`.
- `nave_binary` (optional): Nave executable path; default `nave`.
- `mode` (optional): `refresh | analyze`; default `refresh`.

Output: `{workspace_path}/.hiivmind/github/fleet-evidence.yaml`.

## Boundaries

- Evidence is a Nave-tracked structural projection, **not authoritative fleet
  membership**. A repository absent from the snapshot is **not observed**; it is
  not proven outside the fleet. Workspace/GitHub membership is resolved elsewhere.
- Structural signals are facts, never profile assignments.
- Do not mutate repositories. Do not mutate GitHub. This skill writes only the
  local evidence artifact under `.hiivmind/github/`; Nave owns its external cache.
- Do not parse Nave tables. Use JSON only through `nave_adapter.py`.
- Preserve `PULSE_NAVE_FIXTURES` when set; the adapter uses it instead of subprocesses.

`{PLUGIN_ROOT}` is the plugin root. Set:

```text
CONFIG_DIR = {workspace_path}/.hiivmind/github
EVIDENCE = CONFIG_DIR/fleet-evidence.yaml
NAVE_BINARY = {nave_binary input, default "nave"}
MODE = {mode input, default "refresh"}
TMP = a fresh temporary directory outside the workspace
```

Reject an absent `workspace_path`, a missing `CONFIG_DIR`, or a mode other than
`refresh | analyze`. Do not discover a workspace by walking parents.

## Phase 1: PROBE

Write the provider report:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/nave_adapter.py" probe \
  --binary "$NAVE_BINARY" > "$TMP/provider.json"
```

If `available` is false, write empty JSON objects to `$TMP/search.json`,
`$TMP/build.json`, and `$TMP/check.json`, then continue directly to NORMALIZE.
The resulting evidence must contain:

```yaml
capability_status:
  state: unavailable
repos: []
```

Validate it and return success with the capability warning. Missing tooling is
not a repository failure.

If any of `build_json` or `check_json` is absent, record a provider error for
each missing capability, set provider state to `degraded`, write an adapter-error
object for the corresponding report, and continue. Do not invent unsupported
flags. `search_json` is probed for downstream workflows but is not required for
the baseline inventory because Nave search requires a content predicate.

## Phase 2: SCAN

Skip this and PULL when `MODE=analyze`. Otherwise run:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/nave_adapter.py" scan \
  --binary "$NAVE_BINARY" --no-interaction > "$TMP/scan.json"
```

Do not add `--json` to the Nave lifecycle command. A non-zero exit appends
`scan failed: <stderr>` to provider errors and changes an `available` provider
state to `degraded`; continue so an existing cache can still provide evidence.

## Phase 3: PULL

In `refresh` mode run:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/nave_adapter.py" pull \
  --binary "$NAVE_BINARY" > "$TMP/pull.json"
```

Handle failure like SCAN. Nave currently exposes only lifecycle exit status, so
never claim per-repository scan or pull outcomes.

## Phase 4: ANALYZE

Create `$TMP/search.json` as
`{"repos":[],"repos_considered":0,"repos_without_checkout":0}`. This explicitly
means “no content predicate requested,” not “empty fleet.”

For supported capabilities, run:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/nave_adapter.py" build \
  --binary "$NAVE_BINARY" > "$TMP/build.json"
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/nave_adapter.py" check \
  --binary "$NAVE_BINARY" > "$TMP/check.json"
```

The adapter prints a typed error object when valid JSON is unavailable. Preserve
that object; NORMALIZE converts it into degraded capability evidence. Do not
replace it with a repository failure.

## Phase 5: NORMALIZE

Capture one quoted UTC timestamp and write a temporary snapshot:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/evidence_snapshot.py" \
  --provider "$TMP/provider.json" \
  --search "$TMP/search.json" \
  --build "$TMP/build.json" \
  --check "$TMP/check.json" \
  --generated-at "$RUN_AT" > "$TMP/fleet-evidence.yaml"
```

Never add `profiles` or turn missing repositories into negative evidence.

## Phase 6: VALIDATE

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/validate_evidence.py" \
  "$TMP/fleet-evidence.yaml"
```

Exit `0`: atomically replace `EVIDENCE`, then print
`fleet-evidence: state=<capability state> repos=<count> path=<EVIDENCE>`.

Exit non-zero: report validator stderr verbatim and do not replace an existing
valid artifact. This is a skill/integration error, not repository health.

## Quick reference

| Situation | Result |
|---|---|
| Nave missing | valid `unavailable` evidence, return success |
| Lifecycle failure | degraded provider error, analyze existing cache |
| JSON capability absent | typed adapter error, no inferred repo failure |
| Repo absent from evidence | not observed; no membership conclusion |
| Validator failure | preserve previous artifact and report skill bug |

Common mistakes are treating Nave’s default tracked paths as fleet membership,
adding nonexistent JSON flags to lifecycle commands, or assigning repository
profiles from structural signals. All violate this skill’s evidence boundary.
