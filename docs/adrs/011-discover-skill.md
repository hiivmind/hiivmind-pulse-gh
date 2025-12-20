# ADR-011: Discover Skill for Capability Exploration

**Status:** Accepted
**Date:** 2025-12-20

## Context

The hiivmind-pulse-gh plugin has four skills:
- **init** - First-time workspace setup
- **refresh** - Sync config when stale
- **operations** - Execute GitHub operations
- **awareness** - Inject capability docs into CLAUDE.md

Users face a discovery problem: they don't know what operations they CAN ask the operations skill to perform. The existing reference files (`lib/references/api-routing.md` and `lib/references/domains/*.md`) contain comprehensive capability information but aren't surfaced interactively.

The gateway command has a basic "Interactive Menu" mode but it only shows 10 domains with typical operations - not the full capability matrix of 25 domains × multiple operations each.

## Decision

Create a new skill `hiivmind-pulse-gh-discover` that:

1. **Presents the quick reference table** from `lib/references/api-routing.md` (25 domains × 4 methods)
2. **Offers interactive drill-down** into domain-specific files
3. **Shows operation matrices** with CLI commands, REST endpoints, GraphQL mutations
4. **Hands off to operations** when user is ready to execute

### Skill Design

```
1. OVERVIEW  -> 2. NAVIGATE  -> 3. DETAIL  -> 4. HANDOFF
   (quick ref)    (domain)       (ops)        (execute)
```

**Key characteristics:**
- Does NOT require workspace initialization (read-only exploration)
- Uses existing reference files (no new data needed)
- Supports "fast path" for users who describe task directly
- Preserves context when handing off to operations skill

### Skill Taxonomy

| Skill | Answers |
|-------|---------|
| awareness | "What is this plugin?" (static CLAUDE.md injection) |
| operations | "Do this thing" (execution) |
| **discover** | "What CAN I ask you to do?" (interactive exploration) |

## Alternatives Considered

1. **Extend awareness skill** - Rejected. Awareness is about CLAUDE.md injection, not interactive exploration. Different user intent.

2. **Extend gateway interactive menu** - Rejected. Gateway should remain lightweight routing layer; discover is a dedicated exploration flow with drill-down.

3. **Add --help flag to operations** - Rejected. Doesn't provide the interactive drill-down experience or domain exploration.

4. **Generate static documentation** - Rejected. Users prefer interactive discovery over reading docs.

## Consequences

### Positive

- Users can explore capabilities before committing to an operation
- Leverages existing comprehensive reference documentation (no duplication)
- Seamless handoff preserves context (domain, operation already known)
- No workspace init required - works anywhere, even outside git repos
- Aligns with progressive disclosure pattern (overview → detail → action)

### Negative

- Fifth skill increases plugin complexity
- Gateway routing table needs update
- Some overlap with gateway's interactive menu (but discover is more comprehensive)

## Implementation

### Files to Create

| File | Purpose |
|------|---------|
| `skills/hiivmind-pulse-gh-discover/SKILL.md` | Main skill (~250 lines) |
| `skills/hiivmind-pulse-gh-discover/examples/examples.md` | Domain mapping reference |

### Files to Modify

| File | Change |
|------|--------|
| `commands/hiivmind-pulse-gh.md` | Add discover to domain detection and routing |

### Files to Read (No Changes)

| File | Purpose |
|------|---------|
| `lib/references/api-routing.md` | Quick reference table source |
| `lib/references/domains/*.md` | Domain detail source (25 files) |
