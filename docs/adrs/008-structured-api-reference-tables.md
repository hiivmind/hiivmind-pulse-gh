# ADR-008: Structured API Reference Tables

**Status:** Accepted
**Date:** 2025-12-19
**Related:** ADR-007 (Domain File Split)

## Context

Following ADR-007, each domain file has:
- Support matrix table (operations × 4 methods)
- CLI Command Reference (structured table with `| Operation | Command | Notes |`)
- Corpus Lookup Guide (paragraph-style listing)

The Corpus Lookup Guide crams all REST endpoints and GraphQL mutations into single table rows, making it difficult to scan for specific operations:

```markdown
| REST | `GET /repos/{owner}/{repo}/issues`, `GET /issues/{number}`, `POST /issues`, ... |
```

## Decision

Replace the "Corpus Lookup Guide" section with two structured tables matching the CLI Command Reference format:

### REST API Reference

```markdown
## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/issues` | |
| Get | GET | `/repos/{owner}/{repo}/issues/{number}` | |
| Create | POST | `/repos/{owner}/{repo}/issues` | |
```

### GraphQL Reference

```markdown
## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.issues` | |
| Get | Query | `node(id:)` | Use `Issue` type |
| Create | Mutation | `createIssue` | |
```

### What to Drop

- **Search Keywords column** - Explicit operation names make corpus search hints redundant

### When to Include Tables

- **REST API Reference**: Only if domain has REST support (✓ in REST column)
- **GraphQL Reference**: Only if domain has GraphQL support (✓ in GraphQL column)

## Consequences

### Positive

- **Consistent format**: CLI, REST, and GraphQL all use same table structure
- **Easy scanning**: Find specific operation without parsing comma-separated lists
- **Support matrix alignment**: Table operations match support matrix operations
- **Corpus navigation**: Explicit endpoint/mutation names improve lookup accuracy

### Negative

- **File size increase**: Structured tables are more verbose than paragraph lists
- **Update scope**: All 25 domain files need modification

### Neutral

- **No new columns**: Notes column handles special cases (same as CLI tables)

## Implementation

1. Transform each domain file's Corpus Lookup Guide into two tables
2. Match operation names to support matrix rows
3. Include only tables for supported API methods
4. Remove old Corpus Lookup Guide section

## Success Criteria

- [ ] All domain files have structured REST/GraphQL tables (where applicable)
- [ ] Table operations match support matrix operations
- [ ] No remaining "Corpus Lookup Guide" sections
- [ ] Consistent column format across all domain files
