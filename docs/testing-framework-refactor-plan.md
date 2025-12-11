# Testing Framework Refactor Plan

> **Status:** Planning
> **Created:** 2024-12-11
> **Updated:** 2024-12-11 (Restructured to share resource management between fixtures and E2E)
> **Related Issues:** #23-#29

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
├── lib/                          # SHARED TEST LIBRARIES
│   └── resources/                # Resource management (used by fixtures AND e2e)
│       ├── core.bash             # Track/cleanup utilities
│       ├── milestone.bash        # create_milestone, delete_milestone
│       ├── issue.bash            # create_issue, close_issue, delete_issue
│       ├── pr.bash               # create_pr, close_pr
│       ├── release.bash          # create_release, delete_release
│       ├── protection.bash       # create_ruleset, delete_ruleset
│       ├── variable.bash         # create_variable, delete_variable
│       └── project.bash          # create_project_item, delete_project_item
│
├── fixtures/                     # CENTRALIZED fixture library
│   ├── scripts/
│   │   ├── record_fixtures.bash  # Main recorder (uses lib/resources/)
│   │   ├── sanitize_fixture.bash # Data sanitization
│   │   └── detect_drift.bash     # Schema drift detection
│   ├── recording_manifest.yaml   # What to record, setup/teardown refs
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
│   └── _synthetic/               # Hand-crafted edge cases
│       ├── errors/
│       └── empty/
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
    ├── sandbox.bash              # Setup/teardown orchestrator (uses lib/resources/)
    ├── domain/                   # Per-domain live tests
    └── smoke/                    # Basic connectivity tests
```

**Key Design Decision:** The `tests/lib/resources/` library is shared between fixture recording and E2E testing. Both need to create/delete GitHub resources - this eliminates duplication.

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

### Phase 2: Test Data Infrastructure

**Objective:** Create shared resource management AND fixture recording infrastructure. This phase has two parts that build on each other.

**Why Combined?**

Fixture recording and E2E testing both need to create/delete GitHub resources. By building resource management first, we:
- Eliminate duplicate code between fixture recording and E2E
- Ensure consistent resource lifecycle handling
- Create deterministic, reproducible fixtures via setup/teardown

---

#### Part A: Resource Management Library

**Objective:** Create reusable scripts for creating/deleting GitHub resources.

**Deliverables:**
1. `tests/lib/resources/` library
2. CRUD operations for all domain resources
3. Resource tracking and cleanup utilities

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 2A.1 | Create `tests/lib/resources/` directory structure | 15 min |
| 2A.2 | Implement `core.bash` - tracking, cleanup, error handling | 2 hrs |
| 2A.3 | Implement `milestone.bash` - create/delete milestones | 1 hr |
| 2A.4 | Implement `issue.bash` - create/close/delete issues | 1.5 hrs |
| 2A.5 | Implement `pr.bash` - create/close PRs | 1.5 hrs |
| 2A.6 | Implement `release.bash` - create/delete releases | 1 hr |
| 2A.7 | Implement `protection.bash` - create/delete rulesets | 1.5 hrs |
| 2A.8 | Implement `variable.bash` - create/delete variables | 1 hr |
| 2A.9 | Implement `project.bash` - create/delete project items | 1 hr |
| 2A.10 | Implement `label.bash` - create/delete labels | 30 min |
| 2A.11 | Write tests for resource library | 2 hrs |
| 2A.12 | Document resource library usage | 1 hr |

**Resource Library Architecture:**
```bash
# tests/lib/resources/core.bash

# Global tracking array
declare -g TRACKED_RESOURCES=""

# Track a resource for cleanup
track_resource() {
    local type="$1"    # milestone, issue, pr, etc.
    local id="$2"      # Resource identifier
    TRACKED_RESOURCES+="$type:$id "
}

# Cleanup all tracked resources (call in teardown)
cleanup_tracked_resources() {
    for resource in $TRACKED_RESOURCES; do
        local type="${resource%%:*}"
        local id="${resource#*:}"
        "delete_${type}" "$id" 2>/dev/null || true
    done
    TRACKED_RESOURCES=""
}

# Trap for cleanup on failure
setup_cleanup_trap() {
    trap 'cleanup_tracked_resources' EXIT ERR
}
```

```bash
# tests/lib/resources/milestone.bash
source "$(dirname "${BASH_SOURCE[0]}")/core.bash"

create_milestone() {
    local owner="$1" repo="$2" title="$3"
    local result=$(gh api "repos/$owner/$repo/milestones" \
        -f title="$title" -f state="open")
    local number=$(echo "$result" | jq -r '.number')
    track_resource "milestone" "$owner/$repo/$number"
    echo "$number"
}

delete_milestone() {
    local ref="$1"  # owner/repo/number
    local owner="${ref%%/*}"
    local rest="${ref#*/}"
    local repo="${rest%%/*}"
    local number="${rest#*/}"
    gh api -X DELETE "repos/$owner/$repo/milestones/$number" 2>/dev/null || true
}
```

**Acceptance Criteria (Part A):**
- [ ] All resource types have create/delete functions
- [ ] Resources are automatically tracked for cleanup
- [ ] Cleanup handles partial failures gracefully
- [ ] Library has its own test suite

---

#### Part B: Fixture Recording System

**Objective:** Record fixtures from live APIs using the resource library for setup/teardown.

**Why Record From Live APIs?**

Hand-crafted fixtures test against **assumptions** about the API, not reality. If our assumptions are wrong (missing fields, different structures, schema changes), tests pass but production fails.

**Deliverables:**
1. Fixture recording scripts (using Part A)
2. Sanitization pipeline
3. Drift detection
4. Fixtures for all 11 domains

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 2B.1 | Create fixture directory structure | 30 min |
| 2B.2 | Implement `record_fixtures.bash` (uses lib/resources/) | 3 hrs |
| 2B.3 | Implement `sanitize_fixture.bash` pipeline | 2 hrs |
| 2B.4 | Implement `detect_drift.bash` | 2 hrs |
| 2B.5 | Create `recording_manifest.yaml` with setup/teardown refs | 2 hrs |
| 2B.6 | Migrate existing fixtures to new location | 1 hr |
| 2B.7 | Record fixtures for Identity domain | 1 hr |
| 2B.8 | Record fixtures for Repository domain | 1 hr |
| 2B.9 | Record fixtures for Milestone domain | 1 hr |
| 2B.10 | Record fixtures for Issue domain | 1 hr |
| 2B.11 | Record fixtures for PR domain | 1 hr |
| 2B.12 | Record fixtures for Project domain | 1 hr |
| 2B.13 | Record fixtures for Protection domain | 1 hr |
| 2B.14 | Record fixtures for Action domain | 1 hr |
| 2B.15 | Record fixtures for Secret domain | 1 hr |
| 2B.16 | Record fixtures for Variable domain | 1 hr |
| 2B.17 | Record fixtures for Release domain | 1 hr |
| 2B.18 | Create synthetic edge case fixtures | 2 hrs |
| 2B.19 | Add CI workflow for weekly drift detection | 1 hr |
| 2B.20 | Document fixture recording process | 1 hr |

**Recording Manifest with Setup/Teardown:**
```yaml
# fixtures/recording_manifest.yaml
fixtures:
  milestone:
    list_populated:
      type: rest
      endpoint: "/repos/{owner}/{repo}/milestones?state=all"
      setup:
        - resource: milestone
          params: { title: "Test Milestone v1.0", state: "open" }
        - resource: milestone
          params: { title: "Test Milestone v2.0", state: "closed" }
      # teardown is automatic via tracked resources

    list_empty:
      type: rest
      endpoint: "/repos/{owner}/{repo}/milestones?state=all"
      setup:
        - action: ensure_empty
          resource: milestone
      # Ensures no milestones exist before recording
```

**Recording Flow:**
```bash
# fixtures/scripts/record_fixtures.bash
source "../../lib/resources/core.bash"
source "../../lib/resources/milestone.bash"
# ... source all resource libraries

record_fixture() {
    local domain="$1" fixture="$2"

    # Setup cleanup trap
    setup_cleanup_trap

    # Run setup from manifest
    run_setup "$domain" "$fixture"

    # Record API response
    local response=$(execute_api_call "$domain" "$fixture")

    # Cleanup happens automatically via trap

    # Sanitize and save
    echo "$response" | sanitize_fixture "$domain" > "fixtures/$domain/$fixture.json"
}
```

**Acceptance Criteria (Part B):**
- [ ] All domain fixtures recorded from live APIs
- [ ] Setup creates precise test state before recording
- [ ] Teardown cleans up automatically (via Part A)
- [ ] Sanitization removes all sensitive data
- [ ] Drift detection catches schema changes
- [ ] Re-recording produces identical fixtures

**Dependencies:** Phase 1, Part A must complete before Part B

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

**Objective:** Create reliable E2E testing by leveraging the shared resource management from Phase 2.

**Key Design Decision:** This phase **reuses** the `tests/lib/resources/` library built in Phase 2. No duplicate resource management code is needed.

**Deliverables:**
1. Sandbox orchestrator (using Phase 2 resource library)
2. E2E tests for critical paths
3. CI workflow integration

**Tasks:**

| Task | Description | Estimate |
|------|-------------|----------|
| 6.1 | Create `e2e/sandbox.bash` orchestrator (uses lib/resources/) | 2 hrs |
| 6.2 | Create `e2e/smoke/` connectivity tests | 1 hr |
| 6.3 | E2E: Milestone CRUD cycle | 1.5 hrs |
| 6.4 | E2E: Issue lifecycle | 1.5 hrs |
| 6.5 | E2E: PR operations | 1.5 hrs |
| 6.6 | E2E: Project item management | 1.5 hrs |
| 6.7 | E2E: Protection rule application | 1.5 hrs |
| 6.8 | E2E: Variable CRUD cycle | 1 hr |
| 6.9 | E2E: Release creation | 1.5 hrs |
| 6.10 | Update CI workflow for E2E | 2 hrs |
| 6.11 | Configure test environment variables | 1 hr |
| 6.12 | Document E2E test requirements | 1 hr |

**Sandbox Using Shared Resources:**
```bash
# tests/e2e/sandbox.bash
# Reuses the resource library from Phase 2!

source "../lib/resources/core.bash"
source "../lib/resources/milestone.bash"
source "../lib/resources/issue.bash"
source "../lib/resources/pr.bash"
source "../lib/resources/release.bash"
source "../lib/resources/protection.bash"
source "../lib/resources/variable.bash"

# Sandbox setup - creates test resources
setup_sandbox() {
    setup_cleanup_trap  # From core.bash - cleanup on exit/error

    # Create resources using Phase 2 functions
    export TEST_MILESTONE=$(create_milestone "$TEST_ORG" "$TEST_REPO" "E2E Test Milestone")
    export TEST_ISSUE=$(create_issue "$TEST_ORG" "$TEST_REPO" "E2E Test Issue")
    export TEST_LABEL=$(create_label "$TEST_ORG" "$TEST_REPO" "e2e-test")

    echo "Sandbox ready: milestone=$TEST_MILESTONE, issue=$TEST_ISSUE"
}

# Sandbox teardown - automatic via cleanup_tracked_resources()
teardown_sandbox() {
    cleanup_tracked_resources  # From core.bash
}
```

**E2E Test Pattern:**
```bash
#!/usr/bin/env bats
# tests/e2e/domain/test_milestone_e2e.bats

setup_file() {
    source "../sandbox.bash"
    setup_sandbox
}

teardown_file() {
    teardown_sandbox
}

@test "milestone: create and fetch roundtrip" {
    source "../../lib/github/gh-milestone-functions.sh"

    # Create via our functions
    local number=$(create_milestone "$TEST_ORG" "$TEST_REPO" "Roundtrip Test")

    # Fetch and verify
    run fetch_milestone "$TEST_ORG" "$TEST_REPO" "$number"
    assert_success
    assert_output --partial "Roundtrip Test"
}
```

**What's NOT Needed (thanks to Phase 2):**
- ❌ `sandbox/resources.bash` - Use `lib/resources/*.bash` instead
- ❌ `create_test_milestone()` - Use `create_milestone()` from Phase 2
- ❌ `cleanup_sandbox()` - Use `cleanup_tracked_resources()` from Phase 2
- ❌ Resource tracking logic - Already in `lib/resources/core.bash`

**Acceptance Criteria:**
- [ ] E2E tests use Phase 2 resource library (no duplication)
- [ ] Sandbox setup/teardown is reliable
- [ ] No orphaned resources after test runs
- [ ] E2E tests cover critical user journeys
- [ ] CI runs E2E on main branch only
- [ ] Test environment documented

**Dependencies:** Phase 2 (resource library), Phase 5

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
| Phase 2A: Resource Management | 2 days | Phase 1 |
| Phase 2B: Fixture Recording | 3 days | Phase 2A |
| Phase 3: Mock System | 2 days | Phase 2B |
| Phase 4: Unit Tests | 3 days | Phase 1, 2B |
| Phase 5: Integration | 4 days | Phase 3, 4 |
| Phase 6: E2E | 2 days | Phase 2A, Phase 5 |
| **Total** | **~17 days** | |

**Note:** Phase 6 duration reduced from 3→2 days because it reuses Phase 2A's resource management library instead of building its own.

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
