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

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `reference/api-routing.md` | Which API (GraphQL vs REST) for each operation |
| `reference/workflows/` | Multi-step workflow examples |
| `templates/config.yaml.template` | Template used to generate config |
| `templates/user.yaml.template` | Template for user-specific config |
