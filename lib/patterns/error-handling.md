# Pattern: Error Handling

## Purpose

Central reference for detecting and recovering from errors across all GitHub operations.

## When to Use

- After any GitHub API operation fails
- Building error handling into workflows
- Understanding what went wrong and how to fix it

## Prerequisites

- **tool-detection.md** - Verify tools available before checking tool errors
- **authentication.md** - Auth errors are a common failure mode

---

## Focused Error Guides

For detailed error handling, see the focused guides:

| Guide | Covers |
|-------|--------|
| **error-auth.md** | Authentication, missing scopes, token expiry |
| **error-graphql.md** | GraphQL response errors, type mismatches, entity resolution |
| **error-rest.md** | REST HTTP errors, rate limiting, network issues |
| **error-local.md** | Config file errors, tool availability, YAML parsing |

---

## Quick Error Detection

### GraphQL Errors

```bash
RESPONSE=$(gh api graphql -f query="$(cat /tmp/query.graphql)" 2>&1)

if echo "$RESPONSE" | jq -e '.errors' >/dev/null 2>&1; then
  echo "GraphQL Error:"
  echo "$RESPONSE" | jq -r '.errors[].message'
  exit 1
fi
```

**Details:** See `error-graphql.md`

### REST Errors

```bash
if ! RESPONSE=$(gh api "$ENDPOINT" 2>&1); then
  echo "REST API call failed: $RESPONSE"
  exit 1
fi
```

**Details:** See `error-rest.md`

### Authentication Errors

```bash
if ! gh auth status >/dev/null 2>&1; then
  echo "Not authenticated - run: gh auth login"
  exit 1
fi
```

**Details:** See `error-auth.md`

### Local/Config Errors

```bash
if [[ ! -f ".hiivmind/github/config.yaml" ]]; then
  echo "Config not found - run: /gh init"
  exit 1
fi
```

**Details:** See `error-local.md`

---

## User Communication

When reporting errors to users, include:

1. **What happened** - Clear description
2. **Why** - Likely cause
3. **How to fix** - Actionable recovery steps

```markdown
**Error:** Could not resolve to a ProjectV2 with the number 99.

**Cause:** Project #99 either doesn't exist or you don't have access.

**Recovery:**
1. Verify the project number in the project URL
2. Check you have access to the project
3. Try listing projects to find the correct number
```

---

## Error Recovery Flow

```
Error Detected
      ↓
┌─────────────────────────────────────┐
│ 1. Identify error category          │
│    (auth? API? network? local?)     │
└───────────────────┬─────────────────┘
                    ↓
┌─────────────────────────────────────┐
│ 2. Check if auto-recoverable        │
│    (retry? refresh token? wait?)    │
└───────────────────┬─────────────────┘
                    ↓
         ┌─────────┴─────────┐
         │                   │
    Auto-recover         User action
         │                   │
         ↓                   ↓
      Retry              Show clear
      operation          error message
                         with recovery
                         steps
```

---

## Related Patterns

- **error-auth.md** - Authentication and authorization errors
- **error-graphql.md** - GraphQL-specific errors
- **error-rest.md** - REST API and network errors
- **error-local.md** - Config and tool errors
- **authentication.md** - Proactive auth verification
- **tool-detection.md** - Tool availability checks
- **graphql-execution.md** - GraphQL-specific error context
- **corpus-lookup.md** - Syntax lookup when uncertain
