# Pattern: Repository profiles and scorecards

Repository intent is committed workspace metadata, not a conclusion silently
written by a detector. The authoritative file is
`.hiivmind/github/profiles.yaml`.

## Authority boundary

- `repository_profiles` selects the reviewed intent labels and scorecard for a
  repository.
- `scorecards` selects checks, adapters, weights, and applicability.
- `adapters` records whether an adapter implementation is available.
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
      - id: dependencies
        adapter: python.lockfiles
        applicability: profile:python
        weight: 2

adapters:
  generic.docs:
    state: available
  python.lockfiles:
    state: available
  terraform.dependencies:
    state: unsupported
    reason: dependency adapter not implemented
```

All three root mappings are required. Unknown keys, scorecards, and adapters
are configuration errors. Adapter state is `available | unsupported`; an
unsupported adapter requires a reason and produces coverage debt rather than a
repository failure.

## Check identity and inheritance

A check ID occurs once in a resolved scorecard. A child that intentionally
changes an inherited check must set `replace: true`; accidental duplicates are
configuration errors. Weight is a non-negative number and travels with the
check result so scoring can be reproduced from the artifact.

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
