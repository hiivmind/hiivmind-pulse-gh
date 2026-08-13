# Backlog: F4 deferred scope (from the 2026-08-13 Codex adversarial plan review)

**Date:** 2026-08-13 (updated after a fourth review round)
**Status:** Open (index)
**Source:** Four rounds of adversarial design review of
`docs/superpowers/plans/2026-07-13-f4-dependency-adapters.md` (codex `gpt-5.6-sol`, high
effort). Round 1 **BLOCK** (3 blocking/8 major/2 minor). Round 2 **BLOCK** again (3 new
blocking/8 new major — 10 of 13 resolved cleanly). Round 3 **BLOCK** again: root cause was a
bare `tuple[PackageRecord, ...]` unable to carry per-declaration range facts — fixed via a
typed `DependencyRepoEvaluation` object, plus 5 more major/1 minor fix (group-distance
reduction for 3+ member groups, Python uv-workspace detection mirroring Node's, typed
missing-evidence pre-dispatch, polyglot-repo ecosystem-set support, the stderr content-free
contradiction, always-unique record identity). Round 4 **BLOCK** again, narrower: the
`RepositoryEvaluationSummary` coverage-reconciliation source was information-incomplete and
never reached the snapshot builder — fixed via a redesigned summary (per-group membership,
matched/total package counts, partial-unsupported counts) plus an `evaluate_fleet`
`dependency_collector` out-param — plus 4 more major/1 minor fix (the `local_status` literal
used adapter-detection states instead of check-status states; `"python"|"npm"` vs
`"python"|"node"` ecosystem-literal confusion between two genuinely different domains; a
polyglot repo needs two distinct check ids, not one shared id, since `resolve_scorecard`
rejects duplicates; the release right-padding rule still indexed out of bounds for
equal-short-length-but-unequal versions like `2.dev1` vs `2`; the Poetry conversion algorithm
now covers bare-exact-version and wildcard forms too). See the plan file's round-4 revision
header for the full disposition. This backlog captures what all four rounds agree is genuine v2
scope — not required for F4 v1 correctness — where v1 instead ships an explicit, honest
coverage-debt narrowing (never a silently wrong answer). Item B was broadened by round 3's
finding that Python's uv workspaces (`[tool.uv.workspace]`) have the identical
unobserved-member problem as Node's — v1 now treats **both** ecosystems' manager-declared
workspaces as wholesale `unsupported`, not just Node's; item C was sharpened by round 2's
provenance-association finding (v1 now ships role-associated `(role, path, blob_sha)`
provenance, not an unordered SHA bag — only the F11 handoff-object construction itself remains
deferred).

**Read first:** `docs/superpowers/plans/2026-07-13-f4-dependency-adapters.md` — Global
Constraints and the "Deferred to backlog" section at the end name exactly which v1 scope cut
each item below replaces.

---

## A. Full Conda ecosystem support [LOW]

**F4 v1 scope:** only the nested `pip:` section of `environment.yml` is parsed, into the
`python` ecosystem. Native Conda specs (channel/subdir/build-qualified, non-Python packages
like `openssl`/`nodejs`) are explicit `unsupported` coverage debt — never force-mapped into
PEP 503/PEP 440 identity, which would falsely compare a Conda artifact against an unrelated
PyPI distribution or silently discard identity-significant channel/build qualifiers.

**Full scope:** a distinct Conda ecosystem/source namespace with a Conda-aware MatchSpec
identity and version comparator (channel, subdir, name, version, build), splitting nested
`pip:` dependencies back into the PyPI namespace rather than treating the whole environment
file as one ecosystem. If cross-source alignment between a Conda-packaged and a
PyPI-packaged same-name dependency is ever wanted, it needs an explicit policy alias — never
automatic name equality across ecosystems.

**Trigger to build:** a real coherence-group consumer with Conda-managed repositories in the
fleet that need native-spec (not just nested-pip) comparison.

---

## B. Full per-declaration/per-resolution `PackageRecord` cardinality, including real workspace-member modeling for both ecosystems [MEDIUM]

**F4 v1 scope:** two distinct narrowings, both typed as visible coverage debt rather than
guessed:
- **Manager-declared workspace repositories are wholesale `unsupported`, for both ecosystems**
  — Node's `package.json` `workspaces` key / `pnpm-workspace.yaml`, and Python's uv
  `[tool.uv.workspace]` table (not a partial or per-member comparison in either case). The
  static `DEPENDENCY_SELECTORS` catalog only fetches repo-root manifests/locks/sentinels; it
  cannot see workspace-member manifests, so any attempt to infer per-member divergence from the
  root file alone would be a guess, not a detection. Round 2 flagged the round-1 attempt to
  type Node's case as `resolution="multiple"` as unsound for exactly this reason; round 3 found
  the same problem applied to Python's uv workspaces, which the round-2 revision had missed —
  the ambiguity was never actually observable with the selectors in scope, for either ecosystem.
- **Python markers/extras/optional-dependency-groups** that produce a genuinely ambiguous
  *resolution* (not merely multiple declarations resolving to one version — that case is
  `resolution="single"` in v1, verified against `DeclaredRequirement`, per the corrected Global
  Constraints) still emit one `PackageRecord` with `resolution="multiple"` and
  `unresolved_reason="multiple_resolutions"`. This case *is* honestly observable from the
  single already-fetched manifest, so it stays in v1's detection scope, just not its full
  requirement-unit modeling.

**Full scope:** two separable pieces of future work:
1. **Real workspace-member modeling, for both ecosystems** — a second materialize round-trip:
   fetch the root manifest/`pnpm-workspace.yaml`/`[tool.uv.workspace]` table first, discover
   the configured member globs, then issue a follow-up `MaterializeRequest` for the actual
   member manifests, and model each member's declarations as first-class records (rather than
   collapsing them or refusing to look).
2. **Full requirement-unit identity** for both ecosystems — `normalized_name` + `manifest_path`
   + workspace/member + dependency group/kind + marker/platform/extras + declared spec, each
   with one-or-more resolution records (lock path, provenance). This lets local consistency
   flag "this workspace member's range is violated" instead of a repo-wide "some member's range
   is violated," and lets fleet comparison exclude dev-only/platform-gated pins that should
   never enter it.

**Trigger to build:** (1) once F4 v1 is running against the real fleet, if the
`workspace_repository`-`unsupported` count is high enough — across either ecosystem — that a
meaningful slice of the fleet gets zero coherence signal; (2) separately, if
`resolution="multiple"` coverage debt from Python markers/extras shows up often enough to blind
the fleet coherence check for a meaningful fraction of Python repos.


---

## C. F11 apply-mode dependency-bump handoff object [MEDIUM]

**Dependency:** F11 apply-mode production wiring (`docs/backlogs/2026-07-29-apply-mode-v2-deferrals.md`
§ A) and the general apply-mode "richest neutral use case" item (same doc § D.1).

**F4 v1 scope:** `PackageRecord`/`deps-snapshot.json` preserve the identity/provenance F11
will need, **role-associated**: `tree_sha`, and a `provenance` tuple of `(role: "manifest"|
"lock", path, blob_sha)` entries — not an unordered bag of SHAs — so a later consumer can tell
which blob backs which file without guessing. F4 does **not** construct anything apply-mode-
shaped from a `DivergenceFinding`.

**Full scope:** given a `DivergenceFinding`, build the actual guarded-proposal handoff object
F11's `pen_orchestrator`/`apply_ops` needs: `selection` (which repos/packages to bump and to
what target version — a policy decision F4 deliberately does not make), `expected_shas` (guard
against a repo moving between evidence and apply), the manager-specific mutation strategy
(which command bumps `uv.lock`/`package-lock.json`/etc. for the detected manager), and
`bound_paths` (exactly which manifest/lock files the mutation touches). This is F11's
responsibility, not F4's — F4 only needs to not lose the inputs F11 will require.

**Trigger to build:** when apply-mode production wiring (F11's own top P1 backlog item) is
underway and needs a concrete dependency-bump proposal source to demonstrate against.

---

## D. Per-package policy overrides beyond the narrower-coherence-group idiom [LOW]

**F4 v1 scope:** `dependencies.yaml`'s only per-package precision mechanism is defining a
narrower `CoherenceGroup` (fewer repos, a tighter `packages`/`exclude_packages` glob set) with
its own `policy`. Overlapping groups are independent — no merge, no precedence beyond
"exclude always wins within one group's own include/exclude lists."

**Full scope:** an explicit per-package policy override inside a group (e.g. "same-minor for
everything in this group except `python:requests`, which is `exact`") rather than requiring a
second, narrower group to express that. Only worth building if the narrower-group idiom
produces workspace-policy files that are unwieldy in practice (many near-duplicate groups
differing by one package's policy).

**Trigger to build:** real `dependencies.yaml` authoring friction — wait for the workspace
config to actually need it before designing the override syntax.

---

## Suggested priority

1. **B. Full cardinality modeling** — the one item that can silently degrade fleet coherence
   coverage as the fleet grows; watch `unresolved_reason` counts once F4 v1 ships.
2. **C. F11 handoff object** — sequenced by F11's own apply-mode production-wiring timeline,
   not by F4.
3. **A. Full Conda support** — narrow, single-repo, wait for a real Conda-managed
   coherence-group need.
4. **D. Per-package overrides** — cosmetic until real policy-authoring friction shows up.
