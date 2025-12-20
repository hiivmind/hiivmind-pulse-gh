# ADR-012: Flexible Operations Execution

**Status:** Accepted
**Date:** 2025-12-21

## Context

The operations skill (`skills/hiivmind-pulse-gh-operations/SKILL.md`) used a rigid 5-phase sequential structure that created several problems:

1. **Redundant file reads** - Phases mandated reading files that may already be in context
2. **Duplicate content** - Phase 2 had a 16-row "IDs Needed per Domain" table duplicating `api-routing.md`
3. **Verbose domain mappings** - A 25-row domain file mapping table when Claude often knows the syntax
4. **No fast path** - Common operations like `gh issue create` went through full lookup flow

Additionally, Claude consistently attempted non-existent CLI commands like `gh milestone create`, indicating a need for explicit documentation of CLI-less domains.

## Decision

### 1. Replace Rigid Phases with Decision-Tree Flow

Replace 5 sequential phases with 4 lightweight considerations:

```
1. VERIFY WORKSPACE (quick check)
   ↓
2. DETERMINE APPROACH
   ├─ Known CLI command? → Execute directly with enrichment
   ├─ Known API pattern? → Execute via gh api
   ├─ Uncertain? → Consult resources → Execute
   └─ Unknown domain? → Corpus lookup required
   ↓
3. EXECUTE + ENRICH (apply context from config)
   ↓
4. REPORT
```

### 2. Context-Aware Resource Consultation

Replace "Read X" imperatives with "Consult X when needed":

| Knowledge Gap | Resource |
|---------------|----------|
| Which API (GraphQL vs REST)? | `{PLUGIN_ROOT}/lib/references/api-routing.md` |
| Exact mutation/endpoint syntax | Corpus lookup |
| ID resolution from cache | `{PLUGIN_ROOT}/lib/patterns/id-resolution.md` |
| Error recovery | `{PLUGIN_ROOT}/lib/patterns/error-handling.md` |

Key principle: If a resource was already read earlier in the conversation, don't re-read it.

### 3. Document CLI-less Domains Explicitly

Add a prominent section listing all 14 domains without `gh` CLI support:

| Domain | REST Endpoint Pattern |
|--------|----------------------|
| **Milestones** | `/repos/{owner}/{repo}/milestones` |
| Branch Protection | `/repos/{owner}/{repo}/branches/{branch}/protection` |
| Collaborators | `/repos/{owner}/{repo}/collaborators/{username}` |
| Teams | `/orgs/{org}/teams` |
| Webhooks | `/repos/{owner}/{repo}/hooks` |
| Checks | `/repos/{owner}/{repo}/check-runs` |
| Deployments | `/repos/{owner}/{repo}/deployments` |
| Environments | `/repos/{owner}/{repo}/environments/{name}` |
| Dependabot | `/repos/{owner}/{repo}/dependabot/alerts` |
| Code Scanning | `/repos/{owner}/{repo}/code-scanning/alerts` |
| Secret Scanning | `/repos/{owner}/{repo}/secret-scanning/alerts` |
| Notifications | `/notifications` |
| Reactions | `/repos/{owner}/{repo}/issues/{number}/reactions` |
| Rulesets | `/repos/{owner}/{repo}/rulesets` |

This prevents Claude from attempting non-existent commands like `gh milestone create`.

### 4. Establish `{PLUGIN_ROOT}` Path Convention

Define a semantic path convention for cross-skill file references:

- `{PLUGIN_ROOT}` = Plugin root directory (where `plugin.json` lives)
- Skills document this convention in a "Path Convention" section
- Enables clear references like `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

Applied to all 9 skill and example files.

## Consequences

### Positive

- **Faster execution** - Known operations proceed directly without mandatory lookups
- **Reduced context usage** - No redundant file reads
- **Clearer errors** - Explicit CLI-less domain list prevents incorrect command attempts
- **Simpler skill** - Reduced from ~400 to ~220 lines
- **Semantic paths** - `{PLUGIN_ROOT}` is self-documenting vs `../../lib/`

### Negative

- Less explicit phase structure may reduce predictability for new users
- Relies on Claude's judgment about "known" vs "uncertain" operations

### Migration

Domain-specific notes moved from operations SKILL.md to respective domain files:
- Projects v2 field types → `lib/references/domains/projects-v2.md`
- Teams scope requirements → `lib/references/domains/teams.md`
- Milestones CLI warning → `lib/references/domains/milestones.md`
