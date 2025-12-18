# Refresh Skill Examples

Local references to centralized examples plus refresh-specific notes.

## Introspection Examples

These are the primary examples used by the refresh skill:

| Example | Location | Refresh Usage |
|---------|----------|---------------|
| Config Parsing | `lib/examples/introspection/config-parsing.md` | Read existing config, update sections |
| GraphQL Execution | `lib/examples/introspection/graphql-execution.md` | Re-query changed sections |
| Error Handling | `lib/examples/introspection/error-handling.md` | Handle stale ID errors |
| ID Resolution | `lib/examples/introspection/id-resolution.md` | Verify cached IDs still valid |

## Operations Examples

| Example | Location | Refresh Usage |
|---------|----------|---------------|
| API Routing | `lib/examples/operations/api-routing.md` | Determine GraphQL vs REST for re-queries |
| Corpus Lookup | `lib/examples/operations/corpus-lookup.md` | Look up query syntax for sections |

## Refresh-Specific Notes

### Staleness Checking

Refresh checks `.hiivmind/github/freshness.yaml` for per-section staleness:

```yaml
sections:
  workspace:
    last_checked: "2025-12-16T12:00:00Z"
    threshold_hours: 168  # 7 days
    stale: false
  projects:
    last_checked: "2025-12-15T10:00:00Z"
    threshold_hours: 24   # 1 day
    stale: true
```

### Section Priority

When multiple sections are stale, refresh in this order:
1. `workspace` - Foundation for other lookups
2. `projects` - Most frequently changing
3. `views` - Depends on projects
4. `repo_settings` - Less frequently changing
5. `automations` - Rarely changes
6. `relationships` - Rarely changes
7. `teams` - Rarely changes

### Selective Refresh

Users can refresh specific sections:
- "refresh projects" → only `projects` section
- "refresh all" → all stale sections
- "force refresh workspace" → ignore freshness, re-query

### Merging Strategy

When updating config:
1. Load existing config
2. Query fresh data for section
3. Merge (fresh data wins for that section)
4. Update freshness timestamp
5. Write config

Never lose data from un-refreshed sections.

---

## Related

- [Refresh SKILL.md](../SKILL.md) - Full skill documentation
- [Freshness Template](../../../templates/freshness.yaml.template) - Freshness tracking schema
