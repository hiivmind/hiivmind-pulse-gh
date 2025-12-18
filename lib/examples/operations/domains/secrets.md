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

## Corpus Lookup Guide

| API | Endpoints | Search Keywords |
|-----|-----------|-----------------|
| REST | `GET /repos/{owner}/{repo}/actions/secrets`, `GET /secrets/{secret_name}`, `PUT /secrets/{name}`, `DELETE /secrets/{name}` | `GET /actions/secrets`, `PUT /secrets/{name}`, `encrypted_value`, `key_id`, `public_key` |

## Key Concepts

Secrets require encryption with repository public key. gh CLI handles this automatically. For REST API, must encrypt value with libsodium before sending.

**Scopes:** Repository, Environment (via `/environments/{env_name}/secrets`), Organization (via `/orgs/{org}/secrets`)
