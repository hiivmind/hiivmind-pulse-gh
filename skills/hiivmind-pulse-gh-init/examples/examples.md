# Init Skill Examples

Local references to centralized examples plus init-specific notes.

## Introspection Examples

These are the primary examples used by the init skill:

| Example | Location | Init Usage |
|---------|----------|------------|
| Tool Detection | `lib/examples/introspection/tool-detection.md` | Check gh, jq, yq availability |
| Authentication | `lib/examples/introspection/authentication.md` | Verify gh auth and required scopes |
| Workspace Detection | `lib/examples/introspection/workspace-detection.md` | Git remote → owner/repo extraction |
| Config Parsing | `lib/examples/introspection/config-parsing.md` | Write discovered config to YAML |
| GraphQL Execution | `lib/examples/introspection/graphql-execution.md` | Query organization/user structure |
| Error Handling | `lib/examples/introspection/error-handling.md` | Handle API errors during discovery |

## Operations Examples

| Example | Location | Init Usage |
|---------|----------|------------|
| API Routing | `lib/examples/operations/api-routing.md` | Determine GraphQL vs REST for discovery |
| Corpus Lookup | `lib/examples/operations/corpus-lookup.md` | Look up projectsV2 query syntax |

## Init-Specific Notes

### Tool Detection Order

Init checks tools in this order (fail fast):
1. `gh` - Required for all GitHub operations
2. `jq` - Required for JSON parsing
3. `yq` - Required for YAML config

If any tool is missing, stop immediately with install instructions.

### Authentication Scopes

Init requires these scopes:
- `repo` - Repository access
- `read:org` - Organization structure (if org workspace)
- `read:project` - Project v2 access
- `project` - Project v2 mutations (for status updates)

### Discovery Order

Init discovers in this order:
1. Workspace type (org vs user)
2. Repositories (from git remote)
3. Projects v2 (all accessible)
4. Fields per project
5. Options per field

### Config Write Location

Always write to `.hiivmind/github/config.yaml` relative to git root.

---

## Related

- [Init SKILL.md](../SKILL.md) - Full skill documentation
- [Config Schema](../../../docs/config-schema.md) - Config.yaml structure
