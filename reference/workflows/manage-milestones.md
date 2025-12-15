# Workflow: Manage Milestones

> **Goal:** Create, update, and assign milestones to issues.
> **API:** REST for CRUD, GraphQL for assignment

## Prerequisites

- `hiivmind-pulse-gh-init` has been run
- `.hiivmind/github/config.yaml` exists

## Load Context

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
REPO="hiivmind-pulse-gh"  # or from config
```

---

## Create Milestone

**REST API required** (not available in GraphQL)

```bash
gh api "/repos/$OWNER/$REPO/milestones" \
  -f title="v2.0" \
  -f description="Second major release" \
  -f due_on="2025-06-30T00:00:00Z" \
  -f state="open"
```

**Response includes:**
```json
{
  "number": 3,
  "title": "v2.0",
  "state": "open",
  "due_on": "2025-06-30T00:00:00Z"
}
```

---

## List Milestones

**GraphQL (better for detailed queries):**

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!) {
    repository(owner: $owner, name: $repo) {
      milestones(first: 20, states: [OPEN]) {
        nodes {
          number
          title
          dueOn
          progressPercentage
          issues { totalCount }
        }
      }
    }
  }
' -f owner="$OWNER" -f repo="$REPO"
```

**REST (simpler):**

```bash
gh api "/repos/$OWNER/$REPO/milestones" --jq '.[] | {number, title, state, due_on}'
```

---

## Update Milestone

**REST API required**

```bash
# Close a milestone
gh api "/repos/$OWNER/$REPO/milestones/3" \
  -X PATCH \
  -f state="closed"

# Update due date
gh api "/repos/$OWNER/$REPO/milestones/3" \
  -X PATCH \
  -f due_on="2025-07-31T00:00:00Z"

# Update title and description
gh api "/repos/$OWNER/$REPO/milestones/3" \
  -X PATCH \
  -f title="v2.0 - Summer Release" \
  -f description="Updated scope for summer release"
```

---

## Delete Milestone

**REST API required**

```bash
gh api "/repos/$OWNER/$REPO/milestones/3" -X DELETE
```

---

## Assign Milestone to Issue

**GraphQL mutation** (updateIssue)

First, get the milestone's node ID:

```bash
MILESTONE_ID=$(gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      milestone(number: $number) { id }
    }
  }
' -f owner="$OWNER" -f repo="$REPO" -F number=3 --jq '.data.repository.milestone.id')
```

Then assign to issue:

```bash
ISSUE_ID="..."  # Get from issue query

gh api graphql -f query='
  mutation($issueId: ID!, $milestoneId: ID!) {
    updateIssue(input: {id: $issueId, milestoneId: $milestoneId}) {
      issue { number title milestone { title } }
    }
  }
' -f issueId="$ISSUE_ID" -f milestoneId="$MILESTONE_ID"
```

**Simpler with `gh` CLI:**

```bash
gh issue edit 42 --milestone "v2.0"
```

---

## Remove Milestone from Issue

**GraphQL mutation** with null milestone:

```bash
gh api graphql -f query='
  mutation($issueId: ID!) {
    updateIssue(input: {id: $issueId, milestoneId: null}) {
      issue { number milestone { title } }
    }
  }
' -f issueId="$ISSUE_ID"
```

**Or with `gh` CLI:**

```bash
gh issue edit 42 --milestone ""
```

---

## Check Milestone Progress

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      milestone(number: $number) {
        title
        progressPercentage
        issues(states: [OPEN]) { totalCount }
        closedIssues: issues(states: [CLOSED]) { totalCount }
      }
    }
  }
' -f owner="$OWNER" -f repo="$REPO" -F number=3
```

---

## API Routing Summary

| Operation | API | Why |
|-----------|-----|-----|
| Create | REST | No GraphQL mutation |
| List | Either | GraphQL has better filtering |
| Update | REST | No GraphQL mutation |
| Delete | REST | No GraphQL mutation |
| Assign to issue | GraphQL | Via `updateIssue` mutation |
| Query with issues | GraphQL | Better nested queries |

---

## Corpus Lookup

For exact field names and types:
- GraphQL: `grep -n "^type Milestone " graphql-schema:schema.docs.graphql -A 30`
- REST: `sections/rest.md` → search "milestones"

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Resource not accessible" | Missing repo write access | Check `gh auth status` |
| "Validation failed" | Invalid due_on format | Use ISO 8601: `YYYY-MM-DDTHH:MM:SSZ` |
| "Not Found" | Milestone doesn't exist | List milestones first |
