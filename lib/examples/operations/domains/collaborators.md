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

## Corpus Lookup Guide

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/collaborators`, `GET /collaborators/{username}`, `PUT /collaborators/{username}`, `DELETE /collaborators/{username}`, `GET /collaborators/{username}/permission`, `GET /repos/{owner}/{repo}/invitations`, `PATCH /invitations/{invitation_id}`, `DELETE /invitations/{invitation_id}` | `GET /collaborators`, `PUT /collaborators/{username}`, `permission`, `invitations` |
| GraphQL | `repository { collaborators }` (read-only query) | `query { repository { collaborators { edges { permission } } } }` |

**Note:** No GraphQL mutations for collaborator management. Use REST API for all write operations.
