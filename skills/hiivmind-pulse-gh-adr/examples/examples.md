# ADR Skill Examples

Local references to centralized examples plus ADR-specific patterns.

## Introspection Examples

| Example | Location | ADR Usage |
|---------|----------|-----------|
| Config Parsing | `lib/examples/introspection/config-parsing.md` | Check workspace initialization |
| ID Resolution | `lib/examples/introspection/id-resolution.md` | Resolve milestone IDs for linking |

## Operations Examples

| Example | Location | ADR Usage |
|---------|----------|-----------|
| API Routing | `lib/examples/operations/api-routing.md` | Issues (create) → GraphQL |
| Corpus Lookup | `lib/examples/operations/corpus-lookup.md` | Look up createIssue mutation |

## ADR-Specific Patterns

### ADR Numbering

```bash
# Get next ADR number
LAST_NUM=$(ls doc/adr/*.md 2>/dev/null | grep -oP '\d{4}' | sort -n | tail -1)
NEXT_NUM=$((10#${LAST_NUM:-0} + 1))
printf "%04d" "$NEXT_NUM"
```

### ADR File Template

**See:** `docs/adr-template.md` for full template.

```markdown
---
adr: {number}
title: "{title}"
status: Proposed
date: {date}
milestone: (to be linked)
issue: (to be created)
---

# {number}. {title}

## Status

Proposed

## Context

[Context from user...]

## Decision

[Decision from user...]

## Consequences

[Consequences from user...]
```

### Creating GitHub Issue

ADRs create linked GitHub issues with the `adr` label:

```bash
# Ensure adr label exists
gh label create adr --description "Architecture Decision Record" --color 0E8A16 2>/dev/null || true

# Create issue
gh issue create \
  --title "ADR-$NUM: $TITLE" \
  --label "adr" \
  --body "$(cat $ADR_FILE)"
```

### Updating Frontmatter

After creating the issue, update the ADR file:

```bash
# Update frontmatter with issue number and milestone
yq -i --front-matter=process ".issue = $ISSUE_NUM | .milestone = \"$MILESTONE\"" "$ADR_FILE"
```

### Proactive Triggering

Suggest ADRs when:
- Milestone has 5+ issues
- User describes major refactoring (3+ files)
- Keywords: "restructure", "migrate", "redesign", "new pattern"
- Modifying public APIs or interfaces

---

## Related

- [ADR SKILL.md](../SKILL.md) - Full skill documentation
- [ADR Template](../../../docs/adr-template.md) - Markdown template
- [Awareness Patterns](../../hiivmind-pulse-gh-awareness/examples/) - ADR awareness and management
