# Healthcheck Evaluation Pattern

> **Purpose:** Step-by-step evaluation logic for each healthcheck. Cache-first strategy with local vs remote branching.

---

## Evaluation Strategy

For each check, determine if the target repo is the **current repo** (local) or a **remote repo** (in catalog but not cwd):

| Scenario | Data Source | Approach |
|----------|-------------|----------|
| Current repo | Filesystem first, then cache, then API | Fastest — no API calls for file checks |
| Remote repo | Cache first, then API | Cannot check filesystem for remote repos |

### Detecting Current Repo

```bash
CURRENT_REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")
```

If `CURRENT_REPO` matches the repo being evaluated → use local strategy.

---

## Pre-Evaluation Setup

Before running individual checks, load shared context:

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")

# Determine repo scope
# If specific repo passed: REPOS=("repo-name")
# If all: REPOS=($(yq '.repositories[].name' "$CONFIG"))
```

---

## Check Evaluations

### `branch_protection`

**Local path (cache):**

```bash
REPO_CACHE=".hiivmind/github/repos/${REPO_NAME}.yaml"
if [[ -f "$REPO_CACHE" ]]; then
  DEFAULT_BRANCH=$(yq '.repository.default_branch' "$REPO_CACHE")
  HAS_PROTECTION=$(yq ".branch_protection[\"${DEFAULT_BRANCH}\"].enabled // false" "$REPO_CACHE")
  HAS_RULESETS=$(yq '.rulesets | length > 0' "$REPO_CACHE")
  ENFORCE_ADMINS=$(yq ".branch_protection[\"${DEFAULT_BRANCH}\"].enforce_admins // false" "$REPO_CACHE")
  REQUIRED_REVIEWS=$(yq ".branch_protection[\"${DEFAULT_BRANCH}\"].required_pull_request_reviews.required_approving_review_count // 0" "$REPO_CACHE")
fi
```

**API fallback:**

```bash
DEFAULT_BRANCH=$(gh api "/repos/${OWNER}/${REPO_NAME}" --jq '.default_branch')
PROTECTION=$(gh api "/repos/${OWNER}/${REPO_NAME}/branches/${DEFAULT_BRANCH}/protection" 2>/dev/null)
# 404 = no protection → fail
# 200 = has protection → check details for pass vs warn
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| Protection enabled with required reviews >= 1 and enforce_admins | pass |
| Protection enabled but missing enforce_admins or no required reviews | warn |
| Active rulesets exist (even without legacy protection) | pass |
| No protection and no rulesets | fail |

**Detail string:** `"{branch}: {review_count} required review(s), admins enforced: {yes/no}"` or `"No protection on {branch}"`

---

### `project_linkage`

**Local path (cache):**

```bash
# Check relationships.yaml
RELATIONSHIPS=".hiivmind/github/relationships.yaml"
if [[ -f "$RELATIONSHIPS" ]]; then
  LINKED=$(yq ".project_repo_links | to_entries | .[].value.linked_repos[] | select(.name == \"${REPO_NAME}\") | .name" "$RELATIONSHIPS" 2>/dev/null)
fi
```

**API fallback (GraphQL):**

```bash
gh api graphql -f query='
  query($owner: String!, $name: String!) {
    repository(owner: $owner, name: $name) {
      projectsV2(first: 1) { totalCount }
    }
  }
' -f owner="$OWNER" -f name="$REPO_NAME" --jq '.data.repository.projectsV2.totalCount'
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| Repo linked to >= 1 project | pass |
| No project linkage found | fail |

**Detail string:** `"Linked to {N} project(s)"` or `"Not linked to any project"`

---

### `issue_triage`

**Local path (cache):**

```bash
REPO_CACHE=".hiivmind/github/repos/${REPO_NAME}.yaml"
if [[ -f "$REPO_CACHE" ]]; then
  LABELS=$(yq '.labels[].name' "$REPO_CACHE" | tr '[:upper:]' '[:lower:]')
fi
```

**API fallback:**

```bash
LABELS=$(gh api "/repos/${OWNER}/${REPO_NAME}/labels" --paginate --jq '.[].name' | tr '[:upper:]' '[:lower:]')
```

**Evaluation:**

```bash
# Bug-type labels (case-insensitive)
HAS_BUG=$(echo "$LABELS" | grep -iE '^(bug|defect|error|incident)$' | head -1)

# Priority labels (case-insensitive, partial match)
HAS_PRIORITY=$(echo "$LABELS" | grep -iE '(priority|^p[0-4]$|critical|urgent)' | head -1)
```

| Condition | Status |
|-----------|--------|
| Both bug-type and priority labels exist | pass |
| One category exists but not the other | warn |
| Neither category exists | fail |

**Detail string:** `"Bug: {label}, Priority: {label}"` or `"Missing: {category}"`

---

### `ci_cd`

**Local path (filesystem — current repo only):**

```bash
if [[ "$REPO_NAME" == "$CURRENT_REPO" ]]; then
  WORKFLOW_COUNT=$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null | wc -l | tr -d ' ')
fi
```

**API fallback (remote repos):**

```bash
WORKFLOW_COUNT=$(gh api "/repos/${OWNER}/${REPO_NAME}/actions/workflows" --jq '.total_count')
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| Workflow count >= 1 | pass |
| No workflows found | fail |

**Detail string:** `"{N} workflow(s) configured"` or `"No CI/CD workflows"`

---

### `releases`

**Always API (not cached):**

```bash
RELEASE_COUNT=$(gh api "/repos/${OWNER}/${REPO_NAME}/releases?per_page=1" --jq 'length')
TAG_COUNT=$(gh api "/repos/${OWNER}/${REPO_NAME}/tags?per_page=1" --jq 'length')
```

**Check for release workflow (current repo only):**

```bash
if [[ "$REPO_NAME" == "$CURRENT_REPO" ]]; then
  HAS_RELEASE_WF=$(grep -rl 'release' .github/workflows/ 2>/dev/null | head -1)
fi
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| Releases exist (count >= 1) or release workflow present | pass |
| No releases but tags exist | warn |
| No releases, no tags, no release workflow | fail |

**Detail string:** `"Latest: {tag_name} ({date})"` or `"Tags only (no formal releases)"` or `"No releases or tags"`

---

### `documentation`

**Local path (filesystem — current repo only):**

```bash
if [[ "$REPO_NAME" == "$CURRENT_REPO" ]]; then
  HAS_README=$([[ -f "README.md" || -f "readme.md" || -f "README" ]] && echo "true" || echo "false")
  HAS_CONTRIBUTING=$([[ -f "CONTRIBUTING.md" || -f ".github/CONTRIBUTING.md" ]] && echo "true" || echo "false")
  HAS_DOCS=$([[ -d "docs" ]] && echo "true" || echo "false")
fi
```

**API fallback (remote repos):**

```bash
# README
gh api "/repos/${OWNER}/${REPO_NAME}/readme" --silent 2>/dev/null && HAS_README="true" || HAS_README="false"

# CONTRIBUTING.md
gh api "/repos/${OWNER}/${REPO_NAME}/contents/CONTRIBUTING.md" --silent 2>/dev/null && HAS_CONTRIBUTING="true" || HAS_CONTRIBUTING="false"

# docs/
gh api "/repos/${OWNER}/${REPO_NAME}/contents/docs" --silent 2>/dev/null && HAS_DOCS="true" || HAS_DOCS="false"
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| README + (CONTRIBUTING or docs/) | pass |
| README only | warn |
| No README | fail |

**Detail string:** `"README ✓, CONTRIBUTING ✓, docs/ ✓"` format listing what exists

---

### `codeowners`

**Local path (filesystem — current repo only):**

```bash
if [[ "$REPO_NAME" == "$CURRENT_REPO" ]]; then
  for path in "CODEOWNERS" ".github/CODEOWNERS" "docs/CODEOWNERS"; do
    [[ -f "$path" ]] && CODEOWNERS_PATH="$path" && break
  done
fi
```

**API fallback:**

```bash
for path in "CODEOWNERS" ".github/CODEOWNERS" "docs/CODEOWNERS"; do
  if gh api "/repos/${OWNER}/${REPO_NAME}/contents/${path}" --silent 2>/dev/null; then
    CODEOWNERS_PATH="$path"
    break
  fi
done
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| CODEOWNERS found | pass |
| Not found | fail |

**Detail string:** `"Found at {path}"` or `"No CODEOWNERS file"`

---

### `security_policy`

**Local path (filesystem — current repo only):**

```bash
if [[ "$REPO_NAME" == "$CURRENT_REPO" ]]; then
  for path in "SECURITY.md" ".github/SECURITY.md"; do
    [[ -f "$path" ]] && SECURITY_PATH="$path" && break
  done
fi
```

**API fallback:**

```bash
for path in "SECURITY.md" ".github/SECURITY.md"; do
  if gh api "/repos/${OWNER}/${REPO_NAME}/contents/${path}" --silent 2>/dev/null; then
    SECURITY_PATH="$path"
    break
  fi
done
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| SECURITY.md found | pass |
| Not found | fail |

**Detail string:** `"Found at {path}"` or `"No security policy"`

---

### `license`

**Local path (filesystem — current repo only):**

```bash
if [[ "$REPO_NAME" == "$CURRENT_REPO" ]]; then
  LICENSE_FILE=$(ls LICENSE* 2>/dev/null | head -1)
fi
```

**API fallback:**

```bash
LICENSE_INFO=$(gh api "/repos/${OWNER}/${REPO_NAME}/license" --jq '.license.spdx_id' 2>/dev/null)
# 404 = no license
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| LICENSE file found | pass |
| Not found | fail |

**Detail string:** `"{license_type}"` (e.g., `"MIT"`) or `"No license file"`

---

### `dependency_management`

**Local path (filesystem — current repo only):**

```bash
if [[ "$REPO_NAME" == "$CURRENT_REPO" ]]; then
  # Dependabot
  HAS_DEPENDABOT=$([[ -f ".github/dependabot.yml" || -f ".github/dependabot.yaml" ]] && echo "true" || echo "false")
  # Renovate
  HAS_RENOVATE=$([[ -f "renovate.json" || -f ".github/renovate.json" || -f ".renovaterc" || -f ".renovaterc.json" ]] && echo "true" || echo "false")
fi
```

**API fallback:**

```bash
HAS_DEPENDABOT="false"
gh api "/repos/${OWNER}/${REPO_NAME}/contents/.github/dependabot.yml" --silent 2>/dev/null && HAS_DEPENDABOT="true"

HAS_RENOVATE="false"
for path in "renovate.json" ".github/renovate.json" ".renovaterc" ".renovaterc.json"; do
  if gh api "/repos/${OWNER}/${REPO_NAME}/contents/${path}" --silent 2>/dev/null; then
    HAS_RENOVATE="true"
    break
  fi
done
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| Dependabot or Renovate config exists | pass |
| Neither found | fail |

**Detail string:** `"Dependabot configured"`, `"Renovate configured"`, `"Dependabot + Renovate configured"`, or `"No dependency management tool configured"`

---

### `secrets_scanning`

**Always API (not cached):**

```bash
REPO_DATA=$(gh api "/repos/${OWNER}/${REPO_NAME}" --jq '{
  secret_scanning: .security_and_analysis.secret_scanning.status,
  push_protection: .security_and_analysis.secret_scanning_push_protection.status
}' 2>/dev/null)

SECRET_SCANNING=$(echo "$REPO_DATA" | jq -r '.secret_scanning // "unknown"')
PUSH_PROTECTION=$(echo "$REPO_DATA" | jq -r '.push_protection // "unknown"')
```

**Evaluation:**

| Condition | Status |
|-----------|--------|
| Both scanning and push protection enabled | pass |
| Scanning enabled, push protection disabled | warn |
| Scanning not enabled or fields not available | fail |
| Fields null (insufficient permissions) | unknown |

**Detail string:** `"Scanning: enabled, Push protection: enabled"` or details of what's missing

**Note:** Private repos on free plans may not have these fields. Mark as `unknown` if data is null.

---

## Dismissal Check

Before evaluating each check, verify it isn't dismissed:

```bash
HEALTHCHECK_FILE=".hiivmind/github/healthcheck.yaml"

# Check if dismissed for this repo
DISMISSED_AT=$(yq ".dismissals[\"${REPO_NAME}\"][\"${CHECK_ID}\"].dismissed_at // \"\"" "$HEALTHCHECK_FILE" 2>/dev/null)
REVIEW_AFTER=$(yq ".dismissals[\"${REPO_NAME}\"][\"${CHECK_ID}\"].review_after // \"\"" "$HEALTHCHECK_FILE" 2>/dev/null)

if [[ -n "$DISMISSED_AT" ]]; then
  if [[ -n "$REVIEW_AFTER" ]]; then
    # Check if review_after date has passed
    if [[ "$(date -u +%Y-%m-%d)" > "$REVIEW_AFTER" || "$(date -u +%Y-%m-%d)" == "$REVIEW_AFTER" ]]; then
      # Dismissal expired — re-evaluate
      echo "Dismissal expired for ${CHECK_ID}, re-evaluating..."
    else
      # Still dismissed — skip
      echo "Skipping ${CHECK_ID} (dismissed until ${REVIEW_AFTER})"
      continue
    fi
  else
    # Permanently dismissed — skip
    echo "Skipping ${CHECK_ID} (permanently dismissed)"
    continue
  fi
fi
```

---

## Score Calculation

After evaluating all checks for a repo:

```
score = count(pass) + floor(count(warn) * 0.5)
total = count(pass) + count(warn) + count(fail)
# Exclude: dismissed, unknown

grade:
  A = score >= total - 1  (10-11 of 11)
  B = score >= total - 3  (8-9 of 11)
  C = score >= total - 5  (6-7 of 11)
  D = score >= total - 7  (4-5 of 11)
  F = score < total - 7   (0-3 of 11)
```

For multi-repo aggregate:

```
aggregate_score = sum(repo_scores)
aggregate_total = sum(repo_totals)
aggregate_grade = grade(aggregate_score / aggregate_total * 11)
```
