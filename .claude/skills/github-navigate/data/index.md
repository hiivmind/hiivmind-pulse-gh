# GitHub API & CLI Documentation Index

> Source: https://github.com/github/docs
> Last updated: 2025-12-08
> Commit: 352e783e2254f5a61080202aec6bae09502aa151
> Focus: REST API, GraphQL API, GitHub CLI

---

## REST API

*Create integrations, retrieve data, and automate workflows*

### Getting Started
- **About the REST API** `rest/about-the-rest-api/about-the-rest-api.md` - Overview and capabilities
- **Getting Started** `rest/using-the-rest-api/getting-started-with-the-rest-api.md` - First API call walkthrough
- **Quickstart** `rest/quickstart.md` - Hands-on tutorial
- **API Versions** `rest/about-the-rest-api/api-versions.md` - Version selection and compatibility
- **OpenAPI Description** `rest/about-the-rest-api/about-the-openapi-description-for-the-rest-api.md` - Schema documentation

### Authentication
- **Authenticating to the REST API** `rest/authentication/authenticating-to-the-rest-api.md` - Auth methods overview
- **Keeping Credentials Secure** `rest/authentication/keeping-your-api-credentials-secure.md` - Security best practices
- **Fine-grained PAT Endpoints** `rest/authentication/endpoints-available-for-fine-grained-personal-access-tokens.md`
- **GitHub App Permissions** `rest/authentication/permissions-required-for-github-apps.md`
- **App Installation Tokens** `rest/authentication/endpoints-available-for-github-app-installation-access-tokens.md`
- **App User Access Tokens** `rest/authentication/endpoints-available-for-github-app-user-access-tokens.md`

### Using the API
- **Best Practices** `rest/using-the-rest-api/best-practices-for-using-the-rest-api.md` - Production recommendations
- **Rate Limits** `rest/using-the-rest-api/rate-limits-for-the-rest-api.md` - Limits and handling
- **Pagination** `rest/using-the-rest-api/using-pagination-in-the-rest-api.md` - Navigating large result sets
- **Troubleshooting** `rest/using-the-rest-api/troubleshooting-the-rest-api.md` - Common errors and fixes
- **Libraries** `rest/using-the-rest-api/libraries-for-the-rest-api.md` - Official SDKs (Octokit)
- **CORS and JSONP** `rest/using-the-rest-api/using-cors-and-jsonp-to-make-cross-origin-requests.md`
- **Timezones** `rest/using-the-rest-api/timezones-and-the-rest-api.md`
- **Event Types** `rest/using-the-rest-api/github-event-types.md` - Webhook/activity events
- **Issue Event Types** `rest/using-the-rest-api/issue-event-types.md`

### Guides
- **Scripting with JavaScript** `rest/guides/scripting-with-the-rest-api-and-javascript.md`
- **Scripting with Ruby** `rest/guides/scripting-with-the-rest-api-and-ruby.md`
- **Building a CI Server** `rest/guides/building-a-ci-server.md`
- **Delivering Deployments** `rest/guides/delivering-deployments.md`
- **Interacting with Checks** `rest/guides/using-the-rest-api-to-interact-with-checks.md`
- **Git Database Operations** `rest/guides/using-the-rest-api-to-interact-with-your-git-database.md`
- **Encrypting Secrets** `rest/guides/encrypting-secrets-for-the-rest-api.md`
- **Working with Comments** `rest/guides/working-with-comments.md`
- **Discovering User Resources** `rest/guides/discovering-resources-for-a-user.md`
- **Rendering Data as Graphs** `rest/guides/rendering-data-as-graphs.md`

### Endpoint Reference

#### Repositories
- **Repos** `rest/repos/repos.md` - Create, get, update, delete repos
- **Contents** `rest/repos/contents.md` - File CRUD operations
- **Forks** `rest/repos/forks.md` - Fork management
- **Webhooks** `rest/repos/webhooks.md` - Repository webhooks
- **Tags** `rest/repos/tags.md` - Tag protection
- **Rules** `rest/repos/rules.md` - Branch/tag rules
- **Rule Suites** `rest/repos/rule-suites.md`
- **Autolinks** `rest/repos/autolinks.md`
- **Custom Properties** `rest/repos/custom-properties.md`
- **LFS** `rest/repos/lfs.md` - Large file storage

#### Pull Requests
- **Pulls** `rest/pulls/pulls.md` - PR CRUD operations
- **Reviews** `rest/pulls/reviews.md` - PR review management
- **Review Requests** `rest/pulls/review-requests.md`
- **Comments** `rest/pulls/comments.md` - PR comments

#### Issues
- **Issues** `rest/issues/issues.md` - Issue CRUD
- **Comments** `rest/issues/comments.md` - Issue comments
- **Labels** `rest/issues/labels.md` - Label management
- **Milestones** `rest/issues/milestones.md`
- **Assignees** `rest/issues/assignees.md`
- **Events** `rest/issues/events.md` - Issue events
- **Timeline** `rest/issues/timeline.md`

#### Actions (CI/CD)
- **Workflows** `rest/actions/workflows.md` - Workflow management
- **Workflow Runs** `rest/actions/workflow-runs.md` - Run operations
- **Workflow Jobs** `rest/actions/workflow-jobs.md` - Job details
- **Artifacts** `rest/actions/artifacts.md` - Build artifacts
- **Secrets** `rest/actions/secrets.md` - Encrypted secrets
- **Variables** `rest/actions/variables.md` - Environment variables
- **Cache** `rest/actions/cache.md` - Dependency caching
- **Self-hosted Runners** `rest/actions/self-hosted-runners.md`
- **Runner Groups** `rest/actions/self-hosted-runner-groups.md`
- **Hosted Runners** `rest/actions/hosted-runners.md`
- **Permissions** `rest/actions/permissions.md`
- **OIDC** `rest/actions/oidc.md` - OpenID Connect

#### Users & Organizations
- **Users** `rest/users/` - User profiles and settings
- **Orgs** `rest/orgs/` - Organization management
- **Teams** `rest/teams/` - Team operations
- **Collaborators** `rest/collaborators/` - Repository collaborators

#### Git Operations
- **Git** `rest/git/` - Low-level git operations (blobs, commits, refs, trees)
- **Commits** `rest/commits/` - Commit data and status
- **Branches** `rest/branches/` - Branch management

#### Security & Code Quality
- **Code Scanning** `rest/code-scanning/` - SAST alerts
- **Secret Scanning** `rest/secret-scanning/` - Secret detection
- **Dependabot** `rest/dependabot/` - Dependency alerts
- **Security Advisories** `rest/security-advisories/` - Vulnerability advisories
- **Dependency Graph** `rest/dependency-graph/` - SBOM operations

#### Other Endpoints
- **Search** `rest/search/` - Search code, issues, repos, users
- **Gists** `rest/gists/` - Gist management
- **Packages** `rest/packages/` - GitHub Packages
- **Pages** `rest/pages/` - GitHub Pages
- **Projects** `rest/projects/` - Projects (new)
- **Projects Classic** `rest/projects-classic/` - Classic project boards
- **Releases** `rest/releases/` - Release management
- **Deployments** `rest/deployments/` - Deployment status
- **Checks** `rest/checks/` - Check runs and suites
- **Reactions** `rest/reactions/` - Emoji reactions
- **Activity** `rest/activity/` - Events, feeds, notifications, starring, watching
- **Apps** `rest/apps/` - GitHub App management
- **Copilot** `rest/copilot/` - Copilot API
- **Codespaces** `rest/codespaces/` - Codespace management
- **Billing** `rest/billing/` - Usage and billing
- **Meta** `rest/meta/` - GitHub API metadata
- **Rate Limit** `rest/rate-limit/` - Check rate limit status
- **Markdown** `rest/markdown/` - Render markdown
- **Emojis** `rest/emojis/` - Available emojis
- **Gitignore** `rest/gitignore/` - Gitignore templates
- **Licenses** `rest/licenses/` - License templates

---

## GraphQL API

*More precise and flexible queries than REST*

### Overview
- **About the GraphQL API** `graphql/overview/about-the-graphql-api.md` - Why GraphQL
- **Public Schema** `graphql/overview/public-schema.md` - Schema explorer
- **Rate Limits** `graphql/overview/rate-limits-and-query-limits-for-the-graphql-api.md`
- **Breaking Changes** `graphql/overview/breaking-changes.md`
- **Changelog** `graphql/overview/changelog.md`

### Guides
- **Introduction to GraphQL** `graphql/guides/introduction-to-graphql.md` - Core concepts
- **Forming Calls** `graphql/guides/forming-calls-with-graphql.md` - Query construction
- **Using GraphQL Clients** `graphql/guides/using-graphql-clients.md` - Client libraries
- **Pagination** `graphql/guides/using-pagination-in-the-graphql-api.md` - Cursor-based pagination
- **Global Node IDs** `graphql/guides/using-global-node-ids.md` - Object identification
- **Migrating Node IDs** `graphql/guides/migrating-graphql-global-node-ids.md`
- **Migrating from REST** `graphql/guides/migrating-from-rest-to-graphql.md` - Transition guide
- **Managing Enterprise Accounts** `graphql/guides/managing-enterprise-accounts.md`
- **Discussions API** `graphql/guides/using-the-graphql-api-for-discussions.md`

### Reference
- **Reference Documentation** `graphql/reference/` - Full schema reference (queries, mutations, objects, interfaces, enums, unions, input objects, scalars)

---

## GitHub CLI (gh)

*GitHub from the command line*

### Getting Started
- **About GitHub CLI** `github-cli/github-cli/about-github-cli.md` - Overview and features
- **Quickstart** `github-cli/github-cli/quickstart.md` - Installation and first commands

### Reference
- **CLI Reference** `github-cli/github-cli/github-cli-reference.md` - Complete command reference

### Extensions
- **Creating Extensions** `github-cli/github-cli/creating-github-cli-extensions.md` - Build custom commands
- **Using Extensions** `github-cli/github-cli/using-github-cli-extensions.md` - Install and use extensions

### Advanced
- **Using Multiple Accounts** `github-cli/github-cli/using-multiple-accounts.md` - Account switching

---

## REST vs GraphQL Comparison

| Feature | REST | GraphQL |
|---------|------|---------|
| Data fetching | Fixed endpoints | Flexible queries |
| Over-fetching | Common | Avoided |
| Multiple resources | Multiple requests | Single request |
| Versioning | URL-based | Schema evolution |
| Rate limits | Per-request | Point-based |
| Best for | Simple operations | Complex data needs |

See: `rest/about-the-rest-api/comparing-githubs-rest-api-and-graphql-api.md`

---

## Quick Reference

### Common gh Commands
```bash
gh auth login          # Authenticate
gh repo clone REPO     # Clone repository
gh pr create           # Create pull request
gh pr list             # List PRs
gh pr checkout NUM     # Checkout PR
gh issue create        # Create issue
gh issue list          # List issues
gh api ENDPOINT        # Raw API call
gh api graphql         # GraphQL query
```

### Authentication Methods
1. **Personal Access Tokens (PAT)** - `Authorization: Bearer <token>`
2. **GitHub Apps** - JWT + Installation tokens
3. **OAuth Apps** - OAuth flow
4. **GitHub CLI** - `gh auth token`

### Rate Limits
- **REST**: 5,000 requests/hour (authenticated)
- **GraphQL**: 5,000 points/hour
- **Search**: 30 requests/minute
