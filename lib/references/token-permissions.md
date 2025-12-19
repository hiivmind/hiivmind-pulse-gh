# Token Permissions Reference

This document lists required token permissions for each GitHub API domain.

**Source:** [GitHub Fine-grained PAT Permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)

## Quick Reference

| Domain | Classic OAuth | Fine-grained (Read) | Fine-grained (Write) |
|--------|--------------|---------------------|----------------------|
| issues | `repo` | Issues: Read | Issues: Read and write |
| pull-requests | `repo` | Pull requests: Read | Pull requests: Read and write |
| milestones | `repo` | Issues: Read | Issues: Read and write |
| labels | `repo` | Issues: Read | Issues: Read and write |
| reactions | `repo` | Issues/PRs: Read | Issues/PRs: Read and write |
| projects-v2 | `project`, `read:project` | Projects: Read | Projects: Read and write |
| actions | `repo` | Actions: Read | Actions: Read and write |
| secrets | `repo` | — | Secrets: Read and write |
| variables | `repo` | Variables: Read | Variables: Read and write |
| releases | `repo` | Contents: Read | Contents: Read and write |
| branch-protection | `repo` | Administration: Read | Administration: Read and write |
| rulesets | `repo` | Administration: Read | Administration: Read and write |
| checks | `repo` | Commit statuses: Read | Commit statuses: Read and write |
| deployments | `repo` | Deployments: Read | Deployments: Read and write |
| environments | `repo` | Environments: Read | Environments: Read and write |
| webhooks | `admin:repo_hook` | Webhooks: Read | Webhooks: Read and write |
| code-scanning | `repo`, `security_events` | Code scanning alerts: Read | Code scanning alerts: Read and write |
| secret-scanning | `repo`, `security_events` | Secret scanning alerts: Read | Secret scanning alerts: Read and write |
| dependabot | `repo`, `security_events` | Dependabot alerts: Read | Dependabot alerts: Read and write |
| notifications | `notifications` | Metadata: Read | — |
| repository | `repo` | Metadata: Read | Administration: Read and write |
| collaborators | `repo` | Metadata: Read | Administration: Read and write |
| teams | `read:org` | Members: Read | Members: Read and write |
| gists | `gist` | Gists: Read | Gists: Read and write |
| search | `repo` | Metadata: Read | — |

## Domain Groups

### Issues, Milestones, Labels, Reactions

**Classic OAuth:** `repo`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Issues: Read |
| Write | Issues: Read and write |

**Covers:** Create/update/close issues, manage milestones, add/remove labels, add reactions.

**Note:** Reactions on PRs require `Pull requests` permission instead.

### Pull Requests

**Classic OAuth:** `repo`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Pull requests: Read |
| Write | Pull requests: Read and write |

**Covers:** Create/update/merge PRs, reviews, comments.

### Projects v2

**Classic OAuth:** `project`, `read:project`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Projects: Read |
| Write | Projects: Read and write |

**Note:** Organization-level permission. For org projects, also requires `read:org`.

### Actions, Secrets, Variables

**Classic OAuth:** `repo`

| Domain | Read | Write |
|--------|------|-------|
| actions | Actions: Read | Actions: Read and write |
| secrets | — | Secrets: Read and write |
| variables | Variables: Read | Variables: Read and write |

**Note:** Secrets cannot be read (only listed). Set/delete requires write.

### Releases

**Classic OAuth:** `repo`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Contents: Read |
| Write | Contents: Read and write |

**Covers:** Create/update/delete releases, upload assets.

### Branch Protection & Rulesets

**Classic OAuth:** `repo` (with admin access to repository)

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Administration: Read |
| Write | Administration: Read and write |

**Note:** Requires repository admin role for write operations.

### Checks & Commit Statuses

**Classic OAuth:** `repo`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Commit statuses: Read |
| Write | Commit statuses: Read and write |

**Note:** Creating check runs requires a GitHub App, not a PAT.

### Deployments & Environments

**Classic OAuth:** `repo`

| Domain | Read | Write |
|--------|------|-------|
| deployments | Deployments: Read | Deployments: Read and write |
| environments | Environments: Read | Environments: Read and write |

### Webhooks

**Classic OAuth:** `admin:repo_hook`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Webhooks: Read |
| Write | Webhooks: Read and write |

**Note:** Different from other repo permissions. Uses `admin:repo_hook` scope.

### Security Alerts

**Classic OAuth:** `repo`, `security_events`

| Domain | Read | Write |
|--------|------|-------|
| code-scanning | Code scanning alerts: Read | Code scanning alerts: Read and write |
| secret-scanning | Secret scanning alerts: Read | Secret scanning alerts: Read and write |
| dependabot | Dependabot alerts: Read | Dependabot alerts: Read and write |

**Note:** Requires both `repo` and `security_events` scopes for classic tokens.

### Repository & Collaborators

**Classic OAuth:** `repo`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Metadata: Read |
| Write | Administration: Read and write |

**Covers:** Repository settings, adding/removing collaborators.

### Teams

**Classic OAuth:** `read:org` (read), `admin:org` (write)

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Members: Read |
| Write | Members: Read and write |

**Note:** Organization-level permission.

### Notifications

**Classic OAuth:** `notifications`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Metadata: Read |
| Write | — |

**Note:** No fine-grained write permission. Notifications are managed via classic scopes.

### Gists

**Classic OAuth:** `gist`

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Gists: Read |
| Write | Gists: Read and write |

### Search

**Classic OAuth:** `repo` (for private repos)

| Access | Fine-grained Permission |
|--------|------------------------|
| Read | Metadata: Read |
| Write | — |

**Note:** Search is read-only. Private repo search requires repo access.
