# Protection Domain Functions Index

> **Domain:** Protection (Branch Protection Rules + Repository Rulesets)
> **File:** `gh-protection-functions.sh`
> **Created:** 2025-12-11

This domain provides a unified interface for GitHub repository protection:
- **Legacy Branch Protection Rules** - Per-branch rules (REST-primary)
- **Modern Repository Rulesets** - Pattern-based rules (GraphQL-primary)
- **Organization Rulesets** - Org-wide rules

---

## Quick Reference

### FETCH Primitives

| Function | Args | Description |
|----------|------|-------------|
| `fetch_branch_protection` | `owner`, `repo`, `branch` | Get protection for specific branch (REST) |
| `fetch_branch_protection_graphql` | `owner`, `repo`, `pattern` | Get protection via GraphQL |
| `fetch_repo_rulesets` | `owner`, `repo`, `[include_parents]` | List repo rulesets (REST) |
| `fetch_repo_rulesets_graphql` | `owner`, `repo`, `[targets]` | List repo rulesets (GraphQL) |
| `fetch_org_rulesets` | `org` | List org rulesets (REST) |
| `fetch_org_rulesets_graphql` | `org` | List org rulesets (GraphQL) |
| `fetch_ruleset` | `owner`, `repo`, `ruleset_id` | Get specific ruleset by ID |
| `fetch_ruleset_by_name` | `owner`, `repo`, `name` | Get ruleset by name |

### DISCOVER Primitives

| Function | Args | Description |
|----------|------|-------------|
| `discover_repo_branch_protections` | `owner`, `repo` | All branch protection rules |
| `discover_repo_rulesets` | `owner`, `repo` | All repo rulesets |
| `discover_org_rulesets` | `org` | All org rulesets |
| `discover_rules_for_branch` | `owner`, `repo`, `branch` | Rules applying to branch |

### LOOKUP Primitives

| Function | Args | Description |
|----------|------|-------------|
| `get_branch_protection_rule_id` | `owner`, `repo`, `pattern` | Node ID by pattern |
| `get_ruleset_id` | `owner`, `repo`, `name` | Ruleset ID by name |
| `get_org_ruleset_id` | `org`, `name` | Org ruleset ID by name |

### DETECT Primitives

| Function | Args | Description |
|----------|------|-------------|
| `detect_branch_protection_exists` | `owner`, `repo`, `branch` | Check if protection exists |
| `detect_ruleset_exists` | `owner`, `repo`, `name` | Check if ruleset exists |
| `detect_protection_source` | `owner`, `repo`, `branch` | Identify protection source |

### FILTER Primitives (stdin → stdout)

| Function | Args | Description |
|----------|------|-------------|
| `filter_rulesets_by_target` | `target` | Filter by BRANCH/TAG/PUSH |
| `filter_rulesets_by_enforcement` | `enforcement` | Filter by ACTIVE/EVALUATE/DISABLED |
| `filter_rules_by_type` | `type` | Filter by rule type |

### FORMAT Primitives (stdin → stdout)

| Function | Description |
|----------|-------------|
| `format_branch_protection` | Human-readable protection |
| `format_rulesets` | Human-readable ruleset list |
| `format_ruleset_detail` | Detailed ruleset view |
| `format_rules_for_branch` | Rules applying to branch |

### MUTATE Primitives - Branch Protection

| Function | Args | Description |
|----------|------|-------------|
| `set_branch_protection_rest` | `owner`, `repo`, `branch` + stdin | Set via REST |
| `delete_branch_protection_rest` | `owner`, `repo`, `branch` | Delete via REST |
| `create_branch_protection` | `repo_id`, `pattern` + stdin | Create via GraphQL |
| `update_branch_protection` | `rule_id` + stdin | Update via GraphQL |
| `delete_branch_protection` | `rule_id` | Delete via GraphQL |

### MUTATE Primitives - Repository Rulesets

| Function | Args | Description |
|----------|------|-------------|
| `create_repo_ruleset` | `owner`, `repo` + stdin | Create ruleset |
| `update_repo_ruleset` | `owner`, `repo`, `ruleset_id` + stdin | Update ruleset |
| `delete_repo_ruleset` | `owner`, `repo`, `ruleset_id` | Delete ruleset |
| `upsert_repo_ruleset` | `owner`, `repo`, `name` + stdin | Create or update |

### MUTATE Primitives - Organization Rulesets

| Function | Args | Description |
|----------|------|-------------|
| `create_org_ruleset` | `org` + stdin | Create org ruleset |
| `update_org_ruleset` | `org`, `ruleset_id` + stdin | Update org ruleset |
| `delete_org_ruleset` | `org`, `ruleset_id` | Delete org ruleset |

### UTILITY Functions - Templates

| Function | Args | Description |
|----------|------|-------------|
| `get_protection_template` | `template_name` | Get protection preset |
| `get_ruleset_template` | `template_name` | Get ruleset preset |
| `list_protection_templates` | - | List available templates |
| `list_ruleset_templates` | - | List available templates |

### UTILITY Functions - Smart Apply

| Function | Args | Description |
|----------|------|-------------|
| `apply_main_branch_protection` | `owner`, `repo` | Auto-detect and apply |
| `apply_develop_branch_protection` | `owner`, `repo` | Auto-detect and apply |
| `apply_branch_naming_ruleset` | `owner`, `repo` | Apply naming rules |
| `apply_release_branch_ruleset` | `owner`, `repo` | Apply release rules |
| `apply_tag_protection_ruleset` | `owner`, `repo` | Apply tag protection |
| `get_protection_summary` | `owner`, `repo` | Summary of all protections |

---

## Function Details

### FETCH Primitives

#### `fetch_branch_protection`

Get branch protection rules for a specific branch via REST API.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `branch` - Branch name

**Output:** JSON protection configuration

**Example:**
```bash
fetch_branch_protection "hiivmind" "api" "main"
```

---

#### `fetch_repo_rulesets`

List all rulesets for a repository via REST API.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `include_parents` - Include org rulesets (default: true)

**Output:** JSON array of rulesets

**Example:**
```bash
fetch_repo_rulesets "hiivmind" "api"
fetch_repo_rulesets "hiivmind" "api" "false"  # Repo only, no org rulesets
```

---

#### `fetch_ruleset_by_name`

Get a specific ruleset by name.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `name` - Ruleset name

**Output:** JSON ruleset details (first match)

**Example:**
```bash
fetch_ruleset_by_name "hiivmind" "api" "Branch Naming Convention"
```

---

### DISCOVER Primitives

#### `discover_repo_branch_protections`

Get all branch protection rules for a repository via GraphQL.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name

**Output:** JSON with branch protection rules

**Example:**
```bash
discover_repo_branch_protections "hiivmind" "api"
```

---

#### `discover_rules_for_branch`

Get all rules (from any source) that apply to a specific branch.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `branch` - Branch name

**Output:** JSON array of active rules

**Example:**
```bash
discover_rules_for_branch "hiivmind" "api" "main"
```

---

### DETECT Primitives

#### `detect_protection_source`

Determine where protection comes from for a specific branch.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `branch` - Branch name

**Output:** One of: `branch_rule`, `repo_ruleset`, `org_ruleset`, `none`

**Example:**
```bash
source=$(detect_protection_source "hiivmind" "api" "main")
echo "Protection source: $source"
```

---

### MUTATE Primitives

#### `set_branch_protection_rest`

Set branch protection rules via REST API. Creates or replaces existing rules.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `branch` - Branch name
- stdin - JSON configuration

**Output:** Result JSON

**Example:**
```bash
cat << 'EOF' | set_branch_protection_rest "hiivmind" "api" "main"
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci/build"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "restrictions": null
}
EOF
```

---

#### `upsert_repo_ruleset`

Create or update a repository ruleset by name.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `name` - Ruleset name
- stdin - JSON configuration

**Output:** Result JSON

**Example:**
```bash
get_ruleset_template "branch_naming" | upsert_repo_ruleset "hiivmind" "api" "Branch Naming Convention"
```

---

### UTILITY Functions

#### `apply_main_branch_protection`

Auto-detect repository type and apply appropriate main branch protection.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name

**Output:** Result JSON

**Behavior:**
- For organization repos: applies `main_org` template (strict)
- For personal repos: applies `main_personal` template (relaxed)

**Example:**
```bash
apply_main_branch_protection "hiivmind" "api"
```

---

#### `get_protection_summary`

Get a summary of all protections for a repository.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name

**Output:** JSON summary

**Example:**
```bash
get_protection_summary "hiivmind" "api"
# Returns:
# {
#   "repository": "hiivmind/api",
#   "branch_protection_rules": 2,
#   "rulesets": 3,
#   "total_protections": 5
# }
```

---

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

---

## jq Filters Reference

| Filter | Description |
|--------|-------------|
| `.filters.format_branch_protection` | Format REST protection response |
| `.filters.format_branch_protection_graphql` | Format GraphQL protection |
| `.filters.format_rulesets_list` | Format ruleset list |
| `.filters.format_ruleset_detail` | Format single ruleset |
| `.filters.format_rules_for_branch` | Format rules for branch |
| `.filters.format_rulesets_graphql` | Format GraphQL rulesets |
| `.filters.format_branch_protections_graphql` | Format GraphQL protections |
| `.filters.extract_rule_types` | Extract unique rule types |
| `.filters.extract_bypass_actors` | Extract bypass actors |
| `.filters.protection_summary` | Summarize protections |
| `.filters.ruleset_summary` | Summarize rulesets |

---

## GraphQL Queries Reference

| Query | Description |
|-------|-------------|
| `.queries.repo_branch_protection_rules` | List all branch protections |
| `.queries.branch_protection_by_pattern` | Get protection by pattern |
| `.queries.branch_protection_by_id` | Get protection by node ID |
| `.queries.repo_rulesets` | List repo rulesets |
| `.queries.org_rulesets` | List org rulesets |
| `.queries.ruleset_by_id` | Get ruleset by node ID |

| Mutation | Description |
|----------|-------------|
| `.mutations.create_branch_protection_rule` | Create protection rule |
| `.mutations.update_branch_protection_rule` | Update protection rule |
| `.mutations.delete_branch_protection_rule` | Delete protection rule |
| `.mutations.create_repository_ruleset` | Create ruleset |
| `.mutations.update_repository_ruleset` | Update ruleset |
| `.mutations.delete_repository_ruleset` | Delete ruleset |

---

## Composition Examples

### Check and apply protection

```bash
source lib/github/gh-protection-functions.sh

# Check if main branch is protected
if ! detect_branch_protection_exists "hiivmind" "api" "main"; then
    echo "No protection found, applying..."
    apply_main_branch_protection "hiivmind" "api"
fi
```

### List all protections

```bash
source lib/github/gh-protection-functions.sh

# Get summary
get_protection_summary "hiivmind" "api"

# List branch protection rules
discover_repo_branch_protections "hiivmind" "api" | \
    jq '.data.repository.branchProtectionRules.nodes[] | {pattern, requiresApprovingReviews}'

# List rulesets
fetch_repo_rulesets "hiivmind" "api" | format_rulesets
```

### Apply standard protection suite

```bash
source lib/github/gh-protection-functions.sh

# Protect main and develop branches
apply_main_branch_protection "hiivmind" "api"
apply_develop_branch_protection "hiivmind" "api"

# Add rulesets for patterns
apply_branch_naming_ruleset "hiivmind" "api"
apply_release_branch_ruleset "hiivmind" "api"
apply_tag_protection_ruleset "hiivmind" "api"
```

### Custom ruleset

```bash
source lib/github/gh-protection-functions.sh

# Create custom ruleset
cat << 'EOF' | create_repo_ruleset "hiivmind" "api"
{
  "name": "Feature Branch Rules",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/feature/*"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true
      }
    }
  ]
}
EOF
```

---

## Related Domains

- **Repository** - `gh-repo-functions.sh` - Repository metadata, branches
- **Identity** - `gh-identity-functions.sh` - Users, teams for bypass actors

## Related Files

- `gh-branch-protection-templates.yaml` - Protection and ruleset presets
- `gh-protection-graphql-queries.yaml` - GraphQL queries and mutations
- `gh-protection-jq-filters.yaml` - jq filter templates
