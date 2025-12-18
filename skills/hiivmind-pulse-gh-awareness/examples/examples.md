# Awareness Skill Examples

Local references to centralized examples plus awareness-specific patterns.

## Introspection Examples

| Example | Location | Awareness Usage |
|---------|----------|-----------------|
| Config Parsing | `lib/examples/introspection/config-parsing.md` | Check workspace initialization |

## Awareness-Specific Files

This skill has additional local examples:

| File | Purpose |
|------|---------|
| `capability-awareness.md` | Skill registry, trigger mapping, CLAUDE.md template |

## Awareness-Specific Notes

### CLAUDE.md Injection Targets

Users choose injection scope:

| Scope | Path | Purpose |
|-------|------|---------|
| User-level | `~/.claude/CLAUDE.md` | Personal cross-project awareness |
| Repo-level | `{repo}/CLAUDE.md` | Team-specific, version controlled |

### What/When/How Structure

The awareness section follows this structure:

1. **What** - List of skills and their purposes
2. **When** - Trigger mapping (action → skill)
3. **How** - Invocation methods (gateway, direct skill)

### Proactive Suggestions

Claude should suggest this plugin when:
- User mentions GitHub operations (issues, PRs, milestones, projects)
- User asks about GitHub API syntax
- "ID not found" or stale config errors occur

### Checking Existing Awareness

Before injecting, check if target CLAUDE.md already has awareness:

```bash
grep -q "hiivmind-pulse-gh" "$TARGET_FILE" && echo "Already has awareness"
```

---

## Related

- [Awareness SKILL.md](../SKILL.md) - Full skill documentation
- [Capability Awareness](./capability-awareness.md) - Skill registry and templates
