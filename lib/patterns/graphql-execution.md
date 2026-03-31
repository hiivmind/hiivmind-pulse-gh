# Pattern: GraphQL Execution

## Purpose

Execute GraphQL queries via gh CLI without shell escaping issues.

## When to Use

- Executing queries with `$variable` parameters
- Queries discovered from corpus schema
- Any GraphQL mutation or parameterized query

## Prerequisites

- **tool-detection.md** - gh CLI must be available
- **authentication.md** - Must be authenticated with required scopes

## The Problem

GraphQL queries use `$variable` syntax that conflicts with bash variable expansion:

```bash
# FAILS - shell tries to expand $login
gh api graphql -f query='query($login: String!) { organization(login: $login) { id } }'
# Error: Expected VAR_SIGN, actual: UNKNOWN_CHAR
```

This happens because the shell interprets `$login` as a shell variable before passing it to gh.

---

## Method 1: Temp File (Queries with Variables)

The most reliable method for queries with `$variable` parameters.

### Step 1: Write Query to Temp File

Use the **Write tool** to create the query file. This avoids shell expansion issues entirely
and keeps the file creation separate from the `gh api` call.

**Write tool** → `/tmp/query.graphql`:

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

**Key:** Using the Write tool instead of a Bash heredoc means:
- No shell expansion issues (`$variable` stays literal)
- File creation is handled cleanly without shell involvement
- The query file is ready for the next step

### Step 2: Execute with File Read

Use a **separate Bash call** to execute the query:

```bash
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f login="hiivmind"
```

**Why two separate tool calls:**
1. Write tool handles file creation without shell expansion issues
2. `gh api` call cleanly matches `Bash(gh:*)` allowlist
3. A compound `cat > file && gh api` command matches neither rule

### Step 3: Cleanup (Optional)

```bash
rm -f /tmp/query.graphql
```

For scripts, use a unique temp file name (e.g. `/tmp/query-{unique-id}.graphql`) and write it
with the Write tool before executing with a separate Bash call.

---

## Method 2: Direct Queries (No Variables)

Queries without `$variable` parameters work directly:

```bash
# WORKS - no $ variables in query
gh api graphql -f query='{ viewer { login id } }' --jq '.data.viewer'
```

**Output:**
```json
{"login": "username", "id": "MDQ6VXNlcjEyMzQ1"}
```

### When to Use Direct Queries

- Viewer queries (authenticated user info)
- Queries with hardcoded values
- Simple schema introspection

---

## Variable Passing

### Flag Types

| GraphQL Type | gh Flag | Example |
|--------------|---------|---------|
| `String!` | `-f` | `-f login="hiivmind"` |
| `Int!` | `-F` | `-F number=2` |
| `Boolean` | `-F` | `-F includeArchived=true` |
| `ID!` | `-f` | `-f projectId="PVT_xxx"` |

**Rule:** Use `-f` for strings, `-F` for numbers and booleans.

### Multiple Variables

```bash
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f login="hiivmind" \
  -F number=2 \
  -F includeArchived=false
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Expected VAR_SIGN, actual: UNKNOWN_CHAR` | Shell expanded `$` in query | Use temp file method |
| `Could not resolve to an Organization` | Wrong login or no access | Check spelling, verify membership |
| `Resource not accessible by integration` | Missing scopes | Run `gh auth refresh --scopes '...'` |
| `Could not resolve to a ProjectV2` | Wrong project number | Verify project exists and is accessible |

### Checking for GraphQL Errors

```bash
RESPONSE=$(gh api graphql -f query="$(cat /tmp/query.graphql)" -f login="$OWNER" 2>&1)

if echo "$RESPONSE" | jq -e '.errors' >/dev/null 2>&1; then
  echo "GraphQL Error:"
  echo "$RESPONSE" | jq -r '.errors[].message'
  exit 1
fi

# Process successful response
echo "$RESPONSE" | jq '.data'
```

---

## Examples

### Example 1: List Organization Projects

**Goal:** Get all projects for an organization.

**Write tool** → `/tmp/query.graphql`:

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
      }
    }
  }
}
```

**Execute:**
```bash
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f login="hiivmind" \
  | jq '.data.organization.projectsV2.nodes'
```

**Output:**
```json
[
  {"number": 2, "title": "Feature Planner", "closed": false, "id": "PVT_xxx"},
  {"number": 3, "title": "Bug Tracker", "closed": false, "id": "PVT_yyy"}
]
```

---

### Example 2: Add Issue to Project

**Goal:** Add an existing issue to a project.

**Write tool** → `/tmp/query.graphql`:

```graphql
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {
    projectId: $projectId
    contentId: $contentId
  }) {
    item {
      id
    }
  }
}
```

**Execute:**
```bash
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f projectId="PVT_kwDODUFJxM4A..." \
  -f contentId="I_kwDODUFJxM6..."
```

**Output:**
```json
{
  "data": {
    "addProjectV2ItemById": {
      "item": {
        "id": "PVTI_..."
      }
    }
  }
}
```

---

### Example 3: Get Viewer (Direct Query)

**Goal:** Get authenticated user info (no variables needed).

**Execute directly:**
```bash
gh api graphql -f query='{ viewer { login id name email } }' --jq '.data.viewer'
```

**Output:**
```json
{"login": "username", "id": "MDQ6VXNlcjEyMzQ1", "name": "User Name", "email": "user@example.com"}
```

---

## Integration with v3 Flow

This pattern is Step 3 of the v3 architecture flow:

```
1. api-routing.md     → Decide: GraphQL, REST, or gh CLI
2. Corpus Discovery   → Get exact query syntax from schema
3. graphql-execution  → Execute query with temp file method (this pattern)
```

For corpus discovery, see:
- `graphql-queries.md` - Query syntax reference
- External corpus: `hiivmind-corpus-github-docs-navigate` - Full schema and API docs

---

## Cross-Platform Notes

| Aspect | Notes |
|--------|-------|
| Write query file | Use the **Write tool** — platform-agnostic, no shell involvement |
| Execute query | Bash: `gh api graphql -f query="$(cat /tmp/query.graphql)"` |
| Windows (PowerShell) | Write tool still works; Bash step becomes `$(Get-Content file -Raw)` |

---

## Related Patterns

- **tool-detection.md** - Verify gh CLI available
- **authentication.md** - Ensure required scopes
- **graphql-queries.md** - Query syntax and schema reference
- **config-parsing.md** - Get cached IDs for variables
