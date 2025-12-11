# Secret Domain Functions Index

> **Domain:** GitHub Secrets (Actions, Dependabot, Codespaces)
> **File:** `lib/github/gh-secret-functions.sh`
> **Layer:** 2 (Primitives only - no Layer 3 needed)
> **Last updated:** 2025-12-11

## Quick Reference

### Secret Scopes

| Scope | Apps | Access Level |
|-------|------|--------------|
| **Repository** | Actions, Dependabot, Codespaces | Single repository |
| **Environment** | Actions only | Specific deployment environment |
| **Organization** | Actions, Dependabot, Codespaces | Org-wide with repo visibility control |
| **User** | Codespaces only | User's personal codespaces |

### FETCH Primitives (4)

| Function | Purpose | Example |
|----------|---------|---------|
| `fetch_repo_public_key` | Get public key for repo secrets | `fetch_repo_public_key "owner" "repo" "actions"` |
| `fetch_org_public_key` | Get public key for org secrets | `fetch_org_public_key "org" "actions"` |
| `fetch_env_public_key` | Get public key for environment | `fetch_env_public_key "owner" "repo" "prod"` |
| `fetch_user_public_key` | Get public key for user secrets | `fetch_user_public_key` |

### DISCOVER Primitives (7)

| Function | Purpose | Example |
|----------|---------|---------|
| `discover_repo_secrets` | List repository secrets | `discover_repo_secrets "owner" "repo" "actions"` |
| `discover_env_secrets` | List environment secrets | `discover_env_secrets "owner" "repo" "production"` |
| `discover_org_secrets` | List organization secrets | `discover_org_secrets "org" "actions"` |
| `discover_user_secrets` | List user secrets | `discover_user_secrets` |
| `discover_org_secret_repos` | List repos with access to org secret | `discover_org_secret_repos "org" "SECRET" "actions"` |
| `discover_org_secrets_available` | List org secrets available to repo | `discover_org_secrets_available "owner" "repo"` |

### LOOKUP Primitives (1)

| Function | Purpose | Example |
|----------|---------|---------|
| `get_secret_visibility` | Get org secret visibility | `get_secret_visibility "org" "SECRET" "actions"` |

### FILTER Primitives (3)

| Function | Purpose | Example |
|----------|---------|---------|
| `filter_secrets_by_app` | Filter by app type | `echo "$SECRETS" \| filter_secrets_by_app "actions"` |
| `filter_secrets_by_visibility` | Filter by visibility | `echo "$SECRETS" \| filter_secrets_by_visibility "selected"` |
| `filter_secrets_by_name` | Filter by name pattern | `echo "$SECRETS" \| filter_secrets_by_name "^DB_"` |

### FORMAT Primitives (3)

| Function | Purpose | Example |
|----------|---------|---------|
| `format_secrets` | Tabular secret list | `discover_repo_secrets "owner" "repo" "actions" \| format_secrets` |
| `format_secret_detail` | Single secret details | `discover_org_secrets "org" "actions" \| jq '.[0]' \| format_secret_detail` |
| `format_public_key` | Format public key | `fetch_repo_public_key "owner" "repo" "actions" \| format_public_key` |

### DETECT Primitives (3)

| Function | Returns | Example |
|----------|---------|---------|
| `detect_secret_exists` | "true" \| "false" | `detect_secret_exists "owner" "repo" "MY_SECRET" "actions"` |
| `detect_env_secret_exists` | "true" \| "false" | `detect_env_secret_exists "owner" "repo" "prod" "SECRET"` |
| `detect_org_secret_exists` | "true" \| "false" | `detect_org_secret_exists "org" "SECRET" "actions"` |

### MUTATE Primitives (12)

| Function | Purpose | Example |
|----------|---------|---------|
| `set_repo_secret` | Set repository secret | `set_repo_secret "owner" "repo" "TOKEN" "value" "actions"` |
| `set_env_secret` | Set environment secret | `set_env_secret "owner" "repo" "prod" "DB_PASS" "value"` |
| `set_org_secret` | Set organization secret | `set_org_secret "org" "TOKEN" "value" "actions" "all"` |
| `set_user_secret` | Set user secret | `set_user_secret "MY_TOKEN" "value"` |
| `delete_repo_secret` | Delete repository secret | `delete_repo_secret "owner" "repo" "TOKEN" "actions"` |
| `delete_env_secret` | Delete environment secret | `delete_env_secret "owner" "repo" "prod" "DB_PASS"` |
| `delete_org_secret` | Delete organization secret | `delete_org_secret "org" "TOKEN" "actions"` |
| `delete_user_secret` | Delete user secret | `delete_user_secret "MY_TOKEN"` |
| `set_org_secret_repos` | Set repo access for org secret | `set_org_secret_repos "org" "SECRET" "actions" "[1,2,3]"` |
| `add_repo_to_org_secret` | Grant repo access | `add_repo_to_org_secret "org" "SECRET" "actions" 123` |
| `remove_repo_from_org_secret` | Revoke repo access | `remove_repo_from_org_secret "org" "SECRET" "actions" 123` |

---

## Function Details

### FETCH Primitives

#### `fetch_repo_public_key`
Get public key for encrypting repository secrets.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `app` - Application: actions, dependabot, or codespaces (default: actions)

**Output:** Public key JSON `{key_id, key}`

**Example:**
```bash
fetch_repo_public_key "octocat" "hello-world" "actions"
fetch_repo_public_key "octocat" "hello-world" "dependabot"
```

**Use case:** Manual secret encryption (advanced). gh CLI handles this automatically.

---

#### `fetch_org_public_key`
Get public key for encrypting organization secrets.

**Args:**
- `org` - Organization name
- `app` - Application: actions or dependabot (default: actions)

**Output:** Public key JSON `{key_id, key}`

**Example:**
```bash
fetch_org_public_key "my-org" "actions"
```

---

#### `fetch_env_public_key`
Get public key for encrypting environment secrets.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `environment` - Environment name (e.g., production, staging)

**Output:** Public key JSON `{key_id, key}`

**Example:**
```bash
fetch_env_public_key "octocat" "hello-world" "production"
```

---

#### `fetch_user_public_key`
Get public key for encrypting user Codespaces secrets.

**Args:** None

**Output:** Public key JSON `{key_id, key}`

**Example:**
```bash
fetch_user_public_key
```

---

### DISCOVER Primitives

#### `discover_repo_secrets`
List all secrets for a repository.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `app` - Application: actions, dependabot, or codespaces (default: actions)

**Output:** JSON array of secrets

**Example:**
```bash
# List Actions secrets
discover_repo_secrets "octocat" "hello-world" "actions"

# List Dependabot secrets
discover_repo_secrets "octocat" "hello-world" "dependabot"
```

**Composition:**
```bash
discover_repo_secrets "octocat" "hello-world" "actions" | format_secrets
```

---

#### `discover_env_secrets`
List secrets for a deployment environment.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `environment` - Environment name

**Output:** JSON array of secrets

**Example:**
```bash
discover_env_secrets "octocat" "hello-world" "production"
```

---

#### `discover_org_secrets`
List organization-level secrets.

**Args:**
- `org` - Organization name
- `app` - Application: actions, dependabot, or codespaces (default: actions)

**Output:** JSON array of secrets with visibility info

**Example:**
```bash
discover_org_secrets "my-org" "actions"
discover_org_secrets "my-org" "dependabot"
```

**Composition:**
```bash
discover_org_secrets "my-org" "actions" | filter_secrets_by_visibility "selected" | format_secrets
```

---

#### `discover_user_secrets`
List user Codespaces secrets.

**Args:** None

**Output:** JSON array of secrets

**Example:**
```bash
discover_user_secrets | format_secrets
```

---

#### `discover_org_secret_repos`
List which repositories can access an organization secret.

**Args:**
- `org` - Organization name
- `secret_name` - Secret name
- `app` - Application: actions or dependabot (default: actions)

**Output:** JSON array of repositories

**Example:**
```bash
discover_org_secret_repos "my-org" "ORG_TOKEN" "actions"
```

---

#### `discover_org_secrets_available`
List organization secrets available to a specific repository.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name

**Output:** JSON array of organization secrets

**Example:**
```bash
discover_org_secrets_available "octocat" "hello-world"
```

---

### MUTATE Primitives

#### `set_repo_secret`
Create or update a repository secret.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `secret_name` - Secret name (uppercase recommended)
- `value` - Secret value
- `app` - Application: actions, dependabot, or codespaces (default: actions)

**Output:** Empty (success)

**Example:**
```bash
set_repo_secret "octocat" "hello-world" "API_TOKEN" "ghp_abc123" "actions"
set_repo_secret "octocat" "hello-world" "NPM_TOKEN" "npm_xyz789" "dependabot"
```

**Security:** Value is encrypted automatically by gh CLI.

---

#### `set_env_secret`
Create or update an environment secret.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `environment` - Environment name
- `secret_name` - Secret name
- `value` - Secret value

**Output:** Empty (success)

**Example:**
```bash
set_env_secret "octocat" "hello-world" "production" "DB_PASSWORD" "secure_pass"
```

---

#### `set_org_secret`
Create or update an organization secret.

**Args:**
- `org` - Organization name
- `secret_name` - Secret name
- `value` - Secret value
- `app` - Application: actions, dependabot, or codespaces (default: actions)
- `visibility` - Visibility: all, private, or selected (default: all)
- `repo_ids` (optional) - Comma-separated repository IDs if visibility=selected

**Output:** Empty (success)

**Example:**
```bash
# Available to all repos
set_org_secret "my-org" "ORG_TOKEN" "value" "actions" "all"

# Available to private repos only
set_org_secret "my-org" "PRIVATE_KEY" "value" "actions" "private"

# Available to selected repos
set_org_secret "my-org" "DEPLOY_KEY" "value" "actions" "selected" "123,456"
```

---

#### `set_user_secret`
Create or update a user Codespaces secret.

**Args:**
- `secret_name` - Secret name
- `value` - Secret value

**Output:** Empty (success)

**Example:**
```bash
set_user_secret "MY_API_KEY" "value"
```

---

#### `delete_repo_secret`
Delete a repository secret.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `secret_name` - Secret name
- `app` - Application: actions, dependabot, or codespaces (default: actions)

**Output:** Empty (success)

**Example:**
```bash
delete_repo_secret "octocat" "hello-world" "OLD_TOKEN" "actions"
```

---

#### `delete_env_secret`
Delete an environment secret.

**Args:**
- `owner` - Repository owner
- `repo` - Repository name
- `environment` - Environment name
- `secret_name` - Secret name

**Output:** Empty (success)

**Example:**
```bash
delete_env_secret "octocat" "hello-world" "production" "OLD_PASSWORD"
```

---

#### `delete_org_secret`
Delete an organization secret.

**Args:**
- `org` - Organization name
- `secret_name` - Secret name
- `app` - Application: actions, dependabot, or codespaces (default: actions)

**Output:** Empty (success)

**Example:**
```bash
delete_org_secret "my-org" "OLD_TOKEN" "actions"
```

---

#### `delete_user_secret`
Delete a user Codespaces secret.

**Args:**
- `secret_name` - Secret name

**Output:** Empty (success)

**Example:**
```bash
delete_user_secret "OLD_KEY"
```

---

#### `set_org_secret_repos`
Set which repositories can access an organization secret (replaces entire list).

**Args:**
- `org` - Organization name
- `secret_name` - Secret name
- `app` - Application: actions or dependabot (default: actions)
- `repo_ids_json` - JSON array of repository IDs (e.g., "[123, 456]")

**Output:** Empty (success)

**Example:**
```bash
set_org_secret_repos "my-org" "DEPLOY_KEY" "actions" "[123, 456, 789]"
```

**Note:** This replaces the entire repository access list.

---

#### `add_repo_to_org_secret`
Grant a single repository access to an organization secret.

**Args:**
- `org` - Organization name
- `secret_name` - Secret name
- `app` - Application: actions or dependabot (default: actions)
- `repo_id` - Repository ID (numeric)

**Output:** Empty (success)

**Example:**
```bash
add_repo_to_org_secret "my-org" "DEPLOY_KEY" "actions" 123
```

---

#### `remove_repo_from_org_secret`
Revoke repository access from an organization secret.

**Args:**
- `org` - Organization name
- `secret_name` - Secret name
- `app` - Application: actions or dependabot (default: actions)
- `repo_id` - Repository ID (numeric)

**Output:** Empty (success)

**Example:**
```bash
remove_repo_from_org_secret "my-org" "DEPLOY_KEY" "actions" 123
```

---

## Composition Examples

### List All Secrets Across Scopes
```bash
#!/bin/bash
OWNER="octocat"
REPO="hello-world"
ORG="my-org"

echo "=== Repository Actions Secrets ==="
discover_repo_secrets "$OWNER" "$REPO" "actions" | format_secrets

echo -e "\n=== Repository Dependabot Secrets ==="
discover_repo_secrets "$OWNER" "$REPO" "dependabot" | format_secrets

echo -e "\n=== Environment Secrets (production) ==="
discover_env_secrets "$OWNER" "$REPO" "production" | format_secrets

echo -e "\n=== Organization Actions Secrets ==="
discover_org_secrets "$ORG" "actions" | format_secrets

echo -e "\n=== User Codespaces Secrets ==="
discover_user_secrets | format_secrets
```

### Rotate Secret Across Environments
```bash
NEW_VALUE="new_secure_value"
SECRET_NAME="DB_PASSWORD"

# Update production
set_env_secret "octocat" "hello-world" "production" "$SECRET_NAME" "$NEW_VALUE"

# Update staging
set_env_secret "octocat" "hello-world" "staging" "$SECRET_NAME" "$NEW_VALUE"

echo "Secret $SECRET_NAME rotated across environments"
```

### Manage Organization Secret Visibility
```bash
ORG="my-org"
SECRET="DEPLOY_KEY"

# Check current visibility
VISIBILITY=$(get_secret_visibility "$ORG" "$SECRET" "actions")
echo "Current visibility: $VISIBILITY"

# If visibility is "selected", list repos
if [[ "$VISIBILITY" == "selected" ]]; then
    echo "Repositories with access:"
    discover_org_secret_repos "$ORG" "$SECRET" "actions" | jq -r '.[].full_name'
fi

# Add a new repository
REPO_ID=456
add_repo_to_org_secret "$ORG" "$SECRET" "actions" "$REPO_ID"
```

### Check Secret Existence Before Setting
```bash
OWNER="octocat"
REPO="hello-world"
SECRET="API_TOKEN"

if [[ $(detect_secret_exists "$OWNER" "$REPO" "$SECRET" "actions") == "true" ]]; then
    echo "Secret exists, updating..."
else
    echo "Secret doesn't exist, creating..."
fi

set_repo_secret "$OWNER" "$REPO" "$SECRET" "new_value" "actions"
```

---

## Security Best Practices

### 1. Never Log Secret Values
```bash
# GOOD - value not visible in logs
set_repo_secret "owner" "repo" "TOKEN" "$SECRET_VALUE" "actions"

# BAD - never echo secrets
echo "Setting secret: $SECRET_VALUE"  # NEVER DO THIS
```

### 2. Use Appropriate Scopes
```bash
# Use repo secrets for repo-specific values
set_repo_secret "owner" "repo" "DEPLOY_TOKEN" "$value" "actions"

# Use org secrets for shared values
set_org_secret "org" "SHARED_TOKEN" "$value" "actions" "selected" "123,456"

# Use environment secrets for environment-specific values
set_env_secret "owner" "repo" "production" "DB_CONN" "$value"
```

### 3. Leverage Visibility Control
```bash
# Don't expose org secrets to all repos
set_org_secret "org" "SENSITIVE" "$value" "actions" "selected" "123"

# Use "private" for private repos only
set_org_secret "org" "INTERNAL" "$value" "actions" "private"
```

### 4. Rotate Secrets Regularly
```bash
# Automated rotation script
SECRET_NAME="API_KEY"
NEW_VALUE=$(generate_new_key)  # Your key generation logic

set_repo_secret "owner" "repo" "$SECRET_NAME" "$NEW_VALUE" "actions"
echo "Rotated $SECRET_NAME"
```

### 5. Clean Up Unused Secrets
```bash
# List all secrets
discover_repo_secrets "owner" "repo" "actions" | jq -r '.[].name' | \
while read secret_name; do
    echo "Found secret: $secret_name"
    # Check if used in workflows, then delete if not
    # delete_repo_secret "owner" "repo" "$secret_name" "actions"
done
```

---

## Common Workflows

### Sync Secrets Across Repositories
```bash
ORG="my-org"
SECRET_NAME="SHARED_TOKEN"
SECRET_VALUE="value"

# Set as org secret with selected visibility
REPO_IDS="123,456,789"
set_org_secret "$ORG" "$SECRET_NAME" "$SECRET_VALUE" "actions" "selected" "$REPO_IDS"

echo "Secret synced to repositories: $REPO_IDS"
```

### Audit Organization Secret Usage
```bash
ORG="my-org"

discover_org_secrets "$ORG" "actions" | jq -r '
    .[] |
    select(.visibility == "selected") |
    "\(.name): \(.numSelectedRepos) repos"
'
```

### Environment-Specific Secret Setup
```bash
OWNER="octocat"
REPO="hello-world"

ENVIRONMENTS=("production" "staging" "development")

for env in "${ENVIRONMENTS[@]}"; do
    echo "Setting up secrets for $env..."
    set_env_secret "$OWNER" "$REPO" "$env" "DB_HOST" "db-$env.example.com"
    set_env_secret "$OWNER" "$REPO" "$env" "API_URL" "https://api-$env.example.com"
done
```

---

## Error Handling

| Error Code | Meaning | Common Causes |
|------------|---------|---------------|
| 404 | Not found | Secret doesn't exist |
| 403 | Forbidden | Insufficient permissions |
| 422 | Unprocessable | Invalid secret name or value |
| 409 | Conflict | Secret already exists (on create) |

### Required Scopes
```bash
gh auth refresh -s repo -s admin:org
```

---

## Related Domains

- **Action domain** - Workflows use secrets
- **Repository domain** - Secrets belong to repositories
- **Variable domain** - Similar to secrets but not encrypted

---

## API Coverage

| Operation | gh CLI | REST API |
|-----------|--------|----------|
| List secrets | ✅ `gh secret list` | ✅ |
| Set secret | ✅ `gh secret set` | ✅ |
| Delete secret | ✅ `gh secret delete` | ✅ |
| Get public key | ❌ | ✅ |
| Manage repo access | ❌ | ✅ |

**Recommendation:** Use gh CLI for all secret management. REST API only needed for public keys (manual encryption) and granular repository access control.
