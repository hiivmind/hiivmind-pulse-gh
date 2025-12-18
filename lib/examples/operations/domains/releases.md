# Releases

**Hybrid: Read via REST + GraphQL, mutations via REST + gh CLI only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All support reading |
| Get by ID | ✓ | ✓ | ✓ | ✓ | All support reading |
| Get by tag | ✓ | ✓ | ✗ | ✓ | GraphQL requires ID lookup first |
| Get latest | ✓ | ✓ | ✓ | ✓ | All support reading |
| Create | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Upload asset | ✓ | ✓ | ✗ | ✓ | Special uploads.github.com endpoint |
| Update asset | ✗ | ✓ | ✗ | ✓ | Metadata only, no CLI support |
| Delete asset | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Generate notes | ✗ | ✓ | ✗ | ✓ | REST only, no CLI direct support |
| Verify attestation | ✓ | ✗ | ✗ | ✓ | CLI only, no REST endpoint |

## CLI Command Reference

| Operation | Command |
|-----------|---------|
| List | `gh release list` |
| Get | `gh release view {tag}` |
| Create | `gh release create {tag}` |
| Update | `gh release edit {tag}` |
| Delete | `gh release delete {tag}` |
| Upload asset | `gh release upload {tag} {file}` |
| Delete asset | `gh release delete-asset {tag} {asset-name}` |
| Download | `gh release download {tag}` |
| Verify attestation | `gh release verify {tag}` |

## Corpus Lookup Guide

| API | Endpoints/Queries | Search Keywords |
|-----|-------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/releases`, `GET /releases/{release_id}`, `GET /releases/tags/{tag}`, `GET /releases/latest`, `POST /releases`, `PATCH /releases/{release_id}`, `DELETE /releases/{release_id}`, `POST /releases/generate-notes`, `POST https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets` | `GET /releases`, `POST /releases`, `tag_name`, `target_commitish`, `uploads.github.com`, `generate-notes` |
| GraphQL | `releases` (query), `release` (query) - No mutations available | `query { repository { releases { edges { node } } } }` |

**Note:** GraphQL has no mutations for release management. Upload asset uses special `uploads.github.com` endpoint.
