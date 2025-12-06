# GitHub CLI Toolkit

A Claude Code plugin that enables comprehensive GitHub API operations via GraphQL and REST. When installed, Claude automatically understands how to manage Projects v2, Milestones, and other GitHub resources.

## Features

- **GitHub Projects v2** - Full support for project boards, items, status updates, views, fields, and repository linking
- **Milestones** - Query, set on issues/PRs (GraphQL), create/update/close (REST)
- **Branch Protection** - Per-branch protection rules and modern repository rulesets
- **REST API** - Foundation for operations not available via GraphQL

## How It Works

This plugin provides Claude with four **skills** - specialized knowledge that Claude invokes automatically:

| Skill | Use Case |
|-------|----------|
| `github-projects` | "Show me the project board", "Filter by assignee", "Create a status update" |
| `github-milestones` | "List milestones", "Set milestone on this issue", "Close the v1.0 milestone" |
| `github-branch-protection` | "Protect main branch", "Set up branch naming rules", "List rulesets" |
| `github-rest-api` | "Create a new milestone", "Get repository info" |

## Installation

### As Claude Code Plugin

```bash
# Install from marketplace (when published)
claude plugin add your-org/github-cli-toolkit
```

### Prerequisites

- **GitHub CLI (`gh`)**: Authenticated with your GitHub account
- **jq**: JSON processor (1.6+)
- **yq**: YAML processor (4.0+)

```bash
# Verify prerequisites
gh auth status
jq --version
yq --version
```

## Usage

Once installed, simply ask Claude about your GitHub resources:

```
> What projects do I have access to?
> Show me all items in project 2 for acme-corp
> Create a status update saying we're on track
> List milestones for the api repository
> Set the v2.0 milestone on issue #123
```

## Plugin Architecture

```
github-cli-toolkit/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest
│   └── marketplace.json         # Marketplace distribution
├── skills/
│   ├── github-projects/         # Projects v2 skill
│   ├── github-milestones/       # Milestones skill
│   ├── github-branch-protection/# Branch protection skill
│   └── github-rest-api/         # REST API skill
├── lib/github/
│   ├── gh-project-functions.sh      # GraphQL shell functions
│   ├── gh-project-graphql-queries.yaml
│   ├── gh-project-jq-filters.yaml
│   ├── gh-rest-functions.sh         # REST shell functions
│   ├── gh-rest-endpoints.yaml
│   └── gh-branch-protection-templates.yaml  # Protection presets
└── docs/
```

## Manual Usage

```bash
# Source the functions
source lib/github/gh-project-functions.sh
source lib/github/gh-rest-functions.sh

# Projects v2
fetch_org_project 2 "acme-corp" | apply_assignee_filter "john"
fetch_project_views "PVT_xxx"
create_status_update "PVT_xxx" "ON_TRACK" "Sprint going well"

# Milestones
list_milestones "acme" "api" | format_milestones
create_milestone "acme" "api" "v2.0" "Q1 Release" "2025-03-31T00:00:00Z"
set_issue_milestone "I_xxx" "MI_xxx"

# Branch Protection
apply_main_branch_protection "acme" "api"    # Auto-detects org/personal
apply_branch_naming_ruleset "acme" "api"     # Enforce naming conventions
get_branch_protection "acme" "api" "main" | format_branch_protection
list_rulesets "acme" "api" | format_rulesets
```

## Key Capabilities

### Projects v2 (GraphQL)
- Fetch and filter project items
- Status updates (ON_TRACK, AT_RISK, OFF_TRACK, COMPLETE, INACTIVE)
- View management (TABLE, BOARD, ROADMAP)
- Field management and single-select options
- Repository linking
- Server-side sorting and pagination

### Milestones (Mixed GraphQL/REST)
- Query milestones via GraphQL
- Set milestones on issues/PRs via GraphQL
- Create/update/close milestones via REST (no GraphQL mutation exists)

### Branch Protection (REST)
- Per-branch protection rules (main, develop)
- Repository rulesets for pattern-based protection (feature/*, release/*)
- Preset templates for org and personal repositories
- Branch naming convention enforcement
- Smart auto-detection of repo type

### REST API
- Milestone management
- Branch and repository operations
- Extensible for webhooks, labels, etc.

## Troubleshooting

### "gh: command not found"
Install GitHub CLI: https://cli.github.com/

### "yq: command not found"
Install yq v4+: `brew install yq` or https://github.com/mikefarah/yq

### Permission errors
Ensure your token has appropriate scopes:
```bash
gh auth refresh -s read:project -s repo
```

## Contributing

The system is designed to be extensible:

1. **GraphQL Operations**: Add to `lib/github/gh-project-*.yaml` and `gh-project-functions.sh`
2. **REST Operations**: Add to `lib/github/gh-rest-*.yaml` and `gh-rest-functions.sh`
3. **Skills**: Add new skills in `skills/` or enhance existing ones

## License

MIT
