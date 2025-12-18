# Implementation Plan: Secret Domain

> **Document ID:** IMPL-005
> **Created:** 2025-12-11
> **Status:** Planning
> **GitHub Issue:** #18

## Overview

Implement the Secret domain for managing encrypted secrets across GitHub Actions, Dependabot, and Codespaces at repository, environment, organization, and user scopes.

## Design Decision

**Secret domain will be Layer 2 primitives only** - No Layer 3 (Smart Application) functions needed.

**Rationale:**
- Simple CRUD operations (list, set, delete)
- gh CLI handles encryption automatically
- No complex configurations or context detection required
- Uniform API across all secret types (Actions, Dependabot, Codespaces)

## API Strategy

| Operation Category | Primary API | Reason |
|-------------------|-------------|---------|
| List secrets | gh CLI (`gh secret list --json`) | Native formatting, handles all scopes |
| Set secrets | gh CLI (`gh secret set`) | Automatic encryption with libsodium |
| Delete secrets | gh CLI (`gh secret delete`) | Simple, works for all scopes |
| Public keys | REST API | Not in gh CLI, needed for manual encryption |
| Repository visibility | REST API | Organization secret repo access management |

### Why We Use gh CLI Primarily

**gh CLI advantages:**
- Automatic encryption using repository/org public key
- No manual libsodium sealed box encryption required
- Unified interface for Actions, Dependabot, Codespaces
- Handles environment, org, repo, user scopes consistently

**REST API for:**
- Fetching public keys (not in gh secret)
- Managing organization secret repository visibility
- Programmatic secret management without interactive input

## Secret Scopes

| Scope | Available For | Access Level |
|-------|---------------|--------------|
| **Repository** | Actions, Dependabot | Single repository |
| **Environment** | Actions only | Specific deployment environment |
| **Organization** | Actions, Dependabot, Codespaces | Org-wide with repo visibility control |
| **User** | Codespaces only | User's personal codespaces |

## Primitive Specification

### FETCH Primitives (4)

| Function | API | Purpose |
|----------|-----|---------|
| `fetch_repo_public_key` | REST | Get public key for repo secret encryption |
| `fetch_org_public_key` | REST | Get public key for org secret encryption |
| `fetch_env_public_key` | REST | Get public key for environment secret encryption |
| `fetch_user_public_key` | REST | Get public key for user secret encryption |

**Signature pattern:**
```bash
fetch_repo_public_key "owner" "repo" "actions"  # or "dependabot", "codespaces"
fetch_org_public_key "org" "actions"            # or "dependabot"
fetch_env_public_key "owner" "repo" "production"
fetch_user_public_key "codespaces"
```

**Note:** Public keys are needed if manually encrypting secrets via REST API instead of using gh CLI.

### DISCOVER Primitives (8)

| Function | API | Purpose |
|----------|-----|---------|
| `discover_repo_secrets` | gh CLI | List repository secrets (Actions/Dependabot) |
| `discover_env_secrets` | gh CLI | List environment secrets |
| `discover_org_secrets` | gh CLI | List organization secrets |
| `discover_user_secrets` | gh CLI | List user secrets (Codespaces) |
| `discover_repo_actions_secrets` | gh CLI | List repo Actions secrets specifically |
| `discover_repo_dependabot_secrets` | gh CLI | List repo Dependabot secrets specifically |
| `discover_org_secret_repos` | REST | List repos that can access org secret |
| `discover_org_secrets_available` | REST | List org secrets available to repo |

**Signature pattern:**
```bash
discover_repo_secrets "owner" "repo" "actions"      # or "dependabot"
discover_env_secrets "owner" "repo" "production"
discover_org_secrets "org" "actions"                # or "dependabot", "codespaces"
discover_user_secrets "codespaces"
discover_org_secret_repos "org" "secret_name" "actions"
```

### LOOKUP Primitives (1)

| Function | API | Purpose |
|----------|-----|---------|
| `get_secret_visibility` | REST | Get org secret visibility (all/private/selected) |

**Signature pattern:**
```bash
get_secret_visibility "org" "MY_SECRET" "actions"  # → "all", "private", or "selected"
```

### FILTER Primitives (3)

| Function | Purpose |
|----------|---------|
| `filter_secrets_by_app` | Keep secrets for specific app (actions, dependabot, codespaces) |
| `filter_secrets_by_visibility` | Keep secrets matching visibility (all, private, selected) |
| `filter_secrets_by_name` | Keep secrets matching name pattern |

**Input/Output:** JSON from stdin → filtered JSON to stdout

### FORMAT Primitives (3)

| Function | Purpose |
|----------|---------|
| `format_secrets` | Tabular secret list (name, updated, visibility) |
| `format_secret_detail` | Single secret with visibility and repo count |
| `format_public_key` | Format public key with key_id |

### DETECT Primitives (3)

| Function | Returns | Purpose |
|----------|---------|---------|
| `detect_secret_exists` | "true" \| "false" | Check if secret exists at scope |
| `detect_secret_scope` | "repo" \| "env" \| "org" \| "user" | Determine secret scope |
| `detect_secret_app` | "actions" \| "dependabot" \| "codespaces" | Determine app type |

### MUTATE Primitives (9)

| Function | API | Purpose |
|----------|-----|---------|
| `set_repo_secret` | gh CLI | Set repository secret (Actions/Dependabot) |
| `set_env_secret` | gh CLI | Set environment secret |
| `set_org_secret` | gh CLI | Set organization secret |
| `set_user_secret` | gh CLI | Set user secret (Codespaces) |
| `delete_repo_secret` | gh CLI | Delete repository secret |
| `delete_env_secret` | gh CLI | Delete environment secret |
| `delete_org_secret` | gh CLI | Delete organization secret |
| `delete_user_secret` | gh CLI | Delete user secret |
| `set_org_secret_repos` | REST | Set which repos can access org secret |

**Signature pattern:**
```bash
set_repo_secret "owner" "repo" "MY_SECRET" "value" "actions"
set_env_secret "owner" "repo" "production" "DB_PASSWORD" "value"
set_org_secret "org" "ORG_TOKEN" "value" "actions" "selected" "[repo_ids]"
delete_repo_secret "owner" "repo" "MY_SECRET" "actions"
set_org_secret_repos "org" "MY_SECRET" "actions" "[1,2,3]"  # Repo IDs
```

## Total: 31 Primitives

- FETCH: 4 (public keys for each scope)
- DISCOVER: 8 (list secrets at each scope + repo access)
- LOOKUP: 1 (get visibility)
- FILTER: 3 (by app, visibility, name)
- FORMAT: 3 (secrets, detail, public key)
- DETECT: 3 (exists, scope, app)
- MUTATE: 9 (set/delete at each scope + repo access)

## REST API Endpoints Reference

### Actions Secrets

**Repository:**
- `GET /repos/{owner}/{repo}/actions/secrets` - List
- `GET /repos/{owner}/{repo}/actions/secrets/public-key` - Public key
- `GET /repos/{owner}/{repo}/actions/secrets/{name}` - Get
- `PUT /repos/{owner}/{repo}/actions/secrets/{name}` - Create/update
- `DELETE /repos/{owner}/{repo}/actions/secrets/{name}` - Delete

**Environment:**
- `GET /repos/{owner}/{repo}/environments/{env}/secrets` - List
- `GET /repos/{owner}/{repo}/environments/{env}/secrets/public-key` - Public key
- `PUT /repos/{owner}/{repo}/environments/{env}/secrets/{name}` - Create/update
- `DELETE /repos/{owner}/{repo}/environments/{env}/secrets/{name}` - Delete

**Organization:**
- `GET /orgs/{org}/actions/secrets` - List
- `GET /orgs/{org}/actions/secrets/public-key` - Public key
- `PUT /orgs/{org}/actions/secrets/{name}` - Create/update
- `DELETE /orgs/{org}/actions/secrets/{name}` - Delete
- `GET /orgs/{org}/actions/secrets/{name}/repositories` - List repo access
- `PUT /orgs/{org}/actions/secrets/{name}/repositories` - Set repo access

### Dependabot Secrets

(Same structure as Actions, but `/dependabot/` instead of `/actions/`)

### Codespaces Secrets

**User:**
- `GET /user/codespaces/secrets` - List
- `GET /user/codespaces/secrets/public-key` - Public key
- `PUT /user/codespaces/secrets/{name}` - Create/update
- `DELETE /user/codespaces/secrets/{name}` - Delete

**Repository:**
- `GET /repos/{owner}/{repo}/codespaces/secrets` - List
- `GET /repos/{owner}/{repo}/codespaces/secrets/public-key` - Public key

## gh CLI Commands

```bash
# Repository secrets
gh secret list -R owner/repo --json name,updatedAt
gh secret list -R owner/repo --app actions
gh secret list -R owner/repo --app dependabot
gh secret set MY_SECRET -R owner/repo --app actions
gh secret set MY_SECRET -R owner/repo --app dependabot
gh secret delete MY_SECRET -R owner/repo --app actions

# Environment secrets
gh secret list -R owner/repo --env production
gh secret set DB_PASSWORD --env production -R owner/repo
gh secret delete DB_PASSWORD --env production -R owner/repo

# Organization secrets
gh secret list --org my-org --app actions
gh secret list --org my-org --app dependabot
gh secret set ORG_TOKEN --org my-org --app actions --visibility selected
gh secret delete ORG_TOKEN --org my-org --app actions

# User secrets (Codespaces)
gh secret list --user
gh secret set MY_TOKEN --user
gh secret delete MY_TOKEN --user
```

## Data Structures

### Secret Object (List)
```json
{
  "name": "MY_SECRET",
  "created_at": "2019-08-10T14:59:22Z",
  "updated_at": "2020-01-10T14:59:22Z",
  "visibility": "selected",  // Org secrets only
  "selected_repositories_url": "https://api.github.com/orgs/octo-org/actions/secrets/MY_SECRET/repositories"
}
```

### Secret Object (Detail)
```json
{
  "name": "MY_SECRET",
  "created_at": "2019-08-10T14:59:22Z",
  "updated_at": "2020-01-10T14:59:22Z",
  "visibility": "selected",
  "selected_repositories_url": "..."
}
```

**Note:** Encrypted values are NEVER returned by the API.

### Public Key Object
```json
{
  "key_id": "012345678912345678",
  "key": "2Sg8iYjAxxmI2LvUXpJjkYrMxURPc8r+dB7TJyvvcCU="
}
```

### Visibility Options (Organization Secrets)
- `all` - Available to all repositories in organization
- `private` - Available only to private repositories
- `selected` - Available to selected repositories (requires `selected_repository_ids`)

## Files to Create

1. **`lib/github/gh-secret-functions.sh`** (~500 lines)
   - 31 primitive functions
   - Follow ARCH-001 Layer 2 patterns
   - Use gh CLI where possible, REST for public keys and repo access

2. **`lib/github/gh-secret-jq-filters.yaml`** (~150 lines)
   - Format filters: `format_secrets_list`, `format_secret_detail`, `format_public_key`
   - Extract filters: `extract_secret_names`, `extract_selected_repos`
   - Filter operations: `filter_by_app`, `filter_by_visibility`

3. **`lib/github/gh-secret-index.md`** (~350 lines)
   - Quick reference table
   - Function details with examples
   - jq filters reference
   - Composition examples
   - Encryption guidance

## Why No Layer 3 Functions?

Secret domain **does not need** Smart Application functions because:

1. **No context detection** - Secret scope is explicit (repo/env/org/user)
2. **No schema variations** - Same API structure across all scopes
3. **No complex configurations** - Only name + value (+ optional visibility)
4. **gh CLI is already smart** - Handles encryption automatically
5. **No multi-step compositions** - Set/delete are single operations

**Comparison with Protection domain (which HAS Layer 3):**
- Protection: 40+ fields, org vs personal schemas, complex templates
- Secret: 2-3 parameters max (name, value, optional visibility)

## Security Considerations

### Encryption Process

**When using gh CLI (recommended):**
```bash
# CLI handles encryption automatically
gh secret set MY_SECRET -R owner/repo
# Prompts for value or reads from stdin
```

**When using REST API (advanced):**
1. Get public key: `fetch_repo_public_key "owner" "repo" "actions"`
2. Encrypt value using libsodium sealed box with public key
3. Send encrypted value + key_id via REST API

**Important:** This library focuses on gh CLI approach. Manual encryption is out of scope.

### Best Practices

1. **Never log secret values** - All functions handle secrets securely
2. **Use appropriate scopes** - Don't use org secrets when repo secrets suffice
3. **Leverage visibility** - Use `selected` for org secrets when possible
4. **Rotate regularly** - Update secrets periodically
5. **Delete unused secrets** - Clean up after decommissioning workflows

## Implementation Tasks

- [x] Research GitHub Secrets REST API
- [x] Research gh CLI secret capabilities
- [x] Design primitive specification
- [ ] Create `gh-secret-functions.sh` with 31 primitives
- [ ] Create `gh-secret-jq-filters.yaml`
- [ ] Create `gh-secret-index.md`
- [ ] Update `CLAUDE.md` with Secret domain section
- [ ] Test key workflows

## Acceptance Criteria

1. All 31 primitives implemented and tested
2. Functions follow ARCH-001 Layer 2 patterns:
   - Explicit parameters (owner, repo, name, app, scope)
   - Stdin→stdout for data flow (filters, formatters)
   - No context detection
3. Error handling: stderr for errors, proper exit codes
4. Composition works: `discover_repo_secrets | filter_secrets_by_app "actions" | format_secrets`
5. Documentation complete in gh-secret-index.md
6. Security: No secret values logged or exposed
7. Integration with existing domains (repos)

## Related Documents

- **ARCH-001:** `knowledge/architecture-principles.md` - Layer 2 primitive patterns
- **ARCH-002:** `knowledge/domain-segmentation.md` - Domain boundaries
- **Issue #18:** P2 Secret Domain Implementation
- **Related:** Action domain (secrets used by workflows)
