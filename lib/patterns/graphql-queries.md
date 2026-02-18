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

## Critical: Shell Escaping Issues

**Problem:** GraphQL queries use `$variable` syntax that conflicts with bash variable expansion in different ways depending on shell context.

```bash
# FAILS in most contexts - shell tries to expand $login
gh api graphql -f query='query($login: String!) { organization(login: $login) { id } }'
# Error: Expected VAR_SIGN, actual: UNKNOWN_CHAR
```

### Solution: Temp File Method

**See:** `graphql-execution.md` for the complete execution pattern.

The recommended solution is to write queries to a temp file and execute via `cat` substitution:

```bash
# 1. Write query to temp file (single-quoted HEREDOC delimiter)
cat > /tmp/query.graphql << 'QUERY'
query($login: String!) {
  organization(login: $login) { id }
}
QUERY

# 2. Execute with file read
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f login="hiivmind"
```

### What Works Directly

Queries **without** `$variable` parameters work inline:

```bash
gh api graphql -f query='{ viewer { login id } }' --jq '.data.viewer'
```

---

## Variable Types

| GraphQL Type | gh Flag | Example |
|--------------|---------|---------|
| `String!` | `-f` | `-f login="hiivmind"` |
| `Int!` | `-F` | `-F number=2` |
| `Boolean` | `-F` | `-F includeArchived=true` |
| `ID!` | `-f` | `-f projectId="PVT_xxx"` |

**Rule:** Use `-f` for strings and IDs (values passed as-is), `-F` for numbers and booleans (values parsed by gh).

---

## Project Discovery Queries

**Note:** These are reference queries. Due to shell escaping issues, store them in YAML files and execute via functions (see "Critical: Shell Escaping Issues" above).

### List Organization Projects

**Query (for YAML file):**
```graphql
query($login: String!) {
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
}
```

**Variables:** `login` (String!) - organization login

**Expected Output:**
```json
[
  {"number": 2, "title": "Feature Planner", "closed": false, "id": "PVT_xxx", "url": "https://..."},
  {"number": 3, "title": "Bug Tracker", "closed": false, "id": "PVT_yyy", "url": "https://..."}
]
```

---

### List User Projects

**Query (for YAML file):**
```graphql
query($login: String!) {
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
}
```

**Variables:** `login` (String!) - user login

---

### Get Project with Fields

**Query (for YAML file):**
```graphql
query($login: String!, $number: Int!) {
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
}
```

**Variables:** `login` (String!), `number` (Int!) - organization login and project number

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

**Query (for YAML file):**
```graphql
query($login: String!) {
  organization(login: $login) {
    id
    name
    login
  }
}
```

**Variables:** `login` (String!) - organization login

---

### Get User ID

**Query (for YAML file):**
```graphql
query($login: String!) {
  user(login: $login) {
    id
    name
    login
  }
}
```

**Variables:** `login` (String!) - user login

---

## jq Parsing Patterns

**Important:** Pipe to `jq` separately rather than using `--jq` inline. This avoids escaping conflicts.

### Extract Project Numbers

```bash
| jq '.data.organization.projectsV2.nodes[].number'
```

### Extract Open Projects Only

```bash
| jq '.data.organization.projectsV2.nodes | map(select(.closed == false))'
```

### Format as "number: title"

```bash
| jq -r '.data.organization.projectsV2.nodes[] | "\(.number): \(.title)"'
```

### Extract Single Select Field Options

```bash
| jq '.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .options'
```

### Get Field ID by Name

```bash
| jq -r '.data.organization.projectV2.fields.nodes[] | select(.name == "Status") | .id'
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Expected VAR_SIGN, actual: UNKNOWN_CHAR` | Shell expanding `$` in query | Use multiline format with `-F` flag |
| `Could not resolve to an Organization` | Wrong login or no access | Check spelling, verify membership |
| `Resource not accessible by integration` | Missing scopes | Run `gh auth refresh --scopes '...'` |
| `Could not resolve to a ProjectV2` | Wrong project number | Verify project exists and is accessible |

### Check for Errors in Response

```bash
RESPONSE=$(gh api graphql -F login="$OWNER" -f query='
query($login: String!) {
  organization(login: $login) { id }
}
' 2>&1)

if echo "$RESPONSE" | jq -e '.errors' >/dev/null 2>&1; then
  echo "GraphQL Error:"
  echo "$RESPONSE" | jq '.errors[].message'
  exit 1
fi
```

---

## Complete Example: Discover and Cache Projects

**See:** `graphql-execution.md` for the temp file execution method.

```bash
#!/bin/bash
# Discover projects for an organization

OWNER="$1"

# Write query to temp file
cat > /tmp/query.graphql << 'QUERY'
query($login: String!) {
  organization(login: $login) {
    id
    projectsV2(first: 20) {
      nodes { number title closed id url }
    }
  }
}
QUERY

# Execute and extract projects
RESULT=$(gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f login="$OWNER")

# Extract data
WORKSPACE_ID=$(echo "$RESULT" | jq -r '.data.organization.id')
PROJECTS=$(echo "$RESULT" | jq '.data.organization.projectsV2.nodes')

echo "Workspace ID: $WORKSPACE_ID"
echo "Projects:"
echo "$PROJECTS" | jq -r '.[] | "  \(.number): \(.title) [\(if .closed then "closed" else "open" end)]"'

# Cleanup
rm -f /tmp/query.graphql
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

- **graphql-execution.md** - Execute queries with temp file method (solves escaping)
- **tool-detection.md** - Verify gh CLI available
- **authentication.md** - Ensure required scopes
- **config-parsing.md** - Store discovered IDs in config
- **workspace-detection.md** - Determine org vs user for query selection
