#!/usr/bin/env bash
# Fixture Recording Script
# Records fixtures from live GitHub APIs with setup/teardown and sanitization
#
# Uses the shared resource management library (tests/lib/resources/) for
# creating and cleaning up test resources during fixture recording.

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="${SCRIPT_DIR%/*}"
TESTS_DIR="${FIXTURES_DIR%/*}"
PROJECT_ROOT="${TESTS_DIR%/*}"
MANIFEST_FILE="${FIXTURES_DIR}/recording_manifest.yaml"
SANITIZE_SCRIPT="${SCRIPT_DIR}/sanitize_fixture.bash"
RESOURCES_DIR="${TESTS_DIR}/lib/resources"

# Default test targets
: "${TEST_ORG:=hiivmind}"
: "${TEST_REPO:=hiivmind-pulse-gh}"

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
# RESOURCE MANAGEMENT INTEGRATION
# =============================================================================

# Load resource management library
load_resource_library() {
    if [[ -d "$RESOURCES_DIR" ]]; then
        source "${RESOURCES_DIR}/core.bash"
        source "${RESOURCES_DIR}/milestone.bash"
        source "${RESOURCES_DIR}/issue.bash"
        source "${RESOURCES_DIR}/label.bash"
        source "${RESOURCES_DIR}/variable.bash"
        source "${RESOURCES_DIR}/release.bash"
        source "${RESOURCES_DIR}/protection.bash"
        source "${RESOURCES_DIR}/pr.bash"
        source "${RESOURCES_DIR}/project.bash"
        log_success "Resource management library loaded"
        return 0
    else
        log_warning "Resource library not found at $RESOURCES_DIR"
        log_warning "Setup/teardown features will be disabled"
        return 1
    fi
}

# Run setup actions for a fixture
# Usage: run_setup DOMAIN FIXTURE_NAME
run_setup() {
    local domain="$1"
    local fixture_name="$2"

    # Check if setup is defined
    local setup_count=$(yq ".fixtures.${domain}.${fixture_name}.setup | length // 0" "$MANIFEST_FILE")

    if [[ "$setup_count" == "0" ]] || [[ "$setup_count" == "null" ]]; then
        return 0
    fi

    log_info "Running setup for ${domain}/${fixture_name}..."

    # Get fixture-specific test targets (override global defaults)
    local fixture_test_org=$(yq ".fixtures.${domain}.${fixture_name}.test_org // \"${TEST_ORG}\"" "$MANIFEST_FILE")
    local fixture_test_repo=$(yq ".fixtures.${domain}.${fixture_name}.test_repo // \"${TEST_REPO}\"" "$MANIFEST_FILE")

    # Use fixture-specific values for this setup
    TEST_ORG="$fixture_test_org"
    TEST_REPO="$fixture_test_repo"

    # Setup cleanup trap
    setup_cleanup_trap

    # Process each setup action
    for i in $(seq 0 $((setup_count - 1))); do
        local resource_type=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].resource" "$MANIFEST_FILE")
        local action=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].action // \"\"" "$MANIFEST_FILE")
        local capture_var=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].capture // \"\"" "$MANIFEST_FILE")

        if [[ "$action" == "ensure_empty" ]]; then
            log_info "  Ensuring no ${resource_type}s exist..."
            ensure_empty "$resource_type" "$TEST_ORG" "$TEST_REPO"
            continue
        fi

        if [[ "$resource_type" != "null" && -n "$resource_type" ]]; then
            local title=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].params.title // \"\"" "$MANIFEST_FILE")
            local description=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].params.description // \"\"" "$MANIFEST_FILE")
            local name=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].params.name // \"\"" "$MANIFEST_FILE")
            local value=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].params.value // \"\"" "$MANIFEST_FILE")

            # NOTE: We use command substitution to capture the result, but this runs in a subshell
            # so track_resource() calls inside the create_* functions won't update TRACKED_RESOURCES
            # in the parent shell. We must track resources explicitly here after capturing the result.
            case "$resource_type" in
                milestone)
                    log_info "  Creating milestone: $title"
                    local result=$(create_milestone_raw "$TEST_ORG" "$TEST_REPO" "$title" "$description")
                    track_resource "milestone" "${TEST_ORG}/${TEST_REPO}/${result}"
                    if [[ -n "$capture_var" ]]; then
                        export "$capture_var"="$result"
                        log_info "  Captured $capture_var=$result"
                    fi
                    ;;
                issue)
                    log_info "  Creating issue: $title"
                    local result=$(create_issue_raw "$TEST_ORG" "$TEST_REPO" "$title" "$description")
                    track_resource "issue" "${TEST_ORG}/${TEST_REPO}/${result}"
                    if [[ -n "$capture_var" ]]; then
                        export "$capture_var"="$result"
                        log_info "  Captured $capture_var=$result"
                    fi
                    ;;
                label)
                    log_info "  Creating label: $name"
                    local result=$(create_label_raw "$TEST_ORG" "$TEST_REPO" "$name")
                    track_resource "label" "${TEST_ORG}/${TEST_REPO}/${result}"
                    ;;
                variable)
                    log_info "  Creating variable: $name"
                    local result=$(create_variable_raw "$TEST_ORG" "$TEST_REPO" "$name" "$value")
                    track_resource "variable" "${TEST_ORG}/${TEST_REPO}/${result}"
                    ;;
                pr)
                    log_info "  Creating test PR: $title"
                    local result=$(create_test_pr_raw "$TEST_ORG" "$TEST_REPO" "$title")
                    track_resource "pr" "${TEST_ORG}/${TEST_REPO}/${result}"
                    if [[ -n "$capture_var" ]]; then
                        export "$capture_var"="$result"
                        log_info "  Captured $capture_var=$result"
                    fi
                    ;;
                release)
                    local tag_name=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].params.tag_name // \"\"" "$MANIFEST_FILE")
                    local body=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].params.body // \"\"" "$MANIFEST_FILE")
                    log_info "  Creating release: $name ($tag_name)"
                    local result=$(create_release_raw "$TEST_ORG" "$TEST_REPO" "$tag_name" "$name" "$body")
                    track_resource "release" "${TEST_ORG}/${TEST_REPO}/${result}"
                    if [[ -n "$capture_var" ]]; then
                        export "$capture_var"="$result"
                        log_info "  Captured $capture_var=$result"
                    fi
                    ;;
                project_item)
                    local project_number=$(yq ".fixtures.${domain}.${fixture_name}.setup[$i].params.project_number // \"\"" "$MANIFEST_FILE")
                    log_info "  Creating draft project item: $title"
                    local result=$(create_draft_item_raw "$TEST_ORG" "$project_number" "$title" "$description")
                    track_resource "project_item" "${TEST_ORG}/${project_number}/${result}"
                    if [[ -n "$capture_var" ]]; then
                        export "$capture_var"="$result"
                        log_info "  Captured $capture_var=$result"
                    fi
                    ;;
                *)
                    log_warning "  Unknown resource type: $resource_type"
                    ;;
            esac
        fi
    done

    log_success "Setup complete"
}

# Run teardown (automatic via cleanup trap)
run_teardown() {
    log_info "Running teardown..."
    cleanup_tracked_resources
    log_success "Teardown complete"
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

    # Run setup (creates test resources if defined in manifest)
    if [[ -n "${RESOURCES_LOADED:-}" ]]; then
        run_setup "$domain" "$fixture_name"
    fi

    # Record based on type
    local record_success=true
    case "$fixture_type" in
        graphql)
            record_graphql_fixture "$domain" "$fixture_name" "$output_file" || record_success=false
            ;;
        rest)
            record_rest_fixture "$domain" "$fixture_name" "$output_file" || record_success=false
            ;;
        *)
            log_error "Unknown fixture type: $fixture_type"
            record_success=false
            ;;
    esac

    # Run teardown (automatic via trap, but also explicit for clarity)
    if [[ -n "${RESOURCES_LOADED:-}" ]] && [[ -n "${TRACKED_RESOURCES:-}" ]]; then
        run_teardown
    fi

    if [[ "$record_success" == "false" ]]; then
        return 1
    fi

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
    local variables_json=$(yq -o=json ".fixtures.${domain}.${fixture_name}.variables // {}" "$MANIFEST_FILE")

    if [[ "$query" == "null" ]]; then
        log_error "No query defined for ${domain}/${fixture_name}"
        return 1
    fi

    # Build command arguments
    local args=(-f "query=$query")

    # Add variables as individual flags
    if [[ "$variables_json" != "{}" ]] && [[ "$variables_json" != "null" ]]; then
        # Extract each variable and add as -f or -F flag
        while IFS='=' read -r key value; do
            # Determine if value is a number (use -F) or string (use -f)
            if [[ "$value" =~ ^[0-9]+$ ]]; then
                args+=(-F "$key=$value")
            else
                # Remove quotes from string values
                value="${value%\"}"
                value="${value#\"}"
                args+=(-f "$key=$value")
            fi
        done < <(echo "$variables_json" | jq -r 'to_entries[] | "\(.key)=\(.value)"')
    fi

    # Execute GraphQL query
    gh api graphql "${args[@]}" > "$output_file"
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

    # Replace standard variables in endpoint
    endpoint="${endpoint//\{owner\}/$test_org}"
    endpoint="${endpoint//\{repo\}/$test_repo}"

    # Replace any captured variables (exported by setup)
    # Match {variable_name} patterns and substitute with environment variables
    while [[ "$endpoint" =~ \{([a-zA-Z_][a-zA-Z0-9_]*)\} ]]; do
        local var_name="${BASH_REMATCH[1]}"
        local var_value="${!var_name:-}"
        if [[ -n "$var_value" ]]; then
            endpoint="${endpoint//\{$var_name\}/$var_value}"
        else
            log_warning "Variable $var_name not found for endpoint substitution"
            break
        fi
    done

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
            ((count++)) || true
        else
            ((failed++)) || true
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
            ((total++)) || true
        else
            ((failed++)) || true
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

    # Load resource management library for setup/teardown
    if load_resource_library; then
        RESOURCES_LOADED=true
    else
        RESOURCES_LOADED=""
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
