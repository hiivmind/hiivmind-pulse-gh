# Dependency-Bump Apply Handoff (F11 ← F4) — Design Spec

**Date:** 2026-08-15
**Status:** Approved (brainstorm); revised after GLM-5.2 adversarial review (BLOCK → addressed).
**Origin:** `docs/backlogs/2026-08-13-f4-deferred-scope.md` § C — the F4 v1 plan deliberately
materializes the evidence a later apply-mode consumer needs (`PackageRecord` identity/provenance,
a `DivergenceFinding` per diverging package) but does **not** construct anything apply-mode-shaped
from it. This spec closes that gap: turn an F4 `DivergenceFinding` into a guarded `Proposal` the
already-shipped apply spine (`apply_driver` → fence/lease/journal → `nave pen` verbs → PR →
reconcile) can land.

**Read alongside:** `docs/superpowers/specs/2026-08-15-multi-repo-apply-design.md` (the multi-repo
spine this reuses), `docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md`
(authorization + fencing), `lib/pulse/scripts/dependencies.py` (`PackageRecord`,
`DivergenceFinding`), `lib/pulse/scripts/mutation_plan.py` (`Proposal`, `TransformationEntry`,
`resolve_argv`, `proposal_digest`), `lib/pulse/scripts/apply_phases.py` (`exec_phase`),
`lib/pulse/scripts/apply_reconcile.py` (`resolve_intended_base`).

---

## 1. Problem

F4 (dependency-coherence adapters) now scores fleet dependency coherence and emits, per coherence
group, a `DivergenceFinding` per package whose locked version diverges across member repos:

```python
@dataclass(frozen=True)
class DivergenceFinding:
    group: str
    ecosystem: Literal["python", "npm"]
    package: str
    versions: tuple[tuple[str, str | None], ...]   # (repo, locked_version | None)
    distance: Literal["major", "minor", "patch", "unresolved"]
```

F11 (apply-mode) now lands guarded, allow-listed proposals — single- and multi-repo — end to end.
The one missing link to the flagship fleet use-case ("align `requests` across the Python coherence
group and land the lockfile change") is the **handoff**: nothing turns a finding into the
`selection` / `expected_shas` / mutation strategy / `bound_paths` the apply spine consumes.

Two properties of the current spine make this non-trivial, both settled in § 2:

1. **`TransformationEntry.command_argv` is strict** — `_argv` (mutation_plan.py) forbids any
   templating: "an argv element is exactly the string committed in the registry, always." A
   dependency bump must write a **target version** into a manifest, and that version is only known
   at re-derive time.
2. **A finding is dynamic, not authored.** The neutral source re-derives from a static binding
   (`repos` / `transformation` / `bound_paths`); a finding's repos and target are *computed* from
   fresh fleet evidence at collect time.

## 2. Decisions (settled in brainstorm)

1. **Target = highest locked version in the group**, by **semantic version order** (the same
   PEP 440 / semver comparator F4 already uses to compute `distance`; `packaging.Version` orders
   pre-releases before finals, so `2.0.0rc1 < 2.0.0` correctly) — not lexicographic string order,
   which mis-orders `2.10.0` vs `2.9.0`. Deterministic, zero new config: the repo that was
   semantically ahead becomes the source of truth. No `target:` field in `dependencies.yaml` (a
   later, separable refinement if align-up proves wrong).
2. **Whitelisted argv templating**, not a bump-spec file or a first-class `nave pen bump` verb.
   The bump stays a plain `TransformationEntry` whose `command_argv` contains `{package}` /
   `{version}` placeholders; the driver expands them from a new `Proposal.transform_params` field.
   Validation is **param-aware** (package-name vs version shapes differ — § 4.3). One small,
   additive nave change: `nave pen create` also reports a locally-computed `observed_tree_sha`
   (§ 4.4 step 7); the bump command itself is unchanged.
3. **New `dependency-bump` source kind** (not a neutral transformation + extended binding). A
   finding is derived, not authored, and the neutral binding shape cannot carry the derived target;
   the alternative still needs the `Proposal` extension, so it buys nothing.
4. **One proposal per (finding, manager), restricted to `main`-group declarations in v1.** A
   finding's repos can span managers (uv / poetry / npm / pnpm) whose bump commands differ; each
   manager group becomes its own homogeneous proposal. A package declared in a `dev`/`optional`
   group is `blocked` (never silently promoted to main — § 4.4 step 4). v1 pins **exact** (`==V` /
   `@V --save-exact`); range preservation is a non-goal (§ 7).

## 3. Architecture — what reuses vs. what changes

| Layer | Today | Change |
|-------|-------|--------|
| `mutation_plan.Proposal` | `transformation: str` only | **`transform_params: dict[str, str]`** |
| `mutation_plan.proposal_digest` | payload omits params | **include canonicalized `transform_params`** |
| `mutation_plan.TransformationEntry` | `command_argv` (strict) | **`params: tuple[str, ...]`** (declared placeholders) |
| `mutation_plan.resolve_argv` | returns `command_argv` verbatim | **expands `{key}` from `transform_params`** |
| `apply_phases.exec_phase` | `resolve_argv(entry)` | passes `proposal.transform_params` |
| `apply_reconcile.resolve_intended_base` | 4 source kinds | **`dependency-bump` branch** (§ 4.8) |
| `apply_rederive` sources | neutral / plan-sync / generated-artifact / marketplace-sync | **`dependency-bump` provider** (collect-once, rederive-many) |
| `apply_driver` | `--binding-ref` (neutral) / `--recorded-summary` | **`--finding-ref`** + `bump_summary` synthesis |
| fence / lease / journal / phases / PR / rollup | multi-repo already | none (per-proposal, looped — § 4.7) |
| nave | owns clone writes | provisioning also reports `observed_tree_sha` (local git, § 4.4 step 7) |

## 4. Design

### 4.1 `Proposal.transform_params` (mutation_plan.py)

`Proposal` gains one field, defaulting empty for full backward compatibility:

```python
transform_params: dict[str, str] = field(default_factory=dict)
```

`build_proposal` validates it against the registry entry: every key must be a member of
`entry.params` (no undeclared keys), every value must pass `_validate_param_value` (§ 4.3), and —
for entries with declared params — every declared key must be present (a templated entry without
its values is a `MutationPlanError`, fail-closed). Entries with empty `params` (all existing
transforms) require `transform_params == {}`.

**Digest:** `proposal_digest`'s payload (mutation_plan.py) **must** add `transform_params`,
canonicalized (`dict` sorted by key, values as-is). This is what makes a target change visible to
audit: § 4.6 makes the id target-independent on purpose, so the digest is the only place a target
change is pinned. `bump_summary` (§ 4.7) additionally carries the human-readable `target`.

### 4.2 `TransformationEntry.params` + templated `resolve_argv` (mutation_plan.py)

`TransformationEntry` gains `params: tuple[str, ...] = ()` — the set of `{placeholders}` an entry's
`command_argv` is allowed to contain. `_argv` / registry loading still rejects **undeclared**
placeholders (a `{foo}` in `command_argv` with no matching `params` entry is a load error), so the
registry stays the single source of truth for what may be substituted.

`resolve_argv` signature becomes `resolve_argv(entry, params: dict[str, str] | None = None)`:

- `None` → verbatim `command_argv` (all existing callers unchanged; `exec_phase` passes
  `proposal.transform_params`).
- a `dict` → each element is scanned for `{key}`; a `{key}` not in `entry.params` is an error, a
  declared key missing from `params` is an error, and each substituted value is re-validated with
  `_validate_param_value(key, value)` before insertion. The result is a plain string tuple handed
  to `subprocess.run(..., shell=False)` exactly as today.

**Security rationale.** The strict-argv rule existed to prevent *flag injection* (runtime data
being reinterpreted as argv flags) and, secondarily, shell metacharacter smuggling. Templating
reopens only the first, so § 4.3's value validator is the compensating control: a value that
cannot begin with `-` and cannot contain `=` / whitespace / shell metacharacters cannot become a
flag or an argument separator. There is still no shell anywhere in the path (`shell=False` is
unchanged), and values are substituted into a single argv element (never split on whitespace).

### 4.3 Parameter value validation (`_validate_param_value(key, value)`)

Validation is **param-aware** because a normalized package name and a version have different legal
shapes — one character class for both is wrong (it would reject every scoped npm package, whose
normalized identity is `@scope/name`). In `mutation_plan.py`:

```
package: ^(@[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*|[A-Za-z0-9][A-Za-z0-9._-]*)$
version: ^[A-Za-z0-9][A-Za-z0-9._+~-]*$
```

Both preserve the two security invariants: **first character alphanumeric** (no leading `-`), and
body limited to characters with no argv meaning (`/` and `@` are inert in an argv element; `=`,
whitespace, and `;|&$\`"'<>()` are excluded). A `version` with a PEP 440 epoch (`1!2.3.4`) is
**rejected — epochs are unsupported in v1** (a `!` is not in the class; fail-closed, § 7). A value
that fails is rejected at re-derive time (`RederiveError`), never at exec time.

### 4.4 The `dependency-bump` source kind (apply_rederive.py)

Add `"dependency-bump"` to `SOURCE_KINDS` and a provider pair mirroring the neutral one, with one
structural difference (§ 4.7): `_collect` returns **one `ProviderInputs` carrying the resolved
finding**, and `_rederive` returns **one proposal per (finding, manager)**.

**Input / finding address.** A finding is addressed by the triple `(group, ecosystem, package)`,
unique per package per group. The driver accepts it as JSON:
`--finding-ref '{"group":"core-runtime","ecosystem":"python","package":"requests"}'`.

**`_collect_dependency_bump(finding_ref, io_seams)`** (pre-fence, whole-run gates):

1. Re-derive the finding **fresh** from F4 evidence — the same compare path that produces the
   healthcheck `fleet.dependencies.coherence` findings — and locate the one finding matching
   `(group, ecosystem, package)`. Missing finding → `RederiveError` ("nothing to do" is never a
   silent no-op). (Implementation detail: reuse the F4 fleet `compare` / evidence materialization;
   the contract is freshness + exact-address resolution, not the specific loader.)
2. **Reject unresolved findings.** `compare()` emits either a divergence finding (all `versions`
   non-`None`) **or** an unresolved entry (`distance == "unresolved"`, some `None`) per identity —
   never both. A caller addressing an unresolved package must fail closed:
   `distance == "unresolved"` → `RederiveError` (a partial proposal bumping only the resolved
   repos would be semantically wrong). After this, every `locked_version` is non-`None`.
3. Compute `target` = the **semantically highest** `locked_version` among the finding's versions,
   reusing F4's version comparator (not `max()` over strings).
4. **Selection** = `{repo for (repo, v) in finding.versions if v != target}` (only diverging
   repos). Empty selection → `RederiveError`.
5. **Main-group restriction.** A `DivergenceFinding` collapses all declarations of a package into
   one finding keyed on `(repo, name)` — the `DeclaredRequirement.group` (`main`/`dev`/`optional`)
   is lost. Bumping a dev/optional-declared package with `uv add`/`npm install` would **promote it
   to main** (a duplicate, inconsistent declaration). v1 therefore restricts selection to repos
   whose declaration for this package is `group == "main"` (joined via the
   `DependencyRepoEvaluation.declarations` for that repo). A selected repo whose declaration is
   `dev`/`optional` is dropped from selection with a per-repo `blocked` outcome
   (`non-main-group-package`). Threading group through the finding is backlog (§ 7).
6. **Split by manager**: map each selected repo to the `PackageRecord` keyed by
   `(repo, ecosystem, name=package)` in the same F4 evidence and take its `manager`; group repos by
   manager. Each `(manager, repos)` group becomes one proposal. (The join is 1:1 — `PackageRecord`
   is "always exactly one per identity".)
7. **Two independent drift guards — commit (branch-provisioning) and tree (finding-validity) — not
   one.** `nave pen create`'s `observed_base_sha`/`expected_base_sha` gate is a hard **commit**-SHA
   invariant: `provision_one` (`apply_ops.rs`) rejects a non-commit object outright (`cat-file -t`
   must read `commit`) and then `checkout -B` from that exact SHA — it cannot be repurposed to carry
   a tree SHA. So `expected_shas` (commit-level) is populated the **same way neutral proposals
   already do it**: a fresh `GET /repos/{owner}/{name}/branches/{base_ref}` at collect-time (reuse
   `_collect_neutral`'s `head_sha` loop), not pinned to evidence. This just answers "am I branching
   off what's there right now" — the same short, already-accepted TOCTOU window every other
   proposal kind lives with.

   Separately, the thing that actually needs the evidence's `tree_sha` guard is **finding
   validity**: has the tracked-file content this bump was computed from changed since F4 evidence
   was materialized. That's a **tree**-SHA question (`validate_dependency_evidence.py`'s `tree_sha`
   is the GitHub tree API's tree SHA, not a commit), and the commit-level gate above can't answer
   it — a repo can gain new commits (docs, CI) whose tree is unchanged, or move to a different tree
   on the same nominal branch. nave's provisioning already does `git fetch` + `rev-parse` locally
   right before branching, so it reports the tree for free: `provision_one` additionally computes
   `git rev-parse {observed}^{tree}` (a **local** git call — zero extra GitHub API cost, zero
   nave-scan change, zero evidence-schema change) and adds `observed_tree_sha: String` to
   `BranchRepoResult` — additive and non-breaking (no exact-key wire validation on this struct,
   unlike the evidence document's `REPO_KEYS`). `Proposal` gains a second, dependency-bump-only
   field `expected_tree_shas: dict[str, str] | None = None`, populated **only** for repos whose F4
   `tree_sha` is non-`None` — a repo with a `None` `tree_sha` is dropped from selection during
   collect (§ 5 error table, "evidence `tree_sha` missing"), so `expected_tree_shas` never holds a
   `None` value; a stray `None` compared as `observed_tree_sha != None` would misreport as
   `stale-tree` when the real problem is missing evidence. `apply_phases.provision_phase` gains one
   more `elif` mirroring its existing `observed_base_sha` check
   (`item.get("observed_tree_sha") != expected_tree_shas.get(repo)` → per-repo `blocked`,
   `stale-tree`), gated on `proposal.expected_tree_shas is not None` so every other proposal kind
   is unaffected. It is placed **after** the existing `observed_base_sha` check in the `elif`
   chain: if the commit itself drifted, the operator sees `stale-base` (the more actionable
   diagnosis) rather than a `stale-tree` message that would send them investigating evidence
   staleness for what is actually a branch move. A repo whose tree moved between evidence and apply
   — commit unchanged — is `blocked` (`stale-tree`) instead of mutating a target that no longer
   matches the finding.
8. **`bound_paths[repo]`** = the `PackageRecord.manifest_path` + `lock_path` for that repo (both
   repo-relative; `None` entries omitted). A mapped v1 manager (uv/poetry/npm/pnpm) is detected by
   lock presence, so a lockless repo never reaches a mapped manager in v1 — state this invariant,
   don't leave it implicit.

**`_rederive_dependency_bump(...)`** builds, per manager group, a `Proposal`:

```
transformation     = MANAGER_TRANSFORM[manager]           # § 4.5
transform_params   = {"package": finding.package, "version": target}
selection          = tuple(sorted(group_repos))
expected_shas      = {repo: fresh_head_sha for repo in group_repos}      # step 7, same as neutral
expected_tree_shas = {repo: evidence_tree_sha for repo in group_repos}   # step 7, finding-validity
bound_paths        = {repo: (manifest_path, lock_path) present}
mutation_policy    = "allow-listed"
id                 = bump_proposal_id(ecosystem, package, manager, selection)   # § 4.6
```

`binding_id` for `authorize()` identity is the proposal id (as neutral's fleet id is).

### 4.5 Bump transformations (transformations.yaml)

Add manager → transformation entries to `templates/transformations.yaml.template` (and the
workspace's deployed copy), each declaring `params: [package, version]`:

| id | `command_argv` |
|----|----------------|
| `bump-python-uv` | `["uv", "add", "{package}=={version}"]` |
| `bump-python-poetry` | `["poetry", "add", "{package}=={version}"]` |
| `bump-npm` | `["npm", "install", "--save-exact", "{package}@{version}"]` |
| `bump-pnpm` | `["pnpm", "add", "--save-exact", "{package}@{version}"]` |

`MANAGER_TRANSFORM` keys `PackageRecord.manager` → transformation id. A manager with no entry is a
per-manager `blocked` outcome, so the rest of the finding still proceeds. **v1 deliberately leaves
unmapped** (and therefore per-manager-`blocked`) these managers F4 actually reports:
`pdm`, `conda`, `pip-tools` (Python) and `yarn1` (Node). They are added the same way when a fleet
consumer exists; the names are listed here so a reader does not infer they ship.

### 4.6 Deterministic proposal id (`bump_proposal_id`)

```
apply-bump-{ecosystem}-{package}-{manager}-{sha256(sorted selection)[:12]}
```

Stable over the bump's identity (ecosystem, package, manager, membership); the **target version is
not part of the id** — it is a re-derived value. A changed target re-derives through the same id
and re-reconciles (consistent with "apply re-derives from fresh source state"); a membership or
manager change yields a new id. Distinct from the neutral fleet id so the two never collide.

**Cascading-bump semantics (documented, not accidental).** Because the id is target-independent,
the branch is `pulse/apply/{id}` and `open_apply_pr` reuses the existing PR. An already-`applied`
repo whose fleet max later rises above its merged version (its `locked_version` is now below the
new target) re-enters selection and its PR re-opens; repos already at the new target are excluded
by the divergence filter (§ 4.4 step 4). These are intended semantics, not a bug.

### 4.7 Driver + recorded summary + authorization (apply_driver.py)

- `--source-kind dependency-bump` takes `--finding-ref` (JSON triple) instead of `--binding-ref`.
  `recorded_summary` is **synthesized** (`bump_summary(finding_ref, target, selection, manager)` →
  `{binding: <finding_ref>, transformation: <bump transform>, proposal_id, target}`), mirroring the
  driver's existing `source_kind == "neutral"` synthesis branch (no propose phase). The `target` is
  included for human review even though it is not in the id.
- **Multi-manager fan-out is collect-once → rederive-many.** The existing spine is strictly
  one-in/one-out (`collect_inputs → ProviderInputs` → `rederive → RederivedProposal` → `run_apply`
  fences **one** proposal). `dependency-bump` must not silently paper over this:
  `_collect` materializes F4 evidence **once** and resolves the finding **once**; `_rederive`
  returns the list of per-manager proposals; the driver **authorizes each, then fences and runs
  each sequentially** — one journal/ledger step per proposal id, a shared pen (manager groups are
  disjoint repo sets with one argv each). N independent `run_apply` invocations are **not**
  acceptable (they would re-materialize F4 evidence N× and race themselves).
- **Authorization** is the existing `apply_authorization.authorize` over `permitted_repos` +
  per-repo `bound_paths`; the workspace `apply-authorization.yaml` must authorize the manifest/lock
  paths for the bump transformation (a data change in `hiivmind/hiivmind-workspace`, not code).
- **Workspace absence by construction:** F4 v1 treats manager-declared workspaces as wholesale
  `unsupported`, so workspace-member repos produce no comparable `PackageRecord` and never enter
  findings or selection — no monorepo-member handling is needed in v1.

### 4.8 `resolve_intended_base` branch (apply_reconcile.py)

`run_apply` calls `apply_reconcile.resolve_intended_base(rederived.source_kind, …)`
unconditionally; it currently raises `ValueError("unknown source_kind")` for anything outside the
four known sources, which the driver converts into a whole-run `blocked`. **Without a branch,
`dependency-bump` dies before the lease.** Add:

```
dependency-bump → dict[repo, default_branch] for the proposal's selection,
                  from fleet meta (the same default-branch map § 4.4 already resolves)
```

Carry it through the same channel neutral uses (`finalizer_record`), so `base_refs` is populated
per repo exactly as the neutral multi-repo path does.

## 5. Error handling

| Condition | Outcome |
|-----------|---------|
| finding address resolves nothing | `RederiveError` (whole-run `blocked`) |
| finding `distance == "unresolved"` | `RederiveError` (fail-closed) |
| selection empty (every repo already at target) | `RederiveError` ("nothing to do") |
| repo's declaration is `dev`/`optional` | per-repo `blocked` (`non-main-group-package`) |
| a manager has no transform entry | per-manager `blocked`; other managers proceed |
| evidence `tree_sha` missing for a repo | per-repo `blocked` |
| repo's tree moved between evidence and apply | `stale-tree`: per-repo `blocked` (§ 4.4 step 7) |
| repo's commit moved between collect and provision | existing `stale-base` provision gate blocks per-repo |
| `transform_params` key/value fails validation | `RederiveError` (fail-closed) |

## 6. Testing

1. **`resolve_argv` templating** — declared-key expansion; undeclared `{key}` → error; missing
   declared value → error; value failing `_validate_param_value` (leading `-`, `=`, whitespace,
   metachar) → error; `None` params → verbatim argv (backward compat).
2. **`_validate_param_value` param shapes** — scoped npm package `@scope/name` accepted;
   bare name accepted; PEP 440 epoch `1!2.3.4` rejected; leading `-` rejected for both params.
3. **`build_proposal` `transform_params`** — unknown key rejected; missing declared key rejected;
   empty for non-templated entries; round-trips into `proposal_digest`.
4. **Target/selection** — semantically-highest target (incl. `2.10.0 > 2.9.0`,
   `2.0.0 > 2.0.0rc1`); only diverging repos selected; empty selection → error.
5. **Unresolved rejection** — `distance == "unresolved"` → `RederiveError`.
6. **Main-group restriction** — dev/optional-declared repo → per-repo `blocked`, not promoted.
7. **Manager split** — mixed-manager finding → N proposals with correct transforms/bound_paths;
   unmapped manager (pdm/conda/pip-tools/yarn1) → blocked group.
8. **`bump_proposal_id`** — deterministic over (ecosystem, package, manager, selection); distinct
   from neutral fleet id; target-independent.
9. **`resolve_intended_base`** — `dependency-bump` returns the per-repo default-branch map; no
   `ValueError`.
10. **Integration** — finding → proposals → driver (collect-once, rederive-many, sequential
    fenced runs) with fake ops through `pr_opened`; reconcile detects merge.
11. **Live proof** — a 2-repo single-manager bump (one Python coherence group, two `uv` repos with
    a diverging main-group package) → two branches → two PRs → merge → `applied`.

## 7. Non-goals (v1 scope guard)

- **Range preservation** — v1 pins exact (`==V` / `--save-exact`); preserving the original
  manifest range style (or honoring `same-major`/`same-minor` as a *constraint* target rather than
  a *check* policy) is a follow-up.
- **Declared per-package targets** — target is always max-locked (§ 2.1); no `target:` config.
- **`dev`/`optional`-group bumps** — v1 blocks them (§ 4.4 step 5); threading declaration group
  through the finding and splitting per `(finding, manager, group)` with group-aware flags
  (`uv add --group dev`, `npm i --save-dev`) is backlog — it requires the finding/selection shape
  to carry group, a cross-cut into F4.
- **PEP 440 epochs** — version strings containing `!` are rejected (fail-closed, § 4.3).
- **Multi-package proposals** — one proposal per (finding, manager); batching N packages into one
  proposal/pen is out of scope.
- **pip-tools / pdm / conda / yarn1** — manager transforms added only when a fleet consumer exists
  (§ 4.5).
- **Scheduled auto-apply / `allow`** — unchanged, still gated behind the `🔵 v2` confirmation-model
  design (dependency-bump inherits `mutation_policy="allow-listed"`, PR-gated).
- **nave changes** — the bump itself is a `nave pen exec` command exactly like `format-python`;
  the one nave change is **provisioning reporting a locally-computed `observed_tree_sha`**
  alongside the existing `observed_base_sha` (§ 4.4 step 7) — additive, no new API calls, no
  evidence-schema change.
