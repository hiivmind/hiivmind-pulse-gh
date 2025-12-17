---
name: hiivmind-pulse-gh-adr
description: >
  Create and manage Architecture Decision Records (ADRs) as markdown files with linked GitHub issues.
  This skill should be used when: documenting architecture decisions, creating ADRs, recording technical
  choices, explaining design rationale, capturing "why we chose X over Y". Trigger phrases: "create an
  ADR", "document this decision", "record why we", "architecture decision record", "design decision",
  "technical decision", "why did we choose", "decision log", "document the rationale". Proactively
  suggest when: milestone has 5+ issues, major refactoring planned, breaking API changes, new patterns
  introduced, technology migrations, or user asks "should we document this".
---

# Architecture Decision Records

Create, manage, and link ADRs across local files and GitHub issues.

## Scope

| Does | Does NOT |
|------|----------|
| Create ADR markdown files (`doc/adr/`) | Make decisions automatically |
| Create linked GitHub issues with `adr` label | Implement the decisions |
| Assign ADRs to milestones | Modify code files |
| Sync ADR status between file and issue | Create milestones (use operations) |
| Suggest ADRs for large milestones | Bypass user confirmation |

## Proactive Triggering

### When to Suggest ADRs

This skill may be **proactively suggested** when:

1. **Milestone Analysis** - A milestone has 5+ issues
2. **Major Refactoring** - User describes refactoring involving 3+ files
3. **Architecture Change** - Keywords: "restructure", "migrate", "redesign", "new pattern"
4. **Breaking Change** - Modifying public APIs or interfaces

**See:** `lib/github/patterns/adr-awareness.md`

### Suggestion Format

```
I noticed [trigger condition].

Would you like to create an Architecture Decision Record (ADR) to document:
- The context and problem being solved
- The decision and rationale
- Consequences and trade-offs

This helps future developers understand why this approach was chosen.

Create ADR? [Yes / No / Later]
```

## Phase Overview

```
1. CONTEXT    -> 2. GATHER      -> 3. GENERATE -> 4. GITHUB   -> 5. LINK     -> 6. CONFIRM
   (detect)       (collaborate)     (write)       (issue)       (milestone)    (done)
      |               |                |             |             |             |
   STOP if        STOP for         Write file    Create issue   Assign to    STOP: show
   not init       user input       (preview)     with label     milestone    summary
```

---

## Phase 1: CONTEXT

**Goal:** Load configuration and determine ADR numbering.

**See:** `lib/github/patterns/config-parsing.md`
**See:** `lib/github/patterns/adr-management.md`

### What to Do

1. Check if we're in a git repository
2. Check for `.hiivmind/github/config.yaml` (optional for local-only ADRs)
3. Check for `doc/adr/` directory (create if needed)
4. Determine next ADR number from existing files

### ADR Numbering

```bash
# Get next ADR number (from adr-management.md)
LAST_NUM=$(ls doc/adr/*.md 2>/dev/null | grep -oP '\d{4}' | sort -n | tail -1)
NEXT_NUM=$((10#${LAST_NUM:-0} + 1))
printf "%04d" "$NEXT_NUM"
```

### STOP Point

**If not in a git repository:**

```
This doesn't appear to be a git repository.

ADRs are typically stored in version-controlled repositories.
Would you like to:
  1. Continue anyway (create ADR in current directory)
  2. Navigate to a repository first
```

**If workspace not initialized but GitHub features requested:**

```
Workspace not initialized for GitHub integration.

ADRs can be created locally, but milestone/issue linking requires init.

Options:
  1. Create ADR locally only
  2. Initialize workspace first (/hiivmind-pulse-gh init)
```

---

## Phase 2: GATHER

**Goal:** Collect ADR information through structured conversation.

### STOP Point - Title

```
Let's document this architecture decision.

**Title:** (brief, descriptive - e.g., "Use GraphQL for GitHub API")
```

### STOP Point - Context

After title:

```
**Context:** What is the issue or situation motivating this decision?
(Describe the problem, constraints, and forces at play)
```

### STOP Point - Decision

After context:

```
**Decision:** What is the change or approach you're taking?
(Be specific about what will be done)
```

### STOP Point - Consequences

After decision:

```
**Consequences:** What are the results of this decision?

Please describe:
- Positive outcomes
- Negative impacts or trade-offs
- Neutral changes
```

### STOP Point - Optional Fields

After core fields:

```
**Additional fields (all optional):**

1. Alternatives considered?
2. Related/superseded ADRs?
3. Target milestone?
4. Decision participants?

[Enter numbers to provide, or press Enter to skip]
```

---

## Phase 3: GENERATE

**Goal:** Generate ADR markdown file.

**See:** `reference/adr-template.md`

### What to Do

1. Format ADR using Nygard template
2. Generate filename slug from title
3. Include frontmatter with placeholders for GitHub links
4. Preview to user before writing

### STOP Point - Preview

```
=== ADR Preview ===

File: doc/adr/0005-use-graphql-for-github-api.md

---
adr: 5
title: "Use GraphQL for GitHub API"
status: Proposed
date: 2025-12-17
milestone: (to be linked)
issue: (to be created)
---

# 5. Use GraphQL for GitHub API

## Status

Proposed

## Context

[Context text from Phase 2...]

## Decision

[Decision text from Phase 2...]

## Consequences

[Consequences text from Phase 2...]

===================

Write this file? [Yes / Edit / Cancel]
```

---

## Phase 4: GITHUB

**Goal:** Create GitHub issue linked to ADR.

**See:** `lib/github/patterns/adr-management.md`

### Prerequisites

- Workspace must be initialized (`.hiivmind/github/config.yaml` exists)
- User confirmed GitHub integration in Phase 1

### What to Do

1. Ensure `adr` label exists (create if not)
2. Create issue with title "ADR-NNNN: [Title]"
3. Include ADR content in issue body
4. Link to file location in repo

### STOP Point - Issue Creation

```
Create GitHub issue for this ADR?

  Title: ADR-0005: Use GraphQL for GitHub API
  Labels: adr
  Body: [ADR content with link to file]

This enables discussion, milestone tracking, and project board visibility.

[Yes / No - keep local file only]
```

### Issue Body Template

```markdown
## Architecture Decision Record

**ADR Number:** {number}
**File:** `doc/adr/{filename}`
**Status:** Proposed

---

{adr_content}

---

_This issue tracks the ADR. Update the markdown file for authoritative content._
```

---

## Phase 5: LINK

**Goal:** Link ADR issue to milestone and optionally project.

**See:** `lib/github/patterns/id-resolution.md`

### What to Do

1. List available milestones from config
2. Ask user to select milestone (if not specified earlier)
3. Assign issue to milestone
4. Optionally add to project board

### STOP Point - Milestone Selection

```
Assign ADR to a milestone?

Available milestones:
  1. v5.1.0 - ADR Integration (1 issue)
  2. v5.0.0 - Pattern Architecture (0 issues)
  3. Backlog (12 issues)

[Enter number, or 'none' to skip]
```

### Milestone Assignment

```bash
# Using gh CLI (simplest)
gh issue edit "$ISSUE_NUM" --milestone "$MILESTONE_TITLE"
```

### STOP Point - Project Board (Optional)

```
Add ADR to a project board?

  Default project: {project_name} (#{project_number})

[Yes / No / Different project]
```

---

## Phase 6: CONFIRM

**Goal:** Summarize what was created and update ADR frontmatter.

### What to Do

1. Update ADR file frontmatter with issue number and milestone
2. Display summary of created artifacts
3. Offer next steps

### Update ADR Frontmatter

**See:** `lib/github/patterns/adr-management.md`

```bash
# Update frontmatter with yq
yq -i --front-matter=process ".issue = $ISSUE_NUM | .milestone = \"$MILESTONE\"" "$ADR_FILE"
```

### STOP Point - Summary

```
ADR Created Successfully!

**Local File:**
  doc/adr/0005-use-graphql-for-github-api.md

**GitHub Issue:**
  #142 - ADR-0005: Use GraphQL for GitHub API
  https://github.com/owner/repo/issues/142

**Milestone:**
  v5.1.0 - ADR Integration

**Next Steps:**
  1. Share with team for review
  2. Update status when decision is accepted/rejected
  3. Run '/hiivmind-pulse-gh adr sync 5' to sync changes

What would you like to do?
  1. Create another ADR
  2. List all ADRs
  3. Done
```

---

## Quick Reference Commands

### Create ADR

```
/hiivmind-pulse-gh create ADR for [topic]
/hiivmind-pulse-gh document decision about [topic]
```

### List ADRs

```
/hiivmind-pulse-gh list ADRs
```

### Update ADR Status

```
/hiivmind-pulse-gh adr update [number] status [Accepted|Deprecated|Superseded]
```

### Sync ADR

```
/hiivmind-pulse-gh adr sync [number]
```

Syncs content between markdown file and GitHub issue (file is authoritative).

---

## Related Skills

- **hiivmind-pulse-gh-init** - Workspace setup (required for GitHub features)
- **hiivmind-pulse-gh-operations** - General GitHub operations (milestone creation)
- **hiivmind-pulse-gh-refresh** - Update cached milestone/project data

## Pattern Library

| Pattern | Purpose |
|---------|---------|
| `lib/github/patterns/adr-management.md` | ADR numbering, file creation, GitHub sync |
| `lib/github/patterns/adr-awareness.md` | Proactive triggers, CLAUDE.md integration |
| `lib/github/patterns/config-parsing.md` | Read workspace config |
| `lib/github/patterns/id-resolution.md` | Resolve milestone/issue IDs |
| `lib/github/patterns/graphql-execution.md` | Execute mutations |

## References

| Reference | Purpose |
|-----------|---------|
| `reference/adr-template.md` | ADR markdown template and schema |
| `reference/api-routing.md` | Routing for issue/milestone operations |
