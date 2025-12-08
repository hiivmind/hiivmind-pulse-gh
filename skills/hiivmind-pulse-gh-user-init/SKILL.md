---
name: hiivmind-pulse-gh-user-init
description: >
  First-time user setup: verify GitHub CLI installation, authenticate with required scopes,
  check dependencies (yq, jq), and persist user identity to .hiivmind/github/user.yaml.
  This is a PREREQUISITE for ALL other skills. Re-run if you encounter scope/permission errors.
---

# GitHub User Setup

Verify environment, authenticate, and persist user identity. This is a **prerequisite for ALL other skills**.

## Skill Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  hiivmind-pulse-gh-user-init          ← YOU ARE HERE (run first, always)   │
│       │                                                                     │
│       ▼                                                                     │
│  hiivmind-pulse-gh-workspace-init     ← Requires user-init                 │
│       │                                                                     │
│       ▼                                                                     │
│  All other skills                     ← Require user-init + workspace-init │
│  (projects, milestones, investigate, branch-protection, workspace-refresh) │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

The simplest way to initialize a user using the provided functions:

```bash
# 1. Source the user functions
source lib/github/gh-user-functions.sh

# 2. Run the complete initialization
initialize_user
```

That's it! The `initialize_user` function handles everything:
1. Checks all CLI tools (gh, jq, yq)
2. Validates GitHub authentication
3. Checks token scopes
4. Fetches your identity from GitHub
5. Creates `.hiivmind/github/user.yaml`

---

## What This Skill Does

| Step | Action | Function |
|------|--------|----------|
| 1 | Check gh CLI installed | `check_gh_cli` |
| 2 | Check jq installed | `check_jq` |
| 3 | Check yq installed | `check_yq` |
| 4 | Validate GitHub auth | `check_gh_auth` |
| 5 | Check token scopes | `check_required_scopes` |
| 6 | Test Projects v2 access | `check_projects_access` |
| 7 | Fetch user identity | `fetch_user_identity` |
| 8 | Save to user.yaml | `save_user_yaml` |

---

## Process Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. SOURCE       →  2. CHECK        →  3. FETCH       →  4. SAVE           │
│     (functions)      (prerequisites)    (identity)        (user.yaml)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Implementation

### Step 1: Source Functions

```bash
source lib/github/gh-user-functions.sh
```

### Step 2: Check Prerequisites

```bash
if ! check_all_prerequisites; then
    echo "Please fix the issues above before continuing."
    exit 1
fi
```

This checks:
- `gh` CLI is installed
- `jq` is installed
- `yq` is installed
- GitHub CLI is authenticated
- Token has required scopes
- Projects v2 access works

### Step 3: Fetch User Identity

```bash
USER_JSON=$(fetch_user_identity)
echo "$USER_JSON" | display_user_identity
```

**Output:**
```
User identity:
  Login: discreteds
  ID:    U_kgDOxxxxxxx
  Name:  Nathaniel Ramm
```

### Step 4: Save to user.yaml

```bash
echo "$USER_JSON" | save_user_yaml
```

This creates or updates `.hiivmind/github/user.yaml`.

---

## Available Functions Reference

### CLI Tool Checks

| Function | Description |
|----------|-------------|
| `check_gh_cli` | Check if gh is installed, return 0/1 |
| `check_jq` | Check if jq is installed, return 0/1 |
| `check_yq` | Check if yq is installed, return 0/1 |
| `get_gh_version` | Output gh version string |
| `get_jq_version` | Output jq version string |
| `get_yq_version` | Output yq version string |

### Authentication Checks

| Function | Description |
|----------|-------------|
| `check_gh_auth` | Check if authenticated, return 0/1 |
| `get_auth_account` | Output authenticated username |
| `get_current_scopes` | Output current token scopes |
| `has_scope SCOPE` | Check if specific scope present |
| `check_required_scopes` | Check all required scopes present |
| `check_projects_access` | Test Projects v2 API access |
| `get_missing_required_scopes` | Output missing required scopes |
| `get_missing_recommended_scopes` | Output missing recommended scopes |
| `get_scope_fix_command` | Output command to fix scopes |

### Combined Check

| Function | Description |
|----------|-------------|
| `check_all_prerequisites` | Run all checks, show status, return 0/1 |

### User Identity

| Function | Description |
|----------|-------------|
| `fetch_user_identity` | Fetch user from GitHub API (outputs JSON) |
| `display_user_identity` | Display user info (reads JSON from stdin) |

### user.yaml Management

| Function | Description |
|----------|-------------|
| `user_yaml_exists` | Check if user.yaml exists, return 0/1 |
| `create_user_yaml LOGIN ID NAME EMAIL` | Create new user.yaml |
| `update_user_yaml LOGIN ID NAME EMAIL` | Update existing user.yaml |
| `save_user_yaml` | Create or update (reads JSON from stdin) |

### Gitignore

| Function | Description |
|----------|-------------|
| `check_gitignore_has_user_yaml` | Check if user.yaml is gitignored |
| `remind_gitignore` | Print reminder if not gitignored |

### Main Workflow

| Function | Description |
|----------|-------------|
| `initialize_user` | Complete initialization workflow |
| `print_user_init_help` | Print help text |

---

## Required Scopes

| Scope | Purpose | Required |
|-------|---------|----------|
| `repo` | Repository access, issues, PRs | Yes |
| `read:org` | Organization membership | Yes |
| `read:project` | Read Projects v2 data | Recommended |
| `project` | Write Projects v2 data | Recommended |

**Fix missing scopes:**
```bash
gh auth refresh --scopes 'repo,read:org,read:project,project'
```

---

## Output Files

### user.yaml

Created at `.hiivmind/github/user.yaml`:

```yaml
# hiivmind-pulse-gh - User Configuration
# Add to .gitignore: .hiivmind/github/user.yaml

user:
  login: discreteds
  id: U_kgDOxxxxxxx
  name: Nathaniel Ramm
  email: null

permissions:
  org_role: null
  project_roles: {}
  repo_roles: {}

preferences:
  default_project: null
  default_repo: null

cache:
  user_checked_at: "2025-12-09T10:00:00Z"
  permissions_checked_at: null
  permissions_ttl_hours: 24
```

**Keep this in .gitignore** - contains personal identity.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "gh not installed" | GitHub CLI missing | `sudo apt install gh` |
| "jq not installed" | jq missing | `sudo apt install jq` |
| "yq not installed" | yq missing | `sudo snap install yq` |
| "Not authenticated" | gh not logged in | `gh auth login` |
| "Missing required scopes" | Token lacks scopes | `gh auth refresh --scopes '...'` |
| "Projects v2 access failed" | Missing project scope | `gh auth refresh --scopes '...'` |

---

## Quick Fix Commands

```bash
# Install tools
sudo apt install gh jq
sudo snap install yq

# Authenticate
gh auth login

# Add required scopes
gh auth refresh --scopes 'repo,read:org,read:project,project'

# If scopes still fail, re-authenticate completely
gh auth logout
gh auth login --scopes 'repo,read:org,read:project,project'
```

---

## Templates

The `create_user_yaml` function uses the template at `templates/user.yaml.template`.

The template defines the expected structure:
```yaml
user:
  login: null
  id: null
  name: null
  email: null

permissions:
  org_role: null
  project_roles: {}
  repo_roles: {}

preferences:
  default_project: null
  default_repo: null

cache:
  user_checked_at: null
  permissions_checked_at: null
  permissions_ttl_hours: 24
```

If you need to modify the user.yaml structure, update the template first.

---

## Reference

- **Functions library:** `lib/github/gh-user-functions.sh`
- **Template:** `templates/user.yaml.template`
- **Initialize workspace:** `skills/hiivmind-pulse-gh-workspace-init/SKILL.md`
- **GitHub CLI docs:** https://cli.github.com/manual/
- **yq docs:** https://mikefarah.gitbook.io/yq/
