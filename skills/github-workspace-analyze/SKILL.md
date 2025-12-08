---
name: github-workspace-analyze
description: Discover and cache GitHub organization structure including projects, fields, repositories, and milestones. Populates .hiivmind/github/config.yaml with cached IDs for simplified operations. Run after github-workspace-init.
---

# GitHub Workspace Analyzer

Discover and cache GitHub organization/user structure for simplified operations without repeated ID lookups.

## Prerequisites

- `.hiivmind/github/config.yaml` exists (created by `github-workspace-init`)
- `gh` CLI authenticated with appropriate scopes
- Source toolkit functions: `source lib/github/gh-project-functions.sh`

## Process

```
1. LOAD CONFIG  →  2. DISCOVER     →  3. SELECT      →  4. ANALYZE    →  5. CACHE USER  →  6. SAVE
   (workspace)       (projects)        (with user)       (fields/repos)    (permissions)     (configs)
```

## Phase 1: Load Configuration

Read the existing workspace configuration:

```bash
CONFIG_PATH=".hiivmind/github/config.yaml"

if [[ ! -f "$CONFIG_PATH" ]]; then
    echo "No workspace configuration found."
    echo "Run github-workspace-init first."
    exit 1
fi

WORKSPACE_TYPE=$(yq '.workspace.type' "$CONFIG_PATH")
WORKSPACE_LOGIN=$(yq '.workspace.login' "$CONFIG_PATH")
WORKSPACE_ID=$(yq '.workspace.id' "$CONFIG_PATH")

echo "Analyzing workspace: $WORKSPACE_LOGIN ($WORKSPACE_TYPE)"
```

## Phase 2: Discover Projects

Find all accessible projects in the workspace.

### For Organizations

```bash
source lib/github/gh-project-functions.sh

# Discover all org projects
PROJECTS_JSON=$(discover_org_projects "$WORKSPACE_LOGIN")

# Format for display
echo "$PROJECTS_JSON" | jq -r '
    .data.organization.projectsV2.nodes[] |
    "  #\(.number) - \(.title) [\(.closed | if . then "closed" else "open" end)]"
'
```

### For Users

```bash
PROJECTS_JSON=$(discover_user_projects)

echo "$PROJECTS_JSON" | jq -r '
    .data.viewer.projectsV2.nodes[] |
    "  #\(.number) - \(.title) [\(.closed | if . then "closed" else "open" end)]"
'
```

### Sample Output

```
Found 3 projects in acme-corp:
  #1 - Engineering Backlog [open]
  #2 - Product Roadmap [open]
  #5 - Archive 2024 [closed]
```

## Phase 3: Select Projects

Ask user which projects to include in the workspace catalog:

| Question | Options |
|----------|---------|
| "Which projects should be included?" | List discovered projects |
| "Which project should be the default?" | One of the selected |

**Include open projects by default, ask about closed.**

Example interaction:
```
Include project #1 - Engineering Backlog? [Y/n] y
Include project #2 - Product Roadmap? [Y/n] y
Include project #5 - Archive 2024 (closed)? [y/N] n

Default project number: 2
```

## Phase 4: Analyze Selected Projects

For each selected project, discover complete field structure.

### Fetch Project Details

```bash
PROJECT_NUMBER=2

# Get project with all fields
FIELDS_JSON=$(fetch_org_project_fields "$PROJECT_NUMBER" "$WORKSPACE_LOGIN")
# or: fetch_user_project_fields "$PROJECT_NUMBER"

# Extract project info
PROJECT_ID=$(echo "$FIELDS_JSON" | jq -r '.data.organization.projectV2.id')
PROJECT_TITLE=$(echo "$FIELDS_JSON" | jq -r '.data.organization.projectV2.title')
PROJECT_URL=$(echo "$FIELDS_JSON" | jq -r '.data.organization.projectV2.url')
```

### Parse Fields

Extract field definitions with their types and options:

```bash
echo "$FIELDS_JSON" | jq '
    .data.organization.projectV2.fields.nodes | map(
        if .dataType == "SINGLE_SELECT" then
            {
                name: .name,
                id: .id,
                type: "single_select",
                options: (.options | map({(.name): .id}) | add)
            }
        elif .dataType == "ITERATION" then
            {
                name: .name,
                id: .id,
                type: "iteration",
                iterations: (.configuration.iterations | map({(.title): .id}) | add)
            }
        else
            {
                name: .name,
                id: .id,
                type: (.dataType | ascii_downcase)
            }
        end
    )
'
```

### Sample Field Output

```yaml
fields:
  Status:
    id: PVTSSF_lADOxxxxxxx
    type: single_select
    options:
      Backlog: PVTSSFO_xxxxxxx1
      Ready: PVTSSFO_xxxxxxx2
      In Progress: PVTSSFO_xxxxxxx3
      In Review: PVTSSFO_xxxxxxx4
      Done: PVTSSFO_xxxxxxx5
  Priority:
    id: PVTSSF_lADOyyyyyyy
    type: single_select
    options:
      P0 - Critical: PVTSSFO_yyyyyyy1
      P1 - High: PVTSSFO_yyyyyyy2
      P2 - Medium: PVTSSFO_yyyyyyy3
      P3 - Low: PVTSSFO_yyyyyyy4
  Sprint:
    id: PVTIF_lADOzzzzzzz
    type: iteration
    iterations:
      Sprint 1: PVTI_zzzzzzz1
      Sprint 2: PVTI_zzzzzzz2
  Due Date:
    id: PVTF_lADOaaaaaaa
    type: date
  Estimate:
    id: PVTF_lADObbbbbbb
    type: number
```

### Discover Repositories

Find repositories linked to projects or accessible in the org:

```bash
# Get linked repositories from project
LINKED_REPOS=$(fetch_linked_repositories "$PROJECT_ID")

# Or list org repositories
ORG_REPOS=$(gh api "orgs/${WORKSPACE_LOGIN}/repos" --paginate --jq '
    .[] | {
        name: .name,
        id: .node_id,
        full_name: .full_name,
        default_branch: .default_branch,
        visibility: .visibility
    }
')
```

### Discover Milestones

For each repository, fetch milestones:

```bash
REPO_NAME="api"

MILESTONES=$(gh api "repos/${WORKSPACE_LOGIN}/${REPO_NAME}/milestones" --jq '
    map({
        number: .number,
        id: .node_id,
        title: .title,
        state: .state,
        due_on: .due_on
    })
')
```

## Phase 5: Cache User Information

Get the authenticated user's identity and permissions.

### User Identity

```bash
USER_JSON=$(gh api user)
USER_LOGIN=$(echo "$USER_JSON" | jq -r '.login')
USER_ID=$(gh api graphql -H X-Github-Next-Global-ID:1 \
    -f query='{ viewer { id } }' --jq '.data.viewer.id')
USER_NAME=$(echo "$USER_JSON" | jq -r '.name')
USER_EMAIL=$(echo "$USER_JSON" | jq -r '.email')
```

### Organization Role

```bash
ORG_ROLE=$(gh api "orgs/${WORKSPACE_LOGIN}/memberships/${USER_LOGIN}" \
    --jq '.role' 2>/dev/null || echo "none")
```

### Repository Permissions

```bash
for REPO in api frontend docs; do
    PERMISSION=$(gh api "repos/${WORKSPACE_LOGIN}/${REPO}/collaborators/${USER_LOGIN}/permission" \
        --jq '.permission' 2>/dev/null || echo "none")
    echo "$REPO: $PERMISSION"
done
```

### Project Permissions

Project permissions require checking the project's collaborators or inferring from org role:

```bash
# Projects inherit from org for members
# Can check specific access via project collaborators API if needed
```

## Phase 6: Save Configurations

### Update config.yaml

```yaml
workspace:
  type: organization
  login: acme-corp
  id: O_kgDOxxxxxxx

projects:
  default: 2
  catalog:
    - number: 1
      id: PVT_kwDOxxxxxxx1
      title: Engineering Backlog
      url: https://github.com/orgs/acme-corp/projects/1
      fields:
        # ... discovered fields ...
    - number: 2
      id: PVT_kwDOxxxxxxx2
      title: Product Roadmap
      url: https://github.com/orgs/acme-corp/projects/2
      fields:
        # ... discovered fields ...

repositories:
  - name: api
    id: R_kgDOxxxxxxx
    full_name: acme-corp/api
    default_branch: main
    visibility: private
  - name: frontend
    id: R_kgDOyyyyyyy
    full_name: acme-corp/frontend
    default_branch: main
    visibility: private

milestones:
  api:
    - number: 1
      id: MI_xxxxxxx
      title: v1.0.0
      state: open
  frontend:
    - number: 1
      id: MI_yyyyyyy
      title: MVP
      state: open

cache:
  initialized_at: "2025-12-08T09:00:00Z"
  last_synced_at: "2025-12-08T10:00:00Z"
  toolkit_version: "2.1.0"
```

### Update user.yaml

```yaml
user:
  login: nathanielramm
  id: U_kgDOxxxxxxx
  name: Nathaniel Ramm
  email: nathaniel@example.com

permissions:
  org_role: member
  project_roles:
    1: write
    2: admin
  repo_roles:
    api: maintain
    frontend: write
    docs: read

preferences:
  default_project: null
  default_repo: null

cache:
  permissions_checked_at: "2025-12-08T10:00:00Z"
  permissions_ttl_hours: 24
```

## Output Summary

```
GitHub workspace analyzed!

Workspace: acme-corp (organization)

Projects cached: 2
  #1 - Engineering Backlog (5 fields)
  #2 - Product Roadmap (7 fields) [default]

Repositories cached: 3
  acme-corp/api (2 milestones)
  acme-corp/frontend (1 milestone)
  acme-corp/docs (0 milestones)

User: nathanielramm
  Org role: member
  Project #2: admin

Config saved:
  .hiivmind/github/config.yaml (shared)
  .hiivmind/github/user.yaml (personal)

You can now use simplified commands like:
  fetch_project | apply_status_filter "In Progress"
```

## Interactive Mode

When run interactively, present choices clearly:

1. Show discovered projects, ask which to include
2. Ask for default project
3. Show discovered repos, ask which to include
4. Confirm before writing

When run with flags, can skip interaction:
- `--all-projects` - Include all open projects
- `--all-repos` - Include all repositories
- `--default-project N` - Set default project number

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "No projects found" | No projects or no access | Check org membership and project visibility |
| "Rate limit exceeded" | Too many API calls | Wait or use authenticated token with higher limits |
| "Field not found" | Project structure changed | Re-run analyze to refresh |

## Reference

- Initialize workspace: `skills/github-workspace-init/SKILL.md`
- Refresh workspace: `skills/github-workspace-refresh/SKILL.md`
- Architecture: `docs/meta-skill-architecture.md`
- Field query functions: `lib/github/gh-project-functions.sh`
