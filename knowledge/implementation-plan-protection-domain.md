# Implementation Plan: Protection Domain

> **Document ID:** IMPL-003
> **Created:** 2025-12-11
> **Status:** Draft - For Review
> **Relates To:** Milestone "Architecture Refactor: Domain Segmentation P0-P1a", P1c

This document provides a complete specification for the Protection domain, designed from base principles aligned with ARCH-001 (Architecture Principles) and ARCH-002 (Domain Segmentation).

---

## Executive Summary

### Design Decision: Unified Protection Domain

Following the recommendation in ARCH-002, we will create a **single unified Protection domain** that handles both:
- Legacy Branch Protection Rules (per-branch, REST-primary)
- Modern Repository Rulesets (pattern-based, GraphQL-primary)

**Rationale:**
- Both protect repository branches/tags
- Users think in terms of "protection" not API version
- Unified view simplifies querying "what protections exist?"
- Skills can abstract the choice between APIs

### API Strategy

| Concept | Primary API | Secondary API | Notes |
|---------|-------------|---------------|-------|
| **Branch Protection Rules** | REST | GraphQL (read) | REST has full CRUD, GraphQL read-only on some fields |
| **Repository Rulesets** | GraphQL | REST | GraphQL has complete CRUD, REST also works |
| **Organization Rulesets** | GraphQL | REST | Org-level rulesets via GraphQL |

**Priority Chain Application:**
1. Native `gh` CLI - limited support for protection
2. GraphQL for rulesets (full CRUD, pattern-based)
3. REST for branch protection (full CRUD, per-branch)
4. Research via github-navigate for new features

---

## Domain Boundaries

### In Scope

The Protection domain covers:
- **Branch Protection Rules** - per-branch rules (main, develop)
- **Repository Rulesets** - pattern-based rules (feature/*, release/*)
- **Organization Rulesets** - org-wide rulesets applying to multiple repos
- **Rule Evaluation** - what rules apply to a specific branch
- **Bypass Configuration** - who can bypass rules

### Out of Scope

- **Repository settings** (visibility, features) - Repository domain
- **User/team permissions** - Identity domain
- **GitHub Actions secrets** - Secret domain (P2)
- **Deployment environments** - Action domain (P2)

---

## GraphQL Schema Analysis

### BranchProtectionRule Type

From `schema.docs.graphql` lines 2668-2959:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `ID!` | Node ID |
| `pattern` | `String!` | Branch pattern (glob) |
| `allowsDeletions` | `Boolean!` | Can branch be deleted |
| `allowsForcePushes` | `Boolean!` | Are force pushes allowed |
| `blocksCreations` | `Boolean!` | Is creation protected |
| `dismissesStaleReviews` | `Boolean!` | Dismiss stale reviews on push |
| `isAdminEnforced` | `Boolean!` | Enforce for admins |
| `lockBranch` | `Boolean!` | Read-only branch |
| `lockAllowsFetchAndMerge` | `Boolean!` | Allow fork syncing when locked |
| `requireLastPushApproval` | `Boolean!` | Last push must be approved by different user |
| `requiredApprovingReviewCount` | `Int` | Number of required approvals |
| `requiredDeploymentEnvironments` | `[String]` | Required deployment envs |
| `requiredStatusCheckContexts` | `[String]` | Required status check names |
| `requiredStatusChecks` | `[RequiredStatusCheckDescription!]` | Status checks with app ID |
| `requiresApprovingReviews` | `Boolean!` | Reviews required |
| `requiresCodeOwnerReviews` | `Boolean!` | Code owner review required |
| `requiresCommitSignatures` | `Boolean!` | Signed commits required |
| `requiresConversationResolution` | `Boolean!` | Conversations must be resolved |
| `requiresDeployments` | `Boolean!` | Deployments required |
| `requiresLinearHistory` | `Boolean!` | No merge commits |
| `requiresStatusChecks` | `Boolean!` | Status checks required |
| `requiresStrictStatusChecks` | `Boolean!` | Branch must be up to date |
| `restrictsPushes` | `Boolean!` | Push restricted |
| `restrictsReviewDismissals` | `Boolean!` | Review dismissal restricted |
| `matchingRefs` | `RefConnection!` | Branches matching this rule |
| `bypassForcePushAllowances` | `BypassForcePushAllowanceConnection!` | Who can force push |
| `bypassPullRequestAllowances` | `BypassPullRequestAllowanceConnection!` | Who can bypass PR |
| `pushAllowances` | `PushAllowanceConnection!` | Who can push |
| `reviewDismissalAllowances` | `ReviewDismissalAllowanceConnection!` | Who can dismiss reviews |

### RepositoryRuleset Type

From `schema.docs.graphql` lines 53451-53551:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `ID!` | Node ID |
| `name` | `String!` | Ruleset name |
| `target` | `RepositoryRulesetTarget` | BRANCH, TAG, PUSH, REPOSITORY |
| `enforcement` | `RuleEnforcement!` | ACTIVE, EVALUATE, DISABLED |
| `conditions` | `RepositoryRuleConditions!` | When ruleset applies |
| `rules` | `RepositoryRuleConnection` | List of rules |
| `bypassActors` | `RepositoryRulesetBypassActorConnection` | Who can bypass |
| `source` | `RuleSource!` | Repository, Organization, or Enterprise |
| `createdAt` | `DateTime!` | Creation timestamp |
| `updatedAt` | `DateTime!` | Last update timestamp |

### RepositoryRuleType Enum (29 rule types)

| Rule Type | Description |
|-----------|-------------|
| `AUTHORIZATION` | Authorization checks |
| `BRANCH_NAME_PATTERN` | Branch naming convention |
| `CODE_SCANNING` | Code scanning must pass |
| `COMMITTER_EMAIL_PATTERN` | Committer email format |
| `COMMIT_AUTHOR_EMAIL_PATTERN` | Author email format |
| `COMMIT_MESSAGE_PATTERN` | Commit message format |
| `COPILOT_CODE_REVIEW` | Request Copilot review |
| `CREATION` | Restrict branch/tag creation |
| `DELETION` | Restrict branch/tag deletion |
| `FILE_EXTENSION_RESTRICTION` | Block certain file extensions |
| `FILE_PATH_RESTRICTION` | Block certain file paths |
| `LOCK_BRANCH` | Branch is read-only |
| `MAX_FILE_PATH_LENGTH` | Limit file path length |
| `MAX_FILE_SIZE` | Limit file size |
| `MAX_REF_UPDATES` | Limit ref updates per push |
| `MERGE_QUEUE` | Require merge queue |
| `MERGE_QUEUE_LOCKED_REF` | Merge queue locked ref |
| `NON_FAST_FORWARD` | Prevent force pushes |
| `PULL_REQUEST` | Require pull request |
| `REQUIRED_DEPLOYMENTS` | Require deployments |
| `REQUIRED_LINEAR_HISTORY` | No merge commits |
| `REQUIRED_REVIEW_THREAD_RESOLUTION` | Resolve conversations |
| `REQUIRED_SIGNATURES` | Signed commits |
| `REQUIRED_STATUS_CHECKS` | Status checks must pass |
| `REQUIRED_WORKFLOW_STATUS_CHECKS` | Workflow checks must pass |
| `SECRET_SCANNING` | Secret scanning |
| `TAG` | Tag protection |
| `TAG_NAME_PATTERN` | Tag naming convention |
| `UPDATE` | Restrict updates |
| `WORKFLOWS` | Required workflows |
| `WORKFLOW_UPDATES` | Prevent workflow file changes |

### GraphQL Mutations Available

| Mutation | Input Type | Description |
|----------|------------|-------------|
| `createBranchProtectionRule` | `CreateBranchProtectionRuleInput!` | Create branch protection |
| `updateBranchProtectionRule` | `UpdateBranchProtectionRuleInput!` | Update branch protection |
| `deleteBranchProtectionRule` | `DeleteBranchProtectionRuleInput!` | Delete branch protection |
| `createRepositoryRuleset` | `CreateRepositoryRulesetInput!` | Create ruleset |
| `updateRepositoryRuleset` | `UpdateRepositoryRulesetInput!` | Update ruleset |
| `deleteRepositoryRuleset` | `DeleteRepositoryRulesetInput!` | Delete ruleset |

---

## REST API Analysis

### Branch Protection Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/repos/{owner}/{repo}/branches/{branch}/protection` | Get protection rules |
| PUT | `/repos/{owner}/{repo}/branches/{branch}/protection` | Set protection rules |
| DELETE | `/repos/{owner}/{repo}/branches/{branch}/protection` | Remove protection |
| GET/POST/DELETE | `.../protection/enforce_admins` | Admin enforcement |
| GET/PATCH/DELETE | `.../protection/required_pull_request_reviews` | PR review settings |
| GET/PATCH/DELETE | `.../protection/required_signatures` | Signature requirements |
| GET/PATCH/DELETE | `.../protection/required_status_checks` | Status check settings |
| GET/POST/PUT/DELETE | `.../protection/required_status_checks/contexts` | Status check contexts |
| GET/DELETE | `.../protection/restrictions` | Push restrictions |
| GET/POST/PUT/DELETE | `.../protection/restrictions/users` | User restrictions |
| GET/POST/PUT/DELETE | `.../protection/restrictions/teams` | Team restrictions |
| GET/POST/PUT/DELETE | `.../protection/restrictions/apps` | App restrictions |

**REST Limitation:** Cannot use wildcard patterns. REST is per-branch only.

### Repository Ruleset Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/repos/{owner}/{repo}/rules/branches/{branch}` | Rules applying to branch |
| GET | `/repos/{owner}/{repo}/rulesets` | List repo rulesets |
| POST | `/repos/{owner}/{repo}/rulesets` | Create repo ruleset |
| GET | `/repos/{owner}/{repo}/rulesets/{ruleset_id}` | Get specific ruleset |
| PUT | `/repos/{owner}/{repo}/rulesets/{ruleset_id}` | Update ruleset |
| DELETE | `/repos/{owner}/{repo}/rulesets/{ruleset_id}` | Delete ruleset |
| GET | `/repos/{owner}/{repo}/rulesets/{ruleset_id}/history` | Ruleset history |

### Organization Ruleset Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/orgs/{org}/rulesets` | List org rulesets |
| POST | `/orgs/{org}/rulesets` | Create org ruleset |
| GET | `/orgs/{org}/rulesets/{ruleset_id}` | Get specific ruleset |
| PUT | `/orgs/{org}/rulesets/{ruleset_id}` | Update ruleset |
| DELETE | `/orgs/{org}/rulesets/{ruleset_id}` | Delete ruleset |

---

## Existing Implementation Analysis

### Current Files

| File | Status | Contains |
|------|--------|----------|
| `gh-rest-functions.sh` | Active | Branch protection + Ruleset functions (lines 142-505) |
| `gh-rest-endpoints.yaml` | Active | REST endpoint documentation |
| `gh-branch-protection-templates.yaml` | Active | 5 protection + 5 ruleset templates |

### Functions to MIGRATE from gh-rest-functions.sh

| Function | Type | Lines | Migrate To |
|----------|------|-------|------------|
| `get_branch_protection` | FETCH | 148-156 | gh-protection-functions.sh |
| `check_branch_protection_exists` | DETECT | 159-169 | gh-protection-functions.sh |
| `set_branch_protection` | MUTATE | 174-183 | gh-protection-functions.sh |
| `format_branch_protection` | FORMAT | 186-212 | gh-protection-jq-filters.yaml |
| `list_rulesets` | FETCH | 221-228 | gh-protection-functions.sh |
| `get_ruleset` | FETCH | 231-237 | gh-protection-functions.sh |
| `get_ruleset_by_name` | FETCH | 240-247 | gh-protection-functions.sh |
| `check_ruleset_exists` | DETECT | 250-257 | gh-protection-functions.sh |
| `create_ruleset` | MUTATE | 261-269 | gh-protection-functions.sh |
| `update_ruleset` | MUTATE | 273-282 | gh-protection-functions.sh |
| `create_or_update_ruleset` | MUTATE | 286-305 | gh-protection-functions.sh |
| `format_rulesets` | FORMAT | 308-319 | gh-protection-jq-filters.yaml |
| `detect_repo_type` | DETECT | 326-338 | Already in gh-repo-functions.sh |
| `get_repository` | FETCH | 341-346 | Already in gh-repo-functions.sh |
| `list_branches` | FETCH | 353-362 | Already in gh-repo-functions.sh |
| `check_branch_exists` | DETECT | 365-375 | Already in gh-repo-functions.sh |
| `get_branch` | FETCH | 378-384 | Already in gh-repo-functions.sh |
| `format_branches` | FORMAT | 387-394 | Already in gh-repo-jq-filters.yaml |
| `_get_script_dir` | UTILITY | 402-410 | gh-protection-functions.sh |
| `get_protection_template` | UTILITY | 413-419 | gh-protection-functions.sh |
| `get_ruleset_template` | UTILITY | 422-428 | gh-protection-functions.sh |
| `list_protection_templates` | UTILITY | 431-436 | gh-protection-functions.sh |
| `list_ruleset_templates` | UTILITY | 439-444 | gh-protection-functions.sh |
| `apply_main_branch_protection` | UTILITY | 452-467 | gh-protection-functions.sh |
| `apply_develop_branch_protection` | UTILITY | 470-485 | gh-protection-functions.sh |
| `apply_branch_naming_ruleset` | UTILITY | 488-493 | gh-protection-functions.sh |
| `apply_release_branch_ruleset` | UTILITY | 496-501 | gh-protection-functions.sh |

### Functions Already in Correct Domains

- `detect_repo_type` - gh-repo-functions.sh
- `list_branches`, `check_branch_exists`, `get_branch` - gh-repo-functions.sh
- Milestone functions - gh-milestone-functions.sh (lines 1-140 of gh-rest-functions.sh)

---

## Protection Domain Specification

### Primitive Classification

| Type | Count | Pattern |
|------|-------|---------|
| FETCH | 8 | `fetch_*_protection`, `fetch_*_rulesets` |
| DISCOVER | 4 | `discover_*_rulesets`, `discover_rules_for_branch` |
| LOOKUP | 3 | `get_*_id` |
| FILTER | 3 | `filter_*` |
| FORMAT | 4 | `format_*` |
| DETECT | 3 | `detect_*`, `check_*_exists` |
| MUTATE | 8 | `create_*`, `update_*`, `delete_*`, `set_*` |
| UTILITY | 6 | Template functions, smart apply functions |

**Total: 39 primitives**

---

## Function Specifications

### FETCH Primitives

| Function | Args | API | Output | Description |
|----------|------|-----|--------|-------------|
| `fetch_branch_protection` | `owner`, `repo`, `branch` | REST | JSON | Get protection for specific branch |
| `fetch_branch_protection_graphql` | `owner`, `repo`, `branch` | GraphQL | JSON | Get protection via GraphQL |
| `fetch_repo_rulesets` | `owner`, `repo`, `include_parents?` | REST | JSON | List repo rulesets |
| `fetch_repo_rulesets_graphql` | `owner`, `repo`, `targets?` | GraphQL | JSON | List repo rulesets via GraphQL |
| `fetch_org_rulesets` | `org` | REST | JSON | List org rulesets |
| `fetch_org_rulesets_graphql` | `org` | GraphQL | JSON | List org rulesets via GraphQL |
| `fetch_ruleset` | `owner`, `repo`, `ruleset_id` | REST | JSON | Get specific ruleset |
| `fetch_ruleset_by_name` | `owner`, `repo`, `name` | REST | JSON | Get ruleset by name |

### DISCOVER Primitives

| Function | Args | API | Output | Description |
|----------|------|-----|--------|-------------|
| `discover_repo_branch_protections` | `owner`, `repo` | GraphQL | JSON | All branch protection rules |
| `discover_repo_rulesets` | `owner`, `repo` | GraphQL | JSON | All repo rulesets |
| `discover_org_rulesets` | `org` | GraphQL | JSON | All org rulesets |
| `discover_rules_for_branch` | `owner`, `repo`, `branch` | REST | JSON | All rules applying to branch |

### LOOKUP Primitives

| Function | Args | API | Output | Description |
|----------|------|-----|--------|-------------|
| `get_branch_protection_rule_id` | `owner`, `repo`, `pattern` | GraphQL | ID string | Get node ID by pattern |
| `get_ruleset_id` | `owner`, `repo`, `name` | REST | ID string | Get ruleset ID by name |
| `get_org_ruleset_id` | `org`, `name` | REST | ID string | Get org ruleset ID by name |

### DETECT Primitives

| Function | Args | API | Output | Description |
|----------|------|-----|--------|-------------|
| `detect_branch_protection_exists` | `owner`, `repo`, `branch` | REST | 0/1 | Check if protection exists |
| `detect_ruleset_exists` | `owner`, `repo`, `name` | REST | 0/1 | Check if ruleset exists |
| `detect_protection_source` | `owner`, `repo`, `branch` | Mixed | String | Identify protection source (branch rule, repo ruleset, org ruleset) |

### FILTER Primitives (stdin → stdout)

| Function | Input | Args | Output | Description |
|----------|-------|------|--------|-------------|
| `filter_rulesets_by_target` | Rulesets JSON | `target` | Filtered JSON | Filter by BRANCH/TAG/PUSH |
| `filter_rulesets_by_enforcement` | Rulesets JSON | `enforcement` | Filtered JSON | Filter by ACTIVE/EVALUATE/DISABLED |
| `filter_rules_by_type` | Rules JSON | `type` | Filtered JSON | Filter by rule type |

### FORMAT Primitives (stdin → stdout)

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `format_branch_protection` | Protection JSON | Formatted JSON | Human-readable protection |
| `format_rulesets` | Rulesets JSON | Formatted JSON | Human-readable ruleset list |
| `format_ruleset_detail` | Ruleset JSON | Formatted JSON | Detailed ruleset view |
| `format_rules_for_branch` | Rules JSON | Formatted JSON | Rules applying to branch |

### MUTATE Primitives - Branch Protection

| Function | Args | API | Output | Description |
|----------|------|-----|--------|-------------|
| `create_branch_protection` | `owner`, `repo`, `pattern`, config (stdin) | GraphQL | Result JSON | Create protection rule |
| `update_branch_protection` | `rule_id`, config (stdin) | GraphQL | Result JSON | Update protection rule |
| `delete_branch_protection` | `rule_id` | GraphQL | Result JSON | Delete protection rule |
| `set_branch_protection_rest` | `owner`, `repo`, `branch`, config (stdin) | REST | Result JSON | Set protection via REST |

### MUTATE Primitives - Repository Rulesets

| Function | Args | API | Output | Description |
|----------|------|-----|--------|-------------|
| `create_repo_ruleset` | `owner`, `repo`, config (stdin) | GraphQL | Result JSON | Create repo ruleset |
| `update_repo_ruleset` | `ruleset_id`, config (stdin) | GraphQL | Result JSON | Update repo ruleset |
| `delete_repo_ruleset` | `ruleset_id` | GraphQL | Result JSON | Delete repo ruleset |
| `upsert_repo_ruleset` | `owner`, `repo`, `name`, config (stdin) | Mixed | Result JSON | Create or update by name |

### MUTATE Primitives - Organization Rulesets

| Function | Args | API | Output | Description |
|----------|------|-----|--------|-------------|
| `create_org_ruleset` | `org`, config (stdin) | GraphQL | Result JSON | Create org ruleset |
| `update_org_ruleset` | `ruleset_id`, config (stdin) | GraphQL | Result JSON | Update org ruleset |
| `delete_org_ruleset` | `ruleset_id` | GraphQL | Result JSON | Delete org ruleset |

### UTILITY Functions - Templates

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `get_protection_template` | `template_name` | JSON | Get protection preset |
| `get_ruleset_template` | `template_name` | JSON | Get ruleset preset |
| `list_protection_templates` | - | YAML list | List available protection templates |
| `list_ruleset_templates` | - | YAML list | List available ruleset templates |

### UTILITY Functions - Smart Apply

| Function | Args | Output | Description |
|----------|------|--------|-------------|
| `apply_main_branch_protection` | `owner`, `repo` | Result JSON | Auto-detect and apply main protection |
| `apply_develop_branch_protection` | `owner`, `repo` | Result JSON | Auto-detect and apply develop protection |
| `apply_branch_naming_ruleset` | `owner`, `repo` | Result JSON | Apply naming convention ruleset |
| `apply_release_branch_ruleset` | `owner`, `repo` | Result JSON | Apply release branch ruleset |

---

## GraphQL Queries Specification

### New Queries to Create

| Query Key | Category | Description |
|-----------|----------|-------------|
| `repo_branch_protection_rules` | discovery | All branch protection rules for repo |
| `branch_protection_by_pattern` | fetch | Get rule by pattern |
| `branch_protection_by_id` | fetch | Get rule by node ID |
| `repo_rulesets` | discovery | All rulesets for repo |
| `org_rulesets` | discovery | All rulesets for org |
| `ruleset_by_id` | fetch | Get ruleset by node ID |
| `ruleset_with_rules` | fetch | Ruleset with full rule details |

### Mutations to Create

| Mutation Key | Description |
|--------------|-------------|
| `create_branch_protection_rule` | Create via GraphQL |
| `update_branch_protection_rule` | Update via GraphQL |
| `delete_branch_protection_rule` | Delete via GraphQL |
| `create_repository_ruleset` | Create ruleset via GraphQL |
| `update_repository_ruleset` | Update ruleset via GraphQL |
| `delete_repository_ruleset` | Delete ruleset via GraphQL |

---

## jq Filters Specification

### Filters to Create

| Category | Filter Key | Description |
|----------|------------|-------------|
| format_filters | `format_branch_protection` | Format protection for display |
| format_filters | `format_rulesets_list` | Format ruleset list |
| format_filters | `format_ruleset_detail` | Format single ruleset |
| format_filters | `format_rules_for_branch` | Format applied rules |
| filter_filters | `filter_by_target` | Filter rulesets by target |
| filter_filters | `filter_by_enforcement` | Filter rulesets by enforcement |
| filter_filters | `filter_by_rule_type` | Filter rules by type |
| extract_filters | `extract_rule_types` | Get unique rule types |
| extract_filters | `extract_bypass_actors` | Get bypass actor list |

---

## Files to Create

| File | Purpose |
|------|---------|
| `lib/github/gh-protection-functions.sh` | Shell function primitives |
| `lib/github/gh-protection-graphql-queries.yaml` | GraphQL queries and mutations |
| `lib/github/gh-protection-jq-filters.yaml` | jq filter templates |
| `lib/github/gh-protection-index.md` | Domain documentation |

### Files to Update

| File | Change |
|------|--------|
| `lib/github/gh-rest-functions.sh` | Remove protection functions (lines 142-505), add deprecation note |
| `lib/github/gh-rest-endpoints.yaml` | Move protection endpoints reference to gh-protection-index.md |
| `skills/hiivmind-pulse-gh-branch-protection/SKILL.md` | Update to use new domain library |
| `CLAUDE.md` | Add Protection domain to Key Function Groups |

---

## Implementation Tasks

### Task 1: Create gh-protection-functions.sh

Create new file with all 39 primitives:
- FETCH (8)
- DISCOVER (4)
- LOOKUP (3)
- DETECT (3)
- FILTER wrappers (3)
- FORMAT wrappers (4)
- MUTATE (12)
- UTILITY (6)

### Task 2: Create gh-protection-graphql-queries.yaml

Create GraphQL queries:
- 7 queries for discovery and fetch
- 6 mutations for CRUD

### Task 3: Create gh-protection-jq-filters.yaml

Create jq filters:
- 4 format filters
- 3 filter filters
- 2 extract filters

### Task 4: Create gh-protection-index.md

Document all primitives with:
- Quick reference table
- Detailed function documentation
- GraphQL queries reference
- jq filters reference
- Composition examples
- Template reference

### Task 5: Deprecate functions in gh-rest-functions.sh

Add deprecation warnings to lines 142-505:
```bash
# DEPRECATED: Use gh-protection-functions.sh instead
# These functions will be removed in a future version
```

### Task 6: Update SKILL.md

Update branch-protection skill to:
- Source gh-protection-functions.sh
- Update function references
- Add new capabilities

### Task 7: Update CLAUDE.md

Add Protection domain to Key Function Groups section.

---

## Acceptance Criteria

1. [ ] `gh-protection-functions.sh` exists with all 39 primitives
2. [ ] `gh-protection-graphql-queries.yaml` exists with all queries/mutations
3. [ ] `gh-protection-jq-filters.yaml` exists with all filters
4. [ ] `gh-protection-index.md` exists with full documentation
5. [ ] `gh-rest-functions.sh` has deprecation warnings on protection functions
6. [ ] Skill SKILL.md updated to use new library
7. [ ] CLAUDE.md updated with Protection domain
8. [ ] All existing protection operations still work (no regressions)

---

## Testing Plan

### Smoke Tests

```bash
# Source and test core functions
source lib/github/gh-protection-functions.sh

# Test branch protection (REST)
fetch_branch_protection "owner" "repo" "main" | format_branch_protection

# Test rulesets (GraphQL)
discover_repo_rulesets "owner" "repo" | format_rulesets

# Test detection
detect_branch_protection_exists "owner" "repo" "main" && echo "Protected"

# Test template application
apply_main_branch_protection "owner" "repo"
```

### Regression Tests

Verify these common patterns still work:
1. `get_branch_protection | format_branch_protection` (existing)
2. `list_rulesets | format_rulesets` (existing)
3. `apply_main_branch_protection` (existing)
4. `create_or_update_ruleset` (existing)

---

## Migration Notes

### For Existing Users

The existing functions in `gh-rest-functions.sh` will continue to work but will show deprecation warnings. Users should:

1. Update imports: `source lib/github/gh-protection-functions.sh`
2. Optionally use new GraphQL-based functions for rulesets
3. No changes needed for templates - same `get_protection_template` API

### API Preference

| Operation | Preferred API | Reason |
|-----------|---------------|--------|
| Branch protection CRUD | REST | More field control |
| Branch protection read | GraphQL | Richer data model |
| Ruleset CRUD | GraphQL | Full feature support |
| Rules for branch | REST | Direct answer |
| Org rulesets | GraphQL | Better pagination |

---

## Related Documents

- **ARCH-001:** Architecture Principles & Design Patterns
- **ARCH-002:** Domain Segmentation Analysis
- **IMPL-001:** Implementation Plan P0-P1a
- **IMPL-002:** Implementation Plan Project Domain
