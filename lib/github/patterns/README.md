# GitHub Pattern Library

Reusable, tested patterns for GitHub operations. Skills reference these patterns rather than embedding inline examples.

## Purpose

This pattern library provides:
- **Tested commands** - Each pattern contains working bash/GraphQL examples verified to work in Claude Code's Bash tool
- **Multiple implementations** - Preferred method (Claude tools/yq) with fallbacks (grep/sed)
- **Cross-platform support** - Bash examples with notes on Windows/PowerShell alternatives where applicable
- **Error recovery** - Common errors and how to handle them

## How Skills Reference Patterns

Skills reference patterns using the `See:` convention:

```markdown
### Step 2: Detect Workspace

Determine the GitHub owner/repo from git remote configuration.

**See:** `lib/github/patterns/workspace-detection.md`
```

This keeps skills focused on workflow orchestration while patterns handle implementation details.

## Pattern Format

Each pattern file follows this structure:

```markdown
# Pattern: [Name]

## Purpose
[One-line description of what this pattern does]

## When to Use
- [Use case 1]
- [Use case 2]

## Prerequisites
- [Required tools or patterns]
- [Configuration requirements]

## Algorithm

### Step 1: [Step Name]
[Description of the step]

**Using Claude tools (preferred):**
- [Approach using Read/Grep/Glob tools]

**Using bash with gh/jq/yq:**
```bash
# Tested, working command
gh api graphql -f query='...'
```

**Using bash without yq (fallback):**
```bash
# grep/sed fallback when yq unavailable
grep -E "^key:" config.yaml | cut -d: -f2
```

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `error message` | Why it happens | How to fix |

## Examples

### Example 1: [Scenario Name]
**Input:**
[What you start with]

**Process:**
[Commands executed]

**Output:**
[Expected result]

## Related Patterns
- `other-pattern.md` - [How they relate]
```

## Pattern Index

### Iteration 1: Foundation + Init

| Pattern | Purpose | Status |
|---------|---------|--------|
| `tool-detection.md` | Verify gh, jq, yq availability | Done |
| `authentication.md` | Auth verification, scope checking | Done |
| `config-parsing.md` | Read/write config.yaml | Done |
| `workspace-detection.md` | Git remote parsing, org vs user detection | Done |
| `graphql-queries.md` | Query syntax reference (schema patterns) | Done |
| `graphql-execution.md` | Execute queries via temp file (solves escaping) | Done |
| `corpus-lookup.md` | Look up API syntax when uncertain | Done |

### Iteration 2: Patterns + Refresh Skill

| Pattern | Purpose | Status |
|---------|---------|--------|
| `id-resolution.md` | Resolve names/numbers to GraphQL IDs with cache-first strategy | Done |
| `error-handling.md` | Central error reference for all GitHub operations | Done |

### ADR Integration (v5.1.0)

| Pattern | Purpose | Status |
|---------|---------|--------|
| `adr-management.md` | ADR numbering, file creation, GitHub issue linking, sync | Done |
| `adr-awareness.md` | Proactive triggers, CLAUDE.md integration, suggestion templates | Done |

### Why No Domain-Specific Patterns?

The corpus lookup pattern (`corpus-lookup.md`) provides just-in-time syntax lookup when needed, eliminating domain-specific patterns like `rest-operations.md`, `project-operations.md`, etc.

**How it works:**
1. **Routing guide** (`reference/api-routing.md`) determines API type (GraphQL/REST/CLI) - useful standalone
2. **Corpus skill** provides exact syntax when uncertain (70k+ line GraphQL schema and REST docs)
3. **Execution patterns** (`graphql-execution.md`) handle all API types uniformly

All domain operations (issues, projects, milestones, protection, etc.) can use corpus lookup when syntax is uncertain.

No separate domain patterns needed - the corpus has the syntax, the routing guide has the decisions.

## Design Principles

1. **Test everything** - No pattern includes untested commands
2. **Multiple fallbacks** - Graceful degradation when preferred tools unavailable
3. **Show the output** - Examples include expected output format
4. **Link related patterns** - Clear dependency graph between patterns
5. **Error-first** - Every pattern documents common failures

## Reference

This pattern library follows the architecture from [hiivmind-corpus](https://github.com/hiivmind/hiivmind-corpus/tree/main/lib/corpus/patterns).
