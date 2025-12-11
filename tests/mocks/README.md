# Enhanced Mock System

> **Registry-based gh CLI mocking for integration tests**
> **Status:** Phase 3 Complete

A flexible, maintainable mock system for the `gh` CLI that supports dynamic request routing, response customization, and call tracking.

## Architecture

### Registry Pattern

Instead of hardcoding responses in the mock script, the enhanced system uses a **registry** that maps request patterns to responses:

```
Request → Pattern Match → Fixture/Response → Return
```

**Benefits:**
- ✅ Add responses without modifying mock code
- ✅ Override defaults per-test
- ✅ Track and verify mock calls
- ✅ Support complex patterns
- ✅ Load fixtures automatically

### Components

```
mocks/
├── gh                    # Mock gh executable (routes commands)
├── registry.bash         # Registry implementation
├── defaults/             # Default responses per domain
│   ├── identity.yaml
│   ├── repository.yaml
│   ├── milestone.yaml
│   ├── issue.yaml
│   └── project.yaml
└── README.md            # This file
```

## Quick Start

### Basic Usage

```bash
#!/usr/bin/env bats

setup() {
    load '../test_helper'
    setup_mock_gh  # Activates mock + loads defaults

    # Optional: Add custom responses
    register_mock_graphql "myQuery" "graphql/custom/response.json"
}

teardown() {
    teardown_mock_gh
}

@test "my function uses gh API" {
    run my_function_that_calls_gh

    assert_success
    assert_registry_mock_called "myQuery"
}
```

### Advanced Usage

```bash
setup() {
    load '../test_helper'
    setup_mock_gh

    # Register GraphQL mock
    register_mock_graphql "fetch_org_project" "graphql/project/org_project.json"

    # Register REST mock
    register_mock_rest "repos/owner/repo/milestones" "rest/milestone/list_all.json" "GET"

    # Register inline JSON
    register_mock_json "error_query" "graphql" '{"errors":[{"message":"Not found"}]}'
}

@test "complex workflow" {
    # Function makes multiple API calls
    run complex_workflow

    # Verify both were called
    assert_registry_mock_called "fetch_org_project"
    assert_registry_mock_called "repos/.*/milestones"
}
```

## Default Configurations

The mock automatically loads default responses from `defaults/*.yaml`:

### identity.yaml
```yaml
mocks:
  - pattern: "viewer|ViewerQuery"
    type: "graphql"
    fixture: "graphql/identity/viewer.json"
```

### project.yaml
```yaml
mocks:
  - pattern: "ProjectV2"
    type: "graphql"
    fixture: "graphql/project/org_project.json"
```

### milestone.yaml
```yaml
mocks:
  - pattern: "repos/.*/milestones"
    type: "rest"
    fixture: "rest/milestone/list_all.json"
```

**Defaults are loaded automatically** when `setup_mock_gh` is called.

## API Reference

### Setup/Teardown

#### `setup_mock_gh`
Activates the mock gh CLI and initializes the registry.

```bash
setup() {
    load '../test_helper'
    setup_mock_gh
}
```

**Actions:**
- Prepends `tests/mocks/` to PATH
- Creates temp config directory
- Initializes registry
- Loads default configurations

#### `teardown_mock_gh`
Restores original PATH and cleans up mock state.

```bash
teardown() {
    teardown_mock_gh
}
```

### Registering Responses

#### `register_mock_graphql PATTERN FIXTURE_PATH`
Register a GraphQL response.

```bash
# Pattern can be query name or regex
register_mock_graphql "fetch_org_project" "graphql/project/org_project.json"
register_mock_graphql "viewer|ViewerQuery" "graphql/identity/viewer.json"
```

#### `register_mock_rest ENDPOINT FIXTURE_PATH [METHOD]`
Register a REST API response.

```bash
register_mock_rest "repos/owner/repo/milestones" "rest/milestone/list_all.json" "GET"
register_mock_rest "repos/.*/issues" "rest/issue/list.json"  # Regex pattern
```

#### `register_mock_json PATTERN TYPE JSON_STRING`
Register an inline JSON response.

```bash
register_mock_json "error_query" "graphql" '{"errors":[{"message":"Error"}]}'
register_mock_json "repos/test/repo" "rest" '{"name":"test-repo","private":false}'
```

### Verification

#### `assert_registry_mock_called PATTERN [MIN_COUNT]`
Assert that a mock was called.

```bash
@test "function calls API" {
    run my_function

    # Assert called at least once
    assert_registry_mock_called "fetch_org_project"

    # Assert called at least N times
    assert_registry_mock_called "repos/.*/milestones" 3
}
```

### Management

#### `clear_mocks`
Clear all registered mocks (keeps defaults).

```bash
@test "test 1" {
    register_mock_graphql "custom" "fixture.json"
    # ... test code ...
}

@test "test 2" {
    clear_mocks  # Start fresh
    register_mock_graphql "different" "other.json"
}
```

#### `load_mock_config_file PATH`
Load mocks from a YAML configuration file.

```bash
setup() {
    load '../test_helper'
    setup_mock_gh
    load_mock_config_file "tests/mocks/custom_config.yaml"
}
```

#### `print_mock_registry`
Debug: Print current registry state and call log.

```bash
@test "debug test" {
    register_mock_graphql "test" "fixture.json"
    run my_function
    print_mock_registry  # See what was registered and called
}
```

## Pattern Matching

Patterns support regex for flexible matching:

### Exact Match
```bash
register_mock_rest "repos/owner/repo/milestones" "fixture.json"
# Matches: repos/owner/repo/milestones
# Doesn't match: repos/other/repo/milestones
```

### Regex Pattern
```bash
register_mock_rest "repos/.*/milestones" "fixture.json"
# Matches: repos/ANY/repo/milestones
# Matches: repos/owner/repo/milestones
```

### GraphQL Query Patterns
```bash
# By query name
register_mock_graphql "fetch_org_project" "fixture.json"

# By query content
register_mock_graphql "ProjectV2.*items" "fixture.json"

# Multiple patterns (OR)
register_mock_graphql "viewer|ViewerQuery" "fixture.json"
```

## Creating Custom Defaults

Add domain-specific defaults in `defaults/{domain}.yaml`:

```yaml
# defaults/custom.yaml
mocks:
  # GraphQL mock
  - pattern: "myQuery"
    type: "graphql"
    fixture: "graphql/custom/response.json"

  # REST mock with regex
  - pattern: "repos/.*/custom"
    type: "rest"
    fixture: "rest/custom/list.json"

  # CLI command mock
  - pattern: "custom command"
    type: "cli"
    fixture: "_synthetic/empty/empty_array.json"
```

The mock will load this automatically on setup.

## How It Works

### Request Flow

1. **Test calls gh command:**
   ```bash
   gh api graphql -f query='{ viewer { login } }'
   ```

2. **Mock gh routes to registry:**
   - Determines request type (GraphQL, REST, CLI)
   - Extracts pattern (query name, endpoint)

3. **Registry searches for match:**
   - Checks registered patterns (test-specific)
   - Checks default patterns (from defaults/)
   - Returns first match

4. **Response returned:**
   - If fixture path → load and return file
   - If inline JSON → return directly
   - If no match → error

5. **Call logged:**
   - Timestamp, type, pattern logged
   - Available for verification

### Example Flow

```
gh api repos/owner/repo/milestones
  ↓
Mock gh executable
  ↓
handle_rest_request("GET", "repos/owner/repo/milestones")
  ↓
find_mock_response("rest", "repos/owner/repo/milestones")
  ↓
Pattern match: "repos/.*/milestones"
  ↓
Load fixture: rest/milestone/list_all.json
  ↓
Return to test
```

## Backward Compatibility

Old mock system functions still work:

```bash
# Old way (still works)
mock_response "pattern" "fixture.json"
mock_graphql_response "query" "fixture.json"
assert_mock_called "pattern"

# New way (preferred)
register_mock_rest "pattern" "fixture.json"
register_mock_graphql "query" "fixture.json"
assert_registry_mock_called "pattern"
```

The mock automatically detects which system is available and adapts.

## Troubleshooting

### "No mock registered for..."

**Cause:** No pattern matched the request.

**Solution:**
1. Check pattern syntax (regex?)
2. Print registry: `print_mock_registry`
3. Add explicit mock:
   ```bash
   register_mock_graphql "exact_query_name" "fixture.json"
   ```

### "Mock fixture not found"

**Cause:** Fixture path is incorrect.

**Solution:**
Paths are relative to `tests/fixtures/`:
```bash
# Correct
register_mock_graphql "viewer" "graphql/identity/viewer.json"

# Wrong (don't include tests/fixtures/)
register_mock_graphql "viewer" "tests/fixtures/graphql/identity/viewer.json"
```

### Mock not being called

**Cause:** Mock not in PATH or old gh being used.

**Solution:**
```bash
@test "verify mock active" {
    run which gh
    assert_output --partial "tests/mocks/gh"
}
```

### Pattern not matching

**Cause:** Regex escaping or pattern too specific.

**Solution:**
Use `print_mock_registry` to debug, or use broader patterns:
```bash
# Too specific
register_mock_rest "repos/exact/name/milestones?state=all&page=1" "fixture.json"

# Better (regex)
register_mock_rest "repos/.*/milestones" "fixture.json"
```

## Best Practices

1. **Use defaults for common responses**
   - Add to `defaults/{domain}.yaml`
   - Avoid duplicating in every test

2. **Override only what you need**
   ```bash
   setup() {
       setup_mock_gh  # Loads defaults
       # Only override specific responses
       register_mock_graphql "special_case" "custom.json"
   }
   ```

3. **Use regex patterns for flexibility**
   ```bash
   # Matches any repo/milestone combination
   register_mock_rest "repos/.*/milestones" "fixture.json"
   ```

4. **Verify mock calls in tests**
   ```bash
   @test "function makes API call" {
       run my_function
       assert_registry_mock_called "expected_pattern"
   }
   ```

5. **Clear mocks between independent tests**
   ```bash
   @test "test 1" {
       register_mock_graphql "test1" "fixture1.json"
       clear_mocks  # Clean slate for next test
   }
   ```

6. **Use inline JSON for simple responses**
   ```bash
   # No need for fixture file
   register_mock_json "simple" "rest" '{"status":"ok"}'
   ```

## Examples

### Test with Multiple API Calls

```bash
@test "complex workflow with multiple APIs" {
    setup_mock_gh

    # Register all needed mocks
    register_mock_graphql "viewer" "graphql/identity/viewer.json"
    register_mock_rest "repos/.*/milestones" "rest/milestone/list_all.json"
    register_mock_graphql "ProjectV2" "graphql/project/org_project.json"

    # Run function
    run complex_function

    # Verify all were called
    assert_success
    assert_registry_mock_called "viewer"
    assert_registry_mock_called "repos/.*/milestones"
    assert_registry_mock_called "ProjectV2"
}
```

### Test Error Handling

```bash
@test "handles API errors gracefully" {
    setup_mock_gh

    # Register error response
    register_mock_json "fetch_project" "graphql" '{"errors":[{"message":"Not found"}]}'

    # Function should handle error
    run my_function_with_error_handling

    assert_failure
    assert_output --partial "Project not found"
}
```

### Test with Custom Config

```bash
@test "load custom mock configuration" {
    setup_mock_gh
    load_mock_config_file "tests/mocks/custom_scenario.yaml"

    run scenario_function

    assert_success
}
```

## Related Documentation

- **Phase 3 Plan:** `../../docs/testing-framework-refactor-plan.md`
- **Test Helpers:** `../bats-helpers/mocks.bash`
- **Fixtures:** `../fixtures/README.md`
- **Test README:** `../README.md`

## Summary

The enhanced mock system provides:

- ✅ **Registry-based routing** - Dynamic request matching
- ✅ **Default configurations** - Auto-loaded per domain
- ✅ **Pattern matching** - Regex support for flexibility
- ✅ **Call tracking** - Verify mocks were used
- ✅ **Fixture integration** - Auto-loads from centralized fixtures
- ✅ **Backward compatible** - Old functions still work
- ✅ **Easy customization** - Override defaults per-test
- ✅ **Debugging tools** - Print registry state

Use it to write maintainable, reliable integration tests!
