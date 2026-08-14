# Apply-Mode Workspace Enrollment — Design Spec

**Date:** 2026-08-14
**Status:** Approved (brainstorm) — revised after one adversarial design review (GLM-5.2 via
opencode-go, REQUEST CHANGES; all 4 must-fix + 8 minors incorporated). Pending implementation plan.
**Origin:** `docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md` § 5F
("Workspace enrollment (`hiivmind/hiivmind-workspace`) — gated on an installed engine"), and the
plan follow-up of `docs/superpowers/plans/2026-07-30-apply-mode-pulse-wiring.md`.

**Read alongside:** the production-wiring spec (§ 4 authorization model, § 5A–E components),
`lib/pulse/scripts/apply_rederive.py` (the re-derivation provider registry), and
`docs/backlogs/README.md` (the cross-repo dependency map — this is a two-repo item).

---

## 1. Problem — the neutral source gap

The apply driver (`apply_driver.run_apply`) re-derives a proposal from **fresh source state**
through `apply_rederive` before it authorizes or mutates. But `apply_rederive.SOURCE_KINDS` is:

```
("plan-sync", "generated-artifact", "marketplace-sync")
```

There is **no neutral source kind**. The standalone neutral transformations in the registry
(`format-python`, `refresh-node-lockfile`, `regenerate-docs-index`) are executable entries with no
propose driver and no re-derivation provider, so `run_apply` cannot mint an allow-listed proposal
for any of them today. The workspace (`hiivmind/hiivmind-workspace`, a.k.a.
`~/git/hiivmind/.hiivmind/github/`) also carries **no** `ApplyAuthorization` policy and **no**
binding files of any kind.

F11's "production wiring" therefore stalls one step short of runnable: the driver and the Nave
verbs are merged, but nothing tells apply-mode *what* to land. This closes that gap with the
flagship neutral use case.

## 2. Decisions (settled in brainstorm + review)

1. **New neutral provider** — a 4th source kind (`"neutral"`) in `apply_rederive`, not a reuse of
   `generated-artifact` and not a hand-minted proposal.
2. **Neutral transformation set** — exactly the three standalone, self-contained neutral
   transformations: `format-python`, `refresh-node-lockfile`, `regenerate-docs-index`. The
   generator-based `regenerate-from-template` (argv `nave generate --from-template`) routes through
   the F7 `generated-artifact` source, not the neutral provider; the two F9 overlays
   (`regenerate-corpus-navigate-skill`, `marketplace-entry-update`) are `profile:claude-plugin`
   and are **not** neutral. (Review M3.)
3. **Proof transformation** — `format-python` (`ruff format .`). It is deterministic (same base +
   ruff version → same output), which satisfies the v1 crash-resume "reset + re-exec" contract,
   and it is genuinely neutral (`applies_to: profile:python`, no `profile:claude-plugin`
   predicate).
4. **Proof repo** — `hiivmind/agent-kernel` (an external Python app repo: `src/ tests/ examples/`,
   `pyproject.toml`). `hiivmind/agno-oracle-demo` is the fallback (same shape).
5. **Pure-neutral → terminal at merge.** `format-python` has no base to advance; the merge gate is
   the end of the run (`applied`), no F8 bookkeeping PR.
6. **`mutation_plan.build_proposal` is the neutral builder.** Neutral transformations have no
   source-specific decision logic (that is the point); the proposal is "binding + live HEAD".
   The other three sources keep their real, source-specific builders untouched.

## 3. Architecture — two repos, six touch points

```
pulse-gh (code):     apply_rederive (4th source kind + helpers) + apply_reconcile (one branch)
workspace (config):  apply-neutral.yaml (binding) + apply-authorization.yaml (policy)
```

The re-derivation registry separates *collection* (`collect_inputs` → a typed provider inputs
dataclass) from *re-derivation* (`rederive` → the real builder). The neutral provider follows that
split, but it is **not** zero-touch: two shared dispatchers need source-kind branches. The complete
pulse-gh touch-point list (review C1/C2/M4):

1. `apply_rederive.SOURCE_KINDS` — add `"neutral"`.
2. `apply_rederive.ProviderInputs` union — add `NeutralProviderInputs`.
3. `apply_rederive.collect_inputs` — **identity resolution** (neutral uses `repo`, not `id`) and
   the **dispatch** (`if source_kind == "neutral": return _collect_neutral(...)`).
4. `apply_rederive.rederive` — `isinstance` dispatch to `_rederive_neutral`.
5. `apply_reconcile.resolve_intended_base` — add a `"neutral"` branch reading
   `binding_ref["base_ref"]`.
6. `apply_rederive._collect_neutral` / `_rederive_neutral` / `neutral_summary` /
   `neutral_proposal_id` — the provider itself.

`apply_authorization.py` is **unchanged** — its `load_authorization`/`authorize` already consume
the neutral authorization shape verbatim.

## 4. pulse-gh — the neutral provider

### 4.1 Interfaces

```python
# apply_rederive.py
SOURCE_KINDS = ("plan-sync", "generated-artifact", "marketplace-sync", "neutral")
NEUTRAL_TRANSFORMATIONS = ("format-python", "refresh-node-lockfile", "regenerate-docs-index")

@dataclass(frozen=True)
class NeutralProviderInputs:
    binding: Mapping[str, Any]        # {repo, transformation, base_ref, bound_paths}
    head_sha: str | None              # live HEAD of the binding's base_ref branch
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None

ProviderInputs = (PlanSyncProviderInputs | GeneratedProviderInputs
                  | MarketplaceProviderInputs | NeutralProviderInputs)

def neutral_proposal_id(binding) -> str            # single source of the deterministic id
def neutral_summary(binding) -> dict[str, str]     # the synthesized recorded_summary
def _collect_neutral(binding_ref, actor, io_seams) -> NeutralProviderInputs
def _rederive_neutral(inputs: NeutralProviderInputs) -> RederivedProposal
```

### 4.2 Collection (fresh state, no pen)

`_collect_neutral` resolves the target repo's **live `base_ref` HEAD** via the existing
`io_seams.gh_api` seam (`(endpoint) -> parsed JSON`, already used by plan-sync — review M5): it
calls `gh_api(f"repos/{owner}/{name}/branches/{base_ref}")["commit"]["sha"]`. It fails closed
(`RederiveError`) when `base_ref` is missing/non-string (review M6) or when the HEAD evidence is
missing. It **never** reads SHAs from the caller-supplied `binding_ref`; `base_ref` is read from the
binding, the SHA from the live API.

### 4.3 Re-derivation

`_rederive_neutral` builds the proposal from the binding + fresh HEAD:

```python
owner, name = binding["repo"].split("/", 1)
id = neutral_proposal_id(binding)          # f"apply-{transformation}-{owner}-{name}"
mutation_plan.build_proposal(
    id=id,
    selection=[binding["repo"]],
    transformation=binding["transformation"],
    expected_shas={binding["repo"]: head_sha},
    bound_paths={binding["repo"]: binding["bound_paths"]},
    mutation_policy="allow-listed",
    actor=actor,
)
```

Gating that fires inside this path (all fail-closed):

- `binding["transformation"]` must be in `NEUTRAL_TRANSFORMATIONS` — the explicit allowlist
  **is** the "transformation must be neutral" gate (review I1). This rejects `plan-sync-doc-patch`
  (which is `applies_to: always` and would pass a naive "no claude-plugin predicate" test), the F9
  overlays, and any unknown id, with `RederiveError`.
- `build_proposal` already enforces exact, non-empty `bound_paths` coverage for allow-listed
  (Task 2) — the binding supplies them.
- `allow_scheduled` is **not** gated here: `apply_driver._actor` hardcodes `mode="interactive"`,
  so scheduled-neutral gating is out of the re-derivation path (consistent with the other three
  sources — review M7). Scheduled neutral apply is v2.

### 4.4 `finalizer_record`

Neutral transformations have no F8 doc-blob base to advance, so `finalizer_record` is `None`
(only the generated-artifact provider emits `None` today; marketplace emits `{"base_ref": …}` —
review M1). The driver's finalizer-persistence path already skips a `None` record; the intended
base for neutral comes from `binding_ref["base_ref"]` via `resolve_intended_base`, not from a
finalizer.

### 4.5 Recorded-summary identity (no propose phase)

Neutral transformations have no F10 propose run to persist a `{binding, transformation,
proposal_id}` summary. The apply driver still requires `recorded_summary` so `authorize()` can run
its full identity + scope check. For neutral, **`run_apply` synthesizes it internally** (review I2):
when `source_kind == "neutral"` it computes `recorded_summary = neutral_summary(binding_ref)` =
`{binding: binding["repo"], transformation: binding["transformation"], proposal_id:
neutral_proposal_id(binding_ref)}` and ignores the `recorded_summary` CLI/kwarg (which is
meaningful only for the three propose-backed sources).

The id formula lives in **one** place — `neutral_proposal_id` — used by both `neutral_summary` and
`_rederive_neutral`, so the synthesized summary's `proposal_id` can never drift from the
re-derived proposal's `id`. `_rederive_neutral` returns `RederivedProposal(binding_id=
binding["repo"], …)` so the `authorize()` binding-match (`recorded_binding == rederived.binding_id`)
holds. The scope half of `authorize()` (transformation authorized, `selection ⊆ permitted_repos`,
`bound_paths` within authorization) still applies unchanged — the binding is not self-elevating.

### 4.6 Shared-dispatcher branches (review C1/C2)

- **`collect_inputs` identity** — the existing pre-check resolves `binding_id =
  binding_ref.get("plugin_id" if source_kind == "marketplace-sync" else "id")`. For neutral the
  binding is `repo`-keyed, so add: `binding_id = binding_ref.get("repo" if source_kind ==
  "neutral" else ("plugin_id" if source_kind == "marketplace-sync" else "id"))`. This makes the
  § 4.5 identity match (`binding_id == "hiivmind/agent-kernel"`) hold instead of raising.
- **`collect_inputs` dispatch** — add `if source_kind == "neutral": return _collect_neutral(...)`
  before the existing fallthrough.
- **`resolve_intended_base`** — add `if source_kind == "neutral": return _required(binding_ref
  ["base_ref"])` (mirroring the plan-sync fallback), before the final
  `raise ValueError(f"unknown source_kind: {source_kind}")`.

## 5. workspace — binding + authorization

Two new config files in the workspace repo (`hiivmind/hiivmind-workspace`, flow `feature → main`):

```yaml
# apply-neutral.yaml
bindings:
  - repo: hiivmind/agent-kernel        # single-repo scalar; multi-repo is N bindings (v1)
    transformation: format-python
    base_ref: main
    bound_paths:
      - src/**
      - tests/**
      - examples/**
```

```yaml
# apply-authorization.yaml
authorizations:
  format-python:
    mutation_policy: allow-listed
    permitted_repos:
      - hiivmind/agent-kernel
    bound_paths:
      hiivmind/agent-kernel:
        - src/**
        - tests/**
        - examples/**
```

`apply-authorization.yaml` is consumed verbatim by `apply_authorization.load_authorization` — the
shape is already pinned by that loader. The `apply-neutral.yaml` binding is consumed by
`_collect_neutral`; its `repo` is a **single-repo scalar** (review M8): a multi-repo intent is
expressed as multiple bindings in the list, each applied by a separate single-repo run (the
driver's `selection > 1` guard is the backstop, not the schema).

## 6. Determinism & installed-engine gate

- **Determinism.** `ruff format .` is deterministic given a pinned ruff version, so a crash
  between `pen_exec` and the journal's completion receipt recovers by reset + re-exec (v1
  contract). The neutral binding does **not** carry a tool version pin; the pen's installed ruff
  version is the operative pin (same stance as `refresh-node-lockfile`'s npm).
- **Installed-engine gate.** The enrollment PR is gated on the § 3 Nave verbs **and** pulse-gh
  being locally installed (`uv`-installed, per the single-developer context). This is a
  **deployment precondition**, verified before the live proof run — not a code deliverable. The
  live proof fails closed at the capability handshake if Nave is stale/absent.

## 7. Acceptance

1. **pulse-gh unit tests** (new `test_apply_rederive_neutral` cases):
   - `collect_inputs("neutral", …)` returns `NeutralProviderInputs` with live HEAD for a bound
     repo, and passes the § 4.6 identity pre-check (no `RederiveError` on a `repo`-keyed binding);
   - `_rederive_neutral` returns an allow-listed `RederivedProposal` whose `id`, `selection`,
     `expected_shas`, `bound_paths`, and `mutation_policy` match the binding + HEAD, and whose
     `id == neutral_proposal_id(binding)` (single-source id);
   - `resolve_intended_base("neutral", {"base_ref": "main"}, None) == "main"`;
   - fail-closed: missing HEAD evidence → `RederiveError`; missing `base_ref` → `RederiveError`;
     a non-neutral transformation id (`plan-sync-doc-patch`, `regenerate-corpus-navigate-skill`)
     → `RederiveError`; empty/missing `bound_paths` → `MutationPlanError` (from `build_proposal`).
2. **Live proof** (not fixture): `gh-apply` on `hiivmind/agent-kernel` drives the real
   `apply_driver` → `pen_create` → `preflight` → `provision` (remote-base CAS) → `format-python`
   exec → validate → commit → push `pulse/apply/{id}` → open PR → merge-detect (base + head
   verified) → terminal `applied`. Pure-neutral, no base advance.
3. **Format-drift is a hard requirement** (review M2). `format-python` validates with `kind:
   none`, but a no-op run (repo already ruff-formatted) fails at the **commit** boundary — nothing
   to stage → `git commit` nonzero — so it never reaches push/PR/merge-detect and only proves
   collect→provision. To exercise the full spine, the proof **must** land a real diff: check
   `agent-kernel` for genuine ruff drift, and if none, introduce a deliberate formatting
   inconsistency in a scratch clone for the proof (never committed upstream to `agent-kernel`).

## 8. Scope notes & deferrals

- **Multi-repo apply** stays v2 — `apply-neutral.yaml` is a list of single-repo bindings; v1
  applies one repo per run (the driver blocks `selection > 1` with "multi-repo apply is v2").
- **`refresh-node-lockfile` / `regenerate-docs-index`** become available through the same `neutral`
  provider with no further code — only a binding + an `apply-authorization` entry each. Out of
  this PR's proof scope.
- **`regenerate-from-template`** is **not** a neutral-provider transformation: its argv runs
  `nave generate --from-template` under the F7 generator-dispatch machinery, so it belongs to the
  `generated-artifact` source (review M3). Excluded from `NEUTRAL_TRANSFORMATIONS`.
- **F4 fleet-wide dependency-coherence apply** remains out of scope (unchanged from the wiring
  spec); `format-python` is the neutral proof, not the coherence use case.
- **Tool-version pinning** (a ruff/npm/mkdocs version field on the binding) is a follow-up if a
  real non-determinism shows up; v1 relies on the pen's installed tool.
