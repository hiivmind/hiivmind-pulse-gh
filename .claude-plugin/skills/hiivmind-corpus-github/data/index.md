# GitHub Documentation Corpus Index

> **Source:** github-docs (github/docs)
> **Focus:** GraphQL API, REST API, gh CLI
> **Last updated:** 2024-12-10

---

## GraphQL API

### Overview & Getting Started

- **About the GraphQL API** `github-docs:graphql/overview/about-the-graphql-api.md` - Introduction to GitHub's GraphQL API
- **Public Schema** `github-docs:graphql/overview/public-schema.md` - Download and explore the schema
- **Rate Limits** `github-docs:graphql/overview/rate-limits-and-query-limits-for-the-graphql-api.md` - Understanding query limits and costs
- **Breaking Changes** `github-docs:graphql/overview/breaking-changes.md` - API deprecations and changes
- **Changelog** `github-docs:graphql/overview/changelog.md` - Recent API updates

### GraphQL Guides

- **Introduction to GraphQL** `github-docs:graphql/guides/introduction-to-graphql.md` - Core concepts and terminology
- **Forming Calls** `github-docs:graphql/guides/forming-calls-with-graphql.md` - How to construct GraphQL queries
- **Using Pagination** `github-docs:graphql/guides/using-pagination-in-the-graphql-api.md` - Cursor-based pagination patterns
- **Global Node IDs** `github-docs:graphql/guides/using-global-node-ids.md` - Working with node IDs across APIs
- **Migrating Global Node IDs** `github-docs:graphql/guides/migrating-graphql-global-node-ids.md` - ID format migration guide
- **Migrating from REST** `github-docs:graphql/guides/migrating-from-rest-to-graphql.md` - REST to GraphQL transition
- **GraphQL Clients** `github-docs:graphql/guides/using-graphql-clients.md` - Client libraries and tools
- **Discussions API** `github-docs:graphql/guides/using-the-graphql-api-for-discussions.md` - Managing discussions via GraphQL
- **Enterprise Accounts** `github-docs:graphql/guides/managing-enterprise-accounts.md` - Enterprise management via GraphQL

### GraphQL Reference

- **Queries** `github-docs:graphql/reference/queries.md` - Available query root fields
- **Mutations** `github-docs:graphql/reference/mutations.md` - All mutation operations
- **Objects** `github-docs:graphql/reference/objects.md` - Object type definitions
- **Interfaces** `github-docs:graphql/reference/interfaces.md` - Interface definitions
- **Enums** `github-docs:graphql/reference/enums.md` - Enumeration types
- **Scalars** `github-docs:graphql/reference/scalars.md` - Scalar type definitions
- **Unions** `github-docs:graphql/reference/unions.md` - Union type definitions
- **Input Objects** `github-docs:graphql/reference/input-objects.md` - Input type definitions

### GraphQL Schema (SDL)

- **Full Schema** `graphql-schema:schema.docs.graphql` - Complete GitHub GraphQL API schema in SDL format (70k+ lines)

---

## REST API

### Getting Started

- **About the REST API** `github-docs:rest/about-the-rest-api/about-the-rest-api.md` - Overview and basics
- **Quickstart** `github-docs:rest/quickstart.md` - Quick introduction
- **API Versions** `github-docs:rest/about-the-rest-api/api-versions.md` - Versioning and stability
- **Comparing REST and GraphQL** `github-docs:rest/about-the-rest-api/comparing-githubs-rest-api-and-graphql-api.md` - When to use each
- **Breaking Changes** `github-docs:rest/about-the-rest-api/breaking-changes.md` - API deprecations
- **OpenAPI Description** `github-docs:rest/about-the-rest-api/about-the-openapi-description-for-the-rest-api.md` - Machine-readable API spec

### Using the REST API

- **Getting Started** `github-docs:rest/using-the-rest-api/getting-started-with-the-rest-api.md` - First API calls
- **Best Practices** `github-docs:rest/using-the-rest-api/best-practices-for-using-the-rest-api.md` - Recommended patterns
- **Rate Limits** `github-docs:rest/using-the-rest-api/rate-limits-for-the-rest-api.md` - Understanding rate limiting
- **Pagination** `github-docs:rest/using-the-rest-api/using-pagination-in-the-rest-api.md` - Paginating through results
- **Troubleshooting** `github-docs:rest/using-the-rest-api/troubleshooting-the-rest-api.md` - Common issues and solutions

### Authentication

- **Authenticating to REST API** `github-docs:rest/authentication/authenticating-to-the-rest-api.md` - Auth methods overview
- **Keeping Credentials Secure** `github-docs:rest/authentication/keeping-your-api-credentials-secure.md` - Security best practices
- **Fine-grained PAT Endpoints** `github-docs:rest/authentication/endpoints-available-for-fine-grained-personal-access-tokens.md` - PAT-accessible endpoints
- **GitHub App Permissions** `github-docs:rest/authentication/permissions-required-for-github-apps.md` - App permission reference
- **PAT Permissions** `github-docs:rest/authentication/permissions-required-for-fine-grained-personal-access-tokens.md` - PAT permission reference
- **App Installation Tokens** `github-docs:rest/authentication/endpoints-available-for-github-app-installation-access-tokens.md` - Installation token endpoints
- **App User Tokens** `github-docs:rest/authentication/endpoints-available-for-github-app-user-access-tokens.md` - User token endpoints

### REST Guides

- **Scripting with JavaScript** `github-docs:rest/guides/scripting-with-the-rest-api-and-javascript.md` - Using Octokit.js
- **Scripting with Ruby** `github-docs:rest/guides/scripting-with-the-rest-api-and-ruby.md` - Using Octokit.rb
- **Working with Comments** `github-docs:rest/guides/working-with-comments.md` - Comment operations
- **Interacting with Checks** `github-docs:rest/guides/using-the-rest-api-to-interact-with-checks.md` - Check runs and suites
- **Git Database** `github-docs:rest/guides/using-the-rest-api-to-interact-with-your-git-database.md` - Low-level git operations
- **Building a CI Server** `github-docs:rest/guides/building-a-ci-server.md` - CI integration patterns
- **Delivering Deployments** `github-docs:rest/guides/delivering-deployments.md` - Deployment workflows
- **Encrypting Secrets** `github-docs:rest/guides/encrypting-secrets-for-the-rest-api.md` - Secret encryption for API
- **Discovering User Resources** `github-docs:rest/guides/discovering-resources-for-a-user.md` - User resource discovery
- **Rendering Data as Graphs** `github-docs:rest/guides/rendering-data-as-graphs.md` - Data visualization

---

### Issues, PRs & Projects (Priority)

#### Issues

- **Issues** `github-docs:rest/issues/issues.md` - Create, update, list issues
- **Issue Comments** `github-docs:rest/issues/comments.md` - Comment management
- **Issue Labels** `github-docs:rest/issues/labels.md` - Label operations
- **Issue Milestones** `github-docs:rest/issues/milestones.md` - Milestone management
- **Issue Assignees** `github-docs:rest/issues/assignees.md` - Assignee operations
- **Issue Events** `github-docs:rest/issues/events.md` - Issue event history
- **Issue Timeline** `github-docs:rest/issues/timeline.md` - Timeline events
- **Sub-issues** `github-docs:rest/issues/sub-issues.md` - Sub-issue relationships
- **Issue Dependencies** `github-docs:rest/issues/issue-dependencies.md` - Dependency tracking

#### Pull Requests

- **Pull Requests** `github-docs:rest/pulls/pulls.md` - PR operations
- **PR Review Comments** `github-docs:rest/pulls/comments.md` - Review comment management
- **PR Reviews** `github-docs:rest/pulls/reviews.md` - Review operations
- **PR Review Requests** `github-docs:rest/pulls/review-requests.md` - Request reviewers

#### Projects

- **Projects (v2)** `github-docs:rest/projects/projects.md` - Projects v2 API
- **Project Collaborators** `github-docs:rest/projects/collaborators.md` - Project access
- **Projects Classic** `github-docs:rest/projects-classic/projects.md` - Legacy project boards
- **Project Cards (Classic)** `github-docs:rest/projects-classic/cards.md` - Classic project cards
- **Project Columns (Classic)** `github-docs:rest/projects-classic/columns.md` - Classic project columns

#### Reactions

- **Reactions** `github-docs:rest/reactions/reactions.md` - Emoji reactions on issues/PRs

---

### Repositories & Branches (Priority)

#### Repositories

- **Repos** `github-docs:rest/repos/repos.md` - Repository CRUD operations
- **Repo Contents** `github-docs:rest/repos/contents.md` - File content operations
- **Repo Topics** `github-docs:rest/repos/topics.md` - Repository topics
- **Repo Tags** `github-docs:rest/repos/tags.md` - Tag management
- **Repo Forks** `github-docs:rest/repos/forks.md` - Fork operations
- **Repo Autolinks** `github-docs:rest/repos/autolinks.md` - Autolink references
- **Repo Rules** `github-docs:rest/repos/rules.md` - Repository rulesets
- **Repo Custom Properties** `github-docs:rest/repos/custom-properties.md` - Custom property values
- **Repo Webhooks** `github-docs:rest/repos/webhooks.md` - Webhook management

#### Branches

- **Branches** `github-docs:rest/branches/branches.md` - Branch operations
- **Branch Protection** `github-docs:rest/branches/branch-protection.md` - Protection rules

#### Commits

- **Commits** `github-docs:rest/commits/commits.md` - Commit information
- **Commit Comments** `github-docs:rest/commits/comments.md` - Commit comments
- **Commit Statuses** `github-docs:rest/commits/statuses.md` - Status checks

#### Git Data

- **Git Blobs** `github-docs:rest/git/blobs.md` - Blob objects
- **Git Commits** `github-docs:rest/git/commits.md` - Commit objects
- **Git Refs** `github-docs:rest/git/refs.md` - Reference management
- **Git Tags** `github-docs:rest/git/tags.md` - Tag objects
- **Git Trees** `github-docs:rest/git/trees.md` - Tree objects

#### Collaborators & Access

- **Collaborators** `github-docs:rest/collaborators/collaborators.md` - Repo collaborators
- **Repo Invitations** `github-docs:rest/collaborators/invitations.md` - Collaboration invites
- **Deploy Keys** `github-docs:rest/deploy-keys/deploy-keys.md` - Deploy key management

#### Releases

- **Releases** `github-docs:rest/releases/releases.md` - Release management
- **Release Assets** `github-docs:rest/releases/assets.md` - Release asset operations

---

### Organizations & Teams (Priority)

#### Organizations

- **Organizations** `github-docs:rest/orgs/orgs.md` - Org management
- **Org Members** `github-docs:rest/orgs/members.md` - Member management
- **Org Outside Collaborators** `github-docs:rest/orgs/outside-collaborators.md` - External collaborators
- **Org Webhooks** `github-docs:rest/orgs/webhooks.md` - Org webhook management
- **Org Custom Properties** `github-docs:rest/orgs/custom-properties.md` - Custom property definitions
- **Org Custom Roles** `github-docs:rest/orgs/custom-roles.md` - Custom role definitions
- **Org Rules** `github-docs:rest/orgs/rules.md` - Organization rulesets
- **Org Security Managers** `github-docs:rest/orgs/security-managers.md` - Security manager role
- **Org Blocking** `github-docs:rest/orgs/blocking.md` - User blocking
- **Org API Insights** `github-docs:rest/orgs/api-insights.md` - API usage insights

#### Teams

- **Teams** `github-docs:rest/teams/teams.md` - Team management
- **Team Members** `github-docs:rest/teams/members.md` - Team membership
- **Team Discussions** `github-docs:rest/teams/discussions.md` - Team discussions
- **Team Discussion Comments** `github-docs:rest/teams/discussion-comments.md` - Discussion comments

---

### Checks & Actions

#### Checks

- **Check Runs** `github-docs:rest/checks/runs.md` - Check run operations
- **Check Suites** `github-docs:rest/checks/suites.md` - Check suite management

#### Actions

- **Workflows** `github-docs:rest/actions/workflows.md` - Workflow operations
- **Workflow Runs** `github-docs:rest/actions/workflow-runs.md` - Run management
- **Workflow Jobs** `github-docs:rest/actions/workflow-jobs.md` - Job information
- **Artifacts** `github-docs:rest/actions/artifacts.md` - Artifact management
- **Secrets** `github-docs:rest/actions/secrets.md` - Secret management
- **Variables** `github-docs:rest/actions/variables.md` - Variable management
- **Permissions** `github-docs:rest/actions/permissions.md` - Actions permissions
- **Self-hosted Runners** `github-docs:rest/actions/self-hosted-runners.md` - Runner management
- **Runner Groups** `github-docs:rest/actions/self-hosted-runner-groups.md` - Runner group management
- **Cache** `github-docs:rest/actions/cache.md` - Cache operations
- **Hosted Runners** `github-docs:rest/actions/hosted-runners.md` - GitHub-hosted runners
- **OIDC** `github-docs:rest/actions/oidc.md` - OIDC configuration

---

### Security & Code Quality

#### Code Scanning

- **Code Scanning** `github-docs:rest/code-scanning/code-scanning.md` - Code scanning alerts
- **Alert Dismissal Requests** `github-docs:rest/code-scanning/alert-dismissal-requests.md` - Dismissal workflows

#### Secret Scanning

- **Secret Scanning** `github-docs:rest/secret-scanning/secret-scanning.md` - Secret alerts

#### Dependabot

- **Dependabot Alerts** `github-docs:rest/dependabot/alerts.md` - Vulnerability alerts
- **Dependabot Secrets** `github-docs:rest/dependabot/secrets.md` - Dependabot secrets
- **Dependabot Repo Access** `github-docs:rest/dependabot/repository-access.md` - Repository access

#### Security Advisories

- **Security Advisories** `github-docs:rest/security-advisories/security-advisories.md` - Advisory management
- **Repository Advisories** `github-docs:rest/security-advisories/repository-advisories.md` - Repo-specific advisories
- **Global Advisories** `github-docs:rest/security-advisories/global-advisories.md` - GitHub advisory database

#### Dependency Graph

- **Dependency Review** `github-docs:rest/dependency-graph/dependency-review.md` - Dependency diff
- **Dependency Submission** `github-docs:rest/dependency-graph/dependency-submission.md` - Submit dependencies
- **SBOMs** `github-docs:rest/dependency-graph/sboms.md` - Software bill of materials

#### Code Security

- **Security Configurations** `github-docs:rest/code-security/configurations.md` - Security config management

---

### Deployments & Environments

- **Deployments** `github-docs:rest/deployments/deployments.md` - Deployment operations
- **Deployment Statuses** `github-docs:rest/deployments/statuses.md` - Status updates
- **Environments** `github-docs:rest/deployments/environments.md` - Environment management
- **Branch Policies** `github-docs:rest/deployments/branch-policies.md` - Deployment branch policies
- **Protection Rules** `github-docs:rest/deployments/protection-rules.md` - Environment protection

---

### Apps & OAuth

#### GitHub Apps

- **Apps** `github-docs:rest/apps/apps.md` - App management
- **App Installations** `github-docs:rest/apps/installations.md` - Installation operations
- **App Webhooks** `github-docs:rest/apps/webhooks.md` - App webhook config
- **OAuth Apps** `github-docs:rest/apps/oauth-applications.md` - OAuth app management
- **Marketplace** `github-docs:rest/apps/marketplace.md` - Marketplace integration

#### OAuth Authorizations

- **OAuth Authorizations** `github-docs:rest/oauth-authorizations/oauth-authorizations.md` - Token management

---

### Users & Activity

#### Users

- **Users** `github-docs:rest/users/users.md` - User information
- **Emails** `github-docs:rest/users/emails.md` - Email management
- **Followers** `github-docs:rest/users/followers.md` - Follower operations
- **SSH Keys** `github-docs:rest/users/keys.md` - SSH key management
- **GPG Keys** `github-docs:rest/users/gpg-keys.md` - GPG key management
- **Blocking** `github-docs:rest/users/blocking.md` - User blocking
- **Social Accounts** `github-docs:rest/users/social-accounts.md` - Social media links

#### Activity

- **Events** `github-docs:rest/activity/events.md` - Event streams
- **Feeds** `github-docs:rest/activity/feeds.md` - Atom feeds
- **Notifications** `github-docs:rest/activity/notifications.md` - Notification management
- **Starring** `github-docs:rest/activity/starring.md` - Star operations
- **Watching** `github-docs:rest/activity/watching.md` - Watch operations

---

### Enterprise (Reference)

- **Enterprise Admin** `github-docs:rest/enterprise-admin/index.md` - Enterprise API overview
- **Audit Log** `github-docs:rest/enterprise-admin/audit-log.md` - Audit log access
- **SCIM** `github-docs:rest/enterprise-admin/scim.md` - SCIM provisioning
- **Licensing** `github-docs:rest/enterprise-admin/licensing.md` - License management
- **Enterprise Orgs** `github-docs:rest/enterprise-admin/orgs.md` - Org management
- **Enterprise Users** `github-docs:rest/enterprise-admin/users.md` - User management
- **Enterprise Rules** `github-docs:rest/enterprise-admin/rules.md` - Enterprise rulesets
- **Custom Properties** `github-docs:rest/enterprise-admin/custom-properties.md` - Enterprise properties
- **Enterprise Teams** `github-docs:rest/enterprise-teams/enterprise-teams.md` - Enterprise team management

---

### Other APIs

#### Search

- **Search** `github-docs:rest/search/search.md` - Search API

#### Webhooks

- **Webhooks** `github-docs:rest/webhooks/webhooks.md` - Webhook reference

#### Gists

- **Gists** `github-docs:rest/gists/gists.md` - Gist operations
- **Gist Comments** `github-docs:rest/gists/comments.md` - Gist comments

#### Packages

- **Packages** `github-docs:rest/packages/packages.md` - Package management

#### Pages

- **Pages** `github-docs:rest/pages/pages.md` - GitHub Pages

#### Codespaces

- **Codespaces** `github-docs:rest/codespaces/codespaces.md` - Codespace management
- **Codespace Secrets** `github-docs:rest/codespaces/secrets.md` - User secrets
- **Codespace Org Secrets** `github-docs:rest/codespaces/organization-secrets.md` - Org secrets

#### Rate Limit

- **Rate Limit** `github-docs:rest/rate-limit/rate-limit.md` - Check rate limit status

#### Meta

- **Meta** `github-docs:rest/meta/meta.md` - GitHub API metadata

---

## gh CLI

### Getting Started

- **About GitHub CLI** `github-docs:github-cli/github-cli/about-github-cli.md` - Introduction and capabilities
- **Quickstart** `github-docs:github-cli/github-cli/quickstart.md` - Installation and first commands
- **CLI Reference** `github-docs:github-cli/github-cli/github-cli-reference.md` - Command reference

### Advanced Usage

- **Using Multiple Accounts** `github-docs:github-cli/github-cli/using-multiple-accounts.md` - Multi-account configuration
- **Using Extensions** `github-docs:github-cli/github-cli/using-github-cli-extensions.md` - Installing and using extensions
- **Creating Extensions** `github-docs:github-cli/github-cli/creating-github-cli-extensions.md` - Building custom extensions

---

## Quick Reference

### Common Patterns

| Task | GraphQL | REST | gh CLI |
|------|---------|------|--------|
| List issues | `github-docs:graphql/reference/queries.md` | `github-docs:rest/issues/issues.md` | `gh issue list` |
| Create PR | `github-docs:graphql/reference/mutations.md` | `github-docs:rest/pulls/pulls.md` | `gh pr create` |
| Project items | `github-docs:graphql/guides/introduction-to-graphql.md` | `github-docs:rest/projects/projects.md` | `gh project` |
| Branch protection | N/A | `github-docs:rest/branches/branch-protection.md` | `gh api` |
| Org members | `github-docs:graphql/reference/objects.md` | `github-docs:rest/orgs/members.md` | `gh api` |

### Authentication Quick Links

- **REST Auth** `github-docs:rest/authentication/authenticating-to-the-rest-api.md`
- **GraphQL Rate Limits** `github-docs:graphql/overview/rate-limits-and-query-limits-for-the-graphql-api.md`
- **App Permissions** `github-docs:rest/authentication/permissions-required-for-github-apps.md`
