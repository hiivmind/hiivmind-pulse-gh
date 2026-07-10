# Target Workflows: Lockstep Bindings Across Repos, Docs, and GitHub State

**Date:** 2026-07-10
**Status:** Proposed — living catalog; new workflows are added as entries in Part 3
**Companion spec:** `2026-07-10-workspace-root-and-headless-orchestration-design.md`
(the platform this catalog runs on; phase references P0–P7 point there)

## Purpose

The companion spec builds the machinery: workspace root, result contracts,
headless skills, deterministic Python, scheduler, and workflow schema v3.
This spec is the demand side — the concrete high-value workflows that
machinery exists to run, and the one shared primitive they all reduce to.

This is a living document. Each target workflow is a catalog entry (Part 3)
written against the common primitive (Part 2). New workflow ideas get an
entry here first; only if an entry cannot be expressed as a binding does the
platform spec need extending.

---

## Part 1: The Observation

Every candidate workflow so far is the corpus freshness model, generalized.
Corpus's core loop:

1. **Declare a binding** between two states (index entry ↔ upstream file@SHA)
2. **Snapshot both sides** deterministically
3. **Diff** — is the binding stale?
4. **Emit typed findings** (result contract)
5. **Reconcile** via recorded policy, or surface for human judgment

The target workflows differ only in what the two sides are:

| Workflow | Side A | Side B | Staleness signal |
|---|---|---|---|
| plan-sync | Planning/spec markdown in a central repo | Issue / project item / milestone | Doc git SHA vs artifact `updated_at` since last sync |
| impact-audit | Repo A `develop` head (watched paths) | Repo B's last integration-tested SHA of A | A's head moved past what B was validated against |
| dep-coherence | Repo A lockfile pin of dependency X | Repo B lockfile pin of dependency X | Resolved versions diverge |

**Design consequence:** build one primitive — the binding record — and each
workflow becomes configuration plus a thin skill, not a new subsystem.

---

## Part 2: The Binding Primitive

### 2.1 Binding record

A binding is: two references, the last-reconciled state of each side, and a
reconciliation policy.

```yaml
binding:
  id: <stable id>
  kind: plan-sync | impact | deps | <future>
  side_a: { ref: <locator>, last_reconciled: <blob/tree hash | timestamp> }  # content-addressed (I1)
  side_b: { ref: <locator>, last_reconciled: <blob/tree hash | timestamp> }
  base: { <field>: <value at last reconciliation>, ... }   # for multi-master kinds (I5)
  policy: <kind-specific reconciliation policy; per-field tie-breaks optional>
```

### 2.2 Where bindings live

Two homes, chosen by whether the binding travels with an artifact:

- **Artifact-carried** (corpus-style): plan-sync bindings live in the doc's
  frontmatter (`sync:` block) so the binding moves/renames with the doc and
  is reviewed in the same PR that edits the doc.
- **Workspace-carried:** repo-to-repo bindings (impact edges, dep-coherence
  scope/dismissals) live in the workspace repo — `relationships.yaml`
  gains edge-level state (see 3.2). Committed, team-shared, versioned (D1).

### 2.3 Execution shape (shared by all binding workflows)

```
poll.py source            → detects side A or B moved (heartbeat trigger)
gh-<kind>-headless        → snapshots both sides, diffs, emits <kind>-result.yaml
  findings[]              → typed, deterministic where possible, `inferred: true` where LLM judged
  proposed_actions[]      → reconciliations the policy allows but headless declined
  asks_recorded[]         → true conflicts needing human judgment
apply step                → PR-based (docs, config) or API mutations under
                            headless mutation policy (on_mutation: propose default)
scheduler                 → fleet-wide sweep via pulse-scheduler template
release-train gate        → binding currency usable as a v3 gate condition
```

### 2.4 Platform deltas required (all additive)

The companion spec's P0–P7 plan needs no structural change. This catalog
adds, per its own delivery:

- **New result kinds** — `plan-sync`, `impact`, `deps` (contract_version
  designed for additive kinds; extend `validate_result.py`).
- **New poll sources** — `docs`, `branch_heads`, `lockfiles` in `poll.py`.
- **Edge-level state in `relationships.yaml`** — `watch_paths`,
  `integration_tested_sha`, dep-coherence dismissal scope.
- **Fleet-scoped healthcheck checks** — check catalog gains `scope: fleet`
  (current checks are per-repo).
- **New Python** — `impact.py`, `deps.py`, doc-frontmatter parse/patch
  helpers for plan-sync.

### 2.5 Cross-cutting invariants

Failure modes observed in advance; every catalog entry MUST satisfy these.
Entries note deviations explicitly (see the 3.7 template).

**I1 — Staleness is content-addressed and path-scoped, never repo-head.**
A file binding stores the **blob SHA** of the bound path (content hash), not
the repo's commit SHA. A repo can advance hundreds of commits without a
stable bound file changing — the binding is stale only when the *content it
binds* changed. Commit SHAs are kept alongside only where a diff *range* is
needed (impact-audit's `git diff sha..head -- paths` is already path-scoped
and satisfies this by construction). For rename survival use
`git log --follow` when a blob disappears. For directory-shaped bindings
(scaffold templates), use the **tree hash**
(`git rev-parse HEAD:templates/path`) — same property, directory-granular.

**I2 — Markers are shared; transients are per-machine.**
The team is M:M across individuals, GitHub profiles, and physical machines.
Anything that records *reconciled state* (binding `last_reconciled`,
`integration_tested_sha`, generation manifests, field bases) is durable and
shared: committed to the workspace repo or carried in artifact frontmatter —
**never machine-local**. Per-machine files (poll-state, snapshots,
`*-result.yaml`) are advisory caches only. Every reconciling run pulls the
workspace repo and re-reads markers *before* diffing; local poll-state is
never authority. Consequence: any teammate's machine (or the scheduler) can
run any workflow and reach the same conclusion.

**I3 — Concurrency by idempotence + supersede, not locks.**
Two machines (or a scheduler plus a human session) may run the same workflow
concurrently. Therefore: (a) reconciliation is **idempotent** — re-running
against already-reconciled state is a no-op; (b) marker updates travel in
PRs, so concurrent runs produce competing PRs resolved by the
corpus-scheduler **supersede pattern** (a newer run, regenerated from
current state, closes older automated PRs only after its own PR exists);
(c) long-lived v3 runs may take a soft lease in the `runs/` ledger, but
leases are advisory — correctness never depends on them.

**I4 — Every mutation is attributed.**
Run records and result files record the acting human, GitHub profile
(`gh auth status` identity), and machine. Needed for audit, and so that
identity-sensitive logic (self-assignment, "you touched this" checks) works
when one person operates under multiple profiles from multiple machines.
The person↔profiles↔machines map lives in `user.yaml` (local) with an
optional team map in the workspace repo.

**I5 — No environment is primary: three-way merge over field bases.**
Changes legitimately originate in *any* environment — GitHub Projects, the
docs repo, the project repo on GitHub, a local clone — and must propagate in
whichever direction the change happened. Bindings therefore store, per bound
field, the **base**: the value at last reconciliation. On sync, compute
`delta_A = A − base` and `delta_B = B − base`; exactly one side changed →
propagate it; both changed → **conflict → `asks_recorded`**, never
auto-resolved. Field *ownership* survives only as an optional per-field
tie-break policy an entry may declare — it is a default conflict resolution,
not the propagation model.

**I6 — Only durable states are sync sources.**
A local working tree (uncommitted or unpushed work) is never read as a
binding side; bindings reconcile pushed commits and API state only. "Local
ahead of remote" is *detected and reported* as a finding (a nudge to push),
not synced from. This keeps every run reproducible from any machine (I2) and
prevents one teammate's half-finished local edits from propagating.

---

## Part 3: Workflow Catalog

Each entry: intent, binding definition, determinism split (Python vs LLM),
reconciliation policy, platform dependencies, and delivery status.

### 3.1 plan-sync — planning docs ↔ issues / project items / milestones

**Intent.** Backlog, spec, and planning markdown in a central repo (e.g.
`mountainash-central`) stay in lockstep with GitHub issues, project tasks,
and milestones — the way corpus keeps its index in lockstep with remote
sources. Docs stop drifting from the board; the board stops drifting from
the written plan.

**Binding.** Artifact-carried, in doc frontmatter:

```yaml
# frontmatter of plans/2026-q3-release.md
sync:
  issue: hiivmind/hiivmind-pulse-gh#42
  project_item: PVTI_xxx
  milestone: v5.0
  last_synced:
    at: 2026-07-01T10:00:00Z
    doc_blob: abc123           # blob SHA of this file at last sync (I1 — content, not repo head)
    base:                      # per-field values at last reconciliation (I5)
      title: "Q3 release plan"
      status: "In progress"
      assignees: [nathanielramm]
      milestone: v5.0
```

**The bidirectional model — three-way merge (I5).** Corpus sync is
one-directional (pull); plan-sync is multi-master: title edits happen in the
doc, status moves happen on the board, either may also happen in the other
place, and *no environment is primary*. Per bound field, diff each side
against the stored `base`:

- only the doc changed → propagate doc → GitHub
- only GitHub changed → propagate GitHub → doc
- both changed → **conflict → `asks_recorded`**, never auto-resolved
- neither → no-op (idempotence, I3)

The base for scalar fields is stored inline in `sync.last_synced.base` (kept
compact — spec *body* content uses the doc blob SHA as its base, retrievable
from git history, rather than an inline copy). The earlier field-ownership
idea survives only as optional per-field tie-break policy
(`sync.policy.title: prefer-doc`) for teams that want auto-resolution of
specific conflicts; the default resolves nothing.

Staleness detection is I1-compliant on both sides: the doc side compares the
file's current blob SHA against `doc_blob` (commits elsewhere in the docs
repo never trigger a sync); the GitHub side compares field values against
`base` (not `updated_at` alone, which moves on unrelated activity like
comments). Doc-side syncs read the **pushed** state of the docs repo, never
a teammate's local working tree (I6).

**Determinism split.** Python: frontmatter parse, SHA/timestamp diff,
desired-state computation, issue-body patch generation. LLM (flagged
`inferred`): matching a *new, unlinked* doc to an existing issue; drafting an
issue body from a new spec doc.

**Reconciliation application.** GitHub-side mutations via gh-operations under
headless mutation policy; doc-side changes always via PR to the central repo
(never direct commit to main).

**Trigger.** Heartbeat `docs` poll source (central repo head moved) OR
existing `issues`/`projects` sources (artifact side moved); scheduled sweep
via pulse-scheduler.

**Depends on:** P1 (contract), P2 (poll source), P3-conventions, P4
(mutation policy). Benefits from P6 (a release-train can gate on "plan docs
in sync for milestone X").

**Status:** proposed.

### 3.2 impact-audit — cross-repo dependency change detection

**Intent.** When repo A's `develop` (or a feature branch) changes something
repo B depends on, the need for integration testing is *detected and
tracked*, not remembered. Corpus refresh semantics applied to dependency
edges: an edge is stale when upstream moved past what the dependent was
validated against.

**Binding.** Workspace-carried, extending `relationships.yaml`
`repo_dependencies` with edge-level state:

```yaml
repo_dependencies:
  hiivmind-corpus-scheduler:
    depends_on:
      - repo: hiivmind-corpus
        watch_paths:                      # the interface surface B consumes
          - "skills/hiivmind-corpus-refresh-headless/**"
          - "lib/corpus/patterns/headless-contract.md"
          - "lib/corpus/scripts/validate_result.py"
        watch_branch: main                # or develop
        integration_tested_sha: abc123    # last A-SHA validated against
        tested_at: 2026-07-01T10:00:00Z
```

**Detection is fully deterministic** (`impact.py`): per edge,
`git diff {integration_tested_sha}..{watch_branch head} -- {watch_paths}`;
any hit ⇒ edge stale, with the file list as evidence. LLM judgment enters
only for *severity* — breaking vs additive — emitted as a finding with
`inferred: true`.

**Findings → actions.** Per stale edge: open/update a tracking issue on the
dependent repo ("integration test against A@{sha}; changed: {files}"),
optionally trigger the dependent's integration-test workflow. Closing the
loop: a successful integration run updates `integration_tested_sha` —
which is itself a plan-sync-style mutation applied by PR to the workspace
repo.

**Release-train integration (the payoff).** Edge currency becomes a v3 gate
condition: `gate: all edges into {repo} current` — a release cannot proceed
past unvalidated upstream drift.

**Trigger.** New `branch_heads` poll source (cheap: `git ls-remote` per
watched branch — the corpus status-headless trick); scheduled sweep.

**Depends on:** P1, P2 (poll source + `impact.py`), P3-conventions. Gate
usage depends on P6.

**Status:** proposed.

### 3.3 dep-coherence — third-party version-lock divergence

**Intent.** Detect when third-party dependency pins diverge across the fleet
(repo A on polars 1.9, repo B on 0.20) or when a lockfile drifts from its
manifest range. Today this is discovered by accident; it should be a
standing fleet check.

**Binding.** Implicit pairwise bindings over a workspace-level snapshot —
no per-edge records needed. `deps.py` parses every repo's manifests and
lockfiles (`uv.lock`, `pyproject.toml`, `package.json`/lock, plugin.json
dependencies) into a BRONZE artifact:

```
{workspace}/.hiivmind/github/deps-snapshot.json
  { dep → { repo → { manifest_range, locked_version, source_file } } }
```

Divergence detection is then a pure table operation: same dependency,
different resolved versions across repos; severity scored by semver distance
(major > minor > patch). Zero LLM involvement in detection.

**Delivery vehicle: the first fleet-scoped healthcheck check.** Extends the
check catalog with `scope: fleet` (existing checks are per-repo). Runs inside
`gh-healthcheck-headless`; results land in the fleet report PR. Intentional
divergence uses the **existing dismissal mechanism** unchanged
(`dismissals` with reason + `review_after`) — e.g. "repo X pinned old
polars deliberately, review after 2026-09".

**Depends on:** P1, P2 (`deps.py`), P3.2 (healthcheck-headless). No P4/P6
dependency — **this is the earliest shippable entry** and a good first proof
of fleet-scoped machinery.

**Status:** proposed.

### 3.4 fleet-membership — org repo list ↔ workspace catalog (+ onboarding cascade)

**Intent.** The workspace `repositories[]` catalog silently under-covers the
moment a repo is created, archived, or transferred — and every fleet sweep
(healthcheck, dep-coherence, scaffold-drift) inherits the blind spot. This
workflow keeps every *other* fleet workflow's scope honest.

**Binding.** Workspace-carried. Side A: the org's live repo list (GitHub
API). Side B: `repositories[]` in workspace config. Staleness: any repo in
exactly one side (new/archived/transferred/renamed).

**The onboarding cascade.** Detection is trivial; the value is what a new
repo triggers: register in the catalog → apply governance baseline (see
3.6.3 governance-parity) → seed labels/milestones → create scheduler stub if
the repo class warrants one → open a checklist issue for the non-automatable
steps. Archival triggers the reverse (retire stubs, close tracking issues).

**Determinism split.** Python: list diff, catalog patch. LLM (`inferred`):
classifying the new repo (plugin / corpus-data / app / test) to pick the
right onboarding overlay — confirmed via `asks_recorded` on first sight.

**Reconciliation.** Catalog updates by PR to the workspace repo; onboarding
mutations under headless mutation policy (`propose` by default).

**Trigger.** Cheap org-level poll (`gh api orgs/{org}/repos` paginated head
count + newest `created_at`) added to `poll.py`; scheduled sweep.

**Depends on:** P1, P2, P3-conventions. Cascade steps mature with 3.6.3.

**Status:** proposed.

### 3.5 scaffold-drift — generator templates ↔ generated files downstream

**Intent.** Repos generated from templates drift from the generator. Two
live instances: the blueprint family (`hiivmind-blueprint` / `-central` /
`-lib` generating repos) and the corpus plugin's `templates/` generating
navigate skills inside every `hiivmind-corpus-*` data repo — template
changes currently strand ~15 corpus repos on stale generated skills with no
detection at all. Likely the highest-leverage entry in this catalog by
silent-failure surface.

**Binding.** Artifact-carried in the generated repo: a generation manifest
(`.generated.yaml`, or a stamp comment in the generated file) recording the
template source, template SHA at generation time, and the files it produced:

```yaml
# {generated-repo}/.generated.yaml
generated:
  - source: hiivmind/hiivmind-corpus@templates/navigate-skill/
    template_tree: abc123     # tree hash of the template dir (I1 — content-addressed,
                              # not repo commit SHA; unrelated plugin commits don't trigger)
    files:
      - path: skills/hiivmind-corpus-{name}-navigate/SKILL.md
        blob: def456          # blob SHA as generated (I5 base — detects local customization)
    generated_at: 2026-05-01T10:00:00Z
```

Side A: tree hash of the template directory at `watch_branch` head
(`git rev-parse {head}:templates/navigate-skill`). Side B: `template_tree`
in the manifest. Staleness: the tree hashes differ — commits elsewhere in
the template's repo never trigger regeneration (I1). The per-file `blob`
records the generated content as its I5 base: if the file's current blob no
longer matches, it was customized locally after generation, and both sides
have changed → conflict → `asks_recorded`, never overwritten.

**Determinism split.** Python: manifest parse, SHA diff, per-repo stale-file
list. LLM: performing the regeneration itself (templates have placeholders
filled from repo context — this is the corpus-init/build machinery re-run),
with the regenerated diff reviewed in a PR, never pushed direct. Local
customization detection is the per-file `blob` base check above.

**Reconciliation.** One PR per stale downstream repo; fleet sweep produces a
roll-up ("template X moved: 12 repos stale, 12 PRs opened / 2 conflicts").

**Bootstrap cost.** Existing generated repos lack manifests. A one-shot
backfill (analog of `hiivmind-corpus-migrate`) stamps current state as the
baseline — drift is then measured from backfill forward.

**Trigger.** `branch_heads` poll source (shared with 3.2 impact-audit)
watching template paths; scheduled sweep.

**Depends on:** P1, P2, P3-conventions; PR-application conventions from 3.2.

**Status:** proposed.

### 3.6 Shortlist — captured, not yet designed

Binding one-liners for accepted ideas awaiting full entries. Promote by
rewriting against the 3.7 template; keep the ID when promoting.

**3.6.1 marketplace-sync.** Plugin repo's latest release tag ↔ its entry in
`hiivmind-marketplace`. Deterministic detection, one-file PR to apply.
Small, concrete early win. *Prereq: P3.*

**3.6.2 split-repo-currency.** `hiivmind-pulse-gh` main HEAD ↔
`hiivmind-pulse-gh-tests` last-validated SHA. Impact-audit (3.2) with
`watch_paths: ["**"]` — likely a documented edge configuration rather than
its own skill. *Prereq: 3.2.*

**3.6.3 governance-parity.** Golden governance spec in the workspace repo
(protection, rulesets, merge settings, label taxonomy; org base +
repo-class overlays) ↔ each repo's live settings. Upgrades healthcheck from
"score" to "reconcile to declared standard" with `proposed_actions`.
Wants the golden-spec design conversation first. *Prereq: P3.2, P4.*

**3.6.4 contract-propagation.** Shared contract definition (e.g.
`headless-contract.md` + validator) ↔ each consumer's supported
`contract_version`. Impact-audit specialized to interface versions; the
binding architecture should audit itself. *Prereq: 3.2.*

**3.6.5 milestone-alignment.** Milestone "vX" in repo A ↔ same-named
milestones in train-scoped repos B, C (via `cross_project_coordination`,
today purely documentary). Staleness: due dates diverge or a blocking issue
sits in a closed milestone. *Prereq: P3; enforcement value rises with P6.*

**3.6.6 changelog-rollup.** Constituent repos' releases since last train ↔
org-level release note in the central repo. GATHER-and-draft (LLM drafts,
`inferred`), applied by PR to central. Natural final step of a v3
release-train. *Prereq: P6.*

**3.6.7 claude-md-currency.** A repo's CLAUDE.md claims ↔ its actual
structure (skills, directories, commands). Fuzzy verification — fits as a
fleet healthcheck check with `inferred` findings rather than a full binding
workflow. (This review caught pulse-gh's CLAUDE.md missing three skills by
accident; that detection should be standing.) *Prereq: P3.2.*

### 3.7 Entry template for future workflows

Candidates should be written as binding definitions using the entry template:

```
### 3.N <name> — <one-line intent>
**Intent.**  What drift does this eliminate?
**Binding.** Side A / Side B / staleness signal; artifact- or workspace-carried.
**Determinism split.** What is Python; what is LLM (inferred-flagged).
**Reconciliation.** Propagation directions; what is auto vs asks_recorded;
                    any per-field tie-break policy.
**Invariants.** How I1–I6 are satisfied; call out any deviation and why.
**Trigger.** Poll source(s); scheduled sweep?
**Depends on.** Platform phases + catalog deltas.
**Status.** proposed | accepted | building | live.
```

If an idea cannot be expressed as a binding (two sides + staleness +
reconciliation), that is signal it needs platform-spec work, not a catalog
entry — raise it against the companion spec instead.

---

## Part 4: Prioritization and Tracking

### 4.1 Scoring model

Entries are prioritized by **leverage** (silent-failure surface eliminated ×
number of repos/orgs affected) against **effort** (new machinery required
beyond what earlier entries prove) and **readiness** (are its platform
prerequisites and design decisions closed?). Priority bands:

- **PR1** — schedule as soon as prerequisites land
- **PR2** — schedule after PR1 entries prove the machinery they ride on
- **PR3** — valuable but gated on an unbuilt platform phase or an open
  design decision; do not start

Re-score when platform phases complete or when an org's pain shifts;
priorities are expected to move.

### 4.2 Prioritization and tracking table

Source of truth for catalog status and ordering (same convention as the
companion spec §8.9: update in the same commit as the work).
Status values: `proposed | accepted | building | live | retired`.
Leverage/effort: `low | med | high`.

| Entry | Workflow | Priority | Leverage | Effort | Prereqs | Rides on | Status | Live since |
|-------|----------|----------|----------|--------|---------|----------|--------|------------|
| 3.3 | dep-coherence | PR1 | high | low | P1–P3 | — (first fleet check) | proposed | |
| 3.4 | fleet-membership | PR1 | high | low | P1–P3 | 3.3's fleet sweep | proposed | |
| 3.6.1 | marketplace-sync | PR1 | med | low | P3 | 3.3's PR-apply shape | proposed | |
| 3.2 | impact-audit | PR1 | high | med | P1–P3 (gates: P6) | `branch_heads` source | proposed | |
| 3.5 | scaffold-drift | PR2 | high | med | P1–P3 + backfill | 3.2's `branch_heads` + PR apply | proposed | |
| 3.6.2 | split-repo-currency | PR2 | med | low | 3.2 | 3.2 (edge config only) | proposed | |
| 3.6.4 | contract-propagation | PR2 | med | low | 3.2 | 3.2 (version edges) | proposed | |
| 3.6.7 | claude-md-currency | PR2 | med | low | P3.2 | fleet checks (3.3) | proposed | |
| 3.1 | plan-sync | PR2 | high | high | P1, P2, P4 (P6 opt.) | PR-apply + policy patterns from PR1 set | proposed | |
| 3.6.3 | governance-parity | PR3 | high | med | P3.2, P4 + golden-spec design | fleet checks + mutation policy | proposed | |
| 3.6.5 | milestone-alignment | PR3 | med | low | P3 (value rises with P6) | release-train defs | proposed | |
| 3.6.6 | changelog-rollup | PR3 | med | med | P6 | release-train (P6.5) | proposed | |

### 4.3 Ordering rationale

- **PR1 wave** proves each new machinery class once, cheaply:
  3.3 dep-coherence (fleet-scoped checks, workspace BRONZE snapshot,
  zero-LLM detection), 3.4 fleet-membership (keeps every subsequent sweep's
  scope honest — anything fleet-wide silently under-covers without it),
  3.6.1 marketplace-sync (smallest end-to-end detect→PR loop), and
  3.2 impact-audit (edge state + `branch_heads` + one write-back mutation).
- **PR2 wave** is mostly configuration and reuse: 3.6.2 and 3.6.4 are
  impact-audit edge configurations; 3.6.7 is another fleet check;
  3.5 scaffold-drift reuses 3.2's source and PR machinery but adds the
  manifest backfill (highest leverage of the wave — ~15 stranded corpus
  repos); 3.1 plan-sync closes the wave because bidirectional field
  ownership is the largest judgment surface and benefits from every pattern
  established before it.
- **PR3 wave** is gated: governance-parity on the golden-spec design
  decision, milestone-alignment and changelog-rollup on P6 release-trains
  being real.

## Part 5: Open questions

- **Binding identity across renames:** artifact-carried bindings survive doc
  renames (frontmatter travels), and I1's blob-SHA + `--follow` handles the
  history side; but issue references in *other* docs don't. Is a
  workspace-level binding index (derived, regenerable from frontmatter)
  worth maintaining for reverse lookups? Lean: yes, as a derived artifact —
  never hand-edited (derivation-DAG rules apply).
- **Base storage growth:** I5 bases are compact for scalar fields but need a
  convention for rich content (current answer: blob-SHA-as-base for doc
  bodies; revisit if a kind needs field-level bases over large values).
- **Attribution map (I4) shape:** minimal viable version is the gh profile
  recorded per run; the full person↔profiles↔machines map should stay
  optional until a workflow actually needs cross-profile identity (e.g.
  "you touched this" checks in ci-monitor run headlessly on a shared box).
- **watch_paths maintenance:** who keeps the interface-surface globs honest as
  repos evolve? Candidate: a healthcheck check that flags edges whose
  watch_paths matched zero files in the last N diffs (dead globs).
- **plan-sync scope creep:** milestones and project items have richer
  lifecycle than issues (iterations, custom fields). v1 should bind
  issue + milestone only; project-item field sync deferred until the
  field-ownership table proves out.
- **Cross-workspace bindings** (e.g. mountainash-central in a different org
  than the code repos): the binding model doesn't care, but poll sources and
  auth scopes do. Defer until a real case exists.
