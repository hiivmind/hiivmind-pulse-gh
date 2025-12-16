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

### Future Iterations

| Pattern | Purpose | Iteration |
|---------|---------|-----------|
| `rest-operations.md` | REST endpoint patterns | 2 |
| `project-operations.md` | Project v2 field updates, item management | 2 |
| `issue-pr-operations.md` | Issue/PR CRUD operations | 2 |
| `protection-operations.md` | Branch protection, rulesets | 2 |
| `error-handling.md` | Common errors and recovery | 2 |
| `api-selection.md` | GraphQL vs REST decision logic | 4 |
| `corpus-lookup.md` | How to find syntax in embedded corpus | 4 |
| `id-resolution.md` | Resolve project/field/option IDs from config | 3 |

## Design Principles

1. **Test everything** - No pattern includes untested commands
2. **Multiple fallbacks** - Graceful degradation when preferred tools unavailable
3. **Show the output** - Examples include expected output format
4. **Link related patterns** - Clear dependency graph between patterns
5. **Error-first** - Every pattern documents common failures

## Reference

This pattern library follows the architecture from [hiivmind-corpus](https://github.com/hiivmind/hiivmind-corpus/tree/main/lib/corpus/patterns).
