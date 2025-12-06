# GitHub Projects Explorer

A Claude Code plugin that enables intelligent exploration and analysis of GitHub Projects v2. When installed, Claude automatically understands how to query, filter, and analyze your project boards.

## How It Works

This plugin provides Claude with a **skill** - specialized knowledge about GitHub Projects v2 that Claude can invoke automatically when you ask questions like:

- "What's the status of our project board?"
- "Show me John's backlog items"
- "How many high-priority issues are in the API repository?"
- "Who's working on the frontend?"

Claude reads the skill documentation and executes the appropriate bash pipelines to fetch and analyze your project data.

## Installation

### As Claude Code Plugin

```bash
# Install from marketplace (when published)
claude plugin add your-org/github-projects-explorer
```

### Prerequisites

The following tools must be installed on your system:

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

Once installed, simply ask Claude about your GitHub Projects:

```
> What projects do I have access to?

> Show me all items in project 2 for acme-corp

> Filter the project to show only John's items in the Backlog

> How many items are assigned to each team member?

> What repositories are represented in this project?
```

Claude will automatically source the functions, execute the queries, and present the results.

## Plugin Architecture

```
github-projects-explorer/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest
│   └── marketplace.json         # Marketplace distribution
├── skills/
│   └── github-projects-explorer/
│       └── SKILL.md             # Skill knowledge (auto-invoked by Claude)
├── lib/github/
│   ├── gh-project-functions.sh  # Bash pipeline functions
│   ├── gh-project-graphql-queries.yaml
│   └── gh-project-jq-filters.yaml
└── docs/
    └── PROJECT_OVERVIEW.md      # Architecture documentation
```

### The Skill

The `SKILL.md` file contains comprehensive documentation that Claude reads to understand:

- Available functions and their parameters
- Pipeline patterns for composing queries
- Output formats and how to interpret results
- Common workflows and best practices

### The Pipeline Library

The `lib/github/` directory contains the actual implementation:

| File | Purpose |
|------|---------|
| `gh-project-functions.sh` | Bash functions for fetching and filtering |
| `gh-project-graphql-queries.yaml` | GraphQL query templates |
| `gh-project-jq-filters.yaml` | jq filter definitions |

## Manual Usage

You can also use the functions directly in bash:

```bash
# Source the functions
source lib/github/gh-project-functions.sh

# Discover projects
discover_user_projects | format_user_projects
discover_org_projects "acme-corp" | format_org_projects "acme-corp"

# Fetch and filter project items
fetch_org_project 2 "acme-corp" | apply_assignee_filter "john"
fetch_org_project 2 "acme-corp" | apply_universal_filter "api" "" "Backlog" ""

# Discovery functions
fetch_org_project 2 "acme-corp" | list_assignees
fetch_org_project 2 "acme-corp" | list_repositories
fetch_org_project 2 "acme-corp" | list_statuses
```

## Troubleshooting

### "gh: command not found"
Install GitHub CLI: https://cli.github.com/

### "yq: command not found"
Install yq v4+: `brew install yq` or https://github.com/mikefarah/yq

### Permission errors
Ensure your token has the `read:project` scope:
```bash
gh auth refresh -s read:project
```

### Empty results
1. Verify project number and organization name
2. Check access with `gh project list --owner ORG`
3. Use discovery functions to find valid filter values

## Contributing

The system is designed to be extensible:

1. **New Filters**: Add to `lib/github/gh-project-jq-filters.yaml`
2. **New Functions**: Add to `lib/github/gh-project-functions.sh`
3. **New Queries**: Add to `lib/github/gh-project-graphql-queries.yaml`
4. **Skill Updates**: Enhance `skills/github-projects-explorer/SKILL.md`

## License

MIT
