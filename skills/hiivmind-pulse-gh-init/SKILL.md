---
name: hiivmind-pulse-gh-init
description: >
  Initialize GitHub workspace: verify CLI tools (gh, jq, yq), authenticate, discover projects,
  and cache IDs to config.yaml. Run once per repository. This is the ONLY prerequisite for
  GitHub operations - after init, use gh CLI directly with routing guide and corpus.
---

# GitHub Workspace Initialization

Single entry point for all setup. Run this once per repository.

## What This Does

1. Verifies gh CLI, jq, yq installed
2. Validates GitHub authentication and scopes
3. Detects workspace from git remote
4. Discovers projects and caches field IDs
5. Creates `.hiivmind/github/config.yaml` (team-shared)
6. Creates `.hiivmind/github/user.yaml` (personal, gitignored)

## Quick Check

Already initialized? Check for config:

```bash
ls -la .hiivmind/github/
```

If `config.yaml` exists and is recent, you're ready. Skip to "After Initialization".

---

## Step 1: Verify Prerequisites

### Check CLI Tools

```bash
gh --version && jq --version && yq --version
```

**Missing tools?**
```bash
# Ubuntu/Debian
sudo apt install gh jq
sudo snap install yq

# macOS
brew install gh jq yq
```

### Check Authentication

```bash
gh auth status
```

**Not authenticated?**
```bash
gh auth login
```

### Check Scopes

```bash
gh auth status | grep -i scopes
```

**Required scopes:** `repo`, `read:org`, `read:project`, `project`

**Missing scopes?**
```bash
gh auth refresh --scopes 'repo,read:org,read:project,project'
```

---

## Step 2: Detect Workspace

Get the owner from your git remote:

```bash
git remote get-url origin | sed -E 's#.*[:/]([^/]+)/[^/]+\.git$#\1#'
```

Determine if organization or user:

```bash
OWNER="hiivmind"  # from above
gh api "/users/$OWNER" --jq '.type' 2>/dev/null || echo "Organization"
```

---

## Step 3: Discover Projects

List available projects:

```bash
OWNER="hiivmind"
TYPE="organization"  # or "user"

if [[ "$TYPE" == "organization" ]]; then
  gh api graphql -f query='
    query($login: String!) {
      organization(login: $login) {
        projectsV2(first: 20) {
          nodes { number title closed }
        }
      }
    }
  ' -f login="$OWNER" --jq '.data.organization.projectsV2.nodes[] | "\(.number): \(.title) [\(if .closed then "closed" else "open" end)]"'
else
  gh api graphql -f query='
    query($login: String!) {
      user(login: $login) {
        projectsV2(first: 20) {
          nodes { number title closed }
        }
      }
    }
  ' -f login="$OWNER" --jq '.data.user.projectsV2.nodes[] | "\(.number): \(.title) [\(if .closed then "closed" else "open" end)]"'
fi
```

**Select which projects to cache** - typically all open ones.

---

## Step 4: Create Config Directory

```bash
mkdir -p .hiivmind/github
```

---

## Step 5: Generate config.yaml

Fetch workspace ID and project details, then create config:

```bash
OWNER="hiivmind"
TYPE="organization"
DEFAULT_PROJECT=2
PROJECTS="2"  # space-separated list

# Get workspace ID
if [[ "$TYPE" == "organization" ]]; then
  OWNER_ID=$(gh api graphql -f query='query($login: String!) { organization(login: $login) { id } }' -f login="$OWNER" --jq '.data.organization.id')
else
  OWNER_ID=$(gh api graphql -f query='query($login: String!) { user(login: $login) { id } }' -f login="$OWNER" --jq '.data.user.id')
fi

# Create base config
cat > .hiivmind/github/config.yaml << EOF
# hiivmind-pulse-gh workspace configuration
# Generated: $(date -Iseconds)

workspace:
  type: $TYPE
  login: $OWNER
  id: $OWNER_ID

projects:
  default: $DEFAULT_PROJECT
  catalog: []

repositories: []

milestones: {}

cache:
  initialized_at: $(date -Iseconds)
  last_synced_at: $(date -Iseconds)
EOF
```

### Add Project Details

For each project, fetch and add field IDs:

```bash
PROJECT_NUM=2

# Fetch project with fields
PROJECT_DATA=$(gh api graphql -f query='
  query($owner: String!, $number: Int!) {
    organization(login: $owner) {
      projectV2(number: $number) {
        id
        title
        url
        fields(first: 50) {
          nodes {
            ... on ProjectV2SingleSelectField {
              id
              name
              options { id name }
            }
            ... on ProjectV2Field {
              id
              name
            }
          }
        }
      }
    }
  }
' -f owner="$OWNER" -F number="$PROJECT_NUM")

# Extract and format (use yq to merge into config.yaml)
echo "$PROJECT_DATA" | jq '.data.organization.projectV2'
```

---

## Step 6: Generate user.yaml

```bash
# Fetch your identity
USER_DATA=$(gh api graphql -f query='{ viewer { login id name email } }')

LOGIN=$(echo "$USER_DATA" | jq -r '.data.viewer.login')
USER_ID=$(echo "$USER_DATA" | jq -r '.data.viewer.id')
NAME=$(echo "$USER_DATA" | jq -r '.data.viewer.name // empty')
EMAIL=$(echo "$USER_DATA" | jq -r '.data.viewer.email // empty')

cat > .hiivmind/github/user.yaml << EOF
# hiivmind-pulse-gh user configuration
# DO NOT COMMIT - add to .gitignore
# Generated: $(date -Iseconds)

user:
  login: $LOGIN
  id: $USER_ID
  name: $NAME
  email: $EMAIL

permissions:
  org_role: null
  project_roles: {}
  repo_roles: {}

preferences:
  default_project: null
  default_repo: null

cache:
  user_checked_at: $(date -Iseconds)
  permissions_checked_at: null
EOF
```

### Add to .gitignore

```bash
if ! grep -q "user.yaml" .gitignore 2>/dev/null; then
  echo ".hiivmind/github/user.yaml" >> .gitignore
fi
```

---

## Step 7: Verify Setup

```bash
echo "=== Config Summary ==="
yq '.workspace' .hiivmind/github/config.yaml
echo ""
echo "Projects cached:"
yq '.projects.catalog[].number' .hiivmind/github/config.yaml
echo ""
echo "Default project: $(yq '.projects.default' .hiivmind/github/config.yaml)"
```

---

## After Initialization

Once initialized, you DON'T need specialized skills. Instead:

1. **Load context:**
   ```bash
   CONFIG=".hiivmind/github/config.yaml"
   OWNER=$(yq '.workspace.login' "$CONFIG")
   ```

2. **Check routing:** Read `reference/api-routing.md` for which API (GraphQL vs REST)

3. **Get syntax:** Search corpus using keywords from routing guide

4. **Execute:** Use `gh api` or `gh` commands directly

### Example: Create Issue and Add to Project

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT=$(yq '.projects.default' "$CONFIG")

# Create issue
ISSUE_URL=$(gh issue create -R "$OWNER/repo" --title "New feature" --json url --jq '.url')

# Add to project
gh project item-add "$PROJECT" --owner "$OWNER" --url "$ISSUE_URL"
```

---

## Refreshing

If your config becomes stale (new projects, changed fields):

```bash
# Re-run init (will detect existing config)
# Or use hiivmind-pulse-gh-refresh for targeted updates
```

Signs you need refresh:
- "Field not found" errors
- "Option not found" errors
- New projects not appearing

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "gh: command not found" | Install GitHub CLI |
| "not logged in" | Run `gh auth login` |
| "missing scopes" | Run `gh auth refresh --scopes '...'` |
| "organization not found" | Check spelling, verify membership |
| "project not found" | Check project number, verify access |

---

## Corpus Lookup

Search the corpus index using these keywords:

| Need | Keywords |
|------|----------|
| GraphQL viewer | `viewer`, `User`, `login`, `id` |
| Organization query | `organization`, `projectsV2`, `teams` |
| Project fields | `ProjectV2Field`, `ProjectV2SingleSelectField`, `options` |
| Authentication | `gh auth`, `scopes`, `token` |

Start with `reference/api-routing.md` for routing decisions.
