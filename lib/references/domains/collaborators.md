# Collaborators

**REST API only for mutations. GraphQL read-only. No CLI support.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✗ | ✓ | ✓ | ✓ | Via repository.collaborators |
| Get | ✗ | ✓ | ✓ | ✓ | Check permission level |
| Add | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Remove | ✗ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Check permission | ✗ | ✓ | ✓ | ✓ | Permission level for user |
| List invitations | ✗ | ✓ | ✗ | ✓ | Pending invites |
| Update invitation | ✗ | ✓ | ✗ | ✓ | Change permission |
| Delete invitation | ✗ | ✓ | ✗ | ✓ | Cancel invite |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| All | (Not available) | Use REST API |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/collaborators` | |
| Get | GET | `/repos/{owner}/{repo}/collaborators/{username}` | |
| Add | PUT | `/repos/{owner}/{repo}/collaborators/{username}` | Set permission level |
| Remove | DELETE | `/repos/{owner}/{repo}/collaborators/{username}` | |
| Check permission | GET | `/repos/{owner}/{repo}/collaborators/{username}/permission` | |
| List invitations | GET | `/repos/{owner}/{repo}/invitations` | Pending invites |
| Update invitation | PATCH | `/repos/{owner}/{repo}/invitations/{invitation_id}` | |
| Delete invitation | DELETE | `/repos/{owner}/{repo}/invitations/{invitation_id}` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.collaborators` | Read-only |
| Check permission | Query | `repository.collaborators.edges.permission` | |

**Note:** No GraphQL mutations for collaborator management. Use REST API for all write operations.
