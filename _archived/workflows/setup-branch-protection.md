# Workflow: Setup Branch Protection

> **Goal:** Configure branch protection rules and repository rulesets.
> **API:** REST for both (GraphQL is read-only for protection)

## Prerequisites

- `hiivmind-pulse-gh-init` has been run
- `.hiivmind/github/config.yaml` exists
- Admin access to the repository

## Load Context

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
REPO="hiivmind-pulse-gh"
BRANCH="main"
```

---

## Option 1: Legacy Branch Protection

Classic branch protection rules applied to a specific branch.

### Enable Basic Protection

```bash
gh api "/repos/$OWNER/$REPO/branches/$BRANCH/protection" \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":[]}' \
  -f enforce_admins=true \
  -F required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  -f restrictions=null
```

### Full Protection with All Options

```bash
# Corpus keywords: branch protection, required_status_checks, required_pull_request_reviews
# Reference: hiivmind-corpus-github → "branch protection rules"

gh api "/repos/$OWNER/$REPO/branches/$BRANCH/protection" \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci/build", "ci/test"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2,
    "require_last_push_approval": true
  },
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "restrictions": null
}
EOF
```

### Check Current Protection

```bash
gh api "/repos/$OWNER/$REPO/branches/$BRANCH/protection" \
  --jq '{
    status_checks: .required_status_checks.contexts,
    pr_reviews: .required_pull_request_reviews.required_approving_review_count,
    enforce_admins: .enforce_admins.enabled
  }'
```

### Remove Protection

```bash
gh api "/repos/$OWNER/$REPO/branches/$BRANCH/protection" -X DELETE
```

---

## Option 2: Repository Rulesets (Modern)

Rulesets are more flexible - support patterns, multiple targets, and org-level rules.

### Create Basic Ruleset

```bash
# Corpus keywords: rulesets, enforcement, conditions, ref_name, rules
# Reference: hiivmind-corpus-github → "repository rulesets"

gh api "/repos/$OWNER/$REPO/rulesets" \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --input - <<'EOF'
{
  "name": "main-branch-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
    {"type": "required_linear_history"}
  ]
}
EOF
```

### Create Comprehensive Ruleset

```bash
# Corpus keywords: rulesets, pull_request, required_status_checks, required_linear_history
# Reference: hiivmind-corpus-github → "ruleset rule types"

gh api "/repos/$OWNER/$REPO/rulesets" \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --input - <<'EOF'
{
  "name": "protected-branches",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main", "refs/heads/release/*"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 2,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          {"context": "ci/build"},
          {"context": "ci/test"}
        ]
      }
    },
    {"type": "required_linear_history"},
    {"type": "non_fast_forward"},
    {"type": "deletion"}
  ]
}
EOF
```

### Create Branch Naming Ruleset

Enforce naming conventions:

```bash
gh api "/repos/$OWNER/$REPO/rulesets" \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --input - <<'EOF'
{
  "name": "branch-naming-convention",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~ALL"],
      "exclude": ["refs/heads/main", "refs/heads/develop"]
    }
  },
  "rules": [
    {
      "type": "branch_name_pattern",
      "parameters": {
        "name": "Must follow naming convention",
        "negate": false,
        "operator": "regex",
        "pattern": "^(feature|bugfix|hotfix|release)/[a-z0-9-]+$"
      }
    }
  ]
}
EOF
```

### List Rulesets

```bash
gh api "/repos/$OWNER/$REPO/rulesets" \
  --jq '.[] | {id, name, enforcement, target}'
```

### Update Ruleset

```bash
RULESET_ID=123456

gh api "/repos/$OWNER/$REPO/rulesets/$RULESET_ID" \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  --input - <<'EOF'
{
  "name": "main-branch-protection",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main", "refs/heads/develop"],
      "exclude": []
    }
  },
  "rules": [
    {"type": "pull_request", "parameters": {"required_approving_review_count": 2}}
  ]
}
EOF
```

### Delete Ruleset

```bash
RULESET_ID=123456
gh api "/repos/$OWNER/$REPO/rulesets/$RULESET_ID" -X DELETE
```

### Check Rules Applied to Branch

```bash
gh api "/repos/$OWNER/$REPO/rules/branches/$BRANCH" \
  --jq '.[] | {type, parameters}'
```

---

## Choosing Between Protection and Rulesets

| Feature | Branch Protection | Rulesets |
|---------|-------------------|----------|
| Pattern matching | Single branch | Glob patterns |
| Multiple targets | No | Yes |
| Org-level rules | No | Yes |
| Bypass permissions | Limited | Granular |
| API complexity | Simpler | More flexible |

**Recommendation:** Use rulesets for new setups. Branch protection is legacy but still supported.

---

## Available Rule Types (Rulesets)

| Type | Description |
|------|-------------|
| `creation` | Block branch/tag creation |
| `deletion` | Block branch/tag deletion |
| `update` | Block branch/tag updates |
| `non_fast_forward` | Block force pushes |
| `pull_request` | Require PR with reviews |
| `required_status_checks` | Require CI checks to pass |
| `required_linear_history` | No merge commits |
| `branch_name_pattern` | Enforce naming conventions |
| `tag_name_pattern` | Enforce tag naming |
| `commit_message_pattern` | Enforce commit message format |
| `commit_author_email_pattern` | Enforce author email format |

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Resource not accessible" | Not repo admin | Check permissions |
| "Validation failed" | Invalid rule configuration | Check rule parameters |
| "Branch not found" | Branch doesn't exist | Create branch first |
| "Conflicts with existing ruleset" | Overlapping conditions | Adjust conditions or merge rulesets |

---

## Corpus Lookup

Search the corpus index using these keywords:

| Need | Keywords |
|------|----------|
| Branch protection REST | `branch protection`, `required_status_checks`, `enforce_admins` |
| PR review requirements | `required_pull_request_reviews`, `approving_review_count` |
| Rulesets REST | `rulesets`, `ruleset`, `enforcement`, `conditions` |
| Available rules | `rules`, `creation`, `deletion`, `non_fast_forward` |
| Branch naming | `branch_name_pattern`, `regex`, `operator` |

Start with `reference/api-routing.md` → "Branch Protection" or "Rulesets" section for routing decisions.
