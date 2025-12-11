#!/bin/bash
# tests/fixtures/scripts/detect_drift.bash
# Detects schema drift between recorded fixtures and live GitHub API responses
#
# This script compares the structure (keys/fields) of recorded fixtures against
# live API responses to detect when GitHub changes their API schema.
#
# Usage:
#   ./detect_drift.bash                    # Check all fixtures
#   ./detect_drift.bash --domain identity  # Check specific domain
#   ./detect_drift.bash --verbose          # Show detailed diff output
#   ./detect_drift.bash --update           # Update fixtures with new schema

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="${SCRIPT_DIR}/.."
MANIFEST_FILE="${FIXTURES_DIR}/recording_manifest.yaml"

# =============================================================================
# CONFIGURATION
# =============================================================================

VERBOSE="${VERBOSE:-false}"
UPDATE_MODE="${UPDATE_MODE:-false}"
DOMAIN_FILTER=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# LOGGING
# =============================================================================

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_drift() { echo -e "${YELLOW}[DRIFT]${NC} $*"; }

# =============================================================================
# ARGUMENT PARSING
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --domain)
                DOMAIN_FILTER="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE="true"
                shift
                ;;
            --update)
                UPDATE_MODE="true"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --domain DOMAIN  Check only specific domain"
                echo "  --verbose, -v    Show detailed diff output"
                echo "  --update         Update fixtures with new schema (re-record)"
                echo "  --help, -h       Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

# =============================================================================
# SCHEMA EXTRACTION
# =============================================================================

# Extract schema (field names only, ignoring values) from JSON
# This extracts a "skeleton" of the JSON structure
# Includes both scalar values AND null fields
extract_schema() {
    local json_file="$1"

    # Use jq to extract all paths (scalars and nulls)
    jq -r '
        [paths(scalars), paths(. == null)] | flatten(1) |
        sort |
        map(
            map(
                if type == "number" then "[*]"
                else .
                end
            ) |
            join(".")
        ) |
        unique |
        .[]
    ' "$json_file" 2>/dev/null | sort
}

# Extract schema from a JSON string
extract_schema_from_string() {
    local json_string="$1"

    echo "$json_string" | jq -r '
        [paths(scalars), paths(. == null)] | flatten(1) |
        sort |
        map(
            map(
                if type == "number" then "[*]"
                else .
                end
            ) |
            join(".")
        ) |
        unique |
        .[]
    ' 2>/dev/null | sort
}

# =============================================================================
# DRIFT DETECTION
# =============================================================================

# Compare schemas and report drift
compare_schemas() {
    local fixture_schema="$1"
    local live_schema="$2"
    local fixture_name="$3"

    local added_fields=""
    local removed_fields=""

    # Find fields in live but not in fixture (added fields)
    added_fields=$(comm -23 <(echo "$live_schema") <(echo "$fixture_schema"))

    # Find fields in fixture but not in live (removed fields)
    removed_fields=$(comm -13 <(echo "$live_schema") <(echo "$fixture_schema"))

    local has_drift=false

    if [[ -n "$added_fields" ]]; then
        has_drift=true
        log_drift "${fixture_name}: New fields detected in API response:"
        while IFS= read -r field; do
            echo "  + $field"
        done <<< "$added_fields"
    fi

    if [[ -n "$removed_fields" ]]; then
        has_drift=true
        log_drift "${fixture_name}: Fields missing from API response:"
        while IFS= read -r field; do
            echo "  - $field"
        done <<< "$removed_fields"
    fi

    if [[ "$has_drift" == "true" ]]; then
        return 1
    fi

    return 0
}

# =============================================================================
# LIVE API QUERIES
# =============================================================================

# Fetch live response for a GraphQL fixture
fetch_live_graphql() {
    local domain="$1"
    local fixture_name="$2"

    local query=$(yq ".fixtures.${domain}.${fixture_name}.query" "$MANIFEST_FILE")
    local variables_json=$(yq -o=json ".fixtures.${domain}.${fixture_name}.variables // {}" "$MANIFEST_FILE")

    if [[ "$query" == "null" ]]; then
        return 1
    fi

    # Build command arguments
    local args=(-f "query=$query")

    # Add variables as individual flags
    if [[ "$variables_json" != "{}" ]] && [[ "$variables_json" != "null" ]]; then
        while IFS='=' read -r key value; do
            if [[ "$value" =~ ^[0-9]+$ ]]; then
                args+=(-F "$key=$value")
            else
                value="${value%\"}"
                value="${value#\"}"
                args+=(-f "$key=$value")
            fi
        done < <(echo "$variables_json" | jq -r 'to_entries[] | "\(.key)=\(.value)"')
    fi

    gh api graphql "${args[@]}" 2>/dev/null
}

# Fetch live response for a REST fixture
fetch_live_rest() {
    local domain="$1"
    local fixture_name="$2"

    local endpoint=$(yq ".fixtures.${domain}.${fixture_name}.endpoint" "$MANIFEST_FILE")
    local method=$(yq ".fixtures.${domain}.${fixture_name}.method // \"GET\"" "$MANIFEST_FILE")
    local test_org=$(yq ".fixtures.${domain}.${fixture_name}.test_org // \"hiivmind\"" "$MANIFEST_FILE")
    local test_repo=$(yq ".fixtures.${domain}.${fixture_name}.test_repo // \"hiivmind-pulse-test-fixtures\"" "$MANIFEST_FILE")

    if [[ "$endpoint" == "null" ]]; then
        return 1
    fi

    # Replace variables in endpoint
    endpoint="${endpoint//\{owner\}/$test_org}"
    endpoint="${endpoint//\{repo\}/$test_repo}"

    # Skip fixtures with dynamic variables (like milestone_number)
    if [[ "$endpoint" =~ \{[a-zA-Z_]+\} ]]; then
        echo "SKIP_DYNAMIC"
        return 0
    fi

    gh api "$endpoint" -X "$method" 2>/dev/null
}

# =============================================================================
# MAIN DETECTION LOGIC
# =============================================================================

check_fixture() {
    local domain="$1"
    local fixture_name="$2"

    local fixture_type=$(yq ".fixtures.${domain}.${fixture_name}.type" "$MANIFEST_FILE")

    if [[ "$fixture_type" == "null" ]]; then
        return 1
    fi

    # Determine fixture path
    local fixture_path="${FIXTURES_DIR}/${fixture_type}/${domain}/${fixture_name}.json"

    if [[ ! -f "$fixture_path" ]]; then
        log_warning "Fixture not found: $fixture_path"
        return 1
    fi

    # Skip synthetic fixtures
    if [[ "$fixture_path" == *"_synthetic"* ]]; then
        [[ "$VERBOSE" == "true" ]] && log_info "Skipping synthetic fixture: ${domain}/${fixture_name}"
        return 0
    fi

    # Fetch live response
    local live_response=""

    case "$fixture_type" in
        graphql)
            live_response=$(fetch_live_graphql "$domain" "$fixture_name")
            ;;
        rest)
            live_response=$(fetch_live_rest "$domain" "$fixture_name")
            ;;
        *)
            log_warning "Unknown fixture type: $fixture_type"
            return 1
            ;;
    esac

    # Check for dynamic fixture skip
    if [[ "$live_response" == "SKIP_DYNAMIC" ]]; then
        [[ "$VERBOSE" == "true" ]] && log_info "Skipping dynamic fixture: ${domain}/${fixture_name}"
        return 0
    fi

    if [[ -z "$live_response" ]]; then
        log_warning "Failed to fetch live response for ${domain}/${fixture_name}"
        return 1
    fi

    # Extract and compare schemas
    local fixture_schema=$(extract_schema "$fixture_path")
    local live_schema=$(extract_schema_from_string "$live_response")

    if compare_schemas "$fixture_schema" "$live_schema" "${domain}/${fixture_name}"; then
        [[ "$VERBOSE" == "true" ]] && log_success "No drift: ${domain}/${fixture_name}"
        return 0
    else
        if [[ "$UPDATE_MODE" == "true" ]]; then
            log_info "Updating fixture: ${domain}/${fixture_name}"
            "${SCRIPT_DIR}/record_fixtures.bash" --fixture "${domain}/${fixture_name}"
        fi
        return 1
    fi
}

check_domain() {
    local domain="$1"
    local drift_count=0
    local check_count=0

    log_info "Checking domain: $domain"

    local fixture_names=$(yq ".fixtures.${domain} | keys | .[]" "$MANIFEST_FILE" 2>/dev/null)

    if [[ -z "$fixture_names" ]]; then
        log_warning "No fixtures defined for domain: $domain"
        return 0
    fi

    while IFS= read -r fixture_name; do
        # Skip fixtures with setup (they require ephemeral resources)
        local has_setup=$(yq ".fixtures.${domain}.${fixture_name}.setup | length // 0" "$MANIFEST_FILE")
        if [[ "$has_setup" -gt 0 ]]; then
            [[ "$VERBOSE" == "true" ]] && log_info "Skipping fixture with setup: ${domain}/${fixture_name}"
            continue
        fi

        ((check_count++)) || true

        if ! check_fixture "$domain" "$fixture_name"; then
            ((drift_count++)) || true
        fi
    done <<< "$fixture_names"

    if [[ "$drift_count" -gt 0 ]]; then
        log_warning "Domain $domain: ${drift_count}/${check_count} fixtures have drift"
        return 1
    else
        log_success "Domain $domain: ${check_count} fixtures checked, no drift"
        return 0
    fi
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    parse_args "$@"

    # Verify prerequisites
    if ! command -v gh &>/dev/null; then
        log_error "gh CLI is required but not installed"
        exit 1
    fi

    if ! command -v yq &>/dev/null; then
        log_error "yq is required but not installed"
        exit 1
    fi

    if [[ ! -f "$MANIFEST_FILE" ]]; then
        log_error "Manifest file not found: $MANIFEST_FILE"
        exit 1
    fi

    log_info "Starting drift detection..."

    local total_drift=0
    local domains_checked=0

    # Get list of domains
    local domains
    if [[ -n "$DOMAIN_FILTER" ]]; then
        domains="$DOMAIN_FILTER"
    else
        domains=$(yq '.fixtures | keys | .[]' "$MANIFEST_FILE")
    fi

    while IFS= read -r domain; do
        ((domains_checked++)) || true
        if ! check_domain "$domain"; then
            ((total_drift++)) || true
        fi
    done <<< "$domains"

    echo ""
    if [[ "$total_drift" -gt 0 ]]; then
        log_warning "Drift detected in $total_drift domain(s)"
        echo ""
        echo "To update fixtures with new schema, run:"
        echo "  $0 --update"
        exit 1
    else
        log_success "No schema drift detected across $domains_checked domain(s)"
        exit 0
    fi
}

main "$@"
