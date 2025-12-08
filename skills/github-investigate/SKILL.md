---
name: hiivmind-github-investigate
description: >
  Deep-dive investigation of GitHub entities. Starting from an issue, PR, or project item,
  traverse all relationships to build full context: linked issues, pull requests, comments,
  reviewers, commits, and participants. Use when you need to understand the complete picture
  of a work item, prepare for standups, or audit who touched what. Returns rich context
  but does NOT cache (data too volatile). Answers: "What's the full story on issue #42?"
---

# GitHub Entity Investigator

Deep-dive investigation tool that traverses GitHub entity relationships to build complete context.

## Purpose

Unlike `hiivmind-github-workspace-refresh` (which syncs structural metadata), this skill **explores entities on-demand** to answer questions like:

- "What's the full story on issue #42?"
- "Who's involved in this PR and what's blocking it?"
- "Show me everything related to this project item"

## Key Principles

1. **No caching** - Entity data changes rapidly; always fetch fresh
2. **Relationship traversal** - Follow links between entities
3. **Rich context** - Return everything needed to understand/act
4. **Starting point agnostic** - Can start from issue, PR, or project item

## Entity Relationship Map

```
                              ┌─────────────┐
                              │   Project   │
                              │    Item     │
                              └──────┬──────┘
                                     │ links to
                              ┌──────▼──────┐
                         ┌────┤    Issue    ├────┐
                         │    └──────┬──────┘    │
                    mentions         │         linked to
                         │           │           │
              ┌──────────▼───┐ ┌─────▼─────┐ ┌───▼──────────┐
              │    Issues    │ │  Comments │ │     PRs      │
              │  (related)   │ │           │ │  (closing)   │
              └──────────────┘ └─────┬─────┘ └───┬──────────┘
                                     │           │
                              ┌──────▼───┐ ┌─────▼─────┐
                              │  Authors │ │  Commits  │
                              │          │ │  Reviews  │
                              └──────────┘ └───────────┘
```

## Traversal Depths

| Depth | Entities Fetched | Use Case |
|-------|------------------|----------|
| **shallow** | Direct properties only | Quick status check |
| **standard** | + comments, linked PRs, assignees | Normal investigation |
| **deep** | + PR commits, reviews, related issues, all participants | Full audit trail |

## Starting Points

### From Issue Number

```bash
# Input: owner/repo#42 or just #42 (with workspace config)
analyze_issue "acme-corp" "api" 42
```

### From Pull Request

```bash
# Input: owner/repo#87 or PR URL
analyze_pr "acme-corp" "api" 87
```

### From Project Item

```bash
# Input: Project item ID (from project query)
analyze_project_item "PVTI_lADOxxxxxxx"
```

## Output Structure

### Standard Analysis Output

```yaml
entity:
  type: issue
  number: 42
  title: "Fix authentication timeout"
  url: https://github.com/acme-corp/api/issues/42
  state: open
  created: 2025-12-01T10:00:00Z
  updated: 2025-12-08T14:30:00Z

attribution:
  author: "@alice"
  assignees: ["@alice", "@bob"]

labels:
  - bug
  - priority:high
  - area:auth

milestone:
  title: "v2.1.0"
  due: 2025-01-15
  progress: "12/20 (60%)"

project:
  name: "Product Roadmap"
  status: "In Progress"
  priority: "P1 - High"
  sprint: "Sprint 5"

timeline:
  - 2025-12-01: Created by @alice
  - 2025-12-02: Assigned to @bob
  - 2025-12-03: Linked to PR #87
  - 2025-12-05: @bob commented (investigation notes)
  - 2025-12-08: @alice commented (proposed fix)

comments:
  count: 5
  last:
    author: "@alice"
    date: 2025-12-08T14:30:00Z
    preview: "I think the issue is in the retry logic..."
  participants: ["@alice", "@bob", "@carol"]

linked_prs:
  - number: 87
    title: "Add retry logic for auth timeouts"
    state: draft
    author: "@alice"
    branch: "fix/auth-timeout"
    checks: passing
    commits: 3
    additions: 120
    deletions: 45

related_issues:
  - number: 38
    title: "Timeout errors in production"
    state: closed
    relationship: "mentioned in #42"
  - number: 55
    title: "Auth service latency spike"
    state: open
    relationship: "same labels"

blockers:
  - "PR #87 is still in draft"
  - "No reviewers assigned to PR #87"
```

## GraphQL Queries

### Issue with Full Context

```graphql
query IssueAnalysis($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      id
      number
      title
      body
      state
      createdAt
      updatedAt
      url

      author { login }
      assignees(first: 10) { nodes { login } }
      labels(first: 20) { nodes { name color } }

      milestone {
        title
        dueOn
        progressPercentage
      }

      projectItems(first: 5) {
        nodes {
          project { title }
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
              ... on ProjectV2ItemFieldIterationValue {
                title
                field { ... on ProjectV2IterationField { name } }
              }
            }
          }
        }
      }

      comments(first: 20) {
        totalCount
        nodes {
          author { login }
          createdAt
          body
        }
      }

      timelineItems(first: 50, itemTypes: [
        CROSS_REFERENCED_EVENT,
        CONNECTED_EVENT,
        ASSIGNED_EVENT,
        LABELED_EVENT
      ]) {
        nodes {
          __typename
          ... on CrossReferencedEvent {
            source {
              ... on PullRequest { number title state }
              ... on Issue { number title state }
            }
          }
          ... on ConnectedEvent {
            subject { ... on PullRequest { number title } }
          }
          ... on AssignedEvent {
            assignee { ... on User { login } }
            createdAt
          }
        }
      }
    }
  }
}
```

### PR with Commits and Reviews

```graphql
query PRAnalysis($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      id
      number
      title
      body
      state
      isDraft
      createdAt
      updatedAt
      url

      author { login }
      assignees(first: 10) { nodes { login } }

      headRefName
      baseRefName

      additions
      deletions
      changedFiles

      commits(first: 50) {
        totalCount
        nodes {
          commit {
            oid
            messageHeadline
            author { name email date }
          }
        }
      }

      reviews(first: 20) {
        nodes {
          author { login }
          state
          submittedAt
          body
        }
      }

      reviewRequests(first: 10) {
        nodes {
          requestedReviewer {
            ... on User { login }
            ... on Team { name }
          }
        }
      }

      closingIssuesReferences(first: 10) {
        nodes {
          number
          title
          state
        }
      }

      statusCheckRollup {
        state
        contexts(first: 20) {
          nodes {
            ... on CheckRun {
              name
              conclusion
              status
            }
          }
        }
      }
    }
  }
}
```

## Implementation Functions

### Core Analysis Functions

```bash
# Analyze an issue with full context
analyze_issue() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local depth="${4:-standard}"  # shallow, standard, deep

    # Fetch issue data
    local issue_data=$(gh api graphql -f query="..." \
        -f owner="$owner" -f repo="$repo" -F number="$number")

    # Parse and format
    format_issue_analysis "$issue_data" "$depth"
}

# Analyze a pull request
analyze_pr() {
    local owner="$1"
    local repo="$2"
    local number="$3"
    local depth="${4:-standard}"

    local pr_data=$(gh api graphql -f query="..." \
        -f owner="$owner" -f repo="$repo" -F number="$number")

    format_pr_analysis "$pr_data" "$depth"
}

# Analyze a project item (follows link to underlying issue/PR)
analyze_project_item() {
    local item_id="$1"
    local depth="${2:-standard}"

    # Get project item with content reference
    local item_data=$(gh api graphql -f query='
        query($id: ID!) {
            node(id: $id) {
                ... on ProjectV2Item {
                    content {
                        ... on Issue {
                            number
                            repository { owner { login } name }
                        }
                        ... on PullRequest {
                            number
                            repository { owner { login } name }
                        }
                    }
                }
            }
        }
    ' -f id="$item_id")

    # Follow to underlying entity
    # ...
}
```

### Relationship Discovery

```bash
# Find all issues related to a given issue
find_related_issues() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    # Same labels
    # Same milestone
    # Mentioned in timeline
    # Linked in body
}

# Find all participants in an issue thread
find_participants() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    # Author
    # Assignees
    # Commenters
    # Reviewers (if linked PRs)
    # Mentioned users
}

# Build timeline of events
build_timeline() {
    local owner="$1"
    local repo="$2"
    local number="$3"

    # Merge timeline events into chronological order
    # Include: created, assigned, labeled, commented, linked, closed
}
```

## Usage Examples

### Quick Status Check

```
You: What's happening with issue #42?

Claude: [Runs analyze at shallow depth]

        Issue #42: "Fix authentication timeout"
        State: Open | Assigned: @alice | Updated: 2 hours ago
        Milestone: v2.1.0 (due Jan 15)
        Project: In Progress
```

### Full Investigation

```
You: I need to understand everything about #42 before the standup

Claude: [Runs analyze at deep depth]

        Issue #42: "Fix authentication timeout"
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        📋 Status
        ├── State: Open (created Dec 1, updated 2h ago)
        ├── Assignees: @alice, @bob
        ├── Labels: bug, priority:high, area:auth
        └── Milestone: v2.1.0 (60% complete, due Jan 15)

        📊 Project Board
        ├── Product Roadmap → In Progress
        ├── Priority: P1 - High
        └── Sprint: Sprint 5

        💬 Discussion (5 comments)
        ├── Dec 2: @bob - Initial investigation, found retry gap
        ├── Dec 5: @alice - Proposed solution approach
        └── Dec 8: @alice - "Ready to open PR for review"

        🔗 Linked Pull Requests
        └── PR #87: "Add retry logic" (draft)
            ├── Author: @alice | Branch: fix/auth-timeout
            ├── +120/-45 lines across 4 files
            ├── 3 commits (last: 1 hour ago)
            ├── CI: ✓ All checks passing
            └── ⚠ No reviewers assigned

        📎 Related Issues
        ├── #38: "Timeout errors in production" (closed) - referenced
        └── #55: "Auth service latency" (open) - same labels

        👥 Participants
        └── @alice (author, assignee), @bob (assignee), @carol (commenter)

        ⚠ Blockers
        ├── PR #87 is still in draft mode
        └── No reviewers have been requested
```

### Audit Trail

```
You: Who touched issue #42 and when?

Claude: [Runs analyze focusing on timeline]

        Timeline for Issue #42
        ━━━━━━━━━━━━━━━━━━━━━━
        Dec 01 10:00  @alice created issue
        Dec 01 10:05  @alice added labels: bug, area:auth
        Dec 01 10:10  Added to project "Product Roadmap"
        Dec 02 09:00  @alice assigned @bob
        Dec 02 14:30  @bob commented (investigation notes)
        Dec 03 11:00  Linked to PR #87
        Dec 05 16:00  @alice commented (proposed fix)
        Dec 05 16:05  Status changed: Backlog → In Progress
        Dec 08 14:30  @alice commented (ready for review)
```

## Future Enhancements

### Planned Traversals

| Feature | Description |
|---------|-------------|
| **Cross-repo links** | Follow references to issues in other repos |
| **Commit analysis** | Deep-dive into commit diffs and blame |
| **Team patterns** | Identify who typically reviews what |
| **Stale detection** | Flag items with no activity |
| **Dependency graph** | Visualize blocking relationships |

### Integration Points

- Feed analysis results to other skills for action
- Generate summaries for standups/reports
- Identify automation opportunities

## Reference

- Refresh workspace: `skills/github-workspace-refresh/SKILL.md`
- Initialize workspace: `skills/github-workspace-init/SKILL.md`
- Projects operations: `skills/github-projects/SKILL.md`
