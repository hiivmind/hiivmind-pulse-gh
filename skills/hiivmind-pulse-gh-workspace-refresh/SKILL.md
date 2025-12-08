---
name: hiivmind-pulse-gh-workspace-refresh
description: >
  Quick structural sync of workspace configuration. Validates cached IDs for projects, fields, options,
  repositories, and milestones. Detects renamed/added/removed fields and warns about breaking changes.
  Run frequently (daily/weekly) or when operations fail with "ID not found" errors.
  Does NOT cache volatile data like issue statuses - only stable structural metadata.
---

# GitHub Workspace Refresh

Synchronize the local workspace configuration with the current state of GitHub projects, fields, and repositories.

## Prerequisites

Requires:
- User environment configured (`hiivmind-pulse-gh-user-init`)
- Workspace initialized (`hiivmind-pulse-gh-workspace-init`)

## When to Refresh

- **Periodically** - Config older than 7 days
- **After errors** - "Field not found", "Option not found" errors
- **After GitHub changes** - New fields added, options renamed, repos created
- **Team sync** - After pulling config changes from git

## Process

```
1. LOAD       →  2. CHECK STATUS  →  3. DETECT CHANGES  →  4. REPORT   →  5. UPDATE
   (configs)       (staleness)         (per entity)          (to user)      (if approved)
```

## Phase 1: Load Configuration

```bash
CONFIG_PATH=".hiivmind/github/config.yaml"
USER_CONFIG_PATH=".hiivmind/github/user.yaml"

if [[ ! -f "$CONFIG_PATH" ]]; then
    echo "No workspace configuration found."
    echo "Run hiivmind-pulse-gh-workspace-init first."
    exit 1
fi

WORKSPACE_LOGIN=$(yq '.workspace.login' "$CONFIG_PATH")
LAST_SYNCED=$(yq '.cache.last_synced_at' "$CONFIG_PATH")

echo "Workspace: $WORKSPACE_LOGIN"
echo "Last synced: $LAST_SYNCED"
```

## Phase 2: Check Staleness

Calculate time since last sync:

```bash
if [[ "$LAST_SYNCED" != "null" ]]; then
    LAST_SYNC_EPOCH=$(date -d "$LAST_SYNCED" +%s 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    DAYS_OLD=$(( (NOW_EPOCH - LAST_SYNC_EPOCH) / 86400 ))

    if [[ $DAYS_OLD -gt 7 ]]; then
        echo "Warning: Config is $DAYS_OLD days old. Refresh recommended."
    else
        echo "Config is $DAYS_OLD days old."
    fi
fi
```

### Status Command

For quick status check without updating:

```bash
# Just report status, don't change anything
echo "Workspace: $WORKSPACE_LOGIN"
echo "Last synced: $LAST_SYNCED ($DAYS_OLD days ago)"
echo "Projects cached: $(yq '.projects.catalog | length' "$CONFIG_PATH")"
echo "Repositories cached: $(yq '.repositories | length' "$CONFIG_PATH")"
```

## Phase 3: Detect Changes

Compare cached state against current GitHub state.

### Project Changes

```bash
# Get current projects from GitHub
CURRENT_PROJECTS=$(discover_org_projects "$WORKSPACE_LOGIN")

# Get cached project numbers
CACHED_PROJECTS=$(yq '.projects.catalog[].number' "$CONFIG_PATH")

# Detect new projects
for proj in $(echo "$CURRENT_PROJECTS" | jq -r '.data.organization.projectsV2.nodes[].number'); do
    if ! echo "$CACHED_PROJECTS" | grep -q "^${proj}$"; then
        echo "NEW: Project #$proj"
    fi
done

# Detect removed projects
for proj in $CACHED_PROJECTS; do
    if ! echo "$CURRENT_PROJECTS" | jq -e ".data.organization.projectsV2.nodes[] | select(.number == $proj)" >/dev/null; then
        echo "REMOVED: Project #$proj"
    fi
done
```

### Field Changes

For each cached project, compare fields:

```bash
PROJECT_NUMBER=2
PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUMBER) | .id" "$CONFIG_PATH")

# Get current fields
CURRENT_FIELDS=$(fetch_org_project_fields "$PROJECT_NUMBER" "$WORKSPACE_LOGIN")

# Compare with cached
CACHED_FIELDS=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUMBER) | .fields | keys" "$CONFIG_PATH")

# Detect new fields
# Detect renamed fields (same ID, different name)
# Detect removed fields
# Detect new/changed options for single-select fields
```

### Field Change Detection Logic

```bash
# For each field in current state
for field_id in $(echo "$CURRENT_FIELDS" | jq -r '.data.organization.projectV2.fields.nodes[].id'); do
    FIELD_NAME=$(echo "$CURRENT_FIELDS" | jq -r ".data.organization.projectV2.fields.nodes[] | select(.id == \"$field_id\") | .name")

    # Check if field exists in cache
    CACHED_NAME=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUMBER) | .fields | to_entries[] | select(.value.id == \"$field_id\") | .key" "$CONFIG_PATH")

    if [[ -z "$CACHED_NAME" ]]; then
        echo "NEW FIELD: $FIELD_NAME ($field_id)"
    elif [[ "$CACHED_NAME" != "$FIELD_NAME" ]]; then
        echo "RENAMED FIELD: $CACHED_NAME -> $FIELD_NAME"
    fi
done
```

### Single-Select Option Changes

```bash
# For Status field, compare options
FIELD_NAME="Status"
CURRENT_OPTIONS=$(echo "$CURRENT_FIELDS" | jq -r "
    .data.organization.projectV2.fields.nodes[] |
    select(.name == \"$FIELD_NAME\") |
    .options[]? | \"\(.name):\(.id)\"
")

CACHED_OPTIONS=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUMBER) | .fields.${FIELD_NAME}.options | to_entries[] | \"\(.key):\(.value)\"" "$CONFIG_PATH")

# Compare and report differences
```

### Repository Changes

```bash
# Get current repos
CURRENT_REPOS=$(gh api "orgs/${WORKSPACE_LOGIN}/repos" --paginate --jq '.[].name')

# Compare with cached
CACHED_REPOS=$(yq '.repositories[].name' "$CONFIG_PATH")

# Detect new/removed repos
```

### Milestone Changes

```bash
# For each cached repo, check milestones
for repo in $(yq '.repositories[].name' "$CONFIG_PATH"); do
    CURRENT_MILESTONES=$(gh api "repos/${WORKSPACE_LOGIN}/${repo}/milestones" --jq '.[].number')
    CACHED_MILESTONES=$(yq ".milestones.${repo}[].number" "$CONFIG_PATH")

    # Compare and report
done
```

## Phase 4: Report Changes

Present changes to the user before applying:

```
Workspace Refresh Report for acme-corp
=======================================

Projects:
  ✓ #2 Product Roadmap - no changes
  ⚠ #1 Engineering Backlog - field changes detected:
      NEW FIELD: "Complexity" (single_select)
      RENAMED: "Urgency" -> "Priority"
      NEW OPTION in Status: "Blocked"

Repositories:
  ✓ api - no changes
  ✓ frontend - no changes
  + docs-v2 - NEW repository

Milestones:
  api:
    + v1.2.0 - NEW milestone
    ~ v1.1.0 - state changed: open -> closed

User Permissions:
  ~ Project #2: write -> admin (upgraded)
```

### Change Indicators

| Symbol | Meaning |
|--------|---------|
| ✓ | No changes |
| + | Added |
| - | Removed |
| ~ | Modified |
| ⚠ | Breaking change (may affect existing usage) |

## Phase 5: Update Configuration

After user approves, apply changes:

### Confirmation

```
Apply these changes? [Y/n]
```

Or with flags:
- `--yes` - Apply all changes without prompting
- `--dry-run` - Report changes but don't apply
- `--projects-only` - Only refresh project data
- `--permissions-only` - Only refresh user permissions

### Update Logic

```bash
# Update projects with new field structure
# Add new repositories
# Remove deleted repositories (with warning)
# Update milestones
# Refresh user permissions
# Update last_synced_at timestamp
```

### Breaking Change Handling

For breaking changes (removed fields, renamed options):

```
⚠ Breaking Change Detected:

The option "In Review" was removed from the Status field.
This may break existing automation or saved filters.

Cached ID: PVTSSFO_xxxxxxx4
Current options: Backlog, Ready, In Progress, Done

How to proceed:
  [1] Remove from cache (recommended if no longer used)
  [2] Keep in cache (may cause errors)
  [3] Cancel refresh
```

## Output Summary

```
Workspace refresh complete!

Changes applied:
  Projects: 1 updated, 0 added, 0 removed
  Fields: 2 new, 1 renamed
  Repositories: 1 added
  Milestones: 2 updated

Configs updated:
  .hiivmind/github/config.yaml
  .hiivmind/github/user.yaml

Last synced: 2025-12-08T15:30:00Z
```

## Automatic Refresh Triggers

Skills can check config age and suggest refresh:

```bash
check_config_freshness() {
    local config_path=".hiivmind/github/config.yaml"
    local max_age_days=7

    if [[ ! -f "$config_path" ]]; then
        return 0  # No config, nothing to check
    fi

    local last_synced=$(yq '.cache.last_synced_at' "$config_path")
    if [[ "$last_synced" == "null" ]]; then
        echo "⚠ Workspace config incomplete. Run hiivmind-pulse-gh-workspace-init."
        return 1
    fi

    # Calculate age and warn if stale
    # ...
}
```

## Error Recovery

If operations fail due to stale IDs:

```
Error: Field ID "PVTSSF_xxxxxxx" not found in project.

The cached field ID may be outdated. This can happen when:
  - A field was deleted from the project
  - A field was recreated (new ID)
  - The project structure was reset

Recommended action:
  Run: hiivmind-pulse-gh-workspace-refresh

To continue without cached IDs:
  Specify field by name instead of using cached ID
```

## Reference

- Initialize workspace: `skills/hiivmind-pulse-gh-workspace-init/SKILL.md`
- Investigate entities: `skills/hiivmind-pulse-gh-investigate/SKILL.md`
- Architecture: `docs/meta-skill-architecture.md`
