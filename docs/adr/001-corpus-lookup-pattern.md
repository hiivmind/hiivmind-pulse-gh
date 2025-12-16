# ADR 001: Rename "v3 Flow" to "Corpus Lookup Pattern"

**Status:** Accepted
**Date:** 2025-12-17

## Context

The hiivmind-pulse-gh plugin uses a three-step process for executing GitHub API operations:

1. **ROUTE** - Determine which API to use (GraphQL vs REST)
2. **CORPUS** - Look up exact syntax from bundled documentation
3. **EXECUTE** - Run the operation

This process is currently called "v3 flow" throughout the codebase. This name is problematic:

1. **Opaque naming** - "v3 flow" says nothing about what it does; it's a version number, not a description
2. **Implied mandate** - Documentation states "all operations use the v3 flow", implying it's required every time
3. **Coupled concerns** - API routing decisions (which are useful standalone) are bundled with corpus lookup (which is only needed when uncertain)
4. **Confusing warnings** - Skills contain "DO NOT use global corpus" warnings that draw attention to something users should ignore

## Decision

### 1. Rename "v3 flow" to "Corpus Lookup Pattern"

The new name clearly conveys:
- **What it is:** A lookup mechanism using the documentation corpus
- **What it does:** Provides exact API syntax when needed
- **It's optional:** "Pattern" implies a tool to use when applicable, not a mandatory flow

### 2. Frame corpus lookup as optional

Change the framing from:
> "All operations use the v3 flow"

To:
> "Use corpus lookup when uncertain about syntax"

Skills should present a decision tree:
1. Check routing guide for API choice
2. If syntax is clear → Execute directly
3. If uncertain → Use corpus lookup pattern

### 3. Separate API routing as standalone reference

The `reference/api-routing.md` guide is useful on its own - it tells you which API (GraphQL vs REST) to use for each domain. This is valuable even when you don't need to look up exact syntax.

Add a header clarifying:
> **Standalone:** This guide is useful on its own - you do not need corpus lookup for every operation.

### 4. Remove global navigation warnings

Instead of:
> **DO NOT** use the global `hiivmind-corpus:hiivmind-corpus-navigate` skill

Simply state what to use:
> **Invoke:** `hiivmind-pulse-gh:hiivmind-corpus-github`

### 5. Keep corpus navigation as a Skill (not Agent)

The corpus lookup should remain a deliberately-invoked Skill rather than an auto-triggering Agent because:
- Corpus lookup should be intentional, not automatic
- An agent might over-fire on any GitHub-related question
- Skill invocation is explicit and predictable

## Consequences

### Files Affected

| File | Changes |
|------|---------|
| `lib/github/patterns/v3-flow.md` | Rename to `corpus-lookup.md`, rewrite framing |
| `reference/api-routing.md` | Add standalone usage note |
| `CLAUDE.md` | Update architecture section |
| `skills/hiivmind-pulse-gh-operations/SKILL.md` | Rewrite Phase 4, remove warnings |
| `skills/hiivmind-pulse-gh-refresh/SKILL.md` | Rewrite Phase 4, remove warnings |
| `skills/hiivmind-pulse-gh-init/SKILL.md` | Update Phase 4 terminology |
| `lib/github/patterns/README.md` | Update pattern index |
| `lib/github/patterns/id-resolution.md` | Update 7 references |
| `lib/github/patterns/error-handling.md` | Update related patterns |

### Benefits

- **Clearer naming** - "Corpus Lookup Pattern" describes what it does
- **Reduced confusion** - Users understand when to use it (uncertainty about syntax)
- **Standalone routing** - API routing guide is immediately useful without corpus
- **Cleaner skills** - No confusing "DO NOT use" warnings

### Migration Notes

- Search for "v3 flow" and "v3-flow" to find all references
- Update any external documentation or tests that reference the old name
