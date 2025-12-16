# Pattern: Error Handling

## Purpose

Central reference for detecting and recovering from errors across all GitHub operations.

## When to Use

- After any GitHub API operation fails
- Building error handling into workflows
- Understanding what went wrong and how to fix it
- Providing clear error messages to users

## Prerequisites

- **tool-detection.md** - Verify tools available before checking tool errors
- **authentication.md** - Auth errors are a common failure mode

---

## Error Detection

### GraphQL Errors

GraphQL responses include an `errors` array when something goes wrong:

```bash
RESPONSE=$(gh api graphql -f query="$(cat /tmp/query.graphql)" 2>&1)

# Check for GraphQL errors in response
if echo "$RESPONSE" | jq -e '.errors' >/dev/null 2>&1; then
  echo "GraphQL Error:"
  echo "$RESPONSE" | jq -r '.errors[].message'
  exit 1
fi

# Check for empty data (query succeeded but returned nothing)
if echo "$RESPONSE" | jq -e '.data | values | length == 0' >/dev/null 2>&1; then
  echo "No results found"
fi
```

### REST Errors

REST API returns HTTP status codes:

```bash
# Method 1: Check status with -i flag
RESPONSE=$(gh api /repos/owner/repo/milestones -i 2>&1)
HTTP_STATUS=$(echo "$RESPONSE" | head -1 | cut -d' ' -f2)

if [[ "$HTTP_STATUS" != "200" && "$HTTP_STATUS" != "201" ]]; then
  echo "REST Error: HTTP $HTTP_STATUS"
  echo "$RESPONSE" | tail -n +2 | jq -r '.message // .'
  exit 1
fi

# Method 2: Check exit code (simpler)
if ! gh api /repos/owner/repo/milestones 2>&1; then
  echo "REST API call failed"
  exit 1
fi
```

### gh CLI Errors

CLI commands return non-zero exit codes on failure:

```bash
# Check exit code
if ! OUTPUT=$(gh issue list 2>&1); then
  echo "Command failed: $OUTPUT"
  exit 1
fi

# Or capture both output and status
OUTPUT=$(gh issue list 2>&1)
STATUS=$?
if [[ $STATUS -ne 0 ]]; then
  echo "Error (exit $STATUS): $OUTPUT"
fi
```

---

## Authentication Errors

### Not Logged In

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

### Missing Scopes

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

### Token Expired

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

## GraphQL Errors

### Shell Variable Expansion

**Error:**
```
Expected VAR_SIGN, actual: UNKNOWN_CHAR ("a")
```

**Cause:** Shell expanded `$variable` in query string before sending to API.

**Detection:** Error message contains "Expected VAR_SIGN" or "UNKNOWN_CHAR".

**Recovery:** Use temp file pattern from `graphql-execution.md`:
```bash
# Write query to file (no shell expansion)
cat > /tmp/query.graphql << 'QUERY'
query($login: String!) {
  organization(login: $login) { id }
}
QUERY

# Execute with -f for query, -f/-F for variables
gh api graphql -f query="$(cat /tmp/query.graphql)" -f login="hiivmind"
rm -f /tmp/query.graphql
```

---

### Entity Not Found

**Error:**
```
Could not resolve to an Organization with the login of 'xxx'.
Could not resolve to a ProjectV2 with the number 99.
Could not resolve to a Repository with the name 'xxx'.
```

**Detection:**
```bash
if echo "$RESPONSE" | grep -q "Could not resolve to"; then
  ENTITY=$(echo "$RESPONSE" | grep -oP "Could not resolve to (an? )?\K\w+")
  echo "Not found: $ENTITY"
fi
```

**Recovery:**
- Verify entity exists and spelling is correct
- Check user has access to the entity
- For organizations: verify membership
- For projects: verify project number matches URL

---

### Type/Argument Errors

**Error:**
```
Argument 'number' on Field 'projectV2' has an invalid value (abc). Expected type 'Int!'.
Variable $first is declared as Int! but got String.
```

**Detection:**
```bash
if echo "$RESPONSE" | grep -qE "invalid value|Expected type"; then
  echo "Type error in GraphQL query"
fi
```

**Recovery:**
- Check variable types match schema
- Use `-F` for integers, `-f` for strings:
  ```bash
  gh api graphql -F number=2 -f login="hiivmind" ...
  ```

---

### Field Not Found

**Error:**
```
Field 'xxx' doesn't exist on type 'Query'
```

**Cause:** Query references field that doesn't exist in schema.

**Recovery:**
- Check corpus for correct field names
- Schema may have changed - refresh corpus

---

## REST Errors

### 404 Not Found

**Error:**
```json
{
  "message": "Not Found",
  "documentation_url": "https://docs.github.com/..."
}
```

**Common causes:**
- Resource doesn't exist
- Wrong owner/repo
- Private resource without access

**Recovery:**
```bash
# Verify resource exists
gh repo view owner/repo
gh api /repos/owner/repo/milestones
```

---

### 403 Forbidden

**Error:**
```json
{
  "message": "Must have admin rights to Repository.",
  "documentation_url": "..."
}
```
or rate limiting:
```json
{
  "message": "API rate limit exceeded for user ID xxx.",
  "documentation_url": "..."
}
```

**Detection:**
```bash
if echo "$RESPONSE" | grep -q "rate limit"; then
  echo "Rate limited"
elif echo "$RESPONSE" | grep -q "403"; then
  echo "Permission denied"
fi
```

**Recovery for permissions:**
- Check repository permissions
- Request access from owner
- Use token with appropriate access

**Recovery for rate limiting:**
```bash
# Check rate limit status
gh api /rate_limit --jq '.resources.core'

# Wait and retry
sleep 60
```

---

### 422 Unprocessable Entity

**Error:**
```json
{
  "message": "Validation Failed",
  "errors": [
    {
      "resource": "Milestone",
      "code": "already_exists",
      "field": "title"
    }
  ]
}
```

**Common causes:**
- Duplicate resource (already exists)
- Missing required field
- Invalid field value

**Detection:**
```bash
if echo "$RESPONSE" | grep -q "Validation Failed"; then
  echo "$RESPONSE" | jq -r '.errors[] | "\(.resource).\(.field): \(.code)"'
fi
```

**Recovery:**
- Check for existing resource before creating
- Verify all required fields provided
- Check field value constraints

---

## Network Errors

### Timeout

**Error:**
```
context deadline exceeded
```
or command hangs.

**Recovery:**
```bash
# Set explicit timeout
gh api --timeout 30s /repos/owner/repo

# For long operations, increase timeout
gh api --timeout 120s /repos/owner/repo/contents
```

---

### Connection Refused

**Error:**
```
dial tcp: connect: connection refused
```

**Recovery:**
- Check internet connection
- Check GitHub status: https://www.githubstatus.com/
- Try again later

---

### DNS Resolution Failed

**Error:**
```
dial tcp: lookup api.github.com: no such host
```

**Recovery:**
- Check DNS settings
- Try `ping api.github.com`
- Check if behind proxy/firewall

---

## Local/Config Errors

### Config File Not Found

**Error:**
```
Configuration file not found at .hiivmind/github/config.yaml
```

**Detection:**
```bash
if [[ ! -f ".hiivmind/github/config.yaml" ]]; then
  echo "Config not found - workspace not initialized"
fi
```

**Recovery:**
```
Run: /hiivmind-pulse-gh init
```

---

### YAML Parse Error

**Error:**
```
yaml: line 5: did not find expected key
```

**Detection:**
```bash
if ! yq '.' .hiivmind/github/config.yaml >/dev/null 2>&1; then
  echo "Config file is malformed"
fi
```

**Recovery:**
- Check for tab characters (YAML requires spaces)
- Check indentation consistency
- Validate with: `yq '.' config.yaml`

---

### Tool Not Found

**Error:**
```
yq: command not found
jq: command not found
```

**Detection:**
See `tool-detection.md` for detection patterns.

**Recovery:**
```bash
# yq installation
# macOS: brew install yq
# Linux: snap install yq

# jq installation
# macOS: brew install jq
# Linux: apt install jq
```

---

## User Communication

### Error Message Template

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
3. Try: `gh api graphql -f query='{ organization(login: "hiivmind") { projectsV2(first: 10) { nodes { number title } } } }'`
```

---

### Error Recovery Flow

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

## Examples

### Example 1: Complete GraphQL Error Handling

```bash
execute_graphql() {
  local query_file="$1"
  local response

  # Execute query
  response=$(gh api graphql -f query="$(cat "$query_file")" "${@:2}" 2>&1)
  local status=$?

  # Check command failure
  if [[ $status -ne 0 ]]; then
    echo "Error: gh api command failed"
    echo "$response"
    return 1
  fi

  # Check GraphQL errors
  if echo "$response" | jq -e '.errors' >/dev/null 2>&1; then
    local error_msg
    error_msg=$(echo "$response" | jq -r '.errors[0].message')

    # Categorize error
    if echo "$error_msg" | grep -q "Could not resolve"; then
      echo "Error: Entity not found"
      echo "Check that the resource exists and you have access."
    elif echo "$error_msg" | grep -q "Resource not accessible"; then
      echo "Error: Permission denied"
      echo "Run: gh auth refresh --scopes 'repo,read:org,project'"
    else
      echo "Error: $error_msg"
    fi
    return 1
  fi

  # Success - return data
  echo "$response" | jq '.data'
}
```

---

### Example 2: REST API with Retry

```bash
api_with_retry() {
  local endpoint="$1"
  local max_retries=3
  local retry_delay=5

  for ((i=1; i<=max_retries; i++)); do
    response=$(gh api "$endpoint" 2>&1)
    status=$?

    if [[ $status -eq 0 ]]; then
      echo "$response"
      return 0
    fi

    # Check if rate limited
    if echo "$response" | grep -q "rate limit"; then
      echo "Rate limited, waiting 60s..."
      sleep 60
      continue
    fi

    # Check if temporary error
    if echo "$response" | grep -qE "timeout|connection refused"; then
      echo "Temporary error, retry $i/$max_retries in ${retry_delay}s..."
      sleep $retry_delay
      retry_delay=$((retry_delay * 2))
      continue
    fi

    # Permanent error - don't retry
    echo "Error: $response"
    return 1
  done

  echo "Failed after $max_retries retries"
  return 1
}
```

---

## Related Patterns

- **authentication.md** - Detailed auth error handling
- **tool-detection.md** - Tool availability errors
- **config-parsing.md** - Config file errors
- **graphql-execution.md** - GraphQL-specific errors
- **v3-flow.md** - Flow-level error handling
