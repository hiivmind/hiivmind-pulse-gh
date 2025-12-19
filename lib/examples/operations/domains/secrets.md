# Secrets

**REST API + gh CLI. No GraphQL support. Requires encryption.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✗ | ✓ | Full support |
| Get | ✓ | ✓ | ✗ | ✓ | Full support |
| Set/Create | ✓ | ✓ | ✗ | ✓ | Full support (gh CLI handles encryption) |
| Update | ✓ | ✓ | ✗ | ✓ | Same as set |
| Delete | ✓ | ✓ | ✗ | ✓ | Full support |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh secret list` | Repository secrets only |
| Get | `gh secret view {secret-name}` | Shows value (use carefully) |
| Set | `gh secret set {name} < value.txt` | Handles encryption automatically |
| Delete | `gh secret delete {name}` | |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (repo) | GET | `/repos/{owner}/{repo}/actions/secrets` | |
| Get (repo) | GET | `/repos/{owner}/{repo}/actions/secrets/{secret_name}` | |
| Set (repo) | PUT | `/repos/{owner}/{repo}/actions/secrets/{secret_name}` | Requires encryption |
| Delete (repo) | DELETE | `/repos/{owner}/{repo}/actions/secrets/{secret_name}` | |
| Get public key | GET | `/repos/{owner}/{repo}/actions/secrets/public-key` | For encryption |
| List (org) | GET | `/orgs/{org}/actions/secrets` | |
| Set (org) | PUT | `/orgs/{org}/actions/secrets/{secret_name}` | |
| Delete (org) | DELETE | `/orgs/{org}/actions/secrets/{secret_name}` | |
| List (env) | GET | `/repos/{owner}/{repo}/environments/{env}/secrets` | |
| Set (env) | PUT | `/repos/{owner}/{repo}/environments/{env}/secrets/{secret_name}` | |

## Key Concepts

Secrets require encryption with repository public key. gh CLI handles this automatically. For REST API, must encrypt value with libsodium before sending.

**Scopes:** Repository, Environment (via `/environments/{env_name}/secrets`), Organization (via `/orgs/{org}/secrets`)
