# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## System Overview

This is **hiivmind-pulse-gh** - a Claude Code plugin providing comprehensive GitHub API operations via GraphQL and REST APIs. It includes support for:

- **GitHub Projects v2** - Full project management, status updates, views, fields
- **Milestones** - Repository-level milestone management
- **Protection** - Branch protection rules and repository rulesets (unified domain)
- **REST API** - Operations not available via GraphQL

## Skills

The toolkit provides seven skills with a clear dependency hierarchy:

### Skill Hierarchy

```
hiivmind-pulse-gh-user-init          ← Run FIRST (validates env, creates user.yaml)
       │
       ▼
hiivmind-pulse-gh-workspace-init     ← Run SECOND (discovers org, creates config.yaml)
       │
       ▼
All other skills                     ← Require both init skills completed
```

### Setup & Maintenance

| Skill | Purpose | Creates |
|-------|---------|---------|
| `hiivmind-pulse-gh-user-init` | Verify gh CLI, auth scopes, deps; persist user identity | `user.yaml` |
| `hiivmind-pulse-gh-workspace-init` | Discover projects/repos, cache IDs, enrich user permissions | `config.yaml` |
| `hiivmind-pulse-gh-workspace-refresh` | Sync structural metadata with current GitHub state | Updates both |

### Investigation

| Skill | Purpose | Requires |
|-------|---------|----------|
| `hiivmind-pulse-gh-investigate` | Deep-dive into issues, PRs, project items | Both init skills |

### Operations

| Skill | Purpose | Requires |
|-------|---------|----------|
| `hiivmind-pulse-gh-projects` | Projects v2 - items, filtering, status updates, views | Both init skills |
| `hiivmind-pulse-gh-milestones` | Milestone queries and management | Both init skills |
| `hiivmind-pulse-gh-branch-protection` | Branch protection rules and repository rulesets | Both init skills |

## Workspace Configuration

Skills can use cached org/project structure from `.hiivmind/github/config.yaml`:

```bash
# Check for workspace config
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    ORG=$(yq '.workspace.login' .hiivmind/github/config.yaml)
    DEFAULT_PROJECT=$(yq '.projects.default' .hiivmind/github/config.yaml)
fi
```

See `docs/meta-skill-architecture.md` for full schema.

## When to Use hiivmind-pulse-gh

**Use the config for context, use `gh` for actions.**

### Always Read Config First

Before any GitHub operations in this workspace, load the context:

```bash
# Load workspace context (do this once per session)
CONFIG=".hiivmind/github/config.yaml"
if [[ -f "$CONFIG" ]]; then
    OWNER=$(yq '.workspace.login' "$CONFIG")
    DEFAULT_PROJECT=$(yq '.projects.default' "$CONFIG")
fi
```

Then use these variables with `gh` commands instead of hardcoding:

```bash
# Good - uses config values
gh issue create -R "$OWNER/hiivmind-pulse-gh" --title "..."
gh project item-add "$DEFAULT_PROJECT" --owner "$OWNER" --url "..."

# Bad - hardcoded values
gh issue create -R "hiivmind/hiivmind-pulse-gh" --title "..."
gh project item-add 2 --owner "hiivmind" --url "..."
```

### When to Use Function Libraries

| Use Case | Approach |
|----------|----------|
| Simple issue/PR operations | Raw `gh` with config values |
| Project item add/remove/list | Raw `gh project` with config values |
| Complex GraphQL queries | `source lib/github/gh-project-functions.sh` |
| Filtering project items | Use `apply_*_filter` functions |
| Bulk field/option lookups | Use function libraries |
| Deep issue/PR analysis | Use `investigate` skill |

### When to Use Skills

| Skill | Use When |
|-------|----------|
| `workspace-refresh` | Config is stale or operations fail with "ID not found" |
| `investigate` | Need full context on issue/PR (comments, reviews, timeline) |
| `projects` | Complex project queries, status updates, view management |
| `milestones` | Milestone CRUD operations |
| `branch-protection` | Setting up or modifying branch rules |

### Workflow Example

```bash
# 1. Load context
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
DEFAULT_PROJECT=$(yq '.projects.default' "$CONFIG")

# 2. Create issue with gh (simple operation)
ISSUE_URL=$(gh issue create -R "$OWNER/repo" --title "Feature X" --label "enhancement" --json url --jq '.url')

# 3. Add to project with gh (simple operation)
gh project item-add "$DEFAULT_PROJECT" --owner "$OWNER" --url "$ISSUE_URL"

# 4. For complex queries, use function libraries
source lib/github/gh-project-functions.sh
fetch_org_project "$DEFAULT_PROJECT" "$OWNER" | apply_status_filter "In Progress"
```

## Quick Start

```bash
# Source domain-specific functions (Architecture v2)
source lib/github/gh-identity-functions.sh   # Identity operations
source lib/github/gh-repo-functions.sh       # Repository operations
source lib/github/gh-milestone-functions.sh  # Milestone operations
source lib/github/gh-issue-functions.sh      # Issue operations
source lib/github/gh-pr-functions.sh         # Pull request operations
source lib/github/gh-project-functions.sh    # Project v2 operations
source lib/github/gh-protection-functions.sh # Protection (branch + rulesets)
source lib/github/gh-action-functions.sh     # Actions (workflows, runs, jobs)
source lib/github/gh-secret-functions.sh     # Secrets (encrypted secrets)
source lib/github/gh-variable-functions.sh   # Variables (configuration variables)
source lib/github/gh-release-functions.sh    # Releases (tags, assets, notes)

# Examples
get_viewer_id                                           # Get current user ID
fetch_repo "hiivmind" "hiivmind-pulse-gh" | format_repo # Get repo info
discover_repo_issues "owner" "repo" | format_issues_list # List issues
fetch_org_project 2 "org-name" | apply_status_filter "In Progress"
get_protection_summary "owner" "repo"                   # Summary of all protections
discover_repo_runs "owner" "repo" | filter_runs_by_conclusion "failure" | format_runs
```

## File Structure

```
hiivmind-pulse-gh/
├── .claude-plugin/              # Plugin manifests
├── skills/
│   ├── hiivmind-pulse-gh-user-init/        # Setup: verify CLI, auth, dependencies
│   ├── hiivmind-pulse-gh-workspace-init/   # Setup: create config + discover structure
│   ├── hiivmind-pulse-gh-workspace-refresh/# Maintenance: sync structural metadata
│   ├── hiivmind-pulse-gh-investigate/      # Investigation: deep-dive into entities
│   ├── hiivmind-pulse-gh-projects/         # Operations: Projects v2
│   ├── hiivmind-pulse-gh-milestones/       # Operations: Milestones
│   └── hiivmind-pulse-gh-branch-protection/# Operations: Branch protection
├── templates/                   # Config file templates
│   ├── config.yaml.template     # Shared workspace config
│   ├── user.yaml.template       # Personal user config
│   └── gitignore.template       # Suggested gitignore entries
├── lib/github/
│   ├── # Domain-Specific Libraries (NEW - Architecture v2)
│   ├── gh-identity-functions.sh     # Identity domain (users, orgs, auth)
│   ├── gh-identity-graphql-queries.yaml
│   ├── gh-identity-jq-filters.yaml
│   ├── gh-identity-index.md
│   ├── gh-repo-functions.sh         # Repository domain
│   ├── gh-repo-graphql-queries.yaml
│   ├── gh-repo-jq-filters.yaml
│   ├── gh-repo-index.md
│   ├── gh-milestone-functions.sh    # Milestone domain
│   ├── gh-milestone-graphql-queries.yaml
│   ├── gh-milestone-jq-filters.yaml
│   ├── gh-milestone-index.md
│   ├── gh-issue-functions.sh        # Issue domain
│   ├── gh-issue-graphql-queries.yaml
│   ├── gh-issue-jq-filters.yaml
│   ├── gh-issue-index.md
│   ├── gh-pr-functions.sh           # Pull Request domain
│   ├── gh-pr-graphql-queries.yaml
│   ├── gh-pr-jq-filters.yaml
│   ├── gh-pr-index.md
│   ├── # Project Domain (cleaned)
│   ├── gh-project-functions.sh      # Projects v2 only
│   ├── gh-project-graphql-queries.yaml
│   ├── gh-project-jq-filters.yaml
│   ├── # Protection Domain
│   ├── gh-protection-functions.sh   # Branch protection + rulesets
│   ├── gh-protection-graphql-queries.yaml
│   ├── gh-protection-jq-filters.yaml
│   ├── gh-protection-index.md
│   ├── # Action Domain
│   ├── gh-action-functions.sh       # Workflows, runs, jobs
│   ├── gh-action-jq-filters.yaml
│   ├── gh-action-index.md
│   ├── # Secret Domain
│   ├── gh-secret-functions.sh       # Encrypted secrets
│   ├── gh-secret-jq-filters.yaml
│   ├── gh-secret-index.md
│   ├── # Variable Domain
│   ├── gh-variable-functions.sh     # Configuration variables
│   ├── gh-variable-jq-filters.yaml
│   ├── gh-variable-index.md
│   ├── # Release Domain
│   ├── gh-release-functions.sh      # Releases, tags, assets
│   ├── gh-release-graphql-queries.yaml
│   ├── gh-release-jq-filters.yaml
│   ├── gh-release-index.md
│   ├── # Legacy/Supporting
│   ├── gh-rest-functions.sh         # REST shell functions (DEPRECATED)
│   ├── gh-rest-endpoints.yaml       # REST endpoint templates
│   └── gh-branch-protection-templates.yaml
└── docs/
    └── meta-skill-architecture.md   # Workspace config design
```

## Key Function Groups

### Identity Domain (`gh-identity-functions.sh`)
- `get_viewer_id`, `get_user_id`, `get_org_id` - Lookup IDs
- `fetch_viewer`, `fetch_user`, `fetch_organization` - Fetch data
- `detect_owner_type` - Determine user vs org
- `discover_viewer_organizations` - List user's orgs

### Repository Domain (`gh-repo-functions.sh`)
- `get_repo_id` - Lookup repository ID
- `fetch_repo`, `discover_org_repos`, `discover_user_repos` - Fetch data
- `detect_default_branch`, `detect_repo_visibility` - Detection
- `list_repo_branches` - List branches

### Milestone Domain (`gh-milestone-functions.sh`)
- `get_milestone_id`, `get_milestone_number` - Lookups
- `fetch_repo_milestones`, `fetch_milestone` - GraphQL queries
- `list_milestones_rest`, `create_milestone`, `update_milestone`, `close_milestone` - REST CRUD
- `format_milestones`, `format_milestone_rest` - Formatting

### Issue Domain (`gh-issue-functions.sh`)
- `get_issue_id` - Lookup issue ID
- `fetch_issue`, `discover_repo_issues` - Fetch data
- `filter_issues_by_*` - Filter by state/label/assignee
- `set_issue_milestone`, `add_issue_labels`, `close_issue` - Mutations
- `format_issue`, `format_issues_list` - Formatting

### Pull Request Domain (`gh-pr-functions.sh`)
- `get_pr_id` - Lookup PR ID
- `fetch_pr`, `discover_repo_prs` - Fetch data
- `filter_prs_by_*` - Filter by state/label/reviewer
- `set_pr_milestone`, `request_pr_review`, `mark_pr_ready` - Mutations
- `format_pr`, `format_prs_list` - Formatting

### Projects v2 (`gh-project-functions.sh`)
- `fetch_org_project`, `fetch_user_project` - Fetch project data
- `apply_*_filter` - Filter project items
- `list_*` - Discovery functions
- `fetch_project_status_updates`, `create_status_update` - Status updates
- `fetch_project_views`, `create_project_view` - View management
- `fetch_linked_repositories`, `link_repo_to_project` - Repository linking

### Protection Domain (`gh-protection-functions.sh`)
- `fetch_branch_protection`, `fetch_repo_rulesets`, `fetch_ruleset_by_name` - Fetch data
- `discover_repo_branch_protections`, `discover_rules_for_branch` - Discovery
- `detect_branch_protection_exists`, `detect_ruleset_exists`, `detect_protection_source` - Detection
- `set_branch_protection_rest`, `create_repo_ruleset`, `upsert_repo_ruleset` - Mutations
- `apply_main_branch_protection`, `apply_branch_naming_ruleset`, `get_protection_summary` - Smart templates
- `format_branch_protection`, `format_rulesets` - Formatting

### Action Domain (`gh-action-functions.sh`)
- `fetch_workflow`, `fetch_run`, `fetch_job` - Fetch workflow/run/job details
- `discover_repo_workflows`, `discover_repo_runs`, `discover_run_jobs` - Discovery
- `detect_workflow_state`, `detect_run_status`, `detect_run_conclusion` - Detection
- `trigger_workflow`, `cancel_run`, `rerun_workflow`, `rerun_failed_jobs` - Mutations
- `enable_workflow`, `disable_workflow`, `delete_run_logs` - Management
- `filter_runs_by_*`, `filter_workflows_by_*` - Filtering
- `format_workflows`, `format_runs`, `format_jobs` - Formatting

### Secret Domain (`gh-secret-functions.sh`)
- `fetch_repo_public_key`, `fetch_org_public_key`, `fetch_env_public_key` - Public keys for encryption
- `discover_repo_secrets`, `discover_env_secrets`, `discover_org_secrets`, `discover_user_secrets` - Discovery
- `detect_secret_exists`, `detect_env_secret_exists`, `detect_org_secret_exists` - Detection
- `set_repo_secret`, `set_env_secret`, `set_org_secret`, `set_user_secret` - Set secrets
- `delete_repo_secret`, `delete_env_secret`, `delete_org_secret`, `delete_user_secret` - Delete secrets
- `set_org_secret_repos`, `add_repo_to_org_secret`, `remove_repo_from_org_secret` - Repo access management
- `filter_secrets_by_*`, `format_secrets` - Filtering and formatting

### Variable Domain (`gh-variable-functions.sh`)
- `fetch_repo_variable`, `fetch_org_variable`, `fetch_env_variable` - Fetch variable with value
- `discover_repo_variables`, `discover_env_variables`, `discover_org_variables` - Discovery
- `get_variable_value`, `get_variable_visibility` - Lookup value and visibility
- `detect_repo_variable_exists`, `detect_env_variable_exists`, `detect_org_variable_exists` - Detection
- `set_repo_variable`, `set_env_variable`, `set_org_variable` - Set variables
- `update_repo_variable`, `update_org_variable`, `update_env_variable` - Update variables
- `delete_repo_variable`, `delete_env_variable`, `delete_org_variable` - Delete variables
- `set_org_variable_repos`, `add_repo_to_org_variable`, `remove_repo_from_org_variable` - Repo access management
- `filter_variables_by_*`, `format_variables` - Filtering and formatting

### Release Domain (`gh-release-functions.sh`)
- `fetch_release`, `fetch_release_by_tag`, `fetch_latest_release` - Fetch release data
- `discover_repo_releases`, `discover_release_assets`, `discover_repo_tags` - Discovery
- `get_release_id`, `get_release_tag`, `get_asset_id` - Lookup IDs and tags
- `detect_release_exists`, `detect_is_prerelease`, `detect_is_draft`, `detect_is_latest` - Detection
- `create_release`, `create_draft_release`, `update_release`, `delete_release` - Release CRUD
- `upload_release_asset`, `download_release_asset`, `delete_release_asset` - Asset management
- `publish_draft_release`, `generate_release_notes`, `download_release_tarball` - Utilities
- `filter_releases_by_*`, `format_releases`, `format_assets` - Filtering and formatting

## Pipeline Pattern

All functions read stdin, write stdout. Compose with pipes:

```bash
fetch_org_project 2 "org" | apply_assignee_filter "user" | list_repositories
```

## Dependencies

- GitHub CLI (`gh`) - authenticated with appropriate scopes
- jq (1.6+)
- yq (4.0+)

**Run `hiivmind-pulse-gh-user-init` to verify all dependencies are properly configured.**

## Knowledge Base

Technical documentation for known issues and architectural decisions:

| Document | Description |
|----------|-------------|
| [`knowledge/claude-code-bash-escaping.md`](knowledge/claude-code-bash-escaping.md) | Claude Code Bash tool escaping bug - affects commands with `$(...)`, variables, and pipes |

### Critical: Bash Command Patterns

When writing Bash commands for this plugin, **always use pipe-first patterns**:

```bash
# GOOD - pipe-first, no intermediate variables
discover_projects "$LOGIN" "$TYPE" | format_projects_list

# BAD - triggers Claude Code escaping bug when combined with pipes
PROJECTS=$(discover_projects "$LOGIN" "$TYPE") && echo "$PROJECTS" | format_projects_list
```

See `knowledge/claude-code-bash-escaping.md` for full details on the bug and workarounds.
