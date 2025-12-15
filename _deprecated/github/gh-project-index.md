# Project Domain Index

> **Domain:** Projects v2
> **Files:** `gh-project-functions.sh`, `gh-project-graphql-queries.yaml`, `gh-project-jq-filters.yaml`
> **Last Updated:** 2025-12-11

This index documents all primitives for GitHub Projects v2 operations.

---

## Quick Reference

| Function | Type | Description |
|----------|------|-------------|
| `discover_user_projects` | DISCOVER | List viewer's projects |
| `discover_org_projects` | DISCOVER | List organization's projects |
| `discover_repo_projects` | DISCOVER | List projects linked to repository |
| `discover_all_projects` | DISCOVER | List all accessible projects |
| `fetch_user_project` | FETCH | Get user project with items |
| `fetch_org_project` | FETCH | Get org project with items |
| `fetch_user_project_fields` | FETCH | Get user project field structure |
| `fetch_org_project_fields` | FETCH | Get org project field structure |
| `fetch_project_status_updates` | FETCH | Get project status updates |
| `fetch_project_views` | FETCH | Get project views |
| `fetch_linked_repositories` | FETCH | Get linked repositories |
| `get_user_project_id` | LOOKUP | Get user project node ID |
| `get_org_project_id` | LOOKUP | Get org project node ID |
| `get_field_id` | LOOKUP | Get field node ID by name |
| `get_option_id` | LOOKUP | Get single-select option ID |
| `apply_universal_filter` | FILTER | Multi-criteria filter |
| `apply_assignee_filter` | FILTER | Filter by assignee |
| `apply_repo_filter` | FILTER | Filter by repository |
| `apply_status_filter` | FILTER | Filter by status |
| `list_repositories` | EXTRACT | Extract unique repos from items |
| `list_assignees` | EXTRACT | Extract unique assignees |
| `list_statuses` | EXTRACT | Extract status values |
| `list_priorities` | EXTRACT | Extract priority values |
| `list_fields` | EXTRACT | Extract field structure |
| `format_projects` | FORMAT | Format project list |
| `get_count` | UTILITY | Get filtered item count |
| `get_items` | UTILITY | Get items array |
| `update_item_single_select` | MUTATE | Update single-select field |
| `update_item_text` | MUTATE | Update text field |
| `update_item_number` | MUTATE | Update number field |
| `update_item_date` | MUTATE | Update date field |
| `update_item_iteration` | MUTATE | Update iteration field |
| `clear_item_field` | MUTATE | Clear field value |
| `add_item_to_project` | MUTATE | Add issue/PR to project |
| `add_draft_issue` | MUTATE | Create draft issue |
| `archive_project_item` | MUTATE | Archive item |
| `create_status_update` | MUTATE | Create status update |
| `link_repo_to_project` | MUTATE | Link repository |

---

## DISCOVER Primitives

### `discover_user_projects`

List all projects for the authenticated user.

**Args:** None

**Output:** JSON with project nodes

**Example:**
```bash
discover_user_projects | format_user_projects
```

---

### `discover_org_projects`

List all projects for an organization.

**Args:**
- `org_login` - Organization login name

**Output:** JSON with project nodes

**Example:**
```bash
discover_org_projects "hiivmind" | format_org_projects
```

---

### `discover_repo_projects`

List projects linked to a repository.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name

**Output:** JSON with project nodes

**Example:**
```bash
discover_repo_projects "hiivmind" "hiivmind-pulse-gh" | format_repo_projects
```

---

### `discover_all_projects`

List all accessible projects (user + organizations).

**Args:** None

**Output:** JSON with categorized project nodes

**Example:**
```bash
discover_all_projects | format_all_projects
```

---

## FETCH Primitives

### `fetch_user_project`

Get user project with all items and field values.

**Args:**
- `project_number` - Project number

**Output:** Full project JSON with items

**Example:**
```bash
fetch_user_project 1 | apply_status_filter "In Progress"
```

---

### `fetch_org_project`

Get organization project with all items and field values.

**Args:**
- `project_number` - Project number
- `org_login` - Organization login

**Output:** Full project JSON with items

**Example:**
```bash
fetch_org_project 2 "hiivmind" | apply_assignee_filter "discreteds"
```

---

### `fetch_user_project_fields` / `fetch_org_project_fields`

Get project field structure (fields, options, iterations).

**Args:**
- `project_number` - Project number
- `org_login` - Organization login (org version only)

**Output:** JSON with field definitions

**Example:**
```bash
fetch_org_project_fields 2 "hiivmind" | list_fields
```

---

### `fetch_project_status_updates`

Get all status updates for a project.

**Args:**
- `project_id` - Project node ID

**Output:** JSON with status update nodes

**Example:**
```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
fetch_project_status_updates "$PROJECT_ID"
```

---

### `fetch_project_views`

Get all views for a project.

**Args:**
- `project_id` - Project node ID

**Output:** JSON with view nodes

**Example:**
```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
fetch_project_views "$PROJECT_ID"
```

---

### `fetch_linked_repositories`

Get repositories linked to a project.

**Args:**
- `project_id` - Project node ID

**Output:** JSON with repository nodes

**Example:**
```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
fetch_linked_repositories "$PROJECT_ID"
```

---

## LOOKUP Primitives

### `get_user_project_id`

Get the node ID for a user's project.

**Args:**
- `project_number` - Project number

**Output:** Node ID string (e.g., `PVT_kwHOA-ytfM4A...`)

**Example:**
```bash
PROJECT_ID=$(get_user_project_id 1)
```

---

### `get_org_project_id`

Get the node ID for an organization's project.

**Args:**
- `project_number` - Project number
- `org_login` - Organization login

**Output:** Node ID string

**Example:**
```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
```

---

### `get_field_id`

Get the node ID for a project field by name.

**Args:**
- `project_id` - Project node ID
- `field_name` - Field name (e.g., "Status", "Priority")

**Output:** Field node ID string

**Example:**
```bash
FIELD_ID=$(get_field_id "$PROJECT_ID" "Status")
```

---

### `get_option_id`

Get the node ID for a single-select option.

**Args:**
- `project_id` - Project node ID
- `field_name` - Field name
- `option_name` - Option name (e.g., "Done", "P0")

**Output:** Option node ID string

**Example:**
```bash
OPTION_ID=$(get_option_id "$PROJECT_ID" "Status" "Done")
```

---

## FILTER Primitives

All filter primitives read from stdin and write to stdout.

### `apply_universal_filter`

Apply multiple filter criteria with conditional logic.

**Args:**
- `repo` - Repository name (empty string to skip)
- `assignee` - Username (empty string to skip)
- `status` - Status value (empty string to skip)
- `priority` - Priority value (empty string to skip)

**Input:** Project JSON from fetch

**Output:** Filtered project JSON

**Example:**
```bash
fetch_org_project 2 "hiivmind" | apply_universal_filter "hiivmind-pulse-gh" "" "In Progress" ""
```

---

### `apply_assignee_filter`

Filter items by assignee username.

**Args:**
- `assignee` - Username to filter by

**Example:**
```bash
fetch_org_project 2 "hiivmind" | apply_assignee_filter "discreteds"
```

---

### `apply_repo_filter`

Filter items by repository name.

**Args:**
- `repo` - Repository name to filter by

**Example:**
```bash
fetch_org_project 2 "hiivmind" | apply_repo_filter "hiivmind-pulse-gh"
```

---

### `apply_status_filter`

Filter items by status field value.

**Args:**
- `status` - Status value (e.g., "Done", "In Progress")

**Example:**
```bash
fetch_org_project 2 "hiivmind" | apply_status_filter "Done"
```

---

## EXTRACT Primitives

All extract primitives read from stdin and write to stdout.

### `list_repositories`

Extract unique repository names from project items.

**Input:** Project JSON

**Output:** JSON array of repository names

**Example:**
```bash
fetch_org_project 2 "hiivmind" | list_repositories
```

---

### `list_assignees`

Extract unique assignee usernames from project items.

**Input:** Project JSON

**Output:** JSON array of usernames

**Example:**
```bash
fetch_org_project 2 "hiivmind" | list_assignees
```

---

### `list_statuses`

Extract unique status values from project items.

**Input:** Project JSON

**Output:** JSON array of status values

**Example:**
```bash
fetch_org_project 2 "hiivmind" | list_statuses
```

---

### `list_priorities`

Extract unique priority values from project items.

**Input:** Project JSON

**Output:** JSON array of priority values

**Example:**
```bash
fetch_org_project 2 "hiivmind" | list_priorities
```

---

### `list_fields`

Extract project field structure.

**Input:** Fields JSON from fetch_*_project_fields

**Output:** JSON array of field definitions

**Example:**
```bash
fetch_org_project_fields 2 "hiivmind" | list_fields
```

---

## FORMAT Primitives

### `format_user_projects` / `format_org_projects` / `format_repo_projects` / `format_all_projects`

Format project discovery output for display.

**Input:** Discovery JSON from discover_* functions

**Output:** Formatted JSON

**Example:**
```bash
discover_org_projects "hiivmind" | format_org_projects
```

---

## UTILITY Functions

### `get_count`

Get the count of filtered items.

**Input:** Filtered project JSON

**Output:** Number

**Example:**
```bash
fetch_org_project 2 "hiivmind" | apply_status_filter "Done" | get_count
```

---

### `get_items`

Get the items array from filtered results.

**Input:** Filtered project JSON

**Output:** JSON array of items

**Example:**
```bash
fetch_org_project 2 "hiivmind" | apply_status_filter "Done" | get_items
```

---

## MUTATE Primitives

### Field Updates

#### `update_item_single_select`

Update a single-select field value.

**Args:**
- `project_id` - Project node ID
- `item_id` - Item node ID
- `field_id` - Field node ID
- `option_id` - Option node ID

**Example:**
```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
FIELD_ID=$(get_field_id "$PROJECT_ID" "Status")
OPTION_ID=$(get_option_id "$PROJECT_ID" "Status" "Done")
update_item_single_select "$PROJECT_ID" "$ITEM_ID" "$FIELD_ID" "$OPTION_ID"
```

---

#### `update_item_text` / `update_item_number` / `update_item_date` / `update_item_iteration`

Update various field types.

**Args:** Similar pattern - `project_id`, `item_id`, `field_id`, `value`

---

#### `clear_item_field`

Clear a field value from an item.

**Args:**
- `project_id` - Project node ID
- `item_id` - Item node ID
- `field_id` - Field node ID

---

### Item Management

#### `add_item_to_project`

Add an existing issue or PR to a project.

**Args:**
- `project_id` - Project node ID
- `content_id` - Issue or PR node ID

**Example:**
```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
add_item_to_project "$PROJECT_ID" "$ISSUE_ID"
```

---

#### `add_draft_issue`

Create a draft issue in a project.

**Args:**
- `project_id` - Project node ID
- `title` - Draft issue title
- `body` - Draft issue body (optional)

---

#### `archive_project_item` / `unarchive_project_item`

Archive or unarchive a project item.

**Args:**
- `project_id` - Project node ID
- `item_id` - Item node ID

---

### Status Updates

#### `create_status_update`

Create a new status update for a project.

**Args:**
- `project_id` - Project node ID
- `status` - ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, or INACTIVE
- `body` - Message (optional)
- `start_date` - YYYY-MM-DD (optional)
- `target_date` - YYYY-MM-DD (optional)

---

### Repository Linking

#### `link_repo_to_project` / `unlink_repo_from_project`

Link or unlink a repository to/from a project.

**Args:**
- `project_id` - Project node ID
- `repository_id` - Repository node ID

---

## GraphQL Queries

| Query | Category | Description |
|-------|----------|-------------|
| `discovery.user_projects` | Discovery | List user's projects |
| `discovery.organization_projects` | Discovery | List org's projects via viewer |
| `discovery.specific_organization_projects` | Discovery | List specific org's projects |
| `discovery.repository_projects` | Discovery | List repo's linked projects |
| `project_structure.project_fields` | Structure | User project fields |
| `project_structure.organization_project_fields` | Structure | Org project fields |
| `item_queries.user_project_items_full` | Items | Full user project with items |
| `item_queries.organization_project_items_full` | Items | Full org project with items |
| `filtering.items_by_repository` | Filtering | Items by repo (post-process) |
| `filtering.items_by_assignee` | Filtering | Items by assignee (post-process) |
| `filtering.items_by_status` | Filtering | Items by status (post-process) |
| `utilities.project_by_id` | Utilities | Project by node ID |
| `utilities.project_summary` | Utilities | Quick status summary |
| `utilities.project_readme` | Utilities | README content |
| `status_updates.project_status_updates` | Status | All status updates |
| `status_updates.latest_status_update` | Status | Most recent update |
| `views.project_views` | Views | All project views |
| `views.project_view_by_number` | Views | Specific view |
| `repository_linking.project_linked_repositories` | Linking | Linked repos |
| `pagination.user_project_items_paginated` | Pagination | Paginated user items |
| `pagination.organization_project_items_paginated` | Pagination | Paginated org items |
| `pagination.user_project_items_sorted` | Pagination | Sorted user items |
| `pagination.organization_project_items_sorted` | Pagination | Sorted org items |

---

## jq Filters

| Filter | Category | Description |
|--------|----------|-------------|
| `basic_filters.no_filter` | Basic | Return all data |
| `basic_filters.repository_filter` | Basic | Filter by repo |
| `basic_filters.assignee_filter` | Basic | Filter by assignee |
| `basic_filters.status_filter` | Basic | Filter by status |
| `basic_filters.priority_filter` | Basic | Filter by priority |
| `combined_filters.universal_filter` | Combined | Multi-criteria filter |
| `discovery_filters.list_repositories` | Discovery | Extract repos |
| `discovery_filters.list_assignees` | Discovery | Extract assignees |
| `discovery_filters.list_statuses` | Discovery | Extract statuses |
| `discovery_filters.list_priorities` | Discovery | Extract priorities |
| `discovery_filters.list_fields` | Discovery | Extract field structure |
| `discovery_filters.format_user_projects` | Format | Format user projects |
| `discovery_filters.format_org_projects` | Format | Format org projects |
| `view_filters.list_views` | Views | Format views list |
| `status_update_filters.format_status_updates` | Status | Format updates |
| `repository_filters.list_linked_repositories` | Linking | Format linked repos |
| `workspace_filters.transform_project_fields` | Workspace | Transform for config.yaml |

---

## Composition Examples

### Get open items for a repo in an org project

```bash
fetch_org_project 2 "hiivmind" | apply_repo_filter "hiivmind-pulse-gh" | apply_status_filter "In Progress" | get_items
```

### Update item status

```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
FIELD_ID=$(get_field_id "$PROJECT_ID" "Status")
OPTION_ID=$(get_option_id "$PROJECT_ID" "Status" "Done")
update_item_single_select "$PROJECT_ID" "$ITEM_ID" "$FIELD_ID" "$OPTION_ID"
```

### Get project field structure

```bash
fetch_org_project_fields 2 "hiivmind" | list_fields | jq '.[].name'
```

### Create a status update

```bash
PROJECT_ID=$(get_org_project_id 2 "hiivmind")
create_status_update "$PROJECT_ID" "ON_TRACK" "Sprint progressing well" "2025-12-01" "2025-12-15"
```

---

## Related Domains

- **Issue Domain** (`gh-issue-*`) - Issue CRUD and milestone assignment
- **PR Domain** (`gh-pr-*`) - Pull request operations
- **Milestone Domain** (`gh-milestone-*`) - Milestone CRUD
- **Repository Domain** (`gh-repo-*`) - Repository operations

---

## Notes

- Projects v2 uses GraphQL node IDs (e.g., `PVT_...`, `PVTI_...`)
- Field values are set on project items, not issues/PRs directly
- Milestones are set on issues/PRs, not project items (use Issue/PR domains)
- Single-select fields require option IDs, not option names
- Status updates require ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, or INACTIVE

## API Limitations

The following operations are **NOT available** via the GraphQL API:

### View Management
- **No `createProjectV2View`** - Views can only be created via the GitHub UI
- **No `updateProjectV2View`** - Views can only be updated via the GitHub UI
- Views can be READ via the `views` connection on ProjectV2

### Single-Select Option Management
- **No `createProjectV2FieldOption`** - Options cannot be added individually
- **No `updateProjectV2FieldOption`** - Options cannot be updated individually
- To manage options, use `updateProjectV2Field` with `singleSelectOptions` parameter
- The `singleSelectOptions` array **OVERWRITES** all existing options
- Workflow: Fetch current options → Modify array → Update field with complete array
