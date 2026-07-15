# F3 whole-branch final fixes report

Date: 2026-07-15 (Australia/Melbourne)
Branch: `feat/f3-dispatched-healthchecks`
Review range: `28f8ab2..003a093`

## Requirement audit

1. **F0 observational completeness and capabilities**
   - Version-1 repository evidence now accepts optional `files_complete` and sorted,
     duplicate-free `capabilities` string lists; legacy absence remains valid and is
     interpreted conservatively as incomplete/no derived capabilities.
   - Nave normalization always emits `files_complete: false` and derives only factual
     `ci` capability from `has_workflows`; it does not assign profiles.
   - Contract documentation and real normalization tests cover the emitted shape.

2. **Generic adapter absence semantics**
   - Documentation, CI, license, and security policy use observed paths as positive
     proof but infer negative outcomes only from `files_complete: true`.
   - Incomplete observations emit `unknown` with an evidence-gap detail and citations.
   - README plus extra docs passes regardless of completeness; README-only warns only
     when complete. Recognized SPDX metadata and observed root license files pass;
     explicit authoritative `github.repo.license: null` fails when no license file was
     observed. `NOASSERTION` metadata does not produce a false pass.
   - Legacy exhaustive fixtures explicitly set completeness. An acceptance test feeds
     actual pyproject-only `evidence_snapshot.normalize` output through dispatch and
     proves all four universal checks are `unknown`, never failures.

3. **Applicability**
   - A real normalize -> default `profiles.yaml.template` load -> dispatch integration
     proves an observed workflow derives `ci` and activates `capability:ci`.
   - Acceptance coverage now includes actual normalized F0 data rather than relying
     solely on hand-authored capability fixtures.

4. **Dismissal JSON normalization**
   - Copied dismissal metadata is recursively converted to JSON-native mappings/lists;
     YAML `date` and `datetime` values become ISO strings.
   - CLI regression uses unquoted `review_after` and `dismissed_at`, parses stdout as
     JSON, and verifies their normalized strings.

5. **Finite numeric safety**
   - Profile loading rejects negative, NaN, and positive/negative infinity weights.
   - `score_checks` rejects those weights before all status paths, including
     `unsupported` and `not_applicable`.
   - Result number validators reject booleans where numeric values are required and
     reject every non-finite repository/check/aggregate number under test.

6. **Ruleset accuracy**
   - Legacy protection endpoint mappings retain their pass/warn behavior.
   - Without legacy protection, only active `target: branch` rulesets whose ref
     conditions include `~ALL`, `~DEFAULT_BRANCH`, or the exact default ref, without a
     default exclusion, pass.
   - Tag-only and excluded/nonmatching rulesets fail; active branch rulesets with
     incomplete condition facts return `unknown`.

7. **Result validation invariants**
   - Every check requires mapping `data.evidence` with string-list `paths` and `refs`.
   - Enforced: score <= total, coverage_supported <= coverage_total,
     checks_supported <= checks_total, repos_scored <= repos, and average_percent is
     null or finite within 0..100. Numeric values are finite, non-negative where
     applicable, and boolean-rejected.

8. **Acceptance maintainability**
   - Positional `evidence[1]` lookup was replaced by repository-name indexing.
   - Adapter nonexecution assertions are scoped to the Terraform repository so future
     legitimate Python/plugin fixtures do not make the gate brittle.

## TDD evidence

- Baseline: `uv run pytest -q` -> `220 passed in 6.44s`.
- F0 RED: focused normalization/validator run -> 6 expected failures for missing
  completeness/capability emission and validation; GREEN -> `22 passed`.
- Generic/ruleset RED: focused adapter run -> 9 expected failures for observational
  absence and ruleset targeting; GREEN -> `32 passed`.
- Numeric/dismissal/result RED: focused four-suite run -> 28 expected failures,
  including non-finite weights, JSON serialization, evidence citations, and invariant
  bounds; GREEN -> `113 passed`.
- License self-review RED: `NOASSERTION` incorrectly passed; GREEN generic adapter
  suite -> `33 passed`.
- Acceptance/F0 focused run before the final edge case -> `41 passed`.

## Final verification

- `uv run pytest -q` -> `273 passed in 7.40s`.
- `uvx ruff check <all changed Python files/tests>` -> recorded clean before commit.
- `git diff --check` -> recorded clean before commit.

## Concerns

None. The changes are compatibility-preserving at the F0 schema boundary and remain
within the eight review findings; no authoritative profile inference was introduced.
