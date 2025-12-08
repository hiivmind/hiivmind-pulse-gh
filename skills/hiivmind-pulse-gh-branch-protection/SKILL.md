---
name: hiivmind-pulse-gh-branch-protection
description: Manage GitHub branch protection rules and repository rulesets using the REST API. Use when setting up branch protection, enforcing naming conventions, or configuring pattern-based protection rules.
---

# GitHub Branch Protection Skill

You are an expert at using hiivmind-pulse-gh's Branch Protection module - for managing branch protection rules and repository rulesets via the REST API.

## Important Concepts

### Branch Protection vs Rulesets

| Feature | Branch Protection (Legacy) | Rulesets (Modern) |
|---------|---------------------------|-------------------|
| **Scope** | Per-branch (main, develop) | Pattern-based (feature/*, release/*) |
| **Availability** | All repositories | Organization repos only |
| **Flexibility** | Fixed branch names | Regex patterns, multiple conditions |
| **Management** | Individual branches | Centralized rule sets |

**When to use which:**
- **Branch Protection**: For specific named branches (main, develop) in any repo
- **Rulesets**: For pattern-based rules in organization repositories

### Organization vs Personal Repositories

| Setting | Organization Repo | Personal Repo |
|---------|------------------|---------------|
| `restrictions` | Object with users/teams/apps | Must be `null` |
| `required_signatures` | Supported | Not supported |
| `bypass_pull_request_allowances` | Supported | Not supported |
| Rulesets | Supported | Not supported |

## Prerequisites

**Required setup (run once):**
1. `hiivmind-pulse-gh-user-init` - Validates environment, creates `user.yaml`
2. `hiivmind-pulse-gh-workspace-init` - Discovers repos, creates `config.yaml`

**Runtime requirements:**
```bash
# Source the REST functions
source lib/github/gh-rest-functions.sh
```

## Workspace Configuration

If a `.hiivmind/github/config.yaml` file exists in the repository root, use it to simplify commands:

```bash
CONFIG_PATH=".hiivmind/github/config.yaml"

if [[ -f "$CONFIG_PATH" ]]; then
    # Load workspace context
    ORG=$(yq '.workspace.login' "$CONFIG_PATH")
    WORKSPACE_TYPE=$(yq '.workspace.type' "$CONFIG_PATH")

    # Get cached repository info
    get_repo_default_branch() {
        local repo_name="$1"
        yq ".repositories[] | select(.name == \"$repo_name\") | .default_branch" "$CONFIG_PATH"
    }
fi
```

### With Config (Simplified)

```bash
# Apply protection using org from config
apply_main_branch_protection "$ORG" "api"

# Get default branch from config
DEFAULT_BRANCH=$(get_repo_default_branch "api")
get_branch_protection "$ORG" "api" "$DEFAULT_BRANCH" | format_branch_protection
```

### Without Config (Explicit)

```bash
# Must specify owner explicitly
apply_main_branch_protection "acme-corp" "api"

# Must know or look up default branch
get_branch_protection "acme-corp" "api" "main" | format_branch_protection
```

### Setup Workspace

To create a workspace configuration:
1. Run `hiivmind-pulse-gh-workspace-init` to create and populate `.hiivmind/github/config.yaml`
2. Commit `config.yaml` to share with team

## Function Reference

### Branch Protection (Legacy API)

| Function | Purpose | Example |
|----------|---------|---------|
| `get_branch_protection "OWNER" "REPO" "BRANCH"` | Get protection rules | `get_branch_protection "acme" "api" "main"` |
| `check_branch_protection_exists "OWNER" "REPO" "BRANCH"` | Check if protected | `check_branch_protection_exists "acme" "api" "main"` |
| `set_branch_protection "OWNER" "REPO" "BRANCH"` | Set protection (stdin) | `echo '{}' \| set_branch_protection "acme" "api" "main"` |
| `format_branch_protection` | Format for display | `get_branch_protection "acme" "api" "main" \| format_branch_protection` |

### Repository Rulesets (Modern API)

| Function | Purpose | Example |
|----------|---------|---------|
| `list_rulesets "OWNER" "REPO"` | List all rulesets | `list_rulesets "acme" "api"` |
| `get_ruleset "OWNER" "REPO" ID` | Get specific ruleset | `get_ruleset "acme" "api" 123` |
| `get_ruleset_by_name "OWNER" "REPO" "NAME"` | Get by name | `get_ruleset_by_name "acme" "api" "Branch Naming"` |
| `check_ruleset_exists "OWNER" "REPO" "NAME"` | Check if exists | `check_ruleset_exists "acme" "api" "Branch Naming"` |
| `create_ruleset "OWNER" "REPO"` | Create (stdin) | `echo '{}' \| create_ruleset "acme" "api"` |
| `update_ruleset "OWNER" "REPO" ID` | Update (stdin) | `echo '{}' \| update_ruleset "acme" "api" 123` |
| `create_or_update_ruleset "OWNER" "REPO" "NAME"` | Upsert (stdin) | `echo '{}' \| create_or_update_ruleset "acme" "api" "My Rule"` |
| `format_rulesets` | Format for display | `list_rulesets "acme" "api" \| format_rulesets` |

### Template Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `get_protection_template "NAME"` | Get protection config | `get_protection_template "main_org"` |
| `get_ruleset_template "NAME"` | Get ruleset config | `get_ruleset_template "branch_naming"` |
| `list_protection_templates` | List available | `list_protection_templates` |
| `list_ruleset_templates` | List available | `list_ruleset_templates` |

### Smart Application Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `apply_main_branch_protection "OWNER" "REPO"` | Auto-detect and apply | `apply_main_branch_protection "acme" "api"` |
| `apply_develop_branch_protection "OWNER" "REPO"` | Auto-detect and apply | `apply_develop_branch_protection "acme" "api"` |
| `apply_branch_naming_ruleset "OWNER" "REPO"` | Apply naming rules | `apply_branch_naming_ruleset "acme" "api"` |
| `apply_release_branch_ruleset "OWNER" "REPO"` | Apply release rules | `apply_release_branch_ruleset "acme" "api"` |

### Helper Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `detect_repo_type "OWNER" "REPO"` | Get repo type | `detect_repo_type "acme" "api"` → "organization" |
| `list_branches "OWNER" "REPO"` | List branches | `list_branches "acme" "api"` |
| `check_branch_exists "OWNER" "REPO" "BRANCH"` | Check if exists | `check_branch_exists "acme" "api" "main"` |
| `format_branches` | Format for display | `list_branches "acme" "api" \| format_branches` |

## Available Templates

### Branch Protection Templates

| Template | Description |
|----------|-------------|
| `main_org` | Strict main branch for orgs (2 approvals, code owners, signed commits) |
| `main_personal` | Relaxed main branch for personal repos (1 approval) |
| `develop_org` | Moderate develop branch for orgs (1 approval, code owners) |
| `develop_personal` | Light develop branch for personal repos |
| `minimal` | Bare minimum (just prevent force push/delete) |

### Ruleset Templates

| Template | Description |
|----------|-------------|
| `branch_naming` | Enforce naming convention (main, develop, feature/*, etc.) |
| `release_branches` | Protect release/* branches |
| `feature_branches` | Light protection for feature/* |
| `hotfix_branches` | Protection for hotfix/* |
| `tag_protection` | Protect tags from unauthorized changes |

## Common Workflows

### Protect Main Branch (Auto-detect)

```bash
source lib/github/gh-rest-functions.sh

# Automatically applies org or personal template
apply_main_branch_protection "acme" "api"
```

### Protect Main Branch (Manual)

```bash
source lib/github/gh-rest-functions.sh

# Check repo type
detect_repo_type "acme" "api"  # → "organization"

# Get and apply template
get_protection_template "main_org" | set_branch_protection "acme" "api" "main"
```

### Set Up Branch Naming Convention

```bash
source lib/github/gh-rest-functions.sh

# Apply the branch naming ruleset
apply_branch_naming_ruleset "acme" "api"

# Or manually with custom pattern
get_ruleset_template "branch_naming" | \
    jq '.rules[0].parameters.pattern = "^(main|dev)|((feat|fix)/.+)$"' | \
    create_or_update_ruleset "acme" "api" "Branch Naming Convention"
```

### Check Current Protection

```bash
source lib/github/gh-rest-functions.sh

# Get formatted protection info
get_branch_protection "acme" "api" "main" | format_branch_protection

# List all rulesets
list_rulesets "acme" "api" | format_rulesets
```

### Custom Protection Configuration

```bash
source lib/github/gh-rest-functions.sh

# Create custom config and apply
cat << 'EOF' | set_branch_protection "acme" "api" "main"
{
    "required_status_checks": {
        "strict": true,
        "contexts": ["ci/build", "ci/test"]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews": true
    },
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false
}
EOF
```

### Set Up Full Repository Protection (Org)

```bash
source lib/github/gh-rest-functions.sh

# Protect main and develop branches
apply_main_branch_protection "acme" "api"
apply_develop_branch_protection "acme" "api"

# Add branch naming convention
apply_branch_naming_ruleset "acme" "api"

# Add release branch protection
apply_release_branch_ruleset "acme" "api"
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| 404 | Branch/ruleset doesn't exist | Check branch exists first |
| 403 | Insufficient permissions | Ensure admin access |
| 422 | Invalid configuration | Check JSON structure |
| 404 on restrictions | Personal repo with restrictions object | Set `restrictions: null` |

Required token scopes:
```bash
gh auth refresh -s repo -s admin:repo_hook
```

## Related Skills

- **hiivmind-pulse-gh-projects** - Project management (status updates, views, fields)
- **hiivmind-pulse-gh-milestones** - Milestone management
