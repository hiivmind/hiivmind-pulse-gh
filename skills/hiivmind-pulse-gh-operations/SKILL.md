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

## Step 2: Determine API Type

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

## Step 3: Find Workflow Example

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

## Step 4: Search Corpus for Syntax

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

## Step 5: Execute Operation

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

## Step 6: Report Result

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
