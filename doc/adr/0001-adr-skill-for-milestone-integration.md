---
adr: 1
title: "ADR Skill for Milestone Integration"
status: Proposed
date: 2025-12-17
milestone: "v5.1.0 - ADR Integration"
issue: 83
deciders: [nathanielramm]
---

# 1. ADR Skill for Milestone Integration

## Status

Proposed

## Context

The hiivmind-pulse-gh plugin manages GitHub operations including milestones, issues, and projects. When planning significant work (milestones with many issues, major refactoring), architectural decisions are made but not systematically documented.

Problems with current approach:
- Decisions are lost in chat history or commit messages
- New contributors don't understand why certain approaches were chosen
- Trade-offs and alternatives considered are not recorded
- No link between architectural decisions and the milestones they affect

Architecture Decision Records (ADRs) are a lightweight documentation format (popularized by Michael Nygard in 2011) that captures decisions along with their context and consequences.

## Decision

Add an ADR skill to hiivmind-pulse-gh that:

1. **Dual Storage** - ADRs stored as both:
   - Markdown files in `doc/adr/NNNN-title.md` (version controlled, authoritative)
   - GitHub issues with `adr` label (discussion, milestone linking)

2. **Milestone Integration** - ADR issues assigned to milestones, creating traceability between decisions and implementation work

3. **Proactive Suggestions** - Skill proactively suggests ADR creation when:
   - Milestone has 5+ issues (indicates significant work)
   - Refactoring keywords detected (restructure, migrate, redesign)
   - Always requires explicit user confirmation

4. **Cross-Project Awareness** - Projects with hiivmind-pulse-gh installed learn about ADR capability via CLAUDE.md section injection

5. **v3 Flow Architecture** - Skill follows existing pattern-based architecture with routing, corpus lookup, and execution patterns

## Consequences

### Positive

- Architectural decisions are systematically captured with context
- Milestone planning includes decision documentation by default
- Future developers can understand rationale via linked ADR issues
- ADR workflow integrates naturally with existing GitHub project management
- Self-documenting: this very ADR demonstrates the workflow

### Negative

- Additional skill to maintain
- Risk of ADR fatigue if triggered too aggressively (mitigated by confirmation requirement)
- Two locations for ADR content (file vs issue) could drift (mitigated by file-as-authoritative pattern)

### Neutral

- Introduces `doc/adr/` directory convention to repositories
- Requires `adr` label in GitHub repositories

## Alternatives Considered

### Alternative 1: ADRs as GitHub Issues Only

Store ADRs purely as GitHub issues without markdown files.

**Rejected because:** Issues are not version-controlled, harder to review in PRs, and would be lost if repository migrated.

### Alternative 2: ADRs as Files Only (adr-tools style)

Use traditional adr-tools approach with local files only, no GitHub integration.

**Rejected because:** Loses milestone/project linking benefits, no discussion capability, doesn't integrate with existing GitHub-centric workflow.

### Alternative 3: Use External ADR Service

Integrate with dedicated ADR management tools like Log4Brains or ADR Manager.

**Rejected because:** Adds external dependency, doesn't integrate with existing hiivmind-pulse-gh ecosystem.

## Implementation

The skill will be implemented as:

| File | Purpose |
|------|---------|
| `skills/hiivmind-pulse-gh-adr/SKILL.md` | Main skill with 6-phase workflow |
| `lib/github/patterns/adr-management.md` | Numbering, file creation, sync patterns |
| `reference/adr-template.md` | Nygard format template with frontmatter |
| `lib/github/patterns/adr-awareness.md` | CLAUDE.md injection snippet |

Gateway command update adds ADR to domain detection and interactive menu.

## References

- [Michael Nygard's original ADR blog post](http://thinkrelevance.com/blog/2011/11/15/documenting-architecture-decisions)
- [adr-tools by Nat Pryce](https://github.com/npryce/adr-tools)
- [hiivmind-pulse-gh v3 architecture](../docs/architecture-redesign.md)
