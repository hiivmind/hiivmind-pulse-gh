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
| Set default | ✓ | ✗ | ✗ | ✗ | CLI only — set default repo |
| Autolink list | ✓ | ✓ | ✗ | ✓ | |
| Autolink create | ✓ | ✓ | ✗ | ✓ | |
| Autolink delete | ✓ | ✓ | ✗ | ✓ | |
| Autolink view | ✓ | ✓ | ✗ | ✓ | |
| Deploy key list | ✓ | ✓ | ✗ | ✓ | |
| Deploy key add | ✓ | ✓ | ✗ | ✓ | |
| Deploy key delete | ✓ | ✓ | ✗ | ✓ | |

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
| Set default | `gh repo set-default [repo]` | Set default repo for commands |
| Autolink list | `gh repo autolink list` | List autolink references |
| Autolink create | `gh repo autolink create {prefix} {url}` | Create autolink reference |
| Autolink delete | `gh repo autolink delete {id}` | Delete autolink reference |
| Autolink view | `gh repo autolink view {id}` | View autolink reference |
| Deploy key list | `gh repo deploy-key list` | List deploy keys |
| Deploy key add | `gh repo deploy-key add {key-file}` | Add deploy key |
| Deploy key delete | `gh repo deploy-key delete {id}` | Delete deploy key |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List (user) | GET | `/user/repos` | Authenticated user's repos |
| List (org) | GET | `/orgs/{org}/repos` | |
| Get | GET | `/repos/{owner}/{repo}` | |
| Create (user) | POST | `/user/repos` | |
| Create (org) | POST | `/orgs/{org}/repos` | |
| Update | PATCH | `/repos/{owner}/{repo}` | |
| Delete | DELETE | `/repos/{owner}/{repo}` | ⊗ Blocked |
| Fork | POST | `/repos/{owner}/{repo}/forks` | |
| Transfer | POST | `/repos/{owner}/{repo}/transfer` | ⊗ Blocked |
| Sync fork | POST | `/repos/{owner}/{repo}/merge-upstream` | |
| Update topics | PUT | `/repos/{owner}/{repo}/topics` | |
| Autolink list | GET | `/repos/{owner}/{repo}/autolinks` | |
| Autolink create | POST | `/repos/{owner}/{repo}/autolinks` | |
| Autolink get | GET | `/repos/{owner}/{repo}/autolinks/{id}` | |
| Autolink delete | DELETE | `/repos/{owner}/{repo}/autolinks/{id}` | |
| Deploy key list | GET | `/repos/{owner}/{repo}/keys` | |
| Deploy key add | POST | `/repos/{owner}/{repo}/keys` | |
| Deploy key get | GET | `/repos/{owner}/{repo}/keys/{key_id}` | |
| Deploy key delete | DELETE | `/repos/{owner}/{repo}/keys/{key_id}` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| Get | Query | `repository` | |
| List | Query | `user.repositories` or `organization.repositories` | |
| Create | Mutation | `createRepository` | |
| Update | Mutation | `updateRepository` | |
| Archive | Mutation | `archiveRepository` | ⊗ Blocked |
| Unarchive | Mutation | `unarchiveRepository` | |
| Update topics | Mutation | `updateTopics` | |

**Note:** No GraphQL mutation for delete, fork, or transfer. See `lib/references/operation-blocklist.md` for blocked operations.

## Post-Create Operations

### Adding Git Remote (SSH Default)

**CRITICAL:** When adding a git remote after creating a repository, always use SSH format:

```bash
# ✅ CORRECT - SSH format (recommended)
git remote add origin git@github.com:owner/repo.git

# ❌ AVOID - HTTPS format (requires credential manager)
git remote add origin https://github.com/owner/repo.git
```

**Why SSH is preferred:**
- Works silently with SSH keys (no interactive prompts)
- Doesn't require credential manager configuration
- Standard for CLI/terminal workflows
- GitHub's recommended approach for developers

**Converting HTTPS to SSH:**
```bash
git remote set-url origin git@github.com:owner/repo.git
```

**Complete post-create workflow:**
```bash
# After: gh repo create owner/repo --public
git remote add origin git@github.com:owner/repo.git
git push -u origin main
```

**See:** `lib/patterns/workspace-detection.md` for full SSH best practices
