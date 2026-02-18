# ADR-014: Event-Driven Workflow System

**Status:** Accepted
**Date:** 2026-02-18

## Context

hiivmind-pulse-gh enriches GitHub operations with cached context but is purely reactive — it only acts when the user explicitly asks. Users miss important state changes between sessions: new PRs needing review, failed CI runs, stale issues, and outdated config caches.

**Key constraint:** This is a Claude Code CLI plugin, not a server. There are no webhooks, no daemons, and no persistent processes. The event system must work within Claude Code's hook model.

### Claude Code Hook Model

Claude Code provides event hooks that fire at specific lifecycle points:

- **SessionStart** — Fires once when a Claude Code session begins
- **PostToolUse** — Fires after each tool invocation completes
- **PreToolUse** — Fires before each tool invocation (already used for safety validation)

These hooks run shell scripts that can output JSON to influence Claude's behavior.

## Decision

Implement a poll-based event system using Claude Code hooks and a workflow YAML schema:

1. **SessionStart hook (heartbeat.sh)** — Polls GitHub for state changes on session start, diffs against cached poll state, and outputs a JSON summary of triggered workflows
2. **PostToolUse hook (post-operation-check.sh)** — Detects completed `gh` operations and matches them against post-operation workflow triggers
3. **Workflow YAML schema** — Declarative workflow definitions with trigger types (`session_poll`, `post_operation`, `freshness`, `on_demand`), action lists, cooldown enforcement, and an `auto` flag controlling whether workflows execute automatically or ask first
4. **Two new skills** — `hiivmind-pulse-gh-workflows` for CRUD management of workflows, and `hiivmind-pulse-gh-heartbeat` for handling wake-up actions when hooks detect pending work

### Workflow Storage

Workflow definitions live in `.hiivmind/github/workflows/` alongside existing config. Poll state is tracked in `.hiivmind/github/poll-state.yaml`. Templates for built-in workflows ship in the plugin's `templates/workflows/` directory.

### Autonomy Model

Each workflow has an `auto` flag:
- `auto: false` (default) — Present detected changes and ask before acting
- `auto: true` — Execute immediately without prompting

All built-in workflow templates default to `auto: false`.

## Alternatives Considered

### Option A: GitHub Webhooks
Requires a running server, external infrastructure, and network exposure. Incompatible with CLI plugin model.

### Option B: Polling Daemon
A background process could poll continuously. However, Claude Code plugins cannot spawn persistent processes, and this would consume API rate limits unnecessarily.

### Option C: Poll-Based via Hooks (CHOSEN)
Uses existing Claude Code hook infrastructure. Polling happens only at session start (bounded cost), with post-operation triggers providing real-time reactivity during sessions. No external infrastructure required.

## Consequences

### Positive

- **Zero infrastructure** — No servers, daemons, or external services
- **Bounded API cost** — Polling happens once per session start, not continuously
- **User control** — `auto` flag gives per-workflow autonomy control
- **Extensible** — New workflow templates can be added without code changes
- **Familiar patterns** — Uses existing plugin conventions (YAML config, pattern files, phase-based skills)

### Negative

- **Not real-time** — Changes are detected at session start, not immediately
- **Rate limit risk** — Many enabled session_poll workflows could consume rate limits on session start
- **Complexity** — Adds two new skills, two hooks, and a new config directory

### Mitigations

- Cooldown enforcement prevents excessive API calls
- Poll state diffing minimizes redundant work
- Heartbeat hook exits early when no workflows are enabled

## Implementation

**New Files:**
- `hooks/heartbeat.sh` — SessionStart hook
- `hooks/post-operation-check.sh` — PostToolUse hook
- `templates/workflow.yaml.template` — Workflow schema template
- `templates/poll-state.yaml.template` — Poll state template
- `templates/workflows/*.yaml` — Built-in workflow templates (5 files)
- `skills/hiivmind-pulse-gh-workflows/SKILL.md` — Workflow management skill
- `skills/hiivmind-pulse-gh-heartbeat/SKILL.md` — Heartbeat wake-up skill
- `lib/patterns/poll-state.md` — Poll state management pattern
- `lib/patterns/workflow-execution.md` — Workflow execution pattern
- `lib/references/workflow-triggers.md` — Trigger type reference

**Modified Files:**
- `hooks/hooks.json` — Add SessionStart and PostToolUse entries
- `commands/hiivmind-pulse-gh.md` — Add workflow/automation keywords to intent detection
- `commands/intent-mapping.yaml` — Add routing rules for new skills
