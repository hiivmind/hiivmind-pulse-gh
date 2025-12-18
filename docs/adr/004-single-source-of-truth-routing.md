# ADR-004: Single Source of Truth for API Routing

**Status:** Accepted
**Date:** 2025-12-18
**Related Issues:** #94, #97, #98, #99, #100
**Milestone:** v5.3.0

## Context

Domain-to-API routing decisions (e.g., "Milestones → REST for CRUD, GraphQL for assignment") currently appear in **10+ locations**:

| Location | Purpose |
|----------|---------|
| `reference/api-routing.md` | Canonical routing guide (260 lines) |
| `README.md` | Quick reference for users |
| `CLAUDE.md` | Development reference |
| `skills/hiivmind-pulse-gh-operations/SKILL.md` | Domain Quick Reference table |
| `skills/hiivmind-pulse-gh-refresh/SKILL.md` | Refreshable sections |
| `commands/hiivmind-pulse-gh.md` | Domain detection keywords |
| `lib/github/patterns/corpus-lookup.md` | Example routing lookups |
| `reference/workflows/*.md` | Embedded routing examples |
| Archived/deprecated files | Historical copies |

This duplication creates:
1. **Maintenance burden:** Updates require changing 10+ files
2. **Drift risk:** Tables can become inconsistent across files
3. **Confusion:** Multiple "authoritative" sources

## Decision

**`lib/examples/operations/api-routing.md` is THE canonical source of truth for API routing decisions. All other files must reference it, not embed copies.**

### Implementation

1. Move `reference/api-routing.md` to `lib/examples/operations/api-routing.md`

2. Remove domain tables from:
   - `CLAUDE.md` (development guidance only)
   - `README.md` (link instead of embed)
   - `skills/hiivmind-pulse-gh-operations/SKILL.md` (reference instead of embed)

3. Update all files to reference the canonical location:
   ```markdown
   **See:** `lib/examples/operations/api-routing.md`
   ```

4. Keep intent detection keywords in `commands/hiivmind-pulse-gh.md` (different purpose: natural language → domain mapping, not API routing)

## Consequences

### Positive

- **Single update point:** One file to modify when APIs change
- **Consistency guaranteed:** No drift between copies
- **Clear ownership:** api-routing.md is THE authoritative source
- **Reduced file size:** Other files become smaller and more focused

### Negative

- **Indirection:** Readers must follow reference to see routing
- **Two-step lookup:** Skills reference api-routing.md, then may invoke corpus

### Neutral

- **Domain detection keywords remain:** Gateway still needs them for intent parsing

## What Stays vs What Goes

### KEEP in api-routing.md (canonical):
- Quick Reference table (domain → API mapping)
- Domain Details sections (operation → API → keywords)
- Search keywords for corpus lookup
- Loading context examples
- Unlisted domains guidance

### REMOVE from other files:
- "Supported Domains" table from README.md
- "Supported Domains" table from CLAUDE.md
- "Domain Quick Reference" table from operations skill
- Embedded routing examples from workflow docs

### KEEP (different purpose):
- Domain detection keywords in gateway command (intent detection, not API routing)
- Example workflows (historical reference, archived)

## Files Affected

| File | Change |
|------|--------|
| `reference/api-routing.md` | MOVE to `lib/examples/operations/` |
| `CLAUDE.md` | Remove domain table, link to api-routing.md |
| `README.md` | Remove domain table, link to api-routing.md |
| `skills/hiivmind-pulse-gh-operations/SKILL.md` | Remove Domain Quick Reference, add reference |
| `commands/hiivmind-pulse-gh.md` | Keep intent keywords, add clarifying note |

## Verification

After implementation:

```bash
# Find any remaining embedded domain tables (should only be api-routing.md)
grep -r "| Issues | GraphQL |" skills/ commands/ CLAUDE.md README.md

# Verify references point to new location
grep -r "lib/examples/operations/api-routing.md" skills/ commands/
```
