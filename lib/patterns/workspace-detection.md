# Pattern: Workspace Detection

## Purpose

Detect the GitHub workspace (organization or user) from git context or user input, handling ambiguous situations gracefully.

## When to Use

- First step of init workflow, after tool detection and authentication
- When workspace context is needed but not yet cached in config.yaml
- When re-initializing or switching workspace targets

## Workspace Root Resolution (Normative)

This section is the single source of truth for locating configuration.
All skills, hooks, and commands MUST use this algorithm. The two-level
check (`.` then `..`) is retired.

### CRITICAL: `.hiivmind/` Is a Multi-Plugin Namespace

The `.hiivmind/` directory is shared across multiple hiivmind plugins:
- `.hiivmind/github/` — hiivmind-pulse-gh (this plugin)
- `.hiivmind/corpus/` — hiivmind-corpus
- Other plugins may add their own subdirectories

**NEVER delete, move, or replace a `.hiivmind/` directory.** Only operate on
`.hiivmind/github/`, which is this plugin's subdirectory — and, when placed at
a workspace root, its own git repository (see "The Workspace Repo" below).

### The two config layers (D2)

| Layer | Location | Marker | Role |
|-------|----------|--------|------|
| **Workspace config (base)** | `{workspace_root}/.hiivmind/github/config.yaml` | HAS a top-level `workspace:` section | Workspace identity, project/repo catalogs, teams, relationships, org-wide workflows, poll-state, runs |
| **Repo overlay (optional)** | `{repo}/.hiivmind/github/config.yaml` | MUST NOT have a `workspace:` section | Repo-scoped workflows and setting overrides only |

The `workspace_root` is typically the parent folder holding all of an org's
repo clones (`~/git/{org}/`), but for a standalone single-repo setup it may be
the repo itself. What makes a directory the workspace root is the marker, not
its position.

Precedence: the workspace config is the base; a repo overlay wins for scalar
conflicts **within its own repo's scope**. An overlay never carries workspace
identity — resolution skips any config lacking the `workspace:` marker and
keeps walking up.

### Resolution algorithm

```bash
# Resolve the workspace root: walk up from a start dir to the first directory
# whose .hiivmind/github/config.yaml carries a top-level `workspace:` section.
# Prints the workspace root (the dir CONTAINING .hiivmind/); exit 1 if none.
resolve_workspace_root() {
    local dir="${1:-$PWD}"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/.hiivmind/github/config.yaml" ]] \
           && grep -q '^workspace:' "$dir/.hiivmind/github/config.yaml"; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

WORKSPACE_ROOT=$(resolve_workspace_root) || WORKSPACE_ROOT=""
CONFIG_PATH="${WORKSPACE_ROOT:+$WORKSPACE_ROOT/.hiivmind/github/config.yaml}"
```

Overlay discovery (only meaningful when inside a git repo that is not itself
the workspace root):

```bash
REPO_TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
OVERLAY_DIR=""
if [[ -n "$REPO_TOPLEVEL" && "$REPO_TOPLEVEL" != "$WORKSPACE_ROOT" \
      && -d "$REPO_TOPLEVEL/.hiivmind/github" ]]; then
    OVERLAY_DIR="$REPO_TOPLEVEL/.hiivmind/github"
fi
```

**Result interpretation:**
- `WORKSPACE_ROOT` non-empty → use `$CONFIG_PATH` as the base config; apply
  `$OVERLAY_DIR` overrides if present.
- `WORKSPACE_ROOT` empty → workspace not initialized; prompt for `gh-init`.

### D4: Headless skills never discover

Directory discovery is an **interactive-only** convenience. Any headless skill
(P3+) MUST take explicit `workspace_path` (and, where relevant, `repo`) inputs
in its frontmatter and MUST NOT call `resolve_workspace_root`. In CI or a
scheduled runtime a single repo is checked out and no parent workspace exists;
discovery there is undefined behavior.

### The Workspace Repo (D1)

`{workspace_root}/.hiivmind/github/` is itself a small git repository — the
"workspace repo" — shared by the team via a private remote (default name
`{login}-workspace`). It versions the human-authored and shared assets;
per-machine transients are gitignored:

| Committed (shared) | Gitignored (per-machine) |
|--------------------|--------------------------|
| `config.yaml`, `freshness.yaml` | `user.yaml` |
| `workflows/`, `views/`, `repos/`, `automations/` | `poll-state.yaml` |
| `teams.yaml`, `relationships.yaml`, `healthcheck.yaml` | `project-snapshot.json`, `*-result.yaml` |
| `runs/` (run ledger) | `log/` |

Repo clone directories are siblings of `.hiivmind/`, outside the workspace
repo entirely — no nested-repo or ignore gymnastics.

### Multi-machine, multi-actor topology

Each machine's workspace root holds its own **clone** of the shared workspace
repo plus its own set of repo clones, possibly at different states. The team
is M:M across individuals, GitHub profiles, and physical machines. Rules:

- **Shared vs. per-machine split:** committed workspace-repo content is the
  *only* shared state. `poll-state.yaml`, snapshots, and result files are
  per-machine advisory caches — two machines legitimately hold different
  poll-state. Never commit them; never treat them as authority.
- **Pull before reconcile:** any run that reads or writes shared markers
  (config catalogs, workflow definitions, dismissals, run ledger, binding
  state) pulls the workspace repo first. Local caches are never authority.
- **Cooldowns are advisory:** poll-state cooldown bookkeeping is per-machine
  and cannot enforce a global rate across machines. It is a politeness
  optimization only; global correctness comes from idempotent runs plus the
  supersede pattern, not from cooldowns.
- **Actor attribution:** every run records the human, the GitHub profile
  (`gh auth` identity), and the machine — in run records and result files.
  Identity-sensitive logic ("you touched this", self-assignment) resolves
  against the recorded actor, not whatever profile the current machine holds.
- **Local clones are never sync sources:** skills read pushed commits and API
  state; a dirty or unpushed repo clone is surfaced as a finding, never
  consumed as truth.

## Prerequisites

- **tool-detection.md** - git must be available for git-based detection
- **authentication.md** - gh CLI must be authenticated for type detection

## Algorithm

### Step 1: Check If In Git Repository

**Using bash:**
```bash
git rev-parse --is-inside-work-tree 2>/dev/null && echo "in_git_repo" || echo "not_git_repo"
```

**Result interpretation:**
- `in_git_repo` → Proceed to Step 2
- `not_git_repo` → Skip to Step 3 (ask user)

---

### Step 2: Extract Owner From Git Remote

**Check if origin remote exists:**
```bash
git remote get-url origin 2>/dev/null
```

**If no origin remote:** Skip to Step 3 (ask user)

**Extract owner from remote URL:**

The remote URL can be in multiple formats:
- SSH: `git@github.com:owner/repo.git`
- HTTPS: `https://github.com/owner/repo.git`
- HTTPS (no .git): `https://github.com/owner/repo`

**Using bash (handles all formats):**
```bash
# Extract owner from any GitHub URL format
git remote get-url origin 2>/dev/null | sed -E 's#(git@github\.com:|https://github\.com/)##' | sed -E 's#/.*##'
```

**Alternative (more explicit):**
```bash
URL=$(git remote get-url origin 2>/dev/null)
if [[ "$URL" == git@* ]]; then
    # SSH format: git@github.com:owner/repo.git
    echo "$URL" | sed -E 's#git@github\.com:([^/]+)/.*#\1#'
elif [[ "$URL" == https://* ]]; then
    # HTTPS format: https://github.com/owner/repo.git
    echo "$URL" | sed -E 's#https://github\.com/([^/]+)/.*#\1#'
fi
```

---

### Step 3: Handle Non-Git Context (User Collaboration)

**When to ask the user:**

1. Not in a git repository
2. No git remote configured
3. Multiple remotes exist (need to choose)
4. Owner extraction failed

**Prompt template:**
```
I couldn't detect a GitHub workspace from git context.

Please specify the GitHub organization or username you want to initialize:
```

**With context (multi-repo parent):**
```
You're in a directory without a git remote. This might be a multi-repo parent directory.

Please specify the GitHub organization or username to initialize:

Examples:
- Organization: "hiivmind"
- Personal account: "your-username"
```

**IMPORTANT:** Never auto-decide on a workspace target. Always confirm with user if detection is uncertain.

---

### Step 4: Determine Workspace Type (Org vs User)

Once we have an owner login, determine if it's an organization or user account.

**Using gh API:**
```bash
# Try organization first (more common for team projects)
TYPE=$(gh api "orgs/$OWNER" --jq '.type' 2>/dev/null)

if [[ "$TYPE" == "Organization" ]]; then
    echo "organization"
else
    # Check if it's a user
    TYPE=$(gh api "users/$OWNER" --jq '.type' 2>/dev/null)
    if [[ "$TYPE" == "User" ]]; then
        echo "user"
    else
        echo "not_found"
    fi
fi
```

**Compact version:**
```bash
gh api "orgs/$OWNER" --jq '.type' 2>/dev/null | grep -q "Organization" && echo "organization" || echo "user"
```

---

## Decision Flow

```
┌─────────────────────────────────────────────────────────┐
│         Check: git rev-parse --is-inside-work-tree      │
└─────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
      In git repo                 Not in git repo
            │                           │
            ▼                           │
┌───────────────────────┐               │
│ git remote get-url    │               │
│ origin                │               │
└───────────────────────┘               │
            │                           │
     ┌──────┴──────┐                    │
     │             │                    │
     ▼             ▼                    │
Has origin    No origin                 │
     │             │                    │
     ▼             └────────────────────┤
┌───────────────────────┐               │
│ Extract owner from    │               │
│ remote URL            │               │
└───────────────────────┘               │
     │                                  │
     ▼                                  ▼
┌───────────────────────┐    ┌───────────────────────┐
│ Confirm with user:    │    │ STOP: Ask user to     │
│ "Detected workspace   │    │ specify owner         │
│ 'X'. Correct?"        │    │                       │
└───────────────────────┘    └───────────────────────┘
            │                           │
            └─────────────┬─────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│         Determine type: gh api orgs/{owner}             │
└─────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
      Organization                    User
            │                           │
            └─────────────┬─────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│         Return: { login, type, detected_from }          │
└─────────────────────────────────────────────────────────┘
```

---

## User Collaboration Points

### Always Confirm Detection

Even when workspace is auto-detected from git remote, confirm with user:

```
Detected workspace from git remote:
  Owner: hiivmind
  Type: organization

Is this the workspace you want to initialize? [Y/n]
```

### Ask When Ambiguous

When detection fails or is uncertain:

```
I couldn't determine the workspace from git context.

Which GitHub organization or username should I initialize?
```

### Multiple Remotes

When repository has multiple remotes:

```
Found multiple git remotes:
  1. origin → hiivmind/repo-name
  2. upstream → other-org/repo-name

Which remote should I use for workspace detection?
```

---

## Error Handling

### Not In Git Repository

**Detection:**
```bash
git rev-parse --is-inside-work-tree 2>/dev/null || echo "not_git"
```

**Response:**
```
You're not in a git repository.

To initialize a workspace, please either:
1. Navigate to a git repository with a GitHub remote
2. Specify the workspace manually: "Initialize workspace for [org/user]"
```

### No Remote Configured

**Detection:**
```bash
git remote get-url origin 2>/dev/null || echo "no_remote"
```

**Response:**
```
This repository has no 'origin' remote configured.

Please specify the GitHub organization or username to initialize:
```

### Owner Not Found

**Detection:**
```bash
gh api "orgs/$OWNER" 2>/dev/null || gh api "users/$OWNER" 2>/dev/null || echo "not_found"
```

**Response:**
```
Could not find GitHub organization or user '$OWNER'.

Please check:
- The spelling is correct
- You have access to this organization
- The account exists on GitHub
```

### Non-GitHub Remote

**Detection:**
```bash
git remote get-url origin | grep -q "github.com" || echo "not_github"
```

**Response:**
```
The 'origin' remote points to a non-GitHub host.

This plugin only supports GitHub. Please specify a GitHub organization or username:
```

---

## Examples

### Example 1: Happy Path (In Git Repo)

**Context:** User runs init from `/home/user/projects/my-repo/`

**Detection:**
```bash
$ git rev-parse --is-inside-work-tree
true

$ git remote get-url origin
git@github.com:hiivmind/my-repo.git

$ # Extract owner
$ echo "git@github.com:hiivmind/my-repo.git" | sed -E 's#git@github\.com:([^/]+)/.*#\1#'
hiivmind

$ # Check type
$ gh api orgs/hiivmind --jq '.type'
Organization
```

**Result:** `{ login: "hiivmind", type: "organization", detected_from: "git_remote" }`

### Example 2: Multi-Repo Parent Directory

**Context:** User runs init from `/home/user/projects/hiivmind/` (contains multiple repos)

**Detection:**
```bash
$ git rev-parse --is-inside-work-tree
fatal: not a git repository

$ # Not in git repo - ask user
```

**User interaction:**
```
You're in a directory without a git repository.
This might be a multi-repo parent directory.

Please specify the GitHub organization or username to initialize:
> hiivmind

Detected workspace:
  Owner: hiivmind
  Type: organization

Proceed with initialization? [Y/n]
```

**Result:** `{ login: "hiivmind", type: "organization", detected_from: "user_input" }`

### Example 3: Personal Repository

**Context:** User runs init on their personal repo

**Detection:**
```bash
$ git remote get-url origin
https://github.com/discreteds/my-project.git

$ gh api orgs/discreteds --jq '.type'
# (error - not an org)

$ gh api users/discreteds --jq '.type'
User
```

**Result:** `{ login: "discreteds", type: "user", detected_from: "git_remote" }`

---

## Git Remote URL Best Practices

### Default to SSH Remotes

**IMPORTANT:** When adding git remotes, always prefer SSH format over HTTPS.

| Format | URL Pattern | Recommendation |
|--------|-------------|----------------|
| SSH | `git@github.com:owner/repo.git` | ✅ **Preferred** |
| HTTPS | `https://github.com/owner/repo.git` | ⚠️ Avoid for CLI |

**Why SSH is preferred:**
1. **Authentication:** SSH keys work silently; HTTPS prompts for credentials
2. **Reliability:** SSH doesn't expire or require credential manager
3. **Automation:** Scripts and CI work without interactive auth
4. **Modern standard:** GitHub recommends SSH for CLI/terminal use

**When creating remotes:**
```bash
# ✅ CORRECT - SSH format
git remote add origin git@github.com:owner/repo.git

# ❌ AVOID - HTTPS format (will fail without credential manager)
git remote add origin https://github.com/owner/repo.git
```

**When fixing HTTPS remotes:**
```bash
# Convert HTTPS to SSH
git remote set-url origin git@github.com:owner/repo.git
```

**Detecting and fixing:**
```bash
URL=$(git remote get-url origin 2>/dev/null)
if [[ "$URL" == https://* ]]; then
    # Convert HTTPS to SSH
    SSH_URL=$(echo "$URL" | sed -E 's#https://github\.com/([^/]+)/(.*)#git@github.com:\1/\2#')
    echo "Consider switching to SSH: git remote set-url origin $SSH_URL"
fi
```

### HTTPS Exceptions

HTTPS is acceptable only when:
- SSH is blocked by firewall
- User explicitly prefers HTTPS with credential manager
- Running in CI environment with token auth

---

## Cross-Platform Notes

| Operation | Unix | Windows (PowerShell) |
|-----------|------|---------------------|
| Check git repo | `git rev-parse 2>/dev/null` | `git rev-parse 2>$null` |
| Extract with sed | `sed -E 's#pattern#\1#'` | Use PowerShell regex |
| Redirect stderr | `2>/dev/null` | `2>$null` |

**PowerShell alternative for URL parsing:**
```powershell
$url = git remote get-url origin 2>$null
if ($url -match 'github\.com[:/]([^/]+)/') { $Matches[1] }
```

---

## Related Patterns

- **tool-detection.md** - Must verify git is available before using
- **authentication.md** - Must be authenticated before querying gh api
- **config-parsing.md** - Writes detected workspace to config.yaml
- **graphql-queries.md** - Uses workspace type to choose org vs user queries
