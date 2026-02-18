# Pattern: GraphQL Errors

## Purpose

Detect and recover from GraphQL-specific API errors.

## When to Use

- After GraphQL queries return errors in the response
- When query syntax or variable types are wrong
- When entities cannot be resolved

**Parent:** See `error-handling.md` for the error detection overview and recovery flow.

---

## Error Detection

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

---

## Shell Variable Expansion

**Error:**
```
Expected VAR_SIGN, actual: UNKNOWN_CHAR ("a")
```

**Cause:** Shell expanded `$variable` in query string before sending to API.

**Recovery:** Use temp file pattern from `graphql-execution.md`:
```bash
cat > /tmp/query.graphql << 'QUERY'
query($login: String!) {
  organization(login: $login) { id }
}
QUERY

gh api graphql -f query="$(cat /tmp/query.graphql)" -f login="hiivmind"
rm -f /tmp/query.graphql
```

---

## Entity Not Found

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

## Type/Argument Errors

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
- Use `-f` for strings/IDs, `-F` for numbers/booleans:
  ```bash
  gh api graphql -F number=2 -f login="hiivmind" ...
  ```

---

## Field Not Found

**Error:**
```
Field 'xxx' doesn't exist on type 'Query'
```

**Cause:** Query references field that doesn't exist in schema.

**Recovery:**
- Check corpus for correct field names
- Schema may have changed - refresh corpus

---

## Complete GraphQL Error Handling Example

```bash
execute_graphql() {
  local query_file="$1"
  local response

  response=$(gh api graphql -f query="$(cat "$query_file")" "${@:2}" 2>&1)
  local status=$?

  if [[ $status -ne 0 ]]; then
    echo "Error: gh api command failed"
    echo "$response"
    return 1
  fi

  if echo "$response" | jq -e '.errors' >/dev/null 2>&1; then
    local error_msg
    error_msg=$(echo "$response" | jq -r '.errors[0].message')

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

  echo "$response" | jq '.data'
}
```

---

## Related Patterns

- **graphql-execution.md** - Query execution with temp file method
- **error-handling.md** - Error detection overview and recovery flow
- **error-auth.md** - Authentication/permission errors
