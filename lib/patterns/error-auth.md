# Pattern: Authentication Errors

## Purpose

Detect and recover from GitHub authentication and authorization errors.

## When to Use

- After receiving 401/403 responses
- When operations fail with "Resource not accessible" messages
- When token scopes are insufficient

**Parent:** See `error-handling.md` for the error detection overview and recovery flow.

---

## Not Logged In

**Error:**
```
You are not logged into any GitHub hosts. Run gh auth login to authenticate.
```

**Detection:**
```bash
if ! gh auth status >/dev/null 2>&1; then
  echo "Not authenticated"
fi
```

**Recovery:**
```bash
gh auth login
```

---

## Missing Scopes

**Error:**
```
Resource not accessible by integration
```
or
```
GraphQL: Resource not accessible by personal access token
```

**Detection:**
```bash
# Check current scopes
SCOPES=$(gh auth status 2>&1 | grep -oP "Token scopes: '\K[^']+")
echo "Current scopes: $SCOPES"

# Check for specific scope
if ! echo "$SCOPES" | grep -q "project"; then
  echo "Missing 'project' scope"
fi
```

**Recovery:**
```bash
# Add specific scopes
gh auth refresh --scopes 'repo,read:org,project,read:project'
```

**Required scopes for hiivmind-pulse-gh:**
- `repo` - Repository access
- `read:org` - Organization membership
- `project` - Project write access
- `read:project` - Project read access

---

## Token Expired

**Error:**
```
HTTP 401
Bad credentials
```

**Detection:**
```bash
if gh api /user 2>&1 | grep -q "401\|Bad credentials"; then
  echo "Token expired or invalid"
fi
```

**Recovery:**
```bash
gh auth login
```

---

## Related Patterns

- **authentication.md** - Proactive auth verification before operations
- **error-handling.md** - Error detection overview and recovery flow
