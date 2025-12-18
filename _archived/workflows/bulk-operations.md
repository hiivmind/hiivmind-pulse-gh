# Workflow: Bulk Operations

> **Goal:** Perform batch operations on multiple items efficiently.
> **Pattern:** Loop with rate limiting, error handling, and progress tracking.

## Prerequisites

- `hiivmind-pulse-gh-init` has been run
- `.hiivmind/github/config.yaml` exists
- Appropriate access for target operations

## Load Context

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT_NUM=$(yq '.projects.default' "$CONFIG")
PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .id" "$CONFIG")
```

---

## Pattern 1: Add Multiple Issues to Project

### From Issue Numbers

```bash
REPO="hiivmind-pulse-gh"
ISSUES=(37 38 39 40 41 42 43)

for num in "${ISSUES[@]}"; do
  ISSUE_URL="https://github.com/$OWNER/$REPO/issues/$num"
  echo "Adding issue #$num..."
  gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$ISSUE_URL" 2>/dev/null || echo "  (already in project or error)"
  sleep 0.5  # Rate limiting
done
```

### From Label Query

```bash
REPO="hiivmind-pulse-gh"
LABEL="enhancement"

gh issue list -R "$OWNER/$REPO" --label "$LABEL" --state open --json url --jq '.[].url' | while read -r url; do
  echo "Adding: $url"
  gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$url" 2>/dev/null || true
  sleep 0.5
done
```

### From Milestone

```bash
REPO="hiivmind-pulse-gh"
MILESTONE="v3 Architecture Migration"

gh issue list -R "$OWNER/$REPO" --milestone "$MILESTONE" --state all --json url --jq '.[].url' | while read -r url; do
  echo "Adding: $url"
  gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$url" 2>/dev/null || true
  sleep 0.5
done
```

---

## Pattern 2: Update Status for Multiple Items

### Move All "Todo" to "In Progress"

```bash
STATUS_FIELD=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.id" "$CONFIG")
TODO_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options.Todo" "$CONFIG")
IN_PROGRESS=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options[\"In Progress\"]" "$CONFIG")

# Get all items with "Todo" status
gh api graphql -f query='
  query($project: ID!) {
    node(id: $project) {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            id
            fieldValues(first: 10) {
              nodes {
                ... on ProjectV2ItemFieldSingleSelectValue {
                  field { ... on ProjectV2SingleSelectField { name } }
                  optionId
                }
              }
            }
          }
        }
      }
    }
  }
' -f project="$PROJECT_ID" \
  --jq ".data.node.items.nodes[] | select(.fieldValues.nodes[] | select(.field.name == \"Status\" and .optionId == \"$TODO_ID\")) | .id" \
| while read -r item_id; do
  echo "Updating item: $item_id"
  gh api graphql -f query='
    mutation($project: ID!, $item: ID!, $field: ID!, $value: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $project, itemId: $item, fieldId: $field,
        value: {singleSelectOptionId: $value}
      }) { projectV2Item { id } }
    }
  ' -f project="$PROJECT_ID" -f item="$item_id" -f field="$STATUS_FIELD" -f value="$IN_PROGRESS"
  sleep 0.5
done
```

---

## Pattern 3: Apply Labels to Multiple Issues

### Add Label to Issues Matching Query

```bash
REPO="hiivmind-pulse-gh"
QUERY_LABEL="bug"
ADD_LABEL="needs-triage"

gh issue list -R "$OWNER/$REPO" --label "$QUERY_LABEL" --state open --json number --jq '.[].number' | while read -r num; do
  echo "Adding label to issue #$num..."
  gh issue edit "$num" -R "$OWNER/$REPO" --add-label "$ADD_LABEL"
  sleep 0.5
done
```

### Remove Label from All Issues

```bash
REPO="hiivmind-pulse-gh"
REMOVE_LABEL="wontfix"

gh issue list -R "$OWNER/$REPO" --label "$REMOVE_LABEL" --state all --json number --jq '.[].number' | while read -r num; do
  echo "Removing label from issue #$num..."
  gh issue edit "$num" -R "$OWNER/$REPO" --remove-label "$REMOVE_LABEL"
  sleep 0.5
done
```

---

## Pattern 4: Set Milestone on Multiple Issues

### Assign Milestone by Label

```bash
REPO="hiivmind-pulse-gh"
LABEL="v3-migration"
MILESTONE="v3 Architecture Migration"

gh issue list -R "$OWNER/$REPO" --label "$LABEL" --state open --json number --jq '.[].number' | while read -r num; do
  echo "Setting milestone on issue #$num..."
  gh issue edit "$num" -R "$OWNER/$REPO" --milestone "$MILESTONE"
  sleep 0.5
done
```

### Clear Milestone from Closed Issues

```bash
REPO="hiivmind-pulse-gh"
MILESTONE="Old Milestone"

gh issue list -R "$OWNER/$REPO" --milestone "$MILESTONE" --state closed --json number --jq '.[].number' | while read -r num; do
  echo "Clearing milestone from issue #$num..."
  gh issue edit "$num" -R "$OWNER/$REPO" --milestone ""
  sleep 0.5
done
```

---

## Pattern 5: Close Stale Issues

### Close Issues Older Than 90 Days

```bash
REPO="hiivmind-pulse-gh"
CUTOFF=$(date -d "90 days ago" +%Y-%m-%d)

gh issue list -R "$OWNER/$REPO" --state open --json number,createdAt --jq ".[] | select(.createdAt < \"$CUTOFF\") | .number" | while read -r num; do
  echo "Closing stale issue #$num..."
  gh issue close "$num" -R "$OWNER/$REPO" --comment "Closing due to inactivity. Please reopen if still relevant."
  sleep 0.5
done
```

---

## Pattern 6: Archive Completed Project Items

```bash
# Get all items with "Done" status
DONE_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options.Done" "$CONFIG")

gh api graphql -f query='
  query($project: ID!) {
    node(id: $project) {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            id
            fieldValues(first: 10) {
              nodes {
                ... on ProjectV2ItemFieldSingleSelectValue {
                  field { ... on ProjectV2SingleSelectField { name } }
                  optionId
                }
              }
            }
          }
        }
      }
    }
  }
' -f project="$PROJECT_ID" \
  --jq ".data.node.items.nodes[] | select(.fieldValues.nodes[] | select(.field.name == \"Status\" and .optionId == \"$DONE_ID\")) | .id" \
| while read -r item_id; do
  echo "Archiving item: $item_id"
  gh api graphql -f query='
    mutation($project: ID!, $item: ID!) {
      archiveProjectV2Item(input: {projectId: $project, itemId: $item}) {
        item { id }
      }
    }
  ' -f project="$PROJECT_ID" -f item="$item_id"
  sleep 0.5
done
```

---

## Pattern 7: Parallel Operations (Advanced)

For large batches, use `xargs` for controlled parallelism:

```bash
REPO="hiivmind-pulse-gh"

# Add issues to project with 4 parallel workers
gh issue list -R "$OWNER/$REPO" --state open --json url --jq '.[].url' | \
  xargs -P 4 -I {} sh -c "gh project item-add $PROJECT_NUM --owner $OWNER --url {} 2>/dev/null; sleep 0.2"
```

**Warning:** Be careful with parallelism - too many concurrent requests may hit rate limits.

---

## Rate Limiting Best Practices

| Scenario | Recommended Delay |
|----------|-------------------|
| Simple mutations | 0.5s between requests |
| Complex queries | 1s between requests |
| Parallel operations | 0.2s with max 4 workers |
| Large batches (100+) | Add 2s pause every 50 items |

### Check Rate Limit Status

```bash
gh api rate_limit --jq '{
  core: {remaining: .resources.core.remaining, reset: .resources.core.reset},
  graphql: {remaining: .resources.graphql.remaining, reset: .resources.graphql.reset}
}'
```

---

## Error Handling Pattern

```bash
# Robust bulk operation with logging
LOG_FILE="/tmp/bulk-op-$(date +%Y%m%d-%H%M%S).log"
ERRORS=0

process_item() {
  local item="$1"
  if gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$item" 2>>"$LOG_FILE"; then
    echo "OK: $item"
  else
    echo "FAIL: $item" | tee -a "$LOG_FILE"
    ((ERRORS++))
  fi
  sleep 0.5
}

gh issue list -R "$OWNER/$REPO" --state open --json url --jq '.[].url' | while read -r url; do
  process_item "$url"
done

echo "Complete. Errors: $ERRORS. Log: $LOG_FILE"
```

---

## Dry Run Pattern

Test before executing:

```bash
# Preview what would happen
DRY_RUN=true

gh issue list -R "$OWNER/$REPO" --label "bug" --state open --json number,title | while read -r line; do
  num=$(echo "$line" | jq -r '.number')
  title=$(echo "$line" | jq -r '.title')

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would close issue #$num: $title"
  else
    gh issue close "$num" -R "$OWNER/$REPO"
    echo "Closed issue #$num: $title"
  fi
done
```

---

## Corpus Lookup

Search the corpus index using these keywords:

| Need | Keywords |
|------|----------|
| Project item mutations | `addProjectV2ItemById`, `archiveProjectV2Item` |
| Issue mutations | `updateIssue`, `closeIssue`, `addLabelsToLabelable` |
| Label operations | `labelIds`, `addLabelsToLabelable`, `removeLabelsFromLabelable` |
| Milestone assignment | `milestoneId`, `updateIssue` |

Start with `reference/api-routing.md` for routing decisions on each operation type.

---

## Error Handling Reference

| Error | Cause | Solution |
|-------|-------|----------|
| "rate limit exceeded" | Too many requests | Add delays, check `gh api rate_limit` |
| "secondary rate limit" | Burst of requests | Add longer delays (2-5s) |
| "not found" | Invalid URL/ID | Validate input before processing |
| "already exists" | Duplicate operation | Safe to ignore (use `|| true`) |
