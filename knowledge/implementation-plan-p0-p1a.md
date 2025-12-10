# Implementation Plan: Foundation + Work Tracking (P0-P1a)

> **Document ID:** IMPL-001
> **Created:** 2025-12-10
> **Status:** Active Implementation Plan
> **Tracks:** GitHub Milestone "Architecture Refactor: Domain Segmentation"

This document details the implementation plan for Phase 1 (Foundation) and Phase 2a (Work Tracking) of the domain segmentation architecture.

---

## Overview

### Scope

| Phase | Priority | Domains | Purpose |
|-------|----------|---------|---------|
| Phase 1 | P0 | Identity, Repository | Foundation - everything else depends on these |
| Phase 2a | P1 | Issue, Pull Request, Milestone, Project (clean) | Core work tracking workflow |

### Deliverables per Domain

Each domain will have:
1. `gh-{domain}-functions.sh` - Shell function primitives
2. `gh-{domain}-graphql-queries.yaml` - GraphQL query templates (if needed)
3. `gh-{domain}-jq-filters.yaml` - jq filter templates (if needed)
4. `gh-{domain}-index.md` - Documentation index

### Primitive Classification Reference

| Type | Pattern | Purpose | Input | Output |
|------|---------|---------|-------|--------|
| **FETCH** | `fetch_{entity}`, `discover_{scope}_{entities}` | Retrieve data | Args | JSON stdout |
| **LOOKUP** | `get_{entity}_id` | Resolve identifiers | Args | Single value stdout |
| **FILTER** | `filter_{criteria}`, `apply_{criteria}_filter` | Transform/filter data | JSON stdin | JSON stdout |
| **EXTRACT** | `extract_{what}` | Pull specific fields | JSON stdin | JSON/text stdout |
| **FORMAT** | `format_{entity}` | Human-readable output | JSON stdin | Text stdout |
| **MUTATE** | `create_*`, `update_*`, `delete_*`, `set_*` | Create/update/delete | Args | Result JSON stdout |
| **DETECT** | `detect_{what}` | Determine type/state | Args | Type string stdout |

---

## Phase 1: Foundation (P0)

### Domain: Identity

**File:** `lib/github/gh-identity-functions.sh`

#### Functions to Implement

| Function | Type | Source | Description |
|----------|------|--------|-------------|
| `get_viewer_id` | LOOKUP | New | Current authenticated user's node ID |
| `get_user_id` | LOOKUP | New | Specific user's node ID by login |
| `get_org_id` | LOOKUP | Move from `gh-project-functions.sh:1028` | Organization's node ID by login |
| `fetch_viewer` | FETCH | New | Current authenticated user info |
| `fetch_user` | FETCH | New | Specific user by login |
| `fetch_organization` | FETCH | New | Organization by login |
| `discover_viewer_organizations` | FETCH | New | List orgs current user belongs to |
| `detect_owner_type` | DETECT | Extract from `gh-workspace-functions.sh` | Is login a user or organization? |
| `check_auth_scopes` | DETECT | Move from `gh-user-functions.sh` | Verify gh auth scopes |

#### GraphQL Queries (gh-identity-graphql-queries.yaml)

```yaml
discovery:
  viewer:
    description: "Get current authenticated user"
    query: |
      query {
        viewer {
          id
          login
          name
          email
          avatarUrl
        }
      }

  viewer_with_orgs:
    description: "Get current user and their organizations"
    query: |
      query {
        viewer {
          id
          login
          name
          organizations(first: 100) {
            nodes {
              id
              login
              name
            }
          }
        }
      }

  specific_user:
    description: "Get specific user by login"
    parameters:
      - name: "login"
        type: "String!"
    query: |
      query($login: String!) {
        user(login: $login) {
          id
          login
          name
          email
          avatarUrl
          company
          location
        }
      }

  specific_organization:
    description: "Get specific organization by login"
    parameters:
      - name: "login"
        type: "String!"
    query: |
      query($login: String!) {
        organization(login: $login) {
          id
          login
          name
          description
          websiteUrl
          isVerified
        }
      }

utilities:
  owner_type_check:
    description: "Check if login is user or organization"
    parameters:
      - name: "login"
        type: "String!"
    query: |
      query($login: String!) {
        user(login: $login) { id }
        organization(login: $login) { id }
      }
```

#### jq Filters (gh-identity-jq-filters.yaml)

```yaml
# Identity-specific filters are minimal since most operations return simple values
format_filters:
  format_viewer:
    description: "Format viewer information"
    filter: |
      {
        login: .data.viewer.login,
        name: .data.viewer.name,
        email: .data.viewer.email,
        id: .data.viewer.id
      }

  format_organizations:
    description: "Format organization list"
    filter: |
      {
        viewer: .data.viewer.login,
        organizations: [.data.viewer.organizations.nodes[] | {
          login: .login,
          name: .name,
          id: .id
        }],
        count: (.data.viewer.organizations.nodes | length)
      }
```

---

### Domain: Repository

**File:** `lib/github/gh-repo-functions.sh`

#### Functions to Implement

| Function | Type | Source | Description |
|----------|------|--------|-------------|
| `get_repo_id` | LOOKUP | Move from `gh-project-functions.sh:1041` | Repository node ID |
| `fetch_repo` | FETCH | New | Repository metadata by owner/name |
| `discover_user_repos` | FETCH | New | List repos for a specific user |
| `discover_org_repos` | FETCH | New | List repos for an organization |
| `discover_viewer_repos` | FETCH | New | List repos for authenticated user |
| `detect_default_branch` | DETECT | Move from `gh-rest-functions.sh` | Get default branch name |
| `detect_repo_visibility` | DETECT | New | public/private/internal |
| `detect_repo_type` | DETECT | Move from `gh-rest-functions.sh` | Fork/source/template |
| `list_branches` | FETCH | Move from `gh-rest-functions.sh` | List repository branches |

#### GraphQL Queries (gh-repo-graphql-queries.yaml)

```yaml
discovery:
  repository:
    description: "Get repository metadata"
    parameters:
      - name: "owner"
        type: "String!"
      - name: "name"
        type: "String!"
    query: |
      query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
          id
          name
          nameWithOwner
          description
          url
          homepageUrl
          isPrivate
          isFork
          isArchived
          isTemplate
          visibility
          defaultBranchRef {
            name
          }
          owner {
            login
            ... on User { id }
            ... on Organization { id }
          }
          primaryLanguage { name }
          languages(first: 10) {
            nodes { name }
          }
          createdAt
          updatedAt
          pushedAt
        }
      }

  user_repositories:
    description: "List repositories for a specific user"
    parameters:
      - name: "login"
        type: "String!"
      - name: "first"
        type: "Int"
    query: |
      query($login: String!, $first: Int = 100) {
        user(login: $login) {
          login
          repositories(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
            nodes {
              id
              name
              nameWithOwner
              description
              isPrivate
              isFork
              isArchived
              visibility
              defaultBranchRef { name }
              updatedAt
            }
            totalCount
          }
        }
      }

  organization_repositories:
    description: "List repositories for an organization"
    parameters:
      - name: "login"
        type: "String!"
      - name: "first"
        type: "Int"
    query: |
      query($login: String!, $first: Int = 100) {
        organization(login: $login) {
          login
          repositories(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
            nodes {
              id
              name
              nameWithOwner
              description
              isPrivate
              isFork
              isArchived
              visibility
              defaultBranchRef { name }
              updatedAt
            }
            totalCount
          }
        }
      }

  viewer_repositories:
    description: "List repositories for authenticated user"
    parameters:
      - name: "first"
        type: "Int"
    query: |
      query($first: Int = 100) {
        viewer {
          login
          repositories(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
            nodes {
              id
              name
              nameWithOwner
              description
              isPrivate
              isFork
              isArchived
              visibility
              defaultBranchRef { name }
              updatedAt
            }
            totalCount
          }
        }
      }

  repository_branches:
    description: "List branches for a repository"
    parameters:
      - name: "owner"
        type: "String!"
      - name: "name"
        type: "String!"
      - name: "first"
        type: "Int"
    query: |
      query($owner: String!, $name: String!, $first: Int = 100) {
        repository(owner: $owner, name: $name) {
          refs(refPrefix: "refs/heads/", first: $first, orderBy: {field: ALPHABETICAL, direction: ASC}) {
            nodes {
              name
              target {
                ... on Commit {
                  oid
                  committedDate
                  message
                }
              }
            }
            totalCount
          }
        }
      }
```

#### jq Filters (gh-repo-jq-filters.yaml)

```yaml
format_filters:
  format_repo:
    description: "Format single repository"
    filter: |
      .data.repository | {
        name: .name,
        fullName: .nameWithOwner,
        description: (.description // ""),
        visibility: .visibility,
        defaultBranch: .defaultBranchRef.name,
        isPrivate: .isPrivate,
        isFork: .isFork,
        isArchived: .isArchived,
        owner: .owner.login,
        url: .url,
        createdAt: .createdAt,
        updatedAt: .updatedAt
      }

  format_repos_list:
    description: "Format repository list"
    filter: |
      {
        owner: (.data.user // .data.organization // .data.viewer).login,
        repositories: [(.data.user // .data.organization // .data.viewer).repositories.nodes[] | {
          name: .name,
          fullName: .nameWithOwner,
          description: (.description // ""),
          visibility: .visibility,
          defaultBranch: (.defaultBranchRef.name // ""),
          isPrivate: .isPrivate,
          updatedAt: .updatedAt
        }],
        totalCount: (.data.user // .data.organization // .data.viewer).repositories.totalCount
      }

  format_branches:
    description: "Format branch list"
    filter: |
      {
        branches: [.data.repository.refs.nodes[] | {
          name: .name,
          sha: .target.oid,
          lastCommit: .target.committedDate,
          message: (.target.message | split("\n")[0])
        }],
        count: .data.repository.refs.totalCount
      }

discovery_filters:
  list_repo_names:
    description: "Extract just repository names"
    filter: |
      [(.data.user // .data.organization // .data.viewer).repositories.nodes[].name]
```

---

## Phase 2a: Work Tracking (P1)

### Domain: Issue

**File:** `lib/github/gh-issue-functions.sh`

#### Functions to Implement

| Function | Type | Source | Description |
|----------|------|--------|-------------|
| `get_issue_id` | LOOKUP | Move from `gh-project-functions.sh:1056` | Issue node ID by number |
| `fetch_issue` | FETCH | New | Full issue data by number |
| `discover_repo_issues` | FETCH | New | List issues in a repository |
| `filter_issues_by_state` | FILTER | New | Filter by OPEN/CLOSED |
| `filter_issues_by_label` | FILTER | New | Filter by label name |
| `filter_issues_by_assignee` | FILTER | New | Filter by assignee login |
| `set_issue_milestone` | MUTATE | Move from `gh-project-functions.sh:289` | Set milestone on issue |
| `clear_issue_milestone` | MUTATE | Move from `gh-project-functions.sh:326` | Clear milestone |
| `add_issue_labels` | MUTATE | New | Add labels to issue |
| `remove_issue_labels` | MUTATE | New | Remove labels from issue |
| `set_issue_assignees` | MUTATE | New | Set assignees on issue |
| `close_issue` | MUTATE | New | Close an issue |
| `reopen_issue` | MUTATE | New | Reopen an issue |
| `format_issue` | FORMAT | New | Single issue display |
| `format_issues_list` | FORMAT | New | Issue list display |

#### GraphQL Queries (gh-issue-graphql-queries.yaml)

```yaml
queries:
  issue_by_number:
    description: "Get issue by number with full details"
    parameters:
      - name: "owner"
        type: "String!"
      - name: "repo"
        type: "String!"
      - name: "number"
        type: "Int!"
    query: |
      query($owner: String!, $repo: String!, $number: Int!) {
        repository(owner: $owner, name: $repo) {
          issue(number: $number) {
            id
            number
            title
            body
            state
            stateReason
            url
            createdAt
            updatedAt
            closedAt
            author { login }
            assignees(first: 10) {
              nodes { login name }
            }
            labels(first: 20) {
              nodes { name color description }
            }
            milestone {
              id
              number
              title
              dueOn
              state
            }
            comments(first: 1) { totalCount }
            reactions { totalCount }
            linkedPullRequests: timelineItems(first: 10, itemTypes: [CONNECTED_EVENT, CROSS_REFERENCED_EVENT]) {
              nodes {
                ... on ConnectedEvent {
                  source {
                    ... on PullRequest { number title state }
                  }
                }
              }
            }
          }
        }
      }

  repository_issues:
    description: "List issues in a repository"
    parameters:
      - name: "owner"
        type: "String!"
      - name: "repo"
        type: "String!"
      - name: "states"
        type: "[IssueState!]"
      - name: "first"
        type: "Int"
    query: |
      query($owner: String!, $repo: String!, $states: [IssueState!] = [OPEN], $first: Int = 100) {
        repository(owner: $owner, name: $repo) {
          issues(first: $first, states: $states, orderBy: {field: UPDATED_AT, direction: DESC}) {
            nodes {
              id
              number
              title
              state
              url
              createdAt
              updatedAt
              author { login }
              assignees(first: 5) {
                nodes { login }
              }
              labels(first: 10) {
                nodes { name color }
              }
              milestone {
                title
                dueOn
              }
              comments(first: 1) { totalCount }
            }
            totalCount
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      }

mutations:
  update_issue:
    description: "Update issue (milestone, labels, assignees, state)"
    parameters:
      - name: "issueId"
        type: "ID!"
      - name: "milestoneId"
        type: "ID"
      - name: "labelIds"
        type: "[ID!]"
      - name: "assigneeIds"
        type: "[ID!]"
      - name: "state"
        type: "IssueState"
    query: |
      mutation($issueId: ID!, $milestoneId: ID, $labelIds: [ID!], $assigneeIds: [ID!], $state: IssueState) {
        updateIssue(input: {
          id: $issueId
          milestoneId: $milestoneId
          labelIds: $labelIds
          assigneeIds: $assigneeIds
          state: $state
        }) {
          issue {
            id
            number
            title
            state
            milestone { title }
            labels(first: 10) { nodes { name } }
            assignees(first: 10) { nodes { login } }
          }
        }
      }

  close_issue:
    description: "Close an issue"
    parameters:
      - name: "issueId"
        type: "ID!"
      - name: "stateReason"
        type: "IssueClosedStateReason"
    query: |
      mutation($issueId: ID!, $stateReason: IssueClosedStateReason = COMPLETED) {
        closeIssue(input: {
          issueId: $issueId
          stateReason: $stateReason
        }) {
          issue {
            id
            number
            state
            stateReason
          }
        }
      }

  reopen_issue:
    description: "Reopen a closed issue"
    parameters:
      - name: "issueId"
        type: "ID!"
    query: |
      mutation($issueId: ID!) {
        reopenIssue(input: {
          issueId: $issueId
        }) {
          issue {
            id
            number
            state
          }
        }
      }

  add_labels:
    description: "Add labels to an issue"
    parameters:
      - name: "labelableId"
        type: "ID!"
      - name: "labelIds"
        type: "[ID!]!"
    query: |
      mutation($labelableId: ID!, $labelIds: [ID!]!) {
        addLabelsToLabelable(input: {
          labelableId: $labelableId
          labelIds: $labelIds
        }) {
          labelable {
            ... on Issue {
              labels(first: 20) { nodes { name } }
            }
          }
        }
      }

  remove_labels:
    description: "Remove labels from an issue"
    parameters:
      - name: "labelableId"
        type: "ID!"
      - name: "labelIds"
        type: "[ID!]!"
    query: |
      mutation($labelableId: ID!, $labelIds: [ID!]!) {
        removeLabelsFromLabelable(input: {
          labelableId: $labelableId
          labelIds: $labelIds
        }) {
          labelable {
            ... on Issue {
              labels(first: 20) { nodes { name } }
            }
          }
        }
      }
```

---

### Domain: Pull Request

**File:** `lib/github/gh-pr-functions.sh`

#### Functions to Implement

| Function | Type | Source | Description |
|----------|------|--------|-------------|
| `get_pr_id` | LOOKUP | Move from `gh-project-functions.sh:1074` | PR node ID by number |
| `fetch_pr` | FETCH | New | Full PR data by number |
| `discover_repo_prs` | FETCH | New | List PRs in a repository |
| `filter_prs_by_state` | FILTER | New | Filter by OPEN/CLOSED/MERGED |
| `filter_prs_by_label` | FILTER | New | Filter by label name |
| `filter_prs_by_assignee` | FILTER | New | Filter by assignee login |
| `filter_prs_by_reviewer` | FILTER | New | Filter by reviewer login |
| `set_pr_milestone` | MUTATE | Move from `gh-project-functions.sh:307` | Set milestone on PR |
| `clear_pr_milestone` | MUTATE | Move from `gh-project-functions.sh:332` | Clear milestone |
| `add_pr_labels` | MUTATE | New | Add labels to PR |
| `remove_pr_labels` | MUTATE | New | Remove labels from PR |
| `set_pr_assignees` | MUTATE | New | Set assignees on PR |
| `request_pr_review` | MUTATE | New | Request reviewers |
| `format_pr` | FORMAT | New | Single PR display |
| `format_prs_list` | FORMAT | New | PR list display |

#### GraphQL Queries (gh-pr-graphql-queries.yaml)

```yaml
queries:
  pr_by_number:
    description: "Get pull request by number with full details"
    parameters:
      - name: "owner"
        type: "String!"
      - name: "repo"
        type: "String!"
      - name: "number"
        type: "Int!"
    query: |
      query($owner: String!, $repo: String!, $number: Int!) {
        repository(owner: $owner, name: $repo) {
          pullRequest(number: $number) {
            id
            number
            title
            body
            state
            url
            isDraft
            mergeable
            merged
            mergedAt
            mergedBy { login }
            createdAt
            updatedAt
            closedAt
            headRefName
            baseRefName
            author { login }
            assignees(first: 10) {
              nodes { login name }
            }
            labels(first: 20) {
              nodes { name color description }
            }
            milestone {
              id
              number
              title
              dueOn
              state
            }
            reviewRequests(first: 10) {
              nodes {
                requestedReviewer {
                  ... on User { login name }
                  ... on Team { name slug }
                }
              }
            }
            reviews(first: 20) {
              nodes {
                author { login }
                state
                submittedAt
              }
            }
            comments(first: 1) { totalCount }
            additions
            deletions
            changedFiles
            commits(first: 1) { totalCount }
          }
        }
      }

  repository_prs:
    description: "List pull requests in a repository"
    parameters:
      - name: "owner"
        type: "String!"
      - name: "repo"
        type: "String!"
      - name: "states"
        type: "[PullRequestState!]"
      - name: "first"
        type: "Int"
    query: |
      query($owner: String!, $repo: String!, $states: [PullRequestState!] = [OPEN], $first: Int = 100) {
        repository(owner: $owner, name: $repo) {
          pullRequests(first: $first, states: $states, orderBy: {field: UPDATED_AT, direction: DESC}) {
            nodes {
              id
              number
              title
              state
              url
              isDraft
              merged
              createdAt
              updatedAt
              headRefName
              baseRefName
              author { login }
              assignees(first: 5) {
                nodes { login }
              }
              labels(first: 10) {
                nodes { name color }
              }
              milestone {
                title
                dueOn
              }
              reviewRequests(first: 5) {
                nodes {
                  requestedReviewer {
                    ... on User { login }
                    ... on Team { slug }
                  }
                }
              }
              reviews(first: 5) {
                nodes {
                  author { login }
                  state
                }
              }
            }
            totalCount
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      }

mutations:
  update_pr:
    description: "Update pull request (milestone, labels, assignees)"
    parameters:
      - name: "prId"
        type: "ID!"
      - name: "milestoneId"
        type: "ID"
      - name: "labelIds"
        type: "[ID!]"
      - name: "assigneeIds"
        type: "[ID!]"
    query: |
      mutation($prId: ID!, $milestoneId: ID, $labelIds: [ID!], $assigneeIds: [ID!]) {
        updatePullRequest(input: {
          pullRequestId: $prId
          milestoneId: $milestoneId
          labelIds: $labelIds
          assigneeIds: $assigneeIds
        }) {
          pullRequest {
            id
            number
            title
            state
            milestone { title }
            labels(first: 10) { nodes { name } }
            assignees(first: 10) { nodes { login } }
          }
        }
      }

  request_reviews:
    description: "Request reviews on a pull request"
    parameters:
      - name: "prId"
        type: "ID!"
      - name: "userIds"
        type: "[ID!]"
      - name: "teamIds"
        type: "[ID!]"
    query: |
      mutation($prId: ID!, $userIds: [ID!], $teamIds: [ID!]) {
        requestReviews(input: {
          pullRequestId: $prId
          userIds: $userIds
          teamIds: $teamIds
        }) {
          pullRequest {
            reviewRequests(first: 10) {
              nodes {
                requestedReviewer {
                  ... on User { login }
                  ... on Team { slug }
                }
              }
            }
          }
        }
      }
```

---

### Domain: Milestone

**File:** `lib/github/gh-milestone-functions.sh`

#### Functions to Implement

| Function | Type | Source | Description |
|----------|------|--------|-------------|
| `get_milestone_id` | LOOKUP | Move from `gh-project-functions.sh:279` | Milestone ID by title |
| `fetch_milestone` | FETCH | Move from `gh-project-functions.sh:265` | Single milestone by number |
| `fetch_repo_milestones` | FETCH | Move from `gh-project-functions.sh:251` | List repo milestones |
| `filter_milestones_by_state` | FILTER | New | Filter OPEN/CLOSED |
| `create_milestone` | MUTATE | Move from `gh-rest-functions.sh` | Create milestone (REST) |
| `update_milestone` | MUTATE | Move from `gh-rest-functions.sh` | Update milestone (REST) |
| `close_milestone` | MUTATE | Move from `gh-rest-functions.sh` | Close milestone (REST) |
| `delete_milestone` | MUTATE | Move from `gh-rest-functions.sh` | Delete milestone (REST) |
| `format_milestone` | FORMAT | New | Single milestone display |
| `format_milestones_list` | FORMAT | Move jq filter | List display |

**Note:** Milestone mutations use REST API (GraphQL doesn't support milestone create/update).

#### GraphQL Queries

Move from `gh-project-graphql-queries.yaml`:
- `milestones.repository_milestones`
- `milestones.milestone_by_number`

#### jq Filters

Move from `gh-project-jq-filters.yaml`:
- `milestone_filters.list_milestones_graphql`
- `milestone_filters.list_milestones_rest`
- `milestone_filters.milestone_progress`

---

### Domain: Project (Clean)

**File:** `lib/github/gh-project-functions.sh` (cleaned)

#### Functions to KEEP

All ProjectsV2-specific functions remain:

**FETCH:**
- `fetch_user_project`, `fetch_org_project`
- `fetch_user_project_fields`, `fetch_org_project_fields`
- `fetch_user_project_page`, `fetch_org_project_page`
- `fetch_user_project_all`, `fetch_org_project_all`
- `fetch_user_project_sorted`, `fetch_org_project_sorted`
- `fetch_project_readme`
- `fetch_project_status_updates`, `get_latest_status_update`
- `fetch_project_views`, `fetch_project_view`
- `fetch_linked_repositories`

**LOOKUP:**
- `get_org_project_id`, `get_user_project_id`
- `get_field_id`, `get_option_id`

**DISCOVER:**
- `discover_user_projects`, `discover_org_projects`
- `discover_repo_projects`, `discover_all_projects`

**FILTER:**
- `apply_universal_filter`, `apply_assignee_filter`
- `apply_repo_filter`, `apply_status_filter`
- `list_repositories`, `list_assignees`, `list_statuses`
- `list_priorities`, `list_reviewers`, `list_linked_prs`
- `list_fields`

**FORMAT:**
- `format_user_projects`, `format_org_projects`
- `format_repo_projects`, `format_all_projects`
- `get_count`, `get_items`

**MUTATE:**
- `update_item_single_select`, `update_item_text`
- `update_item_number`, `update_item_date`
- `update_item_iteration`, `clear_item_field`
- `add_item_to_project`, `add_draft_issue`
- `convert_draft_to_issue`
- `archive_project_item`, `unarchive_project_item`
- `create_project`, `update_project`, `copy_project`
- `create_project_field`, `update_project_field`
- `add_field_option`, `update_field_option`
- `update_project_readme`
- `create_status_update`, `update_status_update`
- `link_repo_to_project`, `unlink_repo_from_project`
- `create_project_view`, `update_project_view`

#### Functions to REMOVE (move to other domains)

| Function | Move To |
|----------|---------|
| `get_user_id` | gh-identity-functions.sh |
| `get_org_id` | gh-identity-functions.sh |
| `get_repo_id` | gh-repo-functions.sh |
| `get_repository_id` | gh-repo-functions.sh (duplicate) |
| `get_issue_id` | gh-issue-functions.sh |
| `get_pr_id` | gh-pr-functions.sh |
| `fetch_repo_milestones` | gh-milestone-functions.sh |
| `fetch_milestone` | gh-milestone-functions.sh |
| `get_milestone_id` | gh-milestone-functions.sh |
| `set_issue_milestone` | gh-issue-functions.sh |
| `set_pr_milestone` | gh-pr-functions.sh |
| `clear_issue_milestone` | gh-issue-functions.sh |
| `clear_pr_milestone` | gh-pr-functions.sh |

---

## Implementation Order

### Recommended Sequence

1. **Identity** - Foundation, no dependencies
2. **Repository** - Depends on Identity for owner type detection
3. **Milestone** - Isolated, needed by Issue and PR
4. **Issue** - Depends on Identity, Repository, Milestone
5. **Pull Request** - Depends on Identity, Repository, Milestone
6. **Project (clean)** - Remove extracted functions, update imports

### For Each Domain

1. Create `gh-{domain}-functions.sh` with function stubs
2. Create `gh-{domain}-graphql-queries.yaml` with query templates
3. Create `gh-{domain}-jq-filters.yaml` with filter templates
4. Implement functions one primitive type at a time (LOOKUP → FETCH → FILTER → FORMAT → MUTATE)
5. Create `gh-{domain}-index.md` documenting all primitives
6. Test composition patterns work

---

## GitHub Issue Structure

### Milestone

**Title:** Architecture Refactor: Domain Segmentation P0-P1a

**Description:**
```markdown
Implement domain-segmented library structure as defined in:
- `knowledge/architecture-principles.md`
- `knowledge/domain-segmentation.md`
- `knowledge/implementation-plan-p0-p1a.md`

## Scope
- **Phase 1 (P0):** Identity, Repository
- **Phase 2a (P1):** Issue, Pull Request, Milestone, Project (clean)

## Deliverables
Each domain: functions.sh + graphql-queries.yaml + jq-filters.yaml + index.md
```

### Issues

1. **[P0] Identity Domain** - `gh-identity-*` files
2. **[P0] Repository Domain** - `gh-repo-*` files
3. **[P1] Milestone Domain** - `gh-milestone-*` files
4. **[P1] Issue Domain** - `gh-issue-*` files
5. **[P1] Pull Request Domain** - `gh-pr-*` files
6. **[P1] Project Domain Cleanup** - Remove extracted functions

---

## Cross-Domain Patterns

### Source Loading

```bash
# Skills should source needed domains
source "$(dirname "$0")/../../lib/github/gh-identity-functions.sh"
source "$(dirname "$0")/../../lib/github/gh-repo-functions.sh"
source "$(dirname "$0")/../../lib/github/gh-issue-functions.sh"
```

### Composition Example

```bash
# Lookup-then-mutate pattern
OWNER_TYPE=$(detect_owner_type "hiivmind")
MILESTONE_ID=$(get_milestone_id "hiivmind" "repo" "v1.0")
ISSUE_ID=$(get_issue_id "hiivmind" "repo" 123)
set_issue_milestone "$ISSUE_ID" "$MILESTONE_ID"
```

### Pipe-First Pattern

```bash
# Filter issues by label and format
discover_repo_issues "hiivmind" "repo" | filter_issues_by_label "bug" | format_issues_list
```
