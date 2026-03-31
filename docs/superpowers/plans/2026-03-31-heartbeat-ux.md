# Heartbeat UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate redundant approval steps in heartbeat execution and add contextual handoff with actionable next steps.

**Architecture:** Four targeted edits to skill markdown files and one JSON config change. No shell scripts or workflow YAML files change. The changes are: (1) rewrite the GraphQL execution pattern to use Write tool + separate Bash, (2) add pre-approved execution guidance to workflow execution pattern, (3) add pre-approved context and Phase 7 handoff to heartbeat skill, (4) add Edit allowlist rule for `.hiivmind/` files.

**Tech Stack:** Markdown (skill/pattern documents), JSON (settings)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `lib/patterns/graphql-execution.md` | Modify | Change Method 1 from compound Bash to Write tool + separate Bash |
| `lib/patterns/workflow-execution.md` | Modify | Add pre-approved caller context that skips auto-check |
| `skills/gh-heartbeat/SKILL.md` | Modify | Add pre-approved execution guidance to Phases 4-5; add Phase 7 handoff |
| `.claude/settings.local.json` | Modify | Add `Edit(.hiivmind/**)` allowlist rule |

---

### Task 1: Update GraphQL Execution Pattern

**Files:**
- Modify: `lib/patterns/graphql-execution.md:36-88` (Method 1: Temp File section)

This task changes the recommended GraphQL execution method from a compound Bash command (cat heredoc + gh api in one call) to two separate tool calls (Write tool + Bash). This ensures `gh api` calls match the existing `Bash(gh:*)` allowlist rule.

- [ ] **Step 1: Replace Method 1 steps in graphql-execution.md**

In `lib/patterns/graphql-execution.md`, replace the "Method 1: Temp File (Queries with Variables)" section (lines 36-88). The old content uses `cat > /tmp/query.graphql << 'QUERY'` as a Bash command. Replace with guidance to use the Write tool for the query file and a separate Bash call for execution.

Replace the existing Step 1 and Step 2 content (lines 38-79) with:

```markdown
## Method 1: Temp File (Queries with Variables)

The most reliable method for queries with `$variable` parameters.

### Step 1: Write Query to Temp File

Use the **Write tool** to create the query file. This avoids shell expansion issues entirely
and does not require explicit permission from the user.

**Write tool** → `/tmp/query.graphql`:

```graphql
query($login: String!) {
  organization(login: $login) {
    id
    projectsV2(first: 20) {
      nodes {
        number
        title
        closed
        id
        url
      }
    }
  }
}
```

**Key:** Using the Write tool instead of a Bash heredoc means:
- No shell expansion issues (`$variable` stays literal)
- No user approval needed (Write tool is implicitly allowed)
- The query file is ready for the next step

### Step 2: Execute with File Read

Use a **separate Bash call** to execute the query:

```bash
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f login="hiivmind"
```

**Why two separate tool calls:**
1. Write tool creates the file (no approval needed)
2. `gh api` call matches `Bash(gh:*)` allowlist (pre-approved)
3. A compound `cat > file && gh api` command matches neither rule

### Step 3: Cleanup (Optional)

```bash
rm -f /tmp/query.graphql
```
```

- [ ] **Step 2: Update Examples section to match new pattern**

In the same file, update Example 1 (lines 169-199) and Example 2 (lines 210-249) to use the Write tool + separate Bash pattern instead of `cat > /tmp/query.graphql << 'QUERY'`.

For Example 1, replace the "Query file:" bash block with:

```markdown
**Write tool** → `/tmp/query.graphql`:
```graphql
query($login: String!) {
  organization(login: $login) {
    id
    projectsV2(first: 20) {
      nodes {
        number
        title
        closed
        id
      }
    }
  }
}
```

**Execute:**
```bash
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f login="hiivmind" \
  | jq '.data.organization.projectsV2.nodes'
```
```

For Example 2, replace the "Query file:" bash block with:

```markdown
**Write tool** → `/tmp/query.graphql`:
```graphql
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {
    projectId: $projectId
    contentId: $contentId
  }) {
    item {
      id
    }
  }
}
```

**Execute:**
```bash
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f projectId="PVT_kwDODUFJxM4A..." \
  -f contentId="I_kwDODUFJxM6..."
```
```

- [ ] **Step 3: Update Cross-Platform Notes**

Replace the cross-platform table (lines 287-292) to reflect that the Write tool is platform-agnostic:

```markdown
## Cross-Platform Notes

The Write tool is platform-agnostic — it works identically on Unix, Windows, and containerized environments. Only the Bash execution step varies:

| Aspect | Unix | Windows (PowerShell) |
|--------|------|---------------------|
| Write query | Write tool (same) | Write tool (same) |
| Execute | `gh api graphql -f query="$(cat /tmp/query.graphql)"` | `gh api graphql -f query="$(Get-Content $env:TEMP\query.graphql -Raw)"` |
```

- [ ] **Step 4: Verify the document reads correctly**

Read the full file to confirm no broken markdown, no orphaned references to the old heredoc pattern, and all code blocks are properly fenced.

- [ ] **Step 5: Commit**

```bash
git add lib/patterns/graphql-execution.md
git commit -m "refactor: graphql execution pattern uses Write tool + separate Bash

Compound cat-heredoc + gh api commands don't match Bash(gh:*) allowlist.
Split into Write tool (no approval needed) + separate gh api call (pre-approved)."
```

---

### Task 2: Add Pre-Approved Context to Workflow Execution Pattern

**Files:**
- Modify: `lib/patterns/workflow-execution.md:50-66` (Execution Flow section)

This task adds guidance to the workflow execution pattern so that when a caller (like heartbeat) has already obtained user approval, the pattern skips its own auto-check and confirmation steps.

- [ ] **Step 1: Add Pre-Approved Caller Context section**

In `lib/patterns/workflow-execution.md`, add a new section after the Execution Flow (after line 66), before the Cooldown Check section. Insert:

```markdown
---

## Pre-Approved Execution

When a caller has already obtained user approval to run a workflow (e.g., the heartbeat skill
presented workflows and the user selected which to run), downstream execution MUST NOT re-confirm.

**How to recognize pre-approved context:**
- The heartbeat skill explicitly states workflows are pre-approved after user selection
- On-demand workflow runs (via workflows skill "run" command) are pre-approved by the user's request

**When pre-approved:**
1. Skip the `auto: false` permission check in step 3 of the execution flow — the user already approved
2. Execute actions directly without confirmation prompts
3. If stale config is detected during execution, auto-refresh and continue — do not stop to ask
4. Read-only operations (list, show, summarize, get) never need confirmation regardless of context

**The `auto` flag meaning is unchanged:**
- `auto: true` — Heartbeat runs this workflow without presenting it for selection (Phase 4)
- `auto: false` — Heartbeat presents this workflow for user selection (Phase 5)
- After selection, both are pre-approved for execution
```

- [ ] **Step 2: Update the Execution Flow step 3 to reference pre-approved context**

In the Execution Flow section (line 55-56), update step 3 to reference the new section. Replace:

```markdown
3. CHECK auto flag
   ├── auto: true  → execute immediately
   └── auto: false → present to user, ask permission
```

With:

```markdown
3. CHECK approval context
   ├── pre-approved (heartbeat selection, on-demand run) → execute immediately
   ├── auto: true  → execute immediately
   └── auto: false → present to user, ask permission
```

- [ ] **Step 3: Verify the document reads correctly**

Read the full file to confirm the new section integrates cleanly and doesn't contradict existing content.

- [ ] **Step 4: Commit**

```bash
git add lib/patterns/workflow-execution.md
git commit -m "feat: add pre-approved execution context to workflow execution pattern

When heartbeat or on-demand run has already obtained user approval,
downstream execution skips auto-check and confirmation gates."
```

---

### Task 3: Update Heartbeat Skill — Pre-Approved Execution and Phase 7 Handoff

**Files:**
- Modify: `skills/gh-heartbeat/SKILL.md:153-205` (Phases 4-6, add Phase 7)

This is the largest task. It modifies the heartbeat skill to: (a) add pre-approved execution guidance to Phases 4 and 5, (b) add auto-refresh behavior when stale config is detected, and (c) add a new Phase 7 with contextual handoff.

- [ ] **Step 1: Add pre-approved execution note to Phase 4**

In `skills/gh-heartbeat/SKILL.md`, after the Phase 4 heading "Execute Auto Workflows" (line 155), add a note before the existing content:

```markdown
### 4. Execute Auto Workflows

**Execution context:** Auto workflows are pre-approved by definition. Execute without confirmation.
When invoking downstream skills (operations, refresh), all execution is pre-approved — do NOT
re-confirm with the user.

**See:** `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` (Pre-Approved Execution section)
```

Keep the existing Phase 4 content (load workflow, execute actions, update poll-state) after this note.

- [ ] **Step 2: Rewrite Phase 5 with pre-approved execution context**

Replace the existing Phase 5 content (lines 170-183) with:

```markdown
### 5. Execute Non-Auto Workflows

For workflows in `triggered_workflows` but NOT in `auto_workflows`:

Present a single selection prompt:

```
Which workflows would you like to run?

  1. pr-lifecycle — Summarize PR diffs, suggest reviewers (PR state changed)
  2. project-sync — Detect project board changes (board updated)
  3. All — Run all triggered workflows
  4. Skip — Don't run any workflows

Select one or more (e.g., "1, 2" or "all"):
```

**After user selects:** All selected workflows are **pre-approved**. Execute them immediately
without any further confirmation. This means:

- Do NOT re-confirm individual workflow execution
- Do NOT re-confirm operations invoked by workflow actions
- If stale config is detected during execution, auto-refresh and continue
- Read-only operations never need mutation confirmation

**See:** `{PLUGIN_ROOT}/lib/patterns/workflow-execution.md` (Pre-Approved Execution section)

For each selected workflow, execute using the workflow execution pattern with pre-approved context.
```

- [ ] **Step 3: Update Phase 6 to collect results for handoff**

Replace the existing Phase 6 content (lines 187-205) with:

```markdown
### 6. Collect Results

After all executions, update poll-state.yaml with results for each executed workflow.

Build a results summary for Phase 7:

```
EXECUTED_RESULTS = {
  workflow_name: {
    result: "success" | "failure" | "skipped",
    findings: <output from workflow actions>
  }
}

SKIPPED_WORKFLOWS = workflows in triggered but not selected by user
```

Display execution summary:

```
## Heartbeat Results

| Workflow | Result |
|----------|--------|
| auto-refresh | success |
| project-sync | success |
```
```

- [ ] **Step 4: Add Phase 7 — Contextual Handoff**

After Phase 6, add the new Phase 7:

```markdown
### 7. What's Next

Present actionable next steps derived from workflow results. This phase ensures the heartbeat
never ends at a dead end.

**Structure (always in this order):**

**7a. Actions from findings**

Analyze the output of each executed workflow and suggest concrete next actions.
Map workflow types to suggestion patterns:

| Workflow | What to Look For | Suggestion |
|----------|-----------------|------------|
| project-sync | Items in actionable states (Approved, In Review) | "Issue #N is [Status] — [action]?" |
| project-sync | Items assigned to user | "You have N items assigned across projects" |
| pr-lifecycle | PRs needing review | "PR #N needs your review" |
| pr-lifecycle | PRs with requested changes | "PR #N has requested changes to address" |
| ci-monitor | Failed CI runs | "CI run failed on [branch] — investigate?" |
| ci-monitor | Successful runs | "[branch] CI is green" (informational) |
| issue-triage | Untriaged issues | "N new issues need labels" |
| stale-check | Stale PRs/issues | "PR #N has had no activity for N days" |
| auto-refresh | Sections refreshed | "Refreshed: [sections]" (informational) |

**Example:**
```
## What's Next

Based on what we found:
  - #9 Plan: Dev Ops Clarity is Approved — start implementing?
  - Board has 4 items in Implementing
  - PR #15 needs your review
```

**7b. Remaining workflows** (only if some triggered workflows were not selected)

```
Workflows not run this session:
  - pr-lifecycle, ci-monitor

Run remaining?
```

**7c. Fallback**

Always end with an escape to broader options:

```
Pick an action, or /gh for more options.
```

**If no workflows produced actionable findings** (e.g., only auto-refresh ran):

```
## What's Next

All clear — no items need attention right now.

/gh for GitHub operations.
```
```

- [ ] **Step 5: Verify the full skill reads correctly**

Read the entire `skills/gh-heartbeat/SKILL.md` to confirm:
- Phases flow logically 1 → 2 → 3 → 4 → 5 → 6 → 7
- No orphaned references to old Phase 5/6 content
- Pre-approved execution is clearly stated in both Phase 4 and Phase 5
- Phase 7 examples are consistent with the workflow types defined in `.hiivmind/github/workflows/`

- [ ] **Step 6: Commit**

```bash
git add skills/gh-heartbeat/SKILL.md
git commit -m "feat: frictionless heartbeat execution with contextual handoff

- Phases 4-5: pre-approved downstream execution after user selection
- Phase 6: collect results for handoff
- Phase 7: contextual next actions from findings + remaining workflows"
```

---

### Task 4: Add Edit Allowlist Rule

**Files:**
- Modify: `.claude/settings.local.json`

- [ ] **Step 1: Add Edit(.hiivmind/**) to the allowlist**

In `.claude/settings.local.json`, add `"Edit(.hiivmind/**)"` to the `permissions.allow` array. Insert it after the existing `Bash(bash -n:*)` entry (line 33):

```json
"Bash(bash -n:*)",
"Edit(.hiivmind/**)",
```

- [ ] **Step 2: Verify the JSON is valid**

Read the file and confirm valid JSON with no trailing commas or syntax errors.

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.local.json
git commit -m "config: allow Edit for .hiivmind/ files without approval

Covers config.yaml, freshness.yaml, poll-state.yaml, and workflow edits
that previously required manual approval during heartbeat execution."
```
