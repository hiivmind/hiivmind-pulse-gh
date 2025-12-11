# Testing Framework Refactor Plan

> **Status:** Planning
> **Created:** 2024-12-11
> **Related Issues:** #21-#26 (to be created)

## Executive Summary

This document outlines a comprehensive plan to refactor the hiivmind-pulse-gh testing framework to align with the domain-based architecture. The refactor addresses fixture management, mock complexity, domain coverage, and E2E resource lifecycle challenges.

---

## Current State

### What Exists

```
tests/
├── test_helper.bash              # Basic assertions
├── unit/
│   ├── fixtures/                 # Project-specific fixtures
│   └── test_jq_filters.bats      # Project jq filter tests
├── integration/
│   ├── fixtures/                 # Separate fixture copies
│   ├── mocks/gh                  # Simple pattern-matching mock
│   ├── test_fetch_functions.bats
│   └── test_rest_functions.bats
└── e2e/
    └── test_live_api.bats        # Live API tests (Project only)
```

### Gaps Identified

| Gap | Impact | Priority |
|-----|--------|----------|
| Only Project domain has tests | 90% of code untested | Critical |
| Fixtures duplicated/scattered | Maintenance burden | High |
| Mock `gh` too simplistic | Can't test complex flows | High |
| No E2E resource management | Tests leave orphaned data | Medium |
| No cross-domain testing | Integration bugs missed | Medium |

---

## Target State

### Proposed Structure

```
tests/
├── test_helper.bash              # Enhanced base helper
├── bats-helpers/                 # Modular helper library
│   ├── assertions.bash           # JSON/API assertions
│   ├── fixtures.bash             # Fixture loading utilities
│   └── mocks.bash                # Mock setup utilities
│
├── fixtures/                     # CENTRALIZED fixture library
│   ├── graphql/                  # GraphQL response fixtures
│   │   ├── identity/
│   │   ├── repository/
│   │   ├── project/
│   │   ├── issue/
│   │   ├── pr/
│   │   └── release/
│   ├── rest/                     # REST response fixtures
│   │   ├── milestone/
│   │   ├── protection/
│   │   ├── secret/
│   │   ├── variable/
│   │   ├── release/
│   │   └── action/
│   └── generators/               # Fixture generation scripts
│
├── mocks/
│   ├── gh                        # Registry-based mock CLI
│   ├── registry.bash             # Request routing logic
│   └── handlers/                 # Domain-specific handlers
│
├── unit/                         # Pure function tests
│   └── domain/
│       ├── identity/
│       ├── repository/
│       ├── milestone/
│       ├── issue/
│       ├── pr/
│       ├── project/
│       ├── protection/
│       ├── action/
│       ├── secret/
│       ├── variable/
│       └── release/
│
├── integration/                  # Mock-based tests
│   ├── domain/                   # Per-domain function tests
│   └── cross-domain/             # Pipeline composition tests
│
└── e2e/                          # Live API tests
    ├── sandbox/                  # Resource management
    │   ├── setup.bash
    │   ├── teardown.bash
    │   └── resources.bash
    ├── domain/                   # Per-domain live tests
    └── smoke/                    # Basic connectivity tests
```

---

## Implementation Phases

### Phase 1: Foundation & Helper Library

**Objective:** Create the foundational infrastructure for all subsequent phases.

**Deliverables:**
1. Directory restructure
2. Enhanced `test_helper.bash`
3. Modular `bats-helpers/` library
4. Fixture loading conventions

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 1.1 | Create new directory structure | 30 min |
| 1.2 | Create `bats-helpers/assertions.bash` with enhanced JSON assertions | 2 hrs |
| 1.3 | Create `bats-helpers/fixtures.bash` with domain-aware loading | 1 hr |
| 1.4 | Create `bats-helpers/mocks.bash` with mock setup utilities | 1 hr |
| 1.5 | Refactor `test_helper.bash` to use new helpers | 1 hr |
| 1.6 | Document helper usage patterns | 1 hr |

**Acceptance Criteria:**
- [ ] All existing tests pass with new helpers
- [ ] Helper functions have consistent naming (`assert_*`, `load_*`, `setup_*`)
- [ ] Documentation includes usage examples

**Dependencies:** None

---

### Phase 2: Centralized Fixture Library (Live Recording)

**Objective:** Create a single source of truth for test fixtures, **recorded from live GitHub APIs** to ensure they reflect actual API response structures.

**Why Record From Live APIs?**

Hand-crafted fixtures test against **assumptions** about the API, not reality. If our assumptions are wrong (missing fields, different structures, schema changes), tests pass but production fails.

| Approach | Validates |
|----------|-----------|
| Hand-crafted fixtures | Our code handles data we *think* the API returns |
| Recorded fixtures | Our code handles data the API *actually* returns |

**Deliverables:**
1. Centralized `fixtures/` directory
2. Fixture recording system with sanitization
3. Drift detection for schema changes
4. Fixtures for all 11 domains (recorded from live API)
5. Synthetic fixtures for edge cases (errors, empty states)

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 2.1 | Create fixture directory structure (graphql/, rest/, scripts/) | 30 min |
| 2.2 | Implement `scripts/record_fixtures.bash` main recorder | 3 hrs |
| 2.3 | Implement `scripts/sanitize_fixture.bash` pipeline | 2 hrs |
| 2.4 | Implement `scripts/detect_fixture_drift.bash` | 2 hrs |
| 2.5 | Create `recording_manifest.yaml` configuration | 1 hr |
| 2.6 | Migrate existing fixtures to new location | 1 hr |
| 2.7 | Record fixtures for Identity domain | 1 hr |
| 2.8 | Record fixtures for Repository domain | 1 hr |
| 2.9 | Record fixtures for Milestone domain | 1 hr |
| 2.10 | Record fixtures for Issue domain | 1 hr |
| 2.11 | Record fixtures for PR domain | 1 hr |
| 2.12 | Record fixtures for Project domain | 1 hr |
| 2.13 | Record fixtures for Protection domain | 1 hr |
| 2.14 | Record fixtures for Action domain | 1 hr |
| 2.15 | Record fixtures for Secret domain | 1 hr |
| 2.16 | Record fixtures for Variable domain | 1 hr |
| 2.17 | Record fixtures for Release domain | 1 hr |
| 2.18 | Create synthetic edge case fixtures (empty, nulls, errors) | 2 hrs |
| 2.19 | Add CI workflow for weekly drift detection | 1 hr |
| 2.20 | Document fixture recording process | 1 hr |

**Recording & Sanitization:**
```bash
# Record a fixture from live API
./scripts/record_fixtures.bash identity viewer

# Sanitization removes sensitive data while preserving structure:
# - Usernames → "test-user"
# - Node IDs → deterministic fake IDs
# - Emails → "test@example.com"
# - Timestamps → normalized values
```

**Drift Detection:**
```bash
# Run periodically to detect API schema changes
./scripts/detect_fixture_drift.bash --all
# Output: "WARNING: milestone/list.json has new field 'due_on_timestamp'"
```

**Fixture Naming Convention:**
```
{domain}/{operation}[_{variant}].json

Examples:
milestone/list_all.json        # Recorded from live API
milestone/list_open.json       # Recorded from live API
_synthetic/empty/array.json    # Hand-crafted (clearly marked)
_synthetic/errors/404.json     # Hand-crafted (clearly marked)
```

**Acceptance Criteria:**
- [ ] All domain fixtures recorded from live APIs
- [ ] Sanitization removes all sensitive data
- [ ] Drift detection catches schema changes
- [ ] Synthetic fixtures clearly separated and documented
- [ ] CI runs weekly drift detection
- [ ] Old fixture locations removed

**Dependencies:** Phase 1

---

### Phase 3: Enhanced Mock System

**Objective:** Create a flexible, maintainable mock `gh` CLI.

**Deliverables:**
1. Registry-based mock `gh` executable
2. Domain-specific request handlers
3. Mock configuration system
4. Error simulation support

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 3.1 | Design mock registry architecture | 1 hr |
| 3.2 | Implement `mocks/gh` main entrypoint | 2 hrs |
| 3.3 | Implement `mocks/registry.bash` request router | 3 hrs |
| 3.4 | Create handler: Identity domain | 1 hr |
| 3.5 | Create handler: Repository domain | 1 hr |
| 3.6 | Create handler: Milestone domain | 1 hr |
| 3.7 | Create handler: Issue domain | 1 hr |
| 3.8 | Create handler: PR domain | 1 hr |
| 3.9 | Create handler: Project domain | 1 hr |
| 3.10 | Create handler: Protection domain | 1 hr |
| 3.11 | Create handler: Action domain | 1 hr |
| 3.12 | Create handler: Secret/Variable domain | 1 hr |
| 3.13 | Create handler: Release domain | 1 hr |
| 3.14 | Implement error simulation mode | 2 hrs |
| 3.15 | Create mock test suite (test the mock itself) | 2 hrs |
| 3.16 | Document mock usage and extension | 1 hr |

**Mock Architecture:**
```bash
# mocks/gh - Main entrypoint
#!/bin/bash
source "$(dirname "$0")/registry.bash"

case "$1" in
    api)
        if [[ "$2" == "graphql" ]]; then
            route_graphql "${@:3}"
        else
            route_rest "${@:2}"
        fi
        ;;
    secret|variable)
        route_cli_command "$@"
        ;;
    auth)
        route_auth_command "$@"
        ;;
    *)
        route_misc_command "$@"
        ;;
esac
```

**Acceptance Criteria:**
- [ ] Mock handles all current integration test scenarios
- [ ] New handlers can be added without modifying core
- [ ] Error responses can be triggered for testing
- [ ] Mock has its own test suite
- [ ] Documented extension pattern

**Dependencies:** Phase 2 (needs fixtures)

---

### Phase 4: Unit Test Suite

**Objective:** Comprehensive unit tests for all domain jq filters and pure functions.

**Deliverables:**
1. Unit tests for all 11 domains
2. Coverage of all jq filters
3. Edge case testing
4. Test templates for consistency

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 4.1 | Create unit test template | 1 hr |
| 4.2 | Unit tests: Identity domain filters | 2 hrs |
| 4.3 | Unit tests: Repository domain filters | 2 hrs |
| 4.4 | Unit tests: Milestone domain filters | 2 hrs |
| 4.5 | Unit tests: Issue domain filters | 2 hrs |
| 4.6 | Unit tests: PR domain filters | 2 hrs |
| 4.7 | Unit tests: Project domain filters (migrate existing) | 2 hrs |
| 4.8 | Unit tests: Protection domain filters | 2 hrs |
| 4.9 | Unit tests: Action domain filters | 2 hrs |
| 4.10 | Unit tests: Secret domain filters | 1 hr |
| 4.11 | Unit tests: Variable domain filters | 1 hr |
| 4.12 | Unit tests: Release domain filters | 2 hrs |
| 4.13 | Add null/empty handling tests per domain | 3 hrs |
| 4.14 | Document test patterns | 1 hr |

**Test Template:**
```bash
#!/usr/bin/env bats
# Unit tests for {domain} jq filters

setup() {
    load '../../../test_helper'
    load '../../../bats-helpers/assertions'
    load '../../../bats-helpers/fixtures'

    DOMAIN="{domain}"
    FILTERS_FILE="gh-{domain}-jq-filters.yaml"
}

# =============================================================================
# Format Filters
# =============================================================================

@test "{domain}: format_{entity} produces valid output" {
    local fixture=$(load_fixture "$DOMAIN" "list_all")
    local filter=$(get_filter "$FILTERS_FILE" ".filters.format_{entity}")

    run jq "$filter" <<< "$fixture"

    assert_success
    assert_valid_json "$output"
}

# ... more tests
```

**Acceptance Criteria:**
- [ ] Every jq filter has at least one test
- [ ] Null/empty handling tested for each filter
- [ ] All tests pass in CI
- [ ] Coverage report shows >80% filter coverage

**Dependencies:** Phase 1, Phase 2

---

### Phase 5: Integration Test Suite

**Objective:** Test domain functions with mocked GitHub API.

**Deliverables:**
1. Integration tests for all domains
2. Cross-domain pipeline tests
3. Error handling tests

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 5.1 | Create integration test template | 1 hr |
| 5.2 | Integration tests: Identity functions | 2 hrs |
| 5.3 | Integration tests: Repository functions | 2 hrs |
| 5.4 | Integration tests: Milestone functions | 2 hrs |
| 5.5 | Integration tests: Issue functions | 2 hrs |
| 5.6 | Integration tests: PR functions | 2 hrs |
| 5.7 | Integration tests: Project functions (migrate) | 2 hrs |
| 5.8 | Integration tests: Protection functions | 3 hrs |
| 5.9 | Integration tests: Action functions | 2 hrs |
| 5.10 | Integration tests: Secret functions | 2 hrs |
| 5.11 | Integration tests: Variable functions | 2 hrs |
| 5.12 | Integration tests: Release functions | 2 hrs |
| 5.13 | Cross-domain: Issue + Milestone pipeline | 2 hrs |
| 5.14 | Cross-domain: PR + Review pipeline | 2 hrs |
| 5.15 | Cross-domain: Release + Asset pipeline | 2 hrs |
| 5.16 | Error handling tests (API failures) | 3 hrs |
| 5.17 | Document integration test patterns | 1 hr |

**Acceptance Criteria:**
- [ ] Every public function has integration test
- [ ] Pipelines tested (fetch | filter | format)
- [ ] Error scenarios tested
- [ ] All tests pass with mock `gh`

**Dependencies:** Phase 3, Phase 4

---

### Phase 6: E2E Test Infrastructure

**Objective:** Create reliable E2E testing with proper resource management.

**Deliverables:**
1. Test sandbox setup/teardown system
2. Resource tracking and cleanup
3. E2E tests for critical paths
4. CI workflow integration

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 6.1 | Design sandbox resource model | 2 hrs |
| 6.2 | Implement `sandbox/setup.bash` | 3 hrs |
| 6.3 | Implement `sandbox/teardown.bash` | 2 hrs |
| 6.4 | Implement `sandbox/resources.bash` helpers | 2 hrs |
| 6.5 | Create smoke tests (connectivity, auth) | 1 hr |
| 6.6 | E2E: Milestone CRUD cycle | 2 hrs |
| 6.7 | E2E: Issue lifecycle | 2 hrs |
| 6.8 | E2E: PR operations | 2 hrs |
| 6.9 | E2E: Project item management | 2 hrs |
| 6.10 | E2E: Protection rule application | 2 hrs |
| 6.11 | E2E: Variable CRUD cycle | 2 hrs |
| 6.12 | E2E: Release creation | 2 hrs |
| 6.13 | Update CI workflow | 2 hrs |
| 6.14 | Configure test environment variables | 1 hr |
| 6.15 | Document E2E test requirements | 1 hr |

**Sandbox Resource Model:**
```bash
# sandbox/resources.bash

# Track created resources for cleanup
declare -A SANDBOX_RESOURCES=(
    [milestones]=""
    [issues]=""
    [labels]=""
    [releases]=""
    [rulesets]=""
    [variables]=""
)

# Create resource and track for cleanup
create_test_milestone() {
    local title="bats-test-$(date +%s)"
    local result=$(gh api "repos/$TEST_ORG/$TEST_REPO/milestones" \
        -f title="$title" -f state="open")

    local number=$(echo "$result" | jq -r '.number')
    SANDBOX_RESOURCES[milestones]+=" $number"

    echo "$number"
}

# Cleanup all tracked resources
cleanup_sandbox() {
    for milestone in ${SANDBOX_RESOURCES[milestones]}; do
        gh api -X DELETE "repos/$TEST_ORG/$TEST_REPO/milestones/$milestone" 2>/dev/null || true
    done
    # ... cleanup other resource types
}
```

**Acceptance Criteria:**
- [ ] Sandbox creates/destroys resources reliably
- [ ] No orphaned resources after test runs
- [ ] E2E tests cover critical user journeys
- [ ] CI runs E2E on main branch only
- [ ] Test environment documented

**Dependencies:** Phase 5

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Fixture recording fails for some endpoints | Medium | Medium | Manual fixture creation fallback, document in _synthetic/ |
| API rate limits during fixture recording | Low | Low | Use authenticated requests, record in batches |
| Sanitization misses sensitive data | Medium | High | Review sanitization rules, use allowlist approach |
| Drift detection false positives | Medium | Low | Ignore non-structural changes (timestamps, counts) |
| Mock complexity exceeds maintainability | Low | High | Regular mock refactoring reviews |
| E2E tests flaky due to API timing | Medium | Medium | Retry logic, longer timeouts |
| CI secrets misconfigured | Low | High | Document setup, use repository variables |
| Breaking changes during refactor | Medium | High | Run old tests until new ones verified |

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Domain test coverage | 1/11 (9%) | 11/11 (100%) |
| jq filter test coverage | ~30% | >80% |
| Integration test count | ~15 | >100 |
| E2E test scenarios | 5 | >20 |
| CI pipeline time | ~2 min | <5 min |

---

## Timeline Overview

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Foundation | 1 day | None |
| Phase 2: Fixtures (Live Recording) | 3 days | Phase 1 |
| Phase 3: Mock System | 2 days | Phase 2 |
| Phase 4: Unit Tests | 3 days | Phase 1, 2 |
| Phase 5: Integration | 4 days | Phase 3, 4 |
| Phase 6: E2E | 3 days | Phase 5 |
| **Total** | **~16 days** | |

---

## Appendix A: Fixture Categories by Domain

### GraphQL Fixtures Needed

| Domain | Fixtures |
|--------|----------|
| Identity | viewer, user, organization, viewer_with_orgs |
| Repository | repo, user_repos, org_repos, branches |
| Project | org_project, user_project, project_items, fields |
| Issue | issue, repo_issues, issue_with_comments |
| PR | pr, repo_prs, pr_with_reviews |
| Release | release_by_tag, latest_release, release_assets |

### REST Fixtures Needed

| Domain | Fixtures |
|--------|----------|
| Milestone | list, get, create_response, update_response |
| Protection | branch_protection, rulesets, ruleset_detail |
| Action | workflows, runs, jobs, run_detail |
| Secret | public_key, list_secrets, repo_access |
| Variable | list_variables, get_variable |
| Release | list, get, assets, generate_notes |

---

## Appendix B: CI Environment Variables

```yaml
# Repository Variables (non-sensitive)
TEST_ORG: "hiivmind"           # Organization for E2E tests
TEST_REPO: "test-sandbox"       # Repository for E2E tests
TEST_PROJECT_NUMBER: "99"       # Project number for tests

# Repository Secrets (sensitive)
TEST_GITHUB_TOKEN: "ghp_..."    # PAT with required scopes
```

**Required Token Scopes:**
- `repo` - Full repository access
- `read:org` - Organization membership
- `read:project` / `project` - Projects v2 access
- `admin:repo_hook` - For protection tests (optional)
