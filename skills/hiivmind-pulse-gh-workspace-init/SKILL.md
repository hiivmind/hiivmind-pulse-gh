---
name: hiivmind-pulse-gh-workspace-init
description: >
  Initialize and configure a GitHub workspace. Creates .hiivmind/github/config.yaml,
  discovers projects/fields/repositories, and enriches user.yaml with permissions.
  REQUIRES hiivmind-pulse-gh-user-init to be run first (creates user.yaml).
  Run once per repository, then use hiivmind-pulse-gh-workspace-refresh to keep in sync.
---

# GitHub Workspace Initializer

Complete workspace setup: create config structure, discover GitHub projects, and cache IDs for simplified operations.

## Skill Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  hiivmind-pulse-gh-user-init          ← Must run FIRST (creates user.yaml) │
│       │                                                                     │
│       ▼                                                                     │
│  hiivmind-pulse-gh-workspace-init     ← YOU ARE HERE                       │
│       │                                                                     │
│       ▼                                                                     │
│  All other skills                     ← Require both init skills           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

**REQUIRED:** Run `hiivmind-pulse-gh-user-init` first. This skill expects:
- `.hiivmind/github/user.yaml` to exist with user identity
- GitHub CLI (`gh`) authenticated with required scopes
- Dependencies installed (`jq`, `yq`)

```bash
# Check for user.yaml (created by user-init)
if [[ ! -f ".hiivmind/github/user.yaml" ]]; then
    echo "ERROR: user.yaml not found."
    echo "Run hiivmind-pulse-gh-user-init first."
    exit 1
fi

# Read user identity from existing user.yaml
USER_LOGIN=$(yq '.user.login' .hiivmind/github/user.yaml)
USER_ID=$(yq '.user.id' .hiivmind/github/user.yaml)
echo "User: $USER_LOGIN ($USER_ID)"
```

## Process Overview

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  SETUP PHASE                                                                    │
│  1. CHECK      →  2. GATHER     →  3. VERIFY    →  4. CREATE                   │
│     (user.yaml?)    (workspace)      (access)        (config.yaml)             │
│                                                                                 │
│  DISCOVERY PHASE                                                                │
│  5. DISCOVER   →  6. SELECT     →  7. ANALYZE   →  8. ENRICH USER  →  9. SAVE │
│     (projects)      (which ones)     (fields)        (permissions)      (all)  │
└────────────────────────────────────────────────────────────────────────────────┘

Note: User identity is read from user.yaml (created by user-init).
      This skill only ENRICHES user.yaml with permissions, not recreates it.
```

---

## SETUP PHASE

### Phase 1: Check Prerequisites and Existing Config

**First**, verify user-init has been run:

```bash
USER_CONFIG_PATH=".hiivmind/github/user.yaml"

if [[ ! -f "$USER_CONFIG_PATH" ]]; then
    echo "ERROR: user.yaml not found at $USER_CONFIG_PATH"
    echo ""
    echo "You must run hiivmind-pulse-gh-user-init first."
    echo "This skill requires user.yaml to exist with your GitHub identity."
    exit 1
fi

# Load user identity for later use
USER_LOGIN=$(yq '.user.login' "$USER_CONFIG_PATH")
USER_ID=$(yq '.user.id' "$USER_CONFIG_PATH")

if [[ "$USER_LOGIN" == "null" || -z "$USER_LOGIN" ]]; then
    echo "ERROR: user.yaml exists but user.login is not set."
    echo "Re-run hiivmind-pulse-gh-user-init to populate user identity."
    exit 1
fi

echo "User: $USER_LOGIN"
```

**Then**, check if workspace config already exists:

```bash
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    echo "Workspace already initialized."
    echo "To reinitialize, remove .hiivmind/github/config.yaml first."
    echo "To update, run hiivmind-pulse-gh-workspace-refresh."
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

### Phase 8: Enrich User Permissions

The user identity already exists in `user.yaml` (created by `user-init`). This phase adds **permissions** for the workspace being initialized.

#### Read User Identity (from existing user.yaml)

```bash
USER_CONFIG_PATH=".hiivmind/github/user.yaml"

# User identity already populated by user-init
USER_LOGIN=$(yq '.user.login' "$USER_CONFIG_PATH")
USER_ID=$(yq '.user.id' "$USER_CONFIG_PATH")

echo "Enriching permissions for user: $USER_LOGIN"
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
# hiivmind-pulse-gh - Workspace Configuration
# This file is shared across the team and should be committed to git.
# Generated by hiivmind-pulse-gh-workspace-init on 2025-12-08T10:00:00Z

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

#### user.yaml (Enriched with Permissions)

The `user.yaml` file was **created by user-init** with user identity. This skill **enriches** it with workspace-specific permissions:

```bash
USER_CONFIG_PATH=".hiivmind/github/user.yaml"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Update permissions section (user section already populated by user-init)
yq -i ".permissions.org_role = \"$ORG_ROLE\"" "$USER_CONFIG_PATH"
yq -i ".permissions.project_roles.$PROJECT_NUMBER = \"$PROJECT_ROLE\"" "$USER_CONFIG_PATH"
yq -i ".permissions.repo_roles.$REPO_NAME = \"$REPO_ROLE\"" "$USER_CONFIG_PATH"
yq -i ".cache.permissions_checked_at = \"$TIMESTAMP\"" "$USER_CONFIG_PATH"
```

**Result (after enrichment):**

```yaml
# hiivmind-pulse-gh - User Configuration
# Generated by hiivmind-pulse-gh-user-init on 2025-12-08T09:00:00Z
# Permissions enriched by hiivmind-pulse-gh-workspace-init on 2025-12-08T10:00:00Z
# Add to .gitignore: .hiivmind/github/user.yaml

user:                           # ← Populated by user-init
  login: nathanielramm
  id: U_kgDOxxxxxxx
  name: Nathaniel Ramm
  email: nathaniel@example.com

permissions:                    # ← Enriched by workspace-init
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
  user_checked_at: "2025-12-08T09:00:00Z"          # ← Set by user-init
  permissions_checked_at: "2025-12-08T10:00:00Z"  # ← Set by workspace-init
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

User: nathanielramm (from user.yaml)
  Org role: member
  Project #2: admin

Config saved:
  .hiivmind/github/config.yaml (shared - commit this)
  .hiivmind/github/user.yaml (enriched with permissions)

Next steps:
  1. Commit .hiivmind/github/config.yaml to share with team
  2. Use hiivmind-pulse-gh-workspace-refresh to keep IDs in sync
  3. You're ready to use all hiivmind-pulse-gh skills!
```

**Note:** The `user.yaml` file was created by `user-init` and enriched with permissions by this skill. Ensure it's in your `.gitignore`.

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
| "user.yaml not found" | user-init not run | Run `hiivmind-pulse-gh-user-init` first |
| "user.login is not set" | Corrupted user.yaml | Re-run `hiivmind-pulse-gh-user-init` |
| "Cannot access organization" | No membership or wrong name | Verify spelling, check `gh auth status` |
| "No projects found" | No projects or no access | Check org membership and project visibility |
| "gh: command not found" | GitHub CLI not installed | Install from cli.github.com |
| "gh: not logged in" | Not authenticated | Run `gh auth login` |
| "config.yaml exists" | Previous init | Remove `.hiivmind/github/config.yaml` and retry |
| "Rate limit exceeded" | Too many API calls | Wait or use token with higher limits |

---

## Reference

- Refresh workspace: `skills/hiivmind-pulse-gh-workspace-refresh/SKILL.md`
- Investigate entities: `skills/hiivmind-pulse-gh-investigate/SKILL.md`
- Architecture: `docs/meta-skill-architecture.md`
- Config schema: `templates/config.yaml.template`
