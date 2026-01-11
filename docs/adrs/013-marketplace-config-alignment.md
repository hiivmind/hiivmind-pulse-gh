# ADR-013: Marketplace Configuration Alignment

**Status:** Accepted
**Date:** 2026-01-11

## Context

The init skill was updated to automatically configure `.claude/settings.json` with marketplace dependencies, enabling team members to be prompted to install hiivmind-pulse-gh when they trust a repository (Phase 5, lines 243-289).

However, the initial implementation had two critical misalignments with the Claude Code marketplace specification and existing documentation:

### Issue 1: Incorrect `repo` Field Format

The configuration used:
```json
"repo": "hiivmind"
```

But the [Claude Code marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces.md) requires the full `owner/repo` format for GitHub sources:

> For GitHub sources: `repo` is required... the full URL must match exactly

The README.md installation instructions (line 54) also confirm the correct format:
```bash
/plugin marketplace add hiivmind/hiivmind-pulse-gh
```

### Issue 2: Marketplace Name Inconsistency

The configuration used `"hiivmind"` as the marketplace key:
```json
"extraKnownMarketplaces": {
  "hiivmind": { ... }
},
"enabledPlugins": {
  "hiivmind-pulse-gh@hiivmind": true
}
```

This created a disconnect between:
- **Manual installation**: `/plugin install hiivmind-pulse-gh@hiivmind-pulse-gh` (per README)
- **Marketplace manifest**: `"name": "hiivmind-pulse-gh"` (in marketplace.json:2)
- **Auto-configuration**: References marketplace as `hiivmind`

Users would see different marketplace names depending on installation method, creating confusion.

## Decision

Align `.claude/settings.json` configuration with marketplace.json and manual installation patterns:

```json
{
  "extraKnownMarketplaces": {
    "hiivmind-pulse-gh": {
      "source": {
        "source": "github",
        "repo": "hiivmind/hiivmind-pulse-gh"
      }
    }
  },
  "enabledPlugins": {
    "hiivmind-pulse-gh@hiivmind-pulse-gh": true
  }
}
```

### Key Changes

1. **`repo` field**: Use full `"hiivmind/hiivmind-pulse-gh"` format
2. **Marketplace key**: Use `"hiivmind-pulse-gh"` to match marketplace.json name
3. **Plugin identifier**: Use `"hiivmind-pulse-gh@hiivmind-pulse-gh"` to match manual installation

## Alternatives Considered

### Option A: Match marketplace.json Name (CHOSEN)

Use `"hiivmind-pulse-gh"` as marketplace key to match the marketplace.json name.

**Pros:**
- Consistent experience between manual and auto-configured installations
- Users see the same marketplace name regardless of how it was added
- Aligns with the single-marketplace-per-repo pattern

**Cons:**
- None identified

### Option B: Use Organization-Level Key

Use `"hiivmind"` as marketplace key for potential future multi-plugin organization.

**Pros:**
- Semantic grouping if organization publishes multiple marketplaces
- Shorter identifier

**Cons:**
- Inconsistent with marketplace.json actual name
- Confusing UX: manual install sees `hiivmind-pulse-gh`, auto-config sees `hiivmind`
- Premature optimization (no other hiivmind marketplaces exist)
- Requires README update to explain the dual naming

## Consequences

### Positive

- **Consistency**: Auto-configured and manually installed marketplaces appear identically
- **Compliance**: Follows Claude Code marketplace specification exactly
- **Clarity**: Single source of truth for marketplace name (marketplace.json)
- **Documentation alignment**: Configuration matches README installation instructions

### Negative

- None identified. This is a pure fix with no tradeoffs.

### Migration

Since this is a new feature (marketplace auto-configuration in init skill), no migration is required. Users running init after this change will get the correct configuration from the start.

Existing repositories that ran init before this fix may have incorrect settings:
- Config is still valid but uses inconsistent naming
- Next refresh or re-init will use corrected format
- No breaking change (both forms work, one is just clearer)

## Implementation

**Files Changed:**
- `skills/hiivmind-pulse-gh-init/SKILL.md` (lines 247-263)

**Verification:**
- ✅ Aligns with marketplace.json `"name": "hiivmind-pulse-gh"`
- ✅ Matches README.md manual installation pattern
- ✅ Follows Claude Code marketplace specification for GitHub sources
- ✅ Consistent user experience across installation methods
