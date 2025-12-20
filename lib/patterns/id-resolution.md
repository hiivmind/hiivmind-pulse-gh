# Pattern: ID Resolution

## Purpose

Resolve user-friendly names and numbers to GraphQL/REST IDs using cache-first strategy with API fallback.

## When to Use

- Before any GitHub API operation requiring entity IDs
- When user specifies entities by name/number instead of ID
- Resolving: projects, fields, options, issues, PRs, milestones

## Prerequisites

- **config-parsing.md** - For cached ID extraction
- **corpus-lookup.md** - For API fallback when cache misses
- Config exists at `.hiivmind/github/config.yaml`

---

## Resolution Strategy

```
User Input (name/number)
        ↓
┌───────────────────┐
│ 1. CHECK CACHE    │  ← config-parsing.md patterns
│    Found?         │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │ Yes       │ No
    ↓           ↓
  Return    ┌───────────────────┐
  ID        │ 2. CORPUS LOOKUP │  ← corpus-lookup.md
            │    Query GitHub   │
            └─────────┬─────────┘
                      │
            ┌─────────┴─────────┐
            │ 3. OPTIONALLY     │
            │    Cache result   │  ← config-parsing.md write
            └─────────┬─────────┘
                      ↓
                  Return ID
```

---

## Entity Resolution Reference

| Entity | Lookup Key | Cached? | Cache Path | Fallback |
|--------|-----------|---------|------------|----------|
| Project | Number | Yes | `.projects.catalog[].number` → `.id` | corpus lookup: projectsV2 |
| Field | Name + Project | Yes | `.fields[].name` → `.id` | corpus lookup: projectV2.fields |
| Option | Name + Field | Yes | `.options[].name` → `.id` | corpus lookup: field.options |
| Issue | Number | No | — | corpus lookup: repository.issue |
| PR | Number | No | — | corpus lookup: repository.pullRequest |
| Milestone | Title or Number | Partial | `.milestones[repo][]` | REST: /milestones |

---

## Resolution Patterns

### Project ID by Number

Projects are cached during init. Resolve by project number (from URL).

**Using yq (preferred):**
```bash
CONFIG=".hiivmind/github/config.yaml"
PROJECT_NUM=2

# Try cache first
PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .id" "$CONFIG")

if [[ -n "$PROJECT_ID" && "$PROJECT_ID" != "null" ]]; then
  echo "Resolved from cache: $PROJECT_ID"
else
  echo "Not in cache - use corpus lookup fallback"
  # See: lib/patterns/corpus-lookup.md
  # routing: Projects → List → GraphQL
  # keywords: projectsV2, organization/user
fi
```

**Using Python:**
```bash
python3 -c "
import yaml
config = yaml.safe_load(open('.hiivmind/github/config.yaml'))
projects = config.get('projects', {}).get('catalog', [])
project = next((p for p in projects if p.get('number') == 2), None)
print(project.get('id', '') if project else '')
"
```

---

### Field ID by Name

Fields are stored as a dictionary keyed by field name under each project.

**Config structure:**
```yaml
projects:
  catalog:
    - number: 2
      fields:
        Status:           # Field name is the key
          id: PVTSSF_xxx  # Field ID
          type: single_select
          options:
            In progress: 47fc9ee4
```

**Using yq (preferred):**
```bash
CONFIG=".hiivmind/github/config.yaml"
PROJECT_NUM=2
FIELD_NAME="Status"

# Resolve field ID from cache (fields are keyed by name)
FIELD_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields[\"$FIELD_NAME\"].id" "$CONFIG")

if [[ -n "$FIELD_ID" && "$FIELD_ID" != "null" ]]; then
  echo "Resolved from cache: $FIELD_ID"
else
  echo "Not in cache - use corpus lookup fallback"
  # See: lib/patterns/corpus-lookup.md
  # routing: Projects → Fields → GraphQL
  # keywords: projectV2, fields, SingleSelectField
fi
```

**Using Python:**
```bash
python3 -c "
import yaml
config = yaml.safe_load(open('.hiivmind/github/config.yaml'))
projects = config.get('projects', {}).get('catalog', [])
project = next((p for p in projects if p.get('number') == 2), {})
fields = project.get('fields', {})
field = fields.get('Status', {})
print(field.get('id', ''))
"
```

**Note:** Grep fallback is impractical for nested field lookups due to YAML structure.

---

### Option ID by Name

Options are stored as a dictionary keyed by option name under each field.

**Config structure:**
```yaml
fields:
  Status:
    options:
      In progress: 47fc9ee4  # Option name: option ID
      Done: "98236657"
```

**Using yq (preferred):**
```bash
CONFIG=".hiivmind/github/config.yaml"
PROJECT_NUM=2
FIELD_NAME="Status"
OPTION_NAME="In progress"

# Resolve option ID from cache (options are keyed by name, value is the ID)
OPTION_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields[\"$FIELD_NAME\"].options[\"$OPTION_NAME\"]" "$CONFIG")

if [[ -n "$OPTION_ID" && "$OPTION_ID" != "null" ]]; then
  echo "Resolved from cache: $OPTION_ID"
else
  echo "Not in cache - use corpus lookup fallback"
  # See: lib/patterns/corpus-lookup.md
  # routing: Projects → Fields → GraphQL
  # keywords: SingleSelectField, options
fi
```

**Using Python:**
```bash
python3 -c "
import yaml
config = yaml.safe_load(open('.hiivmind/github/config.yaml'))
projects = config.get('projects', {}).get('catalog', [])
project = next((p for p in projects if p.get('number') == 2), {})
fields = project.get('fields', {})
field = fields.get('Status', {})
options = field.get('options', {})
print(options.get('In progress', ''))
"
```

---

### Issue/PR Node ID

Issues and PRs are **not cached** - always use corpus lookup to query GitHub.

**Why not cached:** Issues/PRs are too numerous and change frequently. Caching would be stale immediately.

**Resolution via v3 Flow:**

```bash
OWNER="hiivmind"
REPO="hiivmind-pulse-gh"
ISSUE_NUM=42

# 1. Read routing guide: Issues → Read → GraphQL
# 2. Search corpus for: repository.issue node_id
# 3. Execute query:

cat > /tmp/query.graphql << 'QUERY'
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      id
      title
    }
  }
}
QUERY

gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f owner="$OWNER" \
  -f repo="$REPO" \
  -F number="$ISSUE_NUM" \
  --jq '.data.repository.issue.id'

rm -f /tmp/query.graphql
```

**For Pull Requests:** Replace `issue(number:)` with `pullRequest(number:)`.

---

### Milestone ID

Milestones may be cached if workspace includes milestone data, otherwise use REST fallback.

**Check cache first (using yq):**
```bash
CONFIG=".hiivmind/github/config.yaml"
REPO="hiivmind-pulse-gh"
MILESTONE_TITLE="v5.0.0"

# Try cache
MILESTONE_ID=$(yq ".milestones[\"$REPO\"][] | select(.title == \"$MILESTONE_TITLE\") | .id // .node_id" "$CONFIG" 2>/dev/null)

if [[ -n "$MILESTONE_ID" && "$MILESTONE_ID" != "null" ]]; then
  echo "Resolved from cache: $MILESTONE_ID"
else
  echo "Not in cache - using REST fallback"
fi
```

**REST fallback (always works):**
```bash
OWNER="hiivmind"
REPO="hiivmind-pulse-gh"
MILESTONE_TITLE="v5.0.0"

# List milestones and find by title
gh api "/repos/$OWNER/$REPO/milestones" --jq ".[] | select(.title == \"$MILESTONE_TITLE\") | .node_id"
```

**Get milestone by number:**
```bash
MILESTONE_NUM=7
gh api "/repos/$OWNER/$REPO/milestones/$MILESTONE_NUM" --jq '.node_id'
```

---

## Fallback Strategy

When cache lookup fails, use corpus lookup:

```
Cache Miss
    ↓
┌─────────────────────────────────────────────────────────┐
│ 1. Read routing guide (lib/references/api-routing.md)        │
│    → Determine: GraphQL vs REST                         │
│    → Get search keywords                                │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Search corpus                                        │
│    → Invoke: hiivmind-corpus-github-docs-navigate       │
│    → Query with keywords from step 1                    │
│    → Get exact syntax (query/mutation/endpoint)         │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Execute query                                        │
│    → GraphQL: temp file pattern (graphql-execution.md)  │
│    → REST: gh api endpoint                              │
└────────────────────────┬────────────────────────────────┘
                         ↓
                    Return ID
```

**See:** `lib/patterns/corpus-lookup.md` for complete flow documentation.

---

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| Empty result from cache | Entity not cached | Use corpus lookup fallback |
| `null` returned | Key exists but value is null | Use corpus lookup fallback |
| "yq: command not found" | yq not installed | Fall back to Python |
| No match in cache | Name/number typo | List available entities, ask user |
| Multiple matches | Ambiguous name | Present options, ask user to clarify |
| API 404 | Entity doesn't exist on GitHub | Inform user, suggest alternatives |

### Handling Ambiguous Names

If field name exists in multiple projects:

```bash
# List all projects with this field
echo "Field '$FIELD_NAME' found in projects:"
yq ".projects.catalog[] | select(.fields[\"$FIELD_NAME\"]) | {project: .number, title: .title}" "$CONFIG"

# Ask user to specify project number
echo "Please specify project number."
```

---

## Examples

### Example 1: Set Issue Status in Project

**User request:** "Set issue #42 to 'In progress' in project 2"

**Resolution needed:**
1. Project ID (from number 2)
2. Status field ID (from name "Status")
3. Option ID (from name "In progress")
4. Issue node ID (from number 42)

```bash
CONFIG=".hiivmind/github/config.yaml"
PROJECT_NUM=2
FIELD_NAME="Status"
OPTION_NAME="In progress"
ISSUE_NUM=42

# 1. Resolve Project ID (cached)
PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .id" "$CONFIG")

# 2. Resolve Field ID (cached - fields keyed by name)
FIELD_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields[\"$FIELD_NAME\"].id" "$CONFIG")

# 3. Resolve Option ID (cached - options keyed by name, value is ID)
OPTION_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields[\"$FIELD_NAME\"].options[\"$OPTION_NAME\"]" "$CONFIG")

# 4. Resolve Issue Node ID (not cached - query GitHub)
OWNER=$(yq '.workspace.login' "$CONFIG")
REPO=$(yq '.repositories[0].name' "$CONFIG")

cat > /tmp/query.graphql << 'QUERY'
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) { id }
  }
}
QUERY
ISSUE_ID=$(gh api graphql -f query="$(cat /tmp/query.graphql)" -f owner="$OWNER" -f repo="$REPO" -F number="$ISSUE_NUM" --jq '.data.repository.issue.id')
rm -f /tmp/query.graphql

echo "Resolved IDs:"
echo "  Project: $PROJECT_ID"
echo "  Field: $FIELD_ID"
echo "  Option: $OPTION_ID"
echo "  Issue: $ISSUE_ID"
```

---

### Example 2: Add Issue to Project

**User request:** "Add issue #15 to project 2"

**Resolution needed:**
1. Project ID (from number 2)
2. Issue node ID (from number 15)

```bash
CONFIG=".hiivmind/github/config.yaml"

# 1. Project ID (cached)
PROJECT_ID=$(yq '.projects.catalog[] | select(.number == 2) | .id' "$CONFIG")

# 2. Issue ID (corpus lookup - not cached)
# See Issue/PR Node ID section above
```

---

### Example 3: List Available Options

**User request:** "What status options are available in project 2?"

```bash
CONFIG=".hiivmind/github/config.yaml"
PROJECT_NUM=2
FIELD_NAME="Status"

echo "Available options for $FIELD_NAME field in project $PROJECT_NUM:"
yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields[\"$FIELD_NAME\"].options | keys[]" "$CONFIG"
```

---

## Related Patterns

- **config-parsing.md** - Raw YAML extraction (this pattern uses it for cache lookup)
- **corpus-lookup.md** - API fallback flow (routing → corpus → execute)
- **graphql-execution.md** - Temp file pattern for GraphQL queries
- **tool-detection.md** - Check yq/Python availability before resolution
