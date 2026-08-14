# Apply-Mode Workspace Enrollment — Design Spec

**Date:** 2026-08-14
**Status:** Approved (brainstorm) — pending implementation plan.
**Origin:** `docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md` § 5F
("Workspace enrollment (`hiivmind/hiivmind-workspace`) — gated on an installed engine"), and the
plan follow-up of `docs/superpowers/plans/2026-07-30-apply-mode-pulse-wiring.md` ("Workspace
enrollment PR: `ApplyAuthorization` policy + a real neutral proposal source, gated on the
installed engine").

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

There is **no neutral source kind**. The neutral transformations in the registry
(`format-python`, `refresh-node-lockfile`, `regenerate-docs-index`, `regenerate-from-template`)
are executable entries with no propose driver and no re-derivation provider, so `run_apply`
cannot mint an allow-listed proposal for any of them today. The workspace
(`hiivmind/hiivmind-workspace`, a.k.a. `~/git/hiivmind/.hiivmind/github/`) also carries **no**
`ApplyAuthorization` policy and **no** binding files of any kind.

F11's "production wiring" therefore stalls one step short of runnable: the driver and the Nave
verbs are merged, but nothing tells apply-mode *what* to land. This closes that gap with the
flagship neutral use case.

## 2. Decisions (settled in brainstorm)

1. **New neutral provider** — a 4th source kind (`"neutral"`) in `apply_rederive`, not a reuse of
   `generated-artifact` and not a hand-minted proposal. It is complete and reusable for every
   neutral transformation.
2. **Proof transformation** — `format-python` (`ruff format .`). It is deterministic (same base +
   ruff version → same output), which satisfies the v1 crash-resume "reset + re-exec" contract,
   and it is genuinely neutral (`applies_to: profile:python`, no `profile:claude-plugin`
   predicate).
3. **Proof repo** — `hiivmind/agent-kernel` (an external Python app repo: `src/ tests/ examples/`,
   `pyproject.toml`). External to both the corpus and the plugin, so the neutrality proof is not
   self-referential. `hiivmind/agno-oracle-demo` is the fallback (same shape).
4. **Pure-neutral → terminal at merge.** `format-python` has no base to advance; the merge gate is
   the end of the run (`applied`), no F8 bookkeeping PR.
5. **`mutation_plan.build_proposal` is the neutral builder.** Neutral transformations have no
   source-specific decision logic (that is the point); the proposal is "binding + live HEAD".
   The other three sources keep their real, source-specific builders untouched.

## 3. Architecture — two repos

```
pulse-gh (code):     apply_rederive gains SOURCE_KINDS "neutral" + provider
workspace (config):  apply-neutral.yaml (binding) + apply-authorization.yaml (policy)
```

The re-derivation registry already separates *collection* (`collect_inputs` → a typed provider
inputs dataclass) from *re-derivation* (`rederive` → the real builder). The neutral provider
follows that exact shape; no new machinery.

## 4. pulse-gh — the neutral provider

### 4.1 Interfaces

```python
# apply_rederive.py
SOURCE_KINDS = ("plan-sync", "generated-artifact", "marketplace-sync", "neutral")

@dataclass(frozen=True)
class NeutralProviderInputs:
    binding: Mapping[str, Any]        # the neutral binding (repo, transformation, bound_paths, base_ref)
    head_sha: str | None              # live HEAD of the binding's base_ref branch
    actor: Mapping[str, Any] | mutation_plan.Actor
    registry: mutation_plan.TransformationRegistry | None = None

ProviderInputs = (PlanSyncProviderInputs | GeneratedProviderInputs
                  | MarketplaceProviderInputs | NeutralProviderInputs)

def _collect_neutral(binding_ref, actor, io_seams) -> NeutralProviderInputs
def _rederive_neutral(inputs: NeutralProviderInputs) -> RederivedProposal
```

### 4.2 Collection (fresh state, no pen)

`_collect_neutral` resolves the target repo's **live `base_ref` HEAD** via the existing
`io_seams.runner` seam (the same `(argv, cwd) -> CompletedProcess` shape every source uses). It
makes a direct `gh api repos/{owner}/{name}/branches/{base_ref}` call for that branch's `sha` —
it does **not** reuse `marketplace_sync_run.fetch_remote_evidence` (that fetches marketplace
releases/docs, not a neutral repo's HEAD). It **never** reads SHAs from the caller-supplied
`binding_ref`, and it fails closed (`RederiveError`) when the HEAD evidence is missing.

### 4.3 Re-derivation

`_rederive_neutral` builds the proposal from the binding + fresh HEAD:

```python
mutation_plan.build_proposal(
    id=f"apply-{transformation}-{owner}-{name}",  # deterministic from (repo, transformation)
    selection=[binding["repo"]],
    transformation=binding["transformation"],
    expected_shas={binding["repo"]: head_sha},
    bound_paths={binding["repo"]: binding["bound_paths"]},
    mutation_policy="allow-listed",
    actor=actor,
)
```

Gating that fires inside this path (all fail-closed):

- the transformation id must exist in the registry and be **neutral** (reject plan-sync,
  generated, marketplace, and the F9 overlay ids);
- `build_proposal` already enforces exact, non-empty `bound_paths` coverage for allow-listed
  (Task 2) — the binding supplies them;
- `allow_scheduled` gating is left to `build_proposal`/the registry, as for the other sources.

### 4.4 `finalizer_record`

Neutral transformations have no F8 doc-blob base to advance, so `finalizer_record` is `None`
(exactly as the existing generated/marketplace providers emit). No change to the driver's
finalizer-persistence path (it already skips a `None` record).

### 4.5 Recorded-summary identity (no propose phase)

Neutral transformations have no F10 propose run to persist a `{binding, transformation,
proposal_id}` summary. The apply driver still requires `recorded_summary` so `authorize()` can run
its full identity + scope check. For neutral, `recorded_summary` is **synthesized from the
binding**: `{binding: binding["repo"], transformation: binding["transformation"], proposal_id:
<the deterministic id above>}`. `_rederive_neutral` returns `RederivedProposal(binding_id=
binding["repo"], ...)` so the `authorize()` binding-match (`recorded_binding ==
rederived.binding_id`) holds, and the deterministic id makes `proposal_id` stable across
re-derivation. The scope half of `authorize()` (transformation authorized, `selection ⊆
permitted_repos`, `bound_paths` within authorization) still applies unchanged — the binding is not
self-elevating.

## 5. workspace — binding + authorization

Two new config files in the workspace repo (`hiivmind/hiivmind-workspace`, flow `feature → main`):

```yaml
# apply-neutral.yaml
bindings:
  - repo: hiivmind/agent-kernel
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
shape is already pinned by that loader (`authorizations.<id> = {mutation_policy, permitted_repos,
bound_paths}`). The `apply-neutral.yaml` binding is consumed by the new `_collect_neutral`.

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
   - `_collect_neutral` returns `NeutralProviderInputs` with live HEAD for a bound repo;
   - `_rederive_neutral` returns an allow-listed `RederivedProposal` whose `selection`,
     `expected_shas`, `bound_paths`, and `mutation_policy` match the binding + HEAD;
   - fail-closed: missing HEAD evidence → `RederiveError`; a non-neutral transformation id
     (e.g. `plan-sync-doc-patch`) → `RederiveError`; empty/missing `bound_paths` →
     `MutationPlanError` (from `build_proposal`).
2. **Live proof** (not fixture): `gh-apply` on `hiivmind/agent-kernel` drives the real
   `apply_driver` → `pen_create` → `preflight` → `provision` (remote-base CAS) → `format-python`
   exec → validate → commit → push `pulse/apply/{id}` → open PR → merge-detect (base + head
   verified) → terminal `applied`. Pure-neutral, no base advance.
3. **Format-drift note.** `format-python` validates with `kind: none`, so a repo already
   ruff-formatted yields a zero-diff branch (the wiring still proves, but lands nothing). During
   implementation, check `agent-kernel` for real drift; if none, introduce a deliberate
   formatting inconsistency in a scratch clone for the proof (never committed to `agent-kernel`).

## 8. Scope notes & deferrals

- **Multi-repo apply** stays v2 — the binding is a list for shape symmetry, but v1 applies one
  repo per run (the driver already blocks `selection > 1` with "multi-repo apply is v2").
- **`refresh-node-lockfile` / `regenerate-docs-index` / `regenerate-from-template`** become
  available through the same `neutral` provider with no further code — only a binding + an
  `apply-authorization` entry each. Out of this PR's proof scope.
- **F4 fleet-wide dependency-coherence apply** remains out of scope (unchanged from the wiring
  spec); `format-python` is the neutral proof, not the coherence use case.
- **Tool-version pinning** (a ruff/npm/mkdocs version field on the binding) is a follow-up if a
  real non-determinism shows up; v1 relies on the pen's installed tool.
