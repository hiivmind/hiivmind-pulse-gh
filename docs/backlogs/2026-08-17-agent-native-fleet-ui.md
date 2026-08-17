# Backlog: a visual/agent-native UI layer for the fleet program

**Date:** 2026-08-17
**Status:** Open, no spec
**Severity:** Product/architecture — new consumer-facing layer, largest-scope open item
**Found in:** user proposal, following the `lib/pulse` package-extraction capture
**Scope:** a new application, outside `hiivmind-pulse-gh` proper; consumes this program's
existing result contracts, proposals, and apply-mode driver as its backend

## Problem

Every surface this program has today is a Claude-session skill, a headless
CLI driver, or a PR diff. There is no visual, standing view of fleet state:

- **Project/issue/workflow state** lives in per-machine transients
  (`poll-state.yaml`, `project-snapshot.json`, `.project-changes.json`) and is
  only ever *read* inside a Claude session (`gh-heartbeat`) — there's no
  place to just look at it.
- **Discrepancies** (F4 `DivergenceFinding`s, F8 plan-sync conflicts, F5
  impact-audit stale edges, F6/F7 healthcheck `fail`/`warn` checks) are typed,
  structured findings (see `lib/patterns/headless-contract.md`) that today
  only ever surface as YAML fields a human reads via `cat` or a PR body.
- **Approvals** — the propose-only gate every mutating phase (F6 generic
  proposals, F11 apply-mode) is deliberately built around — happen via `gh pr`
  review or an interactive terminal confirmation. There is no dashboard of
  "here are N pending proposals, here is what each would change, approve/
  reject."
- **Running work** (a skill, a `lib/pulse/scripts/*.py` invocation, a `nave`
  verb) requires opening a terminal/Claude session and knowing which skill to
  invoke. There's no single surface where a user watches fleet state, spots a
  problem, and tells an agent "fix that" in the same place.

## Proposal

Build a visual UI on the [agent-native](https://github.com/BuilderIO/agent-native)
framework (BuilderIO): projects, statuses, workflows, and issues presented
visually; discrepancies the system already finds surfaced as a review queue;
approvals as a first-class UI action (not a PR review or terminal prompt); and
an LLM agent panel with the same fleet context that can invoke the skills,
`lib/pulse` scripts, and Nave tasks needed to act on what's shown.

### Why agent-native specifically fits this program's shape

agent-native's core primitive is `defineAction()`: **one implementation, every
surface** — UI (`useActionQuery`/`useActionMutation`), agent tool (chat),
HTTP, MCP, A2A, and CLI all resolve to the same action, with the same schema
validation and access checks, so nothing drifts out of sync between "what the
button does" and "what the agent can do." That is close to a direct match for
this program's own repeated pattern — one typed `run()` implementation
(`build_result`, `execute()`, etc.) invoked identically from an interactive
skill and a headless driver (`lib/patterns/headless-contract.md`,
`workflow-execution.md`). A fleet UI built on agent-native would define one
action per pulse capability (e.g. "run healthcheck," "run plan-sync," "apply
this proposal," "reconcile this repo") and get a button, a chat-callable
tool, and an MCP tool for free from a single definition — instead of needing a
bespoke API layer *and* a bespoke agent-tool layer maintained in parallel.

### Why the data substrate is unusually ready for this

This isn't starting from an unstructured CLI tool. `lib/patterns/headless-contract.md`
already defines **10 versioned, schema-validated result-contract kinds**
(`status`, `healthcheck`, `fleet-membership`, `refresh`, `workflow-run`,
`impact`, `repo-mutation`, `generated-artifact`, `plan-sync`, `apply-status`)
with a common `actor`/`errors` envelope, and every kind that can find a
problem already separates **`findings`** (typed, severity-graded discrepancies)
from **`proposed_actions`** (mutations a headless run declined to make) from
**`asks_recorded`** (decisions needing a human). That three-way split —
discrepancy / proposed fix / needs-a-human — is exactly the shape a
"discrepancies + approvals" UI needs, and it already exists as committed,
validated output today. `poll.py`'s Projects v2 GraphQL pipeline
(`check_projects`, bronze→silver→gold: `project-snapshot.json` →
`my_assignments`/`status_distribution` → `.project-changes.json`) is the same
story for the "projects, statuses" half of the ask.

## What this would require (real scope)

- **A cross-language action boundary.** agent-native is TypeScript/Node;
  `lib/pulse/scripts/*.py` and `nave` are Python and Rust, invoked today by
  subprocess (`uv run <script>.py`, `nave <verb>`) from Bash-driven skills.
  Each agent-native `defineAction()`'s `run()` body would shell out to those
  same binaries/scripts — this is exactly the boundary
  `2026-08-17-lib-pulse-package-extraction.md` is about cleaning up (real
  console entry points, no `{PLUGIN_ROOT}`-relative path coupling). **This
  item is a direct downstream consumer of that one** — a Node process has no
  natural way to resolve a Claude-plugin-root-relative script path; it needs
  an installed CLI to shell out to.
- **A read model for existing result contracts and committed state.** Actions
  reading `*-result.yaml` (per-machine, gitignored, transient — see
  `workspace-detection.md` § multi-machine topology), the committed
  `hiivmind-workspace` repo (`config.yaml`, `healthcheck.yaml`, `relationships.yaml`,
  `apply-authorization.yaml`, run ledgers under `runs/`), and backlog docs
  need a defined sync/refresh strategy into the app's own SQL database
  (agent-native is Drizzle-backed) — this is itself a design question: does
  the app poll git, run the existing headless skills on a schedule, or both?
- **An approvals action wired to the real apply-mode gate.** "Approve" in the
  UI must resolve to the same fenced, journaled, lease-guarded apply path
  (`apply_driver.py`, `apply_reconcile.py`, `ApplyLock`) that `gh-apply`
  drives today — never a shortcut that bypasses the lease/fence/journal
  machinery `2026-07-30-apply-mode-production-wiring-design.md` built.
- **Multi-machine / multi-user identity.** The `actor: {gh_login, machine,
  mode}` model this program uses throughout assumes a human at a machine
  running a Claude session. A hosted app introduces a genuinely different
  identity/session model (who is "logged in," whose GitHub token is used for
  writes, single-tenant vs. team-hosted) that has no answer yet — this is a
  real design fork, not a detail.
- **Deployment/hosting decision.** agent-native apps need a Nitro-compatible
  host and a SQL database — is this a local personal app (`pnpm dev` on a
  laptop, reading the local `hiivmind-workspace` checkout) or a shared hosted
  team app (reading/writing the committed workspace repo over the network)?
  Materially different auth, deployment, and multi-machine-state answers.
- **Scope cut for v1.** Given the size of this, a v1 should almost certainly
  be **read-only visualization + approvals for one already-built phase**
  (e.g. render `healthcheck-result.yaml` findings + let a user approve/reject
  F11 apply-mode proposals) before wiring every skill as an agent action.

## Evidence

- [`BuilderIO/agent-native`](https://github.com/BuilderIO/agent-native) —
  framework README: `defineAction()` → UI/agent/HTTP/MCP/A2A/CLI from one
  definition; Drizzle-backed, Nitro-hostable.
- `lib/patterns/headless-contract.md` — 10 versioned result-contract kinds,
  common `actor`/`errors` envelope, `findings`/`proposed_actions`/
  `asks_recorded` already the shared vocabulary for "discrepancy" and
  "needs approval" across every phase (F2–F11).
- `lib/pulse/scripts/poll.py` (`check_projects`, `_build_query`,
  `_silver_views`) — existing Projects v2 GraphQL bronze/silver/gold
  pipeline; the closest existing analog to "visually present projects,
  statuses" today, currently only consumed by `gh-heartbeat`'s text summary.
- `docs/backlogs/2026-08-17-lib-pulse-package-extraction.md` — the
  prerequisite cross-language boundary problem this item inherits directly.
- `docs/superpowers/specs/2026-07-30-apply-mode-production-wiring-design.md`
  — the lease/fence/journal apply-mode machinery an "Approve" button must
  drive through, not bypass.

## Notes

Design-first, and the largest single open item in this backlog by scope — a
new application, a new hosting/identity model, and a cross-language action
boundary, not a change inside `hiivmind-pulse-gh`. Should get its own
`brainstorming` → spec pass, and its sequencing should be considered relative
to `2026-08-17-lib-pulse-package-extraction.md` (this item's cleanest path
runs through that one landing first).
