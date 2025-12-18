# Workflow: Project Status Update

> **Goal:** Update project item fields and create project-level status updates.
> **API:** GraphQL exclusively (Projects v2 has no REST API)

## Prerequisites

- `hiivmind-pulse-gh-init` has been run
- `.hiivmind/github/config.yaml` exists with project fields cached
- Write access to the project

## Load Context

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT_NUM=$(yq '.projects.default' "$CONFIG")
PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .id" "$CONFIG")
```

---

## Update Item Status Field

### Get Field and Option IDs from Config

```bash
STATUS_FIELD=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.id" "$CONFIG")
IN_PROGRESS=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options[\"In Progress\"]" "$CONFIG")
```

### Update Single Item

```bash
ITEM_ID="PVTI_..."  # Project item ID

gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $value: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: {singleSelectOptionId: $value}
    }) {
      projectV2Item { id }
    }
  }
' -f project="$PROJECT_ID" \
  -f item="$ITEM_ID" \
  -f field="$STATUS_FIELD" \
  -f value="$IN_PROGRESS"
```

### Move Item to Done

```bash
DONE=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options.Done" "$CONFIG")

gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $value: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: {singleSelectOptionId: $value}
    }) {
      projectV2Item { id }
    }
  }
' -f project="$PROJECT_ID" \
  -f item="$ITEM_ID" \
  -f field="$STATUS_FIELD" \
  -f value="$DONE"
```

---

## Update Other Field Types

### Text Field

```bash
NOTES_FIELD="PVTF_..."  # Text field ID

gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $text: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: {text: $text}
    }) {
      projectV2Item { id }
    }
  }
' -f project="$PROJECT_ID" \
  -f item="$ITEM_ID" \
  -f field="$NOTES_FIELD" \
  -f text="Implementation complete, awaiting review"
```

### Number Field

```bash
POINTS_FIELD="PVTF_..."  # Number field ID

gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $num: Float!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: {number: $num}
    }) {
      projectV2Item { id }
    }
  }
' -f project="$PROJECT_ID" \
  -f item="$ITEM_ID" \
  -f field="$POINTS_FIELD" \
  -F num=5
```

### Date Field

```bash
DUE_FIELD="PVTF_..."  # Date field ID

gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $date: Date!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: {date: $date}
    }) {
      projectV2Item { id }
    }
  }
' -f project="$PROJECT_ID" \
  -f item="$ITEM_ID" \
  -f field="$DUE_FIELD" \
  -f date="2025-12-31"
```

### Iteration Field

```bash
ITERATION_FIELD="PVTF_..."  # Iteration field ID
ITERATION_ID="..."  # Specific iteration ID

gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $iteration: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: {iterationId: $iteration}
    }) {
      projectV2Item { id }
    }
  }
' -f project="$PROJECT_ID" \
  -f item="$ITEM_ID" \
  -f field="$ITERATION_FIELD" \
  -f iteration="$ITERATION_ID"
```

---

## Find Item ID from Issue/PR

### By Issue Number

```bash
ISSUE_NUMBER=42

ITEM_ID=$(gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!, $project: Int!) {
    repository(owner: $owner, name: $repo) {
      issue(number: $number) {
        projectItems(first: 10) {
          nodes {
            id
            project { number }
          }
        }
      }
    }
  }
' -f owner="$OWNER" -f repo="$REPO" -F number="$ISSUE_NUMBER" -F project="$PROJECT_NUM" \
  --jq ".data.repository.issue.projectItems.nodes[] | select(.project.number == $PROJECT_NUM) | .id")
```

### By Issue URL

```bash
ISSUE_URL="https://github.com/owner/repo/issues/42"

ITEM_ID=$(gh api graphql -f query='
  query($url: URI!, $project: Int!) {
    resource(url: $url) {
      ... on Issue {
        projectItems(first: 10) {
          nodes {
            id
            project { number }
          }
        }
      }
    }
  }
' -f url="$ISSUE_URL" -F project="$PROJECT_NUM" \
  --jq ".data.resource.projectItems.nodes[] | select(.project.number == $PROJECT_NUM) | .id")
```

---

## Create Project Status Update

Project-level status updates (visible in project summary).

### Check Existing Updates

```bash
gh api graphql -f query='
  query($project: ID!) {
    node(id: $project) {
      ... on ProjectV2 {
        statusUpdates(first: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
          nodes {
            id
            body
            status
            createdAt
          }
        }
      }
    }
  }
' -f project="$PROJECT_ID"
```

### Create Status Update

```bash
gh api graphql -f query='
  mutation($project: ID!, $body: String!, $status: ProjectV2StatusUpdateStatus) {
    createProjectV2StatusUpdate(input: {
      projectId: $project
      body: $body
      status: $status
    }) {
      statusUpdate {
        id
        body
        status
        createdAt
      }
    }
  }
' -f project="$PROJECT_ID" \
  -f body="Sprint 3 complete. All planned items delivered. Moving to sprint 4 planning." \
  -f status="ON_TRACK"
```

### Status Options

| Status | Use When |
|--------|----------|
| `INACTIVE` | Project paused |
| `ON_TRACK` | Everything going well |
| `AT_RISK` | Some concerns |
| `OFF_TRACK` | Behind schedule |
| `COMPLETE` | Project finished |

### Update Existing Status

```bash
STATUS_UPDATE_ID="PSU_..."

gh api graphql -f query='
  mutation($id: ID!, $body: String!, $status: ProjectV2StatusUpdateStatus) {
    updateProjectV2StatusUpdate(input: {
      statusUpdateId: $id
      body: $body
      status: $status
    }) {
      statusUpdate { id body status }
    }
  }
' -f id="$STATUS_UPDATE_ID" \
  -f body="Updated: Blocked on external dependency" \
  -f status="AT_RISK"
```

### Delete Status Update

```bash
gh api graphql -f query='
  mutation($id: ID!) {
    deleteProjectV2StatusUpdate(input: {statusUpdateId: $id}) {
      statusUpdate { id }
    }
  }
' -f id="$STATUS_UPDATE_ID"
```

---

## Archive/Restore Items

### Archive Item

```bash
gh api graphql -f query='
  mutation($project: ID!, $item: ID!) {
    archiveProjectV2Item(input: {projectId: $project, itemId: $item}) {
      item { id }
    }
  }
' -f project="$PROJECT_ID" -f item="$ITEM_ID"
```

### Restore Archived Item

```bash
gh api graphql -f query='
  mutation($project: ID!, $item: ID!) {
    unarchiveProjectV2Item(input: {projectId: $project, itemId: $item}) {
      item { id }
    }
  }
' -f project="$PROJECT_ID" -f item="$ITEM_ID"
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Could not resolve to a ProjectV2" | Invalid project ID | Check config, run refresh |
| "Field not found" | Field ID changed | Run `hiivmind-pulse-gh-refresh` |
| "Option not found" | Status option renamed | Run `hiivmind-pulse-gh-refresh` |
| "Not authorized" | Missing project write access | Check project permissions |
| "Item not in project" | Wrong item ID | Query item ID from issue first |

---

## Corpus Lookup

Search the corpus index using these keywords:

| Need | Keywords |
|------|----------|
| Update item field | `updateProjectV2ItemFieldValue`, `fieldId`, `value` |
| Status updates | `createProjectV2StatusUpdate`, `ON_TRACK`, `AT_RISK` |
| Archive items | `archiveProjectV2Item`, `unarchiveProjectV2Item` |
| Project types | `type ProjectV2`, `ProjectV2Item`, `ProjectV2Field` |
| Field value input | `ProjectV2FieldValue`, `singleSelectOptionId`, `text`, `number` |

Start with `reference/api-routing.md` → "Projects v2" section for routing decisions.
