# Pattern: GraphQL Queries

## Purpose

Tested GraphQL query patterns for GitHub project discovery and workspace initialization.

## When to Use

- Discovering projects in an organization or user account
- Fetching project field configurations and options
- Getting organization/user IDs for GraphQL mutations
- Querying the authenticated user (viewer)

## Prerequisites

- **tool-detection.md** - gh CLI must be available
- **authentication.md** - Must be authenticated with required scopes

## Critical: The Variable Pattern

**Problem:** GraphQL queries use `$variable` syntax that conflicts with bash variable expansion.

```bash
# FAILS - bash tries to expand $login as a shell variable
gh api graphql -f query='query($login: String!) { organization(login: $login) { id } }'
# Error: Expected VAR_SIGN, actual: UNKNOWN_CHAR
```

**Solution:** Store the query in a bash variable first, then pass it with double quotes.

```bash
# WORKS - query stored in variable, passed with double quotes
QUERY='query($login: String!) { organization(login: $login) { id } }'
gh api graphql -f login="myorg" -f query="$QUERY"
```

**Why this works:**
1. Single quotes around `QUERY='...'` prevent bash from expanding `$login`
2. Double quotes around `-f query="$QUERY"` expand `$QUERY` but the query string itself is now a literal

---

## Variable Types

| GraphQL Type | gh Flag | Example |
|--------------|---------|---------|
| `String!` | `-f` | `-f login="hiivmind"` |
| `Int!` | `-F` | `-F number=2` |
| `Boolean` | `-F` | `-F includeArchived=true` |
| `ID!` | `-f` | `-f projectId="PVT_xxx"` |

**Important:** Use `-f` for strings, `-F` for numbers and booleans.

---

## Project Discovery Queries

### List Organization Projects

```bash
QUERY='query($login: String!) {
  organization(login: $login) {
    id
    projectsV2(first: 20) {
      nodes {
        number
        title
        closed
        id
        url
      }
    }
  }
}'

gh api graphql -f login="$OWNER" -f query="$QUERY" \
  --jq '.data.organization.projectsV2.nodes'
```

**Output:**
```json
[
  {"number": 2, "title": "Feature Planner", "closed": false, "id": "PVT_xxx", "url": "https://..."},
  {"number": 3, "title": "Bug Tracker", "closed": false, "id": "PVT_yyy", "url": "https://..."}
]
```

---

### List User Projects

```bash
QUERY='query($login: String!) {
  user(login: $login) {
    id
    projectsV2(first: 20) {
      nodes {
        number
        title
        closed
        id
        url
      }
    }
  }
}'

gh api graphql -f login="$OWNER" -f query="$QUERY" \
  --jq '.data.user.projectsV2.nodes'
```

---

### Get Project with Fields

```bash
QUERY='query($login: String!, $number: Int!) {
  organization(login: $login) {
    projectV2(number: $number) {
      id
      title
      url
      fields(first: 50) {
        nodes {
          ... on ProjectV2Field {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
          ... on ProjectV2IterationField {
            id
            name
          }
        }
      }
    }
  }
}'

gh api graphql -f login="$OWNER" -F number="$PROJECT_NUM" -f query="$QUERY" \
  --jq '.data.organization.projectV2'
```

**Output:**
```json
{
  "id": "PVT_xxx",
  "title": "Feature Planner",
  "url": "https://github.com/orgs/myorg/projects/2",
  "fields": {
    "nodes": [
      {"id": "PVTF_xxx", "name": "Title"},
      {"id": "PVTF_yyy", "name": "Assignees"},
      {"id": "PVTSSF_zzz", "name": "Status", "options": [
        {"id": "abc123", "name": "Backlog"},
        {"id": "def456", "name": "In Progress"},
        {"id": "ghi789", "name": "Done"}
      ]}
    ]
  }
}
```

---

### Get User Project with Fields

Same as above but use `user(login: $login)` instead of `organization(login: $login)`.

---

## Identity Queries

### Get Authenticated User (Viewer)

```bash
gh api graphql -f query='{ viewer { login id name email } }' \
  --jq '.data.viewer'
```

**Note:** No variables needed, so single quotes work directly.

**Output:**
```json
{"login": "myuser", "id": "MDQ6VXNlcjEyMzQ1", "name": "My Name", "email": "me@example.com"}
```

---

### Get Organization ID

```bash
QUERY='query($login: String!) {
  organization(login: $login) {
    id
    name
    login
  }
}'

gh api graphql -f login="$OWNER" -f query="$QUERY" \
  --jq '.data.organization.id'
```

---

### Get User ID

```bash
QUERY='query($login: String!) {
  user(login: $login) {
    id
    name
    login
  }
}'

gh api graphql -f login="$OWNER" -f query="$QUERY" \
  --jq '.data.user.id'
```

---

## jq Parsing Patterns

### Extract Project Numbers

```bash
--jq '.data.organization.projectsV2.nodes[].number'
```

### Extract Open Projects Only

```bash
--jq '.data.organization.projectsV2.nodes | map(select(.closed == false))'
```

### Format as "number: title"

```bash
--jq '.data.organization.projectsV2.nodes[] | "\(.number): \(.title)"'
```

### Extract Single Select Field Options

```bash
--jq '.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .options'
```

### Get Field ID by Name

```bash
--jq '.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .id'
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Expected VAR_SIGN, actual: UNKNOWN_CHAR` | Shell expanding `$` in query | Use variable pattern (see above) |
| `Could not resolve to an Organization` | Wrong login or no access | Check spelling, verify membership |
| `Resource not accessible by integration` | Missing scopes | Run `gh auth refresh --scopes '...'` |
| `Could not resolve to a ProjectV2` | Wrong project number | Verify project exists and is accessible |

### Check for Errors in Response

```bash
RESPONSE=$(gh api graphql -f login="$OWNER" -f query="$QUERY" 2>&1)

if echo "$RESPONSE" | jq -e '.errors' >/dev/null 2>&1; then
  echo "GraphQL Error:"
  echo "$RESPONSE" | jq '.errors[].message'
  exit 1
fi
```

---

## Complete Example: Discover and Cache Projects

```bash
#!/bin/bash
set -e

OWNER="$1"
TYPE="$2"  # "organization" or "user"

# Build query based on type
if [[ "$TYPE" == "organization" ]]; then
  QUERY='query($login: String!) {
    organization(login: $login) {
      id
      projectsV2(first: 20) {
        nodes { number title closed id url }
      }
    }
  }'
  JQ_PATH=".data.organization"
else
  QUERY='query($login: String!) {
    user(login: $login) {
      id
      projectsV2(first: 20) {
        nodes { number title closed id url }
      }
    }
  }'
  JQ_PATH=".data.user"
fi

# Execute query
RESULT=$(gh api graphql -f login="$OWNER" -f query="$QUERY")

# Extract data
WORKSPACE_ID=$(echo "$RESULT" | jq -r "$JQ_PATH.id")
PROJECTS=$(echo "$RESULT" | jq "$JQ_PATH.projectsV2.nodes")

echo "Workspace ID: $WORKSPACE_ID"
echo "Projects:"
echo "$PROJECTS" | jq -r '.[] | "  \(.number): \(.title) [\(if .closed then "closed" else "open" end)]"'
```

---

## Cross-Platform Notes

| Aspect | Unix | Windows (PowerShell) |
|--------|------|---------------------|
| Variable assignment | `QUERY='...'` | `$QUERY = '...'` |
| Variable expansion | `"$QUERY"` | `"$QUERY"` |
| jq availability | Usually installed | May need manual install |

---

## Related Patterns

- **tool-detection.md** - Verify gh CLI available
- **authentication.md** - Ensure required scopes
- **config-parsing.md** - Store discovered IDs in config
- **workspace-detection.md** - Determine org vs user for query selection
