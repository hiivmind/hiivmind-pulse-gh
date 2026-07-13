# Fleet Profile Dispatch and Nave Integration

**Date:** 2026-07-13  
**Status:** Proposed  
**Companion design:** `2026-07-10-lockstep-bindings-and-target-workflows-design.md`  
**Related audit:** `docs/superpowers/audits/2026-07-13-fleet-scope-audit.md`

## Purpose

`hiivmind-pulse-gh` manages a heterogeneous GitHub repository fleet. A Claude
plugin repository, Python library, Node application, service, infrastructure
repository, and documentation repository should not receive identical checks or
weights. They should share fleet mechanics while using explicit repository
profiles, scorecards, and evidence adapters.

This design adds a profile-dispatch layer and uses the external `nave` CLI as
the fleet evidence and repository-file transaction subsystem. It prevents the
plugin's own structure (`skills/`, `CLAUDE.md`, `.claude-plugin/`, corpus
templates) from becoming an accidental universal repository contract.

## Design principles

1. **Generic shell, explicit policy.** Workflows own discovery, snapshots,
   findings, reconciliation, attribution, and result recording. Profiles own
   what a repository should contain.
2. **Evidence before classification.** Repository facts are collected before a
   profile is proposed. A proposal never silently changes authoritative profile
   metadata or scoring.
3. **Capability absence is not failure.** Checks that do not apply are
   `not_applicable`; unsupported adapters are visible as coverage gaps.
4. **Nave is an external evidence provider.** Pulse invokes the installed nave
   CLI through a versioned JSON adapter; pulse does not import nave internals.
5. **One mutation boundary per state type.** Nave pens handle repository-file
   changes. Pulse handles GitHub API mutations and workspace metadata PRs.
6. **Dogfood is an overlay.** Plugin, marketplace, generated-skill, and
   `CLAUDE.md` workflows are explicit profiles, not core fleet defaults.

## Layered architecture

```text
GitHub fleet
    │
    ▼
Nave evidence provider
  scan → pull → search/build/check
    │
    ▼
RepoEvidenceSnapshot
    │
    ├── profile proposal (non-authoritative)
    ├── generic workflow dispatch
    └── profile/adapter workflow dispatch
            │
            ▼
      scorecard evaluation
            │
            ▼
      findings/actions/asks
            │
      ┌─────┴─────┐
      ▼           ▼
 nave pen     Pulse GitHub mutation
 repo files   issues/projects/releases
      │           │
      └─────┬─────┘
            ▼
       result contract
```

### Pulse core

Pulse remains responsible for workspace discovery, heartbeat/poll scheduling,
workflow execution, binding records, result contracts, actor attribution,
mutation policy, GitHub API operations, and durable workspace metadata.

### Nave subsystem

Nave is responsible for the remote fleet projection, configurable tracked paths,
sparse evidence checkout, structural search, anti-unification/profile signals,
schema validation, and isolated pen workspaces for repository-file mutations.

Nave is AGPL-3.0. The first integration is a process boundary through its CLI.
The adapter must report the installed version and supported JSON command
protocol before use. A future tighter integration requires a separate licensing
and packaging decision.

## Nave CLI adapter

The adapter is a pulse-owned interface with a nave-backed implementation:

```text
NaveCliAdapter
  probe() -> NaveCapabilities
  scan() -> FleetIndex
  pull(paths) -> EvidenceCache
  search(query) -> SearchResult
  build(path_kind) -> StructuralProfiles
  check() -> ValidationReport
  pen_create(selection, name) -> PenHandle
```

`probe()` runs `nave --version` and `nave --help`, then records:

```yaml
nave:
  available: true
  version: 0.4.0
  protocol: 1
  capabilities: [scan, pull, search, build, check, pen]
```

The adapter invokes JSON-producing commands where supported. Pulse normalizes
the output into a stable internal contract so workflow code does not depend on
nave's internal Rust or Python structures:

```yaml
repo_evidence:
  repo: owner/name
  remote_sha: abc123
  files:
    - path: pyproject.toml
      blob: def456
      kind: pyproject
      parsed: true
      data: {}
  capabilities: [python, ci]
  structural_signals:
    - signal: uses_uv
      evidence: [pyproject.toml, uv.lock]
  validation:
    state: valid
    errors: []
```

If nave is unavailable or lacks a required command, pulse continues where
possible and records `capability_status.nave.state: unavailable` or
`unsupported`. This is not a repository health failure. Workflows that require
Nave evidence must become `blocked_by_capability` with a proposed remediation.

The adapter supports fixture mode so pulse tests do not require a nave binary,
network, or GitHub credentials. The fixture protocol is the normalized
`RepoEvidenceSnapshot`, not raw nave internals.

## Profiles and scorecards

Profiles describe capabilities and intent. Scorecards define expectations,
weights, adapters, and applicability. Workspace metadata is authoritative:

```yaml
repository_profiles:
  hiivmind-pulse-gh:
    profiles: [python, claude-plugin, control-plane]
    scorecard: claude-plugin-v1
  billing-api:
    profiles: [python, service]
    scorecard: python-service-v1
  web-console:
    profiles: [node, web-application]
    scorecard: node-web-v1
```

A scorecard contains checks with explicit adapters and weights:

```yaml
scorecards:
  python-service-v1:
    checks:
      - id: dependency-lock
        adapter: python.lockfiles
        weight: 2
      - id: ci
        adapter: github.actions
        weight: 2
      - id: documentation
        adapter: generic.docs
        weight: 1
      - id: claude-context
        adapter: claude.context
        applicability: capability:claude_context
        weight: 0
  claude-plugin-v1:
    extends: python-service-v1
    checks:
      - id: plugin-manifest
        adapter: claude.plugin_manifest
        weight: 2
      - id: skill-layout
        adapter: claude.skills
        weight: 1
      - id: marketplace-release
        adapter: hiivmind.marketplace
        weight: 1
```

The same check ID may have different adapters by scorecard, but a repository
must not count the same check twice through multiple profiles. Scorecard
inheritance is resolved before evaluation and duplicate IDs are rejected unless
the child explicitly replaces the parent check.

### Scoring states

```text
pass | warn | fail | unknown | not_applicable | unsupported | error
```

- `not_applicable` is excluded from the denominator and does not lower a score.
- `unsupported` is excluded from the score but counted in fleet coverage debt.
- `unknown` means applicable evidence could not be established.
- `error` means collection or execution failed and requires investigation.
- Fleet reports show normalized percentage, profile-specific grade, and coverage
  debt. An `A` on a plugin scorecard is not presented as equivalent to an `A`
  on a Python-service scorecard without the scorecard identifier.

## Workflow taxonomy

### Generic workflows

These operate on any repository or workspace when their binding is configured:

- fleet membership and catalog currency;
- impact audit over configured repository dependency edges;
- plan/document synchronization;
- branch, release, issue, project, and repository polling;
- result validation, attribution, mutation policy, and run recording;
- repository inventory and profile-review workflows.

Generic workflows must not inspect plugin-specific paths unless an adapter is
selected.

### Profile-specific workflows

These require an explicit profile or capability:

- Python dependency and packaging coherence;
- Node dependency and packaging coherence;
- Claude plugin manifest and skill layout;
- marketplace release synchronization;
- generated-artifact drift for a configured generator;
- service deployment/runtime checks;
- library release/API compatibility checks;
- infrastructure configuration/schema checks.

Profile-specific workflows use the generic result contract and mutation policy,
but their detectors, evidence paths, and score weights come from adapters.

### Generic top-level workflows with internal dispatch

Some operations are generic in intent but require repository-aware execution:

- `healthcheck`: universal shell, scorecard-selected checks;
- `dependency-coherence`: universal fleet operation, ecosystem adapters;
- `scaffold-drift`: universal binding model, generator adapters;
- `contract-propagation`: universal version-edge model, contract parsers;
- `documentation-currency`: universal intent, repository documentation
  adapters, with Claude context as an optional adapter;
- `onboarding`: universal catalog registration, profile-specific governance,
  labels, milestones, scheduler, and checklist actions.

Dispatch is deterministic once profiles are resolved:

```text
workflow invocation
  → load repository profile and scorecard
  → collect adapter-declared evidence paths through nave
  → run generic detector
  → dispatch selected profile adapters
  → evaluate scorecard
  → merge findings by stable (repo, check_id, adapter) identity
  → apply only allowed actions
  → record result and coverage state
```

## Metadata and instruction flow

### Authoritative inputs

- Workspace profile and scorecard metadata: committed workspace configuration.
- Adapter definitions and detection instructions: versioned plugin/skill/script
  assets, selected by scorecard.
- Nave tracked paths and cache settings: nave configuration, with pulse-owned
  workspace integration defaults.
- Binding markers: artifact frontmatter or workspace relationship state.

### Derived outputs

- Nave fleet/evidence cache;
- structural profile proposals;
- capability findings;
- scorecard results;
- `proposed_actions` and `asks_recorded`;
- transient snapshots and result files.

### Flow for changes

```text
new evidence or detection finding
  → proposal with evidence and confidence
  → asks_recorded
  → human confirmation
  → workspace metadata PR
  → subsequent run uses the new profile/scorecard
```

No detector may silently alter a profile, scorecard, tracked-path set, or
mutation policy. A workflow may suggest those changes, but the next run must
continue using the old authoritative metadata until the change is merged.

## Mutation boundaries

Repository-file changes use nave pens:

```text
pulse selection
  → nave pen create
  → nave rewrite/exec/check
  → pulse result validation
  → PR proposal/open
```

GitHub-side changes use pulse operations and the configured headless mutation
policy. Workspace profile/scorecard changes are always PR-based. A successful
integration test or reconciliation updates durable markers only through the
workspace/artifact marker path; local caches never become authority.

## Failure and degraded modes

| Condition | Result |
|---|---|
| nave missing | continue generic GitHub-only workflows; mark evidence-dependent work unavailable |
| nave version too old | skip unsupported adapter; record protocol mismatch |
| no profile assigned | run universal checks; propose profile; do not run profile mutations |
| profile evidence conflicts | retain current profile; record `asks_recorded` |
| adapter unsupported | emit coverage debt, not repository failure |
| repository archived/forked/mirror | apply workspace discovery policy before onboarding |
| dirty/local-ahead checkout | report nudge; never sync local content |
| scorecard malformed | block that repository’s scorecard and report configuration error |

## Migration of existing plans

- W1 becomes the first dependency adapter family, with explicit Python/Node
  coverage and `unsupported` states for other ecosystems.
- W2 remains generic for membership detection; its onboarding cascade dispatches
  through profiles instead of a hard-coded repository-class list.
- W3 becomes the `claude-plugin`/`hiivmind.marketplace` overlay.
- W4 remains generic impact-audit infrastructure.
- W5 becomes generic generated-artifact binding infrastructure plus configured
  generator adapters; generated Claude skills are one overlay.
- W6 and W7 remain concrete W4 edge configurations.
- W8 becomes an opt-in Claude context adapter, never a universal healthcheck.
- W9 remains generic plan synchronization with repository/profile policy only
  where required.

## Open implementation decisions

1. Pin the minimum nave protocol version and define the first normalized JSON
   schemas.
2. Decide whether pulse should install nave, require a user-installed binary,
   or offer a documented `uvx`/package-manager fallback.
3. Define the first neutral scorecards (`python-library-v1`,
   `python-service-v1`, `node-package-v1`, `claude-plugin-v1`).
4. Define workspace metadata merge rules for profile proposals and scorecard
   inheritance.
5. Decide which nave pen lifecycle commands pulse may invoke automatically and
   which require explicit user approval.
