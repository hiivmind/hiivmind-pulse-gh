# Workflow: Create Issue and Add to Project

> **Goal:** Create a new issue and add it to a Projects v2 board with initial status.

## Prerequisites

- `hiivmind-pulse-gh-init` has been run
- `.hiivmind/github/config.yaml` exists with project fields cached

## Step 1: Load Context

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT_NUM=$(yq '.projects.default' "$CONFIG")
```

## Step 2: Create the Issue

**Using `gh` CLI (simplest):**

```bash
ISSUE_URL=$(gh issue create \
  -R "$OWNER/hiivmind-pulse-gh" \
  --title "Add dark mode support" \
  --body "Users have requested a dark mode option." \
  --label "enhancement" \
  --json url --jq '.url')

echo "Created: $ISSUE_URL"
```

**Output:** `https://github.com/hiivmind/hiivmind-pulse-gh/issues/42`

## Step 3: Add Issue to Project

**Using `gh project` (simplest):**

```bash
gh project item-add "$PROJECT_NUM" \
  --owner "$OWNER" \
  --url "$ISSUE_URL"
```

**Alternative: GraphQL mutation**

First, get the issue's node ID:

```bash
# Corpus keywords: resource, url, URI, Issue
ISSUE_ID=$(gh api graphql -f query='query($url: URI!) { resource(url: $url) { ... on Issue { id } } }' -f url="$ISSUE_URL" --jq '.data.resource.id')
```

Then add to project:

```bash
PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .id" "$CONFIG")

# Corpus keywords: addProjectV2ItemById, projectId, contentId
# Reference: hiivmind-pulse-gh-operations skill → Domain: Projects v2
gh api graphql -f query='mutation($projectId: ID!, $contentId: ID!) { addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) { item { id } } }' \
  -f projectId="$PROJECT_ID" -f contentId="$ISSUE_ID"
```

## Step 4: Set Initial Status (Optional)

If you want to set the Status field immediately:

```bash
# Get IDs from config
FIELD_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.id" "$CONFIG")
OPTION_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options.Backlog" "$CONFIG")
ITEM_ID="PVTI_..."  # from addProjectV2ItemById response

# Corpus keywords: updateProjectV2ItemFieldValue, singleSelectOptionId
# Reference: hiivmind-pulse-gh-operations skill → Domain: Projects v2
gh api graphql -f query='mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) { updateProjectV2ItemFieldValue(input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: {singleSelectOptionId: $optionId}}) { projectV2Item { id } } }' \
  -f projectId="$PROJECT_ID" -f itemId="$ITEM_ID" -f fieldId="$FIELD_ID" -f optionId="$OPTION_ID"
```

## Complete Single-Command Version

For simple cases, `gh` handles everything:

```bash
# Create issue and add to project in one flow
ISSUE_URL=$(gh issue create \
  -R "$OWNER/repo" \
  --title "Feature request" \
  --body "Description" \
  --project "$PROJECT_NUM" \
  --json url --jq '.url')
```

The `--project` flag automatically adds the issue to the project.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Project not found" | Wrong project number | Check `yq '.projects.catalog[].number' "$CONFIG"` |
| "Could not add item" | Issue already in project | Safe to ignore |
| "Field not found" | Field ID changed | Run `hiivmind-pulse-gh-refresh` |
| "Option not found" | Status option renamed | Run `hiivmind-pulse-gh-refresh` |

## Corpus Lookup

Search the corpus index using these keywords:

| Need | Keywords |
|------|----------|
| Create issue | `createIssue`, `repositoryId`, `title`, `body` |
| Add to project | `addProjectV2ItemById`, `projectId`, `contentId` |
| Update field value | `updateProjectV2ItemFieldValue`, `fieldId`, `singleSelectOptionId` |
| Project types | `type ProjectV2`, `ProjectV2Item`, `ProjectV2Field` |

Start with `reference/api-routing.md` → "Issues" or "Projects v2" section for routing decisions.

---

## Related Workflows

- `manage-milestones.md` - Set milestone on the issue
- `project-status-update.md` - Update project status after adding items
