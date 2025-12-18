# Pattern: ADR Awareness

## Purpose

Guide Claude Code instances on when to suggest creating Architecture Decision Records and how to integrate ADR workflows with milestone planning.

## When to Use

This pattern provides:
1. **CLAUDE.md injection snippet** - Add to projects to enable ADR awareness
2. **Proactive trigger detection** - When to suggest ADR creation
3. **Suggestion templates** - How to propose ADR creation to users

---

## Project Awareness Snippet

Add this section to `CLAUDE.md` in projects that use hiivmind-pulse-gh:

```markdown
## Architecture Decision Records

This project uses ADRs to document significant architecture decisions.

### When to Suggest ADR Creation

Create an ADR when:

1. **Choosing between alternatives** - Multiple valid approaches exist
2. **Changing established patterns** - Modifying how something has been done
3. **Introducing new dependencies** - Adding libraries, services, or tools
4. **Defining standards** - Establishing conventions for the project
5. **Making trade-offs** - Accepting downsides for benefits

### Proactive Triggers

Suggest ADR creation when detecting:
- Milestone with 5+ issues (indicates significant work)
- Refactoring involving 3+ files
- Keywords: "restructure", "migrate", "redesign", "new pattern", "breaking change"
- Discussion of "why" something is done a certain way

### How to Create an ADR

```
/hiivmind-pulse-gh create ADR for [topic]
```

Or describe your decision:
```
"I've decided to use X instead of Y because Z. Can we document this as an ADR?"
```

### ADR Location

- **Files:** `doc/adr/NNNN-title.md` (authoritative)
- **Issues:** Labeled with `adr`, linked to milestones
- **Template:** See `reference/adr-template.md`
```

---

## Proactive Trigger Detection

### Milestone Planning Trigger

When a user creates or discusses a milestone with multiple issues:

**Detection Logic:**
```
IF milestone.open_issues >= 5
AND milestone.title matches (version pattern OR feature name)
THEN suggest ADR creation
```

**Suggestion Template:**
```
I notice you're planning milestone "{milestone_title}" with {N} issues.

For significant architectural work like this, I recommend creating an ADR to document:
- **Context:** Why this work is needed
- **Decision:** The approach you're taking
- **Consequences:** Trade-offs and implications

This helps future developers understand the rationale.

Would you like to create an ADR for this milestone?
```

### Refactoring Trigger

When user describes refactoring work:

**Detection Logic:**
```
IF message contains ["refactor", "restructure", "migrate", "redesign", "rewrite"]
AND (file_count >= 3 OR scope_keywords present)
THEN suggest ADR creation
```

**Suggestion Template:**
```
I see you're planning to {action} the {component}.

This kind of architectural change benefits from an ADR to capture:
- Why the current approach needs changing
- What the new approach will be
- Trade-offs you're accepting

Would you like to create an ADR before we start?
```

### Breaking Change Trigger

When user mentions breaking changes:

**Detection Logic:**
```
IF message contains ["breaking change", "API change", "incompatible", "migration required"]
THEN strongly suggest ADR creation
```

**Suggestion Template:**
```
Breaking changes should be documented in an ADR to:
- Explain why the breaking change is necessary
- Document the migration path
- Record what was considered as alternatives

I recommend creating an ADR for this change. Shall I help?
```

---

## Keywords Reference

| Category | Keywords |
|----------|----------|
| Architecture | architecture, design, pattern, approach, structure, system |
| Change | refactor, migrate, restructure, redesign, rewrite, overhaul |
| Decision | decide, choice, alternative, trade-off, why, because |
| Significance | major, significant, breaking, foundational, core |
| Documentation | document, record, explain, rationale, reasoning |

---

## Integration with Other Skills

### With Init Skill

During workspace initialization:
- Check for existing `doc/adr/` directory
- Mention ADR capability in completion message if directory exists

### With Operations Skill

When creating milestones:
- If milestone has description suggesting major work, offer ADR
- When milestone reaches 5+ issues, remind about ADR opportunity

### With Refresh Skill

When refreshing config:
- Include ADR issues in milestone issue counts
- Flag stale ADRs (Proposed status > 30 days)

---

## Example Scenarios

### Scenario 1: New Milestone Planning

**User:** "Let's create a milestone for the authentication redesign. It'll involve updating the login flow, adding OAuth support, and migrating existing sessions."

**Response:** Detect "redesign", "migrating", multiple components mentioned.

**Suggestion:**
```
This authentication redesign sounds like significant architectural work.

I recommend creating an ADR to document:
- Why the current auth system needs redesigning
- The new OAuth-based approach
- Migration strategy for existing sessions
- Security implications

Would you like to create ADR-NNNN: Authentication System Redesign?
```

### Scenario 2: Technical Decision Made

**User:** "I've decided we should use GraphQL instead of REST for the new API because it gives us better flexibility for the mobile app."

**Response:** Detect decision statement with rationale.

**Suggestion:**
```
That's a significant technical decision. Let's capture it as an ADR so future developers understand the reasoning.

I'll create:
- **ADR-NNNN: Use GraphQL for New API**
- Context: Mobile app flexibility needs
- Decision: GraphQL over REST
- Consequences: [we can discuss these]

Shall I proceed?
```

---

## Related Patterns

- **adr-management.md** - Technical implementation of ADR operations
- **config-parsing.md** - Workspace configuration
- **id-resolution.md** - Milestone linking

## Related References

- **reference/adr-template.md** - ADR file template
