#!/usr/bin/env bash
# GitHub Releases Domain Functions
# Layer 2 primitives for managing releases, tags, and assets

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

_get_release_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [ -h "$source" ]; do
        local dir
        dir=$(cd -P "$(dirname "$source")" && pwd)
        source=$(readlink "$source")
        [[ $source != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

# =============================================================================
# FETCH PRIMITIVES
# =============================================================================
# Retrieve single release or asset

# Fetch release by ID
# Args: owner, repo, release_id
# Output: Release JSON
fetch_release() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$release_id" ]]; then
        echo "ERROR: fetch_release requires owner, repo, and release_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/$release_id" \
        -H "Accept: application/vnd.github+json"
}

# Fetch release by tag name
# Args: owner, repo, tag_name
# Output: Release JSON
fetch_release_by_tag() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: fetch_release_by_tag requires owner, repo, and tag_name" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/tags/$tag_name" \
        -H "Accept: application/vnd.github+json"
}

# Fetch latest release (non-prerelease)
# Args: owner, repo
# Output: Release JSON
fetch_latest_release() {
    local owner="$1"
    local repo="$2"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: fetch_latest_release requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/latest" \
        -H "Accept: application/vnd.github+json"
}

# Fetch release assets
# Args: owner, repo, release_id
# Output: JSON array of assets
fetch_release_assets() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$release_id" ]]; then
        echo "ERROR: fetch_release_assets requires owner, repo, and release_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/$release_id/assets" \
        -H "Accept: application/vnd.github+json"
}

# Fetch single asset metadata
# Args: owner, repo, asset_id
# Output: Asset JSON
fetch_asset() {
    local owner="$1"
    local repo="$2"
    local asset_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$asset_id" ]]; then
        echo "ERROR: fetch_asset requires owner, repo, and asset_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/assets/$asset_id" \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# DISCOVER PRIMITIVES
# =============================================================================
# List releases, assets, or tags

# Discover repository releases
# Args: owner, repo, [limit], [exclude_drafts], [exclude_prereleases]
# Output: JSON array of releases
discover_repo_releases() {
    local owner="$1"
    local repo="$2"
    local limit="${3:-30}"
    local exclude_drafts="${4:-false}"
    local exclude_prereleases="${5:-false}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_releases requires owner and repo" >&2
        return 2
    fi

    local args=("-R" "$owner/$repo")
    args+=(--json tagName,name,publishedAt,createdAt,isPrerelease,isDraft,isLatest)
    args+=(--limit "$limit")

    [[ "$exclude_drafts" == "true" ]] && args+=(--exclude-drafts)
    [[ "$exclude_prereleases" == "true" ]] && args+=(--exclude-pre-releases)

    gh release list "${args[@]}"
}

# Discover release assets
# Args: owner, repo, tag_name
# Output: JSON array of assets
discover_release_assets() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: discover_release_assets requires owner, repo, and tag_name" >&2
        return 2
    fi

    gh release view "$tag_name" -R "$owner/$repo" --json assets --jq '.assets'
}

# Discover repository tags
# Args: owner, repo, [per_page], [page]
# Output: JSON array of tags
discover_repo_tags() {
    local owner="$1"
    local repo="$2"
    local per_page="${3:-100}"
    local page="${4:-1}"

    if [[ -z "$owner" || -z "$repo" ]]; then
        echo "ERROR: discover_repo_tags requires owner and repo" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/tags?per_page=$per_page&page=$page" \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# LOOKUP PRIMITIVES
# =============================================================================
# Resolve IDs and names

# Get release ID by tag name
# Args: owner, repo, tag_name
# Output: Release ID
get_release_id() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: get_release_id requires owner, repo, and tag_name" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/tags/$tag_name" --jq '.id'
}

# Get tag name by release ID
# Args: owner, repo, release_id
# Output: Tag name
get_release_tag() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$release_id" ]]; then
        echo "ERROR: get_release_tag requires owner, repo, and release_id" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/$release_id" --jq '.tag_name'
}

# Get asset ID by name
# Args: owner, repo, release_id, asset_name
# Output: Asset ID
get_asset_id() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"
    local asset_name="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$release_id" || -z "$asset_name" ]]; then
        echo "ERROR: get_asset_id requires owner, repo, release_id, and asset_name" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/$release_id/assets" \
        --jq ".[] | select(.name == \"$asset_name\") | .id"
}

# =============================================================================
# FILTER PRIMITIVES
# =============================================================================
# Transform/filter JSON data (stdin → stdout)

# Filter releases by prerelease status
# Args: "true" | "false"
# Input: JSON array of releases
# Output: Filtered JSON array
filter_releases_by_prerelease() {
    local is_prerelease="$1"

    if [[ -z "$is_prerelease" ]]; then
        echo "ERROR: filter_releases_by_prerelease requires is_prerelease argument" >&2
        return 2
    fi

    if [[ "$is_prerelease" == "true" ]]; then
        jq 'map(select(.isPrerelease == true or .prerelease == true))'
    else
        jq 'map(select(.isPrerelease == false or .prerelease == false))'
    fi
}

# Filter releases by draft status
# Args: "true" | "false"
# Input: JSON array of releases
# Output: Filtered JSON array
filter_releases_by_draft() {
    local is_draft="$1"

    if [[ -z "$is_draft" ]]; then
        echo "ERROR: filter_releases_by_draft requires is_draft argument" >&2
        return 2
    fi

    if [[ "$is_draft" == "true" ]]; then
        jq 'map(select(.isDraft == true or .draft == true))'
    else
        jq 'map(select(.isDraft == false or .draft == false))'
    fi
}

# Filter releases by tag pattern
# Args: pattern (regex)
# Input: JSON array of releases
# Output: Filtered JSON array
filter_releases_by_tag_pattern() {
    local pattern="$1"

    if [[ -z "$pattern" ]]; then
        echo "ERROR: filter_releases_by_tag_pattern requires pattern argument" >&2
        return 2
    fi

    jq --arg pattern "$pattern" 'map(select(.tagName // .tag_name | test($pattern)))'
}

# Filter assets by name pattern
# Args: pattern (regex)
# Input: JSON array of assets
# Output: Filtered JSON array
filter_assets_by_name() {
    local pattern="$1"

    if [[ -z "$pattern" ]]; then
        echo "ERROR: filter_assets_by_name requires pattern argument" >&2
        return 2
    fi

    jq --arg pattern "$pattern" 'map(select(.name | test($pattern)))'
}

# =============================================================================
# FORMAT PRIMITIVES
# =============================================================================
# Transform JSON to human-readable output (stdin → stdout)

# Format releases as table
# Input: JSON array of releases
# Output: Formatted table
format_releases() {
    jq -r '
        ["TAG", "NAME", "PUBLISHED", "PRERELEASE", "DRAFT", "LATEST"] as $headers |
        [$headers],
        (.[] | [
            (.tagName // .tag_name),
            .name,
            (.publishedAt // .published_at // "-"),
            ((.isPrerelease // .prerelease) | tostring),
            ((.isDraft // .draft) | tostring),
            ((.isLatest // false) | tostring)
        ]) |
        @tsv
    '
}

# Format single release detail
# Input: Single release JSON
# Output: Formatted details
format_release_detail() {
    jq -r '
        "Tag Name: \(.tag_name // .tagName)",
        "Release Name: \(.name)",
        "Created: \(.created_at // .createdAt)",
        "Published: \(.published_at // .publishedAt // \"Not published\")",
        "Prerelease: \(.prerelease // .isPrerelease)",
        "Draft: \(.draft // .isDraft)",
        "Latest: \(.isLatest // false)",
        "Target: \(.target_commitish)",
        "Author: \(.author.login)",
        "Assets: \(.assets | length)",
        "",
        "Release Notes:",
        "\(.body // \"No release notes\")"
    '
}

# Format assets as table
# Input: JSON array of assets
# Output: Formatted table
format_assets() {
    jq -r '
        ["NAME", "SIZE", "DOWNLOADS", "CONTENT_TYPE"] as $headers |
        [$headers],
        (.[] | [
            .name,
            (.size | tostring),
            ((.downloadCount // .download_count) | tostring),
            .content_type
        ]) |
        @tsv
    '
}

# Format release notes (body)
# Input: Single release JSON
# Output: Release notes text
format_release_notes() {
    jq -r '.body // "No release notes"'
}

# =============================================================================
# DETECT PRIMITIVES
# =============================================================================
# Determine release properties

# Detect if release exists by tag
# Args: owner, repo, tag_name
# Output: "true" | "false"
detect_release_exists() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: detect_release_exists requires owner, repo, and tag_name" >&2
        return 2
    fi

    if gh api "repos/$owner/$repo/releases/tags/$tag_name" 2>/dev/null >/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# Detect if release is prerelease
# Args: owner, repo, tag_name
# Output: "true" | "false"
detect_is_prerelease() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: detect_is_prerelease requires owner, repo, and tag_name" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/tags/$tag_name" --jq '.prerelease' 2>/dev/null || echo "false"
}

# Detect if release is draft
# Args: owner, repo, tag_name
# Output: "true" | "false"
detect_is_draft() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: detect_is_draft requires owner, repo, and tag_name" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/releases/tags/$tag_name" --jq '.draft' 2>/dev/null || echo "false"
}

# Detect if release is latest
# Args: owner, repo, tag_name
# Output: "true" | "false"
detect_is_latest() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: detect_is_latest requires owner, repo, and tag_name" >&2
        return 2
    fi

    local latest_tag
    latest_tag=$(gh api "repos/$owner/$repo/releases/latest" --jq '.tag_name' 2>/dev/null)

    if [[ "$latest_tag" == "$tag_name" ]]; then
        echo "true"
    else
        echo "false"
    fi
}

# =============================================================================
# MUTATE PRIMITIVES
# =============================================================================
# Create, update, or delete releases and assets

# Create release
# Args: owner, repo, tag_name, [title], [notes_file], [--draft], [--prerelease], [asset_files...]
# Output: Release JSON
create_release() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    shift 3

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: create_release requires owner, repo, and tag_name" >&2
        return 2
    fi

    local args=(-R "$owner/$repo" "$tag_name")

    # Parse optional arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title)
                args+=(--title "$2")
                shift 2
                ;;
            --notes)
                args+=(--notes "$2")
                shift 2
                ;;
            --notes-file)
                args+=(--notes-file "$2")
                shift 2
                ;;
            --draft)
                args+=(--draft)
                shift
                ;;
            --prerelease)
                args+=(--prerelease)
                shift
                ;;
            *)
                # Assume it's an asset file
                args+=("$1")
                shift
                ;;
        esac
    done

    gh release create "${args[@]}"
}

# Create draft release
# Args: owner, repo, tag_name, [title], [notes_file]
# Output: Release JSON
create_draft_release() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local title="${4:-}"
    local notes_file="${5:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: create_draft_release requires owner, repo, and tag_name" >&2
        return 2
    fi

    local args=("$owner" "$repo" "$tag_name" --draft)
    [[ -n "$title" ]] && args+=(--title "$title")
    [[ -n "$notes_file" ]] && args+=(--notes-file "$notes_file")

    create_release "${args[@]}"
}

# Update release
# Args: owner, repo, tag_name, [--title "New title"], [--notes "New notes"], [--draft true|false], [--prerelease true|false]
# Output: Empty (204 No Content)
update_release() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    shift 3

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: update_release requires owner, repo, and tag_name" >&2
        return 2
    fi

    local args=(-R "$owner/$repo" "$tag_name")

    # Parse optional arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title)
                args+=(--title "$2")
                shift 2
                ;;
            --notes)
                args+=(--notes "$2")
                shift 2
                ;;
            --notes-file)
                args+=(--notes-file "$2")
                shift 2
                ;;
            --draft)
                args+=(--draft="$2")
                shift 2
                ;;
            --prerelease)
                args+=(--prerelease="$2")
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    gh release edit "${args[@]}"
}

# Delete release
# Args: owner, repo, tag_name, [--yes]
# Output: Empty (204 No Content)
delete_release() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local yes_flag="${4:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: delete_release requires owner, repo, and tag_name" >&2
        return 2
    fi

    local args=(-R "$owner/$repo" "$tag_name")
    [[ "$yes_flag" == "--yes" ]] && args+=(--yes)

    gh release delete "${args[@]}"
}

# Upload release asset
# Args: owner, repo, tag_name, asset_file_path
# Output: Empty
upload_release_asset() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local asset_file="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" || -z "$asset_file" ]]; then
        echo "ERROR: upload_release_asset requires owner, repo, tag_name, and asset_file" >&2
        return 2
    fi

    if [[ ! -f "$asset_file" ]]; then
        echo "ERROR: Asset file not found: $asset_file" >&2
        return 2
    fi

    gh release upload "$tag_name" "$asset_file" -R "$owner/$repo"
}

# Download release asset
# Args: owner, repo, tag_name, [pattern], [output_dir]
# Output: Downloaded files
download_release_asset() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local pattern="${4:-}"
    local output_dir="${5:-.}"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: download_release_asset requires owner, repo, and tag_name" >&2
        return 2
    fi

    local args=(-R "$owner/$repo" "$tag_name" --dir "$output_dir")
    [[ -n "$pattern" ]] && args+=(--pattern "$pattern")

    gh release download "${args[@]}"
}

# Delete release asset
# Args: owner, repo, asset_id
# Output: Empty (204 No Content)
delete_release_asset() {
    local owner="$1"
    local repo="$2"
    local asset_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$asset_id" ]]; then
        echo "ERROR: delete_release_asset requires owner, repo, and asset_id" >&2
        return 2
    fi

    gh api -X DELETE "repos/$owner/$repo/releases/assets/$asset_id"
}

# Publish draft release
# Args: owner, repo, release_id
# Output: Release JSON
publish_draft_release() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    if [[ -z "$owner" || -z "$repo" || -z "$release_id" ]]; then
        echo "ERROR: publish_draft_release requires owner, repo, and release_id" >&2
        return 2
    fi

    gh api -X PATCH "repos/$owner/$repo/releases/$release_id" \
        -f draft=false \
        -H "Accept: application/vnd.github+json"
}

# =============================================================================
# UTILITY PRIMITIVES
# =============================================================================
# Helper operations

# Generate release notes
# Args: owner, repo, tag_name, [previous_tag]
# Output: Generated release notes JSON
generate_release_notes() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local previous_tag="${4:-}"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" ]]; then
        echo "ERROR: generate_release_notes requires owner, repo, and tag_name" >&2
        return 2
    fi

    local args=(-X POST)
    args+=(-f tag_name="$tag_name")
    [[ -n "$previous_tag" ]] && args+=(-f previous_tag_name="$previous_tag")

    gh api "repos/$owner/$repo/releases/generate-notes" "${args[@]}"
}

# Download release tarball
# Args: owner, repo, tag_name, output_file
# Output: Downloaded tarball
download_release_tarball() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local output_file="$4"

    if [[ -z "$owner" || -z "$repo" || -z "$tag_name" || -z "$output_file" ]]; then
        echo "ERROR: download_release_tarball requires owner, repo, tag_name, and output_file" >&2
        return 2
    fi

    gh api "repos/$owner/$repo/tarball/$tag_name" > "$output_file"
}
