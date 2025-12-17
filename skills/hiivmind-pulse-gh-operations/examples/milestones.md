# Milestone Operations Examples

Examples of milestone operations using hiivmind-pulse-gh.

**Note:** Milestone CRUD uses REST API. Assigning milestones to issues uses GraphQL.

## Create Milestone

**Natural language:**
```
/hiivmind-pulse-gh create milestone "v2.0"
/hiivmind-pulse-gh new milestone "Q1 Release" due 2025-03-31
/hiivmind-pulse-gh create milestone titled "Sprint 5" with description "Auth features"
```

**REST endpoint:**
```
POST /repos/{owner}/{repo}/milestones
```

**Request body:**
```json
{
  "title": "v2.0",
  "description": "Major release with new features",
  "due_on": "2025-03-31T23:59:59Z",
  "state": "open"
}
```

**CLI equivalent:**
```bash
gh api repos/{owner}/{repo}/milestones -X POST \
  -f title="v2.0" \
  -f description="Major release" \
  -f due_on="2025-03-31T23:59:59Z"
```

---

## Update Milestone

**Natural language:**
```
/hiivmind-pulse-gh update milestone "v2.0" due date to 2025-04-15
/hiivmind-pulse-gh rename milestone 3 to "v2.1"
/hiivmind-pulse-gh change milestone "v2.0" description
```

**REST endpoint:**
```
PATCH /repos/{owner}/{repo}/milestones/{milestone_number}
```

**Request body:**
```json
{
  "title": "v2.1",
  "due_on": "2025-04-15T23:59:59Z"
}
```

---

## Close Milestone

**Natural language:**
```
/hiivmind-pulse-gh close milestone "v1.0"
/hiivmind-pulse-gh mark milestone 2 as closed
```

**REST endpoint:**
```
PATCH /repos/{owner}/{repo}/milestones/{milestone_number}
```

**Request body:**
```json
{
  "state": "closed"
}
```

---

## Delete Milestone

**Natural language:**
```
/hiivmind-pulse-gh delete milestone "Old Release"
/hiivmind-pulse-gh remove milestone 5
```

**REST endpoint:**
```
DELETE /repos/{owner}/{repo}/milestones/{milestone_number}
```

---

## List Milestones

**Natural language:**
```
/hiivmind-pulse-gh list milestones
/hiivmind-pulse-gh show open milestones
/hiivmind-pulse-gh list milestones sorted by due date
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/milestones?state=open&sort=due_on
```

**CLI equivalent:**
```bash
gh api repos/{owner}/{repo}/milestones --jq '.[] | {number, title, due_on, open_issues}'
```

---

## Assign Milestone to Issue

**Natural language:**
```
/hiivmind-pulse-gh set milestone v2.0 on issue #42
/hiivmind-pulse-gh add issues #40, #41, #42 to milestone "Sprint 5"
/hiivmind-pulse-gh assign milestone to PR #15
```

**What happens:**
1. Resolve milestone ID from title (via config or query)
2. Use GraphQL `updateIssue` mutation with `milestoneId`

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

## Remove Milestone from Issue

**Natural language:**
```
/hiivmind-pulse-gh remove milestone from #42
/hiivmind-pulse-gh clear milestone on issue 42
```

**GraphQL mutation:** Same as above, with `milestoneId: null`

```graphql
mutation ClearMilestone($issueId: ID!) {
  updateIssue(input: {
    id: $issueId
    milestoneId: null
  }) {
    issue {
      number
      milestone { title }
    }
  }
}
```

---

## View Milestone Progress

**Natural language:**
```
/hiivmind-pulse-gh show milestone "v2.0" progress
/hiivmind-pulse-gh milestone status for Sprint 5
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/milestones/{milestone_number}
```

**Response includes:**
```json
{
  "title": "v2.0",
  "open_issues": 5,
  "closed_issues": 12,
  "due_on": "2025-03-31T23:59:59Z"
}
```

**Progress calculation:** `closed_issues / (open_issues + closed_issues) * 100`
