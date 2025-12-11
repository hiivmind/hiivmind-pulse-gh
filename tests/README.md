# Testing Framework

> **Status:** Phase 1 Complete (Foundation & Helper Library)
> **Coverage:** Project domain only (10 other domains pending)

This directory contains the test suite for hiivmind-pulse-gh. The framework is organized by test type (unit, integration, E2E) and follows domain-based architecture.

## Quick Start

```bash
# Run all tests
bats tests/

# Run unit tests only
bats tests/unit/

# Run integration tests only
bats tests/integration/

# Run E2E tests (requires GitHub auth)
bats tests/e2e/

# Run tests for specific domain
bats tests/unit/domain/project/
```

## Directory Structure

```
tests/
├── test_helper.bash              # Main test helper (loads all helpers)
│
├── bats-helpers/                 # Modular helper library
│   ├── assertions.bash           # Enhanced JSON/API assertions
│   ├── fixtures.bash             # Domain-aware fixture loading
│   └── mocks.bash                # Mock setup utilities
│
├── fixtures/                     # Centralized fixture library
│   ├── graphql/                  # GraphQL response fixtures
│   │   ├── identity/
│   │   ├── repository/
│   │   ├── project/              # ✅ Available
│   │   ├── issue/
│   │   ├── pr/
│   │   └── ...                   # Other domains pending Phase 2
│   ├── rest/                     # REST API response fixtures
│   │   ├── milestone/
│   │   ├── protection/
│   │   └── ...
│   └── generators/               # Fixture generation scripts (Phase 2)
│
├── mocks/                        # Mock gh CLI (Phase 3)
│   ├── gh                        # Mock executable (to be enhanced)
│   ├── registry.bash             # Request routing (pending)
│   └── handlers/                 # Domain-specific handlers (pending)
│
├── unit/                         # Pure function tests (jq filters)
│   └── domain/
│       ├── identity/             # Pending Phase 4
│       ├── repository/           # Pending Phase 4
│       ├── milestone/            # Pending Phase 4
│       ├── issue/                # Pending Phase 4
│       ├── pr/                   # Pending Phase 4
│       ├── project/              # ✅ Partial coverage
│       ├── protection/           # Pending Phase 4
│       ├── action/               # Pending Phase 4
│       ├── secret/               # Pending Phase 4
│       ├── variable/             # Pending Phase 4
│       └── release/              # Pending Phase 4
│
├── integration/                  # Mock-based function tests
│   ├── domain/                   # Per-domain tests (Phase 5)
│   └── cross-domain/             # Pipeline tests (Phase 5)
│
└── e2e/                          # Live API tests
    ├── sandbox/                  # Resource management (Phase 6)
    ├── domain/                   # Per-domain E2E (Phase 6)
    └── smoke/                    # Connectivity tests (Phase 6)
```

## Writing Tests

### Unit Tests (jq Filters)

Unit tests validate jq filters in isolation using fixtures.

**Template:**

```bash
#!/usr/bin/env bats
# Unit tests for {domain} jq filters

setup() {
    load '../../test_helper'
    DOMAIN="milestone"
}

@test "format_milestones_list produces valid TSV" {
    local fixture=$(load_rest_fixture "$DOMAIN" "list_all")
    local filter=$(get_domain_filter "$DOMAIN" ".filters.format_milestones_list")

    local result=$(echo "$fixture" | jq -r "$filter")

    assert_valid_json "$fixture"
    echo "$result" | grep -q "TITLE"  # Check for header
}
```

**Run:**
```bash
bats tests/unit/domain/milestone/test_filters.bats
```

### Integration Tests (Function Composition)

Integration tests validate function behavior with mocked `gh` CLI.

**Template:**

```bash
#!/usr/bin/env bats
# Integration tests for {domain} functions

setup() {
    load '../../test_helper'
    source_domain_lib "milestone"
    setup_mock_gh

    # Configure mock responses
    mock_rest_response "repos/.*/milestones" "milestone/list_all.json"
}

teardown() {
    teardown_mock_gh
}

@test "discover_repo_milestones returns array" {
    run discover_repo_milestones "owner" "repo"

    assert_success
    assert_valid_json "$output"
    assert_json_array_not_empty "$output"
}
```

**Run:**
```bash
bats tests/integration/domain/milestone/
```

### E2E Tests (Live API)

E2E tests validate against real GitHub API with proper cleanup.

**Template:**

```bash
#!/usr/bin/env bats
# E2E tests for {domain}

setup() {
    load '../../test_helper'
    source "$TEST_DIR/e2e/sandbox/setup.bash"
    source_domain_lib "milestone"
}

teardown() {
    source "$TEST_DIR/e2e/sandbox/teardown.bash"
}

@test "create and fetch milestone" {
    # Create test milestone
    local title="bats-test-$(date +%s)"
    local milestone_number=$(create_test_milestone "$title")

    # Fetch it back
    run fetch_milestone "$TEST_ORG" "$TEST_REPO" "$milestone_number"

    assert_success
    assert_field_equals "$output" ".title" "$title"
}
```

**Requirements:**
- GitHub CLI authenticated
- Environment variables: `TEST_ORG`, `TEST_REPO`
- Appropriate permissions

**Run:**
```bash
# Setup environment
export TEST_ORG="hiivmind"
export TEST_REPO="test-sandbox"

bats tests/e2e/domain/milestone/
```

## Helper Functions

### Assertions (`bats-helpers/assertions.bash`)

**JSON Assertions:**
- `assert_json_equals EXPECTED ACTUAL` - Deep equality
- `assert_json_contains JSON FRAGMENT` - Partial match
- `assert_json_has_keys JSON KEY1 KEY2 ...` - Key existence
- `assert_json_array_length JSON LENGTH` - Array size
- `assert_json_array_not_empty JSON` - Non-empty array
- `assert_json_type JSON TYPE` - Type checking

**API Assertions:**
- `assert_api_success RESPONSE` - API success validation
- `assert_valid_json STRING` - JSON syntax validation

**Field Assertions:**
- `assert_field_not_null JSON PATH` - Field existence
- `assert_field_equals JSON PATH VALUE` - Field value match
- `assert_field_matches JSON PATH PATTERN` - Regex match

**GitHub-Specific:**
- `assert_valid_github_node_id VALUE` - Node ID format
- `assert_valid_iso8601_timestamp VALUE` - Timestamp format
- `assert_valid_repo_full_name VALUE` - owner/repo format

### Fixtures (`bats-helpers/fixtures.bash`)

**Loading Fixtures:**
- `load_fixture DOMAIN NAME [TYPE]` - Load centralized fixture
- `load_graphql_fixture DOMAIN NAME` - Load GraphQL fixture
- `load_rest_fixture DOMAIN NAME` - Load REST fixture
- `load_synthetic_fixture CATEGORY NAME` - Load hand-crafted fixture

**Loading Filters/Queries:**
- `get_domain_filter DOMAIN PATH` - Extract jq filter from YAML
- `get_filter FILENAME PATH` - Extract filter from any YAML
- `get_domain_query DOMAIN NAME` - Extract GraphQL query

**Utilities:**
- `source_domain_lib DOMAIN` - Source domain function library
- `fixture_exists DOMAIN NAME [TYPE]` - Check fixture existence
- `list_fixtures DOMAIN [TYPE]` - List available fixtures

### Mocks (`bats-helpers/mocks.bash`)

**Setup/Teardown:**
- `setup_mock_gh` - Activate mock `gh` in PATH
- `teardown_mock_gh` - Restore original PATH

**Configuration:**
- `mock_response PATTERN FIXTURE` - Map endpoint to fixture
- `mock_error PATTERN CODE [MESSAGE]` - Simulate error
- `mock_graphql_response QUERY FIXTURE` - Map GraphQL query

**Verification:**
- `assert_mock_gh_active` - Verify mock is active
- `assert_mock_called PATTERN [COUNT]` - Verify mock was called
- `get_mock_call_count PATTERN` - Get call count

**Modes:**
- `mock_enable_strict_mode` - Fail on unmapped requests
- `mock_enable_passthrough` - Forward unmapped to real gh
- `mock_enable_recording OUTPUT_DIR` - Record responses

## Fixture Organization

### Naming Convention

```
{domain}/{operation}[_{variant}].json
```

**Examples:**
- `milestone/list_all.json` - All milestones
- `milestone/list_open.json` - Open milestones only
- `milestone/get_single.json` - Single milestone detail
- `project/org_project_with_items.json` - Project with items
- `_synthetic/empty/array.json` - Empty array (hand-crafted)
- `_synthetic/errors/404.json` - 404 error (hand-crafted)

### Fixture Types

**GraphQL Fixtures** (`fixtures/graphql/{domain}/`)
- Recorded from live API (Phase 2)
- Contain `data` field wrapper
- Example domains: identity, repository, project, issue, pr, release

**REST Fixtures** (`fixtures/rest/{domain}/`)
- Recorded from live API (Phase 2)
- Direct JSON responses (no wrapper)
- Example domains: milestone, protection, action, secret, variable, release

**Synthetic Fixtures** (`fixtures/_synthetic/{category}/`)
- Hand-crafted for edge cases
- Categories: `empty`, `errors`, `null_fields`, `large_arrays`
- Clearly separated from live-recorded fixtures

## Running Tests Locally

### Prerequisites

```bash
# Install BATS
npm install

# Verify installation
npx bats --version
```

### Run All Tests

```bash
# From project root
bats tests/

# Verbose output
bats tests/ --tap

# Filter by test name
bats tests/ --filter "milestone"
```

### Run Specific Test Files

```bash
# Unit tests for project domain
bats tests/unit/test_jq_filters.bats

# Integration tests
bats tests/integration/test_fetch_functions.bats

# E2E tests (requires auth)
bats tests/e2e/test_live_api.bats
```

### Debug Failed Tests

```bash
# Run with verbose output
bats tests/unit/test_jq_filters.bats -t

# Run single test
bats tests/unit/test_jq_filters.bats --filter "format_project_items"

# Print all assertions
BATS_VERBOSE_RUN=1 bats tests/unit/test_jq_filters.bats
```

## Backward Compatibility

The Phase 1 refactor maintains full backward compatibility:

- ✅ Existing tests run without modification
- ✅ Old fixture loading paths still work
- ✅ Legacy assertions preserved
- ✅ Original mock system functional

**Deprecated Functions:**
- `assert_json_path()` → Use `assert_field_equals()`
- `fixture()` → Use `load_fixture()`
- Old `load_fixture()` → Use `load_fixture(DOMAIN, NAME)`

## CI Integration

Tests run automatically on:
- Pull requests
- Pushes to main
- Manual workflow dispatch

**GitHub Actions Workflow:**

```yaml
- name: Run unit tests
  run: bats tests/unit/

- name: Run integration tests
  run: bats tests/integration/

# E2E tests run only on main branch with secrets
- name: Run E2E tests
  if: github.ref == 'refs/heads/main'
  env:
    TEST_ORG: ${{ vars.TEST_ORG }}
    TEST_REPO: ${{ vars.TEST_REPO }}
    GH_TOKEN: ${{ secrets.TEST_GITHUB_TOKEN }}
  run: bats tests/e2e/
```

## Adding New Tests

### For New Domain

1. **Create directory structure:**
   ```bash
   mkdir -p tests/unit/domain/{domain}
   mkdir -p tests/integration/domain/{domain}
   mkdir -p tests/e2e/domain/{domain}
   ```

2. **Add unit tests** (Phase 4):
   - Test jq filters from `gh-{domain}-jq-filters.yaml`
   - Use centralized fixtures

3. **Add integration tests** (Phase 5):
   - Test function composition
   - Use mocked `gh` CLI

4. **Add E2E tests** (Phase 6):
   - Test critical user journeys
   - Use sandbox for resource management

### Adding Fixtures

**Wait for Phase 2** - Fixtures will be recorded from live API with proper sanitization.

For now, place temporary fixtures in:
- `tests/fixtures/graphql/{domain}/`
- `tests/fixtures/rest/{domain}/`

## Troubleshooting

### Tests fail with "fixture not found"

**Cause:** Centralized fixtures not yet created (Phase 2 pending)

**Fix:** Use legacy fixture paths temporarily:
```bash
# tests/unit/domain/milestone/fixtures/list_all.json
load_legacy_fixture "fixtures/list_all.json"
```

### Mock gh not working

**Cause:** Mock not in PATH

**Fix:**
```bash
setup() {
    load '../../test_helper'
    setup_mock_gh
    assert_mock_gh_active  # Verify mock is active
}
```

### E2E tests fail with auth error

**Cause:** GitHub CLI not authenticated or missing scopes

**Fix:**
```bash
# Authenticate
gh auth login

# Verify scopes
gh auth status

# Required scopes: repo, read:org, project
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Foundation & Helper Library |
| **Phase 2** | 🔜 Next | Centralized Fixture Library (Live Recording) |
| **Phase 3** | Pending | Enhanced Mock System |
| **Phase 4** | Pending | Unit Test Suite (All Domains) |
| **Phase 5** | Pending | Integration Test Suite |
| **Phase 6** | Pending | E2E Test Infrastructure |

See `docs/testing-framework-refactor-plan.md` for full roadmap.

## Contributing

### Test Style Guide

1. **Use descriptive test names:**
   ```bash
   # Good
   @test "format_milestones_list produces TSV with headers"

   # Bad
   @test "test format function"
   ```

2. **Arrange-Act-Assert pattern:**
   ```bash
   @test "function behavior" {
       # Arrange - setup data
       local fixture=$(load_rest_fixture "milestone" "list_all")

       # Act - execute function
       run format_milestones "$fixture"

       # Assert - verify results
       assert_success
       assert_output_contains "TITLE"
   }
   ```

3. **One assertion per test** (when possible)

4. **Use helper functions** (don't duplicate logic)

5. **Clean up in teardown** (especially for E2E)

### Adding New Assertions

Add to `tests/bats-helpers/assertions.bash`:

```bash
# Assert that value is valid {format}
# Usage: assert_valid_{format} VALUE
assert_valid_semver() {
    local value="$1"

    if ! echo "$value" | grep -qE '^v?[0-9]+\.[0-9]+\.[0-9]+'; then
        echo "Invalid semantic version: $value"
        return 1
    fi
}
```

## Related Documentation

- **Testing Plan:** `docs/testing-framework-refactor-plan.md`
- **Architecture:** `knowledge/architecture-principles.md`
- **Domain Libraries:** `lib/github/gh-*-functions.sh`
- **Issue Tracking:** #23-#26 (Testing framework phases)
