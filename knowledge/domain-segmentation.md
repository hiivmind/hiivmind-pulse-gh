# Domain Segmentation Analysis

> **Document ID:** ARCH-002
> **Created:** 2025-12-10
> **Updated:** 2025-12-11
> **Status:** Active - Phase 1 Complete

This document analyzes how GitHub concerns should be segmented into domains, comparing our current state with a recommended structure.

---

## Implementation Progress

### Completed Work

| Phase | Domain | Status | GitHub Links |
|-------|--------|--------|--------------|
| P0 | **Identity** | ✅ Complete | [Issue #9](https://github.com/hiivmind/hiivmind-pulse-gh/issues/9) |
| P0 | **Repository** | ✅ Complete | [Issue #10](https://github.com/hiivmind/hiivmind-pulse-gh/issues/10) |
| P1a | **Milestone** | ✅ Complete | [Issue #11](https://github.com/hiivmind/hiivmind-pulse-gh/issues/11) |
| P1a | **Issue** | ✅ Complete | [Issue #12](https://github.com/hiivmind/hiivmind-pulse-gh/issues/12) |
| P1a | **Pull Request** | ✅ Complete | [Issue #13](https://github.com/hiivmind/hiivmind-pulse-gh/issues/13) |
| P1b | **Project (cleanup)** | ✅ Complete | [Issue #14](https://github.com/hiivmind/hiivmind-pulse-gh/issues/14), [Issue #15](https://github.com/hiivmind/hiivmind-pulse-gh/issues/15) |

**Milestone:** [Architecture Refactor: Domain Segmentation P0-P1a](https://github.com/hiivmind/hiivmind-pulse-gh/milestone/2)

**Commits:**
- `d3045ee` - feat: Implement domain-segmented library architecture (P0-P1a)
- `dd02bc6` - feat: Complete Project domain cleanup and add documentation (P1b)

### Implementation Documents

| Document | ID | Description |
|----------|-----|-------------|
| [`architecture-principles.md`](architecture-principles.md) | ARCH-001 | Core principles, priority chain, primitive types |
| [`implementation-plan-p0-p1a.md`](implementation-plan-p0-p1a.md) | IMPL-001 | Full specs for Identity, Repo, Milestone, Issue, PR |
| [`implementation-plan-project-domain.md`](implementation-plan-project-domain.md) | IMPL-002 | Project domain cleanup specs |

### Files Created

```
lib/github/
├── gh-identity-functions.sh          # ~350 lines
├── gh-identity-graphql-queries.yaml  # ~280 lines
├── gh-identity-jq-filters.yaml       # ~280 lines
├── gh-identity-index.md              # Documentation
├── gh-repo-functions.sh              # ~330 lines
├── gh-repo-graphql-queries.yaml      # ~340 lines
├── gh-repo-jq-filters.yaml           # ~280 lines (+ format_repository_for_config)
├── gh-repo-index.md                  # Documentation
├── gh-milestone-functions.sh         # ~400 lines
├── gh-milestone-graphql-queries.yaml # ~200 lines
├── gh-milestone-jq-filters.yaml      # ~280 lines
├── gh-milestone-index.md             # Documentation
├── gh-issue-functions.sh             # ~470 lines
├── gh-issue-graphql-queries.yaml     # ~320 lines
├── gh-issue-jq-filters.yaml          # ~250 lines
├── gh-issue-index.md                 # Documentation
├── gh-pr-functions.sh                # ~520 lines
├── gh-pr-graphql-queries.yaml        # ~400 lines
├── gh-pr-jq-filters.yaml             # ~280 lines
├── gh-pr-index.md                    # Documentation
├── gh-project-functions.sh           # Cleaned (deprecation comments)
├── gh-project-graphql-queries.yaml   # Cleaned (-284 lines)
├── gh-project-jq-filters.yaml        # Cleaned (-81 lines)
└── gh-project-index.md               # New documentation
```

### Next Steps

| Priority | Domain/Task | Description |
|----------|-------------|-------------|
| P1c | **Protection** | Consolidate branch protection + rulesets into single domain |
| P2 | **Action** | GitHub Actions: workflows, runs, jobs |
| P2 | **Secret** | Actions/Dependabot secrets |
| P2 | **Variable** | Environment variables |
| P2 | **Release** | Release management |
| P3 | **Deprecate Legacy** | Remove gh-user-functions.sh, gh-workspace-functions.sh, gh-rest-functions.sh |
| P3 | **Update Skills** | Update skills to use new domain libraries |

---

## Current State Analysis

### Library Files (lib/github/)

| File | Actual Scope | Problems |
|------|--------------|----------|
| `gh-project-functions.sh` | Projects + Milestones + ID lookups | **Kitchen sink** - mixes Projects, Milestones, and generic utilities |
| `gh-project-graphql-queries.yaml` | Projects + Milestones + Views + Status Updates | Same mixing problem |
| `gh-project-jq-filters.yaml` | Project filtering | Correctly scoped |
| `gh-rest-functions.sh` | Milestones + Branch protection detection | Segmented by **API type** not **domain** |
| `gh-rest-endpoints.yaml` | Mixed endpoints | Same problem - API type segmentation |
| `gh-branch-protection-templates.yaml` | Branch protection presets | Correctly scoped |
| `gh-user-functions.sh` | User init workflow + CLI checks | Goal-oriented, not primitives |
| `gh-workspace-functions.sh` | Workspace init workflow | Goal-oriented, not primitives |
| `gh-investigate-functions.sh` | Issue/PR deep analysis | Goal-oriented, mixes Issue + PR domains |

### Current Skills

| Skill | Purpose | Domain Coverage |
|-------|---------|-----------------|
| `user-init` | Verify auth, create user.yaml | Identity (setup) |
| `workspace-init` | Discover org/projects, create config.yaml | Identity + Projects (setup) |
| `workspace-refresh` | Sync config with GitHub | Identity + Projects (maintenance) |
| `investigate` | Deep-dive into issues/PRs | Issues + PRs |
| `projects` | Project operations | Projects |
| `milestones` | Milestone operations | Milestones |
| `branch-protection` | Branch rules | Repositories |

---

## The Core Problem

### Segmentation by API Type (Wrong)

```
gh-rest-functions.sh      ← Contains milestones, branch detection
gh-project-functions.sh   ← Contains GraphQL everything
```

This is wrong because:
1. Developers think in **domains** (Issues, Projects, Milestones), not API types
2. A domain often needs BOTH GraphQL and REST
3. Leads to hunting across files for related functionality

### Segmentation by Workflow (Wrong)

```
gh-user-functions.sh      ← "Initialize user"
gh-workspace-functions.sh ← "Initialize workspace"
gh-investigate-functions.sh ← "Investigate things"
```

This is wrong because:
1. These are **composite workflows**, not primitives
2. Can't be recomposed - they're goal-locked
3. Duplicates primitives that should be shared

---

## GitHub Domain Model

GitHub's entities naturally cluster into these domains:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              IDENTITY                                        │
│  Users, Organizations, Teams, Permissions                                   │
│  "Who can do what?"                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        │ owns
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REPOSITORIES                                      │
│  Repos, Branches, Branch Protection, Rulesets, Settings                     │
│  "Where code lives and how it's protected"                                  │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        │ contains
        ▼
┌───────────────────────────────┐     ┌───────────────────────────────────────┐
│           ISSUES              │     │            PULL REQUESTS              │
│  Issues, Labels, Assignees,   │     │  PRs, Reviews, Checks, Merging        │
│  Comments, Reactions          │     │  "Code review workflow"               │
│  "Work tracking"              │     │                                       │
└───────────────────────────────┘     └───────────────────────────────────────┘
        │                                       │
        │ grouped by                            │
        ▼                                       │
┌───────────────────────────────┐               │
│          MILESTONES           │◄──────────────┘
│  Repo-level grouping for      │
│  issues and PRs               │
│  "Release planning"           │
└───────────────────────────────┘
        │
        │ tracked in
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PROJECTS V2                                       │
│  Projects, Items, Fields, Views, Status Updates, Workflows                  │
│  "Cross-repo planning and tracking"                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete GitHub Domain Catalog

Based on REST API endpoints, GraphQL schema, and `gh` CLI capabilities, here is the full scope of GitHub domains:

### Tier 1: Core Development Workflow

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Identity** | `gh auth` | `/users`, `/orgs` | `user`, `organization`, `viewer` | Users, Orgs, Teams, Auth |
| **Repository** | `gh repo` | `/repos` | `repository` | Repos, Branches, Settings |
| **Issue** | `gh issue` | `/issues` | `issue` mutations | Work tracking |
| **Pull Request** | `gh pr` | `/pulls` | `pullRequest` mutations | Code review |
| **Project** | `gh project` | `/projects` | `projectV2` | Cross-repo planning |

### Tier 2: Release & Deployment

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Release** | `gh release` | `/releases` | Limited | Versioned distributions |
| **Milestone** | - | `/milestones` | `milestone` | Release planning |
| **Deployment** | - | `/deployments` | `deployment` | Deploy status tracking |

### Tier 3: CI/CD & Automation

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Action** | `gh workflow`, `gh run` | `/actions` | Limited | Workflow execution |
| **Secret** | `gh secret` | `/actions/secrets` | - | Encrypted secrets |
| **Variable** | `gh variable` | `/actions/variables` | - | Environment variables |
| **Cache** | `gh cache` | `/actions/cache` | - | Dependency caching |
| **Check** | - | `/check-runs`, `/check-suites` | `checkRun` mutations | CI status checks |

### Tier 4: Security & Compliance

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Branch Protection** | `gh ruleset` | `/branches/*/protection` | `branchProtectionRule` | Branch rules |
| **Ruleset** | `gh ruleset` | `/rulesets` | `repositoryRuleset` | Repository rulesets |
| **Code Scanning** | - | `/code-scanning` | - | SAST alerts |
| **Secret Scanning** | - | `/secret-scanning` | - | Leaked secrets |
| **Dependabot** | - | `/dependabot` | - | Dependency alerts |
| **Security Advisory** | - | `/security-advisories` | `securityAdvisory` | Vulnerability reports |

### Tier 5: Collaboration & Community

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Discussion** | - | - | `discussion` mutations | Community Q&A |
| **Comment** | - | `/comments` | Various | Issue/PR/Discussion comments |
| **Reaction** | - | `/reactions` | `addReaction` | Emoji reactions |
| **Label** | `gh label` | `/labels` | `createLabel` | Issue/PR labels |
| **Notification** | - | `/notifications` | - | Activity notifications |

### Tier 6: Content & Artifacts

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Gist** | `gh gist` | `/gists` | `gist` | Code snippets |
| **Package** | - | `/packages` | - | GitHub Packages |
| **Artifact** | - | `/actions/artifacts` | - | Build artifacts |
| **Pages** | - | `/pages` | - | Static site hosting |
| **Wiki** | - | - | - | Repository wikis |

### Tier 7: Cloud & Infrastructure

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Codespace** | `gh codespace` | `/codespaces` | - | Cloud dev environments |
| **Self-hosted Runner** | - | `/actions/runners` | - | CI runner management |

### Tier 8: Search & Discovery

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Search** | `gh search` | `/search` | `search` | Cross-resource search |
| **Topic** | - | `/topics` | `topic` | Repository topics |
| **Explore** | - | - | - | Trending, recommendations |

### Tier 9: Enterprise & Admin

| Domain | gh CLI | REST | GraphQL | Description |
|--------|--------|------|---------|-------------|
| **Enterprise** | - | `/enterprises` | `enterprise` | Enterprise management |
| **Audit Log** | - | `/audit-log` | - | Activity auditing |
| **Billing** | - | `/billing` | - | Usage and costs |

---

## Recommended Domain Structure

### Strategic Domain Groupings

Rather than implementing all 30+ possible domains, we should focus on **coherent domain groups** that support real workflows.

### Group A: Foundation (P0)

These are prerequisite domains - every other operation depends on them.

| Domain | File Prefix | Scope | gh CLI |
|--------|-------------|-------|--------|
| **Identity** | `gh-identity-` | Users, Orgs, Teams, Auth scopes | `gh auth` |
| **Repository** | `gh-repo-` | Repos, Branches, Settings, Visibility | `gh repo` |

### Group B: Work Tracking (P1)

The core Issue → PR → Project workflow.

| Domain | File Prefix | Scope | gh CLI |
|--------|-------------|-------|--------|
| **Issue** | `gh-issue-` | Issues, Labels, Assignees | `gh issue` |
| **Pull Request** | `gh-pr-` | PRs, Reviews, Review Requests | `gh pr` |
| **Milestone** | `gh-milestone-` | Milestones (repo-level grouping) | - |
| **Project** | `gh-project-` | ProjectsV2, Items, Fields, Views | `gh project` |

### Group C: CI/CD & Automation (P1)

GitHub Actions and related automation - high value for DevOps workflows.

| Domain | File Prefix | Scope | gh CLI |
|--------|-------------|-------|--------|
| **Action** | `gh-action-` | Workflows, Runs, Jobs | `gh workflow`, `gh run` |
| **Secret** | `gh-secret-` | Actions/Dependabot/Codespaces secrets | `gh secret` |
| **Variable** | `gh-variable-` | Environment variables | `gh variable` |
| **Cache** | `gh-cache-` | Dependency caching | `gh cache` |
| **Check** | `gh-check-` | Check runs, Check suites | - |

**Note:** Secret, Variable, Cache could be sub-domains of Action, or kept separate for clarity.

### Group D: Release & Deployment (P2)

Release management and deployment tracking.

| Domain | File Prefix | Scope | gh CLI |
|--------|-------------|-------|--------|
| **Release** | `gh-release-` | Releases, Tags, Assets | `gh release` |
| **Deployment** | `gh-deployment-` | Deployments, Environments | - |
| **Artifact** | `gh-artifact-` | Build artifacts | - |

### Group E: Security & Compliance (P2)

Branch protection, code scanning, dependency management.

| Domain | File Prefix | Scope | gh CLI |
|--------|-------------|-------|--------|
| **Protection** | `gh-protection-` | Branch protection, Rulesets | `gh ruleset` |
| **Code Scanning** | `gh-codescan-` | SAST alerts, Code analysis | - |
| **Dependabot** | `gh-dependabot-` | Dependency alerts, Updates | - |
| **Secret Scanning** | `gh-secretscan-` | Leaked credential detection | - |

### Group F: Collaboration (P3)

Community and collaboration features.

| Domain | File Prefix | Scope | gh CLI |
|--------|-------------|-------|--------|
| **Discussion** | `gh-discussion-` | Discussions, Categories, Polls | - |
| **Label** | `gh-label-` | Labels (shared across Issues/PRs) | `gh label` |
| **Search** | `gh-search-` | Cross-resource search | `gh search` |

### Group G: Cloud & Infrastructure (P3)

Cloud development environments and runner management.

| Domain | File Prefix | Scope | gh CLI |
|--------|-------------|-------|--------|
| **Codespace** | `gh-codespace-` | Codespaces CRUD | `gh codespace` |
| **Runner** | `gh-runner-` | Self-hosted runners | - |

### Not In Scope (for now)

| Domain | Reason |
|--------|--------|
| **Gist** | Low value for project workflows |
| **Package** | Complex, separate ecosystem |
| **Pages** | Specialized use case |
| **Wiki** | Limited API support |
| **Enterprise** | Requires enterprise plan |
| **Audit Log** | Enterprise feature |
| **Billing** | Admin-only, sensitive |

---

## Implementation Roadmap

### Phase 1: Solid Foundation
1. **Identity** - Extract from workspace-functions
2. **Repository** - Extract from rest-functions + new primitives
3. **Clean Project** - Remove non-project functions

### Phase 2: Complete Work Tracking
4. **Issue** - Full CRUD + labels + assignees
5. **Pull Request** - Full CRUD + reviews
6. **Milestone** - Extract from project/rest functions

### Phase 3: CI/CD Power
7. **Action** - Workflows, Runs, Jobs (high value!)
8. **Secret** - Secret management
9. **Variable** - Variable management

### Phase 4: Release Management
10. **Release** - Full release CRUD
11. **Check** - Check runs/suites integration

### Phase 5: Security
12. **Protection** - Consolidate branch protection + rulesets

---

## Domain Consolidation Decisions

### Should Labels be separate?

**Option A:** Separate `gh-label-` domain
- Pro: Clean single responsibility
- Con: Labels are always used with Issues/PRs

**Option B:** Include in Issue domain
- Pro: Matches usage patterns
- Con: PRs also use labels

**Recommendation:** Keep as primitives in Issue domain, with cross-references in PR domain.

### Should Comments be separate?

**Option A:** Separate `gh-comment-` domain
- Pro: Comments exist on Issues, PRs, Discussions, Commits
- Con: Rarely used standalone

**Option B:** Include in parent domains
- Pro: Matches mental model
- Con: Duplication

**Recommendation:** Include in parent domains (Issue, PR, Discussion) since the APIs are different for each.

### Should Secrets/Variables/Cache be under Action?

**Option A:** Nested under Action domain
- Pro: Logically grouped
- Con: Large domain, secrets also used by Dependabot/Codespaces

**Option B:** Separate sibling domains
- Pro: Clear separation, reusable
- Con: More files

**Recommendation:** Keep separate. They have different scopes (repo, org, environment) and are used by multiple features.

### Branch Protection vs Rulesets?

**Option A:** Separate domains
- Pro: Different APIs (REST vs GraphQL)
- Con: Same purpose, confusing

**Option B:** Single Protection domain
- Pro: Unified view of repo protection
- Con: Different underlying systems

**Recommendation:** Single `gh-protection-` domain that handles both legacy branch protection and modern rulesets.

---

## Domain File Structure

Each domain should have:

```
lib/github/
├── gh-{domain}-functions.sh           # Shell primitives
├── gh-{domain}-graphql-queries.yaml   # GraphQL templates (if needed)
├── gh-{domain}-jq-filters.yaml        # jq filters (if needed)
└── gh-{domain}-index.md               # Documentation
```

### Domain Boundaries

**Rule: A function belongs to the domain of its PRIMARY entity.**

| Operation | Primary Entity | Domain |
|-----------|---------------|--------|
| `get_user_id` | User | Identity |
| `get_org_id` | Organization | Identity |
| `detect_owner_type` | Owner (User/Org) | Identity |
| `get_repo_id` | Repository | Repository |
| `detect_default_branch` | Branch | Repository |
| `get_issue_id` | Issue | Issue |
| `set_issue_milestone` | Issue (being modified) | Issue |
| `get_pr_id` | Pull Request | Pull Request |
| `set_pr_milestone` | Pull Request (being modified) | Pull Request |
| `get_milestone_id` | Milestone | Milestone |
| `create_milestone` | Milestone | Milestone |
| `get_project_id` | Project | Project |
| `add_item_to_project` | Project (being modified) | Project |

### Cross-Domain References

Domains may reference each other's IDs:

```bash
# Issue domain function, but needs milestone ID from Milestone domain
# The function lives in Issue domain, calls Milestone domain for ID

# In gh-issue-functions.sh:
set_issue_milestone() {
    local issue_id="$1"
    local milestone_id="$2"  # Caller gets this from Milestone domain
    # ... mutation
}

# Caller composes:
source gh-milestone-functions.sh
source gh-issue-functions.sh

MILESTONE_ID=$(get_milestone_id "owner" "repo" "v1.0")
set_issue_milestone "$ISSUE_ID" "$MILESTONE_ID"
```

---

## Proposed Refactoring

### Phase 1: Extract Identity Domain

Create `gh-identity-functions.sh` with:
- `fetch_viewer` - Current authenticated user
- `fetch_user` - Specific user by login
- `fetch_organization` - Org by login
- `get_user_id` - ← Move from gh-project-functions.sh
- `get_org_id` - ← Move from gh-project-functions.sh
- `detect_owner_type` - ← Move from gh-workspace-functions.sh
- `check_auth_scopes` - ← Move from gh-user-functions.sh

### Phase 2: Extract Repository Domain

Create `gh-repo-functions.sh` with:
- `fetch_repo` - Repository metadata
- `discover_user_repos` - List user's repos
- `discover_org_repos` - List org's repos
- `get_repo_id` - ← Move from gh-project-functions.sh
- `detect_default_branch` - ← Move from gh-rest-functions.sh
- `detect_repo_visibility` - New
- Branch protection functions - ← Move from gh-rest-functions.sh

### Phase 3: Extract Issue Domain

Create `gh-issue-functions.sh` with:
- `fetch_issue` - Full issue data
- `discover_repo_issues` - List repo issues
- `get_issue_id` - ← Move from gh-project-functions.sh
- `set_issue_milestone` - ← Move from gh-project-functions.sh
- `set_issue_labels` - New
- `set_issue_assignees` - New

### Phase 4: Extract PR Domain

Create `gh-pr-functions.sh` with:
- `fetch_pr` - Full PR data
- `discover_repo_prs` - List repo PRs
- `get_pr_id` - ← Move from gh-project-functions.sh
- `set_pr_milestone` - ← Move from gh-project-functions.sh

### Phase 5: Extract Milestone Domain

Create `gh-milestone-functions.sh` with:
- `fetch_repo_milestones` - ← Move from gh-project-functions.sh
- `fetch_milestone` - ← Move from gh-project-functions.sh
- `get_milestone_id` - ← Move from gh-project-functions.sh
- `create_milestone` - ← Move from gh-rest-functions.sh
- `update_milestone` - ← Move from gh-rest-functions.sh
- `close_milestone` - ← Move from gh-rest-functions.sh

### Phase 6: Clean Up Project Domain

`gh-project-functions.sh` becomes **only** ProjectsV2:
- `discover_*_projects` - Keep
- `fetch_*_project` - Keep
- `fetch_*_project_fields` - Keep
- `add_item_to_project` - Keep
- `update_item_*` - Keep
- `create_project` - Keep
- Status updates - Keep
- Views - Keep

Remove:
- All `get_*_id` except `get_*_project_id`
- All milestone functions
- Generic utilities

### Phase 7: Deprecate Workflow Files

Delete or mark deprecated:
- `gh-user-functions.sh` - Replace with Identity domain + SKILL.md composition
- `gh-workspace-functions.sh` - Replace with domain composition
- `gh-investigate-functions.sh` - Replace with Issue + PR domains + SKILL.md composition
- `gh-rest-functions.sh` - Functions moved to proper domains
- `gh-rest-endpoints.yaml` - Not needed

---

## Skill Alignment

Skills should map to workflows, not domains:

| Skill | Composes Domains |
|-------|------------------|
| `user-init` | Identity |
| `workspace-init` | Identity + Project |
| `workspace-refresh` | Identity + Project |
| `investigate` | Issue + PR + Project |
| `projects` | Project |
| `milestones` | Milestone + Issue + PR |
| `branch-protection` | Repository |

---

## Migration Strategy

### Approach: Parallel Creation

1. Create new domain files alongside existing
2. Move functions one at a time, updating imports
3. Add deprecation warnings to old files
4. Update skills to use new structure
5. Delete old files after full migration

### Backward Compatibility

During migration, old files can re-export from new locations:

```bash
# gh-rest-functions.sh (deprecated)
echo "WARNING: gh-rest-functions.sh is deprecated. Use domain-specific files." >&2

source "$(dirname "$0")/gh-milestone-functions.sh"
source "$(dirname "$0")/gh-repo-functions.sh"
```

---

## Summary

| Current | Problem | Proposed |
|---------|---------|----------|
| `gh-project-functions.sh` | Kitchen sink | Split into Project + move utilities to proper domains |
| `gh-rest-functions.sh` | API-type segmentation | Dissolve into Milestone + Repository domains |
| `gh-user-functions.sh` | Workflow, not primitives | Dissolve into Identity domain |
| `gh-workspace-functions.sh` | Workflow, not primitives | Dissolve into Identity + Project domains |
| `gh-investigate-functions.sh` | Workflow, not primitives | Dissolve into Issue + PR domains |

**New structure:**
- `gh-identity-functions.sh` - Users, Orgs, Auth
- `gh-repo-functions.sh` - Repos, Branches, Protection
- `gh-issue-functions.sh` - Issues
- `gh-pr-functions.sh` - Pull Requests
- `gh-milestone-functions.sh` - Milestones
- `gh-project-functions.sh` - ProjectsV2 only (cleaned)
