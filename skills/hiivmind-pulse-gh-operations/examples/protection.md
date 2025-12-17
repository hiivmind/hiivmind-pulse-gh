# Branch Protection Operations Examples

Examples of branch protection and ruleset operations using hiivmind-pulse-gh.

**Note:** All protection operations use REST API.

## Set Branch Protection

**Natural language:**
```
/hiivmind-pulse-gh protect branch main
/hiivmind-pulse-gh add protection to main requiring 2 reviews
/hiivmind-pulse-gh set branch protection on main
```

**REST endpoint:**
```
PUT /repos/{owner}/{repo}/branches/{branch}/protection
```

**Request body (comprehensive):**
```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci/build", "ci/test"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

**CLI equivalent:**
```bash
gh api repos/{owner}/{repo}/branches/main/protection -X PUT \
  -F required_status_checks='{"strict":true,"contexts":["ci/build"]}' \
  -F enforce_admins=true \
  -F required_pull_request_reviews='{"required_approving_review_count":2}'
```

---

## Require Status Checks

**Natural language:**
```
/hiivmind-pulse-gh require CI checks on main
/hiivmind-pulse-gh add required status check "build" to main
/hiivmind-pulse-gh require passing checks before merge on main
```

**REST endpoint:**
```
PUT /repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks
```

**Request body:**
```json
{
  "strict": true,
  "contexts": ["ci/build", "ci/test", "ci/lint"]
}
```

---

## Require Pull Request Reviews

**Natural language:**
```
/hiivmind-pulse-gh require 2 reviews on main
/hiivmind-pulse-gh enable required reviews for main
/hiivmind-pulse-gh require code owner review on main
```

**REST endpoint:**
```
PUT /repos/{owner}/{repo}/branches/{branch}/protection/required_pull_request_reviews
```

**Request body:**
```json
{
  "dismiss_stale_reviews": true,
  "require_code_owner_reviews": true,
  "required_approving_review_count": 2,
  "require_last_push_approval": true
}
```

---

## View Branch Protection

**Natural language:**
```
/hiivmind-pulse-gh show protection on main
/hiivmind-pulse-gh view branch protection rules
/hiivmind-pulse-gh check what protection main has
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/branches/{branch}/protection
```

**CLI equivalent:**
```bash
gh api repos/{owner}/{repo}/branches/main/protection
```

---

## Remove Branch Protection

**Natural language:**
```
/hiivmind-pulse-gh remove protection from main
/hiivmind-pulse-gh delete branch protection on develop
```

**REST endpoint:**
```
DELETE /repos/{owner}/{repo}/branches/{branch}/protection
```

---

## Create Ruleset

**Natural language:**
```
/hiivmind-pulse-gh create ruleset for release branches
/hiivmind-pulse-gh add ruleset requiring linear history
```

**REST endpoint:**
```
POST /repos/{owner}/{repo}/rulesets
```

**Request body:**
```json
{
  "name": "Release Branch Rules",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/release/*"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "required_linear_history" },
    { "type": "pull_request", "parameters": { "required_approving_review_count": 2 } },
    { "type": "required_status_checks", "parameters": { "required_status_checks": [{ "context": "ci" }] } }
  ]
}
```

---

## List Rulesets

**Natural language:**
```
/hiivmind-pulse-gh list rulesets
/hiivmind-pulse-gh show repository rulesets
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/rulesets
```

---

## Update Ruleset

**Natural language:**
```
/hiivmind-pulse-gh update ruleset 123 to require 3 reviews
/hiivmind-pulse-gh modify ruleset "Release Rules"
```

**REST endpoint:**
```
PUT /repos/{owner}/{repo}/rulesets/{ruleset_id}
```

---

## Delete Ruleset

**Natural language:**
```
/hiivmind-pulse-gh delete ruleset 123
/hiivmind-pulse-gh remove ruleset "Old Rules"
```

**REST endpoint:**
```
DELETE /repos/{owner}/{repo}/rulesets/{ruleset_id}
```

---

## Common Protection Patterns

### Minimal Protection (Solo Projects)
```json
{
  "required_status_checks": {
    "strict": false,
    "contexts": ["ci"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
```

### Team Protection (Small Teams)
```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci/build", "ci/test"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null
}
```

### Enterprise Protection (Large Teams)
```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci/build", "ci/test", "ci/security", "ci/lint"]
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
  "restrictions": {
    "users": [],
    "teams": ["release-managers"],
    "apps": []
  }
}
```
