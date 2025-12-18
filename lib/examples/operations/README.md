# Operations Examples

**Purpose:** Lightweight routing guidance for GitHub API operations.

These examples are LIGHT because **the corpus provides exact syntax just-in-time**. Operations examples focus on routing decisions (GraphQL vs REST) and how to invoke the corpus when needed.

## Index

| Example | Purpose |
|---------|---------|
| `api-routing.md` | Domain → API routing decisions (THE canonical source) |
| `corpus-lookup.md` | How to invoke corpus for syntax when uncertain |

## Why Light?

Operation examples are minimal because:

1. **Corpus provides JIT syntax** - The external corpus has exact GraphQL mutations and REST endpoints
2. **Routing is stable** - GraphQL vs REST decisions don't change often
3. **Skills orchestrate** - Skills focus on flow, corpus provides implementation details

## The Corpus-First Approach

```
1. ROUTE       →   2. RESOLVE   →   3. EXECUTE
   (API choice)      (IDs)           (run)
        │               │                │
 api-routing.md    config.yaml      corpus lookup
                   cache            (if uncertain)
```

1. **Check api-routing.md** - Determine GraphQL vs REST
2. **If syntax is clear** - Execute directly
3. **If uncertain** - Use corpus lookup for exact syntax

## Usage

The operations skill references `api-routing.md` as THE source of truth:

```markdown
## Phase 3: ROUTE

**See:** `lib/examples/operations/api-routing.md` (canonical source)

If uncertain about syntax, use corpus lookup.
```

## Domain-Specific Examples Removed

Previous versions had domain-specific examples (issues.md, projects.md, etc.). These have been removed because:

- Corpus provides better, more current syntax
- Reduces maintenance burden
- Single source of truth (corpus) is easier to update

## Related

- `lib/examples/introspection/` - HEAVY examples for state-checking
- External corpus: `hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs`
