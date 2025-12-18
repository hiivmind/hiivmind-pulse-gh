# Pattern: Corpus Lookup

## Purpose

Look up exact API syntax from the bundled GitHub documentation corpus when you are **uncertain** about query structure, endpoint format, or parameter requirements.

## When to Use

Use corpus lookup when you have a **knowledge gap**:

- **Uncertain syntax** - Unsure of exact GraphQL mutation or query structure
- **Unfamiliar endpoints** - Don't know REST endpoint path or request body format
- **Complex operations** - Multi-step operations not covered by cached examples
- **API changes** - Behavior may have changed since last use
- **Cache miss** - ID resolution failed and need to query fresh

## When NOT to Use

Skip corpus lookup for operations where you **already know the syntax**:

- **Simple operations** - Common patterns you've used before
- **CLI shortcuts** - `gh issue create`, `gh pr merge`, etc. (well-documented)
- **Explicit examples** - Following workflow docs with exact syntax shown
- **Read-only checks** - Quick status queries that don't need precise syntax
- **Cached IDs available** - Just need to substitute values into known patterns

---

## The Lookup Flow

When you need syntax help:

```
Your Request
     ↓
┌────────────────────────────────────────────────────────────┐
│  Step 1: ROUTING DECISION                                  │
│  Read: lib/examples/operations/api-routing.md                            │
│  Output: API type (GraphQL/REST/CLI) + search keywords     │
└────────────────────────────────────────────────────────────┘
     ↓
┌────────────────────────────────────────────────────────────┐
│  Step 2: CORPUS DISCOVERY                                  │
│  Invoke: hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs          │
│  Query: Keywords from Step 1                               │
│  Output: Exact syntax (query/endpoint/command)             │
└────────────────────────────────────────────────────────────┘
     ↓
┌────────────────────────────────────────────────────────────┐
│  Step 3: EXECUTE OPERATION                                 │
│  GraphQL: Use temp file pattern (graphql-execution.md)     │
│  REST: Use gh api with endpoint                            │
│  CLI: Use gh command directly                              │
└────────────────────────────────────────────────────────────┘
     ↓
  Result
```

---

## Step 1: Routing Decision

**Read:** `lib/examples/operations/api-routing.md`

The routing guide provides:
1. **API type** - GraphQL, REST, or gh CLI
2. **Search keywords** - Terms to find in corpus

**Note:** The routing guide is useful on its own - if you know the syntax, you can skip Steps 2-3 and execute directly.

### Example Routing Lookups

| User Request | Domain | Operation | API | Keywords |
|--------------|--------|-----------|-----|----------|
| "Create a milestone" | Milestones | Create | REST | `milestones`, `POST`, `create`, `title`, `due_on` |
| "Add issue to project" | Projects v2 | Add item | GraphQL | `addProjectV2ItemById`, `mutation`, `contentId` |
| "List open PRs" | Pull Requests | List | GraphQL | `pullRequests`, `repository`, `states` |
| "Trigger workflow" | Actions | Trigger | REST | `dispatches`, `POST`, `workflow_dispatch` |

---

## Step 2: Corpus Discovery

**Invoke:** `hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs`

The corpus skill searches:
- **Index:** `data/index.md` - Keyword-tagged entries
- **GraphQL schema:** `data/uploads/graphql-schema/schema.docs.graphql`
- **REST docs:** `.source/docs/content/rest/...`
- **gh CLI docs:** `.source/docs/content/github-cli/...`

### Query the Skill

Provide the keywords from Step 1:

```
Query: "addProjectV2ItemById mutation contentId GraphQL"
```

The skill returns paths to source documentation with exact syntax.

### What You Get

| API Type | Corpus Returns |
|----------|----------------|
| GraphQL | Mutation signature, input types, return fields |
| REST | Endpoint path, HTTP method, request/response schema |
| gh CLI | Command syntax, flags, examples |

---

## Step 3: Execute Operation

Choose execution method based on API type from Step 1.

### GraphQL Execution

**Pattern:** `lib/examples/introspection/graphql-execution.md`

Use the temp file method for queries with `$variable` parameters:

```bash
# 1. Write query to temp file
cat > /tmp/query.graphql << 'QUERY'
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {
    projectId: $projectId
    contentId: $contentId
  }) {
    item { id }
  }
}
QUERY

# 2. Execute with variables
gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f projectId="PVT_xxx" \
  -f contentId="I_xxx"

# 3. Cleanup
rm -f /tmp/query.graphql
```

### REST Execution

Use `gh api` with the endpoint from corpus:

```bash
# Create milestone
gh api /repos/{owner}/{repo}/milestones \
  -f title="v2.0" \
  -f description="Version 2.0 release" \
  -f due_on="2025-06-01T00:00:00Z"

# Trigger workflow
gh api /repos/{owner}/{repo}/actions/workflows/ci.yml/dispatches \
  -f ref="main" \
  -f inputs='{"environment":"staging"}'
```

### gh CLI Execution

Use the command directly:

```bash
# Create issue
gh issue create --title "Bug: Login fails" --body "Steps to reproduce..."

# Create release
gh release create v1.0.0 --title "Version 1.0.0" --notes "Release notes..."

# List workflow runs
gh run list --workflow=ci.yml --limit=10
```

---

## Decision Tree

```
Need to execute GitHub operation
           ↓
    Do you know the exact syntax?
           │
    ┌──────┴──────┐
    │             │
   YES           NO
    │             │
    ↓             ↓
Execute       Read api-routing.md
directly      for API type + keywords
                   │
                   ↓
            Search corpus skill
                   │
                   ↓
            Get exact syntax
                   │
                   ↓
               Execute
```

---

## Complete Examples

### Example 1: Add Issue to Project (GraphQL)

**Request:** "Add issue #42 to the Feature Planner project"

**Step 1 - Routing:**
```
Read api-routing.md
→ Projects v2 → Add item → GraphQL
→ Keywords: addProjectV2ItemById, mutation, contentId
```

**Step 2 - Corpus:**
```
Invoke corpus skill with: "addProjectV2ItemById mutation"
→ Returns mutation signature and input type
```

**Step 3 - Execute:**
```bash
cat > /tmp/query.graphql << 'QUERY'
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
QUERY

gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f projectId="PVT_kwDOxxx" \
  -f contentId="I_kwDOxxx"
```

---

### Example 2: Create Milestone (REST)

**Request:** "Create a milestone for v2.0 due June 2025"

**Step 1 - Routing:**
```
Read api-routing.md
→ Milestones → Create → REST
→ Keywords: milestones, POST, create, title, due_on
```

**Step 2 - Corpus:**
```
Invoke corpus skill with: "milestones POST create"
→ Returns: POST /repos/{owner}/{repo}/milestones
→ Body: title (required), description, due_on, state
```

**Step 3 - Execute:**
```bash
gh api /repos/hiivmind/hiivmind-pulse-gh/milestones \
  -f title="v2.0" \
  -f description="Version 2.0 release" \
  -f due_on="2025-06-01T00:00:00Z"
```

---

### Example 3: Trigger Workflow (REST)

**Request:** "Run the CI workflow on main branch"

**Step 1 - Routing:**
```
Read api-routing.md
→ Actions → Trigger → REST
→ Keywords: dispatches, POST, workflow_dispatch, inputs
```

**Step 2 - Corpus:**
```
Invoke corpus skill with: "workflow dispatches POST"
→ Returns: POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
→ Body: ref (required), inputs (optional)
```

**Step 3 - Execute:**
```bash
gh api /repos/hiivmind/hiivmind-pulse-gh/actions/workflows/ci.yml/dispatches \
  -f ref="main"
```

---

### Example 4: Skip Corpus - Known Syntax

**Request:** "Create an issue for the login bug"

**Decision:** You know `gh issue create` syntax already.

**Execute directly:**
```bash
gh issue create \
  --title "Bug: Login fails with SSO" \
  --body "When using SSO, login redirects to blank page" \
  --label "bug"
```

No corpus lookup needed for well-known CLI commands.

---

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| "Not found in routing" | Operation not in api-routing.md | Search corpus directly with descriptive keywords |
| "No corpus results" | Keywords too specific | Broaden search terms, check index sections |
| "GraphQL syntax error" | Shell escaping issue | Use temp file method (graphql-execution.md) |
| "REST 404" | Wrong endpoint or missing resource | Verify owner/repo, check resource exists |
| "Permission denied" | Missing scopes | Run `gh auth refresh --scopes '...'` |

---

## Related Patterns

- **graphql-execution.md** - Temp file method for GraphQL queries
- **tool-detection.md** - Verify gh CLI available
- **authentication.md** - Check scopes before operations
- **config-parsing.md** - Load cached IDs from config.yaml

## Related References

- **lib/examples/operations/api-routing.md** - Routing decisions and keywords (useful standalone)
- **docs/config-schema.md** - Config.yaml structure for cached IDs
- **hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs** - GitHub API corpus skill
