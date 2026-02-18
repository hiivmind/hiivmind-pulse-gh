# Operations Skill Examples

Local references to centralized examples. Domain-specific examples removed — corpus provides JIT syntax.

## Introspection Examples

Used before executing operations:

| Example | Location | Operations Usage |
|---------|----------|------------------|
| Config Parsing | `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` | Load workspace context |
| ID Resolution | `{PLUGIN_ROOT}/lib/patterns/id-resolution.md` | Resolve names to IDs (cache-first) |
| GraphQL Execution | `{PLUGIN_ROOT}/lib/patterns/graphql-execution.md` | Execute GraphQL mutations |
| Error Handling | `{PLUGIN_ROOT}/lib/patterns/error-handling.md` | Handle API errors |

## Operations Examples

Used for routing and syntax lookup:

| Example | Location | Operations Usage |
|---------|----------|------------------|
| API Routing | `{PLUGIN_ROOT}/lib/references/api-routing.md` | Determine GraphQL vs REST (THE source) |
| Corpus Lookup | `{PLUGIN_ROOT}/lib/patterns/corpus-lookup.md` | Look up exact syntax when uncertain |

## Architecture: Corpus-First

**Why no domain-specific examples here?**

Operations uses a corpus-first approach:

1. **Route** - Read `api-routing.md` for API choice (GraphQL vs REST)
2. **Resolve** - Get IDs from config cache
3. **Syntax** - If uncertain, corpus provides exact syntax JIT
4. **Execute** - Run via `gh api`

Domain examples (issues.md, projects.md) were removed because:
- The corpus is more comprehensive (70k+ lines)
- Corpus stays up-to-date with GitHub API changes
- Examples would duplicate corpus content

## Operations-Specific Notes

### When to Use Corpus

Use corpus lookup when you have a **knowledge gap**:
- Uncertain about mutation structure
- Unfamiliar endpoint
- Complex multi-step operation
- API may have changed

Skip corpus for **well-known patterns**:
- `gh issue create`
- `gh pr merge`
- Simple REST endpoints you've used before

### ID Resolution Priority

Always try cache first:
1. Check `.hiivmind/github/config.yaml`
2. If found → use cached ID
3. If not found → corpus lookup + API query

### Blocked Operations

Some dangerous operations are blocked. Check `{PLUGIN_ROOT}/lib/references/operation-blocklist.md` before executing:
- Repository deletion
- Organization deletion
- Transfer ownership

---

## Related

- [Operations SKILL.md](../SKILL.md) - Full skill documentation
- [API Routing]({PLUGIN_ROOT}/lib/references/api-routing.md) - Domain → API decisions
- [External Corpus](https://github.com/hiivmind/hiivmind-corpus-github) - GitHub API documentation
