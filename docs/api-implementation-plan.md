# Architectural Plan: GitHub Projects v2 API Complete Implementation

## Overview

This plan adds all remaining GitHub Projects v2 API features to the existing GitHub Projects Explorer plugin, following established architectural patterns.

## Files to Modify

| File | Purpose |
|------|---------|
| `lib/github/gh-project-graphql-queries.yaml` | Add new GraphQL queries and mutations |
| `lib/github/gh-project-functions.sh` | Add new shell functions |
| `lib/github/gh-project-jq-filters.yaml` | Add new jq filters for data extraction |

---

## Feature 1: Project Status Updates

### Background
GitHub added status updates in June 2024 for sharing project progress (ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, INACTIVE).

### GraphQL Additions (`gh-project-graphql-queries.yaml`)

**New section: `status_updates`**

```yaml
status_updates:
  project_status_updates:
    description: "Get all status updates for a project"
    parameters:
      - name: "projectId"
        type: "ID!"
    query: |
      query($projectId: ID!) {
        node(id: $projectId) {
          ... on ProjectV2 {
            statusUpdates(first: 20) {
              nodes {
                id
                body
                bodyHTML
                status
                startDate
                targetDate
                createdAt
                updatedAt
                creator {
                  login
                  name
                }
              }
            }
          }
        }
      }
```

**New mutations:**
- `create_status_update` - Create new status update
- `update_status_update` - Modify existing update

### Shell Functions (`gh-project-functions.sh`)

**New section: `# STATUS UPDATE FUNCTIONS`**

```bash
# Query functions
fetch_project_status_updates()     # Get all status updates
get_latest_status_update()         # Get most recent update

# Mutation functions
create_status_update()             # Create new status update
update_status_update()             # Modify existing update
```

### jq Filters (`gh-project-jq-filters.yaml`)

**New section: `status_update_filters`**

```yaml
status_update_filters:
  format_status_updates:
    description: "Format status updates for display"
  filter_by_status:
    description: "Filter updates by status value"
```

---

## Feature 2: Project Views & Layouts

### Background
Projects support multiple views (table, board, roadmap) with custom sorting, filtering, and grouping.

### GraphQL Additions

**New section: `views`**

```yaml
views:
  project_views:
    description: "Get all views for a project"
    # Returns: id, name, number, layout (TABLE, BOARD, ROADMAP)
    # Plus: sortBy, groupBy, filter settings

  project_view_by_number:
    description: "Get specific view configuration"
```

**New mutations:**
- `create_view` - Create new project view
- `update_view` - Modify view settings (name, layout, sorting, grouping)

### Shell Functions

**New section: `# VIEW FUNCTIONS`**

```bash
# Query functions
fetch_project_views()              # List all views
fetch_project_view()               # Get specific view config

# Mutation functions
create_project_view()              # Create new view
update_project_view()              # Modify view settings
```

### jq Filters

```yaml
view_filters:
  list_views:
    description: "Extract view names and layouts"
  format_view_config:
    description: "Format view configuration details"
```

---

## Feature 3: Field Management Updates

### Background
Missing: `updateProjectV2Field` and `updateProjectV2SingleSelectFieldOption` for modifying existing fields.

### GraphQL Additions (to `mutations` section)

```yaml
mutations:
  # Add to existing mutations section
  update_field:
    description: "Update field settings (name, etc.)"

  update_single_select_option:
    description: "Update a single-select option (name, color, description)"

  create_single_select_option:
    description: "Add new option to single-select field"
```

### Shell Functions

**Add to `# MUTATION FUNCTIONS - Field Management`**

```bash
update_project_field()             # Rename field or update settings
update_field_option()              # Modify single-select option
add_field_option()                 # Add new option to single-select
```

---

## Feature 4: Repository Linking

### Background
Projects can be linked to repositories for easier access.

### GraphQL Additions

**To `project_structure` section:**

```yaml
project_structure:
  project_linked_repositories:
    description: "Get repositories linked to a project"
```

**To `mutations` section:**

```yaml
mutations:
  link_repository:
    description: "Link a repository to a project"

  unlink_repository:
    description: "Unlink a repository from a project"
```

### Shell Functions

```bash
# Query
fetch_linked_repositories()        # List linked repos

# Mutations
link_repo_to_project()             # Link a repository
unlink_repo_from_project()         # Unlink a repository
```

### jq Filters

```yaml
repository_filters:
  list_linked_repositories:
    description: "Extract linked repository information"
```

---

## Feature 5: Additional Field Value Types

### Background
Current implementation missing: Reviewers, Linked Branches, Linked PRs, Tracks/TrackedBy relationships.

### GraphQL Additions

**Enhance existing item queries to include:**

```graphql
fieldValues(first: 30) {
  nodes {
    # Existing types...

    # NEW: Add these fragments
    ... on ProjectV2ItemFieldReviewersValue {
      reviewers(first: 10) {
        nodes {
          ... on User { login name }
          ... on Team { name slug }
        }
      }
      field { ... on ProjectV2Field { name } }
    }

    ... on ProjectV2ItemFieldLinkedBranchesValue {
      linkedBranches(first: 10) {
        nodes {
          ref
          repository { name owner { login } }
        }
      }
      field { ... on ProjectV2Field { name } }
    }

    ... on ProjectV2ItemFieldPullRequestsValue {
      pullRequests(first: 10) {
        nodes {
          number
          title
          state
          url
        }
      }
      field { ... on ProjectV2Field { name } }
    }
  }
}
```

**Enhance content queries to include tracking relationships:**

```graphql
content {
  ... on Issue {
    # Existing fields...

    # NEW: Tracking relationships
    trackedIssues(first: 10) {
      nodes { number title state }
    }
    trackedInIssues(first: 10) {
      nodes { number title state }
    }
  }
}
```

### jq Filters

```yaml
field_value_filters:
  list_reviewers:
    description: "Extract all reviewers across items"
  list_linked_branches:
    description: "Extract all linked branches"
  list_tracked_issues:
    description: "Extract tracking relationships"
```

---

## Feature 6: Server-Side Sorting

### Background
The `items` connection supports `orderBy` parameter for server-side sorting.

### GraphQL Additions

**New paginated queries with sorting:**

```yaml
pagination:
  user_project_items_sorted:
    description: "Get items with server-side sorting"
    parameters:
      - name: "orderField"
        type: "ProjectV2ItemOrderField"
        description: "POSITION, CREATED_AT, UPDATED_AT"
      - name: "orderDirection"
        type: "OrderDirection"
        description: "ASC or DESC"
    query: |
      query($projectNumber: Int!, $first: Int = 100, $after: String,
            $orderField: ProjectV2ItemOrderField = POSITION,
            $orderDirection: OrderDirection = ASC) {
        viewer {
          projectV2(number: $projectNumber) {
            items(first: $first, after: $after,
                  orderBy: {field: $orderField, direction: $orderDirection}) {
              # ... existing fields
            }
          }
        }
      }
```

### Shell Functions

```bash
# Enhanced fetch functions with sorting
fetch_user_project_sorted()        # Fetch with orderBy
fetch_org_project_sorted()         # Fetch with orderBy
```

---

## Feature 7: Milestone Management

### Background
Milestones are repository-level entities assigned to issues/PRs. The `ProjectV2ItemFieldMilestoneValue` in Projects is **read-only** - it reflects the milestone on the underlying issue. To set milestones, you must use `updateIssue` mutation.

### GraphQL Additions

**New section: `milestones`**

```yaml
milestones:
  repository_milestones:
    description: "List all milestones in a repository"
    parameters:
      - name: "owner"
        type: "String!"
      - name: "repo"
        type: "String!"
      - name: "states"
        type: "[MilestoneState!]"
        description: "OPEN, CLOSED, or both"
    query: |
      query($owner: String!, $repo: String!, $states: [MilestoneState!] = [OPEN]) {
        repository(owner: $owner, name: $repo) {
          milestones(first: 100, states: $states) {
            nodes {
              id
              number
              title
              description
              dueOn
              state
              closed
              closedAt
              createdAt
              updatedAt
              url
              progressPercentage
              issues(first: 1) { totalCount }
            }
          }
        }
      }

  milestone_by_number:
    description: "Get specific milestone by number"
    query: |
      query($owner: String!, $repo: String!, $number: Int!) {
        repository(owner: $owner, name: $repo) {
          milestone(number: $number) {
            id
            number
            title
            description
            dueOn
            state
            progressPercentage
          }
        }
      }
```

**New mutations (to `mutations` section):**

```yaml
mutations:
  set_issue_milestone:
    description: "Set or update milestone on an issue"
    parameters:
      - name: "issueId"
        type: "ID!"
        description: "Issue node ID (from project item content)"
      - name: "milestoneId"
        type: "ID"
        description: "Milestone node ID (null to clear)"
    query: |
      mutation($issueId: ID!, $milestoneId: ID) {
        updateIssue(input: {
          id: $issueId
          milestoneId: $milestoneId
        }) {
          issue {
            id
            number
            milestone {
              id
              title
            }
          }
        }
      }

  set_pr_milestone:
    description: "Set or update milestone on a pull request"
    parameters:
      - name: "prId"
        type: "ID!"
      - name: "milestoneId"
        type: "ID"
    query: |
      mutation($prId: ID!, $milestoneId: ID) {
        updatePullRequest(input: {
          pullRequestId: $prId
          milestoneId: $milestoneId
        }) {
          pullRequest {
            id
            number
            milestone {
              id
              title
            }
          }
        }
      }
```

**Note:** Creating milestones requires REST API (no GraphQL mutation):
```bash
gh api repos/OWNER/REPO/milestones -X POST -f title="v1.0" -f due_on="2024-12-31T00:00:00Z"
```

### Shell Functions

```bash
# Query functions
fetch_repo_milestones()            # List milestones in a repository
fetch_milestone()                  # Get specific milestone by number
get_milestone_id()                 # Helper: get milestone ID by title

# Mutation functions
set_issue_milestone()              # Set milestone on issue
set_pr_milestone()                 # Set milestone on PR
clear_issue_milestone()            # Clear milestone (convenience wrapper)

# REST-based (no GraphQL equivalent)
create_milestone()                 # Create new milestone via REST API
update_milestone()                 # Update milestone via REST API
close_milestone()                  # Close milestone via REST API
```

### jq Filters

```yaml
milestone_filters:
  list_milestones:
    description: "Format milestone list"
  milestone_progress:
    description: "Show milestone completion stats"
```

---

## Feature 8: Project README

### Background
Projects have a full README field beyond just shortDescription.

### GraphQL Additions

**Enhance discovery queries to include README:**

```yaml
discovery:
  user_projects:
    # Add to existing query:
    # readme

  project_readme:
    description: "Get full project README"
    query: |
      query($projectId: ID!) {
        node(id: $projectId) {
          ... on ProjectV2 {
            readme
            shortDescription
          }
        }
      }
```

**Add mutation for updating README:**

```yaml
mutations:
  update_project_readme:
    description: "Update project README content"
```

### Shell Functions

```bash
fetch_project_readme()             # Get project README
update_project_readme()            # Update README content
```

---

## Implementation Order

### Phase 1: Enhanced Field Values (Low Risk)
1. Add new field value type fragments to existing queries
2. Add tracking relationship fields to content queries
3. Add corresponding jq filters
4. **No new mutations - read-only enhancements**

### Phase 2: Server-Side Sorting (Low Risk)
1. Add sorted query variants
2. Add shell functions with orderBy parameters
3. **No new mutations - read-only enhancements**

### Phase 3: Project README (Low Risk)
1. Enhance discovery queries with readme field
2. Add project_readme query
3. Add update_project_readme mutation and function

### Phase 4: Milestone Management (Medium Risk)
1. Add milestones query section (repository-level)
2. Add set_issue_milestone and set_pr_milestone mutations
3. Add shell functions including REST-based create/update/close
4. Add jq filters for milestone formatting
5. **Note:** Milestones are issue/PR properties, not project fields

### Phase 5: Status Updates (Medium Risk)
1. Add status_updates query section
2. Add all status update mutations
3. Add shell functions
4. Add jq filters for formatting

### Phase 6: Field Management (Medium Risk)
1. Add field update mutations
2. Add single-select option management mutations
3. Add corresponding shell functions

### Phase 7: Repository Linking (Medium Risk)
1. Add linked_repositories query
2. Add link/unlink mutations
3. Add shell functions

### Phase 8: Project Views (Higher Complexity)
1. Add views query section
2. Add view mutations (create, update)
3. Add shell functions
4. Add jq filters

---

## New YAML Section Structure

After implementation, the `gh-project-graphql-queries.yaml` will have these sections:

```yaml
discovery:           # Existing - enhanced with readme
project_structure:   # Existing - enhanced with linked_repositories
item_queries:        # Existing - enhanced with new field value types
filtering:           # Existing
utilities:           # Existing
pagination:          # Existing - add sorted variants
milestones:          # NEW - repository-level milestone queries
status_updates:      # NEW
views:               # NEW
mutations:           # Existing - many additions (including updateIssue/updatePullRequest for milestones)
field_types:         # Existing reference
examples:            # Existing
```

---

## New Shell Function Organization

After implementation, `gh-project-functions.sh` will have these sections:

```bash
# =============================================================================
# DATA FETCHING FUNCTIONS (existing, enhanced)
# =============================================================================

# =============================================================================
# FILTER FUNCTIONS (existing)
# =============================================================================

# =============================================================================
# DISCOVERY FUNCTIONS (existing, enhanced)
# =============================================================================

# =============================================================================
# PAGINATION FUNCTIONS (existing, enhanced with sorting)
# =============================================================================

# =============================================================================
# MILESTONE FUNCTIONS (NEW - repository-level)
# =============================================================================

# =============================================================================
# STATUS UPDATE FUNCTIONS (NEW)
# =============================================================================

# =============================================================================
# VIEW FUNCTIONS (NEW)
# =============================================================================

# =============================================================================
# MUTATION FUNCTIONS - Field Updates (existing)
# =============================================================================

# =============================================================================
# MUTATION FUNCTIONS - Item Management (existing)
# =============================================================================

# =============================================================================
# MUTATION FUNCTIONS - Issue/PR Updates (NEW - for milestones, labels, assignees)
# =============================================================================

# =============================================================================
# MUTATION FUNCTIONS - Project Management (existing, enhanced)
# =============================================================================

# =============================================================================
# MUTATION FUNCTIONS - Field Management (existing, enhanced)
# =============================================================================

# =============================================================================
# MUTATION FUNCTIONS - Repository Linking (NEW)
# =============================================================================

# =============================================================================
# HELPER FUNCTIONS - ID Lookups (existing, enhanced with milestone lookups)
# =============================================================================
```

---

## Safety Considerations

### Mutations EXCLUDED (per user decision - no delete operations):
- `deleteProjectV2StatusUpdate` - EXCLUDED
- `deleteProjectV2View` - EXCLUDED
- `deleteProjectV2SingleSelectFieldOption` - EXCLUDED
- `deleteProjectV2Item` - Already excluded
- `deleteProjectV2` - Already excluded
- `deleteProjectV2Field` - Already excluded

All delete operations are intentionally omitted for safety.

---

## Estimated Scope

| Component | New Queries | New Mutations | New Functions | New Filters |
|-----------|-------------|---------------|---------------|-------------|
| Status Updates | 2 | 2 | 3 | 2 |
| Views | 2 | 2 | 4 | 2 |
| Field Management | 0 | 3 | 3 | 0 |
| Repository Linking | 1 | 2 | 3 | 1 |
| Field Value Types | 0 (enhancements) | 0 | 0 | 3 |
| Sorting | 2 | 0 | 2 | 0 |
| Milestones | 2 | 2 | 6 (+3 REST) | 2 |
| README | 1 | 1 | 2 | 0 |
| **Total** | **10** | **12** | **23** (+3 REST) | **10** |

Plus enhancements to ~6 existing queries for new field types.

---

## Summary

This plan adds comprehensive support for all remaining GitHub Projects v2 API features:

1. **Project Status Updates** - Track project health with ON_TRACK/AT_RISK/OFF_TRACK status
2. **Project Views** - Query and create custom table/board/roadmap views
3. **Field Management** - Update fields and single-select options
4. **Repository Linking** - Link/unlink repos to projects
5. **Enhanced Field Values** - Reviewers, linked branches, tracked issues
6. **Server-Side Sorting** - orderBy support for efficient queries
7. **Milestone Management** - Query, set, and manage milestones on issues/PRs
8. **Project README** - Full README access and updates

**Important Note on Milestones:**
Milestones are repository-level entities assigned to issues/PRs. They appear in Projects as read-only field values. To set a milestone, use `updateIssue` or `updatePullRequest` mutations, not ProjectV2 mutations.

All implementations follow existing architectural patterns:
- YAML-driven query templates
- Process substitution for YAML extraction
- Pipeline-composable functions
- Dual user/org context support
- No delete operations for safety
