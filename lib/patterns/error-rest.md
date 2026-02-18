# Pattern: REST & Network Errors

## Purpose

Detect and recover from REST API and network-level errors.

## When to Use

- After REST API calls return non-2xx status codes
- When network connectivity issues occur
- When rate limits are hit

**Parent:** See `error-handling.md` for the error detection overview and recovery flow.

---

## REST Error Detection

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

---

## 404 Not Found

**Error:**
```json
{"message": "Not Found", "documentation_url": "https://docs.github.com/..."}
```

**Common causes:** Resource doesn't exist, wrong owner/repo, private resource without access.

**Recovery:**
```bash
gh repo view owner/repo
gh api /repos/owner/repo/milestones
```

---

## 403 Forbidden

**Error (permissions):**
```json
{"message": "Must have admin rights to Repository."}
```

**Error (rate limit):**
```json
{"message": "API rate limit exceeded for user ID xxx."}
```

**Detection:**
```bash
if echo "$RESPONSE" | grep -q "rate limit"; then
  echo "Rate limited"
elif echo "$RESPONSE" | grep -q "403"; then
  echo "Permission denied"
fi
```

**Recovery for rate limiting:**
```bash
gh api /rate_limit --jq '.resources.core'
sleep 60
```

---

## 422 Unprocessable Entity

**Error:**
```json
{
  "message": "Validation Failed",
  "errors": [{"resource": "Milestone", "code": "already_exists", "field": "title"}]
}
```

**Common causes:** Duplicate resource, missing required field, invalid field value.

**Detection:**
```bash
if echo "$RESPONSE" | grep -q "Validation Failed"; then
  echo "$RESPONSE" | jq -r '.errors[] | "\(.resource).\(.field): \(.code)"'
fi
```

---

## Network Errors

### Timeout

**Error:** `context deadline exceeded`

**Recovery:**
```bash
gh api --timeout 30s /repos/owner/repo
```

### Connection Refused

**Error:** `dial tcp: connect: connection refused`

**Recovery:** Check internet connection, check https://www.githubstatus.com/

### DNS Resolution Failed

**Error:** `dial tcp: lookup api.github.com: no such host`

**Recovery:** Check DNS settings, try `ping api.github.com`

---

## REST API with Retry Example

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

    if echo "$response" | grep -q "rate limit"; then
      echo "Rate limited, waiting 60s..."
      sleep 60
      continue
    fi

    if echo "$response" | grep -qE "timeout|connection refused"; then
      echo "Temporary error, retry $i/$max_retries in ${retry_delay}s..."
      sleep $retry_delay
      retry_delay=$((retry_delay * 2))
      continue
    fi

    echo "Error: $response"
    return 1
  done

  echo "Failed after $max_retries retries"
  return 1
}
```

---

## Related Patterns

- **error-handling.md** - Error detection overview and recovery flow
- **error-auth.md** - Authentication errors (401/403 permission)
