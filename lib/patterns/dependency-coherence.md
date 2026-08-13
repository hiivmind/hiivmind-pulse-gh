# Dependency coherence policy contract

F4's fleet dependency-coherence check (`fleet_dependency_coherence`) compares
locked package versions across repositories, but only inside coherence groups
the workspace explicitly commits — never by inferring relationships from repo
names or shared packages alone. The committed policy lives at
`.hiivmind/github/dependencies.yaml` and is loaded by
`lib/pulse/scripts/dependency_policy.py`.

## Contract version 1

```yaml
contract_version: 1
coherence_groups:
  core-runtime:
    repos: [acme/api, acme/worker]
    packages: ["python:requests", "npm:@acme/*"]
    exclude_packages: ["python:typing-extensions"]
    policy: same-minor
```

Top-level keys are exact: `contract_version`, `coherence_groups` — no extras.
Each group entry has exactly `repos`, `packages`, `policy`, and the optional
`exclude_packages` (defaults to `[]` when omitted). `coherence_groups` may be
an empty mapping (`{}`) — a workspace with no committed groups yet is valid,
just uncomparable (every selected repository reports
`fleet_dependency_coherence` as `not_applicable`, tracked as durable coverage
debt via `repositories_ungrouped`, never a silent gap).

- `repos`: non-empty list of unique `owner/name` strings — the group's members.
- `packages`: non-empty list of ecosystem-qualified globs (grammar below) —
  the packages this group tracks for divergence.
- `exclude_packages`: list of the same glob grammar; a package matching any
  `exclude_packages` glob is never compared, even if it also matches
  `packages` — **exclude always wins**, unconditionally.
- `policy`: one of `exact`, `same-major`, `same-minor`. `exact` rejects any
  locked-version mismatch across group members. `same-minor` allows `patch`-
  tier divergence. `same-major` allows `minor` and `patch`-tier divergence. A
  `major`-tier divergence is always a policy violation regardless of policy.

A repository/package pair may belong to multiple groups; each group emits an
independent finding — overlapping groups are never merged or ranked.

The loader (`lib/pulse/scripts/dependency_policy.py`) is **strict**: it
rejects duplicate `coherence_groups` keys, duplicate `repos` entries within
one group, unknown top-level/group keys, an unrecognized `policy` value, an
empty `repos`/`packages` list, and any glob failing the grammar below. It
parses raw YAML text with a duplicate-key-detecting loader — never a
pre-parsed dict — because ordinary YAML parsing already silently keeps the
last key on a duplicate, discarding the very fact this loader must catch.

## Package identity and glob grammar

Package identity is `(ecosystem, normalized_name)`. Python names are PEP 503
normalized (lowercase, runs of `-_.` collapsed to a single `-`); npm names are
lowercased, preserving the `@scope/name` structure verbatim. The normalized
identity string globs match against is `"ecosystem:name"` — e.g.
`"python:requests"`, `"npm:@acme/widgets"` — using the **package namespace**
ecosystem literal (`python`/`npm`), never the adapter-selection literal
(`python`/`node`): npm packages are always in the `npm` namespace, regardless
of which `node` adapter parsed them.

A `packages`/`exclude_packages` glob must match this grammar exactly:

```ebnf
glob        = python_glob | npm_glob
python_glob = "python:" py_segment
npm_glob    = "npm:" (npm_scoped | npm_plain)
npm_scoped  = "@" plain_atom+ "/" plain_atom+
npm_plain   = plain_atom+
py_segment  = plain_atom+
plain_atom  = literal | star | question | bracket
literal     = letter | digit | "-" | "_" | "."
star        = "*"
question    = "?"
bracket     = "[" ["!"] rangeitem+ "]"
rangeitem   = letter | digit | letter "-" letter | digit "-" digit
letter      = "a".."z" | "A".."Z"          (* ASCII only; no Unicode letters *)
digit       = "0".."9"
```

`/` and `@` are not members of `literal`/`plain_atom` — they appear only in
the fixed `npm_scoped` production, at the fixed positions shown. This rejects
`python:@foo/bar` (no production admits `@`/`/` under `python_glob`) and any
npm glob placing `@`/`/` outside the scoped form's fixed shape (`npm:foo@bar`,
`npm:foo/bar/baz`). Matching itself uses `fnmatch.fnmatchcase` — case-sensitive
even post-normalization, never the platform-normalizing `fnmatch.fnmatch`.

## Cross-repo divergence semantics

- **Only `locked_version` is compared** — never `manifest_range`. A group's
  `distance` for a package with more than two fully-resolved members is the
  coarsest pairwise distance among every member's `locked_version`, under the
  explicit ordering `major > minor > patch`.
- A package record that cannot be resolved unambiguously
  (`resolution == "multiple"`) or whose `locked_version` fails to parse
  (`unresolved_reason == "unparseable_version"`) is never silently dropped
  from a group's comparison — it produces a `DivergenceFinding` in
  `DivergenceReport.unresolved` instead of `DivergenceReport.findings`, with
  `None` standing in for the unresolved participant(s)' version. This is
  coverage debt, never a guessed comparison.
- A bucket with fewer than two comparable (fully-resolved) members produces no
  finding at all — there is nothing to compare.
- `unresolved_reason == "non_range_spec"` describes an unusual
  `manifest_range` (a VCS/URL/local-path spec, for Python; `*`, a dist-tag,
  `workspace:`, or a git/tarball/file URL, for npm) — it does **not**
  disqualify an otherwise fully-resolved record from fleet distance
  comparison, since only `locked_version` participates in that comparison.

See `docs/superpowers/plans/2026-07-13-f4-dependency-adapters.md` for the full
F4 design, including the Python/Node adapter algorithms that produce
`PackageRecord`s, and `dependency-evidence-contract.md` for the transient
evidence contract these adapters parse.
