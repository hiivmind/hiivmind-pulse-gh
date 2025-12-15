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

## Step 4: Determine API Type

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

## Step 5: Find Workflow Example

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

## Step 6: Search Corpus for Syntax

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

## Step 7: Execute Operation

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
gh api "/repos/$REPO_FULL/milestones" \
  -f title="$MILESTONE_TITLE" \
  -f description="$DESCRIPTION" \
  -f due_on="$DUE_DATE"  # ISO 8601: YYYY-MM-DDTHH:MM:SSZ
```

**Update milestone (REST):**
```bash
gh api "/repos/$REPO_FULL/milestones/$MILESTONE_NUM" \
  -X PATCH \
  -f state="closed"
```

**Delete milestone (REST):**
```bash
gh api "/repos/$REPO_FULL/milestones/$MILESTONE_NUM" -X DELETE
```

**List milestones (GraphQL):**
```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!) {
    repository(owner: $owner, name: $repo) {
      milestones(first: 20, states: [OPEN]) {
        nodes { number title dueOn progressPercentage }
      }
    }
  }
' -f owner="$OWNER" -f repo="$REPO"
```

**Assign milestone to issue:**
```bash
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --milestone "$MILESTONE_TITLE"
```

---

### Domain: Labels

**Create label (REST):**
```bash
gh api "/repos/$REPO_FULL/labels" \
  -f name="$LABEL_NAME" \
  -f color="$HEX_COLOR" \
  -f description="$DESCRIPTION"
```

**Add label to issue (GraphQL or CLI):**
```bash
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --add-label "$LABEL_NAME"
```

**Remove label from issue:**
```bash
gh issue edit $ISSUE_NUM -R "$REPO_FULL" --remove-label "$LABEL_NAME"
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
# Simple - gh CLI
gh project item-add $PROJECT_NUM --owner "$OWNER" --url "$ITEM_URL"

# Or GraphQL mutation
ITEM_ID="..."  # Issue or PR node ID
gh api graphql -f query='
  mutation($projectId: ID!, $contentId: ID!) {
    addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
      item { id }
    }
  }
' -f projectId="$PROJECT_ID" -f contentId="$ITEM_ID"
```

**Update project field:**
```bash
# Get field and option IDs from config
FIELD_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.id" "$CONFIG")
OPTION_ID=$(yq ".projects.catalog[] | select(.number == $PROJECT_NUM) | .fields.Status.options.\"In progress\"" "$CONFIG")

# Update field value
gh api graphql -f query='
  mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $projectId,
      itemId: $itemId,
      fieldId: $fieldId,
      value: {singleSelectOptionId: $optionId}
    }) {
      projectV2Item { id }
    }
  }
' -f projectId="$PROJECT_ID" -f itemId="$ITEM_ID" -f fieldId="$FIELD_ID" -f optionId="$OPTION_ID"
```

**Archive project item:**
```bash
gh api graphql -f query='
  mutation($projectId: ID!, $itemId: ID!) {
    archiveProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
      item { id }
    }
  }
' -f projectId="$PROJECT_ID" -f itemId="$ITEM_ID"
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

## Step 8: Report Result

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
