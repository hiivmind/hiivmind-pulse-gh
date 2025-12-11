#!/usr/bin/env bash
# Fixture Sanitization Script
# Removes sensitive and variable data while preserving structure

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="${SCRIPT_DIR%/*}"
MANIFEST_FILE="${FIXTURES_DIR}/recording_manifest.yaml"

# =============================================================================
# SANITIZATION RULES
# =============================================================================

# Generic sanitization rules applied to all fixtures
sanitize_generic() {
    jq '
        walk(
            if type == "object" then
                # Sanitize user/org logins
                (if .login then .login = "test-user" else . end) |

                # Sanitize emails
                (if .email then .email = "test@example.com" else . end) |

                # Sanitize avatar URLs
                (if .avatarUrl or .avatar_url then
                    .avatarUrl = "https://avatars.githubusercontent.com/test-user" |
                    .avatar_url = "https://avatars.githubusercontent.com/test-user"
                else . end) |

                # Sanitize names (but preserve title/name fields for milestones/repos)
                (if .name and (.type == "User" or .type == "Organization") then
                    .name = "Test User"
                else . end) |

                # Sanitize node IDs (GitHub base64 encoded IDs)
                (if .id and (.id | type) == "string" then
                    if (.id | startswith("I_")) then .id = "I_SANITIZED_ISSUE"
                    elif (.id | startswith("PR_")) then .id = "PR_SANITIZED_PR"
                    elif (.id | startswith("MDU6")) then .id = "MDU6_SANITIZED_USER"
                    elif (.id | startswith("MDEw")) then .id = "MDEw_SANITIZED_ORG"
                    elif (.id | startswith("PVT_")) then .id = "PVT_SANITIZED_PROJECT"
                    elif (.id | startswith("PVTF_")) then .id = "PVTF_SANITIZED_FIELD"
                    elif (.id | startswith("PVTI_")) then .id = "PVTI_SANITIZED_ITEM"
                    else . end
                else . end) |

                # Sanitize URLs with usernames
                (if .url and (.url | type) == "string" then
                    .url = (.url |
                        gsub("/users/[^/]+"; "/users/test-user") |
                        gsub("/orgs/[^/]+"; "/orgs/test-org")
                    )
                else . end) |

                # Sanitize HTML URLs
                (if .html_url and (.html_url | type) == "string" then
                    .html_url = (.html_url |
                        gsub("/[^/]+/[^/]+/(issues|pull)"; "/test-org/test-repo/\\1") |
                        gsub("github\\.com/[^/]+(?!/test-)"; "github.com/test-user")
                    )
                else . end)
            else . end
        )
    '
}

# Normalize timestamps to fixed values (preserves chronological order)
sanitize_timestamps() {
    local base_date="2024-01-01T00:00:00Z"

    jq --arg base "$base_date" '
        # Track unique timestamps and assign sequential values
        . as $root |
        [paths(type == "string" and test("\\d{4}-\\d{2}-\\d{2}T"))] as $paths |
        reduce $paths[] as $path (
            {data: $root, timestamps: {}, counter: 0};
            .timestamps[getpath($path)] as $existing |
            if $existing then
                setpath(["data"] + $path; $existing)
            else
                .counter += 1 |
                .timestamps[getpath($path)] = (
                    $base | fromdateiso8601 | . + (.counter * 3600) | todateiso8601
                ) |
                setpath(["data"] + $path; .timestamps[getpath($path)])
            end
        ) |
        .data
    ' 2>/dev/null || cat  # Fallback to original if jq fails
}

# Sanitize GitHub-specific sensitive data
sanitize_github_specific() {
    jq '
        walk(
            if type == "object" then
                # Remove tokens and secrets
                (if .token then .token = "sanitized_token" else . end) |
                (if .secret then .secret = "sanitized_secret" else . end) |

                # Sanitize SSH URLs
                (if .ssh_url then .ssh_url = "git@github.com:test-org/test-repo.git" else . end) |

                # Sanitize clone URLs
                (if .clone_url then .clone_url = "https://github.com/test-org/test-repo.git" else . end) |
                (if .git_url then .git_url = "git://github.com/test-org/test-repo.git" else . end)
            else . end
        )
    '
}

# =============================================================================
# DOMAIN-SPECIFIC SANITIZATION
# =============================================================================

# Apply domain-specific rules from manifest
sanitize_domain_specific() {
    local domain="$1"
    local fixture_name="$2"
    local input_file="$3"

    # Check if domain-specific rules exist
    local rules=$(yq ".fixtures.${domain}.${fixture_name}.sanitize // []" "$MANIFEST_FILE" 2>/dev/null)

    if [[ "$rules" == "[]" ]] || [[ "$rules" == "null" ]]; then
        # No specific rules, just pass through
        cat "$input_file"
        return
    fi

    # Apply each rule
    local temp_file="${input_file}.tmp"
    cp "$input_file" "$temp_file"

    local rule_count=$(echo "$rules" | yq 'length')

    for ((i=0; i<rule_count; i++)); do
        local path=$(echo "$rules" | yq ".[$i].path")
        local value=$(echo "$rules" | yq ".[$i].value")

        if [[ "$path" != "null" ]] && [[ "$value" != "null" ]]; then
            jq --arg path "$path" --arg value "$value" \
                'setpath($path | split("."); $value)' \
                "$temp_file" > "${temp_file}.2"
            mv "${temp_file}.2" "$temp_file"
        fi
    done

    cat "$temp_file"
    rm -f "$temp_file"
}

# =============================================================================
# MAIN SANITIZATION PIPELINE
# =============================================================================

sanitize_fixture() {
    local domain="$1"
    local fixture_name="$2"
    local fixture_file="$3"

    if [[ ! -f "$fixture_file" ]]; then
        echo "ERROR: Fixture file not found: $fixture_file" >&2
        return 1
    fi

    # Create backup
    cp "$fixture_file" "${fixture_file}.backup"

    # Apply sanitization pipeline
    cat "$fixture_file" | \
        sanitize_generic | \
        sanitize_github_specific | \
        sanitize_timestamps > "${fixture_file}.sanitized"

    # Apply domain-specific rules if they exist
    if [[ -f "$MANIFEST_FILE" ]]; then
        sanitize_domain_specific "$domain" "$fixture_name" "${fixture_file}.sanitized" > "${fixture_file}.final"
        mv "${fixture_file}.final" "$fixture_file"
    else
        mv "${fixture_file}.sanitized" "$fixture_file"
    fi

    # Validate JSON
    if ! jq '.' "$fixture_file" > /dev/null 2>&1; then
        echo "ERROR: Sanitization produced invalid JSON, restoring backup" >&2
        mv "${fixture_file}.backup" "$fixture_file"
        return 1
    fi

    # Pretty-print final result
    jq '.' "$fixture_file" > "${fixture_file}.pretty"
    mv "${fixture_file}.pretty" "$fixture_file"

    # Remove backup
    rm -f "${fixture_file}.backup" "${fixture_file}.sanitized"

    echo "Sanitized: $fixture_file"
}

# =============================================================================
# USAGE
# =============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") DOMAIN FIXTURE_NAME FIXTURE_FILE

Sanitize a recorded fixture by removing sensitive data.

ARGUMENTS:
    DOMAIN          Domain name (e.g., identity, milestone)
    FIXTURE_NAME    Fixture name (e.g., viewer, list_all)
    FIXTURE_FILE    Path to fixture JSON file

EXAMPLES:
    $(basename "$0") identity viewer tests/fixtures/graphql/identity/viewer.json
    $(basename "$0") milestone list_all tests/fixtures/rest/milestone/list_all.json

SANITIZATION RULES:
    - Usernames → test-user
    - Organizations → test-org
    - Emails → test@example.com
    - Node IDs → deterministic fake IDs
    - Timestamps → normalized sequential values
    - Avatar URLs → generic test URLs
    - Tokens/secrets → sanitized placeholders

EOF
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    if [[ $# -lt 3 ]]; then
        usage
        exit 1
    fi

    sanitize_fixture "$1" "$2" "$3"
}

# Only run main if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
