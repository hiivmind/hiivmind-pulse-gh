# Architecture Redesign: Pattern-Based Skill System

**Status:** In Progress
**Created:** 2025-12-16
**Milestone:** v5.0.0

## Summary

Transform hiivmind-pulse-gh to use a pattern-based architecture following hiivmind-corpus's proven model. This addresses reliability issues discovered during init workflow testing.

## Problem Statement

The current skill system has several issues:

1. **Untested inline examples** - GraphQL queries embedded in SKILL.md files fail with syntax errors in Claude Code's Bash tool
2. **No pattern library** - Examples are embedded inline, not reusable or testable
3. **Context assumptions** - Init assumes git repository context, fails when run from multi-repo parent directories
4. **Vague corpus instructions** - Says "search corpus" without explaining how
5. **No STOP points** - Phases blend together without explicit boundaries
6. **No user collaboration** - Auto-decides on targets instead of asking

## Reference Architecture

We're adopting the pattern-based architecture from [hiivmind-corpus](https://github.com/hiivmind/hiivmind-corpus), which demonstrates:

- **Pattern library** at `lib/corpus/patterns/` with 7 tool-agnostic algorithm documents
- **Multiple implementations** per pattern (yq preferred → Python → grep fallback)
- **Cross-platform** examples (Bash and PowerShell)
- **Skills reference patterns** via "**See:** `lib/corpus/patterns/X.md`"
- **Explicit STOP points** between phases
- **User collaboration points** - never auto-decide on destinations, targets, mutations

## New Architecture

### Pattern Library: `lib/github/patterns/`

| Pattern | Purpose |
|---------|---------|
| `tool-detection.md` | Verify gh, jq, yq availability |
| `authentication.md` | Auth verification, scope checking |
| `workspace-detection.md` | Git remote parsing, org vs user detection |
| `config-parsing.md` | Read/write config.yaml |
| `id-resolution.md` | Resolve project/field/option IDs from config |
| `api-selection.md` | GraphQL vs REST decision logic |
| `graphql-queries.md` | Tested query patterns |
| `rest-operations.md` | REST endpoint patterns |
| `project-operations.md` | Project v2 field updates, item management |
| `issue-pr-operations.md` | Issue/PR CRUD operations |
| `protection-operations.md` | Branch protection, rulesets |
| `error-handling.md` | Common errors and recovery |
| `corpus-lookup.md` | How to find syntax in embedded corpus |

### Pattern Document Structure

Each pattern follows a consistent format:

```markdown
# Pattern: [Name]

## Purpose
[One-line description]

## When to Use
- [Use case 1]
- [Use case 2]

## Prerequisites
- [Tool detection reference if needed]
- [Config requirements]

## Algorithm

### Step 1: [Name]
[Description]

**Using Claude tools (preferred):**
- [Approach]

**Using bash with gh/jq/yq:**
```bash
# Tested command
```

**Using bash without yq (fallback):**
```bash
# Grep-based fallback
```

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|

## Examples

### Example 1: [Scenario]
[Input, process, output]

## Related Patterns
- `pattern-name.md` - [relationship]
```

### Skill Redesigns

#### Init Skill

**Scope Boundary:**

| Does | Does NOT |
|------|----------|
| Verify CLI tools and auth | Execute GitHub operations |
| Detect workspace type | Refresh stale configs |
| Discover and cache project IDs | Fetch views/automations/teams |
| Create config.yaml + user.yaml | Build extended configs |

**Phase Structure:**

```
1. CONTEXT    → 2. PREREQS   → 3. INPUT    → 4. DISCOVER → 5. CACHE    → 6. VERIFY
   (detect)       (tools)        (confirm)     (projects)    (write)       (done)
      │              │               │              │            │            │
   STOP if       STOP if         STOP for       STOP for       -         STOP: offer
   ambiguous     missing         user OK        selection              refresh/ops
```

**User Collaboration Points:**
1. Context detected: "Found workspace `X` (organization/user). Correct?"
2. After discovery: "Found N projects. Which to cache?"
3. After discovery: "Set default project to?"
4. After verify: "Init complete. Run operations or fetch extended config?"

#### Refresh Skill

**Scope Boundary:**

| Does | Does NOT |
|------|----------|
| Check staleness per section | Execute GitHub operations |
| Refresh selected sections | Initialize new workspaces |
| Update freshness timestamps | Modify GitHub resources |

**Section-Based Architecture:**

| Section | Pattern Reference | Freshness Key |
|---------|-------------------|---------------|
| workspace | `workspace-detection.md` | `.sections.workspace` |
| projects | `project-operations.md` | `.sections.projects` |
| views | `project-operations.md` | `.sections.views` |
| repo_settings | `protection-operations.md` | `.sections.repo_settings` |
| automations | `project-operations.md` | `.sections.automations` |
| relationships | `graphql-queries.md` | `.sections.relationships` |
| teams | `graphql-queries.md` | `.sections.teams` |

#### Operations Skill

**Scope Boundary:**

| Does | Does NOT |
|------|----------|
| Execute single GitHub operations | Multi-step workflows |
| Load IDs from config | Initialize or refresh config |
| Consult corpus for syntax | Cache results |

**Phase Structure:**

```
1. CONTEXT → 2. RESOLVE → 3. ROUTE → 4. LOOKUP → 5. EXECUTE → 6. REPORT
   (load)      (IDs)       (API)     (corpus)     (gh)        (result)
```

### Gateway Command Updates

**New Flow:**

```
1. ARGUMENTS → 2. CONTEXT → 3. FRESHNESS → 4. INTENT → 5. CONFIRM → 6. ROUTE
   (check)       (init?)      (stale?)       (parse)     (if mut)     (skill)
```

**Key Changes:**
- Context detection BEFORE intent detection
- Check initialization first
- Check freshness for required sections
- Block mutations if config is hard stale

## Implementation Plan

### Iteration 1: Foundation + Init

**Goal:** Get init working reliably from multi-repo parent directory

1. Create `lib/github/patterns/` directory
2. Create foundation patterns:
   - `tool-detection.md`
   - `authentication.md`
   - `config-parsing.md`
   - `workspace-detection.md`
   - `graphql-queries.md` (project discovery only)
3. Archive current init skill to `_archived/skills-v3/`
4. Create new init skill with pattern references
5. Test from `/home/nathanielramm/git/hiivmind/`

### Iteration 2: Operations Patterns

After init is proven working:
- `rest-operations.md`
- `project-operations.md`
- `issue-pr-operations.md`
- `protection-operations.md`
- `error-handling.md`

### Iteration 3: Refresh & Operations Skills

After patterns are complete:
- Archive and replace refresh skill
- Archive and replace operations skill

### Iteration 4: Gateway & Polish

Final integration:
- `api-selection.md`
- `corpus-lookup.md`
- Update gateway command
- Update CLAUDE.md
- Update tests

## Success Criteria

1. **Init works from multi-repo parent** - Detects context, asks to confirm workspace
2. **GraphQL queries work** - All patterns contain tested, working commands
3. **Clear STOP points** - Each phase has explicit completion criteria
4. **User collaboration** - Never auto-decides on targets, destinations, mutations
5. **Pattern references** - Skills contain "See: lib/github/patterns/X.md" at each step
6. **Corpus lookup documented** - Explicit instructions for finding syntax
7. **Error recovery** - Each pattern includes error handling section

## Migration Strategy

1. Archive current skills to `_archived/skills-v3/` (not delete)
2. Create new pattern library from scratch
3. Create new skills referencing patterns
4. Test each iteration before proceeding
5. Update CLAUDE.md after all skills are redesigned

## Related Documents

- Reference architecture: [hiivmind-corpus patterns](https://github.com/hiivmind/hiivmind-corpus/tree/main/lib/corpus/patterns)
- Current routing guide: `reference/api-routing.md`
- Current skills: `skills/hiivmind-pulse-gh-*/SKILL.md`
- Deprecated functions: `_deprecated/github/` (source for pattern extraction)
