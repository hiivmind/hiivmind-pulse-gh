#!/usr/bin/env bash
# Fixture Drift Detection Script
# Detects schema changes in GitHub APIs by comparing recorded fixtures

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="${SCRIPT_DIR%/*}"
PROJECT_ROOT="${FIXTURES_DIR%/*}/.."
MANIFEST_FILE="${FIXTURES_DIR}/recording_manifest.yaml"
RECORD_SCRIPT="${SCRIPT_DIR}/record_fixtures.bash"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Drift tracking
DRIFT_DETECTED=0
TOTAL_CHECKED=0
DRIFTED_FIXTURES=()

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Extract JSON schema (structure without values)
extract_schema() {
    local json_file="$1"

    jq 'walk(
        if type == "object" then
            map_values(
                if type == "object" then "object"
                elif type == "array" then
                    if length > 0 then
                        [.[0] | walk(
                            if type == "object" then "object"
                            elif type == "array" then "array"
                            else type
                            end
                        )]
                    else "array"
                    end
                else type
                end
            )
        elif type == "array" then
            if length > 0 then
                [.[0] | walk(
                    if type == "object" then "object"
                    elif type == "array" then "array"
                    else type
                    end
                )]
            else []
            end
        else type
        end
    )' "$json_file"
}

# Compare two schemas and report differences
compare_schemas() {
    local old_schema="$1"
    local new_schema="$2"
    local fixture_path="$3"

    local diff_output=$(diff <(echo "$old_schema" | jq -S '.') <(echo "$new_schema" | jq -S '.') || true)

    if [[ -n "$diff_output" ]]; then
        log_warning "Schema drift detected in: $fixture_path"

        # Detailed analysis
        local old_keys=$(echo "$old_schema" | jq -r 'paths(type != "object" and type != "array") | join(".")' | sort)
        local new_keys=$(echo "$new_schema" | jq -r 'paths(type != "object" and type != "array") | join(".")' | sort)

        # New fields
        local added=$(comm -13 <(echo "$old_keys") <(echo "$new_keys"))
        if [[ -n "$added" ]]; then
            echo -e "  ${GREEN}+ New fields:${NC}"
            echo "$added" | sed 's/^/    /'
        fi

        # Removed fields
        local removed=$(comm -23 <(echo "$old_keys") <(echo "$new_keys"))
        if [[ -n "$removed" ]]; then
            echo -e "  ${RED}- Removed fields:${NC}"
            echo "$removed" | sed 's/^/    /'
        fi

        return 1
    fi

    return 0
}

# =============================================================================
# DRIFT DETECTION
# =============================================================================

# Check single fixture for drift
check_fixture_drift() {
    local domain="$1"
    local fixture_name="$2"
    local fixture_type="$3"

    ((TOTAL_CHECKED++))

    local fixture_file="${FIXTURES_DIR}/${fixture_type}/${domain}/${fixture_name}.json"

    if [[ ! -f "$fixture_file" ]]; then
        log_warning "Fixture not found (skipping): ${fixture_type}/${domain}/${fixture_name}"
        return 0
    fi

    log_info "Checking drift: ${domain}/${fixture_name}"

    # Extract current schema
    local old_schema=$(extract_schema "$fixture_file")

    # Record fresh fixture to temp location
    local temp_dir=$(mktemp -d)
    local temp_manifest="${temp_dir}/manifest.yaml"

    # Create minimal manifest for this single fixture
    yq ".fixtures.${domain}.${fixture_name}" "$MANIFEST_FILE" > "$temp_manifest.partial"
    echo "fixtures:" > "$temp_manifest"
    echo "  ${domain}:" >> "$temp_manifest"
    echo "    ${fixture_name}:" >> "$temp_manifest"
    yq '.' "$temp_manifest.partial" | sed 's/^/      /' >> "$temp_manifest"

    # Temporarily override manifest location
    export MANIFEST_FILE="$temp_manifest"

    # Record fresh fixture (suppress output)
    if bash "$RECORD_SCRIPT" --fixture "$domain" "$fixture_name" >/dev/null 2>&1; then
        local new_fixture="${temp_dir}/${fixture_type}/${domain}/${fixture_name}.json"

        if [[ -f "$new_fixture" ]]; then
            local new_schema=$(extract_schema "$new_fixture")

            # Compare schemas
            if ! compare_schemas "$old_schema" "$new_schema" "${fixture_type}/${domain}/${fixture_name}"; then
                ((DRIFT_DETECTED++))
                DRIFTED_FIXTURES+=("${domain}/${fixture_name}")
            else
                log_success "No drift: ${domain}/${fixture_name}"
            fi
        else
            log_error "Failed to record fresh fixture for comparison"
        fi
    else
        log_error "Failed to record ${domain}/${fixture_name}"
    fi

    # Cleanup
    rm -rf "$temp_dir"
    unset MANIFEST_FILE
}

# Check all fixtures for a domain
check_domain_drift() {
    local domain="$1"

    log_info "Checking drift for domain: $domain"

    # Get all fixtures for domain
    local fixture_names=$(yq ".fixtures.${domain} | keys | .[]" "$MANIFEST_FILE")

    if [[ -z "$fixture_names" ]]; then
        log_warning "No fixtures defined for domain: $domain"
        return 0
    fi

    while IFS= read -r fixture_name; do
        local fixture_type=$(yq ".fixtures.${domain}.${fixture_name}.type" "$MANIFEST_FILE")
        check_fixture_drift "$domain" "$fixture_name" "$fixture_type"
    done <<< "$fixture_names"
}

# Check all fixtures from manifest
check_all_drift() {
    log_info "Checking drift for all fixtures"

    # Get all domains
    local domains=$(yq '.fixtures | keys | .[]' "$MANIFEST_FILE")

    if [[ -z "$domains" ]]; then
        log_error "No domains found in manifest"
        return 1
    fi

    while IFS= read -r domain; do
        check_domain_drift "$domain"
    done <<< "$domains"

    # Summary
    echo ""
    echo "========================================"
    echo "Drift Detection Summary"
    echo "========================================"
    echo "Total fixtures checked: $TOTAL_CHECKED"
    echo "Fixtures with drift: $DRIFT_DETECTED"

    if [[ $DRIFT_DETECTED -gt 0 ]]; then
        echo ""
        echo "Drifted fixtures:"
        printf '%s\n' "${DRIFTED_FIXTURES[@]}" | sed 's/^/  - /'
        echo ""
        log_error "Drift detected! Review changes and update fixtures."
        return 1
    else
        echo ""
        log_success "No drift detected - all fixtures match current API schema"
        return 0
    fi
}

# =============================================================================
# USAGE
# =============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Detect schema drift in recorded fixtures by comparing against live API.

OPTIONS:
    --all                   Check all fixtures for drift
    --domain DOMAIN         Check all fixtures for specific domain
    --fixture DOMAIN NAME   Check single fixture
    --help                 Show this help message

EXAMPLES:
    # Check all fixtures
    $(basename "$0") --all

    # Check milestone domain
    $(basename "$0") --domain milestone

    # Check single fixture
    $(basename "$0") --fixture identity viewer

EXIT CODES:
    0 - No drift detected
    1 - Drift detected or error occurred

DRIFT DETECTION:
    - Records fresh fixtures to temporary location
    - Extracts schema structure (not values)
    - Compares field names and types
    - Reports new, removed, or changed fields
    - Does NOT compare data values (only structure)

USE IN CI:
    # Fail build if drift detected
    ./detect_fixture_drift.bash --all || exit 1

    # Create GitHub issue if drift detected
    if ! ./detect_fixture_drift.bash --all; then
        gh issue create --title "Fixture drift detected" ...
    fi

EOF
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    # Check manifest exists
    if [[ ! -f "$MANIFEST_FILE" ]]; then
        log_error "Manifest file not found: $MANIFEST_FILE"
        exit 1
    fi

    # Parse arguments
    if [[ $# -eq 0 ]]; then
        usage
        exit 0
    fi

    case "$1" in
        --all)
            check_all_drift
            ;;
        --domain)
            if [[ -z "${2:-}" ]]; then
                log_error "Domain name required"
                usage
                exit 1
            fi
            check_domain_drift "$2"
            exit $?
            ;;
        --fixture)
            if [[ -z "${2:-}" ]] || [[ -z "${3:-}" ]]; then
                log_error "Domain and fixture name required"
                usage
                exit 1
            fi
            local fixture_type=$(yq ".fixtures.$2.$3.type" "$MANIFEST_FILE")
            check_fixture_drift "$2" "$3" "$fixture_type"
            exit $?
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
}

main "$@"
