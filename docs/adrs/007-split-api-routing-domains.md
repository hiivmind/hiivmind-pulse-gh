# ADR-007: Split API Routing Guide into Domain-Specific Files

**Status:** Accepted
**Date:** 2025-12-19
**Supersedes:** None
**Related:** ADR-004 (Single Source of Truth), ADR-006 (Multi-Method Visibility)

## Context

Following ADR-006, `lib/references/api-routing.md` grew to 1,052 lines covering 25 GitHub domains. Each domain has:
- Support matrix table (4 methods × operations)
- CLI command reference
- Corpus lookup guide

The operations skill requires reading this file in Phase 3 for routing decisions. Loading 1,052 lines for every operation creates unnecessary context overhead when only one domain's details are needed.

### Current State

```
lib/references/
└── api-routing.md (1,052 lines, ~50 KB)
    ├── Quick Reference table (30 lines)
    ├── Method Selection Guide (45 lines)
    └── 25 Domain Detail Sections (~40 lines each)
```

### Problem

- **Context bloat**: Full file loaded even for single-domain operations
- **Maintenance difficulty**: One large file harder to update than focused files
- **Review complexity**: Changes to one domain require reviewing entire file

## Decision

Split `api-routing.md` into:

1. **Quick reference** (`api-routing.md`, ~150 lines): Summary table + method selection guide
2. **Domain files** (`domains/{domain}.md`, ~50 lines each): Detailed syntax per domain

### New Structure

```
lib/references/
├── api-routing.md (~150 lines)
│   ├── Quick Reference table (25 domains × 4 methods)
│   ├── Method Selection Guide
│   ├── Symbol legend (✓/✗/⊗)
│   └── Link to domains/ directory
│
└── domains/
    ├── issues.md
    ├── pull-requests.md
    ├── milestones.md
    ├── labels.md
    ├── projects-v2.md
    ├── branch-protection.md
    ├── rulesets.md
    ├── actions.md
    ├── secrets.md
    ├── variables.md
    ├── releases.md
    ├── repository.md
    ├── gists.md
    ├── search.md
    ├── collaborators.md
    ├── teams.md
    ├── webhooks.md
    ├── checks.md
    ├── deployments.md
    ├── environments.md
    ├── dependabot.md
    ├── code-scanning.md
    ├── secret-scanning.md
    ├── notifications.md
    └── reactions.md
```

### Skill Reading Pattern

Update `hiivmind-pulse-gh-operations` Phase 3:

**Before:**
```
Read the FULL lib/references/api-routing.md file.
Do NOT grep or search - read it completely.
```

**After:**
```
1. Read lib/references/api-routing.md (quick reference, ~150 lines)
2. Identify domain from quick reference table
3. Read lib/references/domains/{domain}.md for detailed syntax
```

## Consequences

### Positive

- **80% context reduction**: ~200 lines vs 1,052 lines per operation
- **Focused maintenance**: Update one domain without touching others
- **Easier review**: Domain-specific PRs are smaller and clearer
- **ADR-004 preserved**: Quick reference remains single routing source

### Negative

- **Two-step reading**: Must read quick reference then domain file
- **More files**: 26 files instead of 1 (manageable with clear naming)
- **Cross-domain operations**: May need multiple domain files (rare)

### Neutral

- **Skill changes required**: Phase 3 needs updated reading pattern
- **File discovery**: Domain files are clearly named and linked from quick reference

## Alternatives Considered

1. **Keep monolithic file**: Rejected - context overhead scales with domain count
2. **Per-domain skills**: Rejected - 25+ skills violates plugin-dev guidance, massive duplication
3. **Skill references directory**: Considered - domains/ in lib/examples/ is more aligned with existing patterns

## Implementation

1. Create `lib/references/domains/` directory
2. Extract each domain section to its own file
3. Slim `api-routing.md` to quick reference only
4. Update `hiivmind-pulse-gh-operations` Phase 3
5. Verify all domain files are correctly formatted

## Success Criteria

- [ ] Quick reference table accessible in ~150 lines
- [ ] Each domain file is self-contained (~50 lines)
- [ ] Operations skill correctly routes using two-step pattern
- [ ] All 25 domains have individual files
- [ ] Total context per operation: ~200 lines (quick ref + 1 domain)
