# Hardcoded Scripts Triage Report

**Date:** 2025-12-15
**Scope:** All skills and reference files in hiivmind-pulse-gh
**Total Analyzed:** ~4,800 lines of documentation

## Executive Summary

This report categorizes all hardcoded bash scripts, GraphQL queries, and yq filters across the plugin as:
- **🟢 GOOD** (17%): Keep as-is
- **🟡 OK** (23%): Could improve
- **🔴 UGLY** (60%): Should reference corpus instead

**Key Finding:** 60% of content (~2,900 lines) is over-specified and should reference the GitHub API corpus instead of hardcoding complete implementations.

**Expected Impact:**
- 31% reduction in total documentation (4,800 → 3,320 lines)
- 83% reduction in hardcoded API calls (1,800 → 300 lines)
- Single source of truth for API syntax (corpus)
- Skills become orchestration tools, not copy-paste libraries

---

## Triage Criteria

### 🟢 GOOD - Keep Hardcoded
- **Infrastructure patterns** that rarely change (config loading, file checks)
- **Decision tables** and routing logic (not executable code)
- **Schema documentation** (field types, structures)
- **Short, universal helpers** (< 10 lines, used everywhere)

### 🟡 OK - Could Improve
- **Medium-length patterns** (10-30 lines) used in 2-3 places
- **Domain-specific helpers** that could be DRYer
- **Examples that blend instruction with code**
- **Patterns needing context to understand**

### 🔴 UGLY - Should Reference Corpus
- **Complete API calls** with full query/mutation syntax
- **Long scripts** (> 30 lines) implementing complete workflows
- **Duplicated patterns** across multiple files
- **Anything that changes when GitHub API evolves**

---

## File-by-File Analysis

### 1. skills/hiivmind-pulse-gh-init/SKILL.md (428 lines)

#### 🟢 GOOD - Keep (3 sections, ~140 lines)
- **Lines 34-60:** CLI verification (jq, gh, yq version checks)
- **Lines 63-84:** Git remote detection for workspace discovery
- **Lines 295-330:** User config template structure

#### 🟡 OK - Could Improve (2 sections, ~150 lines)
- **Lines 142-176:** Config.yaml heredoc → Move to templates/ directory
- **Lines 222-289:** Freshness.yaml heredoc → Use template file

#### 🔴 UGLY - Reference Corpus (2 sections, ~140 lines)
- **Lines 104-122:** Project discovery GraphQL (duplicated in refresh skill)
  ```graphql
  query($login: String!) {
    organization(login: $login) {
      projectsV2(first: 20) { nodes { number id title closed } }
    }
  }
  ```
  **Fix:** "Corpus keywords: `projectsV2`, `organization`, `user`"

- **Lines 187-214:** Project field discovery with fragments (28 lines)
  **Fix:** "Corpus keywords: `ProjectV2Field`, `ProjectV2SingleSelectField`, `options`"

**Recommendation:** 428 → ~220 lines (48% reduction)

---

### 2. skills/hiivmind-pulse-gh-refresh/SKILL.md (1,213 lines)

#### 🟢 GOOD - Keep (2 sections, ~60 lines)
- **Lines 42-61:** Freshness status check (simple yq queries)
- **Lines 199-207:** Update freshness tracking (standard pattern)

#### 🟡 OK - Could Improve (2 sections, ~300 lines)
- **Lines 68-192:** Fetch project views (125 lines) → Split GraphQL (corpus), processing (keep), template (file)
- **Lines 216-388:** Repository settings refresh (173 lines) → Break into subsections with corpus references

#### 🔴 UGLY - Reference Corpus (3 major sections, ~850 lines)

**1. Complete views query (lines 79-132, 54 lines):**
```graphql
query($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      id title
      views(first: 20) {
        nodes {
          id number name layout filter
          fields(first: 50) { nodes { ... } }
          groupByFields(first: 10) { nodes { ... } }
          sortByFields(first: 10) { nodes { ... } }
        }
      }
    }
  }
}
```
**Fix:** "Corpus keywords: `views`, `fields`, `groupByFields`, `sortByFields`"

**2. Branch protection REST API (lines 226-305, 80 lines):**
```bash
PROTECTION=$(gh api "/repos/$OWNER/$REPO/branches/$BRANCH/protection")
# ... 70+ lines of JSON parsing
```
**Fix:** "Corpus keywords: `branches protection`, `required_status_checks`"

**3. Teams GraphQL (lines 790-820, 31 lines):**
```graphql
query($login: String!) {
  organization(login: $login) {
    teams(first: 100) {
      nodes {
        id slug name privacy
        members(first: 100) { edges { role node { login id } } }
        repositories(first: 100) { edges { permission node { name } } }
      }
    }
  }
}
```
**Fix:** "Corpus keywords: `teams`, `members`, `repositories`, `edges.role`"

**Recommendation:** 1,213 → ~600 lines (50% reduction)

---

### 3. skills/hiivmind-pulse-gh-operations/SKILL.md (1,619 lines)

#### 🟢 GOOD - Keep (3 sections, ~400 lines)
- **Lines 22-40:** Config loading (standard infrastructure)
  ```bash
  CONFIG=".hiivmind/github/config.yaml"
  OWNER=$(yq '.workspace.login' "$CONFIG")
  ```
- **Lines 44-214:** Extended config loading functions (load_views, load_repo_settings, etc.)
- **Lines 728-948:** API Routing Table (decision support, not code)

#### 🟡 OK - Could Improve (2 sections, ~400 lines)
- **Lines 218-437:** Step 2 - View configuration (220 lines) → Keep helpers, corpus for examples
- **Lines 439-621:** Step 3 - Repository settings (183 lines) → Extract common patterns, corpus for edge cases

#### 🔴 UGLY - Reference Corpus (4 major sections, ~800 lines)

**1. Domain: Issues (lines 1220-1268, 49 lines):**
```bash
gh api graphql -f query='
  mutation($repositoryId: ID!, $title: String!, $body: String!) {
    createIssue(input: {repositoryId: $repositoryId, title: $title, body: $body}) {
      issue { id number url }
    }
  }
' -f repositoryId="$REPO_ID" -f title="$TITLE" -f body="$BODY"
```
**Fix:** "Corpus keywords: `createIssue`, `updateIssue`, `closeIssue`"

**2. Domain: Pull Requests (lines 1270-1318, 49 lines):**
**Fix:** "Corpus keywords: `createPullRequest`, `mergePullRequest`, `requestReviews`"

**3. Domain: Projects (lines 1320-1407, 88 lines):**
**Fix:** "Corpus keywords: `addProjectV2ItemById`, `updateProjectV2ItemFieldValue`"

**4. All other domains (lines 1409-1575, 167 lines):**
- Milestones (REST), Labels (GraphQL), Protection (REST), Actions (REST), Secrets (REST), Releases (REST)
- Each should reference corpus with specific keywords

**Recommendation:** 1,619 → ~1,000 lines (38% reduction)

---

### 4. reference/api-routing.md (245 lines)

#### 🟢 GOOD - Keep All (245 lines)
- **Lines 8-22:** API Routing Decision Table (perfect decision support format)
- **Lines 24-218:** Domain-specific routing guidance (natural language)
- **Lines 220-233:** Loading Context (essential infrastructure)

#### 🟡 OK - None identified

#### 🔴 UGLY - None identified

**Assessment:** This file is already well-designed for corpus-guided approach. No changes needed.

---

### 5. reference/config-schema.md (1,028 lines)

#### 🟢 GOOD - Keep (~900 lines)
- All schema documentation tables (workspace, projects, repositories, views, repos, automations, relationships, teams)
- All "Common Lookups" tables (lines 241-246, 418-430, 673-680, 789-799)

#### 🟡 OK - Could Improve (~75 lines)
- Pattern examples throughout → Show signature/intent, reference corpus for details

#### 🔴 UGLY - Reference Corpus (2 patterns, ~50 lines)
- **Lines 960-989:** Pattern 5 (Protection-Aware PR Merge) - 30 lines of complete bash
  - **Problem:** Duplicates repo_settings loading logic from operations skill
  - **Fix:** "See Step 3 in operations skill for repo settings helpers"

- **Lines 991-1012:** Pattern 6 (Automation-Aware Operations) - 22 lines
  - **Problem:** Duplicates Step 4 helpers from operations skill
  - **Fix:** "See Step 4 in operations skill for automation helpers"

**Recommendation:** 1,028 → ~900 lines (12% reduction)

---

### 6. reference/workflows/*.md (5 files, ~1,400 lines)

#### 🟢 GOOD - Keep (~250 lines)
- Error handling tables in each workflow
- Prerequisites sections
- High-level flow descriptions

#### 🟡 OK - Could Improve (~50 lines duplication)
- Context loading repeated in all 5 files:
  ```bash
  CONFIG=".hiivmind/github/config.yaml"
  OWNER=$(yq '.workspace.login' "$CONFIG")
  # ... same 8-10 lines in every workflow
  ```
  **Fix:** Extract to "Common Patterns" section in api-routing.md

#### 🔴 UGLY - Reference Corpus (6 major sections, ~1,100 lines)

**1. setup-branch-protection.md, lines 23-82:** Legacy branch protection (60 lines)
- **Fix:** "Corpus keywords: `branches protection`, `required_status_checks`, `enforce_admins`"

**2. setup-branch-protection.md, lines 86-231:** Rulesets creation (146 lines)
- Massive JSON payloads in heredocs
- **Fix:** "Corpus keywords: `rulesets`, `enforcement`, `conditions`, `rules`"

**3. bulk-operations.md, lines 23-233:** Patterns 1-6 (210 lines)
- Seven different bulk operation scripts
- **Fix:** "Corpus keywords: `gh issue list`, `addProjectV2ItemById`, `updateProjectV2ItemFieldValue`"

**4. manage-milestones.md, lines 21-105:** Milestone CRUD (85 lines)
- Complete REST endpoints for all operations
- **Fix:** "Corpus keywords: REST `milestones` endpoints (POST, PATCH, DELETE)"

**5. issue-to-project.md, lines 50-100:** GraphQL alternatives (50 lines)
- Three different ways to do the same thing
- **Fix:** "Corpus keywords: `addProjectV2ItemById` with examples"

**6. project-status-update.md, lines 37-99:** Field update patterns (63 lines)
- Complete mutations for single-select, text, iteration fields
- **Fix:** "Corpus keywords: `updateProjectV2ItemFieldValue` with field type examples"

**Recommendation:** ~1,400 → ~500 lines (64% reduction)

---

## Summary Statistics

### By Category

| Category | Lines | Percentage | Files Affected | Action |
|----------|-------|------------|----------------|--------|
| 🟢 GOOD (Keep) | ~800 | 17% | All | No changes |
| 🟡 OK (Improve) | ~1,100 | 23% | 4 files | Refactor for DRY |
| 🔴 UGLY (Corpus) | ~2,900 | 60% | 5 files | Replace with corpus refs |

**Total analyzed:** ~4,800 lines

### Top 5 Offenders (Most Ugly Content)

| Rank | Location | Lines | Type | Fix |
|------|----------|-------|------|-----|
| 1 | refresh skill, GraphQL queries | 350 | Complete queries | Corpus keywords |
| 2 | operations skill, domain mutations | 450 | CRUD mutations | Corpus references |
| 3 | workflows, complete implementations | 600 | Full scripts | High-level + corpus |
| 4 | refresh skill, REST API parsing | 400 | API + jq parsing | Corpus endpoints |
| 5 | init skill, template generation | 200 | Inline heredocs | Template files |

### Impact by File Type

| File Type | Current Lines | Projected Lines | Reduction |
|-----------|---------------|-----------------|-----------|
| Init skill | 428 | 220 | 48% |
| Refresh skill | 1,213 | 600 | 50% |
| Operations skill | 1,619 | 1,000 | 38% |
| Config schema | 1,028 | 900 | 12% |
| Workflows (5 files) | 1,400 | 500 | 64% |
| API routing | 245 | 245 | 0% |
| **TOTAL** | **4,800** | **3,320** | **31%** |

---

## Detailed Recommendations

### Phase 1: Audit Corpus Coverage (Before Refactoring)

**Goal:** Ensure corpus has all necessary content before removing hardcoded examples.

**Required Corpus Content:**

1. **GraphQL Mutations:**
   - Issues: createIssue, updateIssue, closeIssue, addComment
   - PRs: createPullRequest, mergePullRequest, requestReviews
   - Projects: addProjectV2ItemById, updateProjectV2ItemFieldValue
   - Labels: addLabelsToLabelable, removeLabelsFromLabelable
   - Milestones: (via GraphQL updateIssue with milestoneId)

2. **REST Endpoints:**
   - /repos/{owner}/{repo}/milestones (GET, POST, PATCH, DELETE)
   - /repos/{owner}/{repo}/branches/{branch}/protection (GET, PUT, DELETE)
   - /repos/{owner}/{repo}/rulesets (GET, POST, PUT, DELETE)
   - /repos/{owner}/{repo}/actions/* (workflows, runs, secrets, variables)
   - /repos/{owner}/{repo}/releases (GET, POST, PATCH, DELETE)

3. **Search Keywords to Add:**
   - GraphQL schema types: ProjectV2Field, ProjectV2SingleSelectField, ProjectV2IterationField
   - Common parameters: repositoryId, projectId, milestoneId, labelIds
   - Field update patterns: single-select, text, number, date, iteration
   - Pagination patterns: first, after, edges, nodes

**Acceptance Criteria:** All APIs referenced in skills exist in corpus with keyword tags

---

### Phase 2: Extract Templates

**Goal:** Move inline heredocs to template files.

**Files to Create:**

1. `templates/config.yaml.template` (if doesn't exist)
   - Extract from init skill, lines 142-176
   - Add {{variable}} placeholders for substitution

2. `templates/user.yaml.template` (if doesn't exist)
   - Extract from init skill, lines 295-330
   - Add {{variable}} placeholders

3. Update init skill to reference template files instead of inline heredocs

**Lines Saved:** ~150

---

### Phase 3: Refactor Init Skill

**File:** skills/hiivmind-pulse-gh-init/SKILL.md

**Changes:**

1. **Replace GraphQL (lines 104-122, 187-214) with corpus references:**
   ```markdown
   ## Discover Projects

   **GraphQL Pattern:**
   Reference corpus for project discovery:
   - Keywords: `projectsV2`, `organization`, `user`
   - Example search: "list projects for organization"
   - Returns: project number, ID, title, closed status

   ## Discover Project Fields

   **GraphQL Pattern:**
   Reference corpus for field discovery:
   - Keywords: `ProjectV2Field`, `ProjectV2SingleSelectField`, `options`
   - Example search: "project fields with options"
   - Fragments needed: Field types with inline fragments
   ```

2. **Reference template files instead of inline heredocs:**
   ```markdown
   ## Generate config.yaml

   Use template at `templates/config.yaml.template` with substitutions:
   - {{workspace_type}}: organization or user
   - {{workspace_login}}: $OWNER
   - {{workspace_id}}: $WORKSPACE_ID
   ```

**Result:** 428 → ~220 lines (48% reduction)

---

### Phase 4: Refactor Refresh Skill

**File:** skills/hiivmind-pulse-gh-refresh/SKILL.md

**Changes:**

1. **Replace GraphQL queries with corpus references:**
   ```markdown
   ## Refresh Project Views

   **GraphQL Query:**
   Reference corpus for view query structure:
   - Keywords: `views`, `fields`, `groupByFields`, `sortByFields`
   - Query type: `projectV2(number: Int!)`
   - Nested fields: views.nodes with layout, filter, fields
   - Example search: "project views with field configuration"

   **Processing Logic:** (keep)
   After fetching view data, extract and format:
   - View metadata (number, id, name, layout, filter)
   - Visible fields array
   - Group by configuration
   - Sort by configuration
   ```

2. **Replace REST API examples with corpus references:**
   ```markdown
   ## Fetch Branch Protection

   **REST API:**
   Reference corpus for branch protection endpoint:
   - Endpoint: GET /repos/{owner}/{repo}/branches/{branch}/protection
   - Keywords: `branches protection`, `required_status_checks`, `enforce_admins`
   - Example search: "branch protection settings"
   - Returns: protection rules, required reviews, status checks

   **Processing Logic:** (keep)
   Parse protection response and extract:
   - Required review count
   - Dismiss stale reviews setting
   - Required status checks array
   ```

3. **Keep all processing logic** (jq parsing, file generation, freshness updates)

**Result:** 1,213 → ~600 lines (50% reduction)

---

### Phase 5: Refactor Operations Skill

**File:** skills/hiivmind-pulse-gh-operations/SKILL.md

**Changes:**

1. **Replace domain mutations with corpus references:**
   ```markdown
   ## Step 10: Execute Operation

   ### Domain: Issues

   **Create Issue:**
   - Corpus keywords: `createIssue`, `repositoryId`, `title`, `body`
   - Required fields: repositoryId, title
   - Optional fields: body, assigneeIds, labelIds, projectIds, milestoneId
   - Example search: "create issue with labels"
   - Returns: issue.id, issue.number, issue.url

   **Update Issue:**
   - Corpus keywords: `updateIssue`, `issueId`, `state`
   - Updatable fields: title, body, state, assigneeIds, labelIds, milestoneId
   - Example search: "close issue mutation"

   **Add Comment:**
   - Corpus keywords: `addComment`, `subjectId`, `body`
   - Required fields: subjectId (issue.id), body
   - Example search: "add comment to issue"
   ```

2. **Keep all helper functions:**
   - is_field_visible
   - get_repo_writers
   - load_views, load_teams, etc.

3. **Keep API routing table** (decision support)

4. **Simplify yq examples** to show intent only

**Result:** 1,619 → ~1,000 lines (38% reduction)

---

### Phase 6: Refactor Workflows

**Files:** reference/workflows/*.md (all 5 files)

**Changes:**

1. **Extract common context loading to api-routing.md:**
   ```markdown
   ## Common Patterns

   ### Load Workspace Context

   Standard pattern used in all workflows:
   \`\`\`bash
   CONFIG=".hiivmind/github/config.yaml"
   OWNER=$(yq '.workspace.login' "$CONFIG")
   WORKSPACE_TYPE=$(yq '.workspace.type' "$CONFIG")
   DEFAULT_PROJECT=$(yq '.projects.default' "$CONFIG")
   \`\`\`
   ```

2. **Replace complete scripts with high-level steps + corpus:**
   ```markdown
   ## Workflow: Manage Milestones

   ### Step 1: Create Milestone

   **API:** REST POST /repos/{owner}/{repo}/milestones
   **Corpus keywords:** `milestones`, `due_on`, `description`, `state`
   **Example search:** "create milestone with due date"

   **Required fields:** title
   **Optional fields:** state, description, due_on

   ### Step 2: Assign Milestone to Issues

   **API:** GraphQL updateIssue mutation
   **Corpus keywords:** `updateIssue`, `milestoneId`
   **Example search:** "assign milestone to issue"

   **Required fields:** issueId, milestoneId

   ### Error Handling

   | Error | Cause | Solution |
   |-------|-------|----------|
   | 422 Unprocessable | Invalid due_on format | Use ISO 8601: YYYY-MM-DDTHH:MM:SSZ |
   | 404 Not Found | Milestone doesn't exist | Verify milestone title/number |
   ```

3. **Keep error handling tables and troubleshooting**

**Result:** ~1,400 → ~500 lines (64% reduction)

---

### Phase 7: Clean Up Config Schema

**File:** reference/config-schema.md

**Changes:**

1. **Remove Pattern 5 & 6** (lines 960-1012, ~50 lines)
   - These duplicate operations skill helpers

2. **Add cross-references:**
   ```markdown
   ## Common Usage Patterns

   For pattern examples using cached config data, see:
   - **View-aware operations:** Step 2 in operations skill
   - **Protection-aware operations:** Step 3 in operations skill
   - **Automation-aware operations:** Step 4 in operations skill
   - **Team-aware operations:** Step 6 in operations skill
   ```

3. **Keep all schema tables and common lookups**

**Result:** 1,028 → ~900 lines (12% reduction)

---

## Success Criteria

### Corpus Coverage
✅ All GraphQL mutations indexed with keywords
✅ All REST endpoints documented
✅ Search keywords comprehensive and tested
✅ Examples show required vs optional fields

### Skills Refactored
✅ Init skill: < 250 lines (from 428)
✅ Refresh skill: < 700 lines (from 1,213)
✅ Operations skill: < 1,100 lines (from 1,619)

### Workflows Simplified
✅ Each workflow: < 100 lines (from ~280 avg)
✅ Common patterns extracted to api-routing.md
✅ Focus on decision-making over implementation

### Maintainability
✅ Single source of truth for API syntax (corpus)
✅ GitHub API updates only require corpus changes
✅ Skills focus on orchestration, not syntax
✅ No duplication across files

### Usability
✅ Clear corpus search keywords at each decision point
✅ Natural language guidance preserved
✅ Error handling and troubleshooting kept
✅ Quick lookup tables remain for common patterns

---

## Total Impact Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Total lines** | 4,800 | 3,320 | -31% |
| **Hardcoded API calls** | ~1,800 | ~300 | -83% |
| **Duplication** | High | Low | Eliminated |
| **Corpus usage** | Minimal | Primary | Primary source |
| **Maintainability** | Low | High | Single source of truth |
| **API updates** | Touch all files | Touch corpus only | Centralized |

**Expected Outcome:** Skills become corpus-guided orchestration tools rather than copy-paste command libraries. When GitHub's API evolves, only the corpus needs updates—skills remain stable.

---

## Next Steps

1. **Audit corpus** - Verify all referenced APIs exist with proper keywords
2. **Extract templates** - Move heredocs to template files
3. **Refactor skills** - Replace hardcoded APIs with corpus references (phases 3-5)
4. **Refactor workflows** - Simplify to high-level steps + corpus pointers (phase 6)
5. **Clean up config schema** - Remove duplicates, add cross-references (phase 7)
6. **Test discovery** - Verify corpus search keywords work for all use cases
7. **Update documentation** - Document corpus-first approach in CLAUDE.md

---

## Appendix: Example Corpus References

### Good Corpus Reference Pattern

```markdown
## Create Issue

**GraphQL Mutation:**
Reference corpus for createIssue syntax:
- Keywords: `createIssue`, `repositoryId`, `title`, `body`
- Required: repositoryId, title
- Optional: body, assigneeIds, labelIds, projectIds, milestoneId
- Search: "create issue with labels"

**Returns:** issue.id, issue.number, issue.url
```

### Bad (Current) Hardcoded Pattern

```bash
# Create issue
gh api graphql -f query='
  mutation($repositoryId: ID!, $title: String!, $body: String!, $labelIds: [ID!]) {
    createIssue(input: {
      repositoryId: $repositoryId
      title: $title
      body: $body
      labelIds: $labelIds
    }) {
      issue {
        id
        number
        url
        labels(first: 10) {
          nodes {
            name
          }
        }
      }
    }
  }
' -f repositoryId="$REPO_ID" -f title="Bug in login" -f body="..." -f labelIds='["label1","label2"]'
```

The good pattern tells you **what to search for** and **what fields matter**, while letting the corpus provide the **exact syntax**. This keeps skills concise and maintainable while corpus becomes the authoritative API reference.
