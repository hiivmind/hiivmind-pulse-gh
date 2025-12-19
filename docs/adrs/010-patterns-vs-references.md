# ADR-010: Separate Patterns from References in lib/

**Status:** Accepted
**Date:** 2025-12-20
**Supersedes:** ADR-005 (Examples Library Architecture)

## Context

ADR-005 established `lib/examples/` with two subdirectories:
- `introspection/` - Intended for "HEAVY" state-checking examples
- `operations/` - Intended for "LIGHT" API routing examples

Over time, the distinction became unclear:
- "introspection" contains mostly executable patterns but also `token-permissions.md` (reference data)
- "operations" contains `corpus-lookup.md` (pattern) alongside `domains/` (reference data)
- The "HEAVY" vs "LIGHT" terminology was imprecise

The plugin-dev skill recommends separating `examples/` (executable guides) from `references/` (static data).

## Decision

Reorganize `lib/` into two clear categories based on content type:

```
lib/
├── patterns/                   # HOW to do things (executable guides)
│   ├── authentication.md
│   ├── config-parsing.md
│   ├── corpus-lookup.md
│   ├── error-handling.md
│   ├── graphql-execution.md
│   ├── graphql-queries.md
│   ├── id-resolution.md
│   ├── tool-detection.md
│   └── workspace-detection.md
└── references/                 # WHAT exists (static lookup data)
    ├── api-routing.md
    ├── token-permissions.md
    └── domains/
        └── (25 domain files)
```

### Classification Criteria

| Type | Contains | Example Content |
|------|----------|-----------------|
| **Pattern** | Step-by-step instructions, algorithms, code examples | "Run this command, parse output, handle errors..." |
| **Reference** | Lookup tables, matrices, static data | "Issues use GraphQL. Milestones use REST..." |

## Consequences

### Positive

- Clear distinction between HOW (patterns) and WHAT (references)
- Aligns with plugin-dev skill recommendations
- Easier to find documentation by purpose
- Simpler mental model: "Need to know how? → patterns/. Need to look up? → references/"

### Negative

- Requires updating ~100 file references across the codebase
- Supersedes ADR-005 structure

### Migration

All `lib/examples/` path references must be updated:
- `lib/patterns/` → `lib/patterns/`
- `lib/references/` → `lib/references/` (for api-routing.md, domains/)
- `lib/patterns/corpus-lookup.md` → `lib/patterns/corpus-lookup.md`
