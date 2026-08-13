# Pattern: Repository profiles and scorecards

Repository intent is committed workspace metadata, not a conclusion silently
written by a detector. The authoritative file is
`.hiivmind/github/profiles.yaml`.

## Authority boundary

- `repository_profiles` selects the reviewed intent labels and scorecard for a
  repository.
- `scorecards` selects checks, adapters, weights, and applicability.
- `adapters` records whether an adapter implementation is available.
- `proposal_rules` optionally records deterministic evidence-to-profile
  suggestions. It is detection policy, never authoritative assignment.
- Detection may emit profile proposals and `asks_recorded`, but those outputs
  never modify this file. A profile or scorecard changes only through a merged
  workspace-metadata change.

## Schema

```yaml
repository_profiles:
  acme/api:
    profiles: [python, service]
    scorecard: python-service-v1

scorecards:
  generic-v1:
    checks:
      - id: documentation
        adapter: generic.docs
        applicability: always
        weight: 1
  python-service-v1:
    extends: generic-v1
    checks:
      - id: python_manifest_lock_consistency
        adapter: python.dependencies
        applicability: profile:python
        weight: 2

adapters:
  generic.docs:
    state: available
  python.dependencies:
    state: available
  terraform.dependencies:
    state: unsupported
    reason: dependency adapter not implemented

proposal_rules:
  python-pyproject:
    profile: python
    confidence: 0.95
    priority: 10
    any_paths: [pyproject.toml]
```

The first three root mappings are required; `proposal_rules` is optional.
Unknown keys, scorecards, adapters, and proposal-rule fields are configuration
errors. Adapter state is `available | unsupported`; an
unsupported adapter requires a reason and produces coverage debt rather than a
repository failure.

## Profile proposals

A proposal rule declares `profile`, rule-defined `confidence`, optional
non-negative `priority` (default 100), and at least one selector:
`any_paths`, `all_paths`, `capabilities`, or `structural_signals`. Path
selectors use shell-style glob matching against normalized F0 evidence.

Matching rules create ordered candidates with observed evidence and rule IDs.
They never edit `repository_profiles`. Optional inferred explanation may
annotate a completed proposal, but cannot add, remove, or reorder candidates.
An evidence set that matches no rule produces an empty candidate list rather
than a guessed fallback profile. A repository with authoritative profiles is
omitted when every detected candidate is already assigned; only additive or
conflicting evidence returns it for renewed review.

### Confirmation boundary

Confirmation is an explicit compare-and-swap patch of workspace metadata:

```bash
uv run "${PLUGIN_ROOT}/lib/pulse/scripts/profile_proposals.py" confirm \
  --profiles .hiivmind/github/profiles.yaml \
  --repo acme/widget \
  --expected-scorecard generic-v1 \
  --profiles-list python,library \
  --scorecard python-library-v1
```

Use `--expected-scorecard absent` when the repository has no authoritative
entry. A mismatched expected scorecard is a conflict and leaves the file
unchanged. Repeating an already-applied target is idempotent even when the
original expected base is now stale. The script atomically patches only
`repository_profiles`; it never commits, pushes, opens a PR, or runs onboarding
actions. The caller owns the workspace metadata PR.

## Check identity and inheritance

A check ID occurs once in a resolved scorecard. A child that intentionally
changes an inherited check must set `replace: true`; accidental duplicates are
configuration errors. Weight is a non-negative number and travels with the
check result so scoring can be reproduced from the artifact.

**Polyglot repositories select multiple ecosystem-specific check IDs, never
one shared ID.** A repository whose scorecard resolves both
`python_manifest_lock_consistency` (adapter `python.dependencies`) and
`node_manifest_lock_consistency` (adapter `node.dependencies`) is legal — they
are distinct check IDs, and the same-check-ID-occurs-once rule above never
forces them into one. Reusing a single ID for both ecosystems would not load:
the second `checks[].id` occurrence requires `replace: true`, which is
semantically wrong here (both ecosystems' results are wanted, not one
replacing the other). See `lib/patterns/dependency-coherence.md` for the full
evidence-state lattice both adapters share, and the separate
`fleet_dependency_coherence` check (adapter `fleet.dependencies.coherence`),
which compares locked versions across repositories inside committed
`.hiivmind/github/dependencies.yaml` coherence groups rather than within one
repository.

Applicability predicates are evaluated only after inheritance resolves:

- `always`
- `profile:<id>` against authoritative repository profiles
- `capability:<id>` against that repository's derived evidence capabilities
- `evidence_path:<glob>` against observed repository paths

Applicability never assigns a profile. A false predicate produces
`not_applicable`. An applicable check whose adapter is unavailable produces
`unsupported`.

## Score interpretation

Grades are scorecard-specific. Reports always pair a grade with its scorecard
ID; an `A` on one scorecard is not claimed equivalent to an `A` on another.
`not_applicable` and `unsupported` do not enter the score denominator, while
unsupported weight is visible as coverage debt.
