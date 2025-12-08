---
name: hiivmind-pulse-gh-user-init
description: >
  First-time user setup: verify GitHub CLI installation, authenticate with required scopes,
  and check dependencies (yq, jq). Run this BEFORE workspace-init or any other skill.
  Re-run if you encounter scope/permission errors.
---

# GitHub User Setup

Verify and configure user environment for hiivmind-pulse-gh operations. This is a **prerequisite** for all other skills.

## Prerequisites Checklist

| Requirement | Purpose | Check Command |
|-------------|---------|---------------|
| GitHub CLI (`gh`) | All GitHub API operations | `gh --version` |
| `jq` (1.6+) | JSON processing | `jq --version` |
| `yq` (4.0+) | YAML processing | `yq --version` |
| GitHub auth | API access | `gh auth status` |
| Project scopes | Projects v2 access | `gh auth status` (check scopes) |

## Process Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. CHECK CLI    →  2. CHECK AUTH   →  3. CHECK SCOPES  →  4. CHECK DEPS   │
│     (gh exists?)      (logged in?)       (project scope?)     (yq, jq?)    │
│                                                                             │
│  5. FIX ISSUES   →  6. VERIFY       →  7. REPORT                           │
│     (if needed)       (all green?)       (status summary)                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Check GitHub CLI

```bash
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is not installed."
    echo ""
    echo "Install instructions:"
    echo "  Ubuntu/Debian: sudo apt install gh"
    echo "  macOS:         brew install gh"
    echo "  Other:         https://cli.github.com/manual/installation"
    exit 1
fi

GH_VERSION=$(gh --version | head -1)
echo "GitHub CLI: $GH_VERSION"
```

## Phase 2: Check Authentication

```bash
if ! gh auth status &> /dev/null; then
    echo "Not logged in to GitHub CLI."
    echo ""
    echo "Run: gh auth login"
    echo ""
    echo "When prompted, select:"
    echo "  - GitHub.com (or your enterprise host)"
    echo "  - HTTPS (recommended)"
    echo "  - Login with a web browser (or paste token)"
    exit 1
fi

# Get current auth details
AUTH_STATUS=$(gh auth status 2>&1)
ACCOUNT=$(echo "$AUTH_STATUS" | grep -oP 'account \K\S+' | head -1)
echo "Authenticated as: $ACCOUNT"
```

## Phase 3: Check Token Scopes

The following scopes are **required** for full functionality:

| Scope | Required For |
|-------|--------------|
| `repo` | Repository access, issues, PRs |
| `read:org` | Organization membership |
| `read:project` | Read Projects v2 data |
| `project` | Write Projects v2 data (optional for read-only use) |

### Check Current Scopes

```bash
AUTH_STATUS=$(gh auth status 2>&1)
CURRENT_SCOPES=$(echo "$AUTH_STATUS" | grep -oP "Token scopes: '\K[^']+")

echo "Current scopes: $CURRENT_SCOPES"

# Required scopes
REQUIRED_SCOPES=("repo" "read:org" "read:project")
OPTIONAL_SCOPES=("project")  # For write operations

MISSING_REQUIRED=()
MISSING_OPTIONAL=()

for scope in "${REQUIRED_SCOPES[@]}"; do
    if [[ ! "$CURRENT_SCOPES" =~ $scope ]]; then
        MISSING_REQUIRED+=("$scope")
    fi
done

for scope in "${OPTIONAL_SCOPES[@]}"; do
    if [[ ! "$CURRENT_SCOPES" =~ $scope ]]; then
        MISSING_OPTIONAL+=("$scope")
    fi
done

if [[ ${#MISSING_REQUIRED[@]} -gt 0 ]]; then
    echo ""
    echo "MISSING REQUIRED SCOPES: ${MISSING_REQUIRED[*]}"
    echo ""
    echo "Your token needs additional scopes for Projects v2 access."
fi

if [[ ${#MISSING_OPTIONAL[@]} -gt 0 ]]; then
    echo "MISSING OPTIONAL SCOPES: ${MISSING_OPTIONAL[*]}"
    echo "(Only needed for write operations)"
fi
```

### Fix Missing Scopes

If scopes are missing, refresh authentication:

```bash
# For read-only access (minimum):
gh auth refresh --scopes "repo,read:org,read:project"

# For full read/write access (recommended):
gh auth refresh --scopes "repo,read:org,read:project,project"
```

**Alternative: Re-authenticate completely:**

```bash
gh auth logout
gh auth login --scopes "repo,read:org,read:project,project"
```

### Verify Scopes Work

Test that Projects v2 queries succeed:

```bash
# Quick test - get viewer's login
gh api graphql -f query='{ viewer { login } }' --jq '.data.viewer.login'

# Test project access (will fail without read:project scope)
gh api graphql -f query='{ viewer { projectsV2(first: 1) { totalCount } } }' \
    --jq '.data.viewer.projectsV2.totalCount' 2>/dev/null

if [[ $? -eq 0 ]]; then
    echo "Projects v2 access: OK"
else
    echo "Projects v2 access: FAILED - check scopes"
fi
```

## Phase 4: Check Dependencies

### jq

```bash
if ! command -v jq &> /dev/null; then
    echo "jq is not installed."
    echo ""
    echo "Install instructions:"
    echo "  Ubuntu/Debian: sudo apt install jq"
    echo "  macOS:         brew install jq"
    exit 1
fi

JQ_VERSION=$(jq --version)
echo "jq: $JQ_VERSION"

# Check version (need 1.6+)
JQ_MAJOR=$(echo "$JQ_VERSION" | grep -oP 'jq-\K\d+')
JQ_MINOR=$(echo "$JQ_VERSION" | grep -oP 'jq-\d+\.\K\d+')
if [[ "$JQ_MAJOR" -lt 1 ]] || [[ "$JQ_MAJOR" -eq 1 && "$JQ_MINOR" -lt 6 ]]; then
    echo "Warning: jq 1.6+ recommended (found $JQ_VERSION)"
fi
```

### yq

```bash
# yq might be in /snap/bin on Ubuntu
export PATH="/snap/bin:$PATH"

if ! command -v yq &> /dev/null; then
    echo "yq is not installed."
    echo ""
    echo "Install instructions:"
    echo "  Ubuntu (snap): sudo snap install yq"
    echo "  macOS:         brew install yq"
    echo "  Other:         https://github.com/mikefarah/yq#install"
    exit 1
fi

YQ_VERSION=$(yq --version)
echo "yq: $YQ_VERSION"
```

**Note:** On Ubuntu with snap, yq is installed at `/snap/bin/yq`. You may need to add this to your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc:
export PATH="/snap/bin:$PATH"
```

## Phase 5: Complete Setup Script

Run this script to check all prerequisites at once:

```bash
#!/bin/bash
# hiivmind-pulse-gh user setup check

set -e

echo "=== hiivmind-pulse-gh User Setup Check ==="
echo ""

# Add snap to PATH for yq
export PATH="/snap/bin:$PATH"

ERRORS=0

# 1. Check gh
echo -n "GitHub CLI (gh): "
if command -v gh &> /dev/null; then
    echo "$(gh --version | head -1)"
else
    echo "NOT FOUND"
    echo "  Install: https://cli.github.com/"
    ERRORS=$((ERRORS + 1))
fi

# 2. Check jq
echo -n "jq: "
if command -v jq &> /dev/null; then
    echo "$(jq --version)"
else
    echo "NOT FOUND"
    echo "  Install: sudo apt install jq"
    ERRORS=$((ERRORS + 1))
fi

# 3. Check yq
echo -n "yq: "
if command -v yq &> /dev/null; then
    echo "$(yq --version)"
else
    echo "NOT FOUND"
    echo "  Install: sudo snap install yq"
    ERRORS=$((ERRORS + 1))
fi

# 4. Check gh auth
echo -n "GitHub auth: "
if gh auth status &> /dev/null; then
    ACCOUNT=$(gh auth status 2>&1 | grep -oP 'account \K\S+' | head -1)
    echo "Logged in as $ACCOUNT"
else
    echo "NOT AUTHENTICATED"
    echo "  Run: gh auth login"
    ERRORS=$((ERRORS + 1))
fi

# 5. Check scopes
echo -n "Token scopes: "
AUTH_STATUS=$(gh auth status 2>&1)
CURRENT_SCOPES=$(echo "$AUTH_STATUS" | grep -oP "Token scopes: '\K[^']+" || echo "unknown")
echo "$CURRENT_SCOPES"

# Check for read:project scope
if [[ ! "$CURRENT_SCOPES" =~ "read:project" ]]; then
    echo ""
    echo "  MISSING: read:project scope (required for Projects v2)"
    echo "  Fix: gh auth refresh --scopes 'repo,read:org,read:project,project'"
    ERRORS=$((ERRORS + 1))
fi

# 6. Test Projects v2 access
echo -n "Projects v2 access: "
if gh api graphql -f query='{ viewer { projectsV2(first: 1) { totalCount } } }' &> /dev/null; then
    echo "OK"
else
    echo "FAILED"
    ERRORS=$((ERRORS + 1))
fi

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "All checks passed! Ready to use hiivmind-pulse-gh."
    echo ""
    echo "Next step: Run hiivmind-pulse-gh-workspace-init to set up your workspace."
else
    echo "$ERRORS issue(s) found. Please fix before proceeding."
fi
```

## Output Summary

**All checks pass:**

```
=== hiivmind-pulse-gh User Setup Check ===

GitHub CLI (gh): gh version 2.40.0 (2024-01-15)
jq: jq-1.7
yq: yq (https://github.com/mikefarah/yq/) version v4.40.5
GitHub auth: Logged in as username
Token scopes: 'admin:public_key', 'gist', 'read:org', 'read:project', 'repo', 'project'
Projects v2 access: OK

All checks passed! Ready to use hiivmind-pulse-gh.

Next step: Run hiivmind-pulse-gh-workspace-init to set up your workspace.
```

**Issues found:**

```
=== hiivmind-pulse-gh User Setup Check ===

GitHub CLI (gh): gh version 2.40.0 (2024-01-15)
jq: jq-1.7
yq: NOT FOUND
  Install: sudo snap install yq
GitHub auth: Logged in as username
Token scopes: 'admin:public_key', 'gist', 'read:org', 'repo'

  MISSING: read:project scope (required for Projects v2)
  Fix: gh auth refresh --scopes 'repo,read:org,read:project,project'

Projects v2 access: FAILED

2 issue(s) found. Please fix before proceeding.
```

---

## Quick Fix Commands

| Issue | Fix Command |
|-------|-------------|
| gh not installed | `sudo apt install gh` or `brew install gh` |
| jq not installed | `sudo apt install jq` or `brew install jq` |
| yq not installed | `sudo snap install yq` or `brew install yq` |
| Not logged in | `gh auth login` |
| Missing scopes | `gh auth refresh --scopes "repo,read:org,read:project,project"` |
| yq not in PATH | `export PATH="/snap/bin:$PATH"` |

---

## Reference

- Initialize workspace: `skills/hiivmind-pulse-gh-workspace-init/SKILL.md`
- Refresh workspace: `skills/hiivmind-pulse-gh-workspace-refresh/SKILL.md`
- GitHub CLI docs: https://cli.github.com/manual/
- yq docs: https://mikefarah.gitbook.io/yq/
