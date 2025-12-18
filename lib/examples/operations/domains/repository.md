# Repository

**Full CLI support. REST and GraphQL both support most operations. Some operations blocked for safety.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | User or org repos |
| Get | ✓ | ✓ | ✓ | ✓ | |
| Create | ✓ | ✓ | ✓ | ✓ | |
| Update/Edit | ✓ | ✓ | ✓ | ✓ | Settings, description, visibility |
| Delete | ✓ | ✓ | ✗ | ✓ | ⊗ Blocked for safety |
| Archive | ✓ | ✗ | ✓ | ✓ | ⊗ Blocked for safety |
| Unarchive | ✓ | ✗ | ✓ | ✓ | |
| Fork | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Clone | ✓ | ✗ | ✗ | ✗ | CLI only (git operation) |
| Rename | ✓ | ✓ | ✓ | ✓ | Via PATCH or updateRepository |
| Transfer | ✗ | ✓ | ✗ | ✓ | ⊗ Blocked for safety |
| Sync (fork) | ✓ | ✓ | ✗ | ✓ | Sync fork with upstream |
| Update topics | ✗ | ✓ | ✓ | ✓ | Via updateTopics mutation |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh repo list [owner]` | List repos for user/org |
| Get | `gh repo view [repo]` | View repo details |
| Create | `gh repo create [name]` | Interactive or with flags |
| Edit | `gh repo edit [repo]` | Update settings |
| Delete | `gh repo delete [repo]` | ⊗ Blocked |
| Archive | `gh repo archive [repo]` | ⊗ Blocked |
| Unarchive | `gh repo unarchive [repo]` | |
| Fork | `gh repo fork [repo]` | |
| Clone | `gh repo clone [repo]` | |
| Rename | `gh repo rename [new-name]` | |
| Sync | `gh repo sync [repo]` | Sync fork with upstream |

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}`, `GET /user/repos`, `GET /orgs/{org}/repos`, `POST /user/repos`, `POST /orgs/{org}/repos`, `PATCH /repos/{owner}/{repo}`, `DELETE /repos/{owner}/{repo}`, `POST /repos/{owner}/{repo}/forks`, `POST /repos/{owner}/{repo}/transfer`, `POST /repos/{owner}/{repo}/merge-upstream`, `PUT /repos/{owner}/{repo}/topics` | `GET /repos`, `POST /user/repos`, `PATCH /repos/{owner}/{repo}`, `POST /forks`, `PUT /topics` |
| GraphQL | `repository`, `repositories` (queries), `createRepository`, `updateRepository`, `archiveRepository`, `unarchiveRepository`, `updateTopics` (mutations) | `query { repository }`, `mutation { createRepository }`, `mutation { updateRepository }`, `mutation { archiveRepository }` |

**Note:** No GraphQL mutation for delete, fork, or transfer. Archive/unarchive use REST-like patterns but via GraphQL mutations. Repository delete/transfer/archive blocked for safety - see `docs/operation-blocklist.md`.
