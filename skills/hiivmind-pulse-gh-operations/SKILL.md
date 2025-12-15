---
name: hiivmind-pulse-gh-operations
description: Execute GitHub operations across all domains (issues, PRs, milestones, projects, protection, actions, releases). Receives intent from gateway command, consults routing guide and corpus, executes via gh CLI. Use when the gateway command routes an operation here after intent detection.
---

# GitHub Operations Execution

This skill executes GitHub operations across all domains. It is invoked by the `/hiivmind-pulse-gh` gateway command after intent detection.

## Expected Context

When invoked, expect these to be provided or available:

- **Domain**: issues, pull_requests, milestones, labels, projects, branch_protection, rulesets, actions, secrets, variables, releases
- **Operation**: create, read, update, delete, link, trigger, merge
- **Target**: Specific entity (issue #42, milestone "v2.0", etc.)
- **Config path**: `.hiivmind/github/config.yaml`
- **User config path**: `.hiivmind/github/user.yaml`

---

## Step 1: Load Configuration

```bash
CONFIG=".hiivmind/github/config.yaml"
USER_CONFIG=".hiivmind/github/user.yaml"

# Core context
OWNER=$(yq '.workspace.login' "$CONFIG")
WORKSPACE_TYPE=$(yq '.workspace.type' "$CONFIG")
WORKSPACE_ID=$(yq '.workspace.id' "$CONFIG")

# Default project
DEFAULT_PROJECT=$(yq '.projects.default' "$CONFIG")

# First repository (or specify)
REPO=$(yq '.repositories[0].name' "$CONFIG")
REPO_ID=$(yq '.repositories[0].id' "$CONFIG")
REPO_FULL="$OWNER/$REPO"
```

---

## Extended Config Loading Functions (Phase 7)

Consolidated functions to load extended configuration files on demand.

### load_views()

Check if view configuration is cached for a project.

```bash
# Function to check if views are cached for a project
load_views() {
  local project_num=$1
  local view_file=".hiivmind/github/views/project-$project_num.yaml"

  if [[ -f "$view_file" ]]; then
    echo "loaded"
    return 0
  else
    echo "not_cached"
    return 1
  fi
}

# Usage
if load_views 2 >/dev/null; then
  echo "Views loaded for project 2"
  # Use view helpers from Step 2
else
  echo "Views not cached - operations will proceed without view awareness"
fi
```

### load_repo_settings()

Check if repository settings are cached.

```bash
# Function to check if repo settings are cached
load_repo_settings() {
  local repo_name=$1
  local repo_file=".hiivmind/github/repos/$repo_name.yaml"

  if [[ -f "$repo_file" ]]; then
    echo "loaded"
    return 0
  else
    echo "not_cached"
    return 1
  fi
}

# Usage
if load_repo_settings "hiivmind-pulse-gh" >/dev/null; then
  echo "Repository settings loaded"
  # Use repo helpers from Step 3
else
  echo "Repo settings not cached - using defaults"
fi
```

### load_automations()

Check if automations are documented for a project.

```bash
# Function to check if automations are documented
load_automations() {
  local project_num=$1
  local automations_file=".hiivmind/github/automations/project-$project_num.yaml"

  if [[ -f "$automations_file" ]]; then
    echo "loaded"
    return 0
  else
    echo "not_cached"
    return 1
  fi
}

# Usage
if load_automations 2 >/dev/null; then
  echo "Automations loaded for project 2"
  # Use automation helpers from Step 4
else
  echo "Automations not documented - proceeding without automation awareness"
fi
```

### load_relationships()

Check if cross-repo relationships are documented.

```bash
# Function to check if relationships are documented
load_relationships() {
  local relationships_file=".hiivmind/github/relationships.yaml"

  if [[ -f "$relationships_file" ]]; then
    echo "loaded"
    return 0
  else
    echo "not_cached"
    return 1
  fi
}

# Usage
if load_relationships >/dev/null; then
  echo "Relationships loaded"
  # Use relationship helpers from Step 5
else
  echo "Relationships not documented - proceeding without relationship awareness"
fi
```

### load_teams()

Check if organization teams are cached.

```bash
# Function to check if teams are cached
load_teams() {
  local teams_file=".hiivmind/github/teams.yaml"

  if [[ -f "$teams_file" ]]; then
    echo "loaded"
    return 0
  else
    echo "not_cached"
    return 1
  fi
}

# Usage
if load_teams >/dev/null; then
  echo "Teams loaded"
  # Use team helpers from Step 6
else
  echo "Teams not cached - proceeding without team awareness"
fi
```

### Batch Loading Pattern

Load all extended configs for an operation:

```bash
# Example: PR creation needs repos, teams, and optionally relationships
load_pr_configs() {
  local repo_name=$1

  # Load required configs
  load_repo_settings "$repo_name" >/dev/null
  REPO_SETTINGS_LOADED=$?

  load_teams >/dev/null
  TEAMS_LOADED=$?

  # Optional configs
  load_relationships >/dev/null
  RELATIONSHIPS_LOADED=$?

  # Report what's available
  [[ $REPO_SETTINGS_LOADED -eq 0 ]] && echo "✓ Repo settings loaded"
  [[ $TEAMS_LOADED -eq 0 ]] && echo "✓ Teams loaded (can suggest reviewers)"
  [[ $RELATIONSHIPS_LOADED -eq 0 ]] && echo "✓ Relationships loaded (cross-repo awareness)"
}

# Usage
load_pr_configs "hiivmind-pulse-gh"
```

---

## Step 2: Load View Configuration (Phase 2)

**Optional:** If the operation involves creating/updating project items, load view configuration to respect visible fields.

### Check if Views are Cached

```bash
PROJECT_NUM=2
VIEW_FILE=".hiivmind/github/views/project-$PROJECT_NUM.yaml"

if [[ -f "$VIEW_FILE" ]]; then
  echo "Views cached for project $PROJECT_NUM"
else
  echo "Views not cached - consider running refresh with views section"
fi
```

### Load View Configuration

```bash
PROJECT_NUM=2
VIEW_FILE=".hiivmind/github/views/project-$PROJECT_NUM.yaml"
VIEW_NAME="Backlog"  # Or use default view (number 1)

# Get visible fields for a view
VISIBLE_FIELDS=$(yq ".views[] | select(.name == \"$VIEW_NAME\") | .visible_fields[]" "$VIEW_FILE")

echo "Visible fields in $VIEW_NAME view:"
echo "$VISIBLE_FIELDS"
```

### Check if Field is Visible

```bash
# Function to check if a field should be shown in a view
is_field_visible() {
  local project_num=$1
  local view_name=$2
  local field_name=$3
  local view_file=".hiivmind/github/views/project-$project_num.yaml"

  if [[ ! -f "$view_file" ]]; then
    # No view config - assume all fields visible
    return 0
  fi

  local visible=$(yq ".views[] | select(.name == \"$view_name\") | .visible_fields[] | select(. == \"$field_name\")" "$view_file")

  if [[ -n "$visible" ]]; then
    return 0  # Field is visible
  else
    return 1  # Field is hidden
  fi
}

# Usage
if is_field_visible 2 "Backlog" "Priority"; then
  echo "Priority field is visible - safe to update"
else
  echo "Priority field is hidden in this view - skip or warn"
fi
```

### Get View's Visible Fields for Validation

When creating items or suggesting field updates, respect the view's visible fields:

```bash
PROJECT_NUM=2
VIEW_NAME="Current Sprint"
VIEW_FILE=".hiivmind/github/views/project-$PROJECT_NUM.yaml"

# Get all visible fields for the view
VISIBLE_FIELDS=$(yq ".views[] | select(.name == \"$VIEW_NAME\") | .visible_fields[]" "$VIEW_FILE")

echo "When adding items to '$VIEW_NAME' view, these fields are visible:"
echo "$VISIBLE_FIELDS"
echo ""
echo "Consider prompting user to set these fields."
```

### Get Default View for Project

```bash
PROJECT_NUM=2
VIEW_FILE=".hiivmind/github/views/project-$PROJECT_NUM.yaml"

# Default view is typically the first one (number: 1)
DEFAULT_VIEW=$(yq '.views[] | select(.number == 1) | .name' "$VIEW_FILE")

echo "Default view for project $PROJECT_NUM: $DEFAULT_VIEW"
```

---

## Step 3: Load Repository Settings (Phase 3)

**Optional:** If the operation involves PRs, branch protection, or merging, load repository settings to respect protection rules and merge preferences.

### Check if Repository Settings are Cached

```bash
REPO="hiivmind-pulse-gh"
REPO_FILE=".hiivmind/github/repos/$REPO.yaml"

if [[ -f "$REPO_FILE" ]]; then
  echo "Repository settings cached for $REPO"
else
  echo "Repository settings not cached - consider running refresh with repo_settings section"
fi
```

### Check Branch Protection Status

```bash
# Function to check if a branch has protection enabled
is_branch_protected() {
  local repo=$1
  local branch=$2
  local repo_file=".hiivmind/github/repos/$repo.yaml"

  if [[ ! -f "$repo_file" ]]; then
    # No repo config - assume not protected
    return 1
  fi

  local protected=$(yq ".branch_protection[\"$branch\"].enabled" "$repo_file")

  if [[ "$protected" = "true" ]]; then
    return 0  # Branch is protected
  else
    return 1  # Branch is not protected
  fi
}

# Usage
if is_branch_protected "hiivmind-pulse-gh" "main"; then
  echo "main branch is protected - PRs required"
else
  echo "main branch is not protected - direct push allowed"
fi
```

### Get Required Status Checks

```bash
REPO="hiivmind-pulse-gh"
BRANCH="main"
REPO_FILE=".hiivmind/github/repos/$REPO.yaml"

# Get required status checks for a branch
REQUIRED_CHECKS=$(yq ".branch_protection[\"$BRANCH\"].required_status_checks.contexts[]" "$REPO_FILE" 2>/dev/null)

if [[ -n "$REQUIRED_CHECKS" ]]; then
  echo "Required status checks for $BRANCH:"
  echo "$REQUIRED_CHECKS"
else
  echo "No required status checks for $BRANCH"
fi
```

### Get Required Review Count

```bash
REPO="hiivmind-pulse-gh"
BRANCH="main"
REPO_FILE=".hiivmind/github/repos/$REPO.yaml"

# Get required approving review count
REVIEW_COUNT=$(yq ".branch_protection[\"$BRANCH\"].required_pull_request_reviews.required_approving_review_count" "$REPO_FILE" 2>/dev/null)

if [[ "$REVIEW_COUNT" != "null" ]] && [[ "$REVIEW_COUNT" != "0" ]]; then
  echo "Branch $BRANCH requires $REVIEW_COUNT approving review(s)"
else
  echo "Branch $BRANCH has no review requirements"
fi
```

### Check Allowed Merge Methods

```bash
REPO="hiivmind-pulse-gh"
REPO_FILE=".hiivmind/github/repos/$REPO.yaml"

# Check which merge methods are allowed
ALLOW_MERGE=$(yq '.merge_settings.allow_merge_commit' "$REPO_FILE")
ALLOW_SQUASH=$(yq '.merge_settings.allow_squash_merge' "$REPO_FILE")
ALLOW_REBASE=$(yq '.merge_settings.allow_rebase_merge' "$REPO_FILE")

echo "Allowed merge methods for $REPO:"
[[ "$ALLOW_MERGE" = "true" ]] && echo "  - merge commit"
[[ "$ALLOW_SQUASH" = "true" ]] && echo "  - squash merge"
[[ "$ALLOW_REBASE" = "true" ]] && echo "  - rebase merge"
```

### Get Preferred Merge Method

```bash
# Function to get the preferred merge method
get_preferred_merge_method() {
  local repo=$1
  local repo_file=".hiivmind/github/repos/$repo.yaml"

  if [[ ! -f "$repo_file" ]]; then
    echo "merge"  # Default fallback
    return
  fi

  # Check in order of preference: squash, merge, rebase
  if [[ $(yq '.merge_settings.allow_squash_merge' "$repo_file") = "true" ]]; then
    echo "squash"
  elif [[ $(yq '.merge_settings.allow_merge_commit' "$repo_file") = "true" ]]; then
    echo "merge"
  elif [[ $(yq '.merge_settings.allow_rebase_merge' "$repo_file") = "true" ]]; then
    echo "rebase"
  else
    echo "merge"  # Fallback
  fi
}

# Usage
PREFERRED=$(get_preferred_merge_method "hiivmind-pulse-gh")
echo "Preferred merge method: $PREFERRED"

# Use with gh pr merge
gh pr merge $PR_NUM -R "$REPO_FULL" --$PREFERRED
```

### Check if Branch Auto-Deletes

```bash
REPO="hiivmind-pulse-gh"
REPO_FILE=".hiivmind/github/repos/$REPO.yaml"

# Check if branches auto-delete after merge
AUTO_DELETE=$(yq '.merge_settings.delete_branch_on_merge' "$REPO_FILE")

if [[ "$AUTO_DELETE" = "true" ]]; then
  echo "Branches will auto-delete after merge"
  # No need to manually delete branch
else
  echo "Branches will NOT auto-delete after merge"
  # Offer to delete branch manually
fi
```

### Get Repository Labels

```bash
REPO="hiivmind-pulse-gh"
REPO_FILE=".hiivmind/github/repos/$REPO.yaml"

# List all available labels
echo "Available labels for $REPO:"
yq '.labels[] | "\(.name) (\(.color))"' "$REPO_FILE"

# Get default labels (GitHub standard labels)
echo ""
echo "Default labels:"
yq '.labels[] | select(.default == true) | .name' "$REPO_FILE"
```

### Validate Label Before Use

```bash
# Function to check if a label exists
label_exists() {
  local repo=$1
  local label_name=$2
  local repo_file=".hiivmind/github/repos/$repo.yaml"

  if [[ ! -f "$repo_file" ]]; then
    # No repo config - assume label exists
    return 0
  fi

  local exists=$(yq ".labels[] | select(.name == \"$label_name\") | .name" "$repo_file")

  if [[ -n "$exists" ]]; then
    return 0  # Label exists
  else
    return 1  # Label does not exist
  fi
}

# Usage
if label_exists "hiivmind-pulse-gh" "bug"; then
  echo "Label 'bug' exists - safe to apply"
  gh issue edit $ISSUE_NUM --add-label "bug"
else
  echo "Label 'bug' does not exist - create it first"
fi
```

---

## Step 4: Check Project Automations (Phase 4)

**Optional:** If the operation involves adding items to a project or updating fields, check if automations might handle it automatically to avoid duplication.

### Check if Automations are Documented

```bash
PROJECT_NUM=2
AUTOMATIONS_FILE=".hiivmind/github/automations/project-$PROJECT_NUM.yaml"

if [[ -f "$AUTOMATIONS_FILE" ]]; then
  echo "Automations documented for project $PROJECT_NUM"
else
  echo "No automations documented - operations will proceed normally"
fi
```

### Check Auto-Add Status

```bash
# Function to check if a repository has auto-add enabled
has_auto_add() {
  local project_num=$1
  local repo_name=$2
  local automations_file=".hiivmind/github/automations/project-$project_num.yaml"

  if [[ ! -f "$automations_file" ]]; then
    return 1  # No automations file - assume no auto-add
  fi

  local auto_add_enabled=$(yq '.built_in.auto_add.enabled' "$automations_file")

  if [[ "$auto_add_enabled" != "true" ]]; then
    return 1  # Auto-add not enabled
  fi

  # Check if this repo is in the auto-add list
  local repo_in_list=$(yq ".built_in.auto_add.repositories[] | select(. == \"$repo_name\")" "$automations_file")

  if [[ -n "$repo_in_list" ]]; then
    return 0  # Repo has auto-add enabled
  else
    return 1  # Repo not in auto-add list
  fi
}

# Usage
if has_auto_add 2 "hiivmind-pulse-gh"; then
  echo "Project 2 has auto-add enabled for hiivmind-pulse-gh"
  echo "New issues/PRs will be added automatically - no need to add manually"
else
  echo "Project 2 does not have auto-add for hiivmind-pulse-gh"
  echo "Will need to add items manually"
fi
```

### Check for Status Auto-Set Workflows

```bash
# Function to check if status will be auto-set on an event
will_auto_set_status() {
  local project_num=$1
  local trigger_type=$2  # e.g., "item_closed", "item_added"
  local automations_file=".hiivmind/github/automations/project-$project_num.yaml"

  if [[ ! -f "$automations_file" ]]; then
    return 1  # No automations
  fi

  # Check if any workflow matches this trigger and sets Status
  local matching_workflow=$(yq ".workflows[] | select(.trigger.type == \"$trigger_type\") | select(.actions[].field == \"Status\") | .name" "$automations_file")

  if [[ -n "$matching_workflow" ]]; then
    echo "$matching_workflow"
    return 0  # Automation exists
  else
    return 1  # No automation for this trigger
  fi
}

# Usage
WORKFLOW=$(will_auto_set_status 2 "item_closed")
if [[ $? -eq 0 ]]; then
  echo "Workflow '$WORKFLOW' will auto-set Status when item is closed"
  echo "Skipping manual status update to avoid duplication"
else
  echo "No automation for item_closed - will set status manually"
fi
```

### Get Auto-Archive Settings

```bash
PROJECT_NUM=2
AUTOMATIONS_FILE=".hiivmind/github/automations/project-$PROJECT_NUM.yaml"

# Check if auto-archive is enabled
AUTO_ARCHIVE_ENABLED=$(yq '.built_in.auto_archive.enabled' "$AUTOMATIONS_FILE" 2>/dev/null)

if [[ "$AUTO_ARCHIVE_ENABLED" = "true" ]]; then
  STATUS=$(yq '.built_in.auto_archive.conditions.status_value' "$AUTOMATIONS_FILE")
  DELAY=$(yq '.built_in.auto_archive.conditions.delay_days' "$AUTOMATIONS_FILE")

  echo "Auto-archive is enabled:"
  echo "  Trigger: Items with status '$STATUS'"
  echo "  Delay: $DELAY days"
  echo ""
  echo "Items will archive automatically - no need to manually archive"
else
  echo "Auto-archive not enabled - items must be archived manually"
fi
```

### Check for Duplicate Automation

```bash
# Function to check if an operation would duplicate an automation
would_duplicate_automation() {
  local project_num=$1
  local operation_type=$2  # e.g., "add_to_project", "set_status"
  local context=$3         # Additional context (e.g., status value)
  local automations_file=".hiivmind/github/automations/project-$project_num.yaml"

  if [[ ! -f "$automations_file" ]]; then
    return 1  # No automations - no duplication
  fi

  case "$operation_type" in
    "add_to_project")
      # Check if auto-add would handle this
      local repo=$context
      if has_auto_add "$project_num" "$repo"; then
        return 0  # Would duplicate auto-add
      fi
      ;;

    "set_status")
      # Check if any workflow sets this status automatically
      local status_value=$context
      local auto_set=$(yq ".workflows[] | select(.actions[].field == \"Status\") | select(.actions[].value == \"$status_value\")" "$automations_file")
      if [[ -n "$auto_set" ]]; then
        return 0  # Would duplicate automation
      fi
      ;;
  esac

  return 1  # No duplication
}

# Usage
if would_duplicate_automation 2 "add_to_project" "hiivmind-pulse-gh"; then
  echo "WARNING: Auto-add is enabled - this item will be added automatically"
  echo "Skipping manual add to avoid duplication"
else
  echo "No automation for this operation - proceeding"
fi
```

### List Documented Workflows

```bash
PROJECT_NUM=2
AUTOMATIONS_FILE=".hiivmind/github/automations/project-$PROJECT_NUM.yaml"

echo "Documented workflows for project $PROJECT_NUM:"
yq '.workflows[] | "- \(.name): \(.description)"' "$AUTOMATIONS_FILE" 2>/dev/null

echo ""
echo "Built-in automations:"
echo "  Auto-add: $(yq '.built_in.auto_add.enabled' "$AUTOMATIONS_FILE" 2>/dev/null)"
echo "  Auto-archive: $(yq '.built_in.auto_archive.enabled' "$AUTOMATIONS_FILE" 2>/dev/null)"
```

---

## Step 5: Check Cross-Repo Relationships (Phase 5)

**Optional:** If the operation involves multiple repositories or cross-project coordination, check relationships to understand dependencies and project links.

### Check if Relationships are Documented

```bash
RELATIONSHIPS_FILE=".hiivmind/github/relationships.yaml"

if [[ -f "$RELATIONSHIPS_FILE" ]]; then
  echo "Relationships documented"
else
  echo "No relationships documented - operations will proceed without relationship awareness"
fi
```

### Get Linked Repositories for a Project

```bash
# Function to get repositories linked to a project
get_project_repos() {
  local project_num=$1
  local relationships_file=".hiivmind/github/relationships.yaml"

  if [[ ! -f "$relationships_file" ]]; then
    return 1
  fi

  yq ".project_repo_links[$project_num].linked_repos[].name" "$relationships_file" 2>/dev/null
}

# Usage
echo "Repositories linked to project 2:"
get_project_repos 2
```

### Find Projects for a Repository

```bash
# Function to find which projects include a specific repository
get_repo_projects() {
  local repo_name=$1
  local relationships_file=".hiivmind/github/relationships.yaml"

  if [[ ! -f "$relationships_file" ]]; then
    return 1
  fi

  # Find all projects that have this repo in their linked_repos
  yq ".project_repo_links | to_entries | .[] | select(.value.linked_repos[].name == \"$repo_name\") | .key" "$relationships_file" 2>/dev/null
}

# Usage
echo "Projects that include hiivmind-pulse-gh:"
get_repo_projects "hiivmind-pulse-gh"
```

### Get Repository Dependencies

```bash
# Function to get repositories that this repo depends on
get_repo_dependencies() {
  local repo_name=$1
  local relationships_file=".hiivmind/github/relationships.yaml"

  if [[ ! -f "$relationships_file" ]]; then
    return 1
  fi

  yq ".repo_dependencies[\"$repo_name\"].depends_on[]" "$relationships_file" 2>/dev/null
}

# Function to get repositories that depend on this repo
get_repo_dependents() {
  local repo_name=$1
  local relationships_file=".hiivmind/github/relationships.yaml"

  if [[ ! -f "$relationships_file" ]]; then
    return 1
  fi

  yq ".repo_dependencies[\"$repo_name\"].depended_by[]" "$relationships_file" 2>/dev/null
}

# Usage
echo "Dependencies of hiivmind-pulse-gh:"
get_repo_dependencies "hiivmind-pulse-gh"

echo ""
echo "Repositories that depend on hiivmind-pulse-gh:"
get_repo_dependents "hiivmind-pulse-gh"
```

### Cross-Project Milestone Coordination

```bash
# Function to find related projects for milestone coordination
get_coordinated_projects() {
  local project_num=$1
  local relationships_file=".hiivmind/github/relationships.yaml"

  if [[ ! -f "$relationships_file" ]]; then
    return 1
  fi

  # Find projects coordinated with this one
  yq ".cross_project_coordination[] | select(.source_project == $project_num or .target_project == $project_num) | if .source_project == $project_num then .target_project else .source_project end" "$relationships_file" 2>/dev/null
}

# Usage - when creating a milestone, check for coordinated projects
PROJECT_NUM=2
MILESTONE_TITLE="v3.0"

echo "Creating milestone '$MILESTONE_TITLE' in project $PROJECT_NUM"

# Check for coordinated projects
COORDINATED=$(get_coordinated_projects "$PROJECT_NUM")

if [[ -n "$COORDINATED" ]]; then
  echo ""
  echo "NOTE: This project coordinates with project(s): $COORDINATED"
  echo "Consider creating aligned milestones in those projects"
fi
```

### Get All Repositories in Dependency Chain

```bash
# Function to get all repositories in a dependency chain
get_dependency_chain() {
  local repo_name=$1
  local relationships_file=".hiivmind/github/relationships.yaml"
  local visited=()
  local chain=()

  _get_deps_recursive() {
    local current_repo=$1

    # Check if already visited
    for visited_repo in "${visited[@]}"; do
      if [[ "$visited_repo" == "$current_repo" ]]; then
        return
      fi
    done

    visited+=("$current_repo")
    chain+=("$current_repo")

    # Get dependencies
    local deps=$(yq ".repo_dependencies[\"$current_repo\"].depends_on[]" "$relationships_file" 2>/dev/null)

    if [[ -n "$deps" ]]; then
      while read -r dep; do
        _get_deps_recursive "$dep"
      done <<< "$deps"
    fi
  }

  _get_deps_recursive "$repo_name"

  # Print chain
  printf '%s\n' "${chain[@]}"
}

# Usage - when running tests, include dependencies
REPO="hiivmind-pulse-gh-tests"

echo "Dependency chain for $REPO:"
get_dependency_chain "$REPO"

echo ""
echo "Ensure all dependencies are tested before $REPO"
```

### Check Repository Relationship Type

```bash
# Function to get repository relationship type
get_repo_type() {
  local repo_name=$1
  local relationships_file=".hiivmind/github/relationships.yaml"

  if [[ ! -f "$relationships_file" ]]; then
    echo "unknown"
    return
  fi

  yq ".repo_dependencies[\"$repo_name\"].relationship_type" "$relationships_file" 2>/dev/null || echo "unknown"
}

# Usage - determine appropriate operations based on repo type
REPO="hiivmind-pulse-gh-tests"
REPO_TYPE=$(get_repo_type "$REPO")

case "$REPO_TYPE" in
  "test")
    echo "$REPO is a test repository - run tests after dependencies"
    ;;
  "plugin")
    echo "$REPO is a plugin repository - ensure main repo is stable"
    ;;
  "main")
    echo "$REPO is a main repository - changes affect dependent repos"
    ;;
  *)
    echo "$REPO type unknown - proceed with caution"
    ;;
esac
```

---

## Step 6: Load Organization Teams (Phase 6)

**Optional:** If the operation involves reviewer suggestions, permission checks, or team-aware operations, load team membership and permissions.

### Check if Teams are Cached

```bash
TEAMS_FILE=".hiivmind/github/teams.yaml"

if [[ -f "$TEAMS_FILE" ]]; then
  echo "Teams cached"
else
  echo "Teams not cached - consider running refresh with teams section"
fi
```

### Get Team Members

```bash
# Function to get members of a specific team
get_team_members() {
  local team_slug=$1
  local teams_file=".hiivmind/github/teams.yaml"

  if [[ ! -f "$teams_file" ]]; then
    return 1
  fi

  yq ".teams[] | select(.slug == \"$team_slug\") | .members[].login" "$teams_file" 2>/dev/null
}

# Usage
echo "Members of core-maintainers team:"
get_team_members "core-maintainers"
```

### Get Team's Repository Access

```bash
# Function to get repositories a team has access to
get_team_repos() {
  local team_slug=$1
  local permission=${2:-""}  # Optional: filter by permission (ADMIN, WRITE, READ)
  local teams_file=".hiivmind/github/teams.yaml"

  if [[ ! -f "$teams_file" ]]; then
    return 1
  fi

  if [[ -n "$permission" ]]; then
    # Filter by specific permission
    yq ".teams[] | select(.slug == \"$team_slug\") | .repo_permissions | to_entries | .[] | select(.value == \"$permission\") | .key" "$teams_file" 2>/dev/null
  else
    # All repos regardless of permission
    yq ".teams[] | select(.slug == \"$team_slug\") | .repo_permissions | keys[]" "$teams_file" 2>/dev/null
  fi
}

# Usage
echo "Repositories core-maintainers has admin access to:"
get_team_repos "core-maintainers" "ADMIN"

echo ""
echo "All repositories core-maintainers has access to:"
get_team_repos "core-maintainers"
```

### Get Teams with Repository Access

```bash
# Function to get teams with access to a repository
get_repo_teams() {
  local repo_name=$1
  local permission=${2:-""}  # Optional: filter by permission (admin, write, read)
  local teams_file=".hiivmind/github/teams.yaml"

  if [[ ! -f "$teams_file" ]]; then
    return 1
  fi

  if [[ -n "$permission" ]]; then
    # Get teams with specific permission level
    yq ".repo_team_access[\"$repo_name\"].$permission[]" "$teams_file" 2>/dev/null
  else
    # Get all teams with any access
    {
      yq ".repo_team_access[\"$repo_name\"].admin[]" "$teams_file" 2>/dev/null
      yq ".repo_team_access[\"$repo_name\"].write[]" "$teams_file" 2>/dev/null
      yq ".repo_team_access[\"$repo_name\"].read[]" "$teams_file" 2>/dev/null
    } | sort -u
  fi
}

# Usage
echo "Teams with write access to hiivmind-pulse-gh:"
get_repo_teams "hiivmind-pulse-gh" "write"

echo ""
echo "All teams with access to hiivmind-pulse-gh:"
get_repo_teams "hiivmind-pulse-gh"
```

### Get Repository Writers (for Reviewer Suggestions)

```bash
# Function to get all users who can write to a repository
get_repo_writers() {
  local repo_name=$1
  local teams_file=".hiivmind/github/teams.yaml"

  if [[ ! -f "$teams_file" ]]; then
    return 1
  fi

  local writers=()

  # Get teams with admin or write access
  local admin_teams=$(yq ".repo_team_access[\"$repo_name\"].admin[]" "$teams_file" 2>/dev/null)
  local write_teams=$(yq ".repo_team_access[\"$repo_name\"].write[]" "$teams_file" 2>/dev/null)

  # Combine teams
  local all_teams=$(echo -e "$admin_teams\n$write_teams" | sort -u)

  # Get members from each team
  while read -r team_slug; do
    if [[ -n "$team_slug" ]]; then
      yq ".teams[] | select(.slug == \"$team_slug\") | .members[].login" "$teams_file" 2>/dev/null
    fi
  done <<< "$all_teams" | sort -u
}

# Usage - suggest reviewers from team members with write access
REPO="hiivmind-pulse-gh"
echo "Potential reviewers for $REPO (users with write+ access):"
get_repo_writers "$REPO"

# Use in PR creation
REVIEWERS=$(get_repo_writers "$REPO" | head -3 | tr '\n' ',' | sed 's/,$//')
echo ""
echo "Suggested reviewers: $REVIEWERS"
# gh pr create ... --reviewer "$REVIEWERS"
```

### Check Team Membership

```bash
# Function to check if a user is a member of a team
is_team_member() {
  local team_slug=$1
  local user_login=$2
  local teams_file=".hiivmind/github/teams.yaml"

  if [[ ! -f "$teams_file" ]]; then
    return 1
  fi

  local member=$(yq ".teams[] | select(.slug == \"$team_slug\") | .members[] | select(.login == \"$user_login\") | .login" "$teams_file" 2>/dev/null)

  if [[ -n "$member" ]]; then
    return 0  # User is a team member
  else
    return 1  # User is not a team member
  fi
}

# Usage
if is_team_member "core-maintainers" "alice"; then
  echo "alice is a core maintainer - assign critical issues"
else
  echo "alice is not a core maintainer - assign routine issues"
fi
```

### Get Team Maintainers

```bash
# Function to get team maintainers (users who can manage the team)
get_team_maintainers() {
  local team_slug=$1
  local teams_file=".hiivmind/github/teams.yaml"

  if [[ ! -f "$teams_file" ]]; then
    return 1
  fi

  yq ".teams[] | select(.slug == \"$team_slug\") | .members[] | select(.role == \"MAINTAINER\") | .login" "$teams_file" 2>/dev/null
}

# Usage - escalate to team maintainers
TEAM="core-maintainers"
echo "Team maintainers who can help with $TEAM team issues:"
get_team_maintainers "$TEAM"
```

### List All Teams

```bash
TEAMS_FILE=".hiivmind/github/teams.yaml"

echo "Organization teams:"
yq '.teams[] | "\(.slug) - \(.name) (\(.privacy))"' "$TEAMS_FILE" 2>/dev/null
```

### Team-Aware CODEOWNERS Integration

```bash
# When suggesting reviewers, prefer team members over individual users
REPO="hiivmind-pulse-gh"

# Get writers who can review
POTENTIAL_REVIEWERS=$(get_repo_writers "$REPO")

# Filter by team membership (prefer maintainers)
echo "Suggested reviewers (maintainers first):"
while read -r user; do
  if is_team_member "core-maintainers" "$user"; then
    echo "  $user (core maintainer) ⭐"
  else
    echo "  $user"
  fi
done <<< "$POTENTIAL_REVIEWERS"
```

---

## Step 7: Determine API Type

Use this routing table to determine GraphQL vs REST:

### API Routing Table

| Domain | Read | Create | Update | Delete | Notes |
|--------|------|--------|--------|--------|-------|
| **issues** | GraphQL | GraphQL | GraphQL | GraphQL | Full GraphQL support |
| **pull_requests** | GraphQL | GraphQL | GraphQL | GraphQL | Full GraphQL support |
| **milestones** | GraphQL | REST | REST | REST | CRUD is REST-only |
| **labels** | GraphQL | REST | REST | REST | CRUD is REST-only |
| **projects** | GraphQL | GraphQL | GraphQL | GraphQL | Except views (UI only) |
| **branch_protection** | REST | REST | REST | REST | GraphQL is read-only |
| **rulesets** | Both | REST | REST | REST | GraphQL for queries |
| **actions** | REST | REST | REST | REST | No GraphQL support |
| **secrets** | REST | REST | REST | REST | No GraphQL support |
| **variables** | REST | REST | REST | REST | No GraphQL support |
| **releases** | Both | REST | REST | REST | GraphQL for queries |

**Reference:** `${CLAUDE_PLUGIN_ROOT}/reference/api-routing.md` for detailed routing decisions and search keywords.

---

## Step 8: Find Workflow Example

Check for relevant workflow pattern:

| Domain + Operation | Workflow File |
|--------------------|---------------|
| issues + create + link to project | `reference/workflows/issue-to-project.md` |
| milestones + any | `reference/workflows/manage-milestones.md` |
| branch_protection + any | `reference/workflows/setup-branch-protection.md` |
| rulesets + any | `reference/workflows/setup-branch-protection.md` |
| projects + update | `reference/workflows/project-status-update.md` |
| any + bulk | `reference/workflows/bulk-operations.md` |

```bash
# List available workflows
ls "${CLAUDE_PLUGIN_ROOT}/reference/workflows/"
```

**Read the relevant workflow** for step-by-step patterns before executing.

---

## Step 9: Search Corpus for Syntax

Use keywords to find exact syntax in the corpus.

### Corpus Location

```
${CLAUDE_PLUGIN_ROOT}/.claude-plugin/skills/hiivmind-corpus-github/data/index.md
```

### GraphQL Schema Search

For mutations and types (70k+ line schema):

```bash
SCHEMA="${CLAUDE_PLUGIN_ROOT}/.claude-plugin/skills/hiivmind-corpus-github/data/uploads/graphql-schema/schema.docs.graphql"

# Find mutation signature
grep -n "{mutationName}" "$SCHEMA" -B 5 -A 30

# Find type definition
grep -n "^type {TypeName} " "$SCHEMA" -A 50

# Find input type
grep -n "^input {InputName} " "$SCHEMA" -A 30

# Find enum values
grep -n "^enum {EnumName} " "$SCHEMA" -A 20
```

### Keyword Reference

| Domain | Search Keywords |
|--------|-----------------|
| issues | `createIssue`, `updateIssue`, `closeIssue`, `addComment`, `subjectId` |
| pull_requests | `createPullRequest`, `mergePullRequest`, `requestReviews`, `baseRefName` |
| milestones | `milestones`, `due_on`, `milestoneId`, `updateIssue` |
| labels | `addLabelsToLabelable`, `removeLabelsFromLabelable`, `labelIds` |
| projects | `addProjectV2ItemById`, `updateProjectV2ItemFieldValue`, `archiveProjectV2Item`, `createProjectV2StatusUpdate` |
| branch_protection | `required_status_checks`, `enforce_admins`, `required_pull_request_reviews` |
| rulesets | `rulesets`, `enforcement`, `conditions`, `ref_name` |
| actions | `workflows`, `runs`, `dispatches`, `cancel`, `rerun` |
| secrets | `secrets`, `encrypted_value`, `public-key`, `key_id` |
| variables | `variables`, `visibility`, `POST`, `PATCH` |
| releases | `releases`, `tag_name`, `assets`, `generate-notes` |

---

## Step 10: Execute Operation

### Domain: Issues

**Create issue:**
```bash
# Simple - gh CLI
gh issue create -R "$REPO_FULL" \
  --title "$TITLE" \
  --body "$BODY" \
  --label "$LABELS"

# With project assignment
gh issue create -R "$REPO_FULL" \
  --title "$TITLE" \
  --body "$BODY" \
  --project "$DEFAULT_PROJECT"
```

**Update issue:**
```bash
gh issue edit $ISSUE_NUM -R "$REPO_FULL" \
  --title "$NEW_TITLE" \
  --body "$NEW_BODY"

# Add labels
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --add-label "bug,priority"

# Set milestone
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --milestone "$MILESTONE_NAME"
```

**Close issue:**
```bash
gh issue close $ISSUE_NUM -R "$REPO_FULL" --reason "completed"
```

**List issues:**
```bash
gh issue list -R "$REPO_FULL" --state open --limit 20
```

---

### Domain: Pull Requests

**Create PR:**
```bash
gh pr create -R "$REPO_FULL" \
  --title "$TITLE" \
  --body "$BODY" \
  --base main \
  --head "$BRANCH"
```

**Merge PR:**
```bash
gh pr merge $PR_NUM -R "$REPO_FULL" --squash --delete-branch
```

**Request review:**
```bash
gh pr edit $PR_NUM -R "$REPO_FULL" --add-reviewer "$REVIEWER"
```

**List PRs:**
```bash
gh pr list -R "$REPO_FULL" --state open
```

---

### Domain: Milestones

**Create milestone (REST):**
```bash
# Corpus: REST POST /repos/{owner}/{repo}/milestones
# Keywords: milestones, due_on, description
gh api "/repos/$REPO_FULL/milestones" -f title="$MILESTONE_TITLE" -f description="$DESCRIPTION" -f due_on="$DUE_DATE"  # ISO 8601
```

**Update milestone (REST):**
```bash
# Corpus: REST PATCH /repos/{owner}/{repo}/milestones/{number}
gh api "/repos/$REPO_FULL/milestones/$MILESTONE_NUM" -X PATCH -f state="closed"
```

**Delete milestone (REST):**
```bash
# Corpus: REST DELETE /repos/{owner}/{repo}/milestones/{number}
gh api "/repos/$REPO_FULL/milestones/$MILESTONE_NUM" -X DELETE
```

**List milestones (GraphQL):**
```bash
# Corpus keywords: milestones, repository, dueOn, progressPercentage
gh api graphql -f query='query($owner: String!, $repo: String!) { repository(owner: $owner, name: $repo) { milestones(first: 20, states: [OPEN]) { nodes { number title dueOn progressPercentage } } } }' \
  -f owner="$OWNER" -f repo="$REPO"
```

**Assign milestone to issue:**
```bash
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --milestone "$MILESTONE_TITLE"
```

---

### Domain: Labels

**Create label (REST):**
```bash
# Corpus: REST POST /repos/{owner}/{repo}/labels
# Keywords: labels, color, description
gh api "/repos/$REPO_FULL/labels" -f name="$LABEL_NAME" -f color="$HEX_COLOR" -f description="$DESCRIPTION"
```

**Add/remove label from issue:**
```bash
# Using gh CLI (recommended for label operations)
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --add-label "$LABEL_NAME"
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --remove-label "$LABEL_NAME"

# Or GraphQL: addLabelsToLabelable, removeLabelsFromLabelable mutations
# Corpus keywords: addLabelsToLabelable, removeLabelsFromLabelable, labelIds
```

---

### Domain: Projects v2

**Get project IDs from config:**
```bash
PROJECT_NUM=$DEFAULT_PROJECT
PROJECT_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .id" "$CONFIG")
```

**Add item to project:**
```bash
# Simple - gh CLI (recommended)
gh project item-add $PROJECT_NUM --owner "$OWNER" --url "$ITEM_URL"

# Or GraphQL mutation
# Corpus keywords: addProjectV2ItemById, projectId, contentId
# Reference: hiivmind-corpus-github → "add item to project"
ITEM_ID="..."  # Issue or PR node ID
gh api graphql -f query='mutation($projectId: ID!, $contentId: ID!) { addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) { item { id } } }' \
  -f projectId="$PROJECT_ID" -f contentId="$ITEM_ID"
```

**Update project field:**
```bash
# Get field and option IDs from config
FIELD_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.id" "$CONFIG")
OPTION_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options.\"In progress\"" "$CONFIG")

# Update field value
# Corpus keywords: updateProjectV2ItemFieldValue, singleSelectOptionId, fieldId
# Reference: hiivmind-corpus-github → "update project field value"
# Note: value type varies by field (singleSelectOptionId, text, number, date, iteration)
gh api graphql -f query='mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) { updateProjectV2ItemFieldValue(input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: {singleSelectOptionId: $optionId}}) { projectV2Item { id } } }' \
  -f projectId="$PROJECT_ID" -f itemId="$ITEM_ID" -f fieldId="$FIELD_ID" -f optionId="$OPTION_ID"
```

**Archive project item:**
```bash
# Corpus keywords: archiveProjectV2Item, projectId, itemId
# Reference: hiivmind-corpus-github → "archive project item"
gh api graphql -f query='mutation($projectId: ID!, $itemId: ID!) { archiveProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) { item { id } } }' \
  -f projectId="$PROJECT_ID" -f itemId="$ITEM_ID"
```

---

### Domain: Branch Protection

**Set branch protection (REST):**
```bash
gh api "/repos/$REPO_FULL/branches/$BRANCH/protection" \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "restrictions": null
}
EOF
```

**Get branch protection:**
```bash
gh api "/repos/$REPO_FULL/branches/$BRANCH/protection"
```

**Delete branch protection:**
```bash
gh api "/repos/$REPO_FULL/branches/$BRANCH/protection" -X DELETE
```

---

### Domain: Rulesets

**Create ruleset (REST):**
```bash
gh api "/repos/$REPO_FULL/rulesets" \
  -X POST \
  --input - <<EOF
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {"type": "pull_request", "parameters": {"required_approving_review_count": 1}}
  ]
}
EOF
```

**List rulesets:**
```bash
gh api "/repos/$REPO_FULL/rulesets"
```

---

### Domain: Actions

**Trigger workflow:**
```bash
gh workflow run "$WORKFLOW_FILE" -R "$REPO_FULL" --ref main -f input1=value1
```

**List workflow runs:**
```bash
gh run list -R "$REPO_FULL" --workflow="$WORKFLOW_FILE" --limit 10
```

**View run details:**
```bash
gh run view $RUN_ID -R "$REPO_FULL"
```

**Cancel run:**
```bash
gh run cancel $RUN_ID -R "$REPO_FULL"
```

**Re-run failed jobs:**
```bash
gh run rerun $RUN_ID -R "$REPO_FULL" --failed
```

---

### Domain: Secrets

**Set secret (gh handles encryption):**
```bash
gh secret set $SECRET_NAME -R "$REPO_FULL" --body "$SECRET_VALUE"

# Or from file
gh secret set $SECRET_NAME -R "$REPO_FULL" < secret.txt
```

**List secrets:**
```bash
gh secret list -R "$REPO_FULL"
```

**Delete secret:**
```bash
gh secret delete $SECRET_NAME -R "$REPO_FULL"
```

---

### Domain: Variables

**Set variable:**
```bash
gh variable set $VAR_NAME -R "$REPO_FULL" --body "$VAR_VALUE"
```

**List variables:**
```bash
gh variable list -R "$REPO_FULL"
```

**Delete variable:**
```bash
gh variable delete $VAR_NAME -R "$REPO_FULL"
```

---

### Domain: Releases

**Create release:**
```bash
gh release create "$TAG" -R "$REPO_FULL" \
  --title "$RELEASE_TITLE" \
  --notes "$RELEASE_NOTES" \
  ./dist/*  # Optional: attach assets
```

**Create with auto-generated notes:**
```bash
gh release create "$TAG" -R "$REPO_FULL" \
  --title "$RELEASE_TITLE" \
  --generate-notes
```

**List releases:**
```bash
gh release list -R "$REPO_FULL"
```

**Download release assets:**
```bash
gh release download "$TAG" -R "$REPO_FULL" --pattern "*.tar.gz"
```

---

## Step 11: Report Result

After execution:

1. **Success**: Report what was done, provide relevant URLs/IDs
2. **Partial**: Report what succeeded and what failed
3. **Failure**: Report error, suggest remediation

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Resource not accessible" | Missing permissions | Check `gh auth status`, may need more scopes |
| "Not Found" | Entity doesn't exist | Verify target exists (issue number, milestone name) |
| "Validation failed" | Invalid input | Check format (dates as ISO 8601, valid JSON) |
| "Project not found" | Wrong project number | Run `yq '.projects.catalog[].number' "$CONFIG"` |
| "Field not found" | Stale config | Run `hiivmind-pulse-gh-refresh` |

---

## Workflow References

For complex multi-step operations, read the relevant workflow file:

| Workflow | Path | Use For |
|----------|------|---------|
| Issue to Project | `reference/workflows/issue-to-project.md` | Create + add to project + set status |
| Manage Milestones | `reference/workflows/manage-milestones.md` | Milestone CRUD + assignment |
| Branch Protection | `reference/workflows/setup-branch-protection.md` | Protection + rulesets |
| Project Status | `reference/workflows/project-status-update.md` | Update fields + status |
| Bulk Operations | `reference/workflows/bulk-operations.md` | Batch with rate limiting |

---

## Notes

- **Prefer gh CLI** over raw API calls when available (simpler, handles auth)
- **Use GraphQL** for reads with complex filtering or nested data
- **Use REST** for mutations where GraphQL doesn't support them
- **Config-first**: Always load IDs from config, don't hardcode
- **Corpus for syntax**: Search keywords when unsure of exact API syntax
- **Workflow patterns**: Reference workflow files for multi-step operations
