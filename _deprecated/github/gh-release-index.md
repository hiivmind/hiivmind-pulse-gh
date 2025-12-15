# GitHub Releases Domain - Function Index

> **Domain:** Release Management
> **Layer:** 2 (Primitives)
> **Functions:** 33 primitives across 8 types
> **Dependencies:** gh CLI, jq, GraphQL (optional)

## Overview

The Release domain provides primitives for managing GitHub releases, tags, assets, and auto-generated release notes.

**Key Characteristics:**
- **Multi-state** - Draft, prerelease, and published releases
- **Asset management** - Upload, download, and delete release assets
- **Auto-generated notes** - Create release notes from commits
- **gh CLI primary** - Comprehensive CLI support for all operations
- **Semantic versioning** - Support for SemVer tagging

---

## Quick Reference

| Type | Count | Functions |
|------|-------|-----------|
| **FETCH** | 5 | Get single release, latest, by tag, assets |
| **DISCOVER** | 3 | List releases, assets, tags |
| **LOOKUP** | 3 | Get IDs from names/tags |
| **FILTER** | 4 | By prerelease, draft, tag pattern, asset name |
| **FORMAT** | 4 | Tabular lists, detail view, release notes |
| **DETECT** | 4 | Check exists, prerelease, draft, latest |
| **MUTATE** | 8 | Create, update, delete, upload, download |
| **UTILITY** | 2 | Generate notes, download tarball |

---

## FETCH Primitives (5)

Retrieve single release or asset.

### `fetch_release`

Get release by ID.

\`\`\`bash
fetch_release "owner" "repo" "release_id"
\`\`\`

### `fetch_release_by_tag`

Get release by tag name.

\`\`\`bash
fetch_release_by_tag "owner" "repo" "v1.0.0"
\`\`\`

**Returns:**
\`\`\`json
{
  "id": 123456,
  "tag_name": "v1.0.0",
  "name": "Version 1.0.0",
  "body": "## Changes\\n- Feature A\\n- Bug fix B",
  "draft": false,
  "prerelease": false,
  "published_at": "2023-01-15T12:00:00Z",
  "assets": [...]
}
\`\`\`

### `fetch_latest_release`

Get latest non-prerelease.

\`\`\`bash
fetch_latest_release "owner" "repo"
\`\`\`

### `fetch_release_assets`

Get assets for a release.

\`\`\`bash
fetch_release_assets "owner" "repo" "release_id"
\`\`\`

### `fetch_asset`

Get single asset metadata.

\`\`\`bash
fetch_asset "owner" "repo" "asset_id"
\`\`\`

---

## DISCOVER Primitives (3)

List releases, assets, or tags.

### `discover_repo_releases`

List repository releases.

\`\`\`bash
discover_repo_releases "owner" "repo" [limit] [exclude_drafts] [exclude_prereleases]
\`\`\`

**Examples:**
\`\`\`bash
# List all releases
discover_repo_releases "octocat" "hello-world"

# List only stable releases (no drafts or prereleases)
discover_repo_releases "octocat" "hello-world" 10 "true" "true"

# List with custom limit
discover_repo_releases "octocat" "hello-world" 50
\`\`\`

### `discover_release_assets`

List assets for a release.

\`\`\`bash
discover_release_assets "owner" "repo" "v1.0.0"
\`\`\`

### `discover_repo_tags`

List repository tags.

\`\`\`bash
discover_repo_tags "owner" "repo" [per_page] [page]
\`\`\`

---

## LOOKUP Primitives (3)

Resolve IDs and names.

### `get_release_id`

Get release ID by tag name.

\`\`\`bash
RELEASE_ID=\$(get_release_id "octocat" "hello-world" "v1.0.0")
\`\`\`

### `get_release_tag`

Get tag name by release ID.

\`\`\`bash
TAG_NAME=\$(get_release_tag "octocat" "hello-world" "123456")
\`\`\`

### `get_asset_id`

Get asset ID by name.

\`\`\`bash
ASSET_ID=\$(get_asset_id "octocat" "hello-world" "release_id" "binary.tar.gz")
\`\`\`

---

## FILTER Primitives (4)

Transform/filter JSON data (stdin → stdout).

### `filter_releases_by_prerelease`

Filter by prerelease status.

\`\`\`bash
# Get only prereleases
discover_repo_releases "octocat" "hello-world" | filter_releases_by_prerelease "true"

# Get only stable releases
discover_repo_releases "octocat" "hello-world" | filter_releases_by_prerelease "false"
\`\`\`

### `filter_releases_by_draft`

Filter by draft status.

\`\`\`bash
# Get only drafts
discover_repo_releases "octocat" "hello-world" | filter_releases_by_draft "true"
\`\`\`

### `filter_releases_by_tag_pattern`

Filter by tag pattern (regex).

\`\`\`bash
# Get all v2.x.x releases
discover_repo_releases "octocat" "hello-world" | filter_releases_by_tag_pattern "^v2\\."
\`\`\`

### `filter_assets_by_name`

Filter assets by name pattern.

\`\`\`bash
discover_release_assets "octocat" "hello-world" "v1.0.0" | filter_assets_by_name "\\.tar\\.gz$"
\`\`\`

---

## FORMAT Primitives (4)

Transform JSON to human-readable output.

### `format_releases`

Format releases as table.

\`\`\`bash
discover_repo_releases "octocat" "hello-world" | format_releases
\`\`\`

**Output:**
\`\`\`
TAG       NAME            PUBLISHED              PRERELEASE  DRAFT  LATEST
v1.0.0    Version 1.0.0   2023-01-15T12:00:00Z   false       false  true
v1.0.0-rc Release Cand.  2023-01-10T10:00:00Z   true        false  false
\`\`\`

### `format_release_detail`

Format single release with details.

\`\`\`bash
fetch_release_by_tag "octocat" "hello-world" "v1.0.0" | format_release_detail
\`\`\`

### `format_assets`

Format assets as table.

\`\`\`bash
discover_release_assets "octocat" "hello-world" "v1.0.0" | format_assets
\`\`\`

### `format_release_notes`

Extract release notes.

\`\`\`bash
fetch_release_by_tag "octocat" "hello-world" "v1.0.0" | format_release_notes
\`\`\`

---

## DETECT Primitives (4)

Determine release properties.

### `detect_release_exists`

Check if release exists.

\`\`\`bash
if [[ "\$(detect_release_exists "octocat" "hello-world" "v1.0.0")" == "true" ]]; then
    echo "Release exists"
fi
\`\`\`

### `detect_is_prerelease`

Check if release is prerelease.

\`\`\`bash
detect_is_prerelease "octocat" "hello-world" "v2.0.0-beta.1"
\`\`\`

### `detect_is_draft`

Check if release is draft.

\`\`\`bash
detect_is_draft "octocat" "hello-world" "v1.0.0"
\`\`\`

### `detect_is_latest`

Check if release is latest.

\`\`\`bash
detect_is_latest "octocat" "hello-world" "v1.0.0"
\`\`\`

---

## MUTATE Primitives (8)

Create, update, or delete releases and assets.

### `create_release`

Create release with optional assets.

\`\`\`bash
# Basic release
create_release "octocat" "hello-world" "v1.0.0" --title "Version 1.0.0" --notes "Release notes"

# With notes file
create_release "octocat" "hello-world" "v1.0.0" --title "v1.0.0" --notes-file CHANGELOG.md

# Draft prerelease with assets
create_release "octocat" "hello-world" "v2.0.0-beta.1" --title "Beta 1" \\
    --notes "Beta release" --draft --prerelease ./dist/*.tar.gz
\`\`\`

### `create_draft_release`

Create draft release.

\`\`\`bash
create_draft_release "octocat" "hello-world" "v1.1.0" "Version 1.1.0" "NOTES.md"
\`\`\`

### `update_release`

Update release metadata.

\`\`\`bash
# Update title and notes
update_release "octocat" "hello-world" "v1.0.0" --title "New title" --notes "Updated notes"

# Publish draft
update_release "octocat" "hello-world" "v1.0.0" --draft false
\`\`\`

### `delete_release`

Delete release and its assets.

\`\`\`bash
# With confirmation prompt
delete_release "octocat" "hello-world" "v1.0.0"

# Skip confirmation
delete_release "octocat" "hello-world" "v1.0.0" --yes
\`\`\`

### `upload_release_asset`

Upload asset to release.

\`\`\`bash
upload_release_asset "octocat" "hello-world" "v1.0.0" "./dist/binary.tar.gz"
\`\`\`

### `download_release_asset`

Download asset from release.

\`\`\`bash
# Download all assets
download_release_asset "octocat" "hello-world" "v1.0.0"

# Download matching pattern
download_release_asset "octocat" "hello-world" "v1.0.0" "*.tar.gz" "./downloads"
\`\`\`

### `delete_release_asset`

Delete single asset.

\`\`\`bash
ASSET_ID=\$(get_asset_id "octocat" "hello-world" "\$RELEASE_ID" "old-binary.tar.gz")
delete_release_asset "octocat" "hello-world" "\$ASSET_ID"
\`\`\`

### `publish_draft_release`

Convert draft to published.

\`\`\`bash
RELEASE_ID=\$(get_release_id "octocat" "hello-world" "v1.0.0")
publish_draft_release "octocat" "hello-world" "\$RELEASE_ID"
\`\`\`

---

## UTILITY Primitives (2)

Helper operations.

### `generate_release_notes`

Auto-generate release notes.

\`\`\`bash
# Generate notes between tags
NOTES=\$(generate_release_notes "octocat" "hello-world" "v1.1.0" "v1.0.0")
create_release "octocat" "hello-world" "v1.1.0" --title "v1.1.0" --notes "\$NOTES"

# Generate from beginning
generate_release_notes "octocat" "hello-world" "v1.0.0"
\`\`\`

### `download_release_tarball`

Download source code tarball.

\`\`\`bash
download_release_tarball "octocat" "hello-world" "v1.0.0" "source.tar.gz"
\`\`\`

---

## Composition Examples

### Complete Release Workflow

\`\`\`bash
# 1. Create draft with auto-generated notes
NOTES=\$(generate_release_notes "octocat" "hello-world" "v1.1.0" "v1.0.0")
create_draft_release "octocat" "hello-world" "v1.1.0" "Version 1.1.0" <(echo "\$NOTES")

# 2. Upload build artifacts
upload_release_asset "octocat" "hello-world" "v1.1.0" "./dist/app-linux.tar.gz"
upload_release_asset "octocat" "hello-world" "v1.1.0" "./dist/app-macos.tar.gz"
upload_release_asset "octocat" "hello-world" "v1.1.0" "./dist/checksums.txt"

# 3. Review draft
gh release view v1.1.0 --web

# 4. Publish
RELEASE_ID=\$(get_release_id "octocat" "hello-world" "v1.1.0")
publish_draft_release "octocat" "hello-world" "\$RELEASE_ID"
\`\`\`

### List All Stable Releases

\`\`\`bash
discover_repo_releases "octocat" "hello-world" 100 "true" "true" | format_releases
\`\`\`

### Find All Beta Versions

\`\`\`bash
discover_repo_releases "octocat" "hello-world" | \\
    filter_releases_by_tag_pattern "beta" | \\
    format_releases
\`\`\`

### Download Statistics

\`\`\`bash
# Total downloads for all releases
discover_repo_releases "octocat" "hello-world" | \\
    jq '{
        total_releases: length,
        total_downloads: (map(.assets // [] | map(.downloadCount // 0) | add // 0) | add)
    }'
\`\`\`

### Cleanup Old Prereleases

\`\`\`bash
# Find prereleases older than latest stable
discover_repo_releases "octocat" "hello-world" | \\
    filter_releases_by_prerelease "true" | \\
    jq -r '.[].tagName' | \\
    while read tag; do
        echo "Deleting prerelease: \$tag"
        delete_release "octocat" "hello-world" "\$tag" --yes
    done
\`\`\`

### Generate Changelog

\`\`\`bash
# Create changelog from all releases
discover_repo_releases "octocat" "hello-world" 50 | \\
    jq -r 'map("## " + .name + " (" + .tagName + ") - " + .publishedAt + "\\n\\n" + (.body // "No notes") + "\\n") | join("\\n")' > CHANGELOG.md
\`\`\`

---

## Best Practices

### Semantic Versioning

Follow SemVer (MAJOR.MINOR.PATCH):

\`\`\`bash
# Breaking changes → increment MAJOR
create_release "owner" "repo" "v2.0.0" --title "Major Release" --notes-file BREAKING.md

# New features (backward compatible) → increment MINOR
create_release "owner" "repo" "v1.1.0" --title "Feature Release" --notes-file CHANGELOG.md

# Bug fixes → increment PATCH
create_release "owner" "repo" "v1.0.1" --title "Patch Release" --notes-file FIXES.md
\`\`\`

### Prerelease Strategy

\`\`\`bash
# Alpha → internal testing
create_release "owner" "repo" "v2.0.0-alpha.1" --prerelease

# Beta → public testing
create_release "owner" "repo" "v2.0.0-beta.1" --prerelease

# Release candidate → final testing
create_release "owner" "repo" "v2.0.0-rc.1" --prerelease

# Final release
create_release "owner" "repo" "v2.0.0"
\`\`\`

### Asset Naming Conventions

\`\`\`bash
# Include version, platform, architecture
app-v1.0.0-linux-amd64.tar.gz
app-v1.0.0-darwin-arm64.tar.gz
app-v1.0.0-windows-amd64.zip

# Include checksums
checksums-v1.0.0.txt
checksums-v1.0.0.sha256
\`\`\`

---

## Integration with CI/CD

### GitHub Actions Example

\`\`\`yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build artifacts
        run: make build
      
      - name: Create release with assets
        run: |
          gh release create \${{ github.ref_name }} \\
            --title "Release \${{ github.ref_name }}" \\
            --generate-notes \\
            ./dist/*
        env:
          GH_TOKEN: \${{ secrets.GITHUB_TOKEN }}
\`\`\`

---

## Related Documentation

- **ARCH-001**: \`knowledge/architecture-principles.md\` - Layer 2 patterns
- **IMPL-007**: \`knowledge/implementation-plan-release-domain.md\` - Implementation plan
- **Milestone Domain**: \`lib/github/gh-milestone-index.md\` - Release planning
- **Action Domain**: \`lib/github/gh-action-index.md\` - CI/CD automation

---

## Summary

The Release domain provides 33 primitives for comprehensive release management:

- **Multi-state releases**: Draft, prerelease, published
- **Asset management**: Upload, download, delete
- **Auto-generated notes**: Create from commits
- **gh CLI primary**: Full-featured CLI support
- **Composable**: Pipeline pattern with stdin→stdout
