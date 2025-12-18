# Introspection Examples

**Purpose:** Detailed, repeatable examples for state-checking operations.

These examples need to be HEAVY on detail because they check state and need to be executed consistently. Shell commands, exact syntax, and edge cases matter here.

## Index

| Example | Purpose | Used By |
|---------|---------|---------|
| `config-parsing.md` | Read/write YAML config files | init, refresh, operations, adr, awareness |
| `workspace-detection.md` | Git remote → owner/repo extraction | init |
| `authentication.md` | gh auth verification and scope checking | init, operations |
| `tool-detection.md` | gh, jq, yq availability checking | init |
| `id-resolution.md` | Name → ID resolution with cache-first strategy | operations, adr |
| `graphql-execution.md` | Temp file method for GraphQL queries | operations |
| `graphql-queries.md` | Common GraphQL query patterns | operations, refresh |
| `error-handling.md` | API error patterns and recovery | refresh, operations |

## Why Heavy?

Introspection operations need detailed examples because:

1. **Repeatability** - The same commands should work every time
2. **Exact syntax** - Shell escaping, yq selectors, regex patterns must be precise
3. **Edge cases** - Handling missing files, empty responses, permission errors
4. **Consistency** - All skills should check state the same way

## Usage

Skills reference these examples with the `See:` convention:

```markdown
## Phase 1: CONTEXT

**See:** `lib/examples/introspection/config-parsing.md`

1. Load config.yaml
2. Verify initialization
```

## Related

- `lib/examples/operations/` - LIGHT examples for API routing
- `docs/config-schema.md` - Config file schema reference
