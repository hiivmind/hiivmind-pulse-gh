# Config Schema Reference

> **Purpose:** Document the `.hiivmind/github/config.yaml` schema for direct `gh` CLI usage.

This reference describes how to read workspace configuration for GitHub API operations.

---

## Loading Context

Before any GitHub operation, load workspace context:

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
TYPE=$(yq '.workspace.type' "$CONFIG")
```

For user-specific context (not committed to git):

```bash
USER_CONFIG=".hiivmind/github/user.yaml"
USER_LOGIN=$(yq '.user.login' "$USER_CONFIG")
USER_ID=$(yq '.user.id' "$USER_CONFIG")
```

---

## Schema: config.yaml (Team-Shared)

### workspace

Workspace identification - the org or user that owns the repositories.

| Path | Type | Description |
|------|------|-------------|
| `.workspace.type` | string | `"organization"` or `"user"` |
| `.workspace.login` | string | GitHub org/user login |
| `.workspace.id` | string | GraphQL node ID (e.g., `O_kgDO...` or `U_kgDO...`) |

**Example:**
```yaml
workspace:
  type: organization
  login: hiivmind
  id: O_kgDOBxxxxxx
```

### projects

GitHub Projects v2 configuration.

| Path | Type | Description |
|------|------|-------------|
| `.projects.default` | number | Default project number for operations |
| `.projects.catalog[]` | array | List of discovered projects |
| `.projects.catalog[].number` | number | Project number (visible in URL) |
| `.projects.catalog[].id` | string | GraphQL node ID (`PVT_...`) |
| `.projects.catalog[].title` | string | Project title |
| `.projects.catalog[].fields.{Name}.id` | string | Field ID for a named field |
| `.projects.catalog[].fields.{Name}.options.{Value}` | string | Option ID for single-select values |

**Example:**
```yaml
projects:
  default: 2
  catalog:
    - number: 2
      id: PVT_kwDOBxxxxxx
      title: "Development Board"
      fields:
        Status:
          id: PVTF_lADOBxxxxxx
          options:
            "Todo": 98236657
            "In Progress": 47fc9ee4
            "Done": f75ad846
        Priority:
          id: PVTF_lADOByyyyyy
          options:
            "High": abc123
            "Medium": def456
            "Low": ghi789
```

### repositories

Repository catalog with cached IDs and metadata.

| Path | Type | Description |
|------|------|-------------|
| `.repositories[]` | array | List of repositories |
| `.repositories[].name` | string | Repository name |
| `.repositories[].id` | string | GraphQL node ID (`R_kgDO...`) |
| `.repositories[].default_branch` | string | Default branch name |
| `.repositories[].visibility` | string | `public`, `private`, or `internal` |

**Example:**
```yaml
repositories:
  - name: hiivmind-pulse-gh
    id: R_kgDONxxxxxx
    default_branch: main
    visibility: public
  - name: hiivmind-corpus
    id: R_kgDONyyyyyy
    default_branch: main
    visibility: public
```

### milestones

Milestone catalog keyed by repository name.

| Path | Type | Description |
|------|------|-------------|
| `.milestones.{repo}[]` | array | Milestones for a repository |
| `.milestones.{repo}[].number` | number | Milestone number |
| `.milestones.{repo}[].id` | string | GraphQL node ID (`MI_...`) |
| `.milestones.{repo}[].title` | string | Milestone title |
| `.milestones.{repo}[].state` | string | `OPEN` or `CLOSED` |

**Example:**
```yaml
milestones:
  hiivmind-pulse-gh:
    - number: 5
      id: MI_kwDONxxxxxx
      title: "v3 Architecture Migration"
      state: OPEN
    - number: 4
      id: MI_kwDONyyyyyy
      title: "v2.0 Release"
      state: CLOSED
```

### cache

Metadata about config freshness.

| Path | Type | Description |
|------|------|-------------|
| `.cache.initialized_at` | string | ISO timestamp of initial creation |
| `.cache.last_synced_at` | string | ISO timestamp of last refresh |
| `.cache.toolkit_version` | string | Version of hiivmind-pulse-gh that created this |

---

## Schema: views/project-{N}.yaml (Phase 2)

Project view configurations, stored per-project for faster access and independent freshness tracking.

### project

Identifies which project these views belong to.

| Path | Type | Description |
|------|------|-------------|
| `.project.number` | number | Project number (visible in URL) |
| `.project.id` | string | GraphQL node ID (`PVT_...`) |
| `.project.title` | string | Project title |

### views

Array of view configurations for the project.

| Path | Type | Description |
|------|------|-------------|
| `.views[]` | array | List of views in this project |
| `.views[].number` | number | View number (1-based index) |
| `.views[].id` | string | GraphQL node ID |
| `.views[].name` | string | View name (e.g., "Backlog", "Current Sprint") |
| `.views[].layout` | string | `BOARD_LAYOUT`, `TABLE_LAYOUT`, `ROADMAP_LAYOUT` |
| `.views[].filter` | string | View filter expression (e.g., "status:open") |
| `.views[].visible_fields[]` | array | List of field names visible in this view |
| `.views[].hidden_fields[]` | array | List of field names hidden in this view |
| `.views[].group_by[]` | array | Group by configuration |
| `.views[].group_by[].field` | string | Field name to group by |
| `.views[].group_by[].direction` | string | `ASC` or `DESC` (optional) |
| `.views[].sort_by[]` | array | Sort by configuration |
| `.views[].sort_by[].field` | string | Field name to sort by |
| `.views[].sort_by[].direction` | string | `ASC` or `DESC` |

**Example:**
```yaml
project:
  number: 2
  id: PVT_kwDOBxxxxxx
  title: "Development Board"

views:
  - number: 1
    id: PVTV_lADOBxxxxxx
    name: "Backlog"
    layout: BOARD_LAYOUT
    filter: "status:open"
    visible_fields:
      - Title
      - Status
      - Priority
      - Assignees
    hidden_fields:
      - Estimate
      - Start date
    group_by:
      - field: Status
        direction: ASC
    sort_by:
      - field: Priority
        direction: ASC
      - field: Title
        direction: ASC

  - number: 2
    id: PVTV_lADOByyyyyy
    name: "Current Sprint"
    layout: TABLE_LAYOUT
    filter: "status:\"In Progress\""
    visible_fields:
      - Title
      - Status
      - Priority
      - Assignees
      - Estimate
    sort_by:
      - field: Priority
        direction: DESC

cache:
  synced_at: "2025-12-15T10:30:00Z"
  schema_version: "1.0"
```

### Common View Lookups

| Need | yq Command |
|------|------------|
| Get view by name | `yq '.views[] \| select(.name == "Backlog")' views/project-2.yaml` |
| List all views | `yq '.views[].name' views/project-2.yaml` |
| Get visible fields | `yq '.views[] \| select(.name == "Backlog") \| .visible_fields[]' views/project-2.yaml` |
| Check if field visible | `yq '.views[] \| select(.name == "Backlog") \| .visible_fields[] \| select(. == "Priority")' views/project-2.yaml` |
| Get default view | `yq '.views[] \| select(.number == 1)' views/project-2.yaml` |
| Get view layout | `yq '.views[] \| select(.name == "Backlog") \| .layout' views/project-2.yaml` |

---

## Schema: repos/{repo-name}.yaml (Phase 3)

Repository settings and protection rules, stored per-repository for fast access and independent freshness tracking.

### repository

Repository identification and basic metadata.

| Path | Type | Description |
|------|------|-------------|
| `.repository.name` | string | Repository name |
| `.repository.id` | string | GraphQL node ID (`R_kgDO...`) |
| `.repository.full_name` | string | Full repository path (`owner/repo`) |
| `.repository.default_branch` | string | Default branch name (e.g., `main`) |
| `.repository.visibility` | string | `public`, `private`, or `internal` |
| `.repository.archived` | boolean | `true` if repository is archived |

### branch_protection

Legacy branch protection rules, keyed by branch name.

| Path | Type | Description |
|------|------|-------------|
| `.branch_protection.{branch}` | object | Protection settings for a specific branch |
| `.branch_protection.{branch}.enabled` | boolean | `true` if protection is enabled |
| `.branch_protection.{branch}.required_pull_request_reviews` | object | PR review requirements |
| `.branch_protection.{branch}.required_pull_request_reviews.required_approving_review_count` | number | Number of approvals needed |
| `.branch_protection.{branch}.required_pull_request_reviews.dismiss_stale_reviews` | boolean | Dismiss reviews on new commits |
| `.branch_protection.{branch}.required_pull_request_reviews.require_code_owner_reviews` | boolean | Require code owner approval |
| `.branch_protection.{branch}.required_pull_request_reviews.require_last_push_approval` | boolean | Require approval after last push |
| `.branch_protection.{branch}.required_status_checks` | object | Status check requirements |
| `.branch_protection.{branch}.required_status_checks.strict` | boolean | Require branches to be up to date |
| `.branch_protection.{branch}.required_status_checks.contexts[]` | array | Required check names |
| `.branch_protection.{branch}.enforce_admins` | boolean | Apply rules to admins |
| `.branch_protection.{branch}.required_linear_history` | boolean | Require linear history |
| `.branch_protection.{branch}.allow_force_pushes` | boolean | Allow force pushes |
| `.branch_protection.{branch}.allow_deletions` | boolean | Allow branch deletion |
| `.branch_protection.{branch}.required_conversation_resolution` | boolean | Require conversation resolution |
| `.branch_protection.{branch}.lock_branch` | boolean | Lock branch (read-only) |
| `.branch_protection.{branch}.restrictions` | object | Who can push to this branch |
| `.branch_protection.{branch}.restrictions.users[]` | array | User logins with push access |
| `.branch_protection.{branch}.restrictions.teams[]` | array | Team slugs with push access |
| `.branch_protection.{branch}.restrictions.apps[]` | array | App slugs with push access |

### rulesets

Modern repository rulesets (pattern-based protection).

| Path | Type | Description |
|------|------|-------------|
| `.rulesets[]` | array | List of rulesets |
| `.rulesets[].id` | number | Ruleset ID |
| `.rulesets[].name` | string | Ruleset name |
| `.rulesets[].target` | string | `branch` or `tag` |
| `.rulesets[].enforcement` | string | `active`, `evaluate`, or `disabled` |
| `.rulesets[].conditions` | object | When this ruleset applies |
| `.rulesets[].conditions.ref_name` | object | Branch/tag name patterns |
| `.rulesets[].conditions.ref_name.include[]` | array | Patterns to include (e.g., `refs/heads/main`) |
| `.rulesets[].conditions.ref_name.exclude[]` | array | Patterns to exclude |
| `.rulesets[].rules[]` | array | Rules to enforce |
| `.rulesets[].rules[].type` | string | Rule type (e.g., `pull_request`, `required_signatures`) |
| `.rulesets[].rules[].parameters` | object | Rule-specific parameters |

### merge_settings

Repository merge configuration.

| Path | Type | Description |
|------|------|-------------|
| `.merge_settings.allow_merge_commit` | boolean | Allow merge commits |
| `.merge_settings.allow_squash_merge` | boolean | Allow squash merging |
| `.merge_settings.allow_rebase_merge` | boolean | Allow rebase merging |
| `.merge_settings.allow_auto_merge` | boolean | Allow auto-merge |
| `.merge_settings.delete_branch_on_merge` | boolean | Auto-delete head branches |
| `.merge_settings.allow_update_branch` | boolean | Allow updating PR branches |
| `.merge_settings.squash_merge_commit_title` | string | `PR_TITLE` or `COMMIT_OR_PR_TITLE` |
| `.merge_settings.squash_merge_commit_message` | string | `PR_BODY`, `COMMIT_MESSAGES`, or `BLANK` |
| `.merge_settings.merge_commit_title` | string | `PR_TITLE` or `MERGE_MESSAGE` |
| `.merge_settings.merge_commit_message` | string | `PR_BODY`, `PR_TITLE`, or `BLANK` |

### labels

Repository labels.

| Path | Type | Description |
|------|------|-------------|
| `.labels[]` | array | List of labels |
| `.labels[].name` | string | Label name |
| `.labels[].color` | string | Hex color (without #) |
| `.labels[].description` | string | Label description |
| `.labels[].default` | boolean | `true` if GitHub default label |

**Example:**
```yaml
repository:
  name: hiivmind-pulse-gh
  id: R_kgDONxxxxxx
  full_name: hiivmind/hiivmind-pulse-gh
  default_branch: main
  visibility: public
  archived: false

branch_protection:
  main:
    enabled: true
    required_pull_request_reviews:
      required_approving_review_count: 1
      dismiss_stale_reviews: true
      require_code_owner_reviews: false
      require_last_push_approval: false
    required_status_checks:
      strict: true
      contexts:
        - "ci/build"
        - "ci/test"
    enforce_admins: true
    required_linear_history: false
    allow_force_pushes: false
    allow_deletions: false
    required_conversation_resolution: true
    lock_branch: false
    restrictions:
      users: []
      teams: []
      apps: []

rulesets:
  - id: 12345
    name: "Protect main branch"
    target: branch
    enforcement: active
    conditions:
      ref_name:
        include: ["refs/heads/main"]
        exclude: []
    rules:
      - type: pull_request
        parameters:
          required_approving_review_count: 1

merge_settings:
  allow_merge_commit: true
  allow_squash_merge: true
  allow_rebase_merge: false
  allow_auto_merge: true
  delete_branch_on_merge: true
  allow_update_branch: true
  squash_merge_commit_title: PR_TITLE
  squash_merge_commit_message: PR_BODY
  merge_commit_title: PR_TITLE
  merge_commit_message: PR_BODY

labels:
  - name: bug
    color: d73a4a
    description: "Something isn't working"
    default: true
  - name: enhancement
    color: a2eeef
    description: "New feature or request"
    default: true
  - name: documentation
    color: 0075ca
    description: "Improvements or additions to documentation"
    default: true

cache:
  synced_at: "2025-12-15T12:00:00Z"
  schema_version: "1.0"
```

### Common Repository Lookups

| Need | yq Command |
|------|------------|
| Check if branch protected | `yq '.branch_protection["main"].enabled' repos/repo-name.yaml` |
| Get required review count | `yq '.branch_protection["main"].required_pull_request_reviews.required_approving_review_count' repos/repo-name.yaml` |
| Get required checks | `yq '.branch_protection["main"].required_status_checks.contexts[]' repos/repo-name.yaml` |
| Check merge methods | `yq '.merge_settings \| keys' repos/repo-name.yaml` |
| Check if auto-delete | `yq '.merge_settings.delete_branch_on_merge' repos/repo-name.yaml` |
| List all labels | `yq '.labels[].name' repos/repo-name.yaml` |
| Check label exists | `yq '.labels[] \| select(.name == "bug")' repos/repo-name.yaml` |
| Get default branch | `yq '.repository.default_branch' repos/repo-name.yaml` |

---

## Schema: automations/project-{N}.yaml (Phase 4)

Project automation rules and workflow documentation. Stored per-project for independent tracking.

**Important:** GitHub Projects v2 automations are configured in the project UI and not fully exposed via API. This file is primarily for documentation and automation-awareness. Update it manually to reflect your project's actual automation configuration.

### project

Identifies which project these automations belong to.

| Path | Type | Description |
|------|------|-------------|
| `.project.number` | number | Project number (visible in URL) |
| `.project.id` | string | GraphQL node ID (`PVT_...`) |
| `.project.title` | string | Project title |

### built_in

Built-in GitHub automations configured in the project settings UI.

| Path | Type | Description |
|------|------|-------------|
| `.built_in.auto_add` | object | Auto-add items to project settings |
| `.built_in.auto_add.enabled` | boolean | `true` if auto-add is configured |
| `.built_in.auto_add.repositories[]` | array | Repositories with auto-add enabled |
| `.built_in.auto_archive` | object | Auto-archive settings |
| `.built_in.auto_archive.enabled` | boolean | `true` if auto-archive is configured |
| `.built_in.auto_archive.trigger` | string | Trigger type (e.g., `item_closed`, `status_changed`) |
| `.built_in.auto_archive.conditions` | object | Conditions for auto-archive |
| `.built_in.auto_archive.conditions.status_value` | string | Status that triggers archive |
| `.built_in.auto_archive.conditions.delay_days` | number | Days to wait before archiving |

### workflows

Custom workflow automations documented for this project.

| Path | Type | Description |
|------|------|-------------|
| `.workflows[]` | array | List of documented workflows |
| `.workflows[].name` | string | Workflow name |
| `.workflows[].description` | string | What this workflow does |
| `.workflows[].trigger` | object | What triggers this workflow |
| `.workflows[].trigger.type` | string | Trigger type: `item_added`, `field_changed`, `item_closed` |
| `.workflows[].trigger.field` | string | Field that triggers (for `field_changed` type) |
| `.workflows[].trigger.value` | string | Value that triggers (optional) |
| `.workflows[].actions[]` | array | Actions performed by this workflow |
| `.workflows[].actions[].type` | string | Action type: `set_field`, `add_label`, `notify`, `archive_item` |
| `.workflows[].actions[].field` | string | Field to update (for `set_field` type) |
| `.workflows[].actions[].value` | string | Value to set |

**Example:**
```yaml
project:
  number: 2
  id: PVT_kwDOBxxxxxx
  title: "Development Board"

built_in:
  auto_add:
    enabled: true
    repositories:
      - hiivmind-pulse-gh
      - hiivmind-corpus

  auto_archive:
    enabled: true
    trigger: "status_changed"
    conditions:
      status_value: "Done"
      delay_days: 30

workflows:
  - name: "Auto-triage new issues"
    description: "Set status to Triage for new issues"
    trigger:
      type: "item_added"
      source: "issue"
    actions:
      - type: "set_field"
        field: "Status"
        value: "Triage"
      - type: "set_field"
        field: "Priority"
        value: "Medium"

  - name: "Complete closed issues"
    description: "Set status to Done when issue is closed"
    trigger:
      type: "item_closed"
    actions:
      - type: "set_field"
        field: "Status"
        value: "Done"

  - name: "Start work on assignment"
    description: "Move to In Progress when item is assigned"
    trigger:
      type: "field_changed"
      field: "Assignees"
    actions:
      - type: "set_field"
        field: "Status"
        value: "In Progress"

cache:
  synced_at: "2025-12-15T14:00:00Z"
  schema_version: "1.0"
  source: "manual"
```

### Common Automation Lookups

| Need | yq Command |
|------|------------|
| Check if auto-add enabled | `yq '.built_in.auto_add.enabled' automations/project-2.yaml` |
| Get auto-add repos | `yq '.built_in.auto_add.repositories[]' automations/project-2.yaml` |
| Check if auto-archive enabled | `yq '.built_in.auto_archive.enabled' automations/project-2.yaml` |
| Get archive delay | `yq '.built_in.auto_archive.conditions.delay_days' automations/project-2.yaml` |
| List workflows | `yq '.workflows[].name' automations/project-2.yaml` |
| Find status auto-set | `yq '.workflows[] \| select(.actions[].field == "Status")' automations/project-2.yaml` |

---

## Schema: relationships.yaml (Phase 5)

Cross-repository relationships and project links. Single workspace-level file documenting all relationships.

**Important:** This file is partially auto-generated (project-repo links via API) and partially manual (repository dependencies). Update regularly to reflect your workspace architecture.

### workspace

Workspace identification.

| Path | Type | Description |
|------|------|-------------|
| `.workspace.type` | string | `organization` or `user` |
| `.workspace.login` | string | Workspace login |

### project_repo_links

Documents which repositories are linked to which projects.

| Path | Type | Description |
|------|------|-------------|
| `.project_repo_links.{N}` | object | Links for project number N |
| `.project_repo_links.{N}.project_id` | string | GraphQL node ID (`PVT_...`) |
| `.project_repo_links.{N}.project_title` | string | Project title |
| `.project_repo_links.{N}.linked_repos[]` | array | Repositories linked to this project |
| `.project_repo_links.{N}.linked_repos[].name` | string | Repository name |
| `.project_repo_links.{N}.linked_repos[].auto_add_enabled` | boolean | `true` if auto-add is configured for this repo |

### repo_dependencies

Documents repository dependency relationships (manually maintained).

| Path | Type | Description |
|------|------|-------------|
| `.repo_dependencies.{repo}` | object | Dependencies for a repository |
| `.repo_dependencies.{repo}.depends_on[]` | array | Repositories this repo depends on |
| `.repo_dependencies.{repo}.depended_by[]` | array | Repositories that depend on this repo |
| `.repo_dependencies.{repo}.relationship_type` | string | `main`, `plugin`, `test`, `documentation` |

### cross_project_coordination

Documents scenarios where work in one project affects another (manually maintained).

| Path | Type | Description |
|------|------|-------------|
| `.cross_project_coordination[]` | array | List of coordination relationships |
| `.cross_project_coordination[].source_project` | number | Source project number |
| `.cross_project_coordination[].target_project` | number | Target project number |
| `.cross_project_coordination[].coordination_type` | string | `milestone_sync`, `issue_tracking`, `dependency` |
| `.cross_project_coordination[].description` | string | How these projects coordinate |

**Example:**
```yaml
workspace:
  type: organization
  login: hiivmind

project_repo_links:
  2:
    project_id: PVT_kwDOBxxxxxx
    project_title: "Development Board"
    linked_repos:
      - name: hiivmind-pulse-gh
        auto_add_enabled: true
      - name: hiivmind-corpus
        auto_add_enabled: true

  3:
    project_id: PVT_kwDOByyyyyy
    project_title: "Research"
    linked_repos:
      - name: hiivmind-corpus
        auto_add_enabled: false
      - name: clickhouse_skills
        auto_add_enabled: true

repo_dependencies:
  hiivmind-pulse-gh:
    depends_on: []
    depended_by:
      - hiivmind-pulse-gh-tests
    relationship_type: main

  hiivmind-pulse-gh-tests:
    depends_on:
      - hiivmind-pulse-gh
    depended_by: []
    relationship_type: test

  hiivmind-corpus:
    depends_on: []
    depended_by:
      - hiivmind-corpus-data
      - hiivmind-corpus-claude
    relationship_type: main

  hiivmind-corpus-data:
    depends_on:
      - hiivmind-corpus
    depended_by: []
    relationship_type: plugin

cross_project_coordination:
  - source_project: 2
    target_project: 3
    coordination_type: milestone_sync
    description: "Development milestones align with Research project phases"

cache:
  synced_at: "2025-12-15T16:00:00Z"
  schema_version: "1.0"
  source: "api+manual"
```

### Common Relationship Lookups

| Need | yq Command |
|------|------------|
| Get repos for project | `yq '.project_repo_links[2].linked_repos[].name' relationships.yaml` |
| Find projects for repo | `yq '.project_repo_links \| to_entries \| .[] \| select(.value.linked_repos[].name == "repo-name") \| .key' relationships.yaml` |
| Get repo dependencies | `yq '.repo_dependencies["repo-name"].depends_on[]' relationships.yaml` |
| Get repo dependents | `yq '.repo_dependencies["repo-name"].depended_by[]' relationships.yaml` |
| Get repo type | `yq '.repo_dependencies["repo-name"].relationship_type' relationships.yaml` |
| Find coordinated projects | `yq '.cross_project_coordination[] \| select(.source_project == 2 or .target_project == 2)' relationships.yaml` |

---

## Schema: teams.yaml (Phase 6)

**File:** `.hiivmind/github/teams.yaml` (workspace-level, single file)
**Purpose:** Cache organization team membership and repository permissions for team-aware operations
**Freshness:** 7 days (team membership changes infrequently)

### workspace

Workspace identification (organization only - teams not available for user accounts).

| Path | Type | Description |
|------|------|-------------|
| `.workspace.type` | string | `"organization"` (teams only for orgs) |
| `.workspace.login` | string | Organization login |

### teams

Array of organization teams with members and repository permissions.

| Path | Type | Description |
|------|------|-------------|
| `.teams[]` | array | List of teams |
| `.teams[].slug` | string | Team slug (URL-friendly identifier) |
| `.teams[].id` | string | GraphQL node ID (`T_...`) |
| `.teams[].name` | string | Team display name |
| `.teams[].privacy` | string | `secret` or `closed` |
| `.teams[].members[]` | array | Team members |
| `.teams[].members[].login` | string | Member username |
| `.teams[].members[].id` | string | Member GraphQL node ID |
| `.teams[].members[].role` | string | `MAINTAINER` or `MEMBER` |
| `.teams[].repo_permissions` | object | Repositories this team has access to |
| `.teams[].repo_permissions.{repo}` | string | Permission level: `ADMIN`, `WRITE`, `READ`, `MAINTAIN`, `TRIAGE` |

### repo_team_access

Reverse index mapping repositories to teams by permission level.

| Path | Type | Description |
|------|------|-------------|
| `.repo_team_access.{repo}` | object | Teams with access to this repository |
| `.repo_team_access.{repo}.admin[]` | array | Team slugs with admin access |
| `.repo_team_access.{repo}.write[]` | array | Team slugs with write/maintain access |
| `.repo_team_access.{repo}.read[]` | array | Team slugs with read/triage access |

### cache

Metadata about this cached data.

| Path | Type | Description |
|------|------|-------------|
| `.cache.synced_at` | string | ISO 8601 timestamp of last sync |
| `.cache.schema_version` | string | Schema version (`"1.0"`) |
| `.cache.source` | string | `"graphql"` (fetched via GraphQL API) |

### Example: teams.yaml

```yaml
workspace:
  type: organization
  login: hiivmind

teams:
  - slug: core-maintainers
    id: T_kwDOBxxxxxx
    name: "Core Maintainers"
    privacy: closed
    members:
      - login: alice
        id: U_kgDOAxxxxxx
        role: MAINTAINER
      - login: bob
        id: U_kgDOAyyyyyy
        role: MEMBER
    repo_permissions:
      hiivmind-pulse-gh: ADMIN
      hiivmind-corpus: ADMIN

  - slug: contributors
    id: T_kwDOByyyyyy
    name: "Contributors"
    privacy: closed
    members:
      - login: charlie
        id: U_kgDOAzzzzzz
        role: MEMBER
    repo_permissions:
      hiivmind-pulse-gh: WRITE
      hiivmind-corpus: WRITE

repo_team_access:
  hiivmind-pulse-gh:
    admin: [core-maintainers]
    write: [contributors]
    read: []

  hiivmind-corpus:
    admin: [core-maintainers]
    write: [contributors]
    read: []

cache:
  synced_at: "2025-12-15T18:00:00Z"
  schema_version: "1.0"
  source: "graphql"
```

### Common Team Lookups

| Need | yq Command |
|------|------------|
| Get team members | `yq '.teams[] \| select(.slug == "core-maintainers") \| .members[].login' teams.yaml` |
| Get team's repos | `yq '.teams[] \| select(.slug == "core-maintainers") \| .repo_permissions \| keys[]' teams.yaml` |
| Get teams with repo access | `yq '.repo_team_access["hiivmind-pulse-gh"] \| to_entries \| .[] \| .value[]' teams.yaml` |
| Get repo writers | `yq '.repo_team_access["hiivmind-pulse-gh"].admin[], .repo_team_access["hiivmind-pulse-gh"].write[]' teams.yaml` |
| Check team membership | `yq '.teams[] \| select(.slug == "core-maintainers") \| .members[] \| select(.login == "alice") \| .login' teams.yaml` |
| Get team maintainers | `yq '.teams[] \| select(.slug == "core-maintainers") \| .members[] \| select(.role == "MAINTAINER") \| .login' teams.yaml` |

### Team-Aware Operations

**Use cases:**
- **Reviewer suggestions:** Get users with write+ access for PR reviewers
- **Permission checks:** Verify user can perform operation
- **Team-based assignment:** Assign issues to team maintainers
- **CODEOWNERS integration:** Intelligent reviewer suggestions based on team membership
- **Access audits:** Verify who has access to which repositories

---

## Schema: user.yaml (Personal, Git-Ignored)

### user

Current user's GitHub identity.

| Path | Type | Description |
|------|------|-------------|
| `.user.login` | string | GitHub username |
| `.user.id` | string | GraphQL node ID (`U_kgDO...`) |
| `.user.name` | string | Display name (may be null) |
| `.user.email` | string | Public email (may be null) |

### permissions

Cached permissions for the current user in this workspace.

| Path | Type | Description |
|------|------|-------------|
| `.permissions.org_role` | string | `owner`, `admin`, `member`, `billing_manager` |
| `.permissions.project_roles.{N}` | string | Role for project N: `admin`, `write`, `read` |
| `.permissions.repo_roles.{name}` | string | Role for repo: `admin`, `maintain`, `write`, `triage`, `read` |

### preferences

User-specific overrides.

| Path | Type | Description |
|------|------|-------------|
| `.preferences.default_project` | number | Override team default project |
| `.preferences.default_repo` | string | For ambiguous commands |

---

## Common Lookups

Quick reference for frequently needed values.

| Need | yq Command |
|------|------------|
| Owner login | `yq '.workspace.login' "$CONFIG"` |
| Owner type | `yq '.workspace.type' "$CONFIG"` |
| Owner ID | `yq '.workspace.id' "$CONFIG"` |
| Default project | `yq '.projects.default' "$CONFIG"` |
| Project ID by number | `yq '.projects.catalog[] \| select(.number == N) \| .id' "$CONFIG"` |
| Project title | `yq '.projects.catalog[] \| select(.number == N) \| .title' "$CONFIG"` |
| Status field ID | `yq '.projects.catalog[0].fields.Status.id' "$CONFIG"` |
| Status option ID | `yq '.projects.catalog[0].fields.Status.options["In Progress"]' "$CONFIG"` |
| Repo ID by name | `yq '.repositories[] \| select(.name == "repo") \| .id' "$CONFIG"` |
| Repo default branch | `yq '.repositories[] \| select(.name == "repo") \| .default_branch' "$CONFIG"` |
| Milestone ID | `yq '.milestones["repo"][] \| select(.number == N) \| .id' "$CONFIG"` |
| Current user ID | `yq '.user.id' "$USER_CONFIG"` |
| User's org role | `yq '.permissions.org_role' "$USER_CONFIG"` |

---

## Usage Patterns

### Pattern 1: Load Once Per Session

```bash
# Load at session start
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
DEFAULT_PROJECT=$(yq '.projects.default' "$CONFIG")

# Use throughout session
gh issue create -R "$OWNER/repo-name" --title "New issue"
gh project item-add "$DEFAULT_PROJECT" --owner "$OWNER" --url "$ISSUE_URL"
```

### Pattern 2: Dynamic Field Lookups

```bash
# Get Status field ID for project 2
STATUS_FIELD=$(yq '.projects.catalog[] | select(.number == 2) | .fields.Status.id' "$CONFIG")

# Get "In Progress" option ID
IN_PROGRESS=$(yq '.projects.catalog[] | select(.number == 2) | .fields.Status.options["In Progress"]' "$CONFIG")

# Update item status via GraphQL
gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $value: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: {singleSelectOptionId: $value}
    }) { projectV2Item { id } }
  }
' -f project="$PROJECT_ID" -f item="$ITEM_ID" -f field="$STATUS_FIELD" -f value="$IN_PROGRESS"
```

### Pattern 3: Repository Operations

```bash
# Get repo ID for GraphQL operations
REPO_ID=$(yq '.repositories[] | select(.name == "hiivmind-pulse-gh") | .id' "$CONFIG")

# Use in mutations
gh api graphql -f query='
  mutation($repo: ID!) {
    createIssue(input: {repositoryId: $repo, title: "Test"}) {
      issue { number url }
    }
  }
' -f repo="$REPO_ID"
```

---

## Refreshing Config

When config becomes stale (new projects, renamed fields):

```bash
# Option 1: Re-run workspace init
# Triggers: hiivmind-pulse-gh-workspace-init

# Option 2: Use refresh skill
# Triggers: hiivmind-pulse-gh-workspace-refresh
```

Signs config needs refresh:
- GraphQL returns "Could not resolve to a ProjectV2"
- Field IDs return null
- New projects/repos not appearing

### Pattern 4: View-Aware Operations (Phase 2)

Check if a field is visible in a view before prompting user to set it:

```bash
PROJECT_NUM=2
VIEW_NAME="Backlog"
VIEW_FILE=".hiivmind/github/views/project-$PROJECT_NUM.yaml"

# Get visible fields
VISIBLE_FIELDS=$(yq ".views[] | select(.name == \"$VIEW_NAME\") | .visible_fields[]" "$VIEW_FILE")

# Check if Priority is visible
if echo "$VISIBLE_FIELDS" | grep -q "^Priority$"; then
  echo "Priority field is visible in $VIEW_NAME - prompting user to set it"
  # Proceed with priority field update
else
  echo "Priority field is hidden in $VIEW_NAME - skipping"
fi
```

### Pattern 5: Protection-Aware PR Merge (Phase 3)

Use repository settings to choose the correct merge method and respect auto-delete settings:

```bash
REPO="hiivmind-pulse-gh"
REPO_FILE=".hiivmind/github/repos/$REPO.yaml"
PR_NUM=42

# Get preferred merge method
if [[ $(yq '.merge_settings.allow_squash_merge' "$REPO_FILE") = "true" ]]; then
  MERGE_METHOD="squash"
elif [[ $(yq '.merge_settings.allow_merge_commit' "$REPO_FILE") = "true" ]]; then
  MERGE_METHOD="merge"
else
  MERGE_METHOD="rebase"
fi

# Check if branch auto-deletes
AUTO_DELETE=$(yq '.merge_settings.delete_branch_on_merge' "$REPO_FILE")

# Merge PR
if [[ "$AUTO_DELETE" = "true" ]]; then
  gh pr merge $PR_NUM --$MERGE_METHOD
  echo "Branch will auto-delete after merge"
else
  gh pr merge $PR_NUM --$MERGE_METHOD --delete-branch
  echo "Manually deleting branch after merge"
fi
```

### Pattern 6: Automation-Aware Operations (Phase 4)

Check if auto-add is enabled before manually adding items to a project:

```bash
PROJECT_NUM=2
REPO="hiivmind-pulse-gh"
AUTOMATIONS_FILE=".hiivmind/github/automations/project-$PROJECT_NUM.yaml"

# Check if auto-add is enabled for this repo
AUTO_ADD_ENABLED=$(yq '.built_in.auto_add.enabled' "$AUTOMATIONS_FILE")
AUTO_ADD_REPOS=$(yq '.built_in.auto_add.repositories[]' "$AUTOMATIONS_FILE")

if [[ "$AUTO_ADD_ENABLED" = "true" ]] && echo "$AUTO_ADD_REPOS" | grep -q "^$REPO$"; then
  echo "Auto-add is enabled for $REPO in project $PROJECT_NUM"
  echo "New issues/PRs will be added automatically - skipping manual add"
else
  echo "Auto-add not enabled - adding item manually"
  ISSUE_URL=$(gh issue view $ISSUE_NUM -R "$OWNER/$REPO" --json url --jq '.url')
  gh project item-add $PROJECT_NUM --owner "$OWNER" --url "$ISSUE_URL"
fi
```

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `reference/api-routing.md` | Which API (GraphQL vs REST) for each operation |
| `reference/workflows/` | Multi-step workflow examples |
| `templates/config.yaml.template` | Template used to generate config |
| `templates/user.yaml.template` | Template for user-specific config |
| `templates/freshness.yaml.template` | Template for per-section freshness tracking (Phase 1) |
| `templates/views.yaml.template` | Template for project view config (Phase 2) |
| `templates/repo.yaml.template` | Template for repository settings (Phase 3) |
| `templates/automations.yaml.template` | Template for project automation documentation (Phase 4) |
