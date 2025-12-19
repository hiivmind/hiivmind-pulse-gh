# ADR-009: Consolidated Token Permissions Reference

**Status:** Accepted
**Date:** 2025-12-19
**Related:** ADR-007 (Domain File Split), ADR-008 (Structured API Tables)

## Context

Users need to know which token permissions are required for each API domain. This information is scattered across GitHub's documentation and varies between:

- **Classic OAuth scopes** (e.g., `repo`, `project`, `admin:repo_hook`)
- **Fine-grained PAT permissions** (e.g., `Issues: Read`, `Projects: Read and write`)

The existing `lib/examples/introspection/authentication.md` documents required scopes for this plugin, but doesn't provide per-domain permission details.

## Decision

Create a single centralized reference file at `lib/examples/introspection/token-permissions.md` documenting permissions for all 25 domains in one place.

This consolidates information rather than adding a section to each domain file, which would be harder to maintain and cross-reference.

Document both classic OAuth scopes and fine-grained PAT permissions, sourced from GitHub's official REST API documentation.

## Consequences

### Positive

- Single source of truth for all permission info
- Easy to cross-reference between domains
- Simpler maintenance (one file to update)
- Complements existing `authentication.md` in same directory

### Negative

- Requires consulting a separate file when looking at domain docs
- May need updates as GitHub changes their permission model
