# Projects v2 Operations Examples

Examples of GitHub Projects v2 operations using hiivmind-pulse-gh.

## Add Item to Project

**Natural language:**
```
/hiivmind-pulse-gh add issue #42 to project
/hiivmind-pulse-gh add PR #15 to project board
/hiivmind-pulse-gh add #42 to project "Feature Planner"
```

**What happens:**
1. Gateway detects: domain=projects, operation=link, target=#42
2. Operations skill resolves project ID and content ID (issue/PR node ID)
3. Executes GraphQL `addProjectV2ItemById` mutation
4. Returns item ID for status updates

**GraphQL mutation:**
```graphql
mutation AddToProject($projectId: ID!, $contentId: ID!) {
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

---

## Update Project Status Field

**Natural language:**
```
/hiivmind-pulse-gh set status "In Progress" on #42 in project
/hiivmind-pulse-gh move #42 to "Done" column
/hiivmind-pulse-gh update project status for PR #15 to "Review"
```

**What happens:**
1. Gateway detects: domain=projects, operation=update, target=#42
2. Operations skill resolves:
   - Item ID (from project item, not issue ID)
   - Field ID (Status field)
   - Option ID (e.g., "In Progress" option)
3. Executes `updateProjectV2ItemFieldValue` mutation
4. Returns confirmation

**GraphQL mutation:**
```graphql
mutation UpdateStatus($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { singleSelectOptionId: $optionId }
  }) {
    projectV2Item {
      id
    }
  }
}
```

**Important:** The `itemId` is the project item ID, not the issue/PR ID. Resolve via config or query.

---

## Update Text Field

**Natural language:**
```
/hiivmind-pulse-gh set "Notes" field to "Blocked on API" for #42
/hiivmind-pulse-gh update Sprint field to "Sprint 5" on #42
```

**GraphQL mutation:**
```graphql
mutation UpdateTextField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $text: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { text: $text }
  }) {
    projectV2Item {
      id
    }
  }
}
```

---

## Update Date Field

**Natural language:**
```
/hiivmind-pulse-gh set due date to 2025-01-15 on #42
/hiivmind-pulse-gh update "Target Date" to next Friday for #42
```

**GraphQL mutation:**
```graphql
mutation UpdateDateField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $date: Date!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { date: $date }
  }) {
    projectV2Item {
      id
    }
  }
}
```

**Date format:** ISO 8601 date string, e.g., `"2025-01-15"`

---

## Update Number Field

**Natural language:**
```
/hiivmind-pulse-gh set estimate to 5 on #42
/hiivmind-pulse-gh update "Story Points" to 8 for #42
```

**GraphQL mutation:**
```graphql
mutation UpdateNumberField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $number: Float!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { number: $number }
  }) {
    projectV2Item {
      id
    }
  }
}
```

---

## Update Iteration Field

**Natural language:**
```
/hiivmind-pulse-gh set iteration to "Sprint 3" on #42
/hiivmind-pulse-gh move #42 to current iteration
```

**GraphQL mutation:**
```graphql
mutation UpdateIteration($projectId: ID!, $itemId: ID!, $fieldId: ID!, $iterationId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { iterationId: $iterationId }
  }) {
    projectV2Item {
      id
    }
  }
}
```

---

## Archive Project Item

**Natural language:**
```
/hiivmind-pulse-gh archive #42 from project
/hiivmind-pulse-gh remove #42 from project board
```

**GraphQL mutation:**
```graphql
mutation ArchiveItem($projectId: ID!, $itemId: ID!) {
  archiveProjectV2Item(input: {
    projectId: $projectId
    itemId: $itemId
  }) {
    item {
      id
    }
  }
}
```

---

## View Project Items

**Natural language:**
```
/hiivmind-pulse-gh list items in project
/hiivmind-pulse-gh show project board status
/hiivmind-pulse-gh list items with status "In Progress"
```

**GraphQL query:**
```graphql
query ProjectItems($projectId: ID!, $first: Int = 50) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: $first) {
        nodes {
          id
          content {
            ... on Issue { number title }
            ... on PullRequest { number title }
          }
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Create Project Status Update

**Natural language:**
```
/hiivmind-pulse-gh post project status update "Sprint 3 complete"
/hiivmind-pulse-gh add status update to project
```

**GraphQL mutation:**
```graphql
mutation CreateStatusUpdate($projectId: ID!, $body: String!, $status: ProjectV2StatusUpdateStatus) {
  createProjectV2StatusUpdate(input: {
    projectId: $projectId
    body: $body
    status: $status
  }) {
    statusUpdate {
      id
      body
    }
  }
}
```

**Status values:** `INACTIVE`, `ON_TRACK`, `AT_RISK`, `OFF_TRACK`, `COMPLETE`
