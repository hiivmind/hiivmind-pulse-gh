# V2 Workflow Execution Design

**Date:** 2026-04-01
**Status:** Draft
**Scope:** Update heartbeat skill, workflows skill, and workflow-execution pattern to interpret v2 `workflow:` pseudocode

## Problem

The v2 workflow format replaces `actions[]` with `state:`, `workflow:` (pseudocode FSM), and optionally `params:`. The runtime — heartbeat skill, workflows skill, and workflow-execution pattern — still expects `actions[]` and dispatches typed actions sequentially. These need updating to hand pseudocode to the LLM as executable instructions.

## Design

### Approach: Pseudocode handoff

The LLM reads the `workflow:` field and follows it as an instruction script. No parser. The pseudocode was designed to be LLM-interpreted — the conventions (phase labels, ASK, GOTO, INFER) guide the LLM but don't constrain it mechanically. This matches the fairgo-mcp proven pattern.

### Three files to update

| File | Change |
|------|--------|
| `lib/patterns/workflow-execution.md` | Replace action dispatch with pseudocode handoff |
| `skills/gh-heartbeat/SKILL.md` | Phases 4-6 use new execution pattern |
| `skills/gh-workflows/SKILL.md` | "Run" and "Status" operations use new pattern |

## Workflow Execution Pattern

### Current flow

```
1. LOAD workflow YAML
2. CHECK cooldown
3. CHECK approval context
4. EXECUTE actions[] sequentially
   ├── operation → invoke gh-operations with operation string
   └── skill_invoke → invoke named skill
5. UPDATE poll-state.yaml
6. REPORT summary
```

### New flow

```
1. LOAD workflow YAML
2. CHECK cooldown
3. CHECK approval context
4. RESOLVE params (if params: exists)
   ├── Extract from natural language request context
   ├── Apply defaults for missing params
   └── ASK user for remaining required params (default: null)
5. HAND pseudocode to LLM
   ├── Read workflow: field — this is the instruction script
   ├── Read state: field — these are the workflow's variables
   ├── Present to LLM: "Follow this pseudocode. Use gh-operations for
   │   data operations, AskUserQuestion for ASK statements, and track
   │   state variables through the FSM."
   └── LLM follows the pseudocode phases (GATHER → PRESENT → ACT → SUMMARIZE etc.)
6. UPDATE poll-state.yaml with result
7. REPORT summary (from pseudocode's SUMMARIZE phase output)
```

### Backward compatibility

If a workflow has `actions:` instead of `workflow:`, fall back to the old sequential dispatch. This means existing v1 workflows continue to work during transition.

Detection:

```
IF workflow YAML has 'workflow:' field → use pseudocode handoff (v2)
ELIF workflow YAML has 'actions:' field → use sequential dispatch (v1)
ELSE → error: workflow has neither actions nor workflow field
```

### Parameter resolution

For workflows with `params:`:

1. **Extract from context** — if the workflow was invoked via natural language (e.g., `/gh commit summary last 3 days on main`), extract matching parameter values from the request
2. **Apply defaults** — for params with `default:` set, use the default if not extracted
3. **ASK for required** — for params with `default: null`, prompt the user before starting the workflow

Parameters are resolved before the pseudocode starts executing. The pseudocode references them as `params.name` and can assume they're populated.

### Pseudocode interpretation guidelines

When handing pseudocode to the LLM, include these interpretation rules:

- **Phase labels** (e.g., `GATHER:`, `PRESENT:`) are sequential — execute top to bottom unless `GOTO` redirects
- **Natural language operations** (e.g., `failures = list recent failed workflow runs`) → invoke gh-operations skill or use `gh` CLI directly
- **`ASK` statements** → use AskUserQuestion to present choices to the user
- **`SHOW` statements** → display information to the user (tables, summaries, details)
- **`INFER` statements** → use LLM judgment to classify or categorize
- **`GOTO PHASE`** → jump back to the named phase (loop)
- **`STOP "reason"`** → halt workflow execution, report the reason
- **`INVOKE skill`** → invoke the named skill via the Skill tool
- **`state:` variables** → track in working memory throughout execution
- **`IF/ELIF/ELSE`** → branch based on gathered data or user responses
- **`FOR EACH`** → iterate over collected items
- **`STORE/REMOVE/SET/RECORD`** → manage state variables

### Pre-approved execution

Unchanged from current behavior. When a workflow is pre-approved (user selected it from heartbeat, or invoked it on-demand), the pseudocode runs without re-confirmation. The only user interaction points are `ASK` statements within the pseudocode itself — these are part of the workflow's designed flow, not permission checks.

## Heartbeat Skill Updates

### Phases 0-3: No change

Run hook, parse JSON, assess triggers, present summary — all unchanged.

### Phase 4: Execute Auto Workflows — updated

For each workflow in `auto_workflows`:

1. Load workflow YAML from `.hiivmind/github/workflows/`
2. **If `workflow:` field exists (v2):** follow pseudocode handoff pattern
3. **If `actions:` field exists (v1):** fall back to sequential dispatch
4. Update poll-state.yaml with result

### Phase 5: Present Non-Auto Workflows — no change

Still presents triggered workflows for user selection.

### Phase 6: Execute Selected Workflows — updated

Same change as Phase 4. After user selects workflows, load each and follow its pseudocode. Pre-approved context carries through.

### Phase 7: What's Next — minor update

Results summary reflects what the pseudocode's `SUMMARIZE:` phase produced. The suggestion patterns table remains the same — the heartbeat skill still maps workflow types to next-step suggestions.

## Workflows Skill Updates

### "Run Workflow" operation — updated

Currently says "execute actions sequentially." Updated to use the workflow-execution pattern (pseudocode handoff). On-demand runs skip cooldown (unchanged).

For parameterized workflows (e.g., `commit-summary`), resolve params before execution:
1. If the user's run request includes parameter values, extract them
2. Apply defaults
3. ASK for remaining required params

### "Status" operation — display update

Currently shows numbered actions list. Updated to show workflow phases and params:

```
## Workflow: ci-monitor

Description: Detect failed CI runs, classify failures, and offer targeted remediation
Enabled: yes
Auto: no
Trigger: session_poll (actions, new_failure)
Cooldown: 10 minutes
Params: none

### Phases

GATHER → PRESENT → INVESTIGATE → SUMMARIZE

### Execution History

Last run: 2026-04-01T10:30:00Z
Last result: success
Total runs: 5
```

For parameterized workflows:

```
Params: scope (default: "last 7 days"), user (required)
```

Phase names are extracted by scanning the `workflow:` field for lines matching `^  [A-Z]+(\(.*\))?:` pattern.

### "Create Workflow" operation — template list update

Template list now shows 13 templates (10 original + 3 activity workflows). No structural change to the create flow.

### "List Workflows" operation — no change

Already reads `name`, `enabled`, `auto`, `trigger` from YAML — these fields are unchanged in v2.

## Out of Scope

- Changes to `heartbeat.sh` (SessionStart hook) — it reads trigger/source/cooldown fields which are unchanged
- Changes to `post-operation-check.sh` — reads trigger type which is unchanged
- Changes to `validate-gh-operation.sh` — unrelated to workflow format
- Cross-workflow chaining mechanism
- Formal pseudocode parser or validator
