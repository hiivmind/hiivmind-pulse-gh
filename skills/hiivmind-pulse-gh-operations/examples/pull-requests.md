# Pull Request Operations Examples

Examples of common PR operations using hiivmind-pulse-gh.

## Create Pull Request

**Natural language:**
```
/hiivmind-pulse-gh create PR from feature/login to main
/hiivmind-pulse-gh open PR for current branch
/hiivmind-pulse-gh create pull request titled "Add user authentication"
```

**CLI shortcut (recommended):**
```bash
gh pr create --base main --head feature/login --title "Add user auth" --body "Description"
```

**GraphQL mutation:**
```graphql
mutation CreatePR($repositoryId: ID!, $baseRefName: String!, $headRefName: String!, $title: String!) {
  createPullRequest(input: {
    repositoryId: $repositoryId
    baseRefName: $baseRefName
    headRefName: $headRefName
    title: $title
  }) {
    pullRequest {
      number
      url
    }
  }
}
```

---

## Merge Pull Request

**Natural language:**
```
/hiivmind-pulse-gh merge PR #15
/hiivmind-pulse-gh squash merge #15
/hiivmind-pulse-gh rebase merge PR 15
```

**What happens:**
1. Gateway detects: domain=pull_requests, operation=merge, target=#15
2. Operations skill resolves PR node ID
3. Executes GraphQL `mergePullRequest` with merge method
4. Returns merge confirmation

**GraphQL mutation:**
```graphql
mutation MergePR($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod) {
  mergePullRequest(input: {
    pullRequestId: $pullRequestId
    mergeMethod: $mergeMethod
  }) {
    pullRequest {
      merged
      mergedAt
    }
  }
}
```

**Merge methods:** `MERGE`, `SQUASH`, `REBASE`

**CLI shortcut:**
```bash
gh pr merge 15 --squash
gh pr merge 15 --rebase
gh pr merge 15 --merge
```

---

## Request Review

**Natural language:**
```
/hiivmind-pulse-gh request review from @alice on PR #15
/hiivmind-pulse-gh add reviewer team/backend to #15
```

**GraphQL mutation:**
```graphql
mutation RequestReviews($pullRequestId: ID!, $userIds: [ID!], $teamIds: [ID!]) {
  requestReviews(input: {
    pullRequestId: $pullRequestId
    userIds: $userIds
    teamIds: $teamIds
  }) {
    pullRequest {
      number
      reviewRequests(first: 10) {
        nodes {
          requestedReviewer {
            ... on User { login }
            ... on Team { name }
          }
        }
      }
    }
  }
}
```

---

## Close Pull Request

**Natural language:**
```
/hiivmind-pulse-gh close PR #15
/hiivmind-pulse-gh close pull request 15 without merging
```

**GraphQL mutation:**
```graphql
mutation ClosePR($pullRequestId: ID!) {
  closePullRequest(input: {
    pullRequestId: $pullRequestId
  }) {
    pullRequest {
      number
      state
    }
  }
}
```

---

## List Pull Requests

**Natural language:**
```
/hiivmind-pulse-gh list open PRs
/hiivmind-pulse-gh show PRs by @alice
/hiivmind-pulse-gh list PRs ready for review
```

**CLI shortcut:**
```bash
gh pr list --state open
gh pr list --author alice
gh pr list --search "review:required"
```

---

## Add Labels to PR

**Natural language:**
```
/hiivmind-pulse-gh add label "needs-review" to PR #15
/hiivmind-pulse-gh label PR 15 as ready-to-merge
```

Uses same `addLabelsToLabelable` mutation as issues (PRs are labelable).

---

## Convert PR to Draft

**Natural language:**
```
/hiivmind-pulse-gh convert PR #15 to draft
/hiivmind-pulse-gh mark #15 as draft
```

**GraphQL mutation:**
```graphql
mutation ConvertToDraft($pullRequestId: ID!) {
  convertPullRequestToDraft(input: {
    pullRequestId: $pullRequestId
  }) {
    pullRequest {
      isDraft
    }
  }
}
```

---

## Mark PR Ready for Review

**Natural language:**
```
/hiivmind-pulse-gh mark PR #15 ready for review
/hiivmind-pulse-gh undraft #15
```

**GraphQL mutation:**
```graphql
mutation MarkReady($pullRequestId: ID!) {
  markPullRequestReadyForReview(input: {
    pullRequestId: $pullRequestId
  }) {
    pullRequest {
      isDraft
    }
  }
}
```
