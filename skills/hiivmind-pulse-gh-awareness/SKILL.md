---
name: hiivmind-pulse-gh-awareness
description: >
  Configure CLAUDE.md with hiivmind-pulse-gh skill awareness using What/When/How structure. This skill
  should be used when: adding GitHub capabilities to CLAUDE.md, teaching Claude about this plugin,
  onboarding a new project, or explaining available GitHub skills. Trigger phrases: "add GitHub
  awareness", "configure Claude for GitHub", "what can pulse-gh do", "setup CLAUDE.md for GitHub",
  "enable GitHub skills", "plugin tour", "what GitHub operations are available", "teach Claude about
  GitHub", "add plugin to CLAUDE.md". Supports user-level (~/.claude/CLAUDE.md) and repo-level scope.
---

# Plugin Skill Awareness

Configure CLAUDE.md with hiivmind-pulse-gh skill awareness using a What/When/How structure.

## Scope

| Does | Does NOT |
|------|----------|
| Explain what skills this plugin provides | Detect GitHub features in project |
| Show when to use each skill | Execute GitHub operations |
| Describe how to invoke skills | Create GitHub resources |
| Edit CLAUDE.md with awareness section | Initialize workspace (use init skill) |

## Phase Overview

```
1. CONTEXT  -> 2. WHAT      -> 3. WHEN      -> 4. HOW       -> 5. INJECT
   (check)      (skills)       (triggers)     (invoke)       (edit)
      |            |              |              |              |
   Check for   Present 5     Show trigger   Explain        Preview +
   existing    skills        mapping        invocation     confirm edit
```

---

## Phase 1: CONTEXT - Determine Scope

**Goal:** Determine injection target and check for existing awareness section.

### Step 1: Determine Injection Target

Use AskUserQuestion to ask:

```
Where would you like to add GitHub plugin awareness?

1. **User-level** (~/.claude/CLAUDE.md)
   - Personal cross-project awareness
   - Claude suggests this plugin in ANY project you work on

2. **Repo-level** ({repo}/CLAUDE.md)
   - Team/project-specific awareness
   - Checked into version control for team use

3. Cancel
```

**Store selection** for use in Phase 5.

### Step 2: Check Target Existence

Based on selection:
- **User-level:** Check if `~/.claude/CLAUDE.md` exists
- **Repo-level:** Check if `CLAUDE.md` exists in project root

### STOP Point - No CLAUDE.md

```
No CLAUDE.md found at {target path}.

Would you like to:
  1. Create CLAUDE.md with plugin awareness section
  2. Cancel

[Select option]
```

### Step 3: Check for Existing Section

Search target file for "hiivmind-pulse-gh" or "GitHub Operations" section.

### STOP Point - Existing Awareness

If target CLAUDE.md already has awareness section:

```
{target path} already has hiivmind-pulse-gh awareness.

Would you like to:
  1. Update/replace existing section
  2. View current section
  3. Cancel

[Select option]
```

---

## Phase 2: WHAT - Plugin Skills

**Goal:** Present what skills this plugin provides.

**See:** `skills/hiivmind-pulse-gh-awareness/examples/capability-awareness.md` (WHAT section)

### Present Skills

```
=== What hiivmind-pulse-gh Provides ===

This plugin has 5 skills for GitHub automation:

1. **Init**
   Discover workspace, cache project/field IDs for fast operations.
   Run once per workspace.

2. **Operations**
   Execute GitHub operations: issues, PRs, milestones, labels,
   projects, branch protection, workflows, releases, and more.

3. **Corpus**
   Look up GitHub API syntax: 70k+ line GraphQL schema,
   REST endpoints, gh CLI commands.

4. **ADR**
   Create Architecture Decision Records as markdown files
   with linked GitHub issues and milestone assignment.

5. **Refresh**
   Sync config when stale or when "ID not found" errors occur.

Continue to see when to use each skill? [Yes / Skip to inject]
```

---

## Phase 3: WHEN - Trigger Mapping

**Goal:** Show when each skill should be used.

**See:** `skills/hiivmind-pulse-gh-awareness/examples/capability-awareness.md` (WHEN section)

### Present Trigger Table

```
=== When to Use Each Skill ===

| You Need To... | Use This Skill |
|----------------|----------------|
| Create, update, close issues or PRs | Operations |
| Set milestones, labels, project status | Operations |
| Protect branches, configure rulesets | Operations |
| Trigger workflows, manage secrets | Operations |
| Look up GraphQL mutation syntax | Corpus |
| Find REST endpoint paths | Corpus |
| Fix "ID not found" errors | Refresh |
| Sync stale config | Refresh |
| Document architecture decision | ADR |
| Plan major refactoring | ADR (proactive) |
| First-time workspace setup | Init |

### Proactive Suggestions

Claude should suggest this plugin when:
- User mentions GitHub operations (issues, PRs, milestones, projects)
- User asks about GitHub API syntax
- Major refactoring is planned (suggest ADR)
- Milestone has 5+ issues (suggest documenting decisions)

Continue to see how to invoke? [Yes / Skip to inject]
```

---

## Phase 4: HOW - Invocation Methods

**Goal:** Explain how to invoke the plugin.

**See:** `skills/hiivmind-pulse-gh-awareness/examples/capability-awareness.md` (HOW section)

### Present Invocation Options

```
=== How to Invoke ===

### Gateway Command (Recommended)

/hiivmind-pulse-gh [describe what you want]

The gateway auto-detects intent and routes to the appropriate skill.

Examples:
  /hiivmind-pulse-gh create issue for login bug
  /hiivmind-pulse-gh set milestone v2.0 on #42
  /hiivmind-pulse-gh document decision about using GraphQL

### Direct Skill Invocation

When you know exactly which skill:
  Skill: hiivmind-pulse-gh-operations
  Skill: hiivmind-corpus-github
  Skill: hiivmind-pulse-gh-adr

### Interactive Menu

/hiivmind-pulse-gh (no arguments) → shows numbered menu

Continue to inject into CLAUDE.md? [Yes / Cancel]
```

---

## Phase 5: INJECT

**Goal:** Generate awareness section and edit target CLAUDE.md.

**See:** `skills/hiivmind-pulse-gh-awareness/examples/capability-awareness.md` (Template section)

### Determine Target Path

Based on Phase 1 selection:
- **User-level:** `~/.claude/CLAUDE.md`
- **Repo-level:** `{repo}/CLAUDE.md`

### Generate Section

```markdown
## GitHub Operations (hiivmind-pulse-gh)

This project uses [hiivmind-pulse-gh](https://github.com/hiivmind/hiivmind-pulse-gh) for GitHub automation.

### What This Plugin Provides

| Skill | What It Does |
|-------|--------------|
| **Init** | Discover workspace, cache project/field IDs for fast operations |
| **Operations** | Execute GitHub operations (issues, PRs, milestones, projects, etc.) |
| **Corpus** | Look up GitHub API syntax (GraphQL schema, REST endpoints) |
| **ADR** | Create Architecture Decision Records linked to milestones/issues |
| **Refresh** | Sync config when stale or IDs not found |

### When to Use Each Skill

| You Need To... | Use This |
|----------------|----------|
| Create, update, close issues or PRs | `/hiivmind-pulse-gh [action]` |
| Set milestones, labels, project status | `/hiivmind-pulse-gh [action]` |
| Look up GraphQL/REST syntax | Corpus skill |
| Fix "ID not found" errors | Refresh skill |
| Document an architecture decision | ADR skill |
| First-time workspace setup | Init skill |

### Proactive Suggestions

Suggest using this plugin when:
- User mentions GitHub operations (issues, PRs, milestones, projects)
- User asks about GitHub API syntax or mutations
- Major refactoring is planned (suggest ADR)
- Milestone has 5+ issues (suggest documenting decisions)
- "ID not found" or stale config errors occur

### How to Invoke

**Gateway (recommended):**
```
/hiivmind-pulse-gh create issue for [description]
/hiivmind-pulse-gh document decision about [topic]
```

**Direct skill invocation** when you know which skill:
```
Skill: hiivmind-pulse-gh-operations
Skill: hiivmind-corpus-github
```
```

### STOP Point - Preview

```
=== CLAUDE.md Addition Preview ===

Target: {user-level: ~/.claude/CLAUDE.md | repo-level: {repo}/CLAUDE.md}

[Show generated section above]

Insert location: End of file / After [section name]

Options:
  1. Add to CLAUDE.md
  2. Choose different location
  3. Cancel

[Select option]
```

### Execute Edit

Use Edit tool to:
- Target the file selected in Phase 1
- Append to CLAUDE.md (if appending)
- Insert after specified section (if location chosen)

### STOP Point - Success

**If user-level:**
```
~/.claude/CLAUDE.md updated successfully!

Added hiivmind-pulse-gh skill awareness section.
This awareness works across ALL your projects.

Next steps:
  1. Initialize current workspace (/hiivmind-pulse-gh init) [if not initialized]
  2. Try a GitHub operation
  3. Done

[Select option]
```

**If repo-level:**
```
{repo}/CLAUDE.md updated successfully!

Added hiivmind-pulse-gh skill awareness section.
This is team-specific awareness for this repository.

Next steps:
  1. Initialize workspace (/hiivmind-pulse-gh init) [if not initialized]
  2. Commit CLAUDE.md changes for team use
  3. Try a GitHub operation
  4. Done

[Select option]
```

---

## Quick Reference

### Add Awareness

```
/hiivmind-pulse-gh add awareness
/hiivmind-pulse-gh configure Claude for GitHub
/hiivmind-pulse-gh what can you do
```

---

## Related Skills

- **hiivmind-pulse-gh-init** - Initialize workspace after adding awareness
- **hiivmind-pulse-gh-operations** - Execute GitHub operations
- **hiivmind-corpus-github** - API documentation lookup
- **hiivmind-pulse-gh-adr** - Architecture Decision Records

## Pattern Library

| Pattern | Purpose |
|---------|---------|
| `skills/hiivmind-pulse-gh-awareness/examples/capability-awareness.md` | Skill registry, trigger mapping, CLAUDE.md template |
