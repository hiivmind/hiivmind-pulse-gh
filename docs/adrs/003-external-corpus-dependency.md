# ADR-003: External Corpus Dependency

**Status:** Accepted
**Date:** 2025-12-18
**Related Issues:** #90, #91, #92, #93
**Milestone:** v5.2.0

## Context

The hiivmind-pulse-gh plugin currently embeds a local GitHub documentation corpus at `skills/hiivmind-corpus-github/`. This embedded corpus:

- Consumes **692MB** of disk space
- Contains **9 sections** (REST, GraphQL, Issues, PRs, Repos, Actions, Orgs, CLI, Auth)
- Includes a 70k-line GraphQL schema
- Is a subset of the full GitHub documentation

Meanwhile, an external corpus exists at `hiivmind-corpus-github` which provides:

- **36 sections** (including Copilot, Code Security, Admin, Billing, etc.)
- **3,346 documents** total coverage
- **165 gh CLI commands** indexed (embedded corpus has none)
- Full GitHub documentation from github/docs repository
- Sophisticated navigation skill with STOP points and AskUserQuestion patterns

The embedded corpus was created for self-contained distribution, but maintaining two copies of similar content creates:
1. Synchronization burden (two corpuses to update)
2. Inconsistent coverage (external has 4x more sections)
3. Disk bloat (692MB per plugin installation)

## Decision

**Declare a dependency on the external `hiivmind-corpus-github` plugin. Remove the embedded corpus entirely.**

### Implementation

1. Update `.claude-plugin/plugin.json` to declare dependency:
   ```json
   "dependencies": {
     "plugins": ["hiivmind-corpus-github@hiivmind-corpus-github"]
   }
   ```

2. Update all corpus invocations from:
   ```
   hiivmind-pulse-gh:hiivmind-corpus-github
   ```
   To:
   ```
   hiivmind-corpus-github-docs-navigate
   ```

3. Delete embedded corpus:
   ```bash
   rm -rf skills/hiivmind-corpus-github/
   ```

## Consequences

### Positive

- **Plugin size:** 700MB → ~2MB (99.7% reduction)
- **Coverage:** 9 sections → 36 sections (4x improvement)
- **gh CLI:** Now includes 165 indexed commands
- **Single source of truth:** One corpus to maintain and update
- **Better navigation:** External corpus has sophisticated search patterns

### Negative

- **External dependency:** Users must install both plugins
- **Network requirement:** External corpus must be available for installation
- **Version coupling:** Changes to external corpus may affect pulse-gh

### Neutral

- **GraphQL schema:** Same 70k-line schema in both (no change in schema coverage)

## Files Affected

| File | Change |
|------|--------|
| `.claude-plugin/plugin.json` | Add dependency |
| `skills/hiivmind-corpus-github/` | Delete (692MB) |
| `skills/*/SKILL.md` (5 files) | Update invocation |
| `lib/github/patterns/corpus-lookup.md` | Update invocation |
| `lib/github/patterns/id-resolution.md` | Update invocation |
| `reference/api-routing.md` | Update invocation |
| `CLAUDE.md` | Update invocation |
| `README.md` | Update invocation |

## Verification

After implementation:

```bash
# Verify no old invocations remain
grep -r "hiivmind-pulse-gh:hiivmind-corpus-github" .

# Verify embedded corpus deleted
ls skills/hiivmind-corpus-github/  # Should not exist

# Test new invocation works
# Invoke: hiivmind-corpus-github-docs-navigate
```
