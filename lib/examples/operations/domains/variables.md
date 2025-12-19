# Variables

**REST API + gh CLI only. No GraphQL support. No encryption needed (unlike Secrets).**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List (repo) | ✓ | ✓ | ✗ | ✓ | Repository variables |
| Get (repo) | ✓ | ✓ | ✗ | ✓ | By name |
| Create (repo) | ✓ | ✓ | ✗ | ✓ | Via POST |
| Update (repo) | ✓ | ✓ | ✗ | ✓ | Via PATCH |
| Delete (repo) | ✓ | ✓ | ✗ | ✓ | |
| List (org) | ✗ | ✓ | ✗ | ✓ | Organization level |
| Create (org) | ✗ | ✓ | ✗ | ✓ | With visibility control |
| Update (org) | ✗ | ✓ | ✗ | ✓ | With visibility control |
| Delete (org) | ✗ | ✓ | ✗ | ✓ | |
| List (env) | ✗ | ✓ | ✗ | ✓ | Environment scope |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh variable list` | Repository only |
| Get | `gh variable get {name}` | Repository only |
| Set | `gh variable set {name} {value}` | Repository only; creates or updates |
| Delete | `gh variable delete {name}` | Repository only |
| Org operations | (Not available) | Use REST API |
| Env operations | (Not available) | Use REST API |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (repo) | GET | `/repos/{owner}/{repo}/actions/variables` | |
| Get (repo) | GET | `/repos/{owner}/{repo}/actions/variables/{name}` | |
| Create (repo) | POST | `/repos/{owner}/{repo}/actions/variables` | |
| Update (repo) | PATCH | `/repos/{owner}/{repo}/actions/variables/{name}` | |
| Delete (repo) | DELETE | `/repos/{owner}/{repo}/actions/variables/{name}` | |
| List (org) | GET | `/orgs/{org}/actions/variables` | |
| Get (org) | GET | `/orgs/{org}/actions/variables/{name}` | |
| Create (org) | POST | `/orgs/{org}/actions/variables` | With visibility control |
| Update (org) | PATCH | `/orgs/{org}/actions/variables/{name}` | |
| Delete (org) | DELETE | `/orgs/{org}/actions/variables/{name}` | |
| List (env) | GET | `/repos/{owner}/{repo}/environments/{env}/variables` | |
| Create (env) | POST | `/repos/{owner}/{repo}/environments/{env}/variables` | |

## Key Differences from Secrets

- **No encryption needed** - Variables are plain text
- **Org-level visibility control** - Can be marked `all`, `private`, or `selected` repositories
- **No GraphQL support** - Variables are REST-only
