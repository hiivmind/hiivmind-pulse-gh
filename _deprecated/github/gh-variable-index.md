# GitHub Variables Domain - Function Index

> **Domain:** Variable Management
> **Layer:** 2 (Primitives)
> **Functions:** 32 primitives across 7 types
> **Dependencies:** gh CLI, jq

## Overview

The Variable domain provides primitives for managing **unencrypted** configuration variables across GitHub Actions and Dependabot at repository, environment, and organization scopes.

**Key Characteristics:**
- **Unencrypted** - Variables are readable (unlike secrets)
- **Multi-scope** - Repository, environment, and organization levels
- **Visibility control** - Organization variables support all/private/selected
- **gh CLI primary** - Native CLI handles all common operations

**When to use Variables vs Secrets:**
- **Variables**: Non-sensitive config (API URLs, feature flags, hostnames)
- **Secrets**: Sensitive data (passwords, tokens, API keys)

---

## Quick Reference

| Type | Count | Functions |
|------|-------|-----------|
| **FETCH** | 3 | Get single variable with value |
| **DISCOVER** | 6 | List variables at various scopes |
| **LOOKUP** | 2 | Get value or visibility |
| **FILTER** | 3 | Filter by visibility, name, value |
| **FORMAT** | 3 | Tabular lists, detail view, repo access |
| **DETECT** | 3 | Check if variable exists |
| **MUTATE** | 12 | Set, update, delete variables + repo access |

---

## FETCH Primitives (3)

Retrieve single variable with value.

### `fetch_repo_variable`

Get repository variable.

```bash
fetch_repo_variable "owner" "repo" "VAR_NAME"
```

**Returns:**
```json
{
  "name": "API_URL",
  "value": "https://api.example.com",
  "created_at": "2023-01-15T10:00:00Z",
  "updated_at": "2023-06-20T14:30:00Z"
}
```

### `fetch_org_variable`

Get organization variable.

```bash
fetch_org_variable "org" "VAR_NAME"
```

**Returns:**
```json
{
  "name": "ORG_REGION",
  "value": "us-east-1",
  "created_at": "2023-01-15T10:00:00Z",
  "updated_at": "2023-06-20T14:30:00Z",
  "visibility": "selected",
  "selected_repositories_url": "https://api.github.com/orgs/acme/actions/variables/ORG_REGION/repositories"
}
```

### `fetch_env_variable`

Get environment variable.

```bash
fetch_env_variable "owner" "repo" "production" "DB_HOST"
```

**Returns:**
```json
{
  "name": "DB_HOST",
  "value": "db.prod.example.com",
  "created_at": "2023-01-15T10:00:00Z",
  "updated_at": "2023-06-20T14:30:00Z"
}
```

---

## DISCOVER Primitives (6)

List variables at various scopes.

### `discover_repo_variables`

List repository variables.

```bash
discover_repo_variables "owner" "repo"
```

**Example:**
```bash
discover_repo_variables "octocat" "hello-world" | jq '.[] | {name, value}'
```

### `discover_env_variables`

List environment variables.

```bash
discover_env_variables "owner" "repo" "production"
```

**Example:**
```bash
discover_env_variables "octocat" "hello-world" "production" | format_variables
```

### `discover_org_variables`

List organization variables.

```bash
discover_org_variables "org"
```

**Example:**
```bash
discover_org_variables "acme-corp" | filter_variables_by_visibility "selected"
```

### `discover_org_variable_repos`

List repositories that can access an organization variable.

```bash
discover_org_variable_repos "org" "VAR_NAME"
```

**Example:**
```bash
discover_org_variable_repos "acme-corp" "ORG_TOKEN" | format_variable_repos
```

### `discover_org_variables_available`

List organization variables available to a repository.

```bash
discover_org_variables_available "owner" "repo"
```

**Example:**
```bash
discover_org_variables_available "octocat" "hello-world" | jq 'map(.name)'
```

### `discover_repo_variables_rest`

List repository variables via REST (for pagination).

```bash
discover_repo_variables_rest "owner" "repo" [per_page] [page]
```

**Example:**
```bash
# Get first 50 variables
discover_repo_variables_rest "octocat" "hello-world" 50 1
```

---

## LOOKUP Primitives (2)

Resolve variable properties.

### `get_variable_value`

Get variable value by name.

```bash
get_variable_value "owner" "repo" "VAR_NAME" [scope] [env_or_org]
```

**Scopes:**
- `repo` (default) - Repository variable
- `env` - Environment variable (requires env_or_org = environment name)
- `org` - Organization variable (requires env_or_org = org name)

**Examples:**
```bash
# Repository variable
get_variable_value "octocat" "hello-world" "API_URL"

# Environment variable
get_variable_value "octocat" "hello-world" "DB_HOST" "env" "production"

# Organization variable
get_variable_value "octocat" "hello-world" "ORG_REGION" "org" "acme-corp"
```

### `get_variable_visibility`

Get organization variable visibility.

```bash
get_variable_visibility "org" "VAR_NAME"
```

**Returns:** `all`, `private`, or `selected`

**Example:**
```bash
VISIBILITY=$(get_variable_visibility "acme-corp" "ORG_TOKEN")
echo "Visibility: $VISIBILITY"
```

---

## FILTER Primitives (3)

Transform/filter JSON data (stdin → stdout).

### `filter_variables_by_visibility`

Filter organization variables by visibility.

```bash
filter_variables_by_visibility "all" | "private" | "selected"
```

**Example:**
```bash
discover_org_variables "acme-corp" | filter_variables_by_visibility "selected"
```

### `filter_variables_by_name`

Filter variables by name pattern (regex).

```bash
filter_variables_by_name "pattern"
```

**Example:**
```bash
# Find all API-related variables
discover_repo_variables "octocat" "hello-world" | filter_variables_by_name "^API_"
```

### `filter_variables_by_value`

Filter variables by value pattern (regex).

```bash
filter_variables_by_value "pattern"
```

**Example:**
```bash
# Find variables with production URLs
discover_repo_variables "octocat" "hello-world" | filter_variables_by_value "prod\.example\.com"
```

---

## FORMAT Primitives (3)

Transform JSON to human-readable output (stdin → stdout).

### `format_variables`

Format variables as table.

```bash
format_variables
```

**Example:**
```bash
discover_repo_variables "octocat" "hello-world" | format_variables
```

**Output:**
```
NAME            VALUE                   UPDATED                 VISIBILITY
API_URL         https://api.example.com 2023-06-20T14:30:00Z   -
DB_HOST         db.example.com          2023-06-15T10:00:00Z   -
FEATURE_FLAG    true                    2023-06-18T12:00:00Z   -
```

### `format_variable_detail`

Format single variable with details.

```bash
format_variable_detail
```

**Example:**
```bash
fetch_org_variable "acme-corp" "ORG_TOKEN" | format_variable_detail
```

**Output:**
```
Variable Name: ORG_TOKEN
Value: ghp_***
Created: 2023-01-15T10:00:00Z
Updated: 2023-06-20T14:30:00Z
Visibility: selected
Selected Repos: 5
Selected Repos URL: https://api.github.com/orgs/acme-corp/actions/variables/ORG_TOKEN/repositories
```

### `format_variable_repos`

Format repository access list.

```bash
format_variable_repos
```

**Example:**
```bash
discover_org_variable_repos "acme-corp" "ORG_TOKEN" | format_variable_repos
```

**Output:**
```
REPO_ID     NAME            FULL_NAME
123456      backend         acme-corp/backend
234567      frontend        acme-corp/frontend
```

---

## DETECT Primitives (3)

Determine variable properties.

### `detect_repo_variable_exists`

Check if variable exists at repository scope.

```bash
detect_repo_variable_exists "owner" "repo" "VAR_NAME"
```

**Returns:** `true` or `false`

**Example:**
```bash
if [[ "$(detect_repo_variable_exists "octocat" "hello-world" "API_URL")" == "true" ]]; then
    echo "Variable exists"
fi
```

### `detect_env_variable_exists`

Check if variable exists at environment scope.

```bash
detect_env_variable_exists "owner" "repo" "environment" "VAR_NAME"
```

**Example:**
```bash
detect_env_variable_exists "octocat" "hello-world" "production" "DB_HOST"
```

### `detect_org_variable_exists`

Check if variable exists at organization scope.

```bash
detect_org_variable_exists "org" "VAR_NAME"
```

**Example:**
```bash
detect_org_variable_exists "acme-corp" "ORG_REGION"
```

---

## MUTATE Primitives (12)

Create, update, or delete variables.

### `set_repo_variable`

Set repository variable.

```bash
set_repo_variable "owner" "repo" "VAR_NAME" "value"
```

**Example:**
```bash
set_repo_variable "octocat" "hello-world" "API_URL" "https://api.example.com"
```

### `set_env_variable`

Set environment variable.

```bash
set_env_variable "owner" "repo" "environment" "VAR_NAME" "value"
```

**Example:**
```bash
set_env_variable "octocat" "hello-world" "production" "DB_HOST" "db.prod.example.com"
```

### `set_org_variable`

Set organization variable.

```bash
set_org_variable "org" "VAR_NAME" "value" [visibility] [repo_ids]
```

**Visibility:** `all` (default), `private`, or `selected`

**Examples:**
```bash
# All repositories
set_org_variable "acme-corp" "ORG_REGION" "us-east-1" "all"

# Selected repositories
set_org_variable "acme-corp" "SECRET_VAR" "value" "selected" "123456,234567"
```

### `delete_repo_variable`

Delete repository variable.

```bash
delete_repo_variable "owner" "repo" "VAR_NAME"
```

**Example:**
```bash
delete_repo_variable "octocat" "hello-world" "OLD_VAR"
```

### `delete_env_variable`

Delete environment variable.

```bash
delete_env_variable "owner" "repo" "environment" "VAR_NAME"
```

**Example:**
```bash
delete_env_variable "octocat" "hello-world" "staging" "TEMP_VAR"
```

### `delete_org_variable`

Delete organization variable.

```bash
delete_org_variable "org" "VAR_NAME"
```

**Example:**
```bash
delete_org_variable "acme-corp" "DEPRECATED_VAR"
```

### `update_repo_variable`

Update repository variable via REST.

```bash
update_repo_variable "owner" "repo" "VAR_NAME" "new_value"
```

**Example:**
```bash
update_repo_variable "octocat" "hello-world" "API_URL" "https://api-v2.example.com"
```

### `update_org_variable`

Update organization variable via REST.

```bash
update_org_variable "org" "VAR_NAME" "new_value" [visibility] [repo_ids_json]
```

**Example:**
```bash
update_org_variable "acme-corp" "ORG_REGION" "eu-west-1" "all"
```

### `update_env_variable`

Update environment variable via REST.

```bash
update_env_variable "owner" "repo" "environment" "VAR_NAME" "new_value"
```

**Example:**
```bash
update_env_variable "octocat" "hello-world" "production" "DB_HOST" "db-new.prod.example.com"
```

### `set_org_variable_repos`

Set which repositories can access organization variable.

```bash
set_org_variable_repos "org" "VAR_NAME" "[repo_id1,repo_id2,...]"
```

**Example:**
```bash
set_org_variable_repos "acme-corp" "ORG_TOKEN" "[123456,234567,345678]"
```

### `add_repo_to_org_variable`

Add repository to organization variable access.

```bash
add_repo_to_org_variable "org" "VAR_NAME" "repo_id"
```

**Example:**
```bash
add_repo_to_org_variable "acme-corp" "ORG_TOKEN" "456789"
```

### `remove_repo_from_org_variable`

Remove repository from organization variable access.

```bash
remove_repo_from_org_variable "org" "VAR_NAME" "repo_id"
```

**Example:**
```bash
remove_repo_from_org_variable "acme-corp" "ORG_TOKEN" "123456"
```

---

## Composition Examples

### List All API-Related Variables

```bash
discover_repo_variables "octocat" "hello-world" | \
    filter_variables_by_name "^API_" | \
    format_variables
```

### Find Variables Needing Update

```bash
# Find variables updated before a certain date
discover_org_variables "acme-corp" | \
    jq --arg date "2023-01-01T00:00:00Z" 'map(select(.updatedAt < $date))' | \
    format_variables
```

### Export Variables to .env File

```bash
# Create .env file from repository variables
discover_repo_variables "octocat" "hello-world" | \
    jq -r 'map("\(.name)=\(.value)") | .[]' > .env
```

### Sync Environment Variables

```bash
# Copy production variables to staging
discover_env_variables "octocat" "hello-world" "production" | \
    jq -r '.[] | "\(.name)=\(.value)"' | \
    while IFS='=' read -r name value; do
        set_env_variable "octocat" "hello-world" "staging" "$name" "$value"
    done
```

### Find Potentially Sensitive Variables

```bash
# Variables that might contain sensitive data
discover_repo_variables "octocat" "hello-world" | \
    jq 'map(select(.name | test("(?i)(token|password|secret|key|auth|credential)")))' | \
    format_variables
```

### Bulk Update Variable Visibility

```bash
# Change all org variables from 'all' to 'private'
discover_org_variables "acme-corp" | \
    filter_variables_by_visibility "all" | \
    jq -r '.[] | .name' | \
    while read -r name; do
        value=$(get_variable_value "octocat" "hello-world" "$name" "org" "acme-corp")
        update_org_variable "acme-corp" "$name" "$value" "private"
    done
```

### Variable Summary Report

```bash
# Generate summary of organization variables
discover_org_variables "acme-corp" | \
    jq '{
        total: length,
        by_visibility: (group_by(.visibility) | map({visibility: .[0].visibility, count: length})),
        recent_updates: (sort_by(.updatedAt) | reverse | .[0:5] | map({name, updated: .updatedAt}))
    }'
```

---

## jq Filters Reference

See `lib/github/gh-variable-jq-filters.yaml` for complete filter definitions.

### Format Filters

| Filter | Description |
|--------|-------------|
| `format_variables_list` | Format variables array as table |
| `format_variable_detail` | Format single variable with all metadata |
| `format_variable_repos` | Format repository access list |
| `format_variables_compact` | Format with truncated values |

### Extract Filters

| Filter | Description |
|--------|-------------|
| `extract_variable_names` | Extract array of variable names |
| `extract_variable_values` | Extract array of values |
| `extract_name_value_pairs` | Extract as {name: value} object |
| `extract_selected_repo_ids` | Extract repository IDs |
| `extract_by_visibility` | Group by visibility |

### Filter Operations

| Filter | Description |
|--------|-------------|
| `filter_by_visibility` | Filter by visibility (requires --arg visibility) |
| `filter_by_name` | Filter by name pattern (requires --arg pattern) |
| `filter_by_value` | Filter by value pattern (requires --arg pattern) |
| `filter_updated_after` | Filter by update date (requires --arg date) |
| `filter_with_selected_repos` | Keep only selected visibility |
| `filter_by_name_prefix` | Filter by name prefix |
| `filter_empty_values` | Keep only empty values |
| `filter_non_empty_values` | Keep only non-empty values |

### Summary Filters

| Filter | Description |
|--------|-------------|
| `count_by_visibility` | Count by visibility |
| `variable_summary` | Complete summary with stats |
| `count_by_prefix` | Count by name prefix |
| `variable_value_stats` | Statistics on value lengths |

### Transformation Filters

| Filter | Description |
|--------|-------------|
| `normalize_variable_from_cli` | Normalize gh CLI to REST format |
| `add_scope_metadata` | Add scope field |
| `to_env_file` | Convert to .env format |
| `to_shell_exports` | Convert to export format |
| `mask_sensitive_values` | Mask values matching pattern |
| `sort_by_name` | Sort alphabetically |
| `sort_by_updated` | Sort by update time |

### Validation Filters

| Filter | Description |
|--------|-------------|
| `detect_sensitive` | Flag potentially sensitive variables |
| `validate_names` | Check naming conventions |
| `find_duplicates` | Find duplicate names across scopes |

---

## Security Best Practices

### When to Use Variables vs Secrets

**Use Variables for:**
- ✅ API endpoints and URLs
- ✅ Feature flags (true/false)
- ✅ Environment names (staging, production)
- ✅ Non-sensitive configuration
- ✅ Public identifiers (client IDs, region names)

**Use Secrets for:**
- 🔒 Passwords and tokens
- 🔒 API keys and credentials
- 🔒 Private keys and certificates
- 🔒 Any value that should never be logged
- 🔒 Sensitive configuration data

### Important Security Notes

1. **Variables are NOT encrypted** at rest
2. **Variables ARE readable** via API and CLI
3. **Variables CAN appear in logs** - be cautious
4. **Never store credentials in variables** - use secrets instead
5. **Review regularly** - audit variables for sensitive data

### Naming Conventions

Follow these conventions for clarity:

```bash
# Good - Clear purpose, UPPER_SNAKE_CASE
API_URL="https://api.example.com"
DB_HOST="db.example.com"
FEATURE_FLAG_NEW_UI="true"
REGION="us-east-1"

# Bad - Ambiguous or suggests sensitive data
api_url="..."           # Use UPPER_SNAKE_CASE
TOKEN="..."            # Tokens should be secrets
password="..."         # Passwords should be secrets
```

### Scope Hierarchy

Variables can exist at multiple scopes. Resolution order:

1. **Repository variables** - Override everything
2. **Environment variables** - Override organization (for that environment)
3. **Organization variables** - Base defaults

```bash
# Organization default
set_org_variable "acme-corp" "API_URL" "https://api.acme.com" "all"

# Repository override
set_repo_variable "acme-corp" "backend" "API_URL" "https://api-internal.acme.com"

# Environment override
set_env_variable "acme-corp" "backend" "production" "API_URL" "https://api-prod.acme.com"
```

### Audit and Cleanup

Regular variable audits prevent clutter and security risks:

```bash
# Find old variables (not updated in 6 months)
SIX_MONTHS_AGO=$(date -u -d '6 months ago' +%Y-%m-%dT%H:%M:%SZ)
discover_org_variables "acme-corp" | \
    jq --arg date "$SIX_MONTHS_AGO" 'map(select(.updatedAt < $date))'

# Find potentially sensitive variables
discover_repo_variables "octocat" "hello-world" | \
    jq 'map(select(.name | test("(?i)(token|password|secret|key|auth)")))'

# Find empty variables
discover_repo_variables "octocat" "hello-world" | \
    jq 'map(select(.value == "" or .value == null))'
```

---

## Integration with Other Domains

### With Action Domain

Variables are used by GitHub Actions workflows:

```bash
# List variables used by workflows
discover_repo_variables "octocat" "hello-world"

# Set variable for workflow
set_repo_variable "octocat" "hello-world" "DEPLOY_ENV" "production"
```

### With Secret Domain

Combine variables (configuration) with secrets (credentials):

```bash
# Public configuration - use variables
set_repo_variable "octocat" "hello-world" "API_URL" "https://api.example.com"

# Sensitive credentials - use secrets
source lib/github/gh-secret-functions.sh
set_repo_secret "octocat" "hello-world" "API_TOKEN" "$TOKEN_VALUE" "actions"
```

### With Repository Domain

Variables are scoped to repositories:

```bash
source lib/github/gh-repo-functions.sh

# Get repository ID for org variable access
REPO_ID=$(fetch_repo "octocat" "hello-world" | jq -r '.id')

# Add repo to org variable
add_repo_to_org_variable "acme-corp" "ORG_VAR" "$REPO_ID"
```

---

## Error Handling

Functions follow ARCH-001 error handling patterns:

```bash
# Check exit code
if ! set_repo_variable "octocat" "hello-world" "API_URL" "https://api.example.com"; then
    echo "Failed to set variable" >&2
    exit 1
fi

# Check if variable exists before updating
if [[ "$(detect_repo_variable_exists "octocat" "hello-world" "API_URL")" == "true" ]]; then
    update_repo_variable "octocat" "hello-world" "API_URL" "https://new-api.example.com"
else
    set_repo_variable "octocat" "hello-world" "API_URL" "https://new-api.example.com"
fi
```

---

## Related Documentation

- **ARCH-001**: `knowledge/architecture-principles.md` - Layer 2 primitive patterns
- **ARCH-002**: `knowledge/domain-segmentation.md` - Domain boundaries
- **IMPL-006**: `knowledge/implementation-plan-variable-domain.md` - Implementation plan
- **Secret Domain**: `lib/github/gh-secret-index.md` - Encrypted secrets
- **Action Domain**: `lib/github/gh-action-index.md` - Workflows that use variables
- **Repository Domain**: `lib/github/gh-repo-index.md` - Repository operations

---

## Summary

The Variable domain provides 32 primitives for managing unencrypted configuration variables:

- **Simple CRUD**: Set, get, update, delete
- **Multi-scope**: Repository, environment, organization
- **Visibility control**: Organization variables support fine-grained access
- **gh CLI primary**: Native CLI handles complexity
- **Composable**: Pipeline pattern with stdin→stdout

**Remember**: Variables are unencrypted and readable. For sensitive data, use the Secret domain.
