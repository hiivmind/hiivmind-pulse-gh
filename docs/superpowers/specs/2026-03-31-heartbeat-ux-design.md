# Heartbeat UX: Frictionless Execution and Contextual Handoff

**Date:** 2026-03-31
**Status:** Approved
**Scope:** gh-heartbeat skill, workflow execution pattern, graphql execution pattern, permissions

## Problem

The heartbeat interaction requires 6-8 user approvals to complete a single workflow run. These fall into two categories:

1. **Skill-level re-confirmations** — After the user selects which workflows to run, downstream skills (workflow execution, operations, refresh) each re-ask for permission. Mid-flow discoveries like stale config add additional confirmation gates.
2. **Tool-level approvals** — The GraphQL execution pattern uses compound Bash commands (`cat > /tmp/q.graphql << 'QUERY' ... && gh api graphql`) that don't match existing `Bash(gh:*)` allowlist rules. Config file edits have no allowlist coverage at all.

Additionally, the heartbeat ends with a summary table and no suggestions — a dead end with no handoff to actionable next steps.

## Design

Three changes that work together:

### Change 1: Pre-Approved Downstream Execution

**Principle:** Once the user selects workflows in Phase 5, all downstream execution is pre-approved. No skill re-confirms.

**Heartbeat skill changes:**
- When executing selected workflows, add explicit guidance that downstream skills must not re-confirm. The user's workflow selection IS the approval.
- When stale config is detected mid-execution, auto-refresh and continue. Do not stop and ask.
- Read-only operations (which most workflow actions are) never need mutation confirmation regardless.

**Workflow execution pattern changes:**
- When invoked by heartbeat after user selection, skip the `auto: false` permission check — the heartbeat already handled approval.
- The `auto` flag retains its original meaning: whether the heartbeat itself runs the workflow without asking (Phase 4) vs presents it for selection (Phase 5). It does NOT gate execution after selection.

**Operations skill changes:**
- When invoked as a workflow action from heartbeat context, skip the gateway's Step 4 mutation confirmation.
- Read-only operations (list, show, summarize) should never trigger mutation confirmation regardless of caller.

### Change 2: Phase 7 — Contextual Handoff

Add a new Phase 7 to the heartbeat skill that presents actionable next steps derived from workflow results.

**Structure (always in this order):**

1. **Actions from findings** — Present if any workflows ran and produced actionable results. Each workflow type maps to specific suggestion patterns:

   | Workflow | Suggestion Pattern |
   |----------|--------------------|
   | project-sync | Items in actionable states: "Issue #9 is Approved — start implementing?" |
   | pr-lifecycle | PRs needing attention: "PR #15 needs your review" |
   | ci-monitor | Failed runs: "CI run failed on main — investigate?" |
   | issue-triage | New untriaged issues: "3 new issues need labels" |
   | stale-check | Stale items: "PR #8 has had no activity for 14 days" |
   | auto-refresh | Note what was refreshed (informational, not actionable) |

2. **Remaining workflows** — Present only if some triggered workflows were not selected. Offer to run them.

3. **Fallback** — Always end with `/gh` as an escape to the interactive menu.

**Example output (partial run):**

```
## What's Next

Based on what we found:
  - #9 Plan: Dev Ops Clarity is Approved — start implementing?
  - Board has 4 items in Implementing

Workflows not run this session:
  - pr-lifecycle, ci-monitor

Pick an action, run remaining workflows, or /gh for more options.
```

**Example output (complete run):**

```
## What's Next

Based on what we found:
  - #9 Plan: Dev Ops Clarity is Approved — start implementing?
  - PR #15 needs your review
  - CI run on main succeeded

Pick an action, or /gh for more options.
```

### Change 3: Reduced Tool-Level Friction

**GraphQL execution pattern (`lib/patterns/graphql-execution.md`):**

Change from compound Bash command to two separate tool calls:

| Step | Before | After |
|------|--------|-------|
| Write query | `cat > /tmp/q.graphql << 'QUERY' ...` (Bash) | Write tool to `/tmp/q.graphql` |
| Execute query | `gh api graphql -f query="$(cat /tmp/q.graphql)"` (same Bash call) | Separate Bash: `gh api graphql -f query="$(cat /tmp/q.graphql)"` |

The Write tool doesn't require explicit permission. The `gh api` call is already covered by `Bash(gh:*)`. No new allowlist rules needed for GraphQL execution.

**Allowlist addition (`.claude/settings.local.json`):**

Add one rule to cover config file edits:

```json
"Edit(.hiivmind/**)"
```

This covers config.yaml, freshness.yaml, poll-state.yaml, and workflow file edits.

## Files to Change

| File | Change |
|------|--------|
| `skills/gh-heartbeat/SKILL.md` | Add pre-approved execution context to Phases 4-5; add Phase 7 handoff |
| `lib/patterns/workflow-execution.md` | Skip auto-check when caller is heartbeat post-selection |
| `lib/patterns/graphql-execution.md` | Write tool + separate Bash instead of compound command |
| `.claude/settings.local.json` | Add `Edit(.hiivmind/**)` allowlist rule |

## Out of Scope

- Changes to workflow YAML definitions (auto flag, actions, triggers)
- Changes to the heartbeat shell hook (`hooks/heartbeat.sh`)
- Changes to the gateway command or intent mapping
- Changes to the operations skill's core execution logic (only its confirmation gate behavior changes)
