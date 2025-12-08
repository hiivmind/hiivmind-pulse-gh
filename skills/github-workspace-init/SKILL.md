---
name: hiivmind-github-workspace-init
description: >
  Initialize and configure a GitHub workspace. Creates .hiivmind/github/ config structure,
  discovers projects/fields/repositories, and caches IDs for simplified operations.
  One-time setup that combines workspace creation with structure discovery.
  Run once per repository, then use hiivmind-github-workspace-refresh to keep in sync.
---

# GitHub Workspace Initializer

Complete workspace setup: create config structure, discover GitHub projects, and cache IDs for simplified operations.

## Process Overview

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  SETUP PHASE                                                                    │
│  1. CHECK      →  2. GATHER     →  3. VERIFY    →  4. CREATE                   │
│     (existing?)     (workspace)      (access)        (files)                    │
│                                                                                 │
│  DISCOVERY PHASE                                                                │
│  5. DISCOVER   →  6. SELECT     →  7. ANALYZE   →  8. CACHE USER  →  9. SAVE  │
│     (projects)      (which ones)     (fields)        (permissions)     (all)   │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## SETUP PHASE

### Phase 1: Check Existing

Before proceeding, check if configuration already exists:

```bash
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    echo "Workspace already initialized."
    echo "To reinitialize, remove .hiivmind/github/ first."
    echo "To update, run hiivmind-github-workspace-refresh."
    cat .hiivmind/github/config.yaml
    exit 0
fi
```

If a symlink exists, check where it points:
```bash
if [[ -L ".hiivmind" ]]; then
    echo "Found symlink: .hiivmind -> $(readlink .hiivmind)"
    echo "This repository uses shared workspace configuration."
fi
```

### Phase 2: Gather Information

Collect workspace details from the user:

| Input | Question | Options |
|-------|----------|---------|
| **Workspace Type** | "Is this for an organization or personal account?" | `organization` / `user` |
| **Login** | "What is the organization or username?" | e.g., `acme-corp` |

#### Deriving from Context

If the current repository is a git repo, we can infer:

```bash
# Get remote origin
REMOTE_URL=$(git remote get-url origin 2>/dev/null)

# Extract owner from GitHub URL
# https://github.com/acme-corp/repo-name → acme-corp
# git@github.com:acme-corp/repo-name.git → acme-corp
if [[ "$REMOTE_URL" =~ github\.com[:/]([^/]+)/ ]]; then
    SUGGESTED_LOGIN="${BASH_REMATCH[1]}"
    echo "Detected GitHub owner: $SUGGESTED_LOGIN"
fi
```

**Always confirm with user** before using derived values.

### Phase 3: Verify Access

Confirm the user has access to the workspace:

```bash
# For organization
gh api "orgs/${WORKSPACE_LOGIN}" --jq '.login' 2>/dev/null
if [[ $? -ne 0 ]]; then
    echo "Cannot access organization: ${WORKSPACE_LOGIN}"
    echo "Check: 1) Spelling  2) gh auth status  3) Organization membership"
    exit 1
fi

# For user (viewer = authenticated user)
gh api user --jq '.login'
```

Get the workspace's GraphQL node ID:

```bash
# Organization
ORG_ID=$(gh api graphql -H X-Github-Next-Global-ID:1 \
    -f query='query($login: String!) { organization(login: $login) { id } }' \
    -f login="$WORKSPACE_LOGIN" --jq '.data.organization.id')

# User
USER_ID=$(gh api graphql -H X-Github-Next-Global-ID:1 \
    -f query='{ viewer { id } }' --jq '.data.viewer.id')
```

### Phase 4: Create Directory Structure

```bash
mkdir -p .hiivmind/github
```

---

## DISCOVERY PHASE

### Phase 5: Discover Projects

Find all accessible projects in the workspace.

#### For Organizations

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

#### For Users

```bash
PROJECTS_JSON=$(discover_user_projects)

echo "$PROJECTS_JSON" | jq -r '
    .data.viewer.projectsV2.nodes[] |
    "  #\(.number) - \(.title) [\(.closed | if . then "closed" else "open" end)]"
'
```

#### Sample Output

```
Found 3 projects in acme-corp:
  #1 - Engineering Backlog [open]
  #2 - Product Roadmap [open]
  #5 - Archive 2024 [closed]
```

### Phase 6: Select Projects

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

### Phase 7: Analyze Selected Projects

For each selected project, discover complete field structure.

#### Fetch Project Details

```bash
PROJECT_NUMBER=2

# Get project with all fields
FIELDS_JSON=$(fetch_org_project_fields "$PROJECT_NUMBER" "$WORKSPACE_LOGIN")

# Extract project info
PROJECT_ID=$(echo "$FIELDS_JSON" | jq -r '.data.organization.projectV2.id')
PROJECT_TITLE=$(echo "$FIELDS_JSON" | jq -r '.data.organization.projectV2.title')
PROJECT_URL=$(echo "$FIELDS_JSON" | jq -r '.data.organization.projectV2.url')
```

#### Parse Fields

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

#### Sample Field Output

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
  Due Date:
    id: PVTF_lADOaaaaaaa
    type: date
```

#### Discover Repositories

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

#### Discover Milestones

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

### Phase 8: Cache User Information

Get the authenticated user's identity and permissions.

#### User Identity

```bash
USER_JSON=$(gh api user)
USER_LOGIN=$(echo "$USER_JSON" | jq -r '.login')
USER_ID=$(gh api graphql -H X-Github-Next-Global-ID:1 \
    -f query='{ viewer { id } }' --jq '.data.viewer.id')
USER_NAME=$(echo "$USER_JSON" | jq -r '.name')
USER_EMAIL=$(echo "$USER_JSON" | jq -r '.email')
```

#### Organization Role

```bash
ORG_ROLE=$(gh api "orgs/${WORKSPACE_LOGIN}/memberships/${USER_LOGIN}" \
    --jq '.role' 2>/dev/null || echo "none")
```

#### Repository Permissions

```bash
for REPO in api frontend docs; do
    PERMISSION=$(gh api "repos/${WORKSPACE_LOGIN}/${REPO}/collaborators/${USER_LOGIN}/permission" \
        --jq '.permission' 2>/dev/null || echo "none")
    echo "$REPO: $PERMISSION"
done
```

### Phase 9: Save Configurations

#### config.yaml (Shared)

```yaml
# hiivmind-github-skills - Workspace Configuration
# This file is shared across the team and should be committed to git.
# Generated by hiivmind-github-workspace-init on 2025-12-08T10:00:00Z

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
        Status:
          id: PVTSSF_xxxxxxx
          type: single_select
          options:
            Backlog: PVTSSFO_xxx1
            In Progress: PVTSSFO_xxx2
            Done: PVTSSFO_xxx3
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
  initialized_at: "2025-12-08T10:00:00Z"
  last_synced_at: "2025-12-08T10:00:00Z"
  toolkit_version: "3.0.0"
```

#### user.yaml (Personal)

```yaml
# hiivmind-github-skills - User Configuration
# This file contains user-specific settings and should NOT be committed to git.
# Add to .gitignore: .hiivmind/github/user.yaml

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

preferences:
  default_project: null
  default_repo: null

cache:
  permissions_checked_at: "2025-12-08T10:00:00Z"
  permissions_ttl_hours: 24
```

#### Gitignore Suggestion

```bash
GITIGNORE_LINE=".hiivmind/github/user.yaml"

if [[ -f ".gitignore" ]]; then
    if ! grep -q "$GITIGNORE_LINE" .gitignore; then
        echo "Add to .gitignore: $GITIGNORE_LINE"
    fi
else
    echo "Create .gitignore with: echo '$GITIGNORE_LINE' > .gitignore"
fi
```

---

## Output Summary

After successful initialization:

```
GitHub workspace initialized!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
  .hiivmind/github/config.yaml (shared - commit this)
  .hiivmind/github/user.yaml (personal - add to .gitignore)

Next steps:
  1. Add to .gitignore: .hiivmind/github/user.yaml
  2. Commit .hiivmind/github/config.yaml to share with team
  3. Use hiivmind-github-workspace-refresh to keep IDs in sync
```

---

## Interactive Mode Options

When run interactively, present choices clearly:

1. Show discovered projects, ask which to include
2. Ask for default project
3. Show discovered repos, ask which to include
4. Confirm before writing

With flags for automation:
- `--all-projects` - Include all open projects
- `--all-repos` - Include all repositories
- `--default-project N` - Set default project number

---

## Multi-Repository Setup

If user wants to share config across multiple repositories:

```bash
# Create centralized config location
mkdir -p ~/github-workspaces/acme-corp
cd ~/github-workspaces/acme-corp
# ... run init here ...

# Then in each repo:
cd ~/projects/api
ln -s ~/github-workspaces/acme-corp .hiivmind

cd ~/projects/frontend
ln -s ~/github-workspaces/acme-corp .hiivmind
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Cannot access organization" | No membership or wrong name | Verify spelling, check `gh auth status` |
| "No projects found" | No projects or no access | Check org membership and project visibility |
| "gh: command not found" | GitHub CLI not installed | Install from cli.github.com |
| "gh: not logged in" | Not authenticated | Run `gh auth login` |
| "Directory exists" | Previous init | Remove `.hiivmind/github/` and retry |
| "Rate limit exceeded" | Too many API calls | Wait or use token with higher limits |

---

## Reference

- Refresh workspace: `skills/github-workspace-refresh/SKILL.md`
- Investigate entities: `skills/github-investigate/SKILL.md`
- Architecture: `docs/meta-skill-architecture.md`
- Config schema: `templates/config.yaml.template`
