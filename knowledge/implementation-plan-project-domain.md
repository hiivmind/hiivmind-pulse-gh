# Implementation Plan: Project Domain Completion

> **Document ID:** IMPL-002
> **Created:** 2025-12-11
> **Status:** Active Implementation Plan
> **Relates To:** GitHub Issue (TBD), extends IMPL-001

This document provides a complete specification for the Project domain, addressing gaps identified after the initial P0-P1a implementation. The Project domain was originally marked as "cleanup only" but requires full specification to achieve architectural alignment.

---

## Problem Statement

### Gap Analysis from Issue #14

Issue #14 ("Project Domain Cleanup") was closed with incomplete work:

| Acceptance Criteria | Status | Details |
|---------------------|--------|---------|
| Non-Project functions removed from `.sh` | ✅ Done | Deprecation comments added |
| Non-Project queries moved from `.yaml` | ❌ Not Done | milestones, mutations still present |
| Non-Project filters moved from `.yaml` | ❌ Not Done | milestone_filters still present |
| Pure ProjectsV2 focus | ⚠️ Partial | Code clean, YAML files dirty |
| Index documentation | ❌ Missing | No gh-project-index.md |

### Root Cause

The implementation plan (IMPL-001) specified full function tables for Identity, Repository, Milestone, Issue, and PR domains, but only listed "functions to KEEP/REMOVE" for Project domain without a proper specification.

---

## Scope

### In Scope
1. Complete specification of all Project domain primitives
2. Clean `gh-project-graphql-queries.yaml` (remove non-project queries)
3. Clean `gh-project-jq-filters.yaml` (remove non-project filters)
4. Create `gh-project-index.md` documentation
5. Verify `gh-project-functions.sh` is complete

### Out of Scope
- New functionality beyond what already exists
- Skill updates (deferred to future work)
- Migration of existing callers

---

## Project Domain Specification

### Domain Boundaries

The Project domain covers **GitHub Projects v2** exclusively:
- Projects (boards for cross-repo planning)
- Project Items (issues, PRs, draft issues in a project)
- Project Fields (Status, Priority, custom fields)
- Project Views (Table, Board, Roadmap layouts)
- Project Status Updates (health tracking)
- Repository Linking (connecting repos to projects)

**NOT in Project domain:**
- Issues (→ Issue domain)
- Pull Requests (→ PR domain)
- Milestones (→ Milestone domain)
- Users/Organizations (→ Identity domain)
- Repositories (→ Repository domain)

### Primitive Classification

Following ARCH-001, every primitive is classified into exactly one type:

| Type | Count | Pattern |
|------|-------|---------|
| FETCH | 10 | `fetch_{scope}_project*` |
| DISCOVER | 4 | `discover_{scope}_projects` |
| LOOKUP | 4 | `get_{entity}_id` |
| FILTER | 4 | `apply_{criteria}_filter` |
| EXTRACT | 6 | `list_{what}` |
| FORMAT | 5 | `format_{scope}_projects` |
| MUTATE | 22 | `create_*`, `update_*`, `add_*`, etc. |
| UTILITY | 2 | `get_count`, `get_items` |

**Total: 57 primitives**

---

## Function Specifications

### FETCH Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `fetch_user_project` | `project_number` | JSON | User project with items |
| `fetch_org_project` | `project_number`, `org_login` | JSON | Org project with items |
| `fetch_user_project_fields` | `project_number` | JSON | User project field structure |
| `fetch_org_project_fields` | `project_number`, `org_login` | JSON | Org project field structure |
| `fetch_user_project_page` | `project_number`, `cursor?`, `page_size?` | JSON | Paginated user project items |
| `fetch_org_project_page` | `project_number`, `org_login`, `cursor?`, `page_size?` | JSON | Paginated org project items |
| `fetch_user_project_all` | `project_number`, `page_size?` | JSON | All user project items (auto-pagination) |
| `fetch_org_project_all` | `project_number`, `org_login`, `page_size?` | JSON | All org project items (auto-pagination) |
| `fetch_user_project_sorted` | `project_number`, `order_field?`, `order_direction?`, `page_size?`, `cursor?` | JSON | Sorted user project items |
| `fetch_org_project_sorted` | `project_number`, `org_login`, `order_field?`, `order_direction?`, `page_size?`, `cursor?` | JSON | Sorted org project items |
| `fetch_project_readme` | `project_id` | JSON | Project README content |
| `fetch_project_status_updates` | `project_id` | JSON | All status updates |
| `get_latest_status_update` | `project_id` | JSON | Most recent status update |
| `fetch_project_views` | `project_id` | JSON | All project views |
| `fetch_project_view` | `project_id`, `view_number` | JSON | Specific view by number |
| `fetch_linked_repositories` | `project_id` | JSON | Repositories linked to project |

### DISCOVER Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `discover_user_projects` | - | JSON | List viewer's projects |
| `discover_org_projects` | `org_login` | JSON | List org's projects |
| `discover_repo_projects` | `owner`, `repo` | JSON | List projects linked to repo |
| `discover_all_projects` | - | JSON | List all accessible projects (user + orgs) |

### LOOKUP Primitives

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_user_project_id` | `project_number` | ID string | User project node ID |
| `get_org_project_id` | `project_number`, `org_login` | ID string | Org project node ID |
| `get_field_id` | `project_id`, `field_name` | ID string | Field node ID by name |
| `get_option_id` | `project_id`, `field_name`, `option_name` | ID string | Single-select option ID |

### FILTER Primitives (stdin → stdout)

| Function | Args | Input | Output | Description |
|----------|------|-------|--------|-------------|
| `apply_universal_filter` | `repo?`, `assignee?`, `status?`, `priority?` | Project JSON | Filtered JSON | Multi-criteria filter |
| `apply_assignee_filter` | `assignee` | Project JSON | Filtered JSON | Filter by assignee |
| `apply_repo_filter` | `repo` | Project JSON | Filtered JSON | Filter by repository |
| `apply_status_filter` | `status` | Project JSON | Filtered JSON | Filter by status value |

### EXTRACT Primitives (stdin → stdout)

| Function | Args | Input | Output | Description |
|----------|------|-------|--------|-------------|
| `list_repositories` | - | Project JSON | JSON array | Unique repository names |
| `list_assignees` | - | Project JSON | JSON array | Unique assignee logins |
| `list_statuses` | - | Project JSON | JSON array | Unique status values |
| `list_priorities` | - | Project JSON | JSON array | Unique priority values |
| `list_reviewers` | - | Project JSON | JSON object | Users and teams |
| `list_linked_prs` | - | Project JSON | JSON array | Linked pull requests |
| `list_fields` | - | Fields JSON | JSON array | Field structure |

### FORMAT Primitives (stdin → stdout)

| Function | Args | Input | Output | Description |
|----------|------|-------|--------|-------------|
| `format_user_projects` | - | Discovery JSON | Formatted JSON | Format user projects |
| `format_org_projects` | `org_name` | Discovery JSON | Formatted JSON | Format org projects |
| `format_repo_projects` | `owner`, `repo` | Discovery JSON | Formatted JSON | Format repo projects |
| `format_all_projects` | - | Discovery JSON | Formatted JSON | Format all projects |

### UTILITY Functions

| Function | Args | Input | Output | Description |
|----------|------|-------|--------|-------------|
| `get_count` | - | Filtered JSON | Number | Get filtered item count |
| `get_items` | - | Filtered JSON | JSON array | Get items array |

### MUTATE Primitives - Field Updates

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `update_item_single_select` | `project_id`, `item_id`, `field_id`, `option_id` | Result JSON | Update single-select field |
| `update_item_text` | `project_id`, `item_id`, `field_id`, `text` | Result JSON | Update text field |
| `update_item_number` | `project_id`, `item_id`, `field_id`, `number` | Result JSON | Update number field |
| `update_item_date` | `project_id`, `item_id`, `field_id`, `date` | Result JSON | Update date field (ISO 8601) |
| `update_item_iteration` | `project_id`, `item_id`, `field_id`, `iteration_id` | Result JSON | Update iteration field |
| `clear_item_field` | `project_id`, `item_id`, `field_id` | Result JSON | Clear field value |

### MUTATE Primitives - Item Management

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `add_item_to_project` | `project_id`, `content_id` | Result JSON | Add issue/PR to project |
| `add_draft_issue` | `project_id`, `title`, `body?` | Result JSON | Create draft issue |
| `convert_draft_to_issue` | `project_id`, `item_id`, `repository_id` | Result JSON | Convert draft to real issue |
| `archive_project_item` | `project_id`, `item_id` | Result JSON | Archive item |
| `unarchive_project_item` | `project_id`, `item_id` | Result JSON | Unarchive item |

### MUTATE Primitives - Project Management

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `create_project` | `owner_id`, `title` | Result JSON | Create new project |
| `update_project` | `project_id`, `title?`, `description?`, `closed?`, `public?` | Result JSON | Update project settings |
| `copy_project` | `project_id`, `owner_id`, `title`, `include_drafts?` | Result JSON | Copy project |
| `update_project_readme` | `project_id`, `readme_content` | Result JSON | Update README |

### MUTATE Primitives - Field Management

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `create_project_field` | `project_id`, `data_type`, `name`, `options?` | Result JSON | Create custom field |
| `update_project_field` | `field_id`, `name` | Result JSON | Rename field |
| `add_field_option` | `field_id`, `name`, `color`, `description?` | Result JSON | Add single-select option |
| `update_field_option` | `option_id`, `name?`, `color?`, `description?` | Result JSON | Update option |

### MUTATE Primitives - Status Updates

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `create_status_update` | `project_id`, `status`, `body?`, `start_date?`, `target_date?` | Result JSON | Create status update |
| `update_status_update` | `status_update_id`, `status?`, `body?`, `start_date?`, `target_date?` | Result JSON | Update existing |

### MUTATE Primitives - Repository Linking

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `link_repo_to_project` | `project_id`, `repository_id` | Result JSON | Link repo to project |
| `unlink_repo_from_project` | `project_id`, `repository_id` | Result JSON | Unlink repo |

### MUTATE Primitives - Views

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `create_project_view` | `project_id`, `name`, `layout?` | Result JSON | Create view (TABLE/BOARD/ROADMAP) |
| `update_project_view` | `view_id`, `name?`, `layout?` | Result JSON | Update view settings |

---

## GraphQL Queries Specification

### Queries to KEEP (Project-specific)

| Category | Query Key | Description |
|----------|-----------|-------------|
| discovery | `user_projects` | List user's projects |
| discovery | `organization_projects` | List org's projects (via viewer) |
| discovery | `specific_organization_projects` | List specific org's projects |
| discovery | `repository_projects` | List repo's linked projects |
| project_structure | `project_fields` | User project fields |
| project_structure | `organization_project_fields` | Org project fields |
| item_queries | `user_project_items_full` | Full user project with items |
| item_queries | `organization_project_items_full` | Full org project with items |
| filtering | `items_by_repository` | Items filtered by repo |
| filtering | `items_by_assignee` | Items filtered by assignee |
| filtering | `items_by_status` | Items filtered by status |
| utilities | `project_by_id` | Project by node ID |
| utilities | `project_summary` | Quick status summary |
| utilities | `project_readme` | README content |
| status_updates | `project_status_updates` | All status updates |
| status_updates | `latest_status_update` | Most recent update |
| views | `project_views` | All project views |
| views | `project_view_by_number` | Specific view |
| repository_linking | `project_linked_repositories` | Linked repos |
| pagination | `user_project_items_paginated` | Paginated user items |
| pagination | `organization_project_items_paginated` | Paginated org items |
| pagination | `user_project_items_sorted` | Sorted user items |
| pagination | `organization_project_items_sorted` | Sorted org items |

### Queries to REMOVE (moved to other domains)

| Query Key | Now In | Action |
|-----------|--------|--------|
| `discovery.current_user_info` | gh-identity-graphql-queries.yaml (`viewer`) | DELETE |
| `milestones.repository_milestones` | gh-milestone-graphql-queries.yaml | DELETE |
| `milestones.milestone_by_number` | gh-milestone-graphql-queries.yaml | DELETE |

### Mutations to KEEP (Project-specific)

| Mutation Key | Description |
|--------------|-------------|
| `update_item_field_single_select` | Update single-select value |
| `update_item_field_text` | Update text value |
| `update_item_field_number` | Update number value |
| `update_item_field_date` | Update date value |
| `update_item_field_iteration` | Update iteration value |
| `clear_item_field` | Clear field value |
| `add_item_by_id` | Add issue/PR to project |
| `add_draft_issue` | Create draft issue |
| `convert_draft_to_issue` | Convert draft to issue |
| `archive_item` | Archive project item |
| `unarchive_item` | Unarchive item |
| `create_project` | Create new project |
| `update_project` | Update project settings |
| `copy_project` | Copy project |
| `create_field` | Create custom field |
| `update_field` | Update field name |
| `create_single_select_option` | Add option |
| `update_single_select_option` | Update option |
| `update_project_readme` | Update README |
| `create_status_update` | Create status update |
| `update_status_update` | Update status update |
| `link_repository` | Link repo to project |
| `unlink_repository` | Unlink repo |
| `create_view` | Create project view |
| `update_view` | Update view |

### Mutations to REMOVE (moved to other domains)

| Mutation Key | Now In | Action |
|--------------|--------|--------|
| `set_issue_milestone` | gh-issue-graphql-queries.yaml | DELETE |
| `set_pr_milestone` | gh-pr-graphql-queries.yaml | DELETE |

---

## jq Filters Specification

### Filters to KEEP (Project-specific)

| Category | Filter Key | Description |
|----------|------------|-------------|
| basic_filters | `no_filter` | Return all project data |
| basic_filters | `repository_filter` | Filter by repo |
| basic_filters | `assignee_filter` | Filter by assignee |
| basic_filters | `status_filter` | Filter by status |
| basic_filters | `priority_filter` | Filter by priority |
| combined_filters | `repo_and_assignee` | Multi-filter |
| combined_filters | `repo_and_status` | Multi-filter |
| combined_filters | `assignee_and_status` | Multi-filter |
| combined_filters | `universal_filter` | All criteria filter |
| discovery_filters | `list_repositories` | Extract repos |
| discovery_filters | `list_assignees` | Extract assignees |
| discovery_filters | `list_statuses` | Extract statuses |
| discovery_filters | `list_priorities` | Extract priorities |
| discovery_filters | `list_reviewers` | Extract reviewers |
| discovery_filters | `list_linked_prs` | Extract PRs |
| discovery_filters | `list_fields` | Extract field structure |
| discovery_filters | `format_user_projects` | Format user projects |
| discovery_filters | `format_org_projects` | Format org projects |
| discovery_filters | `format_repo_projects` | Format repo projects |
| discovery_filters | `format_all_projects` | Format all projects |
| view_filters | `list_views` | Format views list |
| view_filters | `format_view_config` | Format view config |
| repository_filters | `list_linked_repositories` | Format linked repos |
| status_update_filters | `format_status_updates` | Format updates |
| status_update_filters | `filter_by_status` | Filter by status value |
| status_update_filters | `latest_status` | Extract latest |

### Filters to REMOVE (moved to other domains)

| Filter Key | Now In | Action |
|------------|--------|--------|
| `milestone_filters.list_milestones_graphql` | gh-milestone-jq-filters.yaml | DELETE |
| `milestone_filters.list_milestones_rest` | gh-milestone-jq-filters.yaml | DELETE |
| `milestone_filters.milestone_progress` | gh-milestone-jq-filters.yaml | DELETE |

### Filters to EVALUATE

| Filter Key | Decision | Rationale |
|------------|----------|-----------|
| `workspace_filters.transform_project_fields` | KEEP | Used by workspace-init for config.yaml |
| `workspace_filters.format_discovered_projects` | KEEP | Used by workspace-init |
| `workspace_filters.format_repository_for_config` | MOVE to gh-repo-jq-filters.yaml | Repository-focused |
| `workspace_filters.count_fields_by_type` | KEEP | Project field analysis |

---

## Implementation Tasks

### Task 1: Clean gh-project-graphql-queries.yaml

**Remove these sections:**
1. Lines 5-16: `discovery.current_user_info` (duplicate of identity domain)
2. Lines 982-1055: `milestones.*` section (entire section)
3. Lines 2478-2534: `mutations.set_issue_milestone` and `mutations.set_pr_milestone`

**Estimated lines removed:** ~130 lines

### Task 2: Clean gh-project-jq-filters.yaml

**Remove these sections:**
1. Lines 545-609: `milestone_filters.*` section (entire section)

**Move to gh-repo-jq-filters.yaml:**
1. `workspace_filters.format_repository_for_config` (lines 665-676)

**Estimated lines removed:** ~75 lines

### Task 3: Verify gh-project-functions.sh

The functions file was already cleaned in issue #14. Verify:
- No milestone functions remain (✅ deprecation comments in place)
- No ID lookup functions for non-project entities (✅ deprecation comments)
- All MUTATE primitives present and working

### Task 4: Create gh-project-index.md

Create comprehensive index documentation:
- Quick reference table (all 57 primitives)
- Detailed function documentation with examples
- GraphQL queries reference
- jq filters reference
- Composition examples

### Task 5: Update CLAUDE.md

Update the Key Function Groups section to reflect:
- Clean Project domain description
- Reference to gh-project-index.md

---

## Acceptance Criteria

1. [ ] `gh-project-graphql-queries.yaml` contains ONLY ProjectsV2 queries/mutations
2. [ ] `gh-project-jq-filters.yaml` contains ONLY ProjectsV2 filters
3. [ ] `gh-project-index.md` exists with full documentation
4. [ ] No duplicate queries/filters across domain files
5. [ ] All existing project functions still work (no regressions)

---

## Testing Plan

### Smoke Tests

```bash
# Source and test core functions
source lib/github/gh-project-functions.sh

# Test discovery
discover_org_projects "hiivmind" | jq '.data.organization.projectsV2.nodes | length'

# Test fetch
fetch_org_project_fields 2 "hiivmind" | list_fields | jq '.fields | length'

# Test lookup
get_org_project_id 2 "hiivmind"

# Test filter
fetch_org_project 2 "hiivmind" | apply_status_filter "Done" | get_count
```

### Regression Tests

Verify these common patterns still work:
1. `discover_org_projects | format_org_projects`
2. `fetch_org_project | apply_assignee_filter | list_repositories`
3. `get_org_project_id` + `get_field_id` + `update_item_single_select`

---

## Related Documents

- **ARCH-001:** Architecture Principles & Design Patterns
- **ARCH-002:** Domain Segmentation Analysis
- **IMPL-001:** Implementation Plan P0-P1a (Identity, Repo, Milestone, Issue, PR)
