# Implementation Plan: Variable Domain

> **Document ID:** IMPL-006
> **Created:** 2025-12-11
> **Status:** Planning
> **GitHub Issue:** #19

## Overview

Implement the Variable domain for managing unencrypted configuration variables across GitHub Actions and Dependabot at repository, environment, and organization scopes.

## Design Decision

**Variable domain will be Layer 2 primitives only** - No Layer 3 (Smart Application) functions needed.

**Rationale:**
- Simple CRUD operations (list, get, set, delete)
- gh CLI provides excellent native support
- No encryption complexity (unlike secrets)
- No complex configurations or context detection required
- Uniform API across all variable scopes

## API Strategy

| Operation Category | Primary API | Reason |
|-------------------|-------------|---------|
| List variables | gh CLI (`gh variable list --json`) | Native formatting, handles all scopes |
| Get variable | gh CLI (`gh variable get`) | Simple, works for all scopes |
| Set variables | gh CLI (`gh variable set`) | No encryption needed, straightforward |
| Delete variables | gh CLI (`gh variable delete`) | Simple, works for all scopes |
| Repository visibility | REST API | Organization variable repo access management |

### Why We Use gh CLI Primarily

**gh CLI advantages:**
- Unified interface for Actions and Dependabot
- Handles environment, org, repo scopes consistently
- Returns values (unlike secrets which are always encrypted)
- Simple syntax for common operations

**REST API for:**
- Managing organization variable repository visibility
- Bulk operations and programmatic access
- Getting variable values via API

## Variable Scopes

| Scope | Available For | Access Level | Encrypted? |
|-------|---------------|--------------|------------|
| **Repository** | Actions, Dependabot | Single repository | No |
| **Environment** | Actions only | Specific deployment environment | No |
| **Organization** | Actions, Dependabot | Org-wide with repo visibility control | No |

**Key Difference from Secrets:**
- Variables are **unencrypted** and **readable**
- Secrets are **encrypted** and **write-only**

## Primitive Specification

### FETCH Primitives (3)

| Function | API | Purpose |
|----------|-----|---------|
| `fetch_repo_variable` | REST | Get repository variable with value |
| `fetch_org_variable` | REST | Get organization variable with value |
| `fetch_env_variable` | REST | Get environment variable with value |

**Signature pattern:**
```bash
fetch_repo_variable "owner" "repo" "VAR_NAME"
fetch_org_variable "org" "VAR_NAME"
fetch_env_variable "owner" "repo" "production" "VAR_NAME"
```

**Output:** JSON with name, value, created_at, updated_at

### DISCOVER Primitives (6)

| Function | API | Purpose |
|----------|-----|---------|
| `discover_repo_variables` | gh CLI | List repository variables |
| `discover_env_variables` | gh CLI | List environment variables |
| `discover_org_variables` | gh CLI | List organization variables |
| `discover_org_variable_repos` | REST | List repos that can access org variable |
| `discover_org_variables_available` | REST | List org variables available to repo |
| `discover_repo_variables_rest` | REST | List repo variables via REST (for pagination) |

**Signature pattern:**
```bash
discover_repo_variables "owner" "repo"
discover_env_variables "owner" "repo" "production"
discover_org_variables "org"
discover_org_variable_repos "org" "VAR_NAME"
```

### LOOKUP Primitives (2)

| Function | API | Purpose |
|----------|-----|---------|
| `get_variable_value` | gh CLI | Get variable value by name |
| `get_variable_visibility` | REST | Get org variable visibility (all/private/selected) |

**Signature pattern:**
```bash
get_variable_value "owner" "repo" "MY_VAR"              # → "value"
get_variable_visibility "org" "MY_VAR"                  # → "all", "private", or "selected"
```

### FILTER Primitives (3)

| Function | Purpose |
|----------|---------|
| `filter_variables_by_visibility` | Keep variables matching visibility (all, private, selected) |
| `filter_variables_by_name` | Keep variables matching name pattern |
| `filter_variables_by_value` | Keep variables matching value pattern |

**Input/Output:** JSON from stdin → filtered JSON to stdout

### FORMAT Primitives (3)

| Function | Purpose |
|----------|---------|
| `format_variables` | Tabular variable list (name, value, updated, visibility) |
| `format_variable_detail` | Single variable with visibility and repo count |
| `format_variable_repos` | List of repositories with access to org variable |

### DETECT Primitives (3)

| Function | Returns | Purpose |
|----------|---------|---------|
| `detect_repo_variable_exists` | "true" \| "false" | Check if variable exists at repo scope |
| `detect_env_variable_exists` | "true" \| "false" | Check if variable exists at env scope |
| `detect_org_variable_exists` | "true" \| "false" | Check if variable exists at org scope |

### MUTATE Primitives (12)

| Function | API | Purpose |
|----------|-----|---------|
| `set_repo_variable` | gh CLI | Set repository variable |
| `set_env_variable` | gh CLI | Set environment variable |
| `set_org_variable` | gh CLI | Set organization variable |
| `delete_repo_variable` | gh CLI | Delete repository variable |
| `delete_env_variable` | gh CLI | Delete environment variable |
| `delete_org_variable` | gh CLI | Delete organization variable |
| `update_repo_variable` | REST | Update repository variable via REST |
| `update_org_variable` | REST | Update organization variable via REST |
| `update_env_variable` | REST | Update environment variable via REST |
| `set_org_variable_repos` | REST | Set which repos can access org variable |
| `add_repo_to_org_variable` | REST | Add repository to org variable access |
| `remove_repo_from_org_variable` | REST | Remove repository from org variable access |

**Signature pattern:**
```bash
set_repo_variable "owner" "repo" "MY_VAR" "value"
set_env_variable "owner" "repo" "production" "DB_HOST" "db.example.com"
set_org_variable "org" "ORG_VAR" "value" "selected" "[repo_ids]"
delete_repo_variable "owner" "repo" "MY_VAR"
set_org_variable_repos "org" "MY_VAR" "[1,2,3]"  # Repo IDs
```

## Total: 32 Primitives

- FETCH: 3 (get variable value at each scope)
- DISCOVER: 6 (list variables at each scope + repo access)
- LOOKUP: 2 (get value, get visibility)
- FILTER: 3 (by visibility, name, value)
- FORMAT: 3 (variables, detail, repos)
- DETECT: 3 (exists at each scope)
- MUTATE: 12 (set/update/delete at each scope + repo access)

## REST API Endpoints Reference

### Actions Variables

**Repository:**
- `GET /repos/{owner}/{repo}/actions/variables` - List
- `GET /repos/{owner}/{repo}/actions/variables/{name}` - Get
- `POST /repos/{owner}/{repo}/actions/variables` - Create
- `PATCH /repos/{owner}/{repo}/actions/variables/{name}` - Update
- `DELETE /repos/{owner}/{repo}/actions/variables/{name}` - Delete

**Environment:**
- `GET /repos/{owner}/{repo}/environments/{env}/variables` - List
- `GET /repos/{owner}/{repo}/environments/{env}/variables/{name}` - Get
- `POST /repos/{owner}/{repo}/environments/{env}/variables` - Create
- `PATCH /repos/{owner}/{repo}/environments/{env}/variables/{name}` - Update
- `DELETE /repos/{owner}/{repo}/environments/{env}/variables/{name}` - Delete

**Organization:**
- `GET /orgs/{org}/actions/variables` - List
- `GET /orgs/{org}/actions/variables/{name}` - Get
- `POST /orgs/{org}/actions/variables` - Create
- `PATCH /orgs/{org}/actions/variables/{name}` - Update
- `DELETE /orgs/{org}/actions/variables/{name}` - Delete
- `GET /orgs/{org}/actions/variables/{name}/repositories` - List repo access
- `PUT /orgs/{org}/actions/variables/{name}/repositories` - Set repo access
- `PUT /orgs/{org}/actions/variables/{name}/repositories/{repo_id}` - Add repo
- `DELETE /orgs/{org}/actions/variables/{name}/repositories/{repo_id}` - Remove repo

## gh CLI Commands

```bash
# Repository variables
gh variable list -R owner/repo --json name,value,updatedAt
gh variable get MY_VAR -R owner/repo
gh variable set MY_VAR -R owner/repo
gh variable set MY_VAR --body "value" -R owner/repo  # Non-interactive
gh variable delete MY_VAR -R owner/repo

# Environment variables
gh variable list -R owner/repo --env production
gh variable get DB_HOST --env production -R owner/repo
gh variable set DB_HOST --env production -R owner/repo
gh variable delete DB_HOST --env production -R owner/repo

# Organization variables
gh variable list --org my-org --json name,value,updatedAt,visibility,numSelectedRepos
gh variable get ORG_VAR --org my-org
gh variable set ORG_VAR --org my-org --visibility selected
gh variable delete ORG_VAR --org my-org
```

## Data Structures

### Variable Object (List)
```json
{
  "name": "MY_VARIABLE",
  "value": "my-value",
  "created_at": "2019-08-10T14:59:22Z",
  "updated_at": "2020-01-10T14:59:22Z",
  "visibility": "selected",  // Org variables only
  "selected_repositories_url": "https://api.github.com/orgs/octo-org/actions/variables/MY_VARIABLE/repositories"
}
```

### Variable Object (Detail)
```json
{
  "name": "MY_VARIABLE",
  "value": "my-value",
  "created_at": "2019-08-10T14:59:22Z",
  "updated_at": "2020-01-10T14:59:22Z",
  "visibility": "selected",
  "selected_repositories_url": "..."
}
```

**Key Difference from Secrets:** Variables include the `value` field (readable).

### Visibility Options (Organization Variables)
- `all` - Available to all repositories in organization
- `private` - Available only to private repositories
- `selected` - Available to selected repositories (requires `selected_repository_ids`)

## Files to Create

1. **`lib/github/gh-variable-functions.sh`** (~600 lines)
   - 32 primitive functions
   - Follow ARCH-001 Layer 2 patterns
   - Use gh CLI where possible, REST for repo access management

2. **`lib/github/gh-variable-jq-filters.yaml`** (~180 lines)
   - Format filters: `format_variables_list`, `format_variable_detail`, `format_variable_repos`
   - Extract filters: `extract_variable_names`, `extract_variable_values`, `extract_selected_repos`
   - Filter operations: `filter_by_visibility`, `filter_by_name`, `filter_by_value`
   - Summary filters: `count_by_visibility`, `variable_summary`

3. **`lib/github/gh-variable-index.md`** (~700 lines)
   - Quick reference table
   - Function details with examples
   - jq filters reference
   - Composition examples
   - Security considerations (even though unencrypted)

## Why No Layer 3 Functions?

Variable domain **does not need** Smart Application functions because:

1. **No context detection** - Variable scope is explicit (repo/env/org)
2. **No schema variations** - Same API structure across all scopes
3. **No complex configurations** - Only name + value (+ optional visibility)
4. **gh CLI is already smart** - Handles all scopes with simple flags
5. **No multi-step compositions** - Set/delete are single operations
6. **No encryption** - Unlike secrets, no public key management

**Comparison with Secret domain (also Layer 2 only):**
- Secret: Encrypted, write-only, public key management
- Variable: Unencrypted, readable, simpler API

## Security Considerations

### When to Use Variables vs Secrets

**Use Variables for:**
- Non-sensitive configuration (API URLs, feature flags)
- Public values that need to be referenced in logs
- Environment-specific settings (hostnames, regions)

**Use Secrets for:**
- Sensitive data (passwords, tokens, API keys)
- Credentials that should never be logged
- Any value that needs encryption at rest

### Best Practices

1. **Never store secrets in variables** - Variables are unencrypted and readable
2. **Use appropriate scopes** - Don't use org variables when repo variables suffice
3. **Leverage visibility** - Use `selected` for org variables when possible
4. **Document variable usage** - Variables are visible, document their purpose
5. **Review regularly** - Clean up unused variables

### Important Notes

- Variables are **NOT encrypted** at rest or in transit (HTTPS only)
- Variable values **ARE readable** via API and CLI (unlike secrets)
- Variables **CAN be logged** in workflow output
- Organization variables can be overridden by repository variables

## Implementation Tasks

- [x] Research GitHub Variables REST API
- [x] Research gh CLI variable capabilities
- [x] Design primitive specification
- [ ] Create `gh-variable-functions.sh` with 32 primitives
- [ ] Create `gh-variable-jq-filters.yaml`
- [ ] Create `gh-variable-index.md`
- [ ] Update `CLAUDE.md` with Variable domain section
- [ ] Test key workflows

## Acceptance Criteria

1. All 32 primitives implemented and tested
2. Functions follow ARCH-001 Layer 2 patterns:
   - Explicit parameters (owner, repo, name, scope)
   - Stdin→stdout for data flow (filters, formatters)
   - No context detection
3. Error handling: stderr for errors, proper exit codes
4. Composition works: `discover_repo_variables | filter_variables_by_name "API_" | format_variables`
5. Documentation complete in gh-variable-index.md
6. Security: Clear guidance on variables vs secrets
7. Integration with existing domains (repos, actions)

## Related Documents

- **ARCH-001:** `knowledge/architecture-principles.md` - Layer 2 primitive patterns
- **ARCH-002:** `knowledge/domain-segmentation.md` - Domain boundaries
- **IMPL-005:** `knowledge/implementation-plan-secret-domain.md` - Similar domain
- **Issue #19:** P2 Variable Domain Implementation
- **Related:** Action domain (variables used by workflows), Secret domain (encrypted alternative)
