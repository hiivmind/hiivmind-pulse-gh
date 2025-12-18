# ADR Template Reference

> **Purpose:** Standard template for Architecture Decision Records following the Nygard format.
> **Usage:** Skills reference this template when generating ADR content.

---

## Frontmatter Schema

ADRs include YAML frontmatter for metadata and GitHub integration:

```yaml
---
adr: 5                        # ADR number (integer)
title: "Decision Title"       # Short, descriptive title
status: Proposed              # Proposed | Accepted | Deprecated | Superseded
date: 2025-12-17              # Date decision was recorded (YYYY-MM-DD)
milestone: v5.0.0             # GitHub milestone (optional, string)
issue: 142                    # GitHub issue number (optional, integer)
supersedes: [3, 4]            # ADR numbers this supersedes (optional, array)
superseded_by: 8              # ADR number that supersedes this (optional, integer)
deciders: [alice, bob]        # GitHub usernames of decision makers (optional)
---
```

### Status Values

| Status | Meaning |
|--------|---------|
| `Proposed` | Under discussion, not yet decided |
| `Accepted` | Decision made and in effect |
| `Deprecated` | No longer relevant (but was once accepted) |
| `Superseded` | Replaced by another ADR |

---

## Full Template

```markdown
---
adr: {number}
title: "{title}"
status: {status}
date: {date}
milestone: {milestone}
issue: {issue_number}
---

# {number}. {title}

## Status

{status}

{if superseded_by: "Superseded by [ADR-{superseded_by}](./NNNN-title.md)"}
{if supersedes: "Supersedes [ADR-{supersedes}](./NNNN-title.md)"}

## Context

{context}

What is the issue that we're seeing that is motivating this decision or change?

## Decision

{decision}

What is the change that we're proposing and/or doing?

## Consequences

{consequences}

What becomes easier or more difficult to do because of this change?

### Positive

- {positive_consequence_1}
- {positive_consequence_2}

### Negative

- {negative_consequence_1}
- {negative_consequence_2}

### Neutral

- {neutral_consequence_1}

## Alternatives Considered

### Alternative 1: {alternative_title}

{alternative_description}

**Rejected because:** {rejection_reason}

## References

- {reference_link_1}
- {reference_link_2}
```

---

## Minimal Template

For quick decisions, use the minimal template:

```markdown
---
adr: {number}
title: "{title}"
status: Accepted
date: {date}
---

# {number}. {title}

## Status

Accepted

## Context

{context}

## Decision

{decision}

## Consequences

{consequences}
```

---

## File Organization

ADRs are stored in `doc/adr/` at the repository root:

```
repository/
├── doc/
│   └── adr/
│       ├── 0001-record-architecture-decisions.md
│       ├── 0002-use-rest-api-exclusively.md
│       ├── 0003-implement-v3-flow-architecture.md
│       └── ...
└── ...
```

### Filename Convention

`NNNN-title-slug.md`

| Component | Format | Example |
|-----------|--------|---------|
| Number | 4-digit zero-padded | `0005` |
| Separator | hyphen | `-` |
| Title slug | lowercase, hyphens | `use-graphql-for-api` |
| Extension | `.md` | `.md` |

**Example:** `0005-use-graphql-for-api.md`

---

## Related Documentation

- `lib/github/patterns/adr-management.md` - Implementation patterns
- `skills/hiivmind-pulse-gh-adr/SKILL.md` - ADR skill workflow
