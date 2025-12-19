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

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/releases` | |
| Get by ID | GET | `/repos/{owner}/{repo}/releases/{release_id}` | |
| Get by tag | GET | `/repos/{owner}/{repo}/releases/tags/{tag}` | |
| Get latest | GET | `/repos/{owner}/{repo}/releases/latest` | |
| Create | POST | `/repos/{owner}/{repo}/releases` | |
| Update | PATCH | `/repos/{owner}/{repo}/releases/{release_id}` | |
| Delete | DELETE | `/repos/{owner}/{repo}/releases/{release_id}` | |
| Generate notes | POST | `/repos/{owner}/{repo}/releases/generate-notes` | |
| Upload asset | POST | `https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets` | Special endpoint |
| Update asset | PATCH | `/repos/{owner}/{repo}/releases/assets/{asset_id}` | Metadata only |
| Delete asset | DELETE | `/repos/{owner}/{repo}/releases/assets/{asset_id}` | |
| List assets | GET | `/repos/{owner}/{repo}/releases/{release_id}/assets` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.releases` | |
| Get | Query | `node(id:)` | Use `Release` type |
| Get latest | Query | `repository.latestRelease` | |

**Note:** GraphQL has no mutations for release management. Upload asset uses special `uploads.github.com` endpoint.
