# Pattern: Authentication

## Purpose

Verify GitHub authentication status and required OAuth scopes before performing API operations.

## When to Use

- After tool detection confirms gh CLI is available
- Before any GitHub API operations (init, refresh, operations)
- When authentication errors occur during operations

## Prerequisites

- **tool-detection.md** - gh CLI must be available

## Scope Requirements

| Scope | Required For | Operations |
|-------|--------------|------------|
| `repo` | Repository access | Issues, PRs, branches, protection rules |
| `read:org` | Organization info | Org membership, teams, org-level projects |
| `project` | Projects v2 write | Create/update project items, set field values |
| `read:project` | Projects v2 read | List projects, read field configurations |

**Minimum required scopes:** `repo`, `read:org`, `project`, `read:project`

## Scope Mapping: Classic OAuth ↔ Fine-grained PAT

This plugin documents scopes using classic OAuth names. If using fine-grained personal access tokens, map as follows:

| Classic OAuth Scope | Fine-grained Permission | Access Level |
|--------------------|-----------------------|-------------|
| `repo` | **Issues**, **Pull requests**, **Contents**, **Actions**, **Administration** | Read and write |
| `read:org` | **Organization: Members** | Read-only |
| `project` | **Projects** | Read and write |
| `read:project` | **Projects** | Read-only |

**See also:** `lib/references/token-permissions.md` for per-domain permission requirements.

---

## Algorithm

### Step 1: Check Authentication Status

**Using bash:**
```bash
gh auth status
```

**Expected output (authenticated):**
```
github.com
  ✓ Logged in to github.com account USERNAME (keyring)
  - Active account: true
  - Git operations protocol: ssh
  - Token: gho_************************************
  - Token scopes: 'project', 'read:org', 'repo'
```

**Expected output (not authenticated):**
```
You are not logged into any GitHub hosts. Run gh auth login to authenticate.
```

### Step 2: Extract Current Scopes

**Using bash:**
```bash
gh auth status 2>&1 | grep -i "token scopes" | sed "s/.*Token scopes: '//" | sed "s/'$//"
```

**Alternative (more robust):**
```bash
gh auth status 2>&1 | grep -oP "Token scopes: '\K[^']+"
```

### Step 3: Verify Required Scopes

**Using bash:**
```bash
# Get current scopes as array
SCOPES=$(gh auth status 2>&1 | grep -i "token scopes" | sed "s/.*Token scopes: '//" | sed "s/'$//")

# Check for required scopes
REQUIRED="repo read:org project read:project"
MISSING=""

for scope in $REQUIRED; do
  if ! echo "$SCOPES" | grep -q "$scope"; then
    MISSING="$MISSING $scope"
  fi
done

if [ -n "$MISSING" ]; then
  echo "Missing scopes:$MISSING"
else
  echo "All required scopes present"
fi
```

### Step 4: Get Authenticated User

**Using bash with jq:**
```bash
gh api user --jq '.login'
```

**Using bash without jq:**
```bash
gh api user | grep -o '"login":"[^"]*"' | cut -d'"' -f4
```

## Error Handling

### Not Logged In

**Error:**
```
You are not logged into any GitHub hosts. Run gh auth login to authenticate.
```

**Recovery:**
```bash
gh auth login
```

This opens an interactive browser-based authentication flow.

### Missing Scopes

**Error:**
```
Missing scopes: project read:project
```

**Recovery:**
```bash
gh auth refresh --scopes 'repo,read:org,project,read:project'
```

This refreshes the token with additional scopes without requiring full re-authentication.

### Token Expired

**Error:**
```
error: authentication token has expired
```

**Recovery:**
```bash
gh auth refresh
```

Or if that fails:
```bash
gh auth login
```

### Insufficient Permissions

**Error (during API call):**
```
GraphQL: Resource not accessible by integration (...)
```

**Cause:** Token has required scopes but user lacks permission to the resource (not a member of org, not a collaborator on repo).

**Recovery:** Verify user has access to the target organization/repository.

## Decision Flow

```
┌─────────────────────────────────────────────────────────┐
│              Check gh auth status                        │
└─────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
     Authenticated              Not authenticated
            │                           │
            │                           ▼
            │               ┌───────────────────────┐
            │               │ STOP: Run gh auth     │
            │               │ login first           │
            │               └───────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│              Extract token scopes                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│       Check for required scopes                          │
│       (repo, read:org, project, read:project)           │
└─────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
     All present                 Scopes missing
            │                           │
            ▼                           ▼
      CONTINUE               ┌───────────────────────┐
                            │ STOP: Run gh auth      │
                            │ refresh --scopes '...' │
                            └───────────────────────┘
```

## Examples

### Example 1: Successful Authentication Check

**Command:**
```bash
gh auth status
```

**Output:**
```
github.com
  ✓ Logged in to github.com account myuser (keyring)
  - Active account: true
  - Git operations protocol: ssh
  - Token: gho_************************************
  - Token scopes: 'project', 'read:org', 'read:project', 'repo'
```

**Result:** All required scopes present. Proceed with operations.

### Example 2: Missing Project Scopes

**Command:**
```bash
gh auth status
```

**Output:**
```
github.com
  ✓ Logged in to github.com account myuser (keyring)
  - Token scopes: 'read:org', 'repo'
```

**Analysis:** Missing `project` and `read:project` scopes.

**Recovery:**
```bash
gh auth refresh --scopes 'repo,read:org,project,read:project'
```

### Example 3: Not Authenticated

**Command:**
```bash
gh auth status
```

**Output:**
```
You are not logged into any GitHub hosts. Run gh auth login to authenticate.
```

**Recovery:**
```bash
gh auth login
```

Follow the interactive prompts to authenticate.

## Cross-Platform Notes

| Aspect | Unix (Linux/macOS) | Windows |
|--------|-------------------|---------|
| Token storage | Keyring/keychain | Windows Credential Manager |
| Browser auth | Opens default browser | Opens default browser |
| SSH vs HTTPS | User choice during login | User choice during login |

## Related Patterns

- **tool-detection.md** - Must run first to ensure gh CLI available
- **workspace-detection.md** - Runs after authentication verified
- **graphql-queries.md** - Requires authentication for API calls
