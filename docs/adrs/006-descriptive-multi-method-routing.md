# ADR-006: Descriptive Multi-Method API Routing Visibility

**Status:** Accepted
**Date:** 2025-12-19
**Accepted:** 2025-12-19
**Related Milestone:** API Routing Guide: Multi-Method Visibility
**Related Issues:** (to be linked during issue creation phase)

## Context

Currently, `lib/examples/operations/api-routing.md` recommends a **single best method** per operation (e.g., "Use GraphQL for this" or "Use REST for that"). This prescriptive approach has limitations:

1. **Limited User Agency**: Users cannot see that multiple methods often work for the same operation
2. **No Alternative Options**: When the recommended method fails, users don't know what to try
3. **Hidden Capabilities**: Users don't understand the full GitHub API landscape (gh CLI, REST, GraphQL, Web UI)
4. **Poor Debugging**: Troubleshooting API issues requires checking multiple sources

### Current State

- Quick Reference table shows 1 API per operation (GraphQL or REST)
- Domain detail sections specify "Use REST for CRUD, GraphQL for reads"
- No mention of gh CLI alternatives (except in a few notes)
- Web UI limitations only documented for Projects v2 views

### Affected Users

- Automation developers (might need gh CLI instead of REST)
- Integration engineers (might need GraphQL for complex queries)
- Troubleshooters (need to try alternative methods when one fails)
- Learners (want to understand GitHub API surface area)

## Decision

Transform `lib/examples/operations/api-routing.md` to show **support across all 4 methods** (gh CLI, REST, GraphQL, Web UI) for each operation, using a clear ✓/✗/⊗ notation:

### New Table Format

```markdown
| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Create | `gh issue create` | ✓ | ✓ | ✓ | All methods work |
| Update | ✗ | ✓ | ✓ | ✓ | No CLI support |
| Delete | ⊗ | ⊗ | ⊗ | ⊗ | Blocked for safety |
```

**Symbol Meanings:**
- ✓ = Supported and available
- ✗ = Not available for this operation
- ⊗ = Available but blocked for safety (see operation-blocklist.md)

### Coverage Scope

Document **all GitHub domains**, organized by category:

- **Core Operations** (11): Issues, PRs, Milestones, Labels, Projects v2, Discussions, Pull Request Reviews
- **Security** (6): Branch Protection, Rulesets, Secrets, Variables, Dependabot, Code Scanning
- **Automation** (3): Actions (Workflows/Runs/Jobs), Releases, Deployments
- **Collaboration** (4): Collaborators, Teams, Invitations, Reactions
- **Repository** (3): Settings, Topics, Webhooks
- **CI/CD** (2): Checks, Environments
- **Other** (4): Gists, Search, Notifications, Secret Scanning

### Implementation Approach

1. **Research each domain** using 4 methods:
   - gh CLI: `gh {domain} --help`
   - REST: Use GitHub API corpus for endpoints
   - GraphQL: Use GitHub API corpus for schema
   - Web UI: Check operation-blocklist.md and existing docs

2. **Update routing guide incrementally** with GitHub issues (one per domain)

3. **Add Method Selection Guide** explaining when to use each method

4. **Move Search Keywords** to separate subsections (cleaner tables)

## Consequences

### Positive

- **User Empowerment**: See all options, choose based on context (automation vs interactive vs complex queries)
- **Better Debugging**: Try alternative methods when one fails
- **Learning Resource**: Understand GitHub API landscape (CLI vs REST vs GraphQL vs UI)
- **Safety Transparency**: ⊗ clearly marks operations that are blocked
- **Backward Compatible**: No skill code changes needed (single source of truth maintained)
- **Standalone Useful**: Guide remains useful without corpus lookup

### Negative

- **Wider Tables**: 4 method columns instead of 1 API recommendation (but still scannable)
- **Research Effort**: ~25 domains × ~3 hours per domain for comprehensive coverage
- **Maintenance Overhead**: More columns to keep in sync as APIs evolve
- **Possible Confusion**: More information might overwhelm some users (mitigated by clear legend and examples)

### Neutral

- **Corpus Integration**: GitHub API corpus queries still used for exact syntax (no change to pattern)
- **Skill Execution**: Operations skill still reads api-routing.md in Phase 3 (no change needed)

## Alternatives Considered

1. **Add CLI column only**: Rejected - doesn't address Web UI limitations or GraphQL visibility
2. **Create separate "all methods" document**: Rejected - violates ADR-004 (single source of truth)
3. **Embed method support in corpus**: Rejected - corpus is for exact API syntax, not routing decisions
4. **Maintain prescriptive format**: Status quo - doesn't solve user limitations

## Related Decisions

- **ADR-004: Single Source of Truth for API Routing** - Maintains this principle by expanding (not duplicating) the canonical routing guide
- **ADR-005: Examples Library Architecture** - Routing guide remains in lib/examples/operations (the canonical location)

## Implementation Plan

1. **Create milestone** "API Routing Guide: Multi-Method Visibility"
2. **Create 25 GitHub issues** (one per domain) for systematic tracking
3. **Research each domain** using gh CLI, GitHub API corpus, and operation-blocklist.md
4. **Update api-routing.md** incrementally as domains are researched
5. **Add Method Selection Guide** explaining ✓/✗/⊗ and when to use each method
6. **Verify** all domains covered and guide remains standalone useful

## Success Criteria

- [x] All documented domains show support for all 4 methods
- [x] Quick Reference table includes method indicators (not just single API)
- [x] Domain detail sections have 4-column method support tables
- [x] Legend clearly explains ✓/✗/⊗ symbols
- [x] CLI commands shown in table (e.g., `gh issue create`)
- [x] Search keywords moved to separate "Corpus Lookup Guide" subsections
- [x] Method Selection Guide added explaining decision tree
- [x] No changes required to skills (api-routing.md remains consumable as-is)
- [x] Cross-references to operation-blocklist.md in place
- [x] File remains standalone useful (no corpus required for basic routing)

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Table width explosion | Keep columns narrow, use separate keywords subsections |
| Information overload | Provide clear legend, add Method Selection Guide with examples |
| Maintenance burden | Create GitHub issues per domain for tracking, establish update process |
| API changes outdating info | Include refresh schedule in documentation |
| User confusion on symbols | Add prominent legend at top, use examples |

## Notes

This ADR expands the scope of `lib/examples/operations/api-routing.md` to be more descriptive and comprehensive, while maintaining its role as the single source of truth per ADR-004. No existing patterns or decisions are violated.
