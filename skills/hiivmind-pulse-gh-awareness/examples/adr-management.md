# Pattern: ADR Management

## Purpose

Manage Architecture Decision Records: numbering, file creation, GitHub issue linking, and sync operations.

## When to Use

- Creating new ADRs
- Syncing ADR content between file and issue
- Updating ADR status
- Listing and searching ADRs

## Prerequisites

- **config-parsing.md** - Workspace config for GitHub operations
- **id-resolution.md** - Resolve milestone IDs
- **graphql-execution.md** - Execute GitHub mutations
- `doc/adr/` directory exists in repository

---

## ADR Numbering Algorithm

### Get Next ADR Number

**Using bash:**
```bash
ADR_DIR="doc/adr"

# Ensure directory exists
mkdir -p "$ADR_DIR"

# Find highest existing number
LAST_NUM=$(ls "$ADR_DIR"/*.md 2>/dev/null | \
  grep -oP '\d{4}' | \
  sort -n | \
  tail -1)

if [[ -z "$LAST_NUM" ]]; then
  NEXT_NUM=1
else
  # Remove leading zeros for arithmetic
  NEXT_NUM=$((10#$LAST_NUM + 1))
fi

# Format with zero-padding
printf "%04d" "$NEXT_NUM"
```

**Output:** `0001` (if no ADRs exist) or `0006` (if 0005 is highest)

### Generate Filename

```bash
ADR_NUM="0005"
TITLE="Use GraphQL for API"

# Convert title to slug
SLUG=$(echo "$TITLE" | \
  tr '[:upper:]' '[:lower:]' | \
  sed 's/[^a-z0-9]/-/g' | \
  sed 's/--*/-/g' | \
  sed 's/^-//' | \
  sed 's/-$//')

FILENAME="${ADR_NUM}-${SLUG}.md"
echo "$FILENAME"
# Output: 0005-use-graphql-for-api.md
```

---

## GitHub Issue Creation

### Step 1: Ensure `adr` label exists

```bash
OWNER="owner"
REPO="repo"

# Check if label exists, create if not
if ! gh api "/repos/$OWNER/$REPO/labels/adr" >/dev/null 2>&1; then
  gh api "/repos/$OWNER/$REPO/labels" \
    -f name="adr" \
    -f color="0052cc" \
    -f description="Architecture Decision Record"
fi
```

### Step 2: Create issue with ADR content

```bash
ADR_NUM="0005"
TITLE="Use GraphQL for API"
ADR_FILE="doc/adr/0005-use-graphql-for-api.md"
MILESTONE="v5.0.0"

# Read ADR content (skip frontmatter for body)
ADR_BODY=$(sed -n '/^---$/,/^---$/!p' "$ADR_FILE" | tail -n +2)

# Create issue
ISSUE_URL=$(gh issue create \
  --repo "$OWNER/$REPO" \
  --title "ADR-$(printf '%04d' $ADR_NUM): $TITLE" \
  --body "## Architecture Decision Record

**ADR Number:** $ADR_NUM
**File:** \`$ADR_FILE\`
**Status:** Proposed

---

$ADR_BODY

---

_This issue tracks the ADR. Update the markdown file for authoritative content._" \
  --label "adr" \
  --milestone "$MILESTONE")

echo "Created: $ISSUE_URL"
```

### Step 3: Extract issue number

```bash
# Extract issue number from URL
ISSUE_NUM=$(echo "$ISSUE_URL" | grep -oP '\d+$')
echo "Issue number: $ISSUE_NUM"
```

---

## Update ADR File with GitHub Links

After creating issue, update the ADR frontmatter:

**Using yq:**
```bash
ADR_FILE="doc/adr/0005-use-graphql-for-api.md"
ISSUE_NUM=142
MILESTONE="v5.0.0"

yq -i --front-matter=process ".issue = $ISSUE_NUM | .milestone = \"$MILESTONE\"" "$ADR_FILE"
```

**Using sed (fallback):**
```bash
# Update milestone line
sed -i "s/^milestone:.*/milestone: \"$MILESTONE\"/" "$ADR_FILE"

# Update issue line
sed -i "s/^issue:.*/issue: $ISSUE_NUM/" "$ADR_FILE"
```

---

## Milestone Assignment

### Using gh CLI (simplest)

```bash
ISSUE_NUM=142
MILESTONE="v5.0.0"

gh issue edit "$ISSUE_NUM" --milestone "$MILESTONE"
```

### Using GraphQL (programmatic)

```bash
# Get milestone node ID
MILESTONE_ID=$(gh api "/repos/$OWNER/$REPO/milestones" \
  --jq ".[] | select(.title == \"$MILESTONE\") | .node_id")

# Get issue node ID
ISSUE_ID=$(gh api "/repos/$OWNER/$REPO/issues/$ISSUE_NUM" --jq '.node_id')

# Assign via updateIssue mutation
cat > /tmp/query.graphql << 'QUERY'
mutation($issueId: ID!, $milestoneId: ID!) {
  updateIssue(input: {id: $issueId, milestoneId: $milestoneId}) {
    issue {
      number
      milestone { title number }
    }
  }
}
QUERY

gh api graphql \
  -f query="$(cat /tmp/query.graphql)" \
  -f issueId="$ISSUE_ID" \
  -f milestoneId="$MILESTONE_ID"

rm -f /tmp/query.graphql
```

---

## Sync Operations

### Sync File to Issue (file is authoritative)

```bash
ADR_FILE="doc/adr/0005-use-graphql-for-api.md"
ISSUE_NUM=142

# Read ADR content (skip frontmatter)
ADR_BODY=$(sed -n '/^---$/,/^---$/!p' "$ADR_FILE" | tail -n +2)

# Update issue body
gh issue edit "$ISSUE_NUM" --body "## Architecture Decision Record

**File:** \`$ADR_FILE\`

---

$ADR_BODY

---

_This issue tracks the ADR. Update the markdown file for authoritative content._"
```

### Sync Status Changes

When ADR status changes in file:

```bash
# Read status from file frontmatter
STATUS=$(yq --front-matter=extract '.status' "$ADR_FILE")

# Map status to issue state
case "$STATUS" in
  "Deprecated"|"Superseded")
    gh issue close "$ISSUE_NUM" --comment "ADR status changed to: $STATUS"
    ;;
  "Accepted"|"Proposed")
    gh issue reopen "$ISSUE_NUM" 2>/dev/null || true
    ;;
esac
```

---

## List ADRs

### List Local ADRs

```bash
echo "=== Architecture Decision Records ==="
for file in doc/adr/*.md; do
  if [[ -f "$file" ]]; then
    NUM=$(basename "$file" | grep -oP '^\d+')
    TITLE=$(yq --front-matter=extract '.title' "$file" 2>/dev/null || \
            grep -m1 '^# ' "$file" | sed 's/^# [0-9]*\. //')
    STATUS=$(yq --front-matter=extract '.status' "$file" 2>/dev/null || echo "Unknown")
    printf "%s. %s [%s]\n" "$NUM" "$TITLE" "$STATUS"
  fi
done
```

### List ADR Issues from GitHub

```bash
gh issue list --label "adr" --state all --json number,title,state,milestone \
  --jq '.[] | "\(.number): \(.title) [\(.state)] - \(.milestone.title // "no milestone")"'
```

---

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `doc/adr/ not found` | Directory doesn't exist | Create with `mkdir -p doc/adr` |
| `Label adr not found` | First ADR in repo | Create label automatically |
| `Milestone not found` | Typo or doesn't exist | List milestones, ask user to select |
| `Permission denied` | No write access | Check repo permissions |
| `Issue already exists` | Duplicate ADR title | Check for existing, offer to link |

---

## Related Patterns

- **config-parsing.md** - Load workspace configuration
- **id-resolution.md** - Resolve milestone/issue IDs from cache
- **graphql-execution.md** - Execute GitHub mutations
- **error-handling.md** - Handle API errors

## Related References

- **reference/adr-template.md** - ADR file template and schema
