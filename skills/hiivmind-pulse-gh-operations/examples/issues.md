# Issue Operations Examples

Examples of common issue operations using hiivmind-pulse-gh.

## Create Issue

**Natural language:**
```
/hiivmind-pulse-gh create issue for login timeout bug
/hiivmind-pulse-gh create issue titled "Add dark mode support"
/hiivmind-pulse-gh new issue: API returns 500 on empty payload
```

**What happens:**
1. Gateway detects: domain=issues, operation=create
2. Operations skill loads config, resolves repository ID
3. Executes GraphQL `createIssue` mutation
4. Returns issue number and URL

**GraphQL mutation:**
```graphql
mutation CreateIssue($repositoryId: ID!, $title: String!, $body: String) {
  createIssue(input: {
    repositoryId: $repositoryId
    title: $title
    body: $body
  }) {
    issue {
      number
      url
    }
  }
}
```

---

## Close Issue

**Natural language:**
```
/hiivmind-pulse-gh close issue #42
/hiivmind-pulse-gh close #42 as completed
/hiivmind-pulse-gh close issue 42 as not planned
```

**What happens:**
1. Gateway detects: domain=issues, operation=delete (close), target=#42
2. Operations skill resolves issue node ID from number
3. Executes GraphQL `closeIssue` mutation with stateReason
4. Returns confirmation

**GraphQL mutation:**
```graphql
mutation CloseIssue($issueId: ID!, $stateReason: IssueClosedStateReason) {
  closeIssue(input: {
    issueId: $issueId
    stateReason: $stateReason
  }) {
    issue {
      number
      state
    }
  }
}
```

**State reasons:** `COMPLETED`, `NOT_PLANNED`

---

## Update Issue

**Natural language:**
```
/hiivmind-pulse-gh update issue #42 title to "New title"
/hiivmind-pulse-gh edit #42 body to include reproduction steps
/hiivmind-pulse-gh rename issue 42 to "Better title"
```

**GraphQL mutation:**
```graphql
mutation UpdateIssue($issueId: ID!, $title: String, $body: String) {
  updateIssue(input: {
    id: $issueId
    title: $title
    body: $body
  }) {
    issue {
      number
      title
    }
  }
}
```

---

## Add Labels to Issue

**Natural language:**
```
/hiivmind-pulse-gh add label "bug" to issue #42
/hiivmind-pulse-gh label #42 as priority-high
/hiivmind-pulse-gh add labels bug, urgent to #42
```

**What happens:**
1. Gateway detects: domain=labels, operation=link, target=#42
2. Operations skill resolves label IDs from config or queries
3. Executes GraphQL `addLabelsToLabelable` mutation
4. Returns updated labels

**GraphQL mutation:**
```graphql
mutation AddLabels($labelableId: ID!, $labelIds: [ID!]!) {
  addLabelsToLabelable(input: {
    labelableId: $labelableId
    labelIds: $labelIds
  }) {
    labelable {
      ... on Issue {
        number
        labels(first: 10) {
          nodes { name }
        }
      }
    }
  }
}
```

---

## Set Milestone on Issue

**Natural language:**
```
/hiivmind-pulse-gh set milestone v2.0 on issue #42
/hiivmind-pulse-gh add #42 to milestone "Q1 Release"
/hiivmind-pulse-gh assign milestone v1.5 to issues #40, #41, #42
```

**What happens:**
1. Gateway detects: domain=milestones, operation=link, target=#42
2. Operations skill resolves milestone ID from config (by title)
3. Executes GraphQL `updateIssue` with milestoneId
4. Returns confirmation

**GraphQL mutation:**
```graphql
mutation SetMilestone($issueId: ID!, $milestoneId: ID) {
  updateIssue(input: {
    id: $issueId
    milestoneId: $milestoneId
  }) {
    issue {
      number
      milestone { title }
    }
  }
}
```

---

## Add Comment to Issue

**Natural language:**
```
/hiivmind-pulse-gh comment on #42 "Fixed in commit abc123"
/hiivmind-pulse-gh add comment to issue 42: "Needs more testing"
```

**GraphQL mutation:**
```graphql
mutation AddComment($subjectId: ID!, $body: String!) {
  addComment(input: {
    subjectId: $subjectId
    body: $body
  }) {
    commentEdge {
      node {
        id
        url
      }
    }
  }
}
```

---

## List Issues

**Natural language:**
```
/hiivmind-pulse-gh list open issues
/hiivmind-pulse-gh show issues with label "bug"
/hiivmind-pulse-gh list issues in milestone v2.0
```

**CLI shortcut:**
```bash
gh issue list --state open
gh issue list --label "bug"
gh issue list --milestone "v2.0"
```
