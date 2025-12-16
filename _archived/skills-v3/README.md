# Archived v3 Skills

**Archived:** 2025-12-16
**Reason:** Replaced by v4 pattern-based architecture

## Why Archived

The v3 init skill had reliability issues discovered during testing:

1. **Untested inline examples** - GraphQL queries embedded in SKILL.md failed with syntax errors
2. **Context assumptions** - Init assumed git repository context, failed from multi-repo parent directories
3. **Vague corpus instructions** - Said "search corpus" without explaining how
4. **No STOP points** - Phases blended together without explicit boundaries
5. **No user collaboration** - Auto-decided on targets instead of asking

## What Replaced It

The v4 architecture introduces:

- **Pattern library** at `lib/github/patterns/` with tested, reusable command patterns
- **Explicit STOP points** between phases
- **User collaboration points** - Always confirms detected context, never auto-decides
- Skills reference patterns via `See: lib/github/patterns/X.md`

See `docs/architecture-redesign.md` for the full redesign plan.

## Contents

| Skill | Purpose | Status |
|-------|---------|--------|
| `hiivmind-pulse-gh-init/` | One-time workspace initialization | Archived |

## Note

The `refresh` and `operations` skills remain active in `skills/`. They will be updated to reference patterns in a future iteration.

## Reference

- Previous archive (v2 skills): `archive/skills/`
- Redesign plan: `docs/architecture-redesign.md`
- New patterns: `lib/github/patterns/`
