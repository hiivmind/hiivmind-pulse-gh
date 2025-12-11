# Schema Differences Log

> **Purpose:** Track differences between our assumptions and actual GitHub API responses
> **Created:** 2024-12-11
> **Why This Matters:** Hand-crafted fixtures test assumptions, not reality. This log documents where our assumptions were wrong.

---

## Identity Domain

### viewer Query - Email Field Requires Extra Scopes

**Date:** 2024-12-11
**Severity:** Medium
**Impact:** Cannot fetch email field without additional token scopes

**Our Assumption:**
```graphql
query {
  viewer {
    email  # ❌ Assumed this was available with default scopes
  }
}
```

**Reality:**
The `email` field requires one of these scopes:
- `user:email`
- `read:user`

**Current Token Scopes:**
- `admin:public_key`
- `gist`
- `project`
- `read:org`
- `repo`

**Resolution:**
- Removed `email` field from `viewer`, `user`, and `organization` queries in manifest
- Updated sanitization rules to remove email-specific sanitization

**Lesson:**
GraphQL schema permissions are field-level, not just query-level. We need to be aware of which fields require elevated scopes.

---

## Milestone Domain

### Empty Milestone List

**Date:** 2024-12-11
**Severity:** Low
**Impact:** Test repository has no milestones, resulting in empty array fixture

**Our Assumption:**
Expected repository to have at least one milestone for testing

**Reality:**
- `list_all.json` - Empty array `[]`
- `list_open.json` - Not recorded (likely empty too)
- `list_closed.json` - Not recorded (likely empty too)

**Resolution:**
- Need to create synthetic fixtures with sample milestone data
- Or record from a repository that has milestones
- Empty array is still valid - shows what API returns when no data exists

**Lesson:**
Live recording will show us edge cases like empty states. We need both:
1. Live-recorded fixtures from repos with data
2. Synthetic fixtures for edge cases we might not hit naturally

---

## Recording Infrastructure Issues

### Viewer Fixture Contains Errors

**Date:** 2024-12-11
**Severity:** Medium
**Impact:** Recorded fixture contains both error and partial data

**Current State:**
```json
{
  "errors": [{
    "type": "INSUFFICIENT_SCOPES",
    "message": "..."
  }],
  "": {
    "data": {
      "viewer": {
        "email": "test@example.com",
        "name": "Test User"
      }
    }
  }
}
```

**Problem:**
- Sanitization script is creating malformed structure
- Empty string key `""` is invalid
- Should either have full data OR errors, not both

**Resolution Needed:**
- Fix sanitization script to handle error responses properly
- Don't sanitize fixtures that contain GraphQL errors
- Or record again after fixing manifest to not request email field

---

## To Be Discovered

As we record more fixtures, we'll document:
- Missing fields we assumed would exist
- Extra fields we didn't know about
- Type mismatches (expected string, got number)
- Null values in fields we thought were required
- Array structures that differ from documentation
- Enum values we didn't account for

This log will guide future fixture updates and help us write more resilient code.
