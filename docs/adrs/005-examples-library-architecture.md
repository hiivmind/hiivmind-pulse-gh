# ADR-005: Examples Library Architecture

**Status:** Accepted
**Date:** 2025-12-18
**Related Issues:** #94, #95, #96, #97, #101, #102
**Milestone:** v5.3.0

## Context

The current plugin has two overlapping documentation structures:

- `lib/github/patterns/` - 13 pattern files (algorithms, implementations)
- `reference/` - Canonical documentation (api-routing, config-schema, workflows)

This creates confusion:
1. **patterns vs reference:** What's the difference?
2. **Dual-purpose content:** Some patterns serve both introspection (checking state) and operations (executing actions)
3. **Scattered examples:** Complete examples exist in patterns, workflows, and skills

Additionally:
- Introspection operations (checking config, auth, tools) need **very repeatable** examples
- Operation executions (API calls) need **minimal** examples since corpus provides JIT syntax

## Decision

**Create a unified `lib/examples/` structure with explicit separation:**

- `lib/patterns/` - HEAVY examples for repeatable state-checking operations
- `lib/references/` - LIGHT examples, just API routing (corpus handles syntax)
- `skills/*/examples/` - Local files that REFER to central examples + add clarifications

### Key Principle

**Introspection needs repeatability (detailed examples). Operations just need routing (corpus provides syntax JIT).**

## Implementation

### New Directory Structure

```
lib/
└── examples/
    ├── introspection/          # HEAVY - very repeatable
    │   ├── README.md           # Index with section groupings
    │   ├── config-parsing.md
    │   ├── workspace-detection.md
    │   ├── authentication.md
    │   ├── tool-detection.md
    │   ├── id-resolution.md
    │   ├── graphql-execution.md
    │   ├── graphql-queries.md
    │   └── error-handling.md
    │
    └── operations/             # LIGHT - just routing
        ├── README.md           # Explains corpus-first approach
        ├── api-routing.md      # THE canonical routing source
        └── corpus-lookup.md    # How to use corpus for syntax
```

### Introspection Examples (HEAVY)

These examples need to be detailed and repeatable because they check state:

| Example | Purpose | Why Heavy |
|---------|---------|-----------|
| `config-parsing.md` | YAML config read/write | Exact yq commands matter |
| `workspace-detection.md` | Git remote → owner/repo | Regex patterns are precise |
| `authentication.md` | gh auth + scope checking | Scope names must match |
| `tool-detection.md` | gh, jq, yq availability | Version requirements specific |
| `id-resolution.md` | Name → ID with cache | GraphQL queries exact |
| `error-handling.md` | API error patterns | Error codes specific |
| `graphql-execution.md` | Temp file method | Escaping is tricky |

### Operations Examples (LIGHT)

Operations just need routing guidance. The corpus provides exact syntax:

| Example | Purpose | Why Light |
|---------|---------|-----------|
| `api-routing.md` | Domain → API decision | Just routing table |
| `corpus-lookup.md` | How to invoke corpus | Invocation pattern only |

**Removed:** Domain-specific examples (issues.md, projects.md, milestones.md)
**Reason:** Corpus provides JIT syntax. Operations skill routes, then calls corpus.

### Skill-Local Examples

Each skill gets `examples/examples.md` that:

1. Lists which central examples it uses
2. Adds skill-specific clarifications
3. Groups by `## Introspection` / `## Operations` sections

```markdown
# Init Skill Examples

## Introspection Examples
| Example | Location | Notes |
|---------|----------|-------|
| Tool Detection | `lib/patterns/tool-detection.md` | Run first |
| Authentication | `lib/patterns/authentication.md` | Check scopes |

## Operations Examples
| Example | Location | Notes |
|---------|----------|-------|
| API Routing | `lib/references/api-routing.md` | For project discovery |
```

## Consequences

### Positive

- **Clear separation:** Introspection vs operations purpose is explicit
- **Maintainability:** Heavy examples (introspection) get attention; light examples (operations) stay minimal
- **Corpus-first:** Operations rely on JIT corpus lookup, reducing embedded examples
- **Skill autonomy:** Local examples files provide context without duplicating content

### Negative

- **Two lookups:** Skill → local examples → central examples
- **Migration effort:** Moving and renaming many files

### Neutral

- **Awareness patterns:** Move to skill-local examples or inline (adr-awareness, capability-awareness)

## Files Affected

| Action | Files |
|--------|-------|
| CREATE | `lib/patterns/README.md` |
| CREATE | `lib/references/README.md` |
| MOVE | 8 patterns → `lib/patterns/` |
| MOVE | api-routing.md, corpus-lookup.md → `lib/references/` |
| CREATE | `skills/*/examples/examples.md` (5 files) |
| DELETE | `skills/hiivmind-pulse-gh-operations/examples/*.md` (domain examples) |
| DELETE | `lib/github/patterns/` (after moving) |
| DELETE | `reference/` (after moving api-routing, config-schema) |
| ARCHIVE | `reference/workflows/`, `knowledge/` |

## Verification

After implementation:

```bash
# Verify new structure exists
ls lib/patterns/
ls lib/references/

# Verify old structure removed
ls lib/github/patterns/  # Should not exist
ls reference/            # Should not exist

# Verify path references updated
grep -r "lib/github/patterns" skills/ commands/  # Should find nothing
```
