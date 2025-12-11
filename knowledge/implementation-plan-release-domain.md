# Implementation Plan: Release Domain

> **Document ID:** IMPL-007
> **Created:** 2025-12-11
> **Status:** Planning
> **GitHub Issue:** #20

## Overview

Implement the Release domain for managing GitHub releases, tags, release assets, and auto-generated release notes.

## Design Decision

**Release domain will be Layer 2 primitives only** - No Layer 3 (Smart Application) functions needed.

**Rationale:**
- Well-structured CRUD operations
- gh CLI provides excellent native support for all common operations
- No complex configurations or context detection required
- Straightforward asset management
- Auto-generated release notes via REST API

## API Strategy

| Operation Category | Primary API | Reason |
|-------------------|-------------|---------|
| List releases | gh CLI (`gh release list --json`) | Native formatting, filtering |
| View release | gh CLI (`gh release view`) | Complete info with assets |
| Create release | gh CLI (`gh release create`) | Interactive or scripted, handles assets |
| Edit release | gh CLI (`gh release edit`) | Simple updates to metadata |
| Delete release | gh CLI (`gh release delete`) | Safe deletion with confirmation |
| Upload assets | gh CLI (`gh release upload`) | Handles file uploads |
| Download assets | gh CLI (`gh release download`) | Pattern matching support |
| Latest release | REST API | `/repos/{owner}/{repo}/releases/latest` |
| Release by tag | REST API | `/repos/{owner}/{repo}/releases/tags/{tag}` |
| Generate notes | REST API | `/repos/{owner}/{repo}/releases/generate-notes` |
| Delete assets | REST API | Not in gh CLI |

### Why We Use gh CLI Primarily

**gh CLI advantages:**
- Comprehensive release management (create, edit, delete, view, list)
- Asset upload/download with pattern matching
- Interactive and non-interactive modes
- Release notes editing support
- Draft and prerelease flags

**REST API for:**
- Auto-generating release notes
- Getting latest release programmatically
- Getting release by tag
- Deleting individual assets

**GraphQL limitations:**
- Limited mutation support (mainly draft releases)
- Asset operations not supported
- Less comprehensive than REST/CLI

## Release Concepts

### Release States

| State | Description | Usage |
|-------|-------------|-------|
| **Draft** | Unpublished, not visible publicly | Work in progress |
| **Prerelease** | Published, marked as not production-ready | Beta, RC versions |
| **Release** | Published, production-ready | Stable versions |
| **Latest** | Most recent non-prerelease | Auto-determined by GitHub |

### Release Components

- **Tag**: Git tag name (e.g., `v1.0.0`)
- **Name**: Display name (e.g., "Version 1.0.0")
- **Body**: Release notes (markdown)
- **Target**: Commit SHA or branch name
- **Assets**: Binaries, archives, packages attached to release

## Primitive Specification

### FETCH Primitives (5)

| Function | API | Purpose |
|----------|-----|---------|
| `fetch_release` | REST | Get release by ID |
| `fetch_release_by_tag` | REST | Get release by tag name |
| `fetch_latest_release` | REST | Get latest non-prerelease |
| `fetch_release_assets` | REST | Get assets for a release |
| `fetch_asset` | REST | Get single asset metadata |

**Signature pattern:**
```bash
fetch_release "owner" "repo" "release_id"
fetch_release_by_tag "owner" "repo" "v1.0.0"
fetch_latest_release "owner" "repo"
fetch_release_assets "owner" "repo" "release_id"
fetch_asset "owner" "repo" "asset_id"
```

### DISCOVER Primitives (3)

| Function | API | Purpose |
|----------|-----|---------|
| `discover_repo_releases` | gh CLI | List repository releases |
| `discover_release_assets` | gh CLI | List assets for a release |
| `discover_repo_tags` | REST | List repository tags |

**Signature pattern:**
```bash
discover_repo_releases "owner" "repo" [limit] [exclude_drafts] [exclude_prereleases]
discover_release_assets "owner" "repo" "tag_name"
discover_repo_tags "owner" "repo"
```

### LOOKUP Primitives (3)

| Function | API | Purpose |
|----------|-----|---------|
| `get_release_id` | REST | Get release ID by tag |
| `get_release_tag` | REST | Get tag name by release ID |
| `get_asset_id` | REST | Get asset ID by name |

**Signature pattern:**
```bash
get_release_id "owner" "repo" "v1.0.0"          # → release ID
get_release_tag "owner" "repo" "12345678"        # → tag name
get_asset_id "owner" "repo" "release_id" "binary.tar.gz"  # → asset ID
```

### FILTER Primitives (4)

| Function | Purpose |
|----------|---------|
| `filter_releases_by_prerelease` | Keep prereleases or stable only |
| `filter_releases_by_draft` | Keep drafts or published only |
| `filter_releases_by_tag_pattern` | Keep releases matching tag pattern |
| `filter_assets_by_name` | Keep assets matching name pattern |

**Input/Output:** JSON from stdin → filtered JSON to stdout

### FORMAT Primitives (4)

| Function | Purpose |
|----------|---------|
| `format_releases` | Tabular release list (tag, name, published, prerelease) |
| `format_release_detail` | Single release with complete metadata |
| `format_assets` | Tabular asset list (name, size, download count) |
| `format_release_notes` | Format release body as readable text |

### DETECT Primitives (4)

| Function | Returns | Purpose |
|----------|---------|---------|
| `detect_release_exists` | "true" \| "false" | Check if release exists by tag |
| `detect_is_prerelease` | "true" \| "false" | Check if release is prerelease |
| `detect_is_draft` | "true" \| "false" | Check if release is draft |
| `detect_is_latest` | "true" \| "false" | Check if release is latest |

### MUTATE Primitives (8)

| Function | API | Purpose |
|----------|-----|---------|
| `create_release` | gh CLI | Create release with assets |
| `update_release` | gh CLI | Update release metadata |
| `delete_release` | gh CLI | Delete release and its assets |
| `upload_release_asset` | gh CLI | Upload asset to release |
| `download_release_asset` | gh CLI | Download asset from release |
| `delete_release_asset` | REST | Delete single asset |
| `publish_draft_release` | REST | Convert draft to published |
| `create_draft_release` | gh CLI | Create draft release |

**Signature pattern:**
```bash
create_release "owner" "repo" "v1.0.0" "Release title" "notes.md" [--draft] [--prerelease]
update_release "owner" "repo" "v1.0.0" [--title "New title"] [--notes "New notes"]
delete_release "owner" "repo" "v1.0.0" [--yes]
upload_release_asset "owner" "repo" "v1.0.0" "binary.tar.gz"
download_release_asset "owner" "repo" "v1.0.0" "binary.tar.gz"
delete_release_asset "owner" "repo" "asset_id"
publish_draft_release "owner" "repo" "release_id"
create_draft_release "owner" "repo" "v1.0.0" "Draft title" "notes.md"
```

### UTILITY Primitives (2)

| Function | API | Purpose |
|----------|-----|---------|
| `generate_release_notes` | REST | Auto-generate release notes from commits |
| `download_release_tarball` | REST | Download source code tarball |

**Signature pattern:**
```bash
generate_release_notes "owner" "repo" "v1.0.0" [previous_tag]
download_release_tarball "owner" "repo" "v1.0.0" "output.tar.gz"
```

## Total: 33 Primitives

- FETCH: 5 (release by ID, by tag, latest, assets, asset)
- DISCOVER: 3 (list releases, list assets, list tags)
- LOOKUP: 3 (get IDs from names/tags)
- FILTER: 4 (by prerelease, draft, tag pattern, asset name)
- FORMAT: 4 (releases, detail, assets, notes)
- DETECT: 4 (exists, is prerelease, is draft, is latest)
- MUTATE: 8 (create, update, delete, upload, download, delete asset, publish, create draft)
- UTILITY: 2 (generate notes, download tarball)

## REST API Endpoints Reference

### Releases

- `GET /repos/{owner}/{repo}/releases` - List releases
- `GET /repos/{owner}/{repo}/releases/{id}` - Get release
- `GET /repos/{owner}/{repo}/releases/latest` - Get latest release
- `GET /repos/{owner}/{repo}/releases/tags/{tag}` - Get release by tag
- `POST /repos/{owner}/{repo}/releases` - Create release
- `PATCH /repos/{owner}/{repo}/releases/{id}` - Update release
- `DELETE /repos/{owner}/{repo}/releases/{id}` - Delete release
- `POST /repos/{owner}/{repo}/releases/generate-notes` - Generate notes

### Assets

- `GET /repos/{owner}/{repo}/releases/{id}/assets` - List assets
- `GET /repos/{owner}/{repo}/releases/assets/{asset_id}` - Get asset
- `POST /repos/{owner}/{repo}/releases/{id}/assets` - Upload asset
- `PATCH /repos/{owner}/{repo}/releases/assets/{asset_id}` - Update asset
- `DELETE /repos/{owner}/{repo}/releases/assets/{asset_id}` - Delete asset

### Download

- `GET /repos/{owner}/{repo}/tarball/{ref}` - Download tarball
- `GET /repos/{owner}/{repo}/zipball/{ref}` - Download zipball

## gh CLI Commands

```bash
# List releases
gh release list -R owner/repo --json tagName,name,publishedAt,isPrerelease,isDraft
gh release list --exclude-drafts --exclude-pre-releases --limit 10

# View release
gh release view v1.0.0 -R owner/repo --json tagName,name,body,assets,publishedAt

# Create release
gh release create v1.0.0 -R owner/repo --title "Version 1.0.0" --notes "Release notes"
gh release create v1.0.0 --draft --prerelease --notes-file CHANGELOG.md
gh release create v1.0.0 ./dist/*.tar.gz  # With assets

# Edit release
gh release edit v1.0.0 -R owner/repo --title "New title" --notes "Updated notes"
gh release edit v1.0.0 --draft=false  # Publish draft

# Delete release
gh release delete v1.0.0 -R owner/repo --yes

# Upload assets
gh release upload v1.0.0 binary.tar.gz checksums.txt -R owner/repo

# Download assets
gh release download v1.0.0 -R owner/repo  # All assets
gh release download v1.0.0 --pattern "*.tar.gz"  # Matching pattern
```

## GraphQL Queries

GraphQL support for releases is limited but useful for read operations:

```graphql
query($owner: String!, $repo: String!, $tagName: String!) {
  repository(owner: $owner, name: $repo) {
    release(tagName: $tagName) {
      id
      name
      tagName
      description
      createdAt
      publishedAt
      isDraft
      isPrerelease
      isLatest
      releaseAssets(first: 10) {
        nodes {
          id
          name
          downloadUrl
          downloadCount
          size
        }
      }
    }
  }
}
```

## Data Structures

### Release Object

```json
{
  "id": 123456,
  "node_id": "RE_kwDOAbc123==",
  "tag_name": "v1.0.0",
  "target_commitish": "main",
  "name": "Version 1.0.0",
  "body": "## Changes\n- Feature A\n- Bug fix B",
  "draft": false,
  "prerelease": false,
  "created_at": "2023-01-15T10:00:00Z",
  "published_at": "2023-01-15T12:00:00Z",
  "updated_at": "2023-01-15T12:00:00Z",
  "author": {
    "login": "octocat",
    "id": 1
  },
  "assets": [
    {
      "id": 234567,
      "name": "app-v1.0.0.tar.gz",
      "label": "Application binary",
      "content_type": "application/gzip",
      "size": 12345678,
      "download_count": 42,
      "created_at": "2023-01-15T11:00:00Z",
      "updated_at": "2023-01-15T11:00:00Z",
      "browser_download_url": "https://github.com/owner/repo/releases/download/v1.0.0/app-v1.0.0.tar.gz"
    }
  ],
  "tarball_url": "https://api.github.com/repos/owner/repo/tarball/v1.0.0",
  "zipball_url": "https://api.github.com/repos/owner/repo/zipball/v1.0.0"
}
```

### Asset Object

```json
{
  "id": 234567,
  "node_id": "RA_kwDOAbc234==",
  "name": "app-v1.0.0.tar.gz",
  "label": "Application binary",
  "content_type": "application/gzip",
  "size": 12345678,
  "download_count": 42,
  "created_at": "2023-01-15T11:00:00Z",
  "updated_at": "2023-01-15T11:00:00Z",
  "browser_download_url": "https://github.com/owner/repo/releases/download/v1.0.0/app-v1.0.0.tar.gz",
  "uploader": {
    "login": "octocat",
    "id": 1
  }
}
```

## Files to Create

1. **`lib/github/gh-release-functions.sh`** (~700 lines)
   - 33 primitive functions
   - Follow ARCH-001 Layer 2 patterns
   - Use gh CLI where possible, REST for special operations

2. **`lib/github/gh-release-graphql-queries.yaml`** (~150 lines)
   - Fetch release query
   - Fetch latest release query
   - List releases query
   - Release with assets query

3. **`lib/github/gh-release-jq-filters.yaml`** (~200 lines)
   - Format filters: `format_releases_list`, `format_release_detail`, `format_assets_list`
   - Extract filters: `extract_tag_names`, `extract_asset_urls`, `extract_download_counts`
   - Filter operations: `filter_by_prerelease`, `filter_by_draft`, `filter_by_tag_pattern`
   - Summary filters: `release_summary`, `download_stats`

4. **`lib/github/gh-release-index.md`** (~800 lines)
   - Quick reference table
   - Function details with examples
   - jq filters reference
   - Composition examples (CI/CD workflows)
   - Release best practices

## Why No Layer 3 Functions?

Release domain **does not need** Smart Application functions because:

1. **No context detection** - Release identification is explicit (tag name or ID)
2. **No schema variations** - Same structure across all repos
3. **gh CLI is comprehensive** - Handles all common workflows
4. **Simple CRUD** - Create, read, update, delete operations
5. **No complex configurations** - Straightforward metadata (tag, name, notes)

## Release Best Practices

### Semantic Versioning

Follow SemVer (MAJOR.MINOR.PATCH):

```bash
# Breaking changes
create_release "owner" "repo" "v2.0.0" "Major Release" "BREAKING.md"

# New features (backward compatible)
create_release "owner" "repo" "v1.1.0" "Feature Release" "CHANGELOG.md"

# Bug fixes
create_release "owner" "repo" "v1.0.1" "Patch Release" "FIXES.md"
```

### Release Workflow

1. **Tag the commit**: `git tag v1.0.0`
2. **Create draft**: `create_draft_release "owner" "repo" "v1.0.0"`
3. **Upload assets**: `upload_release_asset "owner" "repo" "v1.0.0" "binary.tar.gz"`
4. **Review draft**: `gh release view v1.0.0 --web`
5. **Publish**: `publish_draft_release "owner" "repo" "release_id"`

### Auto-Generated Release Notes

```bash
# Generate notes between tags
NOTES=$(generate_release_notes "owner" "repo" "v1.1.0" "v1.0.0")
create_release "owner" "repo" "v1.1.0" "Version 1.1.0" "$NOTES"
```

### Prerelease Strategy

```bash
# Beta releases
create_release "owner" "repo" "v2.0.0-beta.1" "Beta 1" "BETA_NOTES.md" --prerelease

# Release candidates
create_release "owner" "repo" "v2.0.0-rc.1" "RC 1" "RC_NOTES.md" --prerelease

# Final release
create_release "owner" "repo" "v2.0.0" "Version 2.0.0" "RELEASE_NOTES.md"
```

## Implementation Tasks

- [x] Research GitHub Releases REST API
- [x] Research gh CLI release capabilities
- [x] Research GraphQL release queries
- [x] Design primitive specification
- [ ] Create `gh-release-functions.sh` with 33 primitives
- [ ] Create `gh-release-graphql-queries.yaml`
- [ ] Create `gh-release-jq-filters.yaml`
- [ ] Create `gh-release-index.md`
- [ ] Update `CLAUDE.md` with Release domain section
- [ ] Test key workflows

## Acceptance Criteria

1. All 33 primitives implemented and tested
2. Functions follow ARCH-001 Layer 2 patterns:
   - Explicit parameters (owner, repo, tag, release_id)
   - Stdin→stdout for data flow (filters, formatters)
   - No context detection
3. Error handling: stderr for errors, proper exit codes
4. Composition works: `discover_repo_releases | filter_releases_by_prerelease "false" | format_releases`
5. Documentation complete in gh-release-index.md
6. Asset upload/download tested
7. Integration with existing domains (repos, milestones)

## Related Documents

- **ARCH-001:** `knowledge/architecture-principles.md` - Layer 2 primitive patterns
- **ARCH-002:** `knowledge/domain-segmentation.md` - Domain boundaries
- **Issue #20:** P2 Release Domain Implementation
- **Related:** Milestone domain (release planning), Action domain (CI/CD automation)
