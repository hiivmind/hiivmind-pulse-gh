#!/usr/bin/env bash
# tests/lib/resources/release.bash
# Release resource management for testing

# Source core if not already loaded
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# =============================================================================
# CREATE
# =============================================================================

# Create a release without tracking (for use in subshells)
# Usage: create_release_raw "owner" "repo" "tag_name" [name] [body] [draft] [prerelease]
# Output: release id
create_release_raw() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local name="${4:-$tag_name}"
    local body="${5:-}"
    local draft="${6:-false}"
    local prerelease="${7:-false}"

    local args=(
        -f "tag_name=${tag_name}"
        -f "name=${name}"
        -F "draft=${draft}"
        -F "prerelease=${prerelease}"
    )
    [[ -n "$body" ]] && args+=(-f "body=${body}")

    local result
    result=$(gh api "repos/${owner}/${repo}/releases" "${args[@]}")

    local release_id
    release_id=$(echo "$result" | jq -r '.id')

    if [[ "$release_id" == "null" || -z "$release_id" ]]; then
        echo "Error: Failed to create release" >&2
        return 1
    fi

    echo "$release_id"
}

# Create a release and track it for cleanup
# Usage: create_release "owner" "repo" "tag_name" [name] [body] [draft] [prerelease]
# Output: release id
create_release() {
    local owner="$1"
    local repo="$2"
    local release_id
    release_id=$(create_release_raw "$@")
    if [[ $? -eq 0 ]]; then
        track_resource "release" "${owner}/${repo}/${release_id}"
        echo "$release_id"
    else
        return 1
    fi
}

# Create a draft release
# Usage: create_draft_release "owner" "repo" "tag_name" [name] [body]
# Output: release id
create_draft_release() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local name="${4:-$tag_name}"
    local body="${5:-}"

    create_release "$owner" "$repo" "$tag_name" "$name" "$body" "true" "false"
}

# Create a prerelease
# Usage: create_prerelease "owner" "repo" "tag_name" [name] [body]
# Output: release id
create_prerelease() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"
    local name="${4:-$tag_name}"
    local body="${5:-}"

    create_release "$owner" "$repo" "$tag_name" "$name" "$body" "false" "true"
}

# Create a release with auto-generated tag
# Usage: create_test_release "owner" "repo"
# Output: release id
create_test_release() {
    local owner="$1"
    local repo="$2"
    local tag_name
    tag_name="v0.0.0-test-$(date +%s)"

    create_release "$owner" "$repo" "$tag_name" "Test Release ${tag_name}" "Auto-generated test release"
}

# =============================================================================
# READ
# =============================================================================

# Get release by id
# Usage: get_release "owner" "repo" "release_id"
get_release() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    gh api "repos/${owner}/${repo}/releases/${release_id}"
}

# Get release by tag
# Usage: get_release_by_tag "owner" "repo" "tag_name"
get_release_by_tag() {
    local owner="$1"
    local repo="$2"
    local tag_name="$3"

    gh api "repos/${owner}/${repo}/releases/tags/${tag_name}"
}

# Get latest release
# Usage: get_latest_release "owner" "repo"
get_latest_release() {
    local owner="$1"
    local repo="$2"

    gh api "repos/${owner}/${repo}/releases/latest"
}

# List all release ids
# Usage: list_releases "owner" "repo"
# Output: release ids, one per line
list_releases() {
    local owner="$1"
    local repo="$2"

    gh api "repos/${owner}/${repo}/releases?per_page=100" \
        --jq '.[].id'
}

# Check if release exists
# Usage: release_exists "owner" "repo" "release_id"
release_exists() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    gh api "repos/${owner}/${repo}/releases/${release_id}" &>/dev/null
}

# =============================================================================
# UPDATE
# =============================================================================

# Update release
# Usage: update_release "owner" "repo" "release_id" [tag_name] [name] [body] [draft] [prerelease]
update_release() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"
    local tag_name="${4:-}"
    local name="${5:-}"
    local body="${6:-}"
    local draft="${7:-}"
    local prerelease="${8:-}"

    local args=(-X PATCH)
    [[ -n "$tag_name" ]] && args+=(-f "tag_name=${tag_name}")
    [[ -n "$name" ]] && args+=(-f "name=${name}")
    [[ -n "$body" ]] && args+=(-f "body=${body}")
    [[ -n "$draft" ]] && args+=(-F "draft=${draft}")
    [[ -n "$prerelease" ]] && args+=(-F "prerelease=${prerelease}")

    gh api "repos/${owner}/${repo}/releases/${release_id}" "${args[@]}"
}

# Publish draft release
# Usage: publish_release "owner" "repo" "release_id"
publish_release() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    gh api "repos/${owner}/${repo}/releases/${release_id}" \
        -X PATCH -F draft=false
}

# =============================================================================
# DELETE
# =============================================================================

# Delete release by identifier
# Usage: delete_release "owner/repo/release_id"
delete_release() {
    local identifier="$1"

    parse_owner_repo_number "$identifier"

    # Also try to delete the tag
    local release_info
    release_info=$(gh api "repos/${PARSED_OWNER}/${PARSED_REPO}/releases/${PARSED_NUMBER}" 2>/dev/null) || true

    # Delete the release
    gh api -X DELETE "repos/${PARSED_OWNER}/${PARSED_REPO}/releases/${PARSED_NUMBER}" \
        2>/dev/null || true

    # Delete the associated tag if it exists
    if [[ -n "$release_info" ]]; then
        local tag_name
        tag_name=$(echo "$release_info" | jq -r '.tag_name' 2>/dev/null)
        if [[ -n "$tag_name" && "$tag_name" != "null" ]]; then
            gh api -X DELETE "repos/${PARSED_OWNER}/${PARSED_REPO}/git/refs/tags/${tag_name}" \
                2>/dev/null || true
        fi
    fi
}

# Delete release by parts
# Usage: delete_release_by_parts "owner" "repo" "release_id"
delete_release_by_parts() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    delete_release "${owner}/${repo}/${release_id}"
}

# =============================================================================
# ASSETS
# =============================================================================

# Upload asset to release
# Usage: upload_release_asset "owner" "repo" "release_id" "file_path" [name]
upload_release_asset() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"
    local file_path="$4"
    local name="${5:-$(basename "$file_path")}"

    # Get upload URL
    local upload_url
    upload_url=$(gh api "repos/${owner}/${repo}/releases/${release_id}" \
        --jq '.upload_url | sub("\\{.*\\}"; "")')

    # Upload asset
    gh api "${upload_url}?name=${name}" \
        -X POST \
        -H "Content-Type: application/octet-stream" \
        --input "$file_path"
}

# List release assets
# Usage: list_release_assets "owner" "repo" "release_id"
list_release_assets() {
    local owner="$1"
    local repo="$2"
    local release_id="$3"

    gh api "repos/${owner}/${repo}/releases/${release_id}/assets" \
        --jq '.[].id'
}

# Delete release asset
# Usage: delete_release_asset "owner" "repo" "asset_id"
delete_release_asset() {
    local owner="$1"
    local repo="$2"
    local asset_id="$3"

    gh api -X DELETE "repos/${owner}/${repo}/releases/assets/${asset_id}" \
        2>/dev/null || true
}
