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

**Required setup (must be completed first):**
1. `hiivmind-pulse-gh-user-init` - Validates environment, creates `user.yaml`
2. `hiivmind-pulse-gh-workspace-init` - Discovers projects/repos, creates `config.yaml`

This skill updates existing configuration files. If they don't exist, run the init skills first.

## Quick Start

```bash
# Source functions (once per session)
source lib/github/gh-workspace-functions.sh

# Check status without making changes
print_config_status

# Generate a full change report
generate_refresh_report

# Apply refresh (regenerate config from GitHub)
refresh_workspace
```

## When to Refresh

| Trigger | Action |
|---------|--------|
| Periodically | Config older than 7 days |
| After errors | "Field not found", "Option not found" |
| After GitHub changes | New fields added, options renamed |
| Team sync | After pulling config changes from git |

## Function Reference

### Status & Diagnostics

| Function | Purpose | Example |
|----------|---------|---------|
| `print_config_status` | Show workspace status summary | `print_config_status` |
| `get_config_age_days` | Get config age in days | `age=$(get_config_age_days)` |
| `check_config_staleness [DAYS]` | Check if stale (default 7 days) | `if check_config_staleness 7; then ...` |

### Change Detection

| Function | Purpose | Example |
|----------|---------|---------|
| `detect_project_changes` | Find added/removed projects | `detect_project_changes` |
| `detect_field_changes NUM` | Find field changes for project | `detect_field_changes 2` |
| `detect_repository_changes` | Find added/removed repos | `detect_repository_changes` |
| `generate_refresh_report` | Full report of all changes | `generate_refresh_report` |

### Refresh Actions

| Function | Purpose | Example |
|----------|---------|---------|
| `refresh_workspace` | Full refresh (regenerate config) | `refresh_workspace` |
| `update_sync_timestamp` | Update timestamp only (quick sync) | `update_sync_timestamp` |

## Process Overview

```
1. CHECK STATUS    →   2. DETECT CHANGES   →   3. REVIEW REPORT   →   4. APPLY REFRESH
   (print_config_status)  (generate_refresh_report)  (user reviews)       (refresh_workspace)
```

## Example Workflows

### Quick Status Check

```bash
source lib/github/gh-workspace-functions.sh

print_config_status
# Workspace: hiivmind (organization)
# Last synced: 2025-12-08T22:05:29Z
# Config age: 0 days
# Status: Fresh
# Projects cached: 2
# Repositories cached: 1
```

### Full Change Detection

```bash
source lib/github/gh-workspace-functions.sh

generate_refresh_report
# === Workspace Refresh Report for hiivmind ===
#
# Workspace: hiivmind (organization)
# Last synced: 2025-12-08T22:05:29Z
# ...
#
# --- Change Detection ---
#
# PROJECTS
#   No changes
#
# PROJECT #1 FIELDS
#   No changes
#
# PROJECT #2 FIELDS
#   ADDED: NewField
#
# REPOSITORIES
#   ADDED: new-repo
#
# === End Report ===
```

### Apply Refresh

```bash
source lib/github/gh-workspace-functions.sh

# Check for changes first
generate_refresh_report

# If changes look good, apply them
refresh_workspace
# Refreshing workspace for hiivmind (organization)...
# Projects to refresh: 1 2
# Repositories to refresh: hiivmind-pulse-gh
#
# Regenerating config.yaml...
# Updating user permissions...
#
# Workspace refresh complete!
```

### Automated Staleness Check

```bash
source lib/github/gh-workspace-functions.sh

# In a script or before operations
if check_config_staleness 7; then
    echo "Config is stale (>7 days old). Refreshing..."
    refresh_workspace
fi
```

## Change Report Symbols

| Symbol | Meaning |
|--------|---------|
| ADDED | New item detected in GitHub |
| REMOVED | Item no longer exists in GitHub |
| No changes | Cached state matches GitHub |

## Error Recovery

If operations fail due to stale IDs:

```
Error: Field ID "PVTSSF_xxxxxxx" not found in project.
```

**Solution:**
```bash
source lib/github/gh-workspace-functions.sh
refresh_workspace
```

## Files Modified

| File | Description |
|------|-------------|
| `.hiivmind/github/config.yaml` | Regenerated with fresh GitHub data |
| `.hiivmind/github/user.yaml` | Permissions updated |

## Reference

- Functions library: `lib/github/gh-workspace-functions.sh`
- Initialize workspace: `skills/hiivmind-pulse-gh-workspace-init/SKILL.md`
- User setup: `skills/hiivmind-pulse-gh-user-init/SKILL.md`
