# Blocked Operations

Operations that are too dangerous to perform via automation.

## Blocked Operations Table

| Resource | Operation | Reason | Alternative |
|----------|-----------|--------|-------------|
| Repository | delete | Irreversible data loss | Archive instead |
| Repository | transfer | Ownership change | Manual via UI |
| Repository | archive | Can break CI/CD workflows | Manual via UI |
| Organization | delete | Catastrophic data loss | Manual via UI |
| Organization | remove all members | Bulk dangerous operation | Remove individually |
| Branch | delete default | Breaks repository | Change default first |
| Release | delete all | Bulk data loss | Delete individually |

## Handling Blocked Requests

When a user requests a blocked operation:

1. **Explain** - "This operation is blocked for safety: [reason]"
2. **Offer alternative** - If available (e.g., "Use archive instead of delete")
3. **Suggest manual action** - "For this operation, please use the GitHub web UI"

**Do not proceed** with blocked operations under any circumstances.

## Why These Operations Are Blocked

### Repository Deletion
Deleting a repository removes all code, issues, pull requests, wikis, and releases permanently. There is no undo. Even with backups, reconstructing a repository is extremely difficult.

### Repository Transfer
Transferring repository ownership changes who controls the code. This should be a deliberate decision made by a human through the GitHub interface.

### Repository Archive
Archiving makes a repository read-only, which can break CI/CD pipelines, webhooks, and dependent workflows. While reversible, the disruption can be significant.

### Organization Deletion
Deleting an organization removes all repositories, teams, and settings. This is catastrophic and should never be automated.

### Bulk Member Removal
Removing all members from an organization is almost certainly not intentional. Individual removals are allowed; bulk operations are blocked.

### Default Branch Deletion
Deleting the default branch breaks the repository for all users. The default branch should be changed first if a different branch is desired.

### Bulk Release Deletion
Deleting all releases removes versioned artifacts that users may depend on. Individual release deletion is allowed; bulk operations are blocked.

## Defense in Depth

This blocklist is enforced at two levels:

1. **Skill-level** (soft) - The gateway command and operations skill check this blocklist before attempting operations
2. **Hook-level** (hard) - A PreToolUse hook intercepts Bash commands and blocks dangerous patterns at execution time

The hook provides a safety net even if:
- The LLM ignores skill instructions
- Users bypass the gateway with direct `gh api` calls
- Edge cases slip through natural language detection

## Related Files

- `hooks/hooks.json` - PreToolUse hook configuration
- `hooks/validate-gh-operation.sh` - Command hook script
- `commands/hiivmind-pulse-gh.md` - Gateway blocked operations check
