# Dependency-Bump Apply Handoff (F11 ← F4) — Design Spec

**Date:** 2026-08-15
**Status:** Approved (brainstorm)
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
`resolve_argv`), `lib/pulse/scripts/apply_phases.py` (`exec_phase`).

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
   PEP 440 / semver comparator F4 already uses to compute `distance`) — not lexicographic string
   order, which mis-orders `2.10.0` vs `2.9.0`. Deterministic, zero new config: the repo that was
   semantically ahead becomes the source of truth. No `target:` field in `dependencies.yaml` (a
   later, separable refinement if align-up proves wrong).
2. **Whitelisted argv templating**, not a bump-spec file or a first-class `nave pen bump` verb.
   The bump stays a plain `TransformationEntry` whose `command_argv` contains `{package}` /
   `{version}` placeholders; the driver expands them from a new `Proposal.transform_params` field.
   No nave change is required.
3. **New `dependency-bump` source kind** (not a neutral transformation + extended binding). A
   finding is derived, not authored, and the neutral binding shape cannot carry the derived target;
   the alternative still needs the `Proposal` extension, so it buys nothing.
4. **One proposal per (finding, manager).** A finding's repos can span managers (uv / poetry /
   npm / pnpm) whose bump commands differ; each manager group becomes its own homogeneous
   proposal. v1 pins **exact** (`==V` / `@V --save-exact`); range preservation is a non-goal (§ 8).

## 3. Architecture — what reuses vs. what changes

| Layer | Today | Change |
|-------|-------|--------|
| `mutation_plan.Proposal` | `transformation: str` only | **`transform_params: dict[str, str]`** |
| `mutation_plan.TransformationEntry` | `command_argv` (strict) | **`params: tuple[str, ...]`** (declared placeholders) |
| `mutation_plan.resolve_argv` | returns `command_argv` verbatim | **expands `{key}` from `transform_params`** |
| `apply_phases.exec_phase` | `resolve_argv(entry)` | passes `proposal.transform_params` |
| `apply_rederive` sources | neutral / plan-sync / generated-artifact / marketplace-sync | **`dependency-bump` provider** |
| `apply_driver` | `--binding-ref` (neutral) / `--recorded-summary` | **`--finding-ref`** for `dependency-bump` |
| fence / lease / journal / phases / PR / reconcile / rollup | multi-repo already | none |
| nave | owns clone writes | none (this is pulse-gh only) |

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
  `_validate_param_value` before insertion. The result is a plain string tuple handed to
  `subprocess.run(..., shell=False)` exactly as today.

**Security rationale.** The strict-argv rule existed to prevent *flag injection* (runtime data
being reinterpreted as argv flags) and, secondarily, shell metacharacter smuggling. Templating
reopens only the first, so § 4.3's value validator is the compensating control: a value that
cannot begin with `-` and cannot contain `=` / whitespace / shell metacharacters cannot become a
flag or an argument separator. There is still no shell anywhere in the path (`shell=False` is
unchanged).

### 4.3 Parameter value validation (`_validate_param_value`)

One conservative validator for all params, in `mutation_plan.py`:

```
value must be non-empty and match ^[A-Za-z0-9][A-Za-z0-9._+~-]*$
```

i.e. **first character alphanumeric** (no leading `-`), body limited to `[A-Za-z0-9._+~-]` (no
`=`, no whitespace, no `;|&$\`"'<>()` or other metacharacters). Package names (normalized
identities) and versions (PEP 440 / semver) satisfy this by construction; anything that does not
is rejected at re-derive time (`RederiveError`), never at exec time.

### 4.4 The `dependency-bump` source kind (apply_rederive.py)

Add `"dependency-bump"` to `SOURCE_KINDS` and a provider pair mirroring the neutral one:

**Input / finding address.** A finding is addressed by the triple `(group, ecosystem, package)`,
which is unique per package per group. The driver accepts it as JSON:
`--finding-ref '{"group":"core-runtime","ecosystem":"python","package":"requests"}'`.

**`_collect_dependency_bump(finding_ref, io_seams)`** (pre-fence, whole-run gates):

1. Re-derive the finding **fresh** from F4 evidence — the same compare path that produces the
   healthcheck `fleet.dependencies.coherence` findings — and locate the one finding matching
   `(group, ecosystem, package)`. Missing finding → `RederiveError` ("nothing to do" is never a
   silent no-op). (Implementation detail: reuse the F4 fleet `compare` / evidence materialization;
   the contract is freshness + exact-address resolution, not the specific loader.)
2. Compute `target` = the **semantically highest** `locked_version` among the finding's non-`None`
   versions, reusing F4's version comparator (not `max()` over strings).
3. **Selection** = `{repo for (repo, v) in finding.versions if v is not None and v != target}`
   (only diverging repos; unresolved `None` repos are excluded, not bumped). Empty selection →
   `RederiveError`.
4. **Split by manager**: map each selected repo to the `PackageRecord` keyed by
   `(repo, ecosystem, name=package)` in the same F4 evidence and take its `manager`; group repos by
   manager. Each `(manager, repos)` group becomes one proposal (§ 4.5).
5. **Per-repo HEAD** via `io_seams.gh_api(repos/{o}/{n}/branches/{base})`, base = each repo's
   default branch (fleet meta), as in the neutral multi-repo path. Per-repo HEAD failure is a
   per-repo blocked outcome (repo dropped from selection), not a whole-run abort.
6. **`bound_paths[repo]`** = the `PackageRecord.manifest_path` + `lock_path` for that repo (both
   repo-relative; `None` entries omitted). These are exactly the files the bump touches, so commit
   and validation stay scoped.

**`_rederive_dependency_bump(...)`** builds, per manager group, a `Proposal`:

```
transformation  = MANAGER_TRANSFORM[manager]           # § 4.5
transform_params = {"package": finding.package, "version": target}
selection       = tuple(sorted(group_repos))
expected_shas   = {repo: head_sha for repo in group_repos}
bound_paths     = {repo: (manifest_path, lock_path) present}
mutation_policy = "allow-listed"
id              = bump_proposal_id(ecosystem, package, manager, selection)   # § 4.6
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

`MANAGER_TRANSFORM` (a module-level map in `apply_rederive.py`) keys `PackageRecord.manager` →
transformation id; a manager with no entry is a per-manager blocked outcome ("no bump transform
for manager X"), so the rest of the finding still proceeds. (pip-tools / yarn are added the same
way when a consumer exists; not in v1.)

### 4.6 Deterministic proposal id (`bump_proposal_id`)

```
apply-bump-{ecosystem}-{package}-{manager}-{sha256(sorted selection)[:12]}
```

Stable over the bump's identity (ecosystem, package, manager, membership); the **target version is
not part of the id** — it is a re-derived value. A changed target re-derives through the same id
and re-reconciles (consistent with "apply re-derives from fresh source state"); a membership or
manager change yields a new id. Distinct from the neutral fleet id so the two never collide.

### 4.7 Driver + recorded summary + authorization (apply_driver.py)

- `--source-kind dependency-bump` takes `--finding-ref` (JSON triple) instead of `--binding-ref`.
  `recorded_summary` is **synthesized** (`bump_summary(finding_ref, target, selection, manager)` →
  `{binding: <finding_ref>, transformation: <bump transform>, proposal_id}`), matching how neutral
  synthesizes its summary (no propose phase).
- **Multi-manager fan-out**: `_collect` returns one proposal per manager group; the driver runs
  each through the same fenced `run_apply` spine sequentially (one pen/journal per proposal id).
  A manager group that is empty or has no transform is skipped with a recorded reason.
- **Authorization** is the existing `apply_authorization.authorize` over `permitted_repos` +
  per-repo `bound_paths`; the workspace `apply-authorization.yaml` must authorize the manifest/lock
  paths for the bump transformation (a data change in `hiivmind/hiivmind-workspace`, not code).

## 5. Error handling

| Condition | Outcome |
|-----------|---------|
| finding address resolves nothing | `RederiveError` (whole-run `blocked`) |
| finding has zero non-`None` versions | `RederiveError` |
| selection empty (every repo already at target) | `RederiveError` ("nothing to do") |
| a manager has no transform entry | per-manager `blocked`; other managers proceed |
| per-repo HEAD fetch fails | per-repo `blocked`; repo dropped from selection |
| `transform_params` key/value fails validation | `RederiveError` (fail-closed) |
| stale base (repo moved since evidence) | existing provision gate blocks per-repo |

## 6. Testing

1. **`resolve_argv` templating** — declared-key expansion; undeclared `{key}` → error; missing
   declared value → error; value failing `_validate_param_value` (leading `-`, `=`, whitespace,
   metachar) → error; `None` params → verbatim argv (backward compat).
2. **`build_proposal` `transform_params`** — unknown key rejected; missing declared key rejected;
   empty for non-templated entries; round-trips into the proposal digest.
3. **Target/selection** — max-locked target; only diverging repos selected; `None` versions
   excluded; empty selection → error.
4. **Manager split** — mixed-manager finding → N proposals with correct transforms/bound_paths;
   unknown manager → blocked group.
5. **`bump_proposal_id`** — deterministic over (ecosystem, package, manager, selection); distinct
   from neutral fleet id.
6. **Integration** — finding → proposal → driver with fake ops through `pr_opened`; reconcile
   detects merge.
7. **Live proof** — a 2-repo single-manager bump (one Python coherence group, e.g. two repos on
   `uv` with a diverging package) → two branches → two PRs → merge → `applied`.

## 7. Non-goals (v1 scope guard)

- **Range preservation** — v1 pins exact (`==V` / `--save-exact`); preserving the original
  manifest range style (or honoring `same-major`/`same-minor` as a *constraint* target rather than
  a *check* policy) is a follow-up.
- **Declared per-package targets** — target is always max-locked (§ 2.1); no `target:` config.
- **Multi-package proposals** — one proposal per (finding, manager); batching N packages into one
  proposal/pen is out of scope.
- **pip-tools / yarn** — manager transforms added only when a fleet consumer exists.
- **Scheduled auto-apply / `allow`** — unchanged, still gated behind the `🔵 v2` confirmation-model
  design (dependency-bump inherits `mutation_policy="allow-listed"`, PR-gated).
- **nave changes** — none; the bump is a `nave pen exec` command exactly like `format-python`.
