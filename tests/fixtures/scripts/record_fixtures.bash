#!/usr/bin/env bash
# Fixture Recording Script
# Records fixtures from live GitHub APIs with sanitization

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="${SCRIPT_DIR%/*}"
PROJECT_ROOT="${FIXTURES_DIR%/*}/.."
MANIFEST_FILE="${FIXTURES_DIR}/recording_manifest.yaml"
SANITIZE_SCRIPT="${SCRIPT_DIR}/sanitize_fixture.bash"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check prerequisites
check_prerequisites() {
    local missing=()

    if ! command -v gh &> /dev/null; then
        missing+=("gh (GitHub CLI)")
    fi

    if ! command -v jq &> /dev/null; then
        missing+=("jq")
    fi

    if ! command -v yq &> /dev/null; then
        missing+=("yq")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        return 1
    fi

    # Check gh auth
    if ! gh auth status &> /dev/null; then
        log_error "GitHub CLI not authenticated. Run: gh auth login"
        return 1
    fi

    log_success "All prerequisites met"
}

# =============================================================================
# RECORDING FUNCTIONS
# =============================================================================

# Record a single fixture
# Usage: record_fixture DOMAIN FIXTURE_NAME
record_fixture() {
    local domain="$1"
    local fixture_name="$2"

    log_info "Recording fixture: ${domain}/${fixture_name}"

    # Get fixture config from manifest
    local fixture_type=$(yq ".fixtures.${domain}.${fixture_name}.type" "$MANIFEST_FILE")

    if [[ "$fixture_type" == "null" ]]; then
        log_error "Fixture ${domain}/${fixture_name} not found in manifest"
        return 1
    fi

    # Determine output path
    local output_dir="${FIXTURES_DIR}/${fixture_type}/${domain}"
    mkdir -p "$output_dir"
    local output_file="${output_dir}/${fixture_name}.json"

    # Record based on type
    case "$fixture_type" in
        graphql)
            record_graphql_fixture "$domain" "$fixture_name" "$output_file"
            ;;
        rest)
            record_rest_fixture "$domain" "$fixture_name" "$output_file"
            ;;
        *)
            log_error "Unknown fixture type: $fixture_type"
            return 1
            ;;
    esac

    # Sanitize if script exists
    if [[ -f "$SANITIZE_SCRIPT" ]]; then
        log_info "Sanitizing fixture..."
        bash "$SANITIZE_SCRIPT" "$domain" "$fixture_name" "$output_file"
    fi

    # Update last recorded timestamp
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    yq -i ".fixtures.${domain}.${fixture_name}.last_recorded = \"$timestamp\"" "$MANIFEST_FILE"

    log_success "Recorded: $output_file"
}

# Record GraphQL fixture
record_graphql_fixture() {
    local domain="$1"
    local fixture_name="$2"
    local output_file="$3"

    local query=$(yq ".fixtures.${domain}.${fixture_name}.query" "$MANIFEST_FILE")
    local variables=$(yq ".fixtures.${domain}.${fixture_name}.variables // {}" "$MANIFEST_FILE")

    if [[ "$query" == "null" ]]; then
        log_error "No query defined for ${domain}/${fixture_name}"
        return 1
    fi

    # Execute GraphQL query
    if [[ "$variables" != "{}" ]] && [[ "$variables" != "null" ]]; then
        gh api graphql -f query="$query" --input <(echo "$variables") > "$output_file"
    else
        gh api graphql -f query="$query" > "$output_file"
    fi
}

# Record REST fixture
record_rest_fixture() {
    local domain="$1"
    local fixture_name="$2"
    local output_file="$3"

    local endpoint=$(yq ".fixtures.${domain}.${fixture_name}.endpoint" "$MANIFEST_FILE")
    local method=$(yq ".fixtures.${domain}.${fixture_name}.method // \"GET\"" "$MANIFEST_FILE")
    local test_org=$(yq ".fixtures.${domain}.${fixture_name}.test_org // \"hiivmind\"" "$MANIFEST_FILE")
    local test_repo=$(yq ".fixtures.${domain}.${fixture_name}.test_repo // \"hiivmind-pulse-gh\"" "$MANIFEST_FILE")

    if [[ "$endpoint" == "null" ]]; then
        log_error "No endpoint defined for ${domain}/${fixture_name}"
        return 1
    fi

    # Replace variables in endpoint
    endpoint="${endpoint//\{owner\}/$test_org}"
    endpoint="${endpoint//\{repo\}/$test_repo}"

    # Execute REST API call
    gh api "$endpoint" -X "$method" > "$output_file"
}

# =============================================================================
# BATCH RECORDING
# =============================================================================

# Record all fixtures for a domain
record_domain() {
    local domain="$1"

    log_info "Recording all fixtures for domain: $domain"

    # Get all fixture names for domain
    local fixture_names=$(yq ".fixtures.${domain} | keys | .[]" "$MANIFEST_FILE")

    if [[ -z "$fixture_names" ]]; then
        log_warning "No fixtures defined for domain: $domain"
        return 0
    fi

    local count=0
    local failed=0

    while IFS= read -r fixture_name; do
        if record_fixture "$domain" "$fixture_name"; then
            ((count++))
        else
            ((failed++))
        fi
    done <<< "$fixture_names"

    log_success "Domain $domain: $count fixtures recorded, $failed failed"
}

# Record all fixtures from manifest
record_all() {
    log_info "Recording all fixtures from manifest"

    # Get all domains
    local domains=$(yq '.fixtures | keys | .[]' "$MANIFEST_FILE")

    if [[ -z "$domains" ]]; then
        log_error "No domains found in manifest"
        return 1
    fi

    local total=0
    local failed=0

    while IFS= read -r domain; do
        if record_domain "$domain"; then
            ((total++))
        else
            ((failed++))
        fi
    done <<< "$domains"

    log_success "Total: $total domains recorded, $failed failed"
}

# =============================================================================
# USAGE
# =============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Record test fixtures from live GitHub APIs.

OPTIONS:
    --all                   Record all fixtures from manifest
    --domain DOMAIN         Record all fixtures for specific domain
    --fixture DOMAIN NAME   Record single fixture
    --dry-run              Show what would be recorded without executing
    --help                 Show this help message

EXAMPLES:
    # Record single fixture
    $(basename "$0") --fixture identity viewer

    # Record all milestone fixtures
    $(basename "$0") --domain milestone

    # Record all fixtures
    $(basename "$0") --all

NOTES:
    - Requires authenticated GitHub CLI (gh auth login)
    - Uses recording_manifest.yaml to determine what to record
    - Automatically sanitizes fixtures after recording
    - Updates last_recorded timestamp in manifest

EOF
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    # Check prerequisites
    check_prerequisites || exit 1

    # Check manifest exists
    if [[ ! -f "$MANIFEST_FILE" ]]; then
        log_error "Manifest file not found: $MANIFEST_FILE"
        log_info "Create one using recording_manifest.yaml template"
        exit 1
    fi

    # Parse arguments
    if [[ $# -eq 0 ]]; then
        usage
        exit 0
    fi

    case "$1" in
        --all)
            record_all
            ;;
        --domain)
            if [[ -z "${2:-}" ]]; then
                log_error "Domain name required"
                usage
                exit 1
            fi
            record_domain "$2"
            ;;
        --fixture)
            if [[ -z "${2:-}" ]] || [[ -z "${3:-}" ]]; then
                log_error "Domain and fixture name required"
                usage
                exit 1
            fi
            record_fixture "$2" "$3"
            ;;
        --dry-run)
            log_info "Dry run mode - would record from manifest"
            yq '.fixtures | keys | .[]' "$MANIFEST_FILE"
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
